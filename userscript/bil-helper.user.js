// ==UserScript==
// @name         BIL Helper
// @namespace    https://github.com/cosmicindustries/bil
// @version      0.1.0
// @description  Select text on any page, hit Alt+B, and see it run through the BIL interpreter (output text + BIL tokens).
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @connect      127.0.0.1
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  const DEFAULT_ENDPOINT = 'http://127.0.0.1:8787/bil';

  function endpoint() {
    return GM_getValue('bilEndpoint', DEFAULT_ENDPOINT);
  }

  function token() {
    return GM_getValue('bilToken', '');
  }

  GM_registerMenuCommand('Set BIL endpoint', () => {
    const next = window.prompt('BIL webhook endpoint:', endpoint());
    if (next) GM_setValue('bilEndpoint', next);
  });

  GM_registerMenuCommand('Set BIL token', () => {
    const next = window.prompt(
      'BIL auth token (printed by server.py on startup):',
      token()
    );
    if (next !== null) GM_setValue('bilToken', next);
  });

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

  function runBIL(text, anchorRect) {
    GM_xmlhttpRequest({
      method: 'POST',
      url: endpoint(),
      headers: { 'Content-Type': 'application/json', 'X-BIL-Token': token() },
      data: JSON.stringify({
        thread_id: 'userscript',
        input_type: 'english',
        input_text: text,
      }),
      onload: (res) => {
        if (res.status === 401) {
          showPanel(anchorRect, {
            ok: false,
            error: "Missing or invalid token — set it via the Tampermonkey menu ('Set BIL token').",
          });
          return;
        }
        let parsed;
        try {
          parsed = JSON.parse(res.responseText);
        } catch (e) {
          parsed = { ok: false, error: 'Bad response from BIL server' };
        }
        showPanel(anchorRect, parsed);
      },
      onerror: () => {
        showPanel(anchorRect, {
          ok: false,
          error: `Could not reach ${endpoint()} — is server.py running?`,
        });
      },
    });
  }

  document.addEventListener('keydown', (e) => {
    if (!(e.altKey && e.key.toLowerCase() === 'b')) return;
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : '';
    if (!text || !selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    runBIL(text, range.getBoundingClientRect());
  });

  document.addEventListener('mousedown', (e) => {
    if (panel && !panel.contains(e.target)) closePanel();
  });
})();
