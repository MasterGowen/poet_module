import os
import sys
import logging
from pathlib import Path
from pydantic_settings import BaseSettings

from src.generator import PoetryGenerator, Settings
from src.recorder import PoemRecorder
from src.notifier import PoemNotifier

# Absolute path to project root
ROOT_DIR = Path(__file__).resolve().parent.parent
data_dir = ROOT_DIR / "data"
data_dir.mkdir(parents=True, exist_ok=True)

# Configure Logging with absolute paths
logger = logging.getLogger("poet_main")
logger.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger.addHandler(console_handler)

# App Log Handler
app_log_handler = logging.FileHandler(data_dir / "app.log")
app_log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger.addHandler(app_log_handler)

# Error Log Handler
error_log_handler = logging.FileHandler(data_dir / "error.log")
error_log_handler.setLevel(logging.ERROR)
error_log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger.addHandler(error_log_handler)


def main():
    try:
        # 1. Validation & Config
        logger.info("Initializing Poetry Module...")
        settings = Settings()

        # 2. Components Setup (DI)
        recorder = PoemRecorder(str(data_dir / "records.json"))
        notifier = PoemNotifier()

        # 3. Execution Chain with context manager for Generator (resource management)
        with PoetryGenerator(settings) as generator:
            logger.info("Generating new masterpiece...")
            poem_data = generator.generate()

            version = recorder.record(poem_data)
            logger.info(f"Poem saved as version {version}")

            notifier.notify(poem_data)

    except Exception as e:
        logger.exception(f"Critical system failure: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
