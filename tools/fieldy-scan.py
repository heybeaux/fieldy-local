import asyncio
from bleak import BleakScanner


async def main():
    found = await BleakScanner.discover(timeout=12.0, return_adv=True)
    for addr, (dev, adv) in sorted(found.items(), key=lambda kv: -kv[1][1].rssi):
        print(
            f"{addr}  rssi={adv.rssi}  name={adv.local_name or dev.name!r}  "
            f"uuids={adv.service_uuids}  mfr={ {k: v.hex() for k, v in adv.manufacturer_data.items()} }  "
            f"svcdata={ {k: v.hex() for k, v in adv.service_data.items()} }"
        )


asyncio.run(main())
