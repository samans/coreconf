#!/usr/bin/env python3
"""
CORECONF client for the coffee-maker example.

Demonstrates the CORECONF workflow against the server:

  1. GET the full datastore.
  2. FETCH just the power + state leaves.
  3. iPATCH to turn the coffee maker ON (and set cups/strength).
  4. POST the 'brew' action.
  5. GET again to confirm the new state.

All payloads are CBOR keyed by numeric YANG SIDs (RFC 9254 / RFC 9595).

Run (after starting server.py):
    python3 client.py
"""

import asyncio
import logging

import cbor2
from aiocoap import Message, Code, Context

from coffee_sids import (
    SID_COFFEE_MAKER, SID_POWER, SID_CUPS, SID_STRENGTH, SID_STATE,
    SID_WATER_LEVEL, SID_BREW_STARTED, SID_IDLE, SID_OFF, SID_BREWING,
    STRENGTH_TO_INT, INT_TO_STRENGTH,
    CF_YANG_DATA_CBOR, CF_YANG_IDENTIFIERS_SEQ, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-client")

STATE_NAMES = {SID_OFF: "off", SID_IDLE: "idle", SID_BREWING: "brewing"}
SERVER = f"coap://localhost/{DATASTORE_PATH}"


def _pretty(inner):
    return {
        "power": inner.get(SID_POWER),
        "cups": inner.get(SID_CUPS),
        "strength": INT_TO_STRENGTH.get(inner.get(SID_STRENGTH)),
        "state": STATE_NAMES.get(inner.get(SID_STATE)),
        "water_level": inner.get(SID_WATER_LEVEL),
    }


async def get_full(ctx):
    req = Message(code=Code.GET, uri=SERVER)
    resp = await ctx.request(req).response
    data = cbor2.loads(resp.payload)
    LOG.info("GET  -> %s", _pretty(data[SID_COFFEE_MAKER]))
    return data


async def fetch_power_state(ctx):
    # FETCH request: a CBOR sequence of instance-identifiers (bare SIDs).
    payload = cbor2.dumps(SID_POWER) + cbor2.dumps(SID_STATE)
    req = Message(code=Code.FETCH, uri=SERVER, payload=payload,
                  content_format=CF_YANG_IDENTIFIERS_SEQ)
    resp = await ctx.request(req).response
    items = _decode_cbor_seq(resp.payload)
    merged = {}
    for it in items:
        merged.update(it)
    LOG.info("FETCH power=%s state=%s", merged.get(SID_POWER),
             STATE_NAMES.get(merged.get(SID_STATE)))
    return merged


async def turn_on(ctx, cups=2, strength="strong"):
    # iPATCH request: CBOR sequence of {instance-identifier: value} maps.
    # We nest under the container SID to set several leaves at once.
    body = {SID_COFFEE_MAKER: {
        SID_POWER: True,
        SID_CUPS: cups,
        SID_STRENGTH: STRENGTH_TO_INT[strength],
    }}
    payload = cbor2.dumps(body)
    req = Message(code=Code.iPATCH, uri=SERVER, payload=payload,
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    LOG.info("iPATCH turn ON -> %s", resp.code)
    return resp.code.is_successful()


async def turn_off(ctx):
    body = {SID_POWER: False}
    payload = cbor2.dumps(body)
    req = Message(code=Code.iPATCH, uri=SERVER, payload=payload,
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    LOG.info("iPATCH turn OFF -> %s", resp.code)
    return resp.code.is_successful()


async def brew(ctx):
    req = Message(code=Code.POST, uri=SERVER)
    resp = await ctx.request(req).response
    if resp.payload:
        out = cbor2.loads(resp.payload)
        LOG.info("POST brew -> started=%s", out.get(SID_BREW_STARTED))


def _decode_cbor_seq(data):
    import io
    items = []
    while data:
        stream = io.BytesIO(data)
        items.append(cbor2.load(stream))
        data = data[stream.tell():]
    return items


async def main():
    ctx = await Context.create_client_context()

    LOG.info("--- initial state ---")
    await get_full(ctx)
    await fetch_power_state(ctx)

    LOG.info("--- turning the coffee maker ON ---")
    await turn_on(ctx, cups=2, strength="strong")
    await get_full(ctx)

    LOG.info("--- brewing ---")
    await brew(ctx)

    LOG.info("--- turning the coffee maker OFF ---")
    await turn_off(ctx)
    await get_full(ctx)

    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
