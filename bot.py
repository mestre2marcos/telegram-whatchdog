from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio
import aiohttp
import re
from dotenv import load_dotenv
import os

load_dotenv()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(update.effective_user.id)
    print(update.effective_chat.id)
    command_list = [
        "/hello - Greet the user",
        "/doggo - Get a random dog image",
        "/start - Show available commands"
    ]
    response_text = "\n".join(command_list)
    await update.message.reply_text(response_text)

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def doggo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://random.dog/woof.json") as response:
            data = await response.json()
            await update.message.reply_photo(data["url"])
        

app = ApplicationBuilder().token(os.getenv("BOT_KEY")).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("doggo", doggo))

app.run_polling()