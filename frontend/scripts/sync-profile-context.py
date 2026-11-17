"""Build source-attributed context for the frozen Part 4 company sample."""
import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from firmable.extract import reliability, verify_snapshot  # noqa: E402
from firmable.ids import is_valid_abn  # noqa: E402
from firmable.mapping.context_benchmark import load_context_config  # noqa: E402
from firmable.mapping.engine import Engine, record_base  # noqa: E402
from firmable.sources.readers import iter_records  # noqa: E402
from firmable.sources.select import load_manifest  # noqa: E402

FINAL = ROOT / "outputs/experiments/quality-final"
CONTEXT = ROOT / "outputs/experiments/profile-context"
PROFILES = FINAL / "profiles/company_profiles_50.jsonl"
OUTPUT = FINAL / "profiles/company_context.json"
EDITORIAL = ROOT / "config/profile_company_sources.json"
ABN_URL = "https://abr.business.gov.au/ABN/View/"


class RegisterTables(HTMLParser):
    """Collect the heading and cells of each row in ABN Lookup's public tables."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.title = ""
        self.cells = None
        self.cell = None
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if tag == "tr":
            self.cells = []
        if tag in {"td", "th"} and self.cells is not None:
            self.cell = []

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"td", "th"} and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.cells is not None:
            self.rows.append(self.cells)
            self.cells = None


def registry_record(client, abn):
    url = ABN_URL + abn
    for _ in range(2):
        try:
            response = client.get(url)
            response.raise_for_status()
            page = RegisterTables()
            page.feed(response.text)
            title = re.search(r"Current details for ABN ([\d ]+)", page.title)
            if not title or title[1].replace(" ", "") != abn:
                raise ValueError("ABN Lookup returned a different record")
            record, names, heading = {}, {}, None
            for cells in page.rows:
                if len(cells) != 2:
                    continue
                label, value = cells
                if label.endswith(":"):
                    record[label.rstrip(":")] = value
                if label in {"Business name", "Trading name"} and value == "From":
                    heading = label
                    names.setdefault(heading, [])
                elif heading and re.fullmatch(r"\d{2} [A-Z][a-z]{2} \d{4}", value):
                    names[heading].append(label)
                else:
                    heading = None
            if not record.get("Entity name"):
                raise ValueError("ABN Lookup record is missing the entity name")
            return {"url": url, "name": record["Entity name"], "status": record.get("ABN status"),
                    "type": record.get("Entity type"), "gst": record.get("Goods & Services Tax (GST)"),
                    "mainLocation": record.get("Main business location"),
                    "businessNames": names.get("Business name", []), "tradingNames": names.get("Trading name", [])}
        except (httpx.HTTPError, ValueError):
            continue
    return None


def source_context(manifest, source_id, reports, rel):
    source = manifest[source_id]
    path = ROOT / source["snapshot"]["path"]
    verify_snapshot(source)
    base = json.loads((FINAL / f"selected-mappings/{source_id}.json").read_text(encoding="utf-8"))
    doc = json.loads((CONTEXT / f"{source_id}.json").read_text(encoding="utf-8"))
    _, cfg = load_context_config(base, doc, source)
    if reports[source_id]["configDigest"] != doc["config_digest"] or reports[source_id]["unsupported"]:
        raise ValueError(f"Expected a matching context validation without unsupported claims for {source_id}")
    engine = Engine(cfg, source, rel.get(source_id, rel.get("default")),
                    ingested_at=source["snapshot"]["downloaded_at"])
    return iter_records(path, cfg.reader), engine


def matched_context_rows(source_id, members, rows, engine):
    """Read the exact snapshot ordinals that established membership in the Part 4 replay."""
    ordinals, found = {}, set()
    with (FINAL / f"observations/{source_id}.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            obs = json.loads(line)
            rid = obs["source_record_id"]
            if rid in members:
                found.add(rid)
                ordinals[obs["source_row_ordinal"]] = rid
    if found != set(members) or len(ordinals) != len(members):
        raise ValueError(f"Could not resolve all {source_id} profile members to unique snapshot rows")
    for ordinal, row in enumerate(rows, 1):
        if ordinal in ordinals:
            rid = ordinals.pop(ordinal)
            base = record_base(row, engine.cfg)
            if rid != base and not rid.startswith(base + "#"):
                raise ValueError(f"{source_id} row {ordinal} no longer matches {rid}")
            yield members[rid], row, rid, ordinal
        if not ordinals:
            break
    if ordinals:
        raise ValueError(f"Missing {source_id} source rows: {sorted(ordinals)}")


def mapped_context(engine, row, rid, ordinal):
    keys = ("observation_id", "source_id", "source_record_id", "field", "value", "raw_value", "source_fields",
            "transform", "confidence", "extractor_version")
    observations = [{key: item[key] for key in keys} | {"source_row_ordinal": ordinal}
                    for item in engine.process(row, rid=rid) if item["field"].startswith("context.")]
    values = {}
    for item in observations:
        values.setdefault(item["field"].removeprefix("context."), []).append(item["value"])
    return values, observations


def first(values, name):
    return next(iter(values.get(name, ())), None)


def text(value):
    return " ".join(str(value or "").split()) or None


def validate_sources(records, profiles):
    scopes = {"entity", "group", "brand", "project"}
    for abn, item in records.items():
        if abn not in profiles or item["scope"] not in scopes:
            raise ValueError(f"Unknown ABN or source scope for {abn}")
        for url in [item["url"], item.get("website"), item.get("identityUrl"),
                    *(loc["url"] for loc in item.get("locations", []))]:
            if url is not None and (urlsplit(url).scheme != "https" or not urlsplit(url).hostname):
                raise ValueError(f"Expected a public HTTPS source for {abn}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-registry", action="store_true", help="reopen public ABN Lookup pages")
    args = parser.parse_args()
    snapshot = PROFILES.read_bytes()
    profiles = {}
    members = {sid: {} for sid in ("asic_companies", "ato_tax_transparency", "acnc_charities", "vic_liquor")}
    for line in snapshot.decode("utf-8").splitlines():
        row = json.loads(line)
        abn = row["fields"]["entity.abn"]["value"]
        if not is_valid_abn(abn) or abn in profiles:
            raise ValueError(f"Invalid or duplicate company ABN {abn}")
        profiles[abn] = row
        for key in row["member_records"]:
            sid, rid = key.split("::", 1)
            if sid in members:
                if rid in members[sid]:
                    raise ValueError(f"Profile member assigned twice: {key}")
                members[sid][rid] = abn

    editorial = json.loads(EDITORIAL.read_text(encoding="utf-8")) if EDITORIAL.is_file() else {}
    validate_sources(editorial, profiles)
    old = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.is_file() else {}
    registry = {item["abn"]: item["registry"] for item in old.get("companies", {}).values()}
    checked = old.get("registryCheckedAt")
    if args.refresh_registry or not registry:
        with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": "firmable-case-study/1.0"}) as client:
            with ThreadPoolExecutor(max_workers=4) as pool:
                registry = dict(zip(profiles, pool.map(lambda abn: registry_record(client, abn), profiles)))
        checked = datetime.now(timezone.utc).isoformat(timespec="seconds")

    contexts = {abn: {"abn": abn, "registry": registry.get(abn), "business": editorial.get(abn),
                      "tax": [], "charity": None, "licences": [], "companyRegistration": []} for abn in profiles}
    manifest = load_manifest()
    reports = json.loads((CONTEXT / "validation.json").read_text(encoding="utf-8"))["sources"]
    rel = reliability()
    rows, engine = source_context(manifest, "asic_companies", reports, rel)
    for abn, row, rid, ordinal in matched_context_rows("asic_companies", members["asic_companies"], rows, engine):
        _, evidence = mapped_context(engine, row, rid, ordinal)
        if evidence:
            contexts[abn]["companyRegistration"].append({
                "name": text(row["Company Name"]), "currentName": row["Current Name Indicator"] == "Y",
                "mappingEvidence": evidence,
            })
    rows, engine = source_context(manifest, "ato_tax_transparency", reports, rel)
    for abn, row, rid, ordinal in matched_context_rows("ato_tax_transparency", members["ato_tax_transparency"], rows, engine):
        values, evidence = mapped_context(engine, row, rid, ordinal)
        year = first(values, "tax.income_year")
        if not year:
            raise ValueError(f"Mapped tax context for {abn} lacks a reporting year")
        contexts[abn]["tax"].append({"year": year, "name": text(row["Name"]),
                                     "totalIncome": first(values, "tax.total_income_aud"),
                                     "taxableIncome": first(values, "tax.taxable_income_aud"),
                                     "taxPayable": first(values, "tax.tax_payable_aud"), "mappingEvidence": evidence})
    rows, engine = source_context(manifest, "acnc_charities", reports, rel)
    for abn, row, rid, ordinal in matched_context_rows("acnc_charities", members["acnc_charities"], rows, engine):
        if contexts[abn]["charity"] is not None:
            raise ValueError(f"Multiple ACNC members for ABN {abn}")
        values, evidence = mapped_context(engine, row, rid, ordinal)
        contexts[abn]["charity"] = {
            "name": text(row["Charity_Legal_Name"]), "size": first(values, "charity.size"),
            "established": first(values, "charity.established_on"),
            "purposes": values.get("charity.purpose", []), "regions": values.get("charity.operating_region", []),
            "mappingEvidence": evidence,
        }
    rows, engine = source_context(manifest, "vic_liquor", reports, rel)
    for abn, row, rid, ordinal in matched_context_rows("vic_liquor", members["vic_liquor"], rows, engine):
        values, evidence = mapped_context(engine, row, rid, ordinal)
        licence = first(values, "licence.number")
        if not licence:
            raise ValueError(f"Mapped licence context lacks a licence number for {rid}")
        contexts[abn]["licences"].append({
            "id": licence, "licensee": text(row["Licensee"]), "venue": text(row["Trading As"]),
            "category": first(values, "licence.category"), "hours": first(values, "licence.trading_hours"),
            "capacity": first(values, "licence.patron_capacity"),
            "council": first(values, "licence.council"), "region": first(values, "licence.region"),
            "mappingEvidence": evidence,
        })
    for abn, item in contexts.items():
        item["tax"].sort(key=lambda row: (row["year"] or "", row["name"] or ""), reverse=True)
        item["licences"].sort(key=lambda row: row["id"])
        for source, data in (("ato_tax_transparency", item["tax"]), ("acnc_charities", item["charity"]),
                             ("vic_liquor", item["licences"])):
            if source in profiles[abn]["sources"] and not data:
                raise ValueError(f"Unable to join {source} evidence for ABN {abn}")
    result = {"profileSha256": hashlib.sha256(snapshot).hexdigest(), "registryCheckedAt": checked,
              "companies": {row["entity_key"]: contexts[abn] for abn, row in profiles.items()}}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(contexts)} profiles, {sum(bool(x['registry']) for x in contexts.values())} ABR records, "
          f"{len(editorial)} company source entries, {sum(bool(x['tax']) for x in contexts.values())} ATO disclosures")


if __name__ == "__main__":
    main()
