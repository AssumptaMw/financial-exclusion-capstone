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

Target construction, modeling, and deployment remain future stages.

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

## Project structure

- `src/financial_exclusion/`: importable application package, configuration, and data, feature, model, evaluation, and API modules.
- `data/raw/`: locally held original workbook; ignored by Git and Docker.
- `data/interim/`, `data/processed/`: generated datasets; ignored by Git and Docker.
- `documentation/`: data dictionary and methodology records.
- `notebooks/`: exploratory work only; implementation logic belongs in `src/`.
- `reports/`, `artifacts/`: generated outputs; not committed by default.
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
