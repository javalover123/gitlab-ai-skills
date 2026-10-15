// Injected into every page (Playwright addInitScript). A small, subtle step caption at the bottom of the
// viewport, styled like a GitLab dark tooltip. Driven from scenarios via ctx.caption(text) / ctx.hideCaption().
// It survives page navigations (sessionStorage) so a caption can span a click that loads a new page.
(() => {
  if (window.__demoCaptionInstalled) return;
  window.__demoCaptionInstalled = true;
  const KEY = '__demoCaption';
  const style = document.createElement('style');
  style.textContent = `
    #demo-caption{position:fixed;left:50%;bottom:34px;z-index:2147483645;pointer-events:none;transform:translate(-50%,6px);
      opacity:0;transition:opacity .28s ease,transform .28s ease;max-width:1100px;
      font-family:"GitLab Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:17px;line-height:24px;
      font-weight:500;letter-spacing:.005em;color:#fff;background:rgba(31,30,36,.9);border-radius:8px;padding:9px 18px;
      box-shadow:0 4px 14px rgba(5,5,6,.22),0 0 0 1px rgba(255,255,255,.06) inset;white-space:nowrap;display:flex;gap:10px;align-items:center}
    #demo-caption.show{opacity:1;transform:translate(-50%,0)}
    #demo-caption .step{color:#bfbfc3;font-weight:600;font-size:14px;letter-spacing:.02em;text-transform:uppercase}
    #demo-caption .sep{width:1px;height:16px;background:rgba(255,255,255,.22)}`;
  const el = document.createElement('div');
  el.id = 'demo-caption';
  const render = (c) => {
    el.innerHTML = '';
    if (c.step) {
      const s = document.createElement('span');
      s.className = 'step';
      s.textContent = c.step;
      const sep = document.createElement('span');
      sep.className = 'sep';
      el.append(s, sep);
    }
    const t = document.createElement('span');
    t.textContent = c.text;
    el.append(t);
  };
  const api = {
    show(text, { step = '', instant = false } = {}) {
      const c = { text, step };
      try { sessionStorage.setItem(KEY, JSON.stringify(c)); } catch (e) { /* ignore */ }
      render(c);
      if (instant) { el.style.transition = 'none'; el.classList.add('show'); el.offsetWidth; el.style.transition = ''; }
      else requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('show')));
    },
    hide() {
      try { sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ }
      el.classList.remove('show');
    },
  };
  window.__demoCaption = api;
  const mount = () => {
    if (!document.documentElement) return requestAnimationFrame(mount);
    document.documentElement.appendChild(style);
    document.documentElement.appendChild(el);
    try {
      const c = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (c) api.show(c.text, { step: c.step, instant: true });
    } catch (e) { /* ignore */ }
    return undefined;
  };
  mount();
})();
