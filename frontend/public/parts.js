import { demoView, rawMappingView, rawIdentityView, rawProfilesView, runBanner } from "./raw-demo.js";
import { assignmentView, architectureView } from "./assignment.js";

const number = new Intl.NumberFormat("en-AU");
const count = value => number.format(value);
const score = value => Number.isFinite(value) ? value.toFixed(4) : "—";
const readable = value => String(value ?? "—").replaceAll("_", " ").replaceAll(".", " ");
const pageSize = 25;

const sourceNames = {
  acnc_charities: "ACNC", asic_companies: "ASIC Companies", asic_credit_licensees: "ASIC Credit",
  ato_tax_transparency: "ATO", dewr_employment_providers: "DEWR", qbcc_licensees: "QBCC",
  vic_liquor: "Victorian Liquor", qld_suitable_operators: "Queensland SOR",
};
const sourceName = id => sourceNames[id] ?? readable(id);
const recordSource = id => id ? sourceName(id.split("::")[0]) : "Candidate unavailable";
const ruleNames = {
  abn_equal: "Same ABN", acn_equal: "Same ACN", abn_contains_acn_and_name: "ACN and name",
  registered_name_exact: "Company name", registered_name_exact_and_location: "Name and location",
  abn_equal_but_person_vs_company: "Holder mismatch", name_exact_no_company_signal: "Name only",
};
const ruleName = id => ruleNames[id] ?? readable(id);
const fieldLabels = {
  "entity.legal_name": "Legal name", "entity.trading_name": "Trading name", "entity.abn": "ABN",
  "entity.acn": "ACN", "entity.entity_type": "Entity type", "entity.date_registered": "Registration date",
  "entity.status": "Status", "entity.website": "Website", "address.full": "Street address",
};
const fieldName = id => fieldLabels[id] ?? readable(id?.replace(/^address\./, ""));
const fieldValue = value => value == null || value === "" ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
const firstName = (record, key) => record?.names?.[0] || key?.split("::").slice(1).join("::") || "Source record";
const readerName = reader => reader.format === "delimited"
  ? `${reader.archive_member ? "ZIP · " : ""}${reader.delimiter === "\t" ? "TSV" : "CSV"}`
  : reader.format === "json" && reader.record_path === "result.records" ? "CKAN JSON" : reader.format.toUpperCase();
const stageLabels = {
  INSPECTED: "Source inspected", PROPOSED: "Mapping proposed", VALIDATED: "Held-out validation",
  CRITIQUED: "Semantic review", REVISING: "Revision started", PENDING_REVIEW: "Approval requested",
};

function stageName(stage) {
  const [name, round] = stage.split(/_v(\d+)$/);
  const label = stageLabels[name] ?? readable(name);
  return round === undefined ? label : `${label} · Round ${Number(round) + 1}`;
}

function components({ element: el, sourceTable, link, siteLink, disclosure, jsonPreview }) {
  const note = text => el("p", "detail-note", text);
  const copy = text => el("p", "detail-copy", text);
  const section = (title, ...body) => el("section", "detail-section", el("h3", "", title), ...body);
  const facts = (items, className = "detail-meta") => el("dl", className,
    ...items.map(([label, value]) => el("div", "", el("dt", "", label), el("dd", "", fieldValue(value)))));
  const table = (resource, headers, rows) => sourceTable({ resource, headers, rows: rows.map(row => row.map(fieldValue)) });
  const action = (text, handler) => {
    const button = el("button", "text-button", text, el("span", "external", "↗"));
    button.type = "button";
    button.lastChild.setAttribute("aria-hidden", "true");
    button.addEventListener("click", handler);
    return button;
  };
  const callout = (title, body, control) => el("section", "overview-block",
    el("div", "block-title", el("h2", "", title)), el("p", "pilot-result", body), control);
  return { el, note, copy, section, facts, table, disclosure, action, callout, link, siteLink, jsonPreview };
}

function mappingView(data, ui, show) {
  const { note, copy, section, facts, table, disclosure, action, callout, link, siteLink, jsonPreview, el } = ui;
  const observations = data.mappings.reduce((total, row) => total + (row.extraction?.canonical_observations ?? 0), 0);
  const contextual = data.mappings.flatMap(row => row.context ? [row.context] : []);
  const contextTotals = contextual.reduce((totals, { validation }) => ({
    matched: totals.matched + validation.matched, expected: totals.expected + validation.expected,
    rows: totals.rows + validation.rows, unsupported: totals.unsupported + validation.unsupported,
  }), { matched: 0, expected: 0, rows: 0, unsupported: 0 });
  const { baseline, replay } = data.benchmark;
  const variantName = key => key === "approved_baseline" ? "Established mapping" : readable(key.replaceAll("-", " "));

  function contextSection(row) {
    if (!row.context) return null;
    const { mapping, trace, examples, validation } = row.context;
    const added = mapping.config.fields.filter(rule => rule.target.startsWith("context."));
    return section("Supplemental profile mapping",
      copy("These agent-generated rules retain facts at the source record’s own level, including reporting years, company registrations, licences, and service sites."),
      facts([["Rules added", added.length], ["Expected claims recovered", count(validation.matched) + "/" + count(validation.expected)],
        ["Fresh publisher rows", validation.rows], ["Unsupported claims", validation.unsupported],
        ["Agent proposals", trace.proposals], ["Review status", "Awaiting human sign-off"]], "evidence-facts"),
      disclosure("Added source columns and rules", ...added.map(rule => disclosure(
        rule.source_paths[0] + " → " + rule.target,
        copy(rule.rationale),
        note("Field confidence " + score(rule.confidence)),
        rule.when ? note("Apply when " + rule.when.source_path + " " + readable(rule.when.op) + " " + rule.when.values.join(", ")) : null,
        table("mapping transforms", ["Operation", "Arguments"], rule.steps.map(step => [step.op, step.args])),
      ))),
      disclosure("Checked claims by field", table("supplemental checks",
        ["Target", "Expected", "Recovered", "Unsupported"], Object.entries(validation.fields).map(([field, values]) =>
          [field, values.expected ?? 0, values.matched ?? 0, values.unsupported ?? 0]))),
      disclosure("Inspect supplemental observations", () => [
        table("supplemental observations", ["Source column", "Raw value", "Target", "Value", "Field confidence"],
          examples.map(item => [item.sourceFields.join(" + "), item.raw, item.field, item.value,
            score(item.confidence?.field_confidence)])),
      ]),
      disclosure("Exact supplemental configuration", () => [
        note("Agent run " + mapping.run_id + " · " + mapping.model),
        note("Config SHA-256 · " + mapping.config_digest),
        jsonPreview(mapping.config),
      ]));
  }

  function detail(row) {
    const { config } = row.mapping;
    const { reader, record_id: key } = config;
    const { validation, trace, extraction } = row;
    const { stages, evaluations } = trace;
    const duration = Math.round((Date.parse(trace.finished) - Date.parse(trace.started)) / 1000);
    const publisherDocs = {
      asic_companies: ["ASIC company dataset dictionary", "https://data.gov.au/data/dataset/7b8656f9-606d-4337-af29-66b89b2eeefb/resource/9430b6b2-b28c-4b1a-a58a-a88b54912853/download/company-dataset-help-file.pdf"],
      acnc_charities: ["ACNC register guidance", "https://www.acnc.gov.au/charity/about-acnc-charity-register/information-charity-register"],
    }[row.id];
    const unmapped = row.context?.mapping.config.unmapped ?? config.unmapped;
    const rules = config.fields.map(rule => disclosure(
      rule.source_paths.join(" + ") + " → " + fieldName(rule.target),
      copy(rule.rationale),
      facts([["Mapping confidence", score(rule.confidence)], ["Claim scope", readable(rule.claim_scope)],
        ["Transforms", rule.steps.map(step => readable(step.op)).join(" → ") || "Direct mapping"]], "evidence-facts"),
      rule.when ? note("Apply when " + rule.when.source_path + " " + readable(rule.when.op) + " " + rule.when.values.join(", ")) : null,
    ));
    const selected = Object.entries(validation.variants);
    return [
      note(row.publisher),
      facts([["Replay mapping", variantName(row.variant)], ["Reader", readerName(reader)],
        ["Observations", extraction ? count(extraction.canonical_observations) : "Held back from replay"],
        ["Human approval", "Pending"]]),
      el("div", "source-links", row.datasetId ? siteLink("Discovery evidence", "discovery", { dataset: row.datasetId }) : null,
        row.url ? link("Publisher resource", row.url) : null, publisherDocs ? link(...publisherDocs) : null),
      contextSection(row),
      section("Held-out publisher checks",
        copy(validation.matched + "/" + validation.expected + " expected claims recovered across " +
          validation.rows + " unseen source rows. " + validation.unsupported + " unsupported claims."),
        facts([["Exact row-field checks", validation.exact + "/" + validation.checks],
          ["Scope findings", Object.values(validation.scope ?? {}).reduce((sum, value) => sum + value, 0)],
          ["Earlier evaluation rows excluded", validation.excludedEarlier],
          ["Onboarding rows excluded", validation.excluded]], "evidence-facts"),
        validation.roles ? disclosure("Holder names by publisher role", table("holder name coverage",
          ["Source role", "Checked rows", "Names emitted"],
          Object.entries(validation.roles).map(([role, value]) => [readable(role), value.rows, value.names_mapped]))) : null,
        disclosure("Checks by field", table("held-out checks by field", ["Field", "Expected", "Matched", "Unsupported"],
          Object.entries(validation.fields).map(([field, value]) =>
            [fieldName(field), value.expected_claims, value.matched_claims, value.unexpected_claims]))),
        selected.length > 1 ? disclosure("Compare mapping variants", table("mapping variants",
          ["Variant", "Expected recovered", "Unsupported", "Exact checks"], selected.map(([name, value]) =>
            [variantName(name) + (name === row.variant ? " · shown above" : ""),
              value.matched + "/" + value.expected, value.unsupported, value.exact + "/" + value.checks]))) : null),
      row.observations.length ? section("Raw values → canonical observations",
        disclosure("Inspect " + row.observations.length + " observed claims", () => [
          note("Examples from the frozen replay. Each line is one field claim."),
          table("observation examples", ["Source column", "Raw value", "Canonical field", "Canonical value", "Scope", "Transforms", "Field confidence"],
            row.observations.map(obs => [obs.sourceFields.join(" + "), obs.raw, fieldName(obs.field), obs.value,
              readable(obs.scope), obs.transform.map(readable).join(" → "), score(obs.confidence?.field_confidence)])),
        ])) : null,
      section("Reader and rules", copy(config.grain_rationale),
        facts([["Record grain", readable(config.record_grain)], ["Resource", row.resource],
          ["Record key", key.source_paths?.join(" + ") || readable(key.strategy)],
          ...(reader.archive_member ? [["Archive member", reader.archive_member]] : []),
          ...(reader.sheet ? [["Worksheet", reader.sheet], ["Header rows skipped", reader.skip_rows]] : []),
          ...(reader.record_path ? [["Record path", reader.record_path]] : []),
          ...(reader.delimiter ? [["Delimiter", reader.delimiter === "\t" ? "Tab" : reader.delimiter === "," ? "Comma" : reader.delimiter]] : []),
        ], "evidence-facts"),
        disclosure("Field rules · " + rules.length, ...rules),
        config.constants.length ? disclosure("Mapping defaults", table("mapping defaults", ["Field", "Value", "Rationale"],
          config.constants.map(rule => [fieldName(rule.target), rule.value, rule.rationale]))) : null,
        unmapped.length ? disclosure("Unmapped columns · " + unmapped.length,
          table("unmapped columns", ["Column", "Reason"], unmapped.map(field => [field.source_path, field.reason]))) : null,
        disclosure("Exact replay configuration", () => [
          note("SHA-256 · " + row.mapping.config_digest), jsonPreview(config),
        ])),
      section("Onboarding trace",
        facts([["Run ID", row.mapping.run_id], ["Model", row.mapping.model], ["Duration", Number.isFinite(duration) ? duration + " s" : "—"],
          ["Checkpoints", stages.length], ["Tool calls", trace.calls]], "evidence-facts"),
        trace.sameDigest ? null : note("The original onboarding checkpoint and the replay configuration have different hashes. The holdout results above follow the replay configuration."),
        disclosure("Open checkpoints and critic rounds",
          table("onboarding checkpoints", ["Checkpoint", "Time since start"], stages.map(({ stage, at }) =>
            [stageName(stage), "+" + Math.round((Date.parse(at) - Date.parse(trace.started)) / 1000) + " s"])),
          evaluations.length ? table("proposal evaluations", ["Round", "Held-out errors", "Critic errors", "Critic doubts"],
            evaluations.map(result => [result.round + 1, result.holdout_errors, result.critic_wrong, result.critic_doubtful])) : null)),
    ];
  }

  return {
    number: 2, title: "Schema inference & mapping",
    intro: "Follow raw source columns through reader settings, mapping rules, and checks on unseen publisher rows.",
    metrics: [
      ["Replayed sources", Object.keys(data.benchmark.sources).length, "Two additional sources held back"],
      ["Canonical observations", count(observations), "Across the frozen benchmark"],
      ["Expected claims recovered", count(replay.matched_claims) + "/" + count(replay.expected_claims), count(replay.rows) + " held-out rows"],
      ["Human approvals", "0/" + data.mappings.length, "Drafts available for review"],
    ],
    overview: [
      callout("Semantic checks", "Unsupported claims fell from " + baseline.unexpected_claims + " to " + replay.unexpected_claims +
        ". Missing registration scopes fell from " + baseline.scope_findings + " to " + replay.scope_findings + ".",
        action("View evaluation method", () => show("Part 2 method", "How the mappings were checked", [
          copy("The controller inspects source formats, proposes a mapping, runs deterministic checks, and records a semantic critic's feedback."),
          copy("The final evaluation uses unseen publisher rows outside onboarding and the earlier selection sample. It compares the extracted fields with publisher-informed expected claims."),
          copy("The reviewer can inspect the exact configuration and its digest before signing off."),
        ]))),
      callout("Profile context", count(contextTotals.matched) + "/" + count(contextTotals.expected) +
        " expected claims recovered across " + count(contextTotals.rows) + " fresh rows from " +
        contextual.length + " sources. " + count(contextTotals.unsupported) + " unsupported claims."),
    ],
    heading: "Explore the mappings", description: "Open a source to inspect its held-out checks, raw values, and mapping rules.",
    views: [{ id: "mappings", label: "Source mappings", rows: data.mappings }],
    columns: ["Source", "Reader", "Observations"],
    row: row => [row.title, row.extraction ? row.publisher + (row.context ? " · Supplemental mapping" : "") : row.publisher + " · Held back",
      readerName(row.mapping.config.reader), row.extraction ? count(row.extraction.canonical_observations) : "Held back"],
    match: (row, params) => row.id === params.get("source"),
    detail: row => [row.extraction ? "Benchmark mapping" : "Held-back mapping", row.title, detail(row)],
  };
}
function identityView(data, ui, show) {
  const { note, copy, section, facts, table, disclosure, action, callout, siteLink, link, jsonPreview, el } = ui;
  const { summary, auditSummary, benchmark } = data;
  const scores = benchmark.paired_mapping_replay.replay_score_distribution;
  const profileKeys = new Set(data.profileKeys);

  function sides(row, kind) {
    if (kind === "review") return [[row.a, row.record_a], [row.b, row.record_b]];
    if (kind === "unlinked") return [[row.source_record, row.record], [row.best_candidate, row.candidate]];
    return [[row.source_a_record, row.a, row.aView], [row.source_b_record, row.b, row.bView]];
  }

  function recordCard(key, record, claims, index) {
    const sourceId = record?.source_id ?? key?.split("::")[0];
    const abn = record?.abn?.[0];
    return el("section", "pair-card",
      el("p", "field-label", "Record " + (index === 0 ? "A" : "B") + " · " + sourceName(sourceId)),
      el("h3", "pair-name", firstName(record, key)),
      facts([["Record grain", readable(record?.grain)], ["ABN", record?.abn?.join(", ")],
        ["ACN", record?.acn?.join(", ")], ["Postcode", record?.postcode?.join(", ")]], "evidence-facts"),
      note(key ?? "Candidate unavailable"),
      el("div", "source-links", data.sources[sourceId] ? siteLink("Source mapping", "mapping", { source: sourceId }) : null,
        /^\d{11}$/.test(abn) ? link("ABN Lookup", "https://abr.business.gov.au/ABN/View/" + abn) : null),
      claims ? disclosure("Canonical claims", table("canonical claims", ["Field", "Values"],
        Object.entries(claims).map(([field, values]) => [fieldName(field), values.join(" · ")]))) : null);
  }

  function detail(row, kind) {
    if (kind === "relationships") return ["Relationship", "Holds licence", [
      facts([["Resolved entity", row.entity], ["Licence record", row.record], ["Source", recordSource(row.record)]], "evidence-facts"),
      copy("This edge connects a resolved entity to a licence record."),
      profileKeys.has(row.entity) ? siteLink("Open company profile", "profiles", { entity: row.entity }) : null,
    ]];
    const pair = sides(row, kind);
    const value = row.confidence ?? row.score ?? row.best_score;
    const state = kind === "unlinked" ? readable(row.candidate_decision) : kind === "review" ? "Referred for review" : "Proposed link";
    const signals = (row.evidence ?? []).filter(evidence => evidence.type !== "EVIDENCE_SCORE_COMPONENTS");
    const contributions = (row.evidence ?? []).find(evidence => evidence.type === "EVIDENCE_SCORE_COMPONENTS")?.value;
    const body = [
      facts([["Decision", state], ["Rule", ruleName(row.rule)], ["Policy score", score(value)], ["Link threshold", score(summary.threshold)]]),
      el("div", "source-links",
        row.link_id ? siteLink("Pair permalink", "identity", { pair: row.link_id, view: kind }) : null,
        profileKeys.has(row.canonical_entity_key) ? siteLink("Open company profile", "profiles", { entity: row.canonical_entity_key }) : null),
      row.reason ? note("Decision reason · " + readable(row.reason).toLowerCase()) : null,
      row.next_action ? note("Reviewer action · " + row.next_action) : null,
      el("div", "pair-grid", ...pair.map(([key, record, claims], index) => recordCard(key, record, claims, index))),
    ];
    if (row.proxy) {
      const evidence = row.adjudication;
      body.push(section("Audit evidence",
        facts([["Sample pair", row.auditIndex], ["Original AI verdict", readable(row.proxy.label)],
          ["Human verdict", row.humanLabel || "Pending"], ["Sample strata", row.sampleStrata?.join(" + ")]], "evidence-facts"),
        copy(row.proxy.reason),
        evidence ? disclosure("Registry adjudication · " + evidence.adjudicated_label,
          copy(evidence.rationale), note("AI-assisted registry review · ABN " + evidence.abn + " · ACN " + evidence.acn),
          el("div", "source-links", ...evidence.sources.map((url, index) => link("Registry evidence " + (index + 1), url)))) : null,
        row.spotCheck ? disclosure("Publisher cross-check", copy(row.spotCheck.finding),
          link("Open publisher evidence", row.spotCheck.source)) : null,
        row.registry?.both_reported_legal_names_found_for_one_observed_identifier ?
          note("The frozen ASIC snapshot records both reported names under one observed identifier.") : null));
    }
    body.push(section("Match evidence",
      signals.length ? table("match evidence", ["Signal", "Evidence"], signals.map(e =>
        [readable(e.type).toLowerCase(), e.value ?? ([e.a, e.b].filter(Boolean).join(" ↔ ") || "Present")])) : null,
      contributions ? disclosure("How the score was built", table("policy score contributions", ["Component", "Points"],
        Object.entries(contributions).map(([key, points]) =>
          [readable(key), (key !== "rule_base" && points > 0 ? "+" : "") + score(points)])),
        note("The policy score ranks evidence and applies the link threshold. It is a rule score on a 0–1 scale.")) : null,
      row.contradictions?.length ? disclosure("Conflicting identifiers",
        table("contradictions", ["Type", "Record A", "Record B"], row.contradictions.map(e => [readable(e.type), e.a, e.b]))) : null,
      disclosure("Decision record JSON", () => [jsonPreview(row)])));
    return [kind === "audit" ? "Link audit" : state, firstName(pair[0][1], pair[0][0]), body];
  }

  const reviewMethod = () => show("Part 3 evaluation", "How the links were checked", [
    section("Blinded link sample",
      copy("The original AI proxy reviewed 50 links. The registry checks preserve the original verdicts and document separate adjudications."),
      facts([["ASIC snapshot rows scanned", count(data.registrySummary.asic_rows_scanned)],
        ["Both names under one identifier", data.registrySummary.pairs_with_both_reported_legal_names_found_for_one_observed_identifier + "/50"]], "evidence-facts")),
    section("Independent identifier coverage",
      copy("The coverage check independently sampled 450 source rows and then checked shared identifiers against the full ASIC snapshot."),
      table("independent coverage", ["Source", "Sample", "Shared identifier", "Linked", "Referred"],
        Object.entries(data.coverage.sources).map(([id, source]) => [sourceName(id), source.independent_rows_sampled,
          source.rows_sharing_identifier_with_full_asic, source["evidence-v3"].identifier_overlap_rows_linked,
          source["evidence-v3"].identifier_overlap_rows_with_review_pairs]))),
  ]);
  const download = el("a", "text-button", "Download link audit CSV", el("span", "external", "↓"));
  download.href = "/link-audit.csv";
  download.download = "";

  return {
    number: 3, title: "Entity identification",
    intro: "Compare records side by side and see which identifiers, names, and locations support each proposed link.",
    metrics: [
      ["Proposed links", count(summary.links), summary.policy_version + " · threshold " + summary.threshold],
      ["Multi-source entities", count(summary.entities_in_multiple_sources), "Across the six-source replay"],
      ["Distinct link scores", scores.distinct_scores, "Largest score tie · " + scores.largest_tie],
      ["Referred pairs", count(summary.review_pairs), "Identifier and holder mismatch"],
    ],
    overview: [
      callout("Blinded link audit", auditSummary.labels.CORRECT + "/" + auditSummary.sampled +
        " confirmed by the original proxy. Registry evidence supported the two disputed links. Human verdicts remain pending.", download),
      callout("Coverage and referrals", count(summary.unlinked_queue) +
        " unlinked records have candidate evidence. A separate ASIC lookup linked 180 of 182 sampled rows with shared identifiers.",
        action("View coverage checks", reviewMethod)),
    ],
    heading: "Explore match decisions", description: "Open a pair to compare both records, their score, and any audit findings.",
    views: [
      { id: "links", label: "Proposed links", rows: data.links },
      { id: "audit", label: "Link audit", rows: data.audit },
      { id: "review", label: "Review queue", rows: data.review },
      { id: "unlinked", label: "Unlinked", rows: data.unlinked },
      { id: "relationships", label: "Licence edges", rows: data.relationships },
    ],
    columns: kind => kind === "relationships" ? ["Licence record", "Entity key", "Type"] :
      [kind === "unlinked" ? "Source record" : "Record pair", "Rule", kind === "audit" ? "Proxy verdict" : "Score"],
    row: (row, kind) => {
      if (kind === "relationships") return [row.record, recordSource(row.record), row.entity, "Holds licence"];
      const [[a, left], [b, right]] = sides(row, kind);
      return [firstName(left, a), recordSource(a) + " ↔ " + recordSource(b) + " · " + firstName(right, b),
        ruleName(row.rule), kind === "audit" ? readable(row.proxy.label).toLowerCase() :
          score(row.confidence ?? row.score ?? row.best_score)];
    },
    search: row => [row.source_a_record, row.source_b_record, row.source_record, row.best_candidate,
      row.canonical_entity_key, row.entity, row.rule, row.reason, ...[row.a, row.b, row.record_a, row.record_b, row.record, row.candidate]
        .flatMap(record => [...(record?.names ?? []), ...(record?.abn ?? []), ...(record?.acn ?? [])])],
    match: (row, params) => row.link_id === params.get("pair"),
    initialSearch: params => params.get("entity") || "",
    detail,
  };
}
function profileView(data, ui, show) {
  const { note, copy, section, facts, table, disclosure, action, callout, link, siteLink, jsonPreview, el } = ui;
  const conflicts = data.profiles.filter(row => row.conflicts.length);
  const title = row => row.fields["entity.legal_name"]?.value ?? row.entity_key;
  const context = row => data.context[row.entity_key];
  const money = new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 });
  const registryDate = new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeZone: "Australia/Sydney" })
    .format(new Date(data.registryCheckedAt));
  const scopeLabels = { entity: "Company activity", group: "Group activity", brand: "Operating brand", project: "Project activity" };
  const asic = data.deletion.asic_companies;
  const experiment = data.corruption;

  function industry(row) {
    const { business, charity, licences } = context(row);
    if (business) return business.industry;
    if (charity) return "Registered charity";
    if (licences.some(licence => /restaurant and cafe/i.test(licence.category))) return "Restaurants and cafés";
    if (licences.length) return "Licensed venue";
    return null;
  }

  function locationText(location) {
    const fields = location.fields;
    const street = fields["address.full"]?.value;
    const locality = fields["address.locality"]?.value;
    const region = [fields["address.state"]?.value, fields["address.postcode"]?.value].filter(Boolean).join(" ");
    return [street, [locality, region].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  }

  function publicLocations(row) {
    const locations = context(row).business?.locations ?? [];
    return [
      ...locations,
      ...row.locations.filter(location => location.scope !== "licensed_premises").map(location => ({
        label: readable(location.scope),
        address: locationText(location),
        url: data.sources[location.source_record.split("::")[0]]?.catalogue,
      })).filter(location => location.address && !locations.some(other =>
        other.address.toLowerCase().replace(/\W/g, "") === location.address.toLowerCase().replace(/\W/g, ""))),
    ];
  }

  const withActivity = data.profiles.filter(row => industry(row));
  const withAddress = data.profiles.filter(row => publicLocations(row).length ||
    row.locations.some(location => location.fields["address.full"]?.value));

  function activity(row) {
    const { business, charity, licences } = context(row);
    if (!industry(row)) return null;
    const activityList = business?.activities ?? charity?.purposes ?? [...new Set(licences.map(item => item.category).filter(Boolean))];
    const venueNames = [...new Set(licences.map(item => item.venue).filter(Boolean))];
    const basis = business ? [scopeLabels[business.scope], business.name].join(" · ") :
      charity ? "ACNC Charity Register" : "Venue classification · Victorian liquor register";
    return el("section", "company-overview",
      el("p", "field-label", basis),
      el("h3", "", industry(row)),
      business ? copy(business.summary) : !charity && venueNames.length ?
        copy("The licensing snapshot identifies " + venueNames.join(" and ") + ".") : null,
      activityList.length ? el("ul", "activity-list", ...activityList.map(item => el("li", "", item))) : null,
      el("div", "source-links",
        business ? link(business.label, business.url) : null,
        business?.website && business.website !== business.url ? link("Website or contact page", business.website) : null,
        business?.identityUrl ? link("Entity reference", business.identityUrl) : null,
        !business && charity ? link("ACNC register dataset", data.sources.acnc_charities.catalogue) : null,
        !business && !charity ? link("Victorian licence dataset", data.sources.vic_liquor.catalogue) : null));
  }

  function registryDetails(row) {
    const registry = context(row).registry;
    if (!registry) return null;
    const businessNames = [...new Set(registry.businessNames)];
    const tradingNames = [...new Set(registry.tradingNames)];
    return section("Business registration",
      facts([["ABR entity name", registry.name], ["ABN status", registry.status],
        ["Entity type", registry.type], ["GST registration", registry.gst]].filter(([, value]) => value), "evidence-facts"),
      businessNames.length ? el("div", "profile-registry-names", el("p", "field-label", "Registered business names"),
        el("ul", "activity-list", ...businessNames.map(name => el("li", "", name)))) : null,
      tradingNames.length ? disclosure("Historical trading names", el("ul", "signal-list",
        ...tradingNames.map(name => el("li", "", name)))) : null,
      el("div", "source-links", link("ABN Lookup record", registry.url),
        el("p", "detail-note", "Checked " + registryDate)));
  }

  function mappedEvidence(source, claims) {
    if (!claims?.length) return null;
    return disclosure("Mapped source evidence", () => [
      table("supplemental mapping provenance", ["Data row", "Source column", "Raw value", "Mapped field", "Value", "Field confidence"],
        claims.map(item => [item.source_row_ordinal, item.source_fields.join(" + "), item.raw_value, item.field, item.value,
          score(item.confidence?.field_confidence)])),
      siteLink("Open the Part 2 source mapping", "mapping", { source }),
    ]);
  }

  function companyLocations(row) {
    const { registry, licences } = context(row);
    const published = publicLocations(row);
    const venueAddresses = new Map(row.locations.filter(location => location.scope === "licensed_premises")
      .map(location => [location.source_record.split("::")[1], locationText(location)]));
    if (!registry?.mainLocation && !published.length && !licences.length) return null;
    const siteCards = published.map(item => el("article", "company-location",
      el("p", "field-label", item.label), el("strong", "", item.address),
      item.url ? link("Location source", item.url) : null));
    if (registry?.mainLocation) {
      siteCards.push(el("article", "company-location",
        el("p", "field-label", "ABR main business location"), el("strong", "", registry.mainLocation),
        link("State and postcode source", registry.url)));
    }
    return section("Locations and addresses",
      siteCards.length ? el("div", "company-location-grid", ...siteCards) : null,
      licences.length ? el("div", "company-licences",
        el("h4", "", "Licensed premises"),
        note("Premises and licence details come from the saved Victorian register snapshot."),
        ...licences.map(item => disclosure(item.venue || "Licence " + item.id,
          venueAddresses.get(item.id) ? copy(venueAddresses.get(item.id)) : null,
          facts([["Licence number", item.id], ["Licensee", item.licensee], ["Licence type", item.category],
            ["Council", item.council], ["Region", item.region], ["Patron capacity", item.capacity],
            ["Trading hours", item.hours]].filter(([, value]) => value != null), "evidence-facts"),
          mappedEvidence("vic_liquor", item.mappingEvidence))),
        link("Victorian licence dataset", data.sources.vic_liquor.catalogue)) : null);
  }

  function taxDisclosure(row) {
    const { tax } = context(row);
    if (!tax.length) return null;
    const latest = tax[0];
    const amount = value => value == null ? "Unreported" : money.format(value);
    return section("Public tax disclosures",
      note("ATO Corporate Tax Transparency · " + latest.year + " income year"),
      facts([["Reported total income", amount(latest.totalIncome)], ["Taxable income", amount(latest.taxableIncome)],
        ["Tax payable", amount(latest.taxPayable)]], "detail-meta tax-metrics"),
      disclosure("Reporting years and source names", table("public tax disclosures",
        ["Income year", "Name as reported", "Total income", "Taxable income", "Tax payable"],
        tax.map(item => [item.year, item.name, amount(item.totalIncome), amount(item.taxableIncome), amount(item.taxPayable)]))),
      mappedEvidence("ato_tax_transparency", latest.mappingEvidence),
      link("ATO source data", data.sources.ato_tax_transparency.catalogue));
  }

  function charityDetails(row) {
    const charity = context(row).charity;
    if (!charity) return null;
    return section("Charity register",
      facts([["Registered name", charity.name], ["Reporting size", charity.size], ["Established", charity.established],
        ["Declared purposes", charity.purposes.join(", ")], ["Declared operating regions", charity.regions.join(", ")]]
        .filter(([, value]) => value), "evidence-facts"),
      mappedEvidence("acnc_charities", charity.mappingEvidence),
      link("ACNC source data", data.sources.acnc_charities.catalogue));
  }

  function companyRegistration(row) {
    const records = context(row).companyRegistration ?? [];
    if (!records.length) return null;
    const labels = {
      "context.company.share_class": "Company class code",
      "context.company.share_subclass": "Company subclass code",
      "context.company.former_registration_jurisdiction": "Previous registration jurisdiction",
      "context.company.deregistered_on": "Deregistration date",
    };
    return section("ASIC company register",
      ...records.map(item => disclosure(item.name + (item.currentName ? " · Current name row" : " · Register row"),
        facts(item.mappingEvidence.map(claim => [labels[claim.field], claim.value]), "evidence-facts"),
        mappedEvidence("asic_companies", item.mappingEvidence))),
      link("ASIC source data", data.sources.asic_companies.catalogue));
  }

  function impact() {
    show("Part 4 experiment", "How source changes affect profiles", [
      copy("Each deletion removes one source and rebuilds the same 50 sampled profiles."),
      table("source deletion results", ["Source removed", "Profiles affected", "Fields removed", "Values changed",
        "Confidence changes", "Provenance changes"], Object.entries(data.deletion).map(([id, result]) => [
        sourceName(id), result.profiles_affected, result.fields_removed, result.fields_value_changed,
        result.fields_confidence_changed, result.fields_provenance_changed,
      ])),
      section("Registration date corruption", copy("Shifting ASIC dates by one year changed " +
        experiment.profiles_value_changed + " company registration dates. The separate registration scopes were preserved.")),
      section("Legal name corruption", copy("Replacing ASIC legal names produced " + data.nameCorruption.corrupted_winners +
        " corrupted provisional winners. " + data.nameCorruption.corrupted_winners_requiring_review +
        " required review and " + data.nameCorruption.corrupted_winners_above_0_75 + " exceeded 0.75 confidence.")),
    ]);
  }

  function fieldDetails(key, field) {
    return (Array.isArray(field) ? field : [field]).map(entry => {
      const provenance = entry.provenance ?? {};
      const parts = entry.confidence_parts ?? {};
      const losing = entry.resolution?.losing_values ?? [];
      const related = new Set([provenance.observation_id, ...(entry.supporting_observations ?? []),
        ...losing.flatMap(item => item.observation_ids)]);
      const observations = [...related].map(id => data.observations[id]).filter(Boolean);
      const meter = el("meter", "confidence-meter");
      meter.min = 0;
      meter.max = 1;
      meter.value = entry.value_confidence ?? 0;
      meter.setAttribute("aria-label", "Value confidence " + score(entry.value_confidence));
      const label = el("span", "field-summary",
        el("span", "field-label", fieldName(key)),
        el("strong", "", fieldValue(entry.value),
          entry.resolution?.decision === "review_required" ? el("span", "review-tag", "Review required") : null),
        el("span", "field-score", meter, score(entry.value_confidence)));
      return disclosure(label, () => [
        facts([["Mapping confidence", score(parts.field_confidence)], ["Source reliability", score(parts.source_reliability)],
          ["Link confidence", score(parts.link_confidence)], ["Agreeing sources", parts.agreeing_sources?.map(sourceName).join(", ")],
          ["Strongest competing support", score(parts.strongest_competing_support)],
          ["Claim scope", readable(entry.scope ?? provenance.claim_scope)]], "evidence-facts"),
        el("p", "detail-copy", "Winning source · " + sourceName(provenance.source_id)),
        note("Source record · " + (provenance.source_record_id ?? "—") + " · columns " +
          (provenance.source_fields?.join(", ") || "Mapping default")),
        note("Observation " + (provenance.observation_id ?? "—") + " · " + (provenance.observed_at ?? "—")),
        provenance.source_id ? siteLink("Open winning source mapping", "mapping", { source: provenance.source_id }) : null,
        entry.resolution ? copy("Decision · " + entry.resolution.why_this_won + ".") : null,
        losing.length ? table("alternative values", ["Alternative", "Sources", "Observation IDs"],
          losing.map(item => [item.value, item.sources.map(sourceName).join(", "), item.observation_ids.join(", ")])) : null,
        observations.length ? disclosure("Supporting source observations", table("supporting observations",
          ["Source", "Source columns", "Raw value", "Canonical value", "Transformation", "Observation ID"],
          observations.map(obs => [sourceName(obs.source), obs.sourceFields.join(" + "), obs.raw, obs.value,
            obs.transform.map(readable).join(" → "), obs.id]))) : null,
      ]);
    });
  }

  function detail(row) {
    const { fields, locations, registration_events: registrations, historical_names: history, mapping_defaults: defaults } = row;
    const pairs = data.linksByEntity[row.entity_key] ?? [];
    const abn = fields["entity.abn"]?.value;
    return [
      activity(row),
      facts([["ABN", abn], ["ACN", fields["entity.acn"]?.value],
        ["Entity type", context(row).registry?.type],
        ["Linked registers", row.sources.map(sourceName).join(", ")]]),
      el("div", "source-links",
        pairs.length ? siteLink("See " + pairs.length + " supporting " + (pairs.length === 1 ? "link" : "links"),
          "identity", { entity: row.entity_key }) : null,
        /^\d{11}$/.test(abn) ? link("Open ABN Lookup", "https://abr.business.gov.au/ABN/View/" + abn) : null,
        siteLink("Profile permalink", "profiles", { entity: row.entity_key })),
      companyLocations(row),
      taxDisclosure(row),
      charityDetails(row),
      companyRegistration(row),
      registryDetails(row),
      row.conflicts.length ? section("Recorded conflicts",
        table("profile conflicts", ["Field", "Provisional winner", "Alternatives"],
          row.conflicts.map(conflict => [fieldName(conflict.field), conflict.winner, conflict.losers.join(" · ")]))) : null,
      section("Canonical profile fields",
        note("Expand a field to see its source, confidence components, and supporting values."),
        ...Object.entries(fields).sort(([a], [b]) => Number(b.startsWith("entity.")) - Number(a.startsWith("entity.")))
          .flatMap(([key, entry]) => fieldDetails(key, entry))),
      registrations.length ? section("Registration events", ...registrations.flatMap(entry =>
        fieldDetails(readable(entry.scope), entry))) : null,
      history.length ? section("Former legal names", ...history.flatMap(entry => fieldDetails("Former name", entry))) : null,
      locations.length ? section("Source-scoped locations", ...locations.map(location =>
        disclosure(readable(location.scope) + " · " + recordSource(location.source_record), note(location.source_record),
          ...Object.entries(location.fields).flatMap(([key, entry]) => fieldDetails(key, entry))))) : null,
      Object.keys(defaults).length ? section("Mapping defaults",
        disclosure("View contextual defaults", table("mapping defaults", ["Field", "Default", "Source"],
          Object.entries(defaults).flatMap(([key, values]) => values.map(item =>
            [fieldName(key), item.value, sourceName(item.source_id)]))))) : null,
      section("Linked source records", ...row.member_records.map(record =>
        el("div", "member-record", note(record),
          siteLink("Open " + recordSource(record) + " mapping", "mapping", { source: record.split("::")[0] }))),
        disclosure("Profile JSON", () => [jsonPreview(row)])),
    ];
  }

  return {
    number: 4, title: "Company profiles",
    intro: "See what each business does, where it operates, and which sources support the profile.",
    metrics: [
      ["Profiles in sample", data.profiles.length, "From " + count(data.linkedCount) + " multi-source entities"],
      ["With business activity", withActivity.length, "Company, brand, project, or register evidence"],
      ["With street or premises details", withAddress.length, "Source-attributed addresses"],
      ["With public tax disclosures", data.profiles.filter(row => context(row).tax.length).length, "ATO reporting-year amounts"],
    ],
    overview: [
      callout("Company evidence", "Profiles pair linked register records with ABN Lookup and publicly attributed business context. Every office, premises, and group activity is labelled by its source."),
      callout("Source impact", "Removing ASIC affected " + asic.profiles_affected + " profiles and removed " + asic.fields_removed + " core fields.",
        action("View source impact", impact)),
    ],
    heading: "Explore the company profiles", description: "Search by company, brand, activity, location, or identifier.",
    views: [{ id: "profiles", label: "All profiles", rows: data.profiles }, { id: "addresses", label: "With addresses", rows: withAddress },
      { id: "conflicts", label: "With conflicts", rows: conflicts }],
    columns: ["Company", "Business activity", "ABR location"],
    row: row => [title(row), [context(row).business?.name, "ABN " + context(row).abn].filter(Boolean).join(" · "),
      industry(row) ?? "—", context(row).registry?.mainLocation ?? "—"],
    search: row => [row.entity_key, row.fields["entity.abn"]?.value, row.fields["entity.acn"]?.value,
      ...row.sources.map(sourceName), ...row.historical_names.map(entry => entry.value),
      ...(context(row).business?.activities ?? []), ...(context(row).registry?.businessNames ?? []),
      ...(context(row).charity?.purposes ?? []), ...row.locations.map(locationText),
      ...publicLocations(row).map(location => location.address)],
    match: (row, params) => row.entity_key === params.get("entity"),
    detail: row => ["Company profile", title(row), detail(row)],
  };
}

function writeupView(data, root, ui) {
  const { el, siteLink, note, copy, section, facts, table, disclosure } = ui;
  const { usage, checks, mapping, identity, profiles, auditSummary } = data;
  const money = value => "$" + value.toFixed(2);
  const cards = [
    ["discovery", "Discovery", "50 datasets shortlisted. All 20 datasets in the follow-up sample were confirmed in an AI-assisted review of publisher records."],
    ["mapping", "Mapping", count(mapping.replay.matched_claims) + " expected claims recovered on " + count(mapping.replay.rows) + " held-out rows. Eight mapping drafts await human sign-off."],
    ["identity", "Identity", count(identity.links) + " proposed links across " + count(identity.entities_in_multiple_sources) + " multi-source entities. The original audit confirmed " + auditSummary.labels.CORRECT + " of " + auditSummary.sampled + " links."],
    ["profiles", "Profiles", count(profiles.scoped_claims) + " field and context entries across " + profiles.profiles + " profiles, with " + profiles.provenance_errors.length + " provenance errors."],
  ];
  const artifacts = Object.entries(checks.files).map(([file, result]) => [file, result.identical ? "Matched" : "Changed", result.replay_sha256]);
  root.replaceChildren(
    el("section", "overview",
      el("div", "page-intro", el("p", "eyebrow", "Part 5 of 5"), el("h1", "", "Write-up"),
        el("p", "intro", "Results, review status, and reproducibility across the four stages.")),
      el("div", "overview-grid writeup-grid", ...cards.map(([part, title, summary]) =>
        el("section", "overview-block", el("div", "block-title", el("h2", "", title)),
          el("p", "pilot-result", summary), siteLink("Explore " + title.toLowerCase(), part))))),
    el("section", "catalogue writeup-notes",
      el("h2", "", "Replay and review"),
      section("Human review", copy("The mapping drafts and both audits are ready for human review. The site preserves the recorded AI-assisted and registry verdicts alongside the review status.")),
      section("Measured API usage",
        facts([["Provider meter", money(usage.provider_meter_delta_usd) + " of " + money(usage.budget_usd)],
          ["Token-based estimate", money(usage.estimated_usd)], ["Tokens", count(usage.final_tokens)],
          ["Successful model calls", usage.successful_calls], ["Failed attempts", usage.failed_attempts]])),
      section("Reproducibility",
        note("A clean replay reproduced " + checks.files_verified + " saved artifacts byte for byte."),
        disclosure("Verified artifact hashes", table("artifact hashes", ["Artifact", "Replay", "SHA-256"], artifacts)))),
  );
}
function renderExplorer(config, root, { element: el, beginDetail }) {
  const params = new URLSearchParams(window.location.search);
  const requestedView = config.views.find(candidate => candidate.id === params.get("view"));
  const matchingView = config.match && config.views.find(candidate => candidate.rows.some(row => config.match(row, params)));
  let view = requestedView?.rows.some(row => config.match?.(row, params)) ? requestedView
    : matchingView ?? requestedView ?? config.views[0];
  let page = 0;
  let filtered = [];
  const tbody = el("tbody");
  const headings = el("tr");
  const feedback = el("p", "list-count");
  feedback.setAttribute("aria-live", "polite");
  const empty = el("p", "empty", "No entries match your search.");
  const search = el("input");
  search.type = "search";
  search.value = config.initialSearch?.(params) ?? "";
  search.placeholder = "Search entries";
  search.setAttribute("aria-label", `Search ${config.heading.toLowerCase().replace(/^explore the /, "")}`);
  const pager = el("div", "list-pager");
  const back = el("button", "", "← Previous page");
  const forward = el("button", "", "Next page →");
  back.type = forward.type = "button";
  const controls = el("div", "view-nav results-nav");
  const filterNotice = config.filterNotice && el("div");
  controls.setAttribute("aria-label", "Result lists");
  for (const candidate of config.views) {
    const button = el("button", "", candidate.label, el("span", "", count(candidate.rows.length)));
    button.type = "button";
    button.setAttribute("aria-pressed", String(candidate === view));
    button.addEventListener("click", () => {
      view = candidate;
      page = 0;
      for (const tab of controls.children) tab.setAttribute("aria-pressed", String(tab === button));
      render();
    });
    controls.append(button);
  }

  function open(index) {
    const [label, title, content] = config.detail(filtered[index], view.id);
    beginDetail(label, title, content, { index, total: filtered.length, move: open });
  }

  function render() {
    const query = search.value.trim().toLocaleLowerCase("en-AU");
    filtered = view.rows.filter(row => {
      if (config.filter && !config.filter(row, view.id)) return false;
      const parts = [...config.row(row, view.id), ...(config.search?.(row) ?? [])];
      return parts.map(part => part instanceof Node ? part.textContent : part).join(" ").toLocaleLowerCase("en-AU").includes(query);
    });
    const labels = typeof config.columns === "function" ? config.columns(view.id) : config.columns;
    headings.replaceChildren(...[...labels, "Details"].map((label, i) => {
      const th = el("th", i === labels.length ? "detail-column" : config.tableClass ? (i ? "coverage-cell" : "name-cell") : i === 1 ? "format-cell" : "",
        i === labels.length ? el("span", "sr-only", label) : label);
      th.scope = "col";
      return th;
    }));
    const start = page * pageSize;
    const current = filtered.slice(start, start + pageSize);
    tbody.replaceChildren(...current.map((row, index) => {
      const [title, description, ...cells] = config.row(row, view.id);
      const button = el("button", "dataset-name", title);
      button.type = "button";
      button.addEventListener("click", () => open(start + index));
      const arrow = el("td", "chevron-cell", "→");
      arrow.setAttribute("aria-hidden", "true");
      const tr = el("tr", "", el("td", "name-cell", button, el("span", "dataset-publisher", description)),
        ...cells.map((cell, i) => el("td", config.tableClass ? "coverage-cell" : i === 0 ? "format-cell" : "result-cell", cell)), arrow);
      tr.addEventListener("click", event => { if (event.target !== button) button.click(); });
      return tr;
    }));
    feedback.textContent = filtered.length
      ? `Showing ${count(start + 1)}–${count(start + current.length)} of ${count(filtered.length)} entries`
      : "Showing 0 entries";
    empty.hidden = filtered.length > 0;
    pager.hidden = filtered.length <= pageSize;
    back.disabled = page === 0;
    forward.disabled = start + pageSize >= filtered.length;
    if (filterNotice) {
      const notice = config.filterNotice(view.id);
      filterNotice.replaceChildren(...(notice ? [notice] : []));
    }
  }

  const tableScroll = el("div", "table-scroll", el("table", "dataset-table results-table " + (config.tableClass ?? ""),
    el("caption", "sr-only", config.heading), el("thead", "", headings), tbody));
  if (config.tableClass) {
    tableScroll.tabIndex = 0;
    tableScroll.setAttribute("role", "region");
    tableScroll.setAttribute("aria-label", "Profile coverage table. Scroll horizontally to compare all sections.");
  }
  function changePage(offset) {
    const next = page + offset;
    if (next < 0 || next * pageSize >= filtered.length) return;
    page = next;
    render();
    tableScroll.scrollIntoView?.({ block: "start" });
  }
  back.addEventListener("click", () => changePage(-1));
  forward.addEventListener("click", () => changePage(1));
  search.addEventListener("input", () => { page = 0; render(); });
  pager.append(back, forward);
  config.overview[1]?.classList.add("pilot-block");
  const context = el("div", "overview-grid", ...config.overview);

  const overview = el("section", config.visualization ? "overview with-analysis" : "overview", el("div", "page-intro",
    el("p", "eyebrow", `Part ${config.number} of 5`), el("h1", "", config.title), el("p", "intro", config.intro)),
    config.banner,
    el("div", "summary", ...config.metrics.map(([label, value, description]) => el("div", "metric",
      el("p", "metric-label", label), el("strong", "metric-value", String(value)), el("p", "metric-note", description)))),
    config.visualization ? null : context);
  const catalogue = el("section", "catalogue results-catalogue",
    el("div", "section-heading", el("div", "", el("h2", "", config.heading), el("p", "", config.description))),
    el("div", "toolbar", controls, el("label", "search", el("span", "search-icon"), search)),
    filterNotice || null, tableScroll,
    empty, el("div", "result-bottom", feedback, pager));
  if (config.anchor) catalogue.id = config.anchor;
  if (config.visualization) root.replaceChildren(overview, config.visualization(), context, catalogue);
  else root.replaceChildren(overview, catalogue);
  render();
  if (config.anchor && window.location.hash === "#" + config.anchor) catalogue.scrollIntoView();
  const requested = config.match ? filtered.findIndex(row => config.match(row, params)) : -1;
  if (requested >= 0) {
    page = Math.floor(requested / pageSize);
    render();
    open(requested);
  }
}

export async function mountPart(part, root, helpers) {
  const progress = helpers.element("p", "part-load", "Loading results…");
  progress.setAttribute("role", "status");
  root.replaceChildren(progress);
  const snapshot = async name => {
    const response = await fetch(`/${name}.json`);
    if (!response.ok) throw new Error(`Snapshot unavailable for ${name}`);
    return response.json();
  };
  const ui = components(helpers);
  const params = new URLSearchParams(window.location.search);
  if (part === "onboarding") {
    const { mountOnboarding } = await import("./onboarding.js");
    mountOnboarding(await snapshot("onboarding"), root);
    return;
  }
  if (part === "demo") {
    demoView(await snapshot("raw-demo"), root, ui);
    return;
  }
  if (part === "architecture") {
    const [core, onboarding] = await Promise.all([snapshot("raw-demo"), snapshot("onboarding")]);
    architectureView(core, root, ui, onboarding);
    return;
  }
  let archived = params.get("run") === "benchmark" || (!params.has("run") && part === "identity" && params.has("pair"));
  const currentViews = { mapping: rawMappingView, identity: rawIdentityView, profiles: rawProfilesView };
  let config;
  if (!archived) {
    if (part === "write-up") {
      assignmentView(await snapshot("assignment-writeup"), root, ui);
      return;
    }
    config = currentViews[part](await snapshot("raw-" + part), ui, helpers.beginDetail);
    const key = part === "profiles" ? "entity" : part === "mapping" ? "source" : "link";
    if (!params.has("run") && params.has(key) &&
        !config.views.some(view => view.rows.some(row => config.match(row, params)))) archived = true;
  }
  helpers.setArchivedRun(archived);
  if (!archived) {
    renderExplorer({ ...config, banner: runBanner(ui, part) }, root, helpers);
    return;
  }
  const data = await snapshot(part);
  if (part === "write-up") {
    writeupView(data, root, ui);
    root.querySelector(".overview").append(runBanner(ui, part, true));
    return;
  }
  const views = { mapping: mappingView, identity: identityView, profiles: profileView };
  config = views[part](data, ui, helpers.beginDetail);
  renderExplorer({ ...config, banner: runBanner(ui, part, true) }, root, helpers);
}
