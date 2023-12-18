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


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)


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
    try: 
        image = None
        text_query = message.content
        response = None
        for attachment in message.attachments:
            if attachment.content_type.split('/')[0] == "image":
                image = Image.open(requests.get(attachment.url, stream = True).raw)
            else:
                text_query += "\n" + requests.get(attachment.url).content.decode()
        if image:
            response = image_model.generate_content([text_query, image] if text_query else image)
        else:
            response = chat.send_message(text_query)
        strings = []
        string = []
        count = 0
        async with message.channel.typing():
            for char in response.text:
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
    if message.channel.id != 1234: 
        return
    processes.append(message)
    

async def task():
    while True:
        while processes:
            message = processes.popleft()
            async with message.channel.typing():
                asyncio.create_task(get_response(message))
        local_time = time.localtime()
        if [local_time.tm_hour, local_time.tm_min] == [5, 0]:
            chat.history.clear()
        await asyncio.sleep(0.001)
    
    

      

client.run(BOT_TOKEN)
