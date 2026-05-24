// rules.js — detection rules for X Cleaner
// Loaded before content.js. Exposes window.XC_RULES.

(function () {
  'use strict';

  // ---------------------------------------------------------------
  // Known AI reply / agent handles (exact match, case-insensitive)
  // Curated list — extend over time. Keep precision > recall.
  // ---------------------------------------------------------------
  const AI_HANDLES = new Set([
    'grok',
    'askperplexity',
    'perplexity_ai',
    'replyguynet',
    'aigptbot',
    'chatgptbot',
    'askgrok',
    'grokaiapp',
    'autoreplyai',
    'aireplyguy',
    'gemini_app',
    'chatgptapp',
    'aibotreply',
    'replyaibot',
    'ai_agent_x',
    'autogrok',
    'grokchain',
    'grokanswers',
  ]);

  // ---------------------------------------------------------------
  // Username regex patterns — likely AI / bot reply accounts.
  // Tuned to avoid false positives on real users.
  // ---------------------------------------------------------------
  const AI_HANDLE_PATTERNS = [
    /^ask[_-]?(grok|ai|gpt|bot)/i,
    /^(grok|gpt|claude|gemini|llama)[_-]?(reply|bot|ai|agent|answers?)$/i,
    /^(reply|auto)[_-]?(guy|gpt|ai|bot)\d*$/i,
    /^ai[_-]?(reply|bot|agent|answers?)\d*$/i,
    /^bot[_-]?(reply|ai|gpt)\d*$/i,
  ];

  // ---------------------------------------------------------------
  // Bio / display-name keywords that suggest an AI agent account.
  // Combined with other signals — never used alone.
  // ---------------------------------------------------------------
  const AI_BIO_KEYWORDS = [
    'ai agent',
    'ai-powered',
    'powered by gpt',
    'powered by grok',
    'powered by claude',
    'autonomous agent',
    'reply bot',
    'ai reply',
    'gpt-powered',
    'autoreply',
    'auto-reply bot',
  ];

  // ---------------------------------------------------------------
  // DOM phrases that indicate the viewer is blocked by the author,
  // or the post is otherwise unavailable due to author action.
  // Cover EN + common locales.
  // ---------------------------------------------------------------
  const BLOCKED_BY_PHRASES = [
    "you're blocked",
    'you are blocked',
    "you've been blocked",
    'this post is unavailable',
    'this tweet is unavailable',
    '此帖子不可用',
    '此推文不可用',
    '您已被屏蔽',
    '你已被屏蔽',
    'blockiert dich',
    'vous a bloqué',
    'te ha bloqueado',
    'ti ha bloccato',
    'заблокировал вас',
    'があなたをブロックしました',
    '님이 회원님을 차단했습니다',
  ];

  // ---------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------
  function normalizeHandle(h) {
    if (!h) return '';
    return String(h).replace(/^@/, '').trim().toLowerCase();
  }

  function isKnownAIHandle(handle) {
    const h = normalizeHandle(handle);
    if (!h) return false;
    if (AI_HANDLES.has(h)) return true;
    return AI_HANDLE_PATTERNS.some((re) => re.test(h));
  }

  function bioLooksLikeAI(text) {
    if (!text) return false;
    const t = String(text).toLowerCase();
    return AI_BIO_KEYWORDS.some((k) => t.includes(k));
  }

  function textIndicatesBlockedBy(text) {
    if (!text) return false;
    const t = String(text).toLowerCase();
    return BLOCKED_BY_PHRASES.some((p) => t.includes(p));
  }

  window.XC_RULES = {
    AI_HANDLES,
    AI_HANDLE_PATTERNS,
    AI_BIO_KEYWORDS,
    BLOCKED_BY_PHRASES,
    normalizeHandle,
    isKnownAIHandle,
    bioLooksLikeAI,
    textIndicatesBlockedBy,
  };
})();
