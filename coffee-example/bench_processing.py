#!/usr/bin/env python3
"""
Server-side processing-cost benchmark: CORECONF (CBOR/SID) vs NETCONF (XML)
vs RESTCONF (JSON).

The web UI's size panel answers "how many bytes?". This answers the companion
question "how much CPU does the *server* spend handling the message?" for the
SAME set of coffee-maker operations, across all three management protocols.

For each operation it times the three stages where the encodings actually
differ -- decode, schema-dispatch, encode -- in-process (no network/SSH/UDP),
and reports microseconds per operation plus a ratio against CORECONF (the
baseline). See coffee_sids.processing_costs() for exactly what each stage
measures.

    python3 bench_processing.py                # default 2000 iterations/stage
    python3 bench_processing.py --iterations 5000
    python3 bench_processing.py --fleet-size 200   # add a big-GET comparison
    python3 bench_processing.py --json         # machine-readable output

This is Option 1 from the README's "processing power" comparison: an
apples-to-apples micro-benchmark of the codec + dispatch path. Transport and
crypto costs (SSH/TLS vs HTTP/TLS vs CoAP/OSCORE) are deliberately excluded.
"""

import argparse
import json
import platform
import sys

import cbor2  # noqa: F401  (imported so a missing dep fails loudly, like server.py)

from coffee_sids import (
    SID_MANAGER, SID_MAKER, SID_ID, SID_POWER, SID_CUPS, SID_STRENGTH,
    SID_LOCATION, SID_REFILL, SID_MGR_NAME, SID_MAKER_COUNT,
    SID_STATE, SID_WATER_LEVEL, SID_BEANS_LEVEL, SID_HAS_COFFEE,
    SID_CUPS_BREWED, SID_IDLE, SID_OFF,
    STRENGTH_TO_INT, INT_TO_STRENGTH, STATE_NAMES,
    PROTOCOLS, PROTOCOL_IDS, BASELINE_PROTOCOL,
    coreconf_maker_leaf, coreconf_maker_entry,
    netconf_maker_leaf, netconf_maker_entry, netconf_get,
    restconf_maker_leaf, restconf_maker_entry, restconf_action,
    restconf_get_empty, _rc_dumps,
    processing_costs,
)


def _brew_bodies(maker_id):
    cc = {SID_MANAGER: {SID_MAKER: [{SID_ID: maker_id}]}}
    nc = (
        '<rpc message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
        '<action xmlns="urn:ietf:params:xml:ns:yang:1">'
        '<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        f'<coffee-maker><id>{maker_id}</id><brew/></coffee-maker>'
        '</coffee-maker-manager></action></rpc>'
    )
    rc = restconf_action(maker_id, "brew")
    return nc, rc, cc


def _refill_bodies(maker_id):
    cc = {SID_MANAGER: {SID_MAKER: [{SID_ID: maker_id, SID_REFILL: {}}]}}
    nc = (
        '<rpc message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
        '<action xmlns="urn:ietf:params:xml:ns:yang:1">'
        '<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        f'<coffee-maker><id>{maker_id}</id><refill/></coffee-maker>'
        '</coffee-maker-manager></action></rpc>'
    )
    rc = restconf_action(maker_id, "refill")
    return nc, rc, cc


def _large_fleet_get_bodies(n):
    """Synthesize a GET *response* carrying a fleet of ``n`` makers in all
    three encodings — the data-bearing direction, where payload size (and so
    the format's efficiency) actually scales. Mirrors the field set the real
    GET returns in server.py / flow_client.py.

    Returns (netconf_xml, restconf_json, coreconf_obj)."""
    makers_cc = []
    makers_rc = []
    xml_parts = []
    for i in range(n):
        mid = f"maker-{i:04d}"
        loc = f"Floor {i // 10} Room {i % 10}"
        power = (i % 2 == 0)
        cups = (i % 12) + 1
        strength = i % 3
        state = SID_IDLE if power else SID_OFF
        water = (i * 7) % 101
        beans = (i * 13) % 101
        has_coffee = water >= 8 and beans >= 5
        brewed = i * 3

        # CORECONF: SID-keyed CBOR map
        makers_cc.append({
            SID_ID: mid, SID_LOCATION: loc, SID_POWER: power,
            SID_CUPS: cups, SID_STRENGTH: strength, SID_STATE: state,
            SID_WATER_LEVEL: water, SID_BEANS_LEVEL: beans,
            SID_HAS_COFFEE: has_coffee, SID_CUPS_BREWED: brewed,
        })
        # RESTCONF: JSON object with full node names
        makers_rc.append({
            "id": mid, "location": loc, "power": power, "cups": cups,
            "strength": INT_TO_STRENGTH[strength],
            "state": STATE_NAMES[state], "water-level": water,
            "beans-level": beans, "has-coffee": has_coffee,
            "cups-brewed": brewed,
        })
        # NETCONF: XML subtree
        xml_parts.append(
            "<coffee-maker>"
            f"<id>{mid}</id><location>{loc}</location>"
            f"<power>{'true' if power else 'false'}</power>"
            f"<cups>{cups}</cups><strength>{INT_TO_STRENGTH[strength]}</strength>"
            f"<state>{STATE_NAMES[state]}</state>"
            f"<water-level>{water}</water-level><beans-level>{beans}</beans-level>"
            f"<has-coffee>{'true' if has_coffee else 'false'}</has-coffee>"
            f"<cups-brewed>{brewed}</cups-brewed>"
            "</coffee-maker>"
        )

    cc_obj = {SID_MANAGER: {SID_MGR_NAME: "barista-fleet",
                            SID_MAKER_COUNT: n, SID_MAKER: makers_cc}}
    rc_json = _rc_dumps({
        "example-coffee-maker:coffee-maker-manager": {
            "name": "barista-fleet", "maker-count": n,
            "coffee-maker": makers_rc,
        }
    })
    nc_xml = (
        '<rpc-reply message-id="101" '
        'xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><data>'
        '<coffee-maker-manager xmlns="urn:example:coffee-maker">'
        '<name>barista-fleet</name>'
        f'<maker-count>{n}</maker-count>'
        + "".join(xml_parts) +
        '</coffee-maker-manager></data></rpc-reply>'
    )
    return nc_xml, rc_json, cc_obj


def build_operations():
    """Return a list of (label, netconf_xml, restconf_json, coreconf_obj)
    tuples -- the same operations the fleet web console exercises (request
    direction)."""
    mid = "kitchen"
    brew_nc, brew_rc, brew_cc = _brew_bodies(mid)
    refill_nc, refill_rc, refill_cc = _refill_bodies(mid)
    return [
        ("get (read fleet)",
         netconf_get('<coffee-maker-manager xmlns="urn:example:coffee-maker"/>'),
         restconf_get_empty(),
         {}),
        ("power-on",
         netconf_maker_leaf(mid, "power", True),
         restconf_maker_leaf(mid, "power", True),
         coreconf_maker_leaf(mid, SID_POWER, True)),
        ("power-off",
         netconf_maker_leaf(mid, "power", False),
         restconf_maker_leaf(mid, "power", False),
         coreconf_maker_leaf(mid, SID_POWER, False)),
        ("set-cups",
         netconf_maker_leaf(mid, "cups", 4),
         restconf_maker_leaf(mid, "cups", 4),
         coreconf_maker_leaf(mid, SID_CUPS, 4)),
        ("set-strength",
         netconf_maker_leaf(mid, "strength", "strong"),
         restconf_maker_leaf(mid, "strength", "strong"),
         coreconf_maker_leaf(mid, SID_STRENGTH, STRENGTH_TO_INT["strong"])),
        ("brew (action)", brew_nc, brew_rc, brew_cc),
        ("refill (action)", refill_nc, refill_rc, refill_cc),
        ("add maker",
         netconf_maker_entry("patio", {"location": "Patio Bar"}),
         restconf_maker_entry("patio", {"location": "Patio Bar"}),
         coreconf_maker_entry("patio", {SID_LOCATION: "Patio Bar"})),
    ]


def run(iterations, fleet_size=None):
    ops = build_operations()
    if fleet_size:
        nc, rc, cc = _large_fleet_get_bodies(fleet_size)
        ops.append((f"get large fleet ({fleet_size} makers)", nc, rc, cc))
    results = []
    for label, nc_xml, rc_json, cc_obj in ops:
        pc = processing_costs(nc_xml, rc_json, cc_obj, coreconf_is_seq=True,
                              iterations=iterations)
        pc["op"] = label
        results.append(pc)
    return results


def _fmt_us(v):
    return f"{v:8.2f}"


def print_table(results):
    env = (f"Python {platform.python_version()} on "
           f"{platform.system()} {platform.machine()}")
    iters = results[0]["iterations"] if results else 0
    labels = {p["id"]: p["label"] for p in PROTOCOLS}
    print()
    print("Server-side processing cost (microseconds/op) — "
          "NETCONF vs RESTCONF vs CORECONF")
    print(f"  {env}; {iters} iterations/stage; lower is better; "
          f"ratio is vs {BASELINE_PROTOCOL.upper()}")
    print("  stages: decode (parse) + dispatch (schema lookup) + encode (serialize)")
    print()

    header = (f"{'operation':<20} {'protocol':<20} "
              f"{'decode':>9} {'dispatch':>9} {'encode':>9} {'total':>9}  ratio")
    print(header)
    print("-" * len(header))

    totals = {pid: 0.0 for pid in PROTOCOL_IDS}
    for r in results:
        print(f"{r['op']:<20}")
        for pid in PROTOCOL_IDS:
            d = r["protocols"][pid]
            totals[pid] += d["total_us"]
            ratio = "" if pid == BASELINE_PROTOCOL else \
                f"   {r['ratios_total'].get(pid)}x"
            print(f"{'':<20} {labels[pid]:<20} "
                  f"{_fmt_us(d['decode_us'])} {_fmt_us(d['dispatch_us'])} "
                  f"{_fmt_us(d['encode_us'])} {_fmt_us(d['total_us'])}{ratio}")
        print()

    base_total = totals[BASELINE_PROTOCOL]
    print("-" * len(header))
    print(f"{'TOTAL (all ops)':<20}")
    for pid in PROTOCOL_IDS:
        ratio = "" if pid == BASELINE_PROTOCOL else (
            f"   {round(totals[pid] / base_total, 1)}x" if base_total else "")
        print(f"{'':<20} {labels[pid]:<20} "
              f"{'':>9} {'':>9} {'':>9} {_fmt_us(totals[pid])}{ratio}")
    print()
    print(f"Ratios are each protocol's server CPU relative to "
          f"{BASELINE_PROTOCOL.upper()} (codec + schema-dispatch only; "
          f"transport/crypto excluded).")
    print()


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iterations", type=int, default=2000,
                    help="timing-loop iterations per stage (default 2000)")
    ap.add_argument("--fleet-size", type=int, default=None, metavar="N",
                    help="also benchmark a GET response carrying N makers, "
                         "to show how each format scales with payload size "
                         "(e.g. --fleet-size 200)")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of a table")
    args = ap.parse_args(argv)

    results = run(args.iterations, fleet_size=args.fleet_size)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
