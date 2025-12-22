# test_telegram.py
import asyncio
from telegram import Bot

async def test():
    bot = Bot(token="8380750013:AAF7lEiQUvkva7N99CMFlTAoatXL7f3YUwY")
    await bot.send_message(chat_id="8599692441", text="Test from local machine")
    print("✅ Success!")

asyncio.run(test())