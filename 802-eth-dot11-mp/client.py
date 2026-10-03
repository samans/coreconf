#!/usr/bin/env python3
"""
CORECONF client for the 802.11 Wi-Fi hotspot example (keyed-list revision).

Demonstrates the CORECONF workflow against the server:

  1. GET the full datastore (all hotspots).
  2. ADD a new hotspot via iPATCH (a new keyed list entry).
  3. SET that hotspot's target latency via iPATCH.
  4. ENABLE its radio.
  5. GET again to confirm the new state.

All payloads are CBOR keyed by numeric YANG SIDs (RFC 9254 / RFC 9595).
A YANG list is encoded as a CBOR array of maps keyed by 'name'.

Run (after starting server.py):
    python3 client.py
"""

import asyncio
import logging

import cbor2
from aiocoap import Message, Code, Context

from wifi_sids import (
    SID_HOTSPOTS, SID_HOTSPOT, SID_NAME,
    SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL, SID_TX_POWER, SID_LATENCY,
    SID_STATE, SID_ASSOCIATED_STATIONS,
    BAND_TO_INT, INT_TO_BAND, STATE_NAMES,
    CF_YANG_INSTANCES_SEQ, DATASTORE_PATH,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-wifi-client")

SERVER = f"coap://localhost/{DATASTORE_PATH}"


def _pretty(m):
    return {
        "name": m.get(SID_NAME),
        "enabled": m.get(SID_ENABLED),
        "ssid": m.get(SID_SSID),
        "band": INT_TO_BAND.get(m.get(SID_BAND)),
        "channel": m.get(SID_CHANNEL),
        "tx_power": m.get(SID_TX_POWER),
        "latency_ms": m.get(SID_LATENCY),
        "state": STATE_NAMES.get(m.get(SID_STATE)),
        "stations": m.get(SID_ASSOCIATED_STATIONS),
    }


async def get_all(ctx):
    req = Message(code=Code.GET, uri=SERVER)
    resp = await ctx.request(req).response
    data = cbor2.loads(resp.payload)
    entries = data[SID_HOTSPOTS][SID_HOTSPOT]
    LOG.info("GET  -> %d hotspot(s):", len(entries))
    for e in entries:
        LOG.info("        %s", _pretty(e))
    return entries


def _entry_body(name, leaves=None):
    e = {SID_NAME: name}
    if leaves:
        e.update(leaves)
    return {SID_HOTSPOTS: {SID_HOTSPOT: [e]}}


async def _ipatch(ctx, body, label):
    req = Message(code=Code.iPATCH, uri=SERVER, payload=cbor2.dumps(body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    detail = ""
    if not resp.code.is_successful() and resp.payload:
        detail = " (" + resp.payload.decode(errors="replace") + ")"
    LOG.info("%s -> %s%s", label, resp.code, detail)
    return resp.code.is_successful()


async def add_hotspot(ctx, name, ssid, band="band-5g", channel=36, tx_power=23):
    body = _entry_body(name, {
        SID_SSID: ssid,
        SID_BAND: BAND_TO_INT[band],
        SID_CHANNEL: channel,
        SID_TX_POWER: tx_power,
    })
    return await _ipatch(ctx, body, f"iPATCH add hotspot '{name}'")


async def set_latency(ctx, name, latency_ms):
    body = _entry_body(name, {SID_LATENCY: latency_ms})
    return await _ipatch(ctx, body,
                         f"iPATCH set '{name}' latency={latency_ms}ms")


async def enable(ctx, name):
    body = _entry_body(name, {SID_ENABLED: True})
    return await _ipatch(ctx, body, f"iPATCH enable '{name}'")


async def main():
    ctx = await Context.create_client_context()

    LOG.info("--- initial state ---")
    await get_all(ctx)

    LOG.info("--- adding a hotspot 'lobby' ---")
    await add_hotspot(ctx, "lobby", ssid="lobby-guest")

    LOG.info("--- setting lobby latency target to 35 ms ---")
    await set_latency(ctx, "lobby", 35)

    LOG.info("--- enabling lobby radio ---")
    await enable(ctx, "lobby")

    LOG.info("--- final state ---")
    await get_all(ctx)

    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
