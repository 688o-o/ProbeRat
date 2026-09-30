import os
import tempfile
import traceback

from fastapi import UploadFile

from app.core.exceptions import ASRException
from app.service.asr.funasr_client import FunASRClient


class ASRService:

    def __init__(self):
        self.client = FunASRClient()

    async def transcribe(self, audio: UploadFile):

        filename = audio.filename or "audio.wav"
        suffix = os.path.splitext(filename)[1] or ".wav"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as tmp:
            content = await audio.read()
            tmp.write(content)
            temp_path = tmp.name

        try:
            return await self.client.recognize(temp_path)

        except ASRException:
            raise

        except Exception as e:
            print(type(e))
            print(repr(e))
            raise ASRException(repr(e)) from e

        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
    async def close(self):
      await self.client.close()