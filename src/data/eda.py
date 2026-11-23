"""Reproducible, training-only descriptive analysis of FinAccess data."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import textwrap
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.data.feature_engineering import (
    MODEL_METADATA_KEY,
    MODELING_DATASET_PATH,
    PREDICTOR_COLUMNS,
)
from src.data.preprocessing import _coerce_numeric, split_modeling_data
from src.financial_exclusion.config import RANDOM_SEED, REPORTS_DIR

LOGGER = logging.getLogger(__name__)
EDA_REPORT_PATH = REPORTS_DIR / "results" / "eda_report.md"
EDA_FIGURES_DIR = REPORTS_DIR / "figures"
NUMERIC_COLUMNS = ("A18", "B3Ii")
CATEGORICAL_COLUMNS = tuple(
    column for column in PREDICTOR_COLUMNS if column not in NUMERIC_COLUMNS
)
AGE_LABELS = ("18-24", "25-34", "35-44", "45-54", "55-64", "65+")


def load_training_data(path: Path = MODELING_DATASET_PATH) -> tuple[pd.DataFrame, pd.Series]:
    """Load the approved model data and return only the existing training split."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Modeling dataset does not exist: {path}")
    table = pq.read_table(path)
    metadata = table.schema.metadata or {}
    if MODEL_METADATA_KEY not in metadata:
        raise ValueError("Modeling dataset is missing predictor provenance metadata.")
    provenance = json.loads(metadata[MODEL_METADATA_KEY])
    if provenance.get("predictors") != list(PREDICTOR_COLUMNS):
        raise ValueError("Modeling dataset predictors do not match the approved feature list.")
    X_train, _, y_train, _ = split_modeling_data(table.to_pandas())
    return X_train, y_train


def grouped_exclusion(values: pd.Series, target: pd.Series) -> pd.DataFrame:
    """Return unweighted counts and exclusion percentages for every observed group."""
    if not values.index.equals(target.index):
        raise ValueError("Predictor and target indices must match.")
    if target.isna().any() or not target.isin([0, 1]).all():
        raise ValueError("Target values must be non-null binary classes.")
    groups = values.astype("object").where(values.notna(), "<null>")
    frame = pd.DataFrame({"group": groups, "target": target}, index=target.index)
    result = frame.groupby("group", sort=False, dropna=False)["target"].agg(
        respondents="size", excluded="sum"
    )
    result["excluded"] = result["excluded"].astype("int64")
    result["excluded_pct"] = 100 * result["excluded"] / result["respondents"]
    return result.sort_values("respondents", ascending=False)


def quality_summary(X: pd.DataFrame) -> pd.DataFrame:
    """Count actual nulls, blanks, Excel errors and field-specific special codes."""
    if tuple(X.columns) != PREDICTOR_COLUMNS:
        raise ValueError("EDA input must contain exactly the approved predictors in order.")
    rows = []
    for column in PREDICTOR_COLUMNS:
        values = X[column]
        text = values.astype("string")
        rows.append(
            {
                "field": column,
                "dtype": str(values.dtype),
                "null": int(values.isna().sum()),
                "blank": int(text.str.strip().eq("").fillna(False).sum()),
                "excel_error": int(text.str.startswith("#").fillna(False).sum()),
                "special_or_unresolved": int(
                    text.isin(["95"]).sum() if column == "A20"
                    else text.isin(["98", "99"]).sum() if column == "B3Ii"
                    else 0
                ),
                "distinct_non_null": int(values.nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows).set_index("field")


def numeric_associations(X: pd.DataFrame) -> pd.DataFrame:
    """Pairwise Pearson correlations for age, income and binary livelihood fields."""
    numeric = _coerce_numeric(X.loc[:, NUMERIC_COLUMNS])
    for column in ("B3A__2", "B3A__4"):
        numeric[column] = pd.to_numeric(X[column], errors="raise")
    rows = []
    for first, second in combinations(numeric.columns, 2):
        pair = numeric.loc[:, [first, second]].dropna()
        if len(pair) >= 2 and pair[first].nunique() > 1 and pair[second].nunique() > 1:
            corr = pair[first].corr(pair[second])
        else:
            corr = np.nan
        rows.append({"first": first, "second": second, "n": len(pair), "pearson_r": corr})
    return pd.DataFrame(rows)


def categorical_associations(X: pd.DataFrame) -> pd.DataFrame:
    """Calculate descriptive Cramer's V for categorical predictor pairs."""
    rows = []
    for first, second in combinations(CATEGORICAL_COLUMNS, 2):
        pair = X.loc[:, [first, second]].dropna()
        table = pd.crosstab(pair[first], pair[second])
        n = int(table.to_numpy().sum())
        dimension = min(table.shape) - 1
        if n == 0 or dimension <= 0:
            value = np.nan
        else:
            observed = table.to_numpy(dtype=float)
            expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / n
            value = float(np.sqrt(((observed - expected) ** 2 / expected).sum() / (n * dimension)))
        rows.append({"first": first, "second": second, "n": n, "cramers_v": value})
    return pd.DataFrame(rows).sort_values("cramers_v", ascending=False, na_position="last")


def _markdown_table(frame: pd.DataFrame, *, index_label: str | None = None) -> str:
    """Render a small Markdown table without requiring an extra table package."""
    if index_label is not None:
        frame = frame.rename_axis(index_label).reset_index()
    def format_value(value: object) -> str:
        if pd.isna(value):
            return "NA"
        if isinstance(value, (float, np.floating)):
            return f"{value:.2f}"
        return str(value).replace("|", r"\|").replace("\n", " ")
    columns = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(format_value(value) for value in row) + " |")
    return "\n".join(lines)


def _rate_figure(groups: pd.DataFrame, title: str, path: Path) -> None:
    labels = [textwrap.fill(str(label), width=35) for label in groups.index]
    height = max(3.8, min(18.0, len(groups) * 0.3 + 2.0))
    fig, ax = plt.subplots(figsize=(9, height), layout="constrained")
    positions = np.arange(len(groups))
    ax.barh(positions, groups["excluded_pct"], color="#32658a")
    ax.set_yticks(positions, labels=labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 115)
    ax.set_xticks(np.arange(0, 101, 20))
    ax.set_xlabel("Financially excluded (% of group; unweighted training sample)")
    ax.set_title(title)
    for pos, (_, row) in enumerate(groups.iterrows()):
        ax.text(row["excluded_pct"] + 1, pos, f"{row['excluded_pct']:.1f}% (n={int(row['respondents']):,})", va="center", fontsize=8)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def run_eda(
    dataset_path: Path = MODELING_DATASET_PATH,
    report_path: Path = EDA_REPORT_PATH,
    figures_dir: Path = EDA_FIGURES_DIR,
) -> dict[str, object]:
    """Create training-only descriptive tables, figures and an auditable report."""
    dataset_path = Path(dataset_path)
    report_path = Path(report_path)
    figures_dir = Path(figures_dir)
    if dataset_path.resolve() == report_path.resolve():
        raise ValueError("EDA report must not overwrite the modeling dataset.")
    X, y = load_training_data(dataset_path)
    schema = pq.read_schema(dataset_path)
    quality = quality_summary(X)
    numeric = _coerce_numeric(X.loc[:, NUMERIC_COLUMNS])
    age_groups = pd.cut(
        numeric["A18"],
        bins=[18, 25, 35, 45, 55, 65, np.inf],
        labels=AGE_LABELS,
        right=False,
    )
    age_table = grouped_exclusion(age_groups, y)
    grouped = {column: grouped_exclusion(X[column], y) for column in CATEGORICAL_COLUMNS}
    classes = y.value_counts().reindex([0, 1], fill_value=0)
    class_table = pd.DataFrame(
        {"class": ["Included (0)", "Excluded (1)"], "respondents": classes.to_numpy(),
         "percent": 100 * classes.to_numpy() / len(y)}
    )
    income = pd.DataFrame({"income": numeric["B3Ii"], "target": y})
    income_summary = income.groupby("target")["income"].agg(
        available="count", minimum="min", median="median", mean="mean", maximum="max"
    )
    income_summary["missing_or_unresolved"] = income.groupby("target")["income"].size() - income_summary["available"]
    numerical_pairs = numeric_associations(X)
    categorical_pairs = categorical_associations(X)
    figure_tables = {
        "eda_age.png": (age_table, "Exclusion by age group"),
        "eda_sex.png": (grouped["Sex"], "Exclusion by respondent sex"),
        "eda_education.png": (grouped["A20"], "Exclusion by education response"),
        "eda_county.png": (grouped["county"], "Exclusion by county"),
        "eda_rural_urban.png": (grouped["A08"], "Exclusion by rural/urban classification"),
    }
    figures_dir.mkdir(parents=True, exist_ok=True)
    for filename, (groups, title) in figure_tables.items():
        _rate_figure(groups, title, figures_dir / filename)
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    ax.bar(class_table["class"], class_table["percent"], color=["#32658a", "#b45c38"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Respondents (% of unweighted training sample)")
    ax.set_title("Financial exclusion target class composition")
    for pos, row in class_table.iterrows():
        ax.text(pos, row["percent"] + 1, f"{row['percent']:.1f}% (n={int(row['respondents']):,})", ha="center")
    fig.savefig(figures_dir / "eda_target.png", dpi=140)
    plt.close(fig)

    digest = hashlib.sha256()
    with dataset_path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    lines = [
        "# FinAccess exploratory data analysis",
        "",
        "## Scope and reproducibility",
        "",
        f"- Source: `{dataset_path.name}`; SHA-256: `{digest.hexdigest()}`.",
        f"- Dataset: {pq.read_metadata(dataset_path).num_rows:,} rows and {len(schema.names)} columns; approved predictors: {len(PREDICTOR_COLUMNS)}.",
        f"- Training partition: {len(X):,} adult respondents, 17 predictors and the existing binary target.",
        f"- Existing stratified 80/20 split, random seed {RANDOM_SEED}; only training rows are summarized.",
        "- All counts, percentages, associations and plots are unweighted descriptions of the training sample, not national estimates or statistical inference.",
        "- No causal interpretation, feature selection, resampling, imputation, model fitting, or test-set analysis was performed.",
        "- `Overall_Access_fnl` supplies the existing target; the provider's original classification derivation has not been independently verified.",
        "- `S2__1`, `S4`, the two original outcome columns, `indWeight`, and `A07` are not predictors. Weights and the survey design were not used; PSU/strata crosswalks remain unverified.",
        "- Group rates use all rows in each displayed group as the denominator, including explicit special/error categories; counts are not population estimates.",
        "",
        "## Source dataset schema",
        "",
        "These Parquet types describe the dataset schema only; non-predictor columns are not analyzed.",
        "",
        _markdown_table(pd.DataFrame([{"column": field.name, "Parquet type": str(field.type)} for field in schema])),
        "",
        "## Target class distribution",
        "",
        _markdown_table(class_table),
        "",
        f"The training sample contains {int(classes[1]):,} excluded respondents ({100 * classes[1] / len(y):.2f}%) and {int(classes[0]):,} included respondents ({100 * classes[0] / len(y):.2f}%). This is a class imbalance in the sampled training data.",
        "",
        "![Training target composition](../figures/eda_target.png)",
        "",
        "## Predictor data types and unusual values",
        "",
        "Counts are raw training values. `excel_error` counts strings beginning `#`; blanks and nulls are separate. The final column counts distinct non-null source values.",
        "`special_or_unresolved` counts only A20 `95` and B3Ii `98`/`99`; other explicit refusal/Don't know labels remain in categorical tables and are not globally recoded.",
        "`A20=95` has no verified label; its approved preprocessing treatment as missing is not applied in these raw descriptive tables.",
        "",
        _markdown_table(quality, index_label="field"),
        "",
        "## Age and target",
        "",
        "Age groups are descriptive fixed intervals, not a feature-engineering or selection decision. Group denominators and excluded counts are shown.",
        "",
        _markdown_table(age_table, index_label="age group (years)"),
        "",
        "![Exclusion by age](../figures/eda_age.png)",
        "",
        "## Sex, education, and geography",
        "",
        "County and education groups with few respondents or unusual response labels can have unstable sample percentages. Labels are preserved from the data.",
        "",
        "![Exclusion by sex](../figures/eda_sex.png)",
        "",
        "![Exclusion by education](../figures/eda_education.png)",
        "",
        "![Exclusion by county](../figures/eda_county.png)",
        "",
        "![Exclusion by rural/urban type](../figures/eda_rural_urban.png)",
        "",
        "## Livelihood and income",
        "",
        "`B3A__2` and `B3A__4` are source indicators, not verified measures of current employment. Their original 0/1 values are shown without inventing meanings.",
        "`B3Ii` is monthly income in KSh. The existing field-specific numeric conversion treats nonnumeric values, nonfinite values, and 98/99 as missing; no imputation is applied here.",
        "",
        _markdown_table(income_summary, index_label="target (0 included, 1 excluded)"),
        "",
        "## Identification, general digital access, and functional difficulties",
        "",
        "`ID_card` is a combined identification-document field, not national ID alone. `S1` and `S3` describe general phone/internet access or use, not financial transactions. Each A24 item is reported separately.",
        "",
        "## All categorical predictors versus the target",
        "",
        "Tables report raw category labels, respondent counts, excluded counts, and within-category percentages for each of the 15 approved categorical predictors.",
        "",
    ]
    for column in CATEGORICAL_COLUMNS:
        lines.extend([f"### `{column}`", "", _markdown_table(grouped[column], index_label="source value"), ""])
    lines.extend(
        [
            "## Potential redundancy: descriptive associations only",
            "",
            "Pearson correlations use pairwise available values of raw age, numeric income, and the two binary livelihood indicators; no scaling or imputation is used. Pairwise sample sizes differ.",
            "",
            _markdown_table(numerical_pairs),
            "",
            "The ten largest descriptive Cramer's V values across the 15 categorical predictors are shown below. Source response and Excel error tokens remain categories; null pairs are excluded. High-cardinality variables and small cells can inflate associations. These are exploratory associations, not significance tests or grounds for dropping predictors.",
            "",
            _markdown_table(categorical_pairs.head(10)),
            "",
            "## Limitations",
            "",
            "Results are descriptive, unweighted and cross-sectional. They cannot establish causation, national representativeness or design-corrected uncertainty. No population inference or feature-selection decision is made from these summaries.",
            "Some category labels contain original workbook encoding artifacts; they are not silently normalized. S2/S4 routing and S2 export codes, A20=95, income error tokens, and the provider target derivation remain unresolved.",
            "The 80/20 split is stratified by target but is not confirmed as cluster- or survey-design-aware; further design review is required.",
            "",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("EDA report: %s; training rows: %s", report_path, len(X))
    return {
        "training_rows": len(X),
        "predictors": len(PREDICTOR_COLUMNS),
        "class_counts": {int(key): int(value) for key, value in classes.items()},
        "report_path": report_path,
        "figures": [figures_dir / name for name in (*figure_tables, "eda_target.png")],
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run_eda()
    except (OSError, ValueError, TypeError, KeyError):
        LOGGER.exception("FinAccess EDA failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
