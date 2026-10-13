import threading
import time

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.reachy_mini import INIT_HEAD_POSE

from embodied_fo import fo_client, stt, tts

LOOP_HZ = 50

IDLE_ANTENNA_AMP_DEG = 15.0
IDLE_ANTENNA_FREQ_HZ = 0.3


class EmbodiedFo(ReachyMiniApp):
    custom_app_url: str | None = None
    request_media_backend: str | None = None

    def _sway(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        t0 = time.time()
        dt = 1.0 / LOOP_HZ
        amp_rad = np.deg2rad(IDLE_ANTENNA_AMP_DEG)
        while not stop_event.is_set():
            t = time.time() - t0
            a = amp_rad * np.sin(2.0 * np.pi * IDLE_ANTENNA_FREQ_HZ * t)
            reachy_mini.set_target(head=INIT_HEAD_POSE, antennas=[a, -a])
            time.sleep(dt)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        reachy_mini.goto_target(head=INIT_HEAD_POSE, antennas=[0.0, 0.0], duration=1.5)

        print("Loading speech model...")
        stt.start()
        print("Signing in to Fo...")
        fo_client.start()
        reachy_mini.enable_wobbling()
        print("Ready. Just talk — Ctrl-C to exit.\n")

        motion = threading.Thread(
            target=self._sway, args=(reachy_mini, stop_event), daemon=True
        )
        motion.start()

        def handle_utterance(text: str) -> None:
            print(f"you > {text}")
            try:
                reply = fo_client.ask_fo(text)
            except Exception as e:
                print(f"[fo error] {e}\n")
                return
            print(f"fo  > {reply}\n")
            tts.speak(reachy_mini, reply)

        stt.start_listener(handle_utterance)

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
