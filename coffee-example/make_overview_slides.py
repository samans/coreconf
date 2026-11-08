#!/usr/bin/env python3
"""
Generate a PowerPoint deck that mirrors the flow of
IETF_CORE_CoAP_CORECONF_Overview.pptx — same sections, overviews, and
NETCONF/CORECONF information — but with all models, instances, and worked
examples rewritten around the *coffee-maker fleet* example in this repo.

    [coffee-maker manager] --CORECONF--> [coffee-maker fleet datastore]

Run:
    .venv/bin/python3 make_overview_slides.py
Produces:
    IETF_CORE_CoAP_CORECONF_Overview_Coffee.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---------------------------------------------------------------- palette
BG        = RGBColor(0x0B, 0x0F, 0x14)
PANEL     = RGBColor(0x12, 0x18, 0x23)
PANEL2    = RGBColor(0x19, 0x21, 0x2E)
BORDER    = RGBColor(0x27, 0x30, 0x40)
TEXT      = RGBColor(0xE6, 0xED, 0xF3)
MUTED     = RGBColor(0x8B, 0x98, 0xA9)
MANAGER   = RGBColor(0x58, 0xA6, 0xFF)   # blue
FLEET     = RGBColor(0xD2, 0x99, 0x22)   # amber
COREBREW  = RGBColor(0xC0, 0x84, 0x57)   # coffee brown
NETCONF   = RGBColor(0xF0, 0x88, 0x3E)   # orange (the big one)
CORECONF  = RGBColor(0x3F, 0xB9, 0x50)   # green  (the small one)
RESTCONF  = RGBColor(0x58, 0xA6, 0xFF)   # blue
ACCENT    = RGBColor(0xA3, 0x71, 0xF7)   # purple
DANGER    = RGBColor(0xF8, 0x51, 0x49)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
CODEBG    = RGBColor(0x06, 0x0A, 0x0F)

FONT      = "Segoe UI"
MONO      = "Consolas"

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
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(4); tf.margin_right = Pt(4)
    tf.margin_top = Pt(2); tf.margin_bottom = Pt(2)
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
    rect(s, Inches(0.6), Inches(0.55), Inches(0.14), Inches(0.62), NETCONF, line=None)
    text(s, Inches(0.9), Inches(0.45), Inches(11.8), Inches(0.9),
         [[(label, 29, TEXT, True, FONT)]])
    if sub:
        text(s, Inches(0.92), Inches(1.15), Inches(11.6), Inches(0.5),
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
    if title:
        th = Inches(0.32)
        hdr = roundrect(s, x, y, w, th, PANEL2, line=BORDER, radius=0.12)
        tf = hdr.text_frame; tf.margin_left = Pt(8)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = title
        r.font.size = Pt(11); r.font.bold = True; r.font.name = MONO
        r.font.color.rgb = MUTED
        y = Emu(y + th + Inches(0.02))
        h = Emu(h - th - Inches(0.02))
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


def bullet_card(s, x, y, w, h, heading, items, accent, head_size=17, body=13):
    roundrect(s, x, y, w, h, PANEL, line=BORDER, radius=0.04)
    rect(s, x, y, Inches(0.08), h, accent, line=None)
    runs = [[(heading, head_size, accent, True, FONT)]]
    for it in items:
        if isinstance(it, tuple):
            lead, rest = it
            runs.append([("\u2022  ", body, accent, True, FONT),
                         (lead, body, TEXT, True, FONT),
                         (rest, body, MUTED, False, FONT)])
        else:
            runs.append([("\u2022  ", body, accent, True, FONT),
                         (it, body, TEXT, False, FONT)])
    text(s, x + Inches(0.28), y + Inches(0.18), w - Inches(0.5), h - Inches(0.3),
         runs, space_after=7)


def node(s, cx, cy, icon, name, sub, color, r=Inches(0.52)):
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


def section_divider(s, kicker, title, color=NETCONF):
    rect(s, 0, Inches(2.9), EMU_W, Inches(0.06), color, line=None)
    text(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(0.6),
         [[(kicker, 16, color, True, MONO)]])
    text(s, Inches(0.9), Inches(3.1), Inches(11.5), Inches(1.4),
         [[(title, 36, TEXT, True, FONT)]])


def footer(s, n=None):
    # Page number is derived from the live slide count so inserting or
    # reordering slides never requires manual renumbering.
    page = len(prs.slides._sldIdLst)
    text(s, Inches(0.6), Inches(7.08), Inches(11), Inches(0.3),
         [[("IETF CoAP / CORE / CORECONF \u2014 coffee-maker fleet example",
            10, MUTED, False, FONT)]])
    text(s, Inches(12.3), Inches(7.08), Inches(0.8), Inches(0.3),
         [[(str(page), 10, MUTED, False, FONT)]], align=PP_ALIGN.RIGHT)


# keyword/type colors for code
K = MANAGER   # keywords
T = FLEET     # types
V = CORECONF  # values / SIDs


# ================================================================ 1 — title
def s01_title():
    s = slide()
    rect(s, 0, Inches(2.72), EMU_W, Inches(0.06), NETCONF, line=None)
    text(s, Inches(0.9), Inches(1.4), Inches(11.5), Inches(1.2),
         [[("Introduction to IETF CoAP, CORE, and CORECONF", 40, TEXT, True, FONT)]])
    text(s, Inches(0.92), Inches(2.9), Inches(11.5), Inches(0.9),
         [[("with YANG Tooling", 28, NETCONF, True, FONT)]])
    text(s, Inches(0.92), Inches(3.75), Inches(11.5), Inches(0.9),
         [[("Exploring protocols and tools for IoT network management \u2014 "
            "worked through a fleet of coffee makers.", 17, MUTED, False, FONT)]])
    y = Inches(5.0)
    chip(s, Inches(0.92), y, Inches(2.3), "NETCONF \u00b7 XML/SSH", NETCONF, size=13)
    chip(s, Inches(3.42), y, Inches(2.5), "RESTCONF \u00b7 JSON/HTTP", RESTCONF, size=13)
    chip(s, Inches(6.12), y, Inches(2.7), "CORECONF \u00b7 CBOR/CoAP", CORECONF, size=13)
    text(s, Inches(0.92), Inches(6.2), Inches(11.5), Inches(0.5),
         [[("Running example:  ", 14, MUTED, False, FONT),
           ("coffee-maker manager", 14, MANAGER, True, MONO),
           ("  \u2192 CORECONF \u2192  ", 14, CORECONF, True, MONO),
           ("fleet of coffee makers", 14, FLEET, True, MONO)]])
    return s


# ================================================================ 2 — section: context
def s02_section_context():
    s = slide()
    section_divider(s, "PART 1", "Context and Scope of the Presentation", NETCONF)
    footer(s, 2)
    return s


# ================================================================ 3 — goals & scope
def s03_goals():
    s = slide()
    title_bar(s, "Presentation Goals and Technical Scope",
              "What we cover \u2014 grounded in the coffee-maker fleet demo.")
    cards = [
        ("Introduction to IETF CORE", MANAGER,
         "The IETF CORE working group and the CoAP protocol as the foundation "
         "for managing constrained devices \u2014 here, networked coffee makers."),
        ("CORE Architecture & CORECONF", CORECONF,
         "CORE building blocks and CORECONF: YANG over CoAP with compact "
         "CBOR + numeric-SID encoding, driving the coffee-maker fleet."),
        ("Interoperability & YANG Reuse", RESTCONF,
         "One example-coffee-maker YANG model reused across NETCONF, "
         "RESTCONF, and CORECONF for seamless integration."),
        ("Tools & Workflows", FLEET,
         "YANG validation, SID assignment, CBOR encoding, and CoAP client/"
         "server libraries \u2014 the pieces used to build this demo."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 3)
    return s


# ================================================================ 4 — section: CoAP
def s04_section_coap():
    s = slide()
    section_divider(s, "PART 2", "IETF CORE and CoAP Fundamentals", CORECONF)
    footer(s, 4)
    return s


# ================================================================ 5 — CORE WG mission
def s05_core_wg():
    s = slide()
    title_bar(s, "IETF CORE Working Group and Its Mission",
              "Constrained RESTful Environments \u2014 why it exists.")
    cards = [
        ("Purpose of CORE WG", MANAGER,
         "Standardizes protocols for constrained devices that cannot run full "
         "web stacks \u2014 like a low-power coffee maker's controller."),
        ("Core Mission & Principles", CORECONF,
         "Adapts web principles (REST, stateless interactions) to unreliable, "
         "constrained networks."),
        ("Technology Integration", RESTCONF,
         "Aligns with IPv6, UDP, and DTLS/OSCORE to ensure interoperability "
         "and clean network integration."),
        ("IoT Management Foundation", FLEET,
         "Enables standardized monitoring, configuration, and control at scale "
         "\u2014 e.g. a whole building's fleet of coffee makers."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 5)
    return s


# ================================================================ 6 — CoAP overview
def s06_coap_overview():
    s = slide()
    title_bar(s, "Constrained Application Protocol (CoAP) Overview",
              "A lightweight RESTful protocol over UDP (RFC 7252).")
    cards = [
        ("CoAP Protocol Basics", MANAGER,
         "Lightweight UDP-based protocol providing RESTful operations over "
         "constrained networks."),
        ("Message Format & REST Methods", CORECONF,
         "Compact binary message format supporting GET, PUT, POST, DELETE "
         "\u2014 CORECONF adds FETCH and iPATCH."),
        ("Reliability & Async Support", RESTCONF,
         "Confirmable messages + retransmissions; asynchronous updates via the "
         "Observe extension (watch a maker go empty)."),
        ("Security Features", FLEET,
         "Secured with DTLS for channel security or OSCORE for end-to-end "
         "message protection of each command."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 6)
    return s


# ================================================================ 7 — CoAP concepts / REST map
def s07_coap_rest():
    s = slide()
    title_bar(s, "Key CoAP Concepts and REST Mapping",
              "Resources, methods, and response codes \u2014 applied to the fleet.")
    bullet_card(s, Inches(0.6), Inches(1.75), Inches(5.9), Inches(2.3),
                "Resource Identification", [
                    ("Single resource ", "the fleet datastore lives at one URI: coap://host/c."),
                    ("A maker ", "is a list entry keyed by id (kitchen, lobby, lab...).")],
                MANAGER)
    bullet_card(s, Inches(6.8), Inches(1.75), Inches(5.9), Inches(2.3),
                "CoAP Methods and Responses", [
                    ("GET / FETCH ", "read fleet state; iPATCH writes."),
                    ("POST ", "invokes an action (brew / refill)."),
                    ("Codes ", "2.05 Content, 2.04 Changed, 4.03 Forbidden.")],
                CORECONF)
    bullet_card(s, Inches(0.6), Inches(4.3), Inches(5.9), Inches(2.3),
                "Observe & Content Negotiation", [
                    ("Observe ", "clients get pushed updates when a maker runs low."),
                    ("Content-Format ", "negotiates compact CBOR (id=sid).")],
                RESTCONF)
    bullet_card(s, Inches(6.8), Inches(4.3), Inches(5.9), Inches(2.3),
                "Proxying & Caching", [
                    ("Proxies ", "bridge CoAP and HTTP for dashboards."),
                    ("Caching ", "cuts transmissions over lossy links.")],
                FLEET)
    footer(s, 7)
    return s


# ================================================================ 8 — section: architecture
def s08_section_arch():
    s = slide()
    section_divider(s, "PART 3", "CORE Architecture and Management Motivation", ACCENT)
    footer(s, 8)
    return s


# ================================================================ 9 — CORE building blocks
def s09_building_blocks():
    s = slide()
    title_bar(s, "CORE Architectural Building Blocks",
              "The pieces that make constrained management work.")
    cards = [
        ("CoAP Protocol Core", MANAGER,
         "The central RESTful transfer protocol enabling interoperable "
         "communication between the manager and each coffee maker."),
        ("Resource Discovery", CORECONF,
         "CoRE Link Format and Resource Directory dynamically find device "
         "functions \u2014 discovering makers as they join the fleet."),
        ("Security Components", DANGER,
         "DTLS for transport and OSCORE for end-to-end object security "
         "(alice = operator, bob = viewer in the demo)."),
        ("Efficient Data Encoding", FLEET,
         "CBOR and YANG-CBOR give compact representations \u2014 a power "
         "toggle is ~21 B instead of ~285 B of XML."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 9)
    return s


# ================================================================ 10 — why management over CoAP
def s10_why_coap():
    s = slide()
    title_bar(s, "Why Device Management over CoAP Is Needed",
              "The case for CORECONF on a fleet of constrained makers.")
    cards = [
        ("Constraints of Traditional Protocols", DANGER,
         "NETCONF/SSH and RESTCONF/HTTP assume capable devices and reliable "
         "networks \u2014 too heavy for a cheap coffee-maker controller."),
        ("Need for Standardized IoT Management", MANAGER,
         "Operators need scalable, standard methods for configuration, "
         "firmware, and security across hundreds of makers."),
        ("Advantages of CoAP Management", CORECONF,
         "UDP + compact encoding cut protocol overhead, optimizing CPU, RAM, "
         "and radio use on each device."),
        ("CORECONF and YANG Integration", FLEET,
         "CORECONF applies the example-coffee-maker YANG model for "
         "consistent, model-driven management of the whole fleet."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 10)
    return s


# ================================================================ 11 — section: CORECONF/YANG
def s11_section_coreconf():
    s = slide()
    section_divider(s, "PART 4", "CORECONF and YANG-Based Management", CORECONF)
    footer(s, 11)
    return s


# ================================================================ 12 — CORECONF principles
def s12_principles():
    s = slide()
    title_bar(s, "CORECONF Concept and Design Principles",
              "RESTCONF ideas, shrunk for constrained coffee makers.")
    cards = [
        ("Adaptation of RESTCONF", MANAGER,
         "CORECONF adapts RESTCONF principles for constrained devices using "
         "YANG models and CoAP transport."),
        ("Efficient Data Encoding", CORECONF,
         "CBOR encoding of YANG data, keyed by numeric SIDs, slashes message "
         "size and parsing cost."),
        ("Secure Network Operation", DANGER,
         "Supports secure operation with DTLS or OSCORE \u2014 so 'turn on "
         "the coffee maker' can't be read or forged."),
        ("Design Emphasizing Reuse", FLEET,
         "Mirrors RESTCONF's datastore, URI, and CRUD concepts, mapped "
         "efficiently onto CoAP methods."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 12)
    return s


# ================================================================ 13 — how operations work (flow)
def s13_operations():
    s = slide()
    title_bar(s, "How CORECONF Operations Work",
              "manager \u2192 fleet: real CoAP/CBOR/SID exchanges on /c.")
    cx_c = Inches(2.3)
    cx_s = Inches(11.0)
    node(s, cx_c, Inches(2.3), "\U0001F916", "Coffee Manager", "CORECONF client", MANAGER, r=Inches(0.5))
    node(s, cx_s, Inches(2.3), "\u2615", "Coffee Fleet", "coap://host/c", FLEET, r=Inches(0.5))
    for cx in (cx_c, cx_s):
        ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx - Emu(int(Pt(0.75))),
                                Inches(3.0), Pt(1.5), Inches(3.1))
        ln.fill.solid(); ln.fill.fore_color.rgb = BORDER; ln.line.fill.background()
        ln.shadow.inherit = False
    msgs = [
        ("GET /c", CORECONF, True, Inches(3.3)),
        ("2.05 Content  {60010:{...makers}}", FLEET, False, Inches(3.95)),
        ("iPATCH /c  {60010:{60020:[{60021:\"lab\",60023:true}]}}", CORECONF, True, Inches(4.75)),
        ("2.04 Changed", FLEET, False, Inches(5.4)),
        ("POST /c  brew 'lab'", CORECONF, True, Inches(6.05)),
    ]
    for label, color, l2r, y in msgs:
        x1, x2 = (cx_c, cx_s) if l2r else (cx_s, cx_c)
        shaft = min(x1, x2)
        a = s.shapes.add_shape(
            MSO_SHAPE.RIGHT_ARROW if l2r else MSO_SHAPE.LEFT_ARROW,
            shaft, y, abs(x2 - x1), Inches(0.17))
        a.fill.solid(); a.fill.fore_color.rgb = color
        a.line.fill.background(); a.shadow.inherit = False
        text(s, shaft, y - Inches(0.30), abs(x2 - x1), Inches(0.3),
             [[(label, 11, color, True, MONO)]], align=PP_ALIGN.CENTER)
    text(s, Inches(0.9), Inches(6.45), Inches(11.5), Inches(0.5),
         [[("Mapping ", 12, MUTED, False, FONT),
           ("YANG nodes \u2192 CoAP resources", 12, MANAGER, True, FONT),
           ("; URIs reflect paths, payloads are CBOR; error codes + CoAP "
            "reliability give monitoring without constant polling.", 12, MUTED, False, FONT)]])
    footer(s, 13)
    return s


# ================================================================ 14 — comparison table
def s14_comparison():
    s = slide()
    title_bar(s, "Comparison with NETCONF and RESTCONF",
              "Same example-coffee-maker model \u2014 three transports & encodings.")
    cols = ["Protocol", "Transport", "Encoding", "Target Devices"]
    rows = [
        ("NETCONF", "SSH", "XML", "Network infrastructure, servers", NETCONF),
        ("RESTCONF", "HTTP / TLS", "JSON or XML", "Moderately capable devices", RESTCONF),
        ("CORECONF", "CoAP / DTLS or OSCORE", "CBOR + SIDs", "Constrained IoT (coffee makers)", CORECONF),
    ]
    x0 = Inches(0.6)
    widths = [Inches(2.4), Inches(3.1), Inches(2.6), Inches(4.0)]
    y = Inches(1.9)
    hh = Inches(0.55)
    # header
    cx = x0
    for c, w in zip(cols, widths):
        rect(s, cx, y, w, hh, PANEL2, line=BORDER)
        text(s, cx, y + Inches(0.08), w, Inches(0.4),
             [[(c, 14, TEXT, True, FONT)]], align=PP_ALIGN.CENTER)
        cx = Emu(cx + w)
    y = Emu(y + hh)
    rh = Inches(1.0)
    for proto, transport, enc, target, color in rows:
        cx = x0
        vals = [proto, transport, enc, target]
        for i, (val, w) in enumerate(zip(vals, widths)):
            rect(s, cx, y, w, rh, PANEL, line=BORDER)
            col = color if i == 0 else TEXT
            bold = i == 0
            text(s, cx, y + Inches(0.28), w, Inches(0.5),
                 [[(val, 14 if i == 0 else 13, col, bold, FONT if i == 0 else MONO)]],
                 align=PP_ALIGN.CENTER)
            cx = Emu(cx + w)
        # accent stripe on the left edge of the row
        rect(s, x0, y, Inches(0.06), rh, color, line=None)
        y = Emu(y + rh)
    text(s, Inches(0.6), Inches(6.5), Inches(12), Inches(0.5),
         [[("Take-away:  ", 14, FLEET, True, FONT),
           ("the model never changes \u2014 only the wire format does. CORECONF "
            "picks the smallest one for the makers.", 14, MUTED, False, FONT)]])
    footer(s, 14)
    return s


# ================================================================ 15 — section: tooling
def s15_section_tooling():
    s = slide()
    section_divider(s, "PART 5", "YANG Tooling and Practical Workflows", FLEET)
    footer(s, 15)
    return s


# ================================================================ 16 — the coffee YANG model
def s16_yang_model():
    s = slide()
    title_bar(s, "Example: the coffee-maker fleet YANG model",
              "example-coffee-maker@2026-10-18 \u2014 one model, shared by every protocol.")
    code_box(s, Inches(0.6), Inches(1.75), Inches(7.3), Inches(5.0),
             [
                [("container ", K), ("coffee-maker-manager ", TEXT), ("{", MUTED)],
                [("  leaf ", K), ("name ", TEXT), ("{ type ", K), ("string", T), ("; }", MUTED)],
                [("  leaf ", K), ("maker-count ", TEXT), ("{ type ", K), ("uint8", T),
                 ("; config ", K), ("false", DANGER), ("; }", MUTED)],
                [("  list ", K), ("coffee-maker ", TEXT), ("{ key ", K), ('"id"', V), (";", MUTED)],
                [("    leaf ", K), ("id        ", TEXT), ("{ type ", K), ("string", T), ("; }", MUTED)],
                [("    leaf ", K), ("power     ", TEXT), ("{ type ", K), ("boolean", T), ("; }", MUTED)],
                [("    leaf ", K), ("cups      ", TEXT), ("{ type ", K), ("uint8", T),
                 (" { range ", K), ('"1..12"', V), ("; } }", MUTED)],
                [("    leaf ", K), ("strength  ", TEXT), ("{ type ", K),
                 ("enumeration", T), (" {mild,medium,strong} }", MUTED)],
                [("    leaf ", K), ("state     ", TEXT), ("{ ", MUTED), ("config ", K),
                 ("false", DANGER), ("; identityref }", MUTED)],
                [("    leaf ", K), ("water-level ", TEXT), ("{ ", MUTED), ("config ", K),
                 ("false", DANGER), ("; uint8 % }", MUTED)],
                [("    leaf ", K), ("beans-level ", TEXT), ("{ ", MUTED), ("config ", K),
                 ("false", DANGER), ("; uint8 % }", MUTED)],
                [("    leaf ", K), ("has-coffee  ", TEXT), ("{ ", MUTED), ("config ", K),
                 ("false", DANGER), ("; boolean }", MUTED)],
                [("    action ", K), ("brew   ", TEXT), ("{ output {started, reason} }", MUTED)],
                [("    action ", K), ("refill ", TEXT), ("{ in {beans,water} out {levels} }", MUTED)],
                [("  }", MUTED)],
                [("}", MUTED)],
             ], size=12.5, title="yang/example-coffee-maker@2026-10-18.yang")
    code_box(s, Inches(8.15), Inches(1.75), Inches(4.55), Inches(5.0),
             [
                [("# .sid file \u2192 numeric SIDs", MUTED)],
                [("coffee-maker-manager", TEXT), (" \u2192 ", MUTED), ("60010", V)],
                [("  coffee-maker (list)", TEXT), (" \u2192 ", MUTED), ("60020", V)],
                [("    id   (key)", TEXT), (" \u2192 ", MUTED), ("60021", V)],
                [("    power", TEXT), (" \u2192 ", MUTED), ("60023", V)],
                [("    cups", TEXT), (" \u2192 ", MUTED), ("60024", V)],
                [("    strength", TEXT), (" \u2192 ", MUTED), ("60025", V)],
                [("    state", TEXT), (" \u2192 ", MUTED), ("60026", V)],
                [("    water-level", TEXT), (" \u2192 ", MUTED), ("60027", V)],
                [("    beans-level", TEXT), (" \u2192 ", MUTED), ("60028", V)],
                [("    has-coffee", TEXT), (" \u2192 ", MUTED), ("60029", V)],
                [("    brew  (action)", TEXT), (" \u2192 ", MUTED), ("60032", V)],
                [("    refill(action)", TEXT), (" \u2192 ", MUTED), ("60035", V)],
                [("", MUTED)],
                [("SIDs replace long path", MUTED)],
                [("strings on the wire.", MUTED)],
             ], size=12.5, title="example-coffee-maker@2026-10-18.sid")
    footer(s, 16)
    return s


# ================================================================ 17 — tooling required
def s17_tooling():
    s = slide()
    title_bar(s, "Tooling Required for YANG and CORECONF",
              "What built (and validates) the coffee-maker demo.")
    cards = [
        ("YANG Compilers & Validators", MANAGER,
         "pyang / yanglint verify the example-coffee-maker module's syntax "
         "and semantics before anything ships."),
        ("CBOR Encoding Libraries", CORECONF,
         "cbor2 (+ YANG-CBOR/SID mapping in coffee_sids.py) serialize the "
         "fleet payloads efficiently."),
        ("CoAP Client & Server Libraries", FLEET,
         "aiocoap runs server.py (the fleet datastore) and the manager "
         "client \u2014 handling retransmits, Content-Formats, OSCORE."),
        ("Integration & Testing Tools", RESTCONF,
         "The web console + flow_client.py act as a simulator/test harness, "
         "validating model and protocol interoperability."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 17)
    return s


# ================================================================ 18 — end-to-end workflow
def s18_workflow():
    s = slide()
    title_bar(s, "Typical End-to-End YANG and CORECONF Workflow",
              "From model to a running, managed coffee-maker fleet.")
    steps = [
        ("1", "Model Selection & Validation", MANAGER,
         "Author / pick example-coffee-maker; validate with pyang and assign "
         "SIDs in the .sid file."),
        ("2", "Processing for Constrained Devices", CORECONF,
         "Map the model to numeric SIDs and CBOR; embed the resulting schema "
         "into each maker's firmware."),
        ("3", "Device & Client Integration", FLEET,
         "server.py exposes the fleet at /c (optionally OSCORE-secured); the "
         "manager uses YANG-aware CBOR encoders."),
        ("4", "Testing & Unified Deployment", RESTCONF,
         "The web console drives interoperability tests; the same model gives "
         "unified management across the fleet."),
    ]
    x = Inches(0.6)
    w = Inches(2.95)
    gap = Inches(0.17)
    for num, head, color, body in steps:
        roundrect(s, x, Inches(1.9), w, Inches(4.2), PANEL, line=color, line_w=1.5, radius=0.04)
        circ = s.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.25), Inches(2.15),
                                  Inches(0.7), Inches(0.7))
        circ.fill.solid(); circ.fill.fore_color.rgb = color
        circ.line.fill.background(); circ.shadow.inherit = False
        tf = circ.text_frame; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        rr = p.add_run(); rr.text = num; rr.font.size = Pt(22); rr.font.bold = True
        rr.font.color.rgb = BG
        text(s, x + Inches(0.25), Inches(3.05), w - Inches(0.5), Inches(1.0),
             [[(head, 15, color, True, FONT)]])
        text(s, x + Inches(0.25), Inches(3.95), w - Inches(0.5), Inches(2.0),
             [[(body, 12.5, MUTED, False, FONT)]])
        if x < Inches(9):
            arrow(s, Emu(x + w + Inches(0.01)), Inches(3.9), gap, MUTED)
        x = Emu(x + w + gap)
    footer(s, 18)
    return s


# ================================================================ 19 — takeaways
def s19_takeaways():
    s = slide()
    title_bar(s, "Key Takeaways and Summary",
              "CoAP + CORE + CORECONF, proven on the coffee-maker fleet.")
    cards = [
        ("Comprehensive IoT Management", MANAGER,
         "CoAP, IETF CORE, and CORECONF together manage constrained devices "
         "\u2014 a whole fleet of coffee makers \u2014 efficiently."),
        ("Protocol Reuse & Consistency", CORECONF,
         "CORECONF reuses the one YANG model and RESTCONF semantics, "
         "protecting existing investments."),
        ("Mature Tooling Ecosystem", FLEET,
         "pyang, cbor2, and aiocoap support real deployments with "
         "standardized, repeatable workflows."),
        ("Scalable & Secure Management", RESTCONF,
         "CBOR/SID keeps messages tiny (~13\u00d7 smaller than XML) and OSCORE "
         "keeps commands private and authorized."),
    ]
    xs = [Inches(0.6), Inches(6.8)]
    ys = [Inches(1.75), Inches(4.3)]
    i = 0
    for yy in ys:
        for xx in xs:
            h, c, body = cards[i]
            bullet_card(s, xx, yy, Inches(5.9), Inches(2.3), h, [body], c)
            i += 1
    footer(s, 19)
    return s


# ================================================================ NEW — YANG & NETCONF intro
def s_yang_netconf_intro():
    s = slide()
    title_bar(s, "YANG and NETCONF: model vs. protocol",
              "YANG defines WHAT the data is; NETCONF is HOW you move it.")
    bullet_card(s, Inches(0.6), Inches(1.7), Inches(5.9), Inches(2.25),
                "YANG \u2014 the data modeling language (RFC 7950)",
                [("Describes ", "structure, types, constraints, defaults."),
                 ("Hierarchy ", "of containers, lists, leaves \u2014 vendor-neutral."),
                 ("One model ", "serves every protocol below it."),
                 ("Example: ", "example-coffee-maker defines power, cups, state, brew.")],
                MANAGER, head_size=15)
    bullet_card(s, Inches(6.8), Inches(1.7), Inches(5.9), Inches(2.25),
                "NETCONF \u2014 the management protocol (RFC 6241)",
                [("Operations ", "get, edit-config, commit over a session."),
                 ("Datastores ", "running / candidate / startup."),
                 ("Encoding ", "XML, carried over SSH."),
                 ("Validates ", "payloads against the YANG model.")],
                NETCONF, head_size=15)
    # bottom: one model drives three protocols
    y = Inches(4.6)
    roundrect(s, Inches(0.6), y, Inches(2.9), Inches(1.5), PANEL, line=MANAGER, radius=0.06)
    text(s, Inches(0.6), y + Inches(0.24), Inches(2.9), Inches(1.2),
         [[("YANG module", 15, MANAGER, True, FONT)],
          [(".yang", 13, MUTED, False, MONO)],
          [("the single source of truth", 12, MUTED, False, FONT)]], align=PP_ALIGN.CENTER)
    arrow(s, Inches(3.65), y + Inches(0.66), Inches(0.9), MUTED, "drives")
    outs = [("NETCONF", "XML / SSH", NETCONF, Inches(4.8)),
            ("RESTCONF", "JSON / HTTP", RESTCONF, Inches(7.55)),
            ("CORECONF", "CBOR / CoAP", CORECONF, Inches(10.3))]
    for name, enc, color, x in outs:
        roundrect(s, x, y, Inches(2.5), Inches(1.5), PANEL, line=color, radius=0.06)
        text(s, x, y + Inches(0.32), Inches(2.5), Inches(1.0),
             [[(name, 15, color, True, FONT)],
              [(enc, 12, MUTED, False, MONO)]], align=PP_ALIGN.CENTER)
    text(s, Inches(4.8), Emu(y + Inches(1.58)), Inches(7.9), Inches(0.4),
         [[("same model \u2192 three wire formats", 13, MUTED, False, FONT)]],
         align=PP_ALIGN.CENTER)
    footer(s)
    return s


# ================================================================ NEW — the three-protocol family
def s_family():
    s = slide()
    title_bar(s, "NETCONF vs. RESTCONF vs. CORECONF",
              "Same YANG models \u2014 different transports and encodings for different environments.")
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
            ("Best for ", "constrained makers"),
            ("Payload ", "smallest (binary + SIDs)"),
        ]),
    ]
    x = Inches(0.6)
    w = Inches(3.95)
    gap = Inches(0.19)
    for name, color, ref, rows in cols:
        roundrect(s, x, Inches(1.75), w, Inches(4.3), PANEL, line=color, line_w=1.5, radius=0.04)
        rect(s, x, Inches(1.75), w, Inches(0.7), PANEL2, line=None)
        text(s, x, Inches(1.8), w, Inches(0.6),
             [[(name, 20, color, True, FONT)]], align=PP_ALIGN.CENTER)
        text(s, x, Inches(2.42), w, Inches(0.3),
             [[(ref, 11, MUTED, False, MONO)]], align=PP_ALIGN.CENTER)
        runs = []
        for lead, rest in rows:
            runs.append([(lead, 13, color, True, FONT), (rest, 13, TEXT, False, FONT)])
        text(s, x + Inches(0.25), Inches(2.95), w - Inches(0.45), Inches(3.0),
             runs, space_after=12)
        x = Emu(x + w + gap)
    roundrect(s, Inches(0.6), Inches(6.25), Inches(12.1), Inches(0.5), PANEL2,
              line=FLEET, radius=0.5)
    text(s, Inches(0.6), Inches(6.3), Inches(12.1), Inches(0.4),
         [[("Shared foundation:  ", 13, FLEET, True, FONT),
           ("the SAME example-coffee-maker YANG module + the SAME datastore model (NMDA, RFC 8342)",
            13, TEXT, False, FONT)]], align=PP_ALIGN.CENTER)
    footer(s)
    return s


# ================================================================ NEW — NETCONF messages for the same example
def s_netconf_messages():
    s = slide()
    title_bar(s, "Same operation, NETCONF wire messages",
              "What the 'turn maker lab ON' + 'read fleet' exchanges look like in NETCONF/XML.")
    # left: edit-config (write) — equivalent of the CORECONF iPATCH on slide 13
    code_box(s, Inches(0.6), Inches(1.7), Inches(6.05), Inches(3.05),
             [
                [("<rpc message-id=\"101\"", NETCONF)],
                [("     xmlns=\"urn:...:netconf:base:1.0\">", MUTED)],
                [("  <edit-config>", NETCONF)],
                [("    <target><running/></target>", TEXT)],
                [("    <config>", TEXT)],
                [("      <coffee-maker-manager", MANAGER)],
                [("          xmlns=\"urn:example:coffee-maker\">", MUTED)],
                [("        <coffee-maker>", MANAGER)],
                [("          <id>", TEXT), ("lab", FLEET), ("</id>", TEXT)],
                [("          <power>", TEXT), ("true", CORECONF), ("</power>", TEXT)],
                [("        </coffee-maker>", MANAGER)],
                [("      </coffee-maker-manager>", MANAGER)],
                [("    </config>", TEXT)],
                [("  </edit-config>", NETCONF)],
                [("</rpc>", NETCONF)],
             ], size=11.5, title="NETCONF  \u2014  write (edit-config)   \u2248 285 B")
    # right: the CORECONF equivalent
    code_box(s, Inches(6.85), Inches(1.7), Inches(5.85), Inches(1.5),
             [
                [("iPATCH /c", CORECONF)],
                [("{ 60010: { 60020: [", TEXT)],
                [("    { 60021: ", TEXT), ("\"lab\"", FLEET), (", 60023: ", TEXT), ("true", CORECONF), (" }", TEXT)],
                [("] } }", TEXT)],
             ], size=12.5, title="CORECONF  \u2014  same write   \u2248 21 B  (CBOR/SID)")
    # right-lower: NETCONF get-reply vs CORECONF content
    code_box(s, Inches(6.85), Inches(3.35), Inches(5.85), Inches(1.4),
             [
                [("<rpc-reply><data>", NETCONF)],
                [("  <coffee-maker-manager ...>", MANAGER)],
                [("    <coffee-maker><id>kitchen</id>", TEXT)],
                [("      <power>true</power> ...", TEXT)],
                [("  ... (repeats per maker)", MUTED)],
             ], size=11.5, title="NETCONF  \u2014  read reply   \u2248 1309 B")
    # bottom: size comparison bars
    y = Inches(5.05)
    text(s, Inches(0.6), y - Inches(0.05), Inches(12), Inches(0.35),
         [[("Byte size of the SAME operations \u2014 NETCONF (XML) vs CORECONF (CBOR/SID)",
            14, TEXT, True, FONT)]])
    bars = [
        ("write \u00b7 NETCONF", 285, NETCONF, Inches(5.45)),
        ("write \u00b7 CORECONF", 21, CORECONF, Inches(5.85)),
        ("read \u00b7 NETCONF", 1309, NETCONF, Inches(6.25)),
        ("read \u00b7 CORECONF", 286, CORECONF, Inches(6.65)),
    ]
    maxb = 1309
    track_x = Inches(2.7)
    track_w = Inches(8.2)
    for label, val, color, yy in bars:
        text(s, Inches(0.6), yy - Inches(0.02), Inches(2.0), Inches(0.3),
             [[(label, 11, color, True, MONO)]])
        rect(s, track_x, yy, track_w, Inches(0.26), CODEBG, line=BORDER)
        wv = int(track_w * (val / maxb))
        if wv > 0:
            rect(s, track_x, yy, Emu(wv), Inches(0.26), color, line=None)
        text(s, Emu(track_x + track_w + Inches(0.1)), yy - Inches(0.03),
             Inches(1.4), Inches(0.3),
             [[(f"{val} B", 11, TEXT, True, MONO)]])
    text(s, Inches(0.6), Inches(7.08), Inches(11.5), Inches(0.3),
         [[("CORECONF is ~13\u00d7 smaller on writes and ~4.6\u00d7 smaller on the "
            "fleet read \u2014 same model, same semantics.", 11, MUTED, False, FONT)]])
    # footer page number only (custom bottom line above)
    text(s, Inches(12.3), Inches(7.08), Inches(0.8), Inches(0.3),
         [[(str(len(prs.slides._sldIdLst)), 10, MUTED, False, FONT)]], align=PP_ALIGN.RIGHT)
    return s


# ---------------------------------------------------------------- build
def main():
    s01_title()
    s02_section_context()
    s03_goals()
    # YANG/NETCONF grounding + the three-protocol family, before CoAP fundamentals
    s_yang_netconf_intro()
    s_family()
    s04_section_coap()
    s05_core_wg()
    s06_coap_overview()
    s07_coap_rest()
    s08_section_arch()
    s09_building_blocks()
    s10_why_coap()
    s11_section_coreconf()
    s12_principles()
    s13_operations()
    # the same example's NETCONF messages, right after the CORECONF operations
    s_netconf_messages()
    s14_comparison()
    s15_section_tooling()
    s16_yang_model()
    s17_tooling()
    s18_workflow()
    s19_takeaways()
    out = "IETF_CORE_CoAP_CORECONF_Overview_Coffee.pptx"
    prs.save(out)
    print(f"wrote {out} with {len(prs.slides._sldIdLst)} slides")


if __name__ == "__main__":
    main()
