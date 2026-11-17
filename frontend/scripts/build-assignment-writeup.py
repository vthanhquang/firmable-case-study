"""Generate the assignment answers and the website copy from one declared replay."""
import json
import sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from writeup_content import content

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "frontend/data"


def token_summary(costs):
    parts = ["Part 1 — Discovery and triage", "Part 2 — Schema inference and mapping",
             "Part 3 — Entity identification", "Part 4 — Company profiles"]
    usage = [{"part": part, "input_tokens": 0, "output_tokens": 0} for part in parts]
    for path in (ROOT / "runs/usage_ledger.jsonl", ROOT / "outputs/raw-data/usage_ledger.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            stage = row["stage"]
            if stage == "agentic_triage":
                target = usage[0]
            elif stage.startswith(("propose_r", "critic_r")):
                target = usage[1]
            else:
                raise ValueError(f"Unclassified API usage stage: {stage}")
            target["input_tokens"] += row.get("prompt_tokens", 0)
            target["output_tokens"] += row.get("completion_tokens", 0)
    totals = {key: sum(row[key] for row in usage) for key in ("input_tokens", "output_tokens")}
    if any(totals[key] != costs["total"][key] for key in totals):
        raise ValueError("Part-level token totals differ from the recorded usage report")
    pricing = costs["pricing"]
    rate = pricing["off_peak_per_million"]
    def estimate(row):
        return float((Decimal(row["input_tokens"]) * Decimal(str(rate["input"]))
                      + Decimal(row["output_tokens"]) * Decimal(str(rate["output"]))) / Decimal(1_000_000))
    for row in usage:
        row["estimated_usd"] = estimate(row)
    totals["estimated_usd"] = estimate(totals)
    return {"model": pricing["model"], "usage": usage, "total": totals,
            "rates": [{"period": "Off-peak", "input": rate["input"], "output": rate["output"]}],
            "source_url": pricing["source_url"],
            "note": "Estimates include logged experiments and retries. Parts 3–4 make no model calls. Chat assistance is excluded; actual billing is unknown."}


def cost_markdown(summary):
    return [f"Model: **{summary['model']}**. Off-peak prices in USD per 1M tokens; input assumes cache miss.", "",
            "| Period | Input price | Output price |", "| --- | ---: | ---: |",
            *[f"| {r['period']} | ${r['input']:.2f} | ${r['output']:.2f} |" for r in summary["rates"]], "",
            "| Assignment part | Input tokens | Output tokens | Estimated cost (USD) |", "| --- | ---: | ---: | ---: |",
            *[f"| {r['part']} | {r['input_tokens']:,} | {r['output_tokens']:,} | ${r['estimated_usd']:.2f} |" for r in summary["usage"]],
            f"| **Total** | **{summary['total']['input_tokens']:,}** | **{summary['total']['output_tokens']:,}** | **${summary['total']['estimated_usd']:.2f}** |", "",
            summary["note"], "", f"[Model pricing reference]({summary['source_url']}).", ""]


def build():
    demo = json.loads((DATA / "raw-demo.json").read_text(encoding="utf-8"))
    discovery = json.loads((DATA / "part-one.json").read_text(encoding="utf-8"))
    profiles = json.loads((DATA / "raw-profiles.json").read_text(encoding="utf-8"))
    costs = demo["cost"]["cost_report"]
    total, example = costs["total"], costs["example_onboarding"]
    cost_summary = token_summary(costs)
    original_sources = {"asic_companies", "acnc_charities", "ato_tax_transparency", "dewr_employment_providers", "qbcc_licensees", "vic_liquor"}
    links = [json.loads(line) for line in (ROOT / "outputs/raw-data/identity/proposed_links.jsonl").read_text(encoding="utf-8").splitlines() if line]
    original_links = [row for row in links if row["a"]["source_id"] in original_sources and row["b"]["source_id"] in original_sources]
    replay, review = demo["replay"], demo["review"]
    correct = review["human_verdicts"].get("pass", 0)
    labelled = review["audit_labelled"]
    queue_count = sum(replay["unlinked_by_reason"].values())
    deletion = profiles["deletion"]["asic_companies"]
    parts, part5 = content(demo, discovery, profiles, original_links, example, cost_summary)
    context = "Results from the corrected replay, including subsequent work beyond the original six-hour exercise."
    data = {"title": "Case study report", "context": context, "parts": parts, "part5": part5, "cost": cost_summary,
            "submission_limits": "",
            "source": "init_doc/study_case_description.txt", "generated_from": "outputs/raw-data/evaluation/raw_data_metrics.json"}
    (DATA / "assignment-writeup.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    concise = ["# Part 5 — Write-up", "", context, ""]
    for item in part5:
        concise += ["## " + item["title"], "", *(cost_markdown(cost_summary) if item.get("show_cost_table") else []),
                    *[paragraph + "\n" for paragraph in item["answer"]]]
    concise += ["[Parts 1–4 and supporting evidence](docs/ASSIGNMENT_ANSWERS.md).", ""]
    (ROOT / "WRITEUP.md").write_text("\n".join(concise), encoding="utf-8")
    (DATA / "part-five.md").write_text("\n".join(concise), encoding="utf-8")
    full = ["# Assignment answers — Parts 1–5", "", context, ""]
    for item in parts:
        full += ["## " + item["title"], "", *(["**Asked:** " + item["question"], ""] if item["question"] else []),
                 *[p + "\n" for p in item.get("selection", [])],
                 *["- **" + row["name"] + ":** " + row["detail"] + "\n" for row in item.get("dataset_contributions", [])],
                 *["- **" + row["name"] + ":** " + row["detail"] + "\n" for row in item.get("profile_capabilities", [])],
                 *(["### Examples from the saved profiles", ""] if item.get("profile_examples") else []),
                 *["- **" + row["name"] + ":** " + row["detail"] + "\n" for row in item.get("profile_examples", [])],
                 *[p + "\n" for p in item["answer"]],
                 *["**Extra work:** " + p + "\n" for p in item["extra"]], *["**Limit:** " + p + "\n" for p in item["limits"]]]
    full += ["## Part 5 — Engineering decisions", ""]
    for item in part5:
        full += ["### " + item["title"], "", *(cost_markdown(cost_summary) if item.get("show_cost_table") else []),
                 *[p + "\n" for p in item["answer"]]]
    full_text = "\n".join(full).rstrip() + "\n"
    (ROOT / "docs/ASSIGNMENT_ANSWERS.md").write_text(full_text, encoding="utf-8")
    (DATA / "firmable-writeup.md").write_text(full_text, encoding="utf-8")
    relationship_note = "Identity uses constrained clusters with canonical keys; licence/site/programme relationships are separate. Conflicting valid identifiers block merges, and unsupported parent/subsidiary ownership is withheld."
    for path in (ROOT / "WRITEUP.md", DATA / "part-five.md"):
        with path.open("a", encoding="utf-8") as stream:
            stream.write("\n## Entity relationships\n\n" + relationship_note + "\n")
    print(f"Full report: {len(full_text.split())} words including Markdown tables.")
    (ROOT / "outputs/raw-data/evaluation/discounted_cost_report.json").write_text(json.dumps(costs, indent=2) + "\n")
    print(f"Generated assignment answers; Part 5 is {len(' '.join(concise).split())} words.")


if __name__ == "__main__":
    build()
