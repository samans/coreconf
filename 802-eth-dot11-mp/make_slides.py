#!/usr/bin/env python3
"""
Generate a PowerPoint deck explaining YANG + NETCONF/RESTCONF/CORECONF,
grounded in the example-wifi-ap management-chain demo in this repo.

Run:
    .venv/bin/python3 make_slides.py
Produces:
    yang-coreconf-overview.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---------------------------------------------------------------- palette
BG        = RGBColor(0x0B, 0x0F, 0x14)   # near-black (matches the demo UI)
PANEL     = RGBColor(0x12, 0x18, 0x23)
PANEL2    = RGBColor(0x19, 0x21, 0x2E)
BORDER    = RGBColor(0x27, 0x30, 0x40)
TEXT      = RGBColor(0xE6, 0xED, 0xF3)
MUTED     = RGBColor(0x8B, 0x98, 0xA9)
STATION   = RGBColor(0x58, 0xA6, 0xFF)   # blue
SWITCH    = RGBColor(0xA3, 0x71, 0xF7)   # purple
AP        = RGBColor(0x3F, 0xB9, 0x50)   # green
DEVICE    = RGBColor(0xD2, 0x99, 0x22)   # amber
NETCONF   = RGBColor(0xF0, 0x88, 0x3E)   # orange (the big one)
CORECONF  = RGBColor(0x3F, 0xB9, 0x50)   # green  (the small one)
RESTCONF  = RGBColor(0x58, 0xA6, 0xFF)   # blue
DANGER    = RGBColor(0xF8, 0x51, 0x49)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
CODEBG    = RGBColor(0x06, 0x0A, 0x0F)

FONT      = "Segoe UI"
MONO      = "Consolas"

# 16:9
EMU_W = Inches(13.333)
EMU_H = Inches(7.5)

prs = Presentation()
prs.slide_width = EMU_W
prs.slide_height = EMU_H
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers
def slide():
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, EMU_W, EMU_H, BG, line=None)
    return s


def rect(s, x, y, w, h, fill, line=BORDER, line_w=1.0, shape=MSO_SHAPE.RECTANGLE,
         round_val=None):
    sp = s.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    if round_val is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = round_val
        except Exception:
            pass
    return sp


def roundrect(s, x, y, w, h, fill, line=BORDER, line_w=1.0, radius=0.08):
    return rect(s, x, y, w, h, fill, line, line_w,
                shape=MSO_SHAPE.ROUNDED_RECTANGLE, round_val=radius)


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         wrap=True, space_after=6):
    """runs: list of paragraphs; each paragraph is a list of (txt, size, color,
    bold, font) tuples OR a single such tuple."""
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(4)
    tf.margin_right = Pt(4)
    tf.margin_top = Pt(2)
    tf.margin_bottom = Pt(2)
    first = True
    for para in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.space_after = Pt(space_after)
        p.space_before = Pt(0)
        if isinstance(para, tuple):
            para = [para]
        for item in para:
            txt, size, color, bold, font = (item + (None,) * 5)[:5]
            r = p.add_run()
            r.text = txt
            r.font.size = Pt(size or 18)
            r.font.color.rgb = color or TEXT
            r.font.bold = bool(bold)
            r.font.name = font or FONT
    return tb


def title_bar(s, label, sub=None):
    """Standard slide header: accent rule + title (+ optional subtitle)."""
    rect(s, Inches(0.6), Inches(0.55), Inches(0.14), Inches(0.62), NETCONF, line=None)
    runs = [[(label, 30, TEXT, True, FONT)]]
    text(s, Inches(0.9), Inches(0.45), Inches(11.8), Inches(0.9), runs)
    if sub:
        text(s, Inches(0.92), Inches(1.18), Inches(11.6), Inches(0.5),
             [[(sub, 15, MUTED, False, FONT)]])


def chip(s, x, y, w, label, color, size=12, h=Inches(0.34)):
    c = roundrect(s, x, y, w, h, PANEL2, line=color, line_w=1.25, radius=0.5)
    tf = c.text_frame
    tf.word_wrap = False
    tf.margin_top = Pt(1); tf.margin_bottom = Pt(1)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = label
    r.font.size = Pt(size); r.font.bold = True
    r.font.color.rgb = color; r.font.name = MONO
    return c


def arrow(s, x, y, w, color, label=None, label_color=None):
    a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, Inches(0.22))
    a.fill.solid(); a.fill.fore_color.rgb = color
    a.line.fill.background(); a.shadow.inherit = False
    if label:
        text(s, x, y - Inches(0.42), w, Inches(0.35),
             [[(label, 11, label_color or color, True, MONO)]],
             align=PP_ALIGN.CENTER)
    return a


def code_box(s, x, y, w, h, lines, size=13, title=None):
    """lines: list of (text, color) or plain strings."""
    if title:
        th = Inches(0.32)
        hdr = roundrect(s, x, y, w, th, PANEL2, line=BORDER, radius=0.12)
        tf = hdr.text_frame; tf.margin_left = Pt(8)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = title
        r.font.size = Pt(11); r.font.bold = True; r.font.name = MONO
        r.font.color.rgb = MUTED
        y = y + th + Inches(0.02)
        h = h - th - Inches(0.02)
    box = rect(s, x, y, w, h, CODEBG, line=BORDER, line_w=1.0)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(12); tf.margin_right = Pt(10)
    tf.margin_top = Pt(8); tf.margin_bottom = Pt(8)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(1); p.space_before = Pt(0)
        if isinstance(ln, str):
            ln = [(ln, TEXT)]
        if isinstance(ln, tuple):
            ln = [ln]
        for seg in ln:
            txt, color = seg
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.name = MONO
            r.font.color.rgb = color
    return box


def bullet_card(s, x, y, w, h, heading, items, accent):
    roundrect(s, x, y, w, h, PANEL, line=BORDER, radius=0.04)
    rect(s, x, y, Inches(0.08), h, accent, line=None)
    runs = [[(heading, 17, accent, True, FONT)]]
    for it in items:
        if isinstance(it, tuple):
            lead, rest = it
            runs.append([("\u2022  ", 13, accent, True, FONT),
                         (lead, 13, TEXT, True, FONT),
                         (rest, 13, MUTED, False, FONT)])
        else:
            runs.append([("\u2022  ", 13, accent, True, FONT),
                         (it, 13, TEXT, False, FONT)])
    text(s, x + Inches(0.28), y + Inches(0.18), w - Inches(0.5), h - Inches(0.3),
         runs, space_after=7)


def node(s, cx, cy, icon, name, sub, color, r=Inches(0.52)):
    """Draw a ringed node centered at (cx, cy)."""
    ring = s.shapes.add_shape(MSO_SHAPE.OVAL, cx - r, cy - r, r * 2, r * 2)
    ring.fill.solid(); ring.fill.fore_color.rgb = PANEL
    ring.line.color.rgb = color; ring.line.width = Pt(2.5)
    ring.shadow.inherit = False
    tf = ring.text_frame; tf.word_wrap = False
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r0 = p.add_run(); r0.text = icon; r0.font.size = Pt(26)
    r0.font.color.rgb = color
    text(s, cx - Inches(1.0), cy + r + Inches(0.03), Inches(2.0), Inches(0.3),
         [[(name, 13, color, True, FONT)]], align=PP_ALIGN.CENTER)
    text(s, cx - Inches(1.0), cy + r + Inches(0.30), Inches(2.0), Inches(0.3),
         [[(sub, 10, MUTED, False, MONO)]], align=PP_ALIGN.CENTER)


def footer(s, n):
    text(s, Inches(0.6), Inches(7.05), Inches(10), Inches(0.3),
         [[("YANG + NETCONF / RESTCONF / CORECONF  \u00b7  802 management-chain demo",
            10, MUTED, False, FONT)]])
    text(s, Inches(12.3), Inches(7.05), Inches(0.8), Inches(0.3),
         [[(str(n), 10, MUTED, False, FONT)]], align=PP_ALIGN.RIGHT)


# ================================================================ SLIDE 1 — title
def s_title():
    s = slide()
    # decorative accent band
    rect(s, 0, Inches(2.72), EMU_W, Inches(0.06), NETCONF, line=None)
    text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(1.2),
         [[("Modeling Once, Speaking Many", 44, TEXT, True, FONT)]])
    text(s, Inches(0.92), Inches(2.95), Inches(11.5), Inches(1.0),
         [[("YANG with NETCONF, RESTCONF & CORECONF", 26, NETCONF, True, FONT)]])
    text(s, Inches(0.92), Inches(3.8), Inches(11.5), Inches(0.9),
         [[("One data model, three protocols \u2014 and why CORECONF wins on "
            "constrained links.", 17, MUTED, False, FONT)]])
    # protocol chips
    y = Inches(5.0)
    chip(s, Inches(0.92), y, Inches(2.3), "NETCONF \u00b7 XML/SSH", NETCONF, size=13)
    chip(s, Inches(3.42), y, Inches(2.5), "RESTCONF \u00b7 JSON/HTTP", RESTCONF, size=13)
    chip(s, Inches(6.12), y, Inches(2.7), "CORECONF \u00b7 CBOR/CoAP", CORECONF, size=13)
    text(s, Inches(0.92), Inches(6.3), Inches(11), Inches(0.5),
         [[("Worked examples from the ", 14, MUTED, False, FONT),
           ("example-wifi-ap", 14, DEVICE, True, MONO),
           (" management chain.", 14, MUTED, False, FONT)]])
    return s


# ================================================================ SLIDE 2 — YANG <-> NETCONF
def s_yang_netconf():
    s = slide()
    title_bar(s, "YANG and NETCONF: model vs. protocol",
              "YANG defines WHAT the data is; NETCONF is HOW you move it.")
    # left: YANG
    bullet_card(s, Inches(0.6), Inches(1.7), Inches(5.9), Inches(2.3),
                "YANG \u2014 the data modeling language (RFC 7950)",
                [("Describes ", "structure, types, constraints, and defaults."),
                 ("Hierarchy ", "of containers, lists, leaves \u2014 vendor-neutral."),
                 ("One model ", "serves every protocol below."),
                 ("Example: ", "example-wifi-ap defines channel, latency, device{}.")],
                STATION)
    # right: NETCONF
    bullet_card(s, Inches(6.8), Inches(1.7), Inches(5.9), Inches(2.3),
                "NETCONF \u2014 the management protocol (RFC 6241)",
                [("Operations ", "get, edit-config, commit over a session."),
                 ("Datastores ", "running / candidate / startup."),
                 ("Encoding ", "XML, carried over SSH."),
                 ("Validates ", "payloads against the YANG model.")],
                NETCONF)
    # bottom flow: YANG module -> encodings
    y = Inches(4.5)
    roundrect(s, Inches(0.6), y, Inches(2.9), Inches(1.9), PANEL, line=STATION, radius=0.06)
    text(s, Inches(0.6), y + Inches(0.2), Inches(2.9), Inches(1.5),
         [[("YANG module", 15, STATION, True, FONT)],
          [(".yang", 13, MUTED, False, MONO)],
          [("the single source", 12, MUTED, False, FONT)],
          [("of truth", 12, MUTED, False, FONT)]], align=PP_ALIGN.CENTER)
    arrow(s, Inches(3.65), y + Inches(0.85), Inches(0.9), MUTED, "drives")
    # three protocol outputs
    outs = [("NETCONF", "XML / SSH", NETCONF, Inches(4.8)),
            ("RESTCONF", "JSON / HTTP", RESTCONF, Inches(7.55)),
            ("CORECONF", "CBOR / CoAP", CORECONF, Inches(10.3))]
    for name, enc, color, x in outs:
        roundrect(s, x, y, Inches(2.5), Inches(1.9), PANEL, line=color, radius=0.06)
        text(s, x, y + Inches(0.35), Inches(2.5), Inches(1.3),
             [[(name, 15, color, True, FONT)],
              [(enc, 12, MUTED, False, MONO)]], align=PP_ALIGN.CENTER)
    text(s, Inches(4.8), y + Inches(1.98), Inches(7.9), Inches(0.4),
         [[("same model \u2192 three wire formats", 15, MUTED, False, FONT)]],
         align=PP_ALIGN.CENTER)
    footer(s, 2)
    return s


# ================================================================ SLIDE 3 — family
def s_family():
    s = slide()
    title_bar(s, "One family: NETCONF, RESTCONF, CORECONF",
              "Same YANG models, different transports and encodings for different environments.")
    cols = [
        ("NETCONF", NETCONF, "RFC 6241", [
            ("Transport ", "SSH / TCP"),
            ("Encoding ", "XML"),
            ("Style ", "session + datastores"),
            ("Best for ", "routers, data-center gear"),
            ("Payload ", "largest (verbose XML)"),
        ]),
        ("RESTCONF", RESTCONF, "RFC 8040", [
            ("Transport ", "HTTP / TLS"),
            ("Encoding ", "JSON or XML"),
            ("Style ", "RESTful CRUD on resources"),
            ("Best for ", "web / automation tooling"),
            ("Payload ", "medium (JSON)"),
        ]),
        ("CORECONF", CORECONF, "draft-ietf-core-comi", [
            ("Transport ", "CoAP / UDP"),
            ("Encoding ", "CBOR + numeric SIDs"),
            ("Style ", "GET / FETCH / iPATCH"),
            ("Best for ", "constrained IoT devices"),
            ("Payload ", "smallest (binary + SIDs)"),
        ]),
    ]
    x = Inches(0.6)
    w = Inches(3.95)
    gap = Inches(0.19)
    for name, color, ref, rows in cols:
        roundrect(s, x, Inches(1.75), w, Inches(4.4), PANEL, line=color, line_w=1.5, radius=0.04)
        rect(s, x, Inches(1.75), w, Inches(0.7), PANEL2, line=None)
        text(s, x, Inches(1.8), w, Inches(0.6),
             [[(name, 20, color, True, FONT)]], align=PP_ALIGN.CENTER)
        text(s, x, Inches(2.42), w, Inches(0.3),
             [[(ref, 11, MUTED, False, MONO)]], align=PP_ALIGN.CENTER)
        runs = []
        for lead, rest in rows:
            runs.append([(lead, 13, color, True, FONT), (rest, 13, TEXT, False, FONT)])
        text(s, x + Inches(0.25), Inches(2.95), w - Inches(0.45), Inches(3.0),
             runs, space_after=11)
        x = x + w + gap
    # shared base ribbon
    roundrect(s, Inches(0.6), Inches(6.35), Inches(12.1), Inches(0.5), PANEL2,
              line=DEVICE, radius=0.5)
    text(s, Inches(0.6), Inches(6.4), Inches(12.1), Inches(0.4),
         [[("Shared foundation:  ", 13, DEVICE, True, FONT),
           ("the SAME YANG modules + the SAME datastore model (NMDA, RFC 8342)",
            13, TEXT, False, FONT)]], align=PP_ALIGN.CENTER)
    footer(s, 3)
    return s


# ================================================================ SLIDE 4 — NETCONF stack
def s_netconf_stack():
    s = slide()
    title_bar(s, "NETCONF: client \u2192 server message flow",
              "Layered model (RFC 6241) \u2014 XML content over an SSH session.")
    # left: layered stack
    layers = [
        ("Content", "config / state data", STATION),
        ("Operations", "<get>, <edit-config>, <commit>", NETCONF),
        ("Messages", "<rpc>, <rpc-reply>, <notification>", SWITCH),
        ("Secure Transport", "SSH (TCP/830)", AP),
    ]
    y = Inches(1.85)
    lh = Inches(0.92)
    for name, detail, color in layers:
        roundrect(s, Inches(0.6), y, Inches(4.7), Inches(0.8), PANEL, line=color, radius=0.08)
        rect(s, Inches(0.6), y, Inches(0.1), Inches(0.8), color, line=None)
        text(s, Inches(0.85), y + Inches(0.07), Inches(4.3), Inches(0.7),
             [[(name, 15, color, True, FONT)],
              [(detail, 11, MUTED, False, MONO)]], space_after=0)
        y = Emu(y + lh)
    # right: a request/response exchange
    cx_c = Inches(6.6)
    cx_s = Inches(11.9)
    node(s, cx_c, Inches(2.2), "\U0001F4BB", "Client", "manager", STATION, r=Inches(0.45))
    node(s, cx_s, Inches(2.2), "\U0001F5C4", "Server", "device", AP, r=Inches(0.45))
    # vertical lifelines
    for cx in (cx_c, cx_s):
        ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx - Emu(int(Pt(0.75))), Inches(2.9),
                                Pt(1.5), Inches(3.2))
        ln.fill.solid(); ln.fill.fore_color.rgb = BORDER; ln.line.fill.background()
        ln.shadow.inherit = False
    msgs = [
        ("<hello> capabilities", NETCONF, True, Inches(3.3)),
        ("<rpc><edit-config>", NETCONF, True, Inches(4.0)),
        ("<rpc-reply><ok/>", AP, False, Inches(4.7)),
        ("<rpc><get>", NETCONF, True, Inches(5.4)),
        ("<rpc-reply><data>", AP, False, Inches(6.1)),
    ]
    for label, color, l2r, y in msgs:
        x1, x2 = (cx_c, cx_s) if l2r else (cx_s, cx_c)
        shaft = min(x1, x2)
        a = s.shapes.add_shape(
            MSO_SHAPE.RIGHT_ARROW if l2r else MSO_SHAPE.LEFT_ARROW,
            shaft, y, abs(x2 - x1), Inches(0.18))
        a.fill.solid(); a.fill.fore_color.rgb = color
        a.line.fill.background(); a.shadow.inherit = False
        text(s, shaft, y - Inches(0.32), abs(x2 - x1), Inches(0.3),
             [[(label, 11, color, True, MONO)]], align=PP_ALIGN.CENTER)
    footer(s, 4)
    return s


# ================================================================ SLIDE 5 — CORECONF stack
def s_coreconf_stack():
    s = slide()
    title_bar(s, "CORECONF: client \u2192 server message flow",
              "Same YANG model, compact stack \u2014 CBOR + numeric SIDs over CoAP/UDP.")
    layers = [
        ("Content", "CBOR map keyed by numeric SIDs", STATION),
        ("Methods", "GET, FETCH, iPATCH on /c", CORECONF),
        ("Messaging", "CoAP confirmable / Content-Format", SWITCH),
        ("Transport", "UDP (5683) \u00b7 optional OSCORE", DEVICE),
    ]
    y = Inches(1.85)
    lh = Inches(0.92)
    for name, detail, color in layers:
        roundrect(s, Inches(0.6), y, Inches(4.7), Inches(0.8), PANEL, line=color, radius=0.08)
        rect(s, Inches(0.6), y, Inches(0.1), Inches(0.8), color, line=None)
        text(s, Inches(0.85), y + Inches(0.07), Inches(4.3), Inches(0.7),
             [[(name, 15, color, True, FONT)],
              [(detail, 11, MUTED, False, MONO)]], space_after=0)
        y = Emu(y + lh)
    cx_c = Inches(6.6)
    cx_s = Inches(11.9)
    node(s, cx_c, Inches(2.2), "\U0001F4F6", "Client", "AP (COMI)", AP, r=Inches(0.45))
    node(s, cx_s, Inches(2.2), "\U0001F4F1", "Server", "device /c", DEVICE, r=Inches(0.45))
    for cx in (cx_c, cx_s):
        ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx - Emu(int(Pt(0.75))), Inches(2.9),
                                Pt(1.5), Inches(3.2))
        ln.fill.solid(); ln.fill.fore_color.rgb = BORDER; ln.line.fill.background()
        ln.shadow.inherit = False
    msgs = [
        ("GET /c", CORECONF, True, Inches(3.3)),
        ("2.05 Content {CBOR}", DEVICE, False, Inches(4.0)),
        ("iPATCH /c {70010:{70017:35}}", CORECONF, True, Inches(4.9)),
        ("2.04 Changed", DEVICE, False, Inches(5.8)),
    ]
    for label, color, l2r, y in msgs:
        x1, x2 = (cx_c, cx_s) if l2r else (cx_s, cx_c)
        shaft = min(x1, x2)
        a = s.shapes.add_shape(
            MSO_SHAPE.RIGHT_ARROW if l2r else MSO_SHAPE.LEFT_ARROW,
            shaft, y, abs(x2 - x1), Inches(0.18))
        a.fill.solid(); a.fill.fore_color.rgb = color
        a.line.fill.background(); a.shadow.inherit = False
        text(s, shaft, y - Inches(0.32), abs(x2 - x1), Inches(0.3),
             [[(label, 10.5, color, True, MONO)]], align=PP_ALIGN.CENTER)
    # callout
    text(s, Inches(6.1), Inches(6.3), Inches(6.6), Inches(0.6),
         [[("No session setup, no XML, datagram-friendly \u2014 ", 12, MUTED, False, FONT),
           ("SIDs replace long path strings.", 12, CORECONF, True, FONT)]])
    footer(s, 5)
    return s


# ================================================================ SLIDE 6 — YANG snippet
def s_yang_snippet():
    s = slide()
    title_bar(s, "Example: the wifi-ap YANG model",
              "The single model the whole chain shares \u2014 example-wifi-ap@2026-10-05.")
    c = CORECONF
    k = STATION   # keywords
    t = DEVICE    # types
    code_box(s, Inches(0.6), Inches(1.75), Inches(7.1), Inches(5.0),
             [
                [("container ", k), ("wifi-ap ", TEXT), ("{", MUTED)],
                [("  leaf ", k), ("channel ", TEXT), ("{", MUTED)],
                [("    type ", k), ("uint8 ", t), ("{ range ", k), ('"1..196"', DEVICE), ("; }", MUTED)],
                [("    default ", k), ("36", DEVICE), (";", MUTED)],
                [("  }", MUTED)],
                [("  leaf ", k), ("latency ", TEXT), ("{", MUTED)],
                [("    type ", k), ("uint32 ", t), ("{ range ", k), ('"0..10000"', DEVICE), ("; }", MUTED)],
                [("    units ", k), ('"milliseconds"', DEVICE), (";", MUTED)],
                [("  }", MUTED), ("          // writable latency target", MUTED)],
                [("  leaf ", k), ("state ", TEXT), ("{", MUTED)],
                [("    type ", k), ("identityref ", t), ("{ base radio-state; }", MUTED)],
                [("    config ", k), ("false", DANGER), (";", MUTED), ("   // read-only", MUTED)],
                [("  }", MUTED)],
                [("  list ", k), ("device ", TEXT), ("{ key ", k), ('"mac"', DEVICE), (";", MUTED)],
                [("    leaf ", k), ("mac        ", TEXT), ("{ type ", k), ("string", t), ("; }", MUTED)],
                [("    leaf ", k), ("signal-dbm ", TEXT), ("{ type ", k), ("int8", t), ("; }", MUTED)],
                [("    leaf ", k), ("connected  ", TEXT), ("{ type ", k), ("boolean", t), ("; }", MUTED)],
                [("  }", MUTED)],
                [("}", MUTED)],
             ], size=13, title="yang/example-wifi-ap@2026-10-05.yang")
    # right: SID mapping
    bullet_card(s, Inches(7.95), Inches(1.75), Inches(4.75), Inches(2.35),
                "Why it matters",
                [("Vendor-neutral ", "contract for every node."),
                 ("Constraints ", "(ranges, patterns) enforced on write."),
                 ("config false ", "marks read-only operational state."),
                 ("One model ", "\u2014 NETCONF upstream, CORECONF down.")],
                CORECONF)
    code_box(s, Inches(7.95), Inches(4.3), Inches(4.75), Inches(2.45),
             [
                [("# .sid file assigns numeric SIDs", MUTED)],
                [("wifi-ap", TEXT), ("     \u2192 ", MUTED), ("70010", CORECONF)],
                [("  channel", TEXT), ("   \u2192 ", MUTED), ("70015", CORECONF)],
                [("  latency", TEXT), ("   \u2192 ", MUTED), ("70017", CORECONF)],
                [("  state", TEXT), ("     \u2192 ", MUTED), ("70018", CORECONF)],
                [("  device", TEXT), ("    \u2192 ", MUTED), ("70020", CORECONF)],
                [("    mac", TEXT), ("      \u2192 ", MUTED), ("70021", CORECONF)],
             ], size=13, title="example-wifi-ap@2026-10-05.sid")
    footer(s, 7)
    return s


# ================================================================ SLIDE 7 — YANG structure diagram (PlantUML-style)
def s_yang_diagram():
    s = slide()
    title_bar(s, "The wifi-ap model as a structure diagram",
              "example-wifi-ap rendered PlantUML-style \u2014 a container owning a keyed device list.")
    hdr_h = Inches(0.5)

    # wifi-ap "class" box
    bx, by, bw = Inches(0.8), Inches(1.75), Inches(5.2)
    roundrect(s, bx, by, bw, Inches(3.9), PANEL, line=AP, line_w=1.75, radius=0.03)
    rect(s, bx, by, bw, hdr_h, AP, line=None)
    text(s, bx, by + Inches(0.04), bw, Inches(0.42),
         [[("\u00ab container \u00bb  wifi-ap", 16, RGBColor(0x08, 0x12, 0x0B), True, FONT)]],
         align=PP_ALIGN.CENTER)
    rows = [
        ("+ ", "name", "string", CORECONF),
        ("+ ", "enabled", "boolean", CORECONF),
        ("+ ", "ssid", "string", CORECONF),
        ("+ ", "band", "wifi-band", CORECONF),
        ("+ ", "channel", "uint8 [1..196]", CORECONF),
        ("+ ", "tx-power", "uint8 dBm", CORECONF),
        ("+ ", "latency", "uint32 ms", CORECONF),
        ("~ ", "state", "identityref  {ro}", STATION),
    ]
    yy = by + hdr_h + Inches(0.1)
    for vis, name, typ, vcol in rows:
        text(s, bx + Inches(0.22), yy, bw - Inches(0.4), Inches(0.33),
             [[(vis, 13, vcol, True, MONO), (name.ljust(10), 13, TEXT, True, MONO),
               (": " + typ, 13, DEVICE, False, MONO)]], space_after=0)
        yy = Emu(yy + Inches(0.39))

    # device "class" box
    dx, dy, dw = Inches(7.3), Inches(2.45), Inches(5.0)
    roundrect(s, dx, dy, dw, Inches(3.0), PANEL, line=DEVICE, line_w=1.75, radius=0.03)
    rect(s, dx, dy, dw, hdr_h, DEVICE, line=None)
    text(s, dx, dy + Inches(0.04), dw, Inches(0.42),
         [[("\u00ab list \u00bb  device", 16, RGBColor(0x1A, 0x0D, 0x04), True, FONT)]],
         align=PP_ALIGN.CENTER)
    drows = [
        ("\U0001F511 ", "mac", "string  {key}", DANGER),
        ("+ ", "hostname", "string", CORECONF),
        ("+ ", "ip-address", "string", CORECONF),
        ("+ ", "signal-dbm", "int8 dBm", CORECONF),
        ("+ ", "connected", "boolean", CORECONF),
    ]
    yy = dy + hdr_h + Inches(0.14)
    for vis, name, typ, vcol in drows:
        text(s, dx + Inches(0.22), yy, dw - Inches(0.4), Inches(0.33),
             [[(vis, 13, vcol, True, MONO), (name.ljust(11), 13, TEXT, True, MONO),
               (": " + typ, 13, DEVICE, False, MONO)]], space_after=0)
        yy = Emu(yy + Inches(0.42))

    # composition connector  wifi-ap *-- device  (diamond + line + multiplicity)
    link_y = by + Inches(1.95)
    ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, bx + bw, link_y, dx - (bx + bw), Pt(2))
    ln.fill.solid(); ln.fill.fore_color.rgb = MUTED; ln.line.fill.background(); ln.shadow.inherit = False
    dia = s.shapes.add_shape(MSO_SHAPE.DIAMOND, bx + bw - Inches(0.13), link_y - Inches(0.11),
                             Inches(0.26), Inches(0.26))
    dia.fill.solid(); dia.fill.fore_color.rgb = AP; dia.line.color.rgb = AP; dia.shadow.inherit = False
    arr = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, dx - Inches(0.34), link_y - Inches(0.07),
                             Inches(0.34), Inches(0.16))
    arr.fill.solid(); arr.fill.fore_color.rgb = MUTED; arr.line.fill.background(); arr.shadow.inherit = False
    text(s, bx + bw, link_y - Inches(0.5), dx - (bx + bw), Inches(0.3),
         [[("1", 12, AP, True, MONO), ("        composition        ", 11, MUTED, False, MONO),
           ("0..*", 12, DEVICE, True, MONO)]], align=PP_ALIGN.CENTER)
    text(s, bx + bw, link_y + Inches(0.08), dx - (bx + bw), Inches(0.3),
         [[("key: mac", 11, MUTED, True, MONO)]], align=PP_ALIGN.CENTER)

    # legend ribbon
    roundrect(s, Inches(0.8), Inches(5.95), Inches(11.5), Inches(0.95), PANEL2, line=BORDER, radius=0.06)
    text(s, Inches(1.05), Inches(6.02), Inches(11.0), Inches(0.85),
         [[("+", 13, CORECONF, True, MONO), (" read-write (config)      ", 12, MUTED, False, FONT),
           ("~", 13, STATION, True, MONO), (" read-only {ro} state      ", 12, MUTED, False, FONT),
           ("\U0001F511", 12, DANGER, True, MONO), (" list key      ", 12, MUTED, False, FONT),
           ("\u25c6\u2014\u25b6", 13, AP, True, MONO), (" composition (owns)", 12, MUTED, False, FONT)],
          [("Same model the AP exposes over NETCONF upstream and CORECONF (SIDs) down to each device.",
            12, TEXT, False, FONT)]], space_after=4)
    footer(s, 6)
    return s


# ================================================================ SLIDE 8 — instances / encodings
def s_instances():
    s = slide()
    title_bar(s, "Same instance data, three encodings",
              'Set the AP latency target to 35 ms \u2014 identical semantics, very different byte counts.')
    # NETCONF XML
    code_box(s, Inches(0.6), Inches(1.8), Inches(7.6), Inches(2.15),
             [
                [('<rpc message-id="101"', TEXT)],
                [('     xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">', MUTED)],
                [('  <edit-config><target><running/></target>', TEXT)],
                [('    <config>', TEXT)],
                [('      <wifi-ap xmlns="urn:example:wifi-ap">', TEXT)],
                [('        <latency>', TEXT), ('35', DEVICE), ('</latency>', TEXT)],
                [('      </wifi-ap></config>', TEXT)],
                [('  </edit-config></rpc>', TEXT)],
             ], size=12.5, title="NETCONF \u2014 edit-config (XML)")
    # CORECONF CBOR
    code_box(s, Inches(0.6), Inches(4.15), Inches(7.6), Inches(2.2),
             [
                [("iPATCH /c   Content-Format: application/yang-instances+cbor-seq", MUTED)],
                [("", TEXT)],
                [("CBOR (diagnostic):  ", TEXT), ("{70010: {70017: 35}}", CORECONF)],
                [("                     ", TEXT), ("  \u2502       \u2514 latency value", MUTED)],
                [("                     ", TEXT), ("  \u2514 wifi-ap > latency SID", MUTED)],
                [("", TEXT)],
                [("CBOR (hex):  ", TEXT), ("A1 1A0001117A A1 1A00011181 1823", CORECONF)],
             ], size=12.5, title="CORECONF \u2014 iPATCH (CBOR + SID)")
    # right: size comparison bars
    roundrect(s, Inches(8.45), Inches(1.8), Inches(4.25), Inches(4.55), PANEL, line=BORDER, radius=0.04)
    text(s, Inches(8.7), Inches(1.95), Inches(3.8), Inches(0.4),
         [[("Payload size (real bytes)", 15, TEXT, True, FONT)]])
    # NETCONF bar (215)
    def bar(y, label, val, maxv, color):
        text(s, Inches(8.7), y, Inches(3.8), Inches(0.3),
             [[(label, 12, color, True, MONO)]])
        track_w = Inches(3.75)
        rect(s, Inches(8.7), y + Inches(0.3), track_w, Inches(0.34), CODEBG, line=BORDER)
        fill_w = Emu(int(track_w * (val / maxv)))
        if fill_w > 0:
            rect(s, Inches(8.7), y + Inches(0.3), fill_w, Inches(0.34), color, line=None)
        text(s, Inches(8.7), y + Inches(0.68), Inches(3.75), Inches(0.3),
             [[(f"{val} B", 12, TEXT, True, MONO)]], align=PP_ALIGN.RIGHT)
    bar(Inches(2.5), "NETCONF (XML)", 215, 215, NETCONF)
    bar(Inches(3.75), "CORECONF (CBOR/SID)", 14, 215, CORECONF)
    # ratio badge
    roundrect(s, Inches(8.9), Inches(5.0), Inches(3.35), Inches(1.1), PANEL2, line=CORECONF, radius=0.12)
    text(s, Inches(8.9), Inches(5.12), Inches(3.35), Inches(0.6),
         [[("15.4\u00d7", 34, CORECONF, True, FONT)]], align=PP_ALIGN.CENTER)
    text(s, Inches(8.9), Inches(5.68), Inches(3.35), Inches(0.4),
         [[("smaller payload (215 B \u2192 14 B)", 12, MUTED, False, FONT)]],
         align=PP_ALIGN.CENTER)
    footer(s, 8)
    return s


# ================================================================ SLIDE 9 — the cascade
def s_cascade():
    s = slide()
    title_bar(s, 'Processing "set latency = 35 ms" across the chain',
              "A single manager action cascades down four nodes \u2014 NETCONF upstream, CORECONF to the device.")
    # four nodes along a line
    cy = Inches(2.7)
    xs = [Inches(1.4), Inches(4.6), Inches(7.8), Inches(11.0)]
    node(s, xs[0], cy, "\U0001F4BB", "Mgmt Station", "NETCONF mgr", STATION)
    node(s, xs[1], cy, "\U0001F50C", "Switch", "802.3", SWITCH)
    node(s, xs[2], cy, "\U0001F4F6", "Wi-Fi AP", "coap:/c", AP)
    node(s, xs[3], cy, "\U0001F4F1", "Device", "CORECONF", DEVICE)
    # segments + protocol + size
    segs = [
        (xs[0], xs[1], "NETCONF", NETCONF, "edit-config \u00b7 XML \u00b7 215 B"),
        (xs[1], xs[2], "NETCONF", NETCONF, "edit-config \u00b7 XML \u00b7 215 B"),
        (xs[2], xs[3], "CORECONF", CORECONF, "iPATCH \u00b7 CBOR/SID \u00b7 14 B"),
    ]
    for x1, x2, proto, color, size in segs:
        shaft = x1 + Inches(0.62)
        w = x2 - x1 - Inches(1.24)
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, shaft, cy - Inches(0.09), w, Inches(0.18))
        a.fill.solid(); a.fill.fore_color.rgb = color
        a.line.fill.background(); a.shadow.inherit = False
        text(s, shaft, cy - Inches(0.62), w, Inches(0.3),
             [[(proto, 12, color, True, MONO)]], align=PP_ALIGN.CENTER)
        text(s, shaft, cy + Inches(0.18), w, Inches(0.3),
             [[(size, 10.5, MUTED, False, MONO)]], align=PP_ALIGN.CENTER)
    # step-by-step processing cards
    y = Inches(4.5)
    steps = [
        ("1 \u00b7 Station", STATION,
         "Manager issues edit-config setting wifi-ap/latency = 35 (XML over SSH)."),
        ("2 \u00b7 Switch", SWITCH,
         "Validates against YANG, forwards the same edit-config to the AP (NETCONF)."),
        ("3 \u00b7 Access Point", AP,
         "Translates to CORECONF: iPATCH /c with {70010:{70017:35}} (CBOR/SID)."),
        ("4 \u00b7 Device", DEVICE,
         "Applies the leaf, replies 2.04 Changed; ack propagates back up the chain."),
    ]
    x = Inches(0.6)
    w = Inches(2.95)
    for name, color, body in steps:
        roundrect(s, x, y, w, Inches(1.95), PANEL, line=color, radius=0.05)
        rect(s, x, y, w, Inches(0.5), PANEL2, line=None)
        text(s, x + Inches(0.15), y + Inches(0.07), w - Inches(0.3), Inches(0.4),
             [[(name, 14, color, True, FONT)]])
        text(s, x + Inches(0.15), y + Inches(0.6), w - Inches(0.3), Inches(1.25),
             [[(body, 12, TEXT, False, FONT)]])
        x = x + w + Inches(0.18)
    footer(s, 9)
    return s


# ================================================================ SLIDE 10 — value: constrained
def s_value_constrained():
    s = slide()
    title_bar(s, "Why CORECONF for constrained applications",
              "Built for the IoT edge: tiny payloads, no TCP, no XML parser.")
    cards = [
        ("\U0001F4E6  Tiny payloads", CORECONF,
         ["CBOR + numeric SIDs replace verbose XML tag names.",
          "15\u00d7 smaller on the wire in this demo (215 B \u2192 14 B).",
          "Fits a single UDP datagram \u2014 no fragmentation."]),
        ("\U0001F50B  Low power & memory", DEVICE,
         ["No TCP/TLS session state to maintain.",
          "No XML/JSON parser needed on the device.",
          "Less airtime \u2192 longer battery life on radios."]),
        ("\U0001F4E1  Lossy-network friendly", STATION,
         ["CoAP over UDP tolerates intermittent links.",
          "Confirmable messages give lightweight reliability.",
          "OSCORE (RFC 8613) secures without a TLS handshake."]),
        ("\U0001F501  Same model, no rework", AP,
         ["Reuse existing YANG modules unchanged.",
          "SIDs are a deterministic numeric mapping (RFC 9595).",
          "Tooling validates the same constraints end to end."]),
    ]
    positions = [(Inches(0.6), Inches(1.75)), (Inches(6.75), Inches(1.75)),
                 (Inches(0.6), Inches(4.35)), (Inches(6.75), Inches(4.35))]
    for (title, color, items), (x, y) in zip(cards, positions):
        bullet_card(s, x, y, Inches(5.95), Inches(2.4), title, items, color)
    footer(s, 10)
    return s


# ================================================================ SLIDE 11 — value: hybrid
def s_value_hybrid():
    s = slide()
    title_bar(s, "Value of a hybrid YANG + NETCONF/CORECONF stack",
              "Model once; choose the protocol that fits each hop.")
    # center diagram: core uses NETCONF, edge uses CORECONF, shared YANG
    roundrect(s, Inches(0.6), Inches(1.75), Inches(12.1), Inches(1.5), PANEL, line=DEVICE, radius=0.04)
    text(s, Inches(0.9), Inches(1.9), Inches(11.5), Inches(0.5),
         [[("One set of YANG models  (RFC 7950 + NMDA, RFC 8342)", 17, DEVICE, True, FONT)]],
         align=PP_ALIGN.CENTER)
    chip(s, Inches(2.2), Inches(2.55), Inches(2.6), "example-switch", SWITCH, 12)
    chip(s, Inches(5.35), Inches(2.55), Inches(2.6), "example-wifi-ap", AP, 12)
    chip(s, Inches(8.5), Inches(2.55), Inches(2.6), "example-device", DEVICE, 12)
    # two branches
    arrow(s, Inches(3.6), Inches(3.55), Inches(1.2), NETCONF)
    arrow(s, Inches(8.5), Inches(3.55), Inches(1.2), CORECONF)
    roundrect(s, Inches(0.6), Inches(4.0), Inches(5.95), Inches(1.75), PANEL, line=NETCONF, radius=0.05)
    text(s, Inches(0.85), Inches(4.12), Inches(5.5), Inches(1.6),
         [[("Core / managed network", 16, NETCONF, True, FONT)],
          [("NETCONF + RESTCONF", 13, TEXT, True, MONO)],
          [("Rich transactions, candidate datastores,", 12, MUTED, False, FONT)],
          [("mature tooling for switches & routers.", 12, MUTED, False, FONT)]], space_after=3)
    roundrect(s, Inches(6.75), Inches(4.0), Inches(5.95), Inches(1.75), PANEL, line=CORECONF, radius=0.05)
    text(s, Inches(7.0), Inches(4.12), Inches(5.5), Inches(1.6),
         [[("Constrained edge", 16, CORECONF, True, FONT)],
          [("CORECONF", 13, TEXT, True, MONO)],
          [("CBOR/SID over CoAP for battery- and", 12, MUTED, False, FONT)],
          [("bandwidth-limited IoT endpoints.", 12, MUTED, False, FONT)]], space_after=3)
    # bottom takeaways
    roundrect(s, Inches(0.6), Inches(5.95), Inches(12.1), Inches(0.95), PANEL2, line=BORDER, radius=0.06)
    text(s, Inches(0.85), Inches(6.02), Inches(11.6), Inches(0.85),
         [[("Takeaway:  ", 14, DEVICE, True, FONT),
           ("one data model, one skill set, one validation pipeline \u2014 ", 13, TEXT, False, FONT),
           ("open IETF standards, no vendor lock-in, and the right encoding on every hop.",
            13, TEXT, True, FONT)]], space_after=0)
    footer(s, 11)
    return s


# ================================================================ SLIDE 12 — thanks & questions
def s_thanks():
    s = slide()
    # decorative accent band (mirrors the title slide)
    rect(s, 0, Inches(2.72), EMU_W, Inches(0.06), NETCONF, line=None)
    text(s, Inches(0.9), Inches(1.5), Inches(11.5), Inches(1.3),
         [[("Thanks \u2014 Questions?", 46, TEXT, True, FONT)]])
    text(s, Inches(0.92), Inches(3.0), Inches(11.5), Inches(0.8),
         [[("One data model, the right protocol on every hop.", 20, NETCONF, True, FONT)]])
    # contact card
    cy = Inches(4.1)
    roundrect(s, Inches(0.9), cy, Inches(6.6), Inches(1.6), PANEL, line=BORDER, radius=0.06)
    rect(s, Inches(0.9), cy, Inches(0.1), Inches(1.6), CORECONF, line=None)
    text(s, Inches(1.25), cy + Inches(0.22), Inches(6.0), Inches(0.5),
         [[("Scott Mansfield", 24, TEXT, True, FONT)]])
    text(s, Inches(1.27), cy + Inches(0.92), Inches(6.0), Inches(0.5),
         [[("\u2709  ", 15, DEVICE, True, FONT),
           ("scott.mansfield@ericsson.com", 17, STATION, False, MONO)]])
    # protocol chips (echo the title slide)
    y = Inches(6.05)
    chip(s, Inches(0.92), y, Inches(2.3), "NETCONF \u00b7 XML/SSH", NETCONF, size=13)
    chip(s, Inches(3.42), y, Inches(2.5), "RESTCONF \u00b7 JSON/HTTP", RESTCONF, size=13)
    chip(s, Inches(6.12), y, Inches(2.7), "CORECONF \u00b7 CBOR/CoAP", CORECONF, size=13)
    return s


# ---------------------------------------------------------------- build
s_title()
s_yang_netconf()
s_family()
s_netconf_stack()
s_coreconf_stack()
s_yang_diagram()
s_yang_snippet()
s_instances()
s_cascade()
s_value_constrained()
s_value_hybrid()
s_thanks()

OUT = "yang-coreconf-overview.pptx"
prs.save(OUT)
print(f"wrote {OUT}  ({len(prs.slides._sldIdLst)} slides)")
