import time as time_module
from datetime import timedelta
from io import BytesIO
from typing import BinaryIO, cast
from minio import Minio
from minio.error import S3Error

from app.configs.environment_configuration import get_environment_configuration
from app.lib.logging.logging import get_logger

logger = get_logger(__name__)

environment_configuration = get_environment_configuration()


class MinioService:
    BUCKET_NAME = environment_configuration.MINIO_BUCKET_NAME
    
    def __init__(self, minio_client: Minio):
        self.minio_client = minio_client

    async def upload_file(
        self,
        object_name: str,
        file_data: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
    ) -> dict[str, object]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_upload_file",
            "bucket_name": self.BUCKET_NAME,
            "object_name": object_name,
            "content_type": content_type,
            "status": "processing",
        }
        
        try:
            await self.create_bucket_if_not_exists()
            
            # Convert bytes to BytesIO if needed
            if isinstance(file_data, bytes):
                file_data = BytesIO(file_data)
            
            # Ensure we have a BytesIO object
            data_stream = cast(BytesIO, file_data)
            data_stream.seek(0, 2)
            file_size = data_stream.tell()
            data_stream.seek(0)
            
            result = self.minio_client.put_object(
                bucket_name=self.BUCKET_NAME,
                object_name=object_name,
                data=data_stream,
                length=file_size,
                content_type=content_type,
            )
            
            wide_event["status"] = "success"
            wide_event["file_size"] = file_size
            wide_event["etag"] = result.etag
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return {
                "bucket_name": self.BUCKET_NAME,
                "object_name": object_name,
                "etag": result.etag,
                "file_size": file_size,
            }
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def download_file(
        self,
        object_name: str,
    ) -> bytes:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_download_file",
            "bucket_name": self.BUCKET_NAME,
            "object_name": object_name,
            "status": "processing",
        }
        
        try:
            response = self.minio_client.get_object(
                bucket_name=self.BUCKET_NAME,
                object_name=object_name,
            )
            
            file_data = response.read()
            response.close()
            response.release_conn()
            
            wide_event["status"] = "success"
            wide_event["file_size"] = len(file_data)
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return file_data
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def delete_file(
        self,
        object_name: str,
    ) -> dict[str, object]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_delete_file",
            "bucket_name": self.BUCKET_NAME,
            "object_name": object_name,
            "status": "processing",
        }
        
        try:
            self.minio_client.remove_object(
                bucket_name=self.BUCKET_NAME,
                object_name=object_name,
            )
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return {
                "bucket_name": self.BUCKET_NAME,
                "object_name": object_name,
                "deleted": True,
            }
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def list_files(
        self,
        prefix: str = "",
    ) -> list[dict[str, object]]:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_list_files",
            "bucket_name": self.BUCKET_NAME,
            "prefix": prefix,
            "status": "processing",
        }
        
        try:
            objects = self.minio_client.list_objects(
                bucket_name=self.BUCKET_NAME,
                prefix=prefix,
                recursive=True,
            )
            
            files: list[dict[str, object]] = []
            for obj in objects:
                files.append({
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag,
                })
            
            wide_event["status"] = "success"
            wide_event["file_count"] = len(files)
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return files
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def generate_presigned_url(
        self,
        object_name: str,
        expires_in_seconds: int = 3600,
    ) -> str:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_generate_presigned_url",
            "bucket_name": self.BUCKET_NAME,
            "object_name": object_name,
            "expires_in_seconds": expires_in_seconds,
            "status": "processing",
        }
        
        try:
            url = self.minio_client.presigned_get_object(
                bucket_name=self.BUCKET_NAME,
                object_name=object_name,
                expires=timedelta(seconds=expires_in_seconds),
            )
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return url
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def check_bucket_exists(self) -> bool:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_check_bucket_exists",
            "bucket_name": self.BUCKET_NAME,
            "status": "processing",
        }
        
        try:
            exists = self.minio_client.bucket_exists(bucket_name=self.BUCKET_NAME)
            
            wide_event["status"] = "success"
            wide_event["exists"] = exists
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return exists
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e

    async def create_bucket_if_not_exists(self) -> bool:
        start_time = time_module.time()
        wide_event: dict[str, object] = {
            "event_type": "minio_create_bucket_if_not_exists",
            "bucket_name": self.BUCKET_NAME,
            "status": "processing",
        }
        
        try:
            exists = await self.check_bucket_exists()
            
            if not exists:
                self.minio_client.make_bucket(bucket_name=self.BUCKET_NAME)
                wide_event["created"] = True
            else:
                wide_event["created"] = False
            
            wide_event["status"] = "success"
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.info(wide_event)
            
            return True
            
        except S3Error as e:
            wide_event["status"] = "failed"
            wide_event["error"] = str(e)
            wide_event["error_type"] = type(e).__name__
            wide_event["duration_ms"] = (time_module.time() - start_time) * 1000
            
            logger.error(wide_event)
            raise e
    