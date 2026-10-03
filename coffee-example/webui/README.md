# CORECONF Coffee-Maker Web Console

A browser UI for the coffee-maker example. It lets you start the CORECONF
CoAP server, send CORECONF operations through a command line, and watch the
raw output — all from one page.

## Run

```bash
cd coffee-example
. .venv/bin/activate          # the venv with aiocoap + cbor2
python3 webui/web_console.py
```

Then open http://localhost:8080

No extra dependencies: the backend uses only the Python standard library
(`http.server`) and shells out to the existing example scripts.

## What you can do

1. **Start example** — launches `server.py` (NoSec CoAP on udp/5683). Its log
   streams live in the panel below the button. **Stop** terminates it.
2. **Command line** — type a command and press Enter (or click a chip):

   | Command        | CORECONF operation                               |
   |----------------|--------------------------------------------------|
   | `get`          | GET /c — read the whole datastore                |
   | `fetch`        | FETCH /c — read just power + state               |
   | `on`           | iPATCH /c — turn the maker ON (2 cups, strong)   |
   | `off`          | iPATCH /c — turn the maker OFF                   |
   | `brew`         | POST /c — invoke the brew action                 |
   | `demo`         | run the full `client.py` walk-through            |
   | `secure-setup` | generate OSCORE contexts (alice, bob)            |
   | `secure-demo`  | run `secure_client.py`                           |
   | `help`         | list commands                                    |

   Output appears in the terminal pane, color-coded by stream.

3. **Secure demo** — run `secure-setup` once, start `secure_server.py` from the
   Secure Demo card, then run `secure-demo` in the command line to see
   alice (operator) allowed and bob (viewer) denied `4.03`.

## Configuration

Environment variables:

- `WEBUI_HOST` (default `127.0.0.1`)
- `WEBUI_PORT` (default `8080`)

The backend prefers `./.venv/bin/python3` if present so the example's
dependencies are available; otherwise it uses the interpreter that launched it.
