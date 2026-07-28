"""WebRTC AEC3 processing for realtime voice I/O.

The processor keeps the microphone (near-end) and speaker (far-end) streams
separate and feeds matching frames to ``pywebrtc-audio``.  This is deliberately
full-duplex: microphone capture is never muted while the assistant is speaking.
"""
from __future__ import annotations

import importlib

import numpy as np

FRAME_BYTES = 480  # 10 ms of mono PCM16 at 24 kHz
_INTERNAL_RATE = 48_000


class EchoProcessor:
    def __init__(self, sample_rate: int = 24_000) -> None:
        del sample_rate  # 24 kHz is converted to the AEC3-supported 48 kHz.
        self._far_reference = bytearray()
        self._playback_buffer = bytearray()
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

    def reverse(self, data: bytes) -> list[bytes]:
        """Queue the exact far-end PCM that is sent to the speaker."""
        self._far_reference.extend(data)
        self._playback_buffer.extend(data)
        result: list[bytes] = []
        while len(self._playback_buffer) >= FRAME_BYTES:
            frame = bytes(self._playback_buffer[:FRAME_BYTES])
            del self._playback_buffer[:FRAME_BYTES]
            result.append(frame)
        return result

    def capture(self, data: bytes) -> bytes:
        """Process one 10 ms near-end frame against its far-end reference."""
        if self._module is None:
            return data

        near = np.frombuffer(data, dtype=np.int16)
        if near.size == 0:
            return data

        # Match the speaker reference to this capture frame. If playback has
        # not reached this point yet, do not invent a reference; passing the
        # near signal through is safer than cancelling the user's voice.
        if len(self._far_reference) >= len(data):
            far_bytes = bytes(self._far_reference[: len(data)])
            del self._far_reference[: len(data)]
            far = np.frombuffer(far_bytes, dtype=np.int16)
        else:
            return data

        near_48k = np.repeat(near, 2).astype(np.int16, copy=False)
        far_48k = np.repeat(far, 2).astype(np.int16, copy=False)
        processed = self._module.process(near_48k, far_48k)
        # Return to the realtime transport's 24 kHz mono PCM format.
        return np.asarray(processed, dtype=np.int16)[::2].tobytes()
