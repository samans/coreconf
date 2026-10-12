"""
Build a visually appealing PPTX walkthrough of YANG / NETCONF / CORECONF,
grounded in the YANG modules in this project (switch -> wifi-ap -> device)
and the cascade shown by the web demo.

Produces: presentation/802-eth-dot11-mp.pptx
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

# ---- palette (brand-neutral, works light & dark) ------------------------
NAVY       = RGBColor(0x1F, 0x3A, 0x5F)   # primary
TEAL       = RGBColor(0x2E, 0x8B, 0x8B)   # secondary
ORANGE     = RGBColor(0xE0, 0x7A, 0x3C)   # NETCONF accent
GREEN      = RGBColor(0x4A, 0x9D, 0x5B)   # CORECONF accent
PURPLE     = RGBColor(0x6B, 0x4E, 0x9E)   # RESTCONF accent
LIGHT_BG   = RGBColor(0xF5, 0xF7, 0xFA)
PANEL_BG   = RGBColor(0xE8, 0xEE, 0xF5)
CODE_BG    = RGBColor(0x1E, 0x25, 0x33)
CODE_FG    = RGBColor(0xE6, 0xED, 0xF3)
INK        = RGBColor(0x1A, 0x1A, 0x1A)
MUTED      = RGBColor(0x5A, 0x6A, 0x7A)
BORDER     = RGBColor(0xC6, 0xD0, 0xDC)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)

# ---- deck setup ---------------------------------------------------------
prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
SW = prs.slide_width
SH = prs.slide_height
BLANK = prs.slide_layouts[6]


# ---- helpers ------------------------------------------------------------

def add_slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    bg.line.fill.background()
    bg.fill.solid()
    bg.fill.fore_color.rgb = WHITE
    bg.shadow.inherit = False
    # top accent band
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(0.18))
    band.line.fill.background()
    band.fill.solid()
    band.fill.fore_color.rgb = NAVY
    return s


def set_text(tf, text, *, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT,
             font="Calibri", anchor=MSO_ANCHOR.TOP):
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = anchor
    tf.text = ""
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color


def add_text(slide, x, y, w, h, text, **kw):
    tb = slide.shapes.add_textbox(x, y, w, h)
    set_text(tb.text_frame, text, **kw)
    return tb


def add_title(slide, title, subtitle=None):
    add_text(slide, Inches(0.5), Inches(0.35), Inches(12.3), Inches(0.7),
             title, size=32, bold=True, color=NAVY)
    if subtitle:
        add_text(slide, Inches(0.5), Inches(1.05), Inches(12.3), Inches(0.5),
                 subtitle, size=16, color=MUTED)


def rect(slide, x, y, w, h, *, fill=WHITE, line=BORDER, line_w=0.75,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = line
    s.line.width = Pt(line_w)
    s.shadow.inherit = False
    s.text_frame.text = ""
    return s


def label_box(slide, x, y, w, h, text, *, fill=NAVY, color=WHITE, size=14,
              bold=True, align=PP_ALIGN.CENTER, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = rect(slide, x, y, w, h, fill=fill, line=fill, shape=shape)
    set_text(s.text_frame, text, size=size, bold=bold, color=color,
             align=align, anchor=MSO_ANCHOR.MIDDLE)
    return s


def arrow(slide, x1, y1, x2, y2, *, color=NAVY, weight=2.5,
          head=MSO_SHAPE.RIGHT_TRIANGLE):
    """Simple right-facing block arrow between two points on same y."""
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(weight)
    # add arrowhead using XML tweak
    ln = c.line._get_or_add_ln()
    # strip any existing tails
    for tag in ("a:tailEnd", "a:headEnd"):
        for e in ln.findall(qn(tag)):
            ln.remove(e)
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("h", "med")
    return c


def block_arrow(slide, x, y, w, h, *, text="", fill=NAVY, color=WHITE, size=12):
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.color.rgb = fill
    s.shadow.inherit = False
    if text:
        set_text(s.text_frame, text, size=size, bold=True, color=color,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    return s


def code_block(slide, x, y, w, h, code, *, size=11, fg=CODE_FG, bg=CODE_BG,
               title=None):
    r = rect(slide, x, y, w, h, fill=bg, line=bg)
    tf = r.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.15)
    tf.margin_top = tf.margin_bottom = Inches(0.10)
    tf.text = ""
    first = True
    if title:
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.name = "Consolas"
        run.font.size = Pt(size)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x9D, 0xC9, 0xFF)
        first = False
    for line in code.split("\n"):
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = line if line else " "
        run.font.name = "Consolas"
        run.font.size = Pt(size)
        run.font.color.rgb = fg
    return r


def bullet_list(slide, x, y, w, h, items, *, size=16, color=INK, bullet="•"):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.text = ""
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(6)
        r = p.add_run()
        r.text = f"{bullet}  {item}"
        r.font.name = "Calibri"
        r.font.size = Pt(size)
        r.font.color.rgb = color
    return tb


def footer(slide, text="802-eth-dot11-mp  •  NETCONF ↔ CORECONF demo"):
    add_text(slide, Inches(0.5), Inches(7.1), Inches(12.3), Inches(0.3),
             text, size=10, color=MUTED, align=PP_ALIGN.LEFT)


# =========================================================================
# SLIDE 1  —  Title
# =========================================================================
s = add_slide()
# full-bleed hero band
hero = rect(s, 0, Inches(1.3), SW, Inches(4.6), fill=NAVY, line=NAVY,
            shape=MSO_SHAPE.RECTANGLE)
add_text(s, Inches(0.8), Inches(1.8), Inches(11.8), Inches(1.2),
         "YANG everywhere.",
         size=56, bold=True, color=WHITE)
add_text(s, Inches(0.8), Inches(2.9), Inches(11.8), Inches(1.0),
         "NETCONF for the core. CORECONF for the edge.",
         size=32, color=RGBColor(0xC9, 0xDA, 0xF0))
add_text(s, Inches(0.8), Inches(4.1), Inches(11.8), Inches(1.0),
         "An 802.3 switch → 802.11 access point → client-device walkthrough",
         size=20, color=RGBColor(0x9D, 0xB4, 0xCF))

# three protocol pills along the bottom
y = Inches(6.1)
pw = Inches(3.6)
gap = Inches(0.4)
total = 3 * pw + 2 * gap
x0 = (SW - total) // 2
label_box(s, x0 + 0*(pw+gap), y, pw, Inches(0.7), "NETCONF  •  RFC 6241",
          fill=ORANGE, size=18)
label_box(s, x0 + 1*(pw+gap), y, pw, Inches(0.7), "RESTCONF  •  RFC 8040",
          fill=PURPLE, size=18)
label_box(s, x0 + 2*(pw+gap), y, pw, Inches(0.7), "CORECONF  •  RFC 9254/9595",
          fill=GREEN, size=18)


# =========================================================================
# SLIDE 2  —  YANG + NETCONF relationship
# =========================================================================
s = add_slide()
add_title(s, "YANG models the data.  NETCONF moves the data.",
          "The data model is the contract; the protocol is the courier.")

# left — YANG card
yx = Inches(0.6); yy = Inches(1.8); yw = Inches(5.6); yh = Inches(4.6)
rect(s, yx, yy, yw, yh, fill=PANEL_BG, line=BORDER)
label_box(s, yx + Inches(0.3), yy + Inches(0.3), Inches(2.0), Inches(0.55),
          "YANG", fill=TEAL, size=18)
add_text(s, yx + Inches(2.4), yy + Inches(0.3), Inches(3.0), Inches(0.55),
         "RFC 7950", size=12, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
bullet_list(s, yx + Inches(0.3), yy + Inches(1.0), yw - Inches(0.6), yh - Inches(1.3), [
    "A modeling language for configuration & state",
    "Modules, containers, lists, leaves, types",
    "Constraints: ranges, patterns, must/when",
    "Operational vs config data (config false)",
    "Protocol-independent — one model, many wire formats",
], size=15)

# arrow in the middle
arrow(s, yx + yw + Inches(0.1), SH//2 - Inches(0.1),
      yx + yw + Inches(0.9), SH//2 - Inches(0.1), color=NAVY, weight=4)
add_text(s, yx + yw + Inches(0.0), SH//2 - Inches(0.55), Inches(1.1), Inches(0.4),
         "serialized &\ncarried by", size=11, bold=True, color=NAVY,
         align=PP_ALIGN.CENTER)

# right — NETCONF card
nx = yx + yw + Inches(1.0); nw = Inches(5.6)
rect(s, nx, yy, nw, yh, fill=PANEL_BG, line=BORDER)
label_box(s, nx + Inches(0.3), yy + Inches(0.3), Inches(2.0), Inches(0.55),
          "NETCONF", fill=ORANGE, size=18)
add_text(s, nx + Inches(2.4), yy + Inches(0.3), Inches(3.0), Inches(0.55),
         "RFC 6241", size=12, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
bullet_list(s, nx + Inches(0.3), yy + Inches(1.0), nw - Inches(0.6), yh - Inches(1.3), [
    "A protocol for configuring networks",
    "XML-encoded RPCs over SSH (RFC 6242)",
    "Datastores: running, candidate, startup",
    "Operations: get, edit-config, commit, …",
    "Reads/writes YANG-modeled data on a server",
], size=15)

# bottom caption
add_text(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.5),
         "YANG was created so NETCONF (and later friends) had a formal, "
         "machine-readable model to encode and validate against.",
         size=14, color=MUTED, align=PP_ALIGN.CENTER)
footer(s)


# =========================================================================
# SLIDE 3  —  NETCONF / RESTCONF / CORECONF
# =========================================================================
s = add_slide()
add_title(s, "Three protocols, one YANG model.",
          "Same semantics — different wire format, different transport, different scale.")

# shared YANG bar across the top
yang_bar = rect(s, Inches(0.6), Inches(1.9), Inches(12.1), Inches(0.9),
                fill=TEAL, line=TEAL)
set_text(yang_bar.text_frame,
         "YANG  —  one data model (modules, containers, lists, leaves)",
         size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE)

# three columns under it
cols = [
    ("NETCONF",  ORANGE, "RFC 6241", [
        ("Encoding", "XML"),
        ("Transport", "SSH / TLS"),
        ("Message",  "<rpc> / <edit-config>"),
        ("Target",   "Routers, switches, big iron"),
        ("Payload",  "Verbose, human-readable"),
    ]),
    ("RESTCONF", PURPLE, "RFC 8040", [
        ("Encoding", "JSON or XML"),
        ("Transport", "HTTPS"),
        ("Message",  "GET / POST / PUT / PATCH"),
        ("Target",   "Web / cloud controllers"),
        ("Payload",  "REST-friendly, moderate"),
    ]),
    ("CORECONF", GREEN,  "RFC 9254 / 9595", [
        ("Encoding", "CBOR with numeric SIDs"),
        ("Transport", "CoAP (over UDP)"),
        ("Message",  "GET / FETCH / iPATCH"),
        ("Target",   "Constrained IoT devices"),
        ("Payload",  "Tiny, binary"),
    ]),
]
cx0 = Inches(0.6); cw = Inches(3.95); gap = Inches(0.1); cy = Inches(3.1); ch = Inches(4.0)
for i, (name, col, rfc, rows) in enumerate(cols):
    x = cx0 + i * (cw + gap)
    rect(s, x, cy, cw, ch, fill=LIGHT_BG, line=BORDER)
    # header
    hdr = rect(s, x, cy, cw, Inches(0.7), fill=col, line=col,
               shape=MSO_SHAPE.RECTANGLE)
    set_text(hdr.text_frame, f"{name}", size=20, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, x, cy + Inches(0.75), cw, Inches(0.3), rfc,
             size=11, color=MUTED, align=PP_ALIGN.CENTER)
    # rows
    for j, (k, v) in enumerate(rows):
        ry = cy + Inches(1.15) + j * Inches(0.5)
        add_text(s, x + Inches(0.2), ry, Inches(1.2), Inches(0.4), k,
                 size=11, bold=True, color=MUTED)
        add_text(s, x + Inches(1.3), ry, cw - Inches(1.5), Inches(0.4), v,
                 size=12, color=INK)
footer(s)


# =========================================================================
# SLIDE 4  —  NETCONF protocol stack (client -> server)
# =========================================================================
def protocol_stack(slide, title, subtitle, layers_left, layers_right,
                   left_label, right_label, hop_label, hop_color,
                   example_text, example_color):
    add_title(slide, title, subtitle)

    sx = Inches(0.6); sw = Inches(2.9); sy = Inches(2.0); lh = Inches(0.7)
    # left stack
    add_text(slide, sx, sy - Inches(0.5), sw, Inches(0.4), left_label,
             size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    for i, (name, col) in enumerate(layers_left):
        label_box(slide, sx, sy + i * lh, sw, lh - Inches(0.1), name,
                  fill=col, size=14)

    # right stack
    rx = SW - Inches(0.6) - sw
    add_text(slide, rx, sy - Inches(0.5), sw, Inches(0.4), right_label,
             size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    for i, (name, col) in enumerate(layers_right):
        label_box(slide, rx, sy + i * lh, sw, lh - Inches(0.1), name,
                  fill=col, size=14)

    # hop arrow across top layer
    ay = sy + Inches(0.25)
    block_arrow(slide, sx + sw + Inches(0.15), ay, rx - sx - sw - Inches(0.3),
                Inches(0.5), text=hop_label, fill=hop_color, size=14)
    # return arrow across bottom layer
    by = sy + (len(layers_left) - 1) * lh + Inches(0.25)
    ret = slide.shapes.add_shape(MSO_SHAPE.LEFT_ARROW,
                                 sx + sw + Inches(0.15), by,
                                 rx - sx - sw - Inches(0.3), Inches(0.5))
    ret.fill.solid(); ret.fill.fore_color.rgb = MUTED
    ret.line.color.rgb = MUTED
    set_text(ret.text_frame, "response", size=12, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    # example payload box
    ey = sy + len(layers_left) * lh + Inches(0.35)
    rect(slide, Inches(0.6), ey, Inches(12.1), Inches(1.9),
         fill=CODE_BG, line=CODE_BG)
    code_block(slide, Inches(0.6), ey, Inches(12.1), Inches(1.9),
               example_text, size=12, title=f"example wire payload — {hop_label}")
    footer(slide)


# NETCONF stack
s = add_slide()
layers = [
    ("Content  —  YANG-modeled config/state",      TEAL),
    ("Operations  —  <get>, <edit-config>, <commit>", NAVY),
    ("Messages  —  <rpc> / <rpc-reply>  (XML)",    ORANGE),
    ("Secure Transport  —  SSH (RFC 6242) / TLS",  MUTED),
]
example_netconf = (
    '<rpc message-id="101" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">\n'
    '  <edit-config>\n'
    '    <target><running/></target>\n'
    '    <config>\n'
    '      <wifi-ap xmlns="urn:example:wifi-ap">\n'
    '        <latency>50</latency>\n'
    '      </wifi-ap>\n'
    '    </config>\n'
    '  </edit-config>\n'
    '</rpc>'
)
protocol_stack(
    s,
    "NETCONF protocol stack",
    "Client ⟶ Server:  XML RPCs over an SSH-secured session.",
    layers, layers,
    "Client  (mgmt station)", "Server  (switch / AP)",
    "<edit-config>  —  XML over SSH",
    ORANGE, example_netconf, ORANGE,
)


# =========================================================================
# SLIDE 5  —  CORECONF protocol stack
# =========================================================================
s = add_slide()
layers_c = [
    ("Content  —  YANG-modeled data (same model)", TEAL),
    ("Operations  —  GET / FETCH / iPATCH",        NAVY),
    ("Encoding  —  CBOR map, keyed by SIDs",       GREEN),
    ("Transport  —  CoAP over UDP  (optional OSCORE / DTLS)", MUTED),
]
example_coreconf = (
    'POST  coap://ap/c                   (code = 2.02  iPATCH)\n'
    'Content-Format: 140  (application/yang-data+cbor; id=sid)\n'
    '\n'
    'CBOR payload (annotated):\n'
    '  { 70010: {        # wifi-ap\n'
    '      70017: 50      # latency = 50 ms\n'
    '  } }\n'
    '\n'
    'wire bytes:  ~14  (vs. ~215 for the NETCONF XML above)'
)
protocol_stack(
    s,
    "CORECONF protocol stack",
    "Client ⟶ Server:  CBOR-encoded YANG over CoAP — tiny, binary, numeric.",
    layers_c, layers_c,
    "Client  (AP / controller)", "Server  (constrained device)",
    "iPATCH  —  CBOR/SID over CoAP",
    GREEN, example_coreconf, GREEN,
)


# =========================================================================
# SLIDE 6  —  Example YANG modules in this project
# =========================================================================
s = add_slide()
add_title(s, "The example:  switch → access point → device",
          "Three YANG modules model the chain; NETCONF upstream, CORECONF to the edge.")

# chain diagram — 4 nodes
nodes = [
    ("Mgmt\nstation", NAVY),
    ("Switch\n(802.3)", NAVY),
    ("Wi-Fi AP\n(802.11)", NAVY),
    ("Device\n(client)", NAVY),
]
nw = Inches(2.1); nh = Inches(1.3)
nyy = Inches(2.0)
gap = Inches(0.9)
total = 4 * nw + 3 * gap
x0 = (SW - total) // 2
for i, (txt, col) in enumerate(nodes):
    x = x0 + i * (nw + gap)
    label_box(s, x, nyy, nw, nh, txt, fill=col, size=16)
    if i < 3:
        protocol = "NETCONF" if i < 2 else "CORECONF"
        hop_col = ORANGE if i < 2 else GREEN
        block_arrow(s, x + nw + Inches(0.05), nyy + nh/2 - Inches(0.25),
                    gap - Inches(0.1), Inches(0.5),
                    text=protocol, fill=hop_col, size=13)

# three module cards
my = Inches(3.9); mh = Inches(3.1)
mw = Inches(4.0); mg = Inches(0.15)
mx0 = Inches(0.6)
modules = [
    ("example-switch", NAVY,
     "container switch {\n  leaf name           string;\n  leaf mgmt-address   string;\n  leaf enabled        boolean;\n  leaf ap-uplink-port uint8;\n  leaf uplink-up      bool  (ro);\n  leaf port-count     uint8 (ro);\n}"),
    ("example-wifi-ap", TEAL,
     "container wifi-ap {\n  leaf  name, ssid, band, channel;\n  leaf  tx-power, latency, enabled;\n  leaf  state        (ro, identityref);\n  list  device {   // CORECONF-managed\n    key mac;\n    leaf hostname, ip-address,\n         signal-dbm, connected;\n  }\n}"),
    ("example-device", GREEN,
     "container device {\n  leaf mac         string;\n  leaf hostname    string;\n  leaf ip-address  string;\n  leaf signal-dbm  int8 (dBm);\n  leaf connected   boolean;\n}\n\n// SID file assigns numeric SIDs\n// used on the CORECONF hop"),
]
for i, (name, col, body) in enumerate(modules):
    x = mx0 + i * (mw + mg * 2 + Inches(0.1))
    # width adjust to fit three
    x = Inches(0.6) + i * (Inches(4.15))
    rect(s, x, my, Inches(4.0), mh, fill=LIGHT_BG, line=BORDER)
    hdr = rect(s, x, my, Inches(4.0), Inches(0.55), fill=col, line=col,
               shape=MSO_SHAPE.RECTANGLE)
    set_text(hdr.text_frame, name, size=15, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    code_block(s, x + Inches(0.1), my + Inches(0.65),
               Inches(3.8), mh - Inches(0.75), body, size=10)
footer(s)


# =========================================================================
# SLIDE 7  —  Snippets + instance data (switch, wifi-ap)
# =========================================================================
s = add_slide()
add_title(s, "YANG snippet  →  instance data",
          "Each module above becomes real data on the wire. Here are two of them.")

# Left: switch YANG + instance
yang_sw = (
    "module example-switch {\n"
    "  container switch {\n"
    '    leaf name           { type string; }\n'
    '    leaf mgmt-address   { type string; }\n'
    '    leaf enabled        { type boolean; }\n'
    '    leaf ap-uplink-port { type uint8 { range "1..48"; } }\n'
    "    leaf uplink-up      { type boolean; config false; }\n"
    "    leaf port-count     { type uint8;   config false; }\n"
    "  }\n"
    "}"
)
inst_sw = (
    "// instance (NETCONF XML)\n"
    '<switch xmlns="urn:example:switch">\n'
    "  <name>core-switch-1</name>\n"
    "  <mgmt-address>192.0.2.1</mgmt-address>\n"
    "  <enabled>true</enabled>\n"
    "  <ap-uplink-port>1</ap-uplink-port>\n"
    "</switch>"
)
code_block(s, Inches(0.5), Inches(1.75), Inches(6.1), Inches(2.6),
           yang_sw, title="example-switch.yang", size=11)
code_block(s, Inches(0.5), Inches(4.45), Inches(6.1), Inches(2.5),
           inst_sw, title="instance — NETCONF (XML)", size=11)

# Right: wifi-ap YANG + instance
yang_ap = (
    "container wifi-ap {\n"
    '  leaf  name     { type string; default "ap-1"; }\n'
    "  leaf  enabled  { type boolean; }\n"
    "  leaf  ssid     { type string; }\n"
    '  leaf  channel  { type uint8  { range "1..196"; } }\n'
    '  leaf  tx-power { type uint8  { range "1..30"; } units "dBm"; }\n'
    '  leaf  latency  { type uint32 { range "0..10000"; } units "ms"; }\n'
    "  list  device   { key mac;  /* ... */ }\n"
    "}"
)
inst_ap = (
    "// instance (CORECONF CBOR, SID-keyed, annotated)\n"
    "{ 70010 (wifi-ap): {\n"
    '    70011 (name):     "ap-1",\n'
    "    70012 (enabled):  true,\n"
    '    70013 (ssid):     "corp-wifi",\n'
    "    70015 (channel):  36,\n"
    "    70016 (tx-power): 20,\n"
    "    70017 (latency):  0\n"
    "} }"
)
code_block(s, Inches(6.75), Inches(1.75), Inches(6.1), Inches(2.6),
           yang_ap, title="example-wifi-ap.yang", size=11)
code_block(s, Inches(6.75), Inches(4.45), Inches(6.1), Inches(2.5),
           inst_ap, title="instance — CORECONF (CBOR/SID)", size=11)
footer(s)


# =========================================================================
# SLIDE 8  —  set-latency cascade along the chain
# =========================================================================
s = add_slide()
add_title(s, "A manager action cascades the chain",
          "set-latency = 50 ms  —  three hops, two protocols, same YANG.")

# chain with per-hop payload cards underneath
nodes = ["Mgmt\nstation", "Switch", "Wi-Fi AP", "Device"]
nw = Inches(1.9); nh = Inches(1.0); ny = Inches(1.9)
gap = Inches(0.9)
total = 4 * nw + 3 * gap
x0 = (SW - total) // 2
positions = []
for i, txt in enumerate(nodes):
    x = x0 + i * (nw + gap)
    positions.append(x)
    label_box(s, x, ny, nw, nh, txt, fill=NAVY, size=15)

# hop arrows
hop_specs = [
    ("NETCONF  <edit-config>", ORANGE),
    ("NETCONF  <edit-config>", ORANGE),
    ("CORECONF iPATCH",        GREEN),
]
for i, (lbl, col) in enumerate(hop_specs):
    x = positions[i] + nw + Inches(0.05)
    block_arrow(s, x, ny + nh/2 - Inches(0.22), gap - Inches(0.1), Inches(0.45),
                text=lbl, fill=col, size=11)

# per-hop payload cards
card_y = Inches(3.3); card_h = Inches(3.4); card_w = Inches(4.15)
card_gap = Inches(0.1)
# three cards, one per hop
hops_body = [
    ("hop 1 — station → switch   (NETCONF)",
     ORANGE,
     '<rpc message-id="101">\n'
     "  <edit-config>\n"
     "    <target><running/></target>\n"
     "    <config>\n"
     '      <wifi-ap xmlns="urn:example:wifi-ap">\n'
     "        <latency>50</latency>\n"
     "      </wifi-ap>\n"
     "    </config>\n"
     "  </edit-config>\n"
     "</rpc>\n"
     "\n"
     "~215 B payload"),
    ("hop 2 — switch → AP        (NETCONF)",
     ORANGE,
     "// switch is a NETCONF\n"
     "// client toward the AP\n"
     "// — re-issues the same\n"
     "// edit-config for the AP\n"
     "\n"
     "<edit-config target running>\n"
     '  <wifi-ap xmlns=…>\n'
     "    <latency>50</latency>\n"
     "  </wifi-ap>\n"
     "</edit-config>\n"
     "\n"
     "~215 B payload"),
    ("hop 3 — AP → (device scope) (CORECONF)",
     GREEN,
     "POST coap://ap/c\n"
     "Code: 2.02 iPATCH\n"
     "Content-Format: 140\n"
     "\n"
     "CBOR payload:\n"
     "{ 70010: {        # wifi-ap\n"
     "    70017: 50     # latency\n"
     "} }\n"
     "\n"
     "~14 B payload\n"
     " ≈ 15× smaller than NETCONF"),
]
for i, (title, col, body) in enumerate(hops_body):
    x = Inches(0.6) + i * (card_w + card_gap)
    rect(s, x, card_y, card_w, card_h, fill=LIGHT_BG, line=BORDER)
    hdr = rect(s, x, card_y, card_w, Inches(0.5), fill=col, line=col,
               shape=MSO_SHAPE.RECTANGLE)
    set_text(hdr.text_frame, title, size=12, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    code_block(s, x + Inches(0.1), card_y + Inches(0.6),
               card_w - Inches(0.2), card_h - Inches(0.7),
               body, size=11)
footer(s)


# =========================================================================
# SLIDE 9  —  Why CORECONF for constrained devices
# =========================================================================
s = add_slide()
add_title(s, "Why CORECONF for constrained devices?",
          "Same YANG, right-sized protocol for the device at the edge of the chain.")

# left — bar comparison (payload bytes for set-latency)
bar_x = Inches(0.6); bar_y = Inches(1.9); bar_w = Inches(5.6); bar_h = Inches(4.6)
rect(s, bar_x, bar_y, bar_w, bar_h, fill=LIGHT_BG, line=BORDER)
add_text(s, bar_x + Inches(0.3), bar_y + Inches(0.2), bar_w - Inches(0.6), Inches(0.4),
         "set-latency = 50 ms   (payload bytes)",
         size=14, bold=True, color=NAVY)

# NETCONF bar
nb_x = bar_x + Inches(0.6); nb_y = bar_y + Inches(1.0)
nb_full = bar_w - Inches(1.2)
# NETCONF label
add_text(s, nb_x - Inches(0.5), nb_y, Inches(1.5), Inches(0.5),
         "NETCONF", size=12, bold=True, color=ORANGE)
bar1 = rect(s, nb_x + Inches(1.1), nb_y, nb_full - Inches(1.2), Inches(0.6),
            fill=ORANGE, line=ORANGE, shape=MSO_SHAPE.RECTANGLE)
add_text(s, nb_x + Inches(1.1) + nb_full - Inches(1.9),
         nb_y + Inches(0.1), Inches(0.8), Inches(0.4),
         "~215 B", size=12, bold=True, color=WHITE)

# CORECONF bar (scaled to 14/215)
cb_y = nb_y + Inches(1.1)
cb_width = (nb_full - Inches(1.2)) * 14 // 215
add_text(s, nb_x - Inches(0.5), cb_y, Inches(1.5), Inches(0.5),
         "CORECONF", size=12, bold=True, color=GREEN)
rect(s, nb_x + Inches(1.1), cb_y, cb_width, Inches(0.6),
     fill=GREEN, line=GREEN, shape=MSO_SHAPE.RECTANGLE)
add_text(s, nb_x + Inches(1.1) + cb_width + Inches(0.1), cb_y + Inches(0.1),
         Inches(1.0), Inches(0.4), "~14 B", size=12, bold=True, color=GREEN)

# big headline ratio
add_text(s, bar_x + Inches(0.3), bar_y + Inches(2.9), bar_w - Inches(0.6),
         Inches(1.0), "≈ 15× smaller payload",
         size=28, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
add_text(s, bar_x + Inches(0.3), bar_y + Inches(3.7), bar_w - Inches(0.6),
         Inches(0.6), "Add CoAP/UDP vs SSH/TCP framing and the gap only widens.",
         size=12, color=MUTED, align=PP_ALIGN.CENTER)

# right — bullets
rx = bar_x + bar_w + Inches(0.4)
rw = Inches(6.1)
rect(s, rx, bar_y, rw, bar_h, fill=PANEL_BG, line=BORDER)
add_text(s, rx + Inches(0.3), bar_y + Inches(0.2), rw - Inches(0.6), Inches(0.5),
         "Why it matters at the edge", size=16, bold=True, color=NAVY)
bullet_list(s, rx + Inches(0.3), bar_y + Inches(0.8), rw - Inches(0.6),
            bar_h - Inches(1.0), [
    "Battery life — fewer bytes = fewer radio-on-time milliseconds",
    "Memory — CBOR parser + CoAP stack fits in tens of KB",
    "Bandwidth — LPWAN / mesh / sub-GHz links are byte-counted",
    "Latency — no SSH handshake; CoAP works over UDP (and DTLS/OSCORE)",
    "SIDs — numeric identifiers remove string overhead entirely",
    "Same model — the device still speaks the same YANG as the controller",
], size=15)
footer(s)


# =========================================================================
# SLIDE 10  —  Value of a hybrid NETCONF + CORECONF deployment
# =========================================================================
s = add_slide()
add_title(s, "One standard, right-sized at each hop",
          "IETF YANG + NETCONF/RESTCONF/CORECONF lets you keep one model from datacenter to sensor.")

# top: chain reminder
nodes = [("Mgmt station", NAVY), ("Switch", NAVY), ("Access point", NAVY), ("Device", NAVY)]
nw = Inches(2.4); nh = Inches(0.85)
gap = Inches(0.6)
total = 4 * nw + 3 * gap
x0 = (SW - total) // 2
ny = Inches(1.9)
for i, (txt, col) in enumerate(nodes):
    x = x0 + i * (nw + gap)
    label_box(s, x, ny, nw, nh, txt, fill=col, size=14)
    if i < 3:
        hop_col = ORANGE if i < 2 else GREEN
        lbl = "NETCONF" if i < 2 else "CORECONF"
        block_arrow(s, x + nw + Inches(0.05), ny + nh/2 - Inches(0.2),
                    gap - Inches(0.1), Inches(0.4),
                    text=lbl, fill=hop_col, size=12)

# three value cards
vy = Inches(3.3); vh = Inches(3.5); vw = Inches(4.0); vgap = Inches(0.15)
cards = [
    ("One YANG library", TEAL,
     [
         "Define the data model once (IETF or vendor YANG).",
         "Tooling (pyang, yanglint, confd, …) applies everywhere.",
         "No ‘edge-only’ or ‘cloud-only’ silo models to maintain.",
     ]),
    ("Right protocol per link", ORANGE,
     [
         "NETCONF where SSH + XML are already the ops lingua franca.",
         "RESTCONF where web/cloud controllers meet APIs.",
         "CORECONF where every byte and milliamp counts.",
     ]),
    ("Open, interoperable, auditable", GREEN,
     [
         "All three are IETF standards — no vendor lock-in.",
         "The same validation rules on every hop.",
         "Easier security review — one model, one source of truth.",
     ]),
]
for i, (title, col, items) in enumerate(cards):
    x = Inches(0.6) + i * (vw + vgap)
    rect(s, x, vy, vw, vh, fill=LIGHT_BG, line=BORDER)
    hdr = rect(s, x, vy, vw, Inches(0.6), fill=col, line=col,
               shape=MSO_SHAPE.RECTANGLE)
    set_text(hdr.text_frame, title, size=16, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    bullet_list(s, x + Inches(0.25), vy + Inches(0.8),
                vw - Inches(0.5), vh - Inches(1.0),
                items, size=13)

# bottom tagline
add_text(s, Inches(0.6), Inches(7.0), Inches(12.1), Inches(0.4),
         "Model once in YANG.  Transport right-sized per hop.  "
         "Operate one chain end-to-end.",
         size=14, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
footer(s)


# =========================================================================
# Save
# =========================================================================
out = os.path.join(os.path.dirname(__file__), "802-eth-dot11-mp.pptx")
prs.save(out)
print(f"wrote {out}")
