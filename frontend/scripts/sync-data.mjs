import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";

const root = new URL("../../", import.meta.url);
const output = new URL("../data/", import.meta.url);
const base = "outputs/discovery/category_ranked/";
const read = path => readFile(new URL(path, root), "utf8");
const json = async path => JSON.parse(await read(path));

const [shortlistFile, metrics, auditMetrics, catalogueFile, captureFile] = await Promise.all([
  read(base + "shortlist.jsonl"), json(base + "metrics.json"), json(base + "audit/metrics.json"),
  read("outputs/discovery/catalogue_pool.jsonl"), json("data/triage-recheck/discovery-site-captures.json"),
]);

const sha256 = createHash("sha256").update(shortlistFile).digest("hex");
if (sha256 !== auditMetrics.shortlist_sha256 || sha256 !== captureFile.shortlistSha256) {
  throw new Error("The shortlist, saved responses, and audit must come from the same run");
}

const parseLines = file => file.trim().split(/\r?\n/).map(line => JSON.parse(line));
const packages = new Map(parseLines(catalogueFile).map(row => [row.dataset_id, row]));
const audited = new Map(captureFile.audit.map(row => [row.dataset_id, row]));
const humanReviews = captureFile.audit.filter(row => row.human_label);
if (humanReviews.some(row => !["YES", "NO", "UNCERTAIN"].includes(row.human_label) ||
    !row.human_reviewer || !row.human_recorded_at || row.human_shortlist_sha256 !== sha256) ||
    humanReviews.length !== auditMetrics.human_verdicts) {
  throw new Error("Human discovery reviews must identify the current shortlist and agree with audit metrics");
}
const effectiveLabel = row => row.human_label || row.label;
const verdicts = Object.fromEntries(["Yes", "No", "Uncertain"].map(label =>
  [label, captureFile.audit.filter(row => effectiveLabel(row) === label.toUpperCase()).length]));
const originalVerdicts = Object.fromEntries(["yes", "no", "uncertain"].map(label =>
  [label, captureFile.audit.filter(row => row.label === label.toUpperCase()).length]));
const datasets = parseLines(shortlistFile).map((row, index) => {
  const id = row.dataset_id;
  const metadata = captureFile.ranking[id];
  const audit = audited.get(id);
  const capture = captureFile.captures[id];
  const pkg = packages.get(id);
  const components = row.score_components;
  const points = components?.ranking_points;
  if (row.rank !== index + 1 || row.metadata_score !== metadata?.score || !pkg ||
      !Number.isFinite(points) || Math.abs(components.publisher_points + components.catalogue_category.points - points) > 1e-9 ||
      Math.abs(components.publisher_breakdown.reduce((sum, rule) => sum + rule.points, 0) - components.publisher_points) > 1e-9 ||
      (audit && (Number(audit.rank) !== row.rank || audit.resource_id !== row.evidence.resource_id ||
        Number(audit.ranking_points) !== points ||
        capture?.source?.resourceId !== audit.resource_id || !capture.catalogue.body || !capture.source.rows?.length))) {
    throw new Error(`Mismatched discovery evidence for rank ${row.rank} (${id})`);
  }
  return {
    id, rank: row.rank, title: row.title, publisher: row.publisher, url: row.url,
    points, publisherPoints: components.publisher_points, catalogueCategory: components.catalogue_category,
    publisherBreakdown: components.publisher_breakdown,
    format: row.resource_formats.split("|").filter(Boolean), reason: row.reason,
    licence: pkg.licence, query: pkg.query, metadata, evidence: row.evidence,
    audit: audit ? {
      verdict: effectiveLabel(audit)[0] + effectiveLabel(audit).slice(1).toLowerCase(), reviewer: audit.reviewer,
      human: audit.human_label ? { label: audit.human_label, reviewer: audit.human_reviewer,
        recordedAt: audit.human_recorded_at, note: audit.human_note } : null,
      rows: Number(audit.rows_reopened), originalRank: Number(audit.original_rank),
      route: audit.review_route, note: audit.evidence, url: audit.evidence_url,
    } : null,
    capture,
  };
});
if (new Set(datasets.map(row => row.id)).size !== metrics.shortlist ||
    audited.size !== auditMetrics.sampled || originalVerdicts.yes !== auditMetrics.yes ||
    originalVerdicts.no !== auditMetrics.no || originalVerdicts.uncertain !== auditMetrics.uncertain) {
  throw new Error("Discovery totals disagree with audit metrics");
}

const { capturedAt } = captureFile;
const result = {
  catalogueCount: metrics.catalogue_candidates, resourceTables: metrics.rows_read,
  shortlistCount: datasets.length, auditCount: audited.size, verdicts,
  date: [...packages.values()].map(row => row.retrieved_at).filter(Boolean).sort().at(-1),
  capturedAt, distinctScores: metrics.distinct_shortlist_scores, sha256,
  publisherMaxPoints: metrics.publisher_max_points, rankingMaxPoints: metrics.ranking_max_points,
  catalogueCategoryPoints: metrics.catalogue_category_points,
  humanVerdicts: humanReviews.length,
  carriedForwardFrom: auditMetrics.carried_forward_from_sha256, datasets,
};
await mkdir(output, { recursive: true });
await writeFile(new URL("part-one.json", output), JSON.stringify(result) + "\n");
console.log(`Synced ${datasets.length} ranked datasets and ${audited.size} audited datasets with catalogue responses and source previews`);
