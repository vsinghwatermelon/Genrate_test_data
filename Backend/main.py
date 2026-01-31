"""
Entry point for the Test Data Generator API.
Focuses on Selenium execution and AI data generation.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.shared.config import get_config
from modules.shared.logger import get_logger

# Route imports
from modules.execution.router import router as execution_router
from modules.generation.router import router as generation_router
from modules.generation.parsing import router as parsing_router

config = get_config()
logger = get_logger(__name__)

def create_app() -> FastAPI:
    """Setup FastAPI with CORS and core routes."""
    app = FastAPI(title="Test Data Generator", version="3.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Core functional endpoints
    app.include_router(execution_router, tags=["Execution"])
    app.include_router(generation_router, tags=["Generation"])
    app.include_router(parsing_router, tags=["Parsing"])

    @app.get("/", tags=["Health"])
    async def root():
        """Basic heartbeat check."""
        return {"status": "active", "version": "3.0.0"}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.server.host, port=config.server.port, reload=config.server.debug)
