import sounddevice as sd
from faster_whisper import WhisperModel

SAMPLERATE = 16000
MODEL_SIZE = "base"

_model: WhisperModel | None = None


def start() -> None:
    global _model
    _model = WhisperModel(MODEL_SIZE, device="auto", compute_type="auto")


def record_and_transcribe(seconds: float = 5.0) -> str:
    audio = sd.rec(
        int(seconds * SAMPLERATE),
        samplerate=SAMPLERATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    segments, _ = _model.transcribe(
        audio.flatten(),
        language="en",
        initial_prompt="The user is talking to Fo, their AI assistant.",
        hotwords="Fo",
    )
    return "".join(seg.text for seg in segments).strip()
