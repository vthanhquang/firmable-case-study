const n = value => new Intl.NumberFormat("en-AU").format(value);
const escape = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
const types = {
  code: ["CODE", "#ffffff", "#cbd3c9"],
  ai: ["AGENT", "#e7f0e8", "#80a58a"],
  mixed: ["AGENT + CODE", "#e7f0e8", "#80a58a"],
  human: ["HUMAN", "#fbf2df", "#b39354"],
  store: ["SAVED", "#edf0f2", "#99a8b2"],
};
const stage = number => `/?part=onboarding&stage=${number}`;

export function architectureLanes(data) {
  const node = (title, lines, kind, href) => ({title, lines, kind, href});
  return [
    { title: "Acquire source evidence", subtitle: "SHARED INPUTS / Files and evidence, before any semantic inference", y: 82, part: "discovery",
      nodes: [
        node("Discover + rank", ["Catalogue + row previews", "Coded shortlist of 50"], "code", "/?part=discovery"),
        node("Audit + select", ["20-resource human audit", "Select useful source files"], "human", "/?part=discovery"),
        node("Freeze the source", ["File hash + retrieval date", "Licence + publisher origin"], "store", stage(1)),
        node("Register new inputs", ["Single or related tables", "Source ID + documentation"], "code", stage(1)),
        node("Retain raw evidence", ["Original rows and headers", "Reproducible source lineage"], "store", stage(1)),
      ],
      branches: ["Existing approved sources retain their established mapping configs; new-source experiments follow the path below."] },
    { title: "Understand the incoming dataset", subtitle: "EXPERIMENT / Inspector, optional join planner and shared readers", y: 374, part: "onboarding",
      nodes: [
        node("Inspector agent", ["Choose reader + sheet", "Explain grain and identifiers"], "ai", stage(2)),
        node("Shared reader", ["Preserve physical columns", "Keep contextual year headers"], "code", stage(2)),
        node("Optional join plan", ["Agent proposes typed keys", "Code checks cardinality"], "mixed", stage(2)),
        node("Freeze partitions", ["Discovery / validation / test", "Separate final-test evidence"], "code", stage(2)),
        node("Inspection artifacts", ["Grain + header contract", "Sample + joined-row lineage"], "store", stage(2)),
      ],
      branches: ["Join checks: missing keys, duplicate keys and row multiplication. Unsafe matches are refused with reasons.",
        "Implemented joins: one-to-one / many-to-one star joins. Other shapes require an extension."] },
    { title: "Reason and revise one column group", subtitle: "EXPERIMENT / Model decisions become executable rules through a shared compiler", y: 690, part: "onboarding", loop: true,
      nodes: [
        node("Group planner", ["Partition every column", "Declare roles + relationships"], "ai", stage(3)),
        node("Ontology architect", ["Retrieve existing concepts", "Reuse or propose meanings"], "mixed", stage(4)),
        node("Mapper + compiler", ["Agent writes semantic intent", "Code compiles the mapping"], "mixed", stage(5)),
        node("Validator + critic", ["Execute validation rows", "Critique emitted meanings"], "mixed", stage(5)),
        node("Group checkpoint", ["Retain accepted decisions", "Stop unresolved groups"], "store", stage(5)),
      ],
      branches: ["Revision returns to mapping, ontology, or both. Repeated proposals and token budgets can stop a group.",
        "Up to 3 group attempts per pass; recovery reuses accepted work. Missing required context is counted as abstention."] },
    { title: "Reconcile, evaluate and request review", subtitle: "EXPERIMENT / A technically valid candidate is still not a human-approved company fact", y: 1054, part: "onboarding",
      nodes: [
        node("Reconcile groups", ["Compile accepted intents", "Check combined constraints"], "code", stage(5)),
        node("Withheld test", ["Execute unseen test partition", "Separate errors / abstentions"], "code", stage(6)),
        node("Candidate artifacts", ["Versioned ontology + rules", "Claims, edges and refusals"], "store", stage(6)),
        node("Business questions", ["Scope + period requirements", "Check paths to a business"], "code", stage(6)),
        node("Review + memory", ["Concept / binding / relation", "Explicit reviewer decisions"], "human", stage(6)),
      ],
      branches: ["Review memory compares contract fingerprints: unchanged approvals may be reused; changed contracts reopen.",
        "The recorded review-memory evaluation uses synthetic decisions. Human precision and review time remain unmeasured."] },
    { title: "Resolve businesses with the established engine", subtitle: "EXISTING CORE / Approved source configs; deterministic extraction and identity resolution", y: 1510, part: "identity",
      nodes: [
        node("Verified configs", ["Existing Part 2 workflow", "8 human-verified mappings"], "store", "/?part=mapping"),
        node("Extract claims", [n(data.replay.records) + " saved records", n(data.observations) + " observations"], "code", "/?part=mapping"),
        node("Find candidates", ["ABN / ACN / name evidence", "Keep relationship types"], "code", "/?part=identity"),
        node("Link + cluster", ["Threshold 0.85", n(data.replay.challenger.links) + " proposed links"], "code", "/?part=identity"),
        node("Audit proposed links", ["46 / 50 correct = 92%", "4 failed links stay flagged"], "human", "/?part=identity"),
      ],
      branches: ["Refusal branch: 1,245 unlinked records keep reasons. Audit labels do not automatically correct cluster membership."] },
    { title: "Build profiles with traceable claims", subtitle: "EXISTING CORE / Deterministic profile assembly; no additional model calls", y: 1826, part: "profiles",
      nodes: [
        node("Group by scope", ["Business / establishment", "Licence / financial period"], "code", "/?part=profiles"),
        node("Handle conflicts", ["Choose by evidence strength", "Keep alternatives + reasons"], "code", "/?part=profiles"),
        node("Assemble profiles", ["50 company profiles", "Field confidence + origins"], "code", "/?part=profiles"),
        node("Measure dependence", ["Remove a source + rebuild", "Compare claims and links"], "code", "/?part=write-up"),
        node("Inspect the evidence", ["Company + source graphs", "Field-level source citations"], "store", "/?part=profiles"),
      ],
      branches: ["Experimental profile previews are separate: matching a source ABN is a review lead, not an approved merge.",
        "Remaining core limitations include incomplete nested-field confidence and untested financial-source corruption."] },
  ];
}

export function architectureSvg(data) {
  const lanes = architectureLanes(data);
  const text = (x,y,value,size=16,weight=400,fill="#17231e") => `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}">${escape(value)}</text>`;
  const arrow = (d,dashed=false) => `<path d="${d}" fill="none" stroke="#63816e" stroke-width="2" ${dashed?'stroke-dasharray="6 5"':''} marker-end="url(#architecture-arrow)"/>`;
  const out = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 2260" role="img" aria-labelledby="arch-title arch-desc" font-family="Arial, sans-serif">',
    '<title id="arch-title">Current Firmable architecture: grouped ontology onboarding and the established company-profile pipeline</title>',
    '<desc id="arch-desc">Six lanes show source evidence, inspection and optional joins, a bounded group-agent revision loop, candidate evaluation and human review, established identity resolution, and company profiles. The experimental candidate path stops at a production boundary. Automatic promotion is not implemented. Existing approved configurations feed the core resolution pipeline separately. Saved source, mapping and ontology identities preserve provenance.</desc>',
    '<defs><marker id="architecture-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#63816e"/></marker></defs>',
    '<rect width="1280" height="2260" rx="10" fill="#f8f8f4"/>',
  ];
  ["code","ai","mixed","human","store"].forEach((key,i)=>{
    const [label,bg,stroke]=types[key],x=40+i*220;
    out.push(`<rect x="${x}" y="22" width="18" height="18" rx="3" fill="${bg}" stroke="${stroke}"/>`,text(x+28,36,label,13,600,"#4a554e"));
  });
  lanes.forEach((lane,i)=>{
    const y=lane.y;
    out.push(text(40,y+18,String(i+1).padStart(2,"0"),24,700,"#235444"),text(91,y+18,lane.title,24,700),text(91,y+44,lane.subtitle,13,400,"#4a554e"));
    lane.nodes.forEach((node,j)=>{
      const x=40+j*245,top=y+68,[label,bg,stroke]=types[node.kind];
      out.push(`<a href="${escape(node.href)}" aria-label="${escape(node.title)}"><g>`,
        `<rect x="${x}" y="${top}" width="220" height="122" rx="6" fill="${bg}" stroke="${stroke}" stroke-width="${node.kind==='human'?2:1.4}"/>`,
        text(x+13,top+23,label,11,700,"#4a554e"),text(x+13,top+50,node.title,17,700),
        ...node.lines.map((line,k)=>text(x+13,top+77+k*21,line,13.5,400,"#4a554e")), '</g></a>');
      if(j<4)out.push(arrow(`M ${x+220} ${top+61} H ${x+239}`,i===4&&j===3));
    });
    if(lane.loop){
      out.push(arrow(`M 885 ${y+190} V ${y+219} H 395 V ${y+195}`,true),arrow(`M 640 ${y+219} V ${y+195}`,true),text(438,y+243,"Targeted repair: mapping / ontology / both",13,600,"#235444"));
    }
    const noteY=y+(lane.loop?275:224);
    lane.branches.forEach((note,k)=>out.push(text(40,noteY+k*24,note,13.5,400,"#4a554e")));
    if([0,1,2,4].includes(i)){
      const next=lanes[i+1].y;
      out.push(arrow(i===4?`M 885 ${y+190} V ${next-24} H 20 V ${next+129} H 35`:`M 1244 ${y+129} H 1262 V ${next-24} H 20 V ${next+129} H 35`));
    }
  });
  out.push('<rect x="40" y="1384" width="1200" height="82" rx="6" fill="#fff5e4" stroke="#b39354" stroke-dasharray="7 5"/>',
    text(58,1411,"PRODUCTION BOUNDARY — NO AUTOMATIC PROMOTION",14,700,"#78531b"),
    text(58,1437,"Experimental candidates remain separate. Human contract approval does not implement identity integration or release.",14,400,"#78531b"),
    '<rect x="40" y="2160" width="1200" height="70" rx="6" fill="#e9eee7"/>',
    text(58,2185,"SHARED EVIDENCE / REPLAY / GOVERNANCE",13,700,"#235444"),
    text(58,2210,"Snapshot + row ID → ontology version + mapping digest → observation + relationship → link decision → profile claim",15),
    '</svg>');
  return out.join("");
}

export function architectureView(data, root, ui, onboarding) {
  const {el,copy,siteLink}=ui;
  root.classList.add("architecture-current");
  const download=el("a","source-link","Download current architecture · SVG ↓");
  download.href="/system-architecture.svg";download.download="firmable-system-architecture.svg";
  const pngDownload=el("a","source-link","Download architecture · PNG ↓");
  pngDownload.href="/system-architecture.png";pngDownload.download="firmable-system-architecture.png";
  const png=el("img","architecture-png");
  png.src="/system-architecture.png";png.width=2560;png.height=4520;
  png.alt="Current system architecture: source acquisition, inspection and joins, grouped ontology agents, evaluation and human review, established entity resolution and company profiles. Experimental candidates remain outside production.";
  const imageLink=el("a","architecture-image-link",png);
  imageLink.href="/system-architecture.png";imageLink.target="_blank";imageLink.rel="noopener";
  imageLink.setAttribute("aria-label","Open architecture PNG at full resolution");
  const graphic=el("div","architecture-graphic");graphic.innerHTML=architectureSvg(data);
  const mobile=el("div","architecture-mobile",...architectureLanes(data).map((lane,i)=>{
    const content=el("details","architecture-mobile-lane");
    content.open=i===0;
    content.append(el("summary","",String(i+1).padStart(2,"0")+" · "+lane.title),copy(lane.subtitle),
      el("ol","architecture-steps",...lane.nodes.map(node=>{
        const a=el("a","source-link",node.title);a.href=node.href;
        return el("li","architecture-step "+node.kind,el("span","step-kind",types[node.kind][0]),a,copy(node.lines.join(" · ")));
      })),...lane.branches.map(note=>el("p","architecture-branch-note",note)));
    if(i===3)content.append(el("p","architecture-boundary","Production boundary: automatic promotion is not implemented. Candidate facts remain outside the established profile pipeline."));
    return content;
  }));
  const boundary=el("p","architecture-boundary","Current boundary: the grouped ontology pipeline saves reviewable candidates. It does not automatically promote them into the existing entity-resolution and profile pipeline.");
  const evidence=el("section","architecture-evidence",el("h2","","Recorded evidence behind this architecture"),
    copy("These development-source experiments expose partial results. Group acceptance is an agent verdict; business connectivity is measured separately from extraction."));
  if(onboarding){
    const rows=onboarding.sources.map(s=>{
      const a=el("a","source-link",s.name);a.href=stage(6)+"&dataset="+s.key;
      return [a,`${s.metrics.accepted_groups} / ${s.metrics.groups}`,n(s.metrics.observations),n(s.metrics.business_connected_observations),n(s.review_queue.length)];
    });
    const table=el("table","preview-table",el("caption","sr-only","Recorded ontology experiments"),
      el("thead","",el("tr","",...["Source","Agent-accepted groups","Observations","Business-connected","Review contracts"].map(label=>{const th=el("th","",label);th.scope="col";return th;}))),
      el("tbody","",...rows.map(row=>el("tr","",...row.map(value=>el("td","",value))))));
    const scroll=el("div","table-scroll",table);scroll.tabIndex=0;scroll.setAttribute("role","region");scroll.setAttribute("aria-label","Recorded ontology experiments");
    evidence.append(scroll,copy("All three candidate runs still require review. Their experiments added zero production facts; human semantic precision and review time are not measured."));
  }
  const implementation=el("details","architecture-implementation",el("summary","","Implementation and scope"),
    copy("Inspector and shared readers: firmable/evolution + firmable/sources. Group planner, architect, mapper and critic: evolution2/pipeline.py. Typed compilation: evolution2/contracts.py. Join checks: evolution2/joins.py. Abstention, retrieval and progress guards: evolution2/quality.py. Contract memory: evolution2/review.py. Business questions: evolution2/questions.py."),
    copy("Agents share one model interface and run in a bounded controller; the diagram does not imply parallel workers. Existing concepts are retrieved lexically, then judged for semantic fit. The registry and evidence are local versioned files; no Apache, Docker, vector database or external graph database is required."),
    copy("The original Part 2 engine remains available. Grouping is experimental, not the default replacement: the earlier WGEA run retained more observations at lower cost. New ontology contracts, source bindings and business identities still need separate review."));
  root.replaceChildren(el("section","overview assignment-intro",el("p","eyebrow","Current implementation · Core workflow + research extension"),
    el("h1","","How a new source becomes company intelligence"),
    el("p","intro","Inspect the data, propose its meaning, execute and revise the mapping, then review what is safe to use. Every decision keeps its source evidence."),
    el("div","answer-actions",pngDownload,download,siteLink("Follow a dataset through the agents","onboarding"))),imageLink,boundary,
    el("details","architecture-explorer",el("summary","","Explore the interactive architecture"),graphic,mobile),evidence,implementation);
}
