import random
import threading
import time

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.motion.recorded_move import RecordedMoves
from reachy_mini.reachy_mini import INIT_HEAD_POSE, SLEEP_HEAD_POSE

from embodied_fo import fo_client, stt, tts

EMOTION_LIBRARY = "pollen-robotics/reachy-mini-emotions-library"
RESPOND_EMOTIONS = [
    "surprised1", "yes1", "welcoming1", "success1", "success2",
    "proud1", "attentive1", "inquiring2", "welcoming2",
    "inquiring3", "cheerful1", "understanding1",
]

LOOP_HZ = 50

IDLE_ANTENNA_AMP_DEG = 15.0
IDLE_ANTENNA_FREQ_HZ = 0.3

THINK_ANTENNA_AMP_SCALE = 0.3
THINK_ANTENNA_FREQ_HZ = 0.15

_THINK_TILT_DEG = 15
_r = np.deg2rad(_THINK_TILT_DEG)
_ROLL_X = np.array([
    [1, 0, 0, 0],
    [0, np.cos(_r), -np.sin(_r), 0],
    [0, np.sin(_r), np.cos(_r), 0],
    [0, 0, 0, 1],
])
THINK_HEAD_POSE = INIT_HEAD_POSE @ _ROLL_X

HEAD_SMOOTHING = 0.04


class EmbodiedFo(ReachyMiniApp):
    custom_app_url: str | None = None
    request_media_backend: str | None = None

    def _sway(
        self,
        reachy_mini: ReachyMini,
        stop_event: threading.Event,
        thinking: threading.Event,
        playing_move: threading.Event,
    ) -> None:
        t0 = time.time()
        dt = 1.0 / LOOP_HZ
        amp_rad = np.deg2rad(IDLE_ANTENNA_AMP_DEG)
        pose = INIT_HEAD_POSE.copy()
        while not stop_event.is_set():
            if playing_move.is_set():
                time.sleep(dt)
                pose = INIT_HEAD_POSE.copy()
                continue
            t = time.time() - t0
            if thinking.is_set():
                target_pose = THINK_HEAD_POSE
                a = amp_rad * THINK_ANTENNA_AMP_SCALE * np.sin(
                    2.0 * np.pi * THINK_ANTENNA_FREQ_HZ * t
                )
            else:
                target_pose = INIT_HEAD_POSE
                a = amp_rad * np.sin(2.0 * np.pi * IDLE_ANTENNA_FREQ_HZ * t)
            pose = (1.0 - HEAD_SMOOTHING) * pose + HEAD_SMOOTHING * target_pose
            reachy_mini.set_target(head=pose, antennas=[a, -a])
            time.sleep(dt)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        reachy_mini.goto_target(head=INIT_HEAD_POSE, antennas=[0.0, 0.0], duration=1.5)

        print("Loading speech model...")
        stt.start()
        print("Loading emotion library...")
        try:
            emotions_lib = RecordedMoves(EMOTION_LIBRARY)
            respond_moves = [(n, emotions_lib.get(n)) for n in RESPOND_EMOTIONS]
        except Exception as e:
            print(f"[emotions unavailable: {e}]")
            respond_moves = []
        print("Signing in to Fo...")
        fo_client.start()
        reachy_mini.enable_wobbling()
        print("Ready. Just talk — Ctrl-C to exit.\n")

        thinking = threading.Event()
        playing_move = threading.Event()
        motion = threading.Thread(
            target=self._sway,
            args=(reachy_mini, stop_event, thinking, playing_move),
            daemon=True,
        )
        motion.start()

        def on_speech_end() -> None:
            thinking.set()

        def handle_utterance(text: str) -> None:
            print(f"you > {text}")
            try:
                reply = fo_client.ask_fo(text)
            except Exception as e:
                print(f"[fo error] {e}\n")
                return
            finally:
                thinking.clear()
            print(f"fo  > {reply}\n")
            if respond_moves:
                name, move = random.choice(respond_moves)
                print(f"[emotion] {name}")
                playing_move.set()
                try:
                    reachy_mini.play_move(move)
                finally:
                    playing_move.clear()
            tts.speak(reachy_mini, reply)

        stt.start_listener(handle_utterance, on_speech_end=on_speech_end)

        try:
            while not stop_event.wait(0.5):
                pass
        finally:
            stop_event.set()
            motion.join()
            stt.stop()
            try:
                reachy_mini.disable_wobbling()
            except Exception:
                pass
            fo_client.stop()
            fo_client.sign_out()
            print("\nSigned out.")


if __name__ == "__main__":
    app = EmbodiedFo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
