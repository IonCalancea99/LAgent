// LAgent documentation site — shared behavior (sidebar, TOC, theme, search)
// No external dependencies; works fully offline.

const NAV_ITEMS = [
  { id: "index", href: "index.html", label: "Overview", icon: "\ud83c\udfe0" },
  { id: "installation", href: "installation.html", label: "Installation", icon: "\u2699\ufe0f" },
  { id: "preparation", href: "preparation.html", label: "Preparation & Config", icon: "\ud83e\udde9" },
  { id: "running", href: "running.html", label: "Running LAgent", icon: "\u25b6\ufe0f" },
  { id: "quest-mode", href: "quest-mode.html", label: "Quest Mode", icon: "\ud83d\udcdc" },
  { id: "class-flows", href: "class-flows.html", label: "Class Leveling Flows", icon: "\ud83e\udded" },
  { id: "training", href: "training.html", label: "Training Pipeline", icon: "\ud83c\udf93" },
  { id: "architecture", href: "architecture.html", label: "Architecture", icon: "\ud83c\udfd7\ufe0f" },
  { id: "troubleshooting", href: "troubleshooting.html", label: "Troubleshooting", icon: "\ud83d\udee0\ufe0f" },
];

function currentPageId() {
  const script = document.currentScript || document.querySelector('script[data-page]');
  return script ? script.getAttribute("data-page") : "index";
}

function renderSidebar(activeId) {
  const nav = document.getElementById("sidebar");
  if (!nav) return;
  let html = '<div class="group-title">Guide</div>';
  NAV_ITEMS.forEach((item) => {
    const active = item.id === activeId ? " active" : "";
    html += `<a class="nav-link${active}" href="${item.href}"><span>${item.icon}</span><span>${item.label}</span></a>`;
  });
  nav.innerHTML = html;
}

function setupMobileNav() {
  const toggle = document.getElementById("navToggle");
  const sidebar = document.getElementById("sidebar");
  if (!toggle || !sidebar) return;
  toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
  sidebar.addEventListener("click", (e) => {
    if (e.target.closest("a")) sidebar.classList.remove("open");
  });
  document.addEventListener("click", (e) => {
    if (!sidebar.contains(e.target) && !toggle.contains(e.target)) {
      sidebar.classList.remove("open");
    }
  });
}

function setupTheme() {
  const btn = document.getElementById("themeToggle");
  const stored = localStorage.getItem("lagent-docs-theme");
  if (stored) document.documentElement.setAttribute("data-theme", stored);
  if (!btn) return;
  btn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", cur);
    localStorage.setItem("lagent-docs-theme", cur);
  });
}

function buildPageNav(activeId) {
  const idx = NAV_ITEMS.findIndex((i) => i.id === activeId);
  if (idx === -1) return;
  const prev = NAV_ITEMS[idx - 1];
  const next = NAV_ITEMS[idx + 1];
  const container = document.querySelector(".page-nav");
  if (!container) return;
  container.innerHTML = "";
  if (prev) {
    container.innerHTML += `<a class="prev" href="${prev.href}"><span class="dir">\u2190 Previous</span>${prev.label}</a>`;
  } else {
    container.innerHTML += "<span></span>";
  }
  if (next) {
    container.innerHTML += `<a class="next" href="${next.href}"><span class="dir">Next \u2192</span>${next.label}</a>`;
  }
}

function buildToc() {
  const toc = document.getElementById("toc");
  const content = document.querySelector(".content");
  if (!toc || !content) return;
  const headings = content.querySelectorAll("h2, h3");
  if (!headings.length) {
    toc.innerHTML = "";
    return;
  }
  let html = '<div class="toc-title">On this page</div>';
  headings.forEach((h, i) => {
    if (!h.id) h.id = `section-${i}`;
    const cls = h.tagName === "H3" ? " h3" : "";
    html += `<a class="${cls.trim()}" href="#${h.id}" data-target="${h.id}">${h.textContent}</a>`;
  });
  toc.innerHTML = html;

  const links = toc.querySelectorAll("a");
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const link = toc.querySelector(`a[data-target="${entry.target.id}"]`);
        if (!link) return;
        if (entry.isIntersecting) {
          links.forEach((l) => l.classList.remove("active"));
          link.classList.add("active");
        }
      });
    },
    { rootMargin: "-80px 0px -70% 0px" }
  );
  headings.forEach((h) => observer.observe(h));
}

function setupSearch() {
  const input = document.getElementById("searchInput");
  const results = document.getElementById("searchResults");
  if (!input || !results || typeof SEARCH_INDEX === "undefined") return;

  function render(matches, query) {
    if (!query) {
      results.classList.remove("open");
      results.innerHTML = "";
      return;
    }
    if (!matches.length) {
      results.innerHTML = '<div class="search-empty">No results for "' + query + '"</div>';
      results.classList.add("open");
      return;
    }
    results.innerHTML = matches
      .slice(0, 8)
      .map(
        (m) =>
          `<a href="${m.href}"><span>${m.title}</span><small>${m.snippet}</small></a>`
      )
      .join("");
    results.classList.add("open");
  }

  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (!q) return render([], "");
    const matches = SEARCH_INDEX.filter(
      (entry) =>
        entry.title.toLowerCase().includes(q) ||
        entry.keywords.toLowerCase().includes(q) ||
        entry.snippet.toLowerCase().includes(q)
    );
    render(matches, q);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      input.value = "";
      render([], "");
      input.blur();
    }
    if (e.key === "Enter") {
      const first = results.querySelector("a");
      if (first) window.location.href = first.getAttribute("href");
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-wrap")) {
      results.classList.remove("open");
    }
  });
}

(function init() {
  const pageId = currentPageId();
  document.addEventListener("DOMContentLoaded", () => {
    renderSidebar(pageId);
    setupMobileNav();
    setupTheme();
    buildToc();
    buildPageNav(pageId);
    setupSearch();
  });
})();
