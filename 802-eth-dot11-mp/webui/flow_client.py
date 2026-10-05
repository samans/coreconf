#!/usr/bin/env python3
"""
Instrumented client for the 802 management-chain web console.

Emits one JSON object per line (ndjson) describing every message that
crosses each hop of the chain, so the web console can animate the
message passing and show the NETCONF-vs-CORECONF size difference.

    [station] --NETCONF--> [switch] --NETCONF--> [ap] --CORECONF--> [device]

A single manager operation CASCADES down the chain:
  * hop station->switch  : NETCONF (XML) request/response  (sizes computed)
  * hop switch->ap        : NETCONF (XML) request/response  (sizes computed)
  * hop ap->device        : CORECONF (CoAP/CBOR/SID) request/response
                            -- this hop actually hits server.py.

Each emitted hop event carries both encodings' byte sizes so the UI can
render a side-by-side comparison.

Invoked as:
    python3 webui/flow_client.py <op> [--channel N] [--mac M ...]

Operations:
    get                 read the AP datastore (wifi-ap + devices)
    set-channel  --channel N
    set-latency  --latency MS
    set-power    --tx-power DBM
    set-ssid     --ssid NAME
    enable                      enable the AP radio
    disable                     disable the AP radio
    connect      --mac M [--hostname H --ip IP]   add/associate a device
    disconnect   --mac M                           remove a device
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
    SID_WIFI_AP, SID_AP_NAME, SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL,
    SID_TX_POWER, SID_LATENCY, SID_STATE,
    SID_DEVICE, SID_MAC, SID_HOSTNAME, SID_IP_ADDRESS, SID_SIGNAL_DBM,
    SID_CONNECTED,
    BAND_TO_INT, INT_TO_BAND, STATE_NAMES,
    CF_YANG_DATA_CBOR, CF_YANG_IDENTIFIERS_SEQ, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH, decode_cbor_seq, named, cbor_seq,
    coreconf_ap_leaf, coreconf_device_entry,
    netconf_ap_leaf, netconf_switch_leaf, netconf_device_entry, netconf_get,
    sizes,
    NODE_STATION, NODE_SWITCH, NODE_AP, NODE_DEVICE, HOPS,
)

SERVER = f"coap://localhost/{DATASTORE_PATH}"


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _pretty_ap(data):
    try:
        ap = data[SID_WIFI_AP]
    except (KeyError, TypeError):
        return data
    devs = ap.get(SID_DEVICE, []) or []
    return {
        "name": ap.get(SID_AP_NAME),
        "enabled": ap.get(SID_ENABLED),
        "ssid": ap.get(SID_SSID),
        "band": INT_TO_BAND.get(ap.get(SID_BAND)),
        "channel": ap.get(SID_CHANNEL),
        "tx_power": ap.get(SID_TX_POWER),
        "latency_ms": ap.get(SID_LATENCY),
        "state": STATE_NAMES.get(ap.get(SID_STATE)),
        "devices": [
            {"mac": d.get(SID_MAC), "hostname": d.get(SID_HOSTNAME),
             "ip": d.get(SID_IP_ADDRESS), "signal_dbm": d.get(SID_SIGNAL_DBM),
             "connected": d.get(SID_CONNECTED)}
            for d in devs
        ],
    }


def _netconf_get_reply_xml(data):
    """Build the NETCONF <rpc-reply> XML that would carry the same wifi-ap
    subtree a CORECONF GET returns — used to size the *response* direction
    apples-to-apples against the CBOR/SID body."""
    ap = (data or {}).get(SID_WIFI_AP, {}) or {}
    devs = ap.get(SID_DEVICE, []) or []

    def leaf(tag, val):
        if val is None:
            return ""
        if val is True:
            val = "true"
        elif val is False:
            val = "false"
        return f"<{tag}>{val}</{tag}>"

    body = leaf("name", ap.get(SID_AP_NAME))
    body += leaf("enabled", ap.get(SID_ENABLED))
    body += leaf("ssid", ap.get(SID_SSID))
    body += leaf("band", INT_TO_BAND.get(ap.get(SID_BAND)))
    body += leaf("channel", ap.get(SID_CHANNEL))
    body += leaf("tx-power", ap.get(SID_TX_POWER))
    body += leaf("latency", ap.get(SID_LATENCY))
    body += leaf("state", STATE_NAMES.get(ap.get(SID_STATE)))
    for d in devs:
        body += "<device>"
        body += leaf("mac", d.get(SID_MAC))
        body += leaf("hostname", d.get(SID_HOSTNAME))
        body += leaf("ip-address", d.get(SID_IP_ADDRESS))
        body += leaf("signal-dbm", d.get(SID_SIGNAL_DBM))
        body += leaf("connected", d.get(SID_CONNECTED))
        body += "</device>"
    return (
        '<rpc-reply message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><data>'
        f'<wifi-ap xmlns="urn:example:wifi-ap">{body}</wifi-ap>'
        '</data></rpc-reply>'
    )


# =========================================================================
# Cascade emitter
# =========================================================================
#
# A mutation operation produces, in order:
#   1. NETCONF req station->switch   (+ size info)
#   2. NETCONF req switch->ap         (+ size info)
#   3. CORECONF req ap->device        (+ size info) -- real CoAP exchange
#   4. CORECONF resp device->ap
#   5. NETCONF resp ap->switch
#   6. NETCONF resp switch->station
#
# For GET we do a read cascade with the same shape.

def _hop_event(frm, to, protocol, direction, method, size_info,
               label=None, payload=None, extra=None):
    ev = {
        "dir": direction,            # "req" or "resp"
        "from": frm, "to": to,
        "protocol": protocol,        # "NETCONF" | "CORECONF"
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


async def _coreconf_exchange(ctx, cc_body, method, is_get, is_fetch=False):
    """Perform the real CoAP (CORECONF) request to the AP and return resp."""
    if is_get:
        req = Message(code=Code.GET, uri=SERVER)
    elif is_fetch:
        payload = cbor2.dumps(SID_WIFI_AP)
        req = Message(code=Code.FETCH, uri=SERVER, payload=payload,
                      content_format=CF_YANG_IDENTIFIERS_SEQ)
    else:
        req = Message(code=Code.iPATCH, uri=SERVER,
                      payload=cbor2.dumps(cc_body),
                      content_format=CF_YANG_INSTANCES_SEQ)
    return await ctx.request(req).response


async def cascade_mutation(ctx, label, netconf_xml, cc_body, decoded_hint):
    """Animate a manager mutation flowing down all three hops."""
    s = sizes(netconf_xml, cc_body, coreconf_is_seq=True)

    # ---- requests travelling down the chain ----
    _hop_event(NODE_STATION, NODE_SWITCH, "NETCONF", "req", "edit-config",
               s, label=label, payload={"xml": netconf_xml})
    _hop_event(NODE_SWITCH, NODE_AP, "NETCONF", "req", "edit-config",
               s, label=label, payload={"xml": netconf_xml})
    _hop_event(NODE_AP, NODE_DEVICE, "CORECONF", "req", "iPATCH",
               s, label=label, payload={"cbor-sid": named(cc_body)})

    # ---- real CoAP exchange on the AP<->device hop ----
    resp = await _coreconf_exchange(ctx, cc_body, "iPATCH", is_get=False)
    ok = resp.code.is_successful()
    decoded = {"result": "Changed" if ok else "rejected"}
    decoded.update(decoded_hint)
    if not ok and resp.payload:
        decoded["error"] = resp.payload.decode(errors="replace")

    # ---- responses travelling back up the chain ----
    _hop_event(NODE_DEVICE, NODE_AP, "CORECONF", "resp", str(resp.code),
               None, label="ack", payload=decoded,
               extra={"ok": ok, "code": str(resp.code)})
    _hop_event(NODE_AP, NODE_SWITCH, "NETCONF", "resp", "rpc-reply",
               None, label="ok" if ok else "error",
               payload={"xml": '<rpc-reply><ok/></rpc-reply>' if ok
                        else '<rpc-reply><rpc-error/></rpc-reply>'},
               extra={"ok": ok})
    _hop_event(NODE_SWITCH, NODE_STATION, "NETCONF", "resp", "rpc-reply",
               None, label="ok" if ok else "error",
               payload={"xml": '<rpc-reply><ok/></rpc-reply>' if ok
                        else '<rpc-reply><rpc-error/></rpc-reply>'},
               extra={"ok": ok})
    return ok


async def cascade_get(ctx):
    """Animate a read cascade; the AP<->device hop really reads the datastore."""
    # equivalent NETCONF <get> for size comparison (whole wifi-ap subtree)
    nc_xml = netconf_get('<wifi-ap xmlns="urn:example:wifi-ap"/>')
    # CORECONF GET has an empty payload; compare the *response* bodies instead
    resp = await _coreconf_exchange(ctx, None, "GET", is_get=True)
    data = cbor2.loads(resp.payload) if resp.payload else {}

    # size comparison: NETCONF <get> request vs CORECONF GET (empty) request
    s_req = sizes(nc_xml, {}, coreconf_is_seq=False)

    # size comparison for the RESPONSE direction — this is where the real data
    # lives. CORECONF returns the actual CBOR/SID body the server sent; the
    # NETCONF equivalent is the <rpc-reply> XML carrying the same subtree.
    nc_reply_xml = _netconf_get_reply_xml(data)
    cc_resp_bytes = resp.payload if resp.payload else b""
    s_resp = sizes(nc_reply_xml, cc_resp_bytes, coreconf_is_seq=True)

    _hop_event(NODE_STATION, NODE_SWITCH, "NETCONF", "req", "get",
               s_req, label="Read AP state", payload={"xml": nc_xml})
    _hop_event(NODE_SWITCH, NODE_AP, "NETCONF", "req", "get",
               s_req, label="Read AP state", payload={"xml": nc_xml})
    _hop_event(NODE_AP, NODE_DEVICE, "CORECONF", "req", "GET",
               s_req, label="Read AP state", payload={"(empty)": None})

    pretty = _pretty_ap(data)
    _hop_event(NODE_DEVICE, NODE_AP, "CORECONF", "resp", str(resp.code),
               s_resp, label="data (AP state)", payload=named(data),
               extra={"ok": resp.code.is_successful(), "decoded": pretty,
                      "code": str(resp.code),
                      "size_label": "Read AP state (response body)"})
    _hop_event(NODE_AP, NODE_SWITCH, "NETCONF", "resp", "rpc-reply",
               None, label="data", payload={"xml": nc_reply_xml},
               extra={"ok": True, "decoded": pretty})
    _hop_event(NODE_SWITCH, NODE_STATION, "NETCONF", "resp", "rpc-reply",
               None, label="data", payload={"xml": nc_reply_xml},
               extra={"ok": True, "decoded": pretty})
    return pretty


# =========================================================================
# Operations
# =========================================================================

async def op_get(ctx, a):
    await cascade_get(ctx)


async def op_set_channel(ctx, a):
    ch = a.channel if a.channel is not None else 36
    await cascade_mutation(
        ctx, f"Set AP channel = {ch}",
        netconf_ap_leaf("channel", ch),
        coreconf_ap_leaf(SID_CHANNEL, ch),
        {"channel": ch})


async def op_set_latency(ctx, a):
    ms = a.latency if a.latency is not None else 0
    await cascade_mutation(
        ctx, f"Set AP latency = {ms} ms",
        netconf_ap_leaf("latency", ms),
        coreconf_ap_leaf(SID_LATENCY, ms),
        {"latency_ms": ms})


async def op_set_power(ctx, a):
    p = a.tx_power if a.tx_power is not None else 20
    await cascade_mutation(
        ctx, f"Set AP tx-power = {p} dBm",
        netconf_ap_leaf("tx-power", p),
        coreconf_ap_leaf(SID_TX_POWER, p),
        {"tx_power": p})


async def op_set_ssid(ctx, a):
    ssid = a.ssid or "corp-wifi"
    await cascade_mutation(
        ctx, f"Set AP ssid = {ssid}",
        netconf_ap_leaf("ssid", ssid),
        coreconf_ap_leaf(SID_SSID, ssid),
        {"ssid": ssid})


async def op_enable(ctx, a):
    await cascade_mutation(
        ctx, "Enable AP radio",
        netconf_ap_leaf("enabled", True),
        coreconf_ap_leaf(SID_ENABLED, True),
        {"enabled": True})


async def op_disable(ctx, a):
    await cascade_mutation(
        ctx, "Disable AP radio",
        netconf_ap_leaf("enabled", False),
        coreconf_ap_leaf(SID_ENABLED, False),
        {"enabled": False})


async def op_connect(ctx, a):
    mac = a.mac or "aa:bb:cc:00:11:22"
    leaves = {}
    nc_leaves = {}
    if a.hostname:
        leaves[SID_HOSTNAME] = a.hostname
        nc_leaves["hostname"] = a.hostname
    if a.ip:
        leaves[SID_IP_ADDRESS] = a.ip
        nc_leaves["ip-address"] = a.ip
    await cascade_mutation(
        ctx, f"Connect device {mac}",
        netconf_device_entry(mac, nc_leaves),
        coreconf_device_entry(mac, leaves),
        {"mac": mac})


async def op_disconnect(ctx, a):
    mac = a.mac or "aa:bb:cc:00:11:22"
    # delete = CORECONF null value for the entry; NETCONF uses nc:operation
    await cascade_mutation(
        ctx, f"Disconnect device {mac}",
        netconf_device_entry(mac, {"connected": False}),
        coreconf_device_entry(mac, {SID_CONNECTED: False}),
        {"mac": mac})


OPS = {
    "get": op_get,
    "set-channel": op_set_channel,
    "set-latency": op_set_latency,
    "set-power": op_set_power,
    "set-ssid": op_set_ssid,
    "enable": op_enable,
    "disable": op_disable,
    "connect": op_connect,
    "disconnect": op_disconnect,
}


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("op", choices=list(OPS.keys()))
    p.add_argument("--channel", type=int, default=None)
    p.add_argument("--latency", type=int, default=None)
    p.add_argument("--tx-power", dest="tx_power", type=int, default=None)
    p.add_argument("--ssid", default=None)
    p.add_argument("--mac", default=None)
    p.add_argument("--hostname", default=None)
    p.add_argument("--ip", default=None)
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
