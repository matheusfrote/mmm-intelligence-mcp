"""Environment configuration belongs to the host, never to tool arguments."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    allow_real_data: bool = False
    max_rows: int = 10000
    max_file_bytes: int = 10485760
    log_level: str = "INFO"

    def __post_init__(self):
        if not 52 <= self.max_rows <= 100000:
            raise ValueError("MMM_MAX_ROWS must be between 52 and 100000")
        if not 1024 <= self.max_file_bytes <= 100 * 1024 * 1024:
            raise ValueError("MMM_MAX_FILE_BYTES must be between 1024 and 104857600")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("Invalid MMM_LOG_LEVEL")

    @classmethod
    def from_env(cls) -> "Settings":
        flag = os.getenv("MMM_ALLOW_REAL_DATA", "false").lower()
        if flag not in {"true", "false"}:
            raise ValueError("MMM_ALLOW_REAL_DATA must be true or false")
        return cls(
            data_dir=Path(os.getenv("MMM_DATA_DIR", "./var")).absolute(),
            allow_real_data=flag == "true",
            max_rows=int(os.getenv("MMM_MAX_ROWS", "10000")),
            max_file_bytes=int(os.getenv("MMM_MAX_FILE_BYTES", "10485760")),
            log_level=os.getenv("MMM_LOG_LEVEL", "INFO").upper(),
        )
