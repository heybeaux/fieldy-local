"""Sync a Fieldy to this computer: set the clock, download stored recordings,
decode them, and transcribe them locally.

Usage:
  python tools/fieldy-sync.py [--out DIR] [--model REPO] [--no-transcribe]
  python tools/fieldy-sync.py --transcribe-only [--out DIR]

Output (default ~/Fieldy):
  DIR/raw/<fileStamp>.bin     exactly what the device sent, written as it arrives
  DIR/YYYY-MM-DD/HHMMSS_recN.opus   bare 40-byte Opus frames
  DIR/YYYY-MM-DD/HHMMSS_recN.wav    16 kHz mono
  DIR/YYYY-MM-DD/HHMMSS_recN.txt    transcript (local Whisper)

The device deletes a recording once it has sent it (firmware 3.3.5, transport
version 2), with or without an ACK. This tool therefore writes every packet to
disk before doing anything else with it. If a run is interrupted, the partial
raw file stays in DIR/raw/ with a .part suffix.
"""

import argparse
import asyncio
import ctypes.util
import datetime as dt
import os
import struct
import sys
import time
import wave
from pathlib import Path

from bleak import BleakClient, BleakScanner

BASE = "82a48422-3ca9-4156-ae67-4170f58666e{}"
NAND, REC, RECOVERY = BASE.format(1), BASE.format(7), BASE.format("e")
TIME = "00002a2b-0000-1000-8000-00805f9b34fb"

FRAME_BYTES = 40
SAMPLE_RATE = 16000
IDLE_TIMEOUT = 30.0


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# ---------- device ----------


async def find_device():
    return await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "").startswith("Fieldy"), timeout=20.0
    )


async def set_clock(client):
    now = dt.datetime.now(dt.timezone.utc)
    payload = struct.pack(">HBBBBBB", now.year, now.month, now.day,
                          now.hour, now.minute, now.second, now.isoweekday())
    await client.write_gatt_char(TIME, payload, response=True)
    log(f"clock set to {now:%Y-%m-%d %H:%M:%S} UTC")
    try:
        rec = bytes(await client.read_gatt_char(RECOVERY))
        if len(rec) > 2 and rec[2] & 1:
            await client.write_gatt_char(RECOVERY, b"\x01", response=True)
            log("acknowledged device reset report")
    except Exception as e:  # older firmware may not have it
        log(f"reset report not read: {e}")


def parse_status(b):
    if len(b) < 14 or b[:2] != b"*B":
        raise ValueError(f"unexpected storage status {b.hex(' ')}")
    files, size, synced, remaining = struct.unpack_from(">HIHI", b, 2)
    ver = b[19] if len(b) >= 20 and b[19] >= 1 else 1
    return files, size, remaining, ver


def cmd(op, payload=b"\x00" * 6):
    return b"*B" + op + payload + b"#"


class Download:
    """Collects one sync session, writing each packet to disk immediately."""

    def __init__(self, raw_dir: Path, ver: int):
        self.raw_dir = raw_dir
        self.ver = ver
        self.open = {}  # fileId -> (handle, path, bytes)
        self.finished = []  # (path, fileId, bytes)
        self.failed = asyncio.Queue()
        self.acks = asyncio.Queue()
        self.done = asyncio.Event()
        self.last_packet = time.monotonic()
        self.session = dt.datetime.now().strftime("%Y%m%dT%H%M%S")

    def _file(self, fid):
        if fid not in self.open:
            path = self.raw_dir / f"{self.session}_f{fid:05d}.bin.part"
            self.open[fid] = [open(path, "wb"), path, 0]
            log(f"receiving file {fid}")
        return self.open[fid]

    def _close(self, fid):
        handle, path, count = self.open.pop(fid)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        final = path.with_suffix("")  # drop .part
        path.rename(final)
        self.finished.append((final, fid, count))
        log(f"file {fid} complete: {count} bytes")
        if self.ver >= 3:
            self.acks.put_nowait((fid, count))

    def on_notify(self, _, data):
        b = bytes(data)
        self.last_packet = time.monotonic()
        if b in (b"*BENDOFREC", b"*BNOFILES#"):
            log("device: all files sent" if b == b"*BENDOFREC" else "device: no files")
            self.done.set()
            return
        if len(b) == 10 and b[:2] == b"*B" and b[8:10] == b"B#":
            log(f"device will send {struct.unpack_from('>H', b, 2)[0]} file(s)")
            return
        if len(b) == 16 and b[:3] == b"*BF" and b[15:16] == b"#":
            fid, size, offset = struct.unpack_from(">HII", b, 5)
            log(f"device reports file {fid} failed at {offset}/{size}")
            self.failed.put_nowait((fid, size))
            return
        if self.ver == 1:
            if len(b) < 247:
                log(f"short v1 packet ({len(b)} bytes) ignored")
                return
            fid = struct.unpack_from(">H", b, 0)[0]
            payload, eof = b[6:246], b[246] == 1
        else:
            if len(b) < 7:
                log(f"short packet ({len(b)} bytes) ignored")
                return
            fid, _idx, plen, flags = struct.unpack_from(">HHHB", b, 0)
            payload, eof = b[7 : 7 + plen], bool(flags & 1)
        entry = self._file(fid)
        entry[0].write(payload)
        entry[0].flush()
        entry[2] += len(payload)
        if eof:
            self._close(fid)

    def abort_partials(self):
        for fid in list(self.open):
            handle, path, count = self.open.pop(fid)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            log(f"file {fid} INCOMPLETE ({count} bytes kept in {path})")


async def download(out: Path):
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    dev = await find_device()
    if dev is None:
        log("Fieldy not found. Is it awake, and is the phone app disconnected?")
        return []
    async with BleakClient(dev, timeout=30.0) as client:
        log(f"connected to {dev.name}")
        await set_clock(client)
        files, size, remaining, ver = parse_status(bytes(await client.read_gatt_char(NAND)))
        log(f"device holds {files} file(s), {size} bytes; transport v{ver}")
        if files == 0 and remaining == 0:
            return []
        ver = min(3, ver)
        dl = Download(raw_dir, ver)
        await client.start_notify(NAND, dl.on_notify)
        await client.write_gatt_char(NAND, cmd(b"S", bytes([ver if ver > 1 else 0, 0, 0, 0, 0, 0])), response=True)
        retried = set()
        try:
            while not dl.done.is_set():
                if time.monotonic() - dl.last_packet > IDLE_TIMEOUT:
                    log("no data for 30 s; stopping")
                    break
                while not dl.acks.empty():
                    fid, count = dl.acks.get_nowait()
                    await client.write_gatt_char(NAND, cmd(b"A", struct.pack(">HI", fid, count)), response=True)
                while not dl.failed.empty():
                    fid, fsize = dl.failed.get_nowait()
                    op = b"D" if fid in retried else b"R"
                    retried.add(fid)
                    await client.write_gatt_char(NAND, cmd(op, struct.pack(">HI", fid, fsize)), response=True)
                await asyncio.sleep(0.2)
            while not dl.acks.empty():
                fid, count = dl.acks.get_nowait()
                await client.write_gatt_char(NAND, cmd(b"A", struct.pack(">HI", fid, count)), response=True)
        finally:
            dl.abort_partials()
            try:
                await client.stop_notify(NAND)
            except Exception:
                pass
        return dl.finished


# ---------- files ----------


def split_raw(data: bytes):
    """Return (recorded_at_utc or None, recording_id, opus_bytes)."""
    recorded, rec_id, body = None, 0, data
    if data[:2] == b"*S" and len(data) >= 10:
        y, mo, d, h, mi, s = struct.unpack_from(">HBBBBB", data, 2)
        recorded = dt.datetime(y, mo, d, h, mi, s, tzinfo=dt.timezone.utc)
        body = data[10:]
    elif data[:2] == b"*\x02" and len(data) >= 16:
        hlen = data[2]
        ts, rec_id = struct.unpack_from(">IH", data, 3)
        recorded = dt.datetime.fromtimestamp(ts, dt.timezone.utc) if ts else None
        body = data[hlen:]
    body = body.rstrip(b"\x00")
    if len(body) >= 10 and body[-10:-9] == b"*" and body[-9:-8] == b"E" and body[-1:] == b"#":
        body = body[:-10]
    body = body[: len(body) - len(body) % FRAME_BYTES]
    return recorded, rec_id, body


def load_opus():
    if ctypes.util.find_library("opus") is None:
        for cand in ("/opt/homebrew/lib/libopus.0.dylib", "/usr/local/lib/libopus.0.dylib"):
            if os.path.exists(cand):
                orig = ctypes.util.find_library
                ctypes.util.find_library = lambda name, _o=orig, _c=cand: _c if name == "opus" else _o(name)
                break
    import opuslib

    return opuslib


def to_wav(opus_bytes: bytes, dst: Path):
    opuslib = load_opus()
    dec = opuslib.Decoder(SAMPLE_RATE, 1)
    samples = SAMPLE_RATE * 20 // 1000
    pcm = bytearray()
    for off in range(0, len(opus_bytes), FRAME_BYTES):
        pcm.extend(dec.decode(opus_bytes[off : off + FRAME_BYTES], samples))
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(pcm))


def file_out(raw_path: Path, out: Path):
    data = raw_path.read_bytes()
    recorded, rec_id, body = split_raw(data)
    when = (recorded or dt.datetime.fromtimestamp(raw_path.stat().st_mtime, dt.timezone.utc)).astimezone()
    day = out / when.strftime("%Y-%m-%d")
    day.mkdir(parents=True, exist_ok=True)
    stem = day / f"{when:%H%M%S}_rec{rec_id}"
    stem.with_suffix(".opus").write_bytes(body)
    to_wav(body, stem.with_suffix(".wav"))
    log(f"{stem.name}: {len(body) // FRAME_BYTES * 0.02:.1f} s recorded {when:%Y-%m-%d %H:%M:%S}")
    return stem


def transcribe(stem: Path, model: str):
    import mlx_whisper

    result = mlx_whisper.transcribe(str(stem.with_suffix(".wav")), path_or_hf_repo=model)
    lines = []
    for seg in result.get("segments", []):
        m, s = divmod(int(seg["start"]), 60)
        lines.append(f"[{m:02d}:{s:02d}] {seg['text'].strip()}")
    text = "\n".join(lines) or result.get("text", "").strip()
    stem.with_suffix(".txt").write_text(text + "\n")
    log(f"transcribed {stem.name}")
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(Path.home() / "Fieldy"))
    ap.add_argument("--model", default="mlx-community/whisper-small.en-mlx")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--transcribe-only", action="store_true",
                    help="skip Bluetooth; transcribe any .wav without a .txt")
    args = ap.parse_args()
    out = Path(args.out).expanduser()

    stems = []
    if not args.transcribe_only:
        finished = asyncio.run(download(out))
        for raw_path, _fid, _count in finished:
            stems.append(file_out(raw_path, out))
    else:
        stems = [p.with_suffix("") for p in sorted(out.glob("*/*.wav"))
                 if not p.with_suffix(".txt").exists()]

    if args.no_transcribe or not stems:
        log(f"done: {len(stems)} recording(s) in {out}")
        return 0
    for stem in stems:
        text = transcribe(stem, args.model)
        print(text)
    log(f"done: {len(stems)} recording(s) in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
