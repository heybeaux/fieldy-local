"""Read a Fieldy's offline-storage (NAND) status and, optionally, pull its files.

Usage:
  python tools/fieldy-download.py status
  python tools/fieldy-download.py sync OUT_DIR [--ack]

`sync` sends SYNC_START on ...66E1 and saves each file's raw Opus payload.
Note: on firmware 3.3.5 (transport v2) a completed sync deletes the files
from the device whether or not --ack is passed.
"""

import asyncio
import os
import struct
import sys
import time

from bleak import BleakClient, BleakScanner

NAND = "82a48422-3ca9-4156-ae67-4170f58666e1"
CONTROL = "82a48422-3ca9-4156-ae67-4170f58666e7"


def parse_status(b: bytes) -> dict:
    if len(b) < 14 or b[0:2] != b"*B":
        return {"raw": b.hex(" ")}
    total_files, total_size, synced, remaining = struct.unpack_from(">HIHI", b, 2)
    ver = b[19] if len(b) >= 20 and b[19] >= 1 else 1
    return {
        "totalFileCount": total_files,
        "totalFileSize": total_size,
        "syncedFileCount": synced,
        "remainingSyncSize": remaining,
        "maxTransportVersion": ver,
        "raw": b.hex(" "),
    }


def frame(op: bytes, payload: bytes = b"\x00" * 6) -> bytes:
    return b"*B" + op + payload + b"#"


async def find():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "").startswith("Fieldy"), timeout=20.0
    )
    if dev is None:
        print("Fieldy not found (is the phone still connected to it?)")
    return dev


async def status(client):
    raw = bytes(await client.read_gatt_char(NAND))
    st = parse_status(raw)
    for k, v in st.items():
        print(f"  {k}: {v}")
    return st


def strip_header(payload: bytes):
    if payload[:2] == b"*S" and len(payload) >= 10:
        y, mo, d, h, mi, s = struct.unpack_from(">HBBBBB", payload, 2)
        return payload[10:], f"{y:04d}{mo:02d}{d:02d}T{h:02d}{mi:02d}{s:02d}", 0
    if payload[:2] == b"*\x02" and len(payload) >= 16:
        hlen = payload[2]
        ts, rec_id = struct.unpack_from(">IH", payload, 3)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(ts))
        return payload[hlen:], stamp, rec_id
    return payload, "unknown", 0


def strip_tail(data: bytes) -> bytes:
    data = data.rstrip(b"\x00")
    if len(data) >= 10 and data[-10] == ord("*") and data[-9] == ord("E") and data[-1] == ord("#"):
        data = data[:-10]
    return data


async def sync(client, out_dir, ack, ver):
    os.makedirs(out_dir, exist_ok=True)
    done = asyncio.Event()
    files = {}  # fileId -> dict(buf, rx, stamp, rec)
    saved = []
    acks = asyncio.Queue()

    def finish(fid):
        f = files.pop(fid)
        data = strip_tail(bytes(f["buf"]))
        path = os.path.join(out_dir, f"{f['stamp']}_{fid:06d}_offline.opus")
        open(path, "wb").write(data)
        saved.append(path)
        print(f"  saved file {fid}: {len(data)} bytes -> {path}")
        acks.put_nowait((fid, f["rx"]))

    def on_nand(_, data: bytearray):
        b = bytes(data)
        if b in (b"*BENDOFREC", b"*BNOFILES#"):
            print(f"  device: {b.decode()}")
            done.set()
            return
        if len(b) == 10 and b[:2] == b"*B" and b[8:10] == b"B#":
            print(f"  transfer header: files={struct.unpack_from('>H', b, 2)[0]}")
            return
        if len(b) == 16 and b[:3] == b"*BF" and b[15:16] == b"#":
            print(f"  FILE_FAILED: {b.hex(' ')}")
            return
        if ver == 1:
            if len(b) < 247:
                print(f"  ? {len(b)}B {b[:16].hex(' ')}")
                return
            fid, idx = struct.unpack_from(">HI", b, 0)
            payload, eof = b[6:246], b[246] == 1
        else:
            if len(b) < 7:
                print(f"  ? {len(b)}B {b.hex(' ')}")
                return
            fid, idx, plen, flags = struct.unpack_from(">HHHB", b, 0)
            payload, eof = b[7 : 7 + plen], bool(flags & 1)
        f = files.get(fid)
        if f is None:
            payload, stamp, rec = strip_header(payload)
            f = files[fid] = {"buf": bytearray(), "rx": 0, "stamp": stamp, "rec": rec}
            print(f"  file {fid} started (recorded {stamp}, recId {rec})")
        f["buf"].extend(payload)
        f["rx"] += plen if ver != 1 else 240
        if eof:
            finish(fid)

    await client.start_notify(NAND, on_nand)
    cmd = frame(b"S", bytes([ver if ver > 1 else 0, 0, 0, 0, 0, 0]))
    print(f"  SYNC_START {cmd.hex(' ')}")
    await client.write_gatt_char(NAND, cmd, response=True)
    deadline = time.monotonic() + 600
    while not done.is_set() and time.monotonic() < deadline:
        try:
            fid, rx = await asyncio.wait_for(acks.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue
        if ack:
            await client.write_gatt_char(
                NAND, frame(b"A", struct.pack(">HI", fid, rx)), response=True
            )
            print(f"  ACK file {fid} ({rx} bytes)")
        else:
            print(f"  (no ACK sent for file {fid})")
    for fid in list(files):
        print(f"  file {fid} incomplete; saving partial")
        finish(fid)
    await client.stop_notify(NAND)
    return saved


async def main(argv):
    mode = argv[1] if len(argv) > 1 else "status"
    dev = await find()
    if dev is None:
        return 1
    async with BleakClient(dev, timeout=30.0) as client:
        print(f"connected to {dev.name}")
        st = await status(client)
        if mode == "sync":
            ver = min(3, st.get("maxTransportVersion", 1))
            saved = await sync(client, argv[2], "--ack" in argv, ver)
            print(f"saved {len(saved)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv)))
