from unittest.mock import MagicMock

from app.services.pre_processing.data_cleaning_service import DataCleaningService


def build_service() -> DataCleaningService:
    return DataCleaningService(
        simulation_job_repository=MagicMock(),
        simulation_uploaded_row_repository=MagicMock(),
    )


def test_remove_geographic_terms_preserves_extracted_street():
    service = build_service()

    cleaned = service._clean_text("Jl Soekarno Hatta Klojen Malang")
    extracted_street = service._extract_street_name(cleaned)

    sanitized = service._remove_geographic_terms(
        cleaned,
        preserved_phrase=extracted_street,
    )

    assert sanitized == "jalan soekarno hatta"


def test_prepare_row_for_cleaning_strips_geographic_terms_before_fuzzy():
    service = build_service()

    prepared = service._prepare_row_for_cleaning(
        address="Jl Soekarno Hatta Klojen Malang",
        city="KOTA MALANG",
    )

    assert prepared["cleaned"] == "jalan soekarno hatta"
    assert prepared["query"] == "jalan soekarno hatta malang"
    assert "klojen" not in prepared["query"]
    assert prepared["address_type"] == "street"
