"""Import decisions from the human review workbook and keep audit history separate from proxy labels."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

from .agent.review import current_review, decision_proposal, record_decision
from .identity.audit import ACTIVE_AUDIT_CSV, ACTIVE_AUDIT_EVIDENCE
from .paths import OUT_EVAL
from .sources.select import CHOICES, SEVENTH

AUDITS = {
    "triage": ("Triage audit", "triage_audit_20.csv", "triage_audit_evidence.json", {"YES", "NO", "UNCERTAIN"}),
    "strict_links": ("Link audit", "link_audit_50.csv", "link_audit_evidence.json", {"CORRECT", "INCORRECT", "UNCERTAIN"}),
    "strict_v2_links": ("Link audit", ACTIVE_AUDIT_CSV, ACTIVE_AUDIT_EVIDENCE, {"CORRECT", "INCORRECT", "UNCERTAIN"}),
}


def _evidence_hash(audit: str, directory: Path) -> str:
    return hashlib.sha256((directory / AUDITS[audit][2]).read_bytes()).hexdigest()


def _key(audit: str, row: dict) -> tuple:
    return ((str(row["rank"]), row["dataset_id"]) if audit == "triage"
            else (row["record_a"], row["record_b"]))


def _latest_decisions(directory: Path) -> dict:
    path = directory / "human_audit_decisions.jsonl"
    if not path.exists():
        return {}
    latest = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            latest[(record["audit"], record["evidence_sha256"], tuple(record["key"]))] = record
    return latest


def reviewed_rows(audit: str, rows: list[dict], directory: Path) -> list[dict]:
    latest = _latest_decisions(directory)
    if not latest:
        return rows
    evidence = _evidence_hash(audit, directory)
    note_key = "evidence" if audit == "triage" else "note"
    result = []
    for row in rows:
        decision = latest.get((audit, evidence, _key(audit, row)))
        if decision and (audit == "triage" or row["band"] == "strict"):
            row = row | {"label": decision["label"], "reviewer": decision["reviewer"], "reviewer_kind": "human",
                         note_key: decision["note"]}
            if audit == "triage":
                row["basis"] = decision["basis"]
        result.append(row)
    return result


def _sheet_rows(sheet, verdict: str, required: set[str]):
    rows = sheet.iter_rows(min_row=7, values_only=True)
    headers = next(rows, ())
    if not (required | {verdict, "Reviewer"}).issubset(headers):
        raise ValueError(f"{sheet.title}: this workbook is missing required review columns")
    for row_number, cells in enumerate(rows, 8):
        row = dict(zip(headers, cells))
        if not row.get(verdict):
            continue
        reviewer = str(row.get("Reviewer") or "").strip()
        if not reviewer or "ai assistant" in reviewer.casefold():
            raise ValueError(f"{sheet.title} row {row_number}: enter the human reviewer's name")
        yield row | {"Reviewer": reviewer}, row_number


def _mapping_decisions(sheet) -> tuple[list, int]:
    known = {choice[0] for choice in [*CHOICES, SEVENTH]}
    decisions = {"APPROVE": "approved", "REJECT": "rejected", "NEEDS EVIDENCE": "needs_evidence"}
    changes, waiting, seen = [], 0, set()
    for row, number in _sheet_rows(sheet, "Decision", {"Source ID", "Mapping digest", "Run ID", "Snapshot SHA-256"}):
        sid, decision, reviewer = row.get("Source ID"), decisions.get(row["Decision"]), row["Reviewer"]
        if sid not in known or sid in seen or decision is None:
            raise ValueError(f"Mappings row {number}: invalid or duplicate source decision")
        seen.add(sid)
        expected = {"config_digest": row.get("Mapping digest"), "run_id": row.get("Run ID"),
                    "snapshot_sha256": row.get("Snapshot SHA-256")}
        doc, _ = decision_proposal(sid, reviewer, "human", decision != "approved", expected)
        waiting += decision == "needs_evidence"
        current = current_review(sid, doc) or {}
        comment = str(row.get("Decision note") or "").strip()
        raw_minutes = row.get("Review minutes")
        minutes = float(raw_minutes) if raw_minutes not in (None, "") else None
        if minutes is not None and (not math.isfinite(minutes) or minutes < 0):
            raise ValueError(f"Mappings row {number}: review minutes must be a non-negative number")
        if (current.get("reviewer_kind"), current.get("reviewer"), current.get("decision"), current.get("comment"),
                current.get("review_minutes")) != ("human", reviewer, decision, comment, minutes):
            changes.append((sid, reviewer, decision, comment, expected, minutes))
    return changes, waiting


def _audit_decisions(audit: str, sheet, latest: dict) -> list[dict]:
    keys = {"Rank", "Dataset ID", "Basis"} if audit == "triage" else {"Record A key", "Record B key"}
    submitted = list(_sheet_rows(sheet, "Verdict", keys))
    if not submitted:
        return []
    _, csv_name, _, labels = AUDITS[audit]
    evidence = _evidence_hash(audit, OUT_EVAL)
    if sheet["A6"].value != f"Evidence SHA-256 {evidence}":
        raise ValueError(f"{sheet.title}: the evidence changed or the workbook is missing its evidence digest")
    with (OUT_EVAL / csv_name).open(encoding="utf-8", newline="") as fh:
        known = {_key(audit, row) for row in csv.DictReader(fh) if audit == "triage" or row["band"] == "strict"}
    seen, changes = set(), []
    for row, number in submitted:
        key = ((str(row.get("Rank")), row.get("Dataset ID")) if audit == "triage"
               else (row.get("Record A key"), row.get("Record B key")))
        if key not in known or key in seen or row["Verdict"] not in labels:
            raise ValueError(f"{sheet.title} row {number}: invalid or duplicate audit decision")
        seen.add(key)
        record = {"audit": audit, "evidence_sha256": evidence, "key": list(key), "label": row["Verdict"],
                  "reviewer": row["Reviewer"], "note": str(row.get("Evidence note") or "").strip()}
        if audit == "triage":
            if row.get("Basis") not in {"data", "metadata", "unavailable"}:
                raise ValueError(f"Triage audit row {number}: choose an evidence basis")
            record["basis"] = row["Basis"]
        previous = latest.get((audit, evidence, key), {})
        if any(previous.get(field) != value for field, value in record.items()):
            changes.append(record)
    return changes


def import_reviews(path: Path, *, dry_run: bool = False) -> dict:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True)
    try:
        required = {"Mappings", *(spec[0] for spec in AUDITS.values())}
        if not required.issubset(workbook.sheetnames):
            raise ValueError("The workbook must include Mappings, Triage audit, and Link audit sheets")
        mappings, waiting = _mapping_decisions(workbook["Mappings"])
        latest = _latest_decisions(OUT_EVAL)
        link_sheet = workbook["Link audit"]
        active_evidence = OUT_EVAL / ACTIVE_AUDIT_EVIDENCE
        active_digest = (f"Evidence SHA-256 {_evidence_hash('strict_v2_links', OUT_EVAL)}"
                         if active_evidence.exists() else None)
        link_kind = ("strict_v2_links" if active_digest and link_sheet["A6"].value == active_digest else "strict_links")
        audits = {"triage": _audit_decisions("triage", workbook["Triage audit"], latest),
                  link_kind: _audit_decisions(link_kind, link_sheet, latest)}
    finally:
        workbook.close()
    if not dry_run:
        for sid, reviewer, decision, comment, expected, minutes in mappings:
            record_decision(sid, reviewer, "human", decision, comment, expected=expected, review_minutes=minutes)
        decisions = [record for group in audits.values() for record in group]
        if decisions:
            now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            with (OUT_EVAL / "human_audit_decisions.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
                fh.writelines(json.dumps(record | {"decided_at": now}) + "\n" for record in decisions)
    return {"mapping_decisions": len(mappings), "mappings_needing_evidence": waiting,
            "triage_decisions": len(audits["triage"]), "strict_link_decisions": len(audits[link_kind]),
            "dry_run": dry_run}
