# fieldy-local

Use your Fieldy wearable without the Field Labs cloud.

Fieldy is a wrist-worn AI note-taker. The device records audio and syncs it to
the Fieldy phone app over Bluetooth Low Energy. The app then uploads the audio to
Field Labs' servers for transcription and summaries. This project aims to keep
the device useful when those servers are not available, by pulling recordings
directly from the device and processing them on your own computer.

> **Status: research.** The live audio stream format is decoded (Opus, 16 kHz)
> and a recording captured from the official app has been transcribed locally.
> There is no standalone sync tool yet. Nothing in this repo writes to the device.

## Goals

1. Document the Fieldy 3 hardware and Bluetooth protocol.
2. Build a desktop tool that downloads recordings over Bluetooth without the
   official app or cloud.
3. Transcribe and summarize recordings locally (for example, with Whisper).
4. If the stock firmware cannot work without the cloud, evaluate open firmware.

## Supported hardware

| Model | Hardware rev | Firmware | Status |
|-------|--------------|----------|--------|
| FL3B (Fieldy 3, FCC ID 2BVUZI-FL3B) | C | 3.3.5 | Being mapped |

If you own a different model or firmware version, please open an issue with the
output of the tools below.

## Tools

The tools need Python 3.10+ and macOS, Linux, or Windows with Bluetooth LE.

```sh
python3 -m venv .venv
.venv/bin/pip install bleak smpclient
.venv/bin/python tools/fieldy-scan.py      # find nearby devices
.venv/bin/python tools/fieldy-gatt.py      # list Fieldy Bluetooth services
.venv/bin/python tools/fieldy-smp-info.py  # read firmware slot information
```

All three tools are read-only. `fieldy-gatt.py` reads only standard Bluetooth
characteristics (battery, device information, time). `fieldy-smp-info.py` sends
only MCUmgr read requests. Close the Fieldy phone app first if a connection
fails, because the device may accept only one connection at a time.

Their output includes your device serial number. Remove it before you post
output in a public issue.

## Findings

See [docs/hardware.md](docs/hardware.md) and [docs/protocol.md](docs/protocol.md).

## Security note

The Fieldy 3 accepts Bluetooth connections without pairing or bonding. Any
nearby computer can connect to it and read the information listed in
`docs/protocol.md`. We have not yet tested whether recordings can be read
without authentication.

## Legal

This project is an independent interoperability effort. It is not affiliated
with or endorsed by Field Labs Inc. "Fieldy" is a trademark of its owner. This
repo contains only original code and documentation. It does not contain Field
Labs firmware, app code, or decompiled source.

Only record conversations where you are allowed to. Recording consent laws vary
by location.

## License

MIT. See [LICENSE](LICENSE).
