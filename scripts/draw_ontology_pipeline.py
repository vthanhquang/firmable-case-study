"""Render the implemented ontology experiment as an editable paper figure.

Uses ReportLab (PDF) and standard-library SVG; no LLM calls or pipeline changes.
PNG preview: render the exported PDF with Poppler at 220 dpi.
"""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import toColor as HexColor

ROOT = Path(__file__).resolve().parents[1]
W, H = 1820, 1390
SCALE = 0.36  # 9.1-inch vector original; scale to the target paper's column width.
INK, MUTED, LINE = "#17212b", "#536171", "#65717f"
PALETTE = {
    "agent": ("#edf3fc", "#5278a6"),
    "code": ("#f5f6f8", "#73808e"),
    "artifact": ("#eef6f0", "#638872"),
    "human": ("#fff4e5", "#ab7b3f"),
    "hybrid": ("#f1eff9", "#81759b"),
}


class Figure:
    def __init__(self):
        (ROOT / "output/figures").mkdir(parents=True, exist_ok=True)
        (ROOT / "output/pdf").mkdir(parents=True, exist_ok=True)
        for font, filename in (("FigureSans", "arial.ttf"), ("FigureSansBold", "arialbd.ttf")):
            path = Path("C:/Windows/Fonts") / filename
            if path.exists():
                pdfmetrics.registerFont(TTFont(font, str(path)))
        self.fonts = ("FigureSans", "FigureSansBold") if "FigureSans" in pdfmetrics.getRegisteredFontNames() else ("Helvetica", "Helvetica-Bold")
        self.pdf = canvas.Canvas(str(ROOT / "output/pdf/ontology-pipeline.pdf"), pagesize=(W*SCALE, H*SCALE), pageCompression=1)
        self.pdf.setTitle("Evidence-grounded ontology evolution: implemented pipeline")
        self.pdf.setAuthor("Firmable case study")
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
            '<title id="title">Evidence-grounded ontology evolution</title>',
            '<desc id="desc">Three-stage architecture: immutable source preparation, bounded agentic ontology and mapping revision, then sealed evaluation and explicit human review. Production profile integration is not implemented in this experiment.</desc>',
            f'<rect width="{W}" height="{H}" fill="white"/>']

    def rect(self, x, y, w, h, fill="white", stroke=LINE, width=1.6, dashed=False, radius=5):
        self.pdf.setFillColor(HexColor(fill)); self.pdf.setStrokeColor(HexColor(stroke))
        self.pdf.setLineWidth(width*SCALE); self.pdf.setDash([6*SCALE, 5*SCALE] if dashed else [])
        self.pdf.roundRect(x*SCALE, (H-y-h)*SCALE, w*SCALE, h*SCALE, radius*SCALE, stroke=1, fill=1)
        dash = ' stroke-dasharray="6 5"' if dashed else ''
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash}/>')

    def text(self, x, y, value, size=27, bold=False, color=INK, anchor="start"):
        font = self.fonts[int(bold)]
        self.pdf.setFont(font, size*SCALE); self.pdf.setFillColor(HexColor(color))
        draw = {"start": self.pdf.drawString, "middle": self.pdf.drawCentredString, "end": self.pdf.drawRightString}[anchor]
        draw(x*SCALE, (H-y)*SCALE, value)
        self.svg.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}">{escape(value)}</text>')

    def arrow(self, points, color=LINE, dashed=False, width=2):
        self.pdf.setStrokeColor(HexColor(color)); self.pdf.setLineWidth(width*SCALE)
        self.pdf.setDash([7*SCALE, 5*SCALE] if dashed else [])
        path = self.pdf.beginPath(); path.moveTo(points[0][0]*SCALE, (H-points[0][1])*SCALE)
        for x, y in points[1:]:
            path.lineTo(x*SCALE, (H-y)*SCALE)
        self.pdf.drawPath(path)
        coords = " ".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="7 5"' if dashed else ''
        self.svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>')
        import math
        (px, py), (x, y) = points[-2:]
        angle = math.atan2(y-py, x-px)
        head = [(x, y)] + [(x-11*math.cos(angle)+side*4.5*math.sin(angle), y-11*math.sin(angle)-side*4.5*math.cos(angle)) for side in (-1, 1)]
        p = self.pdf.beginPath(); p.moveTo(head[0][0]*SCALE, (H-head[0][1])*SCALE)
        for hx, hy in head[1:]: p.lineTo(hx*SCALE, (H-hy)*SCALE)
        p.close(); self.pdf.setFillColor(HexColor(color)); self.pdf.drawPath(p, fill=1, stroke=0)
        self.svg.append(f'<polygon points="{" ".join(f"{hx},{hy}" for hx,hy in head)}" fill="{color}"/>')

    def box(self, x, y, w, h, title, body, kind="code"):
        fill, stroke = PALETTE[kind]
        self.rect(x, y, w, h, fill, stroke)
        title_lines = title.split("\n")
        for i, line in enumerate(title_lines):
            self.text(x+w/2, y+35+i*31, line, 28, True, anchor="middle")
        body_y = y+35+len(title_lines)*31+13
        for i, line in enumerate(body.split("\n")):
            self.text(x+w/2, body_y+i*28, line, 25, color=MUTED, anchor="middle")

    def finish(self):
        self.pdf.showPage(); self.pdf.save()
        (ROOT / "output/figures/ontology-pipeline.svg").write_text("\n".join(self.svg+["</svg>"]), encoding="utf-8")


def main():
    f = Figure()
    f.text(50, 48, "Evidence-grounded ontology evolution", 38, True)
    f.text(50, 86, "Implemented experimental architecture for onboarding unfamiliar business datasets", 26, color=MUTED)
    f.rect(50, 106, 1720, 49, "#fafbfc", "#dbe0e5", radius=0)
    f.text(70, 138, "SYSTEM CONTEXT", 22, True, MUTED)
    f.text(340, 138, "Catalogue discovery", 24)
    f.arrow([(562,130),(609,130)])
    f.text(632, 138, "Ingestion + ontology evolution", 24, True, "#426995")
    f.arrow([(1010,130),(1050,130)])
    f.text(1073, 138, "Entity resolution", 24)
    f.arrow([(1260,130),(1300,130)])
    f.text(1323, 138, "Company profiles", 24)
    for x, kind, label in [(50,"agent","LLM decision"),(355,"code","Deterministic code"),(745,"artifact","Evidence artifact"),(1120,"human","Human action"),(1450,"hybrid","LLM + code")]:
        fill, stroke = PALETTE[kind]
        f.rect(x,176,20,20,fill,stroke,radius=2)
        f.text(x+32,194,label,23,color=MUTED)

    # A: acquisition and partitioning. Optional joins run before source inspection.
    f.text(50, 236, "(a) Source preparation and reproducible evidence", 29, True)
    top = [
        ("Publisher\nsources", "CSV / XLSX / JSON\nlicence + metadata", "artifact"),
        ("Snapshot\nacquisition", "hash + retrieval time\nimmutable inputs", "code"),
        ("Optional\njoin planning", "LLM-proposed keys\ncardinality + lineage", "hybrid"),
        ("Inspector\nagent", "reader + row grain\nidentity cautions", "agent"),
        ("Shared reader\n+ frozen sample", "discovery / validation\nsealed test partition", "code"),
    ]
    for x, (title, body, kind) in zip([50,390,730,1070,1410], top):
        f.box(x, 290, 300, 166, title, body, kind)
    for x in [350,690,1030,1370]: f.arrow([(x,373),(x+40,373)])
    f.arrow([(540,290),(540,266),(1220,266),(1220,290)])
    f.rect(725,248,310,31,"white","white",width=0,radius=0)
    f.text(880,271,"single-table bypass",22,color=MUTED,anchor="middle")
    f.arrow([(1560,456),(1560,500),(30,500),(30,608),(160,608),(160,625)])
    f.rect(570,480,620,31,"white","white",width=0,radius=0)
    f.text(880,502,"Discovery evidence enters planning; test rows stay withheld",22,color=MUTED,anchor="middle")

    # B: per-group loop. The critic is an agent, never a human verdict.
    f.text(50, 552, "(b) Bounded ontology and mapping revision", 29, True)
    mid = [
        ("Group\nplanner", "column groups\nroles + relations", "agent"),
        ("Concept\nretrieval", "base + accepted\nconcept shortlist", "code"),
        ("Ontology\narchitect", "reuse or extend\ntypes + scope", "agent"),
        ("Semantic\nmapper", "typed field intent\nexplicit omissions", "agent"),
        ("Mapping\ncompiler", "executable rules\nclaim-local dates", "code"),
        ("Execution\n+ validation", "validation rows\nerrors / abstentions", "code"),
        ("Semantic\ncritic", "owner / unit / time\nevidence + verdict", "agent"),
    ]
    for i, (title, body, kind) in enumerate(mid): f.box(50+250*i,625,220,166,title,body,kind)
    for i in range(6): f.arrow([(270+250*i,708),(300+250*i,708)])
    f.arrow([(1660,625),(1660,591),(660,591),(660,625)], color="#a56c34")
    f.arrow([(910,591),(910,625)], color="#a56c34")
    f.rect(765,568,790,31,"white","white",width=0,radius=0)
    f.text(1160,591,"Targeted revision: affected ontology and/or mapping only",23,color="#91602e",anchor="middle")
    f.text(910,831,"CONTROL: per-source budgets  |  at most 3 attempts per group  |  stop unchanged failures  |  reuse accepted groups",24,color=MUTED,anchor="middle")
    f.arrow([(1660,791),(1660,878),(30,878),(30,984),(200,984),(200,1001)])
    f.rect(770,857,590,31,"white","white",width=0,radius=0)
    f.text(1065,880,"Accepted groups retained; unresolved groups reported",23,color=MUTED,anchor="middle")

    # C: acceptance is technical + agent review, followed by explicit human review.
    f.text(50, 934, "(c) Candidate assembly, evaluation and human review", 29, True)
    bottom = [
        ("Reconcile\naccepted groups", "compile one config\nversion the ontology", "code"),
        ("Sealed-test\nexecution", "test gate, then\nsample extraction", "code"),
        ("Candidate\nevidence bundle", "version + mapping\nclaims + provenance\naudit + refusals", "artifact"),
        ("Review queue\n+ utility checks", "business connectivity\ncontract fingerprints", "code"),
        ("Human review\n+ decision memory", "approve / reject\nreopen changed items", "human"),
    ]
    for x, (title, body, kind) in zip([50,390,730,1070,1410],bottom): f.box(x,1001,300,187,title,body,kind)
    for x in [350,690,1030,1370]: f.arrow([(x,1094),(x+40,1094)])
    f.arrow([(1710,1094),(1793,1094),(1793,969),(1220,969),(1220,1001)],color="#a56c34")
    f.rect(1290,948,470,30,"white","white",width=0,radius=0)
    f.text(1525,971,"Reuse only unchanged reviewed contracts",22,color="#91602e",anchor="middle")
    f.text(50,1228,"AUDIT: frozen rows + partitions  /  recorded model decisions  /  hashes + token ledger  /  sealed evidence + offline replay",24,color=MUTED)
    f.arrow([(1560,1188),(1560,1268)],dashed=True,color="#9098a1")
    f.rect(50,1268,1720,91,"#fcfcfc","#9098a1",dashed=True,radius=0)
    f.text(70,1304,"Production integration: not implemented in this experiment",28,True,MUTED)
    f.text(70,1339,"Resolve role-to-business identity and graph semantics before merging candidate facts into the existing company profiles.",25,color=MUTED)
    f.finish()
    print("Created output/figures/ontology-pipeline.svg and output/pdf/ontology-pipeline.pdf")


if __name__ == "__main__":
    main()
