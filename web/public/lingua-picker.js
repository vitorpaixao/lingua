(function () {
  if (window.__linguaPickerLoaded) return;
  window.__linguaPickerLoaded = true;

  let active = false;
  let lastHovered = null;
  const OUTLINE = '2px solid #1677ff';

  function findFiber(el) {
    const key = Object.keys(el).find(
      (k) => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'),
    );
    return key ? el[key] : null;
  }

  function climbToDebugSource(fiber) {
    let f = fiber;
    while (f) {
      if (f._debugSource) {
        const { fileName, lineNumber, columnNumber } = f._debugSource;
        if (fileName) {
          // Trim absolute prefix if running locally
          let path = String(fileName);
          const srcIdx = path.lastIndexOf('/src/');
          if (srcIdx >= 0) path = path.slice(srcIdx + 1);
          return `${path}:${lineNumber}:${columnNumber || 0}`;
        }
      }
      f = f.return;
    }
    return null;
  }

  function nearestComponentName(fiber) {
    let f = fiber;
    while (f) {
      const t = f.type;
      if (typeof t === 'function') {
        return t.displayName || t.name || null;
      }
      if (typeof t === 'object' && t && (t.displayName || t.render?.displayName)) {
        return t.displayName || t.render?.displayName || null;
      }
      f = f.return;
    }
    return null;
  }

  function cssSelectorFor(el) {
    if (el.id) return `#${el.id}`;
    const path = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && path.length < 4) {
      let part = cur.tagName.toLowerCase();
      if (cur.classList.length) {
        part += '.' + Array.from(cur.classList).slice(0, 3).join('.');
      }
      const parent = cur.parentElement;
      if (parent) {
        const idx = Array.from(parent.children).indexOf(cur) + 1;
        part += `:nth-child(${idx})`;
      }
      path.unshift(part);
      cur = cur.parentElement;
    }
    return path.join(' > ');
  }

  function buildPayload(el) {
    const fiber = findFiber(el);
    const source = fiber ? climbToDebugSource(fiber) : null;
    const component = fiber ? nearestComponentName(fiber) : null;
    const selector = cssSelectorFor(el);
    const linguaId = el.getAttribute && el.getAttribute('data-lingua-id');
    const summary = component || (linguaId ? linguaId : el.tagName.toLowerCase());
    const text = el.innerText ? String(el.innerText).slice(0, 80) : '';
    let html = el.outerHTML ? el.outerHTML : '';
    if (html.length > 200) html = html.slice(0, 200) + '…';
    const payload = { selector, summary };
    if (source) payload.source = source;
    if (component) payload.component = component;
    if (linguaId) payload.dataLinguaId = linguaId;
    if (text) payload.text = text;
    if (html) payload.html = html;
    return payload;
  }

  function clearOutline() {
    if (lastHovered) {
      lastHovered.style.outline = '';
      lastHovered.style.outlineOffset = '';
      lastHovered = null;
    }
  }

  function onMouseOver(e) {
    if (!active) return;
    clearOutline();
    lastHovered = e.target;
    lastHovered.style.outline = OUTLINE;
    lastHovered.style.outlineOffset = '1px';
  }

  function onClick(e) {
    if (!active) return;
    e.preventDefault();
    e.stopPropagation();
    const payload = buildPayload(e.target);
    window.parent.postMessage(
      { type: 'lingua:selection', payload, summary: payload.summary },
      '*',
    );
    disable();
  }

  function onKey(e) {
    if (!active) return;
    if (e.key === 'Escape') {
      window.parent.postMessage({ type: 'lingua:cancel' }, '*');
      disable();
    }
  }

  function enable() {
    if (active) return;
    active = true;
    document.body.style.cursor = 'crosshair';
    document.addEventListener('mouseover', onMouseOver, true);
    document.addEventListener('click', onClick, true);
    document.addEventListener('keydown', onKey, true);
  }

  function disable() {
    active = false;
    document.body.style.cursor = '';
    clearOutline();
    document.removeEventListener('mouseover', onMouseOver, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKey, true);
  }

  window.addEventListener('message', (e) => {
    const data = e.data;
    if (!data || typeof data !== 'object') return;
    if (data.type === 'lingua:enable_pick') enable();
    else if (data.type === 'lingua:disable') disable();
  });
})();
