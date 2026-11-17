const count = value => new Intl.NumberFormat("en-AU").format(value);
const usd = value => "US$" + value.toFixed(2);

export function assignmentView(data, root, ui) {
  root.classList.add("report-document");
  const { el, copy, note, table, disclosure, link, siteLink } = ui;
  const jump = (title, id) => {
    const a = el("a", "", title);
    a.href = "#" + id;
    return a;
  };
  const download = el("a", "source-link", "Full report · Markdown ↓");
  download.href = "/firmable-writeup.md";
  download.download = "firmable-writeup.md";
  const pdf = el("a", "source-link", "Parts 1–5 · PDF ↓");
  pdf.href = "/firmable-writeup.pdf";
  pdf.download = "firmable-writeup.pdf";
  const latex = el("a", "source-link", "LaTeX source ↓");
  latex.href = "/firmable-writeup.tex";
  latex.download = "firmable-writeup.tex";
  const heading = el("section", "overview assignment-intro",
    el("p", "eyebrow", "The assignment · Parts 1–5"), el("h1", "", data.title),
    el("p", "intro", data.context),
    el("nav", "answer-nav", ...data.parts.map((part, i) => jump("Part " + (i + 1), part.id)),
      jump("Part 5 · Six questions", "part-5"), jump("Cost calculation", "cost-calculation")),
    el("div", "answer-actions", pdf, latex, download, siteLink("System architecture", "architecture")));
  const sections = data.parts.map(part => {
    const node = el("section", "answer-section",
      el("div", "answer-heading", el("h2", "", part.title), siteLink("Explore results", part.destination)),
      part.question ? el("p", "assignment-question", part.question) : null,
      ...(part.selection ?? []).map(copy),
      part.dataset_contributions?.length ? el("ul", "source-contributions", ...part.dataset_contributions.map(row =>
        el("li", "", el("strong", "", row.name + ". "), row.detail))) : null,
      part.profile_capabilities?.length ? el("ul", "source-contributions", ...part.profile_capabilities.map(row =>
        el("li", "", el("strong", "", row.name + ". "), row.detail))) : null,
      part.profile_examples?.length ? el("div", "profile-report-examples",
        el("ul", "source-contributions", ...part.profile_examples.map(row =>
          el("li", "", el("strong", "", row.name + ". "), row.detail, " ",
            siteLink("View profile", "profiles", { entity: row.entity_key }))))) : null,
      ...part.answer.map(copy),
      ...part.extra.map(text => el("p", "extra-work", el("strong", "", "Extra work. "), text)),
      part.limits.length ? disclosure("Scope and remaining requirements", ...part.limits.map(copy)) : null);
    node.id = part.id;
    return node;
  });
  const costs = data.cost;
  const costNode = el("div", "cost-calculation",
    copy("Model: " + costs.model + ". Off-peak prices in USD per 1M tokens; input assumes cache miss."),
    table("Model prices per million tokens", ["Period", "Input price", "Output price"],
      costs.rates.map(row => [row.period, usd(row.input), usd(row.output)])),
    table("Recorded tokens and estimated cost by assignment part", ["Assignment part", "Input tokens", "Output tokens", "Estimated cost (USD)"],
      [...costs.usage, { part: "Total", ...costs.total }].map(row =>
        [row.part, count(row.input_tokens), count(row.output_tokens), usd(row.estimated_usd)])),
    note(costs.note), link("Model pricing reference", costs.source_url));
  costNode.id = "cost-calculation";
  const fifth = el("section", "answer-section part-five", el("h2", "", "Part 5 — Engineering decisions"),
    ...data.part5.map(item => el("section", "answer-question", el("h3", "", item.title),
      item.question ? el("p", "assignment-question", item.question) : null,
      item.show_cost_table ? costNode : null, ...item.answer.map(copy))));
  fifth.id = "part-5";
  root.replaceChildren(heading, ...sections, fifth);
}

export { architectureView } from "./architecture.js";
