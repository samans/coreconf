#!/usr/bin/env python3
"""
Instrumented client for the coffee-maker fleet web console.

Emits one JSON object per line (ndjson) describing every message that
crosses the CORECONF hop between the manager and the fleet datastore, so the
web console can animate the message passing and show the NETCONF-vs-CORECONF
size difference.

    [manager] --CORECONF--> [fleet]        (real CoAP/CBOR/SID to server.py)

Each operation produces a request event (manager -> fleet) and a response
event (fleet -> manager). The real CoAP exchange hits server.py.

Invoked as:
    python3 webui/flow_client.py <op> [--id ID] [--cups N] ...

Operations:
    get                              read the whole fleet (manager + makers)
    power-on     --id ID             turn a maker on
    power-off    --id ID             turn a maker off
    set-cups     --id ID --cups N    set cups-per-brew
    set-strength --id ID --strength S
    brew         --id ID             brew on a maker (POST action)
    add          --id ID [--location L]  add a new maker to the fleet
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cbor2
from aiocoap import Message, Code, Context

from coffee_sids import (
    SID_MANAGER, SID_MGR_NAME, SID_MAKER_COUNT,
    SID_MAKER, SID_ID, SID_LOCATION, SID_POWER, SID_CUPS, SID_STRENGTH,
    SID_STATE, SID_WATER_LEVEL, SID_BEANS_LEVEL, SID_HAS_COFFEE,
    SID_CUPS_BREWED, SID_LAST_ERROR,
    SID_BREW_STARTED, SID_BREW_REASON,
    SID_REFILL, SID_REFILL_BEANS_LEVEL, SID_REFILL_WATER_LEVEL,
    STRENGTH_TO_INT, INT_TO_STRENGTH, STATE_NAMES,
    CF_YANG_INSTANCES_SEQ, DATASTORE_PATH, decode_cbor_seq, named,
    coreconf_maker_leaf, coreconf_maker_entry,
    netconf_maker_leaf, netconf_maker_entry, netconf_get,
    sizes,
    NODE_MANAGER, NODE_FLEET,
)

SERVER = f"coap://localhost/{DATASTORE_PATH}"


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


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
        "last_error": m.get(SID_LAST_ERROR) or "",
    }


def _pretty_fleet(data):
    try:
        mgr = data[SID_MANAGER]
    except (KeyError, TypeError):
        return data
    makers = mgr.get(SID_MAKER, []) or []
    return {
        "manager": mgr.get(SID_MGR_NAME),
        "maker_count": mgr.get(SID_MAKER_COUNT),
        "makers": [_pretty_maker(m) for m in makers],
    }


def _netconf_get_reply_xml(data):
    """Build the NETCONF <rpc-reply> XML that would carry the same fleet
    subtree a CORECONF GET returns — used to size the *response* direction
    apples-to-apples against the CBOR/SID body."""
    mgr = (data or {}).get(SID_MANAGER, {}) or {}
    makers = mgr.get(SID_MAKER, []) or []

    def leaf(tag, val):
        if val is None:
            return ""
        if val is True:
            val = "true"
        elif val is False:
            val = "false"
        return f"<{tag}>{val}</{tag}>"

    body = leaf("name", mgr.get(SID_MGR_NAME))
    body += leaf("maker-count", mgr.get(SID_MAKER_COUNT))
    for m in makers:
        body += "<coffee-maker>"
        body += leaf("id", m.get(SID_ID))
        body += leaf("location", m.get(SID_LOCATION))
        body += leaf("power", m.get(SID_POWER))
        body += leaf("cups", m.get(SID_CUPS))
        body += leaf("strength", INT_TO_STRENGTH.get(m.get(SID_STRENGTH)))
        body += leaf("state", STATE_NAMES.get(m.get(SID_STATE)))
        body += leaf("water-level", m.get(SID_WATER_LEVEL))
        body += leaf("beans-level", m.get(SID_BEANS_LEVEL))
        body += leaf("has-coffee", m.get(SID_HAS_COFFEE))
        body += leaf("cups-brewed", m.get(SID_CUPS_BREWED))
        body += "</coffee-maker>"
    return (
        '<rpc-reply message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><data>'
        f'<coffee-maker-manager xmlns="urn:example:coffee-maker">{body}'
        '</coffee-maker-manager>'
        '</data></rpc-reply>'
    )


def _hop_event(frm, to, direction, method, size_info,
               label=None, payload=None, extra=None):
    ev = {
        "dir": direction,            # "req" or "resp"
        "from": frm, "to": to,
        "protocol": "CORECONF",
        "method": method,
        "label": label,
        "payload": payload,
    }
    if size_info is not None:
        ev["sizes"] = {
            "netconf": size_info["netconf"],
            "coreconf": size_info["coreconf"],
            "ratio_payload": size_info["ratio_payload"],
            "ratio_wire": size_info["ratio_wire"],
        }
    if extra:
        ev.update(extra)
    emit(ev)


# =========================================================================
# Operation primitives
# =========================================================================

async def _mutation(ctx, label, netconf_xml, cc_body, method="iPATCH"):
    """Animate a manager mutation: request down, real CoAP, response up."""
    s = sizes(netconf_xml, cc_body, coreconf_is_seq=True)

    _hop_event(NODE_MANAGER, NODE_FLEET, "req", method, s,
               label=label, payload={"cbor-sid": named(cc_body)})

    req = Message(code=Code.iPATCH, uri=SERVER,
                  payload=cbor2.dumps(cc_body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    ok = resp.code.is_successful()
    decoded = {"result": "Changed" if ok else "rejected"}
    if not ok and resp.payload:
        decoded["error"] = resp.payload.decode(errors="replace")

    _hop_event(NODE_FLEET, NODE_MANAGER, "resp", str(resp.code),
               None, label="ack", payload=decoded,
               extra={"ok": ok, "code": str(resp.code), "refresh": True})
    return ok


async def op_get(ctx, a):
    """Read the whole fleet; compare the data-bearing response bodies."""
    nc_req_xml = netconf_get(
        '<coffee-maker-manager xmlns="urn:example:coffee-maker"/>')
    req = Message(code=Code.GET, uri=SERVER)
    resp = await ctx.request(req).response
    data = cbor2.loads(resp.payload) if resp.payload else {}

    # request direction: NETCONF <get> vs empty CORECONF GET
    s_req = sizes(nc_req_xml, {}, coreconf_is_seq=False)
    # response direction: the real data bodies
    nc_reply_xml = _netconf_get_reply_xml(data)
    cc_resp_bytes = resp.payload if resp.payload else b""
    s_resp = sizes(nc_reply_xml, cc_resp_bytes, coreconf_is_seq=True)

    pretty = _pretty_fleet(data)
    _hop_event(NODE_MANAGER, NODE_FLEET, "req", "GET", s_req,
               label="Read fleet state", payload={"(empty)": None})
    _hop_event(NODE_FLEET, NODE_MANAGER, "resp", str(resp.code), s_resp,
               label="data (fleet state)", payload=named(data),
               extra={"ok": resp.code.is_successful(), "decoded": pretty,
                      "code": str(resp.code), "refresh": True,
                      "size_label": "Read fleet state (response body)"})
    return pretty


async def op_power_on(ctx, a):
    await _mutation(ctx, f"Power ON maker '{a.id}'",
                    netconf_maker_leaf(a.id, "power", True),
                    coreconf_maker_leaf(a.id, SID_POWER, True))


async def op_power_off(ctx, a):
    await _mutation(ctx, f"Power OFF maker '{a.id}'",
                    netconf_maker_leaf(a.id, "power", False),
                    coreconf_maker_leaf(a.id, SID_POWER, False))


async def op_set_cups(ctx, a):
    cups = a.cups if a.cups is not None else 1
    await _mutation(ctx, f"Set '{a.id}' cups = {cups}",
                    netconf_maker_leaf(a.id, "cups", cups),
                    coreconf_maker_leaf(a.id, SID_CUPS, cups))


async def op_set_strength(ctx, a):
    strength = a.strength or "medium"
    sint = STRENGTH_TO_INT.get(strength, 1)
    await _mutation(ctx, f"Set '{a.id}' strength = {strength}",
                    netconf_maker_leaf(a.id, "strength", strength),
                    coreconf_maker_leaf(a.id, SID_STRENGTH, sint))


async def op_add(ctx, a):
    leaves = {}
    nc_leaves = {}
    if a.location:
        leaves[SID_LOCATION] = a.location
        nc_leaves["location"] = a.location
    await _mutation(ctx, f"Add maker '{a.id}'",
                    netconf_maker_entry(a.id, nc_leaves),
                    coreconf_maker_entry(a.id, leaves))


async def op_brew(ctx, a):
    """POST the brew action for one maker."""
    cc_body = {SID_MANAGER: {SID_MAKER: [{SID_ID: a.id}]}}
    # NETCONF equivalent would be an <action> RPC selecting the list entry.
    nc_xml = (
        '<rpc message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
        '<action xmlns="urn:ietf:params:xml:ns:yang:1">'
        '<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        f'<coffee-maker><id>{a.id}</id><brew/></coffee-maker>'
        '</coffee-maker-manager></action></rpc>'
    )
    s = sizes(nc_xml, cc_body, coreconf_is_seq=True)
    _hop_event(NODE_MANAGER, NODE_FLEET, "req", "POST (brew)", s,
               label=f"Brew on '{a.id}'", payload={"cbor-sid": named(cc_body)})

    req = Message(code=Code.POST, uri=SERVER, payload=cbor2.dumps(cc_body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    ok = resp.code.is_successful()
    out = cbor2.loads(resp.payload) if resp.payload else {}
    started = out.get(SID_BREW_STARTED)
    reason = out.get(SID_BREW_REASON, "")
    decoded = {"started": started, "reason": reason}
    _hop_event(NODE_FLEET, NODE_MANAGER, "resp", str(resp.code), None,
               label="brew result", payload=named(out),
               extra={"ok": ok, "code": str(resp.code), "refresh": True,
                      "decoded": decoded})


async def op_refill(ctx, a):
    """POST the refill action for one maker (add coffee beans + water)."""
    cc_body = {SID_MANAGER: {SID_MAKER: [{SID_ID: a.id, SID_REFILL: {}}]}}
    nc_xml = (
        '<rpc message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
        '<action xmlns="urn:ietf:params:xml:ns:yang:1">'
        '<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        f'<coffee-maker><id>{a.id}</id><refill/></coffee-maker>'
        '</coffee-maker-manager></action></rpc>'
    )
    s = sizes(nc_xml, cc_body, coreconf_is_seq=True)
    _hop_event(NODE_MANAGER, NODE_FLEET, "req", "POST (refill)", s,
               label=f"Add coffee to '{a.id}'",
               payload={"cbor-sid": named(cc_body)})

    req = Message(code=Code.POST, uri=SERVER, payload=cbor2.dumps(cc_body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    ok = resp.code.is_successful()
    out = cbor2.loads(resp.payload) if resp.payload else {}
    decoded = {"beans_level": out.get(SID_REFILL_BEANS_LEVEL),
               "water_level": out.get(SID_REFILL_WATER_LEVEL)}
    _hop_event(NODE_FLEET, NODE_MANAGER, "resp", str(resp.code), None,
               label="refill result", payload=named(out),
               extra={"ok": ok, "code": str(resp.code), "refresh": True,
                      "decoded": decoded})


OPS = {
    "get": op_get,
    "power-on": op_power_on,
    "power-off": op_power_off,
    "set-cups": op_set_cups,
    "set-strength": op_set_strength,
    "brew": op_brew,
    "refill": op_refill,
    "add": op_add,
}


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("op", choices=list(OPS.keys()))
    p.add_argument("--id", default="kitchen")
    p.add_argument("--cups", type=int, default=None)
    p.add_argument("--strength", default=None)
    p.add_argument("--location", default=None)
    return p.parse_args(argv)


async def main():
    args = parse_args(sys.argv[1:])
    op = OPS[args.op]
    ctx = await Context.create_client_context()
    try:
        await op(ctx, args)
    except Exception as exc:  # pragma: no cover
        emit({"dir": "error", "label": f"{type(exc).__name__}: {exc}"})
    finally:
        await ctx.shutdown()
    emit({"dir": "end"})


if __name__ == "__main__":
    asyncio.run(main())
