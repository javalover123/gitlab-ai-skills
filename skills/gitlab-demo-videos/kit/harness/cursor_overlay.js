// Injected into every page (Playwright addInitScript). Draws a visible mouse cursor that
// follows real mouse events (Playwright's video has no cursor), switches to a hand over
// clickable elements, and shows a subtle ripple on mousedown. Position survives page loads
// via sessionStorage so navigation doesn't make the cursor jump.
(() => {
  if (window.__demoCursorInstalled) return;
  window.__demoCursorInstalled = true;
  const KEY = '__demoCursorPos';
  let pos = { x: 1400, y: 640 };
  try {
    pos = JSON.parse(sessionStorage.getItem(KEY)) || pos;
  } catch (e) {
    /* ignore */
  }
  const ARROW =
    '<svg width="26" height="26" viewBox="0 0 26 26" xmlns="http://www.w3.org/2000/svg"><path d="M3 2 L3 20.5 L7.9 16.1 L11.1 23.3 L14.3 21.9 L11.2 14.9 L17.8 14.9 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  const HAND =
    '<svg width="26" height="26" viewBox="0 0 26 26" xmlns="http://www.w3.org/2000/svg"><path d="M9.2 12V4.3a1.7 1.7 0 0 1 3.4 0v6.2l.1-1.3a1.6 1.6 0 0 1 3.2.2v1.3a1.6 1.6 0 0 1 3.2.1v1.2a1.5 1.5 0 0 1 3 .2v5.3c0 3.6-2.7 6.3-6.3 6.3h-1.6c-2.2 0-3.7-.8-5-2.4L4.5 17a1.7 1.7 0 0 1 2.5-2.3z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  const style = document.createElement('style');
  style.textContent = `
    #demo-cursor{position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;will-change:transform;filter:drop-shadow(0 1px 1.5px rgba(0,0,0,.35))}
    #demo-cursor .h{display:none;position:absolute;left:-7px;top:-2px}
    #demo-cursor.hand .a{display:none} #demo-cursor.hand .h{display:block}
    #demo-cursor .a{position:absolute;left:-3px;top:-2px}
    .demo-ripple{position:fixed;z-index:2147483646;pointer-events:none;width:36px;height:36px;margin:-18px 0 0 -18px;border-radius:50%;
      background:rgba(99,102,241,.28);border:2px solid rgba(99,102,241,.55);animation:demo-ripple .55s ease-out forwards}
    @keyframes demo-ripple{from{transform:scale(.35);opacity:1}to{transform:scale(1.35);opacity:0}}
    html.demo-hide-native-cursor, html.demo-hide-native-cursor *{cursor:none !important}`;
  const el = document.createElement('div');
  el.id = 'demo-cursor';
  el.innerHTML = `<div class="a">${ARROW}</div><div class="h">${HAND}</div>`;
  const place = () => {
    el.style.transform = `translate(${pos.x}px, ${pos.y}px)`;
  };
  const isClickable = (x, y) => {
    const t = document.elementFromPoint(x, y);
    if (!t || t === el) return false;
    const c = getComputedStyle(t).cursor;
    return c === 'pointer';
  };
  const mount = () => {
    if (!document.documentElement) return requestAnimationFrame(mount);
    document.documentElement.appendChild(style);
    document.documentElement.appendChild(el);
    place();
    return undefined;
  };
  mount();
  document.addEventListener(
    'mousemove',
    (e) => {
      pos = { x: e.clientX, y: e.clientY };
      place();
      el.classList.toggle('hand', isClickable(pos.x, pos.y));
      try {
        sessionStorage.setItem(KEY, JSON.stringify(pos));
      } catch (err) {
        /* ignore */
      }
    },
    true,
  );
  document.addEventListener(
    'mousedown',
    (e) => {
      const r = document.createElement('div');
      r.className = 'demo-ripple';
      r.style.left = `${e.clientX}px`;
      r.style.top = `${e.clientY}px`;
      document.documentElement.appendChild(r);
      setTimeout(() => r.remove(), 700);
    },
    true,
  );
})();
