from typing import TypedDict

from app.models.error_report import ValidationError


class CSVValidationResult(TypedDict):
    errors: list[ValidationError]
    row_count: int
    invalid_row_count: int
