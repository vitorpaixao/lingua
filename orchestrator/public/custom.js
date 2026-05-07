(function () {
  const PREVIEW_URL = "http://localhost:3000";
  const STORAGE_KEY_VISIBLE = "lingua-preview-visible";
  const STORAGE_KEY_WIDTH = "lingua-sidebar-width";

  let panel = null;
  let iframe = null;
  let dragHandle = null;
  let toggleBtn = null;
  let isVisible = true;
  let isDragging = false;
  let panelWidth = 50;

  function createPanel() {
    if (document.getElementById("lingua-panel")) return;

    const savedWidth = localStorage.getItem(STORAGE_KEY_WIDTH);
    if (savedWidth) panelWidth = parseFloat(savedWidth);
    const savedVisible = localStorage.getItem(STORAGE_KEY_VISIBLE);
    if (savedVisible === "false") isVisible = false;

    panel = document.createElement("div");
    panel.id = "lingua-panel";
    panel.style.cssText = `
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: ${isVisible ? panelWidth + "vw" : "0"};
      background: hsl(240 10% 3.9%);
      border-left: 1px solid hsl(240 3.7% 15.9%);
      z-index: 9998;
      display: flex;
      flex-direction: column;
      transition: width 0.25s ease;
      overflow: hidden;
    `;

    const toolbar = document.createElement("div");
    toolbar.style.cssText = `
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 6px 10px;
      border-bottom: 1px solid hsl(240 3.7% 15.9%);
      background: hsl(240 6% 6%);
      min-height: 36px;
      flex-shrink: 0;
    `;

    const label = document.createElement("span");
    label.textContent = "Live Preview";
    label.style.cssText = "font-size: 12px; color: hsl(240 5% 64.9%); font-family: inherit;";

    const btnGroup = document.createElement("div");
    btnGroup.style.cssText = "display: flex; gap: 4px;";

    function makeBtn(title, svg, onClick) {
      const btn = document.createElement("button");
      btn.title = title;
      btn.innerHTML = svg;
      btn.style.cssText = `
        width: 28px; height: 28px; border-radius: 4px; border: none;
        background: transparent; color: hsl(240 5% 64.9%); cursor: pointer;
        display: flex; align-items: center; justify-content: center;
      `;
      btn.onmouseenter = () => { btn.style.background = "hsl(240 3.7% 15.9%)"; };
      btn.onmouseleave = () => { btn.style.background = "transparent"; };
      btn.onclick = onClick;
      return btn;
    }

    const svgRefresh = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>';
    const svgExternal = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>';

    btnGroup.appendChild(makeBtn("Refresh", svgRefresh, () => {
      if (iframe) iframe.src = iframe.src;
    }));
    btnGroup.appendChild(makeBtn("Open in new tab", svgExternal, () => {
      window.open(PREVIEW_URL, "_blank");
    }));

    toolbar.appendChild(label);
    toolbar.appendChild(btnGroup);

    iframe = document.createElement("iframe");
    iframe.src = PREVIEW_URL;
    iframe.style.cssText = "flex: 1; width: 100%; border: none; display: block;";
    iframe.title = "Live preview";

    panel.appendChild(toolbar);
    panel.appendChild(iframe);
    document.body.appendChild(panel);

    if (!isVisible) {
      panel.style.width = "0";
      panel.style.borderLeft = "none";
    }
  }

  function createDragHandle() {
    if (document.getElementById("lingua-drag-handle")) return;

    dragHandle = document.createElement("div");
    dragHandle.id = "lingua-drag-handle";
    dragHandle.style.cssText = `
      position: fixed;
      top: 0;
      bottom: 0;
      width: 6px;
      cursor: col-resize;
      z-index: 9999;
      background: transparent;
      transition: background 0.15s;
    `;
    if (!isVisible) dragHandle.style.display = "none";

    dragHandle.addEventListener("mouseenter", () => {
      if (!isDragging) dragHandle.style.background = "hsl(240 3.7% 15.9%)";
    });
    dragHandle.addEventListener("mouseleave", () => {
      if (!isDragging) dragHandle.style.background = "transparent";
    });

    document.body.appendChild(dragHandle);
    positionDragHandle();

    dragHandle.addEventListener("mousedown", (e) => {
      isDragging = true;
      dragHandle.style.background = "hsl(142 71% 45% / 0.5)";
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      panel.style.transition = "none";
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const vw = (window.innerWidth - e.clientX) / window.innerWidth * 100;
      panelWidth = Math.max(20, Math.min(vw, 80));
      panel.style.width = panelWidth + "vw";
      applyLayout();
      positionDragHandle();
    });

    document.addEventListener("mouseup", () => {
      if (!isDragging) return;
      isDragging = false;
      dragHandle.style.background = "transparent";
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      panel.style.transition = "width 0.25s ease";
      applyLayout();
      localStorage.setItem(STORAGE_KEY_WIDTH, panelWidth);
    });
  }

  function positionDragHandle() {
    if (!dragHandle || !panel) return;
    const rect = panel.getBoundingClientRect();
    dragHandle.style.left = (rect.left - 3) + "px";
  }

  function createToggleBtn() {
    if (document.getElementById("lingua-toggle-btn")) return;

    toggleBtn = document.createElement("button");
    toggleBtn.id = "lingua-toggle-btn";
    updateToggleAppearance();
    toggleBtn.style.cssText = `
      position: fixed;
      top: 12px;
      z-index: 10000;
      width: 32px;
      height: 32px;
      border-radius: 6px;
      border: 1px solid hsl(240 3.7% 15.9%);
      background: hsl(240 10% 3.9%);
      color: hsl(240 5% 64.9%);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      transition: right 0.25s ease, background 0.15s;
    `;
    toggleBtn.onmouseenter = () => { toggleBtn.style.background = "hsl(240 3.7% 15.9%)"; };
    toggleBtn.onmouseleave = () => { toggleBtn.style.background = "hsl(240 10% 3.9%)"; };

    toggleBtn.addEventListener("click", () => {
      isVisible = !isVisible;
      if (isVisible) {
        panel.style.width = panelWidth + "vw";
        panel.style.borderLeft = "1px solid hsl(240 3.7% 15.9%)";
        dragHandle.style.display = "block";
        positionDragHandle();
      } else {
        panel.style.width = "0";
        panel.style.borderLeft = "none";
        dragHandle.style.display = "none";
      }
      applyLayout();
      updateToggleAppearance();
      positionToggle();
      localStorage.setItem(STORAGE_KEY_VISIBLE, isVisible);
    });

    document.body.appendChild(toggleBtn);
    positionToggle();
  }

  function updateToggleAppearance() {
    if (!toggleBtn) return;
    if (isVisible) {
      toggleBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18" stroke-dasharray="2 2"/></svg>';
      toggleBtn.title = "Hide preview";
    } else {
      toggleBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M15 3v18"/></svg>';
      toggleBtn.title = "Show preview";
    }
  }

  function positionToggle() {
    if (!toggleBtn || !panel) return;
    const rect = panel.getBoundingClientRect();
    toggleBtn.style.right = (isVisible ? rect.width + 8 : 8) + "px";
  }

  function applyLayout() {
    if (!panel) return;
    const w = isVisible ? panelWidth : 0;
    document.body.style.paddingRight = w + "vw";
    document.documentElement.style.setProperty("--lingua-chat-width", (100 - w) + "vw");
  }

  function init() {
    createPanel();
    createDragHandle();
    createToggleBtn();
    applyLayout();
    positionDragHandle();
    positionToggle();

    window.addEventListener("resize", () => {
      applyLayout();
      positionDragHandle();
      positionToggle();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
