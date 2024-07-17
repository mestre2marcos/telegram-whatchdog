from telegram import Update
from telegram.ext import ContextTypes, Application, ApplicationBuilder, CommandHandler

import asyncio
import aiohttp
import re
from dotenv import load_dotenv
import os
import json
from datetime import datetime

import paho.mqtt.client as mqtt

SERVICE_STATUS = {}

chat_id_list = []
CONFIG = {}

config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')
def load_config():
    global CONFIG
    with open(config_file_path, 'r') as config_file:
        CONFIG = json.load(config_file)

def save_config():
    global CONFIG
    with open(config_file_path, 'w') as config_file:
        str_json = json.dumps(CONFIG, indent=4)
        config_file.write(str_json)

load_dotenv()
load_config()

######################################################################################################################################

def on_connect_mqtt(mqttc:mqtt.Client, obj, flags, rc):
    #print("rc: " + str(rc))
    mqttc.disconnect()

######################################################################################################################################

async def callback_10(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in CONFIG["allowed_ids"]:
        if CONFIG["allowed_ids"][chat_id]["active"] == True:
            await context.bot.send_message(chat_id=int(chat_id), text='Hey ' + CONFIG["allowed_ids"][chat_id]["name"] + ' BOT is online')

async def send_push_notification(context: ContextTypes.DEFAULT_TYPE, text, chat_id):
    await context.bot.send_message(chat_id=chat_id, text=text)

async def check_services(context: ContextTypes.DEFAULT_TYPE):
    SERVICE_STATUS["datetime"] = datetime.now().isoformat()
    for broker in CONFIG["broker"]:
        mqttc = mqtt.Client()
        mqttc.on_connect = on_connect_mqtt
        print("Testing Broker:", broker["name"])
        try:
            mqttc.connect(broker["host"], broker["port"], 60)
            SERVICE_STATUS[broker["name"]] =  "ONLINE"
        except Exception as e:
            print(e)
            SERVICE_STATUS[broker["name"]] =  "OFFLINE"
            for chat_id in CONFIG["allowed_ids"]:
                if CONFIG["allowed_ids"][chat_id]["active"] == True:
                    msg = 'Hey! "' + broker["name"] + '" seems to be OFFLINE!'
                    await context.bot.send_message(chat_id=int(chat_id), text=msg)
    
    for api in CONFIG["api"]:
        print("Testing API:", api["host"])
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api["host"]) as response:
                    data = await response.read()
                    #print(data)

                    if data.decode() != api["response"]:
                        for chat_id in CONFIG["allowed_ids"]:
                            if CONFIG["allowed_ids"][chat_id]["active"] == True:
                                msg = 'Hey! "' + api["alias"] + '" did not respond as expected'
                                await context.bot.send_message(chat_id=int(chat_id), text=msg)
                        SERVICE_STATUS[api["alias"]] = "WARNING"
                    else:
                        SERVICE_STATUS[api["alias"]] = "ONLINE"
            except:
                for chat_id in CONFIG["allowed_ids"]:
                    if CONFIG["allowed_ids"][chat_id]["active"] == True:
                        msg = 'Hey! "' + api["alias"] + '" seems to be OFFLINE!'
                        await context.bot.send_message(chat_id=int(chat_id), text=msg)
                SERVICE_STATUS[api["alias"]] = "OFFLINE"

    print("Testing Front")
    for front in CONFIG["front"]:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(front["host"]) as response:
                    if response.status == 200:
                        SERVICE_STATUS[front["alias"]] = "ONLINE"
                    else:
                        for chat_id in CONFIG["allowed_ids"]:
                            if CONFIG["allowed_ids"][chat_id]["active"] == True:
                                msg = 'Hey! ' + front["alias"] + ' seems to be OFFLINE!'
                                await context.bot.send_message(chat_id=int(chat_id), text=msg)
                        SERVICE_STATUS[front["alias"]] = "OFFLINE"
            except:
                for chat_id in CONFIG["allowed_ids"]:
                    if CONFIG["allowed_ids"][chat_id]["active"] == True:
                        msg = 'Hey! ' + front["alias"] + ' seems to be OFFLINE!'
                        await context.bot.send_message(chat_id=int(chat_id), text=msg)
                SERVICE_STATUS[front["alias"]] = "OFFLINE"

######################################################################################################################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command_list = [
        "/start - Show available commands",
        "/help - Show available commands",
        "/addme - Resquest to add your Telegram account",
        "/removeme - Remove your subscription",
        "/listapproval",
        "/approve <id> - Approve a user",
        "/turnadmin <id> - Grant admin privileges to a user",
        "/report",
        "/doggo - Get a random dog image to make your day better",
    ]
    response_text = "\n".join(command_list)
    await update.message.reply_text(response_text)

async def add_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_chat_id = update.effective_chat.id
    print(new_chat_id)
    if CONFIG["allowed_ids"].get(str(new_chat_id), None) != None:
        await update.message.reply_text("User alreary exist")
        return
    CONFIG["allowed_ids"][str(new_chat_id)] = {
        "name" : update.effective_user.first_name,
        "active" : False,
        "admin" : False
    }
    save_config()
    response_text = "Alright " + update.effective_user.first_name + ", your request is waitng for approval!"
    await update.message.reply_text(response_text)
    
    for chat_id in CONFIG["allowed_ids"]:
        if (CONFIG["allowed_ids"][chat_id]["active"] == True) and (CONFIG["allowed_ids"][chat_id]["admin"] == True):
            text = "User " + CONFIG["allowed_ids"][str(new_chat_id)]["name"] + " is requesting for approval ID: " + str(new_chat_id)
            await send_push_notification(context, text, int(chat_id))

async def remove_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_chat_id = update.effective_chat.id
    
    try:
        CONFIG["allowed_ids"].pop(str(new_chat_id))
        save_config()
        await update.message.reply_text("You have been removed")
    except:
        await update.message.reply_text("User not found")

async def list_pendent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actual_chat_id = update.effective_message.chat_id
    actual_user = CONFIG["allowed_ids"].get(str(actual_chat_id), None)
    if not actual_user:
        await update.message.reply_text("User not found")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["active"]): 
        await update.message.reply_text("Not allowed operation")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["admin"]): 
        await update.message.reply_text("Not allowed operation")
        return

    waiting_list = []
    for chat_id in CONFIG["allowed_ids"]:
        if CONFIG["allowed_ids"][chat_id]["active"] == False:
            waiting_list.append("User " + CONFIG["allowed_ids"][chat_id]["name"] + " ID: " + chat_id) 
    if len(waiting_list) == 0:
        response_text = "No one!"
    else:
        response_text = "\n".join(waiting_list)
    await update.message.reply_text(response_text)

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actual_chat_id = update.effective_message.chat_id
    actual_user = CONFIG["allowed_ids"].get(str(actual_chat_id), None)
    if not actual_user:
        await update.message.reply_text("User not found")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["active"]): 
        await update.message.reply_text("Not allowed operation")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["admin"]): 
        await update.message.reply_text("Not allowed operation")
        return

    try:
        due = (context.args[0])
        CONFIG["allowed_ids"][str(due)]["active"] = True
        save_config()
        
        await update.effective_message.reply_text("User "+ CONFIG["allowed_ids"][str(due)]["name"] +" is now active")
        await send_push_notification(context, "Your request was approved!", int(due))

    except (IndexError, ValueError):
        await update.effective_message.reply_text("Usage: /approve <id>")

async def turn_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actual_chat_id = update.effective_message.chat_id
    actual_user = CONFIG["allowed_ids"].get(str(actual_chat_id), None)
    if not actual_user:
        await update.message.reply_text("User not found")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["active"]): 
        await update.message.reply_text("Not allowed operation")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["admin"]): 
        await update.message.reply_text("Not allowed operation")
        return
    
    try:
        due = (context.args[0])
        CONFIG["allowed_ids"][str(due)]["admin"] = True
        save_config()
        
        await update.effective_message.reply_text("User "+ CONFIG["allowed_ids"][str(due)]["name"] +" is now an admin")
        await send_push_notification(context, "Your are now an admin!", int(due))
    
    except (IndexError, ValueError):
        await update.effective_message.reply_text("Usage: /turnadmin <id>")
        
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actual_chat_id = update.effective_message.chat_id
    actual_user = CONFIG["allowed_ids"].get(str(actual_chat_id), None)
    if not actual_user:
        await update.message.reply_text("User not found")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["active"]): 
        await update.message.reply_text("Not allowed operation")
        return
    # if (not CONFIG["allowed_ids"][str(actual_chat_id)]["admin"]): 
    #     await update.message.reply_text("Not allowed operation")
    #     return

    response_list = []
    for broker in SERVICE_STATUS:
        response_list.append(str(broker) + ": " + SERVICE_STATUS[broker])
        

    if len(response_list) > 0:
        response_text = "\n".join(response_list)
    else:
        response_text = "Still generating report..."
    await update.message.reply_text(response_text)

######################################################################################################################################

async def doggo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actual_chat_id = update.effective_message.chat_id
    actual_user = CONFIG["allowed_ids"].get(str(actual_chat_id), None)
    if not actual_user:
        await update.message.reply_text("User not found")
        return
    if (not CONFIG["allowed_ids"][str(actual_chat_id)]["active"]): 
        await update.message.reply_text("Not allowed operation")
        return
    # if (not CONFIG["allowed_ids"][str(actual_chat_id)]["admin"]): 
    #     await update.message.reply_text("Not allowed operation")
    #     return

    async with aiohttp.ClientSession() as session:
        async with session.get("https://random.dog/woof.json") as response:
            data = await response.json()
            await update.message.reply_photo(data["url"])

######################################################################################################################################

app = Application.builder().token(os.getenv("BOT_KEY")).build()

job_queue = app.job_queue
job_queue.run_once(callback_10, 5)
job_queue.run_repeating(check_services, int(os.getenv("REFRESH_TIME")))

app.add_handler(CommandHandler(["start", "help"], start))
app.add_handler(CommandHandler("addme", add_me))
app.add_handler(CommandHandler("removeme", remove_me))
app.add_handler(CommandHandler("listapproval", list_pendent))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("turnadmin", turn_admin))
app.add_handler(CommandHandler("report", report))
app.add_handler(CommandHandler("doggo", doggo))

app.run_polling()