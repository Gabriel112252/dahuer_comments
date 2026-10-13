"""Banco local de avaliações incrementais (volume persistente do Easypanel).

CSV continua sendo o snapshot inicial; este SQLite contém só novos registros.
Não persiste nomes de usuário quando uma plataforma informa que são privados.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("DAHUER_MEDIA_DIR", str(Path(__file__).parent / "media")))
DB_PATH = Path(os.environ.get("DAHUER_REVIEWS_DB", str(ROOT / "reviews.sqlite3")))
FIELDS = ("canal", "produto", "nota", "data", "autor", "texto", "variacao",
          "tem_foto_ou_video", "link", "midia_links", "midia_arquivos")
_LOCK = threading.RLock()
ZONE = ZoneInfo("America/Sao_Paulo")


def normalize_date(raw: str | int | float | None) -> str | None:
    """ISO UTC para datas absolutas; datas relativas ficam sem timestamp."""
    if raw is None or raw == "":
        return None
    try:
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), tz=timezone.utc).isoformat()
        value = str(raw).strip()
        if value.isdigit() and len(value) in (10, 13):
            n = int(value)
            return datetime.fromtimestamp(n / (1000 if len(value) == 13 else 1), tz=timezone.utc).isoformat()
        if "/" in value and len(value) == 10:
            dt = datetime.strptime(value, "%d/%m/%Y").replace(tzinfo=ZONE)
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZONE)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def is_video(row: dict) -> bool:
    import re
    links = (row.get("midia_links") or "")
    return bool(
        re.search(r"(?:\.mp4|\.webm|\.mov)(?:\?|$|\s+\|)|\.vod\.|video-vod-", links, re.I)
        or row.get("canal") == "TikTok" and "tiktok.com/@" in links
        or "vídeo" in (row.get("tem_foto_ou_video") or "").lower()
        or "video" in (row.get("tem_foto_ou_video") or "").lower()
    )


def source_fingerprint(row: dict) -> str:
    return hashlib.sha256("\x1f".join(
        str(row.get(field) or "") for field in ("canal", "produto", "link", "texto")
    ).encode("utf-8")).hexdigest()[:20]


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=20000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            source_key TEXT PRIMARY KEY,
            public_id TEXT UNIQUE NOT NULL,
            source_fingerprint TEXT NOT NULL,
            timestamp_utc TEXT,
            with_video INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_timestamp ON reviews(timestamp_utc DESC)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collector_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            day_local TEXT NOT NULL,
            state TEXT NOT NULL,
            detail TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def insert_reviews(rows: list[dict], known_fingerprints: set[str] | None = None) -> int:
    """Upsert por identificador da plataforma, sem replicar avaliações dos CSVs."""
    if not rows:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with _LOCK, open_db() as db:
        existing = set(known_fingerprints or ())
        existing.update(record[0] for record in db.execute("SELECT source_fingerprint FROM reviews"))
        for row in rows:
            key = str(row.get("source_key") or "").strip()
            if not key or len(key) > 240:
                continue
            row = dict(row)
            canonical = {k: str(row.get(k) or "") for k in FIELDS}
            canonical["nota"] = str(row.get("nota") or "") if row.get("nota") is not None else ""
            fingerprint = source_fingerprint(canonical)
            if fingerprint in existing:
                continue
            timestamp = normalize_date(row.get("timestamp_utc") or canonical["data"])
            pid = "n" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:19]
            payload = {**canonical, "id": pid, "data_iso": timestamp,
                       "fonte_id": key, "com_video": is_video(canonical)}
            cursor = db.execute(
                "INSERT OR IGNORE INTO reviews (source_key,public_id,source_fingerprint,timestamp_utc,with_video,payload,collected_at) VALUES (?,?,?,?,?,?,?)",
                (key, pid, fingerprint, timestamp, int(is_video(canonical)),
                 json.dumps(payload, ensure_ascii=False), now),
            )
            if cursor.rowcount:
                inserted += 1
                existing.add(fingerprint)
        db.commit()
    return inserted


def extra_reviews() -> list[dict]:
    with _LOCK, open_db() as db:
        data = []
        for record in db.execute("SELECT payload FROM reviews"):
            try:
                item = json.loads(record[0])
            except json.JSONDecodeError:
                continue
            item["nota"] = int(item["nota"]) if str(item.get("nota", "")).isdigit() else None
            item["midias"] = [x.strip() for x in item.get("midia_links", "").split(" | ") if x.strip()]
            item["arquivos_midia_referenciados"] = [
                x.strip() for x in item.get("midia_arquivos", "").split(" | ") if x.strip()
            ]
            data.append(item)
        return data


def log_run(state: str, detail: dict, started_at: str) -> None:
    now = datetime.now(timezone.utc)
    with _LOCK, open_db() as db:
        db.execute(
            "INSERT INTO collector_runs (started_at,finished_at,day_local,state,detail) VALUES (?,?,?,?,?)",
            (started_at, now.isoformat(), now.astimezone(ZONE).date().isoformat(),
             state, json.dumps(detail, ensure_ascii=False)),
        )
        db.commit()


def last_run() -> dict | None:
    with _LOCK, open_db() as db:
        record = db.execute(
            "SELECT started_at,finished_at,day_local,state,detail FROM collector_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if record is None:
        return None
    return {
        "inicio": record["started_at"],
        "fim": record["finished_at"],
        "dia_local": record["day_local"],
        "status": record["state"],
        "detalhes": json.loads(record["detail"]),
    }


def count_extra() -> int:
    with _LOCK, open_db() as db:
        return db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
