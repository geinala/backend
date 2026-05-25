from sqlalchemy.orm import Session

from app.models.matrix import MatrixBatch, MatrixBatchStatusEnum, MatrixResult
from app.schemas.matrix_schema import CreateMatrixBatchData, CreateMatrixResultData, UpdateMatrixBatchStatusData


class MatrixRepository:
    def __init__(self, db: Session):
        self.db = db

    def has_batches_by_simulation_id(self, simulation_id: str) -> bool:
        return self.db.query(MatrixBatch).filter(
            MatrixBatch.simulation_id == simulation_id
        ).first() is not None

    def get_batches_by_simulation_id(self, simulation_id: str, status: MatrixBatchStatusEnum | None = None) -> list[MatrixBatch]:
        query = self.db.query(MatrixBatch).filter(MatrixBatch.simulation_id == simulation_id)
        if status is not None:
            query = query.filter(MatrixBatch.status == status)
        return query.all()
        
    def get_matrix_results_by_simulation_id(self, simulation_id: str) -> list[MatrixResult]:
        return self.db.query(MatrixResult).filter(
            MatrixResult.simulation_id == simulation_id
        ).all()

    def insert_matrix_batch(self, data: CreateMatrixBatchData) -> MatrixBatch:
        batch = MatrixBatch(
            simulation_id=data.simulation_id,
            origin_start_index=data.origin_start_index,
            origin_end_index=data.origin_end_index,
            destination_start_index=data.destination_start_index,
            destination_end_index=data.destination_end_index,
            tomtom_job_id=data.tomtom_job_id,
            status=data.status,
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def bulk_insert_matrix_batches(self, insert_data: list[CreateMatrixBatchData]) -> list[MatrixBatch]:
        batches = [
            MatrixBatch(
                simulation_id=data.simulation_id,
                origin_start_index=data.origin_start_index,
                origin_end_index=data.origin_end_index,
                destination_start_index=data.destination_start_index,
                destination_end_index=data.destination_end_index,
                tomtom_job_id=data.tomtom_job_id,
                status=data.status,
            )
            for data in insert_data
        ]
        self.db.add_all(batches)
        self.db.commit()
        for batch in batches:
            self.db.refresh(batch)
        return batches

    def insert_matrix_result(self, data: CreateMatrixResultData) -> MatrixResult:
        result = MatrixResult(
            simulation_id=data.simulation_id,
            origin_index=data.origin_index,
            destination_index=data.destination_index,
            length_in_meters=data.length_in_meters,
            travel_time_in_seconds=data.travel_time_in_seconds,
            traffic_delay_in_seconds=data.traffic_delay_in_seconds,
            matrix_batch_id=data.matrix_batch_id,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def bulk_insert_matrix_results(self, insert_data: list[CreateMatrixResultData]) -> list[MatrixResult]:
        results = [
            MatrixResult(
                simulation_id=data.simulation_id,
                origin_index=data.origin_index,
                destination_index=data.destination_index,
                length_in_meters=data.length_in_meters,
                travel_time_in_seconds=data.travel_time_in_seconds,
                traffic_delay_in_seconds=data.traffic_delay_in_seconds,
                matrix_batch_id=data.matrix_batch_id,
            )
            for data in insert_data
        ]
        self.db.add_all(results)
        self.db.commit()
        for result in results:
            self.db.refresh(result)
        return results

    def has_failed_batches(self, simulation_id: str) -> bool:
        return self.db.query(MatrixBatch).filter(
            MatrixBatch.simulation_id == simulation_id,
            MatrixBatch.status == MatrixBatchStatusEnum.failed
        ).first() is not None

    def delete_all_batches_and_results(self, simulation_id: str) -> None:
        self.db.query(MatrixResult).filter(
            MatrixResult.simulation_id == simulation_id
        ).delete()
        self.db.query(MatrixBatch).filter(
            MatrixBatch.simulation_id == simulation_id
        ).delete()
        self.db.commit()

    def update_matrix_batch_status(self, batch_id: int, data: UpdateMatrixBatchStatusData) -> MatrixBatch | None:
        batch = self.db.query(MatrixBatch).filter(MatrixBatch.id == batch_id).first()
        if not batch:
            return None
        batch.status = data.status
        if data.completed_at:
            batch.completed_at = data.completed_at
        self.db.commit()
        self.db.refresh(batch)
        return batch