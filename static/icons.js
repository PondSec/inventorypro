(function () {
  const createIcon = (paths, className) => {
    const safeClass = className ? ` class="${className}"` : '';
    return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"${safeClass}>${paths}</svg>`;
  };

  const icons = {
    gpu: (className) =>
      createIcon(
        '<rect x="3" y="7" width="14" height="10" rx="2"></rect>' +
          '<circle cx="8" cy="12" r="2"></circle>' +
          '<circle cx="13" cy="12" r="2"></circle>' +
          '<path d="M17 9h4v6h-4"></path>' +
          '<path d="M5 17v2M9 17v2M13 17v2"></path>',
        className
      ),
    ram: (className) =>
      createIcon(
        '<rect x="3" y="9" width="18" height="6" rx="1"></rect>' +
          '<path d="M6 9V7M10 9V7M14 9V7M18 9V7"></path>' +
          '<path d="M6 15v2M10 15v2M14 15v2M18 15v2"></path>',
        className
      ),
    laptop: (className) =>
      createIcon(
        '<rect x="4" y="5" width="16" height="10" rx="1"></rect>' +
          '<path d="M2 19h20"></path>' +
          '<path d="M4 15h16"></path>',
        className
      ),
    'server-rack': (className) =>
      createIcon(
        '<rect x="4" y="3" width="16" height="6" rx="1"></rect>' +
          '<rect x="4" y="10" width="16" height="6" rx="1"></rect>' +
          '<rect x="4" y="17" width="16" height="4" rx="1"></rect>',
        className
      ),
    ssd: (className) =>
      createIcon(
        '<rect x="4" y="6" width="16" height="12" rx="2"></rect>' +
          '<path d="M8 10h8"></path>' +
          '<path d="M8 14h4"></path>',
        className
      ),
    hdd: (className) =>
      createIcon(
        '<rect x="3" y="5" width="18" height="14" rx="2"></rect>' +
          '<circle cx="12" cy="12" r="3"></circle>' +
          '<path d="M12 12h4"></path>',
        className
      ),
    keyboard: (className) =>
      createIcon(
        '<rect x="3" y="7" width="18" height="10" rx="2"></rect>' +
          '<path d="M6 10h2M10 10h2M14 10h2"></path>' +
          '<path d="M6 13h10"></path>',
        className
      )
  };

  window.InventoryCustomIcons = icons;
})();
