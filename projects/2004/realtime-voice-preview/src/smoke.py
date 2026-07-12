import asyncio, json, base64, wave, os
from pathlib import Path

# Load API key: env vars win, then project-local .env, then cwd/.env.
# Mirrors server.py — no machine-specific paths.
key = None
for k in ("OPENAI_REALTIME_API_KEY", "OPENAI_API_KEY"):
    val = os.environ.get(k)
    if val:
        key = val.strip().strip('"').strip("'")
        break
if not key:
    for env_path in (Path(__file__).resolve().parent.parent / ".env", Path.cwd() / ".env"):
        if not env_path.exists():
            continue
        for raw in env_path.read_bytes().splitlines():
            if b"=" not in raw:
                continue
            name, val = raw.split(b"=", 1)
            try:
                key_name = name.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if key_name not in ("OPENAI_REALTIME_API_KEY", "OPENAI_API_KEY"):
                continue
            if val[:1] in (b'"', b"'") and val[-1:] == val[:1]:
                val = val[1:-1]
            key = val.decode("utf-8", errors="strict").strip()
            if key:
                break
        if key:
            break
assert key, "Set OPENAI_REALTIME_API_KEY in env or in a .env at project root"

import websockets

async def main():
    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime-2.1"
    async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {key}"}, max_size=1<<24) as ws:
        audio = bytearray(); transcript = ""
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "output_modalities": ["audio"],
                "audio": {"output": {"format": {"type": "audio/pcm", "rate": 24000}, "voice": "marin"}},
                "instructions": "You are Starchild's voice. Reply in one short sentence."
            }}))
        await ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "Say hello and confirm the realtime link works, in English then Chinese."}]}}))
        await ws.send(json.dumps({"type": "response.create"}))
        async for msg in ws:
            ev = json.loads(msg); t = ev["type"]
            if t == "response.output_audio.delta":
                audio.extend(base64.b64decode(ev["delta"]))
            elif t == "response.output_audio_transcript.delta":
                transcript += ev["delta"]
            elif t == "response.done":
                print("STATUS:", ev["response"].get("status"))
                print("USAGE:", json.dumps(ev["response"].get("usage", {}))[:400])
                break
            elif t == "error":
                print("ERROR:", json.dumps(ev)[:600]); break
        print("transcript:", transcript)
        print("audio bytes:", len(audio))
        if audio:
            with wave.open("hello.wav","wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(bytes(audio))
            print("saved hello.wav")

asyncio.run(main())
