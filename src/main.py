import os
import sys
import logging
from pathlib import Path
from pydantic_settings import BaseSettings

from src.generator import PoetryGenerator, Settings
from src.recorder import PoemRecorder
from src.notifier import PoemNotifier

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("data/app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("poet_main")

def main():
    try:
        # 1. Validation & Config
        logger.info("Initializing Poetry Module...")
        settings = Settings()
        
        # 2. Components Setup
        generator = PoetryGenerator(settings)
        recorder = PoemRecorder("data/records.json")
        notifier = PoemNotifier()

        # 3. Execution Chain
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
