"""WebRTC AEC3 processing for realtime voice I/O.

The processor keeps the microphone (near-end) and speaker (far-end) streams
separate and feeds matching frames to ``pywebrtc-audio``.  This is deliberately
full-duplex: microphone capture is never muted while the assistant is speaking.
"""

from __future__ import annotations

import importlib
import threading

from .lazy_import import lazy_module

np = lazy_module("numpy")

FRAME_BYTES = 480  # 10 ms of mono PCM16 at 24 kHz
_INTERNAL_RATE = 48_000


class EchoProcessor:
    def __init__(self, sample_rate: int = 24_000) -> None:
        del sample_rate  # 24 kHz is converted to the AEC3-supported 48 kHz.
        self._far_reference = bytearray()
        self._reference_lock = threading.Lock()
        self._capture_count = 0
        self._processed_count = 0
        self._bypass_count = 0
        self._reference_bytes = 0
        self._module = None
        try:
            mod = importlib.import_module("pywebrtc_audio")
            processor = getattr(mod, "AudioProcessor")
            self._module = processor(
                sample_rate=_INTERNAL_RATE,
                num_channels=1,
                echo_cancellation=True,
                noise_suppression=True,
                auto_gain_control=False,
                stream_delay_ms=40,
            )
        except Exception:
            # Optional backend: passthrough remains safe when the native binding
            # is unavailable. The caller reports that AEC is inactive.
            self._module = None

    @property
    def enabled(self) -> bool:
        return self._module is not None

    def reference(self, data: bytes) -> None:
        """Feed the PCM frame that was actually handed to the speaker."""
        with self._reference_lock:
            self._far_reference.extend(data)
            self._reference_bytes += len(data)
            # Do not let a delayed callback build an unbounded stale reference.
            max_reference = FRAME_BYTES * 50  # 500 ms
            if len(self._far_reference) > max_reference:
                del self._far_reference[:-max_reference]

    def clear_reference(self) -> None:
        """Drop stale reference when no speaker audio is being played."""
        with self._reference_lock:
            self._far_reference.clear()

    def capture(self, data: bytes) -> bytes:
        """Process one 10 ms near-end frame against its far-end reference."""
        self._capture_count += 1
        if self._module is None:
            self._bypass_count += 1
            return data

        near = np.frombuffer(data, dtype=np.int16)
        if near.size == 0:
            self._bypass_count += 1
            return data

        # Match the speaker reference to this capture frame. If playback has
        # not reached this point yet, do not invent a reference; passing the
        # near signal through is safer than cancelling the user's voice.
        with self._reference_lock:
            if len(self._far_reference) < len(data):
                self._bypass_count += 1
                return data
            far_bytes = bytes(self._far_reference[: len(data)])
            del self._far_reference[: len(data)]
        far = np.frombuffer(far_bytes, dtype=np.int16)

        near_48k = np.repeat(near, 2).astype(np.int16, copy=False)
        far_48k = np.repeat(far, 2).astype(np.int16, copy=False)
        processed = self._module.process(near_48k, far_48k)
        self._processed_count += 1
        # Return to the realtime transport's 24 kHz mono PCM format.
        return np.asarray(processed, dtype=np.int16)[::2].tobytes()

    def debug_snapshot(self) -> dict[str, int | bool]:
        with self._reference_lock:
            reference_buffer = len(self._far_reference)
        return {
            "enabled": self.enabled,
            "capture_frames": self._capture_count,
            "processed_frames": self._processed_count,
            "bypass_frames": self._bypass_count,
            "reference_bytes_total": self._reference_bytes,
            "reference_buffer_bytes": reference_buffer,
        }
