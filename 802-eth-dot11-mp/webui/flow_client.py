#!/usr/bin/env python3
"""
Instrumented CORECONF client for the Wi-Fi hotspot web console.

Emits one JSON object per line ("ndjson") describing every CoAP message
that crosses the wire, so the web console can animate the message passing
between client and server.

Invoked as:
    python3 webui/flow_client.py <op> [--name NAME] [--latency MS] [opts...]

Operations:
    get                      read the whole datastore (all hotspots)
    fetch                    read the hotspots list via FETCH
    add       --name N       add a hotspot (optionally with ssid/band/...)
    enable    --name N       enable a hotspot's radio
    disable   --name N       disable a hotspot's radio
    set-latency --name N --latency MS   set the latency target (ms)
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cbor2
from aiocoap import Message, Code, Context

from wifi_sids import (
    SID_HOTSPOTS, SID_HOTSPOT, SID_NAME,
    SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL, SID_TX_POWER, SID_LATENCY,
    SID_STATE, SID_ASSOCIATED_STATIONS,
    BAND_TO_INT, INT_TO_BAND, STATE_NAMES,
    CF_YANG_DATA_CBOR, CF_YANG_IDENTIFIERS_SEQ, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH,
)

SERVER = f"coap://localhost/{DATASTORE_PATH}"

SID_NAMES = {
    SID_HOTSPOTS: "hotspots",
    SID_HOTSPOT: "hotspot",
    SID_NAME: "name",
    SID_ENABLED: "enabled",
    SID_SSID: "ssid",
    SID_BAND: "band",
    SID_CHANNEL: "channel",
    SID_TX_POWER: "tx-power",
    SID_LATENCY: "latency",
    SID_STATE: "state",
    SID_ASSOCIATED_STATIONS: "associated-stations",
}


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _named(value):
    """Annotate SID keys with their names, recursively."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            name = SID_NAMES.get(k, str(k))
            out[f"{k} ({name})"] = _named(v)
        return out
    if isinstance(value, list):
        return [_named(v) for v in value]
    return value


def _pretty_hotspot(m):
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


def _pretty_all(data):
    try:
        entries = data[SID_HOTSPOTS][SID_HOTSPOT]
    except (KeyError, TypeError):
        return data
    return [_pretty_hotspot(e) for e in entries]


def _decode_cbor_seq(data):
    import io
    items = []
    while data:
        stream = io.BytesIO(data)
        items.append(cbor2.load(stream))
        data = data[stream.tell():]
    return items


async def send(ctx, req, label, req_struct):
    emit({"dir": "req", "method": str(req.code), "uri": SERVER,
          "cf": req.opt.content_format, "label": label,
          "payload": req_struct, "bytes": len(req.payload or b"")})
    return await ctx.request(req).response


def _resp_event(resp, decoded):
    ok = resp.code.is_successful()
    payload_view = "(no body)"
    if resp.payload:
        try:
            payload_view = _named(cbor2.loads(resp.payload))
        except Exception:
            payload_view = resp.payload.decode(errors="replace")
    emit({"dir": "resp", "code": str(resp.code),
          "cf": resp.opt.content_format,
          "payload": payload_view, "decoded": decoded,
          "bytes": len(resp.payload or b"")})


# ---- operations ------------------------------------------------------------

async def op_get(ctx, args):
    req = Message(code=Code.GET, uri=SERVER)
    resp = await send(ctx, req, "Read all hotspots", {"(empty)": None})
    data = cbor2.loads(resp.payload) if resp.payload else {}
    _resp_event(resp, _pretty_all(data))


async def op_fetch(ctx, args):
    payload = cbor2.dumps(SID_HOTSPOTS)
    req = Message(code=Code.FETCH, uri=SERVER, payload=payload,
                  content_format=CF_YANG_IDENTIFIERS_SEQ)
    resp = await send(ctx, req, "Fetch hotspots list",
                      {"request SIDs": [f"{SID_HOTSPOTS} (hotspots)"]})
    data = {}
    for it in _decode_cbor_seq(resp.payload or b""):
        if isinstance(it, dict):
            data.update(it)
    _resp_event(resp, _pretty_all(data))


def _entry(name, leaves=None):
    e = {SID_NAME: name}
    if leaves:
        e.update(leaves)
    return {SID_HOTSPOTS: {SID_HOTSPOT: [e]}}


async def _ipatch(ctx, body, label, decoded_hint):
    req = Message(code=Code.iPATCH, uri=SERVER, payload=cbor2.dumps(body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await send(ctx, req, label, _named(body))
    ok = resp.code.is_successful()
    decoded = {"result": "Changed" if ok else "rejected"}
    decoded.update(decoded_hint)
    if not ok and resp.payload:
        decoded["error"] = resp.payload.decode(errors="replace")
    _resp_event(resp, decoded)


async def op_add(ctx, args):
    leaves = {}
    if args.ssid:
        leaves[SID_SSID] = args.ssid
    if args.band:
        leaves[SID_BAND] = BAND_TO_INT[args.band]
    if args.channel is not None:
        leaves[SID_CHANNEL] = args.channel
    if args.tx_power is not None:
        leaves[SID_TX_POWER] = args.tx_power
    if args.latency is not None:
        leaves[SID_LATENCY] = args.latency
    body = _entry(args.name, leaves)
    await _ipatch(ctx, body, f"Add hotspot '{args.name}'",
                  {"hotspot": args.name})


async def op_enable(ctx, args):
    body = _entry(args.name, {SID_ENABLED: True})
    await _ipatch(ctx, body, f"Enable hotspot '{args.name}'",
                  {"hotspot": args.name})


async def op_disable(ctx, args):
    body = _entry(args.name, {SID_ENABLED: False})
    await _ipatch(ctx, body, f"Disable hotspot '{args.name}'",
                  {"hotspot": args.name})


async def op_set_latency(ctx, args):
    body = _entry(args.name, {SID_LATENCY: args.latency})
    await _ipatch(ctx, body,
                  f"Set latency of '{args.name}' to {args.latency} ms",
                  {"hotspot": args.name, "latency_ms": args.latency})


OPS = {
    "get": op_get,
    "fetch": op_fetch,
    "add": op_add,
    "enable": op_enable,
    "disable": op_disable,
    "set-latency": op_set_latency,
}


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("op", choices=list(OPS.keys()))
    p.add_argument("--name", default="default")
    p.add_argument("--ssid", default=None)
    p.add_argument("--band", default=None, choices=list(BAND_TO_INT.keys()))
    p.add_argument("--channel", type=int, default=None)
    p.add_argument("--tx-power", dest="tx_power", type=int, default=None)
    p.add_argument("--latency", type=int, default=None)
    return p.parse_args(argv)


async def main():
    args = parse_args(sys.argv[1:])
    op = OPS[args.op]
    # validate ops that require a latency value
    if args.op == "set-latency" and args.latency is None:
        emit({"dir": "error", "label": "set-latency requires --latency"})
        return
    ctx = await Context.create_client_context()
    try:
        await op(ctx, args)
    except Exception as exc:  # pragma: no cover
        emit({"dir": "error", "label": f"{type(exc).__name__}: {exc}"})
    finally:
        await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
