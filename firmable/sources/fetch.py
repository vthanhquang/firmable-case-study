"""HTTP access: CKAN Action API calls and bounded resource downloads, both cached on disk."""
from __future__ import annotations

import hashlib
import json
import time

import httpx

from ..paths import HTTP_CACHE, RAW

UA = {"User-Agent": "firmable-case-study/0.1 (research; contact via repo)"}
MAX_DOWNLOAD = 400_000_000  # 400 MB hard cap per resource


def ckan(portal: str, action: str, **params) -> dict:
    """Call a CKAN action, caching the JSON response (the catalogue moves; runs must be replayable)."""
    key = hashlib.sha256(f"{portal}|{action}|{json.dumps(params, sort_keys=True)}".encode()).hexdigest()[:24]
    cache = HTTP_CACHE / f"ckan_{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    url = f"{portal.rstrip('/')}/api/3/action/{action}"
    last = None
    for attempt in range(4):
        try:
            r = httpx.get(url, params=params, headers=UA, timeout=60, follow_redirects=True)
            r.raise_for_status()
            body = r.json()
            if not body.get("success"):
                raise RuntimeError(f"CKAN error: {body.get('error')}")
            out = {"retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "url": str(r.url), "result": body["result"]}
            HTTP_CACHE.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(out), encoding="utf-8")
            return out
        except (httpx.HTTPError, RuntimeError, ValueError) as e:
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"CKAN call failed after retries: {url} {params}: {last}")


def datastore_all(portal: str, resource_id: str, name_hint: str, page: int = 32000) -> dict:
    """Page through a CKAN DataStore resource and write ONE envelope {"result": {"records": [...]}} - the same
    shape as a single datastore_search response, so configs written for one page read the whole register."""
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / name_hint
    records, offset, total = [], 0, None
    while total is None or offset < total:
        for attempt in range(4):
            try:
                r = httpx.get(f"{portal.rstrip('/')}/api/3/action/datastore_search", headers=UA, timeout=180,
                              params={"resource_id": resource_id, "limit": page, "offset": offset})
                r.raise_for_status()
                body = r.json()["result"]
                break
            except (httpx.HTTPError, ValueError, KeyError):
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"DataStore paging failed at offset {offset}")
        total = body.get("total", 0)
        records.extend(body["records"])
        if not body["records"]:
            break
        offset += len(body["records"])
    data = json.dumps({"result": {"records": records, "total": total, "resource_id": resource_id}}).encode()
    dest.write_bytes(data)
    meta = {"url": f"{portal}/api/3/action/datastore_search?resource_id={resource_id} (paged by {page})",
            "path": str(dest.relative_to(RAW.parent.parent)), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "records": len(records), "total_reported": total,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    dest.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def download(url: str, name_hint: str, max_bytes: int = MAX_DOWNLOAD, partial_ok: bool = False) -> dict:
    """Stream a resource to data/raw. Returns a manifest entry with sha256 and HTTP metadata.
    If the body exceeds max_bytes: fail, or (partial_ok) keep the prefix and flag truncated=True."""
    RAW.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name_hint)[:80]
    dest = RAW / safe
    meta_path = dest.with_suffix(dest.suffix + ".meta.json")
    if dest.exists() and meta_path.exists() and dest.stat().st_size == json.loads(meta_path.read_text(encoding="utf-8"))["bytes"]:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    h = hashlib.sha256()
    n = 0
    truncated = False
    tmp = dest.with_suffix(dest.suffix + ".part")   # never leave a partial file under the final name
    try:
        with httpx.stream("GET", url, headers=UA, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    if n + len(chunk) > max_bytes:
                        if not partial_ok:
                            raise RuntimeError(f"download exceeds cap {max_bytes} bytes: {url}")
                        chunk = chunk[: max_bytes - n]
                        truncated = True
                    fh.write(chunk)
                    h.update(chunk)
                    n += len(chunk)
                    if truncated:
                        break
        if n == 0:
            raise RuntimeError(f"empty response body (HTTP {r.status_code}): {url}")
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    meta = {"url": url, "final_url": str(r.url), "path": str(dest.relative_to(RAW.parent.parent)),
            "bytes": n, "sha256": h.hexdigest(), "truncated": truncated,
            "content_type": r.headers.get("content-type"), "last_modified_header": r.headers.get("last-modified"),
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
