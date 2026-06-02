from app.services.pre_processing.data_validation_service import DataValidationService


def test_deduplicate_rows_by_nosi_keeps_first_occurrence() -> None:
    rows = [
        {"Nosi": "N-1", "Courier": "A"},
        {"Nosi": "N-1", "Courier": "B"},
        {"Nosi": "N-2", "Courier": "C"},
        {"Nosi": "", "Courier": "D"},
        {"Courier": "E"},
    ]

    deduplicated_rows = DataValidationService._deduplicate_rows_by_nosi(rows)

    assert deduplicated_rows == [
        {"Nosi": "N-1", "Courier": "A"},
        {"Nosi": "N-2", "Courier": "C"},
        {"Nosi": "", "Courier": "D"},
        {"Courier": "E"},
    ]