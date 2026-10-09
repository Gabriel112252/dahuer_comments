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
