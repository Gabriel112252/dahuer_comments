/* Dahuer Comments — widget leve e sem dependências para LPs. */
(function () {
  'use strict';
  const script = document.currentScript;
  const defaultOrigin = script ? new URL(script.src).origin : location.origin;
  const running = new WeakMap();
  const styles = `
    :host { display:block; color:#182a29; font:inherit; --dc-accent:#087d70; --dc-card:#fff; --dc-text:#172d2b; --dc-muted:#647773; --dc-border:#e5ece9; }
    :host([data-theme="dark"]) { --dc-accent:#63dfc1; --dc-card:#1f302f; --dc-text:#f2f7f5; --dc-muted:#a8bdb6; --dc-border:#40504d; }
    * { box-sizing:border-box; }
    .dc-root { color:var(--dc-text); font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    .dc-top { display:flex; gap:14px; align-items:center; justify-content:space-between; margin:0 0 18px; }
    .dc-title { font-size:19px; font-weight:800; letter-spacing:-.5px; margin:0; }
    .dc-sub { color:var(--dc-muted); font-size:13px; margin:5px 0 0; }
    .dc-count { border:1px solid var(--dc-border); border-radius:999px; padding:7px 11px; color:var(--dc-muted); white-space:nowrap; font-size:12px; }
    .dc-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:13px; }
    .dc-card { background:var(--dc-card); border:1px solid var(--dc-border); border-radius:16px; padding:18px; min-width:0; box-shadow:0 3px 16px rgba(0,0,0,.025); }
    .dc-person { display:flex; align-items:center; gap:10px; min-width:0; }
    .dc-avatar { width:34px; height:34px; flex:0 0 34px; border-radius:12px; display:grid; place-items:center; background:#def6ec; color:#05685e; font-size:13px; font-weight:800; }
    .dc-person-meta { flex:1; min-width:0; }
    .dc-name { font-weight:700; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .dc-source { color:var(--dc-muted); font-size:11px; margin-top:3px; }
    .dc-rating { color:#efad36; letter-spacing:2px; font-size:16px; margin:15px 0 8px; }
    .dc-text { font-size:13px; line-height:1.75; overflow-wrap:anywhere; margin:0; white-space:pre-line; }
    .dc-text.clamp { display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:5; overflow:hidden; }
    .dc-more { display:inline-block; border:0; background:none; color:var(--dc-accent); font:inherit; font-weight:700; font-size:12px; cursor:pointer; margin:7px 0 0; padding:0; }
    .dc-variant { font-size:11px; color:var(--dc-muted); margin-top:10px; }
    .dc-media { display:flex; gap:6px; margin-top:12px; overflow:hidden; }
    .dc-media img { width:67px; height:67px; object-fit:cover; border-radius:9px; background:#edf2ef; border:1px solid var(--dc-border); }
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
  function drawCard(c) {
    const card = el('article', 'dc-card');
    const person = el('div', 'dc-person');
    const avatar = el('span', 'dc-avatar', (c.autor || 'C').trim().charAt(0).toUpperCase());
    const meta = el('div', 'dc-person-meta');
    meta.append(el('div', 'dc-name', c.autor || 'Cliente'),
      el('div', 'dc-source', (c.canal || 'Marketplace') + ' · ' + (c.produto || 'Produto')));
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
    const images = (Array.isArray(c.midias) ? c.midias : [])
      .filter(u => /^https:\/\//i.test(u) && !/\.(mp4|webm|mov)(\?|$)/i.test(u)).slice(0, 3);
    if (images.length) {
      const media = el('div', 'dc-media');
      images.forEach((url, i) => {
        const a = el('a');
        if (!setLink(a, c.link || url)) return;
        const img = el('img');
        img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer';
        img.src = url; img.alt = 'Foto da avaliação ' + (i + 1);
        img.addEventListener('error', () => { a.remove(); });
        a.append(img); media.append(a);
      });
      card.append(media);
    }
    const footer = el('div', 'dc-bottom');
    if (c.data) footer.append(el('span', 'dc-date', c.data));
    const source = el('a', 'dc-link', 'Ver avaliação original ↗');
    if (setLink(source, c.link)) footer.append(source);
    card.append(footer);
    return card;
  }
  async function mount(target, options) {
    const node = typeof target === 'string' ? document.getElementById(target) : target;
    if (!node) return;
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
      const grid = el('div','dc-grid');
      data.data.forEach(c => grid.append(drawCard(c)));
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
      limit:script.dataset.limit || '6',
      theme:script.dataset.theme || 'light',
      apiBase:defaultOrigin
    };
    const run = () => mount(script.dataset.target,args);
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',run,{once:true});
    else run();
  }
})();
