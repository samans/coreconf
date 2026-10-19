#!/usr/bin/env python3
"""
Secured CORECONF client for the coffee-maker example.

Talks to secure_server.py using OSCORE (RFC 8613). It demonstrates two
users with different privileges:

    alice (operator): can read AND turn the coffee maker on/off
    bob   (viewer):   can read, but write attempts are rejected 4.03

Each user loads its own client-side OSCORE context (created by
setup_security.py) so every request is encrypted+authenticated end to end.

Run:
    python3 setup_security.py     # once
    python3 secure_server.py      # in one terminal
    python3 secure_client.py      # in another
"""

import asyncio
import logging
from pathlib import Path

import cbor2
from aiocoap import Message, Code, Context

from coffee_sids import (
    SID_MANAGER, SID_MAKER, SID_ID, SID_LOCATION, SID_POWER, SID_CUPS,
    SID_STRENGTH, SID_STATE, SID_WATER_LEVEL, SID_BEANS_LEVEL,
    SID_HAS_COFFEE, INT_TO_STRENGTH, STRENGTH_TO_INT,
    CF_YANG_DATA_CBOR, CF_YANG_INSTANCES_SEQ, DATASTORE_PATH,
    STATE_NAMES, coreconf_maker_entry,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-secure-client")

CONTEXT_DIR = Path(__file__).parent / "oscore-contexts"
SERVER = f"coap://localhost/{DATASTORE_PATH}"
TARGET = "kitchen"   # the maker alice/bob act on


def _pretty(m):
    return {
        "id": m.get(SID_ID),
        "location": m.get(SID_LOCATION),
        "power": m.get(SID_POWER),
        "cups": m.get(SID_CUPS),
        "strength": INT_TO_STRENGTH.get(m.get(SID_STRENGTH)),
        "state": STATE_NAMES.get(m.get(SID_STATE)),
        "water_level": m.get(SID_WATER_LEVEL),
        "beans_level": m.get(SID_BEANS_LEVEL),
        "has_coffee": m.get(SID_HAS_COFFEE),
    }


def _find_maker(data, maker_id):
    makers = data.get(SID_MANAGER, {}).get(SID_MAKER, []) or []
    for m in makers:
        if m.get(SID_ID) == maker_id:
            return m
    return makers[0] if makers else {}


async def make_user_context(user):
    """Create a client Context whose OSCORE credentials protect all
    requests to the server with this user's security context."""
    ctx = await Context.create_client_context()
    basedir = str(CONTEXT_DIR / f"client-{user}") + "/"
    # Bind the OSCORE context to the server URI pattern.
    ctx.client_credentials.load_from_dict({
        f"{SERVER}*": {"oscore": {"basedir": basedir}}
    })
    return ctx


async def do_get(ctx, user):
    resp = await ctx.request(Message(code=Code.GET, uri=SERVER)).response
    if resp.code.is_successful():
        data = cbor2.loads(resp.payload)
        LOG.info("[%s] GET -> %s", user, _pretty(_find_maker(data, TARGET)))
    else:
        LOG.info("[%s] GET -> %s (%s)", user, resp.code,
                 resp.payload.decode(errors="replace"))
    return resp


async def do_turn_on(ctx, user):
    body = coreconf_maker_entry(TARGET, {
        SID_POWER: True,
        SID_CUPS: 2,
        SID_STRENGTH: STRENGTH_TO_INT["strong"],
    })
    req = Message(code=Code.iPATCH, uri=SERVER,
                  payload=cbor2.dumps(body),
                  content_format=CF_YANG_INSTANCES_SEQ)
    resp = await ctx.request(req).response
    LOG.info("[%s] iPATCH turn '%s' ON -> %s %s", user, TARGET, resp.code,
             ("(" + resp.payload.decode(errors="replace") + ")")
             if resp.payload else "")
    return resp


async def main():
    LOG.info("=== alice (operator) ===")
    alice = await make_user_context("alice")
    await do_get(alice, "alice")
    await do_turn_on(alice, "alice")     # allowed
    await do_get(alice, "alice")
    await alice.shutdown()

    LOG.info("=== bob (viewer, read-only) ===")
    bob = await make_user_context("bob")
    await do_get(bob, "bob")             # allowed
    await do_turn_on(bob, "bob")         # should be rejected 4.03
    await bob.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
