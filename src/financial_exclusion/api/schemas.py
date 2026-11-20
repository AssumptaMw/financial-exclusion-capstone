"""Request and response contracts for the prediction service."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, field_validator

Category = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]
Indicator = Literal[0, 1]


class PredictionInput(BaseModel):
    """The original workbook representations of the approved predictors."""

    model_config = ConfigDict(extra="forbid")

    A18: Annotated[StrictInt, Field(ge=18, description="Adult respondent age; 98 and 99 are special responses.")]
    Sex: Category | None = Field(description="Workbook label for sex of selected individual.")
    A20: Category | None = Field(description="Workbook education label, or '95' for the unresolved code.")
    county: Category | None = Field(description="Workbook county label.")
    A08: Category | None = Field(description="Workbook rural/urban label.")
    B3A__2: Indicator | None = Field(description="Workbook employed income-source indicator: 0 or 1.")
    B3A__4: Indicator | None = Field(description="Workbook self-employed income-source indicator: 0 or 1.")
    B3Ii: Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)] | Literal["#NULL!"] | None = Field(
        description="Monthly income in KSh, #NULL!, or null; 98 and 99 are handled by the model."
    )
    ID_card: Category | None = Field(description="Workbook identification-document label.")
    S1: Category | None = Field(description="Workbook phone ownership/use label.")
    S3: Category | None = Field(description="Workbook internet-use frequency label.")
    A24i: Category | None = Field(description="Workbook difficulty-seeing label.")
    A24ii: Category | None = Field(description="Workbook difficulty-hearing label.")
    A24iii: Category | None = Field(description="Workbook difficulty-walking label.")
    A24iv: Category | None = Field(description="Workbook difficulty-remembering label.")
    A24v: Category | None = Field(description="Workbook self-care difficulty label.")
    A24vi: Category | None = Field(description="Workbook communication difficulty label.")

    @field_validator("A18")
    @classmethod
    def reject_age_special_codes(cls, value: int) -> int:
        if value in (98, 99):
            raise ValueError("98 and 99 are special age responses, not eligible ages.")
        return value

    @field_validator("B3A__2", "B3A__4", mode="before")
    @classmethod
    def validate_indicator_type(cls, value: object) -> object:
        if value is not None and type(value) is not int:
            raise ValueError("Indicator must be 0, 1, or null.")
        return value

    @field_validator(
        "Sex", "A20", "county", "A08", "ID_card", "S1", "S3",
        "A24i", "A24ii", "A24iii", "A24iv", "A24v", "A24vi",
    )
    @classmethod
    def reject_blank_category(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Use null for a missing category, not blank text.")
        return value


class BatchPredictionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: Annotated[list[PredictionInput], Field(min_length=1, max_length=100)]


class PredictionOutput(BaseModel):
    financial_exclusion_status: Literal[0, 1]
    label: Literal["Financially included", "Financially excluded"]


class ContributorExplanation(BaseModel):
    """A single contributor to the prediction."""

    variable: str
    label: str
    shap_value: float
    direction: Literal["towards excluded", "towards included"]


class PredictionWithExplanation(PredictionOutput):
    """Extended prediction with SHAP explanation."""

    explanation: dict[str, object] | None = Field(
        description="SHAP explanation; null if computation failed or was disabled."
    )


class BatchPredictionOutput(BaseModel):
    predictions: list[PredictionOutput]

