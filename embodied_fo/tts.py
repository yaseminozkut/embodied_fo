import asyncio
import subprocess
import tempfile
from pathlib import Path

import edge_tts

VOICE = "en-US-AvaNeural"


async def _synthesize(text: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(out_path)


def speak(text: str) -> None:
    if not text.strip():
        return
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    try:
        asyncio.run(_synthesize(text, path))
        subprocess.run(["afplay", path], check=True)
    finally:
        Path(path).unlink(missing_ok=True)
