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
      ),
    desktop: (className) =>
      createIcon(
        '<rect x="3" y="4" width="18" height="12" rx="1"></rect>' +
          '<path d="M8 20h8"></path>' +
          '<path d="M12 16v4"></path>',
        className
      ),
    tower: (className) =>
      createIcon(
        '<rect x="7" y="3" width="10" height="18" rx="1"></rect>' +
          '<circle cx="12" cy="7" r="1"></circle>' +
          '<circle cx="12" cy="11" r="1"></circle>' +
          '<rect x="9" y="15" width="6" height="3" rx="1"></rect>',
        className
      ),
    router: (className) =>
      createIcon(
        '<rect x="3" y="11" width="18" height="6" rx="2"></rect>' +
          '<path d="M7 11V7"></path>' +
          '<path d="M17 11V7"></path>' +
          '<circle cx="9" cy="14" r="1"></circle>' +
          '<circle cx="12" cy="14" r="1"></circle>' +
          '<circle cx="15" cy="14" r="1"></circle>',
        className
      ),
    switch: (className) =>
      createIcon(
        '<rect x="3" y="9" width="18" height="6" rx="1"></rect>' +
          '<path d="M7 12h2M11 12h2M15 12h2"></path>',
        className
      ),
    'access-point': (className) =>
      createIcon(
        '<circle cx="12" cy="12" r="1.5"></circle>' +
          '<path d="M4 12a8 8 0 0 1 16 0"></path>' +
          '<path d="M6.5 12a5.5 5.5 0 0 1 11 0"></path>',
        className
      ),
    motherboard: (className) =>
      createIcon(
        '<rect x="4" y="4" width="16" height="16" rx="2"></rect>' +
          '<rect x="7" y="7" width="6" height="6" rx="1"></rect>' +
          '<path d="M14 7h3M14 10h3M14 13h3"></path>' +
          '<path d="M7 14v3M10 14v3"></path>',
        className
      ),
    'power-supply': (className) =>
      createIcon(
        '<rect x="4" y="6" width="16" height="12" rx="2"></rect>' +
          '<circle cx="9" cy="12" r="2"></circle>' +
          '<path d="M13 9h4M13 12h4M13 15h4"></path>',
        className
      ),
    dock: (className) =>
      createIcon(
        '<rect x="5" y="14" width="14" height="5" rx="1"></rect>' +
          '<path d="M8 14V6h8v8"></path>',
        className
      ),
    headset: (className) =>
      createIcon(
        '<path d="M4 12a8 8 0 0 1 16 0"></path>' +
          '<rect x="3" y="12" width="3" height="5" rx="1"></rect>' +
          '<rect x="18" y="12" width="3" height="5" rx="1"></rect>',
        className
      ),
    scanner: (className) =>
      createIcon(
        '<rect x="4" y="4" width="16" height="5" rx="1"></rect>' +
          '<rect x="3" y="9" width="18" height="8" rx="2"></rect>' +
          '<path d="M7 13h10"></path>',
        className
      ),
    'battery-pack': (className) =>
      createIcon(
        '<rect x="3" y="7" width="18" height="10" rx="2"></rect>' +
          '<path d="M21 10h1v4h-1"></path>' +
          '<path d="M7 12h2M11 12h2M15 12h2"></path>',
        className
      )
  };

  window.InventoryCustomIcons = icons;
})();
