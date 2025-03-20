import os
import pathlib
import discord
from discord.ext import commands
from discord import app_commands
import requests
from dotenv import load_dotenv

# load token from .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


DISCORD_GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guild_scheduled_events = True



bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

@bot.event
async def setup_hook():
    for file in pathlib.Path("cogs").rglob("*.py"):
        if file.stem.startswith("_"):
            continue
        await bot.load_extension(".".join(file.with_suffix("").parts))

@bot.event
async def on_ready():
    guild = bot.get_guild(DISCORD_GUILD_ID)
    if guild is None:
        print(f"Guild with ID {DISCORD_GUILD_ID} not found")
    else:
        bot.guild = guild
    await bot.change_presence(status=discord.Status.online)
    await bot.tree.sync()
    print(f'{bot.user} is online!')

@bot.event
async def on_message(message: discord.Message) -> None:  # This event is called when a message is sent
    if message.author.bot:  # If the message is sent by a bot, return
        return

    await bot.process_commands(message)  # This is required to process commands

@bot.hybrid_command()
async def ping(ctx: commands.Context) -> None:  
    await ctx.send(f"> Pong! {round(bot.latency * 1000)}ms")

@bot.hybrid_command()
async def reload(ctx: commands.Context) -> None:
    """Sync commands"""
    synced = await ctx.bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands globally", ephemeral=True)

bot.run(TOKEN)



