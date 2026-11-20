# An Explainable Machine Learning Framework for Predicting Financial Exclusion in Kenya

- **Course:** DSA 8401 - Applied Machine Learning
- **Dataset:** 2024 FinAccess Household Survey

## Project overview

This project will develop a reproducible and explainable machine learning workflow to study financial exclusion in Kenya using the 2024 FinAccess Household Survey. The original workbook is kept in `data/raw/` and must never be modified or committed. It is not included in this repository; access and use must follow the dataset's terms.

The approved target and predictor groups are documented in
[variable_selection.md](documentation/variable_selection.md); some field and
survey-design mappings remain unverified. Financial access, ownership, and
actual usage are distinct concepts.

## Objectives

- Inspect the workbook and supporting documentation before selecting data.
- Establish and document an official, defensible financial-exclusion outcome.
- Prepare an auditable dataset while preserving source variable names and recording transformations.
- Build leakage-aware, reproducible preprocessing and modeling workflows.
- Evaluate models with appropriate metrics, survey weights, and sampling-design considerations.
- Explain model outputs without presenting associations as causal effects.
- Provide a tested FastAPI interface and Docker-based deployment path after a model is approved.

## Proposed methodology

1. Review official questionnaire, codebook, target definitions, and sampling documentation.
2. Inventory workbook sheets and structure, then stream only the confirmed respondent data into separate Parquet files.
3. Document target construction and exclude target components and leakage-prone proxies from predictors.
4. Split data before fitting preprocessing; keep preprocessing and any justified resampling inside training folds.
5. Compare baseline and advanced models using reproducible seeds and metrics such as precision, recall, F1, ROC-AUC, and PR-AUC as appropriate. Do not select by accuracy alone.
6. Account for survey weights and sampling design in splitting, fitting, evaluation, and interpretation where the documentation and estimand warrant it.
7. Produce confusion matrices and suitable SHAP explanations; interpret them as model associations, not causal effects.
8. Package the approved preprocessing and model for FastAPI, load it once at application startup, and test the API and Docker deployment.

Model comparison, held-out evaluation and training-only SHAP explanations are
implemented. Deployment remains a future stage.

## Extract selected survey responses

Place the unmodified workbook at `data/raw/2024_Finaccess_Publicdata.xlsx`, then
run from the project root:

```powershell
python -m src.data.convert_to_parquet
```

The command streams the confirmed respondent sheet, retains all source rows, and
writes `data/interim/finaccess_selected.parquet`. It preserves the approved
source column names and records extraction provenance in Parquet schema
metadata under `finaccess_extraction`. The output is read back and checked
against the source sheet's reported row and column counts before publication.
The raw workbook is never modified. The dataset, including outcome and design
fields, is not a predictor matrix; no target or age filter is constructed here.

Mixed text/numeric columns are serialized as text with their names recorded in
metadata. Excel error tokens such as `#NULL!` are preserved as text and counted,
not silently recoded. Some source fields, including `Access_fnl`, contain
labels instead of numeric codes. Review their documented meaning before later
analysis. The conversion uses a temporary disk spool and bounded Parquet
batches; openpyxl may still load workbook shared strings in memory.

Load the full selected dataset when appropriate with:

```python
from src.data.load_data import load_selected_data

table = load_selected_data()
```

## Prepare the adult analysis population

After reviewing the extraction and the variable-selection documentation, run:

```powershell
python -m src.data.prepare_data
```

This writes `data/processed/finaccess_adults_unprepared.parquet` and the
audit at `reports/results/data_cleaning_report.md`. Preparation applies only
the approved 18+ restriction using `A18`; it treats that field's documented
98/99 special responses separately, retains other values and all response
labels/errors unchanged, and records the row counts and field-level audit.
Only the report section between the generated-section markers is refreshed;
manual investigation findings outside those markers are preserved. An existing
report with missing or malformed markers is rejected rather than overwritten.
Manual findings are not regenerated and should be reviewed against refreshed
results if the input changes.
The interim Parquet is not modified. This adult-only response file remains an
unmodified response table: target construction and predictor selection happen
in the next step. Survey-design mappings still require verification.

## Build the modeling dataset

After reviewing `documentation/variable_selection.md`, run:

```powershell
python -m src.data.feature_engineering
```

This writes `data/processed/finaccess_modeling_dataset_6c.parquet`, preserving
the earlier `finaccess_modeling_dataset.parquet` unchanged. The earlier file's
predictor metadata describes Prompt 6B and must not be used as the current
feature list. The
`financial_exclusion_status` target is mapped from the exact observed
`Overall_Access_fnl` labels; original outcome labels, `indWeight`, and `A07`
are retained separately, not as predictors. The provider's classification
methodology is not independently verified. For a reproducible 80/20
stratified split and training-only preprocessing, use
`src.data.preprocessing.split_modeling_data` and
`src.data.preprocessing.build_preprocessor`; no estimator is trained by the
dataset-construction command.

The initial feature list excludes `S4` because of unresolved routing exceptions
and `S2__1` because its workbook 0/1 encoding cannot yet be mapped reliably to
questionnaire Yes/No codes. Both raw columns are retained for review.
Preprocessing treats undocumented `A20=95` as missing and imputes it using the
training mode; numeric income is median-imputed using training data. Original
values remain unchanged in the Parquet files.

## Exploratory analysis

From the project root, run `python -m src.data.eda` or run
`notebooks/01_data_exploration.ipynb` with the project root as its working
directory. The EDA uses only the existing stratified training partition, writes
`reports/results/eda_report.md` and figures under `reports/figures/`, and makes
no feature-selection decisions. Percentages are unweighted sample
descriptions, not national estimates or causal findings. Install the
development requirements for notebook and plotting dependencies.

## Train and evaluate models

With the approved modeling Parquet present, run from the project root:

```powershell
python -m src.models.train
```

The command reuses the established stratified split and preprocessing.
Logistic regression, random forest, XGBoost and an RBF SVM are compared using
five stratified training folds; mean excluded-class F1 selects the model, with
recall as the tie-breaker. All four handle imbalance using weights fitted
within each training fold. SVM ranking uses decision scores rather than
probabilities. The selected model is evaluated on the held-out partition at
its default decision threshold. Results, settings and figures
are written under `reports/`; the fitted pipeline is saved as
`artifacts/financial_exclusion_pipeline.joblib`. Only load Joblib artifacts
from trusted sources, using compatible recorded package versions. The output
is unweighted and is not a national or causal estimate; survey design and
the provider's target derivation remain unresolved.
The selected SVM stores transformed training observations as support vectors;
keep its fitted artifact local and do not commit it. The pipeline provides
`predict` and `decision_function`, not calibrated probabilities.
The same held-out partition was evaluated in the earlier two-model experiment.
It is reused with researcher approval, but is no longer a pristine independent
assessment; do not use its results to revise model selection or tune the
threshold.

## Explain the selected model

With the locally saved SVM pipeline and approved modeling Parquet present, run:

```powershell
python -m src.models.explain
```

Kernel SHAP explains the RBF SVM's class-1 decision margin through the entire
fitted pipeline, grouping transformed columns by their 17 original variables.
The background and global explanation sample come only from the established
training partition. The report, transformed-feature mapping and figures are
written under `reports/results/` and `reports/figures/`; the local example is
a synthetic modal composite and does not export respondent values. SHAP values
are approximate model associations, not probabilities, causal effects or
national estimates. The small samples and independent masking of correlated
predictors limit interpretation.

## Project structure

- `src/financial_exclusion/`: importable application package, configuration, and data, feature, model, evaluation, and API modules.
- `data/raw/`: locally held original workbook; ignored by Git and Docker.
- `data/interim/`, `data/processed/`: generated datasets; ignored by Git and Docker.
- `documentation/`: data dictionary and methodology records.
- `notebooks/`: exploratory work only; implementation logic belongs in `src/`.
- `reports/`, `artifacts/`: generated outputs, ignored by default; requested
  reports and figures are tracked, while the fitted model is kept local.
- `tests/`: automated checks.

## Setup

Use Python 3.10 or newer. From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
```

Run the checks:

```powershell
python -m pytest
python -c "from financial_exclusion.config import PROJECT_ROOT, RANDOM_SEED; print(PROJECT_ROOT, RANDOM_SEED)"
```

The workbook is intentionally not downloaded, copied, or processed by these setup steps. Runtime and development dependencies are separated in `requirements.txt` and `requirements-dev.txt`. Dependency versions are not yet locked; pinning them should follow selection and validation of the supported Python environment.

## Responsible and transparent AI use

See [AI_USE.md](AI_USE.md) for the project's disclosure and verification practices for AI-assisted work.
