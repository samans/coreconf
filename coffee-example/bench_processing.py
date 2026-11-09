#!/usr/bin/env python3
"""
Server-side processing-cost benchmark: CORECONF (CBOR/SID) vs NETCONF (XML).

The web UI's size panel answers "how many bytes?". This answers the companion
question "how much CPU does the *server* spend handling the message?" for the
SAME set of coffee-maker operations.

For each operation it times the three stages where the two encodings actually
differ -- decode, schema-dispatch, encode -- in-process (no network/SSH/UDP),
and reports microseconds per operation plus the NETCONF/CORECONF ratio.
See coffee_sids.processing_costs() for exactly what each stage measures.

    python3 bench_processing.py                # default 2000 iterations/stage
    python3 bench_processing.py --iterations 5000
    python3 bench_processing.py --json         # machine-readable output

This is Option 1 from the README's "processing power" comparison: an
apples-to-apples micro-benchmark of the codec + dispatch path. Transport and
crypto costs (SSH vs CoAP/OSCORE) are deliberately excluded.
"""

import argparse
import json
import platform
import sys

import cbor2  # noqa: F401  (imported so a missing dep fails loudly, like server.py)

from coffee_sids import (
    SID_MANAGER, SID_MAKER, SID_ID, SID_POWER, SID_CUPS, SID_STRENGTH,
    SID_LOCATION, SID_REFILL,
    STRENGTH_TO_INT,
    coreconf_maker_leaf, coreconf_maker_entry,
    netconf_maker_leaf, netconf_maker_entry, netconf_get,
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
    return nc, cc


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
    return nc, cc


def build_operations():
    """Return a list of (label, netconf_xml, coreconf_obj) tuples -- the same
    operations the fleet web console exercises (request direction)."""
    mid = "kitchen"
    brew_nc, brew_cc = _brew_bodies(mid)
    refill_nc, refill_cc = _refill_bodies(mid)
    return [
        ("get (read fleet)",
         netconf_get('<coffee-maker-manager xmlns="urn:example:coffee-maker"/>'),
         {}),
        ("power-on",
         netconf_maker_leaf(mid, "power", True),
         coreconf_maker_leaf(mid, SID_POWER, True)),
        ("power-off",
         netconf_maker_leaf(mid, "power", False),
         coreconf_maker_leaf(mid, SID_POWER, False)),
        ("set-cups",
         netconf_maker_leaf(mid, "cups", 4),
         coreconf_maker_leaf(mid, SID_CUPS, 4)),
        ("set-strength",
         netconf_maker_leaf(mid, "strength", "strong"),
         coreconf_maker_leaf(mid, SID_STRENGTH, STRENGTH_TO_INT["strong"])),
        ("brew (action)", brew_nc, brew_cc),
        ("refill (action)", refill_nc, refill_cc),
        ("add maker",
         netconf_maker_entry("patio", {"location": "Patio Bar"}),
         coreconf_maker_entry("patio", {SID_LOCATION: "Patio Bar"})),
    ]


def run(iterations):
    results = []
    for label, nc_xml, cc_obj in build_operations():
        pc = processing_costs(nc_xml, cc_obj, coreconf_is_seq=True,
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
    print()
    print("CORECONF vs NETCONF — server-side processing cost (microseconds/op)")
    print(f"  {env}; {iters} iterations/stage; lower is better")
    print("  stages: decode (parse) + dispatch (schema lookup) + encode (serialize)")
    print()

    header = (f"{'operation':<20} {'proto':<9} "
              f"{'decode':>9} {'dispatch':>9} {'encode':>9} {'total':>9}  ratio")
    print(header)
    print("-" * len(header))

    tot_nc = tot_cc = 0.0
    for r in results:
        nc, cc = r["netconf"], r["coreconf"]
        tot_nc += nc["total_us"]
        tot_cc += cc["total_us"]
        print(f"{r['op']:<20} {'NETCONF':<9} "
              f"{_fmt_us(nc['decode_us'])} {_fmt_us(nc['dispatch_us'])} "
              f"{_fmt_us(nc['encode_us'])} {_fmt_us(nc['total_us'])}")
        print(f"{'':<20} {'CORECONF':<9} "
              f"{_fmt_us(cc['decode_us'])} {_fmt_us(cc['dispatch_us'])} "
              f"{_fmt_us(cc['encode_us'])} {_fmt_us(cc['total_us'])}"
              f"   {r['ratio_total']}x")
        print()

    overall = round(tot_nc / tot_cc, 1) if tot_cc else None
    print("-" * len(header))
    print(f"{'TOTAL (all ops)':<20} {'NETCONF':<9} "
          f"{'':>9} {'':>9} {'':>9} {_fmt_us(tot_nc)}")
    print(f"{'':<20} {'CORECONF':<9} "
          f"{'':>9} {'':>9} {'':>9} {_fmt_us(tot_cc)}   {overall}x")
    print()
    print(f"CORECONF needs about {overall}x less server CPU than NETCONF "
          f"across these operations")
    print("(codec + schema-dispatch only; transport/crypto excluded).")
    print()


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iterations", type=int, default=2000,
                    help="timing-loop iterations per stage (default 2000)")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of a table")
    args = ap.parse_args(argv)

    results = run(args.iterations)
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
