// ==UserScript==
// @name         BIL Helper
// @namespace    https://github.com/cosmicindustries/bil
// @version      0.2.0
// @description  Select text on any page, hit Alt+B, and see it run through the BIL interpreter (output text + BIL tokens).
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// @connect      127.0.0.1
// @require      https://raw.githubusercontent.com/CosmicIndustries/BIL/main/extension/shared/bil-panel.js
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
          BILPanel.showPanel(anchorRect, {
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
        BILPanel.showPanel(anchorRect, parsed);
      },
      onerror: () => {
        BILPanel.showPanel(anchorRect, {
          ok: false,
          error: `Could not reach ${endpoint()} — is server.py running?`,
        });
      },
    });
  }

  BILPanel.wireAltBShortcut(runBIL);
})();
