/* Refresh only missing visible thumbnails; preserve filters, focus and forms. */
(() => {
  'use strict';
  const rows = [...document.querySelectorAll('[data-preview-key]')];
  if (!rows.length) return;
  let attempts = 0, timer;
  async function refresh() {
    if (document.hidden) { timer = setTimeout(refresh, 5000); return; }
    const missing = rows.filter(row => !row.querySelector('.product-thumbnail img'));
    if (!missing.length || attempts >= 18) return;
    attempts++;
    try {
      const query = missing.map(row => row.dataset.previewKey).join(',');
      const response = await fetch('/api/inventory/photos?objects=' + encodeURIComponent(query));
      if (!response.ok || response.redirected) return;
      const result = await response.json();
      for (const row of missing) {
        const url = result.items[row.dataset.previewKey];
        if (typeof url !== 'string' || !url.startsWith('/media/inventory/')) continue;
        const target = row.querySelector('.product-thumbnail');
        if (!target || target.querySelector('img')) continue;
        const img = document.createElement('img'); img.alt = ''; img.width = 40; img.height = 40;
        img.decoding = 'async'; img.loading = 'lazy'; img.src = url; target.prepend(img);
      }
      if (!result.enabled) return;
    } catch (_) { /* Keep the existing fallback; retry without replacing the page. */ }
    timer = setTimeout(refresh, attempts < 4 ? 2000 : 10000);
  }
  timer = setTimeout(refresh, 2000);
  window.addEventListener('pagehide', () => clearTimeout(timer));
})();
