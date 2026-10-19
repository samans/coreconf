"""
Shared definitions for the CORECONF coffee-maker *fleet* example.

A coffee-maker manager manages a list of coffee makers over CORECONF
(draft-ietf-core-comi): YANG data encoded as CBOR over CoAP, with every
schema node identified by a numeric YANG SID (RFC 9254 / RFC 9595) instead
of a long path string.

    [coffee-maker manager] --CORECONF--> [coffee maker fleet datastore]

These constants come straight from example-coffee-maker@2026-10-18.sid.
The module also carries a small size-comparison engine so the web UI can
show how much more compact CORECONF (CBOR/SID) is than the equivalent
NETCONF (XML) encoding of the same operation.
"""

import io
import cbor2

# =========================================================================
# CORECONF numeric SIDs  (RFC 9595) — from example-coffee-maker@2026-10-18.sid
# =========================================================================

# manager container + leaves
SID_MANAGER = 60010          # container coffee-maker-manager
SID_MGR_NAME = 60011
SID_MAKER_COUNT = 60012

# coffee-maker list + leaves
SID_MAKER = 60020            # list coffee-maker
SID_ID = 60021               # list key
SID_LOCATION = 60022
SID_POWER = 60023
SID_CUPS = 60024
SID_STRENGTH = 60025
SID_STATE = 60026
SID_WATER_LEVEL = 60027
SID_BEANS_LEVEL = 60028
SID_HAS_COFFEE = 60029
SID_CUPS_BREWED = 60030
SID_LAST_ERROR = 60031

# brew action + output
SID_BREW = 60032
SID_BREW_STARTED = 60033
SID_BREW_REASON = 60034

# refill action + input/output
SID_REFILL = 60035
SID_REFILL_BEANS = 60036        # input
SID_REFILL_WATER = 60037        # input
SID_REFILL_BEANS_LEVEL = 60038  # output
SID_REFILL_WATER_LEVEL = 60039  # output

# operational-state identity SIDs
SID_OFF = 60002
SID_IDLE = 60003
SID_BREWING = 60004
SID_NO_WATER = 60005
SID_NO_BEANS = 60006
SID_ERROR = 60007

# strength enum <-> integer mapping (positional, per YANG-to-CBOR).
STRENGTH_TO_INT = {"mild": 0, "medium": 1, "strong": 2}
INT_TO_STRENGTH = {v: k for k, v in STRENGTH_TO_INT.items()}

# operational-state identity names, for pretty-printing.
STATE_NAMES = {
    SID_OFF: "off",
    SID_IDLE: "idle",
    SID_BREWING: "brewing",
    SID_NO_WATER: "no-water",
    SID_NO_BEANS: "no-beans",
    SID_ERROR: "error",
}

# Human-readable names for every SID, used to annotate decoded payloads.
SID_NAMES = {
    SID_MANAGER: "coffee-maker-manager",
    SID_MGR_NAME: "name",
    SID_MAKER_COUNT: "maker-count",
    SID_MAKER: "coffee-maker",
    SID_ID: "id",
    SID_LOCATION: "location",
    SID_POWER: "power",
    SID_CUPS: "cups",
    SID_STRENGTH: "strength",
    SID_STATE: "state",
    SID_WATER_LEVEL: "water-level",
    SID_BEANS_LEVEL: "beans-level",
    SID_HAS_COFFEE: "has-coffee",
    SID_CUPS_BREWED: "cups-brewed",
    SID_LAST_ERROR: "last-error",
    SID_BREW: "brew",
    SID_BREW_STARTED: "started",
    SID_BREW_REASON: "reason",
    SID_REFILL: "refill",
    SID_REFILL_BEANS: "beans",
    SID_REFILL_WATER: "water",
    SID_REFILL_BEANS_LEVEL: "beans-level",
    SID_REFILL_WATER_LEVEL: "water-level",
}

# =========================================================================
# CoAP Content-Formats defined by CORECONF (IANA numbers per the draft).
# =========================================================================
CF_YANG_DATA_CBOR = 140          # application/yang-data+cbor; id=sid
CF_YANG_IDENTIFIERS_SEQ = 141    # application/yang-identifiers+cbor-seq
CF_YANG_INSTANCES_SEQ = 142      # application/yang-instances+cbor-seq

# Datastore resource path used by the fleet's CoAP (CORECONF) server.
DATASTORE_PATH = "c"

# =========================================================================
# Node identifiers and the protocol used on the hop.
# =========================================================================
NODE_MANAGER = "manager"     # CORECONF client (the coffee-maker manager)
NODE_FLEET = "fleet"         # CORECONF server (the coffee-maker datastore)

# =========================================================================
# CBOR sequence helpers
# =========================================================================

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


# =========================================================================
# CORECONF (CBOR/SID) encoders — bodies addressed to a specific maker
# =========================================================================

def coreconf_maker_leaf(maker_id, sid, value):
    """CORECONF iPATCH body setting one leaf on one maker:
    {manager: {coffee-maker: [{id: <id>, sid: value}]}}."""
    return {SID_MANAGER: {SID_MAKER: [{SID_ID: maker_id, sid: value}]}}


def coreconf_maker_entry(maker_id, leaves=None):
    """CORECONF iPATCH body for a whole coffee-maker list entry."""
    entry = {SID_ID: maker_id}
    if leaves:
        entry.update(leaves)
    return {SID_MANAGER: {SID_MAKER: [entry]}}


# =========================================================================
# NETCONF (XML) encoders for the SAME operations — for size comparison only
# =========================================================================

_NC_NS = 'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"'


def _xml_val(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


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


def netconf_maker_leaf(maker_id, leaf_name, value):
    """NETCONF edit-config setting one leaf on one maker (XML), selecting the
    list entry by its key — the apples-to-apples equivalent of the CORECONF
    maker-leaf body."""
    inner = (
        f'<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        f'<coffee-maker>'
        f'<id>{maker_id}</id>'
        f'<{leaf_name}>{_xml_val(value)}</{leaf_name}>'
        f'</coffee-maker>'
        f'</coffee-maker-manager>'
    )
    return _xml_edit_config(inner)


def netconf_maker_entry(maker_id, leaves=None):
    """NETCONF edit-config for a whole coffee-maker entry (XML)."""
    body = f'<coffee-maker><id>{maker_id}</id>'
    for k, v in (leaves or {}).items():
        body += f'<{k}>{_xml_val(v)}</{k}>'
    body += '</coffee-maker>'
    inner = (
        f'<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        f'{body}'
        f'</coffee-maker-manager>'
    )
    return _xml_edit_config(inner)


def netconf_get(subtree_xml):
    """NETCONF <get> RPC with a subtree filter (XML)."""
    return (
        f'<rpc message-id="101" {_NC_NS}>'
        f'<get><filter type="subtree">{subtree_xml}</filter></get>'
        f'</rpc>'
    )


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
#                exactly what travels on the manager<->fleet CoAP hop.

NETCONF_FRAMING_BYTES = 88   # representative SSH record + TCP/IP overhead
COAP_FRAMING_BYTES = 8       # ~4-byte CoAP header + Uri-Path/Content-Format opts


def sizes(netconf_xml, coreconf_obj, coreconf_is_seq=False):
    """Measure and compare NETCONF vs CORECONF encodings of one operation."""
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
    return {
        "netconf": {"payload": nc_p, "wire": nc_w, "xml": netconf_xml},
        "coreconf": {"payload": cc_p, "wire": cc_w},
        "ratio_payload": round(nc_p / cc_p, 1) if cc_p else None,
        "ratio_wire": round(nc_w / cc_w, 1) if cc_w else None,
    }
