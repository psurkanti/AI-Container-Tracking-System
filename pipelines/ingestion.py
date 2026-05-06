from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from fastapi import UploadFile

logger = logging.getLogger(__name__)


class DataIngestionService:
    def __init__(self, uploads_dir: str) -> None:
        self.uploads_dir = Path(uploads_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload_file: UploadFile) -> Path:
        destination = self.uploads_dir / upload_file.filename
        contents = await upload_file.read()
        destination.write_bytes(contents)
        logger.info("Uploaded file saved", extra={"event": "data_ingestion", "source": str(destination)})
        return destination

    def load_from_path(self, file_path: str) -> pd.DataFrame:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        df = pd.read_csv(path)
        logger.info("Data loaded from path", extra={"event": "data_ingestion", "source": str(path)})
        return df

    def load_dataframe(self, file_path: Path | str) -> pd.DataFrame:
        return pd.read_csv(file_path)
