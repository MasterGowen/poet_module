import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any
from filelock import FileLock

logger = logging.getLogger(__name__)

class PoemRecorder:
    def __init__(self, storage_path: str):
        # Use resolve() to handle symlinks and get the real absolute path
        self.storage_path = Path(storage_path).resolve()
        self.lock_path = self.storage_path.with_suffix('.lock')
        
        # Define root directory relative to this file's location
        # src/recorder.py -> poet_module/
        self.root_dir = Path(__file__).resolve().parent.parent
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _validate_path(self):
        # Security check: ensure the path is inside the module root using commonpath
        try:
            if os.path.commonpath([str(self.root_dir), str(self.storage_path)]) != str(self.root_dir):
                raise PermissionError(f"Path traversal detected: {self.storage_path} is outside {self.root_dir}")
        except ValueError as e:
            raise PermissionError(f"Invalid path comparison: {e}")

    def record(self, entry: dict) -> int:
        self._validate_path()
        
        with FileLock(self.lock_path):
            records = []
            if self.storage_path.exists():
                try:
                    with open(self.storage_path, 'r', encoding='utf-8') as f:
                        records = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    # Backup corrupted file before starting fresh
                    corrupt_path = self.storage_path.with_suffix(f'.corrupt.{int(time.time())}.json')
                    logger.error(f"Records file corrupted: {e}. Backing up to {corrupt_path}")
                    try:
                        with open(self.storage_path, 'rb') as src, open(corrupt_path, 'wb') as dst:
                            dst.write(src.read())
                    except Exception as backup_err:
                        logger.critical(f"Failed to backup corrupt file: {backup_err}")
                    records = []

            # Monotonic versioning based on current records length
            version = max([r.get('version', 0) for r in records], default=0) + 1
            
            # Create a copy of entry to avoid mutating the original object (Side effect fix)
            record_entry = entry.copy()
            record_entry['version'] = version

            # Atomic write: write to temp -> rename
            temp_path = self.storage_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(records + [record_entry], f, ensure_ascii=False, indent=2)
                os.replace(temp_path, self.storage_path)
            except Exception as e:
                if temp_path.exists():
                    os.remove(temp_path)
                raise IOError(f"Atomic write failed: {e}")

            logger.info(f"Successfully recorded version {version}")
            return version
