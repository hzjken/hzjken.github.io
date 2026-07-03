/* Projects page — render GitHub-style scorecards live from the GitHub API.
   Same markup/classes as the original static cards; just fed from real repos. */
(function () {
  var GH_USER = 'hzjken';
  // Repos to hide from the projects list (this blog site, etc.). Forks are also hidden.
  var EXCLUDE = ['hzjken.github.io'];
  var API = 'https://api.github.com/users/' + GH_USER +
            '/repos?per_page=100&sort=created&direction=desc';
  var CACHE_KEY = 'gh-repos-' + GH_USER;
  var CACHE_TTL = 30 * 60 * 1000; // 30 min

  // GitHub linguist colors for the language dot (fallback = neutral grey).
  var LANG_COLORS = {
    Python: '#3572A5', JavaScript: '#f1e05a', TypeScript: '#3178c6', HTML: '#e34c26',
    CSS: '#563d7c', 'Jupyter Notebook': '#DA5B0B', Java: '#b07219', 'C++': '#f34b7d',
    C: '#555555', 'C#': '#178600', Go: '#00ADD8', Rust: '#dea584', Ruby: '#701516',
    Shell: '#89e051', Kotlin: '#A97BFF', Swift: '#F05138', PHP: '#4F5D95',
    Vue: '#41b883', Dart: '#00B4AB', Scala: '#c22d40', R: '#198CE7'
  };

  var REPO_SVG = '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/></svg>';
  var STAR_SVG = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"/></svg>';
  var FORK_SVG = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z"/></svg>';

  function esc(s) {
    return (s == null ? '' : String(s)).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function card(repo) {
    var lang = repo.language
      ? '<span class="lang"><span class="lang-dot" style="background:' +
        (LANG_COLORS[repo.language] || '#8b949e') + '"></span>' + esc(repo.language) + '</span>'
      : '';
    var desc = repo.description ? '<p>' + esc(repo.description) + '</p>' : '';
    return '<a class="project-card" href="' + esc(repo.html_url) + '" target="_blank" rel="noopener">' +
      '<div class="repo-head">' + REPO_SVG +
        '<span class="repo-name">' + esc(repo.name) + '</span>' +
        '<span class="badge">Public</span>' +
      '</div>' +
      desc +
      '<div class="repo-meta">' + lang +
        '<span class="stat">' + STAR_SVG + esc(repo.stargazers_count) + '</span>' +
        '<span class="stat">' + FORK_SVG + esc(repo.forks_count) + '</span>' +
      '</div></a>';
  }

  function prepare(repos) {
    return repos
      .filter(function (r) { return !r.fork && EXCLUDE.indexOf(r.name) === -1; })
      .sort(function (a, b) { return new Date(b.created_at) - new Date(a.created_at); });
  }

  function render(repos) {
    var grid = document.getElementById('project-grid');
    if (!grid) return;
    if (!repos.length) {
      grid.innerHTML = '<p class="proj-note">No public repositories to show yet.</p>';
      return;
    }
    grid.innerHTML = repos.map(card).join('');
    grid.removeAttribute('aria-busy');
  }

  function showError() {
    var grid = document.getElementById('project-grid');
    if (grid && grid.getAttribute('aria-busy') === 'true') {
      grid.innerHTML = '<p class="proj-note">Couldn’t load repositories right now. ' +
        'View them on <a href="https://github.com/' + GH_USER + '?tab=repositories" ' +
        'target="_blank" rel="noopener">GitHub →</a></p>';
    }
  }

  function readCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) { return null; }
  }
  function writeCache(repos) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), repos: repos })); } catch (e) {}
  }

  function init() {
    var cached = readCache();
    if (cached && cached.repos) render(prepare(cached.repos)); // instant paint from cache
    if (cached && cached.t && (Date.now() - cached.t) < CACHE_TTL) return; // still fresh

    fetch(API, { headers: { Accept: 'application/vnd.github+json' } })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (repos) { writeCache(repos); render(prepare(repos)); })
      .catch(function () { showError(); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
