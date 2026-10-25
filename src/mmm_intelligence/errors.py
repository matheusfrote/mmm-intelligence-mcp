"""Public domain errors; messages must not expose private data or host paths."""


class MMMError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
