import discord
from discord.ext import commands
import logging
import os
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, COGS_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Bot Events ---
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}. Bot is ready!')
    await bot.change_presence(activity=discord.Game(name="/status for info"))
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID))
        logger.info(f"Synced {len(synced)} command(s) to the server.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


async def load_cogs():
    """Loads all cogs from the 'cogs' directory."""

    for filename in os.listdir(COGS_DIR):
        if filename.endswith('.py'):
            try:
                # The path should be bot.cogs.filename
                await bot.load_extension(f'bot.cogs.{filename[:-3]}')
                logger.info(f"Loaded cog: {filename}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename}: {e}")

async def main():
    """Main function to load cogs and run the bot."""
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_BOT_TOKEN)

# --- Starting the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or "YOUR_SECRET_BOT_TOKEN_HERE" in DISCORD_BOT_TOKEN:
        logger.error("Discord Bot Token is not configured. Please set DISCORD_BOT_TOKEN in your config file.")
    else:
        asyncio.run(main())