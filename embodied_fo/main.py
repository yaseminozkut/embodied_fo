import threading
import time

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.reachy_mini import INIT_HEAD_POSE

from embodied_fo import fo_client

ANTENNA_SWAY_AMP_DEG = 15.0
ANTENNA_SWAY_FREQ_HZ = 0.3
LOOP_HZ = 50


class EmbodiedFo(ReachyMiniApp):
    custom_app_url: str | None = None
    request_media_backend: str | None = None

    def _sway(self, reachy_mini: ReachyMini, stop_event: threading.Event) -> None:
        t0 = time.time()
        dt = 1.0 / LOOP_HZ
        amp_rad = np.deg2rad(ANTENNA_SWAY_AMP_DEG)
        while not stop_event.is_set():
            t = time.time() - t0
            a = amp_rad * np.sin(2.0 * np.pi * ANTENNA_SWAY_FREQ_HZ * t)
            reachy_mini.set_target(head=INIT_HEAD_POSE, antennas=[a, -a])
            time.sleep(dt)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        reachy_mini.goto_target(head=INIT_HEAD_POSE, antennas=[0.0, 0.0], duration=1.5)

        print("Signing in to Fo...")
        fo_client.start()
        print("Signed in.\n")

        motion = threading.Thread(
            target=self._sway, args=(reachy_mini, stop_event), daemon=True
        )
        motion.start()

        print("Ask Fo anything. Type 'quit' or Ctrl-D to exit.\n")
        try:
            while not stop_event.is_set():
                try:
                    text = input("you > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if text.lower() in {"quit", "exit"}:
                    break
                if not text:
                    continue
                try:
                    reply = fo_client.ask_fo(text)
                except Exception as e:
                    print(f"[fo error] {e}\n")
                    continue
                print(f"fo  > {reply}\n")
        finally:
            stop_event.set()
            motion.join()
            fo_client.stop()
            fo_client.sign_out()
            print("\nSigned out.")


if __name__ == "__main__":
    app = EmbodiedFo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
