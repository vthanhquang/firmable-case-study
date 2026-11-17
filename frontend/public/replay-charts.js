const number = new Intl.NumberFormat("en-AU");
const count = value => number.format(value);

const sourceTopics = {
  acnc_charities: ["Charity register", "Registered charities, their purposes, and where they operate."],
  asic_companies: ["Company register", "Registered companies, legal names, company types, and registration status."],
  asic_credit_licensees: ["Credit licences", "Credit licence holders, their authorisations, and licence status."],
  ato_tax_transparency: ["Company tax", "Company income and tax reported for the 2024–25 year."],
  ato_tax_transparency_2023_24: ["Company tax", "Company income and tax reported for the 2023–24 year."],
  dewr_employment_providers: ["Employment services", "Employment service providers, their sites, and service programs."],
  qbcc_licensees: ["Contractor licences", "Queensland contractor licence holders, licence grades, and work categories."],
  vic_liquor: ["Liquor licences", "Victorian liquor licences, licensees, and licensed premises."],
};

function fieldGroup(path) {
  const [family, field] = path.replace(/^ext\./, "").split(".");
  if (family === "financial") return "Tax and revenue";
  if (family === "licence") return "Licences";
  if (family === "address" || family === "establishment" || field === "address_point") return "Locations and sites";
  if (family === "contact" || field === "website") return "Web and contact fields";
  if (["abn", "acn", "legal_name", "trading_name", "former_name", "business_name"].includes(field)) {
    return "Names and identifiers";
  }
  return "Registration and business details";
}

export function mappingChart(mappings, sourceName, ui) {
  const { el, siteLink, disclosure, table } = ui;
  const maxColumns = Math.max(1, ...mappings.map(row => row.columns.raw_columns));
  const step = Math.ceil(maxColumns / 40) * 10;
  const scale = Math.ceil(maxColumns / step) * step;
  const ticks = Array.from({ length: scale / step + 1 }, (_, i) => i * step);
  const buttons = new Map();
  const inspector = el("div", "chart-inspector");
  inspector.setAttribute("aria-live", "polite");

  function select(row) {
    for (const [id, button] of buttons) button.setAttribute("aria-pressed", String(row.id === id));
    const byGroup = new Map();
    for (const { field, observations } of row.extracted_fields) {
      const group = fieldGroup(field);
      byGroup.set(group, (byGroup.get(group) ?? 0) + observations);
    }
    const groups = [...byGroup].sort((a, b) => b[1] - a[1]);
    const fields = row.extracted_fields.toSorted((a, b) => b.observations - a.observations || a.field.localeCompare(b.field));
    const inputs = new Set(fields.flatMap(field => field.columns));
    inspector.replaceChildren(
      el("h3", "", sourceName(row.id)),
      el("p", "chart-topic", sourceTopics[row.id]?.[1] ?? row.title),
      el("dl", "chart-stats",
        el("div", "", el("dt", "", "Rows processed"), el("dd", "", count(row.sample.records))),
        el("div", "", el("dt", "", "Observation inputs"), el("dd", "", count(inputs.size) + " columns")),
        el("div", "", el("dt", "", "Observations"), el("dd", "", count(row.sample.observations)))),
      el("h4", "", "What was extracted"),
      el("ul", "chart-list",
        ...groups.map(([label, emitted]) => el("li", "", el("span", "", label), el("strong", "", count(emitted))))),
      disclosure("View " + fields.length + " emitted fields", () => [
        table("Emitted fields for " + sourceName(row.id), ["Field", "Input columns", "Observations"],
          fields.map(({ field, columns, observations }) => [field, columns.join(", ") || "—", count(observations)])),
      ]),
      siteLink("Open source mapping", "mapping", { source: row.id }));
  }

  const rows = mappings.toSorted((a, b) => b.columns.read_by_extension_config - a.columns.read_by_extension_config);
  const axis = el("div", "column-axis", el("span", "", "Source"),
    el("div", "column-ticks", ...ticks.map(tick => {
      const marker = el("span", "", String(tick));
      marker.style.left = tick / scale * 100 + "%";
      return marker;
    })), el("span", "", "Read / total"));
  axis.setAttribute("aria-hidden", "true");
  const bars = rows.map(row => {
    const { raw_columns: total, read_by_approved_config: base, read_by_extension_config: read } = row.columns;
    const track = el("span", "column-track",
      el("span", "column-total"), el("span", "column-read"), el("span", "column-base"));
    track.setAttribute("aria-hidden", "true");
    track.style.setProperty("--source-total", total / scale * 100 + "%");
    track.style.setProperty("--source-read", read / scale * 100 + "%");
    track.style.setProperty("--source-base", base / scale * 100 + "%");
    const topic = sourceTopics[row.id]?.[0];
    const button = el("button", "column-row", el("span", "", el("span", "column-name", sourceName(row.id)),
      topic ? el("span", "column-topic", topic) : null),
      track, el("strong", "column-value", read + " / " + total));
    button.type = "button";
    button.setAttribute("aria-label", sourceName(row.id) + (topic ? ", " + topic : "") + ", " +
      read + " of " + total + " source columns read, " + base + " in the base mapping");
    button.addEventListener("click", () => select(row));
    buttons.set(row.id, button);
    return button;
  });
  select(rows[0]);
  return el("section", "analysis-section",
    el("div", "section-heading", el("div", "", el("h2", "", "What each source contributed"),
      el("p", "", "Select a source to see what its mapping emitted."))),
    el("div", "analysis-card",
      el("div", "chart-main",
        el("div", "chart-legend", el("span", "", el("i", "legend-read"), "Latest mapping"),
          el("span", "", el("i", "legend-base"), "Base mapping"),
          el("span", "", el("i", "legend-total"), "Source columns")),
        axis, el("div", "column-bars", ...bars),
        el("p", "chart-note", "Column counts include inputs used for field rules, filters and record identifiers. Observation counts come from the saved extraction.")),
      inspector));
}

// Positions keep the finance sources together and the ACNC service and licence links apart.
const sourcePositions = {
  dewr_employment_providers: [12, 19, 25, 87],
  vic_liquor: [12, 81, 76, 87],
  acnc_charities: [27, 50, 66, 64],
  qbcc_licensees: [49, 83, 22, 59],
  asic_companies: [49, 50, 50, 43],
  asic_credit_licensees: [73, 50, 50, 27],
  ato_tax_transparency: [78, 18, 24, 11],
  ato_tax_transparency_2023_24: [86, 82, 76, 11],
};

export function sourcePairs(rows, profiles = false) {
  const grouped = new Map();
  for (const row of rows) {
    const ids = profiles ? [...new Set(row.sources)].sort() : [row.a.source_id, row.b.source_id].sort();
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
      const key = ids[i] + "|" + ids[j];
      if (!grouped.has(key)) grouped.set(key, { a: ids[i], b: ids[j], links: 0, entities: new Set() });
      const pair = grouped.get(key);
      pair.links++;
      pair.entities.add(profiles ? row.entity_key : row.canonical_entity_key);
    }
  }
  return [...grouped.values()].map(pair => ({ ...pair, companies: pair.entities.size,
    entities: [...pair.entities] })).sort((a, b) => b.companies - a.companies || b.links - a.links);
}

export function identityChart(sourceIds, pairs, sourceName, ui, { profiles = false } = {}) {
  const { el, siteLink } = ui;
  const canvas = el("canvas", "network-edges");
  canvas.setAttribute("aria-hidden", "true");
  const nodes = new Map();
  let selected = "";
  const maxLinks = Math.max(1, ...pairs.map(pair => pair.companies));
  const panel = el("div", "chart-inspector network-inspector");
  const graph = el("div", "source-network", canvas);
  graph.setAttribute("role", "group");
  graph.setAttribute("aria-label", "Source network. Select a source to show its proposed links.");
  sourceIds.forEach((id, i) => {
    const angle = i / sourceIds.length * 2 * Math.PI;
    const x = 50 + 35 * Math.cos(angle);
    const y = 50 + 35 * Math.sin(angle);
    const [desktopX, desktopY, mobileX, mobileY] = sourcePositions[id] ?? [x, y, x, y];
    const button = el("button", "network-node", sourceName(id));
    button.type = "button";
    button.style.setProperty("--node-x", desktopX + "%");
    button.style.setProperty("--node-y", desktopY + "%");
    button.style.setProperty("--mobile-x", mobileX + "%");
    button.style.setProperty("--mobile-y", mobileY + "%");
    button.addEventListener("click", () => {
      selected = selected === id ? "" : id;
      update();
    });
    graph.append(button);
    nodes.set(id, button);
  });
  const reset = el("button", "text-button", "Show all");
  reset.type = "button";
  reset.addEventListener("click", () => {
    const previous = nodes.get(selected);
    selected = "";
    update();
    previous?.focus();
  });
  const heading = el("h3");
  const status = el("p", "chart-topic");
  status.setAttribute("aria-live", "polite");
  const list = el("ol", "pair-list");
  panel.append(el("div", "network-panel-heading", heading, reset), status, list);
  const connected = pair => !selected || pair.a === selected || pair.b === selected;
  const pairLink = pair => {
    const link = siteLink("", profiles ? "profiles" : "identity", {
      view: profiles ? "profiles" : "links", source_a: pair.a, source_b: pair.b,
    });
    link.href += profiles ? "#company-profiles" : "#match-decisions";
    return link;
  };
  const edgeLabels = new Map(pairs.map(pair => {
    const link = pairLink(pair);
    link.className = "network-edge-label";
    link.textContent = count(pair.companies);
    link.setAttribute("aria-label", sourceName(pair.a) + " and " + sourceName(pair.b) + ": " +
      count(pair.companies) + (profiles ? " sampled profiles" : " distinct companies"));
    link.title = link.getAttribute("aria-label");
    graph.append(link);
    return [pair, link];
  }));

  function draw() {
    const width = graph.clientWidth;
    const height = graph.clientHeight;
    if (!width || !height) return;
    const pixelRatio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    const context = canvas.getContext("2d");
    if (!context) return;
    context.scale(pixelRatio, pixelRatio);
    context.lineCap = "round";
    const occupied = [...nodes.values()].map(node => ({
      x: node.offsetLeft - node.offsetWidth / 2 - 4, y: node.offsetTop - node.offsetHeight / 2 - 4,
      w: node.offsetWidth + 8, h: node.offsetHeight + 8,
    }));
    for (const pair of pairs.toSorted((a, b) => Number(connected(a)) - Number(connected(b)) || b.links - a.links)) {
      const a = nodes.get(pair.a);
      const b = nodes.get(pair.b);
      context.beginPath();
      context.moveTo(a.offsetLeft, a.offsetTop);
      context.lineTo(b.offsetLeft, b.offsetTop);
      context.strokeStyle = connected(pair) ? (selected ? "#2a624a" : "#668c78") : "#dfe7dd";
      context.lineWidth = 1.5 + 9 * Math.sqrt(pair.companies / maxLinks);
      context.stroke();
      const badge = edgeLabels.get(pair);
      badge.classList.toggle("is-dimmed", !connected(pair));
      const w = badge.offsetWidth + 8, h = badge.offsetHeight + 8;
      const candidates = [0.5, 0.35, 0.65, 0.23, 0.77].map(t => ({
        x: a.offsetLeft + (b.offsetLeft - a.offsetLeft) * t - w / 2,
        y: a.offsetTop + (b.offsetTop - a.offsetTop) * t - h / 2, w, h,
      }));
      const overlap = p => occupied.reduce((sum, r) => sum +
        Math.max(0, Math.min(p.x + p.w, r.x + r.w) - Math.max(p.x, r.x)) *
        Math.max(0, Math.min(p.y + p.h, r.y + r.h) - Math.max(p.y, r.y)), 0);
      const position = candidates.toSorted((a, b) => overlap(a) - overlap(b))[0];
      badge.style.left = position.x + w / 2 + "px";
      badge.style.top = position.y + h / 2 + "px";
      occupied.push(position);
    }
  }

  function update() {
    const visible = pairs.filter(connected);
    const peers = new Set(visible.flatMap(pair => [pair.a, pair.b]));
    for (const [id, button] of nodes) {
      button.setAttribute("aria-pressed", String(id === selected));
      button.classList.toggle("is-dimmed", Boolean(selected && selected !== id && !peers.has(id)));
    }
    heading.textContent = selected ? sourceName(selected) : "Source pairs";
    reset.hidden = !selected;
    const entities = new Set(visible.flatMap(pair => pair.entities));
    status.textContent = visible.length ? count(entities.size) + (profiles ? " sampled profiles" : " distinct companies") +
      " across " + count(visible.length) + (visible.length === 1 ? " pair" : " pairs")
      : profiles ? "No profiles in the 50-company sample use this source." : "No proposed links for this source.";
    list.replaceChildren(...visible.map(pair => {
      const names = selected ? sourceName(pair.a === selected ? pair.b : pair.a)
        : sourceName(pair.a) + " ↔ " + sourceName(pair.b);
      const link = pairLink(pair);
      link.replaceChildren(el("span", "", names), el("span", "pair-counts",
        el("strong", "", count(pair.companies) + (profiles ? (pair.companies === 1 ? " profile" : " profiles") : (pair.companies === 1 ? " company" : " companies"))),
        profiles ? null : el("small", "", count(pair.links) + " record links")));
      link.setAttribute("aria-label", names + ", " + count(pair.companies) + (profiles ? " sampled profiles" : " distinct companies"));
      return el("li", "", link);
    }));
    draw();
  }

  new ResizeObserver(draw).observe(graph);
  update();
  return el("section", "analysis-section",
    el("div", "section-heading", el("div", "", el("h2", "", "How the sources link"),
      el("p", "", profiles ? "Eight source extracts. Edge numbers count the sampled profiles shared by each pair."
        : "Edge numbers count distinct companies. Select a source or open a connection to inspect its matches."))),
    el("div", "analysis-card network-card",
      el("div", "chart-main", graph,
        el("p", "chart-note network-legend", el("span", "line-sample"), el("span", "line-sample wide"),
          profiles ? "Counts cover the 50 displayed profiles. A profile can appear on several edges."
            : "Line widths and labels count distinct companies. ATO years are extracts from the same publisher.")),
      panel));
}
