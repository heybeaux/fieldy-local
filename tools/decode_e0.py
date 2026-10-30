"""Decode Fieldy audio notifications (char ...66E0) into a 16 kHz mono WAV.

Each notification observed so far is 240 bytes: six 40-byte Opus CELT frames
(TOC 0xB8: wideband, 20 ms, mono, one frame per packet).
"""

import ctypes.util
import os
import sys
import wave

os.environ.setdefault("DYLD_LIBRARY_PATH", "/opt/homebrew/lib")
if ctypes.util.find_library("opus") is None:
    ctypes.util.find_library = lambda name, _orig=ctypes.util.find_library: (
        "/opt/homebrew/lib/libopus.0.dylib" if name == "opus" else _orig(name)
    )

import opuslib  # noqa: E402

FRAME_BYTES = 40
SAMPLE_RATE = 16000
FRAME_SAMPLES = SAMPLE_RATE * 20 // 1000


def main(src, dst):
    raw = open(src, "rb").read()
    dec = opuslib.Decoder(SAMPLE_RATE, 1)
    pcm = bytearray()
    bad = 0
    for off in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES):
        frame = raw[off : off + FRAME_BYTES]
        if frame[0] != 0xB8:
            bad += 1
        pcm.extend(dec.decode(frame, FRAME_SAMPLES))
    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(pcm))
    frames = len(raw) // FRAME_BYTES
    print(f"frames={frames} unexpected_toc={bad} seconds={frames * 0.02:.2f} -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
