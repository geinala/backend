import io
import csv
from typing import Any

from app.models.error_report import ValidationError


class FileService:
    @staticmethod
    def parse_csv_bytes(dataset: bytes) -> tuple[list[str], list[dict[str, str]]]:
        try:
            content = dataset.decode("utf-8")
        except UnicodeDecodeError:
            content = dataset.decode("latin-1")

        csv_file = io.StringIO(content)
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")

        rows = list(reader)
        return list(reader.fieldnames), rows
    
    @staticmethod
    def create_csv_from_dict_list(
        data: list[dict[str, Any]],
        fieldnames: list[str],
    ) -> bytes:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(data)
        
        csv_content = output.getvalue()
        output.close()
        
        return csv_content.encode('utf-8')
    
    @staticmethod
    async def create_error_report_file(error_report: str, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(error_report)
    
    @staticmethod
    def create_error_report_csv(errors: list[ValidationError]) -> bytes:
        fieldnames = [
            'row_number',
            'field_name',
            'invalid_value',
            'error_message',
        ]
        
        error_dicts = [error.to_dict() for error in errors]
        return FileService.create_csv_from_dict_list(error_dicts, fieldnames)