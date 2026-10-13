from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_health_and_total():
    r = client.get('/healthz')
    assert r.status_code == 200
    assert r.json()['total_avaliacoes'] == 220


def test_channels_and_filters():
    r = client.get('/api/v1/channels')
    assert {x['canal']: x['total'] for x in r.json()} == {'Shopee': 74, 'Mercado Livre': 60, 'TikTok': 54, 'Amazon': 32}
    r = client.get('/api/v1/comments', params={'canal': 'shopee', 'produto': 'protetor', 'nota': 5})
    assert r.status_code == 200
    assert all(x['canal'] == 'Shopee' and x['produto'] == 'Protetor' and x['nota'] == 5 for x in r.json()['data'])


def test_pagination_and_validation():
    r = client.get('/api/v1/comments', params={'page': 2, 'per_page': 10})
    assert r.status_code == 200
    assert r.json()['total'] == 220 and len(r.json()['data']) == 10
    assert client.get('/api/v1/comments', params={'per_page': 101}).status_code == 422


def test_id_and_download():
    c = client.get('/api/v1/comments').json()['data'][0]
    assert client.get('/api/v1/comments/' + c['id']).json()['id'] == c['id']
    assert client.get('/api/v1/comments/no-such-id').status_code == 404
    csvr = client.get('/api/v1/download', params={'canal': 'Amazon'})
    assert csvr.status_code == 200 and csvr.text.count('\n') == 33
    js = client.get('/api/v1/download', params={'formato': 'json', 'canal': 'TikTok'})
    assert len(js.json()) == 54


def test_stats():
    r = client.get('/api/v1/stats')
    assert r.status_code == 200 and r.json()['total'] == 220


def test_studio_and_embed_script():
    home = client.get('/')
    assert home.status_code == 200
    assert 'text/html' in home.headers['content-type']
    assert 'Selecione um produto' in home.text
    assert 'Copiar código para minha LP' in home.text
    widget = client.get('/widget.js')
    assert widget.status_code == 200
    assert 'javascript' in widget.headers['content-type']
    assert 'DahuerComments' in widget.text
    assert 'data-target' not in widget.text or 'dataset.target' in widget.text
    api = client.get('/api')
    assert api.status_code == 200 and api.json()['total_avaliacoes'] == 220


def test_empty_preview_hides_after_selection():
    home = client.get('/').text
    # Author CSS must override the user-agent default when hidden is set.
    assert '[hidden]{display:none!important}' in home
    assert 'empty.hidden=selected;preview.hidden=!selected;' in home.replace(' ', '')
    widget = client.get('/widget.js').text
    assert ':host([data-theme="dark"]) .dc-root' in widget


def test_media_urls_are_from_our_domain():
    r = client.get('/api/v1/comments', params={'produto': 'Protetor'})
    assert r.status_code == 200
    with_media = next(x for x in r.json()['data'] if x['midias'])
    assert all(url.startswith('http://testserver/media/') for url in with_media['midias'])
    assert with_media['midia_links'] == ' | '.join(with_media['midias'])
    assert with_media['midia_links_originais'].startswith('https://')
    assert with_media['midias_info'][0]['url'].startswith('http://testserver/media/')
    assert 'midias_originais' in with_media


def test_tiktok_video_pages_are_hosted_through_our_url():
    from media_store import manifest, is_tiktok_video
    data = manifest()
    assert len(data) == 423
    assert sum(is_tiktok_video(x['url']) for x in data.values()) == 54
    tiktok = client.get('/api/v1/comments', params={'canal': 'TikTok'}).json()['data']
    assert len(tiktok) == 54
    assert all(len(item['midias']) == 1 for item in tiktok)
    assert all('/media/' in item['midias'][0] for item in tiktok)
    assert all(item['midias_info'][0]['tipo'] == 'video' for item in tiktok)


def test_tiktok_video_page_urls_are_validated():
    from tiktok_media import is_tiktok_video
    assert is_tiktok_video('https://www.tiktok.com/@demo/video/7693709444386950421')
    assert not is_tiktok_video('https://www.tiktok.com/@demo/photo/7693709444386950421')
    assert not is_tiktok_video('https://tiktok.com.evil.example/@demo/video/7693709444386950421')
    assert not is_tiktok_video('http://www.tiktok.com/@demo/video/7693709444386950421')
    assert not is_tiktok_video('https://www.tiktok.com/@demo/video/1')


def test_tiktok_video_download_is_atomic(monkeypatch, tmp_path):
    import tiktok_media
    calls = []

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def download(self, urls):
            calls.extend(urls)
            filename = self.opts['outtmpl'].replace('%(ext)s', 'mp4')
            with open(filename, 'wb') as f:
                f.write(b'\x00\x00\x00\x18ftypisom' + b'v' * 100)
            return 0
    monkeypatch.setattr(tiktok_media, 'YoutubeDL', FakeYoutubeDL)
    dest = tmp_path / 'final_file'
    url = 'https://www.tiktok.com/@demo/video/7693709444386950421'
    tiktok_media.fetch_tiktok_video(url, dest, 1000)
    assert dest.exists()
    assert dest.read_bytes()[4:8] == b'ftyp'
    assert calls == [url]


def test_tiktok_pending_does_not_fetch_while_user_waits(monkeypatch, tmp_path):
    import media_store
    monkeypatch.setattr(media_store, 'MEDIA_DIR', tmp_path)
    key = next(k for k, item in media_store.manifest().items() if media_store.is_tiktok_video(item['url']))
    response = client.get('/media/' + key)
    assert response.status_code == 503
    assert 'Retry-After' in response.headers


def test_media_mirror_downloads_once_and_serves_locally(monkeypatch, tmp_path):
    import io
    import media_store
    monkeypatch.setattr(media_store, 'MEDIA_DIR', tmp_path)
    jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 100
    calls = []

    class Source(io.BytesIO):
        headers = {'Content-Length': str(len(jpeg))}
    class Opener:
        def open(self, req, timeout):
            calls.append(req.full_url)
            return Source(jpeg)
    monkeypatch.setattr(media_store, '_opener', Opener())
    key = next(k for k, x in media_store.manifest().items() if x['tipo'] == 'image')
    r = client.get('/media/' + key)
    assert r.status_code == 200
    assert r.content == jpeg
    assert r.headers['content-type'].startswith('image/jpeg')
    assert r.headers['cache-control'].startswith('public')
    assert len(calls) == 1
    assert client.get('/media/' + key).status_code == 200
    assert len(calls) == 1
    stats = client.get('/api/v1/media/status').json()
    assert stats['baixados'] >= 1
    assert stats['total_importaveis'] == 423
    assert stats['total_tiktok'] == 54
    assert client.get('/media/deadbeef').status_code == 404


def test_media_html_is_rejected(monkeypatch, tmp_path):
    import io
    import media_store
    monkeypatch.setattr(media_store, 'MEDIA_DIR', tmp_path)
    class Source(io.BytesIO):
        headers = {}
    class Opener:
        def open(self, req, timeout):
            return Source(b'<html>Not a photo</html>')
    monkeypatch.setattr(media_store, '_opener', Opener())
    key = next(k for k, x in media_store.manifest().items() if x['tipo'] == 'image')
    response = client.get('/media/' + key)
    assert response.status_code == 503
    assert not (tmp_path / key).exists()


def test_tiktok_tries_alternative_browser_when_webpage_fails(monkeypatch, tmp_path):
    import tiktok_media

    attempts = []

    class MockYoutubeDL:
        def __init__(self, options):
            self.options = options
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def download(self, urls):
            attempts.append(self.options["http_headers"]["User-Agent"])
            if len(attempts) == 1:
                raise RuntimeError("Unexpected response from webpage request")
            filename = self.options["outtmpl"].replace("%(ext)s", "mp4")
            with open(filename, "wb") as output:
                output.write(b"\x00\x00\x00\x18ftypisom" + b"v" * 80)
            return 0

    monkeypatch.setattr(tiktok_media, "YoutubeDL", MockYoutubeDL)
    target = tmp_path / "tiktok-test"
    tiktok_media.fetch_tiktok_video(
        "https://www.tiktok.com/@demo/video/7693709444386950421",
        target, 1000,
    )
    assert target.exists()
    assert len(attempts) == 2
    assert "Chrome/145" in attempts[0]
    assert "Firefox/155" in attempts[1]


def test_old_tiktok_error_is_retried_when_strategy_changes(monkeypatch, tmp_path):
    import json
    import time
    import media_store

    monkeypatch.setattr(media_store, "MEDIA_DIR", tmp_path)
    key = next(
        key for key, media in media_store.manifest().items()
        if media_store.is_tiktok_video(media["url"])
    )
    (tmp_path / ".errors.json").write_text(
        json.dumps({key: {
            "timestamp": time.time(),
            "erro": "Falha do extrator TikTok: Unexpected response",
        }}), encoding="utf-8",
    )
    attempts = []

    def mock_download(media_id):
        attempts.append(media_id)
        (tmp_path / media_id).write_bytes(
            b"\x00\x00\x00\x18ftypisom" + b"v" * 80
        )

    monkeypatch.setattr(media_store, "_fetch", mock_download)
    assert media_store.ensure_downloaded(key)
    assert attempts == [key]
    assert key not in media_store.get_errors()


def test_product_test_lp_uses_live_widget():
    page = client.get('/teste/protetor')
    assert page.status_code == 200
    assert 'text/html' in page.headers['content-type']
    assert 'HIDRABENE' in page.text
    assert '<script src="/widget.js"></script>' in page.text
    assert "produto: 'Protetor'" in page.text
    assert "DahuerComments.mount('reviews-widget',options())" in page.text
    assert '/api/v1/media/status' in page.text
    assert 'id="channel"' in page.text
    assert 'id="only-media"' in page.text
    assert 'href="/teste/protetor"' in client.get('/').text


def test_product_test_lp_has_real_reviews():
    result = client.get('/api/v1/comments', params={
        'produto': 'Protetor', 'per_page': 100,
    }).json()
    assert result['total'] == 38
    assert set(c['canal'] for c in result['data']) == {
        'TikTok', 'Shopee', 'Mercado Livre', 'Amazon',
    }
    assert any(c['midias_info'] for c in result['data'])



def test_comments_date_sort_and_video_priority():
    from app import sort_comments
    items = [
        {"id": "old", "data_iso": "2026-09-01T02:00:00+00:00", "com_video": True},
        {"id": "new", "data_iso": "2026-10-12T02:00:00+00:00", "com_video": False},
        {"id": "unknown", "data_iso": None, "com_video": False},
    ]
    assert [r["id"] for r in sort_comments(items)] == ["new", "old", "unknown"]
    assert [r["id"] for r in sort_comments(items, priorizar_video=True)] == ["old", "new", "unknown"]
    assert [r["id"] for r in sort_comments(items, ordem="antigas")] == ["old", "new", "unknown"]


def test_relative_dates_have_no_invented_timestamp():
    import review_db
    assert review_db.normalize_date("Há 1 mês") is None
    assert review_db.normalize_date("01/10/2026").startswith("2026-10-01")
    assert review_db.normalize_date("2026-10-09T04:21:00Z").startswith("2026-10-09T04:21:00")


def test_sqlite_incremental_dedup_and_media(monkeypatch, tmp_path):
    import review_db
    import media_store
    monkeypatch.setattr(review_db, "DB_PATH", tmp_path / "test-reviews.sqlite3")
    entry = {
        "source_key": "shopee:review-987",
        "canal": "Shopee", "produto": "Protetor", "nota": 5,
        "data": "2026-10-13", "timestamp_utc": "2026-10-13T09:00:00Z",
        "autor": "Cliente", "texto": "Nova avaliação com vídeo de teste",
        "link": "https://shopee.com.br/product/1860098702/58214668571",
        "variacao": "", "tem_foto_ou_video": "vídeo",
        "midia_links": "https://down-aka-br.vod.susercontent.com/video-test.mp4",
        "midia_arquivos": "",
    }
    assert review_db.insert_reviews([entry], set()) == 1
    assert review_db.insert_reviews([entry], set()) == 0
    rows = review_db.extra_reviews()
    assert len(rows) == 1
    assert rows[0]["com_video"] is True
    assert rows[0]["data_iso"].startswith("2026-10-13")
    media_store.manifest.cache_clear()
    assert any(info["url"] == entry["midia_links"] for info in media_store.manifest().values())
    media_store.manifest.cache_clear()


def test_shopee_and_ml_collectors_parse_video_sources():
    import daily_collector
    shopee_products = {"123": {"produto": "Protetor", "url": "https://shopee.com.br/product/9/123"}}
    shopee = daily_collector.from_shopee({
        "type": "review", "reviewId": "9112", "productId": "123",
        "rating": 5, "text": "Com vídeo", "reviewerName": "alguem",
        "createdAt": "2026-10-11T18:00:00Z",
        "videoUrls": ["https://down-br.vod.susercontent.com/video.mp4"], "imageUrls": [],
    }, shopee_products)
    assert shopee["source_key"] == "shopee:9112"
    assert shopee["tem_foto_ou_video"] == "vídeo"
    ml = daily_collector.from_mercadolivre({
        "produto": "Protetor", "link": "https://www.mercadolivre.com.br/p/MLB123"
    }, {
        "id": 23, "date_created": "2026-10-13T08:00:00Z",
        "status": "published", "rate": 4, "title": "Gostei",
        "content": "Produto bom", "videos": [{"url": "https://video-vod-clips.mms.mlstatic.com/abc.mp4"}],
    })
    assert ml["source_key"] == "mercadolivre:23"
    assert "video-vod" in ml["midia_links"]


def test_daily_schedule_and_collector_status():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from daily_collector import next_schedule
    now = datetime(2026, 10, 13, 4, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert next_schedule(now).isoformat().startswith("2026-10-14T03:00")
    status = client.get("/api/v1/collector/status")
    assert status.status_code == 200
    assert "03:00" in status.json()["agendamento"]
    assert status.json()["descoberta_tiktok"] is False



def test_review_video_poster_is_local_and_cached(monkeypatch, tmp_path):
    """Gera a capa uma vez, reutilizando o MP4 e o volume existentes."""
    import media_store
    import subprocess

    monkeypatch.setattr(media_store, "MEDIA_DIR", tmp_path)
    key = next(k for k, entry in media_store.manifest().items()
               if entry["tipo"] == "video")
    video = tmp_path / key
    video.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 128)
    calls = []

    def fake_ffmpeg(argv, **kwargs):
        calls.append(argv)
        (tmp_path / argv[-1]).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 150)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(media_store.subprocess, "run", fake_ffmpeg)
    first = client.get("/media/" + key + "/poster")
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("image/jpeg")
    assert first.content.startswith(b"\xff\xd8\xff")
    assert first.headers["cache-control"].startswith("public")
    second = client.get("/media/" + key + "/poster")
    assert second.status_code == 200
    assert len(calls) == 1
    assert video.exists()
    assert (tmp_path / (key + ".poster.jpg")).exists()


def test_missing_video_poster_does_not_download_video(monkeypatch, tmp_path):
    import media_store

    monkeypatch.setattr(media_store, "MEDIA_DIR", tmp_path)
    video_key = next(k for k, entry in media_store.manifest().items()
                     if entry["tipo"] == "video")
    image_key = next(k for k, entry in media_store.manifest().items()
                     if entry["tipo"] == "image")
    assert client.get("/media/" + video_key + "/poster").status_code == 503
    assert client.get("/media/" + image_key + "/poster").status_code == 404
    assert client.get("/media/no-such-id/poster").status_code == 404


def test_embedded_widget_uses_video_thumbnails_and_attribution():
    script = client.get("/widget.js").text
    assert "dc-video-tile" in script
    assert "dc-video-poster" in script
    assert "makeVideoDialog(shadow)" in script
    assert "data.data.forEach(c => grid.append(drawCard(c, videoDialog.open, imageDialog.open)))" in script
    assert "Comprador da Shopee" in script
    assert "Comprador do Mercado Livre" in script
    assert "Nome não informado" in script

    review = client.get("/api/v1/comments", params={"canal": "TikTok"}).json()["data"][0]
    video = next(m for m in review["midias_info"] if m["tipo"] == "video")
    assert video["poster_url"] == video["url"] + "/poster"



def test_review_images_open_local_lightbox_not_marketplace():
    script = client.get('/widget.js').text
    assert "function makeImageDialog(shadow)" in script
    assert "const tile = el('button', 'dc-photo-tile')" in script
    assert "tile.addEventListener('click', () => openImage(item.url, tile, i + 1))" in script
    assert "data.data.forEach(c => grid.append(drawCard(c, videoDialog.open, imageDialog.open)))" in script
    assert "setLink(a, c.link || item.url)" not in script
    assert "Ver avaliação original ↗" in script
    assert "if (setLink(source, c.link)) footer.append(source)" in script
    assert "photo.src = url" in script
    assert "photo.removeAttribute('src')" in script
    assert "event.key === 'Escape'" in script
    assert "imageDialogs.set(node, imageDialog)" in script
