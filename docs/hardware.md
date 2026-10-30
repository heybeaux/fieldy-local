# Fieldy 3 hardware notes

Observed on one FL3B unit, hardware revision C, firmware 3.3.5.

## Identity

| Field | Value | Source |
|-------|-------|--------|
| Model | FL3B | BLE Device Information, Model Number |
| Manufacturer | Field Labs | BLE Device Information |
| Hardware revision | C | BLE Device Information, boot log |
| Firmware | 3.3.5 | BLE Device Information, boot log, MCUmgr |
| FCC ID | 2BVUZI-FL3B | Device label |

## System

- **RTOS:** Zephyr OS v4.1.0 (boot banner).
- **SoC:** probably Nordic nRF5340. Not confirmed. The boot log names a
  `flash-controller@39000`, which matches the nRF5340 application core NVMC
  address. Omi, an open-source AI wearable, uses the same SoC and RTOS.
- **Bootloader:** MCUboot with two image slots (see below). Firmware updates
  use MCUmgr over BLE.
- **Recording storage:** NAND flash, JEDEC ID `2C 15` (Micron).
- **Internal file system:** LittleFS on internal MCU flash at offset `0xe8000`,
  size 24576 bytes (6 blocks of 4 KiB), mounted at `/lfs1`.
- **Power management:** Analog Devices ADP5360 PMIC and battery charger.

## USB

The charging port enumerates as a USB full-speed (12 Mb/s) CDC-ACM serial
device:

- Vendor ID `0xcafe`, product ID `0x0100`, product string `Fieldy`. `0xcafe` is
  the TinyUSB example vendor ID.
- The serial port carries the Zephyr log output only. It did not respond to a
  carriage return or `help`, so no shell is exposed.
- 115200 baud works. CDC-ACM ignores the baud rate.

Example boot log (abridged):

```
*** Booting Zephyr OS build v4.1.0 ***
I: Firmware version: 3.3.5 HW: C
I: Mounting internal MCU flash LittleFS partition at /lfs1 (offset=0xe8000 size=24576).
I: LittleFS version 2.10, disk version 2.1
D: initializeDFU: Jul 29 2026 17:42:08
D: Starting device setup...
D: Initialize Watchdog
I: Restored time from RAM: ...
I: Watchdog-like reset detected; recording recovery will be evaluated.
I: NAND Device ID: [2C 15]
I: ADP5360: int1=0x02 int2=0x00 chg1=0x22 chg2=0xe4 fault=0x00 pgood=0x0f
```

## Firmware image slots (MCUmgr)

| Slot | Version | Bootable | Confirmed | Active |
|------|---------|----------|-----------|--------|
| 0 | 3.3.5 | yes | yes | yes |
| 1 | 3.3.4 | yes | no | no |

- MCUmgr parameters: `buf_size` 2475, `buf_count` 4.
- `BootloaderInformationRead` and `OSApplicationInfoRead` return `ENOTSUP`.

## Open questions

- Confirm the SoC from the FCC internal photos.
- Locate SWD debug pads.
- Determine whether MCUboot verifies image signatures and with which key.
