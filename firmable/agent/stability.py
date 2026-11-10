"""How repeatable is the agent? Compare an independent re-run's proposals with the approved configs.

For each source: same reader settings? same record grain? and over (canonical target, source columns)
rule pairs: how many agree, and which differ. Identifier rules (abn/acn) are reported separately because
a disagreement there matters most. This is a measurement, not a gate.
"""
from __future__ import annotations

import json

from ..paths import OUT, OUT_EVAL, OUT_MAPPINGS

KEY_TARGETS = {"entity.abn", "entity.acn", "entity.legal_name", "entity.trading_name"}


def _when(f: dict) -> str:
    w = f.get("when")
    return "" if not w else f"{w['source_path']} {w['op']} {sorted(v.upper() for v in w['values'])}"


def _pairs(cfg: dict) -> set:
    return {(f["target"], tuple(f["source_paths"]), _when(f)) for f in cfg["fields"]} | \
           {(c["target"], ("<constant:" + c["value"] + ">",), "") for c in cfg["constants"]}


def compare(experiment: str, baseline: str | None = None) -> dict:
    """Agreement of `experiment` with the approved configs, or with another experiment (`baseline`)."""
    out = {}
    base_dir = OUT / "experiments" / baseline if baseline else OUT_MAPPINGS
    for p in sorted((OUT / "experiments" / experiment).glob("*.json")):
        sid = p.stem
        if not (base_dir / f"{sid}.json").exists():
            continue
        new = json.loads(p.read_text(encoding="utf-8"))["config"]
        old = json.loads((base_dir / f"{sid}.json").read_text(encoding="utf-8"))["config"]
        a, b = _pairs(old), _pairs(new)
        ka = {x for x in a if x[0] in KEY_TARGETS}
        kb = {x for x in b if x[0] in KEY_TARGETS}
        out[sid] = {
            "same_reader": {k: v for k, v in old["reader"].items() if k != "encoding"}
                           == {k: v for k, v in new["reader"].items() if k != "encoding"},
            "same_grain": old["record_grain"] == new["record_grain"],
            "rule_jaccard": round(len(a & b) / max(len(a | b), 1), 3),
            "key_rules_identical": ka == kb,
            "only_in_approved": sorted(map(list, a - b)),
            "only_in_rerun": sorted(map(list, b - a)),
        }
    summary = {"experiment": experiment, "baseline": baseline or "approved", "sources": len(out),
               "same_reader": sum(v["same_reader"] for v in out.values()),
               "same_grain": sum(v["same_grain"] for v in out.values()),
               "key_rules_identical": sum(v["key_rules_identical"] for v in out.values()),
               "mean_rule_jaccard": round(sum(v["rule_jaccard"] for v in out.values()) / max(len(out), 1), 3),
               "per_source": out}
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    name = f"agent_stability_{experiment}" + (f"_vs_{baseline}" if baseline else "")
    (OUT_EVAL / f"{name}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary
