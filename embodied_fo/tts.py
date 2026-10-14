import asyncio
import concurrent.futures
import tempfile
import time
from pathlib import Path

import edge_tts
import soundfile as sf
from gtts import gTTS
from reachy_mini import ReachyMini

VOICE = "en-US-AvaNeural"
PLAYBACK_TAIL_S = 0.3

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


async def _synthesize(text: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(out_path)


def _synthesize_to_file(text: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        asyncio.run(_synthesize(text, path))
    except Exception as e:
        print(f"[edge-tts failed ({type(e).__name__}), falling back to gTTS]")
        gTTS(text, lang="en", tld="com").save(path)
    return path


def prepare(text: str) -> concurrent.futures.Future | None:
    if not text.strip():
        return None
    return _executor.submit(_synthesize_to_file, text)


def play(reachy_mini: ReachyMini, future: concurrent.futures.Future | None) -> None:
    if future is None:
        return
    path = future.result()
    try:
        duration = sf.info(path).duration
        reachy_mini.media.play_sound(path)
        time.sleep(duration + PLAYBACK_TAIL_S)
    finally:
        Path(path).unlink(missing_ok=True)


def speak(reachy_mini: ReachyMini, text: str) -> None:
    play(reachy_mini, prepare(text))
