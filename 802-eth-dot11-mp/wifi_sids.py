"""
Shared definitions for the 802 three-node management-chain example.

Topology and protocols demonstrated:

    [mgmt station] --NETCONF--> [switch] --NETCONF--> [wifi-ap]
                                                --CORECONF--> [device]

  * mgmt station -> switch : NETCONF  (XML over SSH, RFC 6241)
  * switch -> wifi-ap      : NETCONF  (XML over SSH, RFC 6241)
  * wifi-ap -> device      : CORECONF (CoAP + CBOR + numeric SID,
                             draft-ietf-core-comi / RFC 9254 / RFC 9595)

The demo keeps CoAP/CBOR as the *real* transport everywhere (Option B), but
each hop is modeled and labeled with its correct protocol, and we compute
the real serialized byte size of the equivalent NETCONF (XML) encoding and
the CORECONF (CBOR/SID) encoding for the *same* operation, so the UI can
show the size difference between the two protocols as messages pass.

The CORECONF SID constants below come from example-wifi-ap@2026-10-05.sid.
"""

import io
import cbor2

# =========================================================================
# CORECONF (wifi-ap <-> device) numeric SIDs  (RFC 9595)
# =========================================================================

# wifi-ap container + leaves
SID_WIFI_AP = 70010          # container
SID_AP_NAME = 70011
SID_ENABLED = 70012
SID_SSID = 70013
SID_BAND = 70014
SID_CHANNEL = 70015
SID_TX_POWER = 70016
SID_LATENCY = 70017          # writable target latency (ms)
SID_STATE = 70018

# device list + leaves
SID_DEVICE = 70020           # list
SID_MAC = 70021              # list key
SID_HOSTNAME = 70022
SID_IP_ADDRESS = 70023
SID_SIGNAL_DBM = 70024
SID_CONNECTED = 70025

# identity SIDs
SID_DOWN = 70002
SID_SCANNING = 70003
SID_ACTIVE = 70004

# band enum <-> integer mapping (positional).
BAND_TO_INT = {"band-2g4": 0, "band-5g": 1, "band-6g": 2}
INT_TO_BAND = {v: k for k, v in BAND_TO_INT.items()}

# operational radio state identity names, for pretty-printing.
STATE_NAMES = {SID_DOWN: "down", SID_SCANNING: "scanning", SID_ACTIVE: "active"}

# Human-readable names for every SID, used to annotate decoded payloads.
SID_NAMES = {
    SID_WIFI_AP: "wifi-ap",
    SID_AP_NAME: "name",
    SID_ENABLED: "enabled",
    SID_SSID: "ssid",
    SID_BAND: "band",
    SID_CHANNEL: "channel",
    SID_TX_POWER: "tx-power",
    SID_LATENCY: "latency",
    SID_STATE: "state",
    SID_DEVICE: "device",
    SID_MAC: "mac",
    SID_HOSTNAME: "hostname",
    SID_IP_ADDRESS: "ip-address",
    SID_SIGNAL_DBM: "signal-dbm",
    SID_CONNECTED: "connected",
}

# =========================================================================
# CoAP Content-Formats defined by CORECONF (IANA numbers per the draft).
# =========================================================================
CF_YANG_DATA_CBOR = 140          # application/yang-data+cbor; id=sid
CF_YANG_IDENTIFIERS_SEQ = 141    # application/yang-identifiers+cbor-seq
CF_YANG_INSTANCES_SEQ = 142      # application/yang-instances+cbor-seq

# Datastore resource path used by the AP's CoAP (CORECONF) server.
DATASTORE_PATH = "c"

# =========================================================================
# Management chain node identifiers and the protocol used on each hop.
# =========================================================================
NODE_STATION = "station"     # NETCONF manager
NODE_SWITCH = "switch"       # NETCONF server (to station) + client (to AP)
NODE_AP = "ap"               # NETCONF server (to switch) + CORECONF client
NODE_DEVICE = "device"       # CORECONF server

# Ordered hops of the cascade: (from, to, protocol).
HOPS = [
    (NODE_STATION, NODE_SWITCH, "NETCONF"),
    (NODE_SWITCH, NODE_AP, "NETCONF"),
    (NODE_AP, NODE_DEVICE, "CORECONF"),
]

# =========================================================================
# Size-comparison engine
# =========================================================================
#
# For a given semantic operation we serialize the SAME change two ways and
# measure the real byte length of each encoding:
#
#   * NETCONF  : an <edit-config>/<get> RPC in XML (RFC 6241). Real XML text
#                is generated and measured; we just don't ship it over SSH.
#   * CORECONF : a CBOR map keyed by numeric SIDs (RFC 9254/9595), which is
#                exactly what travels on the AP<->device CoAP hop.
#
# We report two numbers per encoding:
#   payload_bytes  -- the serialized data unit only (headline, apples-to-apples)
#   wire_bytes     -- payload + a representative transport-framing estimate
#
# Framing estimates (clearly labeled as estimates in the UI):
#   NETCONF  : SSH binary-packet + TCP/IP overhead, approximated as a constant.
#   CoAP     : the real CoAP header is ~4 bytes + a few option bytes.

NETCONF_FRAMING_BYTES = 88   # representative SSH record + TCP/IP overhead
COAP_FRAMING_BYTES = 8       # ~4-byte CoAP header + Uri-Path/Content-Format opts

# Common NETCONF XML namespace boilerplate.
_NC_NS = 'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"'


def cbor_seq(*items):
    """Serialize items as a CBOR sequence (concatenated CBOR items)."""
    return b"".join(cbor2.dumps(it) for it in items)


def decode_cbor_seq(data):
    """Decode a CBOR sequence into a list of items."""
    items = []
    while data:
        stream = io.BytesIO(data)
        items.append(cbor2.load(stream))
        data = data[stream.tell():]
    return items


def named(value):
    """Annotate SID-keyed maps with human-readable names, recursively."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            label = SID_NAMES.get(k, str(k))
            out[f"{k} ({label})"] = named(v)
        return out
    if isinstance(value, list):
        return [named(v) for v in value]
    return value


# ---- CORECONF (CBOR/SID) encoders ---------------------------------------

def coreconf_ap_leaf(sid, value):
    """CORECONF iPATCH body setting one wifi-ap leaf: {wifi-ap: {sid: value}}."""
    return {SID_WIFI_AP: {sid: value}}


def coreconf_device_entry(mac, leaves=None):
    """CORECONF iPATCH body for a device list entry under wifi-ap."""
    entry = {SID_MAC: mac}
    if leaves:
        entry.update(leaves)
    return {SID_WIFI_AP: {SID_DEVICE: [entry]}}


# ---- NETCONF (XML) encoders for the SAME operations ---------------------

def _xml_edit_config(inner_xml):
    """Wrap inner config XML in a NETCONF <edit-config> RPC."""
    return (
        f'<rpc message-id="101" {_NC_NS}>'
        f'<edit-config>'
        f'<target><running/></target>'
        f'<config>{inner_xml}</config>'
        f'</edit-config>'
        f'</rpc>'
    )


def netconf_ap_leaf(leaf_name, value):
    """NETCONF edit-config setting one wifi-ap leaf (XML)."""
    val = "true" if value is True else "false" if value is False else str(value)
    inner = (
        f'<wifi-ap xmlns="urn:example:wifi-ap">'
        f'<{leaf_name}>{val}</{leaf_name}>'
        f'</wifi-ap>'
    )
    return _xml_edit_config(inner)


def netconf_switch_leaf(leaf_name, value):
    """NETCONF edit-config setting one switch leaf (XML)."""
    val = "true" if value is True else "false" if value is False else str(value)
    inner = (
        f'<switch xmlns="urn:example:switch">'
        f'<{leaf_name}>{val}</{leaf_name}>'
        f'</switch>'
    )
    return _xml_edit_config(inner)


def netconf_device_entry(mac, leaves=None):
    """NETCONF edit-config for a device entry under wifi-ap (XML)."""
    body = f'<device><mac>{mac}</mac>'
    for k, v in (leaves or {}).items():
        val = "true" if v is True else "false" if v is False else str(v)
        body += f'<{k}>{val}</{k}>'
    body += '</device>'
    inner = f'<wifi-ap xmlns="urn:example:wifi-ap">{body}</wifi-ap>'
    return _xml_edit_config(inner)


def netconf_get(subtree_xml):
    """NETCONF <get> RPC with a subtree filter (XML)."""
    return (
        f'<rpc message-id="101" {_NC_NS}>'
        f'<get><filter type="subtree">{subtree_xml}</filter></get>'
        f'</rpc>'
    )


def sizes(netconf_xml, coreconf_obj, coreconf_is_seq=False):
    """Measure and compare NETCONF vs CORECONF encodings of one operation.

    Returns a dict with payload/wire byte counts for both protocols and the
    reduction ratio, suitable for sending to the UI.
    """
    nc_payload = netconf_xml.encode("utf-8")
    if coreconf_is_seq:
        cc_payload = coreconf_obj if isinstance(coreconf_obj, (bytes, bytearray)) \
            else cbor_seq(coreconf_obj)
    else:
        cc_payload = cbor2.dumps(coreconf_obj)

    nc_p = len(nc_payload)
    cc_p = len(cc_payload)
    nc_w = nc_p + NETCONF_FRAMING_BYTES
    cc_w = cc_p + COAP_FRAMING_BYTES
    ratio = round(nc_p / cc_p, 1) if cc_p else None
    return {
        "netconf": {"payload": nc_p, "wire": nc_w, "xml": netconf_xml},
        "coreconf": {"payload": cc_p, "wire": cc_w},
        "ratio_payload": ratio,
        "ratio_wire": round(nc_w / cc_w, 1) if cc_w else None,
    }
