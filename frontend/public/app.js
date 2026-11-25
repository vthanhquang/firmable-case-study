const $ = id => document.getElementById(id);
const number = new Intl.NumberFormat("en-AU");
const points = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 3 });
const publisherRules = {
  business_evidence: "Qualifying business evidence",
  valid_identifier: "Checksum-valid identifiers",
  corporate_name: "Corporate name patterns",
  business_name: "Populated business names",
  identifier_and_name: "Valid identifier and name on the same row",
};
const date = new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeZone: "UTC" });
const verdictClass = { Yes: "positive", No: "negative", Uncertain: "uncertain" };
const sections = {
  demo: [0, "Demo"],
  discovery: [1, "Discovery & triage"],
  mapping: [2, "Schema inference & mapping"],
  onboarding: [0, "Dataset onboarding"],
  identity: [3, "Entity identification"],
  profiles: [4, "Company profiles"],
  "write-up": [5, "Write-up"],
  architecture: [6, "Architecture"],
};
const archiveParts = new Set(["mapping", "identity", "profiles", "write-up"]);
let archivedRun = false;
const detail = $("detail");
let data;
let view = "audit";
let visibleRows = [];
let detailNavigation = null;

function element(tag, className, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  for (const child of children) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

function link(label, url, className = "source-link") {
  const target = new URL(url);
  if (!["http:", "https:"].includes(target.protocol)) throw new Error("Invalid source link");
  const anchor = element("a", className, label, element("span", "external", "↗"));
  anchor.lastChild.setAttribute("aria-hidden", "true");
  anchor.href = target.href;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

function siteLink(label, part, parameters = {}) {
  const inherited = archivedRun && archiveParts.has(part) ? { run: "benchmark" } : {};
  const query = new URLSearchParams({ part, ...inherited, ...parameters });
  const anchor = element("a", "source-link", label, element("span", "external", "→"));
  anchor.lastChild.setAttribute("aria-hidden", "true");
  anchor.href = `/?${query}`;
  return anchor;
}

function disclosure(label, ...body) {
  const details = element("details", "evidence-disclosure", element("summary", "", label));
  const panel = element("div", "disclosure-body");
  details.append(panel);
  if (typeof body[0] === "function") {
    const load = () => {
      if (!details.open) return;
      panel.append(...body[0]());
      details.removeEventListener("toggle", load);
    };
    details.addEventListener("toggle", load);
  } else {
    panel.append(...body.filter(item => item != null));
  }
  return details;
}

function jsonPreview(value) {
  const preview = element("pre", "evidence-code", JSON.stringify(value, null, 2));
  preview.tabIndex = 0;
  preview.setAttribute("aria-label", "Scrollable JSON excerpt");
  return preview;
}

function activatePart() {
  const params = new URLSearchParams(window.location.search);
  const slug = params.get("part");
  const part = Object.hasOwn(sections, slug) ? slug : params.has("dataset") ? "discovery" : "demo";
  for (const tab of document.querySelectorAll("[data-part]")) {
    if (tab.dataset.part === part) {
      tab.setAttribute("aria-current", "page");
      tab.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    else tab.removeAttribute("aria-current");
  }
  $("discovery").hidden = part !== "discovery";
  $("part-content").hidden = part === "discovery";
  document.title = `${sections[part][1]} · Firmable Case Study`;
  return part;
}

function setArchivedRun(value) {
  archivedRun = value;
  if (!value) return;
  for (const tab of document.querySelectorAll("[data-part]")) {
    const part = tab.dataset.part;
    if (archiveParts.has(part)) tab.href = "/?" + new URLSearchParams({ part, run: "benchmark" });
  }
}

function showOverview() {
  const { verdicts } = data;
  const stats = [
    [number.format(data.catalogueCount), "Catalogue records", "Deduplicated CKAN candidates"],
    [data.shortlistCount, "Datasets shortlisted", `${data.distinctScores} distinct ranking scores`],
    [`${verdicts.Yes}/${data.auditCount}`, "Confirmed in audit", data.humanVerdicts === data.auditCount ? "Human review verified" : "Reopened publisher records"],
    [`${Math.round(100 * verdicts.No / data.auditCount)}%`, "Observed false positives", `Among ${data.auditCount} sampled datasets`],
  ];
  $("summary").replaceChildren(...stats.map(([value, label, note]) => element(
    "div", "metric", element("p", "metric-label", label), element("strong", "metric-value", String(value)),
    element("p", "metric-note", note),
  )));
  $("summary").removeAttribute("aria-busy");
  $("audit-review-status").textContent = data.humanVerdicts === data.auditCount ? "Human review verified" : "AI-assisted review";
  const bar = element("div", "audit-bar");
  bar.setAttribute("aria-hidden", "true");
  const legend = element("div", "audit-legend");
  for (const [verdict, count] of Object.entries(verdicts)) {
    const segment = element("span", verdictClass[verdict]);
    segment.style.flexGrow = count;
    bar.append(segment);
    legend.append(element("span", "legend-item", element("i", verdictClass[verdict]),
      element("strong", "", String(count)), verdict.toLowerCase()));
  }
  $("outcome").replaceChildren(bar, legend,
    element("p", "summary-note", `${data.humanVerdicts}/${data.auditCount} human verdicts recorded. Results describe the audited sample.`));
  $("ranking-result").textContent = `The run read publisher records for ${data.resourceTables} datasets. Open an audited dataset to see the saved API response, keyword matches, and up to 50 source rows.`;
  $("audit-tab-count").textContent = data.auditCount;
  $("all-tab-count").textContent = data.shortlistCount;
  if (data.date) $("snapshot-date").textContent = `Catalogue snapshot · ${date.format(new Date(data.date))}`;
}

function pill(verdict) {
  return element("span", `verdict ${verdictClass[verdict]}`, element("i", ""), verdict);
}

function renderRows() {
  if (!data) return;
  const needle = $("search").value.trim().toLocaleLowerCase("en-AU");
  const selectedVerdict = $("verdict").value;
  const auditOnly = view === "audit";
  const eligible = auditOnly ? data.datasets.filter(row => row.audit) : data.datasets;
  visibleRows = eligible.filter(row => {
    const haystack = [row.title, row.publisher, String(row.rank), ...row.format].join(" ").toLocaleLowerCase("en-AU");
    return (!needle || haystack.includes(needle)) && (!auditOnly || !selectedVerdict || row.audit.verdict === selectedVerdict);
  });
  $("verdict-field").hidden = !auditOnly;
  $("verdict-column").hidden = !auditOnly;
  $("datasets").replaceChildren(...visibleRows.map(row => {
    const open = element("button", "dataset-name", row.title);
    open.type = "button";
    open.addEventListener("click", () => showDataset(row));
    const tr = element("tr", "",
      element("td", "rank-cell", String(row.rank).padStart(2, "0")),
      element("td", "name-cell", open, element("span", "dataset-publisher", row.publisher)),
      element("td", "format-cell", row.format.join(" · ")),
      auditOnly ? element("td", "result-cell", pill(row.audit.verdict)) : null,
      element("td", "points-cell", points.format(row.points)),
      element("td", "chevron-cell", "→"),
    );
    tr.lastChild.setAttribute("aria-hidden", "true");
    tr.addEventListener("click", event => { if (event.target !== open) open.click(); });
    return tr;
  }));
  $("empty").hidden = visibleRows.length > 0;
  $("list-count").textContent = `Showing ${visibleRows.length} of ${eligible.length} datasets`;
}

function beginDetail(label, title, content, navigation = null) {
  $("detail-label").textContent = label;
  const heading = element("h2", "detail-title", title);
  heading.id = "detail-title";
  $("detail-content").replaceChildren(heading, ...content.filter(item => item != null));
  detailNavigation = navigation;
  $("drawer-footer").hidden = !navigation;
  if (navigation) {
    $("prev-dataset").disabled = navigation.index === 0;
    $("next-dataset").disabled = navigation.index + 1 >= navigation.total;
    $("detail-position").textContent = `${navigation.index + 1} / ${navigation.total}`;
  }
  $("detail-content").scrollTop = 0;
  if (!detail.open) detail.showModal();
}

function sourceTable(preview) {
  const thead = element("thead", "", element("tr", "", ...preview.headers.map(header => {
    const th = element("th", "", header);
    th.scope = "col";
    return th;
  })));
  const tbody = element("tbody", "", ...preview.rows.map(row => element("tr", "",
    ...row.map(value => element("td", "", value == null || value === "" ? "—" : String(value))))));
  const caption = element("caption", "sr-only", `Source data from ${preview.resource}`);
  const scroller = element("div", "preview-scroll", element("table", "preview-table", caption, thead, tbody));
  scroller.tabIndex = 0;
  scroller.setAttribute("role", "region");
  scroller.setAttribute("aria-label", "Scrollable source preview");
  return scroller;
}

const discoveryRoutes = {
  public_datastore_records: "CKAN DataStore",
  publisher_file_preview: "Publisher file",
  frozen_publisher_snapshot: "Frozen publisher snapshot",
};
const discoveryRoute = value => discoveryRoutes[value] || value?.replaceAll("_", " ") || "Publisher records";
const readableRule = value => value.replaceAll("_", " ").replace(/\(([+-]?\d+(?:\.\d+)?)\)$/, " $1");

function highlight(value, hits) {
  const boundaries = [...new Set([0, value.length, ...hits.flatMap(hit => [hit.start, hit.end])])].sort((a, b) => a - b);
  return boundaries.slice(0, -1).map((start, i) => {
    const end = boundaries[i + 1];
    const active = hits.filter(hit => hit.start < end && hit.end > start);
    const text = value.slice(start, end);
    if (!active.length) return text;
    const mark = element("mark", active.some(hit => hit.weight < 0) ? "keyword penalty" : "keyword", text);
    mark.title = [...new Set(active.map(hit => readableRule(hit.rule) + " " + (hit.weight > 0 ? "+" : "") + hit.weight))].join(" · ");
    return mark;
  });
}

function descriptionHits(text, inputs) {
  const normalized = text.toLowerCase();
  const hits = [];
  for (const input of inputs) {
    for (const hit of input.hits) {
      const term = input.text.slice(hit.start, hit.end).trim().toLowerCase();
      if (!term) continue;
      let start = normalized.indexOf(term);
      while (start >= 0) {
        const end = start + term.length;
        const before = normalized[start - 1] ?? "";
        const after = normalized[end] ?? "";
        if (!/[\p{L}\p{N}]/u.test(before) && !/[\p{L}\p{N}]/u.test(after)) {
          hits.push({ ...hit, start, end });
        }
        start = normalized.indexOf(term, end);
      }
    }
  }
  return hits;
}

function discoveryFacts(items) {
  return element("dl", "detail-meta", ...items.map(([label, value]) =>
    element("div", "", element("dt", "", label), element("dd", "", String(value ?? "—")))));
}

function evidenceSection(title, ...body) {
  return element("section", "detail-section", element("h3", "", title), ...body);
}

function rankEvidence(row) {
  const { metadata, evidence, catalogueCategory } = row;
  const matched = metadata.inputs.filter(input => input.hits.length);
  const rankFields = element("div", "ranking-fields", ...(matched.length ? matched : metadata.inputs).map(input =>
    element("div", "ranking-input", element("span", "field-label", input.label),
      element("p", "", ...highlight(input.text, input.hits)))));
  const signals = element("ul", "signal-list chips", ...metadata.rules.map(rule =>
    element("li", rule.includes("(-") ? "signal-negative" : "", readableRule(rule))));
  return [
    evidenceSection("Deterministic ranking",
      discoveryFacts([["Final ranking points", points.format(row.points) + " / " + points.format(data.rankingMaxPoints)],
        ["Publisher record points", points.format(row.publisherPoints) + " / " + data.publisherMaxPoints],
        ["Catalogue category points", "+" + points.format(catalogueCategory.points)],
        ["Business-signal rows", evidence.business_rows + "/" + evidence.sampled_rows]]),
      element("p", "detail-copy", element("strong", "", catalogueCategory.label),
        catalogueCategory.signals.length ? " · " + catalogueCategory.signals.map(readableRule).join(" · ") : null),
      disclosure("Publisher scoring breakdown", () => [
        sourceTable({ resource: "publisher scoring breakdown", headers: ["Rule", "Matching rows", "Points earned", "Maximum"], rows:
          row.publisherBreakdown.map(rule => [publisherRules[rule.rule],
            rule.support ? rule.matching_rows + " / " + rule.support : rule.matching_rows,
            points.format(rule.points), rule.max_points]) }),
        element("p", "detail-note", "The starting points are awarded once when qualifying evidence appears. The remaining rules award points in proportion to row coverage, using a minimum denominator of 10."),
      ]),
      disclosure("Catalogue inputs and matched rules", rankFields,
        metadata.rules.length ? signals : element("p", "detail-note", "No catalogue rules matched."),
        element("p", "detail-note", "These keyword weights score catalogue retrieval. The final rank adds the points from the one catalogue category shown above."))),
    evidenceSection("Publisher row evidence",
      element("p", "detail-copy", row.reason),
      sourceTable({ resource: "ranking evidence", headers: ["Source column", "Signal", "Matching rows"],
        rows: evidence.fields.map(field => [field.field, readableRule(field.signal), field.count]) }),
      link("Open ranked source resource", evidence.url)),
  ];
}

function responseField(name, value) {
  const count = Array.isArray(value) ? " · " + value.length : "";
  return disclosure(name + count, () => [jsonPreview(value)]);
}

function publisherCapture(row) {
  const { catalogue, source, datastore } = row.capture;
  const result = catalogue.body.result;
  const description = result.notes.trim();
  const context = description ? element("p", "publisher-description",
    ...highlight(description, descriptionHits(description, row.metadata.inputs))) : null;
  const retrieved = date.format(new Date(data.capturedAt));
  const previews = [
    disclosure("Publisher description", context ?? element("p", "detail-note", "This listing has no description."),
      context ? element("p", "detail-note", "Highlights repeat terms from the scored catalogue inputs where they also appear in the publisher description. The description provides context.") : null),
    disclosure("CKAN package_show response · HTTP " + catalogue.httpStatus, () => [
      element("p", "detail-note", "Saved response excerpt · " + retrieved),
      discoveryFacts([["success", catalogue.body.success], ["result.id", result.id], ["result.license_id", result.license_id]]),
      responseField("result.notes", result.notes),
      responseField("result.organization", result.organization),
      responseField("result.resources", result.resources),
      disclosure("JSON excerpt", () => [jsonPreview(catalogue.body)]),
      link("Open catalogue API request", catalogue.url),
    ]),
  ];
  if (datastore) previews.push(disclosure("CKAN datastore_search response · HTTP " + datastore.httpStatus, () => [
    element("p", "detail-note", "Saved response excerpt with up to 50 records. Contact and address columns are omitted."),
    discoveryFacts([["success", datastore.body.success], ["result.resource_id", datastore.body.result.resource_id],
      ["result.total", datastore.body.result.total]]),
    responseField("result.fields", datastore.body.result.fields),
    responseField("result.records", datastore.body.result.records),
    disclosure("JSON excerpt", () => [jsonPreview(datastore.body)]),
    link("Open DataStore API request", datastore.url),
  ]));
  previews.push(disclosure("Source records · " + source.rows.length + " rows", () => [
    element("p", "detail-note", discoveryRoute(source.route) + " · " + (source.resource || "Matched audit resource") +
      " · first " + source.rows.length + " records, up to 20 columns. Contact and address columns are omitted."),
    sourceTable(source), link("Open publisher resource", source.url),
  ]));
  return evidenceSection("Saved publisher evidence", ...previews);
}

function showDataset(row) {
  const review = row.audit;
  const content = [
    element("p", "detail-publisher", row.publisher),
    discoveryFacts([["Formats", row.format.join(", ")], ["Licence", row.licence || "Unknown"], ["Catalogue query", row.query || "Unavailable"]]),
    element("div", "source-links", link("Catalogue listing", row.url),
      siteLink("Dataset permalink", "discovery", { dataset: row.id })),
  ];
  if (review) {
    content.push(element("section", "detail-section audit-detail",
      element("div", "detail-section-title", element("h3", "", review.human ? "Human audit verdict" : "Audit verdict"), pill(review.verdict)),
      review.human ? element("p", "detail-note", "Human review verified · " + review.human.reviewer + " · recorded " + date.format(new Date(review.human.recordedAt))) : null,
      review.human ? element("p", "detail-copy", review.human.note) : null,
      element("p", "detail-copy", review.note),
      element("p", "detail-note", "Initial evidence check: " + review.reviewer + " · " + review.rows + " rows reopened via " + discoveryRoute(review.route)),
      review.originalRank === row.rank ? null : element("p", "detail-note", "Original audit rank " + review.originalRank),
      link("Open audit evidence", review.url)));
  }
  const [ranking, rows] = rankEvidence(row);
  content.push(ranking);
  if (row.capture) content.push(publisherCapture(row));
  content.push(rows);
  const index = visibleRows.findIndex(item => item.id === row.id);
  beginDetail("Shortlist rank " + row.rank, row.title, content, index < 0 ? null : {
    index, total: visibleRows.length, move: next => showDataset(visibleRows[next]),
  });
}

function showMethod() {
  const category = data.catalogueCategoryPoints;
  beginDetail("Part 1 method", "How the shortlist was ranked", [
    evidenceSection("1. Catalogue rules",
      element("p", "detail-copy", "Deduplicate CKAN results. Apply positive and negative rules to the frozen title, publisher, resource names and formats.")),
    evidenceSection("2. Publisher records",
      element("p", "detail-copy", "Preview up to three resources. Shortlist eligibility requires business signals in at least two rows."),
      sourceTable({ resource: "publisher point rubric", headers: ["Publisher record rule", "Maximum points"], rows:
        data.datasets[0].publisherBreakdown.map(rule => [publisherRules[rule.rule], rule.max_points]) }),
      element("p", "detail-note", "The first rule awards its points once. The other four are prorated by qualifying rows, using a minimum denominator of 10.")),
    evidenceSection("3. Catalogue category",
      element("p", "detail-copy", `Publisher records account for up to ${data.publisherMaxPoints} points. One catalogue category contributes up to ${category.strong} more, for a maximum of ${data.rankingMaxPoints}.`),
      sourceTable({ resource: "catalogue category rubric", headers: ["Catalogue evidence", "Points"], rows: [
        ["Explicit identifier or business name, or a register title supported by an entity term or relevant publisher", category.strong],
        ["Two or more other business-context signals", category.corroborated],
        ["One business-context signal", category.single],
        ["Format only, no machine-readable format, or conflicting signals", 0],
      ] }),
      element("p", "detail-note", "A positive category requires a machine-readable format and no aggregate, spatial, or official-disclosure warning.")),
    evidenceSection("4. Audit sample",
      element("p", "detail-copy", `A fixed seed selected 20 datasets for an AI-assisted review of the publisher resources. ${data.humanVerdicts} of the 20 verdicts have subsequently been human-reviewed and confirmed by the project owner. The category rerank kept all 50 datasets and the same resource evidence.`),
      disclosure("Shortlist audit hashes",
        discoveryFacts([["Current shortlist SHA-256", data.sha256], ["Original audited shortlist SHA-256", data.carriedForwardFrom]]))),
    link("Open data.gov.au catalogue", "https://data.gov.au/"),
  ]);
}
for (const button of document.querySelectorAll("[data-view]")) {
  button.addEventListener("click", () => {
    view = button.dataset.view;
    for (const tab of document.querySelectorAll("[data-view]")) tab.setAttribute("aria-pressed", String(tab === button));
    renderRows();
  });
}
$("search").addEventListener("input", renderRows);
$("verdict").addEventListener("change", renderRows);

$("show-method").addEventListener("click", showMethod);
$("close-detail").addEventListener("click", () => detail.close());
detail.addEventListener("click", event => { if (event.target === detail) detail.close(); });
detail.addEventListener("close", () => { detailNavigation = null; });
for (const [id, offset] of [["prev-dataset", -1], ["next-dataset", 1]]) {
  $(id).addEventListener("click", () => {
    if (!detailNavigation) return;
    const next = detailNavigation.index + offset;
    if (next >= 0 && next < detailNavigation.total) detailNavigation.move(next);
  });
}
const part = activatePart();
try {
  if (part === "discovery") {
    const response = await fetch("/part-one.json");
    if (!response.ok) throw new Error("Dataset snapshot unavailable");
    data = await response.json();
    showOverview();
    renderRows();
    const requested = new URLSearchParams(window.location.search).get("dataset");
    const selected = data.datasets.find(row => row.id === requested);
    if (selected) {
      if (!selected.audit) document.querySelector('[data-view="all"]').click();
      showDataset(selected);
    }
  } else {
    const { mountPart } = await import("/parts.js");
    await mountPart(part, $("part-content"), { element, beginDetail, sourceTable, link, siteLink, disclosure, jsonPreview, setArchivedRun });
  }
} catch (error) {
  console.error(error);
  if (part === "discovery") {
    $("load-error").hidden = false;
    $("summary").removeAttribute("aria-busy");
  } else {
    const message = element("p", "part-load", "Results could not be loaded. Reload the page to try again.");
    message.setAttribute("role", "status");
    $("part-content").replaceChildren(message);
  }
}
