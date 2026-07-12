import asyncio, json, base64, wave

key = None
for line in open('.env'):
    if line.startswith('OPENAI_REALTIME_API_KEY='):
        key = line.split('=',1)[1].strip().strip('"').strip("'")
assert key

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
                     "content": [{"type": "input_text", "text": "Say hello to Leon and confirm the realtime link works, in English then Chinese."}]}}))
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
            with wave.open("output/realtime_test/hello.wav","wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(bytes(audio))
            print("saved output/realtime_test/hello.wav")

asyncio.run(main())
