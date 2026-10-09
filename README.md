# Dahuer Comments · Studio e API

**Painel visual para landing pages já hospedado no Easypanel:** https://workspace-dahuer-comments.yu7gwy.easypanel.host/

## Como usar sem programar

1. Acesse o painel acima e escolha **produto**, marketplace, estrelas, quantidade de avaliações, fotos e tema.
2. Confira a prévia e clique em **Copiar código para minha LP**.
3. Cole o HTML copiado na sua landing page. O script público em `/widget.js` carrega as avaliações com segurança, sem interferir no CSS da página.

O painel também permite copiar a URL da API filtrada ou **baixar CSV/JSON**. Não há login e nem armazenamento de preferências.

**Nota:** o código de incorporação requer a API no ar; a URL padrão acima depende do serviço no Easypanel. Se esse endereço mudar, gere um novo snippet no domínio definitivo.

API REST **pública, gratuita e somente leitura** para consultar e exportar avaliações públicas de produtos Hidrabene coletadas em **Shopee, Mercado Livre, TikTok e Amazon**.

**Base inicial: 220 avaliações** (Shopee 74, Mercado Livre 60, TikTok 54, Amazon 32). Os dados estão em [`data/`](data/), disponíveis para download direto, inclusive sem executar servidor.

> **Hospedagem:** a API está disponível no Easypanel no endereço acima. O GitHub continua oferecendo o código e os CSVs; um repositório sozinho não executa o servidor.

## Download público imediato

- [Shopee (CSV)](https://raw.githubusercontent.com/Gabriel112252/dahuer_comments/main/data/hidrabene_shopee.csv)
- [Mercado Livre (CSV)](https://raw.githubusercontent.com/Gabriel112252/dahuer_comments/main/data/hidrabene_mercadolivre.csv)
- [TikTok (CSV)](https://raw.githubusercontent.com/Gabriel112252/dahuer_comments/main/data/hidrabene_tiktok.csv)
- [Amazon (CSV)](https://raw.githubusercontent.com/Gabriel112252/dahuer_comments/main/data/hidrabene_amazon.csv)
- [Repositório completo (ZIP)](https://github.com/Gabriel112252/dahuer_comments/archive/refs/heads/main.zip)

## JSON público (sem precisar hospedar servidor)

**Endpoint estático, já acessível publicamente:**

```text
https://raw.githubusercontent.com/Gabriel112252/dahuer_comments/main/data/comments.json
```

Retorna um objeto com `snapshot`, `total` e `data` (as 220 avaliações). Exemplo:

```js
const url = 'https://raw.githubusercontent.com/Gabriel112252/dahuer_comments/main/data/comments.json';
const {data} = await fetch(url).then(r => r.json());
const protetoresShopee = data.filter(x => x.canal === 'Shopee' && x.produto === 'Protetor');
```

A URL estática entrega a base inteira. Para filtros por URL, paginação e Swagger, utilize a API hospedada no Easypanel.

## Execução

```bash
docker compose up -d --build
```

Abra `http://localhost:8000/docs` para Swagger interativo. Também funciona com Python:

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

## Endpoints

| Método | Caminho | Uso |
|---|---|---|
| `GET` | `/` | Painel visual (seleção, prévia, código e download) |
| `GET` | `/widget.js` | Componente JS incorporável nas LPs |
| `GET` | `/api` | Informações da API |
| `GET` | `/healthz` | Saúde da API |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/openapi.json` | Contrato OpenAPI |
| `GET` | `/api/v1/comments` | Busca paginada e filtros |
| `GET` | `/api/v1/comments/{id}` | Avaliação por ID |
| `GET` | `/api/v1/channels` | Canais e volumes |
| `GET` | `/api/v1/products` | Produtos e volumes |
| `GET` | `/api/v1/stats` | Estatísticas gerais |
| `GET` | `/api/v1/download?formato=csv` | Download em CSV |
| `GET` | `/api/v1/download?formato=json` | Download em JSON |

### Filtros

`canal`, `produto`, `nota` (1–5), `q` (texto), `com_midia` (somente listagem), `page` (a partir de 1), `per_page` (1–100).

Exemplos com servidor em `http://localhost:8000`:

```bash
curl 'http://localhost:8000/api/v1/comments?canal=Shopee&produto=Protetor&nota=5&page=1&per_page=10'
curl 'http://localhost:8000/api/v1/comments?q=textura'
curl 'http://localhost:8000/api/v1/stats'
curl -OJ 'http://localhost:8000/api/v1/download?formato=csv&canal=Amazon'
```

## Deploy público

O projeto expõe a porta `8000`. Em qualquer hospedagem compatível com Docker, configure domínio HTTPS apontando ao contêiner, com comando/porta do Dockerfile padrão. Recomenda-se um serviço simples (1 réplica é suficiente para o volume inicial) com SSL e monitoramento de `/healthz`. No Easypanel, use o repositório GitHub, build via Dockerfile, porta interna `8000` e conecte o domínio desejado. Para atualizar o painel, faça um novo build/deploy da branch `main`.

## Campos

Os CSVs usam `;` como separador: `canal`, `produto`, `nota`, `data`, `autor`, `texto`, `variacao`, `tem_foto_ou_video`, `link`, `midia_links`, `midia_arquivos`. A API também adiciona `id` estável, `midias` (links) e `arquivos_midia_referenciados` (nomes de arquivos, não URLs hospedadas). As datas são mantidas como fornecidas, inclusive valores relativos como “Há 6 meses”; notas não informadas tornam-se `null`.

## Direitos e origem

**O código** é distribuído sob licença MIT. **Avaliações, nomes de autores, imagens e vídeos são conteúdos de terceiros e não passam a ser MIT.** Consulte as plataformas e obtenha os direitos necessários antes de redistribuir dados em produção; mantenha links de origem, respeite solicitações de remoção e as regras das plataformas. Esta API não disponibiliza os arquivos binários de mídia nem contorna restrições de download de criadores. URLs de mídia podem deixar de funcionar. A base é um snapshot, sem coleta automática nem promessa de atualização em tempo real.