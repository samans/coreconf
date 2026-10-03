#!/usr/bin/env python3
"""
CORECONF server for the coffee-maker example.

Implements a CoAP server exposing a single datastore resource at /c that
holds the state of one coffee maker, following the operations described in
draft-ietf-core-comi (CORECONF):

  * GET   /c                 -> return the full datastore (CBOR map of SID:value)
  * FETCH /c                 -> return selected instance-values
  * iPATCH /c                -> merge/replace/delete selected instance-values
                                (this is how the client turns the maker on/off)
  * POST  /c  (brew action)  -> invoke the 'brew' action

Payloads are CBOR maps keyed by numeric YANG SIDs (RFC 9254 / RFC 9595).

Run:
    python3 server.py            # NoSec (plain CoAP) on udp/5683
"""

import asyncio
import logging

import cbor2
from aiocoap import resource, Message, Code, Context

from coffee_sids import (
    SID_COFFEE_MAKER, SID_POWER, SID_CUPS, SID_STRENGTH, SID_STATE,
    SID_WATER_LEVEL, SID_BREW_STARTED, SID_IDLE, SID_OFF, SID_BREWING,
    STRENGTH_TO_INT, INT_TO_STRENGTH,
    CF_YANG_DATA_CBOR, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-server")


class CoffeeDatastore:
    """In-memory YANG datastore for the coffee maker."""

    def __init__(self):
        # configuration
        self.power = False
        self.cups = 1
        self.strength = "medium"
        # operational state
        self.water_level = 80

    @property
    def state(self):
        if not self.power:
            return SID_OFF
        return SID_IDLE

    def config_map(self):
        """Config nodes as a SID-keyed map."""
        return {
            SID_POWER: self.power,
            SID_CUPS: self.cups,
            SID_STRENGTH: STRENGTH_TO_INT[self.strength],
        }

    def full_map(self):
        """Config + operational state, nested under the container SID."""
        inner = self.config_map()
        inner[SID_STATE] = self.state
        inner[SID_WATER_LEVEL] = self.water_level
        return {SID_COFFEE_MAKER: inner}

    def apply_instance(self, sid, value):
        """Apply a single instance-value from an iPATCH request.

        A CBOR null value means 'delete' -> reset to default here.
        Returns None on success or an error string.
        """
        if sid == SID_POWER:
            if value is None:
                self.power = False
            elif isinstance(value, bool):
                self.power = value
                LOG.info("Coffee maker powered %s", "ON" if value else "OFF")
            else:
                return "invalid-value: power must be boolean"
        elif sid == SID_CUPS:
            if value is None:
                self.cups = 1
            elif isinstance(value, int) and 1 <= value <= 12:
                self.cups = value
            else:
                return "not-in-range: cups must be 1..12"
        elif sid == SID_STRENGTH:
            if value is None:
                self.strength = "medium"
            elif value in INT_TO_STRENGTH:
                self.strength = INT_TO_STRENGTH[value]
            else:
                return "invalid-value: unknown strength"
        else:
            return f"unknown-element: SID {sid} is not writable"
        return None


DATASTORE = CoffeeDatastore()


class DatastoreResource(resource.Resource):
    """The /c datastore resource implementing CORECONF methods."""

    async def render_get(self, request):
        LOG.info("GET /c")
        payload = cbor2.dumps(DATASTORE.full_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_DATA_CBOR)

    async def render_fetch(self, request):
        """FETCH: request payload is a CBOR sequence of instance-identifiers
        (bare SIDs here); respond with a CBOR seq of {SID: value} maps."""
        LOG.info("FETCH /c")
        ids = _decode_cbor_seq(request.payload)
        inner = DATASTORE.full_map()[SID_COFFEE_MAKER]
        out = b""
        for ident in ids:
            sid = ident[0] if isinstance(ident, list) else ident
            value = inner.get(sid)
            out += cbor2.dumps({sid: value})
        return Message(code=Code.CONTENT, payload=out,
                       content_format=CF_YANG_INSTANCES_SEQ)

    async def render_ipatch(self, request):
        """iPATCH: merge/replace/delete. Payload is a CBOR sequence of
        {instance-identifier: instance-value} maps."""
        LOG.info("iPATCH /c")
        items = _decode_cbor_seq(request.payload)
        for item in items:
            if not isinstance(item, dict):
                return Message(code=Code.BAD_REQUEST,
                               payload=b"malformed-message")
            for key, value in item.items():
                # key may be a bare SID, or the value may be a nested map
                # keyed by child SIDs (the container case).
                if key == SID_COFFEE_MAKER and isinstance(value, dict):
                    for child_sid, child_val in value.items():
                        err = DATASTORE.apply_instance(child_sid, child_val)
                        if err:
                            return _error(err)
                else:
                    sid = key[0] if isinstance(key, (list, tuple)) else key
                    err = DATASTORE.apply_instance(sid, value)
                    if err:
                        return _error(err)
        return Message(code=Code.CHANGED)

    async def render_post(self, request):
        """POST invokes the 'brew' action (SID 60016)."""
        LOG.info("POST /c (brew action)")
        started = DATASTORE.power  # can only brew if powered on
        if started:
            LOG.info("Brewing %d cup(s), %s", DATASTORE.cups, DATASTORE.strength)
        payload = cbor2.dumps({SID_BREW_STARTED: started})
        return Message(code=Code.CHANGED, payload=payload,
                       content_format=CF_YANG_DATA_CBOR)


def _decode_cbor_seq(data):
    """Decode a CBOR sequence (concatenated CBOR items) into a list."""
    items = []
    decoder_buf = data
    while decoder_buf:
        # cbor2.loads reads one item; use a stream to track consumed bytes.
        import io
        stream = io.BytesIO(decoder_buf)
        obj = cbor2.load(stream)
        items.append(obj)
        decoder_buf = decoder_buf[stream.tell():]
    return items


def _error(msg):
    LOG.warning("Rejecting request: %s", msg)
    return Message(code=Code.BAD_REQUEST, payload=msg.encode())


async def main():
    root = resource.Site()
    root.add_resource([DATASTORE_PATH], DatastoreResource())
    await Context.create_server_context(root, bind=("::", 5683))
    LOG.info("CORECONF coffee-maker server listening on coap://[::]:5683/%s",
             DATASTORE_PATH)
    await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
