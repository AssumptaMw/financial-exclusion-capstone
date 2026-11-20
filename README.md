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

Model comparison, held-out evaluation, training-only SHAP explanations and a
local prediction API are implemented, together with a containerized
demonstration.

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

## End-to-end pipeline

From the project root, choose a **new** run ID:

```powershell
python -m src.pipeline --run-id my-first-run
```

The existing selected interim Parquet, approved modeling Parquet, local SVM,
cleaning report, and recorded training/SHAP provenance must already exist.
The pipeline regenerates adult and modeling data in a separate run directory,
checks their values and order against the approved modeling dataset, and
compares all four candidates in training-only cross-validation. It refits the
winner in memory and stops before evaluation unless the winner is SVM and its
fitted SVC state and training preprocessing outputs match the saved model.
It then evaluates and explains the **existing** SVM without rewriting it.

Outputs are isolated under `data/processed/pipeline_runs/<run-id>/`,
`reports/results/pipeline_runs/<run-id>/`, and
`reports/figures/pipeline_runs/<run-id>/`. The cleaning report is copied first
so manual findings survive the generated-section refresh. Existing run
directories are never overwritten: choose a different ID to run again.
Failed runs remain in place for inspection and have no completion manifest.
The manifest records input hashes and settings; generated data and the local
SVM remain Git-ignored. The existing test partition was previously evaluated,
so its repeated evaluation is not a pristine independent assessment.

## Local prediction API

Install the requirements as described below and place the **trusted**, compatible
fitted pipeline at `artifacts/financial_exclusion_pipeline.joblib`. From the
project root:

```powershell
python -m uvicorn src.financial_exclusion.api.main:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/docs` for the interactive schema, `GET /` for
service information and `GET /health` for model readiness. The pipeline is
loaded once per server process at startup; if loading fails, health and
predictions return 503 until the service is restarted with a valid model.
Never load an untrusted Joblib file: deserialization can execute code.

`POST /predict` accepts one JSON object. `POST /predict/batch` accepts
`{"records": [<object>, ...]}` with 1–100 records and returns predictions in
the same order. For example, this is a synthetic single-record request:

```json
{
  "A18": 35,
  "Sex": "Female",
  "A20": "\"Secondary completed \"",
  "county": "Nairobi City",
  "A08": "Urban",
  "B3A__2": 1,
  "B3A__4": 0,
  "B3Ii": 10000,
  "ID_card": "No ID",
  "S1": "I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia",
  "S3": "Daily/\"Kila siku\"",
  "A24i": "No- no difficulty",
  "A24ii": "No- no difficulty",
  "A24iii": "No- no difficulty",
  "A24iv": "No- no difficulty",
  "A24v": "No- no difficulty",
  "A24vi": "No- no difficulty"
}
```

All 17 fields are required; missing values can be expressed as `null` except
for `A18`, which must be an eligible adult age and cannot be the 98/99 special
codes. `B3A__2` and `B3A__4` are workbook 0/1 indicators. `B3Ii` accepts
non-negative numeric amounts, `null`, or the source token `#NULL!`. Categories
are the **exact workbook text representations**, not questionnaire numeric
codes; quotation marks, spacing and encoding artifacts may be significant.
The source code `A20=95` is accepted as the string `"95"`. Consult the data
dictionary before interpreting fields. The saved preprocessing performs
imputation and encoding; unseen categorical labels are ignored by its
one-hot encoder and can yield unreliable predictions. The API does not log
request bodies; review server and proxy logging before deployment.

Responses provide `financial_exclusion_status` (0 included, 1 excluded) and a
human-readable `label`. The saved SVM does not provide calibrated probabilities,
so no probability, confidence or decision score is returned. The prediction is
a cross-sectional model classification, not a causal or nationally
representative estimate, and its target derivation and survey design remain
subject to the documented limitations.

The local API does not include authentication, encryption, rate limiting or
data-governance controls. Configure these and assess prediction/model-inference
privacy risks before any external or production deployment; do not expose the
local model artifact, which contains support vectors.

## Prediction frontend

The React demonstration connects to the local API through a Vite proxy without
changing the API. See [frontend/README.md](frontend/README.md) for setup,
configuration, tests and deployment limitations.

## Run the application with Docker Compose

Install Docker Desktop with the Compose plugin and start its engine. Place the
**trusted** compatible model file at
`artifacts/financial_exclusion_pipeline.joblib`. It is not included in Git or
the image: Compose mounts that file read-only into the backend. On Windows,
ensure Docker Desktop can access its drive and the file is readable by the
container. Joblib can execute code when loading; never mount an untrusted file.

From the project root:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8080/` for the frontend,
`http://127.0.0.1:8080/api/health` for model readiness and
`http://127.0.0.1:8080/docs` for Swagger UI. The UI sends `/api/predict` to
Nginx, which forwards it to the backend's `/predict`; `/api/predict/batch` and
`/api/docs` are also forwarded. Swagger uses `/openapi.json` and the backend's
documented unprefixed endpoint paths, which Nginx forwards as well. The backend
welcome endpoint is available at `/api/`; `/` serves the React application.
Consequently, Swagger's unprefixed `GET /` opens the frontend rather than the
backend welcome response. The backend is not published directly to the host.

To use a model at another local path or change the frontend port, set these
environment variables before starting Compose:

```powershell
$env:MODEL_FILE = 'C:\path\to\trusted\financial_exclusion_pipeline.joblib'
$env:FRONTEND_PORT = '8081'
docker compose up --build -d
```

The configured model file must exist; Compose will not create it. The API
loads it once at startup and reports unhealthy if loading fails. The frontend
waits for the backend health check; inspect failures with
`docker compose logs backend`. Restart the service after replacing a model.
Serving dependencies are pinned in `requirements-serving.txt` to the recorded
model and tested API environment, but base images and transitive dependencies
are not fully locked. Only use a model compatible with these versions.

Stop this Compose project with `docker compose down`. The default published
port binds to localhost only. This is a demonstration, not a production-secure
deployment: authentication, TLS, rate limiting, privacy assessment and data
governance remain necessary before external use. Predictions are estimates,
not definitive individual assessments.

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
