# fieldy-local

Use your Fieldy wearable without the Field Labs cloud.

Fieldy is a wrist-worn AI note-taker. The device records audio and syncs it to
the Fieldy phone app over Bluetooth Low Energy. The app then uploads the audio to
Field Labs' servers for transcription and summaries. This project aims to keep
the device useful when those servers are not available, by pulling recordings
directly from the device and processing them on your own computer.

> **Status: early, working.** A computer with no phone app and no cloud can
> stream live audio from the device (`tools/fieldy-stream.py`) and download
> recordings stored on the device (`tools/fieldy-download.py`). Whisper then
> transcribes them locally. Deleting files from the device after download is not
> tested yet.

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

```sh
# Live audio: turn off Bluetooth on your phone first (one connection at a time).
.venv/bin/pip install opuslib mlx-whisper   # needs libopus (brew install opus)
.venv/bin/python tools/fieldy-stream.py my-clip 30
.venv/bin/python tools/decode_e0.py my-clip.bin my-clip.wav
.venv/bin/mlx_whisper my-clip.wav --model mlx-community/whisper-small.en-mlx
```

### Download stored recordings

Offline storage needs a bonded connection, and the device keeps only one bond.
If the Fieldy is paired with a phone, the computer cannot read storage. To move
it to your computer, factory reset the Fieldy: short-click the button (under 1
second), then immediately press and hold for 10 seconds until the LED cycles
through 4 colours. **A factory reset erases recordings on the device** and
unpairs it from your phone.

```sh
.venv/bin/python tools/fieldy-setup.py             # set the clock (required after a reset)
# record something with the button, then:
.venv/bin/python tools/fieldy-download.py status   # first encrypted read bonds the computer
.venv/bin/python tools/fieldy-download.py sync recordings
.venv/bin/python tools/decode_e0.py recordings/<file>.opus <file>.wav
.venv/bin/mlx_whisper <file>.wav --model mlx-community/whisper-small.en-mlx
```

If the button gives two short vibrations and does not record, the device clock
is not set. Run `fieldy-setup.py`. `fieldy-download.py` does not tell the device
to delete anything unless you pass `--ack`.

`fieldy-stream.py` writes `01` (start) and `00` (stop) to the recording-control
characteristic. `fieldy-setup.py` writes the current time and acknowledges the
device's reset report. The other three probe tools are read-only. `fieldy-gatt.py` reads only standard Bluetooth
characteristics (battery, device information, time). `fieldy-smp-info.py` sends
only MCUmgr read requests. Close the Fieldy phone app first if a connection
fails, because the device may accept only one connection at a time.

Their output includes your device serial number. Remove it before you post
output in a public issue.

## Findings

See [docs/hardware.md](docs/hardware.md) and [docs/protocol.md](docs/protocol.md).

## Security note

The Fieldy 3 accepts Bluetooth connections without pairing or bonding. Any
nearby computer can connect, read device information, and start live audio
streaming. Stored recordings need a bonded link, and a device already bonded to a
phone refused a new bond in our tests. The firmware update service (MCUmgr)
needs no authentication. See `docs/protocol.md`.

## Legal

This project is an independent interoperability effort. It is not affiliated
with or endorsed by Field Labs Inc. "Fieldy" is a trademark of its owner. This
repo contains only original code and documentation. It does not contain Field
Labs firmware, app code, or decompiled source.

Only record conversations where you are allowed to. Recording consent laws vary
by location.

## License

MIT. See [LICENSE](LICENSE).
