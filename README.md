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

## Mídias hospedadas em domínio próprio (Easypanel)

A API agora transforma as URLs diretas de fotos e vídeos dos marketplaces em **links próprios**:
\`https://workspace-dahuer-comments.yu7gwy.easypanel.host/media/<id>\`

- A importação começa **automaticamente em segundo plano após o deploy**, primeiro imagens, depois vídeos.
- O endpoint \`GET /api/v1/media/status\` indica quantos arquivos estão baixados, pendentes e com falha.
- \`midias\`, \`midias_info\` e \`midia_links\` na API/JSON/CSV de download usam nossos links. Os valores antigos são preservados em \`midias_originais\`/\`midia_links_originais\` no JSON.
- O widget utiliza nossos links e exibe imagens e vídeos com controles de reprodução.
- O endpoint \`GET /media/<id>\` também pode buscar um arquivo no primeiro acesso, com limites de tamanho e origem. Se um original estiver indisponível, retorna \`503\` em vez de redirecionar para o marketplace.
- Foram encontradas **423 referências**, sendo **369 URLs diretas compatíveis para tentativa de importação**. Outras **54 URLs do TikTok são páginas de vídeos**, não arquivos de mídia; são identificadas em \`midias_nao_hospedadas\` e precisam de arquivo original ou autorização/acesso específico para importação.
- O download de cada mídia depende de sua disponibilidade e das permissões do servidor remoto; uma referência não comprova que o arquivo foi importado.
- O espelho não armazena avaliações novas automaticamente: a base vem dos CSVs versionados no GitHub.

### Configuração obrigatória no Easypanel

1. No serviço \`dahuer-comments\`, configure **Volume / Armazenamento persistente** montado em **\`/app/media\`**. Faça isso *antes* de executar o importador, senão os downloads podem se perder no próximo deploy. Para deploy com Docker Compose, há volume nomeado \`dahuer-media:/app/media\`.
2. Mantenha **1 réplica**, porta interna **8000**, build pelo Dockerfile da branch \`main\`.
3. Faça **Deploy**. Não é necessário alterar o nome/domínio da API nem as LPs que usam o widget atual.
4. Acompanhe \`/api/v1/media/status\` ou os logs. O painel inicial também mostra a quantidade importada.

Configuráveis via variáveis de ambiente: \`DAHUER_MEDIA_DIR=/app/media\`, \`DAHUER_MEDIA_AUTO_SYNC=true\`, \`DAHUER_MAX_IMAGE_MB=8\`, \`DAHUER_MAX_VIDEO_MB=48\` e, opcionalmente, \`DAHUER_PUBLIC_BASE_URL=https://seu-dominio\`.

Se preferir disparar manualmente pelo terminal do contêiner:
\`\`\`bash
python media_store.py --status
python media_store.py --retry-failed
\`\`\`
Os downloads são limitados a URLs dos CDNs dos marketplaces presentes nos CSVs, sem parâmetros de URL arbitrários, com validação do tipo de arquivo. Imagens e vídeos de terceiros podem estar sujeitos a direitos autorais, termos das plataformas e autorizações para uso publicitário: valide as permissões antes de redistribuí-los.

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
| `GET` | `/api/v1/media/status` | Quantidade de mídias já importadas e pendentes |
| `GET` | `/media/{id}` | Foto ou vídeo servido pelo nosso domínio |
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

Os CSVs usam `;` como separador: `canal`, `produto`, `nota`, `data`, `autor`, `texto`, `variacao`, `tem_foto_ou_video`, `link`, `midia_links`, `midia_arquivos`. A API também adiciona `id` estável, `midias` (links locais), `midias_info` (links locais com tipo), `midias_originais` (URLs de origem), `midias_nao_hospedadas` (links não importáveis, por exemplo páginas de vídeos do TikTok) e `arquivos_midia_referenciados` (nomes originais, não URLs hospedadas). As datas são mantidas como fornecidas, inclusive valores relativos como “Há 6 meses”; notas não informadas tornam-se `null`.

## Direitos e origem

**O código** é distribuído sob licença MIT. **Avaliações, nomes de autores, imagens e vídeos são conteúdos de terceiros e não passam a ser MIT.** Consulte as plataformas e obtenha os direitos necessários antes de redistribuir dados em produção; mantenha links de origem, respeite solicitações de remoção e as regras das plataformas. O serviço hospeda cópias dos arquivos diretos que puder baixar; não contorna restrições de acesso às mídias nem baixa páginas protegidas. URLs de mídia podem deixar de funcionar. A base é um snapshot, sem coleta automática nem promessa de atualização em tempo real.