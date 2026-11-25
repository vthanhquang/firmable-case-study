// Read-only recorded execution viewer. No model requests or review mutations.
const obNumber = new Intl.NumberFormat("en-AU");
const obCount = value => value == null ? "Not recorded" : obNumber.format(value);
const obLabel = value => String(value ?? "").replaceAll("_", " ");
const obStages = ["Dataset arrives", "Inspect & connect", "Plan information", "Evolve ontology", "Validate & revise", "Evaluate & review", "Profile impact"];
const obStepContracts = [
  ["Source registration", "Publisher metadata and downloaded snapshot", "Source identity, licence and frozen sample"],
  ["Inspector agent + shared reader", "Headers, sampled values and source documentation", "Row grain, preserved columns and tested joins"],
  ["Group planner agent", "Inspected table and current ontology", "Column groups, entity roles and proposed relationships"],
  ["Group architect agent", "Column group, existing concepts and source evidence", "Concept reuse decisions and candidate extensions"],
  ["Mapper agent + executable validator + critic agent", "Proposed concepts and mapping rules", "Accepted group or specific feedback for another attempt"],
  ["Test evaluator + human review", "Candidate mapping and withheld records", "Measured execution results and unresolved review contracts"],
  ["Read-only profile preview", "Candidate observations, provenance and existing profile identifiers", "Possible profile additions; identity and approval gates remain"],
];

function obEl(tag, cls, ...children) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  children.flat().filter(c => c != null).forEach(c => node.append(c));
  return node;
}
function obButton(label, handler, cls = "ob-button") {
  const button = obEl("button", cls, label); button.type = "button";
  button.addEventListener("click", handler); return button;
}
function obText(text, cls = "ob-note") { return obEl("p", typeof cls === "string" ? cls : "ob-note", text); }
function obReplace(node, ...children) { node.replaceChildren(...children.filter(c => c != null)); }
function obBadge(text, kind = "neutral") { return obEl("span", "ob-badge " + kind, text); }
function obCode(value) { const code = obEl("pre", "ob-code", typeof value === "string" ? value : JSON.stringify(value, null, 2)); code.tabIndex = 0; return code; }
function obDetails(title, ...content) { return obEl("details", "ob-disclosure", obEl("summary", "", title), obEl("div", "ob-disclosure-body", content)); }
function obBlock(title, ...content) { return obEl("section", "ob-block", obEl("h3", "", title), content); }
function obFacts(entries) { return obEl("dl", "ob-facts", entries.map(([key, value]) => obEl("div", "", obEl("dt", "", key), obEl("dd", "", String(value ?? "Not recorded"))))); }
function obValue(value) { return value == null || value === "" ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value); }
function obTable(headers, rows, caption) {
  const table = obEl("table", "ob-table", obEl("caption", "sr-only", caption),
    obEl("thead", "", obEl("tr", "", headers.map(h => { const th = obEl("th", "", h); th.scope = "col"; return th; }))),
    obEl("tbody", "", rows.map(row => obEl("tr", "", row.map(v => obEl("td", "", v instanceof Node ? v : obValue(v)))))));
  const scroll = obEl("div", "ob-table-scroll", table); scroll.tabIndex = 0;
  scroll.setAttribute("role", "region"); scroll.setAttribute("aria-label", caption); return scroll;
}
function obSelect(label, options, value, change) {
  const select = obEl("select", "");
  for (const [key, text] of options) { const option = obEl("option", "", text); option.value = key; select.append(option); }
  select.value = value; select.addEventListener("change", () => change(select.value));
  return obEl("label", "ob-select", obEl("span", "", label), select);
}
function obLink(label, href) {
  try { const url = new URL(href); if (!["https:", "http:"].includes(url.protocol)) return null;
    const a = obEl("a", "ob-link", label + " ↗"); a.href = url.href; a.target = "_blank"; a.rel = "noopener noreferrer"; return a;
  } catch { return null; }
}
function obDownload(filename, content, type = "application/json") {
  const url = URL.createObjectURL(new Blob([typeof content === "string" ? content : JSON.stringify(content, null, 2)], {type}));
  const a = obEl("a"); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function obReviewCsv(s) {
  const cell = v => '"' + String(v ?? "").replaceAll('"', '""') + '"';
  const rows = [["key", "kind", "fingerprint", "recorded_state", "human_verdict", "reviewer", "minutes", "notes"],
    ...s.review_queue.map(i => [i.key, i.kind, i.fingerprint, i.review_state, "", "", "", ""])];
  obDownload(s.key + "-review-queue.csv", rows.map(r => r.map(cell).join(",")).join("\r\n"), "text/csv;charset=utf-8");
}
function obSvg(tag, attrs = {}, text) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k,v)); if (text) el.textContent = text; return el;
}
function obLines(svg, text, x, y, width = 25, cls = "ob-svg-text") {
  const words = obLabel(text).split(/\s+/); const lines = []; let line = "";
  for (const word of words) { if ((line + " " + word).length > width && line) { lines.push(line); line = word; } else line += (line ? " " : "") + word; }
  if (line) lines.push(line);
  lines.slice(0,3).forEach((str,i) => svg.append(obSvg("text", {x,y:y+i*18,class:cls}, str)));
}
function obSvgButton(svg, x,y,w,h,label,state,click,subtitle) {
  const g = obSvg("g", {role:"button", tabindex:"0", "aria-label":label, class:"ob-graph-node " + state});
  g.append(obSvg("rect", {x,y,width:w,height:h,rx:5})); obLines(g,label,x+13,y+25,24);
  if (subtitle) g.append(obSvg("text",{x:x+13,y:y+h-13,class:"ob-svg-state"},subtitle));
  g.addEventListener("click",click); g.addEventListener("keydown", e => { if (["Enter"," "].includes(e.key)) { e.preventDefault(); click(); } }); svg.append(g);
}

export function mountOnboarding(data, root, {standalone = false} = {}) {
  const params = new URLSearchParams(location.search);
  let sourceKey = data.sources.some(s => s.key === params.get("dataset")) ? params.get("dataset") : "ip";
  let stage = Math.min(6, Math.max(0, Math.floor(Number(params.get("stage") || 1)) - 1));
  if (!Number.isFinite(stage)) stage = 0;
  root.classList.add("ob-root");
  const shell = obEl("div", "ob-shell");
  const live = obEl("p", "sr-only"); live.setAttribute("aria-live", "polite");
  const intro = obEl("div", "page-intro ob-intro", obText("Research extension · Recorded execution", "eyebrow"),
    obEl("h1", "", "Dataset onboarding"), obText("Follow a source through agent decisions, executable checks and the review needed before its facts reach a company profile.", "intro"));
  intro.dataset.enter = "";
  const picker = obSelect("Replay a dataset", data.sources.map(s => [s.key, s.name]), sourceKey, value => { sourceKey = value; stage = 0; render(); });
  const header = obEl("div", "ob-header", intro, picker);
  obReplace(root,header, shell, live);
  function current() { return data.sources.find(s => s.key === sourceKey); }
  function go(index) { stage = index; render(true); }
  function render(focus = false) {
    const s = current(); const groups = s.groups.filter(g => g.status !== "AGENT_VALIDATED");
    const url = new URL(location.href); url.searchParams.set("dataset", sourceKey); url.searchParams.set("stage", String(stage+1));
    try { history.replaceState(null,"",url); } catch { /* file:// viewers can restrict history. */ }
    const summary = obEl("div", "ob-summary", ...[
      ["Extracted observations", obCount(s.metrics.observations), "Recorded candidate output"],
      ["Business-connected", obCount(s.metrics.business_connected_observations), "Visible facts with a declared business path"],
      ["Human-verified", "Not measured", "No human verdict inferred from agent checks"],
      ["Groups accepted", `${s.metrics.accepted_groups} / ${s.metrics.groups}`, `${groups.length} unresolved · ${obCount(s.run.input_tokens+s.run.output_tokens)} tokens across passes`],
    ].map(([label,value,note]) => obEl("div", "ob-stat", obText(label), obEl("strong", "", value), obText(note))));
    const ribbon = obEl("div", "ob-ribbon", obBadge("Recorded replay", "existing"), obText(s.name + " · " + s.subtitle),
      obButton("Download evidence", () => obDownload(`${s.key}-onboarding-evidence.json`,s), "ob-button ob-secondary"));
    const progress = obEl("ol", "ob-pipeline"); progress.setAttribute("aria-label", "Dataset processing stages");
    obStages.forEach((label,index) => {
      const status = index < 4 ? "Recorded" : index === 4 ? "Partial" : index === 5 ? "Review pending" : "Preview only";
      const button = obButton("",() => go(index),"ob-stage-button");
      button.append(obEl("span","ob-step-number",String(index+1).padStart(2,"0")),obEl("span","ob-stage-label",label),obEl("small","",status));
      button.setAttribute("aria-label",`Stage ${index+1}: ${label}. ${status}`);
      if (index === stage) button.setAttribute("aria-current","step");
      progress.append(obEl("li","",button));
    });
    const main = obEl("article", "ob-stage-main"); main.id = "ob-stage-content";
    const heading = obEl("h2", "", obStages[stage]); heading.tabIndex = -1;
    const stageHeader = obEl("div", "ob-stage-heading", obEl("div","",obText(`Stage ${stage+1} of 7`,"eyebrow"),heading),
      obBadge(stage === 5 ? "Human review pending" : stage === 6 ? "No production changes" : "Recorded evidence",stage >= 5 ? "unresolved" : "neutral"));
    main.append(stageHeader);
    const [actor,input,output] = obStepContracts[stage];
    main.append(obText("Responsible: " + actor, "ob-agent"), obDetails("Step input and output", obFacts([["Input", input], ["Output", output]])));
    [arrival,inspect,plan,ontology,revisions,review,impact][stage](s,main);
    const previous = obButton("← Previous stage",() => go(stage-1),"ob-button ob-secondary"); previous.disabled = stage === 0;
    const next = obButton(stage === 6 ? "Restart replay" : "Next stage →",() => go(stage === 6 ? 0 : stage+1));
    main.append(obEl("nav","ob-stage-controls",previous,obText(`${stage+1} / 7`),next));
    const aside = obEl("aside", "ob-sidebar", obText("Review desk","eyebrow"), obEl("h2","","Human review requirements"),
      obFacts([["Contracts awaiting review",s.review_queue.filter(i=>i.review_state!=="approved_unchanged").length],["Unresolved groups",groups.length],["Production facts added",0]]),
      obText("Inspect meanings, source bindings and business identity before accepting a profile addition."),
      obButton("Open review stage",()=>go(5),"ob-button ob-secondary"), obButton("Download review queue",()=>obReviewCsv(s),"ob-button ob-secondary"),
      obEl("div","ob-side-section",obEl("h3","","Current limitation"),obText(s.takeaway)),
      obEl("div","ob-side-section",obEl("h3","","Recorded model usage"),obFacts([["Input tokens",obCount(s.run.input_tokens)],["Output tokens",obCount(s.run.output_tokens)],["Calls, including retries",s.run.calls]]),
        obText(s.run.model + " · First pass + recovery. Replaying this page makes no model calls.")),
      obDetails("Evidence identity",obText(s.source_id),obText(s.evidence.result),obCode({snapshot:s.source.snapshot_sha256,ontology:s.evidence.ontology_version,manifest:s.evidence.manifest_sha256})),
    );
    obReplace(shell,ribbon,summary,progress,obEl("div","ob-workspace",main,aside));
    live.textContent = `${s.name}. Stage ${stage+1}: ${obStages[stage]}. Recorded execution.`;
    if (focus) { heading.focus({preventScroll:true}); main.scrollIntoView({block:"start",behavior:"instant"}); }
  }

  function arrival(s, main) {
    main.append(obText("Input: a publisher snapshot. Output: an identifiable source with a licence, retrieval date and reproducible sample.","ob-lead"),
      obBlock(s.source.title,obFacts([["Publisher",s.source.publisher],["Retrieved",s.source.retrieved_at?.slice(0,10)],["Available input rows",obCount(s.sampling.source_rows)],["Frozen sample",obCount(s.sampling.sample_rows) + " records"]]),
        obEl("div","ob-links",obLink("Publisher resource",s.source.url),obLink("Documentation",s.source.documentation_url),obLink(s.source.licence_detail?.title || "Licence",s.source.licence_detail?.url))),
      obText(s.key === "ip" ? "This input is a joined view of a 25,000-row patent-prefix cohort. It is not a representative sample of all IP rights." : "The source was sampled reproducibly. The preview below contains the first 50 frozen sample records, not the first 50 consecutive publisher rows."));
    let page = 0, group = "all";
    const preview = obEl("div");
    const renderPreview = () => {
      const columns = group === "all" ? s.headers.parsed_columns.slice(0,8) : s.plan.groups.find(g=>g.name===group).columns;
      const rows = s.preview.slice(page*10,page*10+10);
      const back=obButton("Previous rows",()=>{page--;renderPreview();},"ob-button ob-secondary");back.disabled=page===0;
      const forward=obButton("Next rows",()=>{page++;renderPreview();},"ob-button ob-secondary");forward.disabled=(page+1)*10>=s.preview.length;
      obReplace(preview,obTable(["Source row",...columns],rows.map(r=>[r.ordinal,...columns.map(c=>r.row[c])]),"Frozen source row preview"),
        obEl("div","ob-pager",back,obText(`Sample ${page*10+1}–${page*10+rows.length} of ${s.preview.length} · ${columns.length} columns`),forward));
    };
    main.append(obBlock("Source row preview",obSelect("Columns to inspect",[["all","Identity preview"],...s.plan.groups.map(g=>[g.name,obLabel(g.name)])],group,v=>{group=v;page=0;renderPreview();}),preview,
      obText("Natural-person IP names and direct contact details are withheld in this demo. Original row ordinals and empty values remain visible.")));
    renderPreview();
  }

  function inspect(s, main) {
    main.append(obText("The inspector decides how to read the file and what one record represents. The executor preserves columns and tests join keys against actual values.","ob-lead"),
      obBlock("Recorded inspection",obText(s.inspection.grain,"ob-quote"),obText(s.inspection.rationale),
        obFacts([["Reader",s.inspection.reader.format],["Sheet",s.inspection.reader.sheet || "Not applicable"],["Columns preserved",s.headers.parsed_columns.length]]),
        obDetails("Identity cautions",...s.inspection.identity_cautions.map(obText))),
      obBlock("Frozen evidence partitions",obEl("div","ob-partitions",...Object.entries(s.sampling.partitions).map(([key,n])=>obEl("div","",obEl("strong","",obCount(n)),obText(obLabel(key)),obText(key==="test"?"Withheld until final evaluation":key==="validation"?"Execution feedback and criticism":"Initial proposal evidence"))))));
    if (s.join) {
      main.append(obBlock("Model-proposed joins, checked in code",...s.join.steps.map(({step,measurement:m})=>obEl("div","ob-join",
        obEl("div","ob-join-path",obEl("strong","",obLabel(step.left_table)),obEl("span","","→"),obEl("strong","",obLabel(step.right_table))),
        obText(step.left_columns.join(" + ")+" = "+step.right_columns.join(" + "),"ob-mono"),
        obFacts([["Matched anchor rows",`${obCount(m.matched_left_rows)} / ${obCount(m.left_rows)}`],["Right rows scanned",obCount(m.right_rows_scanned)],["Duplicate right keys",m.right_duplicate_keys_in_cohort],["Maximum rows per anchor",m.materialized_rows_per_left_max]]),
        obDetails("Meaning and constraints",obText(step.meaning),...step.cautions.map(obText))))));
    } else {
      main.append(obBlock("No multi-table join in this run",obText("This source is inspected as one table. Its dates, measures and identifiers remain attached to its recorded grain.")));
      if (s.headers.raw_headers) main.append(obDetails("Physical headers and reporting-year context",obCode({context:s.headers.header_context,physical:s.headers.raw_headers,parsed:s.headers.parsed_columns})));
    }
  }

  function plan(s, main) {
    main.append(obText("The planner partitions source columns and proposes owning entities. A separate node does not automatically become the same business.","ob-lead"));
    const selected = obEl("div","ob-inspector");
    const roles = [{name:"subject",kind:"business",key_paths:[],rationale:"Implicit business subject. A declared relationship is still needed to connect separate source roles."},...Object.entries(s.plan.entities).map(([name,r])=>({name,...r}))];
    const svg = obSvg("svg",{viewBox:`0 0 850 ${190+s.plan.relationships.length*31}`,class:"ob-topology","aria-label":"Recorded entity roles and relationships",role:"group"});
    roles.forEach((r,i)=>{
      const x=20+i*(810/roles.length); const w=810/roles.length-16;
      obSvgButton(svg,x,24,w,110,obLabel(r.name),r.name==="subject"?"existing":"proposed",()=>obReplace(selected,obEl("h4","",obLabel(r.name)),obText(r.rationale),obCode({kind:r.kind,key_paths:r.key_paths})),r.kind);
    });
    s.plan.relationships.forEach((edge,i)=>{
      const left=roles.findIndex(r=>r.name===edge.from_role),right=roles.findIndex(r=>r.name===edge.to_role);
      if (left<0||right<0) return;
      const x=20+(left+.45)*(810/roles.length),x2=20+(right+.45)*(810/roles.length),y=166+i*31;
      svg.append(obSvg("path",{d:`M ${x} 139 L ${x} ${y} L ${x2+(left===right?24:0)} ${y} L ${x2+(left===right?24:0)} 139`,class:"ob-edge"}));
      svg.append(obSvg("circle",{cx:x2+(left===right?24:0),cy:139,r:3,class:"ob-edge-dot"}));
    });
    selected.append(obText("Select a role above to inspect its key and the planner’s recorded rationale."));
    main.append(obBlock("Entity topology",svg,selected,
      obDetails("Inspect recorded relationships",s.plan.relationships.length ? obTable(["From","Relationship","To","Recorded rationale"],s.plan.relationships.map(e=>[e.from_role,e.type,e.to_role,e.rationale]),"Entity relationships") : obText("No relationship was declared by this planner.")),
      obText(s.metrics.business_connected_observations===0?"No visible observations have a declared path to a business in this candidate. Identity reconciliation remains a separate task.":"Some identity facts connect to business; separate charity and other roles still need relationship review.","ob-warning"),
      s.self_edges ? obText(`${obCount(s.self_edges)} emitted self-edges require graph review. A self-edge cannot identify a separate description entity.`,"ob-warning") : null));
    main.append(obBlock("Column groups",...s.plan.groups.map(g=>{
      const result=s.groups.find(r=>r.group===g.name);
      return obDetails(`${obLabel(g.name)} · ${g.columns.length} columns · ${result.status==="AGENT_VALIDATED"?"agent accepted":"unresolved"}`,obText(g.purpose),obEl("div","ob-chips",...g.columns.map(c=>obEl("span","",c))));
    })));
  }

  function ontology(s, main) {
    main.append(obText("Each proposed meaning is compared with the existing ontology. New concepts stay candidates; repeated names alone do not prove equivalent meaning.","ob-lead"));
    const all=[...s.available_concepts,...s.concepts];
    let owner=all.find(c=>c.state==="proposed")?.owner || "business", search="", picked=null;
    const graph=obEl("div","ob-ontology-graph"), inspector=obEl("div","ob-inspector"), list=obEl("div");
    const show=c=>{picked=c;obReplace(inspector,obBadge(c.state,c.state),obEl("h4","",c.path),obText(c.definition),
      obFacts([["Owner",c.owner],["Type",c.type],["Used in final mapping",c.used?"Yes":"No"]]),
      obText(c.required_qualifiers?.length?"Required qualifiers: "+c.required_qualifiers.join(", "):"No required qualifiers declared."),
      c.why_not_existing?obDetails("Recorded reuse decision",obText(c.why_not_existing)):null,
      obText("Human review: pending. This is a proposed semantic contract, not a measured probability."));};
    const renderConcepts=()=>{
      const matches=all.filter(c=>c.owner===owner && [c.path,c.definition].join(" ").toLowerCase().includes(search.toLowerCase()));
      const visible=matches.slice(0,8), h=Math.max(240,Math.ceil(visible.length/2)*112+35);
      const svg=obSvg("svg",{viewBox:`0 0 850 ${h}`,class:"ob-concept-svg",role:"group","aria-label":`${obLabel(owner)} ontology concepts`});
      svg.append(obSvg("rect",{x:12,y:h/2-43,width:180,height:86,rx:5,class:"ob-owner-node"}));
      obLines(svg,owner,26,h/2-9,19,"ob-owner-label");svg.append(obSvg("text",{x:26,y:h/2+25,class:"ob-owner-small"},"owning entity type"));
      visible.forEach((c,i)=>{const x=250+(i%2)*300,y=16+Math.floor(i/2)*112;
        svg.append(obSvg("path",{d:`M 192 ${h/2} H 220 V ${y+45} H ${x}`,class:"ob-edge"}));});
      visible.forEach((c,i)=>{const x=250+(i%2)*300,y=16+Math.floor(i/2)*112;
        obSvgButton(svg,x,y,277,96,c.path.split(".").slice(2).join(".") || c.path,c.state,()=>show(c),c.state+(c.used?" · mapped":" · available"));});
      obReplace(graph,svg,obText(`Showing ${visible.length} of ${matches.length} matching concepts. All matches are available below.`));
      obReplace(list,matches.length?obDetails(`Inspect all ${matches.length} matching concepts`,...matches.map(c=>obButton(c.path,()=>{show(c);inspector.scrollIntoView({block:"nearest"});},"ob-concept-link"))):obText("No concepts match this search."));
      if (!picked || !matches.includes(picked)) { if(matches[0])show(matches[0]);else obReplace(inspector,obText("Change the owner or search to inspect a concept.")); }
    };
    const input=obEl("input");input.type="search";input.placeholder="Search concepts or definitions";input.addEventListener("input",()=>{search=input.value;renderConcepts();});
    main.append(obFacts([["Existing base concepts",s.base_concept_count],["New candidate concepts",s.concepts.filter(c=>c.state==="proposed").length],["Existing concepts mapped",s.concepts.filter(c=>c.state==="reused").length]]),
      obEl("div","ob-legend",...[["existing","Existing"],["reused","Reused"],["proposed","Proposed"],["unresolved","Unresolved"]].map(([k,v])=>obBadge(v,k))),
      obEl("div","ob-filter-row",obSelect("Owning entity",[...new Set(all.map(c=>c.owner))].map(o=>[o,obLabel(o)]),owner,v=>{owner=v;renderConcepts();}),obEl("label","ob-select",obEl("span","","Find a concept"),input)),
      graph,inspector,list,
      obBlock("Unresolved or deliberately omitted columns",obText("These declarations include unfinished groups, empty columns and redundant keys. They are not all mapping errors."),
        obDetails(`${s.mapping.unmapped.length} explicit omissions`,obTable(["Column","Recorded reason"],s.mapping.unmapped.map(u=>[u.source_path,u.reason]),"Unmapped columns"))));
    renderConcepts();
  }

  function revisions(s, main) {
    main.append(obText("Open an actual attempt to see its proposal, execution findings and critic decision. Revisions and token counts come from saved checkpoints.","ob-lead"));
    let groupName=s.key==="ip"?"application_status_and_dates":s.key==="acnc"?"ais_lodgement_and_reporting_classification":"employer_identity_and_classification";
    if (!s.history.some(g=>g.name===groupName)) groupName=s.history[0].name;
    let attemptIndex=0; const panel=obEl("div");
    const renderAttempts=()=>{
      const group=s.history.find(g=>g.name===groupName), final=s.groups.find(g=>g.group===groupName), attempts=group.attempts;
      const a=attempts[attemptIndex]; const timeline=obEl("div","ob-attempts");
      attempts.forEach((r,i)=>{const b=obButton("",()=>{attemptIndex=i;renderAttempts();},"ob-attempt");b.setAttribute("aria-pressed",String(i===attemptIndex));
        b.append(obEl("strong","",`${r.pass} · ${r.attempt}`),obEl("span","",r.critic?.verdict || (r.findings.length||r.error||r.schema_errors.length?"Validation stopped":"Draft recorded")),obEl("small","",obCount(r.input_tokens+r.output_tokens)+" tokens"));timeline.append(b);});
      obReplace(panel,obText(group.purpose),obEl("div","ob-inline-status",obBadge(final.status==="AGENT_VALIDATED"?"Group accepted by agent":"Group unresolved",final.status==="AGENT_VALIDATED"?"reused":"unresolved"),
        obText(final.reused_from?"Accepted decisions reused in recovery; no new group calls.":final.feedback?.stop_reason?"Final stop: "+obLabel(final.feedback.stop_reason):"Final status includes all recorded attempts.")),timeline);
      if(!a){panel.append(obText("No attempt checkpoint was recorded for this group."));return;}
      panel.append(obFacts([["Model calls",a.calls],["Input tokens",obCount(a.input_tokens)],["Output tokens",obCount(a.output_tokens)]]));
      if(a.quality)panel.append(obBlock("Executed validation",obFacts([["Emitted observations",obCount(a.quality.emitted_observations)],["Missing-context abstentions",obCount(a.quality.withheld_missing_context)],["Malformed values",obCount(a.quality.malformed_values)],["Technical gate",a.quality.passes_technical_gate?"Passed":"Not passed"]])));
      const findings=[...a.findings.map(f=>f.detail||f.correction||JSON.stringify(f)),...a.schema_errors,a.error].filter(Boolean);
      if(findings.length)panel.append(obBlock("Executable findings",...findings.map(f=>obText(f,"ob-warning"))));
      if(a.critic)panel.append(obBlock("Recorded critic rationale",obBadge(a.critic.verdict,a.critic.verdict==="accept"?"reused":"unresolved"),obText(a.critic.rationale,"ob-quote"),
        ...a.critic.blocking_findings.map(f=>obDetails(f.field,obFacts([["Observed",f.actual],["Expected",f.expected]]),obText(f.evidence),obText(f.correction,"ob-warning"))),
        obDetails("Other findings and semantic risks",...(a.critic.findings||[]).map(obText),...(a.critic.semantic_risks||[]).map(obText)),obText("Agent critique is recorded evidence, not a human verdict.")));
      const changes=obBlock("What changed from the previous mapping");
      if(!a.mapping)changes.append(obText("No mapping response was recorded for this attempt."));
      else if(!a.has_previous_mapping)changes.append(obText("This is the initial recorded mapping for this group. There is no earlier mapping to compare."));
      else if(!a.diff.length)changes.append(obText("The executable field rules are unchanged from the previous recorded mapping."));
      else for (const d of a.diff) {
        const fields=Object.entries(d.changes).map(([key,v])=>obEl("div","ob-diff",
          obEl("h4","",obLabel(key)),obEl("div","ob-diff-columns",
            obEl("div","ob-before",obText("Before"),obCode(v.before)),
            obEl("div","ob-after",obText("After"),obCode(v.after)))));
        changes.append(obDetails(`${d.kind} · ${d.target}`,obText(d.source_paths.join(" + ")),...fields));
      }
      panel.append(changes);
      if(a.mapping)panel.append(obDetails(`Mapping proposal · ${a.mapping.fields.length} rules`,obTable(["Source columns","Target concept","Role","Recorded rationale"],a.mapping.fields.map(f=>[f.source_paths.join(" + "),f.target,f.entity||"subject",f.rationale]),"Attempt mapping rules"),obButton("Download this mapping",()=>obDownload(s.key+"-"+groupName+"-attempt.json",a.mapping))));
      panel.append(obDetails("Checkpoint paths",...a.evidence.map(p=>obText(p,"ob-mono"))));
    };
    main.append(obSelect("Mapping group",s.history.map(g=>[g.name,obLabel(g.name)]),groupName,v=>{groupName=v;attemptIndex=0;renderAttempts();}),panel);renderAttempts();
  }

  function review(s, main) {
    const q=s.test_quality, pending=s.groups.filter(g=>g.status!=="AGENT_VALIDATED");
    main.append(obText("The withheld test checks execution. Business-question checks expose missing scope and disconnected facts. Human semantic precision is still unmeasured.","ob-lead"),
      obBlock("Withheld-test outcome",obFacts([["Test records",s.sampling.partitions.test],["Emitted observations",obCount(q.emitted_observations)],["Missing-context abstentions",obCount(q.withheld_missing_context)],["Malformed values",obCount(q.malformed_values)],["Eligible present values",obCount(q.eligible_present_values)],["Technical gate",q.passes_technical_gate?"Passed":"Not passed"]]),
        obText("A passed technical gate does not establish semantic accuracy or complete coverage."),obDetails("Field-level test evidence",obTable(["Concept","Source present","Emitted","Errors"],s.test_fields.map(f=>[f.target,f.source_present,f.emitted,f.errors]),"Withheld field measurements"))),
      obBlock("Can the candidate answer business questions?",...s.questions.map(q=>obEl("div","ob-question",obEl("div","ob-question-heading",obEl("h4","",q.question),obBadge(obLabel(q.status).toLowerCase(),q.status==="SUPPORTED_IN_CANDIDATE"?"reused":"unresolved")),
        obFacts([["Rows with values",q.rows_with_requested_values],["Meet evidence contract",q.rows_meeting_evidence_contract],["Connected to business",q.rows_connected_to_business]]),
        Object.keys(q.violations_by_row).length?obDetails("Why the contract is not met",obCode(q.violations_by_row)):null))),
      obBlock("Work remaining",...pending.map(g=>obDetails(obLabel(g.group),obText(g.feedback?.stop_reason?obLabel(g.feedback.stop_reason):"Unresolved recorded feedback"),obCode(g.feedback))),
        obText("Check concept meaning, owner, units and period first. Then inspect the source bindings, relationships, examples and abstentions.")));
    const counts={};s.review_queue.forEach(i=>counts[i.kind]=(counts[i.kind]||0)+1);
    let kind="concept", limit=20;const inventory=obEl("div");
    const showItems=()=>{const items=s.review_queue.filter(i=>i.kind===kind);obReplace(inventory,...items.slice(0,limit).map(i=>obDetails(i.key,obBadge(obLabel(i.review_state),"unresolved"),obCode(i.contract),obText("Fingerprint: "+i.fingerprint,"ob-mono"))),items.length>limit?obButton(`Show next ${Math.min(20,items.length-limit)} items`,()=>{limit+=20;showItems();},"ob-button ob-secondary"):null);};
    main.append(obBlock("Human review inventory",obFacts(Object.entries(counts).map(([k,v])=>[obLabel(k)+" contracts",v])),
      obSelect("Contract type",Object.keys(counts).map(k=>[k,obLabel(k)]),kind,v=>{kind=v;limit=20;showItems();}),inventory,
      obButton("Download blank review CSV",()=>obReviewCsv(s)),obText("This page never writes approvals. CSV verdict, reviewer and timing columns are blank for an explicit human review.")),
      obDetails("How review memory is evaluated",obText("The synthetic test repeats unchanged contracts, then changes one binding. It is not a real review or measured time saving."),obFacts([["Unchanged synthetic approvals reused",data.review_simulation.unchanged_repeat.approved_unchanged],["Reopened after one binding change",data.review_simulation.one_changed_binding.changed_requires_review],["Real approvals from synthetic ledger",data.review_simulation.real_approvals_from_synthetic_ledger]])));
    showItems();
  }

  function impact(s, main) {
    main.append(obText("Preview candidate facts beside an existing profile when its ABN appears in this sample. An identifier overlap is a review lead, not an approved merge.","ob-lead"),
      obEl("div","ob-boundary",obBadge("Production unchanged","unresolved"),obText("0 facts merged by this experiment. Role identity, graph semantics and human review still gate integration.")));
    if(!s.examples.length){main.append(obText("No profile-visible example is available in this candidate."));return;}
    let index=0;const body=obEl("div"), provenance=obEl("div","ob-inspector");
    const showClaim=(c,e)=>{obReplace(provenance,obEl("h4","","Provenance: "+c.field),obFacts([["Owner / role",c.entity_kind+" / "+c.entity_role],["Source record",c.source_record_id],["Source row",c.source_row_ordinal]]),
      obText(c.canonical_definition),obCode({value:c.value,raw_value:c.raw_value,source_fields:c.source_fields,qualifiers:c.qualifiers,valid_from:c.valid_from,valid_to:c.valid_to,confidence:c.confidence,snapshot:c.snapshot_sha256,observation_id:c.observation_id}),
      e.join_lineage?obDetails("Original joined-table lineage",obCode(e.join_lineage)):null);provenance.scrollIntoView({block:"nearest"});};
    const renderExample=()=>{const e=s.examples[index];const existing=e.existing_profile;
      obReplace(provenance,obText("Select a candidate fact to inspect its exact source fields, qualifiers, confidence and snapshot."));
      const before=obEl("div","ob-profile-side",obText("Existing profile","eyebrow"),obEl("h3","",existing?.name||"No verified company connection"),
        existing?obFacts(Object.entries(existing.fields).map(([k,v])=>[obLabel(k.replace("entity.","")),v])):obText("This is a source record preview. The experiment has not established a link to one of the existing company profiles."));
      if(existing&&!standalone){const a=obEl("a","ob-link","Open existing profile →");a.href="/?part=profiles&entity="+encodeURIComponent(existing.id);before.append(a);}
      const after=obEl("div","ob-profile-side",obText("Candidate source record","eyebrow"),obEl("h3","",e.label),
        obFacts([["Visible candidate claims",e.claims.length],["Suppressed claims",e.suppressed_claims],["Source row",e.ordinal],["Partition",e.partition]]),
        obText(existing?"Matching source ABN found. Separate source roles are not automatically the business identity.":"Source labels and application attributes are not verified legal company identity.","ob-warning"));
      obReplace(body,obEl("div","ob-profile-compare",before,after),obBlock("Candidate facts, kept at their source scope",
        obTable(["Fact / inspect evidence","Value","Owning role"],e.claims.map(c=>[obButton(obLabel(c.field.split(".").slice(2).join(".")||c.field),()=>showClaim(c,e),"ob-fact-link"),obValue(c.value),c.entity_role]),"Candidate profile facts")),provenance,
        obDetails("Source row behind this preview",obCode(e.source_row)));
    };
    main.append(obSelect("Source-record example",s.examples.map((e,i)=>[String(i),e.label+(e.existing_profile?" · ABN overlap":"")]),"0",v=>{index=Number(v);renderExample();}),body);
    renderExample();
    const comparison=s.key==="ip"?null:data.comparison.find(r=>r.name.toLowerCase()===s.key);
    if(comparison)main.append(obBlock("Does this version improve the result?",obTable(["Measure","Earlier engine","Grouped + recovery"],[["Retained observations",obCount(comparison.baseline_observations),obCount(comparison.new_observations)],["Model tokens",obCount(comparison.baseline_tokens),obCount(comparison.new_tokens)]],"Original versus grouped result"),obText(s.takeaway)));
    if(s.key==="acnc")main.append(obBlock("A cheaper controller-only improvement",obText(`Replaying the original mapping with corrected abstention accounting emits ${obCount(data.ablation.all_records_quality.emitted_observations)} observations and withholds ${obCount(data.ablation.all_records_quality.withheld_missing_context)} missing-context values. No new model calls. This post-hoc technical check is not a production approval.`)));
  }
  render();
}
