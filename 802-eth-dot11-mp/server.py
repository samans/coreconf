#!/usr/bin/env python3
"""
CORECONF server for the 802.11 Wi-Fi hotspot example (keyed-list revision).

Implements a CoAP server exposing a single datastore resource at /c that
holds a *list* of 802.11 hotspots, following the operations described in
draft-ietf-core-comi (CORECONF):

  * GET   /c   -> return the full datastore: the hotspots container with its
                  list encoded as a CBOR array of per-hotspot maps.
  * FETCH /c   -> return selected instance-values.
  * iPATCH /c  -> merge/replace/delete. Used to:
                    - ADD a hotspot (merge a new keyed list entry), and
                    - SET any leaf of an existing hotspot, including the
                      writable 'latency' target.
  * POST  /c   -> (reserved) no action in this revision.

Payloads are CBOR keyed by numeric YANG SIDs (RFC 9254 / RFC 9595). A YANG
list is encoded as a CBOR array of maps; each map carries the key leaf
(name) plus other leaves.

Run:
    python3 server.py            # NoSec (plain CoAP) on udp/5683
"""

import asyncio
import logging
import random

import cbor2
from aiocoap import resource, Message, Code, Context

from wifi_sids import (
    SID_HOTSPOTS, SID_HOTSPOT, SID_NAME,
    SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL, SID_TX_POWER, SID_LATENCY,
    SID_STATE, SID_ASSOCIATED_STATIONS,
    SID_DOWN, SID_SCANNING, SID_ACTIVE,
    BAND_TO_INT, INT_TO_BAND,
    CF_YANG_DATA_CBOR, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-wifi-server")

# writable leaf SIDs that may appear in an iPATCH entry
WRITABLE = {SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL, SID_TX_POWER,
            SID_LATENCY}


class Hotspot:
    """In-memory state for one 802.11 hotspot (one YANG list entry)."""

    def __init__(self, name):
        self.name = name
        # configuration
        self.enabled = False
        self.ssid = "hotspot"
        self.band = "band-2g4"
        self.channel = 6
        self.tx_power = 20
        self.latency = 0          # writable target latency (ms)
        # operational state
        self.associated_stations = 0

    @property
    def state(self):
        if not self.enabled:
            return SID_DOWN
        if self.associated_stations == 0:
            return SID_SCANNING
        return SID_ACTIVE

    def to_map(self):
        """Encode this hotspot as a SID-keyed CBOR map (one list entry)."""
        return {
            SID_NAME: self.name,
            SID_ENABLED: self.enabled,
            SID_SSID: self.ssid,
            SID_BAND: BAND_TO_INT[self.band],
            SID_CHANNEL: self.channel,
            SID_TX_POWER: self.tx_power,
            SID_LATENCY: self.latency,
            SID_STATE: self.state,
            SID_ASSOCIATED_STATIONS: self.associated_stations,
        }

    def apply_leaf(self, sid, value):
        """Set one writable leaf. Returns None on success or an error str."""
        if sid == SID_ENABLED:
            if not isinstance(value, bool):
                return "invalid-value: enabled must be boolean"
            self.enabled = value
            self.associated_stations = random.randint(1, 5) if value else 0
            LOG.info("[%s] radio %s", self.name,
                     "ENABLED" if value else "DISABLED")
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
            LOG.info("[%s] latency set to %d ms", self.name, value)
        else:
            return f"unknown-element: SID {sid} is not writable"
        return None


class HotspotDatastore:
    """Holds the keyed list of hotspots."""

    def __init__(self):
        self.hotspots = {}  # name -> Hotspot
        # seed one default hotspot so GET is non-empty on first run
        default = Hotspot("default")
        default.ssid = "corp-wifi"
        self.hotspots[default.name] = default

    def full_map(self):
        """The whole datastore: hotspots container -> list (CBOR array)."""
        entries = [hs.to_map() for hs in self.hotspots.values()]
        return {SID_HOTSPOTS: {SID_HOTSPOT: entries}}

    def apply_entry(self, entry):
        """Apply one list-entry map from an iPATCH. The 'name' key selects
        or creates the hotspot; remaining leaves are set on it. Creating a
        new name adds a hotspot. Returns None or an error string."""
        if not isinstance(entry, dict):
            return "malformed-message: list entry must be a map"
        name = entry.get(SID_NAME)
        if not isinstance(name, str) or not (1 <= len(name) <= 32):
            return "missing-key: a valid 'name' (SID 70012) is required"
        hs = self.hotspots.get(name)
        created = False
        if hs is None:
            hs = Hotspot(name)
            self.hotspots[name] = hs
            created = True
            LOG.info("Added hotspot '%s'", name)
        for sid, value in entry.items():
            if sid == SID_NAME:
                continue
            if sid not in WRITABLE:
                return f"unknown-element: SID {sid} is not writable"
            err = hs.apply_leaf(sid, value)
            if err:
                # roll back a just-created hotspot on validation failure
                if created:
                    self.hotspots.pop(name, None)
                return err
        return None


DATASTORE = HotspotDatastore()


class DatastoreResource(resource.Resource):
    """The /c datastore resource implementing CORECONF methods."""

    async def render_get(self, request):
        LOG.info("GET /c")
        payload = cbor2.dumps(DATASTORE.full_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_DATA_CBOR)

    async def render_fetch(self, request):
        """FETCH: request payload is a CBOR sequence of instance-identifiers
        (bare SIDs here). We answer with the whole hotspots list for any
        requested SID (sufficient for this demo)."""
        LOG.info("FETCH /c")
        payload = cbor2.dumps(DATASTORE.full_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_INSTANCES_SEQ)

    async def render_ipatch(self, request):
        """iPATCH: merge/replace/delete. Payload is a CBOR sequence of
        {instance-identifier: instance-value} maps. We accept the hotspots
        container holding a list (CBOR array) of entries; each entry is
        keyed by 'name' and may create a hotspot and/or set its leaves."""
        LOG.info("iPATCH /c")
        items = _decode_cbor_seq(request.payload)
        for item in items:
            if not isinstance(item, dict):
                return _error("malformed-message")
            for key, value in item.items():
                if key == SID_HOTSPOTS and isinstance(value, dict):
                    entries = value.get(SID_HOTSPOT, [])
                    if isinstance(entries, dict):
                        entries = [entries]
                    for entry in entries:
                        err = DATASTORE.apply_entry(entry)
                        if err:
                            return _error(err)
                elif key == SID_HOTSPOT:
                    entries = value if isinstance(value, list) else [value]
                    for entry in entries:
                        err = DATASTORE.apply_entry(entry)
                        if err:
                            return _error(err)
                else:
                    return _error(f"unknown-element: SID {key}")
        return Message(code=Code.CHANGED)

    async def render_post(self, request):
        LOG.info("POST /c (no action defined in this revision)")
        return Message(code=Code.METHOD_NOT_ALLOWED)


def _decode_cbor_seq(data):
    """Decode a CBOR sequence (concatenated CBOR items) into a list."""
    import io
    items = []
    buf = data
    while buf:
        stream = io.BytesIO(buf)
        items.append(cbor2.load(stream))
        buf = buf[stream.tell():]
    return items


def _error(msg):
    LOG.warning("Rejecting request: %s", msg)
    return Message(code=Code.BAD_REQUEST, payload=msg.encode())


async def main():
    root = resource.Site()
    root.add_resource([DATASTORE_PATH], DatastoreResource())
    await Context.create_server_context(root, bind=("::", 5683))
    LOG.info("CORECONF wifi-hotspot server listening on coap://[::]:5683/%s",
             DATASTORE_PATH)
    await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
