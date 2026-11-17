"""Export the exact catalogue ranking inputs and bounded publisher responses for the site."""
import csv
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from firmable.discovery.quality import _catalogue_signals, _preview, _table_score  # noqa: E402
from firmable.discovery.triage import FEATURES, PORTAL  # noqa: E402
from firmable.mapping.schema import ReaderSpec  # noqa: E402

OUTPUT = ROOT / "data/triage-recheck/discovery-site-captures.json"
PRIVATE_COLUMN = re.compile(r"(?:e.?mail|phone|fax|contact|address|latitude|longitude|date of birth)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def read_lines(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line]


def ranking(package, recorded):
    sources = [("Title", package["title"]), ("Publisher", package.get("organisation") or "")]
    sources += [("Resource", value) for item in package["resources"]
                for value in (item.get("name"), item.get("description")) if value]
    score, reasons = _catalogue_signals(package)
    matched = {reason.partition("(")[0] for reason in reasons}
    if score != recorded:
        raise ValueError(f"Metadata score does not replay for {package['dataset_id']}: {score} vs {recorded}")
    inputs = []
    for label, value in sources:
        fields = {"Title": {"title", "all"}, "Publisher": {"org"}, "Resource": {"all"}}[label]
        hits = [{"start": len(value[:m.start()].encode('utf-16-le')) // 2,
                 "end": len(value[:m.end()].encode('utf-16-le')) // 2,
                 "rule": name, "weight": weight}
                for name, weight, regex, field in FEATURES if name in matched and field in fields
                for m in re.finditer(regex, value, re.IGNORECASE)]
        if hits or label != "Resource":
            inputs.append({"label": label, "text": value, "hits": hits})
    return {"score": score, "rules": reasons, "inputs": inputs}


def catalogue_response(client, dataset_id):
    url = f"{PORTAL}/api/3/action/package_show?{urlencode({'id': dataset_id})}"
    try:
        response = client.get(url)
        response.raise_for_status()
        body = response.json()
        result = body["result"]
        if not body["success"] or result["id"] != dataset_id:
            raise ValueError("Catalogue response did not identify the requested dataset")
        keys = ("id", "name", "title", "notes", "license_id", "metadata_created", "metadata_modified")
        excerpt = {key: result[key] for key in keys if key in result}
        excerpt["notes"] = EMAIL.sub("[contact omitted]", excerpt.get("notes") or "")
        excerpt["organization"] = {key: (result.get("organization") or {}).get(key) for key in ("id", "title")}
        excerpt["resources"] = [{key: EMAIL.sub("[contact omitted]", row[key]) if isinstance(row.get(key), str) else row.get(key)
                                 for key in ("id", "name", "format", "description", "datastore_active")}
                                for row in result.get("resources", [])]
        return {"url": url, "httpStatus": response.status_code, "body": {"success": body["success"], "result": excerpt}}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        return {"url": url, "error": type(error).__name__}


def preview_columns(rows, fields):
    columns = list(dict.fromkeys(key for row in rows for key in row if key and not PRIVATE_COLUMN.search(key)))
    priority = {field: i for i, field in enumerate(fields)}
    columns.sort(key=lambda key: priority.get(key, len(priority)))
    return columns[:20]


def safe_records(rows, fields):
    columns = preview_columns(rows, fields)
    return {"headers": columns, "rows": [[EMAIL.sub("[contact omitted]", str(row.get(key, "")))[:240]
                                         if row.get(key) is not None else "" for key in columns] for row in rows[:50]]}


def redact_json(value):
    if isinstance(value, str):
        return EMAIL.sub("[contact omitted]", value)
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_json(item) for key, item in value.items() if not PRIVATE_COLUMN.search(key)}
    return value


def capture(client, row, package, snapshots):
    response = catalogue_response(client, row["dataset_id"])
    wanted = row["evidence"]["resource_id"]
    resource = next(item for item in package["resources"] if item["id"] == wanted)
    datastore = None
    try:
        prefer = row["evidence"]["route"] == "public_datastore_records"
        tables, route = _preview(client, resource, snapshots, prefer_datastore=prefer)
        if not tables:
            raise ValueError("No publisher rows returned")
        expected = {field["field"] for field in row["evidence"]["fields"]}
        def priority(records):
            score = _table_score(records)
            return (len(expected & {field["field"] for field in score["fields"]}), score["row_score"])
        records = max(tables, key=priority)
        table = safe_records(records, sorted(expected))
        source = {**table, "route": route, "url": resource["url"], "resource": resource.get("name"),
                  "resourceId": wanted, "rowsRead": len(records)}
        if route == "public_datastore_records":
            host = urlsplit(resource["url"]).hostname
            portals = ([f"https://{host}"] if host in {"www.data.qld.gov.au", "data.qld.gov.au", "data.sa.gov.au"} else []) + [PORTAL]
            for portal in portals:
                url = f"{portal}/api/3/action/datastore_search?{urlencode({'resource_id': wanted, 'limit': 50})}"
                try:
                    result = client.get(url)
                    result.raise_for_status()
                    payload = result.json()
                    values = payload["result"]
                    if not payload["success"] or values.get("resource_id") != wanted or not values.get("records"):
                        continue
                    columns = preview_columns(values["records"], sorted(expected))
                    datastore = {"url": url, "httpStatus": result.status_code, "body": {"success": True, "result": {
                        "resource_id": values["resource_id"], "total": values.get("total"),
                        "fields": [redact_json(field) for field in values.get("fields", []) if field.get("id") in columns],
                        "records": [{key: redact_json(record[key]) for key in columns if key in record}
                                    for record in values["records"][:50]],
                    }}}
                    break
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    continue
    except (httpx.HTTPError, ValueError, OSError, KeyError) as error:
        source = {"resourceId": wanted, "url": resource["url"], "error": type(error).__name__}
    return {"catalogue": response, "source": source, "datastore": datastore}


def main():
    base = "outputs/discovery/category_ranked/"
    packages = {row["dataset_id"]: row for row in read_lines("outputs/discovery/catalogue_pool.jsonl")}
    shortlist = read_lines(base + "shortlist.jsonl")
    with (ROOT / (base + "audit/audit_20.csv")).open(encoding="utf-8-sig", newline="") as handle:
        audit = list(csv.DictReader(handle))
    audited = {row["dataset_id"] for row in audit}
    sample = read(base + "audit/sample.json")["sample"]
    if len(audited) != len(sample) or audited != {row["dataset_id"] for row in sample}:
        raise ValueError("Audit verdicts do not match the archived sample")
    snapshots = {}
    for source in read("outputs/sources/selected_sources.json"):
        path = ROOT / source["snapshot"]["path"]
        doc = read(f"outputs/mappings/{source['source_id']}.json")
        if path.is_file():
            snapshots[source["resource_id"]] = (path, ReaderSpec.model_validate(doc["config"]["reader"]))
    ranking_inputs = {row["dataset_id"]: ranking(packages[row["dataset_id"]], row["metadata_score"]) for row in shortlist}
    with httpx.Client(timeout=14, follow_redirects=True, headers={"User-Agent": "firmable-case-study/0.2"}) as client:
        with ThreadPoolExecutor(max_workers=8) as executor:
            pending = {row["dataset_id"]: executor.submit(capture, client, row, packages[row["dataset_id"]], snapshots)
                       for row in shortlist if row["dataset_id"] in audited}
            captures = {key: future.result() for key, future in pending.items()}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256((ROOT / (base + "shortlist.jsonl")).read_bytes()).hexdigest()
    OUTPUT.write_text(json.dumps({"capturedAt": datetime.now(timezone.utc).isoformat(), "ranking": ranking_inputs,
                                  "shortlistSha256": sha, "captures": captures, "audit": audit},
                                 ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(captures)} audited datasets; {sum('body' in v['catalogue'] for v in captures.values())} CKAN responses; "
          f"{sum('rows' in v['source'] for v in captures.values())} publisher row previews")


if __name__ == "__main__":
    main()
