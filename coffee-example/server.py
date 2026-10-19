#!/usr/bin/env python3
"""
CORECONF server for the coffee-maker *fleet*.

    [coffee-maker manager] --CORECONF--> [coffee-maker fleet datastore]

This process plays the fleet's CoAP (CORECONF) datastore at /c, which holds
the coffee-maker-manager container and its keyed list of coffee makers.
Payloads are CBOR maps keyed by numeric YANG SIDs (RFC 9254 / RFC 9595).

  * GET   /c   -> full datastore: manager container (CBOR map), with the
                  coffee-maker list encoded as a CBOR array of per-maker maps.
  * FETCH /c   -> selected instance-values (whole subtree for this demo).
  * iPATCH /c  -> set manager/maker leaves and add/update maker entries
                  (keyed by 'id'). This turns individual makers on/off.
  * POST  /c   -> invoke the per-maker 'brew' action. The request payload is
                  a CBOR map {coffee-maker: [{id: <id>}]} selecting the maker.

Run:
    python3 server.py            # NoSec (plain CoAP) on udp/5683
"""

import asyncio
import logging

import cbor2
from aiocoap import resource, Message, Code, Context

from coffee_sids import (
    SID_MANAGER, SID_MGR_NAME, SID_MAKER_COUNT,
    SID_MAKER, SID_ID, SID_LOCATION, SID_POWER, SID_CUPS, SID_STRENGTH,
    SID_STATE, SID_WATER_LEVEL, SID_BEANS_LEVEL, SID_HAS_COFFEE,
    SID_CUPS_BREWED, SID_LAST_ERROR,
    SID_BREW, SID_BREW_STARTED, SID_BREW_REASON,
    SID_REFILL, SID_REFILL_BEANS, SID_REFILL_WATER,
    SID_REFILL_BEANS_LEVEL, SID_REFILL_WATER_LEVEL,
    SID_OFF, SID_IDLE, SID_BREWING, SID_NO_WATER, SID_NO_BEANS, SID_ERROR,
    STRENGTH_TO_INT, INT_TO_STRENGTH,
    CF_YANG_DATA_CBOR, CF_YANG_INSTANCES_SEQ,
    DATASTORE_PATH, decode_cbor_seq,
)

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("coreconf-coffee-server")

# writable manager leaf SIDs
MGR_WRITABLE = {SID_MGR_NAME}
# writable coffee-maker leaf SIDs (per entry)
MAKER_WRITABLE = {SID_LOCATION, SID_POWER, SID_CUPS, SID_STRENGTH}

# water/beans consumed per cup brewed (percentage points).
WATER_PER_CUP = 8
BEANS_PER_CUP = 5


class CoffeeMaker:
    """In-memory state for one coffee maker (list entry)."""

    def __init__(self, maker_id):
        self.id = maker_id
        # configuration
        self.location = ""
        self.power = False
        self.cups = 1
        self.strength = "medium"
        # operational state
        self.water_level = 100
        self.beans_level = 100
        self.cups_brewed = 0
        self.last_error = ""

    # -- derived operational state -----------------------------------------
    @property
    def has_coffee(self):
        """True if the maker has both water and beans to brew a cup now."""
        return self.water_level >= WATER_PER_CUP and self.beans_level >= BEANS_PER_CUP

    @property
    def state(self):
        if self.last_error:
            return SID_ERROR
        if not self.power:
            return SID_OFF
        if self.water_level < WATER_PER_CUP:
            return SID_NO_WATER
        if self.beans_level < BEANS_PER_CUP:
            return SID_NO_BEANS
        return SID_IDLE

    # -- serialization -----------------------------------------------------
    def to_map(self):
        return {
            SID_ID: self.id,
            SID_LOCATION: self.location,
            SID_POWER: self.power,
            SID_CUPS: self.cups,
            SID_STRENGTH: STRENGTH_TO_INT[self.strength],
            SID_STATE: self.state,
            SID_WATER_LEVEL: self.water_level,
            SID_BEANS_LEVEL: self.beans_level,
            SID_HAS_COFFEE: self.has_coffee,
            SID_CUPS_BREWED: self.cups_brewed,
            SID_LAST_ERROR: self.last_error,
        }

    # -- mutation ----------------------------------------------------------
    def apply_leaf(self, sid, value):
        if sid == SID_LOCATION:
            if not (isinstance(value, str) and len(value) <= 64):
                return "invalid-value: location must be 0..64 chars"
            self.location = value
        elif sid == SID_POWER:
            if value is None:
                value = False
            if not isinstance(value, bool):
                return "invalid-value: power must be boolean"
            self.power = value
            LOG.info("maker '%s' powered %s", self.id,
                     "ON" if value else "OFF")
        elif sid == SID_CUPS:
            if value is None:
                value = 1
            if not (isinstance(value, int) and 1 <= value <= 12):
                return "not-in-range: cups must be 1..12"
            self.cups = value
        elif sid == SID_STRENGTH:
            if value is None:
                value = STRENGTH_TO_INT["medium"]
            if value not in INT_TO_STRENGTH:
                return "invalid-value: unknown strength"
            self.strength = INT_TO_STRENGTH[value]
        else:
            return f"unknown-element: SID {sid} is not writable on coffee-maker"
        return None

    def brew(self):
        """Attempt a brew cycle. Returns (started, reason)."""
        if not self.power:
            return False, "powered off"
        if self.water_level < WATER_PER_CUP:
            return False, "out of water"
        if self.beans_level < BEANS_PER_CUP:
            return False, "out of coffee beans"
        cups = max(1, min(self.cups, self.water_level // WATER_PER_CUP,
                          self.beans_level // BEANS_PER_CUP))
        self.water_level -= cups * WATER_PER_CUP
        self.beans_level -= cups * BEANS_PER_CUP
        self.cups_brewed += cups
        LOG.info("maker '%s' brewed %d cup(s) [%s]; water=%d%% beans=%d%%",
                 self.id, cups, self.strength, self.water_level,
                 self.beans_level)
        return True, ""

    def refill(self, beans=True, water=True):
        """Refill beans and/or water to 100% and clear any fault. Returns the
        (beans_level, water_level) after the refill."""
        if beans:
            self.beans_level = 100
        if water:
            self.water_level = 100
        self.last_error = ""
        LOG.info("maker '%s' refilled; water=%d%% beans=%d%%",
                 self.id, self.water_level, self.beans_level)
        return self.beans_level, self.water_level


class FleetDatastore:
    """In-memory YANG datastore: the manager container + coffee-maker list."""

    def __init__(self):
        self.name = "barista-1"
        self.makers = {}  # id -> CoffeeMaker
        self._seed()

    def _seed(self):
        """Pre-populate a few makers so a fresh GET returns a real fleet."""
        seeds = [
            # id,       location,        power, cups, strength, water, beans
            ("kitchen",  "Main Kitchen",  True,  2, "strong", 85, 70),
            ("lobby",    "Front Lobby",   True,  1, "medium", 40, 15),
            ("lab",      "R&D Lab",       False, 1, "mild",   95, 90),
            ("breakout", "Breakout Room", True,  4, "medium", 5,  60),
        ]
        for mid, loc, power, cups, strength, water, beans in seeds:
            m = CoffeeMaker(mid)
            m.location = loc
            m.power = power
            m.cups = cups
            m.strength = strength
            m.water_level = water
            m.beans_level = beans
            self.makers[mid] = m

    def to_map(self):
        return {
            SID_MANAGER: {
                SID_MGR_NAME: self.name,
                SID_MAKER_COUNT: len(self.makers),
                SID_MAKER: [m.to_map() for m in self.makers.values()],
            }
        }

    # -- mutation ----------------------------------------------------------
    def apply_maker_entry(self, entry):
        """Add/update one coffee-maker list entry keyed by 'id'."""
        if not isinstance(entry, dict):
            return "malformed-message: coffee-maker entry must be a map"
        mid = entry.get(SID_ID)
        if not isinstance(mid, str) or not mid:
            return "missing-key: a valid 'id' (SID 60021) is required"
        maker = self.makers.get(mid)
        created = False
        if maker is None:
            maker = CoffeeMaker(mid)
            self.makers[mid] = maker
            created = True
            LOG.info("maker '%s' added to the fleet", mid)
        for sid, value in entry.items():
            if sid == SID_ID:
                continue
            if sid not in MAKER_WRITABLE:
                if created:
                    self.makers.pop(mid, None)
                return f"unknown-element: SID {sid} is not writable on coffee-maker"
            err = maker.apply_leaf(sid, value)
            if err:
                if created:
                    self.makers.pop(mid, None)
                return err
        return None

    def apply_manager(self, value):
        """Apply an iPATCH body under the coffee-maker-manager container."""
        if not isinstance(value, dict):
            return "malformed-message: coffee-maker-manager must be a map"
        for sid, v in value.items():
            if sid == SID_MAKER:
                entries = v if isinstance(v, list) else [v]
                for entry in entries:
                    err = self.apply_maker_entry(entry)
                    if err:
                        return err
            elif sid in MGR_WRITABLE:
                if sid == SID_MGR_NAME:
                    if not (isinstance(v, str) and 1 <= len(v) <= 32):
                        return "invalid-value: name must be 1..32 chars"
                    self.name = v
            else:
                return f"unknown-element: SID {sid} is not writable"
        return None


DATASTORE = FleetDatastore()


class DatastoreResource(resource.Resource):
    """The /c datastore resource implementing CORECONF methods."""

    async def render_get(self, request):
        LOG.info("GET /c")
        payload = cbor2.dumps(DATASTORE.to_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_DATA_CBOR)

    async def render_fetch(self, request):
        LOG.info("FETCH /c")
        payload = cbor2.dumps(DATASTORE.to_map())
        return Message(code=Code.CONTENT, payload=payload,
                       content_format=CF_YANG_INSTANCES_SEQ)

    async def render_ipatch(self, request):
        LOG.info("iPATCH /c")
        items = decode_cbor_seq(request.payload)
        for item in items:
            if not isinstance(item, dict):
                return _error("malformed-message")
            for key, value in item.items():
                if key == SID_MANAGER:
                    err = DATASTORE.apply_manager(value)
                    if err:
                        return _error(err)
                else:
                    return _error(f"unknown-element: SID {key}")
        return Message(code=Code.CHANGED)

    async def render_post(self, request):
        """POST invokes a per-maker action ('brew' or 'refill'). The request
        payload selects the maker and action, e.g.
        {manager: {coffee-maker: [{id: <id>, <action-sid>: <input>}]}}.
        If no action SID is present, 'brew' is assumed."""
        maker_id, action_sid, params = _extract_action(request.payload)
        if maker_id is None:
            return _error("missing-key: action needs a coffee-maker 'id'")
        maker = DATASTORE.makers.get(maker_id)
        if maker is None:
            return _error(f"unknown-maker: no coffee-maker '{maker_id}'")

        if action_sid == SID_REFILL:
            LOG.info("POST /c (refill action) on '%s'", maker_id)
            beans = params.get(SID_REFILL_BEANS, True)
            water = params.get(SID_REFILL_WATER, True)
            beans = True if not isinstance(beans, bool) else beans
            water = True if not isinstance(water, bool) else water
            beans_level, water_level = maker.refill(beans=beans, water=water)
            out = {SID_REFILL_BEANS_LEVEL: beans_level,
                   SID_REFILL_WATER_LEVEL: water_level}
            return Message(code=Code.CHANGED, payload=cbor2.dumps(out),
                           content_format=CF_YANG_DATA_CBOR)

        LOG.info("POST /c (brew action) on '%s'", maker_id)
        started, reason = maker.brew()
        out = {SID_BREW_STARTED: started}
        if reason:
            out[SID_BREW_REASON] = reason
        return Message(code=Code.CHANGED, payload=cbor2.dumps(out),
                       content_format=CF_YANG_DATA_CBOR)


def _extract_action(payload):
    """Pull (maker_id, action_sid, params) out of a POST payload. action_sid
    is SID_REFILL or SID_BREW (default); params is the action-input map."""
    if not payload:
        return None, SID_BREW, {}
    try:
        items = decode_cbor_seq(payload)
    except Exception:
        return None, SID_BREW, {}
    for item in items:
        if not isinstance(item, dict):
            continue
        mgr = item.get(SID_MANAGER, item)
        makers = mgr.get(SID_MAKER) if isinstance(mgr, dict) else None
        entries = makers if isinstance(makers, list) else (
            [mgr] if isinstance(mgr, dict) and mgr.get(SID_ID) else [])
        for entry in entries:
            if not (isinstance(entry, dict) and entry.get(SID_ID)):
                continue
            if SID_REFILL in entry:
                params = entry[SID_REFILL]
                return entry[SID_ID], SID_REFILL, (
                    params if isinstance(params, dict) else {})
            if SID_BREW in entry:
                params = entry[SID_BREW]
                return entry[SID_ID], SID_BREW, (
                    params if isinstance(params, dict) else {})
            return entry[SID_ID], SID_BREW, {}
    return None, SID_BREW, {}


def _error(msg):
    LOG.warning("Rejecting request: %s", msg)
    return Message(code=Code.BAD_REQUEST, payload=msg.encode())


async def main():
    root = resource.Site()
    root.add_resource([DATASTORE_PATH], DatastoreResource())
    await Context.create_server_context(root, bind=("::", 5683))
    LOG.info("CORECONF coffee-maker fleet server listening on "
             "coap://[::]:5683/%s", DATASTORE_PATH)
    await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
