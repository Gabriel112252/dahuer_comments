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


def test_tiktok_page_links_are_not_falsely_marked_as_hosted():
    from media_store import manifest
    assert len(manifest()) == 369
    tiktok = client.get('/api/v1/comments', params={'canal': 'TikTok'}).json()['data']
    assert all(not item['midias'] for item in tiktok)
    assert any(item['midias_nao_hospedadas'] for item in tiktok)


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
    assert stats['total_importaveis'] == 369
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
