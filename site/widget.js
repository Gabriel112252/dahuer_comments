/* Dahuer Comments — widget leve e sem dependências para LPs. */
(function () {
  'use strict';
  const script = document.currentScript;
  const defaultOrigin = script ? new URL(script.src).origin : location.origin;
  const running = new WeakMap();
  const videoDialogs = new WeakMap();
  const styles = `
    :host { display:block; color:#182a29; font:inherit; --dc-accent:#087d70; --dc-card:#fff; --dc-text:#172d2b; --dc-muted:#647773; --dc-border:#e5ece9; }
    :host([data-theme="dark"]) { --dc-accent:#63dfc1; --dc-card:#1f302f; --dc-text:#f2f7f5; --dc-muted:#a8bdb6; --dc-border:#40504d; }
    * { box-sizing:border-box; }
    .dc-root { color:var(--dc-text); font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    :host([data-theme="dark"]) .dc-root { background:#142724; border-radius:16px; padding:18px; }
    .dc-top { display:flex; gap:14px; align-items:center; justify-content:space-between; margin:0 0 18px; }
    .dc-title { font-size:19px; font-weight:800; letter-spacing:-.5px; margin:0; }
    .dc-sub { color:var(--dc-muted); font-size:13px; margin:5px 0 0; }
    .dc-count { border:1px solid var(--dc-border); border-radius:999px; padding:7px 11px; color:var(--dc-muted); white-space:nowrap; font-size:12px; }
    .dc-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px; }
    .dc-card { background:var(--dc-card); border:1px solid var(--dc-border); border-radius:16px; padding:18px; min-width:0; box-shadow:0 3px 16px rgba(0,0,0,.025); }
    .dc-person { display:flex; align-items:center; gap:10px; min-width:0; }
    .dc-avatar { width:34px; height:34px; flex:0 0 34px; border-radius:12px; display:grid; place-items:center; background:#def6ec; color:#05685e; font-size:13px; font-weight:800; }
    .dc-person-meta { flex:1; min-width:0; }
    .dc-avatar-platform { background:#e5f4ef; color:#087d70; font-size:18px; }
    :host([data-theme="dark"]) .dc-avatar-platform { background:#2b4c44; color:#86e6c8; }
    .dc-avatar-shopee { background:#fff0e7; color:#e85b20; }
    .dc-avatar-mercadolivre { background:#fff6d5; color:#766000; }
    .dc-avatar-tiktok { background:#182b2b; color:#b8fff1; }
    .dc-avatar-amazon { background:#fff2dd; color:#a66c0c; }
    :host([data-theme="dark"]) .dc-avatar-shopee { background:#663722; color:#ffb58d; }
    :host([data-theme="dark"]) .dc-avatar-mercadolivre { background:#4e4527; color:#ffdf7a; }
    :host([data-theme="dark"]) .dc-avatar-tiktok { background:#102425; color:#96e7da; }
    :host([data-theme="dark"]) .dc-avatar-amazon { background:#43351d; color:#ffd18b; }
    .dc-name { font-weight:700; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .dc-source { color:var(--dc-muted); font-size:11px; margin-top:3px; }
    .dc-rating { color:#efad36; letter-spacing:2px; font-size:16px; margin:15px 0 8px; }
    .dc-text { font-size:13px; line-height:1.75; overflow-wrap:anywhere; margin:0; white-space:pre-line; }
    .dc-text.clamp { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:5; overflow:hidden; }
    .dc-more { display:inline-block; border:0; background:none; color:var(--dc-accent); font:inherit; font-weight:700; font-size:12px; cursor:pointer; margin:7px 0 0; padding:0; }
    .dc-variant { font-size:11px; color:var(--dc-muted); margin-top:10px; }
    .dc-media { display:flex; gap:9px; margin-top:14px; flex-wrap:wrap; align-items:flex-start; }
    .dc-media > a { display:block; flex:0 0 auto; }
    .dc-media > a img { display:block; width:74px; height:94px; object-fit:cover; border-radius:11px; background:#edf2ef; border:1px solid var(--dc-border); transition:transform .15s; }
    .dc-media > a:hover img { transform:translateY(-2px); }
    .dc-video-tile { position:relative; flex:0 0 auto; width:128px; height:170px; padding:0; border:1px solid var(--dc-border); border-radius:13px; overflow:hidden; cursor:pointer; background:linear-gradient(155deg,#45605c,#11201e 85%); color:#fff; text-align:center; box-shadow:0 6px 18px #00000018; transition:transform .17s ease,box-shadow .17s ease; }
    .dc-video-tile:hover { transform:translateY(-2px); box-shadow:0 10px 22px #0000002a; }
    .dc-video-tile:focus-visible,.dc-close:focus-visible { outline:3px solid #7ee9be; outline-offset:3px; }
    .dc-video-poster { position:absolute; inset:0; width:100%; height:100%; display:block; object-fit:cover; }
    .dc-video-shade { position:absolute; inset:0; background:linear-gradient(180deg,#0005 0%,transparent 38%,#000b 100%); }
    .dc-video-badge { position:absolute; top:9px; left:9px; font-size:9px; font-weight:800; letter-spacing:.045em; color:#fff; background:#0009; border:1px solid #fff4; border-radius:99px; padding:5px 8px; }
    .dc-play { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:48px; height:48px; border-radius:50%; background:#fffffff2; color:#164e3e; display:grid; place-items:center; padding-left:3px; box-shadow:0 6px 22px #0004; font-size:21px; font-weight:900; transition:transform .17s; }
    .dc-video-tile:hover .dc-play { transform:translate(-50%,-50%) scale(1.08); }
    .dc-video-caption { position:absolute; bottom:11px; left:10px; right:10px; color:#fff; font-size:11px; line-height:1.3; font-weight:750; text-align:left; text-shadow:0 1px 5px #0009; }
    .dc-modal[hidden] { display:none!important; }
    .dc-modal { position:fixed; inset:0; z-index:2147483647; background:#06110eea; padding:24px; display:flex; align-items:center; justify-content:center; }
    .dc-modal-panel { position:relative; background:#13201c; color:#fff; border:1px solid #ffffff2b; border-radius:20px; width:min(440px,100%); max-height:95vh; overflow:hidden; box-shadow:0 24px 70px #0009; }
    .dc-modal-top { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:13px 16px; font:700 13px/1.4 Inter,system-ui,sans-serif; }
    .dc-close { border:1px solid #ffffff3b; background:#ffffff1a; color:#fff; font-size:19px; cursor:pointer; border-radius:50%; height:35px; width:35px; display:grid; place-items:center; }
    .dc-modal-video { display:block; width:100%; max-height:75vh; min-height:220px; background:#000; object-fit:contain; }
    .dc-modal-bottom { font:12px/1.5 Inter,system-ui,sans-serif; padding:11px 16px 15px; display:flex; gap:8px; justify-content:space-between; align-items:center; }
    .dc-modal-bottom a { color:#9beed3; text-decoration:none; font-weight:700; }
    .dc-video-error { color:#ffd0c2; font-size:12px; margin:0; padding:0 15px 12px; }
    .dc-video-error[hidden] { display:none!important; }
    @media (prefers-reduced-motion:reduce) { .dc-video-tile,.dc-play,.dc-media > a img { transition:none; } }
    @media (max-width:640px) { .dc-modal { padding:10px; } .dc-modal-panel { border-radius:14px; } }

    .dc-bottom { display:flex; margin-top:12px; justify-content:space-between; align-items:center; gap:10px; }
    .dc-link { color:var(--dc-accent); font-size:11px; text-decoration:none; font-weight:700; }
    .dc-link:hover { text-decoration:underline; }
    .dc-date { color:var(--dc-muted); font-size:11px; }
    .dc-status { padding:34px 16px; border:1px dashed var(--dc-border); color:var(--dc-muted); text-align:center; border-radius:14px; font-size:13px; }
    .dc-foot { color:var(--dc-muted); font-size:11px; margin:14px 0 0; }
    @media (max-width:640px) { .dc-grid { grid-template-columns:1fr; } .dc-card { padding:15px; } .dc-top { align-items:flex-start; } }
  `;
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function setLink(a, url) {
    try {
      const u = new URL(url);
      if (!['https:', 'http:'].includes(u.protocol)) return false;
      a.href = u.href; a.target = '_blank'; a.rel = 'noopener noreferrer nofollow';
      return true;
    } catch (_) { return false; }
  }
  function drawCard(c, openVideo) {
    const card = el('article', 'dc-card');
    const person = el('div', 'dc-person');
    const author = (c.autor || '').trim();
    const platform = (c.canal || 'Marketplace').trim();
    const normalizedAuthor = author.toLocaleLowerCase('pt-BR');
    const anonymous = !author || /^(cliente(?:\s+\d+)?|anônimo|anonimo|anonymous|usuário|usuario|sem nome|não informado|nao informado)$/i.test(normalizedAuthor);
    const anonymousNames = {
      'Shopee': 'Comprador da Shopee',
      'Mercado Livre': 'Comprador do Mercado Livre',
      'Amazon': 'Comprador da Amazon',
      'TikTok': 'Autor no TikTok'
    };
    const anonymousLabel = anonymousNames[platform] || 'Autor não identificado';
    const initial = anonymous ? platform.charAt(0).toUpperCase() : author.charAt(0).toUpperCase();
    const platformClass = {'Shopee':'shopee','Mercado Livre':'mercadolivre',
      'TikTok':'tiktok','Amazon':'amazon'}[platform] || '';
    const avatar = el('span', 'dc-avatar' + (anonymous ? ' dc-avatar-platform dc-avatar-' + platformClass : ''), initial);
    const meta = el('div', 'dc-person-meta');
    meta.append(el('div', 'dc-name', anonymous ? anonymousLabel : author),
      el('div', 'dc-source', anonymous
        ? 'Nome não divulgado · ' + (c.produto || 'Produto')
        : platform + ' · ' + (c.produto || 'Produto')));
    person.append(avatar, meta);
    card.append(person);
    const nota = Number(c.nota);
    if (Number.isInteger(nota) && nota >= 1 && nota <= 5) {
      const stars = el('div', 'dc-rating', '★'.repeat(nota) + '☆'.repeat(5 - nota));
      stars.setAttribute('aria-label', nota + ' de 5 estrelas');
      card.append(stars);
    }
    const review = el('p', 'dc-text clamp', c.texto || '');
    card.append(review);
    if ((c.texto || '').length > 230) {
      const expand = el('button', 'dc-more', 'Ler avaliação completa');
      expand.type = 'button';
      expand.addEventListener('click', () => {
        const isClamped = review.classList.toggle('clamp');
        expand.textContent = isClamped ? 'Ler avaliação completa' : 'Mostrar menos';
      });
      card.append(expand);
    }
    if (c.variacao) card.append(el('div', 'dc-variant', c.variacao));
    const mediaItems = Array.isArray(c.midias_info) ? c.midias_info.slice(0, 3)
      : (Array.isArray(c.midias) ? c.midias.slice(0, 3).map(url => ({url, tipo:'image'})) : []);
    if (mediaItems.length) {
      const media = el('div', 'dc-media');
      mediaItems.forEach((item, i) => {
        if (!item || typeof item.url !== 'string' || !/^https:\/\//i.test(item.url)) return;
        if (item.tipo === 'video') {
          const tile = el('button', 'dc-video-tile');
          tile.type = 'button';
          tile.setAttribute('aria-label', 'Reproduzir vídeo da avaliação ' + (i + 1));
          const coverUrl = typeof item.poster_url === 'string' && item.poster_url.startsWith('https://')
            ? item.poster_url : item.url + '/poster';
          if (/\/media\/[a-f0-9]{32}\/poster(?:\?|$)/i.test(coverUrl)) {
            const image = el('img', 'dc-video-poster');
            image.loading = 'lazy'; image.decoding = 'async';
            image.alt = '';
            image.src = coverUrl;
            image.addEventListener('error', () => image.remove());
            tile.append(image);
          }
          tile.append(el('span', 'dc-video-shade'),
            el('span', 'dc-video-badge', 'VÍDEO'),
            el('span', 'dc-play', '▶'),
            el('span', 'dc-video-caption', 'Assistir à avaliação'));
          tile.addEventListener('click', () => openVideo(item.url, c.link, tile));
          media.append(tile);
        } else if (item.tipo === 'image') {
          const a = el('a');
          if (!setLink(a, c.link || item.url)) return;
          const img = el('img');
          img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
          img.src = item.url; img.alt = 'Foto da avaliação ' + (i + 1);
          img.addEventListener('error', () => a.remove());
          a.append(img); media.append(a);
        }
      });
      if (media.childNodes.length) card.append(media);
    }
    const footer = el('div', 'dc-bottom');
    if (c.data) footer.append(el('span', 'dc-date', c.data));
    const source = el('a', 'dc-link', 'Ver avaliação original ↗');
    if (setLink(source, c.link)) footer.append(source);
    card.append(footer);
    return card;
  }
  function makeVideoDialog(shadow) {
    const modal = el('div', 'dc-modal');
    modal.hidden = true;
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Reprodutor de vídeo da avaliação');
    const panel = el('div', 'dc-modal-panel');
    const top = el('div', 'dc-modal-top');
    top.append(el('span', '', 'Vídeo da avaliação'));
    const closeButton = el('button', 'dc-close', '×');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Fechar vídeo');
    top.append(closeButton);
    const video = el('video', 'dc-modal-video');
    video.controls = true;
    video.playsInline = true;
    video.preload = 'none';
    video.setAttribute('aria-label', 'Vídeo enviado com a avaliação');
    const errorText = el('p', 'dc-video-error', 'Este vídeo ainda não está disponível no nosso servidor.');
    errorText.hidden = true;
    video.addEventListener('error', () => { errorText.hidden = false; });
    const bottom = el('div', 'dc-modal-bottom');
    bottom.append(el('span', '', 'Avaliação publicada em marketplace'));
    const original = el('a', '', 'Ver original ↗');
    bottom.append(original);
    panel.append(top, video, errorText, bottom);
    modal.append(panel);
    shadow.append(modal);
    let opener = null;
    function onKeyDown(e) {
      if (e.key === 'Escape') close();
      if (e.key === 'Tab' && !modal.hidden) {
        const focusables = [...panel.querySelectorAll('button, a[href], video[controls]')];
        const first = focusables[0], last = focusables[focusables.length - 1];
        if (e.shiftKey && shadow.activeElement === first) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && shadow.activeElement === last) {
          e.preventDefault(); first.focus();
        }
      }
    }
    function close() {
      if (modal.hidden) return;
      modal.hidden = true;
      video.pause();
      video.removeAttribute('src');
      video.load();
      document.removeEventListener('keydown', onKeyDown);
      if (opener && opener.isConnected) opener.focus();
      opener = null;
    }
    function open(url, link, button) {
      if (!/^https:\/\//i.test(url)) return;
      opener = button;
      errorText.hidden = true;
      const valid = setLink(original, link || '');
      original.hidden = !valid;
      video.src = url;
      modal.hidden = false;
      document.addEventListener('keydown', onKeyDown);
      closeButton.focus();
      const playing = video.play();
      if (playing && typeof playing.catch === 'function') playing.catch(() => {});
    }
    closeButton.addEventListener('click', close);
    modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
    return {open,close};
  }

  async function mount(target, options) {
    const node = typeof target === 'string' ? document.getElementById(target) : target;
    if (!node) return;
    const previousDialog = videoDialogs.get(node);
    if (previousDialog) previousDialog.close();
    const opts = Object.assign({limit:6,theme:'light'}, options || {});
    const request = (running.get(node) || 0) + 1;
    running.set(node, request);
    const shadow = node.shadowRoot || node.attachShadow({mode:'open'});
    node.dataset.theme = opts.theme === 'dark' ? 'dark' : 'light';
    const style = el('style'); style.textContent = styles;
    const wrap = el('section','dc-root');
    wrap.append(el('div','dc-status','Carregando avaliações…'));
    shadow.replaceChildren(style,wrap);
    const params = new URLSearchParams({per_page: String(Math.max(1,Math.min(100,parseInt(opts.limit,10) || 6)))});
    if (opts.produto) params.set('produto',opts.produto);
    if (opts.canal) params.set('canal',opts.canal);
    if (opts.nota) params.set('nota',opts.nota);
    if (opts.q) params.set('q',opts.q);
    if (opts.com_midia) params.set('com_midia','true');
    if (opts.com_video) params.set('com_video','true');
    params.set('ordem',opts.ordem === 'antigas' ? 'antigas' : 'recentes');
    if (opts.priorizar_video) params.set('priorizar_video','true');
    let data;
    try {
      const base = opts.apiBase || defaultOrigin;
      const response = await fetch(new URL('/api/v1/comments?' + params.toString(), base));
      if (!response.ok) throw Error('HTTP ' + response.status);
      data = await response.json();
    } catch (_) {
      if (running.get(node) === request) wrap.replaceChildren(el('div','dc-status','Não foi possível carregar as avaliações agora.'));
      if (typeof opts.onResult === 'function') opts.onResult({error:true,total:0});
      return;
    }
    if (running.get(node) !== request) return;
    wrap.replaceChildren();
    const header = el('div','dc-top');
    const headerLeft = el('div');
    headerLeft.append(el('h2','dc-title',opts.title || 'O que dizem nossos clientes'),
      el('p','dc-sub','Avaliações compartilhadas por compradores'));
    header.append(headerLeft,el('span','dc-count', data.total + ' avaliação' + (data.total === 1 ? '' : 'ões')));
    wrap.append(header);
    if (!data.data.length) wrap.append(el('div','dc-status','Nenhuma avaliação encontrada para estes filtros.'));
    else {
      const dialog = makeVideoDialog(shadow);
      videoDialogs.set(node, dialog);
      const grid = el('div','dc-grid');
      data.data.forEach(c => grid.append(drawCard(c, dialog.open)));
      wrap.append(grid);
      wrap.append(el('p','dc-foot','Comentários de marketplaces • Consulte a fonte original em cada avaliação.'));
    }
    if (typeof opts.onResult === 'function') opts.onResult({total:data.total,shown:data.data.length});
  }
  const api = {mount};
  window.DahuerComments = api;
  if (script && script.dataset.target) {
    const args = {
      produto:script.dataset.produto || '',
      canal:script.dataset.canal || '',
      nota:script.dataset.nota || '',
      q:script.dataset.q || '',
      com_midia:script.dataset.comMidia === 'true',
      com_video:script.dataset.comVideo === 'true',
      priorizar_video:script.dataset.priorizarVideo === 'true',
      ordem:script.dataset.ordem || 'recentes',
      limit:script.dataset.limit || '6',
      theme:script.dataset.theme || 'light',
      apiBase:defaultOrigin
    };
    const run = () => mount(script.dataset.target,args);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',run,{once:true});
    else run();
  }
})();
