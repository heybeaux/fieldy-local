"""Read-only MCUmgr (SMP) queries against a Fieldy. Sends no write/upload/reset/erase commands."""

import asyncio

from bleak import BleakScanner
from smpclient import SMPClient
from smpclient.requests.image_management import ImageStatesRead
from smpclient.requests.os_management import (
    BootloaderInformationRead,
    MCUMgrParametersRead,
    OSApplicationInfoRead,
)
from smpclient.transport.ble import SMPBLETransport

READ_ONLY_REQUESTS = [
    ImageStatesRead(),
    MCUMgrParametersRead(),
    BootloaderInformationRead(),
    OSApplicationInfoRead(format="a"),
]


async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: (a.local_name or "").startswith("Fieldy"), timeout=15.0
    )
    if dev is None:
        print("Fieldy not found")
        return
    client = SMPClient(SMPBLETransport(), dev.address)
    await client.connect(30.0)
    try:
        for req in READ_ONLY_REQUESTS:
            try:
                resp = await client.request(req, timeout_s=10.0)
                print(f"{type(req).__name__}: {resp}")
            except Exception as e:
                print(f"{type(req).__name__}: ERROR {type(e).__name__}: {e}")
    finally:
        await client.disconnect()


asyncio.run(main())
