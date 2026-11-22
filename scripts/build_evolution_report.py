"""Build a standalone, data-derived HTML/Markdown report for the live experiment."""
import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/experiments/autonomous-ontology/run"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def table(headers, rows):
    esc = lambda x: html.escape(str(x))
    return "<table><thead><tr>" + "".join(f"<th>{esc(x)}</th>" for x in headers) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows) + "</tbody></table>"


def main():
    sources = read(RUN / "sources.json")
    summary = read(RUN / "summary.json")
    views = read(RUN / "profile-facets.json")
    entity_index = {e["ref"]: e for e in views["entities"]}
    usage = [json.loads(l) for l in (RUN / "usage.jsonl").read_text(encoding="utf-8").splitlines()]
    parts = ["<header><p>FIRMABLE · RESEARCH EXTENSION</p><h1>Learning from unfamiliar sources</h1><p>Three government datasets. Agent-authored mappings. An evolving, versioned ontology.</p></header>",
             "<p class='note'>Experimental candidates · Human review pending · Original submission unchanged</p>",
             "<h2>How the system works</h2><div class='flow'>" + "".join(
                 f"<div><b>{n:02d} · {title}</b><p>{text}</p></div>" for n, (title, text) in enumerate([
                     ("Source intake", "Research → licence → download → snapshot hash"),
                     ("Inspector agent", "Actual bytes → reader, row grain and nested roles"),
                     ("Freeze evidence", "Discovery / validation / sealed test partitions"),
                     ("Architect agent", "Reuse concepts or propose typed, scoped additions"),
                     ("Mapper agent", "Generate an executable config and unmapped reasons"),
                     ("Validate + critique", "Run shared engine; Critic challenges meaning; five rounds per pass, with logged resumes"),
                     ("Test + registry", "Sealed test → immutable candidate → verified offline replay"),
                     ("Profiles + review", "Generic facets and ABN link proposals; human approval before promotion")], 1)) + "</div>",
             "<p>The four named agents are separate model calls using the same model. Source research was assistant-led; validation, extraction, registry management and projection are deterministic code.</p>",
             "<h2>Observed results</h2>"]
    rows, md = [], ["# Autonomous ontology experiment: measured results", "", "These are agent-validated experimental candidates, not human-verified semantic accuracy.", ""]
    for s, result in zip(sources, summary["sources"]):
        sid = s["source_id"]
        sampling = read(RUN / sid / "sampling.json")
        ex, test = result.get("extraction", {}), result.get("test", {})
        row = [sid, sampling["source_rows"], sampling["sample_rows"], result["status"], result.get("new_concepts", "—"),
               ex.get("observations", "—"), ex.get("refused_records", "—"), ex.get("value_errors", "—"),
               f"{test.get('value_errors', 0)}/{test.get('present_values', 0)}" if test else "not reached"]
        rows.append(row)
        md += [f"## {sid}", f"- Status: {result['status']}", f"- Source rows: {sampling['source_rows']:,}; sampled rows: {sampling['sample_rows']:,}.",
               f"- Partitions: {sampling['partitions']}.", f"- New concepts: {result.get('new_concepts', 'not accepted')}; observations: {ex.get('observations', 0):,}.",
               f"- Refused records: {ex.get('refused_records', 0)}; sealed-test value errors/present mapped values: {row[-1]}.", ""]
    parts.append(table(["Source", "Available rows", "Sample", "Status", "New concepts", "Observations", "Refused rows", "Rejected values (all)", "Test errors / present values"], rows))
    parts.append("<p>Type/constraint errors are not semantic mapping errors. A zero value here does not imply perfect precision or complete coverage. Samples include forced preview rows and are not population estimates.</p>")
    for s, result in zip(sources, summary["sources"]):
        sid, folder = s["source_id"], RUN / s["source_id"]
        esc = html.escape
        parts.append(f"<section><h2>{esc(s['title'])}</h2><p>{esc(s['selection_rationale'])}</p><p><a href='{esc(s['url'], quote=True)}'>Downloaded source</a> · <a href='{esc(s['documentation_url'], quote=True)}'>Publisher documentation</a> · <a href='{esc(s['licence_detail']['url'], quote=True)}'>{esc(s['licence_detail']['title'])}</a></p>")
        parts.append(f"<p>Publisher: {esc(s['publisher'])}. Retrieved {esc(s['retrieved_at'])}. <small>Snapshot {esc(s['snapshot_sha256'])}</small></p>")
        if (folder / "ontology-proposal.json").exists():
            proposal, mapping = read(folder / "ontology-proposal.json"), read(folder / "mapping.json")
            parts.append("<h3>New ontology concepts</h3>" + table(["Concept", "Owner", "Type", "Meaning"],
                [[c["path"], c["owner"], c["type"], c["definition"]] for c in proposal["concepts"]]))
            parts.append("<h3>Reuse and explicit omissions</h3>" + table(["Existing concept", "Justification"], proposal["reuse"].items()))
            parts.append("<details><summary>Columns deliberately left unmapped</summary>" + table(["Column", "Reason"],
                [[u["source_path"], u["reason"]] for u in mapping["unmapped"]]) + "</details>")
            parts.append("<details><summary>Field coverage and rejected values</summary>" + table(["Target", "Role", "Source present", "Emitted", "Errors", "Deliberate drops"],
                [[f["target"], f.get("entity", "subject"), f["source_present"], f["emitted"], json.dumps(f["errors"]), json.dumps(f.get("dropped", {}))]
                 for f in result["extraction"]["fields"]]) + "</details>")
            parts.append("<h3>What a profile can show</h3>")
            examples = [e for e in views["entities"] if e["ref"].startswith(sid + "::") and e["kind"] != "business"][:2]
            for entity in examples:
                parts.append(f"<details open><summary>{esc(entity['kind'])} · {esc(entity['ref'])}</summary>" + table(["Field", "Value", "Qualifiers"],
                    [[k, str(values[0]["value"]), json.dumps(values[0].get("qualifiers") or {}, ensure_ascii=False)] for k, values in entity["facets"].items()]))
                connected = {}
                for edge in views["relationships"]:
                    if edge["source_id"] != sid:
                        continue
                    left, right = sid + "::" + edge["from_ref"], sid + "::" + edge["to_ref"]
                    other = right if left == entity["ref"] else left if right == entity["ref"] else None
                    if other in entity_index:
                        connected[(edge["type"], other)] = entity_index[other]
                for (relation, _), other in connected.items():
                    parts.append(f"<h3>{esc(relation)} · {esc(other['kind'])}</h3>" + table(["Connected entity field", "Value"],
                        [[k, str(v[0]["value"])] for k, v in other["facets"].items()]))
                parts.append("</details>")
        else:
            proposals = sorted(folder.glob("*-architect.json"), key=lambda p: int(p.name.split("-")[0]))
            if proposals:
                proposed = read(proposals[-1])["response"]
                parts.append("<h3>Proposed concepts — not accepted</h3>" + table(["Concept", "Owner", "Meaning"],
                    [[c["path"], c["owner"], c["definition"]] for c in proposed["concepts"]]))
            feedback = result.get("feedback", {})
            reason = feedback.get("critic", {}).get("rationale") or feedback.get("ontology_gate") or feedback.get("mapping_gate") or feedback.get("error")
            parts.append("<p><b>Review required.</b> " + esc(str(reason)) + "</p>")
        parts.append("<details><summary>Agent trace and validation feedback</summary>")
        for path in sorted(folder.glob("*-*.json")):
            obj = read(path)
            if path.name.endswith("-critic.json") or path.name.endswith("-validation.json"):
                parts.append(f"<h3>{esc(path.name)}</h3><pre>{esc(json.dumps(obj.get('response', obj), indent=2, ensure_ascii=False))}</pre>")
        parts.append("</details></section>")
    parts.append("<h2>Integration and limits</h2><p>" + f"{summary['entity_count']:,} accepted source-scoped entity views; {summary['proposed_identifier_links']:,} exact-ABN link proposals to the existing sample; {summary['unlinked_businesses']:,} business-role records left unlinked. " +
                 "These are record/entity views, not a count of distinct verified companies. Names alone never trigger a merge. Proposed links have not been hand-audited. Existing 50 profiles are not overwritten.</p>")
    relation_counts = Counter((e["source_id"], e["type"]) for e in views["relationships"])
    parts.append(table(["Source", "Relationship type", "Evidence records"], [[a, b, count] for (a, b), count in sorted(relation_counts.items())]))
    parts.append("<p>This was a development experiment. Generic controller defects were fixed during execution; unsuccessful proposals, retries and explicit source resumes are retained. Mapping configs were not manually edited. A source left in review has not reached sealed-test acceptance.</p>")
    totals = Counter()
    costrows = []
    for s in sources:
        items = [u for u in usage if u["source_id"] == s["source_id"]]
        ins, outs = sum(u["prompt_tokens"] for u in items), sum(u["completion_tokens"] for u in items)
        calls, failures = sum("error" not in u for u in items), sum("error" in u for u in items)
        totals.update(input_tokens=ins, output_tokens=outs, calls=calls, failed_requests=failures)
        costrows.append([s["source_id"], calls, failures, f"{ins:,}", f"{outs:,}"])
    parts.append("<h2>Recorded model usage</h2>" + table(["Source", "Completed calls", "Failed requests", "Input tokens", "Output tokens"], costrows))
    parts.append("<p>Model: deepseek-v4-flash through the authorised Mirai gateway. Failed-request token usage may be unknown. Replay makes zero model calls. No credential is included.</p>")
    md += ["## Totals", f"- Source-scoped entity views: {summary['entity_count']:,}.", f"- Proposed exact-ABN links: {summary['proposed_identifier_links']:,}; unlinked business-role records: {summary['unlinked_businesses']:,}.",
           f"- Completed model calls: {totals['calls']}; failed requests: {totals['failed_requests']}.",
           f"- Input tokens: {totals['input_tokens']:,}; output tokens: {totals['output_tokens']:,}. Failed-request usage may be unknown.",
           "- Production promotion: none. Human semantic precision: not measured.", ""]
    parts.append("<footer>Evidence: outputs/experiments/autonomous-ontology/run · Method: docs/autonomous-ontology.md</footer>")
    css = """body{max-width:1160px;margin:48px auto;padding:0 24px;color:#192721;background:#fbfcfa;font:16px/1.55 system-ui,sans-serif}h1{font-size:42px;line-height:1.1}h2{margin-top:48px}h3{font-size:18px}a{color:#24694e}header{border-bottom:2px solid #243e32;padding-bottom:24px}.note{background:#e9eee8;padding:14px}.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.flow div{border:1px solid #becdc1;padding:16px;border-radius:6px}.flow p{font-size:14px;margin-bottom:0}table{border-collapse:collapse;width:100%;font-size:13px;display:block;overflow:auto}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #d8dfd9}th{background:#e9eee8}td{max-width:460px;overflow-wrap:anywhere}small{display:block;overflow-wrap:anywhere}section{border-top:1px solid #becdc1;margin-top:40px}details{padding:12px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#eef2ed;padding:18px}footer{margin-top:48px;padding:24px 0;border-top:1px solid #becdc1;font-size:13px}@media(max-width:760px){.flow{grid-template-columns:1fr 1fr}h1{font-size:32px}}@media print{body{margin:0}details{break-inside:avoid}.flow{grid-template-columns:repeat(4,1fr)}}"""
    target = ROOT / "reports/autonomous-ontology.html"
    target.write_text("<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Autonomous ontology experiment</title><style>" + css + "</style><main>" + "".join(parts) + "</main></html>", encoding="utf-8")
    (RUN.parent / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    print(str(target))


if __name__ == "__main__":
    main()
