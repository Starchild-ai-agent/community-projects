# Realtime Voice Preview

## What
A WebRTC-based real-time voice interface that connects OpenAI's Realtime API to your Starchild Agent. Speak naturally, interrupt mid-sentence, and trigger agent tools via voice.

Features:
- Real-time bidirectional voice via OpenAI Realtime API (WebRTC)
- Function calling bridge — voice queries route to your Starchild Agent runtime
- Configurable agent ID, model, thread mode, and system prompt
- Starchild black/orange themed UI with diagnostics panel
- Thread-level serialization to prevent duplicate request conflicts

## Required env
- `OPENAI_REALTIME_API_KEY` — OpenAI API key with realtime model access (from platform.openai.com)
- Optional: `STARCHILD_RUNTIME_URL` — defaults to `http://127.0.0.1:8000`
- Optional: `REALTIME_MODEL` — defaults to `gpt-realtime-2.1`
- Optional: `REALTIME_VOICE` — defaults to `marin`
- Optional: `REALTIME_DEMO_PORT` — defaults to `8765`

## How to start
1. Ensure `OPENAI_REALTIME_API_KEY` is set in your workspace `.env`
2. Run: `python3 src/server.py`
3. Open the preview URL in your browser
4. Click "Connect" and allow microphone access
5. Speak naturally — say "ask Starchild about my account" to test the agent bridge

### Smoke test (no browser needed)
```bash
python3 src/smoke.py
# success → hello.wav + transcript on stdout
```

### Parser unit tests
```bash
node src/test_function_calls.js
# 59 tests, exits non-zero on failure
```

## Outputs
- Voice conversation through browser
- `hello.wav` — audio output from smoke test
- Transcript and usage stats in the UI diagnostics panel

## Troubleshooting
- **No sound / connection fails**: Check that `OPENAI_REALTIME_API_KEY` is valid and has realtime model access. Verify billing credit on your OpenAI account.
- **"Query interrupted" errors**: This was a known issue with duplicate Realtime events. The server now serializes bridge calls per thread with a 15s result cache. If it recurs, check for multiple browser tabs on the same voice thread.
- **Agent bridge returns errors**: Ensure the Starchild runtime is running at `STARCHILD_RUNTIME_URL` (default `http://127.0.0.1:8000`). Check `/health` endpoint.
- **SDP exchange fails through WAF**: The server wraps SDP in base64 JSON to bypass WAF content inspection. Both `/session` POST and response use this format.