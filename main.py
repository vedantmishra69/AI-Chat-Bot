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
from ratelimit import limits, RateLimitException, sleep_and_retry


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

allowed_channels = []
allowed_guilds = [1063393625049923687, 501032525284769842]
dev_id = 501026469569363988
image_types = ["jpeg", "png", "webp", "heic", "heif"]
no_response_message = "Sorry, can't answer that. possible reasons might be no response, recitation, safety issue or blocked content."
help_text = "```\nUsage:\n$chat : to create a public thread to interact with the bot.\n$private : to create a private thread to interact with the bot.\n\nACD AI answers to all text, image and attachment.\nHave fun!\n\nfor Admin/Mods:\n$set : to set a channel.\n$unset : to unset a channel.\n$show : to show current channels.\n$clear : to delete all the threads in set channels.```"
API_KEY = os.environ["API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

genai.configure(api_key=API_KEY)

text_model = genai.GenerativeModel(model_name="gemini-pro",
                              generation_config=settings.text_generation_config, # type: ignore
                              safety_settings=settings.text_safety_settings)
image_model = genai.GenerativeModel(model_name="gemini-pro-vision",
                              generation_config=settings.image_generation_config, # type: ignore
                              safety_settings=settings.image_safety_settings)

chats = {}

ONE_MINUTE = 60
MAX_CALLS_PER_MINUTE = 60

@sleep_and_retry
@limits(calls=MAX_CALLS_PER_MINUTE, period=ONE_MINUTE)
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


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.content.startswith("$show"):
        if has_permissions(message):
            set_channels = []
            count = 1
            for Id in allowed_channels:
                if message.guild.get_channel(Id):
                    set_channels.append(f"\n{count}. {message.guild.get_channel(Id).name}")
                    count += 1
            if set_channels:
                await message.channel.send("Current channels:" + "".join(set_channels))
            else:
                await message.channel.send("No channel has been set. type $set to set it.")
        else: 
            await message.channel.send("you don't have ``Manage channels`` permission!")
            
    if message.content.startswith("$set"):
        if has_permissions(message):
            if message.channel.type == discord.ChannelType.text:
                if message.channel.id not in allowed_channels:
                    allowed_channels.append(message.channel.id)
                    await message.channel.send(f"channel ``{message.channel.name}`` has been set successfully.")
                else:
                    await message.channel.send(f"``{message.channel.name}`` is already set.")
            else:
                await message.channel.send("It should be a text channel!")
        else:
            await message.channel.send("you don't have ``Manage channels`` permission!")
            
    if message.content.startswith("$help"):
        await message.channel.send(help_text)

    if message.content.startswith("$unset"):
        if has_permissions(message):
            if message.channel.id in allowed_channels:
                allowed_channels.remove(message.channel.id)
                await message.channel.send(f"channel ``{message.channel.name}`` has been unset successfully.")
            else:
                await message.channel.send("This channel has not been set. type $set to set it.")
        else:
            await message.channel.send("you don't have ``Manage channel`` permission!")
            
    if message.content.startswith("$clear"):
        if message.author.guild_permissions.manage_threads:
            for Id in allowed_channels:
                if message.guild.get_channel(Id):
                    count = 0
                    async with message.channel.typing():
                        for thread in message.guild.get_channel(Id).threads:
                            await thread.delete()
                            count += 1
                    await message.channel.send(f"{count} threads deleted for ``{message.guild.get_channel(Id).name}``.")
        else: 
            await message.channel.send("you don't have ``Manage threads`` permission!")
            
            
    if str(message.channel.id) in chats:
        client.loop.create_task(get_response(message, chats[str(message.channel.id)])) # type: ignore
    elif message.content:
        first = message.content.split()[0]
        if first == "$chat": 
            if message.channel.id in allowed_channels: 
                await start_thread(message, True)
            else:
                await message.channel.send("This channel has not been set. type $set to set it.")
        elif first == "$private": 
            if message.channel.id in allowed_channels: 
                await start_thread(message, False)
            else:
                await message.channel.send("This channel has not been set. type $set to set it.")
                
def has_permissions(message):
    return (message.author.guild_permissions.manage_channels and message.guild.id in allowed_guilds) or message.author.id == dev_id


async def start_thread(message, is_public):
    try:
        thread = await message.channel.create_thread(name = "Session with " + message.author.name, slowmode_delay = 1, auto_archive_duration = 60, message = message if is_public else None)
        await thread.add_user(message.author)
        hello_text = text_model.generate_content("hi").text
        async with thread.typing():
            await thread.send(content = f'<@{message.author.id}> {hello_text}')
        chats[str(thread.id)] = text_model.start_chat(history=[{'role':'user', 'parts': ["hi"]}, {'role': 'model', 'parts': [hello_text]}])
    except Exception as e:
        await message.channel.send("Could not start a thread :(")
        print(e)
   
client.run(BOT_TOKEN) 


