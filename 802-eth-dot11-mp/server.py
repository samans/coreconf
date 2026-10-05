#!/usr/bin/env python3
"""
CORECONF server for the Wi-Fi access point (leaf of the management chain).

Topology:

    [mgmt station] --NETCONF--> [switch] --NETCONF--> [wifi-ap]
                                                --CORECONF--> [device]

This process plays the AP's CoAP (CORECONF) datastore at /c, which holds the
wifi-ap container and its keyed list of associated devices. The upstream
NETCONF hops (station->switch->ap) are modeled/animated by the client side;
on the wire the real transport here is CoAP + CBOR + numeric SIDs.

  * GET   /c   -> full datastore: wifi-ap container (CBOR map), with the
                  device list encoded as a CBOR array of per-device maps.
  * FETCH /c   -> selected instance-values (whole subtree for this demo).
  * iPATCH /c  -> merge/replace/delete. Used to set wifi-ap leaves and to
                  add/update/remove device entries.

Run:
    python3 server.py            # NoSec (plain CoAP) on udp/5683
"""

import asyncio
import logging
import random

import cbor2
from aiocoap import resource, Message, Code, Context

from wifi_sids import (
    SID_WIFI_AP, SID_AP_NAME, SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL,
    SID_TX_POWER, SID_LATENCY, SID_STATE,
    SID_DEVICE, SID_MAC, SID_HOSTNAME, SID_IP_ADDRESS, SID_SIGNAL_DBM,
    SID_CONNECTED,
    SID_DOWN, SID_SCANNING, SID_ACTIVE,
    BAND_TO_INT, INT_TO_BAND,
    CF_YANG_DATA_CBOR, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH, decode_cbor_seq,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-ap-server")

# writable wifi-ap leaf SIDs that may appear in an iPATCH
AP_WRITABLE = {SID_AP_NAME, SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL,
               SID_TX_POWER, SID_LATENCY}
# writable device leaf SIDs
DEV_WRITABLE = {SID_HOSTNAME, SID_IP_ADDRESS, SID_SIGNAL_DBM, SID_CONNECTED}


class Device:
    """In-memory state for one associated client station (list entry)."""

    def __init__(self, mac):
        self.mac = mac
        self.hostname = ""
        self.ip_address = ""
        self.signal_dbm = -60
        self.connected = True

    def to_map(self):
        return {
            SID_MAC: self.mac,
            SID_HOSTNAME: self.hostname,
            SID_IP_ADDRESS: self.ip_address,
            SID_SIGNAL_DBM: self.signal_dbm,
            SID_CONNECTED: self.connected,
        }

    def apply_leaf(self, sid, value):
        if sid == SID_HOSTNAME:
            if not (isinstance(value, str) and len(value) <= 64):
                return "invalid-value: hostname must be 0..64 chars"
            self.hostname = value
        elif sid == SID_IP_ADDRESS:
            if not (isinstance(value, str) and len(value) <= 45):
                return "invalid-value: ip-address must be 0..45 chars"
            self.ip_address = value
        elif sid == SID_SIGNAL_DBM:
            if not (isinstance(value, int) and -120 <= value <= 0):
                return "not-in-range: signal-dbm must be -120..0"
            self.signal_dbm = value
        elif sid == SID_CONNECTED:
            if not isinstance(value, bool):
                return "invalid-value: connected must be boolean"
            self.connected = value
        else:
            return f"unknown-element: SID {sid} is not writable on device"
        return None


class AccessPoint:
    """In-memory state for the single wifi-ap container + its device list."""

    def __init__(self):
        # configuration
        self.name = "ap-1"
        self.enabled = True
        self.ssid = "corp-wifi"
        self.band = "band-5g"
        self.channel = 36
        self.tx_power = 20
        self.latency = 0
        self.devices = {}  # mac -> Device
        self._seed_devices()

    def _seed_devices(self):
        """Pre-populate a couple of associated clients so a fresh GET returns
        meaningful device data instead of an empty list."""
        seeds = [
            ("aa:bb:cc:00:11:22", "laptop-1", "192.0.2.50", -57, True),
            ("de:ad:be:ef:00:01", "phone-1", "192.0.2.51", -68, True),
        ]
        for mac, hostname, ip, signal, connected in seeds:
            d = Device(mac)
            d.hostname = hostname
            d.ip_address = ip
            d.signal_dbm = signal
            d.connected = connected
            self.devices[mac] = d

    @property
    def state(self):
        if not self.enabled:
            return SID_DOWN
        active = [d for d in self.devices.values() if d.connected]
        return SID_ACTIVE if active else SID_SCANNING

    def to_map(self):
        return {
            SID_WIFI_AP: {
                SID_AP_NAME: self.name,
                SID_ENABLED: self.enabled,
                SID_SSID: self.ssid,
                SID_BAND: BAND_TO_INT[self.band],
                SID_CHANNEL: self.channel,
                SID_TX_POWER: self.tx_power,
                SID_LATENCY: self.latency,
                SID_STATE: self.state,
                SID_DEVICE: [d.to_map() for d in self.devices.values()],
            }
        }

    def apply_ap_leaf(self, sid, value):
        if sid == SID_AP_NAME:
            if not (isinstance(value, str) and 1 <= len(value) <= 32):
                return "invalid-value: name must be 1..32 chars"
            self.name = value
        elif sid == SID_ENABLED:
            if not isinstance(value, bool):
                return "invalid-value: enabled must be boolean"
            self.enabled = value
            LOG.info("radio %s", "ENABLED" if value else "DISABLED")
        elif sid == SID_SSID:
            if not (isinstance(value, str) and 1 <= len(value) <= 32):
                return "invalid-value: ssid must be 1..32 chars"
            self.ssid = value
        elif sid == SID_BAND:
            if value not in INT_TO_BAND:
                return "invalid-value: unknown band"
            self.band = INT_TO_BAND[value]
        elif sid == SID_CHANNEL:
            if not (isinstance(value, int) and 1 <= value <= 196):
                return "not-in-range: channel must be 1..196"
            self.channel = value
        elif sid == SID_TX_POWER:
            if not (isinstance(value, int) and 1 <= value <= 30):
                return "not-in-range: tx-power must be 1..30 dBm"
            self.tx_power = value
        elif sid == SID_LATENCY:
            if not (isinstance(value, int) and 0 <= value <= 10000):
                return "not-in-range: latency must be 0..10000 ms"
            self.latency = value
            LOG.info("latency set to %d ms", value)
        else:
            return f"unknown-element: SID {sid} is not writable on wifi-ap"
        return None

    def apply_device_entry(self, entry):
        """Add/update/delete one device list entry keyed by 'mac'."""
        if not isinstance(entry, dict):
            return "malformed-message: device entry must be a map"
        mac = entry.get(SID_MAC)
        if not isinstance(mac, str) or not mac:
            return "missing-key: a valid 'mac' (SID 70021) is required"
        dev = self.devices.get(mac)
        created = False
        if dev is None:
            dev = Device(mac)
            # seed a plausible signal for a freshly connected device
            dev.signal_dbm = random.randint(-75, -45)
            self.devices[mac] = dev
            created = True
            LOG.info("Device %s connected", mac)
        for sid, value in entry.items():
            if sid == SID_MAC:
                continue
            if sid not in DEV_WRITABLE:
                if created:
                    self.devices.pop(mac, None)
                return f"unknown-element: SID {sid} is not writable on device"
            err = dev.apply_leaf(sid, value)
            if err:
                if created:
                    self.devices.pop(mac, None)
                return err
        return None

    def apply_wifi_ap(self, value):
        """Apply an iPATCH body under the wifi-ap container."""
        if not isinstance(value, dict):
            return "malformed-message: wifi-ap must be a map"
        for sid, v in value.items():
            if sid == SID_DEVICE:
                entries = v if isinstance(v, list) else [v]
                for entry in entries:
                    err = self.apply_device_entry(entry)
                    if err:
                        return err
            elif sid in AP_WRITABLE:
                err = self.apply_ap_leaf(sid, v)
                if err:
                    return err
            else:
                return f"unknown-element: SID {sid} is not writable"
        return None


AP = AccessPoint()


class DatastoreResource(resource.Resource):
    """The /c datastore resource implementing CORECONF methods."""

    async def render_get(self, request):
        LOG.info("GET /c")
        payload = cbor2.dumps(AP.to_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_DATA_CBOR)

    async def render_fetch(self, request):
        LOG.info("FETCH /c")
        payload = cbor2.dumps(AP.to_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_INSTANCES_SEQ)

    async def render_ipatch(self, request):
        LOG.info("iPATCH /c")
        items = decode_cbor_seq(request.payload)
        for item in items:
            if not isinstance(item, dict):
                return _error("malformed-message")
            for key, value in item.items():
                if key == SID_WIFI_AP:
                    err = AP.apply_wifi_ap(value)
                    if err:
                        return _error(err)
                else:
                    return _error(f"unknown-element: SID {key}")
        return Message(code=Code.CHANGED)

    async def render_post(self, request):
        LOG.info("POST /c (no action defined)")
        return Message(code=Code.METHOD_NOT_ALLOWED)


def _error(msg):
    LOG.warning("Rejecting request: %s", msg)
    return Message(code=Code.BAD_REQUEST, payload=msg.encode())


async def main():
    root = resource.Site()
    root.add_resource([DATASTORE_PATH], DatastoreResource())
    await Context.create_server_context(root, bind=("::", 5683))
    LOG.info("CORECONF wifi-ap server listening on coap://[::]:5683/%s",
             DATASTORE_PATH)
    await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
