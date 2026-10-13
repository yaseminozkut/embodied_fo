import queue
import threading
from collections import deque
from typing import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from silero_vad import VADIterator, load_silero_vad

SAMPLERATE = 16000
VAD_FRAME_SAMPLES = 512
PRE_ROLL_FRAMES = 10
MODEL_SIZE = "base"
MIN_SILENCE_MS = 1500
SPEECH_PAD_MS = 200

_whisper: WhisperModel | None = None
_vad = None
_frame_q: queue.Queue = queue.Queue()
_stop = threading.Event()
_muted = threading.Event()
_listener: threading.Thread | None = None
_stream: sd.InputStream | None = None


def start() -> None:
    global _whisper, _vad
    _whisper = WhisperModel(MODEL_SIZE, device="auto", compute_type="auto")
    _vad = load_silero_vad(onnx=True)


def set_muted(flag: bool) -> None:
    if flag:
        _muted.set()
    else:
        _muted.clear()


def _transcribe(audio: np.ndarray) -> str:
    segments, _ = _whisper.transcribe(
        audio,
        language="en",
        initial_prompt="The user is talking to Fo, their AI assistant.",
        hotwords="Fo",
    )
    return "".join(seg.text for seg in segments).strip()


def _audio_cb(indata, frames, time_info, status):
    _frame_q.put(indata[:, 0].copy())


def _loop(on_utterance: Callable[[str], None]) -> None:
    vad_iter = VADIterator(
        _vad,
        sampling_rate=SAMPLERATE,
        min_silence_duration_ms=MIN_SILENCE_MS,
        speech_pad_ms=SPEECH_PAD_MS,
    )
    pre_roll: deque = deque(maxlen=PRE_ROLL_FRAMES)
    utterance: list[np.ndarray] = []
    in_speech = False
    was_muted = False

    def _reset() -> None:
        nonlocal utterance, in_speech
        vad_iter.reset_states()
        pre_roll.clear()
        utterance = []
        in_speech = False
        while True:
            try:
                _frame_q.get_nowait()
            except queue.Empty:
                return

    while not _stop.is_set():
        try:
            frame = _frame_q.get(timeout=0.1)
        except queue.Empty:
            continue
        if _muted.is_set():
            was_muted = True
            continue
        if was_muted:
            _reset()
            was_muted = False
            continue

        event = vad_iter(frame, return_seconds=False)
        if in_speech:
            utterance.append(frame)
        else:
            pre_roll.append(frame)
        if event is not None and "start" in event:
            in_speech = True
            utterance = list(pre_roll) + utterance
            pre_roll.clear()
        if event is not None and "end" in event and in_speech:
            audio = np.concatenate(utterance)
            _muted.set()
            try:
                text = _transcribe(audio)
                if text:
                    on_utterance(text)
            finally:
                was_muted = True
                _muted.clear()


def start_listener(on_utterance: Callable[[str], None]) -> None:
    global _listener, _stream
    _stop.clear()
    _muted.clear()
    _stream = sd.InputStream(
        samplerate=SAMPLERATE,
        channels=1,
        dtype="float32",
        blocksize=VAD_FRAME_SAMPLES,
        callback=_audio_cb,
    )
    _stream.start()
    _listener = threading.Thread(target=_loop, args=(on_utterance,), daemon=True)
    _listener.start()


def stop() -> None:
    _stop.set()
    if _listener is not None:
        _listener.join(timeout=5)
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
