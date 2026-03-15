import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class EnvironmentConfiguration(BaseSettings):
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", 5432))
    DB_USERNAME: str = os.getenv("DB_USERNAME", "user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    DB_NAME: str = os.getenv("DB_NAME", "simulation_db")
    
    # Redis Configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # RQ Configuration
    RQ_QUEUE: str = os.getenv("RQ_QUEUE", "default")
    RQ_JOB_TIMEOUT: str = os.getenv("RQ_JOB_TIMEOUT", "10m")
    RQ_RESULT_TTL: int = int(os.getenv("RQ_RESULT_TTL", 300))
    
    # Heavy Processing Queue (CPU-intensive, long-running)
    RQ_HEAVY_QUEUE: str = os.getenv("RQ_HEAVY_QUEUE", "heavy")
    RQ_HEAVY_JOB_TIMEOUT: str = os.getenv("RQ_HEAVY_JOB_TIMEOUT", "30m")
    RQ_HEAVY_RESULT_TTL: int = int(os.getenv("RQ_HEAVY_RESULT_TTL", 3600))  # 1 hour
    RQ_HEAVY_WORKERS: int = int(os.getenv("RQ_HEAVY_WORKERS", 2))
    
    # Light Processing Queue (Quick tasks, low resource)
    RQ_LIGHT_QUEUE: str = os.getenv("RQ_LIGHT_QUEUE", "light")
    RQ_LIGHT_JOB_TIMEOUT: str = os.getenv("RQ_LIGHT_JOB_TIMEOUT", "5m")
    RQ_LIGHT_RESULT_TTL: int = int(os.getenv("RQ_LIGHT_RESULT_TTL", 300))
    RQ_LIGHT_WORKERS: int = int(os.getenv("RQ_LIGHT_WORKERS", 4))

    # FastAPI (Health checks only)
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", 8000))
    API_TITLE: str = os.getenv("API_TITLE", "Simulation App Solver")
    API_VERSION: str = os.getenv("API_VERSION", "1.0.0")

    # CORS Configuration
    CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "*")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    CORS_ALLOW_METHODS: str = os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE,PATCH,OPTIONS")
    CORS_ALLOW_HEADERS: str = os.getenv("CORS_ALLOW_HEADERS", "*")
    CORS_EXPOSE_HEADERS: str = os.getenv("CORS_EXPOSE_HEADERS", "content-length,x-json-response")
    CORS_MAX_AGE: int = int(os.getenv("CORS_MAX_AGE", 600))

    # API Documentation Configuration
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() == "true"
    ENABLE_REDOC: bool = os.getenv("ENABLE_REDOC", "true").lower() == "true"
    ENABLE_OPENAPI: bool = os.getenv("ENABLE_OPENAPI", "true").lower() == "true"

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    LOG_FILE: str = os.getenv("LOG_FILE", "app.log")
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", 5))
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", 10485760))  # 10 MB
    ENABLE_FILE_LOGGING: bool = os.getenv("ENABLE_FILE_LOGGING", "false").lower() == "true"  # Only file log in production

    # API Key Configuration
    API_KEY: str = os.getenv("API_KEY", "")
    ENABLE_API_KEY_VALIDATION: bool = os.getenv("ENABLE_API_KEY_VALIDATION", "true").lower() == "true"
    
    # Clerk Configuration
    CLERK_SECRET_KEY: str = os.getenv("CLERK_SECRET_KEY", "")
    
    # Frontend Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # MinIO Configuration
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minio_access_key")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minio_secret_key")
    MINIO_USE_SSL: bool = os.getenv("MINIO_USE_SSL", "false").lower() == "true"
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "simulation-results")
    
    # TomTom Configuration
    TOMTOM_MATRIX_API_KEY: str = os.getenv("TOMTOM_MATRIX_API_KEY", "")
    TOMTOM_ROUTING_API_KEY: str = os.getenv("TOMTOM_ROUTING_API_KEY", "")

    class Config:
        env_file = ".env"
        case_sensitive = True

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ALLOW_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ALLOW_ORIGINS.split(",")]
    
    @property
    def cors_methods(self) -> list[str]:
        return [method.strip() for method in self.CORS_ALLOW_METHODS.split(",")]
    
    @property
    def cors_headers(self) -> list[str] | str:
        if self.CORS_ALLOW_HEADERS == "*":
            return "*"
        return [header.strip() for header in self.CORS_ALLOW_HEADERS.split(",")]
    
    @property
    def cors_expose_headers(self) -> list[str]:
        return [header.strip() for header in self.CORS_EXPOSE_HEADERS.split(",")]


@lru_cache()
def get_environment_configuration() -> EnvironmentConfiguration:
    return EnvironmentConfiguration()
