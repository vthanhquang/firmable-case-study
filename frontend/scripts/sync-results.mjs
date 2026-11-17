import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";

const root = new URL("../../", import.meta.url);
const output = new URL("../data/", import.meta.url);
const final = "outputs/experiments/quality-final/";
const contextRun = "outputs/experiments/profile-context/";
const read = path => readFile(new URL(path, root), "utf8");
const json = async path => JSON.parse(await read(path));
const result = path => json(final + path);
const evaluation = path => result(`evaluation/${path}.json`);

async function* lines(path) {
  const input = createReadStream(new URL(path, root), { encoding: "utf8" });
  try {
    for await (const line of createInterface({ input, crlfDelay: Infinity })) {
      if (line.trim()) yield JSON.parse(line);
    }
  } finally {
    input.destroy();
  }
}

async function collect(path) {
  const records = [];
  for await (const record of lines(path)) records.push(record);
  return records;
}

const [manifest, qld, replay, finalSummary, holdout, rso, summary, links, review, unlinked, relationships, audit,
  auditSummary, adjudications, registry, identityBenchmark, coverage, profiles, profileBenchmark, deletion,
  corruption, nameCorruption, checks, shortlistFile, linkFile, profileContext, profileFile] = await Promise.all([
  json("outputs/sources/selected_sources.json"), json("data/registered/qld_suitable_operators/source.json"),
  result("replay.json"), result("summary.json"), evaluation("mapping-holdout"), evaluation("mapping-rso-semantics"),
  result("identity/summary.json"), collect(final + "identity/proposed_links.jsonl"), collect(final + "identity/review_queue.jsonl"),
  collect(final + "identity/unlinked_queue.jsonl"), collect(final + "identity/relationships.jsonl"),
  evaluation("link_audit_evidence"), evaluation("link_audit_metrics"), evaluation("link_audit_adjudications"),
  evaluation("registry_audit_crosscheck"), evaluation("identity-benchmark"), evaluation("full-register-coverage"),
  collect(final + "profiles/company_profiles_50.jsonl"), evaluation("profile-benchmark"),
  evaluation("source_deletion_impact"), evaluation("source_corruption_impact"), evaluation("source_name_corruption_impact"),
  evaluation("deterministic_replay_check"), read("outputs/discovery/category_ranked/shortlist.jsonl"),
  read(final + "identity/proposed_links.jsonl"),
  result("profiles/company_context.json"), read(final + "profiles/company_profiles_50.jsonl"),
]);

const qldListing = shortlistFile.trim().split(/\r?\n/).map(line => JSON.parse(line)).find(row => row.title === qld.title);
const sources = Object.fromEntries([...manifest, {
  ...qld, dataset_id: qldListing?.dataset_id, url: qldListing?.evidence.url, catalogue_url: qldListing?.url,
}].map(source => [source.source_id, {
  title: source.title, publisher: source.publisher, datasetId: source.dataset_id, url: source.url,
  catalogue: source.catalogue_url, resource: source.resource_name, licence: source.licence,
}]));

const profileEvidence = new Set();
function collectEvidence(value) {
  if (!value || typeof value !== "object") return;
  if (value.observation_id) profileEvidence.add(value.observation_id);
  for (const id of value.supporting_observations ?? []) profileEvidence.add(id);
  for (const id of value.observation_ids ?? []) profileEvidence.add(id);
  for (const child of Object.values(value)) collectEvidence(child);
}
for (const profile of profiles) collectEvidence(profile);
const observationEvidence = {};

function presentObservation(row) {
  return {
    id: row.observation_id, source: row.source_id, record: row.source_record_id, field: row.field,
    value: row.value, raw: row.raw_value, sourceFields: row.source_fields, transform: row.transform,
    level: row.derivation_level, confidence: row.confidence, scope: row.claim_scope,
    validFrom: row.valid_from, validTo: row.valid_to, row: row.source_row_ordinal,
  };
}
const privateField = /(?:email|phone|fax|date.?of.?birth|latitude|longitude)/i;
const contextValidation = await json(contextRun + "validation.json");

async function contextualMapping(id, baseDigest) {
  const validation = contextValidation.sources[id];
  if (!validation) return null;
  const mapping = await json(contextRun + id + ".json");
  const state = await json(`runs/${id}/${mapping.run_id}/state.json`);
  if (validation.baseDigest !== baseDigest || mapping.status !== "PENDING_REVIEW" ||
      validation.configDigest !== mapping.config_digest || state.final_digest !== mapping.config_digest) {
    throw new Error(`Supplemental mapping evidence differs for ${id}`);
  }
  const examples = [];
  const seen = new Set();
  for await (const row of lines(contextRun + `observations/${id}.jsonl`)) {
    const kind = row.field + "\0" + row.source_fields.join(" ");
    if (examples.length < 32 && (!seen.has(kind) || examples.length < 8)) {
      examples.push(presentObservation(row));
      seen.add(kind);
    }
  }
  return {
    mapping, examples,
    validation: { rows: validation.rows, matched: validation.matched, expected: validation.expected,
      unsupported: validation.unsupported, fields: validation.fields },
    trace: { started: state.started_at, finished: state.finished_at, stages: state.stages.length,
      proposals: state.proposals.length, calls: state.tool_calls },
  };
}

const ids = [...Object.keys(replay.mappings), "asic_credit_licensees", "qld_suitable_operators"];
const mappings = await Promise.all(ids.map(async id => {
  const extraction = replay.mappings[id] ?? null;
  const variant = extraction?.variant ?? "quality-final";
  const mapping = await result(extraction ? `selected-mappings/${id}.json` : `${id}.json`);
  const runPath = `runs/${id}/${mapping.run_id}`;
  const holdoutSource = (id === "qld_suitable_operators" ? rso : holdout).sources[id];
  const selected = holdoutSource?.versions[variant];
  if (!selected || selected.run_id !== mapping.run_id ||
      (extraction && (extraction.run_id !== mapping.run_id || extraction.config_digest !== mapping.config_digest))) {
    throw new Error(`Holdout or replay does not identify the selected mapping for ${id}`);
  }
  const [state, events, context] = await Promise.all([
    json(`${runPath}/state.json`), collect(`${runPath}/events.jsonl`), contextualMapping(id, mapping.config_digest),
  ]);
  const observations = [];
  if (extraction) {
    let readRows = 0;
    for await (const row of lines(final + `observations/${id}.jsonl`)) {
      readRows++;
      if (privateField.test(row.field)) continue;
      if (profileEvidence.has(row.observation_id)) observationEvidence[row.observation_id] = presentObservation(row);
      if (observations.length < 50 && row.raw_value != null && !row.field.startsWith("address.")) {
        observations.push(presentObservation(row));
      }
    }
    if (readRows !== extraction.canonical_observations) throw new Error(`Observation total differs for ${id}`);
  }
  const variants = Object.fromEntries(Object.entries(holdoutSource.versions).map(([label, version]) => [label, {
    rows: version.rows, exact: version.exact, checks: version.checked_rows_and_fields,
    expected: version.expected_claims, matched: version.matched_claims, unsupported: version.unexpected_claims,
  }]));
  return {
    id, ...sources[id], variant, extraction, mapping, observations, context,
    validation: {
      ...variants[variant], fields: selected.fields, scope: selected.scope_issues,
      excluded: holdoutSource.excluded_onboarding_rows, excludedEarlier: holdoutSource.excluded_previous_evaluation_rows,
      variants, roles: selected.holder_name_coverage_by_source_role,
    },
    trace: {
      sameDigest: state.final_digest === mapping.config_digest, status: state.status,
      started: state.started_at, finished: state.finished_at, calls: state.tool_calls,
      stages: state.stages.map(({ stage, at }) => ({ stage, at })),
      evaluations: events.filter(event => event.kind === "stage" && event.stage === "EVALUATED")
        .map(({ round, holdout_errors, critic_wrong, critic_doubtful }) =>
          ({ round, holdout_errors, critic_wrong, critic_doubtful })),
    },
  };
}));

const byLink = new Map(links.map(row => [row.link_id, row]));
const registryByLink = new Map(registry.pairs.map(row => [row.link_id, row]));
const spotByPair = new Map(registry.publisher_spot_checks.map(row => [row.pair, row]));
const byAdjudication = new Map(adjudications.cases.map(row => [row.link_id, row]));
const auditPairs = audit.map(row => {
  const link = byLink.get(row.link_id);
  if (!link || link.source_a_record !== row.record_a || link.source_b_record !== row.record_b ||
      link.confidence !== row.score) throw new Error(`Audit pair ${row.pair} differs from replay output`);
  return {
    ...link, auditIndex: row.pair, sampleStrata: row.sample_strata, aView: row.source_records.record_a.claims,
    bView: row.source_records.record_b.claims, proxy: { label: row.proxy_label, reason: row.proxy_reason },
    humanLabel: row.human_label, adjudication: byAdjudication.get(row.link_id),
    registry: registryByLink.get(row.link_id), spotCheck: spotByPair.get(row.pair),
  };
});
if (links.length !== summary.links || review.length !== summary.review_pairs || unlinked.length !== summary.unlinked_queue ||
    auditPairs.length !== auditSummary.sampled || profiles.length !== profileBenchmark.challenger.profiles ||
    relationships.length !== summary.relationships ||
    createHash("sha256").update(linkFile).digest("hex") !== auditSummary.proposed_links_sha256) {
  throw new Error("Replay, registry audit, and profile counts disagree");
}

const profileKeys = profiles.map(profile => profile.entity_key);
if (profileContext.profileSha256 !== createHash("sha256").update(profileFile).digest("hex") ||
    Object.keys(profileContext.companies).length !== profiles.length ||
    profiles.some(row => profileContext.companies[row.entity_key]?.abn !== row.fields["entity.abn"]?.value)) {
  throw new Error("Supplemental context does not identify the exact profile sample");
}
const linksByEntity = Object.fromEntries(profileKeys.map(key => [key, links.filter(link =>
  link.canonical_entity_key === key).map(link => link.link_id)]));
const snapshots = {
  mapping: { sources, mappings, benchmark: finalSummary.mapping, protocol: holdout.protocol },
  identity: { sources, summary, links, review, unlinked, relationships, audit: auditPairs, auditSummary,
    benchmark: identityBenchmark, coverage, registrySummary: registry.summary, profileKeys },
  profiles: { sources, profiles, observations: observationEvidence, linksByEntity, deletion, corruption, nameCorruption,
    benchmark: profileBenchmark, linkedCount: summary.entities_in_multiple_sources,
    context: profileContext.companies, registryCheckedAt: profileContext.registryCheckedAt },
  "write-up": { usage: finalSummary.usage, checks, mapping: finalSummary.mapping, identity: summary,
    profiles: profileBenchmark.challenger, auditSummary },
};

await mkdir(output, { recursive: true });
await Promise.all([
  ...Object.entries(snapshots).map(([part, data]) => writeFile(new URL(`${part}.json`, output), JSON.stringify(data) + "\n")),
  copyFile(new URL("outputs/discovery/category_ranked/audit/audit_20.csv", root), new URL("discovery-audit.csv", output)),
  copyFile(new URL(final + "evaluation/link_audit_50.csv", root), new URL("link-audit.csv", output)),
]);
console.log(`Synced ${mappings.length} mappings, ${links.length} links, ${auditPairs.length} audit pairs, and ${profiles.length} profiles`);
