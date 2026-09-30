from datetime import datetime

import httpx
from fastapi import APIRouter

from app.config.settings import settings

router = APIRouter(
    prefix="/health",
    tags=["Health"]
)


@router.get("/")
async def health():

    asr_status = "DOWN"

    try:

        async with httpx.AsyncClient(timeout=2) as client:

            response = await client.get(settings.FUNASR_URL)

            if response.status_code < 500:
                asr_status = "UP"

    except Exception:
        pass

    return {
        "status": "healthy" if asr_status == "UP" else "degraded",

        "services": {
            "ASR": asr_status,
            "TTS": "UNKNOWN",
            "LLM": "UNKNOWN"
        },

        "version": settings.VERSION,

        "time": datetime.now().isoformat()
    }