import threading
import time

import numpy as np
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.reachy_mini import INIT_HEAD_POSE


# Idle antenna sway
ANTENNA_SWAY_AMP_DEG = 15.0
ANTENNA_SWAY_FREQ_HZ = 0.3

# Streaming control loop rate.
LOOP_HZ = 50


class EmbodiedFo(ReachyMiniApp):
    custom_app_url: str | None = None
    request_media_backend: str | None = None

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        reachy_mini.goto_target(
            head=INIT_HEAD_POSE,
            antennas=[0.0, 0.0],
            duration=1.5,
        )
        print("Fo is awake and waiting. Ctrl+C to exit.")

        t0 = time.time()
        dt = 1.0 / LOOP_HZ
        amp_rad = np.deg2rad(ANTENNA_SWAY_AMP_DEG)

        # Continuous idle: head still, antennas swing in phase-opposed cross.
        while not stop_event.is_set():
            t = time.time() - t0

            a = amp_rad * np.sin(2.0 * np.pi * ANTENNA_SWAY_FREQ_HZ * t)

            reachy_mini.set_target(
                head=INIT_HEAD_POSE,
                antennas=[a, -a],
            )

            time.sleep(dt)


if __name__ == "__main__":
    app = EmbodiedFo()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
