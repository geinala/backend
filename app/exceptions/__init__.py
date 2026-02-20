from .validation import register_validation_exception_handlers
from .api_key import register_api_key_exception_handlers

from fastapi import FastAPI

def global_exception_handler_factory(app: FastAPI):
    register_validation_exception_handlers(app)
    register_api_key_exception_handlers(app)