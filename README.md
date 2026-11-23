# An Explainable Machine Learning Framework for Predicting Financial Exclusion in Kenya

- **Course:** DSA 8401 - Applied Machine Learning
- **Dataset:** 2024 FinAccess Household Survey

## Project overview

This project develops a reproducible and explainable machine learning workflow
to study financial exclusion in Kenya using the 2024 FinAccess Household
Survey. The original workbook is kept in `data/raw/` and must never be
modified or committed. It is not included in this repository; access and use
must follow the dataset's terms.

The approved target and predictor groups are documented in
[variable_selection.md](documentation/variable_selection.md); some field and
survey-design mappings remain unverified. Financial access, ownership, and
actual usage are distinct concepts.

## Research problem and aim

Financial exclusion limits access to and use of financial services. The aim is
to investigate whether approved non-financial characteristics can classify
the survey's project-defined exclusion outcome, and to explain the resulting
model's behavior. The survey is cross-sectional: this is not a forecast of
future exclusion or an assessment of an individual's circumstances.

## Objectives

- Inspect the workbook and official materials; document the approved outcome
  and remaining uncertainty about the provider's classification.
- Prepare an auditable adult cohort and prevent outcome or preprocessing leakage.
- Compare four classifiers using excluded-class F1 and complementary metrics.
- Explain the selected model without presenting associations as causal effects.
- Consider survey design and its unresolved implications for interpretation.
- Provide a tested FastAPI, React and Docker demonstration.

## Dataset, target and predictors

The source is the [2024 FinAccess Household Survey](https://repository.knbs.or.ke/entities/publication/5b57f6d1-ad95-4a09-b9f8-b96cb6935680).
The approved respondent-level worksheet yielded 20,871 records and 23 selected
fields. The `A18` restriction retained **19,746 adults**: 1,121 records under
18 and four records with age response codes 98/99 were excluded. The cohort has
17,987 included and 1,759 excluded observations. These are unweighted sample
counts, not national estimates; see the
[cleaning report](reports/results/data_cleaning_report.md).

The project maps the supplied `Overall_Access_fnl` labels exactly:

| Supplied label | `financial_exclusion_status` |
| --- | ---: |
| `formal only` | 0 — financially included |
| `informal only` | 0 — financially included |
| `excluded` | 1 — financially excluded |

Unexpected or missing target labels are rejected rather than guessed. The
provider's original technical derivation of this classification has **not**
been independently verified. `Overall_Access_fnl` and `Access_fnl` are retained
for traceability, not predictors; individual financial-service indicators are
not used to reconstruct the target.

The 17 approved predictors are:

| Group | Original variables |
| --- | --- |
| Demographics and education | `A18`, `Sex`, `A20` |
| Geography | `county`, `A08` |
| Livelihood and income | `B3A__2`, `B3A__4`, `B3Ii` |
| Identification | `ID_card` |
| General digital access | `S1`, `S3` |
| Functional difficulties | `A24i`, `A24ii`, `A24iii`, `A24iv`, `A24v`, `A24vi` |

`indWeight` and `A07` are retained as metadata, not predictors. Financial
service and transaction fields are excluded to limit target leakage. `S2__1`
and `S4` are excluded pending resolution of coding and routing issues; wealth
quantile was not approved. See the [data dictionary](documentation/data_dictionary.md)
and [variable selection](documentation/variable_selection.md).

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
Rerunning replaces the selected Parquet output. The raw workbook is never
modified. The dataset, including outcome and design
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
Rerunning replaces the adult output and refreshes the generated report section.
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
feature list. Rerunning replaces the 6C modeling output. The
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
training mode; numeric income's nonnumeric responses and field-specific 98/99
codes become missing only in preprocessing. Numeric features are median
imputed, with indicators for missingness observed during fitting, then scaled.
Categorical features are mode-imputed and one-hot encoded; unseen categories
are ignored. Original values remain unchanged in the Parquet files.
Preprocessing is fitted only on
training data, separately within each cross-validation fold.

## Exploratory analysis

From the project root, run `python -m src.data.eda` or run
`notebooks/01_data_exploration.ipynb` with the project root as its working
directory. The EDA uses only the existing stratified training partition, writes
`reports/results/eda_report.md` and figures under `reports/figures/`, and makes
no feature-selection decisions. Percentages are unweighted sample
descriptions, not national estimates or causal findings. Install the
development requirements for notebook and plotting dependencies. This command
rewrites its existing EDA report and figures.

## Train and evaluate models

With the approved modeling Parquet present, run from the project root:

```powershell
python -m src.models.train
```

**Warning:** this standalone command retrains models and overwrites the local
fitted artifact and the established evaluation reports and figures. Preserve
them first if they must remain unchanged.

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

### Recorded comparison and evaluation

The following are five-fold, training-only **mean ± standard deviation**
results, as recorded in the [model evaluation report](reports/results/model_evaluation_report.md).
Precision, recall and F1 use excluded class 1; PR-AUC is average precision.
The fixed candidates were not hyperparameter-tuned or resampled.

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Logistic Regression | 0.8991 ± 0.0027 | 0.4638 ± 0.0079 | 0.8486 ± 0.0245 | 0.5997 ± 0.0089 | 0.9236 ± 0.0065 | 0.5997 ± 0.0097 |
| Random Forest | 0.9300 ± 0.0020 | 0.6528 ± 0.0214 | 0.4606 ± 0.0181 | 0.5397 ± 0.0130 | 0.9174 ± 0.0084 | 0.6068 ± 0.0099 |
| XGBoost | 0.9108 ± 0.0039 | 0.4997 ± 0.0154 | 0.7399 ± 0.0268 | 0.5964 ± 0.0170 | 0.9180 ± 0.0079 | 0.6009 ± 0.0107 |
| RBF SVM | 0.8998 ± 0.0044 | 0.4662 ± 0.0128 | 0.8515 ± 0.0209 | 0.6024 ± 0.0136 | 0.9251 ± 0.0061 | 0.5801 ± 0.0168 |

The SVM was selected by highest mean excluded-class F1, with recall as the
tie-breaker; exact ties follow the fixed candidate order. Logistic regression,
random forest and SVM use balanced class weights; XGBoost computes its
positive-class weight within each fit. The stratified 80/20 split (seed 42)
has 15,796 training and 3,950 held-out records. No held-out scores were used
for model selection.

For the selected SVM, the recorded held-out accuracy is 0.8934, precision
0.4462, recall 0.8125, F1 0.5760, ROC-AUC 0.9201 and average precision
0.5646. The confusion matrix is:

| Actual / predicted | Included (0) | Excluded (1) |
| --- | ---: | ---: |
| Included (0) | 3,243 | 355 |
| Excluded (1) | 66 | 286 |

The [classification report and metrics](reports/results/model_evaluation.json),
[comparison details](reports/results/model_comparison.json), and
[experiment settings](reports/results/model_experiment_config.json) provide
the full results. **The held-out partition was previously inspected and is
not a pristine independent assessment** of the expanded comparison. All
reported metrics are unweighted sample results, not national estimates.

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
predictors limit interpretation. This standalone command overwrites its
existing SHAP report, JSON and figures.

The recorded [SHAP report](reports/results/shap_report.md) uses 24 training
rows as background and 64 disjoint training rows for the global sample, with
128 sampled coalitions per explanation and seed 42. The highest mean absolute
attributions in this sample were phone ownership/use (`S1`, 0.4229),
identification document (`ID_card`, 0.1302) and age (`A18`, 0.0897), on the
SVM decision-margin scale. These rankings are approximate and may change with
the sample or masking; they do not establish causal relationships.

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

With the API running, use a second terminal from the project root:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Open the URL printed by Vite. `VITE_API_BASE_URL` defaults to `/api`, and
`API_PROXY_TARGET` defaults to the local API. These are development settings;
the Docker frontend uses its same-origin Nginx proxy.

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

## CI/CD and Render deployment

`.github/workflows/ci.yml` runs Ruff, the Python test suite, and API/frontend
Docker image builds for pull requests. Connect the Render services to this
GitHub repository; Render builds the API and UI directly from `Dockerfile` and
`frontend/Dockerfile`. `.github/workflows/deploy.yml` triggers their Render
deploy hooks on pushes to `main`, waits for API readiness at `/health`, then
checks the API docs, a synthetic prediction, and the served frontend page.

Before enabling deployment, configure the following in the repository's
**Settings → Secrets and variables → Actions**:

| Name | Type | Value |
| --- | --- | --- |
| `RENDER_API_DEPLOY_HOOK_URL` | Secret | Deploy hook URL for the API Render service |
| `RENDER_UI_DEPLOY_HOOK_URL` | Secret | Deploy hook URL for the frontend Render service |
| `RENDER_API_URL` | Variable or Secret | Public API base URL, without a trailing slash or `/api` suffix |
| `RENDER_UI_URL` | Variable or Secret | Public frontend base URL |

In Render, connect the Blueprint to this GitHub repository and deploy the
`main` branch. The Blueprint defines Docker-based services named
`financial-exclusion-api` and `financial-exclusion-ui`; it needs no GHCR
packages or registry credentials. Render builds the UI against the API's public
`onrender.com` URL, which also works with free web services that cannot receive
private-network traffic. If you change the API service name, update
`API_UPSTREAM` in `render.yaml` to match its public URL.

The model and respondent-level modeling dataset stay out of Git and Docker
build contexts. The API restores both from one Render secret file at startup.
From the repository root, generate the private bundle with:

```powershell
python scripts/package_render_runtime_assets.py
```

In the API service's **Environment → Secret Files**, add a file named
`financial-exclusion-runtime-assets.b64` and paste in the complete contents of
`.secrets/financial-exclusion-runtime-assets.b64`. Render makes it available
to the container at `/etc/secrets/financial-exclusion-runtime-assets.b64`.
The current bundle is below Render's 1 MB combined secret-file limit. Keep it
private and out of Git; it contains survey-derived respondent records. Repeat
the packaging and upload steps whenever the model or modeling dataset changes.
The API extracts the files to writable runtime directories before loading the
model and SHAP background. Without this secret file, the API remains
unavailable. Do not put the model, dataset or deploy hook URLs in the repository.

The deployment workflow also performs a smoke prediction using a synthetic
record. This confirms the live API and UI respond; it does not validate model
quality or produce a nationally representative result.

## Project structure

- `src/data/`: workbook inspection, extraction, preparation, preprocessing and EDA.
- `src/models/`: model comparison, evaluation, explainability and loading.
- `src/pipeline.py`: isolated orchestration of the approved pipeline.
- `src/financial_exclusion/api/`: FastAPI application and request/response schemas.
- `src/financial_exclusion/config.py`: project paths and random seed.
- `frontend/`: React/Vite interface, tests, and Nginx container configuration.
- `data/raw/`: locally held original workbook; ignored by Git and Docker.
- `data/interim/`, `data/processed/`: generated datasets; ignored by Git and Docker.
- `documentation/`: data dictionary and methodology records.
- `notebooks/`: exploratory work only; implementation logic belongs in `src/`.
- `reports/`, `artifacts/`: generated outputs, ignored by default; requested
  reports and figures are tracked, while the fitted model is kept local.
- `tests/`: automated checks.
- `Dockerfile`, `docker-compose.yml`, `requirements-serving.txt`: containerized serving.

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

### Tests and verified results

From the project root, after installation:

```powershell
python -m pytest -q
Set-Location frontend
npm test
npm run build
```

On 2026-11-20, the local environment passed **73 Python tests** and **9
frontend tests**, and the frontend production build succeeded. The Python run
reported one Starlette TestClient deprecation warning. The Docker Compose
configuration, both container health checks, Swagger and a synthetic
browser-to-API prediction were also verified in the Docker phase. The local
model-dependent test is skipped when the trusted artifact is absent, so test
counts may differ on another machine.

## Research limitations and future work

- The provider's classification derivation and the `A07` PSU/EA and stratum
  crosswalks remain unverified. Obtain official technical documentation before
  asserting a verified derivation or full design-based analysis.
- The survey uses a complex design, but fitting, evaluation, split and folds
  are unweighted and not verified as cluster-aware. Define an estimand and
  assess appropriate survey-weighted and design-aware methods.
- Seek a separately approved independent evaluation; the existing held-out
  partition has already been inspected. Review threshold, class weights and
  calibration without tuning on that partition.
- Investigate unresolved `A20=95`, `S2__1` and `S4` coding/routing, and
  consider how source encoding and missingness affect generalization.
- SHAP describes approximate model associations, not causal effects. Small
  samples, correlated predictors and independently masked combinations limit
  interpretation.
- Validate fairness, privacy, security and suitability before any practical
  deployment. The SVM has no calibrated probabilities; its local artifact
  contains support vectors and must not be committed or exposed.

## Responsible and transparent AI use

See [AI_USE.md](AI_USE.md) for the project's disclosure and verification practices for AI-assisted work.
