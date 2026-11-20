# AI use and disclosure

## Use in this project

GitHub Copilot was used during development primarily for **debugging, troubleshooting and a limited number of implementations**. The assistance included:
- Code debugging and error resolution
- Implementation of specific modules and functions
- Code review and suggestions
- Documentation improvements and revisions

The researcher provided all project requirements, made or approved all research decisions, reviewed all AI-assisted changes, and validated intermediate findings and results.

## Review and validation

AI suggestions are not authoritative research evidence. The researcher is responsible for reviewing AI-assisted code, verifying correctness, checking official FinAccess documentation, approving methodological decisions and ensuring that the code and results are appropriate and reproducible. The project's recorded validation includes automated Python and frontend tests, model and data provenance checks, and synthetic API and Docker checks; these tests do not replace human review or independently validate survey methodology.

The [README](README.md) and [evaluation report](reports/results/model_evaluation_report.md) record the results and their limitations.

In particular:
- The provider's target derivation remains unverified
- The previously inspected test partition is not a pristine independent assessment
- SHAP outputs are approximate model associations, not causal explanations
- Survey design complexities and sampling weights are not incorporated in the analysis

## Privacy and accountability

Do not upload the raw FinAccess workbook, respondent records, the fitted model with support vectors, credentials, personal information or other restricted material to an AI service. Use only tools and data handling allowed by the dataset terms and institutional policy.

The researcher remains accountable for the accuracy, privacy, integrity and appropriate use of the final work, regardless of AI involvement.
