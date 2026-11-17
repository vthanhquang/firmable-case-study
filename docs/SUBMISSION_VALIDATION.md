# Submission verification — 17 November 2026

The final staged repository was exported into a fresh directory using `git checkout-index`. No ignored downloads, HTTP cache, local environment files or Python packages were copied into that directory. Dependencies were installed from `requirements.txt` into a new CPython 3.11 virtual environment on Windows. All replay commands ran with `FIRMABLE_OFFLINE=1` and without provider credentials.

| Check | Result |
| --- | --- |
| Restore the committed fixtures and verify SHA-256 | Pass; 1.23 s |
| `python -m firmable.cli raw-replay --sync-demo` | Pass; 106.59 s |
| `python scripts/submission.py verify` | Pass; 3.67 s |
| `python -m pytest -q` | 169 passed, 1 skipped; 12.67 s test time |
| Website JavaScript checks and static build | Pass |
| Source-pair graph tests | 3 passed |
| Standalone HTML report | Rendered and visually inspected; all Parts 1–5 and architecture included |
| Relative documentation links | No missing local targets |
| Repository credential scan | No API-key/private-key patterns or credential files found |
| Existing Git history credential scan | 3,013 blobs checked; no matching patterns |
| GitHub single-file size limit | No tracked file exceeds 100 MB |

Preparation, replay, verification and the test process took approximately 126 seconds after dependency installation. Installation succeeded from the pinned requirements; download speed and hardware affect total time. The ten-minute workflow covers the frozen replay, not fresh model inference or full publisher downloads.

## Reproduction results

- 50 shortlisted datasets; the reviewed JSONL shortlist retains its recorded byte hash.
- Eight mapping configurations retain valid human approvals and unchanged interpretation dependencies.
- 85,446 canonical observations from 7,744 saved records.
- 1,455 proposed links, 1,245 deliberately unlinked records and 50 profiles.
- Proposed links, unlinked queue and the 50 profiles are **byte-identical** to the submitted files.
- All source observations are identical after excluding the new `ingested_at` timestamp.
- Human review remains **46 pass / 4 fail out of 50**, with unchanged evidence bindings. The four failures remain in the proposed set.
- Part 1 human audit remains **20 positives / 20**, with no observed false positives.
- Both historical token ledgers are unchanged; no model call was made.

The skipped test is the optional serial/parallel equivalence check requiring the full original QBCC baseline snapshot. That full file is not part of the frozen sample bundle. The distinct second QBCC snapshot is included for change detection.

## Fixes found during submission preparation

1. The old `data/` ignore rule also excluded `frontend/data/`. It now ignores only root `/data/`, so browser snapshots are committed.
2. The report generator now resolves its shared content module when invoked through the replay's `runpy` path.
3. Historical dependency paths written on Windows are normalised for comparison on other platforms, retaining their content hashes.
4. Archived output, run and correction-bundle bytes are exempt from Git line-ending conversion, preserving evidence hashes.
5. Direct DeepSeek uses an explicit environment key and its current endpoint/model defaults. Mocked HTTP tests cover the request contract; live provider authentication was not tested or billed.
6. Active cost metrics now use the same declared off-peak estimate as the report, without the superseded adjustment.

The GitHub Actions workflow repeats the replay, tests and frontend checks on Ubuntu with no API secrets. Local Windows results above do not by themselves establish the remote CI outcome.
