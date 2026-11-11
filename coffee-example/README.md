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
| `coffee_sids.py` | Shared constants: CORECONF SIDs, CBOR helpers, NETCONF (XML) / RESTCONF (JSON) / CORECONF encoders, and the protocol-list-driven **size** and **processing-cost (CPU)** engines (`sizes()` / `processing_costs()`, CORECONF baseline). |
| `server.py` | Plain (NoSec) CORECONF fleet datastore: `GET`/`FETCH`/`iPATCH`/`POST` on `/c`. Seeds four makers. A brew holds the `brewing` state for a few seconds (`BREW_DURATION`). |
| `client.py` | CLI client: reads the fleet, turns a maker on, brews, reads back, turns off. |
| `bench_processing.py` | CPU micro-benchmark: times decode + schema-dispatch + encode for each operation, comparing NETCONF vs RESTCONF vs CORECONF server-side processing cost (ratios vs CORECONF). `--fleet-size N` adds a large-GET comparison to show how each format scales with payload size. |
| `webui/web_console.py` | Stdlib-only web server: runs operations, streams message events, and serves a fleet snapshot for the dashboard. |
| `webui/flow_client.py` | Instrumented client that emits one JSON event per hop (request + response) with both encodings' sizes. |
| `webui/index.html` | The UI: a top fleet dashboard (one ☕ icon per maker + maker cards), Manager Operations controls below it with a live-populated **Maker id** dropdown, an animated manager&harr;fleet CORECONF hop, a messages pane (NETCONF/RESTCONF simulated messages toggleable), and side-by-side **size** and **processing-cost (CPU)** panels comparing NETCONF vs RESTCONF vs CORECONF. |
| `setup_security.py` | Generates OSCORE security contexts for two users (alice, bob). |
| `secure_server.py` | OSCORE-protected fleet server with per-user roles (operator vs. viewer). |
| `secure_client.py` | OSCORE client demonstrating an authorized write (alice) and a denied write (bob). |
| `run.sh` / `run.bat` / `run.ps1` / `run.cmd` / `Dockerfile` | One-command launchers for the web console (`run.ps1`/`run.cmd` are the native-Windows path — see `WINDOWS.md`). |
| `DOCKER_SHARING.md` | Guide for sharing the Docker image and run instructions for recipients (build, export tarball, or push to a registry). |
| `WINDOWS.md` | Native Windows 11 guide (no WSL/Docker): prerequisites, `run.ps1`/`run.cmd`, env vars, and packaging as a source zip or offline vendored-deps bundle. |

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
  brew (out of water / out of beans / powered off). A successful brew puts the
  maker into the **`brewing`** state for a few seconds (`BREW_DURATION`, 6s by
  default); during that window `state` reports `brewing`, then it returns to
  `idle`. `refill` ("add coffee")
  tops the maker's beans and water back to 100% and clears any fault,
  returning the new `beans-level`/`water-level`.

## Run the web UI

Self-contained — needs **either** Python 3.9+ **or** Docker.

### Option A — one-command launcher (needs Python 3.9+)

```bash
# macOS / Linux
./run.sh
```
```powershell
# Windows 11 (native, no WSL/Docker) — see WINDOWS.md
.\run.ps1
:: or from cmd.exe
run.cmd
```

Creates `.venv/`, installs `aiocoap` + `cbor2` on first run, then serves
http://localhost:8080. Set `WEBUI_PORT=9000 ./run.sh` to change the port.
On native Windows, follow [`WINDOWS.md`](WINDOWS.md) — it covers prerequisites
(Python **3.10+**, no build tools needed), the `run.ps1`/`run.cmd` launchers,
the `COAP_BIND_HOST`/`WEBUI_HOST` environment variables, and how to package the
example for a WSL-less machine (source zip or an offline vendored-wheel
bundle).

### Option B — Docker (no Python needed on the host)

```bash
docker build -t coffee-coreconf .
docker run --rm -p 8080:8080 coffee-coreconf
```

Then open http://localhost:8080.

> **Sharing the image?** See [`DOCKER_SHARING.md`](DOCKER_SHARING.md) for how
> to distribute the containerized simulator (build from source, export a
> tarball, or push to a registry) and copy/paste run instructions to give to
> whoever runs it.

### Using it

1. Click **Start manager + fleet** (launches `server.py`, the fleet
   datastore seeded with four makers).
2. The **Coffee Makers** dashboard sits at the top of the page and shows a
   row of one ☕ icon per maker (a new icon pops in when you add one) above a
   card per maker: power, state, water/bean meters, whether it still **has
   coffee**, and cups brewed. Brewing a maker flips its **state** pill to a
   blue **brewing** for a few seconds — the dashboard auto-refreshes during
   that window and the pill returns to **idle** when the brew finishes.
3. **Act on a maker:** the **Manager Operations** controls sit below the
   dashboard. Pick a maker from the **Maker id** dropdown (populated live from
   the fleet — or click a card/icon to select it) and power it on/off,
   **brew**, **add coffee** (refill beans + water — the button turns red when a
   maker is low on or out of coffee), or change cups/strength.
   **Add** a brand-new maker too.
4. Each action animates on the **manager → fleet** CORECONF hop. The
   **Messages** pane shows the real CORECONF (CBOR/SID) message plus the
   equivalent **simulated NETCONF (XML)** and **RESTCONF (JSON)** messages, so
   their relative verbosity is obvious. Toggle **NETCONF** or **RESTCONF** off
   to hide those.
5. The dashboard refreshes and the side-by-side **size** and **processing-cost
   (CPU)** panels compare NETCONF (XML) vs RESTCONF (JSON) vs CORECONF
   (CBOR/SID) — three bars per operation, with ratios against CORECONF. A read
   is shown as two blocks, **Read fleet — request** and **Read fleet —
   response**; on the request side RESTCONF and CORECONF send no body, so those
   bars read "no body (headers only)" unless you include transport framing.

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
    RESTCONF (JSON)     payload=  35 B  wire= 185 B
    CORECONF (CBOR/SID) payload=  21 B  wire=  29 B
    -> CORECONF is 13.6x smaller than NETCONF (payload), 12.9x (wire)
iPATCH turn 'lab' ON -> 2.04 Changed
POST brew 'lab' -> started=True reason=''
```

The server **seeds the fleet on startup** with four makers (`kitchen`,
`lobby`, `lab`, `breakout`) at different water/bean levels, so a fresh `get`
returns a realistic fleet — including one maker that is out of water.

## Compare processing cost (CPU), not just bytes

The web UI's size panel answers *"how many bytes?"*. `bench_processing.py`
answers the companion question *"how much CPU does the server spend handling
the message?"* for the same operations — across **three** management
protocols: NETCONF (XML), RESTCONF (JSON), and CORECONF (CBOR/SID).

```bash
python3 bench_processing.py                 # table, 2000 iterations/stage
python3 bench_processing.py --iterations 5000
python3 bench_processing.py --json          # machine-readable
```

It runs entirely in-process (no network/SSH/HTTP/UDP) and times the three
stages where the encodings actually differ, for each operation:

| Stage | NETCONF | RESTCONF | CORECONF |
|-------|---------|----------|----------|
| **decode**   | parse XML (`xml.etree.ElementTree`) | parse JSON (`json`) | decode CBOR (`cbor2`) |
| **dispatch** | element local-name → schema (string-key) | JSON key → schema (string-key) | numeric SID → schema (int-key) |
| **encode**   | serialize XML | dump JSON | dump CBOR |

The datastore-apply logic is identical under every protocol, so it is left
out to keep the comparison apples-to-apples. **CORECONF is the baseline**;
each ratio is that protocol's cost relative to CORECONF. Example run (numbers
vary by machine):

```
operation            protocol                decode  dispatch    encode     total  ratio
----------------------------------------------------------------------------------------
get (read fleet)
                     NETCONF (XML)             7.21      1.12     17.79     26.13   16.1x
                     RESTCONF (JSON)           0.00      0.00      0.00      0.00    0.0x
                     CORECONF (CBOR/SID)       0.68      0.12      0.81      1.62
...
TOTAL (all ops)
                     NETCONF (XML)                                         283.80    7.0x
                     RESTCONF (JSON)                                        30.43    0.8x
                     CORECONF (CBOR/SID)                                    40.49
```

So **NETCONF costs roughly 7× the server CPU of CORECONF**, dominated by XML
parsing and serialization. **RESTCONF/JSON is competitive with CORECONF on
CPU** — at these small message sizes CPython's C-accelerated `json` module can
match or even beat `cbor2`, even though RESTCONF's *bytes on the wire* are much
larger than CORECONF's (full node names + HTTP framing). That split — RESTCONF
loses on size but not on CPU — is exactly why both panels are worth showing.
The core logic lives in `processing_costs()` in `coffee_sids.py`, alongside
the size engine; the same numbers are surfaced live in the web UI's **Server
Processing Cost (CPU)** panel next to the size panel.

### Scaling with payload size (`--fleet-size`)

A natural question is whether CORECONF overtakes RESTCONF on CPU once messages
get big. Benchmark a large read with `--fleet-size`:

```bash
python3 bench_processing.py --fleet-size 200 --iterations 400
```

This adds a "get large fleet (200 makers)" row — a GET *response* carrying 200
makers, where payload size actually scales. A representative run:

```
operation                      protocol           decode  dispatch   encode    total  ratio
get large fleet (200 makers)
                               NETCONF (XML)       723.9    365.9   2341.7   3431.4   2.3x
                               RESTCONF (JSON)     170.8    402.0    242.0    814.8   0.6x
                               CORECONF (CBOR/SID) 255.5    427.7    793.6   1476.9
```

At this scale (payloads of **XML ≈ 56 kB, JSON ≈ 35 kB, CBOR ≈ 14 kB**):

- **CORECONF decode is faster than JSON** (CBOR ~175–264 µs vs JSON ~359 µs) —
  the expected codec advantage shows up clearly on the read path.
- **Encode is roughly a tie** (`cbor2.dumps` ≈ `json.dumps`), so RESTCONF stays
  competitive on *total* CPU even for large payloads.
- **CORECONF's decisive, scaling win is bytes on the wire** — ~2.5× smaller
  than JSON and ~4× smaller than XML here. That (plus smaller code/RAM on
  constrained devices) is the real CORECONF story, more than raw server µs.

### What the "Option 1" (C accelerator) check found

The CPU numbers already use **C-accelerated codecs on both sides**: CPython's
built-in `json` C scanner and `cbor2`'s compiled `_cbor2` extension (verify
with `python3 -c "import cbor2, types;
print(isinstance(cbor2.loads, types.BuiltinFunctionType))"` → `True`). So the
near-parity between RESTCONF and CORECONF is **not** a missing-accelerator
artifact — it reflects genuine library behaviour at these sizes, where fixed
per-call overhead and a very well-tuned JSON encoder keep JSON close to CBOR.
`decode_cbor_seq()` was also made O(n) (single in-place `BytesIO`) so the real
servers and the benchmark both measure the codec rather than buffer re-slicing.

Caveats:

- The ratio reflects these specific Python libraries
  (`xml.etree.ElementTree`, `json`, and `cbor2`), not the protocols in the
  abstract. Swap in `lxml`, `orjson`, or a C stack and the numbers change.
- **Transport and crypto are excluded** (SSH/TLS and HTTP/TLS session setup vs
  per-message CoAP/OSCORE). Those are a separate axis; see the OSCORE section
  below for the secured CORECONF server you could extend the benchmark to
  measure.

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
