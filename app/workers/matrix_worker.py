from app.lib.db import get_db
from app.repositories.matrix_repository import MatrixRepository
from app.schemas.matrix_schema import MatrixResultInsert
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)


async def process_matrix_results_batch_job(matrix_payloads: list[MatrixResultInsert]):
    logger.info(
        "Processing batch job for %s matrix results",
        len(matrix_payloads),
    )

    if matrix_payloads:
        first = matrix_payloads[0]

        logger.info(
            "Saving matrix results | simulation_id=%s | type=%s | stage=%s | records=%s",
            first.simulation_id,
            first.matrix_type.value,
            first.matrix_stage,
            len(matrix_payloads),
        )

    db_session = get_db()
    db = next(db_session)

    try:
        logger.info("Starting database transaction for matrix batch job")

        matrix_repo = MatrixRepository(db)
        await matrix_repo.bulk_create_matrix_results(matrix_payloads)

        logger.info(
            "Successfully saved %s matrix results",
            len(matrix_payloads),
        )

    except Exception:
        logger.exception("Failed to save matrix results batch")
        db.rollback()
        raise

    finally:
        db.close()