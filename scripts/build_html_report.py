"""Build a self-contained, printable HTML report from the same content as the website."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "frontend/data/assignment-writeup.json").read_text(encoding="utf-8"))
escape = html.escape


def paragraphs(values):
    return "\n".join(f"<p>{escape(text)}</p>" for text in values)


def bullets(values):
    if not values:
        return ""
    return "<ul>" + "".join(f"<li><strong>{escape(r['name'])}.</strong> {escape(r['detail'])}</li>" for r in values) + "</ul>"


def table(headers, rows):
    return ('<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{escape(str(c))}</td>' for c in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


sections = []
for part in data["parts"]:
    sections.append(f'<section id="{escape(part["id"])}"><h2>{escape(part["title"])}</h2>'
                    + paragraphs(part.get("selection", []))
                    + bullets(part.get("dataset_contributions", []))
                    + bullets(part.get("profile_capabilities", []))
                    + bullets(part.get("profile_examples", []))
                    + paragraphs(part["answer"] + part.get("extra", []) + part.get("limits", [])) + '</section>')
parts5 = []
for item in data["part5"]:
    text = f'<h3>{escape(item["title"])}</h3>'
    if item.get("show_cost_table"):
        cost = data["cost"]
        text += f'<p>Model: {escape(cost["model"])}. USD per million tokens; input assumes cache miss.</p>'
        text += table(["Period", "Input price", "Output price"], [[r["period"], f'${r["input"]:.2f}', f'${r["output"]:.2f}'] for r in cost["rates"]])
        text += table(["Assignment part", "Input tokens", "Output tokens", "Estimated USD"],
                      [[r["part"], f'{r["input_tokens"]:,}', f'{r["output_tokens"]:,}', f'${r["estimated_usd"]:.2f}']
                       for r in cost["usage"] + [{"part": "Total", **cost["total"]}]])
        text += f'<p>{escape(cost["note"])}</p><p><a href="{escape(cost["source_url"], quote=True)}">Model pricing reference</a></p>'
    parts5.append(text + paragraphs(item["answer"]))
sections.append('<section id="part-5"><h2>Part 5 — Engineering decisions</h2>' + '\n'.join(parts5) + '</section>')
svg = (ROOT / "frontend/public/system-architecture.svg").read_text(encoding="utf-8")
sections.append('<section id="architecture"><h2>System architecture</h2><p>Discovery, agent onboarding, review, extraction, linking and profile assembly.</p>' + svg + '</section>')
navigation = " · ".join(f'<a href="#{escape(p["id"])}">Part {i}</a>' for i, p in enumerate(data["parts"], 1))
navigation += ' · <a href="#part-5">Part 5</a> · <a href="#architecture">Architecture</a>'
navigation += ' · <a href="dataset-onboarding.html">Dataset onboarding experiment</a>'
document = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Firmable case study — Parts 1–5</title><style>
*{box-sizing:border-box}body{margin:0 auto;padding:40px 24px;max-width:960px;font:17px/1.55 Georgia,"Times New Roman",serif;color:#202523;background:#fff}
h1{font-size:32px;line-height:1.2;margin:0 0 12px}h2{font-size:24px;line-height:1.25;margin:0 0 12px}h3{font-size:19px;margin:24px 0 8px}
header{border-bottom:1px solid #888;padding-bottom:20px}section{border-bottom:1px solid #ccc;padding:24px 0}p{margin:10px 0}li{margin:6px 0}
nav{margin-top:20px;line-height:2}a{color:#285e4c;text-underline-offset:3px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:14px 0}
th,td{padding:8px;text-align:left;border-bottom:1px solid #bbb}th{background:#f2f4f2}svg{width:100%;height:auto}footer{font-size:14px;margin-top:20px;color:#555}
@media print{body{padding:0;max-width:none;font-size:10pt}nav{display:none}a{color:inherit}h2,h3{break-after:avoid}tr{break-inside:avoid}#architecture{break-before:page}}
</style></head><body><header><h1>Firmable case study</h1><p>''' + escape(data["context"]) + '</p><nav aria-label="Report sections">' + navigation + '</nav></header><main>' + '\n'.join(sections) + '''</main>
<footer>Offline report generated from frontend/data/assignment-writeup.json. The two-page typeset submission is output/pdf/firmable-writeup.pdf; the required Part 5 is WRITEUP.md.</footer>
</body></html>
'''
target = ROOT / "reports/assignment-report.html"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(document, encoding="utf-8")
print("Built reports/assignment-report.html (self-contained; no server or external assets)")
