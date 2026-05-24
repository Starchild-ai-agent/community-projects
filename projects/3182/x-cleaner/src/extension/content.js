// content.js — main scanner for X Cleaner.
// Walks the timeline, scores each tweet, collapses matches.

(function () {
  'use strict';

  const R = window.XC_RULES || {};
  const STORAGE_KEY = 'xc_settings_v1';
  const STATS_KEY = 'xc_stats_v1';

  const DEFAULTS = {
    enabled: true,
    hideBlockedBy: true,
    hideAIReplies: true,
    hideKnownAIHandles: true,
    allowlist: [], // handles never to hide
    showReason: true,
  };

  let settings = { ...DEFAULTS };
  let stats = { hiddenBlockedBy: 0, hiddenAI: 0, total: 0, today: dateKey() };

  function dateKey() {
    const d = new Date();
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }

  // ---------- storage ----------
  function loadSettings() {
    return new Promise((resolve) => {
      try {
        chrome.storage.local.get([STORAGE_KEY, STATS_KEY], (res) => {
          if (res && res[STORAGE_KEY]) {
            settings = { ...DEFAULTS, ...res[STORAGE_KEY] };
          }
          if (res && res[STATS_KEY]) {
            stats = { ...stats, ...res[STATS_KEY] };
            if (stats.today !== dateKey()) {
              stats = { hiddenBlockedBy: 0, hiddenAI: 0, total: 0, today: dateKey() };
            }
          }
          resolve();
        });
      } catch (_e) {
        resolve();
      }
    });
  }

  function saveStats() {
    try {
      chrome.storage.local.set({ [STATS_KEY]: stats });
    } catch (_e) {}
  }

  // Re-scan whenever settings change.
  try {
    chrome.storage.onChanged.addListener((changes) => {
      if (changes[STORAGE_KEY]) {
        settings = { ...DEFAULTS, ...changes[STORAGE_KEY].newValue };
        // unhide everything previously hidden, then re-scan
        document.querySelectorAll('article[data-xc-hidden="1"]').forEach((el) => {
          el.removeAttribute('data-xc-hidden');
          el.removeAttribute('data-xc-reason');
          const banner = el.querySelector('.xc-banner');
          if (banner) banner.remove();
          el.style.display = '';
        });
        document.querySelectorAll('article').forEach(scanArticle);
      }
    });
  } catch (_e) {}

  // ---------- extraction ----------
  function getAuthorHandle(article) {
    // <a href="/handle" role="link"> appears near top; first /handle anchor
    // inside the user block.
    const userBlock = article.querySelector('[data-testid="User-Name"]');
    if (!userBlock) return '';
    const anchors = userBlock.querySelectorAll('a[role="link"][href^="/"]');
    for (const a of anchors) {
      const href = a.getAttribute('href') || '';
      const m = href.match(/^\/([A-Za-z0-9_]{1,15})$/);
      if (m) return m[1];
    }
    return '';
  }

  function getArticleText(article) {
    const t = article.querySelector('[data-testid="tweetText"]');
    return t ? t.innerText : '';
  }

  function getFullText(article) {
    // Used for blocked-by detection — sometimes the article shows only a
    // notice without a tweetText element.
    return article.innerText || '';
  }

  // ---------- scoring ----------
  function classify(article) {
    const full = getFullText(article);

    // 1. Blocked-by-author detection (handle may be missing for these)
    if (settings.hideBlockedBy && R.textIndicatesBlockedBy(full)) {
      return { hide: true, reason: 'blocked-by', label: 'Blocked you' };
    }

    const handle = getAuthorHandle(article);
    if (!handle) return { hide: false };

    const handleLC = handle.toLowerCase();
    if (settings.allowlist.map((h) => h.toLowerCase()).includes(handleLC)) {
      return { hide: false };
    }

    // 2. Known AI / agent handles
    if (settings.hideKnownAIHandles && R.isKnownAIHandle(handle)) {
      return { hide: true, reason: 'ai-handle', label: `AI bot (@${handle})` };
    }

    // 3. AI-flavoured display name on a reply tweet
    if (settings.hideAIReplies) {
      const userBlock = article.querySelector('[data-testid="User-Name"]');
      const displayName = userBlock ? userBlock.innerText : '';
      if (
        R.bioLooksLikeAI(displayName) &&
        /Replying to/i.test(article.innerText || '')
      ) {
        return { hide: true, reason: 'ai-reply', label: `AI-style reply (@${handle})` };
      }
    }

    return { hide: false };
  }

  // ---------- hide UI ----------
  function hideArticle(article, info) {
    if (article.dataset.xcHidden === '1') return;
    article.dataset.xcHidden = '1';
    article.dataset.xcReason = info.reason;

    const banner = document.createElement('div');
    banner.className = 'xc-banner';
    banner.innerHTML = `
      <span class="xc-banner-label">Hidden — ${escapeHTML(info.label)}</span>
      <button class="xc-banner-show" type="button">Show</button>
    `;
    banner.querySelector('.xc-banner-show').addEventListener('click', (e) => {
      e.stopPropagation();
      e.preventDefault();
      article.classList.toggle('xc-reveal');
    });

    article.classList.add('xc-collapsed');
    article.insertBefore(banner, article.firstChild);

    stats.total += 1;
    if (info.reason === 'blocked-by') stats.hiddenBlockedBy += 1;
    else stats.hiddenAI += 1;
    saveStats();
  }

  function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // ---------- scan ----------
  function scanArticle(article) {
    if (!settings.enabled) return;
    if (article.dataset.xcSeen === '1' && article.dataset.xcHidden !== '1') {
      // already classified as visible
      return;
    }
    const info = classify(article);
    article.dataset.xcSeen = '1';
    if (info.hide) hideArticle(article, info);
  }

  function scanAll(root) {
    const articles = (root || document).querySelectorAll('article');
    articles.forEach(scanArticle);
  }

  // ---------- observe ----------
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      m.addedNodes.forEach((node) => {
        if (!(node instanceof HTMLElement)) return;
        if (node.tagName === 'ARTICLE') scanArticle(node);
        else scanAll(node);
      });
    }
  });

  async function start() {
    await loadSettings();
    scanAll(document);
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
