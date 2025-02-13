import os
from utils.logger import AppLogger
import logging
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

# Если вы используете python-dotenv для загрузки .env:
load_dotenv()

# Инициализируем логгер, если используете собственную систему логирования
logger = logging.getLogger(__name__)
# logger = AppLogger()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_notification(message: str) -> None:
    """
    Отправляет уведомление в Telegram через бот.

    :param message: Текст сообщения, которое нужно отправить.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        # Либо выбрасываем исключение, либо записываем в лог
        logger.warning(
            "Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID. "
            "Уведомление не может быть отправлено."
        )
        return

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(f"Уведомление отправлено: {message}")
    except TelegramError as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
