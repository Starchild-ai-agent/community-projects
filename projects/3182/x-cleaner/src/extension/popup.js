// popup.js — settings UI

const STORAGE_KEY = 'xc_settings_v1';
const STATS_KEY = 'xc_stats_v1';

const DEFAULTS = {
  enabled: true,
  hideBlockedBy: true,
  hideAIReplies: true,
  hideKnownAIHandles: true,
  allowlist: [],
  showReason: true,
};

const TOGGLE_IDS = ['enabled', 'hideBlockedBy', 'hideKnownAIHandles', 'hideAIReplies'];

function load() {
  chrome.storage.local.get([STORAGE_KEY, STATS_KEY], (res) => {
    const s = { ...DEFAULTS, ...(res[STORAGE_KEY] || {}) };
    TOGGLE_IDS.forEach((id) => {
      document.getElementById(id).checked = !!s[id];
    });
    document.getElementById('allowlist').value = (s.allowlist || []).join('\n');

    const stats = res[STATS_KEY] || { hiddenBlockedBy: 0, hiddenAI: 0, total: 0 };
    document.getElementById('stat-total').textContent = stats.total || 0;
    document.getElementById('stat-blocked').textContent = stats.hiddenBlockedBy || 0;
    document.getElementById('stat-ai').textContent = stats.hiddenAI || 0;
  });
}

function commit() {
  const s = { ...DEFAULTS };
  TOGGLE_IDS.forEach((id) => {
    s[id] = document.getElementById(id).checked;
  });
  s.allowlist = document
    .getElementById('allowlist')
    .value.split(/[\n,]/)
    .map((x) => x.replace(/^@/, '').trim())
    .filter(Boolean);
  chrome.storage.local.set({ [STORAGE_KEY]: s });
}

document.addEventListener('DOMContentLoaded', () => {
  load();
  TOGGLE_IDS.forEach((id) => {
    document.getElementById(id).addEventListener('change', commit);
  });
  document.getElementById('save').addEventListener('click', commit);
});
