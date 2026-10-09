"""API pública, de leitura, para avaliações de produtos Hidrabene."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

DATA_DIR = Path(os.environ.get('DAHUER_DATA_DIR', Path(__file__).parent / 'data'))
CSV_FILES = ('hidrabene_shopee.csv', 'hidrabene_mercadolivre.csv', 'hidrabene_tiktok.csv', 'hidrabene_amazon.csv')
FIELDS = ('canal', 'produto', 'nota', 'data', 'autor', 'texto', 'variacao', 'tem_foto_ou_video', 'link', 'midia_links', 'midia_arquivos')

app = FastAPI(
    title='Dahuer Comments API',
    description='Consulta pública e exportação de avaliações de produtos, com links para as fontes originais. Os arquivos de mídia não são hospedados nesta API.',
    version='1.0.0',
    license_info={'name': 'Código MIT; os dados e mídias de terceiros mantêm seus direitos originais.'},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['GET'],
    allow_headers=['*'],
)


def norm(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c)).casefold().strip()


def split_media(value: str) -> list[str]:
    return [part.strip() for part in (value or '').split(' | ') if part.strip()]


@lru_cache(maxsize=1)
def read_comments() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []
    for filename in CSV_FILES:
        with (DATA_DIR / filename).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f, delimiter=';')
            if tuple(reader.fieldnames or ()) != FIELDS:
                raise ValueError(f'Cabeçalho inválido: {filename}')
            for row in reader:
                if not row.get('texto'):
                    continue
                comment: dict[str, Any] = {name: (row.get(name) or '').strip() for name in FIELDS}
                comment['id'] = hashlib.sha256(
                    '\x1f'.join(comment[k] for k in ('canal', 'produto', 'link', 'texto')).encode('utf-8')
                ).hexdigest()[:20]
                comment['nota'] = int(comment['nota']) if comment['nota'].isdigit() else None
                comment['midias'] = split_media(comment['midia_links'])
                # Esses caminhos são metadados de uma coleta externa, não URLs desta API.
                comment['arquivos_midia_referenciados'] = split_media(comment['midia_arquivos'])
                data.append(comment)
    return data


def filter_comments(
    canal: str | None = None,
    produto: str | None = None,
    nota: int | None = None,
    q: str | None = None,
    com_midia: bool | None = None,
) -> list[dict[str, Any]]:
    items = read_comments()
    if canal:
        items = [x for x in items if norm(x['canal']) == norm(canal)]
    if produto:
        items = [x for x in items if norm(x['produto']) == norm(produto)]
    if nota is not None:
        items = [x for x in items if x['nota'] == nota]
    if q:
        query = norm(q)
        items = [x for x in items if any(query in norm(x[field]) for field in ('texto', 'variacao', 'produto'))]
    if com_midia is not None:
        items = [x for x in items if bool(x['midias']) == com_midia]
    return items


@app.get('/', tags=['Sobre'])
def root():
    return {'nome': 'Dahuer Comments API', 'total_avaliacoes': len(read_comments()), 'documentacao': '/docs', 'api': '/api/v1/comments', 'download': '/api/v1/download'}


@app.get('/healthz', tags=['Sobre'])
def healthz():
    return {'status': 'ok', 'total_avaliacoes': len(read_comments())}


@app.get('/api/v1/comments', tags=['Avaliações'])
def comments(
    canal: str | None = Query(None, description='Ex.: Shopee, Mercado Livre, TikTok, Amazon'),
    produto: str | None = Query(None, description='Ex.: Protetor, Kit Clareador'),
    nota: int | None = Query(None, ge=1, le=5),
    q: str | None = Query(None, max_length=200, description='Busca textual'),
    com_midia: bool | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    filtered = filter_comments(canal, produto, nota, q, com_midia)
    offset = (page - 1) * per_page
    return {'total': len(filtered), 'page': page, 'per_page': per_page,
            'total_pages': math.ceil(len(filtered) / per_page), 'data': filtered[offset:offset + per_page]}


@app.get('/api/v1/comments/{comment_id}', tags=['Avaliações'])
def comment_by_id(comment_id: str):
    return next((c for c in read_comments() if c['id'] == comment_id), None) or _not_found()


def _not_found():
    raise HTTPException(status_code=404, detail='Avaliação não encontrada')


@app.get('/api/v1/channels', tags=['Catálogo'])
def channels():
    return [{'canal': canal, 'total': total} for canal, total in sorted(Counter(x['canal'] for x in read_comments()).items())]


@app.get('/api/v1/products', tags=['Catálogo'])
def products():
    return [{'produto': produto, 'total': total} for produto, total in sorted(Counter(x['produto'] for x in read_comments()).items())]


@app.get('/api/v1/stats', tags=['Catálogo'])
def stats():
    data = read_comments()
    notes = [x['nota'] for x in data if x['nota'] is not None]
    return {'total': len(data), 'com_nota': len(notes), 'nota_media': round(sum(notes) / len(notes), 2) if notes else None,
            'por_canal': dict(sorted(Counter(x['canal'] for x in data).items())),
            'por_produto': dict(sorted(Counter(x['produto'] for x in data).items())),
            'com_links_midia': sum(bool(x['midias']) for x in data)}


@app.get('/api/v1/download', tags=['Exportação'])
def download(
    formato: str = Query('csv', pattern='^(csv|json)$'),
    canal: str | None = None,
    produto: str | None = None,
    nota: int | None = Query(None, ge=1, le=5),
    q: str | None = Query(None, max_length=200),
):
    data = filter_comments(canal, produto, nota, q)
    if formato == 'json':
        return Response(
            content=json.dumps(data, ensure_ascii=False),
            media_type='application/json; charset=utf-8',
            headers={'Content-Disposition': 'attachment; filename="dahuer_comments.json"'},
        )
    s = io.StringIO(newline='')
    writer = csv.DictWriter(s, fieldnames=FIELDS, delimiter=';', lineterminator='\r\n')
    writer.writeheader()
    for item in data:
        # Proteção contra CSV formula injection em planilhas.
        writer.writerow({k: ("'" + str(item[k]) if str(item[k]).lstrip().startswith(('=', '+', '-', '@')) else item[k] or '') for k in FIELDS})
    return Response(
        content='\ufeff' + s.getvalue(),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="dahuer_comments.csv"'},
    )
