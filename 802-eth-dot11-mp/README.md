# CORECONF 802.11 Wi-Fi Hotspot Example (`802-eth-dot11-mp`)

A minimal, runnable example that manages an **IEEE 802.11 Wi-Fi hotspot /
access point** modeled in YANG using **CORECONF** (`draft-ietf-core-comi`)
— i.e. YANG data over CoAP with CBOR payloads and numeric SIDs — plus a
**browser UI that visualises the message passing** between the CoAP client
and server.

It is a sibling of `coffee-example`, built the same way but modeling an
802.11 access point bridged onto an 802.3 (Ethernet) uplink.

## What's here

| File | Purpose |
|------|---------|
| `yang/example-wifi-hotspot@2026-10-04.yang` | The current YANG model: a `hotspots` container holding a **keyed list** of `hotspot` entries, each with writable `enabled`, `ssid`, `band`, `channel`, `tx-power`, and a writable **`latency`** target, plus read-only `state`/`associated-stations`. |
| `yang/example-wifi-hotspot@2026-10-03.yang` | The original single-`access-point` revision (kept for history). |
| `yang/*.sid` | SID files mapping every schema node to a numeric YANG SID (RFC 9595). CORECONF uses these instead of long path strings. |
| `wifi_sids.py` | Python constants generated from the current `.sid` file + CoAP content-format numbers. |
| `server.py` | CORECONF simulator (NoSec server): `GET`/`FETCH`/`iPATCH` on `/c`, storing a dict of hotspots. |
| `client.py` | CORECONF client: reads all hotspots, **adds** one, **sets its latency**, enables it. |
| `webui/web_console.py` | Stdlib-only web server that runs the simulator and streams message events to the browser. |
| `webui/flow_client.py` | Instrumented client that emits one JSON event per CoAP message. |
| `webui/index.html` | The UI: start button, an **Add-hotspot form**, a **Set-latency form**, an animated client ↔ server message-flow stage, and a decoded message log. |

## The YANG model

```
container hotspots {
  list hotspot {
    key "name";
    leaf name     string(1..32)    // list key
    leaf enabled  boolean          // writable — the main radio knob
    leaf ssid     string(1..32)    // writable
    leaf band     enum{2g4,5g,6g}  // writable
    leaf channel  uint8(1..196)    // writable
    leaf tx-power uint8(1..30) dBm  // writable
    leaf latency  uint32(0..10000) ms  // writable — target latency you can SET
    leaf state    identityref      // read-only: down | scanning | active
    leaf associated-stations uint16 // read-only
  }
}
```

A YANG list is encoded in CBOR as an array of maps; each map carries the
`name` key plus other leaves. **Adding a hotspot** = iPATCH-ing a new list
entry with a fresh `name`. **Setting latency** = iPATCH-ing an existing
entry with a new `latency` value.

SIDs use the example range `70000+`.

## How CORECONF works here

The datastore lives at a single CoAP resource (`/c`). Payloads are CBOR maps
keyed by SID. The hotspots list is a CBOR **array** of per-hotspot maps:

- **GET `/c`** → full datastore, e.g.
  `{70010: {70011: [ {70012: "default", 70013: false, 70018: 0, ...} ]}}`
  (`70010` = `hotspots`, `70011` = `hotspot` list, `70012` = `name`,
  `70013` = `enabled`, `70018` = `latency`).
- **FETCH `/c`** → client sends a CBOR sequence of SIDs; server returns the
  requested instance-values.
- **iPATCH `/c`** → client sends a `hotspots` → `hotspot` list entry keyed by
  `name`. A new `name` **adds a hotspot**; an existing `name` **sets** the
  leaves you include (e.g. `latency`, `enabled`). A `null` value deletes.

## Run it on any computer

This folder is self-contained — it only needs **either** Python 3.9+ **or**
Docker on the target machine. The local `.venv/` is not required (and is not
shipped); the launchers create it on first run. Pick whichever is easiest:

### Option A — one-command launcher (needs Python 3.9+)

```bash
# macOS / Linux
./run.sh

:: Windows
run.bat
```

The script creates `.venv/`, installs `aiocoap` + `cbor2` on first run, then
serves http://localhost:8080. Set `WEBUI_PORT=9000 ./run.sh` to change the port.

### Option B — Docker (no Python needed on the host)

```bash
docker build -t wifi-coreconf .
docker run --rm -p 8080:8080 wifi-coreconf
```

Then open http://localhost:8080. Everything (web console + CoAP simulator)
runs inside the container; only the HTTP port is published.

### Option C — manual setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 webui/web_console.py        # serves http://localhost:8080
```

### Using it

Open http://localhost:8080, then:

1. Click **Start simulator** (launches `server.py`).
2. **Add a hotspot:** in the *Add a hotspot* form enter a name (e.g. `lobby`),
   optionally an SSID / band / channel / tx-power / latency, and click
   **Add hotspot**.
3. **Set a latency value:** in the *Set latency & radio* form enter the
   hotspot name and a latency in ms, then click **Set latency**. You can also
   **Enable** / **Disable** the radio from here.
4. Click **get** to read back all hotspots.
5. Watch each action's packet animate across the wire from client to access
   point and back, and read the decoded CBOR/SID payloads in the message log.

Operations available: `get`, `fetch`, `add`, `enable`, `disable`,
`set-latency`.

Environment variables: `WEBUI_HOST` (default `127.0.0.1`),
`WEBUI_PORT` (default `8080`).

## Run the plain CLI example

```bash
# terminal 1
python3 server.py
# terminal 2
python3 client.py
```

Expected client output (abbreviated):

```
GET  -> 1 hotspot(s):
        {'name': 'default', 'enabled': False, ... 'latency_ms': 0}
iPATCH add hotspot 'lobby' -> 2.04 Changed
iPATCH set 'lobby' latency=35ms -> 2.04 Changed
iPATCH enable 'lobby' -> 2.04 Changed
GET  -> 2 hotspot(s):
        {'name': 'default', ...}
        {'name': 'lobby', 'enabled': True, 'ssid': 'lobby-guest',
         'band': 'band-5g', 'channel': 36, 'tx_power': 23,
         'latency_ms': 35, 'state': 'active', 'stations': 4}
```

## Notes / simplifications

- SIDs use the example range `70000+`. Real modules get SIDs from a
  registered range (RFC 9595).
- `latency` here is a **writable target/budget** you can set, not a measured
  value. (The earlier `2026-10-03` revision modeled latency as read-only and
  simulated it; the current `2026-10-04` revision makes it settable so a
  manager can enter and apply a value.)
- The datastore is in-memory; there is no persistence or NMDA datastore
  separation. The server seeds one `default` hotspot on startup.
- The server is NoSec (plain CoAP). `draft-ietf-core-comi` states NoSec MUST
  NOT be used in production and recommends OSCORE (RFC 8613); see the
  `coffee-example` for an OSCORE + per-user authorization variant.
