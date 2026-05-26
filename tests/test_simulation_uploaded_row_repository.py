from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.schemas.simulation_job_uploaded_row_schema import CreateSimulationUploadedRowSchema


class _DuplicateKeyError(Exception):
    def __str__(self) -> str:
        return 'duplicate key value violates unique constraint "simulation_uploaded_rows_pkey"'


def test_insert_uploaded_rows_repairs_stale_sequence_and_retries(mocker) -> None:
    mock_db = mocker.Mock()
    mock_db.execute.side_effect = [
        IntegrityError("insert", {}, _DuplicateKeyError()),
        None,
        None,
    ]

    repository = SimulationUploadedRowRepository(mock_db)
    rows = [
        CreateSimulationUploadedRowSchema(
            simulation_job_id="150fb632-7499-4b4f-87fb-11a4ded53e91",
            nosi="N-1",
            created_at=datetime(2026, 5, 26, 0, 0, tzinfo=timezone.utc),
        )
    ]

    import asyncio

    asyncio.run(repository.insert_uploaded_rows(rows))

    assert mock_db.execute.call_count == 3
    assert mock_db.rollback.call_count == 1
    assert mock_db.commit.call_count == 1
    assert "setval" in str(mock_db.execute.call_args_list[1].args[0])