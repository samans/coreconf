# 802 Management Chain — NETCONF vs CORECONF Size Demo (`802-eth-dot11-mp`)

A runnable example that models a three-node network-management chain and
**visualises the message passing between the nodes while comparing the
encoding sizes of NETCONF and CORECONF** for the *same* operation.

```
[Mgmt Station] --NETCONF--> [Switch] --NETCONF--> [Wi-Fi AP] --CORECONF--> [Device]
```

- **Station → Switch** and **Switch → AP** use **NETCONF** (XML over SSH,
  RFC 6241).
- **AP → Device** uses **CORECONF** (`draft-ietf-core-comi`): YANG over
  CoAP with CBOR payloads and numeric SIDs (RFC 9254 / RFC 9595).

A manager action (e.g. "set the AP channel") **cascades** down the whole
chain. The browser UI animates each hop, labels it with its protocol, and
shows the **byte size** of the equivalent NETCONF (XML) and CORECONF
(CBOR/SID) encodings side by side — including a running "bytes saved"
total — so you can see how much more compact CORECONF is.

It is a sibling of `coffee-example`, built the same way.

## Approach: real CoAP transport, modeled NETCONF ("Option B")

The **AP → Device** hop is a *real* CoAP/CBOR/SID exchange against
`server.py`. The two upstream **NETCONF** hops are **modeled** rather than
run over a real SSH/NETCONF stack — but the XML they would carry is
genuinely serialized, so the byte sizes shown are the real sizes of the
equivalent NETCONF messages. This keeps the demo dependency-light
(`aiocoap` + `cbor2` only) while making the size comparison accurate and
defensible.

### Size comparison semantics

For each operation the same change is serialized two ways and measured:

| Encoding | What it is | Example (set channel) |
|----------|-----------|-----------------------|
| **NETCONF (XML)** | an `<edit-config>` / `<get>` RPC | ~215 bytes |
| **CORECONF (CBOR/SID)** | a CBOR map keyed by numeric SIDs | ~14 bytes |

Two numbers are reported per encoding:

- **payload bytes** — the serialized data unit only (headline,
  apples-to-apples). This is the default view.
- **wire bytes** — payload plus a representative transport-framing
  estimate (NETCONF over SSH/TCP ≈ 88 B; CoAP header ≈ 8 B), shown when you
  tick *include transport framing*. Framing is clearly labeled an estimate;
  the CoAP header is real, the NETCONF/SSH overhead is a constant.

**Request vs response direction.** Both directions of the CORECONF hop are
measured, not just the request:

- For **writes** (`set-*`, `enable`/`disable`, `connect`/`disconnect`) the
  *request* carries the data, so one comparison is shown for the downstream
  `iPATCH`.
- For **`get`** the request is tiny (a CORECONF `GET` has an empty payload,
  ~1 byte), so the interesting comparison is the **response body** — the
  whole `wifi-ap` container plus the `device` list. The response hop
  (`device → ap`) is measured using the *real CBOR bytes the server
  returned*, compared against the equivalent NETCONF `<rpc-reply>` XML. With
  the seeded datastore this is roughly **CORECONF 212 B vs NETCONF 642 B
  (~3× smaller)**. So `get` produces two comparison blocks: the (tiny)
  request and the (data-bearing) response.

## What's here

| File | Purpose |
|------|---------|
| `yang/example-switch@2026-10-05.yang` | Switch node model (NETCONF-managed): `name`, `mgmt-address`, `enabled`, `ap-uplink-port`, plus read-only `uplink-up`/`port-count`. |
| `yang/example-wifi-ap@2026-10-05.yang` | Access-point model: a single-radio `wifi-ap` container (`enabled`, `ssid`, `band`, `channel`, `tx-power`, writable `latency`, read-only `state`) owning a keyed **`device`** list. |
| `yang/example-wifi-ap@2026-10-05.sid` | SID file for the AP module — the numeric SIDs used on the CORECONF (AP↔device) hop (RFC 9595). |
| `yang/example-device@2026-10-05.yang` | Device model (CORECONF-managed leaf node): `mac`, `hostname`, `ip-address`, `signal-dbm`, `connected`. |
| `yang/example-wifi-hotspot@2026-10-0{3,4}.yang` + `.sid` | Previous single-/list-hotspot revisions, kept for history. |
| `wifi_sids.py` | Shared constants: CORECONF SIDs, node/protocol/hop definitions, and the **size-comparison engine** (NETCONF-XML + CORECONF-CBOR serializers + byte measurement). |
| `server.py` | The AP's CORECONF datastore (NoSec CoAP): `GET`/`FETCH`/`iPATCH` on `/c`, holding the `wifi-ap` container and `device` list. |
| `client.py` | CLI demo: reads AP state, cascades a channel change and a device connect, printing size comparisons. |
| `webui/web_console.py` | Stdlib-only web server that runs the simulator and streams message events to the browser. Serves UI assets with no-cache headers so edits always load fresh. |
| `webui/flow_client.py` | Instrumented client that emits one JSON event per hop (3 down + 3 back). Requests carry both encodings' sizes; for `get` the data-bearing **response** hop also carries sizes (real CBOR bytes vs equivalent `<rpc-reply>` XML). |
| `webui/index.html` | The UI: a 4-node chain (switch drawn as an RJ-45 plug), protocol-labeled hops, animated per-hop packets, a full-width **size-comparison panel** (shows ~3 comparisons with its own scrollbar), and a **resizable split** with the dashboard on the left and a scrollable **messages** pane on the right (drag the divider to resize). |

## The YANG models

Three modules, one per node (each real box owns its own datastore):

```
// switch  (NETCONF)
container switch {
  leaf name           string
  leaf mgmt-address   string
  leaf enabled        boolean
  leaf ap-uplink-port uint8(1..48)
  leaf uplink-up      boolean   (config false)
  leaf port-count     uint8     (config false)
}

// wifi-ap  (NETCONF upstream, CORECONF downstream to devices)
container wifi-ap {
  leaf name     string(1..32)
  leaf enabled  boolean
  leaf ssid     string(1..32)
  leaf band     enum{2g4,5g,6g}
  leaf channel  uint8(1..196)
  leaf tx-power uint8(1..30) dBm
  leaf latency  uint32(0..10000) ms   // writable target
  leaf state    identityref           // read-only: down|scanning|active
  list device {                       // managed over CORECONF
    key "mac";
    leaf mac        string            // list key
    leaf hostname   string
    leaf ip-address string
    leaf signal-dbm int8(-120..0) dBm
    leaf connected  boolean
  }
}

// device  (CORECONF leaf node — mirrors a wifi-ap/device entry)
container device { leaf mac; leaf hostname; leaf ip-address; leaf signal-dbm; leaf connected; }
```

SIDs use the example range `70000+` (real modules get SIDs from a
registered range, RFC 9595).

## How the CORECONF hop works

The AP's datastore lives at a single CoAP resource (`/c`). Payloads are
CBOR maps keyed by SID. The `wifi-ap` container is a CBOR map; its `device`
list is a CBOR **array** of per-device maps:

- **GET `/c`** → full datastore, e.g.
  `{70010: {70011: "ap-1", 70015: 36, ..., 70020: [ {70021: "aa:bb:..", 70022: "laptop-1", ...} ]}}`
  (`70010` = `wifi-ap`, `70015` = `channel`, `70020` = `device` list,
  `70021` = `mac`).
- **FETCH `/c`** → client sends a CBOR sequence of SIDs; server returns the
  requested instance-values.
- **iPATCH `/c`** → set a `wifi-ap` leaf (e.g. `channel`) or add/update a
  `device` entry keyed by `mac`. A new `mac` **connects a device**; an
  existing one **updates** it; a `null`/`connected:false` disconnects.

## Run it on any computer

Self-contained — needs **either** Python 3.9+ **or** Docker. The local
`.venv/` is created on first run and is not shipped.

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
docker build -t wifi-coreconf .
docker run --rm -p 8080:8080 wifi-coreconf
```

Then open http://localhost:8080.

### Option C — manual setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 webui/web_console.py        # serves http://localhost:8080
```

### Using it

Open http://localhost:8080, then:

1. Click **Start simulator** (launches `server.py`, the AP datastore).
2. **Configure the AP:** set channel / latency / tx-power / SSID, or
   **enable** / **disable** the radio. Each action cascades down the chain.
3. **Connect / disconnect a device:** enter a MAC (optionally hostname/IP)
   and click **Connect device** — this adds a device over CORECONF.
4. Click **get** to read back the AP state.
5. Watch each action animate **hop-by-hop** across the four nodes, with the
   protocol labeled per segment, and read the **size comparison** panel:
   NETCONF (XML) vs CORECONF (CBOR/SID) bytes, plus a cumulative
   "bytes saved" total. Toggle *include transport framing* for wire bytes.

Operations: `get`, `set-channel`, `set-latency`, `set-power`, `set-ssid`,
`enable`, `disable`, `connect`, `disconnect`.

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
GET -> {'name': 'ap-1', 'enabled': True, 'channel': 36, ...,
        'devices': [{'mac': 'aa:bb:cc:00:11:22', 'hostname': 'laptop-1', ...},
                    {'mac': 'de:ad:be:ef:00:01', 'hostname': 'phone-1', ...}]}
  size for 'set AP channel=44':
    NETCONF  (XML)      payload= 215 B  wire= 303 B
    CORECONF (CBOR/SID) payload=  14 B  wire=  22 B
    -> CORECONF is 15.4x smaller (payload), 13.8x (wire)
iPATCH set AP channel=44 -> 2.04 Changed
  size for 'connect device aa:bb:cc:00:11:22':
    NETCONF  (XML)      payload= 303 B  wire= 391 B
    CORECONF (CBOR/SID) payload=  67 B  wire=  75 B
    -> CORECONF is 4.5x smaller (payload), 5.2x (wire)
iPATCH connect device 'aa:bb:cc:00:11:22' -> 2.04 Changed
GET -> {'name': 'ap-1', 'channel': 44, 'devices': [{'mac': 'aa:bb:cc:00:11:22', ...}]}
```

The server **seeds the datastore on startup** with the radio enabled and two
associated clients (`laptop-1`, `phone-1`), so a fresh `get` returns real
device data instead of an empty list.

## Notes / simplifications

- **Option B:** only the AP↔device hop uses real CoAP transport. The two
  NETCONF hops are modeled; their XML is really serialized and measured but
  not sent over SSH. Sizes are therefore accurate; the transport is
  simulated.
- SIDs use the example range `70000+` (RFC 9595 for real ranges).
- `latency` on the AP is a **writable target/budget**, not a measured value.
- The datastore is in-memory; no persistence or NMDA separation. The server
  seeds one `ap-1` access point (radio enabled) with two associated clients
  on startup.
- The server is NoSec (plain CoAP). `draft-ietf-core-comi` states NoSec
  MUST NOT be used in production and recommends OSCORE (RFC 8613); see the
  `coffee-example` for an OSCORE + per-user authorization variant.
