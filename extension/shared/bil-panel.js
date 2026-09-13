'use strict';

// Shared by extension/content.js (bundled as a content_scripts entry) and
// userscript/bil-helper.user.js (pulled in via @require from this file's
// raw GitHub URL) so the result-panel UI and Alt+B wiring live in exactly
// one place instead of being duplicated across the two integrations.

(function (global) {
  let panel = null;

  function closePanel() {
    if (panel) {
      panel.remove();
      panel = null;
    }
  }

  function showPanel(anchorRect, result) {
    closePanel();
    panel = document.createElement('div');
    panel.style.cssText = [
      'position:fixed',
      `top:${Math.min(anchorRect.bottom + 8, window.innerHeight - 220)}px`,
      `left:${Math.min(anchorRect.left, window.innerWidth - 380)}px`,
      'width:360px',
      'max-height:300px',
      'overflow:auto',
      'background:#1e1e1e',
      'color:#eee',
      'border:1px solid #444',
      'border-radius:8px',
      'padding:12px',
      'font:12px/1.4 monospace',
      'z-index:2147483647',
      'box-shadow:0 4px 16px rgba(0,0,0,0.4)',
    ].join(';');

    const close = document.createElement('button');
    close.textContent = '×';
    close.style.cssText =
      'float:right;background:none;border:none;color:#aaa;cursor:pointer;font-size:14px;line-height:1;';
    close.addEventListener('click', closePanel);
    panel.appendChild(close);

    const title = document.createElement('div');
    title.textContent = result.ok ? 'BIL round-trip' : 'BIL error';
    title.style.cssText = 'font-weight:bold;margin-bottom:6px;';
    panel.appendChild(title);

    const body = document.createElement('pre');
    body.style.cssText = 'white-space:pre-wrap;word-break:break-word;margin:0;';
    body.textContent = result.ok
      ? `OUTPUT:  ${result.output_text}\nTOKENS:  ${result.bil_tokens}`
      : `ERROR: ${result.error || JSON.stringify(result.validation || {})}`;
    panel.appendChild(body);

    document.body.appendChild(panel);
  }

  function wireAltBShortcut(runBIL) {
    document.addEventListener('keydown', (e) => {
      if (!(e.altKey && e.key.toLowerCase() === 'b')) return;
      const selection = window.getSelection();
      const text = selection ? selection.toString().trim() : '';
      if (!text || !selection.rangeCount) return;
      const range = selection.getRangeAt(0);
      // runBIL may be sync (userscript, GM_xmlhttpRequest-based) or async
      // (extension, fetch-based); Promise.resolve(...).catch(...) handles
      // both without leaving a floating/unhandled rejection either way.
      Promise.resolve(runBIL(text, range.getBoundingClientRect())).catch((err) => {
        console.error('BIL Helper: runBIL failed', err);
      });
    });

    document.addEventListener('mousedown', (e) => {
      if (panel && !panel.contains(e.target)) closePanel();
    });
  }

  global.BILPanel = { showPanel, closePanel, wireAltBShortcut };
})(typeof window !== 'undefined' ? window : globalThis);
