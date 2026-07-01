from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from src.core.logger import log

app = FastAPI(
    title="IDP Invoice Processing API",
    description="Production-grade Intelligent Document Processing system for invoice extraction",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def startup_event():
    log.info("IDP API Server starting up...")


@app.on_event("shutdown")
def shutdown_event():
    log.info("IDP API Server shutting down...")
