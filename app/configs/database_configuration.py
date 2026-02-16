from threading import Lock
from typing import Optional
from .environment_configuration import get_environment_configuration

class DatabaseConfiguration:
    _instance: Optional["DatabaseConfiguration"] = None
    _lock: Lock = Lock()
    
    _initialized: bool = False

    def __new__(cls) -> "DatabaseConfiguration":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._setup()
                    self.__class__._initialized = True

    def _setup(self) -> None:
        settings = get_environment_configuration()
        self._database_url: str = settings.database_url
        self._db_client: Optional[object] = None

    @property
    def database_url(self) -> str:
        return self._database_url