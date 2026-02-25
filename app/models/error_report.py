from typing import TypedDict

class ValidationError:
    def __init__(
        self,
        row_number: int,
        field_name: str,
        invalid_value: str,
        error_message: str,
    ):
        self.row_number = row_number
        self.field_name = field_name
        self.invalid_value = invalid_value
        self.error_message = error_message
    
    def to_dict(self) -> dict[str, str]:
        return {
            "row_number": str(self.row_number),
            "field_name": self.field_name,
            "invalid_value": self.invalid_value,
            "error_message": self.error_message,
        }
        
class CSVValidationResult(TypedDict):
    errors: list[ValidationError]
    row_count: int
    invalid_row_count: int