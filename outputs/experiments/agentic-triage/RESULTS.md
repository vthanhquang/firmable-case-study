# Agentic triage pilot

The pilot uses the same 20 entries selected from the original 50-dataset shortlist with seed `20261109`. DeepSeek V4 Flash receives the catalogue entry and chooses up to three resource previews. It can keep a dataset, exclude it, or send it to review. A keep decision must cite an inspected row preview or published fields for the resource. The evidence file contains saved publisher previews, field lists, and access failures. The model received field names and counts for tabular previews. Audit labels were joined after decisions were saved.

| Method | Kept | Audit yes among kept | Audit no among kept | Uncertain among kept |
|---|---:|---:|---:|---:|
| Original metadata shortlist | 20 | 11 | 7 | 2 |
| Admit any available row preview or exact publisher field list | 13 | 10 | 3 | 0 |
| Agentic triage | 10 | 10 | 0 | 0 |

The agent kept **10 of the 11** audit positives. It excluded four audit negatives and sent six entries to review. The review group contained one audit positive, three audit negatives, and both uncertain entries. The one deferred positive was the QBCC contract-disclosure CSV. The original resource was blocked and the field list came from a same-named file under a different resource ID.

The agent removed all three audit negatives admitted by the evidence-availability rule. It recognised that the Storage Suppliers CSV contains counts and that the Public Toilet Map names facilities. It held the Taxi and Limousine Licence Values listing for review after the downloads it chose were blocked. A publisher field list for that listing was available in the evidence file, and the agent spent its inspection budget on the download routes.

The reference is the AI-assisted triage audit. The pilot measures screening on these 20 entries using previously collected evidence. A new 50-dataset shortlist would require screening additional candidates and independently auditing a fresh sample.

The evaluated run used **208,942 tokens** over 57 model calls, including recovery, for an estimated **US$0.33** at the repository's historical rate. The initial trial used 164,681 tokens and estimated US$0.26. The initial trial exposed invalid model responses. The evaluated run recovered from a Windows console encoding error by resuming from its saved decisions.

Re-run from the repository root with the configured model credential and a new output directory.

```powershell
python -m firmable.discovery.agentic outputs/experiments/agentic-triage/evidence.json outputs/experiments/agentic-triage/next-run --audit outputs/evaluation/triage_audit_20.csv
```

[Saved evidence](evidence.json) · [Per-dataset decisions and comparison](deepseek-v4-flash-v2/comparison.json) · [Usage](deepseek-v4-flash-v2/run.json) · [Reference audit](../../evaluation/triage_recheck_20.md)
