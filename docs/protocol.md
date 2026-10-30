# Fieldy 3 Bluetooth LE protocol

Observed on firmware 3.3.5. Work in progress.

## Advertising

- Local name: `Fieldy` followed by two hex characters, for example `FieldyXX`.
- Advertised services: `4fafc201-1fb5-459e-8fcc-c5c9c331914b` and Battery
  Service (`0x180F`).
- Manufacturer data: company ID `0xFEFE` (unassigned), payload `03 03 05 43 00`.
  The first three bytes match firmware version 3.3.5. The meaning of `43 00` is
  not known yet (`0x43` is ASCII `C`, the hardware revision).

## Connection

- Most characteristics can be read without pairing. Offline storage
  (`...66E1`) and the recording manifest (`...66E6`) need an encrypted,
  bonded link. See "Connection security".
- Negotiated ATT MTU on macOS: 498.

## Services

### Custom service A: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`

The service UUID matches a widely copied ESP32 BLE example.

| Characteristic | Properties | Purpose |
|----------------|------------|---------|
| `82a48422-3ca9-4156-ae67-4170f58666e0` | read, notify | **Live audio.** See "Audio" below. |
| `82a48422-3ca9-4156-ae67-4170f58666e1` | read, write, notify | **Offline storage.** Status, sync commands, file data. Needs bonding. See "Offline storage". |
| `82a48422-3ca9-4156-ae67-4170f58666e2` | read, write | Mute. `01` muted, `00` unmuted. |
| `82a48422-3ca9-4156-ae67-4170f58666e3` | read, write | Always-on LED. `01` on, `00` off. |
| `82a48422-3ca9-4156-ae67-4170f58666e4` | notify | Button events. Byte 0: 1 single, 2 double, 3 short, 4 long. |
| `82a48422-3ca9-4156-ae67-4170f58666e6` | read, write, notify | Recording manifest (list of stored files). Needs bonding. |
| `82a48422-3ca9-4156-ae67-4170f58666e7` | read, write, notify | **Recording control.** Write `01` to start, `00` to stop. Notifies an 11-byte status record. |
| `82a48422-3ca9-4156-ae67-4170f58666e8` | read, write | Recording mode. `00` manual, `01` automatic. |

### Custom service B: `4fafc202-1fb5-459e-8fcc-c5c9c331914b`

| Characteristic | Properties | Purpose |
|----------------|------------|---------|
| `82a48422-3ca9-4156-ae67-4170f58666e5` | read | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e9` | read, write, notify | Device status. The app writes `01`, and the device notifies an 18-byte status record. |
| `82a48422-3ca9-4156-ae67-4170f58666ea` | read, write | Sleep. Write `01` to put the device to sleep. |
| `82a48422-3ca9-4156-ae67-4170f58666eb` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ec` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ed` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ee` | read, write | Reset/recovery report (10 bytes). Write `01` to acknowledge. |
| `82a48422-3ca9-4156-ae67-4170f58666ef` | write | Haptics. `01 04` buzzes the device (find my device). |

### Standard services

| Service | Characteristic | Notes |
|---------|----------------|-------|
| Battery (`0x180F`) | Battery Level `0x2A19` (read, notify) | Percent, uint8 |
| | Battery Level Status `0x2BED` (read, notify) | |
| | Voltage `0x2B18` (read) | uint16 little-endian, millivolts (observed 3872) |
| Current Time (`0x1805`) | Current Time `0x2A2B` (read, write) | Set by the app. Observed value is UTC. |
| Device Information (`0x180A`) | Model, Manufacturer, Serial, Firmware, Hardware, Software revision | Model `FL3B`, firmware `3.3.5`, hardware `C`, software `3` |
| Environmental Sensing (`0x181A`) | Temperature `0x2A6E` (read) | sint16 little-endian, 0.01 °C |
| SMP (`8d53dc1d-1db7-4cd3-868b-8a527460aa84`) | SMP `da2e7828-fbce-4e01-ae9e-261174997c48` | Zephyr MCUmgr. No authentication. |

## Audio

Confirmed from an iPhone HCI capture of the official app (firmware 3.3.5):

1. The app enables notifications on `...66E0` and `...66E7`.
2. The app writes `01` to `...66E7`.
3. The device notifies `...66E7` with a state record, then sends audio as
   notifications on `...66E0`.
4. The app writes `00` to `...66E7` to stop. The device notifies a final state
   record.

Audio format:

- Each `...66E0` notification is 240 bytes: six Opus frames of 40 bytes each.
- Every frame starts with TOC byte `0xB8`: CELT-only, wideband (16 kHz),
  20 ms, mono, one frame. 40 bytes per 20 ms is 16 kbit/s CBR.
- There is no extra framing, encryption, or sequence number in the payload.
- A 13-second test recording decoded cleanly (648 frames, 0 bad TOC bytes) and
  transcribed correctly with Whisper running locally.

`...66E7` state record (11 bytes), observed values:

```
01 01 01 0d 00 00 00 0a f0 e4 6a   after start
01 02 01 0d 00 00 00 0a f0 e4 6a   streaming
01 03 01 0d 00 01 00 17 f0 e4 6a   stopping
01 00 01 0d 00 01 00 17 f0 e4 6a   idle
```

- Byte 1 appears to be the stream state: 1 starting, 2 streaming, 3 stopping,
  0 idle.
- Bytes 7-10 read as a little-endian uint32 timestamp in seconds, in local time
  rather than UTC. It advanced by 13 s during the 13 s recording.
- The other bytes are not decoded yet.

A computer can do the same without the app: `tools/fieldy-stream.py` wrote
`01`, received 185 notifications (22.2 s of audio) over about 25 s, wrote `00`,
and the audio transcribed correctly. No pairing or bonding was needed.

Second observed state sequence (laptop session):

```
01 02 02 11 00 00 00 bd f2 e4 6a   before start (already 2)
01 03 02 11 00 01 00 d7 f2 e4 6a   stopping
01 00 02 11 00 01 00 d7 f2 e4 6a   idle
```

Byte 2 changed from `01` to `02` between sessions, and byte 3 from `0d` to
`11`. The timestamp advanced 26 s.

In the app capture the audio arrived at real-time speed while the recording was in
progress. Recordings made while no phone is connected are stored on the device
and downloaded separately. See "Offline storage".

### Recording status (`...66E7`, 11 bytes, little-endian)

```
0  version u8
1  state u8        0 stopped, 1 starting, 2 active, 3 stopping, 4 error, 5 armed
2  source u8       0 none, 1 phone, 2 button, 3 system
3  recordingId u16
5  stopReason u8   0 none, 1 manual, 2 timeout, 3 storage full, 4 file limit,
                   5 internal error, 6 realtime handoff, 7 silence,
                   8 low battery, 9 watchdog reset, 10 sleep mode
6  errorReason u8  0 none, 1 time not set, 2 storage full, 3 file count limit,
                   4 muted, 5 busy, 6 invalid request, 7 OTA in progress,
                   8 command mode active, 9 file ID limit
7  timestamp u32   seconds
```

## Clock

The device will not record until its clock is set. After a factory reset the
button gives two short vibrations, and `...66E7` reports state 4 (error) with
error 1 (time not set).

Set the time by writing 8 bytes to Current Time (`0x2A2B`), in UTC:

```
year u16 BIG-endian, month (1-12), day, hour, minute, second, weekday (Mon=1..Sun=7)
```

The year is big-endian, unlike the Bluetooth SIG Current Time format, and there
is no fractions or adjust-reason byte. The official app writes the time on
every connection and every 30 minutes. `tools/fieldy-setup.py` does this.

## Offline storage (`...66E1`)

Recordings are stored on the device's NAND flash. Reading or subscribing to
`...66E1` without a bonded, encrypted link fails with ATT error 0x0F
(insufficient encryption) or 0x05 (insufficient authentication).

All multi-byte fields in this section are big-endian.

### Status (read `...66E1`, 20 bytes)

```
0   '*' 'B'
2   totalFileCount u16
4   totalFileSize u32 (bytes)
8   syncedFileCount u16
10  remainingSyncSize u32 (bytes)
14  5 bytes, unknown
19  maxTransportVersion u8 (absent or 0 means 1)
```

Observed after a factory reset and one 30-second recording:
`2a 42 00 01 00 00 ec 0a 00 00 00 00 ec 0a 00 00 00 00 00 02`
(1 file, 60426 bytes, transport version 2).

### Commands (write `...66E1`, with response)

Every command is 10 bytes: `'*' 'B' <opcode> <6 payload bytes> '#'`.

| Opcode | Meaning | Payload |
|--------|---------|---------|
| `S` (0x53) | Start sync | `<version> 00 00 00 00 00`. Use `min(3, maxTransportVersion)`. Version 1 sends all zeros. |
| `A` (0x41) | File received (ACK) | fileId u16, byteCount u32 |
| `R` (0x52) | Retry file | fileId u16, byteCount u32 |
| `D` (0x44) | Drop file | fileId u16, byteCount u32 |

Enable notifications on `...66E1` before writing the start command.

### Notifications during a sync

- `*BNOFILES#` (10 ASCII bytes): nothing to send.
- `*BENDOFREC` (10 ASCII bytes): all files sent.
- Transfer header (10 bytes): `'*' 'B' fileCount u16 ... 'B' '#'`.
- File failed (16 bytes, version 3): `'*' 'B' 'F' flags u8, fsResult u8,
  fileId u16, fileSize u32, failureOffset u32, '#'`.
- Data packets:
  - Version 1: 247 bytes. `fileId u16, packetIndex u32, payload[240], eof u8`.
  - Version 2 and 3: `fileId u16, packetIndex u16, payloadLen u16, flags u8
    (bit 0 = end of file), payload[payloadLen]`.
  - Packet indexes start at 1 for each file.

### File layout

The payloads of one file, concatenated, are:

1. A file header.
   - Version 1 header (10 bytes): `'*' 'S' year u16, month, day, hour,
     minute, second, '#'`.
   - Version 2 header (at least 16 bytes): `'*' 0x02 headerLen u8,
     recordedAt u32 (UTC seconds), recordingId u16, ..., crc16 (2 bytes), '#'`.
     The CRC is CRC-16/XMODEM over the header with the CRC bytes set to zero.
2. Audio: bare 40-byte Opus frames, the same format as the live stream (TOC
   `0xB8`, 16 kHz mono, 20 ms). There is no Ogg container.
3. Possibly a 10-byte trailer `'*' 'E' ... '#'`, followed by zero padding in
   the last packet.

Tested on firmware 3.3.5 with transport version 2: a 30.2-second button
recording arrived as one file, 60400 bytes of audio (1510 frames), and
transcribed correctly with local Whisper.

### Deleting files

**A completed sync deletes the files from the device, even without an ACK.**
Tested on firmware 3.3.5 with transport version 2. A sync with no ACK
downloaded the file and ended with `*BENDOFREC`, and the next status read showed
0 files. A sync that sent the ACK (accepted, write status 0) left the device in
the same state. The official app sends ACKs only for transport version 3, which
this firmware does not offer.

Write every packet to disk as it arrives. `tools/fieldy-sync.py` does this.
It is not yet known whether an interrupted sync keeps the file.

A recording started from a computer (write `01` to `...66E7` without
subscribing to `...66E0`) is stored in offline storage, like a button
recording.

## Connection security

- The device asks the phone to bond (Just Works: Secure Connections, no MITM).
  There is no PIN or passkey.
- The device appears to keep a single bond. While it is bonded to a phone, a
  computer cannot bond with it, so it cannot read offline storage. After a factory
  reset (short click, then immediately press and hold the button for 10 s; the
  LED cycles through 4 colours), macOS bonded automatically on the first
  encrypted read, with no prompt.
- Without bonding, a nearby computer can still connect, read and write the
  other characteristics (including starting live audio on `...66E7`/`...66E0`),
  and use MCUmgr.
- MCUmgr (SMP) needs no authentication. It answers echo, task statistics,
  image state, and file-system status requests. The file-system group is
  enabled. Shell, settings, and group enumeration are not.

## Tools

- `tools/pklg_att.py` extracts ATT packets from an Apple PacketLogger trace.
- `tools/decode_e0.py` decodes concatenated `...66E0` payloads to a WAV file.
  It needs libopus and `pip install opuslib`.

## Next steps

- Test whether an interrupted sync keeps the file on the device.
- Test transport version 3 (needs newer firmware) and the recording manifest
  on `...66E6`.
- Decode the `...66E9` status record.
