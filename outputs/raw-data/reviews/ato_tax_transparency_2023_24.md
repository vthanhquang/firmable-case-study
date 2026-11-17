# Extension mapping review: `ato_tax_transparency_2023_24`

- **Status:** PENDING_REVIEW - awaiting a human decision (run `20261112T205715-4a9edc`, prompt `ext-prompts-v1`, model `deepseek-v4-flash`, critic `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency - 2023-24 Report of Entity Tax Information - Australian Taxation Office; snapshot sha256 `6b47837efab92e1eb2b0cacc46945376a5b185c1b16814146c3282a1921b0c75`
- **Extends approved mapping:** run `20261112T205404-d08c5f`, digest `25a340246ac8b541`; registry `ext-v1` (draft concept definitions)
- **Agent effort:** 1 proposal(s), 9 tool calls, 6 model calls, 62,017 prompt + 5,724 completion tokens, 105s model time

- **Proposal digest:** `244af1f30398ffc614cf5a08be2c16412071bacf19c7c9bdbaa62dece844736c` (round 0)

## What changes relative to the approved mapping

- 3 rule(s) added (table below)

## Added and changed rules

| # | target | role | source columns | transform | qualifiers | conf. | held-out present / emitted / errors / dropped | rationale |
|---|---|---|---|---|---|---|---|---|
| 2 | `ext.financial.total_income` | subject | Total income $ | parse_decimal | currency=AUD, period=col:Income year | 0.9 | 1075 / 1075 / 0 / 0 | Total income as published for the income year; every row populated, integer dollar amounts. |
| 3 | `ext.financial.taxable_income` | subject | Taxable income $ | null_if -> parse_decimal | currency=AUD, period=col:Income year | 0.9 | 844 / 844 / 0 / 0 | Taxable income for the income year; 76% populated, blanks mean not published (not zero), so null_if runs first. |
| 4 | `ext.financial.tax_payable` | subject | Tax payable $ | null_if -> parse_decimal | currency=AUD, period=col:Income year | 0.9 | 794 / 794 / 0 / 0 | Tax payable for the income year; 72% populated, blanks are missing not zero. |

## Held-out validation (rules in this review)

- no issues

## Critic

> All three added rules are financial facts for the income year, correctly typed as decimals, correctly qualified with currency AUD and the period taken from the same row's Income year column, and correctly suppressed when the cell is blank rather than emitted as zero. The income year strings (2023-24, 2022-23) are passed through unaltered as period labels, which is acceptable since the ontology only requires a period qualifier and the value is unambiguous for an Australian income year. No validity, status, name, identifier or address concepts were introduced, so the usual failure modes (trading name as legal name, licence number as identifier, premises vs entity address, deregistered status with valid_to, record-level validity) do not arise here. The only caution worth noting is that the held-out evidence does not exercise the '-'/'n/a' null sentinels declared in the null_if steps, so those remain unverified against real values; this does not make the rules as written wrong. The three empty columns (column_6 to column_8) are correctly listed as unmapped.


## Still unmapped

- `column_6`: Entirely empty in all 527 profiled rows (present_rate 0.0); no values to map.
- `column_7`: Entirely empty in all 527 profiled rows (present_rate 0.0); no values to map.
- `column_8`: Entirely empty in all 527 profiled rows (present_rate 0.0); no values to map.

## Decide

```
python -m firmable.cli raw-approve ato_tax_transparency_2023_24 --reviewer "<your name>"
python -m firmable.cli raw-approve ato_tax_transparency_2023_24 --reviewer "<your name>" --reject --comment "why"
```
