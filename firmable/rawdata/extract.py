"""Extension extraction: agent-written ext-v1 configs over the raw row store (review 5.1-5.3).

Sample = the audited baseline sample (same rows, same record ids, same strata) PLUS a disclosed
`cohort_ext` stratum: rows of another source that the NEW evidence points to (a website / email domain,
a former name, a phone number seen in another source's sample). Without it, two random samples would
share almost no businesses and the new matching evidence could not be measured. Every observation keeps
its stratum, so results can be reported on the baseline rows alone.

A source whose extension proposal is not PENDING_REVIEW (or approved) falls back to its approved base
config, and every observation says which config and which approval state produced it.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import islice

from ..extract import SEED, load_config, reliability
from ..identity.resolve import is_registered_company_name, norm_name
from ..mapping.engine import Engine, record_base
from ..mapping.schema import MappingConfig
from ..mapping.transforms import TransformError, op_url_domain
from ..paths import ROOT
from ..sources.readers import iter_records
from ..sources.select import load_manifest
from . import OUT_RD_MAPPINGS, OUT_RD_OBS

CAP_EXT = 200                 # extension-cohort rows added per source
PROBE_CHUNK = 50_000
PARALLEL_MIN_ROWS = 500_000
# Free-mail / ISP / shared-government domains identify nobody (review 4.1: "ignoring free-mail domains").
SHARED_DOMAINS = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.au", "bigpond.com",
                  "bigpond.net.au", "live.com", "live.com.au", "icloud.com", "me.com", "optusnet.com.au",
                  "iinet.net.au", "tpg.com.au", "internode.on.net", "westnet.com.au", "aol.com", "msn.com",
                  "hotmail.com.au", "outlook.com.au", "ozemail.com.au", "dodo.com.au", "y7mail.com",
                  "gov.au", "nsw.gov.au", "vic.gov.au", "qld.gov.au", "wa.gov.au", "sa.gov.au", "tas.gov.au",
                  "nt.gov.au", "act.gov.au", "edu.au", "com.au", "org.au", "net.au"}
KEY_TARGETS = {"entity.legal_name", "entity.trading_name", "entity.website", "ext.entity.former_name",
               "ext.contact.email_domain", "ext.contact.website_domain"}


def load_ext_config(sid: str) -> tuple[MappingConfig, dict]:
    """(config, provenance). Prefer the extension proposal when it passed its gates; else the approved base."""
    from .review import approval_state
    path = OUT_RD_MAPPINGS / f"{sid}.json"
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
        from .maintenance import verify_dependencies
        verify_dependencies(doc)
        state = approval_state(sid)
        if doc["status"] == "PENDING_REVIEW" and state != "rejected":
            return MappingConfig.model_validate(doc["config"]), {
                "mapping": "extension", "run_id": doc["run_id"], "config_digest": doc["config_digest"],
                "approval_state": state, "mapping_status": doc["status"]}
    cfg, doc = load_config(sid)
    return cfg, {"mapping": "approved_base", "run_id": doc["run_id"], "config_digest": cfg.digest(),
                 "approval_state": "approved_base", "mapping_status": doc["status"],
                 "note": "extension proposal missing, failed its gates, or rejected"}


def domain_of(field: str, value: str) -> str | None:
    if field == "entity.website":
        try:
            value = op_url_domain(value)
        except TransformError:
            return None
    if not value:
        return None
    return None if value in SHARED_DOMAINS or value.endswith(".gov.au") and value.count(".") <= 2 else value


def name_stem(n: str) -> str:
    """A normalised name without its legal suffix: 'JOB CENTRE AUSTRALIA LTD' -> 'JOB CENTRE AUSTRALIA'."""
    from ..identity.resolve import _COMPANY
    return " ".join(_COMPANY.sub(" ", n).split())


def obs_keys(obs: list[dict]) -> set:
    """Extension evidence keys of one record: ('domain', d); ('name', n) current registered names;
    ('stem', s) other current names; ('former', n) and ('former_stem', s) former registered names."""
    out = set()
    for o in obs:
        f, v = o["field"], o["value"]
        if not isinstance(v, str):
            continue
        if f in ("ext.contact.email_domain", "ext.contact.website_domain", "entity.website"):
            d = domain_of(f, v)
            if d:
                out.add(("domain", d))
        elif f == "ext.entity.former_name" and is_registered_company_name(norm_name(v)):
            out.add(("former", norm_name(v)))
            if len(name_stem(norm_name(v)).split()) >= 2:
                out.add(("former_stem", name_stem(norm_name(v))))
        elif f in ("entity.legal_name", "entity.trading_name") and o.get("claim_scope") != "former_legal_name":
            n = norm_name(v)
            out.add(("name", n) if is_registered_company_name(n) else ("stem", n))
    return out


def _wanted(sample_keys_of_others: set) -> set:
    """Keys a non-sampled row must hold to be pulled in: same domain, or a former name equal to another
    sample's current name (with or without the legal suffix), and vice versa."""
    want = set()
    for kind, v in sample_keys_of_others:
        if kind == "domain":
            want.add(("domain", v))
        elif kind == "name":
            want.add(("former", v))
        elif kind == "stem" and len(v.split()) >= 2:
            want.add(("former_stem", v))
        elif kind == "former":
            want.add(("name", v))
    return want


def _key_cfg(cfg: MappingConfig) -> MappingConfig:
    return cfg.model_copy(update={"fields": [f for f in cfg.fields if f.target in KEY_TARGETS], "constants": [],
                                  "relationships": None})


def _probe_chunk(args):
    cfg_json, meta, wanted, chunk = args
    eng = Engine(MappingConfig.model_validate_json(cfg_json), meta)
    out = []
    for i, rec in chunk:
        k = obs_keys(eng.process(rec)) & wanted
        if k:
            out.append((i, sorted(k)))
    return out


def choose_ext_cohort(sids: list[str], keep: dict[str, dict[int, dict]]) -> dict[str, list[int]]:
    """Seeded choice of up to CAP_EXT extension-cohort ordinals per source. Recorded in the sample summary."""
    man = load_manifest()
    cfgs = {sid: load_ext_config(sid)[0] for sid in sids}
    sample_keys = {}
    for sid in sids:
        eng = Engine(_key_cfg(cfgs[sid]), man[sid])
        keys = set()
        for i, rec in enumerate(iter_records(ROOT / man[sid]["snapshot"]["path"], cfgs[sid].reader), start=1):
            if i in keep[sid]:
                keys |= obs_keys(eng.process(rec))
        sample_keys[sid] = keys
    chosen, report = {}, {}
    for sid in sids:
        others = set().union(*[k for s, k in sample_keys.items() if s != sid]) if len(sids) > 1 else set()
        wanted = _wanted(others)
        if not wanted or not any(f.target in KEY_TARGETS - {"entity.legal_name", "entity.trading_name"}
                                 for f in cfgs[sid].fields):
            chosen[sid] = []
            continue
        rows = ((i, rec) for i, rec in enumerate(iter_records(ROOT / man[sid]["snapshot"]["path"], cfgs[sid].reader),
                                                 start=1) if i not in keep[sid])
        key_cfg = _key_cfg(cfgs[sid])
        hits = []
        if man[sid]["snapshot"].get("bytes", 0) > 50_000_000:
            with ProcessPoolExecutor(6) as ex:
                futs = []
                while True:
                    part = list(islice(rows, PROBE_CHUNK))
                    if not part:
                        break
                    futs.append(ex.submit(_probe_chunk, (key_cfg.model_dump_json(), man[sid], wanted, part)))
                for f in futs:
                    hits.extend(f.result())
        else:
            eng = Engine(key_cfg, man[sid])
            for i, rec in rows:
                k = obs_keys(eng.process(rec)) & wanted
                if k:
                    hits.append((i, sorted(k)))
        hits.sort()
        # A key held by many rows (a generic stem, a shared domain) cannot identify one business: drop it.
        holders = Counter(k for _, ks in hits for k in ks)
        hits = [(i, [k for k in ks if holders[k] <= 3]) for i, ks in hits]
        hits = [(i, ks) for i, ks in hits if ks]
        rng = random.Random(SEED + 7)
        picked = sorted(rng.sample(hits, min(CAP_EXT, len(hits))))
        chosen[sid] = [i for i, _ in picked]
        report[sid] = {"candidates": len(hits), "picked": len(picked),
                       "by_key_kind": dict(Counter(k[0] for _, ks in picked for k in ks))}
        print(f"{sid}: extension cohort {len(picked)} of {len(hits)} candidates {report[sid]['by_key_kind']}", flush=True)
    OUT_RD_OBS.mkdir(parents=True, exist_ok=True)
    (OUT_RD_OBS / "ext_cohort.json").write_text(json.dumps({"seed": SEED + 7, "cap": CAP_EXT, "sources": report,
                                                             "ordinals": chosen}, indent=1),
                                                encoding="utf-8", newline="\n")
    return chosen


def run(sids: list[str] | None = None) -> dict:
    from datetime import datetime, timezone

    from .store import iter_rows
    man = load_manifest()
    rel = reliability()
    sids = sids or sorted(p.name.split(".")[0] for p in (ROOT / "data" / "rawstore").glob("*") if p.is_dir())
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT_RD_OBS.mkdir(parents=True, exist_ok=True)
    summary = {}
    for sid in sids:
        cfg, prov = load_ext_config(sid)
        eng = Engine(cfg, man[sid], rel.get(sid, rel.get("default", {})), ingested_at)
        rows = list(iter_rows(sid))
        # Baseline rows keep their audited order and record ids; extension rows are numbered after them.
        base = sorted((r for r in rows if r["stratum"] != "cohort_ext"),
                      key=lambda r: (r["stratum"] != "random", r["ordinal"]))
        ext = sorted((r for r in rows if r["stratum"] == "cohort_ext"), key=lambda r: r["ordinal"])
        for r in base:
            if r["source_record_id"]:      # audited ids are reused; later rows are numbered after them
                eng._seen[record_base(r["row"], cfg)] += 1
        n_obs, strata, by_stratum = 0, {}, Counter()
        with open(OUT_RD_OBS / f"{sid}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in base + ext:
                obs = eng.process(r["row"], r["source_record_id"] or None)
                for o in obs:
                    o.update(sample_stratum=r["stratum"], source_row_ordinal=r["ordinal"],
                             mapping=prov["mapping"], approval_state=prov["approval_state"])
                    fh.write(json.dumps(o, default=str) + "\n")
                    n_obs += 1
                if obs:
                    strata[obs[0]["source_record_id"]] = r["stratum"]
                    by_stratum[r["stratum"]] += 1
        # Edges live in their own folder: every *.jsonl directly under observations/ is an observation file.
        (OUT_RD_OBS / "edges").mkdir(exist_ok=True)
        with open(OUT_RD_OBS / "edges" / f"{sid}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for e in eng.edges:
                fh.write(json.dumps(e | {"approval_state": prov["approval_state"]}) + "\n")
        summary[sid] = {"source_id": sid, **prov, "records": len(rows), "records_with_output": dict(by_stratum),
                        "observations": n_obs, "edges": len(eng.edges), "extractor_version": eng.extractor_version,
                        "engine_report": eng.report(), "record_strata": strata}
        (OUT_RD_OBS / f"{sid}.sample.json").write_text(json.dumps(summary[sid], indent=1, default=str),
                                                      encoding="utf-8", newline="\n")
        print(f"{sid}: {prov['mapping']} ({prov['approval_state']}) -> {n_obs} observations, "
              f"{len(eng.edges)} edges, {dict(by_stratum)}", flush=True)
    return {sid: {k: v for k, v in s.items() if k not in ("engine_report", "record_strata")} for sid, s in summary.items()}
