import asyncio
import tempfile
import time
from pathlib import Path

import edge_tts
import soundfile as sf
from reachy_mini import ReachyMini

VOICE = "en-US-AvaNeural"
PLAYBACK_TAIL_S = 0.3


async def _synthesize(text: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(out_path)


def speak(reachy_mini: ReachyMini, text: str) -> None:
    if not text.strip():
        return
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        asyncio.run(_synthesize(text, path))
        duration = sf.info(path).duration
        reachy_mini.media.play_sound(path)
        time.sleep(duration + PLAYBACK_TAIL_S)
    finally:
        Path(path).unlink(missing_ok=True)
