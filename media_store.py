"""Importação e hospedagem de mídias referenciadas nos CSVs.

Só baixa URLs HTTPS de hosts CDN explicitamente permitidos e já presentes nos CSVs.
Páginas TikTok não são links diretos de mídia e são excluídas do espelhamento.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DAHUER_DATA_DIR", str(BASE_DIR / "data")))
MEDIA_DIR = Path(os.getenv("DAHUER_MEDIA_DIR", str(BASE_DIR / "media")))
CSV_FILES = (
    "hidrabene_shopee.csv",
    "hidrabene_mercadolivre.csv",
    "hidrabene_tiktok.csv",
    "hidrabene_amazon.csv",
)
ALLOWED_DOMAINS = ("susercontent.com", "mlstatic.com", "media-amazon.com")
ID_RE = re.compile(r"^[a-f0-9]{32}$")
MAX_IMAGE_BYTES = int(os.getenv("DAHUER_MAX_IMAGE_MB", "8")) * 1024 * 1024
MAX_VIDEO_BYTES = int(os.getenv("DAHUER_MAX_VIDEO_MB", "48")) * 1024 * 1024
RETRY_SECONDS = 12 * 3600
LOGGER = logging.getLogger("dahuer.media")
_locks_guard = threading.Lock()
_download_locks: dict[str, threading.Lock] = {}
_errors_lock = threading.Lock()
_started_lock = threading.Lock()
_started = False


def split_links(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(" | ") if part.strip()]


def allowed_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        hostname = (parts.hostname or "").lower()
        return (
            parts.scheme == "https"
            and not parts.username
            and not parts.password
            and parts.port in (None, 443)
            and any(hostname == suffix or hostname.endswith("." + suffix) for suffix in ALLOWED_DOMAINS)
        )
    except ValueError:
        return False


def media_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


def media_kind(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.lower()
    if path.endswith((".mp4", ".webm", ".mov")) or ".vod." in host or host.startswith("video-"):
        return "video"
    return "image"


@lru_cache(maxsize=1)
def manifest() -> dict[str, dict[str, str]]:
    mapping = {}
    for filename in CSV_FILES:
        with (DATA_DIR / filename).open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream, delimiter=";"):
                for url in split_links(row.get("midia_links", "")):
                    if allowed_url(url):
                        key = media_key(url)
                        mapping[key] = {"url": url, "tipo": media_kind(url), "canal": row.get("canal", "")}
    return mapping


def local_links(value: str, origin: str) -> tuple[list[str], list[str]]:
    local, unhosted = [], []
    mapping = manifest()
    for url in split_links(value):
        key = media_key(url)
        if key in mapping and mapping[key]["url"] == url:
            local.append(origin.rstrip("/") + "/media/" + key)
        else:
            unhosted.append(url)
    return local, unhosted


def file_path(key: str) -> Path:
    if not ID_RE.fullmatch(key):
        raise ValueError("Identificador de mídia inválido")
    return MEDIA_DIR / key


def present(key: str) -> bool:
    path = file_path(key)
    return path.is_file() and path.stat().st_size > 0


def detect_media(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"avif", b"avis", b"mif1"):
        return "image/avif"
    if head[4:8] == b"ftyp":
        return "video/mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    return None


def content_type(key: str) -> str | None:
    path = file_path(key)
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        return detect_media(stream.read(16))


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError("Redirecionamento para host não permitido")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = build_opener(SafeRedirectHandler)


def _errors_path() -> Path:
    return MEDIA_DIR / ".errors.json"


def get_errors() -> dict:
    try:
        with _errors_path().open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save_error(key: str, message: str) -> None:
    with _errors_lock:
        data = get_errors()
        data[key] = {"timestamp": time.time(), "erro": str(message)[:180]}
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = MEDIA_DIR / (".errors." + str(os.getpid()) + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _errors_path())


def clear_error(key: str) -> None:
    with _errors_lock:
        data = get_errors()
        if key in data:
            del data[key]
            tmp = MEDIA_DIR / (".errors." + str(os.getpid()) + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, _errors_path())


def _fetch(key: str) -> None:
    info = manifest()[key]
    url = info["url"]
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; DahuerComments/1.0; media-cache)",
        "Accept": "image/jpeg,image/png,image/webp,video/mp4,video/webm,*/*;q=0.5",
    })
    limit = MAX_VIDEO_BYTES if info["tipo"] == "video" else MAX_IMAGE_BYTES
    tmp_name = None
    try:
        with _opener.open(request, timeout=25) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > limit:
                raise ValueError("Arquivo excede o limite configurado")
            with tempfile.NamedTemporaryFile(dir=MEDIA_DIR, prefix=".download-", delete=False) as tmp:
                tmp_name = tmp.name
                total = 0
                head = b""
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("Arquivo excede o limite configurado")
                    if len(head) < 16:
                        head = (head + chunk)[:16]
                    tmp.write(chunk)
                detected = detect_media(head)
                if total == 0 or not detected or not detected.startswith(info["tipo"] + "/"):
                    raise ValueError("Resposta não é imagem/vídeo válido")
        os.replace(tmp_name, file_path(key))
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def ensure_downloaded(key: str, *, retry_failed: bool = False) -> bool:
    if key not in manifest():
        return False
    if present(key):
        return True
    with _locks_guard:
        lock = _download_locks.setdefault(key, threading.Lock())
    with lock:
        if present(key):
            return True
        previous = get_errors().get(key)
        if previous and not retry_failed and time.time() - previous.get("timestamp", 0) < RETRY_SECONDS:
            return False
        try:
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            _fetch(key)
            clear_error(key)
            return True
        except (OSError, ValueError, HTTPError, URLError, TimeoutError) as exc:
            LOGGER.warning("Falha ao importar mídia %s: %s", key, exc)
            try:
                save_error(key, str(exc))
            except OSError:
                LOGGER.exception("Impossível gravar falha de importação; confira volume do Easypanel")
            return False


def status() -> dict:
    mapping = manifest()
    errors = get_errors()
    done = [key for key in mapping if present(key)]
    sizes = sum(file_path(key).stat().st_size for key in done)
    total = len(mapping)
    failed = sum(1 for key in mapping if key in errors and key not in done)
    return {
        "total_importaveis": total,
        "baixados": len(done),
        "pendentes": total - len(done),
        "falhas_registradas": failed,
        "bytes_armazenados": sizes,
        "diretorio": str(MEDIA_DIR),
        "importacao_automatica": os.getenv("DAHUER_MEDIA_AUTO_SYNC", "true").lower() in ("1", "true", "yes"),
        "observacao": "Links TikTok para páginas de vídeos não são arquivos diretos e não entram no espelho.",
    }


def sync_all(*, retry_failed: bool = False) -> dict:
    catalog = manifest()
    keys = sorted(catalog, key=lambda key: (catalog[key]["tipo"] == "video", key))
    LOGGER.info("Iniciando importação de %d URLs de mídia para %s", len(keys), MEDIA_DIR)
    for i, key in enumerate(keys, start=1):
        ensure_downloaded(key, retry_failed=retry_failed)
        if i % 25 == 0:
            LOGGER.info("Mídia %d/%d: %s", i, len(keys), status())
        time.sleep(0.12)
    result = status()
    LOGGER.info("Importação de mídia concluída: %s", result)
    return result


def start_auto_sync() -> None:
    global _started
    if os.getenv("DAHUER_MEDIA_AUTO_SYNC", "true").lower() not in ("1", "true", "yes"):
        return
    with _started_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=sync_all, name="dahuer-media-import", daemon=True).start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importa as mídias para o armazenamento local do Dahuer Comments.")
    parser.add_argument("--retry-failed", action="store_true", help="Repete tentativas que falharam")
    parser.add_argument("--status", action="store_true", help="Mostra apenas o progresso")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = status() if args.status else sync_all(retry_failed=args.retry_failed)
    print(json.dumps(result, ensure_ascii=False, indent=2))
