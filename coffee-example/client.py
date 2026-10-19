#!/usr/bin/env python3
"""
CORECONF client for the coffee-maker *fleet*.

    [coffee-maker manager] --CORECONF--> [coffee-maker fleet datastore]

Demonstrates the CORECONF workflow against server.py:

  1. GET the full datastore (manager container + coffee-maker list).
  2. Turn one maker ON (iPATCH a single list entry, keyed by id).
  3. Brew on that maker (POST the brew action with the maker id).
  4. GET again to confirm the new state / remaining coffee.
  5. Turn the maker OFF.

For each mutation it prints the encoded size of the equivalent NETCONF (XML)
message and the CORECONF (CBOR/SID) message, so you can see how much smaller
CORECONF is for the same operation.

All payloads are CBOR keyed by numeric YANG SIDs (RFC 9254 / RFC 9595).

Run (after starting server.py):
    python3 client.py
"""

import asyncio
import logging

import cbor2
from aiocoap import Message, Code, Context

from coffee_sids import (
    SID_MANAGER, SID_MGR_NAME, SID_MAKER_COUNT,
    SID_MAKER, SID_ID, SID_LOCATION, SID_POWER, SID_CUPS, SID_STRENGTH,
    SID_STATE, SID_WATER_LEVEL, SID_BEANS_LEVEL, SID_HAS_COFFEE,
    SID_CUPS_BREWED, SID_LAST_ERROR,
    SID_BREW_STARTED, SID_BREW_REASON,
    INT_TO_STRENGTH, STATE_NAMES,
    CF_YANG_INSTANCES_SEQ, CF_YANG_DATA_CBOR, DATASTORE_PATH,
    coreconf_maker_leaf, coreconf_maker_entry,
    netconf_maker_leaf, sizes,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-coffee-client")

SERVER = f"coap://localhost/{DATASTORE_PATH}"


def _pretty_maker(m):
    return {
        "id": m.get(SID_ID),
        "location": m.get(SID_LOCATION),
        "power": m.get(SID_POWER),
        "cups": m.get(SID_CUPS),
        "strength": INT_TO_STRENGTH.get(m.get(SID_STRENGTH)),
        "state": STATE_NAMES.get(m.get(SID_STATE)),
        "water_level": m.get(SID_WATER_LEVEL),
        "beans_level": m.get(SID_BEANS_LEVEL),
        "has_coffee": m.get(SID_HAS_COFFEE),
        "cups_brewed": m.get(SID_CUPS_BREWED),
        "last_error": m.get(SID_LAST_ERROR),
    }


def _report_sizes(label, s):
    nc, cc = s["netconf"], s["coreconf"]
    LOG.info("  size for '%s':", label)
    LOG.info("    NETCONF  (XML)      payload=%4d B  wire=%4d B",
             nc["payload"], nc["wire"])
    LOG.info("    CORECONF (CBOR/SID) payload=%4d B  wire=%4d B",
             cc["payload"], cc["wire"])
    LOG.info("    -> CORECONF is %sx smaller (payload), %sx (wire)",
             s["ratio_payload"], s["ratio_wire"])


async def get_all(ctx):
    req = Message(code=Code.GET, uri=SERVER)
    resp = await ctx.request(req).response
    data = cbor2.loads(resp.payload)
    mgr = data.get(SID_MANAGER, {})
    makers = mgr.get(SID_MAKER, []) or []
    LOG.info("GET -> manager=%r, %d maker(s):", mgr.get(SID_MGR_NAME),
             mgr.get(SID_MAKER_COUNT))
    for m in makers:
        LOG.info("   %s", _pretty_maker(m))
    return makers


async def _ipatch(ctx, body, label):
    req = Message(code=Code.iPATCH, uri=SERVER, payload=cbor2.dumps(body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    detail = ""
    if not resp.code.is_successful() and resp.payload:
        detail = " (" + resp.payload.decode(errors="replace") + ")"
    LOG.info("%s -> %s%s", label, resp.code, detail)
    return resp.code.is_successful()


async def set_power(ctx, maker_id, on):
    cc_body = coreconf_maker_leaf(maker_id, SID_POWER, on)
    nc_xml = netconf_maker_leaf(maker_id, "power", on)
    _report_sizes(f"set maker '{maker_id}' power={on}",
                  sizes(nc_xml, cc_body, coreconf_is_seq=True))
    verb = "ON" if on else "OFF"
    return await _ipatch(ctx, cc_body, f"iPATCH turn '{maker_id}' {verb}")


async def configure(ctx, maker_id, cups, strength):
    from coffee_sids import STRENGTH_TO_INT
    cc_body = coreconf_maker_entry(maker_id, {
        SID_CUPS: cups,
        SID_STRENGTH: STRENGTH_TO_INT[strength],
    })
    return await _ipatch(ctx, cc_body,
                         f"iPATCH configure '{maker_id}' cups={cups} "
                         f"strength={strength}")


async def brew(ctx, maker_id):
    body = {SID_MANAGER: {SID_MAKER: [{SID_ID: maker_id}]}}
    req = Message(code=Code.POST, uri=SERVER, payload=cbor2.dumps(body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    if resp.payload:
        out = cbor2.loads(resp.payload)
        LOG.info("POST brew '%s' -> started=%s reason=%r", maker_id,
                 out.get(SID_BREW_STARTED), out.get(SID_BREW_REASON, ""))
        return out.get(SID_BREW_STARTED)
    LOG.info("POST brew '%s' -> %s", maker_id, resp.code)
    return False


async def main():
    ctx = await Context.create_client_context()

    LOG.info("--- initial fleet state ---")
    await get_all(ctx)

    LOG.info("--- turn 'lab' ON and configure it ---")
    await set_power(ctx, "lab", True)
    await configure(ctx, "lab", cups=2, strength="strong")

    LOG.info("--- brew on 'lab' ---")
    await brew(ctx, "lab")

    LOG.info("--- final fleet state ---")
    await get_all(ctx)

    LOG.info("--- turn 'lab' OFF ---")
    await set_power(ctx, "lab", False)

    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
