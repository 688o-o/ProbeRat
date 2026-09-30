import os

import httpx

from app.config.settings import settings


class FunASRClient:

    def __init__(self):
        self.base_url = settings.FUNASR_URL
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20
            )
        )

    async def recognize(self, audio_path: str):

        with open(audio_path, "rb") as f:
            files = {
                "audio": (
                    os.path.basename(audio_path),
                    f,
                    "audio/wav"
                )
            }

            response = await self.client.post(
                f"{self.base_url}/recognition",
                files=files
            )

        if response.status_code != 200:
            raise ASRException(
                f"FunASR返回{response.status_code}"
            )

        return response.json()

    async def close(self):
        await self.client.aclose()