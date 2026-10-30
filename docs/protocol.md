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
| `82a48422-3ca9-4156-ae67-4170f58666e0` | read, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e1` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e2` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e3` | read, write | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e4` | notify | Unknown (candidate audio/data stream) |
| `82a48422-3ca9-4156-ae67-4170f58666e6` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e7` | read, write, notify | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e8` | read, write | Unknown |

### Custom service B: `4fafc202-1fb5-459e-8fcc-c5c9c331914b`

| Characteristic | Properties | Purpose |
|----------------|------------|---------|
| `82a48422-3ca9-4156-ae67-4170f58666e5` | read | Unknown |
| `82a48422-3ca9-4156-ae67-4170f58666e9` | read, write, notify | Unknown |
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

## Next steps

- Capture a sync between the official app and the device.
- Map commands and the recording transfer format.
- Identify the audio codec (Opus is common on Zephyr/nRF wearables).
