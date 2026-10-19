# CORECONF Coffee-Maker Fleet Web Console

A browser UI for the coffee-maker **fleet** example. It lets you start the
CORECONF CoAP datastore, see a live dashboard of every coffee maker under
management, send CORECONF operations, watch each message animate on the
manager&harr;fleet hop, and compare NETCONF vs CORECONF encoding sizes.

## Run

```bash
cd coffee-example
./run.sh                       # creates .venv, installs deps, serves :8080
# or, manually:
. .venv/bin/activate
python3 webui/web_console.py
```

Then open http://localhost:8080

No extra UI dependencies: the backend uses only the Python standard library
(`http.server`) and shells out to `server.py` / `webui/flow_client.py`.

## What you can do

1. **Start manager + fleet** — launches `server.py` (NoSec CoAP on udp/5683),
   the fleet datastore seeded with four coffee makers. Its log streams live.
2. **Coffee Makers dashboard** — a card per maker showing power, operational
   state (idle / brewing / no-water / no-beans / error), water and bean
   meters, whether it still **has coffee**, and the lifetime cup count. Each
   card has inline **Turn on/off** and **Brew** buttons.
3. **Manager Operations** — address a maker by its `id` key and:

   | Operation       | CORECONF exchange                                  |
   |-----------------|----------------------------------------------------|
   | `get`           | GET /c — read the whole fleet                      |
   | `power-on`      | iPATCH /c — turn a maker ON                        |
   | `power-off`     | iPATCH /c — turn a maker OFF                       |
   | `set-cups`      | iPATCH /c — set cups-per-brew                      |
   | `set-strength`  | iPATCH /c — set brew strength                      |
   | `brew`          | POST /c — invoke the per-maker brew action         |
   | `add`           | iPATCH /c — add a new maker to the fleet           |

4. **Messages** pane — one entry per request/response, with the decoded
   CBOR/SID (or XML) payload.
5. **Encoding Size Comparison** — NETCONF (XML) vs CORECONF (CBOR/SID) bytes
   for each operation, with a running "bytes saved" total. Toggle *include
   transport framing* for wire bytes.

## Configuration

- `WEBUI_HOST` (default `127.0.0.1`)
- `WEBUI_PORT` (default `8080`)

The backend prefers `./.venv/bin/python3` if present so the example's
dependencies are available; otherwise it uses the interpreter that launched it.
