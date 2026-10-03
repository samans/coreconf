"""
Shared definitions for the CORECONF 802.11 Wi-Fi hotspot example.

CORECONF (draft-ietf-core-comi) manages YANG datastores over CoAP using
CBOR-encoded payloads (RFC 9254). Instead of long string paths, every
schema node is identified by a numeric YANG SID (RFC 9595). These
constants come straight from example-wifi-hotspot@2026-10-04.sid.

This revision models a keyed *list* of hotspots. The datastore shape is:

    { 70010 (hotspots): { 70011 (hotspot): [
        { 70012 (name): "lobby", 70013 (enabled): true, ... },
        { 70012 (name): "garage", ... }
    ] } }

A CORECONF list is encoded as a CBOR array of maps; each map holds the
key leaf plus the other leaves (RFC 9254).
"""

# ---- container / list SIDs ----
SID_HOTSPOTS = 70010         # container
SID_HOTSPOT = 70011          # list
SID_NAME = 70012             # key leaf

# ---- per-hotspot leaf SIDs ----
SID_ENABLED = 70013
SID_SSID = 70014
SID_BAND = 70015
SID_CHANNEL = 70016
SID_TX_POWER = 70017
SID_LATENCY = 70018          # writable target latency (ms)
SID_STATE = 70019
SID_ASSOCIATED_STATIONS = 70020

# identity SIDs
SID_DOWN = 70002
SID_SCANNING = 70003
SID_ACTIVE = 70004

# band enum <-> integer mapping (positional, as in the coffee example).
BAND_TO_INT = {"band-2g4": 0, "band-5g": 1, "band-6g": 2}
INT_TO_BAND = {v: k for k, v in BAND_TO_INT.items()}

# operational radio state identity names, for pretty-printing.
STATE_NAMES = {SID_DOWN: "down", SID_SCANNING: "scanning", SID_ACTIVE: "active"}

# CoAP Content-Formats defined by CORECONF. IANA numbers per the draft.
CF_YANG_DATA_CBOR = 140          # application/yang-data+cbor; id=sid
CF_YANG_IDENTIFIERS_SEQ = 141    # application/yang-identifiers+cbor-seq
CF_YANG_INSTANCES_SEQ = 142      # application/yang-instances+cbor-seq

# Datastore resource path used by the server.
DATASTORE_PATH = "c"
