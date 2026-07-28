"""Optional WebRTC audio processing for realtime mode.

The dependency is optional so normal CLI, TTS, and STT behavior is unchanged.
"""
from __future__ import annotations

import importlib

import numpy as np

FRAME_BYTES = 480  # 10 ms of mono PCM16 at 24 kHz
_INTERNAL_RATE = 48_000


class EchoProcessor:
    def __init__(self, sample_rate: int = 24_000) -> None:
        self._reverse = bytearray()
        self._reverse_seen = False
        self._module = None
        try:
            mod = importlib.import_module("webrtc_audio_processing")
            ap_cls = getattr(mod, "AudioProcessingModule")
            # Use the processing features provided by WebRTC: AEC, noise
            # suppression, and the digital AGC path. VAD is not needed here.
            # The bundled binding's aec_type=3 branch is a no-op (the legacy
            # EchoCanceller3 setup is commented out). Use the implemented
            # WebRTC AEC path instead of reporting a false-positive AEC state.
            self._module = ap_cls(aec_type=2, enable_ns=True, agc_type=1, enable_vad=False)
            self._module.set_aec_level(1)
            self._module.set_ns_level(1)
            self._module.set_agc_level(1)
            # WebRTC APM commonly supports 8/16/32/48 kHz, not 24 kHz.
            # Realtime remains at 24 kHz externally; convert frames at the edge.
            # Specify output format explicitly: the binding defaults output to
            # 16 kHz, which would make process_stream read/write the wrong
            # number of samples and can generate spurious audio.
            self._module.set_stream_format(_INTERNAL_RATE, 1, _INTERNAL_RATE, 1)
            self._module.set_reverse_stream_format(_INTERNAL_RATE, 1)
        except Exception:
            # Optional backend: passthrough remains safe when the native binding
            # is unavailable. The caller can report that AEC is not active.
            self._module = None

    @property
    def enabled(self) -> bool:
        return self._module is not None

    def reverse(self, data: bytes) -> list[bytes]:
        """Feed far-end speaker reference and return processed output frames."""
        self._reverse_seen = True
        self._reverse.extend(data)
        result: list[bytes] = []
        while len(self._reverse) >= FRAME_BYTES:
            frame = bytes(self._reverse[:FRAME_BYTES])
            del self._reverse[:FRAME_BYTES]
            if self._module is not None:
                samples = np.frombuffer(frame, dtype=np.int16)
                internal = np.repeat(samples, 2).astype(np.int16, copy=False).tobytes()
                self._module.process_reverse_stream(internal)
            result.append(frame)
        return result

    def capture(self, data: bytes) -> bytes:
        # The legacy AEC2 implementation aggressively suppresses near-end
        # audio until it has received a far-end reference. Preserve the first
        # user turn (before the assistant has spoken) instead of turning it
        # into silence.
        if self._module is None or not self._reverse_seen:
            return data
        samples = np.frombuffer(data, dtype=np.int16)
        internal = np.repeat(samples, 2).astype(np.int16, copy=False).tobytes()
        processed = self._module.process_stream(internal)
        output = np.frombuffer(processed, dtype=np.int16)[::2]
        return output.astype(np.int16, copy=False).tobytes()
