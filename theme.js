/* Theme toggle + collapsible sidebar (both persistent) + auto-size seamless iframes. */
(function () {
  var KEY = 'kh-theme';
  var SB_KEY = 'kh-sidebar';
  // apply saved theme + sidebar state ASAP to avoid flash
  try {
    var saved = localStorage.getItem(KEY);
    if (saved) document.documentElement.setAttribute('data-theme', saved);
    if (localStorage.getItem(SB_KEY) === 'collapsed')
      document.documentElement.classList.add('sidebar-collapsed');
  } catch (e) {}

  var ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>';

  function collapsed() { return document.documentElement.classList.contains('sidebar-collapsed'); }

  function labelToggle(btn) {
    btn.title = collapsed() ? 'Open sidebar' : 'Collapse sidebar';
    btn.setAttribute('aria-label', btn.title);
  }

  window.toggleSidebar = function () {
    var isCollapsed = document.documentElement.classList.toggle('sidebar-collapsed');
    try { localStorage.setItem(SB_KEY, isCollapsed ? 'collapsed' : 'open'); } catch (e) {}
    var btn = document.querySelector('.sidebar-toggle');
    if (btn) labelToggle(btn);
  };

  function glyph() {
    var mode = document.documentElement.getAttribute('data-theme') || 'light';
    var g = mode === 'dark' ? '\u2600' : '\u263E'; // sun / moon
    document.querySelectorAll('.theme-toggle .glyph').forEach(function (s) { s.textContent = g; });
  }

  window.toggleTheme = function () {
    var cur = document.documentElement.getAttribute('data-theme') || 'light';
    var next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
    glyph();
  };

  function sizeFrames() {
    document.querySelectorAll('iframe.embed-frame').forEach(function (f) {
      try {
        var d = f.contentDocument || (f.contentWindow && f.contentWindow.document);
        if (d && d.body) {
          var h = Math.max(d.body.scrollHeight, d.documentElement.scrollHeight);
          if (h > 0) f.style.height = h + 'px';
        }
      } catch (e) {}
    });
  }

  // seamless iframes can report their own height (works even cross-origin / file://)
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (!d || d.type !== 'kh-embed-height' || typeof d.height !== 'number' || d.height <= 0) return;
    document.querySelectorAll('iframe.embed-frame').forEach(function (f) {
      if (f.contentWindow === e.source) f.style.height = d.height + 'px';
    });
  });

  document.addEventListener('DOMContentLoaded', function () {
    glyph();
    // inject the sidebar collapse toggle (lives outside the sidebar so it stays visible)
    if (!document.querySelector('.sidebar-toggle')) {
      var btn = document.createElement('button');
      btn.className = 'sidebar-toggle';
      btn.type = 'button';
      btn.innerHTML = ICON;
      btn.addEventListener('click', window.toggleSidebar);
      labelToggle(btn);
      document.body.appendChild(btn);
    }
    document.querySelectorAll('iframe.embed-frame').forEach(function (f) {
      f.setAttribute('scrolling', 'no');
      f.addEventListener('load', sizeFrames);
    });
    sizeFrames();
    [200, 600, 1200].forEach(function (t) { setTimeout(sizeFrames, t); });
  });
  window.addEventListener('resize', sizeFrames);
})();
