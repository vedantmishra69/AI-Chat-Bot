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

CHANNEL_ID = 1234
API_KEY = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

genai.configure(api_key=API_KEY)

text_model = genai.GenerativeModel(model_name="gemini-pro",
                              generation_config=settings.text_generation_config, # type: ignore
                              safety_settings=settings.text_safety_settings)
image_model = genai.GenerativeModel(model_name="gemini-pro-vision",
                              generation_config=settings.image_generation_config, # type: ignore
                              safety_settings=settings.image_safety_settings)

chat = text_model.start_chat(history=[])
processes = collections.deque([])

async def get_response(message):
    async with message.channel.typing():
        try: 
            text_query = [message.content]
            total_response = []
            img_count = 1
            for attachment in message.attachments:
                if attachment.content_type.split('/')[0] == "image":
                    try:
                        image = Image.open(requests.get(attachment.url, stream = True).raw)
                        total_response.append("\n" + "Image: " + str(img_count) + "\n" + image_model.generate_content([message.content, image] if message.content else image).text)
                    except Exception as e:
                        total_response.append("\n" + "Image: " + str(img_count) + "\n" + "Response not available for the following image.")
                        print(e)
                    img_count += 1
                else:
                    try:
                        text_query.append("\n" + "text:" + "\n" + requests.get(attachment.url).content.decode())
                    except Exception as e: 
                        total_response.append("\nFormat not supported for " + attachment.filename)
                        print(e)
            text_query = "\n".join(text_query)
            if text_query: total_response.append("\n" + chat.send_message(text_query).text)
            strings = []
            string = []
            count = 0
            total_response = "\n".join(total_response)
            async with message.channel.typing():
                for char in total_response:
                    if count < 2000: string.append(char); count += 1
                    else: strings.append("".join(string)); string = [char]; count = 1
                strings.append("".join(string))
            await message.reply(strings[0])
            for string in strings[1:]: 
                await message.channel.send(string)
        except Exception as e:
            await message.reply("Response has been blocked or not available, please try again.")
            print(e)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    client.loop.create_task(task())


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL_ID:
        return
    processes.append(message)
    

async def task():
    while True:
        while processes:
            message = processes.popleft()
            asyncio.create_task(get_response(message))
        local_time = time.localtime()
        if [local_time.tm_hour, local_time.tm_min] == [5, 0]:
            chat.history.clear()
        await asyncio.sleep(0.001)
    
    

      
client.run(BOT_TOKEN) 
