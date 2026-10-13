# Dahuer Comments · Studio e API

**Painel visual para landing pages já hospedado no Easypanel:** https://workspace-dahuer-comments.yu7gwy.easypanel.host/

## Novas avaliações: coleta diária às 03:00 (São Paulo)

A partir desta versão, o serviço também mantém um banco **SQLite em /app/media/reviews.sqlite3** (o mesmo volume persistente já montado no Easypanel). Os 220 registros dos CSVs continuam sendo o snapshot inicial, e novas avaliações são acrescentadas ao banco sem regravar o GitHub, sem duplicação por ID de avaliação e conteúdo.

- Agendamento diário às **03:00 no fuso America/Sao_Paulo**, com bloqueio por arquivo para impedir duas coletas simultâneas.
- Busca de novas avaliações **uma fonte de cada vez**, com pausa e limite de páginas/requisições. Não é uma coleta contínua nem garante acesso ao histórico inteiro que a plataforma não expõe.
- Os comentários mostram **mais recentes primeiro**, usando timestamp da origem quando presente. Datas relativas como "Há 1 mês" ficam com data desconhecida para a ordenação, sem inventar datas.
- O widget/LP aceita \`com_video=true\` e \`priorizar_video=true\`, além de \`ordem=recentes\` (padrão) ou \`ordem=antigas\`. Mesmo priorizando vídeos, não excluímos as demais avaliações, a menos que se use \`com_video=true\`.
- Mídias das novas avaliações entram no espelho \`/media/<id>\`. Falhas não impedem de exibir a avaliação; um vídeo não é considerado baixado antes de existir no volume.
- Consulte \`GET /api/v1/collector/status\` para ver se os canais foram configurados, quantas avaliações novas foram gravadas, a próxima coleta e o último resultado. Sem fonte habilitada, o agendamento não inventa avaliações e reporta \`sem_fontes_ativas\`.

### Habilitar Mercado Livre (API oficial)

A API oficial \`GET /reviews/item/{ITEM_ID}\` exige um token OAuth válido e o **ID do anúncio** \`MLB...\`, não somente a URL do catálogo \`/p/MLB...\` presente no CSV inicial.

No Easypanel, configure as variáveis de ambiente:

\`\`\`text
DAHUER_ML_ACCESS_TOKEN=<token OAuth valido>
DAHUER_ML_ITEMS_JSON=[{"produto":"Protetor","item_id":"MLB1234567890","catalog_product_id":"MLB60416809"}]
\`\`\`

Os IDs acima são **apenas exemplos de formato**, não anúncios Hidrabene verificados. Cadastre os anúncios reais correspondentes aos produtos. Não publique nem envie tokens no repositório ou em chats.

Documentação: https://developers.mercadolivre.com.br/pt_br/opinioes-sobre-um-produto

### Habilitar Shopee (opcional, serviço Apify cobrado à parte)

A Shopee pode bloquear acessos diretos a avaliações de produtos. Como alternativa, a integração opcional utiliza o ator \`memo23/shopee-reviews-scraper\` do Apify, que informa IDs estáveis, texto, data, fotos e vídeos. As URLs de produtos Shopee são descobertas **automaticamente nos CSVs existentes**; não precisam de cadastro manual adicional.

\`\`\`text
DAHUER_APIFY_TOKEN=<token Apify>
DAHUER_APIFY_MAX_USD=1.5
DAHUER_COLLECTOR_DAYS_BACK=7
\`\`\`

O máximo por execução e os custos do ator podem variar. **Nenhum uso pago é iniciado sem que a variável do token Apify seja configurada.** A API envia um limite de orçamento de até US$1,50 por execução por padrão, quando o provedor oferece esse controle; verifique a cobrança real no painel Apify. A integração cobre avaliações que o ator conseguir obter, não garante a totalidade histórica.

Referência do ator: https://apify.com/memo23/shopee-reviews-scraper

### Amazon e TikTok

Ainda **não possuem conector de descoberta automática** ativo neste projeto. Vídeos TikTok previamente catalogados continuam no importador com \`yt-dlp\`, mas essa biblioteca **não descobre avaliações novas de produtos**. Para Amazon e TikTok Shop, precisamos validar fontes autorizadas e cobertura Brasil antes de ativar rotina automática.

### Operação e limites

\`\`\`text
DAHUER_COLLECTOR_ENABLED=true
DAHUER_COLLECTOR_MAX_PER_SOURCE=300
DAHUER_COLLECTOR_DELAY=1.25
\`\`\`

O limite padrão do ator Shopee é 100 avaliações por produto por execução; o Mercado Livre consulta até 300 por anúncio. Isso evita carga ilimitada e deve ser ajustado conforme custo e cobertura. Para rodar um teste pontual **depois de configurar as credenciais**, execute no contêiner:

\`\`\`bash
python daily_collector.py --status
python daily_collector.py --once
\`\`\`

O volume \`/app/media\` precisa ser preservado, incluindo o banco \`reviews.sqlite3\` e, se houver, os arquivos auxiliares \`-wal\`/\`-shm\`. Para migração, faça backup SQLite consistente. Mantenha só uma réplica do serviço, limite chamadas às APIs e cumpra termos das plataformas e direitos dos autores antes de usar as avaliações/mídias em campanhas.

## Página demonstrativa de produto

Após o deploy no Easypanel, abra **https://workspace-dahuer-comments.yu7gwy.easypanel.host/teste/protetor**.

A página simula uma landing page do protetor solar Hidrabene, com ilustração de produto claramente identificada, sem ofertas comerciais. O bloco de avaliações usa **o mesmo `/widget.js`** do Studio e filtra `produto=Protetor` (38 avaliações provenientes de Shopee, Mercado Livre, TikTok e Amazon).

Na página você pode testar os filtros de canal/estrelas/somente com mídia, reproduzir vídeos já importados, abrir URLs de imagem/vídeo `/media/...` e conferir `/api/v1/media/status` diretamente. Os vídeos do TikTok ainda pendentes podem não reproduzir; isso não afeta a página ou os comentários.

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
- \`GET /api/v1/media/status\` mostra o progresso geral e os campos \`total_tiktok\`, \`baixados_tiktok\` e \`pendentes_tiktok\`.
- \`midias\`, \`midias_info\` e \`midia_links\` na API/JSON/CSV de download usam nossos links. Os valores antigos são preservados em \`midias_originais\`/\`midia_links_originais\` no JSON.
- O widget utiliza nossos links e exibe imagens e vídeos com controles de reprodução.
- O endpoint \`GET /media/<id>\` baixa arquivos diretos no primeiro acesso. Para TikTok, a extração roda somente em segundo plano, sem travar as LPs. Mídias não disponíveis retornam \`503\`.
- São **423 referências**: 369 URLs diretas e **54 páginas de vídeos TikTok**. O [yt-dlp](https://github.com/yt-dlp/yt-dlp) tenta baixar os vídeos públicos e salvá-los no volume persistente. Bloqueios, vídeos removidos ou restrições podem impedir parte dos downloads.
- O download de cada mídia depende de sua disponibilidade e das permissões do servidor remoto; uma referência não comprova que o arquivo foi importado.
- O espelho não armazena avaliações novas automaticamente: a base vem dos CSVs versionados no GitHub.

### TikTok: erro "Unexpected response from webpage request"

É um problema relatado em setembro/2026 no extrator do TikTok ([yt-dlp #17604](https://github.com/yt-dlp/yt-dlp/issues/17604)). Para mitigar:

- `curl_cffi==0.16.0` (versão compatível com a correção publicada);
- tenta User-Agent Chrome 145 e, se falhar, Firefox 155;
- prioriza MP4/H.264 para reprodução nas LPs;
- ao atualizar a estratégia, as falhas TikTok anteriores são tentadas novamente no primeiro ciclo de importação após o deploy, sem apagar as mídias já baixadas.

Não garante sucesso em todos os links: o TikTok pode bloquear IPs de servidores, exigir autenticação ou remover o vídeo. O contador `baixados_tiktok` confirma o sucesso real após o deploy.

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
Os downloads são limitados às URLs de CDN e aos links TikTok \`/@perfil/video/ID\` presentes nos CSVs, com verificação de formato e tamanho. Não é possível solicitar URLs arbitrárias ao servidor. Imagens e vídeos de terceiros continuam sujeitos a direitos autorais, termos das plataformas e permissões de uso publicitário.

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

A URL estática entrega a base inteira como snapshot de origem e **ainda contém URLs externas**. Para LPs, use exclusivamente a API hospedada no Easypanel: ela devolve as URLs `/media/...` do nosso domínio, com filtros e Swagger.

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