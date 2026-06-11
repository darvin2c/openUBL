"""
FastAPI application for openUBL.
"""
from fastapi import FastAPI
from .api.router import router

app = FastAPI(title="openUBL", version="0.1.4")
app.include_router(router, prefix="/api/v1")
