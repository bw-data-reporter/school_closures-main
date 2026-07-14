# Report: Estimating real school closures since 2000

## Bottom line

The most defensible estimate from the attached dataset is **2,507 real closures since 2000**.

That comes from starting with the dataset's **2,781** records flagged `ClosedSince2000 = True`, then subtracting **274 high-confidence continuation / duplicate cases** where a closed entity appears to have a currently active counterpart rather than representing a real closure.

A more aggressive version of the method would also subtract medium-confidence matches, producing **2,398** closures. I would not use that as the lead estimate without manual review.

## Why this method is strongest

The core problem is that an entity can be marked closed in the state directory even when the school operation seems to continue under a different entity code, name, configuration, or location record. The dataset itself contains enough fields to identify many of those administrative closures at scale: entity names, physical addresses, mailing addresses, phone numbers, emails, open dates, close dates, county, and district.

The strongest approach is therefore not to discard all "closed" flags, and not to rely on one field like name or address alone. It is to identify closed records that match active records on multiple continuity signals.

## Method used

1. Loaded `all_schools.csv` and normalized names, root names, emails, phone numbers, physical addresses, mailing addresses, counties, districts, open dates, and close dates.
2. Used the dataset's `ClosedSince2000` flag as the baseline, because it captured two records marked `Close - Pending` with close dates of June 30, 2026 that a strict `EntityStatus = Closed` filter would miss.
3. Compared every closed-since-2000 record against currently active records using these signals:
   - exact same normalized name in same county;
   - same simplified/root name in same county;
   - high fuzzy name similarity in same county;
   - same non-generic email address;
   - same phone number;
   - same physical address;
   - same mailing address;
   - active/open date consistent with a continuation window.
4. Downweighted generic or system-like contact fields, such as blank emails and placeholder emails like `none@none.com`.
5. Classified matches as high, medium, or low confidence.
6. Recommended subtracting **only high-confidence matches** from the baseline count.

## Results

| Measure | Count |
|---|---:|
| Total rows in dataset | 6,716 |
| Active records | 3,934 |
| `ClosedSince2000 = True` baseline | 2,781 |
| Strict closed-status + close date since 2000 | 2,779 |
| High-confidence continuation / duplicate cases | 274 |
| Recommended estimate: real closures | 2,507 |
| Medium-or-high continuation candidates | 383 |
| Aggressive estimate if medium candidates are also excluded | 2,398 |
| Any low-or-better continuation candidates | 733 |

## Why not just use the closed flag?

There are many cases where a closed record matches an active record closely enough to suggest a state directory/entity-code change rather than a real closure. Examples in the candidate file include records with the same school name, same address, same mail address, and sometimes the same email/phone.

## Why not subtract all duplicate-ish records?

Address reuse alone is risky. A new school can occupy an old school building, and that may still represent a real closure. The recommended estimate subtracts only high-confidence matches, where multiple signals point to continuity. Medium and low matches should become a manual-review queue, not automatic exclusions.

## Caveats

- This is a dataset-driven estimate, not a row-by-row web verification.
- Some true closures may be hidden among medium/low matches if schools changed names or reorganized substantially.
- Some high-confidence matches may still represent a real closure followed by a replacement school, especially where the main evidence is shared address rather than shared identity.
- Preschool/nursery/co-op entities are included because they are present in the dataset. There are 171 closed-since-2000 records with names suggesting preschool/nursery/co-op/child-care entities. Whether to count those depends on the story definition of “school closure.”

## Recommended wording

> A state school directory lists 2,781 Michigan school entities as closed since 2000. But after removing 274 records that appear to be duplicative or administrative closures — cases where the school seems to continue under an active record with the same name, address, contact information, or other continuity signals — the best conservative estimate is about 2,507 real closures. A broader review queue could lower that estimate to roughly 2,398 if medium-confidence continuation cases are confirmed.

## Files produced

- `closed_since_2000_classified.csv`: every closed-since-2000 record with match confidence, matched active entity, reasons, and recommended inclusion flag.
- `closure_continuation_candidates.csv`: the candidate duplicate/continuation matches only.
- `closure_analysis_summary.json`: summary counts, date distributions, and examples.
