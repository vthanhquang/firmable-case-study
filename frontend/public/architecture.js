const n = value => new Intl.NumberFormat("en-AU").format(value);
const escape = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
const types = { code: ["CODE", "#ffffff", "#cbd3c9"], ai: ["AI", "#e7f0e8", "#80a58a"],
  mixed: ["CODE + AI", "#e7f0e8", "#80a58a"], human: ["HUMAN", "#fbf2df", "#b39354"], store: ["SAVED", "#edf0f2", "#99a8b2"] };

export function architectureLanes(data) {
  const node = (title, lines, kind = "code") => ({ title, lines, kind });
  return [
    { title: "Discover useful datasets", part: "discovery", y: 80, subtitle: "PART 1 / Find evidence of actual businesses",
      nodes: [node("Catalogue API", ["1,509 deduplicated", "CKAN records"]),
        node("Preview + rank", ["Inspect columns and rows", "50 datasets / 100 points"]),
        node("Audit 20 resources", ["20 positive verdicts", "Human review verified"], "human"),
        node("Choose sources", ["Original six + extensions", "8 extracts / 7 families"]),
        node("Source snapshots", ["Download + hash files", "Retain licence metadata"], "store")],
      branches: ["Optional AI triage inspects saved resource previews; the final ranking remains deterministic."] },
    { title: "Teach one engine a new source", part: "mapping", y: 350, subtitle: "PART 2 / Onboard once; reuse the accepted configuration",
      nodes: [node("Inspect + sample", ["Test reader settings", "Profile discovery rows"], "ai"),
        node("Propose mapping", ["Ontology + transformations", "Confidence + unmapped"], "ai"),
        node("Validate + critique", ["Execute held-out checks", "Inspect semantic meaning"], "mixed"),
        node("Human decision", ["See rules + row evidence", "Accept or request changes"], "human"),
        node("Approved config", ["8 human-verified mappings", "Digest + source version"], "store")],
      branches: ["Failed checks or requested changes return to the proposal. Bounded retries stop at a saved checkpoint.",
        "Seven later maintainer corrections were tested on frozen rows and human-confirmed; they are separate from the original agent loop."] },
    { title: "Identify the same business", part: "identity", y: 675, subtitle: "PART 3 / Deterministic processing; no model API calls",
      nodes: [node("Extract observations", [n(data.replay.records) + " saved rows", n(data.observations) + " field observations"]),
        node("Generate candidates", ["ABN / ACN / names", "Place + domain evidence"]),
        node("Score + decide", ["Threshold 0.85", n(data.replay.challenger.links) + " proposed links"]),
        node("Constrained clusters", [n(data.replay.challenger.entities_in_multiple_sources) + " multi-source entities", "Canonical business keys"]),
        node("Review 50 links", ["46 pass / 4 fail = 92%", "Failures retained + flagged"], "human")],
      branches: ["Refusal branch: 1,245 unlinked records retain reasons and candidate evidence.",
        "Typed relationships keep licences, sites and programmes distinct from business identity. No unsupported ownership inference.",
        "The human audit annotates proposals; it does not yet apply corrections to cluster membership."] },
    { title: "Assemble a useful company profile", part: "profiles", y: 1020, subtitle: "PART 4 / Deterministic assembly; no model API calls",
      nodes: [node("Group claims", ["Separate business / sites", "Licences + financial years"]),
        node("Resolve conflicts", ["Choose by evidence strength", "Keep alternatives + reasons"]),
        node("Build profiles", ["50 business profiles", "Field confidence + origins"]),
        node("Rebuild + compare", ["Remove one source", "Check values + membership"]),
        node("Explore the results", ["Source graphs + profiles", "Evidence + review exports"], "store")],
      branches: ["Nested site/licence confidence remains incomplete. Financial-source dependence is measured; a corruption replay is future work."] }
  ];
}

export function architectureSvg(data) {
  const lanes = architectureLanes(data);
  const text = (x, y, value, size = 16, weight = 400, fill = "#17231e") =>
    `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}">${escape(value)}</text>`;
  const path = (d, dashed = false) => `<path d="${d}" fill="none" stroke="#63816e" stroke-width="2" ${dashed ? 'stroke-dasharray="6 5"' : ""} marker-end="url(#arrow)"/>`;
  const parts = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1400" role="img" aria-labelledby="arch-title arch-desc" font-family="Arial, sans-serif">`,
    `<title id="arch-title">Firmable pipeline: discovery, AI mapping, entity matching and company profiles</title>`,
    `<desc id="arch-desc">Left-to-right steps connect four stages. Green nodes use AI, amber nodes involve human decisions, grey nodes retain outputs. Mapping failures loop back to revision. Matching also creates an unlinked queue and typed relationships. Parts 3 and 4 make no additional model calls.</desc>`,
    `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#63816e"/></marker></defs>`,
    `<rect width="1280" height="1400" rx="10" fill="#f8f8f4"/>`];
  ["code", "ai", "human", "store"].forEach((key, i) => {
    const [label, bg, stroke] = types[key];
    parts.push(`<rect x="${40 + i * 175}" y="20" width="18" height="18" rx="3" fill="${bg}" stroke="${stroke}"/>`,
      text(67 + i * 175, 35, label === "SAVED" ? "SAVED ARTIFACT" : label, 13, 600, "#4a554e"));
  });
  for (const [i, lane] of lanes.entries()) {
    const y = lane.y;
    parts.push(text(40, y + 18, String(i + 1).padStart(2, "0"), 24, 700, "#235444"),
      text(91, y + 18, lane.title, 24, 700), text(91, y + 43, lane.subtitle, 13, 400, "#4a554e"));
    lane.nodes.forEach((node, j) => {
      const x = 40 + j * 245, top = y + 66, [label, bg, stroke] = types[node.kind];
      parts.push(`<a href="/?part=${lane.part}" aria-label="${escape(node.title)}"><g>`,
        `<rect x="${x}" y="${top}" width="220" height="116" rx="7" fill="${bg}" stroke="${stroke}" stroke-width="${node.kind === "human" ? 2 : 1.4}"/>`,
        text(x + 15, top + 23, label, 11, 700, "#4a554e"), text(x + 15, top + 49, node.title, 18, 700),
        ...node.lines.map((line, k) => text(x + 15, top + 74 + k * 20, line, 14, 400, "#4a554e")), `</g></a>`);
      if (j < 4) parts.push(path(`M ${x + 220} ${top + 58} H ${x + 240}`, i === 2 && j === 3));
    });
    if (i === 0) {
      parts.push(text(40, y + 216, lane.branches[0], 15, 400, "#4a554e"),
        path(`M 1250 ${y + 124} H 1260 V 327 H 20 V 474 H 35`), text(465, 318, "Saved files + ontology", 14, 600, "#235444"));
    } else if (i === 1) {
      parts.push(path(`M 640 ${y + 182} V ${y + 215} H 395 V ${y + 187}`, true),
        path(`M 885 ${y + 182} V ${y + 215} H 645`, true),
        text(40, y + 245, lane.branches[0], 14, 400, "#4a554e"),
        text(40, y + 270, "Later maintenance: seven local corrections, frozen-row validation, then human confirmation.", 14, 400, "#4a554e"),
        path(`M 1250 ${y + 124} H 1260 V 652 H 20 V 799 H 35`), text(470, 643, "Reuse accepted rules", 14, 600, "#235444"));
    } else if (i === 2) {
      parts.push(path(`M 640 ${y + 182} V ${y + 202}`),
        `<rect x="530" y="${y + 207}" width="220" height="64" rx="6" fill="#f7eee9" stroke="#c59c89"/>`,
        text(545, y + 231, "1,245 unlinked records", 16, 700), text(545, y + 254, "Reason + candidate evidence", 14, 400, "#4a554e"),
        text(40, y + 228, "Separate relationship edges", 16, 700), text(40, y + 251, "Licences / sites / programmes", 14, 400, "#4a554e"),
        path(`M 150 ${y + 182} V ${y + 204}`),
        text(1020, y + 228, "Audit flags only;", 14, 400, "#4a554e"), text(1020, y + 250, "no automatic correction.", 14, 400, "#4a554e"),
        path(`M 885 ${y + 182} V 997 H 20 V 1144 H 35`), text(470, 988, "Linked records + typed relationships", 14, 600, "#235444"));
    } else {
      parts.push(text(40, y + 216, "Remaining: complete nested-field confidence; test financial-source corruption.", 15, 400, "#4a554e"));
    }
  }
  parts.push(`<rect x="40" y="1293" width="1200" height="76" rx="7" fill="#e9eee7"/>`,
    text(60, 1321, "EVIDENCE TRAVELS WITH THE DATA", 13, 700, "#235444"),
    text(60, 1348, "Source snapshot  →  record ID  →  mapping digest  →  observation  →  link decision  →  profile field", 17), `</svg>`);
  return parts.join("");
}

export function architectureView(data, root, ui) {
  const { el, copy, siteLink } = ui;
  const download = el("a", "source-link", "Download infographic · SVG ↓");
  download.href = "/system-architecture.svg";
  download.download = "firmable-system-architecture.svg";
  const graphic = el("div", "architecture-graphic");
  graphic.innerHTML = architectureSvg(data);
  const mobile = el("div", "architecture-mobile", ...architectureLanes(data).map((lane, i) =>
    el("section", "architecture-mobile-lane", el("p", "eyebrow", "0" + (i + 1) + " / " + lane.subtitle),
      el("h2", "", lane.title), el("ol", "architecture-steps", ...lane.nodes.map(node =>
        el("li", "architecture-step " + node.kind, el("span", "step-kind", types[node.kind][0]),
          siteLink(node.title, lane.part), copy(node.lines.join(" · "))))),
      ...lane.branches.map(note => el("p", "architecture-branch-note", note)))));
  root.replaceChildren(el("section", "overview assignment-intro",
    el("p", "eyebrow", "System architecture"), el("h1", "", "From source records to company profiles"),
    el("p", "intro", "AI learns how to read a source. People verify the mapping. Code links the records and assembles the profiles."),
    el("div", "answer-actions", download, siteLink("Read the two-page write-up", "write-up"))), graphic, mobile);
}
