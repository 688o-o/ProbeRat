class ASRException(Exception):

    def __init__(self, message: str, code: int = -1):
        self.message = message
        self.code = code
        super().__init__(message)