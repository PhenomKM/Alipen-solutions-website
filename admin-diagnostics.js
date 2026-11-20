(() => {
  'use strict';

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
    return;
  }

  initialize();

  function initialize() {

  const excludedSelector = '[data-admin-diagnostic-ui]';
  const report = {
    page: window.location.href,
    userAgent: navigator.userAgent,
    viewportMeta: document.querySelector('meta[name="viewport"]')?.content || null,
    stages: []
  };
  const dialog = document.getElementById('quoteDetailDialog');
  let cycle = 0;

  if (!dialog || document.body.dataset.adminPage !== 'dashboard') return;

  const round = (value) => Math.round(value * 100) / 100;

  function elementInfo(element) {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      tag: element.tagName.toLowerCase(),
      id: element.id || '',
      classNames: typeof element.className === 'string' ? element.className : (element.getAttribute('class') || ''),
      computedWidth: style.width,
      computedHeight: style.height,
      position: style.position,
      rect: {
        left: round(rect.left),
        top: round(rect.top),
        right: round(rect.right),
        bottom: round(rect.bottom),
        width: round(rect.width),
        height: round(rect.height)
      },
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight
    };
  }

  function isVisible(element) {
    if (element.closest(excludedSelector)) return false;
    if (!element.getClientRects().length) return false;

    for (let current = element; current && current.nodeType === Node.ELEMENT_NODE; current = current.parentElement) {
      const style = window.getComputedStyle(current);
      if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || Number(style.opacity) === 0) {
        return false;
      }
    }
    return true;
  }

  function measure(stage, currentCycle) {
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const elements = [document.documentElement, document.body, ...document.body.querySelectorAll('*')]
      .filter(isVisible)
      .map(elementInfo);

    const rightOverflow = elements.filter((item) => item.rect.right > viewportWidth + 1);
    const widthOverflow = elements.filter((item) => item.rect.width > viewportWidth + 1);
    const horizontalScrollers = elements
      .map((item) => ({ ...item, overflow: item.scrollWidth - item.clientWidth }))
      .filter((item) => item.overflow > 1)
      .sort((a, b) => b.overflow - a.overflow);
    const verticalScrollers = elements
      .map((item) => ({ ...item, overflow: item.scrollHeight - item.clientHeight }))
      .filter((item) => item.overflow > 1)
      .sort((a, b) => b.overflow - a.overflow);
    const largestRightOverflow = [...elements].sort((a, b) =>
      Math.max(b.rect.right - viewportWidth, b.rect.width - viewportWidth) -
      Math.max(a.rect.right - viewportWidth, a.rect.width - viewportWidth))[0] || null;
    const largestBottomOverflow = [...elements].sort((a, b) =>
      Math.max(b.rect.bottom - viewportHeight, b.rect.height - viewportHeight) -
      Math.max(a.rect.bottom - viewportHeight, a.rect.height - viewportHeight))[0] || null;

    const visualViewport = window.visualViewport;
    const entry = {
      stage,
      cycle: currentCycle,
      timestamp: new Date().toISOString(),
      viewport: {
        innerWidth: viewportWidth,
        innerHeight: viewportHeight,
        devicePixelRatio: window.devicePixelRatio,
        pageScrollX: window.scrollX,
        pageScrollY: window.scrollY,
        openDialogCount: document.querySelectorAll('dialog[open]').length,
        visualViewport: visualViewport ? {
          width: round(visualViewport.width),
          height: round(visualViewport.height),
          scale: round(visualViewport.scale),
          offsetLeft: round(visualViewport.offsetLeft),
          offsetTop: round(visualViewport.offsetTop)
        } : null
      },
      documentElement: elementInfo(document.documentElement),
      body: elementInfo(document.body),
      dashboardMain: document.querySelector('.admin-main-column') ? elementInfo(document.querySelector('.admin-main-column')) : null,
      dashboardContent: document.querySelector('.admin-content') ? elementInfo(document.querySelector('.admin-content')) : null,
      quoteDialog: elementInfo(dialog),
      visibleElementsPastViewportRight: rightOverflow,
      visibleElementsWiderThanViewport: widthOverflow,
      largestHorizontalOverflow: largestRightOverflow,
      largestVerticalOverflow: largestBottomOverflow,
      largestHorizontalScrollOverflow: horizontalScrollers[0] || null,
      largestVerticalScrollOverflow: verticalScrollers[0] || null,
      elementsWithHorizontalScrollOverflow: horizontalScrollers,
      elementsWithVerticalScrollOverflow: verticalScrollers
    };

    report.stages.push(entry);
    renderReport();
    console.groupCollapsed(`[Admin layout diagnostics] ${stage} (cycle ${currentCycle})`);
    console.log(entry);
    console.groupEnd();
    return entry;
  }

  function renderReport() {
    const output = document.getElementById('adminDiagnosticReport');
    if (output) output.value = JSON.stringify(report, null, 2);
  }

  function waitForRenderedDialog(currentCycle) {
    const deadline = performance.now() + 2500;
    const check = () => {
      if (currentCycle !== cycle || !dialog.open) return;
      const content = document.getElementById('detailContent');
      if (!content.hidden || performance.now() >= deadline) {
        requestAnimationFrame(() => {
          if (currentCycle === cycle && dialog.open) measure('while-open', currentCycle);
        });
        return;
      }
      requestAnimationFrame(check);
    };
    requestAnimationFrame(check);
  }

  function addDiagnosticPanel() {
    const panel = document.createElement('details');
    panel.dataset.adminDiagnosticUi = 'true';
    panel.open = false;
    panel.style.cssText = 'position:fixed;right:8px;bottom:8px;z-index:2147483647;width:min(360px,calc(100vw - 16px));max-height:55vh;overflow:auto;padding:10px;border:1px solid #94a3b8;border-radius:10px;background:#fff;color:#1e293b;box-shadow:0 8px 30px rgba(15,23,42,.25);font:12px/1.4 system-ui,sans-serif;';

    const summary = document.createElement('summary');
    summary.textContent = 'Temporary admin layout diagnostics';
    summary.style.cssText = 'cursor:pointer;font-weight:700;margin-bottom:8px;';

    const actions = document.createElement('div');
    actions.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;';
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.textContent = 'Copy report';
    const download = document.createElement('button');
    download.type = 'button';
    download.textContent = 'Download JSON';
    const status = document.createElement('span');
    status.setAttribute('role', 'status');
    status.style.cssText = 'align-self:center;color:#475569;';

    const output = document.createElement('textarea');
    output.id = 'adminDiagnosticReport';
    output.readOnly = true;
    output.setAttribute('aria-label', 'Admin layout diagnostic report');
    output.style.cssText = 'display:block;width:100%;height:180px;resize:vertical;box-sizing:border-box;font:10px/1.35 ui-monospace,monospace;';

    copy.addEventListener('click', async () => {
      output.value = JSON.stringify(report, null, 2);
      try {
        await navigator.clipboard.writeText(output.value);
        status.textContent = 'Report copied.';
      } catch (_) {
        output.focus();
        output.select();
        status.textContent = document.execCommand('copy') ? 'Report copied.' : 'Select the report text to copy.';
      }
    });

    download.addEventListener('click', () => {
      const blobUrl = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = 'admin-layout-diagnostic.json';
      link.click();
      URL.revokeObjectURL(blobUrl);
      status.textContent = 'JSON report downloaded.';
    });

    actions.append(copy, download, status);
    panel.append(summary, actions, output);
    document.body.append(panel);
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || button.closest(excludedSelector)) return;
    const label = button.textContent.trim().toLowerCase();
    if (button.matches('.reference-link') || label === 'details') {
      cycle += 1;
      measure('before-open', cycle);
      waitForRenderedDialog(cycle);
    }
  }, true);

  dialog.addEventListener('close', () => {
    const closedCycle = cycle;
    measure('after-close-immediate', closedCycle);
    requestAnimationFrame(() => measure('after-close-frame', closedCycle));
  });

  addDiagnosticPanel();
  measure('baseline', 0);
  }
})();
