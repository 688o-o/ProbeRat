from fastapi import APIRouter, UploadFile, File

from app.models.response import ApiResponse
from app.service.asr.funasr_service import ASRService
from app.core.deps import asr_service

router = APIRouter(
    prefix="/asr",
    tags=["ASR"]
)




@router.post(
    "/transcribe",
    response_model=ApiResponse
)
async def transcribe(
    audio: UploadFile = File(...)
):
    result = await asr_service.transcribe(audio)

    return ApiResponse(
        code=0,
        message="success",
        data=result
    )