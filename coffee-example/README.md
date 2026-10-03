# CORECONF Coffee-Maker Example

A minimal, runnable example that manages a **coffee maker** modeled in YANG
using **CORECONF** (`draft-ietf-core-comi`) — i.e. YANG data over CoAP with
CBOR payloads and numeric SIDs — and then shows how to add **user security**
with OSCORE (RFC 8613) plus per-user authorization.

## What's here

| File | Purpose |
|------|---------|
| `yang/example-coffee-maker@2026-09-14.yang` | The YANG model: a `coffee-maker` container with a writable `power` leaf (on/off), `cups`, `strength`, read-only `state`/`water-level`, and a `brew` action. |
| `yang/example-coffee-maker@2026-09-14.sid` | SID file mapping every schema node to a numeric YANG SID (RFC 9595). CORECONF uses these instead of long path strings. |
| `coffee_sids.py` | Python constants generated from the `.sid` file + CoAP content-format numbers. |
| `server.py` | Plain (NoSec) CORECONF server: `GET`/`FETCH`/`iPATCH`/`POST` on `/c`. |
| `client.py` | Plain CORECONF client: reads state, turns the maker on, brews, turns it off. |
| `setup_security.py` | Generates OSCORE security contexts for two users (alice, bob). |
| `secure_server.py` | OSCORE-protected server with per-user roles (operator vs. viewer). |
| `secure_client.py` | OSCORE client demonstrating an authorized write (alice) and a denied write (bob). |

## How CORECONF works here

CORECONF replaces RESTCONF's JSON-over-HTTP with **CBOR-over-CoAP**, and
replaces long identifier strings with **numeric SIDs**. The datastore lives
at a single CoAP resource (`/c`). Payloads are CBOR maps keyed by SID:

- **GET `/c`** → server returns the whole datastore as a CBOR map
  `{60010: {60011: false, 60012: 1, ...}}` (`60010` = `coffee-maker`,
  `60011` = `power`, …).
- **FETCH `/c`** → client sends a CBOR sequence of SIDs; server returns
  just those instance-values.
- **iPATCH `/c`** → client sends `{SID: value}` maps to merge/replace;
  a `null` value deletes. **This is how the coffee maker is turned on/off.**
- **POST `/c`** → invokes the `brew` action.

## Run the plain example

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install "aiocoap[oscore]" cbor2

# terminal 1
python3 server.py
# terminal 2
python3 client.py
```

Expected client output (abbreviated):

```
GET  -> {'power': False, ... 'state': 'off'}
iPATCH turn ON -> 2.04 Changed
GET  -> {'power': True, 'cups': 2, 'strength': 'strong', 'state': 'idle'}
POST brew -> started=True
iPATCH turn OFF -> 2.04 Changed
```

## Add user security (OSCORE + authorization)

`draft-ietf-core-comi` states that **NoSec MUST NOT be used** in production
and recommends **OSCORE** (RFC 8613) for object security, optionally with
**ACE-OAuth** (RFC 9200) to provision keys and authorize users.

This example adds two layers:

1. **OSCORE** – every request/response is encrypted and authenticated with
   an AEAD cipher (`AES-CCM-16-64-128`) keyed by a pre-shared security
   context. A network attacker can neither read nor forge "turn on the
   coffee maker" commands.

2. **Per-user authorization** – each OSCORE context maps to a user with a
   role:
   - `alice` → **operator** (read + write)
   - `bob` → **viewer** (read-only; writes rejected with `4.03 Forbidden`)

```bash
python3 setup_security.py     # generate OSCORE contexts (once)

# terminal 1
python3 secure_server.py
# terminal 2
python3 secure_client.py
```

Expected output:

```
=== alice (operator) ===
[alice] GET -> {'power': False, ...}
[alice] iPATCH turn ON -> 2.04 Changed
[alice] GET -> {'power': True, ...}
=== bob (viewer, read-only) ===
[bob] GET -> {'power': True, ...}
[bob] iPATCH turn ON -> 4.03 Forbidden (role 'viewer' is read-only)
```

### Where ACE-OAuth would fit

In `setup_security.py` we write OSCORE keys to disk for convenience. In a
real deployment, a client would obtain an access token from an
**Authorization Server** (RFC 9200); the token establishes the OSCORE
security context and carries the scope/role that `secure_server.py` enforces
in `_authorize()`. The enforcement logic stays the same — only key
provisioning changes.

## Notes / simplifications

- SIDs use the example range `60000+`. Real modules get SIDs from a
  registered range (RFC 9595).
- The top-level payload uses absolute SIDs for readability; RFC 9254 also
  allows delta-encoding child SIDs relative to the parent.
- The datastore is in-memory and single coffee maker; there is no
  persistence or NMDA datastore separation.
