import asyncio
from bleak import BleakClient, BleakScanner

STANDARD_PREFIX = "0000"
STANDARD_SUFFIX = "-0000-1000-8000-00805f9b34fb"


def is_standard(uuid: str) -> bool:
    return uuid.startswith(STANDARD_PREFIX) and uuid.endswith(STANDARD_SUFFIX)


async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "").startswith("Fieldy"), timeout=15.0
    )
    if dev is None:
        print("Fieldy not found")
        return
    print(f"connecting to {dev.address} ({dev.name})")
    async with BleakClient(dev, timeout=20.0) as client:
        print(f"connected, mtu={client.mtu_size}")
        for svc in client.services:
            print(f"\nSERVICE {svc.uuid}  {svc.description}")
            for ch in svc.characteristics:
                value = ""
                # Only read standard SIG characteristics; custom ones may have side effects.
                if "read" in ch.properties and is_standard(ch.uuid):
                    try:
                        raw = await client.read_gatt_char(ch)
                        value = f"  value={raw!r}"
                    except Exception as e:
                        value = f"  read-error={e}"
                print(f"  CHAR {ch.uuid}  props={ch.properties}  {ch.description}{value}")
                for d in ch.descriptors:
                    print(f"    DESC {d.uuid}  {d.description}")


asyncio.run(main())
