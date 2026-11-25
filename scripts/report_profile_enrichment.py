"""Summarise the unseen-source experiment without promoting any candidate."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/experiments/profile-enrichment"


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def md_table(headers, rows):
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    return ["| " + " | ".join(map(cell, headers)) + " |",
            "| " + " | ".join("---" for _ in headers) + " |"] + [
        "| " + " | ".join(map(cell, row)) + " |" for row in rows]


def main():
    sources = read(ROOT / "config/profile_enrichment_sources.json")
    lines = ["# Company intelligence: unseen-source experiment", "",
        "This experiment tests the existing multi-step ontology/mapping system on ACNC Annual Information Statements, WGEA employer data and IP Australia party activity. All mappings and ontology proposals are recorded model outputs. Human semantic precision has not been measured; production has not been promoted.", "",
        "**Conclusion: the system generalises partially, but is not yet reliable for unattended onboarding.** WGEA passed after a generic reader fix. ACNC stalled because safe abstentions counted against the acceptance threshold. IP exhausted its revision allowance on invalid date mappings. These failures are retained, not relabelled as successes.", "",
        "## Scope and source availability", "",
        "The engine samples up to 600 records per input, with discovery, validation and sealed test partitions. ACNC and WGEA use the complete downloaded CSV/workbook as sampling inputs. IP uses the first 25,000 party-activity records from its ZIP: this prefix contains patents only, not a representative sample of the full IP collection. It does not include joined application status, descriptions, trademarks or classifications.", ""]
    overlap = read(EXP / "source-overlap.json", {})
    lines += md_table(["Input", "Available records", "ABNs also in the existing 50 profiles", "Interpretation"], [
        [name, overlap.get(key, {}).get("available_rows", "—"), len(overlap.get(key, {}).get("matched_existing50_abns", [])), note]
        for name, key, note in [("ACNC AIS 2024", "acnc", "Financials, staffing and activities; charities only"),
                               ("WGEA employer sheet", "wgea", "Workforce/pay measures; not all dashboard indicators"),
                               ("IP party-activity prefix", "ip", "Party roles in patent applications; not current enforceability")]])
    lines += ["", "These overlap counts describe raw source availability, not accepted enrichment, measured link precision or additions already made to the 50 production profiles.", "",
              "## Original engine: first bounded pass", ""]
    results, rows = [], []
    for source in sources:
        sid = source["source_id"]
        folder = EXP / "run" / sid
        result = read(folder / "result.json", {"status": "RUNNING_OR_NOT_STARTED"})
        sampling = read(folder / "sampling.json", {})
        test, extraction = result.get("test", {}), result.get("extraction", {})
        display_status = result["status"]
        if not list(folder.glob("*-inspector.json")) and "budget" in result.get("feedback", {}).get("error", ""):
            display_status = "NOT ATTEMPTED — shared budget exhausted"
        rows.append([sid, display_status, sampling.get("sample_rows", "—"), result.get("rounds", "—"),
                     result.get("new_concepts", "—"), extraction.get("observations", "—"),
                     f"{test.get('value_errors', 0)}/{test.get('present_values', 0)}" if test else "not reached"])
        results.append((source, folder, result))
    lines += md_table(["Source", "Agent/controller status", "Sample", "Rounds", "New concepts", "Observations", "Test rejected/present values"], rows)
    lines += ["", "Zero type/constraint errors do not establish correct meaning, scope or completeness. A controller acceptance is a candidate status, not permission to publish. The independent reader finding below overrides any WGEA baseline acceptance.", "",
              "## Independent finding and repair", "",
              "The original XLSX reader collapsed repeated column headings, silently replacing four current-year WGEA pay-gap columns with prior-year values. In the first employer row, a current-year value of 0.244 (24.4%) was replaced by a blank prior-year cell. The 24-column sheet became 20 parsed columns. A model critic cannot recover information already discarded by the reader.", "",
              "A generic reader correction now assigns collision-safe suffixes to repeated headings in both CSV and XLSX. It preserves positions and values; it does not invent year labels or author mappings. The baseline process had already imported the original reader before this change. Its commit/file hashes and diagnostic example are retained separately. A fresh WGEA process tests the repaired reader against the same workbook.", ""]
    retest = read(EXP / "wgea-retest/wgea_employers_new/result.json", {"status": "RUNNING_OR_NOT_STARTED"})
    lines += [f"WGEA retest status: **{retest['status']}**.", ""]
    if retest.get("test"):
        ex, test = retest["extraction"], retest["test"]
        lines += [f"Retest: {retest['rounds']} rounds; {retest['new_concepts']} new concepts; {ex['observations']:,} observations; sealed-test rejected/present values {test['value_errors']}/{test['present_values']}.", ""]
    demo = read(EXP / "targeted-wgea-profiles.json")
    if demo:
        lines += ["## Concrete profile enrichment", "", f"The exact accepted WGEA mapping was applied, without further model calls, to all {len(demo['profiles'])} ABN-matching employers in the existing 50 profiles. It produced {demo['metrics']['observations']} observations in a separate review artifact. This is a targeted demonstration, not a random precision sample or production merge.", ""]
        example_rows = []
        for profile in demo["profiles"][:3]:
            values = {c["field"]: c["value"] for c in profile["new_observations"]}
            share = values.get("dyn.workforce.total_workforce_women_share")
            example_rows.append([profile["existing_name"], profile["abn"], values.get("dyn.workforce.anzsic_class", "—"),
                values.get("dyn.workforce.employer_size_band", "—"), f"{share:.0%}" if share is not None else "—",
                values.get("dyn.workforce.total_workforce_average_total_remuneration", "—")])
        lines += md_table(["Existing company", "ABN", "Reported industry", "Employee band", "Women in workforce", "Average total remuneration (AUD)"], example_rows)
        lines += ["", "Workforce/pay figures are employer-reported for 2024-25; remuneration is not company revenue. Currency AUD is recorded as inferred. The size band remains a band, not an estimated exact headcount. Complete provenance, qualifiers and separate confidence components are in targeted-wgea-profiles.json.", ""]
    results.append((next(s for s in sources if s["source_id"] == "wgea_employers_new"), EXP / "wgea-retest/wgea_employers_new", retest))
    ip_result = read(EXP / "ip-pilot/ip_party_activity_new/result.json", {"status": "RUNNING_OR_NOT_STARTED"})
    lines += ["## Independent IP pilot", "", "A separate bounded process tests IP without waiting for ACNC's revision loop or inheriting ACNC's candidate ontology. It uses the repaired shared reader; its CSV headers are unique, so the reader correction does not change this input's columns.", "", f"IP pilot status: **{ip_result['status']}**.", ""]
    if ip_result.get("test"):
        ex, test = ip_result["extraction"], ip_result["test"]
        lines += [f"IP pilot: {ip_result['rounds']} rounds; {ip_result['new_concepts']} new concepts; {ex['observations']:,} observations; sealed-test rejected/present values {test['value_errors']}/{test['present_values']}.", ""]
    results.append((next(s for s in sources if s["source_id"] == "ip_party_activity_new"), EXP / "ip-pilot/ip_party_activity_new", ip_result))
    for source, folder, result in results:
        label = source["title"] + (" — repaired reader" if "wgea-retest" in str(folder) else " — independent pilot" if "ip-pilot" in str(folder) else " — baseline")
        lines += ["## " + label, "", f"Publisher: {source['publisher']}. [Dataset]({source['url']}) · [Documentation]({source['documentation_url']}) · [Licence]({source['licence_detail']['url']}).", ""]
        proposal = read(folder / "ontology-proposal.json")
        mapping = read(folder / "mapping.json")
        if proposal and mapping:
            lines += md_table(["New concept", "Owner", "Meaning"], [[c["path"], c["owner"], c["definition"]] for c in proposal["concepts"]])
            lines += ["", "### Explicit omissions", ""]
            lines += md_table(["Source column", "Reason"], [[u["source_path"], u["reason"]] for u in mapping["unmapped"]])
            path = folder / "observations.jsonl"
            claims = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            ontology = read(folder.parent / "registry/versions" / (result["ontology_version"] + ".json"))
            by_record = {}
            for claim in claims:
                if ontology["concepts"][claim["field"]].get("personal_data") == "always":
                    continue
                by_record.setdefault(claim["source_record_id"], []).append(claim)
            if by_record:
                examples = sorted(by_record.values(), key=len, reverse=True)[:2]
                lines += ["", "### Candidate evidence examples", "", "These are source-scoped extracted claims, not merged or human-approved company profiles.", ""]
                for example in examples:
                    lines += md_table(["Field", "Value", "Qualifiers", "Source columns"], [
                        [c["field"], c["value"], json.dumps(c.get("qualifiers", {}), ensure_ascii=False), ", ".join(c["source_fields"])] for c in example]) + [""]
        else:
            feedback = result.get("feedback", {})
            critique = feedback.get("critic", {})
            lines += ["No accepted mapping was produced in this pass.", "",
                str(critique.get("rationale") or feedback.get("ontology_gate") or feedback.get("mapping_gate") or feedback.get("error") or "Awaiting completion."), ""]
            for finding in critique.get("blocking_findings", []):
                lines += ["- " + json.dumps(finding, ensure_ascii=False)]
            lines += [""]
    lines += ["## Recorded model usage", ""]
    usage_rows = []
    for name in ["run", "wgea-retest", "ip-pilot"]:
        path = EXP / name / "usage.jsonl"
        usage = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        for sid in sorted({u["source_id"] for u in usage}):
            items = [u for u in usage if u["source_id"] == sid]
            usage_rows.append([name, sid, sum("error" not in u for u in items), sum("error" in u for u in items),
                               sum(u.get("prompt_tokens", 0) for u in items), sum(u.get("completion_tokens", 0) for u in items)])
    lines += md_table(["Pass", "Source", "Completed calls", "Failed requests", "Input tokens", "Output tokens"], usage_rows)
    lines += ["", "Model: deepseek-v4-flash through the authorised gateway. Failed-request usage may be unknown. No secrets are included. No new human labels, production promotion, commit or push is performed.", ""]
    review = EXP / "REVIEW.md"
    if review.exists():
        lines += review.read_text(encoding="utf-8").splitlines()
    (EXP / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    # Dependency-free, escaped report: source values cannot inject HTML.
    parts, in_table = ['<p><a href="dataset-onboarding.html">Explore the interactive dataset-onboarding replay →</a></p>'], False
    def inline(text):
        escaped = html.escape(text, quote=True)
        escaped = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', escaped)
        return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    for line in lines:
        if line.startswith("| "):
            cells = line.strip("| ").split(" | ")
            if all(c.strip() == "---" for c in cells):
                continue
            if not in_table:
                parts.append("<div class='table'><table>")
            tag = "td" if in_table else "th"
            parts.append("<tr>" + "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in cells) + "</tr>")
            in_table = True
            continue
        if in_table:
            parts.append("</table></div>")
            in_table = False
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            parts.append(f"<h{level}>{html.escape(line[level:].strip())}</h{level}>")
        elif line:
            parts.append("<p>" + inline(line) + "</p>")
    if in_table:
        parts.append("</table></div>")
    css = "body{max-width:1120px;margin:48px auto;padding:0 24px;font:16px/1.6 system-ui;color:#192721;background:#fbfcfa}h1{font-size:36px}h2{margin-top:48px;border-top:1px solid #ccd8cf;padding-top:24px}h3{margin-top:32px}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #d8dfd9;overflow-wrap:anywhere;min-width:100px}th{background:#e9eee8}p{overflow-wrap:anywhere}a{color:#24694e}"
    target = ROOT / "reports/profile-enrichment.html"
    target.write_text("<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Unseen company intelligence sources</title><style>" + css + "</style><main>" + "".join(parts) + "</main></html>", encoding="utf-8")
    print("Wrote", target)


if __name__ == "__main__":
    main()
