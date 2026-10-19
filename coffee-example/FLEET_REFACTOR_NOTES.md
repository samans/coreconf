# Coffee-Maker Fleet Refactor — Notes

Transformed `coffee-example` from a single coffee maker into a **coffee-maker
fleet managed by a coffee-maker manager over CORECONF**, with a UI styled like
`../802-eth-dot11-mp/`.

```
[coffee-maker manager] --CORECONF--> [coffee-maker fleet datastore]
```

## New YANG model

`yang/example-coffee-maker@2026-10-18.yang` (+ matching `.sid`): a
`coffee-maker-manager` container owning a keyed **`coffee-maker` list**. Each
maker has:

- **writable:** `power`, `cups`, `strength`, `location`
- **read-only:** `state` (off / idle / brewing / no-water / no-beans / error),
  `water-level`, `beans-level`, **`has-coffee`**, `cups-brewed`, `last-error`
- **action:** `brew` (output: `started`, `reason`)

The previous single-maker revision (`@2026-09-14`) is kept for history. SIDs use
the example range `60000+` (RFC 9595 for real ranges).

### SID map (fleet revision)

| SID   | Node |
|-------|------|
| 60010 | `coffee-maker-manager` (container) |
| 60011 | `name` |
| 60012 | `maker-count` (config false) |
| 60020 | `coffee-maker` (list) |
| 60021 | `id` (list key) |
| 60022 | `location` |
| 60023 | `power` |
| 60024 | `cups` |
| 60025 | `strength` |
| 60026 | `state` |
| 60027 | `water-level` |
| 60028 | `beans-level` |
| 60029 | `has-coffee` |
| 60030 | `cups-brewed` |
| 60031 | `last-error` |
| 60032 | `brew` (action) |
| 60033 | `brew/started` |
| 60034 | `brew/reason` |
| 60002–60007 | identities: off, idle, brewing, no-water, no-beans, error |

## Rewritten code

- **`coffee_sids.py`** — fleet SIDs (manager + list), CBOR helpers,
  NETCONF/CORECONF encoders, and the size-comparison engine (mirroring
  `wifi_sids.py`).
- **`server.py`** — in-memory fleet datastore seeded with 4 makers
  (`kitchen`, `lobby`, `lab`, `breakout`) at different water/bean levels.
  GET/FETCH/iPATCH, plus per-maker `brew` via POST. Water/beans deplete per
  cup (`WATER_PER_CUP=8`, `BEANS_PER_CUP=5`); `has-coffee` and `state` are
  derived properties.
- **`client.py`** — CLI that reads the fleet, powers a maker on, brews, reads
  back, powers off.
- **`secure_server.py` / `secure_client.py`** — updated the OSCORE +
  per-user-role variant to the fleet model (acts on the `kitchen` maker).

## UI (mirrors the wifi project)

- **`webui/index.html`** — a live **dashboard of maker cards** (power, state,
  water/beans meters, has-coffee, cups brewed) with inline turn-on/off and brew
  buttons; an animated **manager → fleet CORECONF hop**; a messages pane; and a
  NETCONF-vs-CORECONF size-comparison panel with running totals.
- **`webui/flow_client.py`** — emits ndjson events per request/response
  (`get`, `power-on`, `power-off`, `set-cups`, `set-strength`, `brew`, `add`).
- **`webui/web_console.py`** — stdlib server that starts/stops the datastore,
  streams op events, and serves a `/api/fleet` snapshot for the dashboard.
- **`run.sh`, `run.bat`, `Dockerfile`, `.dockerignore`** — one-command
  launchers.

## How CORECONF works here

The fleet datastore lives at a single CoAP resource (`/c`). Payloads are CBOR
maps keyed by SID; the `coffee-maker` list is a CBOR **array** of per-maker
maps. A maker is addressed by its `id` key:

- **iPATCH** `{60010: {60020: [{60021: "lab", 60023: true}]}}` turns the `lab`
  maker on.
- **POST** brew selects the maker by `id`; the reply reports `started` and a
  `reason` if it could not brew (out of water / out of beans / powered off).

## Verified

- CLI end-to-end: turned on `lab`, brewed 2 cups (water 95→79, beans 90→80),
  turned off.
- Web stack: server start, fleet snapshot JSON, streamed ndjson ops, UI served
  (HTTP 200).
- Out-of-water brew correctly rejected with `reason: "out of water"`.
- OSCORE: alice (operator) allowed writes; bob (viewer) denied `4.03 Forbidden`.
- CORECONF is ~13.6× smaller than NETCONF for a power toggle; ~4.6× smaller for
  the full fleet GET response.

## Run it

```bash
cd coffee-example
./run.sh                       # http://localhost:8080
```

Click **Start manager + fleet**, then act on makers from the dashboard.

## "Add coffee" (refill) feature — added later

Each maker gained a `refill` action that tops up beans and/or water to 100% and
clears any fault — used when a maker is low on or out of coffee.

- **YANG**: `action refill { input { leaf beans boolean; leaf water boolean; }
  output { leaf beans-level uint8; leaf water-level uint8; } }`.
- **SIDs**: `60035` refill, `60036` beans (in), `60037` water (in),
  `60038` beans-level (out), `60039` water-level (out).
- **server.py / secure_server.py**: the POST handler dispatches on the action
  SID (`SID_REFILL` vs `SID_BREW`; brew assumed if absent) via
  `_extract_action()` — renamed from `_extract_brew_target`.
  `CoffeeMaker.refill(beans, water)` sets levels to 100 and clears `last_error`.
- **webui/flow_client.py**: `refill` op → POST
  `{manager:{coffee-maker:[{id, 60035:{}}]}}`.
- **webui/web_console.py**: `refill` added to OPERATIONS / OP_PARAMS.
- **webui/index.html**: "Add coffee" button on each maker card (styled
  `danger`/red when low or out, via `lowCoffee(m)`) plus a `refillBtn` in the
  operations panel.

### Verified
- `breakout` (out of water, 5%): brew failed with "out of water"; refill set
  water=100%/beans=100%; brew then succeeded (4 cups).
- Refill response event carries `{60038: 100, 60039: 100}` and
  `decoded:{beans_level:100, water_level:100}` with `refresh:true`.
- `secure_server.py` imports cleanly after the `_extract_action` rename.
