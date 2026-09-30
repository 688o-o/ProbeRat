from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.api import health
from app.api.asr.transcribe import router as asr_router
from app.core.deps import asr_service
from app.core.exceptions import ASRException
from app.models.response import ApiResponse



@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await asr_service.close()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI Reliability Engeering Platform",
    version=settings.VERSION,
    lifespan=lifespan
)


@app.exception_handler(ASRException)
async def asr_exception_handler(request: Request, exc: ASRException):
    return JSONResponse(
        status_code=200,
        content=ApiResponse(
            code=exc.code,
            message=exc.message,
            data=None
        ).model_dump()
    )


app.include_router(health.router)
app.include_router(asr_router)