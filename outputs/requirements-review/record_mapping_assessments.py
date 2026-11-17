"""Record the findings from the 2026-11-17 assistant review, without approving mappings."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from firmable.rawdata.audit import mapping_dependencies, mapping_evidence_digest

run = root / "outputs/raw-data"
checks = json.loads((run / "evaluation/mapping_review_checks.json").read_text())
refs = {
    "acnc": {"title": "ACNC: information published on the Charity Register", "url": "https://www.acnc.gov.au/charity/about-acnc-charity-register/information-charity-register"},
    "asic": {"title": "ASIC EDGE specification, Appendix C, page 92", "url": "https://download.asic.gov.au/media/5982305/els-document-messages-specification-v500-20210218.pdf#page=97"},
    "abn": {"title": "ABR: ABNs for businesses outside Australia", "url": "https://www.abr.gov.au/business-super-funds-charities/applying-abn/abn-businesses-outside-australia"},
    "ato": {"title": "ATO: interpreting the published tax figures", "url": "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/large-business/corporate-tax-transparency/report-of-entity-tax-information"},
    "abs": {"title": "ABS: ANZSIC 3242 and its manufacturing exclusion", "url": "https://www.abs.gov.au/statistics/classifications/australian-and-new-zealand-standard-industrial-classification-anzsic/2006-revision-2-0/detailed-classification/e/32/324/3242"},
}


def finding(priority, title, evidence, action):
    return dict(priority=priority, title=title, evidence=evidence, action=action)


reviews = {
    "acnc_charities": dict(verdict="needs_changes",
        summary="Keep charity identity and purpose fields; correct address role and country contradictions before sign-off.",
        findings=[
            finding("P1", "Register contact addresses are asserted as operating establishments",
                "108 of 1,064 sampled rows contain a PO box or locked bag, yet the mapping emits an establishment and OPERATES_ESTABLISHMENT. Row 1873 is one example. ACNC describes these as contact details.",
                "Have the agent use a business/contact-address scope. Do not assert operating premises from the register address alone."),
            finding("P1", "Contradictory country values become canonical facts",
                "Row 2785 supplies Country=Aruba alongside State=VIC and Postcode=3821; the mapping emits ARUBA. The earlier holdout also reported Austria against an Australian locality.",
                "Retain the raw country as evidence and flag contradictions. Do not silently correct the country or pass contradictory names into canonical address fields.")],
        notes=["Identity, dates, operating regions and purpose flags reproduce correctly. Invalid websites and postcodes are rejected.",
            "Beneficiary columns have an available acnc_beneficiary concept. Leaving them unmapped is conservative, but the explanation that no target exists is inaccurate.",
            "The charity-size crosswalk remains a separate draft dependency; its thresholds should not be treated as period-specific revenue without a reporting year."],
        references=[refs["acnc"]]),
    "asic_companies": dict(verdict="needs_changes",
        summary="Correct subclass crosswalk meanings and remove address-country inference from registration jurisdiction.",
        findings=[
            finding("P1", "Some subclass labels contradict ASIC documentation",
                "The sample includes 6 LISN and 8 NLTD rows. The table describes LISN as listed non-profit and NLTD as no liability; ASIC instead uses these for companies allowed to omit Limited from their names. LISS is also mislabelled as listed.",
                "Correct and separately review the crosswalk, then regenerate observations and affected profiles. Keep unverified rare codes unmapped rather than decoding them speculatively."),
            finding("P2", "Registration jurisdiction is emitted as address country",
                "All 1,166 sampled records receive address.country=AU from a constant, although this dataset has no address column and includes foreign-company registration types.",
                "Remove the address-country constant or represent registration jurisdiction in the appropriate concept.")],
        notes=["Current and former names are separated correctly; zero ABNs are discarded and valid ACNs are retained.",
            "The earlier critic was wrong to question PSTC and ULSS merely from business names: ASIC explicitly supports those trustee meanings.",
            "All four ASIC crosswalks remain separately pending human review."], references=[refs["asic"]]),
    "asic_credit_licensees": dict(verdict="needs_changes",
        summary="Preserve complete authorisation conditions and retain licence dates on licence claims.",
        findings=[
            finding("P1", "Authorisation splitting detaches conditions from permissions",
                "893 emitted fragments begin with where the service or by providing. For example, licence 230637 on row 25 emits a dependent condition as a standalone activity after its parent heading was dropped.",
                "Preserve each complete permission block, including conditions, or leave the complex field as unparsed source evidence. Do not present dependent clauses as separate permissions."),
            finding("P2", "Licence start dates are silently absent from output",
                "All 512 sampled rows have CRED_LIC_START_DT, but the rule targets legacy observation.valid_from, which the engine validates and then ignores.",
                "Map dates to supported licence-scoped facts or validity paths only on claims actually dated by the source; do not apply licence validity to the company itself.")],
        notes=["ABN and ACN are correctly distinguished by length and checksum. Licence status remains separate from company status.",
            "Repeated coordinates may be locality centroids. Verify precision before presenting ext.entity.address_point as an exact business location; the website currently omits coordinates."], references=[]),
    "ato_tax_transparency": dict(verdict="needs_changes",
        summary="Financial mapping is sound; remove the unsupported address-country default.",
        findings=[finding("P2", "An ABN does not establish an Australian address",
            "The mapping emits address.country=AU for all 1,000 sampled rows even though the file contains only identity and tax data. ABR permits eligible non-residents to hold ABNs.",
            "Remove the constant. Preserve known tax jurisdiction separately rather than filling an address field.")],
        notes=["All 2,473 financial claims retain their source income year and AUD qualifier. Blank tax amounts do not become zero.",
            "The earlier critic claimed identity was missing because it saw only extension rules. The complete config and replay contain legal name and ABN, so that warning is dismissed."], references=[refs["abn"], refs["ato"]]),
    "ato_tax_transparency_2023_24": dict(verdict="ready",
        summary="Ready for human sign-off: identity and financial facts are correctly scoped and no blocking issue was found.", findings=[],
        notes=["Replayed all 1,000 sampled records and 2,510 financial claims with no output differences or financial qualifier gaps.",
            "Legal name and checksum-valid ABN identify the subject. Financial figures use the income year from each row and AUD; missing values remain absent.",
            "There is no inferred address-country constant. Blank spreadsheet columns remain explicitly unmapped.",
            "This is a review recommendation, not human approval or a claim that every row in the full source is correct."], references=[refs["ato"]]),
    "dewr_employment_providers": dict(verdict="needs_changes",
        summary="Site fields are mostly well scoped; move the country default to the establishment role before sign-off.",
        findings=[finding("P2", "Country default is attached to the business rather than the site",
            "Address, locality, state and postcode belong to establishment, but all 1,002 rows also emit address.country=AU on subject because generic constants always use subject.",
            "Attach country to the same establishment address as the other fields, or omit it until role-aware constants are supported.")],
        notes=["SITE_NAME is a trading/display name, not promoted to a legal name. Site codes, programmes and addresses preserve establishment scope.",
            "847 rows repeat the same phone under different source roles. This preserves column evidence; the profile builder already deduplicates contact values. It is not evidence of multiple distinct phone numbers.",
            "The current mapping conservatively omits the proposed industry-code inference. Separately, downstream programme labels still use a draft crosswalk and require review."], references=[]),
    "qbcc_licensees": dict(verdict="needs_changes",
        summary="Keep licence and holder identity; revise the activity-to-industry inference before sign-off.",
        findings=[finding("P1", "A draft trade crosswalk overstates business industry",
            "14 sampled Cabinet Making rows are assigned ANZSIC 3242. ABS separates on-site carpentry from manufacturing prefabricated cabinets under 1492; the licence class alone does not resolve that distinction.",
            "Retain the licence category as published. Review ambiguous crosswalk entries and omit or broaden unsupported industry claims; then obtain separate crosswalk sign-off.")],
        notes=["Individual versus organisation holder evidence is preserved without inferring sole-trader status. Licence number, grade and category stay on the licence role.",
            "Three bad ABNs in this saved sample are rejected by checksum. The source is a 32,000-row prefix, so this review does not establish coverage across every category in the full register."], references=[refs["abs"]]),
    "vic_liquor": dict(verdict="needs_changes",
        summary="Premises and postal addresses are separated, but the VIC default is attached to the wrong role.",
        findings=[finding("P1", "Premises jurisdiction contaminates the licensee postal address",
            "The VIC constant is emitted on subject, while the premises address is on premises. 44 of 1,000 sampled records have postal postcodes outside VIC ranges: row 25 has ALBURY 2640 and row 2453 has SYDNEY NSW 2000.",
            "Move VIC and the associated country default to the premises role or omit them. Never combine the Victorian premises state with the licensee correspondence address.")],
        notes=["Licensee, trading name, licence and premises fields are separated; postal fields carry correspondence_address scope. A PO box is valid for that scope, so the earlier postal-address critic warning is not itself a blocker.",
            "The mapping avoids inferring an industry from broad liquor permissions. Opening hours, capacity and licence category remain source facts."], references=[]),
}

path = run / "evaluation/mapping_review_decisions.jsonl"
existing = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
records = []
for sid, review in reviews.items():
    doc = json.loads((run / "mappings" / (sid + ".json")).read_text())
    check = checks["sources"][sid]
    assert check["config_digest"] == doc["config_digest"] and not check["replay_mismatches"] and not check["missing_raw_rows"]
    digest = mapping_evidence_digest(doc | {"source_id": sid}, run / "observations" / (sid + ".jsonl"), mapping_dependencies(doc["config"], root))
    records.append({"source_id": sid, "run_id": doc["run_id"], "config_digest": doc["config_digest"], "snapshot_sha256": doc["snapshot_sha256"],
        "evidence_sha256": digest, "reviewer": "Codex (AI assistant)", "reviewer_kind": "ai_assistant", "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "checks": {k: check[k] for k in ["records_checked", "saved_observations", "missing_raw_rows", "replay_mismatches"]}, **review})
with path.open("a", encoding="utf-8") as stream:
    for row in records:
        if not any(old["source_id"] == row["source_id"] and old["evidence_sha256"] == row["evidence_sha256"] and old["summary"] == row["summary"] for old in existing):
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
report = ["# Mapping review - 17 November 2026", "", "Reviewer: Codex (AI assistant). Advisory review only; no human approval was recorded.", "",
    "Reviewed all eight complete configurations, saved validation and critic reports, raw sample rows, role/scope semantics and referenced crosswalks. Replayed 7,744 rows / 92,092 observations with zero differences. Replay agreement measures reproducibility, not independent accuracy.", "",
    "**Outcome: 1 ready for human sign-off; 7 need changes.** Source configs and the saved replay remain unchanged. Findings below are recommendations for the agent revision loop, not hand-authored replacement mappings.", ""]
for row in records:
    report.extend(["## " + row["source_id"] + " - " + row["verdict"].replace("_", " "), "", row["summary"], "",
        f"Evidence: {row['checks']['records_checked']:,} rows; {row['checks']['saved_observations']:,} observations. Config `{row['config_digest']}`.", ""])
    for f in row["findings"]:
        report.extend(["### " + f["priority"] + " " + f["title"], "", f["evidence"], "", "Correction: " + f["action"], ""])
    report.extend(["- " + note for note in row["notes"]])
    report.append("")
    for ref in row["references"]:
        report.append("Reference: [" + ref["title"] + "](" + ref["url"] + ")")
    report.append("")
(root / "docs/MAPPING_REVIEW_2026-11-17.md").write_text("\n".join(report), encoding="utf-8")
print("Recorded 8 evidence-bound mapping assessments and the detailed review report.")
