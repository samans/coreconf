# CORECONF Coffee-Maker Fleet Example

A runnable example that manages a **fleet of coffee makers** from a
**coffee-maker manager**, modeled in YANG and driven over **CORECONF**
(`draft-ietf-core-comi`) — YANG data over CoAP with CBOR payloads and numeric
SIDs (RFC 9254 / RFC 9595). A browser UI shows the whole fleet, lets you power
makers on/off, brew, and watch each CORECONF message pass between the manager
and the fleet datastore. It then adds **user security** with OSCORE
(RFC 8613) plus per-user authorization.

```
[coffee-maker manager] --CORECONF--> [coffee-maker fleet datastore]
```

## What's here

| File | Purpose |
|------|---------|
| `yang/example-coffee-maker@2026-10-18.yang` | The YANG model: a `coffee-maker-manager` container owning a keyed **`coffee-maker` list**. Each maker has writable `power`, `cups`, `strength`, `location`; read-only `state`, `water-level`, `beans-level`, `has-coffee`, `cups-brewed`, `last-error`; and a `brew` action. |
| `yang/example-coffee-maker@2026-10-18.sid` | SID file mapping every schema node to a numeric YANG SID. |
| `yang/example-coffee-maker@2026-09-14.yang` + `.sid` | Previous single-maker revision, kept for history. |
| `coffee_sids.py` | Shared constants: CORECONF SIDs, CBOR helpers, NETCONF/CORECONF encoders, and the **size-comparison engine**. |
| `server.py` | Plain (NoSec) CORECONF fleet datastore: `GET`/`FETCH`/`iPATCH`/`POST` on `/c`. Seeds four makers. |
| `client.py` | CLI client: reads the fleet, turns a maker on, brews, reads back, turns off. |
| `webui/web_console.py` | Stdlib-only web server: runs operations, streams message events, and serves a fleet snapshot for the dashboard. |
| `webui/flow_client.py` | Instrumented client that emits one JSON event per hop (request + response) with both encodings' sizes. |
| `webui/index.html` | The UI: a live dashboard of maker cards, an animated manager&harr;fleet CORECONF hop, a messages pane, and a size-comparison panel. |
| `setup_security.py` | Generates OSCORE security contexts for two users (alice, bob). |
| `secure_server.py` | OSCORE-protected fleet server with per-user roles (operator vs. viewer). |
| `secure_client.py` | OSCORE client demonstrating an authorized write (alice) and a denied write (bob). |
| `run.sh` / `run.bat` / `Dockerfile` | One-command launchers for the web console. |

## The YANG model

```
container coffee-maker-manager {
  leaf name         string(1..32)
  leaf maker-count  uint8            (config false)
  list coffee-maker {
    key "id";
    leaf id          string(1..32)   // list key
    leaf location    string(0..64)
    leaf power       boolean
    leaf cups        uint8(1..12)
    leaf strength    enum{mild,medium,strong}
    leaf state       identityref     (config false)  // off|idle|brewing|no-water|no-beans|error
    leaf water-level uint8 %          (config false)
    leaf beans-level uint8 %          (config false)
    leaf has-coffee  boolean          (config false)  // water AND beans available
    leaf cups-brewed uint32           (config false)
    leaf last-error  string           (config false)
    action brew { output { leaf started boolean; leaf reason string; } }
    action refill { input  { leaf beans boolean; leaf water boolean; }
                    output { leaf beans-level uint8; leaf water-level uint8; } }
  }
}
```

SIDs use the example range `60000+` (real modules get SIDs from a registered
range, RFC 9595).

## How CORECONF works here

The fleet datastore lives at a single CoAP resource (`/c`). Payloads are CBOR
maps keyed by SID; the `coffee-maker` list is a CBOR **array** of per-maker
maps:

- **GET `/c`** → full datastore:
  `{60010: {60011: "barista-1", 60012: 4, 60020: [ {60021: "kitchen", 60023: true, ...}, ... ]}}`
  (`60010` = `coffee-maker-manager`, `60020` = `coffee-maker` list,
  `60021` = `id`, `60023` = `power`, …).
- **FETCH `/c`** → selected instance-values (whole subtree in this demo).
- **iPATCH `/c`** → set manager/maker leaves or add a maker. Each maker is
  addressed by its `id` key: `{60010: {60020: [{60021: "lab", 60023: true}]}}`
  **turns the `lab` maker on**.
- **POST `/c`** → invokes a maker's `brew` or `refill` action; the request
  selects the maker by `id` and carries the action SID (`brew` = 60032,
  `refill` = 60035). `brew` reports `started` plus a `reason` if it could not
  brew (out of water / out of beans / powered off); `refill` ("add coffee")
  tops the maker's beans and water back to 100% and clears any fault,
  returning the new `beans-level`/`water-level`.

## Run the web UI

Self-contained — needs **either** Python 3.9+ **or** Docker.

### Option A — one-command launcher (needs Python 3.9+)

```bash
# macOS / Linux
./run.sh
:: Windows
run.bat
```

Creates `.venv/`, installs `aiocoap` + `cbor2` on first run, then serves
http://localhost:8080. Set `WEBUI_PORT=9000 ./run.sh` to change the port.

### Option B — Docker (no Python needed on the host)

```bash
docker build -t coffee-coreconf .
docker run --rm -p 8080:8080 coffee-coreconf
```

Then open http://localhost:8080.

### Using it

1. Click **Start manager + fleet** (launches `server.py`, the fleet
   datastore seeded with four makers).
2. The **Coffee Makers** dashboard shows a card per maker: power, state,
   water/bean meters, whether it still **has coffee**, and cups brewed.
3. **Act on a maker:** enter its `id` (or click a card button) and power it
   on/off, **brew**, **add coffee** (refill beans + water — the button turns
   red when a maker is low on or out of coffee), or change cups/strength.
   **Add** a brand-new maker too.
4. Each action animates on the **manager → fleet** CORECONF hop. The
   **Messages** pane shows the real CORECONF (CBOR/SID) message plus the
   equivalent **simulated NETCONF (XML)** message, pretty-printed with line
   breaks so its verbosity is obvious. Untick **show NETCONF** to hide the
   NETCONF messages.
5. The dashboard refreshes and the **size comparison** panel shows NETCONF
   (XML) vs CORECONF (CBOR/SID) bytes with a running "bytes saved" total.

## Run the plain CLI example

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# terminal 1
python3 server.py
# terminal 2
python3 client.py
```

Expected client output (abbreviated):

```
GET -> manager='barista-1', 4 maker(s):
   {'id': 'kitchen', 'power': True, 'state': 'idle', 'water_level': 85, 'has_coffee': True, ...}
   {'id': 'breakout', 'state': 'no-water', 'water_level': 5, 'has_coffee': False, ...}
  size for "set maker 'lab' power=True":
    NETCONF  (XML)      payload= 285 B  wire= 373 B
    CORECONF (CBOR/SID) payload=  21 B  wire=  29 B
    -> CORECONF is 13.6x smaller (payload), 12.9x (wire)
iPATCH turn 'lab' ON -> 2.04 Changed
POST brew 'lab' -> started=True reason=''
```

The server **seeds the fleet on startup** with four makers (`kitchen`,
`lobby`, `lab`, `breakout`) at different water/bean levels, so a fresh `get`
returns a realistic fleet — including one maker that is out of water.

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
[alice] GET -> {'id': 'kitchen', 'power': True, ...}
[alice] iPATCH turn 'kitchen' ON -> 2.04 Changed
=== bob (viewer, read-only) ===
[bob] GET -> {'id': 'kitchen', 'power': True, ...}
[bob] iPATCH turn 'kitchen' ON -> 4.03 Forbidden (role 'viewer' is read-only)
```

### Where ACE-OAuth would fit

In `setup_security.py` we write OSCORE keys to disk for convenience. In a
real deployment, a client would obtain an access token from an
**Authorization Server** (RFC 9200); the token establishes the OSCORE
security context and carries the scope/role that `secure_server.py` enforces
in `_authorize()`.

## Notes / simplifications

- SIDs use the example range `60000+`. Real modules get SIDs from a
  registered range (RFC 9595).
- The top-level payload uses absolute SIDs for readability; RFC 9254 also
  allows delta-encoding child SIDs relative to the parent.
- The datastore is in-memory; there is no persistence or NMDA datastore
  separation. Water/bean levels are decremented per brewed cup to simulate
  real consumption.
- The server is NoSec (plain CoAP); see the OSCORE variant above for the
  secured version.
