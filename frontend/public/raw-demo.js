import { identityChart, mappingChart, sourcePairs } from "./replay-charts.js";

const number = new Intl.NumberFormat("en-AU");
const count = value => number.format(value);
const dollars = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 });
const share = new Intl.NumberFormat("en-AU", { style: "percent", maximumFractionDigits: 1 });
const sourceNames = {
  acnc_charities: "ACNC", asic_companies: "ASIC Companies", asic_credit_licensees: "ASIC Credit",
  ato_tax_transparency: "ATO 2024–25", ato_tax_transparency_2023_24: "ATO 2023–24",
  dewr_employment_providers: "DEWR", qbcc_licensees: "QBCC", vic_liquor: "Victorian Liquor",
};
const label = value => String(value ?? "—").replace(/^ext\.[^.]+\./, "").replaceAll("_", " ");
const score = value => value == null ? "—" : Number(value).toFixed(2);
const source = id => sourceNames[id] ?? label(id);
const entityName = row => row.fields["entity.legal_name"]?.value ?? row.entity_key;
const human = state => state === "approved" ? "Human review verified" : state === "pending_human_review" ? "Awaiting human review" : label(state);
const reviewed = row => row.reviews?.human ?? row.reviews?.ai_assistant;
const reviewText = row => reviewed(row) ? label(reviewed(row).verdict).replace(/^./, c => c.toUpperCase()) +
  (reviewed(row).reviewer_kind === "human" ? " · Human" : " · AI") : row.audit?.label || "Unlabelled";
const fieldLabels = {
  "entity.abn": "ABN", "entity.acn": "ACN", "entity.legal_name": "Legal name", "entity.status": "Status",
  "entity.entity_type": "Entity type", "entity.trading_name": "Trading name", "entity.website": "Website",
  "entity.date_registered": "Registration date", "address.full": "Street address", "address.locality": "Locality",
  "address.state": "State", "address.postcode": "Postcode", "address.country": "Country", lga: "Council",
  total_income: "Total income", taxable_income: "Taxable income", tax_payable: "Tax payable",
  tax_payable_growth: "Tax payable change", taxable_income_growth: "Taxable income change",
  total_income_growth: "Total income change", revenue_growth: "Total income change",
};
const field = name => fieldLabels[name] ?? label(name).replace(/^entity\./, "");
const nameOf = (record, fallback) => record?.names?.[0] ?? record?.source_id?.replaceAll("_", " ") ?? fallback ?? "Unavailable";

function columnsText(data) {
  return count(data.columns.read_by_approved_config) + " → " + count(data.columns.read_by_extension_config);
}

export function runBanner(ui, part, archived = false) {
  const { el, siteLink } = ui;
  return el("aside", "run-banner",
    el("span", "", el("strong", "", archived ? "Earlier benchmark" : "Latest raw-data replay"),
      archived ? " · Saved evaluation" : " · Review preview"),
    archived ? siteLink("View latest run", part, { run: "latest" })
      : siteLink("View earlier benchmark", part, { run: "benchmark" }));
}

export function demoView(data, root, ui) {
  const { el, siteLink } = ui;
  const { replay, featured, review } = data;
  const financial = featured.find(row => row.theme === "financial");
  const amounts = financial?.income.toSorted((a, b) => a.period.localeCompare(b.period)) ?? [];
  const max = Math.max(...amounts.map(row => row.value), 1);
  const showcase = financial && el("article", "demo-showcase",
    el("p", "eyebrow", "From the replay"),
    el("h2", "", financial.name),
    el("p", "detail-note", "ATO reported total income"),
    ...amounts.map(row => {
      const bar = el("div", "demo-bar", el("div", "demo-bar-fill"));
      bar.firstChild.style.width = (row.value / max * 100).toFixed(1) + "%";
      bar.setAttribute("aria-hidden", "true");
      return el("div", "demo-amount", el("div", "demo-amount-label", el("span", "", row.period),
        el("strong", "", dollars.format(row.value))), bar);
    }),
    siteLink("Open company profile", "profiles", { entity: financial.id }));
  const paths = [
    ["discovery", "Discovery", "See the ranked shortlist and inspect a publisher sample."],
    ["mapping", "Mapping", "Open a source to follow its rules, validation and review history.", { source: "vic_liquor" }],
    ["identity", "Identity", "Inspect the 50 audited links, review verdicts and supporting evidence.", { view: "audit" }],
    ["profiles", "Profiles", "Explore establishment records, licence details and financial history."],
    ["write-up", "Write-up", "Review costs, trade-offs and open decisions."],
  ];
  root.replaceChildren(
    el("section", "demo-hero",
      el("div", "page-intro",
        el("p", "eyebrow", "Firmable case study · Latest run"),
        el("h1", "", "From public records to company profiles"),
        el("p", "intro", "Follow the evidence from a publisher’s file through agent-written mappings, cautious matching and profiles with source-level provenance."),
        el("div", "demo-actions", siteLink("Explore the 50 profiles", "profiles"),
          siteLink("See the run results", "write-up"))),
      showcase),
    el("section", "demo-proof", el("h2", "sr-only", "Replay results"),
      ...[["Columns read", columnsText(data)], ["Proposed links", count(replay.challenger.links)],
        ["Profiles", data.profiles], ["Audit labelled", review.audit_labelled + "/" + review.audit_rows]].map(([name, value]) =>
        el("div", "", el("strong", "", String(value)), el("span", "", name)))),
    el("section", "catalogue demo-path",
      el("div", "section-heading", el("h2", "", "Walk through the case study")),
      ...paths.map(([part, title, description, params]) => el("div", "demo-path-row",
        siteLink(title, part, params), el("p", "", description)))));
}

export function rawMappingView(data, ui) {
  const { note, copy, section, facts, table, disclosure, siteLink, link, jsonPreview, callout } = ui;
  const { overview } = data;
  const extensionCount = cfg => cfg.fields.filter(rule => rule.target.startsWith("ext.")).length;
  const assessmentLabel = row => row.sample.approval_state === "approved" ? "Human review verified" : row.assessment?.verdict === "ready" ? "Ready for sign-off"
    : row.assessment?.verdict === "needs_changes" ? "Needs changes" : "Not yet assessed";
  const assessed = overview.review.mapping_assessed ?? 0;
  const verdicts = overview.review.mapping_verdicts ?? {};
  return {
    number: 2, title: "Schema inference & mapping",
    intro: "Compare the sources, see what their mappings extracted, and open the evidence behind each result.",
    metrics: [
      ["Sources mapped", data.mappings.length, "Includes two ATO reporting years"],
      ["Source columns read", count(overview.columns.read_by_extension_config) + " / " + count(overview.columns.raw_columns),
        count(overview.columns.read_by_approved_config) + " in the base mappings"],
      ["Observations extracted", count(overview.observations), "Across all eight source extracts"],
      ["Human review verified", (overview.review.verified_mappings ?? 0) + "/" + data.mappings.length,
        overview.review.pending_mappings + " awaiting review · " + (verdicts.needs_changes ?? 0) + " need changes"],
    ],
    visualization: () => mappingChart(data.mappings, source, ui),
    overview: [
      callout("One row can describe several things", "The Victorian register yields a licensee, a licence and a premises from one row.",
        siteLink("Inspect Victorian Liquor", "mapping", { source: "vic_liquor" })),
      callout("Mapping review", (overview.review.verified_mappings ?? 0) + " mappings verified by the project owner. " +
        "Seven proposals were corrected locally with no additional model API calls. Open a source for the validation evidence and confirmation.",
        siteLink("Inspect ACNC findings", "mapping", { source: "acnc_charities" })),
    ],
    heading: "Explore the mappings", description: "Open a source to inspect the rules, raw values, critic verdicts and exact configuration.",
    views: [{ id: "mappings", label: "Source mappings", rows: data.mappings }],
    columns: ["Source", "Rows extracted", "Review"],
    row: row => [row.title, row.publisher + " · " + extensionCount(row.config) + " extension rules",
      count(row.sample.records), assessmentLabel(row)],
    match: (row, params) => row.id === params.get("source"),
    detail: row => {
      const { config: cfg, trace, columns, holdout } = row;
      const elapsed = Math.round((Date.parse(trace.finished_at) - Date.parse(trace.started_at)) / 1000);
      const roles = Object.entries(cfg.entities ?? {});
      const format = cfg.reader.archive_member ? "ZIP · " + (cfg.reader.delimiter === "\t" ? "TSV" : "CSV")
        : cfg.reader.format.toUpperCase();
      return ["Extension mapping", row.title, [
        note(row.publisher),
        facts([["Review", assessmentLabel(row)], ["Reader", format], ["Rows extracted", count(row.sample.records)],
          ["Observations", count(row.sample.observations)]], "detail-meta"),
        row.human_verification ? section("Human verification", copy("Confirmed by " + row.human_verification.reviewer +
          " on " + row.human_verification.decided_at.slice(0, 10) + ". Applies to this exact configuration and source snapshot."),
          disclosure("Confirmation record", copy(row.human_verification.comment))) : null,
        row.assessment ? section("Mapping review", copy(row.assessment.summary),
          note(row.assessment.reviewer + " · " + row.assessment.reviewed_at.slice(0, 10) +
            " · Human approval: " + human(row.sample.approval_state)),
          facts([["Raw records replayed", count(row.assessment.checks.records_checked)],
            ["Observations compared", count(row.assessment.checks.saved_observations)],
            ["Replay differences", row.assessment.checks.replay_mismatches.length]], "evidence-facts"),
          note("Replay agreement confirms reproducibility; semantic findings are assessed separately below."),
          ...row.assessment.findings.map(finding => section(finding.priority + " · " + finding.title,
            copy(finding.evidence), copy("Recommended correction: " + finding.action))),
          disclosure("Assessment notes recorded before verification", ...row.assessment.notes.map(copy)),
          ...row.assessment.references.map(ref => link(ref.title, ref.url))) : null,
        section("Source columns and record roles", copy(cfg.grain_rationale),
          facts([["Columns read", columns.read_by_approved_config + " → " + columns.read_by_extension_config],
            [trace.local_revision ? "Regression rows" : "Held-out rows", count(holdout.records)], ["Declared edges emitted", count(row.sample.edges)],
            ["Record key", cfg.record_id.source_paths.join(" + ") || label(cfg.record_id.strategy)]], "evidence-facts"),
          roles.length ? table("record roles", ["Role", "Type", "Key"],
            roles.map(([role, value]) => [role, value.kind, value.key_paths.join(" + ")])) : null,
          cfg.relationships?.length ? table("declared relationships", ["Relationship", "From", "To"],
            cfg.relationships.map(edge => [label(edge.type), edge.from_role, edge.to_role])) : null),
        section("Source values and observations",
          table("raw-to-mapped examples", ["Data row", "Source column", "Raw value", "Mapped field", "Value", "Role"],
            row.examples.map(claim => [claim.source_row_ordinal, claim.source_fields.join(" + "), claim.raw_value,
              claim.field, claim.value, claim.entity_role])),
          row.examples[0]?.licence_detail?.attribution ? note(row.examples[0].licence_detail.attribution) : null),
        section("Rules and validation",
          disclosure("Field rules · " + cfg.fields.length, () => [
            table("mapping rules", ["Columns", "Target", "Role", "Transforms", "Confidence"],
              cfg.fields.map(rule => [rule.source_paths.join(" + "), rule.target, rule.entity ?? "subject",
                rule.steps.map(step => step.op).join(" → "), score(rule.confidence)])),
          ]),
          disclosure(trace.local_revision ? "Frozen-sample regression results" : "Held-out field results", table("holdout results", ["Field", "Source columns", "Present", "Emitted", "Errors", "Drops"],
            holdout.fields.map(rule => [rule.target, rule.source_paths.join(" + "), rule.source_present, rule.emitted,
              Object.values(rule.errors ?? {}).reduce((sum, x) => sum + x, 0),
              Object.values(rule.dropped ?? {}).reduce((sum, x) => sum + x, 0)]))),
          holdout.issues.length ? disclosure("Validator findings", table("validator findings", ["Finding", "Severity", "Field"],
            holdout.issues.map(issue => [issue.code, issue.severity, issue.target]))) : null,
          trace.local_revision ? note("Local correction validated against saved source records. No model critic was called.") :
            disclosure("Semantic critic · " + trace.critic_model, table("critic decisions", ["Field", "Columns", "Verdict"],
              row.critic.map(verdict => [verdict.target, verdict.source_paths?.join(" + "), verdict.verdict]))),
          cfg.constants?.length ? disclosure("Scoped defaults", table("mapping constants", ["Field", "Value", "Role", "Scope"],
            cfg.constants.map(rule => [rule.target, rule.value, rule.entity ?? "subject", rule.claim_scope ?? "Unspecified"]))) : null,
          row.crosswalks.length ? disclosure("Draft crosswalks", table("crosswalk status", ["Crosswalk", "Level", "Entries", "Review"],
            row.crosswalks.map(item => [item.name, item.derivation_level, item.entries, item.review_status]))) : null,
          cfg.unmapped.length ? disclosure("Unmapped columns · " + cfg.unmapped.length,
            table("unmapped columns", ["Column", "Reason"], cfg.unmapped.map(item => [item.source_path, item.reason]))) : null),
        section(trace.local_revision ? "Local correction and review" : "Agent run and review",
          facts([["Run ID", row.run_id], ["Proposer", row.model], ["Proposal count", trace.proposals],
            ["Tool calls", trace.tool_calls], ["Model tokens in this run", count(trace.usage.tokens ?? 0)],
            ["Wall time", elapsed + " s"]], "evidence-facts"),
          trace.draft_source ? copy("Recovered agent draft from " + trace.draft_source.run_id + ". " + trace.draft_source.note) : null,
          trace.local_revision ? copy(trace.local_revision.reason) : null,
          trace.local_revision ? note("Original agent run retained: " + trace.local_revision.parent_run_id +
            ". " + trace.local_revision.validation_scope + ". " + human(row.sample.approval_state) + ".") : null,
          trace.feedback_source ? note("Feedback source · " + trace.feedback_source) : null,
          disclosure("Run checkpoints", table("agent checkpoints", ["Checkpoint", "Time (UTC)"],
            trace.stages.map(stage => [label(stage.stage), stage.at]))),
          disclosure("Exact configuration", () => [note("Config SHA-256 · " + row.config_digest),
            note("Snapshot SHA-256 · " + row.snapshot_sha256), jsonPreview(cfg)]),
          row.catalogue_url ? link("Publisher dataset", row.catalogue_url) : null),
      ]];
    },
  };
}

export function rawIdentityView(data, ui) {
  const { el, note, copy, section, facts, table, siteLink, callout, link } = ui;
  const { replay, review } = data.overview;
  const pairs = sourcePairs(data.links);
  const params = new URLSearchParams(window.location.search);
  const selectedPair = pairs.find(pair => pair.a === params.get("source_a") && pair.b === params.get("source_b"));
  const matchById = new Map(data.links.map(row => [row.link_id, row]));
  const audit = data.audit.map(row => ({ ...matchById.get(row.link), audit: row }));
  const download = el("a", "text-button", "Download the audit CSV ↓");
  download.href = "/raw-link-audit.csv";
  download.download = "";
  return {
    number: 3, title: "Entity identification",
    intro: "Review proposed links, the records left separate, and how the challenger differs from strict-v2 on the same observations.",
    metrics: [
      ["Proposed links", count(replay.challenger.links), "Threshold " + replay.threshold],
      ["Multi-source entities", count(replay.challenger.entities_in_multiple_sources), count(replay.records) + " source records evaluated"],
      ["Unlinked queue", count(data.queue.length), "Records with an explicit reason"],
      ["Human-reviewed links", review.audit_labelled + "/" + review.audit_rows,
        (review.human_verdicts?.pass ?? 0) + " pass · " + (review.human_verdicts?.fail ?? 0) + " fail · " +
        (review.human_verdicts?.uncertain ?? 0) + " uncertain"],
    ],
    visualization: () => identityChart(Object.keys(data.sources), pairs, source, ui),
    overview: [
      callout("Same-input matcher comparison", count(replay.comparison.links_added) +
        " links gained domain and name corroboration. " + count(replay.comparison.links_removed) + " links moved to review."),
      callout("Review evidence", "Human reviews: " + review.audit_labelled + "/" + review.audit_rows +
        ". Open a decision to see the reviewer, rationale and source references. Results describe this audit sample.", download),
    ],
    heading: "Explore match decisions", description: "Open a link to compare the records and evidence, or review why a record stayed unlinked.",
    anchor: "match-decisions",
    filter: selectedPair && ((row, view) => view !== "links" ||
      (row.a.source_id === selectedPair.a && row.b.source_id === selectedPair.b) ||
      (row.a.source_id === selectedPair.b && row.b.source_id === selectedPair.a)),
    filterNotice: selectedPair && (view => {
      if (view !== "links") return null;
      return el("aside", "pair-filter",
        el("strong", "", source(selectedPair.a) + " ↔ " + source(selectedPair.b) + " · " + count(selectedPair.links) + " proposed links"),
        siteLink("Clear pair filter", "identity", { view: "links" }));
    }),
    views: [{ id: "audit", label: "Audit sample", rows: audit }, { id: "links", label: "Proposed links", rows: data.links },
      { id: "unlinked", label: "Unlinked queue", rows: data.queue }],
    columns: view => view === "unlinked" ? ["Source record", "Best score", "Disposition"] : ["Record pair", "Policy score", "Review"],
    row: (row, view) => view === "unlinked"
      ? [nameOf(row.record, row.source_record), label(row.reason), score(row.best_score), label(row.candidate_decision)]
      : [nameOf(row.a, row.source_a_record), nameOf(row.b, row.source_b_record) + " · " + source(row.a.source_id) + " / " + source(row.b.source_id),
        score(row.confidence), view === "audit" || reviewed(row) ? reviewText(row) : label(row.rule)],
    search: row => [row.link_id, row.rule, row.a?.abn, row.b?.abn, row.candidate?.names, row.source_record, reviewText(row)],
    match: (row, params) => row.link_id === params.get("link") || row.source_record === params.get("record"),
    detail: (row, view) => view === "unlinked" ? ["Unlinked record", nameOf(row.record, row.source_record), [
      facts([["Reason", label(row.reason)], ["Best score", score(row.best_score)], ["Decision", label(row.candidate_decision)]], "detail-meta"),
      section("Closest candidate", copy(nameOf(row.candidate, row.best_candidate)), note(row.best_candidate), note(row.next_action)),
      section("Source record", note(row.source_record)),
    ]] : ["Proposed link", nameOf(row.a, row.source_a_record), [
      facts([["Policy score", score(row.confidence)], ["Threshold", row.threshold], ["Rule", label(row.rule)],
        ["Audit", reviewed(row) || row.audit ? reviewText(row) : "Outside audit view"]], "detail-meta"),
      reviewed(row) ? section("Review decision", copy(reviewed(row).note),
        note(reviewed(row).reviewer + " · " + reviewed(row).reviewed_at.slice(0, 10)),
        ...(reviewed(row).references ?? []).map(ref => link(ref.title, ref.url))) : null,
      section("Records compared", table("source records", ["Source", "Name", "ABN", "ACN", "Record ID"],
        [row.a, row.b].map(record => [source(record.source_id), record.names.join(", "), record.abn.join(", "),
          record.acn.join(", "), record.record_id]))),
      section("Decision evidence", table("match signals", ["Signal", "Value"], row.evidence.map(item => [label(item.type), item.value])),
        note("Policy " + row.policy_version + " · sampled strata " + row.strata.join(" + ")),
        row.audit?.note ? copy(row.audit.note) : null),
      data.profileKeys.includes(row.canonical_entity_key)
        ? siteLink("Open company profile", "profiles", { entity: row.canonical_entity_key }) : null,
    ]],
  };
}

export function rawProfilesView(data, ui, show) {
  const { el, note, copy, section, facts, table, disclosure, siteLink, callout } = ui;
  const { overview } = data;
  const asList = value => Array.isArray(value) ? value : value == null ? [] : [value];
  const companyDetails = row => Object.entries(row.firmographics).filter(([key, value]) =>
    key !== "financial_facts" && asList(value).some(item => item?.provenance));
  const coverageSections = [
    ["Core fields", row => Object.keys(row.fields).length],
    ["Financial history", row => row.firmographics.financial_facts?.length],
    ["Locations", row => row.establishments.length + (row.locations?.length ?? 0)],
    ["Licences", row => row.licences.length],
    ["Company details", row => companyDetails(row).length],
    ["Charity purpose", row => Object.values(row.firmographics.sector_tags ?? {}).some(tags => tags.length)],
    ["Registration events", row => row.registration_events.length],
    ["Relationships", row => row.relationships.length],
  ];
  function coverageMark(title, available) {
    const mark = el("span", available ? "coverage-mark available" : "coverage-mark missing",
      el("span", "", available ? "✓" : "—"), el("span", "sr-only", title + (available ? ": data available" : ": no data in this profile")));
    mark.firstChild.setAttribute("aria-hidden", "true");
    mark.title = title + (available ? ": data available" : ": no data in this profile");
    return mark;
  }
  const coverageCount = row => coverageSections.filter(([, available]) => available(row)).length;
  const profilesByCoverage = [...data.profiles].sort((a, b) => coverageCount(b) - coverageCount(a) ||
    entityName(a).localeCompare(entityName(b), "en-AU"));
  const withFinancial = profilesByCoverage.filter(row => row.firmographics.financial_facts?.length);
  const withSites = profilesByCoverage.filter(row => row.establishments.length);
  const withLicences = profilesByCoverage.filter(row => row.licences.length);
  const pairs = sourcePairs(data.profiles, true);
  const params = new URLSearchParams(window.location.search);
  const selectedPair = pairs.find(pair => pair.a === params.get("source_a") && pair.b === params.get("source_b"));
  const references = entries => [...new Set(entries)].map(id => data.evidence[id]).filter(Boolean);
  function provenance(ids) {
    const rows = references(ids);
    if (!rows.length) return null;
    const sources = [...new Set(rows.map(claim => claim.source_id))];
    return disclosure("Source evidence · " + rows.length, () => [
      table("provenance", ["Source", "Data row", "Column", "Raw value", "Mapped value", "Observed", "Level", "Field confidence"],
        rows.map(claim => [source(claim.source_id), claim.source_row_ordinal, claim.source_fields.join(" + "),
          claim.raw_value, claim.value, claim.observed_at?.slice(0, 10), claim.derivation_level, score(claim.confidence?.field_confidence)])),
      ...sources.map(id => siteLink("Open " + source(id) + " mapping", "mapping", { source: id })),
    ]);
  }
  const claimIds = item => [item?.provenance?.observation_id, ...(item?.supporting_observations ?? [])].filter(Boolean);
  function claimRows(items) {
    return items.flatMap(([key, value]) => asList(value).map(item => disclosure(
      field(key) + " · " + (item.label ?? item.value),
      facts([["Source", source(item.provenance?.source_id)], ["Value confidence", score(item.value_confidence)],
        ["Derivation", item.provenance?.derivation_level], ["Observed", item.provenance?.observed_at?.slice(0, 10)]], "evidence-facts"),
      item.crosswalk_review_status ? note(item.crosswalk_review_status) : null,
      provenance(claimIds(item)))));
  }
  function finance(row) {
    const financial = row.firmographics.financial_facts ?? [];
    if (!financial.length) return null;
    const periods = [...new Set(financial.map(item => item.period))].sort();
    const measures = ["total_income", "taxable_income", "tax_payable"].filter(measure => financial.some(item => item.measure === measure));
    return section("Published financial history",
      table("ATO reporting periods", ["Measure", ...periods], measures.map(measure => [field(measure),
        ...periods.map(period => {
          const item = financial.find(claim => claim.period === period && claim.measure === measure);
          return item ? dollars.format(item.value) : "Unreported";
        })])),
      row.firmographics.derived?.length ? table("calculated year-on-year changes", ["Change", "Periods", "Value", "Level"],
        row.firmographics.derived.map(item => [field(item.measure), item.from_period + " → " + item.to_period,
          share.format(item.value), item.derivation_level])) : null,
      provenance(financial.flatMap(claimIds)));
  }
  function places(title, items, collapsed = false) {
    if (!items.length) return null;
    const details = () => items.map(item => {
      const headline = item.fields.number ? "Licence " + item.fields.number
        : item.fields["address.full"] || item.fields["address.locality"] || label(item.role);
      return disclosure(headline + " · " + source(item.source_id),
        facts(Object.entries(item.fields).map(([key, value]) => [field(key), asList(value).join(", ")]), "evidence-facts"),
        provenance(item.observation_ids));
    });
    return collapsed ? section(title, disclosure(count(items.length) + " establishment records",
      () => [note("Source records, not a verified count of distinct active offices."), ...details()]))
      : section(title, ...details());
  }
  function contactLocations(row) {
    if (!row.locations?.length) return null;
    return section("Registered and contact addresses", disclosure(count(row.locations.length) + " address records",
      () => row.locations.map(location => disclosure(label(location.scope) + " · " + source(location.source_id),
        note("Published address evidence; this does not establish an operating site."),
        ...claimRows(Object.entries(location.fields))))));
  }
  function experiments() {
    show("Part 4 experiments", "Source deletion and change detection", [
      section("Remove one source", table("source deletion results", ["Removed source", "Affected profiles", "Fields removed", "Values changed"],
        Object.entries(data.deletion).map(([id, row]) => [source(id), row.profiles_affected ?? 0, row.fields_removed, row.fields_value_changed]))),
      section("Financial source dependence", copy("A second independent source corroborates the financial facts in " +
        overview.financial_corruption.profiles_where_a_second_source_would_expose_it + " of " +
        overview.financial_corruption.profiles_with_financial_facts + " sampled profiles with financial facts. An incorrect sole-source value could win unopposed. This is a dependence assessment; no financial-value corruption replay was executed.")),
      section("Detected changes", table("change counts", ["Signal", "Events"],
        Object.entries(overview.changes.by_type).map(([key, value]) => [label(key), value])),
        note("The QBCC diff tracks licence numbers found in the earlier sample. ATO growth compares reporting periods."),
        disclosure("QBCC licence change examples", table("licence changes", ["Licence", "Field", "Before", "After"],
          data.events.filter(event => event.event_type === "FIELD_CHANGED").map(event =>
            [event.entity_ref.split(":").at(-1), field(event.field), event.old, event.new])))),
    ]);
  }
  return {
    number: 4, title: "Company profiles",
    intro: "Browse the 50 profiles from the latest replay. Expand a claim to see the publisher row and the mapping that produced it.",
    metrics: [
      ["Profiles", overview.profiles, "Sampled multi-source entities"],
      ["With financial history", withFinancial.length, "ATO reporting-period facts"],
      ["With establishment records", withSites.length, "Operating sites and licensed premises"],
      ["With licence records", withLicences.length, "Regulator-issued licences"],
    ],
    visualization: () => identityChart(Object.keys(data.sources), pairs, source, ui, { profiles: true }),
    overview: [
      callout("Follow a real example", "Compare reporting years, browse employment sites, or trace a Victorian permit to its premises.",
        el("div", "source-links", ...overview.featured.map(row => siteLink({
          financial: "WGA’s ATO history", establishments: "The Personnel Group’s sites", licence: "Chinese Association’s permit",
        }[row.theme], "profiles", { entity: row.id })))),
      callout("Source dependence", count(overview.changes.events_total) + " detected changes across the QBCC snapshot comparison and ATO reporting periods.",
        (() => {
          const button = el("button", "text-button", "Open the experiments ↗");
          button.type = "button";
          button.addEventListener("click", experiments);
          return button;
        })()),
    ],
    heading: "Explore the profiles", description: "Most checked sections first. ✓ Data available · — No data in this profile. Checks indicate coverage, not verification. Open a company to inspect its evidence.",
    anchor: "company-profiles",
    filter: selectedPair && (row => row.sources.includes(selectedPair.a) && row.sources.includes(selectedPair.b)),
    filterNotice: selectedPair && (() => el("aside", "pair-filter",
      el("strong", "", source(selectedPair.a) + " ↔ " + source(selectedPair.b) + " · " + selectedPair.companies + " sampled profiles"),
      siteLink("Clear pair filter", "profiles"))),
    views: [{ id: "profiles", label: "All profiles", rows: profilesByCoverage }, { id: "financial", label: "Financial", rows: withFinancial },
      { id: "establishments", label: "Establishments", rows: withSites }, { id: "licences", label: "Licences", rows: withLicences }],
    tableClass: "profile-coverage",
    columns: ["Business / sources", ...coverageSections.map(([title]) => title)],
    row: row => [entityName(row), el("span", "profile-context",
      row.fields["entity.abn"]?.value ? el("span", "", "ABN " + row.fields["entity.abn"].value) : null,
      el("span", "", row.sources.map(source).join(" · ")),
      row.link_review_findings?.length || row.conflicts.length ? el("span", "coverage-review",
        [row.link_review_findings?.length ? row.link_review_findings.length + (row.link_review_findings.length === 1 ? " flagged link" : " flagged links") : null,
          row.conflicts.length ? row.conflicts.length + (row.conflicts.length === 1 ? " field conflict" : " field conflicts") : null].filter(Boolean).join(" · ")) : null),
      ...coverageSections.map(([title, available]) => coverageMark(title, !!available(row)))],
    search: row => [row.fields["entity.acn"]?.value, ...row.establishments.flatMap(item => Object.values(item.fields)),
      ...row.licences.flatMap(item => Object.values(item.fields))],
    match: (row, params) => row.entity_key === params.get("entity"),
    detail: row => {
      const firmographics = companyDetails(row);
      return ["Company profile · Latest replay", entityName(row), [
        note(row.sources.map(source).join(" · ") + " · " + human(Object.values(row.mapping_approval_state)[0])),
        facts([["ABN", row.fields["entity.abn"]?.value], ["ACN", row.fields["entity.acn"]?.value],
          ["Status", row.fields["entity.status"]?.value], ["Established", row.firmographics.date_established?.value]], "detail-meta"),
        section("Core fields", ...claimRows(Object.entries(row.fields))),
        row.link_review_findings?.length ? section("Link review findings",
          note("This proposed profile includes " + row.link_review_findings.length + " links flagged by review. Its combined attributes need rechecking."),
          ...[...new Set(row.link_review_findings.map(item => item.note))].map(copy)) : null,
        finance(row), contactLocations(row), places("Establishments and licensed premises", row.establishments, true), places("Licences", row.licences),
        firmographics.length ? section("Company details and firmographics", ...claimRows(firmographics)) : null,
        Object.keys(row.firmographics.sector_tags ?? {}).length ? section("Charity purpose",
          ...Object.entries(row.firmographics.sector_tags).map(([scheme, tags]) => copy(label(scheme) + " · " + tags.join(", ")))) : null,
        row.registration_events.length ? section("Registration events", table("registration events", ["Scope", "Date", "Source"],
          row.registration_events.map(item => [label(item.scope), item.value, source(item.provenance?.source_id)]))) : null,
        row.relationships.length ? section("Relationships", disclosure("Show " + row.relationships.length + " relationship records", () => [
          table("profile relationships", ["Relationship", "Publisher record", "Target", "Basis"],
            row.relationships.map(item => [label(item.type), item.record, item.programme_label ?? item.to ?? item.to_entity, item.basis])),
        ])) : null,
        row.conflicts.length ? section("Conflicts", table("competing values", ["Field", "Selected", "Alternatives"],
          row.conflicts.map(item => [field(item.field), item.winner, item.losers.join(", ")]))) : null,
        row.contact_count ? note(count(row.contact_count) + " business contact points in the replay. The demo shows aggregate contact counts.") : null,
      ]];
    },
  };
}
