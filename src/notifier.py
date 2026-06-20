from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, poem_data: dict):
        pass

class PoemNotifier(BaseNotifier):
    def notify(self, poem_data: dict):
        """
        Sends notification. Currently a stub for Telegram.
        """
        title = poem_data.get('title', 'Untitled')
        poem = poem_data.get('poem', 'No content')
        
        print("\n" + "="*40)
        print(f"[TELEGRAM STUB] 📢 NEW POEM: {title}")
        print("-" * 40)
        print(poem)
        print("="*40 + "\n")
        
        logger.info("Notification delivered to stdout stub")
