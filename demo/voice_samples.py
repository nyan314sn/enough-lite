"""Make short narration samples with OpenAI text-to-speech, one per voice, to choose the demo voice.

Reads OPENAI_TTS_API_KEY (a separate key for speech) from the .env files the app uses (this folder's parent and up); the key is never printed.
Run: python demo/voice_samples.py  ->  demo/samples/<voice>.mp3
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app import config  # noqa: E402,F401  (loads the .env files)
from openai import OpenAI  # noqa: E402

TEXT = ("Can you retire when you want? Tell Enough about your household in your own words. "
        "A team of AI advisers checks each part, and every number comes from real calculations. "
        "In about twenty seconds, you have a plan you can actually read.")
STYLE = ("Warm, calm and confident, like a friendly product narrator. Natural pace, clear diction, "
         "slight smile in the voice. Not salesy.")
VOICES = sys.argv[1:] or ["nova"]

out = HERE / "samples"
out.mkdir(exist_ok=True)
client = OpenAI(api_key=os.environ["OPENAI_TTS_API_KEY"].strip())
for v in VOICES:
    path = out / f"{v}.mp3"
    with client.audio.speech.with_streaming_response.create(model="gpt-4o-mini-tts", voice=v, input=TEXT, instructions=STYLE) as r:
        r.stream_to_file(path)
    print("wrote", path.name, path.stat().st_size, "bytes")
