from app.service.asr.funasr_service import ASRService
import sys


sys.stdout.reconfigure(encoding='utf-8')

service = ASRService()

result = service.speech_to_text("test.wav")

print(result)