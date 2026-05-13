import re
import time as time_module
from datetime import datetime, timezone

from app.repositories.simulation_job_repository import SimulationJobRepository
from app.repositories.simulation_uploaded_row_repository import SimulationUploadedRowRepository
from app.lib.logging.logging import get_logger
from app.models.simulation_job import (
    SimulationJobFileCleaningStatusEnum,
    SimulationJobFileValidationStatusEnum,
)
from app.schemas.simulation_job_schema import SimulationJobUpdateData
from app.models.simulation_uploaded_row import ResolutionStatusEnum
from app.models.simulation_job import SimulationJobStatusEnum

logger = get_logger(__name__)

ALIAS_MAP = {
    "jl": "jalan",
    "jln": "jalan",
    "perum": "perumahan",
    "gg": "gang",
    "resindence": "residence",
    "resindent": "residence",
    "resd": "residence",
    "la": "laksda",
    "lasucipto": "laksda adi sucipto",
    "pbi": "pondok blimbing indah",
    "r": "raden",
    "rp": "raden panji",
    "a": "ahmad",
    "jend": "jenderal",
    "per": "perumahan",
}

NOISE_WORDS = {
    "no", "nomor",
    "rt", "rw",
    "kel", "kelurahan",
    "kec", "kecamatan",
    "kota", "provinsi",
    "pagar", "kuning",
    "gang", "blok", "block",
    "rmh", "rumah",
    "blkg", "belakang",
    "toko", "ruko",
}

RESIDENTIAL_KEYWORDS = {
    "perumahan",
    "cluster",
    "residence",
    "estate",
    "graha",
}

STOP_AFTER_STREET = {
    "perumahan",
    "cluster",
    "residence",
    "estate",
    "graha",
}

BLOCK_PATTERN = re.compile(r"^[a-z]{1,2}\d+$", re.IGNORECASE)
HOUSE_TOKEN_PATTERN = re.compile(r"^(?:\d+[a-z]{0,2}|[a-z]{1,2}\d+[a-z]{0,2})$", re.IGNORECASE)
ROMAN_NUMERAL_PATTERN = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)

class DataCleaningService:
    def __init__(
        self,
        simulation_job_repository: SimulationJobRepository,
        simulation_uploaded_row_repository: SimulationUploadedRowRepository
    ):
        self.simulation_job_repository = simulation_job_repository
        self.simulation_uploaded_row_repository = simulation_uploaded_row_repository
    
    async def run(self, simulation_job_id: str) -> dict[str, object] | None:
        start_time = time_module.time()
        cleaning_started_at = datetime.now(timezone.utc)
        wide_event: dict[str, object] = {
            "event_type": "simulation_clean_uploaded_rows",
            "simulation_job_id": simulation_job_id,
            "status": "processing",
        }

        try:
            simulation_job = await self.simulation_job_repository.get_simulation_job_by_id(simulation_job_id)

            if not simulation_job:
                raise ValueError(f"Simulation job with ID {simulation_job_id} not found.")

            if simulation_job.file_validation_status != SimulationJobFileValidationStatusEnum.completed:
                raise ValueError(f"Cannot start cleaning process for simulation job {simulation_job_id} because file validation is not completed. Current status: {simulation_job.file_validation_status}")

            uploaded_rows = await self.simulation_uploaded_row_repository.get_uploaded_rows_by_simulation_job_id(
                simulation_job_id=simulation_job_id
            )

            if not uploaded_rows:
                raise ValueError(f"No uploaded rows found for simulation job {simulation_job_id}. Cannot proceed with cleaning process.")

            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    cleaning_status=SimulationJobFileCleaningStatusEnum.in_progress,
                    cleaning_started_at=cleaning_started_at,
                    cleaning_completed_at=None,
                    cleaning_progress_percentage=0,
                    updated_at=datetime.now(timezone.utc),
                ),
            )

            cleaned_rows: list[dict[str, object]] = []
            total_rows = len(uploaded_rows)
            progress_update_interval = max(1, total_rows // 20)  # ~5% granularity

            for index, row in enumerate(uploaded_rows, start=1):
                prepared = self._prepare_row_for_cleaning(
                    address=row.address,
                    city=row.city,
                )
                cleaned_row: dict[str, object] = {
                    "id": row.id,
                    "normalized_address": prepared.get("cleaned"),
                    "suggested_address": prepared.get("query"),
                    "final_address": prepared.get("query"),
                    "resolution_status": ResolutionStatusEnum.auto_solved,
                    "resolution_source": "SYSTEM",
                }

                cleaned_rows.append(cleaned_row)

                if index % progress_update_interval == 0 or index == total_rows:
                    progress = int((index / total_rows) * 100)
                    await self.simulation_job_repository.update_simulation_job(
                        simulation_job_id=simulation_job_id,
                        update_data=SimulationJobUpdateData(
                            cleaning_progress_percentage=progress,
                            updated_at=datetime.now(timezone.utc),
                        ),
                    )

            await self.simulation_uploaded_row_repository.update_cleaned_rows(cleaned_rows=cleaned_rows)
            
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    cleaning_status=SimulationJobFileCleaningStatusEnum.completed,
                    cleaning_started_at=cleaning_started_at,
                    cleaning_completed_at=datetime.now(timezone.utc),
                    cleaning_progress_percentage=100,
                    updated_at=datetime.now(timezone.utc),
                    current_step=3
                )
            )

            wide_event["status"] = "success"
            wide_event["processed_rows"] = len(cleaned_rows)
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)

            return {"simulation_job_id": simulation_job_id, "processed_rows": len(cleaned_rows)}

        except Exception as e:
            await self.simulation_job_repository.update_simulation_job(
                simulation_job_id=simulation_job_id,
                update_data=SimulationJobUpdateData(
                    cleaning_status=SimulationJobFileCleaningStatusEnum.failed,
                    cleaning_completed_at=datetime.now(timezone.utc),
                    status=SimulationJobStatusEnum.failed,
                    updated_at=datetime.now(timezone.utc),
                    ),
                )
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise e

    def _prepare_row_for_cleaning(self, address: str | None, city: str | None, default_city: str = "malang") -> dict[str, str | None]:
        cleaned = self._clean_text(address)
        address_type = self._detect_address_type(cleaned)
        street = self._extract_street_name(cleaned)
        fallback = self._extract_city_fallback(city)

        filtered: list[str] = []
        for token in cleaned.split():
            if token in NOISE_WORDS:
                continue
            if self._is_house_number(token):
                continue
            if self._is_block_code(token):
                continue
            if self._is_roman_numeral(token):
                continue
            filtered.append(token)

        if address_type == "residential" and street:
            street_tokens = street.split()
            remainder = [token for token in filtered if token not in street_tokens]
            tokens = street_tokens + remainder
        else:
            tokens = filtered

        if fallback:
            for part in fallback.split():
                if part not in tokens:
                    tokens.append(part)

        query = " ".join(tokens).strip()
        if default_city not in query.split():
            query = f"{query} {default_city}".strip()

        street_candidate: str | None = None
        if address_type != "unknown":
            if street and fallback:
                street_candidate = f"{street} {fallback}".strip()
            elif street:
                street_candidate = street
            elif address_type == "residential" and query:
                street_candidate = query

        return {
            "cleaned": cleaned,
            "street_candidate": street_candidate,
            "fallback": fallback,
            "query": query,
            "address_type": address_type,
        }

    def _clean_text(self, text: str | None) -> str:
        if not text:
            return ""

        normalized = str(text).lower()
        normalized = re.sub(r"(\d+)/(\d+)", r"\1 \2", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = [ALIAS_MAP.get(token, token) for token in normalized.split()]
        return " ".join(tokens)
    
    def _detect_address_type(self, text: str) -> str:
        tokens = text.split()

        if "jalan" in tokens:
            return "street"

        if any(token in RESIDENTIAL_KEYWORDS for token in tokens):
            return "residential"

        return "unknown"
    
    def _extract_street_name(self, text: str) -> str:
        tokens = text.split()

        if "jalan" not in tokens:
            return ""

        start = tokens.index("jalan")
        result = ["jalan"]

        for token in tokens[start + 1:]:
            if token in NOISE_WORDS:
                break
            if token in STOP_AFTER_STREET:
                break
            if self._is_house_number(token):
                break
            if self._is_block_code(token):
                break
            if token == "gang":
                break

            result.append(token)

            if len(result) >= 7:
                break

        return " ".join(result)
    
    def _is_house_number(self, token: str) -> bool:
        return token.isdigit() or bool(HOUSE_TOKEN_PATTERN.match(token))
    
    def _is_block_code(self, token: str) -> bool:
        return bool(BLOCK_PATTERN.match(token))

    def _is_roman_numeral(self, token: str) -> bool:
        return bool(ROMAN_NUMERAL_PATTERN.match(token))
    
    def _extract_city_fallback(self, city: str | None) -> str:
        if not city:
            return ""

        text = str(city).upper()
        if text.startswith("KOTA "):
            text = text[5:]

        parts = [part.strip().lower() for part in text.split(",") if part.strip()]
        parts.reverse()
        return " ".join(parts)