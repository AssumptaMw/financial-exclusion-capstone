# Data dictionary

This dictionary records verified workbook labels and questionnaire wording for
variables used in the prepared modeling dataset. Original FinAccess variable
names are preserved. The approved target mapping and predictor groups are
documented in [variable_selection.md](./variable_selection.md). No model has
been fit, and the provider's original classification methodology remains
unverified.

| Original variable name | Verified definition / question | Response values and missing codes | Role (approved group/candidate) | Transformation | Source (document and page) | Verification status |
|---|---|---|---|---|---|---|
| `Access_fnl` | Workbook value labels: access classification. | Formal Prudential; Formal Non-Prudential; Formal Registered; Informal; Excluded. | Preserved for traceability only; not a predictor or target source. | Retain original text values unchanged; do not use to reconstruct the binary target. | Workbook `Variables` and `Values` sheets; CBK 2024 report, pp. 8–9, Table 1.3. | Category labels verified; provider derivation formula/crosswalk unavailable. |
| `Overall_Access_fnl` | Workbook value labels: overall access classification; observed worksheet labels are lower-case strings. | `formal only`; `informal only`; `excluded`. | Sole source for `financial_exclusion_status`; preserve as traceability; not a predictor. | Exact project mapping: `formal only` and `informal only` -> 0; `excluded` -> 1. Other/missing labels raise an error. | Workbook `Variables` and `Values` sheets; observed labels verified in respondent sheet. | Labels and observed counts verified; provider methodology and relation to `Access_fnl` are not independently verified. |
| `financial_exclusion_status` | Project-derived binary class from `Overall_Access_fnl`. | 0 Financially included; 1 Financially excluded. | Primary modeling target. | Exact label mapping above; no financial-service indicators are used to reconstruct it. | Prompt 6B approved rule; workbook labels. | Project mapping implemented; provider's original classification method remains unverified. |
| `Access_Strand` | Workbook variable label: Access strand. | Value-label set exists; categories not recorded here. | Potential outcome-derived field; exclude from predictors. | None. | Workbook `Variables` and `Values` sheets. | Label verified; exact coding/derivation not reviewed. |
| `formal_service_use` | Ever used formal financial services. | Workbook value labels: 0 Non-usage; 1 Usage. | Leakage candidate; exclude from predictors. | None. | Workbook `Variables` and `Values` sheets. | Label and codes verified; derivation not reviewed. |
| `formal_fullservice_use` | Ever used formal full-service financial services. | Workbook value labels: 0 Non-usage; 1 Usage. | Leakage candidate; exclude from predictors. | None. | Workbook `Variables` and `Values` sheets. | Label and codes verified; derivation not reviewed. |
| `C1_*` | C1 asks whether each listed product/service is currently had/used, used to be had/used, or never had/used in the respondent's own name. The list includes savings, transaction services, loans, investments, insurance, pensions, and other products. | 1 Currently have/use; 2 Used to have/use; 3 Never had/used. Check item-specific routing and value labels. | Target evidence/leakage; exclude from predictors. | Do not collapse status into ownership or recent use without an approved rule. | CBK 2024 questionnaire, pp. 19–24; workbook `Variables` and `Values` sheets. | Wording and broad codes verified; exact workbook item crosswalk and target contribution not documented. |
| `C2_*` | For routed former-use items, asks whether the respondent used the product in the last 12 months. | 1 Yes; 2 No for the shown questions; verify item-specific values. | Target evidence/leakage; exclude from predictors. | No transformation proposed. | CBK 2024 questionnaire, pp. 23–24; workbook `Variables` and `Values` sheets. | Wording verified; full item mapping not reviewed. |
| `A18` | Age of respondent. | 98 Don't Know; 99 Refused. | Candidate demographic predictor and age eligibility field. | Apply the approved 18+ population definition; document under-18 exclusions. | CBK questionnaire, Section A, p. 6; workbook `Variables` sheet. | Wording and questionnaire codes verified. |
| `Age` | Age group of selected individual. | Check workbook value labels before use. | Candidate demographic predictor; may duplicate `A18`. | Use one verified age representation. | Workbook `Variables` and `Values` sheets. | Label verified; mapping and categories pending. |
| `A13` | Sex of the household head. | Check workbook value labels and any nonresponse codes before use. | Optional household-context field; not selected individual's sex. | Do not treat as respondent sex or as a duplicate of `Sex`. | CBK questionnaire, Section A, p. 3; workbook `Variables` sheet. | Questionnaire meaning verified; workbook codes pending. |
| `Sex` | Sex of selected individual. | Check workbook value labels before use. | Candidate individual-level demographic predictor. | Keep distinct from `A13`, which is sex of the household head. | Workbook `Variables` and `Values` sheets. | Label verified; mapping and categories pending. |
| `A20` | Highest level of formal education completed. | 1 None; 2 Some primary; 3 Primary completed; 4 Some secondary; 5 Secondary completed; 6 Some technical training; 7 Completed technical training; 8 Some university; 9 University completed; 10 Other; 98 Don't Know; 99 Refused; observed numeric 95 has no verified label. | Categorical socioeconomic predictor. | Preserve source `95` in Parquet; treat it as missing only in preprocessing, then impute using the training mode. | CBK questionnaire, Section A, p. 7; workbook `Variables` and `Values` sheets; CBK 2024 report, pp. 14–16. | Questionnaire/workbook do not label 95; one adult observation has that value. Missing treatment is a project decision, not an official interpretation. |
| `Education` | Education level of respondent. | Check workbook value labels before use. | Candidate socioeconomic predictor; may duplicate `A20`. | Use one verified representation. | Workbook `Variables` and `Values` sheets. | Label verified; mapping and categories pending. |
| `A24i`, `A24ii`, `A24iii`, `A24iv`, `A24v`, `A24vi` | Self-reported difficulty with seeing, hearing, walking/climbing, cognition, self-care, and communication, respectively. | Questionnaire: 1 No difficulty; 2 Some difficulty; 3 A lot of difficulty; 4 Cannot do at all; 98 Don't Know; 99 Refused. Check workbook representations. | Candidate functional-difficulty predictors. | No combined indicator or response recoding approved. | CBK questionnaire, Section A, p. 8; workbook `Variables` and `Values` sheets. | Questionnaire wording and codes verified; workbook coding pending. |
| `county` | County. | Check workbook value labels. | Candidate geographic predictor. | None approved; do not use finer location identifiers as predictors. | Workbook `Variables` and `Values` sheets; CBK 2024 report, pp. 3, 14–16. | Label verified; category review pending. |
| `A08` | Cluster type. | 1 Rural; 2 Urban. | Candidate geographic predictor; not a stratum identifier. | None approved. | CBK questionnaire, Section A, p. 3; workbook `Variables` and `Values` sheets. | Meaning and questionnaire codes verified. |
| `B3A__2` | B3A income source: Employed. The question asks how the respondent got money in the past 12 months. | Category 2; 98 Don't Know; 99 Refused. Verify workbook representation. | Candidate livelihood predictor. | Treat as an income-source indicator, not necessarily current employment status. | CBK questionnaire, B3A livelihood sources, p. 15; workbook `Variables` and `Values` sheets. | Wording and questionnaire category verified; workbook coding pending. |
| `B3A__4` | B3A income source: Running own business/Self employed. The question asks how the respondent got money in the past 12 months. | Category 4; 98 Don't Know; 99 Refused. Verify workbook representation. | Candidate livelihood predictor. | Treat as an income-source indicator, not necessarily current employment status. | CBK questionnaire, B3A livelihood sources, p. 15; workbook `Variables` and `Values` sheets. | Wording and questionnaire category verified; workbook coding pending. |
| `B3Ii` | Total money received from all income sources in the past month, in KSh. | Adult data: 17,702 numeric-looking values, range 100–200,000; 2,044 `#NULL!` tokens; no 98/99 values observed. | Numeric livelihood/income predictor. | Convert to numeric only in preprocessing; nonnumeric values and questionnaire-specific codes 98/99 become missing and are median-imputed from training data. Preserve original values in Parquet. | CBK questionnaire, livelihood section, p. 18; workbook `Variables` and `Values` sheets. | Wording verified; the meaning of `#NULL!` as a response/skip remains unresolved. |
| `Quintiles` | Workbook label: Quintiles. | Categories and special codes must be checked in the `Values` sheet. | Not in the approved predictor shortlist. | Do not include unless the selection is revised and the construct is verified. | Workbook `Variables` and `Values` sheets; CBK 2024 report's wealth-quintile analysis. | Label verified; construct and cut points unverified. |
| `ID_card` | Ownership of ID Card (National Identity Card, Passport, Alien ID). | Check workbook value labels and source coding. | Candidate identification predictor. | Do not treat this combined field as national-ID-only without a verified crosswalk. | Workbook `Variables` sheet; CBK 2024 report, p. 3 and Table 2.1. | Label verified; source question and derivation unverified. |
| `S1` | Which best describes ownership and usage of mobile phone/tablet services? | 1 own and only respondent uses; 2 own and others use; 3 no ownership but regular access to another's phone; 4 neither own nor use; 99 Refused. | Candidate non-financial digital-access predictor. | Preserve ownership/access distinctions; do not use as financial-service ownership. | CBK questionnaire, Section S, pp. 111–112; workbook `Variables` and `Values` sheets. | Wording and questionnaire codes verified. |
| `S2__1` | Whether the respondent's phone can access the internet. Questionnaire asks S2 only when S1 is 1, 2, or 3. | Questionnaire: Yes=1, No=2. Workbook export: `0`, `1`, `#NULL!`; crosswalk from export values to questionnaire codes is unverified. | Excluded from initial predictors pending verification; retained for review. | Preserve source values; no Yes/No recode or structural-skip imputation is applied. | CBK questionnaire, Section S, pp. 111–112; workbook `Variables` and `Values` sheets; cleaning report routing audit. | The researcher's decision excludes S2 until the export mapping is verified. Some routing cases remain unresolved. |
| `S3` | How frequently the respondent uses the internet. | 1 Daily; 2 Weekly; 3 Monthly; 4 Less often; 5 Never; 6 Other; 99 Refused. | Candidate general digital-access predictor. | Distinguish general internet use from financial transactions. | CBK questionnaire, Section S, pp. 112–113; workbook `Variables` and `Values` sheets. | Wording and questionnaire codes verified. |
| `S4` | Main place/device used during the respondent's last internet use. | Observed place/device labels, Refused, and `#NULL!`; questionnaire skips S4 after S3 Never or Refused. | Excluded from initial predictors; retained for review. | Preserve observed values unchanged; no encoding or imputation. | CBK questionnaire, Section S, pp. 112–113; workbook `Variables` and `Values` sheets; cleaning report routing audit. | Questionnaire routing verified; observed exceptions remain unresolved. |
| `S7_1`, `S7_2` | Self-rated capability to undertake online/internet transactions and mobile-money transactions. | 1 No idea/don't know; 2 Can manage with difficulties; 3 Can manage; 4 Can manage with ease. | Potential proxy-leakage fields; exclude from predictors conservatively. | These ask about capability, not actual transactions; keep distinct from direct use measures. | CBK questionnaire, Section S, p. 113; workbook `Variables` and `Values` sheets. | Wording and questionnaire response scale verified. |
| `A07` | A7. Cluster Number. | Integer identifier; confirm official EA crosswalk. | Candidate PSU/cluster field for design-aware analysis only; not a predictor. | Do not use until mapped to the official EA identifier. | Workbook `Variables` sheet; CBK 2024 report, pp. 3–4. | Label verified; EA mapping unconfirmed. |
| `indWeight` | Individual Weights. | Numeric weight; inspect range and missingness before analysis. | Candidate individual survey weight; not a predictor. | Use only for an explicitly stated estimand and supported weighted analysis. | Workbook `Variables` sheet; CBK 2024 report, pp. 3–4. | Label and report's individual-weighting process verified; exact field crosswalk pending. |
| `hhWeight` | Workbook label: hhWeight. | Numeric weight; inspect range and missingness before analysis. | Household-weight candidate; not a predictor for an individual outcome unless justified. | Do not substitute for `indWeight` by default. | Workbook `Variables` sheet; CBK 2024 report, pp. 3–4. | Field label verified; exact definition/crosswalk pending. |

## Prompt 6C modeling dataset and preprocessing

The Prompt 6C modeling Parquet contains 17 initial predictors, the binary target,
both original outcome fields, `S2__1` and `S4` for review, and separate
`indWeight`/`A07` design fields. Neither review field, design field, nor original
outcome is accepted as a predictor. The original adult-only response Parquet
and earlier modeling Parquet remain unchanged.

`A18` and `B3Ii` are processed numerically. `B3Ii` is stored as text in the
source because of mixed representations; nonnumeric values such as `#NULL!`
and questionnaire-specific 98/99 become missing only in the numeric
preprocessing transform and are median imputed. Raw `B3Ii` strings remain in
Parquet. `A20=95` becomes missing only in preprocessing and is mode imputed
from the training set; its original meaning remains unknown. Remaining
categorical fields use most-frequent imputation followed by one-hot encoding
with `handle_unknown="ignore"`. S2/S4 are excluded from preprocessing; their
original values and skip issues are preserved for review. The preprocessing
pipeline is fit on training data only, after the reproducible stratified split.
No resampling is applied.

The modeling target counts in the 18+ dataset are 17,987 included (0) and
1,759 excluded (1). The mapping implements the researcher's approved project
rule over the provider's observed labels; it does not independently verify the
provider's original classification methodology.

## Required recording conventions

- Keep the source variable name unchanged in this dictionary, even if a clearer internal name is later used in code.
- Record official question wording, response labels, skip patterns, and missing-value codes where documented.
- Identify whether a variable is a candidate predictor, target component, survey weight, stratum, cluster/PSU, identifier, or excluded field; do not make those assignments from names alone.
- For each derived field, record its source variables, rule, handling of missing and special codes, and rationale.
- Cite the official source document and page or table for definitions and coding decisions.
- Mark uncertain or undocumented meanings explicitly instead of filling them by assumption.

`C1_*` and `C2_*` are family shorthand in this table, not literal field names;
the exact workbook columns remain as listed in the variable inventory. The
workbook's `Values` sheet contains variable-specific labels such as Don't Know,
Refused, Not Stated, and Not Applicable. Do not apply a global numeric
missing-code rule; consult the field's label set and questionnaire routing.

The respondent worksheet stores some labeled fields as text rather than numeric
codes: sampled `Access_fnl` cells contain labels such as `Excluded` and
`Formal Prudential`. The extraction preserves the worksheet representation; the
approved numeric code definition must not be applied directly to these text
cells. Some cells contain Excel errors such as `#NULL!`. Extraction preserves
those tokens and records their counts; it does not interpret them as missing or
as substantive answers.
