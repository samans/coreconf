#!/usr/bin/env python3
"""
Preview deck: two ways to show the example-wifi-ap YANG tree on a slide.

  Slide 1 — classic `pyang`-style text tree (monospace ASCII).
  Slide 2 — a PlantUML-style structured/boxed rendering.

Run:   .venv/bin/python3 make_tree_preview.py
Out:   yang-tree-preview.pptx
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# palette (matches the demo UI / main deck)
BG       = RGBColor(0x0B, 0x0F, 0x14)
PANEL    = RGBColor(0x12, 0x18, 0x23)
PANEL2   = RGBColor(0x19, 0x21, 0x2E)
BORDER   = RGBColor(0x27, 0x30, 0x40)
TEXT     = RGBColor(0xE6, 0xED, 0xF3)
MUTED    = RGBColor(0x8B, 0x98, 0xA9)
STATION  = RGBColor(0x58, 0xA6, 0xFF)
SWITCH   = RGBColor(0xA3, 0x71, 0xF7)
AP       = RGBColor(0x3F, 0xB9, 0x50)
DEVICE   = RGBColor(0xD2, 0x99, 0x22)
NETCONF  = RGBColor(0xF0, 0x88, 0x3E)
CORECONF = RGBColor(0x3F, 0xB9, 0x50)
DANGER   = RGBColor(0xF8, 0x51, 0x49)
CODEBG   = RGBColor(0x06, 0x0A, 0x0F)

FONT = "Segoe UI"
MONO = "Consolas"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def slide():
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    r.fill.solid(); r.fill.fore_color.rgb = BG; r.line.fill.background(); r.shadow.inherit = False
    return s


def rect(s, x, y, w, h, fill, line=BORDER, line_w=1.0, shape=MSO_SHAPE.RECTANGLE, radius=None):
    sp = s.shapes.add_shape(shape, x, y, w, h)
    sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try: sp.adjustments[0] = radius
        except Exception: pass
    return sp


def roundrect(s, x, y, w, h, fill, line=BORDER, line_w=1.0, radius=0.08):
    return rect(s, x, y, w, h, fill, line, line_w, MSO_SHAPE.ROUNDED_RECTANGLE, radius)


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space_after=4, wrap=True):
    tb = s.shapes.add_textbox(x, y, w, h); tf = tb.text_frame
    tf.word_wrap = wrap; tf.vertical_anchor = anchor
    tf.margin_left = Pt(4); tf.margin_right = Pt(4); tf.margin_top = Pt(2); tf.margin_bottom = Pt(2)
    first = True
    for para in runs:
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.alignment = align; p.space_after = Pt(space_after); p.space_before = Pt(0)
        if isinstance(para, tuple): para = [para]
        for item in para:
            txt, size, color, bold, font = (item + (None,) * 5)[:5]
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size or 18); r.font.color.rgb = color or TEXT
            r.font.bold = bool(bold); r.font.name = font or FONT
    return tb


def title_bar(s, label, sub=None):
    rect(s, Inches(0.6), Inches(0.5), Inches(0.14), Inches(0.6), NETCONF, line=None)
    text(s, Inches(0.9), Inches(0.42), Inches(11.8), Inches(0.8), [[(label, 28, TEXT, True, FONT)]])
    if sub:
        text(s, Inches(0.92), Inches(1.08), Inches(11.6), Inches(0.5), [[(sub, 14, MUTED, False, FONT)]])


def code_box(s, x, y, w, h, lines, size=14, title=None):
    if title:
        th = Inches(0.34)
        hdr = roundrect(s, x, y, w, th, PANEL2, line=BORDER, radius=0.1)
        tf = hdr.text_frame; tf.margin_left = Pt(8)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
        r = p.add_run(); r.text = title
        r.font.size = Pt(11); r.font.bold = True; r.font.name = MONO; r.font.color.rgb = MUTED
        y = Emu(y + th + Inches(0.03)); h = Emu(h - th - Inches(0.03))
    box = rect(s, x, y, w, h, CODEBG, line=BORDER)
    tf = box.text_frame; tf.word_wrap = False
    tf.margin_left = Pt(12); tf.margin_right = Pt(8); tf.margin_top = Pt(8); tf.margin_bottom = Pt(8)
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.space_after = Pt(2); p.space_before = Pt(0)
        if isinstance(ln, str): ln = [(ln, TEXT)]
        if isinstance(ln, tuple): ln = [ln]
        for seg in ln:
            txt, color = seg
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.name = MONO; r.font.color.rgb = color
    return box


# ================================================================ OPTION A — text tree
def opt_text_tree():
    s = slide()
    title_bar(s, "Option A — pyang-style text tree",
              "example-wifi-ap  ·  the familiar `pyang -f tree` rendering")
    g = MUTED      # tree glyphs / connectors
    k = STATION    # node names
    t = DEVICE     # types
    f = CORECONF   # flags (rw/ro)
    code_box(s, Inches(0.6), Inches(1.55), Inches(8.2), Inches(5.4),
             [
                [("module: example-wifi-ap", TEXT)],
                [("  +--rw ", g), ("wifi-ap", k)],
                [("     +--rw ", g), ("name        ", k), ("string", t)],
                [("     +--rw ", g), ("enabled     ", k), ("boolean", t)],
                [("     +--rw ", g), ("ssid        ", k), ("string", t)],
                [("     +--rw ", g), ("band        ", k), ("wifi-band", t)],
                [("     +--rw ", g), ("channel     ", k), ("uint8", t), ("  [1..196]", MUTED)],
                [("     +--rw ", g), ("tx-power    ", k), ("uint8", t), ("  [1..30] dBm", MUTED)],
                [("     +--rw ", g), ("latency     ", k), ("uint32", t), (" [0..10000] ms", MUTED)],
                [("     +--ro ", g), ("state       ", k), ("identityref", t)],
                [("     +--rw ", g), ("device* ", k), ("[mac]", f)],
                [("        +--rw ", g), ("mac           ", k), ("string", t)],
                [("        +--rw ", g), ("hostname      ", k), ("string", t)],
                [("        +--rw ", g), ("ip-address    ", k), ("string", t)],
                [("        +--rw ", g), ("signal-dbm    ", k), ("int8", t), ("  dBm", MUTED)],
                [("        +--rw ", g), ("connected     ", k), ("boolean", t)],
             ], size=15, title="pyang -f tree  example-wifi-ap@2026-10-05.yang")
    # legend / notes
    roundrect(s, Inches(9.0), Inches(1.9), Inches(3.7), Inches(4.6), PANEL, line=BORDER, radius=0.04)
    text(s, Inches(9.25), Inches(2.05), Inches(3.3), Inches(4.3),
         [
            [("Reading the tree", 16, TEXT, True, FONT)],
            [("+--rw", 13, CORECONF, True, MONO), ("  read-write (config)", 13, MUTED, False, FONT)],
            [("+--ro", 13, STATION, True, MONO), ("  read-only (state)", 13, MUTED, False, FONT)],
            [("* [key]", 13, DEVICE, True, MONO), (" a keyed list", 13, MUTED, False, FONT)],
            [("", 6, MUTED, False, FONT)],
            [("Pros", 14, AP, True, FONT)],
            [("\u2022 Native YANG convention", 12, TEXT, False, FONT)],
            [("\u2022 Compact, whole model at a glance", 12, TEXT, False, FONT)],
            [("\u2022 Copy-paste from pyang", 12, TEXT, False, FONT)],
            [("", 6, MUTED, False, FONT)],
            [("Cons", 14, NETCONF, True, FONT)],
            [("\u2022 Mono-font ASCII, less \u2018designed\u2019", 12, TEXT, False, FONT)],
            [("\u2022 Dense for non-YANG audiences", 12, TEXT, False, FONT)],
         ], space_after=6)
    text(s, Inches(0.6), Inches(7.05), Inches(10), Inches(0.3),
         [[("Preview A \u00b7 text tree", 10, MUTED, False, FONT)]])
    return s


# ================================================================ OPTION B — plantuml-style
def opt_plantuml():
    s = slide()
    title_bar(s, "Option B — PlantUML-style class diagram",
              "example-wifi-ap  ·  rendered as structured boxes (container + list)")
    # wifi-ap "class" box
    bx = Inches(0.8); by = Inches(1.7); bw = Inches(5.2)
    hdr_h = Inches(0.5)
    roundrect(s, bx, by, bw, Inches(3.75), PANEL, line=AP, line_w=1.75, radius=0.03)
    rect(s, bx, by, bw, hdr_h, AP, line=None)
    text(s, bx, by + Inches(0.04), bw, Inches(0.42),
         [[("\u00ab container \u00bb  wifi-ap", 16, RGBColor(0x08,0x12,0x0B), True, FONT)]],
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
    yy = by + hdr_h + Inches(0.08)
    for vis, name, typ, vcol in rows:
        text(s, bx + Inches(0.2), yy, bw - Inches(0.4), Inches(0.33),
             [[(vis, 13, vcol, True, MONO), (name, 13, TEXT, True, MONO),
               ("  : " + typ, 13, DEVICE, False, MONO)]], space_after=0)
        yy = Emu(yy + Inches(0.38))

    # device "class" box
    dx = Inches(7.3); dy = Inches(2.4); dw = Inches(5.0)
    roundrect(s, dx, dy, dw, Inches(2.9), PANEL, line=DEVICE, line_w=1.75, radius=0.03)
    rect(s, dx, dy, dw, hdr_h, DEVICE, line=None)
    text(s, dx, dy + Inches(0.04), dw, Inches(0.42),
         [[("\u00ab list \u00bb  device", 16, RGBColor(0x1A,0x0D,0x04), True, FONT)]],
         align=PP_ALIGN.CENTER)
    drows = [
        ("\U0001F511 ", "mac", "string  {key}", DANGER),
        ("+ ", "hostname", "string", CORECONF),
        ("+ ", "ip-address", "string", CORECONF),
        ("+ ", "signal-dbm", "int8 dBm", CORECONF),
        ("+ ", "connected", "boolean", CORECONF),
    ]
    yy = dy + hdr_h + Inches(0.1)
    for vis, name, typ, vcol in drows:
        text(s, dx + Inches(0.2), yy, dw - Inches(0.4), Inches(0.33),
             [[(vis, 13, vcol, True, MONO), (name, 13, TEXT, True, MONO),
               ("  : " + typ, 13, DEVICE, False, MONO)]], space_after=0)
        yy = Emu(yy + Inches(0.4))

    # composition connector  wifi-ap *-- device  (diamond + line)
    # line
    ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, bx + bw, by + Inches(1.9),
                            dx - (bx + bw), Pt(2))
    ln.fill.solid(); ln.fill.fore_color.rgb = MUTED; ln.line.fill.background(); ln.shadow.inherit = False
    dia = s.shapes.add_shape(MSO_SHAPE.DIAMOND, bx + bw - Inches(0.12), by + Inches(1.78),
                             Inches(0.24), Inches(0.24))
    dia.fill.solid(); dia.fill.fore_color.rgb = AP; dia.line.color.rgb = AP; dia.shadow.inherit = False
    text(s, bx + bw, by + Inches(1.45), dx - (bx + bw), Inches(0.3),
         [[("1  \u2192  0..*  (key: mac)", 11, MUTED, True, MONO)]], align=PP_ALIGN.CENTER)

    # legend / notes
    roundrect(s, Inches(7.3), Inches(5.55), Inches(5.0), Inches(1.4), PANEL2, line=BORDER, radius=0.06)
    text(s, Inches(7.55), Inches(5.65), Inches(4.6), Inches(1.25),
         [
            [("Pros", 13, AP, True, FONT), ("  slide-native, visually clean, scales to big screens",
              12, MUTED, False, FONT)],
            [("Cons", 13, NETCONF, True, FONT), ("  not standard YANG notation; needs a build step",
              12, MUTED, False, FONT)],
            [("Note", 13, STATION, True, FONT), ("  rendered here as PPT shapes mimicking PlantUML output",
              12, MUTED, False, FONT)],
         ], space_after=5)
    text(s, Inches(0.6), Inches(7.05), Inches(10), Inches(0.3),
         [[("Preview B \u00b7 PlantUML-style", 10, MUTED, False, FONT)]])
    return s


opt_text_tree()
opt_plantuml()

OUT = "yang-tree-preview.pptx"
prs.save(OUT)
print(f"wrote {OUT}  ({len(prs.slides._sldIdLst)} slides)")
