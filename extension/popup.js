'use strict';

const DEFAULT_ENDPOINT = 'http://127.0.0.1:8787/bil';

async function load() {
  const { bilEndpoint, bilToken } = await browser.storage.local.get([
    'bilEndpoint',
    'bilToken',
  ]);
  const endpointInput = document.getElementById('endpoint');
  const tokenInput = document.getElementById('token');
  if (endpointInput) endpointInput.value = bilEndpoint || DEFAULT_ENDPOINT;
  if (tokenInput) tokenInput.value = bilToken || '';
}

async function save() {
  const endpointInput = document.getElementById('endpoint');
  const tokenInput = document.getElementById('token');
  const statusEl = document.getElementById('status');

  const endpoint = (endpointInput ? endpointInput.value.trim() : '') || DEFAULT_ENDPOINT;
  const token = tokenInput ? tokenInput.value.trim() : '';
  await browser.storage.local.set({ bilEndpoint: endpoint, bilToken: token });

  if (statusEl) {
    statusEl.textContent = 'Saved.';
    setTimeout(() => {
      statusEl.textContent = '';
    }, 1500);
  }
}

const saveButton = document.getElementById('save');
if (saveButton) {
  saveButton.addEventListener('click', () => {
    save().catch((err) => console.error('BIL Helper: save failed', err));
  });
}

load().catch((err) => console.error('BIL Helper: load failed', err));
