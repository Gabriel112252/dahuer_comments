"""Coleta incremental diária (03:00 America/Sao_Paulo).

Só usa origens configuradas e APIs documentadas:
* Mercado Livre API oficial, com OAuth e IDs de anúncios (MLB...)
* Shopee via ator externo Apify opcional, com token e limite de custo
Amazon/TikTok: sem coletores habilitados até existir uma fonte autorizada.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import media_store
import review_db

LOG = logging.getLogger("dahuer.collector")
ZONE = ZoneInfo("America/Sao_Paulo")
ROOT = Path(os.environ.get("DAHUER_MEDIA_DIR", str(Path(__file__).parent / "media")))
STOP = threading.Event()
_STARTED_LOCK = threading.Lock()
_STARTED = False
ITEM_ID = re.compile(r"^MLB\d{5,20}$")
SHOP_URL = re.compile(r"^https://shopee\.com\.br/product/(\d{5,20})/(\d{5,20})/?$")
MAX_PER_SOURCE = int(os.getenv("DAHUER_COLLECTOR_MAX_PER_SOURCE", "300"))
DAYS_BACK = max(1, min(30, int(os.getenv("DAHUER_COLLECTOR_DAYS_BACK", "7"))))
DELAY = max(0.2, float(os.getenv("DAHUER_COLLECTOR_DELAY", "1.25")))


def source_shopee_products() -> list[dict]:
    found: dict[str, dict] = {}
    csv_path = Path(os.environ.get("DAHUER_DATA_DIR", str(Path(__file__).parent / "data"))) / "hidrabene_shopee.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            url = (row.get("link") or "").strip()
            match = SHOP_URL.fullmatch(url)
            if match:
                product_id = match.group(2)
                found[product_id] = {
                    "produto": (row.get("produto") or "").strip(),
                    "url": url,
                    "id": product_id,
                }
    return list(found.values())


def ml_items() -> list[dict]:
    """Não confundir IDs de catálogo /p/MLB... com IDs de anúncios /items/MLB..."""
    raw = os.getenv("DAHUER_ML_ITEMS_JSON", "[]")
    values = json.loads(raw)
    if not isinstance(values, list):
        raise ValueError("DAHUER_ML_ITEMS_JSON deve ser uma lista JSON")
    valid = []
    for item in values[:80]:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id", "")).upper().strip()
        product = str(item.get("produto", "")).strip()
        if not ITEM_ID.fullmatch(item_id) or not product:
            LOG.warning("Item ML ignorado: precisa de item_id MLB... e produto existente")
            continue
        valid.append({
            "item_id": item_id,
            "produto": product,
            "catalog_product_id": str(item.get("catalog_product_id", "")).strip(),
            "link": str(item.get("link", "")).strip() or "https://produto.mercadolivre.com.br/" + item_id,
        })
    return valid


def load_json(url: str, *, token: str, post: dict | None = None, timeout: int = 25) -> dict | list:
    if not token:
        raise ValueError("Token não configurado")
    body = json.dumps(post).encode("utf-8") if post is not None else None
    headers = {"Accept": "application/json", "Authorization": "Bearer " + token, "User-Agent": "DahuerReviewsCollector/1.0"}
    if post is not None:
        headers["Content-Type"] = "application/json"
    for attempt in range(3):
        req = Request(url, data=body, headers=headers, method="POST" if post is not None else "GET")
        try:
            with urlopen(req, timeout=timeout) as res:
                if res.headers.get("Content-Length") and int(res.headers["Content-Length"]) > 30_000_000:
                    raise ValueError("Resposta maior que 30MB")
                raw = res.read(30_000_001)
                if len(raw) > 30_000_000:
                    raise ValueError("Resposta maior que 30MB")
                return json.loads(raw)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(min(15, 2 ** attempt + 1))
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt + 1)
    raise RuntimeError("Falha de rede após retentativas")


def str_media(parts: list) -> str:
    cleaned = []
    for item in parts:
        if isinstance(item, dict):
            link = item.get("url") or item.get("src") or item.get("videoUrl") or item.get("playUrl")
        else:
            link = item
        if isinstance(link, str) and link.startswith("https://") and link not in cleaned:
            cleaned.append(link)
    return " | ".join(cleaned[:12])


def from_mercadolivre(item: dict, row: dict) -> dict | None:
    if not isinstance(row, dict) or not row.get("id"):
        return None
    status = row.get("status")
    if status and status != "published":
        return None
    media = row.get("media") or {}
    if not isinstance(media, dict):
        media = {}
    videos = row.get("videos") or media.get("videos") or []
    pictures = row.get("pictures") or row.get("photos") or media.get("pictures") or []
    if not isinstance(videos, list):
        videos = []
    if not isinstance(pictures, list):
        pictures = []
    urls = str_media(videos + pictures)
    text = " ".join(p for p in (row.get("title"), row.get("content")) if isinstance(p, str)).strip()
    date = row.get("date_created") or ""
    return {
        "source_key": "mercadolivre:" + str(row["id"]),
        "canal": "Mercado Livre",
        "produto": item["produto"],
        "nota": row.get("rate") or "",
        "data": date[:10] if date else "",
        "timestamp_utc": date,
        "autor": "Cliente",  # Não expor reviewer_id.
        "texto": text,
        "variacao": "",
        "tem_foto_ou_video": "vídeo" if videos else ("foto" if pictures else ""),
        "link": item["link"],
        "midia_links": urls,
        "midia_arquivos": "",
    }


def run_mercadolivre() -> tuple[list[dict], dict]:
    token = os.getenv("DAHUER_ML_ACCESS_TOKEN", "")
    items = ml_items()
    if not token or not items:
        return [], {"estado": "sem_configuracao", "anuncios": len(items)}
    all_reviews = []
    ok = 0
    errors = []
    for item in items:
        collected = []
        offset = 0
        try:
            while offset < MAX_PER_SOURCE:
                query = {"limit": min(25, MAX_PER_SOURCE - offset), "offset": offset}
                catalog = item["catalog_product_id"]
                if catalog:
                    if not ITEM_ID.fullmatch(catalog):
                        raise ValueError("catalog_product_id inválido")
                    query["catalog_product_id"] = catalog
                url = "https://api.mercadolibre.com/reviews/item/" + item["item_id"] + "?" + urlencode(query)
                payload = load_json(url, token=token)
                if not isinstance(payload, dict):
                    raise ValueError("Resposta ML inesperada")
                reviews = payload.get("reviews", [])
                if not isinstance(reviews, list):
                    raise ValueError("Campo reviews não é lista")
                for row in reviews:
                    normalized = from_mercadolivre(item, row)
                    if normalized:
                        collected.append(normalized)
                offset += len(reviews)
                paging = payload.get("paging") or {}
                max_available = paging.get("total_pageable") or paging.get("total") or 0
                if not reviews or len(reviews) < query["limit"] or offset >= int(max_available):
                    break
                time.sleep(DELAY)
            all_reviews.extend(collected)
            ok += 1
        except (ValueError, HTTPError, URLError, TimeoutError) as exc:
            errors.append({"item_id": item["item_id"], "erro": str(exc)[:120]})
            LOG.warning("ML %s: %s", item["item_id"], exc)
        time.sleep(DELAY)
    return all_reviews, {"estado": "parcial" if errors else "ok", "anuncios": ok, "recebidas": len(all_reviews), "erros": errors}


def from_shopee(row: dict, products: dict[str, dict]) -> dict | None:
    if not isinstance(row, dict) or row.get("type") != "review" or not row.get("reviewId"):
        return None
    pid = str(row.get("productId") or "")
    product = products.get(pid)
    if product is None:
        # Não atribuir avaliações de produtos desconhecidos ao produto errado.
        return None
    images = row.get("imageUrls") if isinstance(row.get("imageUrls"), list) else []
    videos = row.get("videoUrls") if isinstance(row.get("videoUrls"), list) else []
    urls = str_media(videos + images)
    date = str(row.get("createdAt") or "")
    text = row.get("text")
    return {
        "source_key": "shopee:" + str(row["reviewId"]),
        "canal": "Shopee",
        "produto": product["produto"],
        "nota": row.get("rating") or "",
        "data": date[:10] if date else "",
        "timestamp_utc": date,
        "autor": "Cliente" if row.get("isAnonymous") else str(row.get("reviewerName") or "Cliente"),
        "texto": text if isinstance(text, str) else "",
        "variacao": str(row.get("variation") or ""),
        "tem_foto_ou_video": "vídeo" if videos else ("foto" if images else ""),
        "link": product["url"],
        "midia_links": urls,
        "midia_arquivos": "",
    }


def run_shopee() -> tuple[list[dict], dict]:
    token = os.getenv("DAHUER_APIFY_TOKEN", "")
    products = source_shopee_products()
    if not token or not products:
        return [], {"estado": "sem_configuracao", "produtos": len(products)}
    # Serviço externo opcional e cobrado à parte; limitar volume e custo da execução.
    actor = "memo23~shopee-reviews-scraper"
    limit = max(1, min(MAX_PER_SOURCE, 100))
    budget = max(0.1, min(10.0, float(os.getenv("DAHUER_APIFY_MAX_USD", "1.5"))))
    product_map = {p["id"]: p for p in products}
    payload = {
        "startUrls": [p["url"] for p in products],
        "maxReviewsPerShop": limit,
        "reviewsSince": f"{DAYS_BACK} days",
        "onlyWithText": False,
        "onlyWithMedia": False,
        "includeSummary": False,
    }
    endpoint = ("https://api.apify.com/v2/acts/" + actor +
                "/run-sync-get-dataset-items?" + urlencode({"maxTotalChargeUsd": budget}))
    try:
        items = load_json(endpoint, token=token, post=payload, timeout=300)
        if not isinstance(items, list):
            raise ValueError("Ator Apify não retornou dataset JSON")
        rows = [normal for entry in items if (normal := from_shopee(entry, product_map))]
        return rows, {"estado": "ok", "produtos": len(products), "recebidas": len(rows),
                      "limite_por_produto": limit, "orcamento_usd": budget}
    except (ValueError, HTTPError, URLError, TimeoutError) as exc:
        LOG.warning("Shopee/Apify: %s", exc)
        return [], {"estado": "erro", "erro": str(exc)[:180], "produtos": len(products)}


def base_fingerprints() -> set[str]:
    from review_db import source_fingerprint
    data_path = Path(os.environ.get("DAHUER_DATA_DIR", str(Path(__file__).parent / "data")))
    result = set()
    for name in media_store.CSV_FILES:
        with (data_path / name).open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream, delimiter=";"):
                result.add(source_fingerprint(row))
    return result


def collect_once() -> dict:
    """Lê canais em sequência, grava novas avaliações e sinaliza novas mídias."""
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / ".review-collector.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"estado": "ja_em_execucao"}
        started_at = datetime.now(timezone.utc).isoformat()
        detail: dict = {"canais": {}, "novas": 0}
        try:
            known = base_fingerprints()
            for name, collector in (("Mercado Livre", run_mercadolivre), ("Shopee", run_shopee)):
                try:
                    records, result = collector()
                    new = review_db.insert_reviews(records, known)
                    detail["canais"][name] = {**result, "novas": new}
                    detail["novas"] += new
                    # Atualizar os fingerprints do novo lote entre plataformas.
                    known.update(review_db.source_fingerprint(x) for x in records)
                    if new:
                        media_store.manifest.cache_clear()
                except Exception as exc:
                    LOG.exception("Coletor %s falhou", name)
                    detail["canais"][name] = {"estado": "erro", "erro": str(exc)[:180]}
                time.sleep(DELAY)
            detail["canais"]["Amazon"] = {"estado": "sem_conector"}
            detail["canais"]["TikTok"] = {"estado": "sem_conector_de_descoberta"}
            states = [x.get("estado") for x in detail["canais"].values()]
            active = any(x == "ok" for x in states)
            state = "ok" if active else ("parcial" if "erro" in states else "sem_fontes_ativas")
            review_db.log_run(state, detail, started_at)
            if detail["novas"]:
                # Importação de novas mídias somente após gravação dos comentários.
                # Pode durar vários minutos sem bloquear nenhuma requisição da API.
                media_store.sync_all()
            return {"estado": state, **detail}
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def next_schedule(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(ZONE)).astimezone(ZONE)
    target = local.replace(hour=3, minute=0, second=0, microsecond=0)
    if local >= target:
        target += timedelta(days=1)
    return target


def status() -> dict:
    import review_db
    ml_token = bool(os.getenv("DAHUER_ML_ACCESS_TOKEN"))
    apify_token = bool(os.getenv("DAHUER_APIFY_TOKEN"))
    try:
        configured_items = len(ml_items())
    except ValueError:
        configured_items = 0
    return {
        "agendamento": "diariamente às 03:00 America/Sao_Paulo",
        "proxima_execucao": next_schedule().isoformat(),
        "coleta_mercadolivre": ml_token and configured_items > 0,
        "ml_anuncios_configurados": configured_items,
        "coleta_shopee": apify_token,
        "coleta_amazon": False,
        "descoberta_tiktok": False,
        "armazenamento": str(review_db.DB_PATH),
        "avaliacoes_novas_armazenadas": review_db.count_extra(),
        "ultima_execucao": review_db.last_run(),
    }


def _background() -> None:
    while not STOP.is_set():
        wait_seconds = max(1, (next_schedule() - datetime.now(ZONE)).total_seconds())
        if STOP.wait(wait_seconds):
            return
        LOG.info("Iniciando coleta diária")
        try:
            LOG.info("Coleta diária: %s", collect_once())
        except Exception:
            LOG.exception("Erro inesperado no agendamento da coleta")


def start() -> None:
    global _STARTED
    if os.getenv("DAHUER_COLLECTOR_ENABLED", "true").lower() not in ("true", "yes", "1"):
        return
    with _STARTED_LOCK:
        if _STARTED:
            return
        _STARTED = True
    threading.Thread(target=_background, name="dahuer-review-collector", daemon=True).start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Roda imediatamente uma coleta de teste")
    parser.add_argument("--status", action="store_true", help="Mostra configuração e estado")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.once:
        result = collect_once()
    else:
        result = status()
    print(json.dumps(result, ensure_ascii=False, indent=2))
