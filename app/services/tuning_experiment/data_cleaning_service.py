import json
import re
import time as time_module
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict, cast

from app.models.tuning_experiment_dataset import TuningExperimentDatasetStatusEnum
from app.repositories.tuning_experiment_dataset_repository import TuningExperimentDatasetRepository
from app.repositories.tuning_experiment_uploaded_row_repository import TuningExperimentUploadedRowRepository
from app.lib.logging.logging import get_logger
from app.schemas.tuning_experiment_uploaded_row_schema import UpdateTuningExperimentUploadedRowSchema

logger = get_logger(__name__)
GEOGRAPHIC_TERMS_PATH = Path(__file__).resolve().parents[2] / "statics" / "malang_geographic_terms.json"

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
    "letjen": "letnan jenderal",
    "kh": "kyai haji",
    "prof": "profesor",
    "mayjen": "mayor jenderal",
    "mayjend": "mayor jenderal",
    "meyjend": "mayor jenderal",
    "myjend": "mayor jenderal",
    "s": "sunandar",
    "priyo": "priyosudarmo",
    "hartono": "haryono",
    "harryono": "haryono",
    "kloweh": "kluwe",
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
AddressType = Literal["street", "residential", "unknown"]


class PreparedAddressResult(TypedDict):
    cleaned: str
    street_candidate: str | None
    fallback: str
    query: str
    address_type: AddressType


class TuningExperimentDataCleaningService:
    def __init__(
        self,
        tuning_experiment_dataset_repository: TuningExperimentDatasetRepository,
        tuning_experiment_uploaded_row_repository: TuningExperimentUploadedRowRepository
    ):
        self.tuning_experiment_dataset_repository = tuning_experiment_dataset_repository
        self.tuning_experiment_uploaded_row_repository = tuning_experiment_uploaded_row_repository

    async def run(self, tuning_experiment_dataset_id: str) -> dict[str, object]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "tuning_clean_uploaded_rows",
            "tuning_experiment_dataset_id": tuning_experiment_dataset_id,
            "status": "processing",
        }

        try:
            dataset = await self.tuning_experiment_dataset_repository.get_tuning_experiment_dataset_by_id_and_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                status=TuningExperimentDatasetStatusEnum.validated
            )

            if not dataset:
                raise ValueError(f"Tuning experiment dataset with ID {tuning_experiment_dataset_id} not found.")
            
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.cleaning
            )

            uploaded_rows = await self.tuning_experiment_uploaded_row_repository.get_uploaded_rows_by_tuning_experiment_dataset_id(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id
            )

            if not uploaded_rows:
                raise ValueError(f"No uploaded rows found for tuning experiment dataset {tuning_experiment_dataset_id}. Cannot proceed with cleaning process.")

            cleaned_rows: list[UpdateTuningExperimentUploadedRowSchema] = []

            for _, row in enumerate(uploaded_rows, start=1):
                prepared = self._prepare_row_for_cleaning(
                    address=row.address,
                    city=row.city,
                )
                
                cleaned_row = UpdateTuningExperimentUploadedRowSchema(
                    id=row.id,
                    normalized_address=prepared["cleaned"] if prepared["cleaned"] and prepared["cleaned"].strip() else None,
                    suggested_address=prepared["query"],
                    final_address=prepared["query"],
                )

                cleaned_rows.append(cleaned_row)

            await self.tuning_experiment_uploaded_row_repository.update_cleaned_rows(cleaned_rows=cleaned_rows)

            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.cleaned
            )

            wide_event["status"] = "success"
            wide_event["processed_rows"] = len(cleaned_rows)
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.info(wide_event)

            return {"tuning_experiment_dataset_id": tuning_experiment_dataset_id, "processed_rows": len(cleaned_rows)}

        except Exception as e:
            await self.tuning_experiment_dataset_repository.update_tuning_experiment_dataset_status(
                tuning_experiment_dataset_id=tuning_experiment_dataset_id,
                new_status=TuningExperimentDatasetStatusEnum.failed
            )
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            logger.error(wide_event)
            raise e

    def _prepare_row_for_cleaning(
        self,
        address: str | None,
        city: str | None,
        default_city: str = "malang",
    ) -> PreparedAddressResult:
        cleaned = self._clean_text(address)
        extracted_street = self._extract_street_name(cleaned)
        cleaned = self._remove_geographic_terms(
            cleaned,
            preserved_phrase=extracted_street,
        )
        address_type = self._detect_address_type(cleaned)
        fallback = self._extract_city_fallback(city)

        all_tokens = cleaned.split()

        def should_keep(token: str) -> bool:
            return not (
                token in NOISE_WORDS
                or self._is_house_number(token)
                or self._is_block_code(token)
                or self._is_roman_numeral(token)
            )

        result: list[str] = []

        if address_type == "street" and extracted_street:
            street_tokens = extracted_street.split()
            jalan_idx = all_tokens.index("jalan")
            street_end_idx = jalan_idx + len(street_tokens)

            for t in all_tokens[:jalan_idx]:
                if should_keep(t):
                    result.append(t)

            result.extend(street_tokens)

            for t in all_tokens[street_end_idx:]:
                if should_keep(t):
                    result.append(t)
        else:
            for t in all_tokens:
                if should_keep(t):
                    result.append(t)

        seen_for_fallback = set(result)
        for part in fallback.split():
            if part not in seen_for_fallback:
                result.append(part)
                seen_for_fallback.add(part)

        if default_city not in seen_for_fallback:
            result.append(default_city)

        query = " ".join(result).strip()
        
        street_candidate: str | None = None
        if address_type != "unknown":
            if extracted_street and fallback:
                street_candidate = f"{extracted_street} {fallback}".strip()
            elif extracted_street:
                street_candidate = extracted_street
            elif address_type == "residential" and query:
                street_candidate = query

        return {
            "cleaned": cleaned,
            "street_candidate": street_candidate,
            "fallback": fallback,
            "query": query,
            "address_type": address_type,
        }

    @classmethod
    @lru_cache(maxsize=1)
    def _load_geographic_terms(cls) -> tuple[tuple[str, ...], ...]:
        if not GEOGRAPHIC_TERMS_PATH.exists():
            logger.warning(
                {
                    "event_type": "geographic_terms_load_missing",
                    "path": str(GEOGRAPHIC_TERMS_PATH),
                }
            )
            return tuple()

        with GEOGRAPHIC_TERMS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if not isinstance(payload, list):
            raise ValueError(f"Invalid geographic terms format in {GEOGRAPHIC_TERMS_PATH}")

        payload = cast(list[str], payload)

        normalized_terms: set[tuple[str, ...]] = set()
        for item in payload:
            cleaned_term = cls._clean_text(item)
            if cleaned_term:
                normalized_terms.add(tuple(cleaned_term.split()))

        return tuple(
            sorted(
                normalized_terms,
                key=lambda term_tokens: (-len(term_tokens), term_tokens),
            )
        )

    def _resolve_street_name(
        self,
        text: str,
        address_type: AddressType,
        extracted_street: str,
    ) -> str:
        if address_type == "unknown" or not extracted_street:
            return extracted_street

        return f"jalan {extracted_street}".strip()

    @staticmethod
    def _clean_text(text: str | None) -> str:
        if not text:
            return ""

        normalized = str(text).lower()
        normalized = re.sub(r"(\d+)/(\d+)", r"\1 \2", normalized)
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = [ALIAS_MAP.get(token, token) for token in normalized.split()]
        return " ".join(tokens)
    
    @staticmethod
    def _detect_address_type(text: str) -> AddressType:
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
            geographic_term_length = self._match_geographic_term_length(tokens, start + len(result))
            if geographic_term_length > 0:
                if len(result) == 1:
                    pass
                else:
                    break
            if self._is_house_number(token):
                break
            if self._is_block_code(token):
                break
            if self._is_roman_numeral(token):
                break
            if token == "gang":
                break

            result.append(token)

            if len(result) >= 7:
                break

        return " ".join(result)

    def _remove_geographic_terms(
        self,
        text: str,
        preserved_phrase: str = "",
    ) -> str:
        tokens = text.split()
        if not tokens:
            return ""

        preserved_tokens = preserved_phrase.split()
        preserved_ranges = self._find_phrase_ranges(tokens, preserved_tokens)

        filtered_tokens: list[str] = []
        index = 0

        while index < len(tokens):
            preserved_range = next(
                (
                    token_range
                    for token_range in preserved_ranges
                    if token_range[0] == index
                ),
                None,
            )
            if preserved_range:
                filtered_tokens.extend(tokens[preserved_range[0]:preserved_range[1]])
                index = preserved_range[1]
                continue

            geographic_term_length = self._match_geographic_term_length(tokens, index)
            if geographic_term_length > 0:
                index += geographic_term_length
                continue

            filtered_tokens.append(tokens[index])
            index += 1

        return " ".join(filtered_tokens)

    @staticmethod
    def _find_phrase_ranges(
        tokens: list[str],
        phrase_tokens: list[str],
    ) -> list[tuple[int, int]]:
        if not phrase_tokens:
            return []

        phrase_length = len(phrase_tokens)
        ranges: list[tuple[int, int]] = []

        for index in range(len(tokens) - phrase_length + 1):
            if tokens[index:index + phrase_length] == phrase_tokens:
                ranges.append((index, index + phrase_length))

        return ranges

    @classmethod
    def _match_geographic_term_length(
        cls,
        tokens: list[str],
        start_index: int,
    ) -> int:
        for term_tokens in cls._load_geographic_terms():
            term_length = len(term_tokens)
            if tuple(tokens[start_index:start_index + term_length]) == term_tokens:
                return term_length

        return 0
    
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
        return " ".join(parts[1:])
    