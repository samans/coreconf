#!/usr/bin/env python3
"""
Secured CORECONF server for the coffee-maker example.

This adds *user security* on top of the plain server using OSCORE
(Object Security for Constrained RESTful Environments, RFC 8613), which
is the security mechanism recommended by draft-ietf-core-comi. The draft
states NoSec MUST NOT be used in production and points to OSCORE and to
ACE-OAuth (RFC 9200) for access control.

Two things are demonstrated:

  1. End-to-end payload authentication + encryption via OSCORE. Each
     request/response is protected with an AEAD cipher keyed by a
     pre-established security context, so an attacker cannot read or
     forge coffee-maker commands.

  2. Per-user authorization. Each OSCORE security context maps to a
     user identity (its sender-id). We attach a simple role to each
     user:
        - "operator" : may read and change configuration (power on/off)
        - "viewer"   : read-only (GET / FETCH); writes are rejected 4.03

Security contexts are loaded from ./oscore-contexts/ (created by
setup_security.py). In a real ACE deployment these keys would be
provisioned by an Authorization Server rather than shipped on disk.

Run:
    python3 setup_security.py     # once, to generate contexts
    python3 secure_server.py
"""

import asyncio
import logging
from pathlib import Path

import cbor2
from aiocoap import resource, Message, Code, Context
from aiocoap.oscore_sitewrapper import OscoreSiteWrapper

from coffee_sids import (
    SID_COFFEE_MAKER, SID_STATE, SID_WATER_LEVEL, SID_BREW_STARTED,
    SID_IDLE, SID_OFF, CF_YANG_DATA_CBOR, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH,
)
from server import CoffeeDatastore, _decode_cbor_seq

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-secure-server")

CONTEXT_DIR = Path(__file__).parent / "oscore-contexts"

# Map each OSCORE credential label to an application role. The label is
# whatever we register the context under in server_credentials; aiocoap
# reports it back on request.remote.authenticated_claims after a message
# is successfully unprotected.
USER_ROLES = {
    ":coffee-alice": ("alice", "operator"),  # full read/write
    ":coffee-bob": ("bob", "viewer"),        # read-only
}

DATASTORE = CoffeeDatastore()


def _role_for_request(request):
    """Return (username, role) for the OSCORE-authenticated request,
    or (None, None) if the request was not protected/known."""
    claims = getattr(request.remote, "authenticated_claims", None) or []
    for claim in claims:
        if claim in USER_ROLES:
            return USER_ROLES[claim]
    return (None, None)


class SecureDatastoreResource(resource.Resource):

    def _authorize(self, request, need_write):
        username, role = _role_for_request(request)
        if role is None:
            # Not authenticated via OSCORE at all.
            return None, Message(code=Code.UNAUTHORIZED,
                                 payload=b"OSCORE required")
        if need_write and role != "operator":
            LOG.warning("DENY: user %s (role=%s) attempted a write",
                        username, role)
            return None, Message(code=Code.FORBIDDEN,
                                 payload=b"role 'viewer' is read-only")
        return (username, role), None

    async def render_get(self, request):
        who, deny = self._authorize(request, need_write=False)
        if deny:
            return deny
        LOG.info("GET /c  (user=%s)", who[0])
        return Message(code=Code.CONTENT,
                       payload=cbor2.dumps(DATASTORE.full_map()),
                       content_format=CF_YANG_DATA_CBOR)

    async def render_fetch(self, request):
        who, deny = self._authorize(request, need_write=False)
        if deny:
            return deny
        LOG.info("FETCH /c  (user=%s)", who[0])
        ids = _decode_cbor_seq(request.payload)
        inner = DATASTORE.full_map()[SID_COFFEE_MAKER]
        out = b""
        for ident in ids:
            sid = ident[0] if isinstance(ident, list) else ident
            out += cbor2.dumps({sid: inner.get(sid)})
        return Message(code=Code.CONTENT, payload=out,
                       content_format=CF_YANG_INSTANCES_SEQ)

    async def render_ipatch(self, request):
        who, deny = self._authorize(request, need_write=True)
        if deny:
            return deny
        LOG.info("iPATCH /c  (user=%s)", who[0])
        items = _decode_cbor_seq(request.payload)
        for item in items:
            for key, value in item.items():
                if key == SID_COFFEE_MAKER and isinstance(value, dict):
                    for child_sid, child_val in value.items():
                        err = DATASTORE.apply_instance(child_sid, child_val)
                        if err:
                            return Message(code=Code.BAD_REQUEST,
                                           payload=err.encode())
                else:
                    sid = key[0] if isinstance(key, (list, tuple)) else key
                    err = DATASTORE.apply_instance(sid, value)
                    if err:
                        return Message(code=Code.BAD_REQUEST,
                                       payload=err.encode())
        return Message(code=Code.CHANGED)

    async def render_post(self, request):
        who, deny = self._authorize(request, need_write=True)
        if deny:
            return deny
        LOG.info("POST /c brew (user=%s)", who[0])
        started = DATASTORE.power
        return Message(code=Code.CHANGED,
                       payload=cbor2.dumps({SID_BREW_STARTED: started}),
                       content_format=CF_YANG_DATA_CBOR)


def load_server_credentials(ctx):
    """Load each server-side OSCORE context into aiocoap's credentials
    store under a stable label (":coffee-<user>") used for authorization."""
    count = 0
    for path in sorted(CONTEXT_DIR.glob("server-*")):
        user = path.name[len("server-"):]
        label = f":coffee-{user}"
        ctx.server_credentials.load_from_dict(
            {label: {"oscore": {"basedir": str(path) + "/"}}}
        )
        count += 1
        LOG.info("Loaded OSCORE context for %s as %s", user, label)
    LOG.info("Loaded %d OSCORE security context(s)", count)


async def main():
    root = resource.Site()
    root.add_resource([DATASTORE_PATH], SecureDatastoreResource())

    ctx = await Context.create_server_context(None, bind=("::", 5683))
    load_server_credentials(ctx)

    # Wrap the site so OSCORE-protected requests are unprotected and the
    # authenticated identity is attached to request.remote before routing.
    ctx.serversite = OscoreSiteWrapper(root, ctx.server_credentials)

    LOG.info("Secure CORECONF server on coap://[::]:5683/%s (OSCORE only)",
             DATASTORE_PATH)
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
