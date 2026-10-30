"""Bring a freshly reset Fieldy to a recordable state, the way the app does on connect.

Reads recording status/mode/recovery/mute, writes the current UTC time to 0x2A2B,
ACKs a pending recovery event. With --record SECONDS it also starts a recording
via ...66E7, waits, and stops it.
"""

import asyncio
import datetime as dt
import struct
import sys

from bleak import BleakClient, BleakScanner

BASE = "82a48422-3ca9-4156-ae67-4170f58666e{}"
MUTE, REC, MODE, RECOVERY = BASE.format(2), BASE.format(7), BASE.format(8), BASE.format("e")
TIME = "00002a2b-0000-1000-8000-00805f9b34fb"

STATES = ["STOPPED", "STARTING", "ACTIVE", "STOPPING", "ERROR", "ARMED"]
ERRORS = ["NONE", "TIME_NOT_SET", "STORAGE_FULL", "FILE_COUNT_LIMIT", "MUTED", "BUSY",
          "INVALID_REQUEST", "OTA_IN_PROGRESS", "COMMAND_MODE_ACTIVE", "FILE_ID_LIMIT"]


def rec_status(b: bytes) -> str:
    if len(b) < 11:
        return b.hex(" ")
    _, state, source, rid, stop, err, ts = struct.unpack_from("<BBBHBBI", b, 0)
    st = STATES[state] if state < len(STATES) else state
    er = ERRORS[err] if err < len(ERRORS) else err
    return f"state={st} source={source} recId={rid} stop={stop} error={er} ts={ts}"


async def read(c, uuid, label, fmt=lambda b: b.hex(" ")):
    try:
        b = bytes(await c.read_gatt_char(uuid))
        print(f"  {label}: {fmt(b)}")
        return b
    except Exception as e:
        print(f"  {label}: ERR {e}")
        return None


async def main(argv):
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "").startswith("Fieldy"), timeout=20.0
    )
    if dev is None:
        print("Fieldy not found")
        return 1
    async with BleakClient(dev, timeout=30.0) as c:
        print(f"connected to {dev.name}")
        await read(c, REC, "recording", rec_status)
        await read(c, MODE, "mode (0 manual, 1 auto)")
        await read(c, MUTE, "mute")
        rec = await read(c, RECOVERY, "recovery")
        await read(c, TIME, "device time")
        now = dt.datetime.now(dt.timezone.utc)
        payload = struct.pack(">HBBBBBB", now.year, now.month, now.day,
                              now.hour, now.minute, now.second, now.isoweekday())
        await c.write_gatt_char(TIME, payload, response=True)
        print(f"  wrote time {now:%Y-%m-%d %H:%M:%S}Z")
        if rec and len(rec) > 2 and rec[2] & 1:
            await c.write_gatt_char(RECOVERY, b"\x01", response=True)
            print("  acked recovery event")
        await read(c, TIME, "device time")
        await read(c, REC, "recording", rec_status)
        if "--record" in argv:
            secs = float(argv[argv.index("--record") + 1])
            await c.start_notify(REC, lambda _, d: print(f"  rec notify: {rec_status(bytes(d))}"))
            await c.write_gatt_char(REC, b"\x01", response=True)
            print(f"  start recording; {secs}s")
            await asyncio.sleep(secs)
            await c.write_gatt_char(REC, b"\x00", response=True)
            await asyncio.sleep(2)
            await read(c, REC, "recording", rec_status)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv)))
