import discord
from discord.ext import commands
import logging
import os
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Custom Bot Class for Reliable Cog Loading ---
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        """This runs when the bot logs in and is the correct place to load cogs and sync commands."""
        logger.info("Running setup_hook: loading cogs...")
        await self.load_all_cogs()
        
        logger.info("Cogs loaded. Syncing commands to the guild.")
        try:
            synced = await self.tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID))
            logger.info(f"--- Successfully synced {len(synced)} command(s). ---")
        except Exception as e:
            logger.error(f"Failed to sync commands on startup: {e}", exc_info=True)

    async def load_all_cogs(self):
        """Finds and loads all cog files."""
        cogs_path = os.path.join('bot', 'cogs')
        for filename in os.listdir(cogs_path):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'bot.cogs.{filename[:-3]}')
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)

# --- Bot Initialization ---
intents = discord.Intents.default()
intents.message_content = True 
bot = MyBot(command_prefix="!", intents=intents)

# --- Bot Events ---
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}. Bot is ready!')
    await bot.change_presence(activity=discord.Game(name="/status for info"))

# --- Starting the Bot ---
if __name__ == "__main__":
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.critical(f"An error occurred while running the bot: {e}", exc_info=True)