"""Concise report copy shared by the website, Markdown and LaTeX exports."""


def content(demo, discovery, profiles, original_links, example, cost_summary):
    replay, review = demo["replay"], demo["review"]
    queue_count = sum(replay["unlinked_by_reason"].values())
    deletion = profiles["deletion"]["asic_companies"]
    parts = [
        {"id": "part-1", "title": "Part 1 — Discovery and triage", "destination": "discovery",
         "answer": [
             f"Ranked 50 datasets from {discovery['catalogueCount']:,} deduplicated CKAN records. Outputs retain IDs, titles, publishers, formats, scores and reasons. The 100-point rubric uses business evidence (45), valid identifiers (20), corporate-name patterns (10), business names (10), identifier–name agreement (10) and catalogue category (5); it is not a probability.",
             "Agentic triage assesses actual file previews instead of relying on potentially ambiguous descriptions. Human review confirmed all 20 sampled resources: 0/20 false positives (0% in this sample). The demo shows up to 50 rows per audited resource."]},
        {"id": "part-2", "title": "Part 2 — Schema inference and mapping", "destination": "mapping",
         "selection": ["Six sources provide complementary identity, purpose, financial, service and regulatory data across ZIP/TSV, XLSX, CSV and JSON. ASIC Credit and another ATO year extend coverage to eight extracts/seven families:"],
         "dataset_contributions": [
             {"name": "ASIC Companies", "detail": "Identifiers, current/former names, registration, legal form and status."},
             {"name": "ACNC", "detail": "Charitable purpose, beneficiaries, size bands, websites, contact addresses and operating regions."},
             {"name": "ATO, two years", "detail": "Total income, taxable income and tax payable, with reporting periods."},
             {"name": "DEWR", "detail": "Employment-service programmes, provider sites, addresses and contacts."},
             {"name": "QBCC", "detail": "Contractor identity, licence categories, grades and addresses."},
             {"name": "Victorian Liquor", "detail": "Licensees, permits, licensed premises and capacity."},
             {"name": "ASIC Credit", "detail": "Credit-licence status, dates, permissions and conditions."}],
         "answer": [
             f"One extractor read {demo['columns']['read_by_extension_config']}/{demo['columns']['raw_columns']} columns: {demo['observations']:,} observations from {replay['records']:,} saved rows. Roles separate company facts, contact addresses, sites and licences; unsupported fields remain unmapped. Eight mappings are human-verified, including seven maintainer-corrected configurations: an exception to fully agent-authored mapping."]},
        {"id": "part-3", "title": "Part 3 — Entity identification", "destination": "identity",
         "answer": [
             f"Threshold {replay['threshold']} yields {replay['challenger']['links']:,} links across {replay['challenger']['entities_in_multiple_sources']:,} multi-source entities ({len(original_links):,} links within the original six sources). Each link retains both source-record IDs, canonical key, confidence and evidence. The {queue_count:,}-record unlinked queue explains refusals: weak evidence, ambiguity or conflicting identifiers.",
             "Constrained clusters use ABN, then ACN, then source-record identity as their key anchor; conflicting valid identifiers block merges. Separate licence, site and programme edges preserve one-to-many relationships. Parent/subsidiary ownership is withheld without direct evidence.",
             f"Human-confirmed review found {review['human_verdicts']['pass']}/{review['audit_labelled']} links correct (92%). This rule-stratified, overlap-enriched sample is not a population estimate. Four failures remain flagged in the proposed output; confidence scores are policy scores, not calibrated probabilities."]},
        {"id": "part-4", "title": "Part 4 — Company profiles", "destination": "profiles",
         "selection": ["Fifty profiles combine identity, activities, locations, licences and period-specific finances. Linked-source examples:"],
         "profile_examples": [
             {"name": "The Personnel Group Ltd", "entity_key": "fe_0af37c51f3ce6b18", "detail": "ACNC size and operating regions plus 11 DEWR establishment records reveal its documented service footprint."},
             {"name": "WGA Group Holdings Pty Ltd", "entity_key": "fe_88da5b8124fc8be9", "detail": "ASIC identity plus two ATO years show total income rising from AUD 138.65m to 145.31m; these are tax measures, not profit."},
             {"name": "Chinese Association of Victoria Inc", "entity_key": "fe_4e9aa5a41fed9c58", "detail": "Charitable purpose combines with a licensed-premises record and BYO permit."}],
         "answer": [
             "Core/financial claims retain confidence, provenance, alternatives and selection reasons. Reliability-weighted evidence, bounded corroboration and recency determine winners; unsupported facts are absent. Nested site/licence fields retain observation references but still lack complete merged-confidence objects.",
             f"Removing ASIC changes {deletion['profiles_affected']}/50 profiles: {deletion['fields_removed']} field entries disappear, {deletion['fields_value_changed']} values change and {deletion['no_longer_multi_source']} profiles lose multi-source support. Confidence-only changes are excluded. All 25 financially populated profiles depend on ATO; uncorroborated source errors can survive."]}
    ]
    for part in parts:
        part.update(question="", extra=[], limits=[])
    rate = cost_summary["rates"][0]
    example_cost = (example["input_tokens"] * rate["input"] + example["output_tokens"] * rate["output"]) / 1_000_000
    part5 = [
        {"title": "1. Cost", "show_cost_table": True,
         "answer": [f"One ASIC onboarding run took {example['wall_seconds']//60}m {example['wall_seconds']%60}s and used {example['input_tokens']:,} input / {example['output_tokens']:,} output tokens: US${example_cost:.4f} estimated, included above. Subsequent per-record model cost is zero; compute/storage costs were not measured."]},
        {"title": "2. Agent design", "answer": [
            "Inspect files, test readers, profile samples, propose mappings, validate held-out rows, critique semantics, revise, then seek human approval. This separates format, execution and interpretation errors. Provider errors retry; exhausted runs checkpoint. Humans see rules, samples, confidence, unmapped fields and validation/critic findings. Semantics is weakest: seven executable mappings needed corrections, including contact addresses treated as sites."]},
        {"title": "3. The hard one", "answer": [
            "ASIC supplied a ZIP with tab-separated .csv data and historical-name rows. Reader settings and conditional mappings handle both. Use a custom reader only when the shared configuration cannot represent a format reliably; preserve the canonical output contract."]},
        {"title": "4. Scale", "answer": [
            "Acquisition fails first: three of nine initial attempts hit HTTP errors or bot challenges; QBCC's fallback was a biased 32k-row prefix. At 500 sources, add publisher queues, pagination, caching, retry limits and schema/freshness checks. Review needs prioritisation; matching needs persistent candidate indexes and incremental processing."]},
        {"title": "5. Change", "answer": [
            "Preserve immutable snapshots/observations, mapping/model/policy versions, candidate evidence, scores, refusals, memberships and human decisions. Run both matchers on identical evidence; compare changed links and cluster splits/merges. Evaluate frozen human labels, review high-impact differences and promote gradually. Rebuild affected profiles, retain old memberships for rollback and publish key aliases/tombstones. Reuse human decisions only while evidence remains applicable.",
            "The implemented comparison retains 1,205 links, adds 250 and removes 363. Evidence-bound review journals exist; automatic corrections, persistent membership history and production rollback remain future work."]},
        {"title": "6. Next", "answer": [
            "Week 1: regressions for four failed links and reviewed cluster corrections. Week 2: reliable fetching, schema-drift detection and review/resume controls. Week 3: nested-field confidence, financial-corruption testing and matcher migration with rollback. Correct known errors before scaling."]}
    ]
    for item in part5:
        item["question"] = ""
    return parts, part5
