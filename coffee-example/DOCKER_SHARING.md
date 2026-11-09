# Sharing & Running the Coffee-Maker CORECONF Simulator (Docker)

This guide explains **how to share** the containerized simulator and **what to
tell people** so they can run it themselves. The container runs the web
console (the UI) plus the CoAP/CORECONF fleet datastore (`server.py`) as a
subprocess — everything needed for the demo lives inside the image.

- **Image contents:** Python 3.12, `aiocoap` + `cbor2`, and all project code.
- **Published port:** `8080` (the HTTP UI). CoAP (udp/5683) runs *inside* the
  container and does not need to be exposed.
- **Default command:** `python webui/web_console.py` with `WEBUI_HOST=0.0.0.0`.

---

## For the person sharing it

You have three ways to share, from easiest for the recipient to most flexible.

### Option 1 — Share the source and let them build (simplest)

Give the recipient the project folder (git repo, zip, etc.). They build the
image locally from the included `Dockerfile`. Nothing else to host.

- Make sure these files are included: `Dockerfile`, `.dockerignore`,
  `requirements.txt`, and the Python/HTML source (`server.py`,
  `coffee_sids.py`, `webui/`, etc.).
- `.dockerignore` already excludes `.venv/`, `__pycache__/`, `.git/`,
  `*.md`, and `oscore-contexts/`, so the build context stays small and
  reproducible.

Then point them at the "For the person running it" section below.

### Option 2 — Share a pre-built image as a file (no registry needed)

Build once, export to a tarball, and send the file (USB, file share, etc.).
The recipient does **not** need the source or network access to a registry.

```bash
# You (build + export):
cd coffee-example
docker build -t coffee-coreconf:latest .
docker save coffee-coreconf:latest | gzip > coffee-coreconf.tar.gz
# send coffee-coreconf.tar.gz to the recipient
```

```bash
# Them (import + run):
docker load < coffee-coreconf.tar.gz
docker run --rm -p 8080:8080 coffee-coreconf:latest
# open http://localhost:8080
```

> Tip: `docker save` captures the exact image you tested, so the recipient
> runs bit-for-bit what you built — no "works on my machine" build drift.

### Option 3 — Push to a container registry (best for teams / repeat use)

Publish to Docker Hub, GitHub Container Registry (GHCR), or a private
registry, and share just the image name.

```bash
# You (tag + push) — example for GHCR:
docker build -t ghcr.io/<you>/coffee-coreconf:latest .
docker login ghcr.io
docker push ghcr.io/<you>/coffee-coreconf:latest
```

```bash
# Them (pull + run):
docker run --rm -p 8080:8080 ghcr.io/<you>/coffee-coreconf:latest
# open http://localhost:8080
```

Make the package public (or grant the recipients access) so `docker pull`
works without extra credentials.

#### Multi-architecture note (Apple Silicon / ARM)

If your recipients are on a mix of Intel/AMD (`amd64`) and Apple Silicon or
ARM (`arm64`), build a multi-arch image so it runs natively on both:

```bash
docker buildx create --use                       # once
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/<you>/coffee-coreconf:latest \
  --push .
```

(An `amd64`-only image still runs on Apple Silicon via emulation, just slower.)

---

## For the person running it (copy/paste this to them)

> ### Run the Coffee-Maker CORECONF simulator
>
> **Requirement:** Docker Desktop (macOS/Windows) or Docker Engine (Linux).
> Nothing else — no Python install needed.
>
> **1. Get the image** (use whichever your sender gave you):
>
> ```bash
> # A) building from source:
> cd coffee-example && docker build -t coffee-coreconf .
>
> # B) from a shared tar file:
> docker load < coffee-coreconf.tar.gz
>
> # C) from a registry:
> docker pull ghcr.io/<owner>/coffee-coreconf:latest
> ```
>
> **2. Run it:**
>
> ```bash
> docker run --rm -p 8080:8080 coffee-coreconf
> ```
>
> **3. Open the UI:** http://localhost:8080
>
> **4. Use it:** click **Start manager + fleet**, then interact with the
> coffee-maker dashboard — power makers on/off, brew, add coffee, and watch the
> CORECONF vs NETCONF size and CPU comparison panels update.
>
> **To stop:** press `Ctrl+C` in the terminal (the `--rm` flag removes the
> container automatically).

---

## Options the runner may need

### Change the host port

If port `8080` is already in use, map a different **host** port (left side);
keep the container port `8080` on the right:

```bash
docker run --rm -p 9000:8080 coffee-coreconf
# then open http://localhost:9000
```

### Run in the background

```bash
docker run -d --name coffee -p 8080:8080 coffee-coreconf
docker logs -f coffee     # watch output
docker stop coffee        # stop it
docker rm coffee          # remove the container
```

### Access from another machine on the LAN

The container already binds `0.0.0.0` inside, so publishing the port is
enough. From another device, browse to `http://<host-ip>:8080` (ensure any
host firewall allows the port).

### Environment variables

| Variable     | Default (in image) | Purpose                              |
|--------------|--------------------|--------------------------------------|
| `WEBUI_HOST` | `0.0.0.0`          | Interface the web UI binds to.       |
| `WEBUI_PORT` | `8080`             | Port the web UI listens on.          |

Changing `WEBUI_PORT` changes the port *inside* the container, so update the
`-p` mapping to match, e.g.:

```bash
docker run --rm -e WEBUI_PORT=8000 -p 8000:8000 coffee-coreconf
```

---

## Notes & caveats

- **Simulator is NoSec.** The container runs the plain (unencrypted) CoAP
  fleet datastore and web console — intended for demos and learning. The
  OSCORE-secured variants (`secure_server.py` / `secure_client.py`) are not
  what the image launches; run those directly with Python per the main
  `README.md`.
- **No persistence.** The fleet datastore is in-memory and reseeds on each
  start; stopping the container discards state. That is by design for a demo.
- **Exposed surface.** Only the HTTP UI port is published. Don't expose it to
  untrusted networks without putting your own authentication/proxy in front —
  the console can start/stop the simulator and run operations.
- **What's in the image is a snapshot.** If you change the source after
  building, rebuild (Option 1) or re-export/re-push (Options 2/3) so recipients
  get the latest UI and comparison-panel changes.

---

## Quick troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `permission denied ... /var/run/docker.sock` | Your user isn't in the `docker` group. Use `sudo docker ...`, or `sudo usermod -aG docker $USER` then re-login. |
| `bind: address already in use` | Port 8080 is taken. Use a different host port: `-p 9000:8080`. |
| UI loads but **Start manager + fleet** does nothing | Check `docker logs <container>` for the `server.py` subprocess output. |
| Can't reach it from another machine | Use the host's LAN IP (not `localhost`) and open the firewall for the port. |
| `no matching manifest for linux/arm64` | Image was built `amd64`-only; rebuild multi-arch (see above) or run with `--platform linux/amd64`. |
