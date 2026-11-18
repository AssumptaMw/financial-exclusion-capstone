# Target and variable selection

## Status

The researcher approved the target, 18+ analysis population, and candidate
predictor groups documented here. Exact field-level processing remains subject
to the verification caveats below. No target has been constructed, no
observations have been filtered, and no model has been implemented.

## Official definition and approved outcome

The 2024 FinAccess report defines financial inclusion as access to and use of
financial services and products to meet financial and other needs. Its access
classification distinguishes formal prudential, formal non-prudential, formal
registered, informal, and excluded. The report classifies consumers relying on
social networks, keeping money in secret places, or having no financial service
or product as excluded (CBK, 2024, pp. 8–9, Table 1.3).

| Item | Approved specification | Evidence and limitation |
|---|---|---|
| Unit and population | Selected individuals aged 18 years or older. | Approved by the researcher. The survey sampled an eligible person aged 16+ per household, but the report says its analysis is for ages 18+ (CBK, 2024, p. 3). Record and report any under-18 exclusions. |
| Primary outcome | Use the workbook's precomputed `Access_fnl` classification: positive/excluded = code 5; negative/not excluded = codes 1–4. Preserve missing or unrecognized codes as unlabeled, not as either class. | Approved by the researcher. The workbook's `Values` sheet labels codes 1–5 as Formal Prudential, Formal Non-Prudential, Formal Registered, Informal, and Excluded. These categories align with the report's classification. The derivation formula/input crosswalk is unavailable; use the precomputed field as supplied and do not recreate it from guessed items. |
| Cross-check | Compare the primary classification with `Overall_Access_fnl`, whose workbook labels are 1 Formal only, 2 Informal only, and 3 Excluded. | Treat it as a validation cross-check, not a second outcome or predictor. The relationship between the two fields remains unverified. |
| Reference and interpretation | A cross-sectional classification of financial access/use in the 2024 survey, not a forecast of future exclusion. | The survey is cross-sectional. C1 combines “currently have/use,” “used to have/use,” and “never had/used”; C2 asks about use in the last 12 months for routed items. Do not describe the outcome as a pure account-ownership measure or as prospective risk. |

### Target construction boundary

The approved approach is to use the workbook's precomputed `Access_fnl` category
as disseminated, with the code labels above. The exact derivation syntax and
item-level crosswalk were reported unavailable. Therefore, document that the
project uses the precomputed classification and does not independently
reconstruct it. Do not assemble a binary target from arbitrary service items.
Any future attempt to rebuild the classification requires official derivation
syntax or a variable-to-classification crosswalk.

The questionnaire's C1 inventory covers savings (items 1a–9), registered
transaction services (10–12b), loans (13a–31), a Postbank account (32),
securities/investments (33–35), insurance (36–39), retirement/pension products
(40–42), and other financial products (43). C1 also asks about social-network
and secret-place arrangements; Table 1.3 classifies social-network arrangements
and keeping money in secret places as excluded, not as qualifying financial
access. C2 asks about recent use for routed former-use items. These are
questionnaire item codes, not a verified one-to-one workbook-column or
`Access_fnl` derivation crosswalk.

For leakage control, exclude all fields that encode the classification or its
financial-service evidence from the predictor matrix, including:

- `Access_fnl`, `Overall_Access_fnl`, `Access_Strand`, `formal_service_use`, and
  `formal_fullservice_use`;
- the C1 product-status fields and routed C2 recent-use fields, plus any
  account, provider, product, or service access/usage aggregates;
- transaction-channel and digital-finance activity fields, including fields
  that record online transactions or mobile-money transactions.

This is a conservative exclusion boundary. The official derivation crosswalk is
still needed to identify every component precisely. Variables must not be
re-admitted merely because they have a demographic-sounding label.

## Candidate predictor shortlist

The researcher approved the following predictor groups for the shortlist; this
does not validate every listed field or response code. Where both an original
response and a derived field are listed, retain only the verified
representation needed for the analysis; do not include duplicate encodings of
the same construct.

| Construct | Candidate original workbook fields | Rationale and verification caveat |
|---|---|---|
| Age | `A18`, `Age` | The report analyzes access by age. The workbook labels `A18` as respondent age and `Age` as the selected individual's age group. Use age 18+ for the proposed analysis population. |
| Sex | `Sex` | The report analyzes access by sex; the workbook labels `Sex` as sex of the selected individual. `A13` is sex of the household head in the questionnaire, so it is not interchangeable with respondent sex; consider it only as a separate household-context feature. |
| Education | `A20`, `Education` | The report analyzes access by education. The workbook labels `A20` as education completed and `Education` as respondent education level. Confirm coding and avoid duplicate representations. |
| Geography | `county`; `A08` | The report presents county and rural/urban comparisons. The questionnaire identifies `A08` as cluster type (1 Rural, 2 Urban); it is not the stratum identifier. |
| Livelihood and income | `B3A__2`, `B3A__4`, `B3Ii` | B3A records income sources reported for the past 12 months; the candidate fields represent Employed and Running own business/Self employed. `B3Ii` records total income received in the past month. Review the full B3A categories and income special codes before selecting or transforming them. |
| Identification | `ID_card` | The workbook label says ownership of an identity document (National ID, passport, or alien ID); the report identifies national ID access as relevant. This combined field is not equivalent to national-ID ownership alone. Confirm the source question, coding, and derivation before use. |
| Non-financial digital access | `S1`, `S2__1`, `S3`, optionally `S4` | The questionnaire asks about mobile-phone/tablet ownership and use (`S1`), phone internet capability (`S2__1`), general internet-use frequency (`S3`), and the main place/device for recent internet use (`S4`). These are candidates as general digital-access context, not as measures of financial-service use. Check skip patterns and special codes. |
| Functional difficulty | `A24i`–`A24vi` | The questionnaire asks about difficulty seeing, hearing, walking/climbing, remembering/concentrating, self-care, and communication. The group is approved for consideration; any combined disability indicator still requires a documented rule based on verified response categories. |

### Not included in the approved shortlist

`Quintiles` is labeled in the workbook and the report analyzes wealth quintiles,
but the researcher did not select wealth for the current predictor shortlist.
Its construction, direction, cut points, and asset inputs also remain
unverified. Do not include it unless the predictor selection is revised and its
definition is verified.

### Excluded or non-predictor fields

| Field group | Proposed handling | Reason |
|---|---|---|
| Financial-service access, ownership/status, and usage | Exclude from predictors, especially C1/C2 fields and derived service-use/access indicators. | These are direct evidence for, or potential components of, the outcome. C1's response combines possession and use; it is not a pure ownership measure. |
| Financial transactions and channels | Exclude fields that record using financial accounts, mobile money, digital banking, online transfers, or other financial transactions. | These can reveal actual financial-service use and create direct or proxy leakage. |
| Survey weights | Never use as predictors. | They represent sample design/adjustment, not respondent characteristics. Consider them for the estimand, supported fitting methods, and population-representative metrics. |
| Cluster/PSU and interview identifiers | Do not use as predictors. | They are design or record identifiers and may allow memorization or leakage across validation folds. Use design identifiers only for approved sampling-aware splitting/analysis. |

## Survey design and analysis population

The official report describes a multi-stage stratified cluster design with 92
strata, enumeration areas (EAs) as primary sampling units, and one selected
individual per sampled household. Individual weights incorporate EA design,
household and individual response adjustments, followed by population
post-stratification and raking (CBK, 2024, pp. 3–4).

The workbook contains `indWeight` (label: Individual Weights), `hhWeight`,
`A07` (A7. Cluster Number), and `A08` (A8. Cluster type; 1 Rural, 2 Urban).
`A07` is a plausible EA/PSU candidate, but the workbook materials inspected do
not explicitly crosswalk it to the report's EA identifier. No explicit
stratum-ID field has been verified. Obtain the official technical crosswalk
before claiming a design-based analysis or using a field as the stratum.

Proposed analysis safeguards, subject to approval:

- use the individual weight for individual-level population summaries and
  weighted evaluation where the metric supports it; do not substitute the
  household weight without justification;
- keep weights, strata, PSUs, and record IDs out of the predictor matrix;
- decide whether model fitting is weighted, and state the target estimand;
- design validation around the confirmed PSU/strata structure, and report
  weighted and unweighted results as appropriate;
- document any under-18 exclusions and every target/predictor missingness
  decision.

## Special response and missing-value handling

The questionnaire and workbook value-label sheet contain variable-specific
special responses, including Don't Know, Refused, Not Stated, and Not
Applicable. Questionnaire examples include 98 for Don't Know and 99 for
Refused; codes vary by question. C1's codes 1, 2, and 3 are substantive current,
former, and never statuses, not missing-value codes. C2's 1/2 are Yes/No.

Do not globally recode numeric values such as 98, 99, 96, or 97 without checking
the field's value labels and routing. A blank caused by a questionnaire skip is
not automatically equivalent to refusal or ordinary missingness. For target
construction, unresolved/special responses must remain unlabeled until their
meaning is verified; record counts and reasons rather than treating them as
excluded. For predictors, preserve the distinction between structural skips,
nonresponse, and substantive categories, then handle them only within the
training pipeline after approval.

## Approved decisions and remaining constraints

- Approved outcome: `Access_fnl == 5` is excluded; codes 1–4 are not excluded.
  `Overall_Access_fnl == 3` is a cross-check only.
- Approved population: selected individuals aged 18+.
- Approved predictor groups: age, sex, education, county/rural-urban context,
  livelihood/income, identification, non-financial digital access, and
  functional difficulty.
- Approved leakage boundary: exclude C1/C2, access-strand and service-use
  aggregates, and financial transaction/service-use fields from predictors.
- The official `Access_fnl` derivation and stratum/EA crosswalk are unavailable.
  Use the disseminated outcome field without reconstructing it; do not claim a
  design-based analysis until the sampling identifiers are mapped. Weighted
  individual-level analysis can be considered using `indWeight`, with the
  estimand and weighting approach stated explicitly.

## Sources

- Central Bank of Kenya (CBK), *2024 FinAccess Household Survey*, pp. 3–4
  (design, population, and weights), pp. 8–9, Table 1.3 (classification),
  pp. 14–16 (demographic access findings), and p. 12 (phone/ID barriers).
- CBK, *2024 FinAccess Household Survey Questionnaire*, pp. 19–24 (C1/C2),
  pp. 111–113 (Section S, technology questions).
- `data/raw/2024_Finaccess_Publicdata.xlsx`, `Variables` and `Values` sheets,
  cross-checked against `reports/results/variable_inventory.csv` and
  `reports/results/data_audit.md`.
