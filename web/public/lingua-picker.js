(() => {
  if (window.__linguaPickerLoaded) return
  window.__linguaPickerLoaded = true

  const HTML_TAGS = new Set([
    'div','span','button','a','p','h1','h2','h3','h4','h5','h6','ul','ol','li',
    'img','input','textarea','select','option','form','label','section','article',
    'header','footer','main','nav','aside','table','thead','tbody','tr','td','th',
    'svg','path','g','circle','rect','line','polygon','polyline','figure','figcaption',
    'br','hr','strong','em','b','i','small','code','pre','blockquote',
  ])

  let active = false
  let overlay = null
  let lastHovered = null

  function ensureOverlay() {
    if (overlay) return overlay
    overlay = document.createElement('div')
    overlay.id = '__lingua_picker_overlay'
    Object.assign(overlay.style, {
      position: 'fixed',
      pointerEvents: 'none',
      border: '2px solid #3b82f6',
      backgroundColor: 'rgba(59, 130, 246, 0.15)',
      zIndex: '2147483647',
      transition: 'all 50ms ease-out',
      boxSizing: 'border-box',
      display: 'none',
    })
    document.body.appendChild(overlay)
    return overlay
  }

  function positionOverlay(el) {
    const o = ensureOverlay()
    const r = el.getBoundingClientRect()
    o.style.display = 'block'
    o.style.left = `${r.left}px`
    o.style.top = `${r.top}px`
    o.style.width = `${r.width}px`
    o.style.height = `${r.height}px`
  }

  function hideOverlay() {
    if (overlay) overlay.style.display = 'none'
  }

  function getFiber(el) {
    const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'))
    return key ? el[key] : null
  }

  function extractSource(el) {
    let fiber = getFiber(el)
    let source = null
    let component = null
    let hops = 0
    while (fiber && hops < 30) {
      if (!source && fiber._debugSource) {
        const s = fiber._debugSource
        source = `${s.fileName}:${s.lineNumber}${s.columnNumber ? ':' + s.columnNumber : ''}`
      }
      if (!component && fiber.type && typeof fiber.type !== 'string') {
        const name = fiber.type.displayName || fiber.type.name
        if (name && !HTML_TAGS.has(name.toLowerCase())) component = name
      }
      if (source && component) break
      fiber = fiber.return
      hops++
    }
    return { source, component }
  }

  function buildSelector(el) {
    if (el.id) return `#${CSS.escape(el.id)}`
    const parts = []
    let cur = el
    let depth = 0
    while (cur && cur.nodeType === 1 && depth < 4) {
      let part = cur.tagName.toLowerCase()
      if (cur.classList.length) {
        const cls = Array.from(cur.classList).slice(0, 3).map((c) => `.${CSS.escape(c)}`).join('')
        part += cls
      }
      const parent = cur.parentElement
      if (parent) {
        const same = Array.from(parent.children).filter((c) => c.tagName === cur.tagName)
        if (same.length > 1) {
          const idx = same.indexOf(cur) + 1
          part += `:nth-of-type(${idx})`
        }
      }
      parts.unshift(part)
      if (cur.id) {
        parts[0] = `#${CSS.escape(cur.id)}`
        break
      }
      cur = cur.parentElement
      depth++
    }
    return parts.join(' > ')
  }

  function truncate(s, n) {
    if (s == null) return ''
    return s.length > n ? s.slice(0, n) + '…' : s
  }

  function buildBlock(el) {
    const { source, component } = extractSource(el)
    const luSource = el.getAttribute && el.getAttribute('data-lingua-source')
    const selector = buildSelector(el)
    const text = truncate((el.textContent || '').trim().replace(/\s+/g, ' '), 500)
    const html = truncate(el.outerHTML || '', 4000)

    const lines = ['[Selected element from preview — edit this in code]']
    if (source) lines.push(`source: ${source}`)
    if (component) lines.push(`component: ${component}`)
    if (luSource) lines.push(`data-lingua-source: ${luSource}`)
    if (selector) lines.push(`selector: ${selector}`)
    if (text) lines.push(`text: "${text}"`)
    if (html) lines.push(`html: ${html}`)
    return { block: lines.join('\n'), summary: component || el.tagName.toLowerCase() }
  }

  async function writeClipboard(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return
    }
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    try { document.execCommand('copy') } finally { document.body.removeChild(ta) }
  }

  async function capture(el) {
    const { block, summary } = buildBlock(el)
    let copied = false
    try {
      await writeClipboard(block)
      copied = true
    } catch (err) {
      console.warn('lingua-picker: clipboard write failed', err)
    }
    window.parent.postMessage(
      { type: 'lingua:selection', summary: `Copied: ${summary}`, block, copied },
      '*',
    )
    disable()
  }

  function onMouseOver(e) {
    if (!active) return
    const t = e.target
    if (!t || t === overlay) return
    lastHovered = t
    positionOverlay(t)
  }

  function onClick(e) {
    if (!active) return
    e.preventDefault()
    e.stopPropagation()
    const t = e.target
    if (t) capture(t)
  }

  function onKeyDown(e) {
    if (!active) return
    if (e.key === 'Escape') {
      window.parent.postMessage({ type: 'lingua:cancel' }, '*')
      disable()
    }
  }

  function enable() {
    if (active) return
    active = true
    document.body.style.cursor = 'crosshair'
    document.addEventListener('mouseover', onMouseOver, true)
    document.addEventListener('click', onClick, true)
    document.addEventListener('keydown', onKeyDown, true)
  }

  function disable() {
    if (!active) return
    active = false
    document.body.style.cursor = ''
    document.removeEventListener('mouseover', onMouseOver, true)
    document.removeEventListener('click', onClick, true)
    document.removeEventListener('keydown', onKeyDown, true)
    hideOverlay()
    lastHovered = null
  }

  window.addEventListener('message', (e) => {
    if (!e.data || typeof e.data !== 'object') return
    if (e.data.type === 'lingua:enable_pick') enable()
    else if (e.data.type === 'lingua:disable') disable()
  })
})()
