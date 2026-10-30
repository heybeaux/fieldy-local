"""Extract ATT packets from an Apple PacketLogger (.pklg) trace.

Usage: python pklg_att.py TRACE.pklg [--handle 0x0012] [--dump-dir DIR]
Prints one line per ATT PDU: time, direction, opcode, handle, length, hex.
"""

import argparse
import os
import struct
import sys

ATT_CID = 0x0004
PKLG_ACL_SEND = 0x02
PKLG_ACL_RECV = 0x03


def iter_records(data):
    off = 0
    # Apple pklg: big-endian length (excludes itself), 8-byte timestamp, 1-byte type.
    # Newer traces use little-endian; detect from the first record.
    le = struct.unpack_from("<I", data, 0)[0] < struct.unpack_from(">I", data, 0)[0]
    fmt = "<I" if le else ">I"
    while off + 13 <= len(data):
        (length,) = struct.unpack_from(fmt, data, off)
        if length < 9 or off + 4 + length > len(data):
            break
        ts_raw = data[off + 4 : off + 12]
        ptype = data[off + 12]
        payload = data[off + 13 : off + 4 + length]
        if le:
            secs, usecs = struct.unpack("<II", ts_raw)
        else:
            secs, usecs = struct.unpack(">II", ts_raw)
        yield secs + usecs / 1e6, ptype, payload
        off += 4 + length


def iter_att(path):
    data = open(path, "rb").read()
    partial = {}  # (direction, handle) -> (ts, expected_len, bytearray)
    for ts, ptype, payload in iter_records(data):
        if ptype not in (PKLG_ACL_SEND, PKLG_ACL_RECV) or len(payload) < 4:
            continue
        direction = "SEND" if ptype == PKLG_ACL_SEND else "RECV"
        hdr, acl_len = struct.unpack_from("<HH", payload, 0)
        conn = hdr & 0x0FFF
        pb = (hdr >> 12) & 0x3
        body = payload[4 : 4 + acl_len]
        key = (direction, conn)
        if pb in (0x0, 0x2):  # first fragment
            if len(body) < 4:
                continue
            l2_len, cid = struct.unpack_from("<HH", body, 0)
            buf = bytearray(body[4:])
            if len(buf) < l2_len:
                partial[key] = (ts, l2_len, cid, buf)
                continue
            if cid == ATT_CID:
                yield ts, direction, conn, bytes(buf[:l2_len])
        elif pb == 0x1 and key in partial:  # continuation
            t0, l2_len, cid, buf = partial[key]
            buf.extend(body)
            if len(buf) >= l2_len:
                del partial[key]
                if cid == ATT_CID:
                    yield t0, direction, conn, bytes(buf[:l2_len])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--handle", type=lambda s: int(s, 0))
    ap.add_argument("--raw-out", help="write concatenated notification payloads for --handle here")
    ap.add_argument("--lengths-out", help="write one payload length per line for --handle here")
    args = ap.parse_args()

    raw = open(args.raw_out, "wb") if args.raw_out else None
    lens = open(args.lengths_out, "w") if args.lengths_out else None
    for ts, direction, conn, pdu in iter_att(args.trace):
        op = pdu[0]
        handle = struct.unpack_from("<H", pdu, 1)[0] if op in (0x12, 0x52, 0x1B, 0x1D, 0x0A, 0x16) and len(pdu) >= 3 else None
        if args.handle is not None and handle != args.handle:
            continue
        value = pdu[3:] if handle is not None else pdu[1:]
        print(f"{ts:.3f} {direction} conn=0x{conn:03x} op=0x{op:02x} handle={handle and f'0x{handle:04x}'} len={len(value)} {value.hex()}")
        if raw is not None and op == 0x1B:
            raw.write(value)
        if lens is not None and op == 0x1B:
            lens.write(f"{len(value)}\n")


if __name__ == "__main__":
    sys.exit(main())
