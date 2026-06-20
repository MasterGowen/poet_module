import os
import json
import logging
from pathlib import Path
from filelock import FileLock

logger = logging.getLogger(__name__)

class PoemRecorder:
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path).absolute()
        self.lock_path = self.storage_path.with_suffix('.lock')
        
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _validate_path(self):
        # Security check: prevent writing outside the module directory
        root_dir = Path("/home/gowen/.openclaw/workspace/poet_module").absolute()
        if not str(self.storage_path).startswith(str(root_dir)):
            raise PermissionError(f"Attempt to write outside module directory: {self.storage_path}")

    def record(self, entry: dict):
        self._validate_path()
        
        with FileLock(self.lock_path):
            records = []
            if self.storage_path.exists():
                try:
                    with open(self.storage_path, 'r', encoding='utf-8') as f:
                        records = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Failed to read records: {e}. Starting fresh.")

            # Monotonic versioning
            version = max([r.get('version', 0) for r in records], default=0) + 1
            entry['version'] = version

            # Atomic write using temporary file
            temp_path = self.storage_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(records + [entry], f, ensure_ascii=False, indent=2)
                os.replace(temp_path, self.storage_path)
            except Exception as e:
                if temp_path.exists():
                    os.remove(temp_path)
                raise IOError(f"Atomic write failed: {e}")

            logger.info(f"Successfully recorded version {version}")
            return version
