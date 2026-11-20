# Methodology

## Status and scope

This document describes the research and engineering workflow. The approved
target, predictor set and adult modeling dataset are documented in
`variable_selection.md`; the original workbook in `data/raw/` is immutable.
Model comparison and held-out evaluation are implemented, while the provider's
original classification derivation and the survey-design crosswalk remain
unverified.

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

### Implemented Phase 8 experiment

The established stratified 80/20 split (seed 42) is reused. The approved
proposal's four candidates are logistic regression, random forest, XGBoost and
an RBF SVM. Logistic regression, random forest and SVM use balanced class
weights; XGBoost computes its positive-class weight from the negative/positive
ratio within each fit. Fixed settings are used without resampling or
hyperparameter tuning. Each candidate's complete preprocessing and estimator
are fit separately in five shuffled stratified training folds (seed 42).
Highest mean F1 for the excluded class selects the model; mean recall breaks a
tie, followed by the fixed candidate order in an exact tie. The selected
pipeline is refit on all training data before held-out evaluation at its
default decision threshold. SVM ROC-AUC and PR-AUC use decision scores, not
calibrated probabilities.

The same held-out partition was evaluated in the earlier two-model experiment.
The researcher approved reusing it for the expanded proposal comparison, but
it is no longer a pristine independent assessment. Do not use its results to
revise model selection or tune the threshold. A fresh independent evaluation
requires separately approved data or design.
The selected SVM stores transformed training observations as support vectors.
Its fitted pipeline must remain local rather than being committed as an
artifact; the previously tracked logistic-regression artifact remains in Git
history.

Precision, recall, F1, accuracy, ROC-AUC and PR-AUC are unweighted; PR-AUC is
reported as average precision, a step-weighted area. The report includes a
confusion matrix and classification report. These metrics describe this sample
split, not national performance; neither the split nor cross-validation is
verified as cluster-aware. Survey weights are not used in fitting or
evaluation, and the proper design-aware estimand remains unresolved. The
results are cross-sectional associations, not causal findings. Exact settings,
versions and results are saved alongside the experiment outputs.

## Explainability

Use SHAP or another justified method compatible with the selected model. Report global and appropriate local explanations with limitations. Explanations describe model behavior and associations; they do not establish causal effects.

The selected RBF SVM is explained with model-agnostic Kernel SHAP applied to
the complete fitted pipeline's class-1 decision margin, not probabilities.
Original input variables are masked as groups before preprocessing, keeping
each variable's one-hot levels and missing indicator together. A reproducible,
disjoint training-only background and global explanation sample are used; the
local example is a synthetic composite of training modes among cases predicted
excluded. The report records sample sizes, approximation budget, hashes and
transformed-to-source mapping. Mean absolute SHAP values are unweighted
descriptions of the selected sample. Independent masking can create
implausible combinations and correlations can redistribute contributions;
rankings may change with the sample and approximation settings.

## Deployment and reproducibility

The API must use the same fitted preprocessing and model as training, load the approved artifact once at startup, and never train during a prediction request. Validate request fields and return informative errors. Build and test a Docker image without including the original workbook or generated datasets. Record software versions, configuration, seeds, model metadata, and the commands needed to reproduce results.
