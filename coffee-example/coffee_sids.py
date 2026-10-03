"""
Shared definitions for the CORECONF coffee-maker example.

CORECONF (draft-ietf-core-comi) manages YANG datastores over CoAP using
CBOR-encoded payloads (RFC 9254). Instead of long string paths, every
schema node is identified by a numeric YANG SID (RFC 9595). These
constants come straight from example-coffee-maker@2026-09-14.sid.
"""

# ---- SIDs from the .sid file ----
SID_COFFEE_MAKER = 60010
SID_POWER = 60011
SID_CUPS = 60012
SID_STRENGTH = 60013
SID_STATE = 60014
SID_WATER_LEVEL = 60015
SID_BREW = 60016
SID_BREW_STARTED = 60017

# identity SIDs
SID_IDLE = 60002
SID_BREWING = 60003
SID_OFF = 60004

# Inside a container, child SIDs are encoded as deltas from the parent
# SID (RFC 9254 Section 4.2.1). We keep it simple in this demo and use
# absolute SIDs in the top-level map, which is also valid.

# strength enum <-> integer mapping (YANG-to-CBOR maps enums to their
# position or an explicit value; we use position here).
STRENGTH_TO_INT = {"mild": 0, "medium": 1, "strong": 2}
INT_TO_STRENGTH = {v: k for k, v in STRENGTH_TO_INT.items()}

# CoAP Content-Formats defined by CORECONF. IANA numbers per the draft.
CF_YANG_DATA_CBOR = 140          # application/yang-data+cbor; id=sid
CF_YANG_IDENTIFIERS_SEQ = 141    # application/yang-identifiers+cbor-seq
CF_YANG_INSTANCES_SEQ = 142      # application/yang-instances+cbor-seq

# Datastore resource path used by the server.
DATASTORE_PATH = "c"
