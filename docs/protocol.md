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

- No pairing or bonding is required.
- Negotiated ATT MTU on macOS: 498.

## Services

### Custom service A: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`

The service UUID matches a widely copied ESP32 BLE example.

| Characteristic | Properties | Purpose |
|----------------|------------|---------|
| `82a48422-3ca9-4156-ae67-4170f58666e0` | read, notify | **Audio stream.** See "Audio" below. |
| `82a48422-3ca9-4156-ae67-4170f58666e1` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e2` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e3` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e4` | notify | Unknown (candidate audio/data stream) |
| `82a48422-3ca9-4156-ae67-4170f58666e6` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e7` | read, write, notify | **Audio stream control.** Write `01` to start, `00` to stop. Notifies state. |
| `82a48422-3ca9-4156-ae67-4170f58666e8` | read, write | Unknown |

### Custom service B: `4fafc202-1fb5-459e-8fcc-c5c9c331914b`

| Characteristic | Properties | Purpose |
|----------------|------------|---------|
| `82a48422-3ca9-4156-ae67-4170f58666e5` | read | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e9` | read, write, notify | Device status. The app writes `01`, and the device notifies an 18-byte status record. |
| `82a48422-3ca9-4156-ae67-4170f58666ea` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666eb` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ec` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ed` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ee` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666ef` | write | Unknown |

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
progress. It is not yet known how the app transfers recordings that were made
while the phone was out of range.

## Connection security

The device sends an SMP Security Request (bonding, Secure Connections, no MITM)
to the phone, and the iPhone reconnects with stored keys. A computer that does
not bond can still connect and read every characteristic listed here.

## Tools

- `tools/pklg_att.py` extracts ATT packets from an Apple PacketLogger trace.
- `tools/decode_e0.py` decodes concatenated `...66E0` payloads to a WAV file.
  It needs libopus and `pip install opuslib`.

## Next steps

- Capture a sync of recordings made while the phone was out of range.
- Map commands and the recording transfer format.
- Decode the `...66E9` status record.
