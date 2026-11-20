(() => {
  if (new URLSearchParams(window.location.search).get('diagnostics') !== '1') return;

  const script = document.createElement('script');
  script.src = 'admin-diagnostics.js';
  document.head.append(script);
})();
