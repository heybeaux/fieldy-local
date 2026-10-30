"""Stream live audio from a Fieldy to a WAV file, without the official app.

Writes 01 to the stream-control characteristic (...66E7), collects Opus frames
from ...66E0, then writes 00 to stop.

Usage: python fieldy-stream.py OUT_PREFIX [SECONDS]
"""

import asyncio
import sys
import time

from bleak import BleakClient, BleakScanner

AUDIO = "82a48422-3ca9-4156-ae67-4170f58666e0"
CONTROL = "82a48422-3ca9-4156-ae67-4170f58666e7"


async def main(prefix, seconds):
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "").startswith("Fieldy"), timeout=20.0
    )
    if dev is None:
        print("Fieldy not found (is the phone app holding the connection?)")
        return 1
    audio = bytearray()
    packets = 0
    t0 = time.monotonic()

    def on_audio(_, data: bytearray):
        nonlocal packets
        packets += 1
        audio.extend(data)

    def on_control(_, data: bytearray):
        print(f"{time.monotonic() - t0:6.2f}s control notify: {data.hex(' ')}")

    async with BleakClient(dev, timeout=30.0) as client:
        print(f"connected to {dev.name}")
        await client.start_notify(CONTROL, on_control)
        await client.start_notify(AUDIO, on_audio)
        state = await client.read_gatt_char(CONTROL)
        print(f"control before: {state.hex(' ')}")
        await client.write_gatt_char(CONTROL, b"\x01", response=True)
        print(f"started; streaming {seconds}s")
        await asyncio.sleep(seconds)
        await client.write_gatt_char(CONTROL, b"\x00", response=True)
        await asyncio.sleep(1.0)
        state = await client.read_gatt_char(CONTROL)
        print(f"control after: {state.hex(' ')}")
    open(f"{prefix}.bin", "wb").write(audio)
    print(f"packets={packets} bytes={len(audio)} -> {prefix}.bin")
    return 0


if __name__ == "__main__":
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    sys.exit(asyncio.run(main(sys.argv[1], secs)))
