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


def _xml_escape(text):
    """Escape XML character-data special characters so values such as
    'R&D Lab' produce well-formed XML (and realistic bytes)."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _xml_val(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return _xml_escape(value)


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
# RESTCONF (HTTP + JSON) encoders for the SAME operations — comparison only
# =========================================================================
#
# RESTCONF (RFC 8040) carries YANG data over HTTP as JSON (RFC 7951). Keys
# are the full YANG node names (module-qualified at the top level), so it is
# more compact than NETCONF/XML but far more verbose than CORECONF/CBOR+SID,
# which uses numeric SIDs. These builders return the JSON *body* text for an
# operation; `restconf_sizes()`-style measurement adds the HTTP request-line
# + headers separately (see HTTP_FRAMING_BYTES).

import json as _json

_RC_MODULE = "example-coffee-maker"   # YANG module name (RFC 7951 namespace)


def _rc_leaf_name(sid):
    """Map a CORECONF SID to its RESTCONF/JSON leaf name."""
    return SID_NAMES.get(sid, str(sid))


def _rc_dumps(obj):
    """Serialize a RESTCONF JSON body compactly (no superfluous spaces), the
    way an on-the-wire RESTCONF message would be framed."""
    return _json.dumps(obj, separators=(",", ":"))


def restconf_maker_leaf(maker_id, leaf_name, value):
    """RESTCONF body setting one leaf on one maker (JSON, RFC 7951).

    The HTTP request would be e.g.
        PUT /restconf/data/example-coffee-maker:coffee-maker-manager/
            coffee-maker=<id>/<leaf>
    with this JSON body selecting the target leaf."""
    return _rc_dumps({f"{_RC_MODULE}:{leaf_name}": value})


def restconf_maker_entry(maker_id, leaves=None):
    """RESTCONF body for a whole coffee-maker list entry (JSON, RFC 7951).

    The HTTP request would be e.g.
        POST /restconf/data/example-coffee-maker:coffee-maker-manager
    with this list-entry body."""
    entry = {"id": maker_id}
    for k, v in (leaves or {}).items():
        entry[k] = v
    return _rc_dumps({f"{_RC_MODULE}:coffee-maker": [entry]})


def restconf_action(maker_id, action_name, input_obj=None):
    """RESTCONF body invoking a YANG action on one maker (JSON, RFC 7951).

    The HTTP request would be e.g.
        POST /restconf/data/example-coffee-maker:coffee-maker-manager/
             coffee-maker=<id>/<action>
    with an (often empty) input container as the body."""
    return _rc_dumps({f"{_RC_MODULE}:input": (input_obj or {})})


def restconf_get_empty():
    """A RESTCONF GET has no request body; the request cost is the URL + HTTP
    headers (HTTP_FRAMING_BYTES). The body text is therefore empty."""
    return ""


# =========================================================================
# Size-comparison engine
# =========================================================================
#
# For a given semantic operation we serialize the SAME change three ways and
# measure the real byte length of each encoding:
#
#   * NETCONF  : an <edit-config>/<get> RPC in XML (RFC 6241).
#   * RESTCONF : a JSON body over HTTP (RFC 8040 / RFC 7951) — full YANG node
#                names as keys.
#   * CORECONF : a CBOR map keyed by numeric SIDs (RFC 9254/9595), which is
#                exactly what travels on the manager<->fleet CoAP hop.
#
# CORECONF is the baseline; ratios express how many times larger / more
# expensive each other protocol is relative to it.

NETCONF_FRAMING_BYTES = 88    # representative SSH record + TCP/IP overhead
HTTP_FRAMING_BYTES = 150      # representative HTTP/1.1 request line + headers
COAP_FRAMING_BYTES = 8        # ~4-byte CoAP header + Uri-Path/Content-Format opts

# The baseline every comparison ratio is measured against.
BASELINE_PROTOCOL = "coreconf"

# Ordered protocol metadata so the engines, CLI, and UI can iterate rather
# than hard-coding "netconf vs coreconf". 'kind' tells the CPU engine which
# codec/dispatch path to time for each protocol.
PROTOCOLS = [
    {"id": "netconf",  "label": "NETCONF (XML)",   "kind": "xml",
     "framing": NETCONF_FRAMING_BYTES},
    {"id": "restconf", "label": "RESTCONF (JSON)", "kind": "json",
     "framing": HTTP_FRAMING_BYTES},
    {"id": "coreconf", "label": "CORECONF (CBOR/SID)", "kind": "cbor",
     "framing": COAP_FRAMING_BYTES},
]
PROTOCOL_IDS = [p["id"] for p in PROTOCOLS]
_PROTO_BY_ID = {p["id"]: p for p in PROTOCOLS}


def _as_bytes(text_or_bytes):
    if isinstance(text_or_bytes, (bytes, bytearray)):
        return bytes(text_or_bytes)
    return str(text_or_bytes).encode("utf-8")


def _coreconf_bytes(coreconf_obj, is_seq):
    if is_seq:
        return coreconf_obj if isinstance(coreconf_obj, (bytes, bytearray)) \
            else cbor_seq(coreconf_obj)
    return cbor2.dumps(coreconf_obj)


def sizes(netconf_xml, restconf_json, coreconf_obj, coreconf_is_seq=False):
    """Measure and compare NETCONF / RESTCONF / CORECONF encodings of one
    operation.

    Returns a protocol-list-driven dict (CORECONF is the baseline):

        {
          "baseline": "coreconf",
          "protocols": {
             "netconf":  {"payload", "wire", "repr": <xml str>},
             "restconf": {"payload", "wire", "repr": <json str>},
             "coreconf": {"payload", "wire", "repr": None},
          },
          "ratios_payload": {"netconf": x, "restconf": y},   # vs coreconf
          "ratios_wire":    {"netconf": x, "restconf": y},
        }
    """
    raw = {
        "netconf": _as_bytes(netconf_xml),
        "restconf": _as_bytes(restconf_json),
        "coreconf": _as_bytes(_coreconf_bytes(coreconf_obj, coreconf_is_seq)),
    }
    reprs = {"netconf": netconf_xml, "restconf": restconf_json,
             "coreconf": None}

    protocols = {}
    for p in PROTOCOLS:
        pid = p["id"]
        payload = len(raw[pid])
        protocols[pid] = {
            "payload": payload,
            "wire": payload + p["framing"],
            "repr": reprs[pid],
        }

    base_p = protocols[BASELINE_PROTOCOL]["payload"]
    base_w = protocols[BASELINE_PROTOCOL]["wire"]

    def _ratio(a, b):
        return round(a / b, 1) if b else None

    ratios_payload = {pid: _ratio(protocols[pid]["payload"], base_p)
                      for pid in PROTOCOL_IDS if pid != BASELINE_PROTOCOL}
    ratios_wire = {pid: _ratio(protocols[pid]["wire"], base_w)
                   for pid in PROTOCOL_IDS if pid != BASELINE_PROTOCOL}

    return {
        "baseline": BASELINE_PROTOCOL,
        "protocols": protocols,
        "ratios_payload": ratios_payload,
        "ratios_wire": ratios_wire,
    }


# =========================================================================
# Processing-cost (CPU) comparison engine
# =========================================================================
#
# The size engine above measures *bytes on the wire*. This engine measures
# the *server-side CPU* needed to handle the SAME semantic operation under
# each protocol, isolating the three stages where the encodings actually
# differ (the datastore-apply logic is identical and is deliberately left
# out so the comparison is apples-to-apples):
#
#   1. decode   — turn the received message bytes into an in-memory tree.
#                   NETCONF : parse XML text   (xml.etree.ElementTree)
#                   RESTCONF: parse JSON text  (json.loads)
#                   CORECONF: decode CBOR bytes (cbor2)
#   2. dispatch — resolve every node in the message to its schema node.
#                   NETCONF : namespaced element localname -> schema (string
#                             key lookup, after stripping the "{ns}" prefix)
#                   RESTCONF: JSON object key -> schema (string key lookup,
#                             after stripping any "module:" prefix)
#                   CORECONF: numeric SID -> schema          (int key lookup)
#   3. encode   — serialize the in-memory tree back to message bytes.
#                   NETCONF : build XML text
#                   RESTCONF: dump JSON text
#                   CORECONF: dump CBOR bytes
#
# Everything runs in-process so there is no network, SSH, or UDP noise: the
# number reflects pure codec + schema-dispatch cost. Transport and crypto
# (SSH/TLS vs CoAP/OSCORE) are intentionally excluded — see the README for
# how to extend the comparison to those. CORECONF is the baseline.
#
# Caveat: the ratio reflects these specific Python implementations
# (xml.etree.ElementTree, json, and cbor2), not the protocols in the
# abstract.

import time
import xml.etree.ElementTree as ET
import json as _json_cpu

# name -> schema-node lookup table, modelling the server's schema index. The
# "schema node" payload is irrelevant to the cost; what matters is a string
# key (NETCONF) vs an int key (CORECONF) lookup, so both tables are built
# from the one SID_NAMES map to stay in lock-step with the real model.
_CC_SCHEMA = {sid: name for sid, name in SID_NAMES.items()}        # int  -> node
_NC_SCHEMA = {name: sid for sid, name in SID_NAMES.items()}        # name -> node


def _localname(tag):
    """Strip an XML '{namespace}local' tag down to 'local'."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _nc_dispatch(elem):
    """Walk a parsed NETCONF tree and resolve each element to its schema
    node by local name — the string-keyed lookup a NETCONF server performs."""
    hits = 0
    for node in elem.iter():
        if _NC_SCHEMA.get(_localname(node.tag)) is not None:
            hits += 1
    return hits


def _cc_dispatch(obj):
    """Walk a decoded CORECONF structure and resolve each SID key to its
    schema node — the int-keyed lookup a CORECONF server performs."""
    hits = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, int) and _CC_SCHEMA.get(k) is not None:
                hits += 1
            hits += _cc_dispatch(v)
    elif isinstance(obj, list):
        for v in obj:
            hits += _cc_dispatch(v)
    return hits


def _rc_localname(key):
    """Strip a RESTCONF/JSON 'module:local' key down to 'local'."""
    return key.split(":", 1)[-1] if ":" in key else key


def _rc_dispatch(obj):
    """Walk a decoded RESTCONF (JSON) structure and resolve each object key
    to its schema node by name — the string-keyed lookup a RESTCONF server
    performs (after stripping any 'module:' prefix)."""
    hits = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if _NC_SCHEMA.get(_rc_localname(k)) is not None:
                hits += 1
            hits += _rc_dispatch(v)
    elif isinstance(obj, list):
        for v in obj:
            hits += _rc_dispatch(v)
    return hits


def _time_us(fn, iterations):
    """Run fn() `iterations` times, return mean microseconds per call."""
    best = None
    # a few repeats, keep the fastest batch to damp scheduler/GC jitter
    for _ in range(5):
        start = time.perf_counter()
        for _ in range(iterations):
            fn()
        elapsed = time.perf_counter() - start
        if best is None or elapsed < best:
            best = elapsed
    return (best / iterations) * 1e6


def _xml_stage_times(xml_text, iterations):
    raw = _as_bytes(xml_text)
    decode = _time_us(lambda: ET.fromstring(raw), iterations)
    tree = ET.fromstring(raw)
    dispatch = _time_us(lambda: _nc_dispatch(tree), iterations)
    encode = _time_us(lambda: ET.tostring(tree, encoding="utf-8"), iterations)
    return decode, dispatch, encode


def _json_stage_times(json_text, iterations):
    raw = _as_bytes(json_text)
    if not raw:
        return 0.0, 0.0, 0.0   # empty body (e.g. a RESTCONF GET request)
    decode = _time_us(lambda: _json_cpu.loads(raw), iterations)
    obj = _json_cpu.loads(raw)
    dispatch = _time_us(lambda: _rc_dispatch(obj), iterations)
    encode = _time_us(lambda: _json_cpu.dumps(obj, separators=(",", ":")),
                      iterations)
    return decode, dispatch, encode


def _cbor_stage_times(coreconf_obj, is_seq, iterations):
    raw = _coreconf_bytes(coreconf_obj, is_seq)
    raw_b = bytes(raw)
    if is_seq:
        decode = _time_us(lambda: decode_cbor_seq(raw_b), iterations)
        obj = decode_cbor_seq(raw_b)
        obj = obj[0] if len(obj) == 1 else obj
    else:
        decode = _time_us(lambda: cbor2.loads(raw_b), iterations)
        obj = coreconf_obj
    dispatch = _time_us(lambda: _cc_dispatch(obj), iterations)
    encode = _time_us(lambda: cbor2.dumps(obj), iterations)
    return decode, dispatch, encode


def processing_costs(netconf_xml, restconf_json, coreconf_obj,
                     coreconf_is_seq=False, iterations=2000):
    """Measure and compare server-side CPU for one operation across all
    protocols (CORECONF is the baseline).

    Returns a protocol-list-driven dict mirroring sizes():

        {
          "iterations": int,
          "baseline": "coreconf",
          "protocols": {
             "<id>": {"decode_us", "dispatch_us", "encode_us", "total_us"},
             ...
          },
          "ratios_total": {"netconf": x, "restconf": y},   # vs coreconf
        }
    """
    stage_times = {
        "netconf": _xml_stage_times(netconf_xml, iterations),
        "restconf": _json_stage_times(restconf_json, iterations),
        "coreconf": _cbor_stage_times(coreconf_obj, coreconf_is_seq,
                                      iterations),
    }

    protocols = {}
    for pid in PROTOCOL_IDS:
        decode, dispatch, encode = stage_times[pid]
        total = decode + dispatch + encode
        protocols[pid] = {
            "decode_us": round(decode, 3),
            "dispatch_us": round(dispatch, 3),
            "encode_us": round(encode, 3),
            "total_us": round(total, 3),
        }

    def _ratio(a, b):
        return round(a / b, 1) if b else None

    base_total = protocols[BASELINE_PROTOCOL]["total_us"]
    ratios_total = {pid: _ratio(protocols[pid]["total_us"], base_total)
                    for pid in PROTOCOL_IDS if pid != BASELINE_PROTOCOL}

    return {
        "iterations": iterations,
        "baseline": BASELINE_PROTOCOL,
        "protocols": protocols,
        "ratios_total": ratios_total,
    }
