'use strict';

// WebExtension port of userscript/bil-helper.user.js for FireDragon/Firefox —
// uses fetch() + browser.storage instead of GM_xmlhttpRequest/GM_*, since
// content scripts don't have userscript-manager APIs.

const DEFAULT_ENDPOINT = 'http://127.0.0.1:8787/bil';

async function getConfig() {
  const { bilEndpoint, bilToken } = await browser.storage.local.get([
    'bilEndpoint',
    'bilToken',
  ]);
  return { endpoint: bilEndpoint || DEFAULT_ENDPOINT, token: bilToken || '' };
}

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
    showPanel(anchorRect, {
      ok: false,
      error: `Could not reach ${endpoint} — is server.py running?`,
    });
    return;
  }

  if (res.status === 401) {
    showPanel(anchorRect, {
      ok: false,
      error: "Missing or invalid token — set it via the extension's toolbar popup.",
    });
    return;
  }

  const parsed = await res
    .json()
    .catch(() => ({ ok: false, error: 'Bad response from BIL server' }));
  showPanel(anchorRect, parsed);
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
