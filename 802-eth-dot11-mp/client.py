#!/usr/bin/env python3
"""
CLI client for the 802 three-node management chain.

    [mgmt station] --NETCONF--> [switch] --NETCONF--> [wifi-ap]
                                                --CORECONF--> [device]

Demonstrates the workflow against the AP's CORECONF datastore (server.py):

  1. GET the AP datastore (wifi-ap container + device list).
  2. SET an AP leaf (e.g. channel) — a manager action that cascades
     NETCONF -> NETCONF -> CORECONF down the chain.
  3. CONNECT a device via iPATCH (adds a device entry over CORECONF).
  4. GET again to confirm.

For each cascaded action it prints the encoded size of the equivalent
NETCONF (XML) message and the CORECONF (CBOR/SID) message, so you can see
how much smaller CORECONF is for the same operation.

Run (after starting server.py):
    python3 client.py
"""

import asyncio
import logging

import cbor2
from aiocoap import Message, Code, Context

from wifi_sids import (
    SID_WIFI_AP, SID_AP_NAME, SID_ENABLED, SID_SSID, SID_BAND, SID_CHANNEL,
    SID_TX_POWER, SID_LATENCY, SID_STATE,
    SID_DEVICE, SID_MAC, SID_HOSTNAME, SID_IP_ADDRESS, SID_SIGNAL_DBM,
    SID_CONNECTED,
    INT_TO_BAND, STATE_NAMES,
    CF_YANG_INSTANCES_SEQ, DATASTORE_PATH,
    coreconf_ap_leaf, coreconf_device_entry,
    netconf_ap_leaf, netconf_device_entry, sizes,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-ap-client")

SERVER = f"coap://localhost/{DATASTORE_PATH}"


def _pretty_ap(ap):
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
    ap = data.get(SID_WIFI_AP, {})
    LOG.info("GET -> %s", _pretty_ap(ap))
    return ap


async def _ipatch(ctx, body, label):
    req = Message(code=Code.iPATCH, uri=SERVER, payload=cbor2.dumps(body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    detail = ""
    if not resp.code.is_successful() and resp.payload:
        detail = " (" + resp.payload.decode(errors="replace") + ")"
    LOG.info("%s -> %s%s", label, resp.code, detail)
    return resp.code.is_successful()


async def set_channel(ctx, channel):
    cc_body = coreconf_ap_leaf(SID_CHANNEL, channel)
    nc_xml = netconf_ap_leaf("channel", channel)
    _report_sizes(f"set AP channel={channel}",
                  sizes(nc_xml, cc_body, coreconf_is_seq=True))
    return await _ipatch(ctx, cc_body, f"iPATCH set AP channel={channel}")


async def connect_device(ctx, mac, hostname, ip):
    leaves = {SID_HOSTNAME: hostname, SID_IP_ADDRESS: ip}
    cc_body = coreconf_device_entry(mac, leaves)
    nc_xml = netconf_device_entry(mac, {"hostname": hostname, "ip-address": ip})
    _report_sizes(f"connect device {mac}",
                  sizes(nc_xml, cc_body, coreconf_is_seq=True))
    return await _ipatch(ctx, cc_body, f"iPATCH connect device '{mac}'")


async def main():
    ctx = await Context.create_client_context()

    LOG.info("--- initial state ---")
    await get_all(ctx)

    LOG.info("--- cascade: manager sets AP channel to 44 ---")
    await set_channel(ctx, 44)

    LOG.info("--- cascade: connect a device ---")
    await connect_device(ctx, "aa:bb:cc:00:11:22", "laptop-1", "192.0.2.50")

    LOG.info("--- final state ---")
    await get_all(ctx)

    await ctx.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
