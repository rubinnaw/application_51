import os
from utils.logger import AppLogger
import logging
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv
from utils.cache import ChatCache

# Если вы используете python-dotenv для загрузки .env:
load_dotenv()

# Инициализируем логгер, если используете собственную систему логирования
logger = logging.getLogger(__name__)
# logger = AppLogger()

TELEGRAM_BOT_TOKEN = "7661660056:AAG4l3zi-5sRTMHG517s6K5eEGBLSgfInyk"


def send_telegram_notification(message: str) -> None:
    """
    Отправляет уведомление в Telegram через бот.

    :param message: Текст сообщения, которое нужно отправить.
    """
    cache = ChatCache()
    auth_data = cache.get_auth_data()
    
    if not auth_data or not auth_data[2]:  # auth_data[2] - это telegram_chat_id
        logger.warning("Telegram Chat ID не найден. Уведомление не может быть отправлено.")
        return
    
    telegram_chat_id = auth_data[2]

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=telegram_chat_id, text=message)
        logger.info(f"Уведомление отправлено: {message}")
    except TelegramError as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
