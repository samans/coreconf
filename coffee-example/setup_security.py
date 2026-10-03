#!/usr/bin/env python3
"""
Provision OSCORE security contexts for the secured coffee-maker example.

OSCORE (RFC 8613) protects each CoAP message with an AEAD cipher using a
shared security context. A context is defined by:

  * a Master Secret (shared secret, must be kept confidential)
  * a Master Salt   (public)
  * a Sender ID and Recipient ID (which side is which)

The client's Sender ID equals the server's Recipient ID and vice-versa.
In a production ACE-OAuth (RFC 9200) deployment these parameters would be
delivered by an Authorization Server as part of an access token; here we
generate them on disk for demonstration.

We create two users:
    alice -> role "operator" (read/write)
    bob   -> role "viewer"   (read-only)

Layout created:
    oscore-contexts/
        server-alice/settings.json     recipient_id = alice  (server view)
        server-bob/settings.json
        client-alice/settings.json     sender_id    = alice  (client view)
        client-bob/settings.json
"""

import json
import os
from pathlib import Path

BASE = Path(__file__).parent / "oscore-contexts"

# 16-byte master secrets (demo values; generate randomly in real life).
USERS = {
    "alice": {
        "id": "01",  # hex sender/recipient id
        "secret": "0011223344556677889aabbccddeeff0",
    },
    "bob": {
        "id": "02",
        "secret": "ffeeddccbbaa99887766554433221100",
    },
}
MASTER_SALT = "9e7ca92223786340"  # public, shared by all contexts here


def write_context(path: Path, sender_id: str, recipient_id: str, secret: str):
    path.mkdir(parents=True, exist_ok=True)
    settings = {
        "algorithm": "AES-CCM-16-64-128",
        "sender-id_hex": sender_id,
        "recipient-id_hex": recipient_id,
        "secret_hex": secret,
        "salt_hex": MASTER_SALT,
    }
    (path / "settings.json").write_text(json.dumps(settings, indent=2))
    # aiocoap keeps a persistent sender sequence number + replay window
    # next to settings. Start fresh each time we (re)provision.
    seq = path / "sequence.json"
    seq.write_text(json.dumps({"next-to-send": 0, "received": "unknown"}))


def main():
    for user, cfg in USERS.items():
        uid = cfg["id"]
        secret = cfg["secret"]
        # Server view: server receives from the user, so recipient-id = uid,
        # and the server's own sender-id is the *other* end. We use a fixed
        # server id of "00".
        write_context(BASE / f"server-{user}",
                      sender_id="00", recipient_id=uid, secret=secret)
        # Client view (mirror image).
        write_context(BASE / f"client-{user}",
                      sender_id=uid, recipient_id="00", secret=secret)
    print(f"Wrote OSCORE contexts under {BASE}")
    for p in sorted(BASE.glob("*/settings.json")):
        print("  ", p.relative_to(BASE.parent))


if __name__ == "__main__":
    main()
