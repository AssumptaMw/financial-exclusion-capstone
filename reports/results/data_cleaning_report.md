# FinAccess data cleaning and preparation report

Generated (UTC): 2026-11-19T07:54:30.130812+00:00

## Scope and input

- Input: `data/interim/finaccess_selected.parquet`
- Output: `data/processed/finaccess_adults_unprepared.parquet`
- Input records: 20,871
- Prepared records: 19,746
- Selected columns retained, in source order: 23
- Input SHA-256: `bf12f1121bf08fadda74e111078744d8b3ef2aa89a3bff7ea09b3cd1fb998d41`
- The source interim Parquet was read-only; no source values or labels were rewritten.

## Row eligibility and counts

| A18 disposition | Records | Handling |
|---|---:|---|
| Adult age (18+, excluding documented special codes) | 19,746 | Retained |
| Under 18 | 1,121 | Excluded from this adult-only file |
| A18 = 98 (Don't know) | 2 | Excluded; age eligibility is unresolved |
| A18 = 99 (Refused) | 2 | Excluded; age eligibility is unresolved |
| Missing A18 | 0 | Excluded if present; no value was imputed |
| Invalid A18 | 0 | Excluded if present; no value was imputed |

Age codes 98 and 99 are treated as special responses based on the verified questionnaire coding recorded in `documentation/data_dictionary.md`. Only these field-specific codes are treated specially; values 96 and 97 were not recoded, and no maximum age was imposed. Respondents aged 100 or older were retained when their recorded age met the rule.

## Field-level value and missingness audit

Parquet nulls are counted separately from preserved Excel error strings such as `#NULL!`. Text responses such as Refused and Don't know are reported as observed categories, not silently mapped to null. The value summary describes the adult-only output; Excel error counts show input → output, to make any age-filter effect visible.

| Original field | Parquet type | Adult distinct values | Parquet nulls (input → adult) | Excel error tokens (input → adult) | Adult observed values / summary |
|---|---|---:|---:|---:|---|
| `county` | `string` | 47 | 0 → 0 | 0 → 0 | 47 distinct values; most frequent: `Nairobi City`: 613; `Meru`: 611; `Nakuru`: 542; `Kakamega`: 539; `Kiambu`: 518 |
| `A07` | `int64` | 1,849 | 0 → 0 | 0 → 0 | 1,849 distinct values; numeric range 1–1849; most frequent: `1020`: 15; `1648`: 15; `442`: 15; `691`: 15; `125`: 15 |
| `A08` | `string` | 2 | 0 → 0 | 0 → 0 | `Rural`: 12,737; `Urban`: 7,009 |
| `A18` | `int64` | 86 | 0 → 0 | 0 → 0 | 86 distinct values; numeric range 18–105; most frequent: `30`: 804; `40`: 653; `28`: 646; `35`: 624; `32`: 618 |
| `Sex` | `string` | 2 | 0 → 0 | 0 → 0 | `Female`: 11,736; `Male`: 8,010 |
| `A20` | `string` | 13 | 0 → 0 | 0 → 0 | `"Secondary completed "`: 4,063; `"Primary completed"`: 3,802; `"Some primary "`: 3,566; `"None "`: 3,018; `"Some secondary"`: 2,045; `Completed technical training after secondary school`: 1,421; `"University completed "`: 988; `Some technical training after secondary school`: 491; `Some university`: 344; `"Refused to Answer (DO NOT READ OUT)"`: 3; `"Other (Specify) "`: 2; `"Don't know (DO NOT READ OUT)"`: 2; `95`: 1 |
| `A24i` | `string` | 5 | 0 → 0 | 2 → 2 | `No- no difficulty`: 16,734; `Yes - some difficulty`: 2,440; `Yes - a lot of difficulty`: 553; `Cannot do at all`: 17; `#NULL!`: 2 |
| `A24ii` | `string` | 5 | 0 → 0 | 2 → 2 | `No- no difficulty`: 18,778; `Yes - some difficulty`: 800; `Yes - a lot of difficulty`: 162; `Cannot do at all`: 4; `#NULL!`: 2 |
| `A24iii` | `string` | 5 | 0 → 0 | 1 → 1 | `No- no difficulty`: 17,787; `Yes - some difficulty`: 1,423; `Yes - a lot of difficulty`: 517; `Cannot do at all`: 18; `#NULL!`: 1 |
| `A24iv` | `string` | 4 | 0 → 0 | 0 → 0 | `No- no difficulty`: 18,752; `Yes - some difficulty`: 859; `Yes - a lot of difficulty`: 130; `Cannot do at all`: 5 |
| `A24v` | `string` | 5 | 0 → 0 | 2 → 2 | `No- no difficulty`: 19,096; `Yes - some difficulty`: 489; `Yes - a lot of difficulty`: 135; `Cannot do at all`: 24; `#NULL!`: 2 |
| `A24vi` | `string` | 5 | 0 → 0 | 7 → 7 | `No- no difficulty`: 19,303; `Yes - some difficulty`: 316; `Yes - a lot of difficulty`: 117; `#NULL!`: 7; `Cannot do at all`: 3 |
| `B3A__2` | `int64` | 2 | 0 → 0 | 0 → 0 | `0`: 17,229; `1`: 2,517 |
| `B3A__4` | `int64` | 2 | 0 → 0 | 0 → 0 | `0`: 15,811; `1`: 3,935 |
| `B3Ii` | `string` | 232 | 0 → 0 | 2,378 → 2,044 | 232 distinct values; numeric range 100–200000; workbook special-value labels 98: 0, 99: 0; most frequent: `#NULL!`: 2,044; `5000`: 1,663; `2000`: 1,570; `3000`: 1,523; `10000`: 1,387 |
| `S1` | `string` | 6 | 0 → 0 | 44 → 44 | `I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia`: 16,679; `I donâ€™t own a mobile phone but am able to use someone elseâ€™s phone regularly`: 1,325; `I donâ€™t own or use a mobile phone/Sina wala situmii simu ya mkononi`: 1,249; `I own a mobile phone that both me and others use/Nina simu ya mkononi ambayo mim`: 445; `#NULL!`: 44; `Refused to Answer (DO NOT READ OUT)/Kataa kujibu`: 4 |
| `S2__1` | `string` | 3 | 0 → 0 | 1,785 → 1,299 | `0`: 9,659; `1`: 8,788; `#NULL!`: 1,299 |
| `S3` | `string` | 7 | 0 → 0 | 44 → 44 | `Never/Situmii"`: 9,029; `Daily/"Kila siku"`: 5,945; `Less ofteN/Mara kwa mara"`: 2,342; `Weekly/Kila wiki"`: 1,999; `Monthly/Mara moja kwa mwezi"`: 368; `#NULL!`: 44; `Refused to Answer/Kataa kujibu`: 19 |
| `S4` | `string` | 11 | 0 → 0 | 8,486 → 7,949 | `On my own mobile phone/ Cellular tablet/Kwenye simu ya rununu/simu ya mkononi"`: 9,297; `#NULL!`: 7,949; `On a friend or neighbourâ€™s computer/tablet where I did not pay/"Kwenye kompyut`: 1,018; `Refused to Answer/"Kataa kujibu"`: 473; `On someone elseâ€™s mobile phone where I paid/Kwenye simu ya mtu mwingine ambapo`: 439; `At an internet cafÃ©/"Eneo ya biashara ya mtandao"`: 289; `On a friend or neighbourâ€™s computer/tablet where I paid/"Kwenye kompyuta /Simu`: 116; `At home on a computer/ noncellular tablets/Kompyuta iliyo nyumbani/ simu isiyo y`: 64; `On a television set/Kwenye runinga"`: 54; `On computers at the office /workplace/Kwenye computer iliyo ofisini"`: 46; `Other (SPECIFY)/"Nyingine (taja)"`: 1 |
| `indWeight` | `double` | 13,642 | 0 → 0 | 0 → 0 | 13,642 distinct values; numeric range 20.0935–73513.2; most frequent: `652.4963989257812`: 9; `826.7677001953125`: 8; `952.83984375`: 7; `1558.8192138671875`: 7; `472.41680908203125`: 7 |
| `ID_card` | `string` | 2 | 0 → 0 | 0 → 0 | `Has ID (National Identity Card (ID),Passport,Alien ID)`: 18,571; `No ID`: 1,175 |
| `Access_fnl` | `string` | 5 | 0 → 0 | 0 → 0 | `Formal Prudential`: 10,102; `Formal Non-Prudential`: 6,685; `Excluded`: 1,759; `Informal`: 1,067; `Formal Registered`: 133 |
| `Overall_Access_fnl` | `string` | 3 | 0 → 0 | 0 → 0 | `formal only`: 16,920; `excluded`: 1,759; `informal only`: 1,067 |

## Special responses, Excel errors, and skip-pattern review

- No global recoding of 96, 97, 98, or 99 was applied. Special-code interpretation is field-specific and only used for `A18` eligibility.
- Aside from excluding records without an eligible `A18` as documented above, no Parquet nulls or Excel error tokens were imputed, normalized, or dropped. Errors remain text and are counted per field above.
- `A20` contains labeled Don't know and Refused responses as text, plus 1 adult `95` value(s) without a verified meaning (2 in the full extract); retained values were not changed.
- The `A24i`–`A24vi` workbook value labels document codes 98/99 as Don't know/Refused. The extracted responses contain substantive text labels and the reported Excel errors; no such codes were recoded. Refer to the field-level counts above.
- `B3Ii` is stored as text because the extraction found mixed cell types. Numeric-looking strings remain strings, `#NULL!` remains an Excel error token, and no income value or sentinel was imputed. The workbook documents 98/99 as special responses; no global numeric-string replacement was made.
- `S1`, `S3`, and `S4` preserve the workbook's text response labels, including their explicit Refused labels. `S2__1` preserves observed `0`/`1` strings and `#NULL!`; its value-label mapping was not confirmed in the workbook inventory.
- The source workbook and extracted text for some `S1`/`S4` labels contain visible character-encoding artifacts (for example, `donâ€™t`). These strings were preserved as supplied; no normalization was attempted.
- Workbook labels describe `S4` as the main place/device used the last time the respondent used the internet, so a skip for non-use is plausible. However, the observed cross-tab is not perfectly aligned: `S3` Never appears with `S4` Excel errors in 8,324 rows and with a non-error `S4` response in 1,332 rows; `S4` Excel errors also occur with non-Never/unknown/refused `S3` in 162 rows. These are unresolved routing/data-quality cases, not recoded structural missingness.
- `S2__1` Excel errors by observed `S1` category: `I donâ€™t own or use a mobile phone/Sina wala situmii simu ya mkononi`: 1,735; `#NULL!`: 44; `Refused to Answer (DO NOT READ OUT)/Kataa kujibu`: 4; `I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia`: 2. The pattern is compatible with routing for some respondents but includes exceptions; no `S2__1` errors were interpreted or replaced.

## Transformations and retained fields

- Applied only the adult eligibility filter on `A18`: retain non-special numeric ages greater than or equal to 18; exclude under-18, age special-code, missing, or invalid-age records as counted above.
- Preserved all 23 source column names, order, Parquet types, response values, labels, and Excel error tokens in the output.
- Preserved `Access_fnl` and `Overall_Access_fnl` as their original text labels. No binary financial-exclusion target was created, and the `Access_fnl` derivation remains unverified.
- Kept `indWeight` and `A07` in the response file as analysis metadata, not predictors. `A07`'s mapping to the official PSU/EA and the stratum identifier remain unverified; full survey-design analysis is not claimed.
- Retained `S4` provisionally. It remains a general internet-use context candidate, not an approved final predictor.
- No wealth quantile was added. No predictor matrix, final modelling dataset, model, or target was created. The selected extraction contains no direct financial-service transaction fields; the two outcome classification fields are retained only for later review.

## Unresolved issues and next review

- Obtain/confirm official `Access_fnl` derivation and the sampling-design crosswalk before target construction or claiming design-based analysis.
- Review the unexplained `A20` value `95`, Excel error tokens, and routing exceptions in `S2__1`/`S4` with the questionnaire and data provider before any predictor missingness treatment.
- Confirm the `S2__1` 0/1 meaning and whether `S4` is suitable after resolving observed skip-pattern inconsistencies.

## Integrity checks

- Input and output row counts reconcile: 20,871 = 19,746 retained + 1,121 under 18 + 4 age special + 0 missing age + 0 invalid age.
- Interim input SHA-256 after preparation: `bf12f1121bf08fadda74e111078744d8b3ef2aa89a3bff7ea09b3cd1fb998d41`.
- Interim input unchanged: **True**.
- Prepared Parquet size: 515,741 bytes.

## Follow-up investigation: workbook metadata and questionnaire

This addendum records checks made against the official 2024 FinAccess main
report, questionnaire, workbook `Variables` and `Values` sheets, and raw
respondent-sheet XML. Where this addendum is more specific than the initial
audit above, it is the current finding. The original workbook and interim
Parquet were read-only throughout.

### Verified facts

#### Target definition and observed distribution

The official report (section 1.5, pp. 8–9, including Table 1.3) describes
financial-inclusion concepts and provider classifications. Workbook metadata
maps `Access_fnl` codes 1–5 to the five observed categories, but neither the
report, questionnaire, nor workbook metadata supplies the variable-level
derivation formula or a source-variable crosswalk for `Access_fnl`.
Respondent-sheet cells contain the category labels; no formulas were found in
the selected outcome cells. The existence of category labels and their
metadata does not establish how the classification was computed.

| Original `Access_fnl` category | Full extracted rows | Adult rows |
|---|---:|---:|
| Formal Prudential | 10,130 | 10,102 |
| Formal Non-Prudential | 6,729 | 6,685 |
| Formal Registered | 137 | 133 |
| Informal | 1,214 | 1,067 |
| Excluded | 2,661 | 1,759 |
| **Total** | **20,871** | **19,746** |

These are distributions of the original labels, not a constructed binary
target. The questionnaire/report describe relevant financial-service
concepts, but do not establish which exact questions, reference periods,
provider rules, precedence rules, or response handling produced
`Access_fnl`. `Overall_Access_fnl` has three observed labels (full extract:
16,996 formal only, 1,214 informal only, 2,661 excluded; adult rows: 16,920
formal only, 1,067 informal only, 1,759 excluded). No derivation for either
field is inferred here.

#### A20 education value 95

The questionnaire (p. 7) lists A20 response codes 1–10, 98 (Don't know), and
99 (Refused). The workbook `Values` metadata likewise has labels for 1–10,
98, and 99, but no label for 95. A read-only scan of the respondent-sheet XML
found exactly two `A20=95` cells, both stored as numeric cells (XML type `n`):
`AD302` and `AD20068`. One occurs in the adult population; the other is among
respondents excluded by the `A18` age rule. Thus `95` is a real numeric source
value, not an extraction artifact, but its meaning remains unverified.

#### Digital-access routing and encoding

The questionnaire (p. 112) routes S2 only after S1 responses for owning or
regularly using a mobile phone; other S1 responses skip to S3. S2 questionnaire
responses are Yes=1 and No=2. The workbook metadata does not provide a value
label mapping for extracted `S2__1`; the respondent data instead contains
`0`, `1`, and `#NULL!`. Their correspondence to questionnaire codes is not
verified, so `0`/`1` are not interpreted as Yes/No.

The questionnaire routes S4 only when S3 is coded 1–4 or 6. S3 Never (5) and
Refused (99) skip S4. The observed `#NULL!` routing cross-tabs are:

| Field | Error-token rows by preceding response | Full extract | Adult rows | Evidence-based interpretation |
|---|---|---:|---:|---|
| `S2__1` | S1 says respondent neither owns nor uses a mobile | 1,735 | 1,249 | Consistent with the questionnaire skip |
| `S2__1` | S1 Refused | 4 | 4 | Applicability is unresolved after refusal |
| `S2__1` | S1 is `#NULL!` | 44 | 44 | Applicability is unknown |
| `S2__1` | S1 is an eligible owner/user response | 2 | 2 | Error despite the S2 route; unresolved |
| `S4` | S3 Never | 8,324 | 7,794 | Consistent with the questionnaire skip |
| `S4` | S3 Refused | 21 | 19 | S4 is not routed after refusal |
| `S4` | S3 is `#NULL!` | 44 | 44 | Applicability is unknown |
| `S4` | S3 is an S4-eligible response | 97 | 92 | Error despite the S4 route; unresolved |

The `S3` Never group also contains a non-error S4 value in 1,332 full-extract
rows (486 Refused labels and 846 substantive place/device labels), including
1,235 adult rows (445 Refused labels and 790 substantive labels). These
responses conflict with the questionnaire skip route. The error tokens that
align with a skip are consistent with structural missingness, but the token
alone does not prove why the value is absent. Refused/unknown preceding
responses and the route violations remain distinct unresolved cases; no
`#NULL!` was recoded.

Representative text strings containing visible encoding artifacts (such as
`donâ€™t`, `neighbourâ€™s`, and `cafÃ©`) occur literally in the source workbook
and identically in the extracted Parquet. They are source values, not a
Parquet-only display conversion. No normalization or category merging was
performed.

#### Duplicate identifiers

The respondent sheet has 20,871 data rows. A streaming scan found zero blank
values and zero duplicates for both `interview__key` and `interview__id`
(20,871 distinct values for each). No records were removed for duplication.
Identifier values are intentionally not reproduced in this report.

#### Field-level null, blank, special-response, and Excel-error summary

Counts below are **full extract → adult output**. True Parquet nulls and
empty/whitespace-only strings are 0 → 0 for every selected field. Excel
`#NULL!` error tokens are preserved strings, not Parquet nulls. “No labelled
special response observed” does not assign meanings to unlabeled values.

| Original field | Nulls / blanks | Labelled special responses or unresolved values | `#NULL!` error tokens | Structural missingness identifiable from routing |
|---|---:|---|---:|---|
| `county` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not applicable |
| `A07` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not applicable |
| `A08` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not applicable |
| `A18` | 0 / 0 → 0 / 0 | 98: 2 → 0; 99: 2 → 0 | 0 → 0 | Not established |
| `Sex` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not applicable |
| `A20` | 0 / 0 → 0 / 0 | Don't know: 2 → 2; Refused: 3 → 3; unlabelled numeric 95: 2 → 1 | 0 → 0 | Not established |
| `A24i` | 0 / 0 → 0 / 0 | No 98/99 response observed; workbook documents those codes | 2 → 2 | Not established |
| `A24ii` | 0 / 0 → 0 / 0 | No 98/99 response observed; workbook documents those codes | 2 → 2 | Not established |
| `A24iii` | 0 / 0 → 0 / 0 | No 98/99 response observed; workbook documents those codes | 1 → 1 | Not established |
| `A24iv` | 0 / 0 → 0 / 0 | No 98/99 response observed; workbook documents those codes | 0 → 0 | Not established |
| `A24v` | 0 / 0 → 0 / 0 | No 98/99 response observed; workbook documents those codes | 2 → 2 | Not established |
| `A24vi` | 0 / 0 → 0 / 0 | No 98/99 response observed; workbook documents those codes | 7 → 7 | Not established |
| `B3A__2` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not established |
| `B3A__4` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not established |
| `B3Ii` | 0 / 0 → 0 / 0 | Workbook labels 98/99; neither observed as a response | 2,378 → 2,044 | Not established |
| `S1` | 0 / 0 → 0 / 0 | Refused: 4 → 4 | 44 → 44 | Preceding route is unknown for the 44 errors |
| `S2__1` | 0 / 0 → 0 / 0 | No special-code mapping verified; observed `0`/`1` left uninterpreted | 1,785 → 1,299 | See S1 routing cross-tab above |
| `S3` | 0 / 0 → 0 / 0 | Refused: 21 → 19 | 44 → 44 | Preceding route is unknown for the 44 errors |
| `S4` | 0 / 0 → 0 / 0 | Refused: 514 → 473 | 8,486 → 7,949 | See S3 routing cross-tab above; includes route violations |
| `indWeight` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not applicable |
| `ID_card` | 0 / 0 → 0 / 0 | None identified | 0 → 0 | Not established |
| `Access_fnl` | 0 / 0 → 0 / 0 | Five classification labels; see distribution above | 0 → 0 | Not applicable; construction is unverified |
| `Overall_Access_fnl` | 0 / 0 → 0 / 0 | Three classification labels; derivation unverified | 0 → 0 | Not applicable; construction is unverified |

The A24 questionnaire/workbook special codes refer to response codes, while
the extracted columns contain text labels and `#NULL!` tokens; no 98/99
responses were observed in those fields. This summary does not convert an
Excel error into structural missingness solely because it coincides with a
skip pattern.

### Proposed handling for review

- Keep `A20=95` as an unresolved, separate observed category pending an
  official label or data-provider clarification. Do not equate it with
  “Other,” Don't know, Refused, or missing.
- Preserve `S2__1`, S1, S3, and S4 exactly as extracted. Do not infer the
  meaning of `S2__1` 0/1 or recode error tokens based only on routing.
- Continue to treat `S4` as provisional; assess it as a predictor only after
  the routing inconsistencies and suitability are reviewed.
- Do not remove duplicated records: none were found by either available
  respondent identifier.
- Do not construct a binary target from `Access_fnl` until its authoritative
  derivation and the intended research definition are confirmed.

### Unresolved confirmation needed

The data provider or official technical documentation must confirm the
`Access_fnl` derivation, including its exact source variables, response
categories, reference periods, provider classifications, precedence rules,
and treatment of nonresponse. Clarification is also needed for `A20=95`, the
`S2__1` 0/1 mapping, and the `S2`/`S4` routing exceptions before missingness
handling or final predictor approval. No target, imputation, category
normalization, predictor matrix, or model was produced in this investigation.

## Prompt 6B: target and modeling preprocessing

This section supersedes earlier statements in this report that no target or
modeling dataset had been created. It records the approved project mapping and
preprocessing implementation; it does not claim that the survey provider's
original classification method has been independently verified.

### Target construction

The target `financial_exclusion_status` is mapped only from the exact observed
`Overall_Access_fnl` text labels:

| `Overall_Access_fnl` | `financial_exclusion_status` | Project interpretation | Adult rows |
|---|---:|---|---:|
| `formal only` | 0 | Financially included | 16,920 |
| `informal only` | 0 | Financially included | 1,067 |
| `excluded` | 1 | Financially excluded | 1,759 |
| **Total** |  |  | **19,746** |

This yields 17,987 included (0) and 1,759 excluded (1). The observed
`Access_fnl` and `Overall_Access_fnl` columns are retained unchanged for
traceability; `Access_fnl` is not used to derive the target. Missing or
unexpected target labels cause an explicit error rather than a guessed mapping
or silent row removal. No individual financial-service indicators are used to
reconstruct the outcome. The mapping is the researcher's approved project rule
over the provider's labels; the provider's derivation algorithm and source
crosswalk remain unverified.

### Predictor set and retained non-predictor fields

The 19 predictors are `A18`, `Sex`, `A20`, `county`, `A08`, `B3A__2`,
`B3A__4`, `B3Ii`, `ID_card`, `S1`, `S2__1`, `S3`, `S4`, and `A24i`–`A24vi`.
They cover the approved demographic, education, geography, livelihood/income,
identification, general nonfinancial digital-access, and functional-difficulty
groups. Direct financial-service, ownership/use, transaction, and outcome
fields are not predictors. No wealth quantile or other unapproved field is
included.

`indWeight` and `A07` remain in separate design fields and are not predictors.
The output also retains the two original outcome columns. The modeling file has
19 predictor columns, the binary target, two traceability columns, and two
survey-design fields (24 columns total); it retains all 19,746 adult rows.

`A20=95` remains an untouched categorical value. `S2__1` values `0`/`1` are
not interpreted as questionnaire Yes/No, and `#NULL!` values in `S2__1` and
`S4` remain categorical values. S4 is included provisionally despite the
documented routing anomalies. These choices preserve unresolved evidence; they
do not resolve its meaning or establish final predictor suitability.

### Preprocessing and split

- Numeric features: `A18` and `B3Ii`. Numeric parsing of `B3Ii` occurs only in
  the preprocessing pipeline. Non-numeric values such as `#NULL!` become NaN
  for that numeric transformation, with the original raw text retained in the
  modeling dataset; missing values are median-imputed and standardized.
  `SimpleImputer(add_indicator=True)` also supplies a missingness indicator
  when the training data contains missing numeric values. The semantics of
  `B3Ii` error tokens remain unresolved.
- Categorical features: remaining approved predictors. Missing values are
  most-frequent-imputed and one-hot encoded with unseen categories ignored.
  Observed categorical special labels and error tokens are not normalized.
- Split: stratified 80/20 with random seed 42. Train has 15,796 rows (14,389
  included, 1,407 excluded); test has 3,950 rows (3,598 included, 352
  excluded). Preprocessing was fitted only on the training predictors, then
  applied to test predictors. The transformed dimensions are 129 features for
  both sets; values were finite after imputation and scaling.
- No resampling, estimator/model fitting, survey-weighted fitting, or
  design-based analysis was performed.

### Output and integrity

Created `data/processed/finaccess_modeling_dataset.parquet` with 19,746 rows
and 24 columns. The existing
`data/processed/finaccess_adults_unprepared.parquet` was read-only. The raw
workbook, interim Parquet, and adult-only Parquet SHA-256 values match their
pre-implementation baselines; no input dataset was overwritten.

## Prompt 6C: targeted data issue decisions

This section supersedes Prompt 6B's predictor list and its `A20=95`
preprocessing decision. Earlier sections are retained as a historical audit.

### Education and income

- `A20=95` occurs in one adult record. Its meaning is not documented in the
  questionnaire or workbook labels. At the researcher's direction it is
  treated as missing only in the preprocessing transform, then imputed using
  the training-set mode. The original source and modeling values remain
  unchanged. This is a project treatment, not an official meaning of 95.
- `B3Ii` asks for total monthly income in Kenyan shillings. In 19,746 adult
  records, 17,702 values parse numerically (range 100–200,000) and 2,044 are
  `#NULL!`. Neither questionnaire-specific special response code 98 or 99
  occurs. Preprocessing converts numeric amounts, treats non-numeric and
  nonfinite values and the field's 98/99 codes as missing, and imputes using
  the training median. The original text values remain in the modeling file.
  The reason for an individual `#NULL!` remains unresolved.

### Digital access

- The questionnaire (p. 112) asks S2 only when S1 is 1, 2, or 3 and specifies
  Yes=1, No=2. The extracted `S2__1` instead contains `0` in 9,659 adults,
  `1` in 8,788, and `#NULL!` in 1,299; no `2` is observed. No verified
  workbook crosswalk connects those export values to questionnaire codes.
  Accordingly, the researcher selected exclusion of `S2__1` from initial
  predictors pending confirmation rather than assuming a Yes/No mapping.
  No S2 recoding or structural-skip imputation has been applied. Its original
  values remain in the modeling dataset for review. Among S2 `#NULL!` rows,
  1,249 align with the no-phone S1 route, 4 follow refusal, 44 have unknown S1,
  and 2 follow an eligible S1 response. These cases are not all interchangeable.
- `S4` is excluded from initial predictors because its routing exceptions remain
  unresolved. Its original values remain available for review; no S4
  preprocessing is applied.

### Predictor selection, target and split

The 17 initial predictors are `A18`, `Sex`, `A20`, `county`, `A08`, `B3A__2`,
`B3A__4`, `B3Ii`, `ID_card`, `S1`, `S3`, and `A24i`–`A24vi`. `S2__1`, `S4`,
the two original outcome columns, `indWeight`, and `A07` are retained as
non-predictor fields. Financial-service access/use and transaction variables
are excluded.

The approved mapping from `Overall_Access_fnl` remains unchanged: 0 included
(17,987 adults) and 1 excluded (1,759). Both original outcome labels are
preserved. The provider's technical classification derivation has not been
independently verified.

Using the reproducible stratified 80/20 split (seed 42), training has 15,796
rows (14,389 included, 1,407 excluded), and test has 3,950 (3,598 included,
352 excluded). Fitting preprocessing on training data only produces 114
features for both sets and finite transformed values. No model or resampling
was applied; no full survey-design analysis is claimed.

### Outputs and integrity

`data/processed/finaccess_modeling_dataset_6c.parquet` contains all 19,746
adult rows and 24 columns: 17 predictors, two retained review fields, the
target, two outcome traceability fields, and two design fields. The earlier
`finaccess_modeling_dataset.parquet` remains unchanged; its embedded predictor
metadata describes Prompt 6B, not the current 17-feature selection. The new
file's metadata records the revised selection. The raw workbook, interim
Parquet, adult-only Parquet, and earlier modeling Parquet remained unchanged
according to SHA-256 checks.
