from flask import Flask, request, jsonify, send_from_directory
import os
from core.http_client import proxied_get, proxied_post

app = Flask(__name__, static_folder='.')
VENICE_BASE = 'https://api.venice.ai/api/v1'
CALLER_ID = f"preview:{os.getenv('PREVIEW_ID', 'venice-demo')}"


def _resolve_api_key(payload: dict | None = None) -> str | None:
    payload = payload or {}
    key = payload.get('api_key') or request.headers.get('X-Venice-Key')
    if key:
        return key.strip()

    env_key = os.getenv('VENICE_API_KEY')
    if env_key:
        return env_key

    for k, v in os.environ.items():
        if k.startswith('CUSTOM_KEY_VENICE') and v:
            return v
    return None


def _headers(api_key: str, json_mode: bool = True):
    h = {
        'Authorization': f'Bearer {api_key}',
        'SC-CALLER-ID': CALLER_ID,
    }
    if json_mode:
        h['Content-Type'] = 'application/json'
    return h


@app.get('/')
def home():
    return send_from_directory('.', 'index.html')


@app.get('/api/health')
def health():
    return jsonify({'ok': True})


@app.post('/api/balance')
def balance():
    payload = request.get_json(silent=True) or {}
    api_key = _resolve_api_key(payload)
    if not api_key:
        return jsonify({'ok': False, 'error': '缺少 Venice API Key'}), 400

    r = proxied_get(
        f'{VENICE_BASE}/api_keys/rate_limits',
        headers=_headers(api_key, json_mode=False),
        timeout=30,
    )
    if r.status_code >= 400:
        return jsonify({'ok': False, 'status': r.status_code, 'error': r.text[:500]}), r.status_code

    data = r.json().get('data', {})
    return jsonify({
        'ok': True,
        'tier': (data.get('apiTier') or {}).get('id'),
        'balance_usd': (data.get('balances') or {}).get('USD'),
        'is_charged': (data.get('apiTier') or {}).get('isCharged'),
        'next_epoch_begins': data.get('nextEpochBegins'),
        'rate_limits_count': len(data.get('rateLimits', [])),
    })


@app.get('/api/models')
def models():
    model_type = request.args.get('type', 'text')
    api_key = _resolve_api_key()
    if not api_key:
        return jsonify({'ok': False, 'error': '缺少 Venice API Key'}), 400

    r = proxied_get(
        f'{VENICE_BASE}/models',
        params={'type': model_type},
        headers=_headers(api_key, json_mode=False),
        timeout=45,
    )
    if r.status_code >= 400:
        return jsonify({'ok': False, 'status': r.status_code, 'error': r.text[:500]}), r.status_code

    raw = r.json().get('data', [])
    out = []
    for m in raw[:50]:
        spec = m.get('model_spec') or {}
        out.append({
            'id': m.get('id'),
            'type': m.get('type'),
            'name': spec.get('name'),
            'privacy': spec.get('privacy'),
            'description': (spec.get('description') or '')[:120],
        })
    return jsonify({'ok': True, 'count': len(raw), 'models': out})


@app.post('/api/chat')
def chat():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get('prompt') or '').strip()
    model = (payload.get('model') or 'zai-org-glm-5-1').strip()
    if not prompt:
        return jsonify({'ok': False, 'error': 'prompt 不能为空'}), 400

    api_key = _resolve_api_key(payload)
    if not api_key:
        return jsonify({'ok': False, 'error': '缺少 Venice API Key'}), 400

    body = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 256,
        'venice_parameters': {
            'include_venice_system_prompt': False,
            'enable_web_search': 'off',
            'strip_thinking_response': True,
        },
    }

    r = proxied_post(
        f'{VENICE_BASE}/chat/completions',
        json=body,
        headers=_headers(api_key, json_mode=True),
        timeout=60,
    )
    if r.status_code >= 400:
        return jsonify({'ok': False, 'status': r.status_code, 'error': r.text[:800]}), r.status_code

    data = r.json()
    text = ''
    try:
        text = data.get('choices', [])[0].get('message', {}).get('content', '')
    except Exception:
        text = ''
    return jsonify({'ok': True, 'model': model, 'text': text, 'usage': data.get('usage')})


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8080'))
    app.run(host='127.0.0.1', port=port, debug=False)
