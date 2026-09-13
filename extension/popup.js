'use strict';

const DEFAULT_ENDPOINT = 'http://127.0.0.1:8787/bil';

async function load() {
  const { bilEndpoint, bilToken } = await browser.storage.local.get([
    'bilEndpoint',
    'bilToken',
  ]);
  document.getElementById('endpoint').value = bilEndpoint || DEFAULT_ENDPOINT;
  document.getElementById('token').value = bilToken || '';
}

document.getElementById('save').addEventListener('click', async () => {
  const endpoint = document.getElementById('endpoint').value.trim() || DEFAULT_ENDPOINT;
  const token = document.getElementById('token').value.trim();
  await browser.storage.local.set({ bilEndpoint: endpoint, bilToken: token });

  const status = document.getElementById('status');
  status.textContent = 'Saved.';
  setTimeout(() => {
    status.textContent = '';
  }, 1500);
});

load();
