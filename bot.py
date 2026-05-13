from __future__ import annotations

import logging
import sys

import telebot
from telebot import types

from config import BOT_TOKEN, CHANNEL_USERNAME
from database import Plant, find_plant, init_db, list_plant_names

WELCOME = (
    "Привет! 🌿 Я помогу тебе ухаживать за комнатными растениями. "
    "Просто введи название растения — например: Монстера, Фикус или Сансевиерия — "
    "и я пришлю рекомендации по уходу.\n"
    "Подпишись на наш Telegram-канал, чтобы получать советы каждый день: "
    f"@{CHANNEL_USERNAME}"
)

NOT_FOUND = (
    "Прости, я понимаю только названия растений на русском 🌿 "
    "Попробуй, например: Монстера, Сансевиерия или Замиокулькас."
)

LIST_HEADER = "🌿 Растения в базе:\n\n"


def format_plant_card(plant: Plant) -> str:
    return (
        f"🌿 Растение: {plant.name}\n\n"
        f"Освещение: {plant.light}\n"
        f"Полив: {plant.water}\n"
        f"Температура: {plant.temperature}\n"
        f"Пересадка: {plant.repot}\n\n"
        "Подпишись на наш Telegram-канал, чтобы получать советы каждый день: "
        f"@{CHANNEL_USERNAME}"
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not BOT_TOKEN:
        logging.error("Задайте переменную окружения BOT_TOKEN (токен бота от @BotFather).")
        sys.exit(1)

    init_db()
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

    @bot.message_handler(commands=["start"])
    def on_start(message: types.Message) -> None:
        bot.reply_to(message, WELCOME)

    @bot.message_handler(commands=["list"])
    def on_list(message: types.Message) -> None:
        names = list_plant_names()
        if not names:
            bot.reply_to(message, "В базе пока нет растений.")
            return
        body = "\n".join(f"• {n}" for n in names)
        bot.reply_to(message, LIST_HEADER + body)

    @bot.message_handler(content_types=["text"])
    def on_text(message: types.Message) -> None:
        text = (message.text or "").strip()
        if not text:
            return
        if text.startswith("/"):
            bot.reply_to(message, NOT_FOUND)
            return
        plant = find_plant(text)
        if plant is None:
            bot.reply_to(message, NOT_FOUND)
        else:
            bot.reply_to(message, format_plant_card(plant))

    logging.info("Бот запущен.")
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    main()
