# Methodology

## Status and scope

This document describes the planned research and engineering workflow. No target, predictor set, extracted dataset, or trained model has been approved or implemented. The original workbook in `data/raw/` is immutable.

## Research questions and target

The project will investigate prediction of financial exclusion in Kenya using the 2024 FinAccess Household Survey. The operational definition of financial exclusion must be verified in official FinAccess documentation before any target is constructed. The analysis must distinguish financial access, ownership, and actual usage; these concepts must not be treated as interchangeable.

Record the target definition, population and unit of analysis, reference period, source variables, exclusions, and alternative interpretations in this document and the decision log. If official materials do not resolve a material ambiguity, pause and seek researcher approval rather than inventing a definition.

## Workbook inspection and preparation

1. Inventory all workbook sheets, including hidden sheets, and inspect sheet metadata, dimensions, headers, formulas, and relevant documentation.
2. Confirm which sheet contains the respondent records; do not assume the first sheet does.
3. Stream or read only the confirmed sheet and required columns to control memory use.
4. Preserve the source workbook and write all derived outputs to separate interim or processed Parquet files.
5. Validate row counts, field types, identifiers, missing and special codes, and extraction results; record all transformations and provenance.

## Leakage control and preprocessing

The target's component variables and fields that directly encode, derive from, or reveal the outcome must not be used as predictors. Review candidate features for proxy leakage, post-outcome information, identifiers, and survey design fields. Record the exclusion rationale and test the approved feature list.

Split observations before fitting imputers, encoders, scalers, feature selection, or other learned transformations. Keep these steps in a pipeline so each cross-validation fold fits preprocessing only on its training partition. Any resampling must be justified and applied only within training folds.

## Survey design

Use official documentation to identify the relevant survey weights, strata, primary sampling units/clusters, and their intended use. The analysis plan must state the target population/estimand and justify how the sampling design affects splitting, cross-validation, fitting, evaluation, and uncertainty. Do not use weights as predictive features. Do not treat unweighted metrics as population-representative without justification.

## Modeling and evaluation

Compare suitable baseline and advanced classifiers after approving the outcome and predictors. Fix and record random seeds. Select models using an appropriate collection of metrics—not accuracy alone—including precision, recall, F1, ROC-AUC, and PR-AUC when appropriate. Report confusion matrices and document the threshold and weighting used for reported results. Consider calibration and class imbalance where appropriate to the research question and sampling design.

## Explainability

Use SHAP or another justified method compatible with the selected model. Report global and appropriate local explanations with limitations. Explanations describe model behavior and associations; they do not establish causal effects.

## Deployment and reproducibility

The API must use the same fitted preprocessing and model as training, load the approved artifact once at startup, and never train during a prediction request. Validate request fields and return informative errors. Build and test a Docker image without including the original workbook or generated datasets. Record software versions, configuration, seeds, model metadata, and the commands needed to reproduce results.
