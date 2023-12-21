from collections.abc import AsyncIterable
import time
import discord
import pathlib
import google.generativeai as genai
from IPython.display import display
from IPython.display import Markdown
import collections
import asyncio
import settings
import requests
from PIL import Image
import os


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

allowed_channels = [1187382039616430250, 1186688322853146676]
image_types = ["jpeg", "png", "webp", "heic", "heif"]
no_response_message = "Sorry, can't answer that. possible reasons might be recitation, safety issue or blocked content."
API_KEY = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

genai.configure(api_key=API_KEY)

text_model = genai.GenerativeModel(model_name="gemini-pro",
                              generation_config=settings.text_generation_config, # type: ignore
                              safety_settings=settings.text_safety_settings)
image_model = genai.GenerativeModel(model_name="gemini-pro-vision",
                              generation_config=settings.image_generation_config, # type: ignore
                              safety_settings=settings.image_safety_settings)

# chat = text_model.start_chat(history=[])
chats = {}

async def get_response(message, chat):
    async with message.channel.typing():
        image = None
        response = ""
        attachment = message.attachments[0] if message.attachments else None
        if not attachment: 
            try: 
                response = chat.send_message(message.content).text
            except Exception as e:
                response = no_response_message
                print("last message:", message.content)
                print(e)
        elif attachment.content_type.split('/')[0] == "image":
            if attachment.content_type.split('/')[1] in image_types:
                try:
                    image = Image.open(requests.get(attachment.url, stream = True).raw)
                    response = image_model.generate_content([message.content, image] if message.content else image).text
                except Exception as e:
                    response = "Unable to process that image."
                    print("last message:", attachment.url)
                    print(e)
            else: response = "Invalid image format. please use JPEG, PNG, WEBP, HEIC or HEIF"
        else:
            try: 
                att_content = requests.get(attachment.url).content.decode()
            except Exception as e:
                response = "Format not supported: " + attachment.filename
                print("last message:", attachment.url)
                print(e)
            else:
                try:
                    response = chat.send_message(message.content + '\n\n' + att_content)
                except Exception as e:
                    response = no_response_message
    client.loop.create_task(print_response(response, message))

async def print_response(response, message):
    async with message.channel.typing():
        strings = []
        string = []
        count = 0
        for char in response:
            if count < 2000: string.append(char); count += 1
            else: strings.append("".join(string)); string = [char]; count = 1
        strings.append("".join(string))
        try:
            await message.reply(strings[0])
            for string in strings[1:]: 
                await message.channel.send(string)
        except Exception as e: 
            message.reply("No response, discord issue :(")
            print("last message:", message.content)
            print(e)
    
                
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    client.loop.create_task(task())


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.startswith("$help") and message.channel.id in allowed_channels:
        await message.channel.send("```\n$chat -> for public chat.\n$private -> for private chat.\n```")
    if message.content.startswith("$chat") and message.channel.id in allowed_channels:
        thread = await message.channel.create_thread(name = "Session with " + message.author.name, slowmode_delay = 1, auto_archive_duration = 60, message = message)
        chats[str(thread.id)] = text_model.start_chat(history=[])
    elif message.content.startswith("$private") and message.channel.id in allowed_channels:
        thread = await message.channel.create_thread(name = "Session with " + message.author.name, slowmode_delay = 1, auto_archive_duration = 60)
        await thread.add_user(message.author)
        chats[str(thread.id)] = text_model.start_chat(history=[])
    elif str(message.channel.id) in chats:
        client.loop.create_task(get_response(message, chats[str(message.channel.id)]))
    

async def task():
    while True:
        local_time = time.localtime()
        if [local_time.tm_wday, local_time.tm_hour] == [6, 4]:
            for id in allowed_channels:
                channel = client.get_channel(id)
                async for thread in channel.archived_threads(private = True):
                    chats.pop(thread.id)
                    thread.delete()
        await asyncio.sleep(1)
    
    

      
client.run(BOT_TOKEN) 
