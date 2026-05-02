from minio import Minio

from app.configs.environment_configuration import get_environment_configuration

environtment = get_environment_configuration()

minio_client = Minio(
    endpoint=environtment.MINIO_ENDPOINT,
    access_key=environtment.MINIO_ACCESS_KEY,
    secret_key=environtment.MINIO_SECRET_KEY,
    secure=environtment.MINIO_USE_SSL
)