'use strict';

// Network + config layer for the FireDragon/Firefox extension. UI (the
// result panel, the Alt+B key handling) lives in shared/bil-panel.js,
// loaded first by manifest.json's content_scripts entry.

const DEFAULT_ENDPOINT = 'http://127.0.0.1:8787/bil';

async function getConfig() {
  const { bilEndpoint, bilToken } = await browser.storage.local.get([
    'bilEndpoint',
    'bilToken',
  ]);
  return { endpoint: bilEndpoint || DEFAULT_ENDPOINT, token: bilToken || '' };
}

async function runBIL(text, anchorRect) {
  const { endpoint, token } = await getConfig();

  let res;
  try {
    res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-BIL-Token': token },
      body: JSON.stringify({
        thread_id: 'firedragon-extension',
        input_type: 'english',
        input_text: text,
      }),
    });
  } catch (e) {
    BILPanel.showPanel(anchorRect, {
      ok: false,
      error: `Could not reach ${endpoint} — is server.py running?`,
    });
    return;
  }

  if (res.status === 401) {
    BILPanel.showPanel(anchorRect, {
      ok: false,
      error: "Missing or invalid token — set it via the extension's toolbar popup.",
    });
    return;
  }

  const parsed = await res
    .json()
    .catch(() => ({ ok: false, error: 'Bad response from BIL server' }));
  BILPanel.showPanel(anchorRect, parsed);
}

BILPanel.wireAltBShortcut(runBIL);
