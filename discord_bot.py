import discord
from discord.ext import commands
import logging
import os
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.synced = False

    async def load_all_cogs(self):
        cogs_path = os.path.join('bot', 'cogs')
        logger.info("--- Loading Cogs ---")
        for filename in os.listdir(cogs_path):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'bot.cogs.{filename[:-3]}')
                    logger.info(f"  [+] Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"  [-] Failed to load cog {filename}: {e}", exc_info=True)

    async def setup_hook(self):
        await self.load_all_cogs()

        if not self.synced:
            logger.info("--- Syncing Slash Commands ---")
            try:
                synced = await self.tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID))
                logger.info(f"  [+] Successfully synced {len(synced)} command(s) to the guild.")
                self.synced = True
            except Exception as e:
                logger.error(f"  [-] Failed to sync commands on startup: {e}", exc_info=True)
        else:
            logger.info("Commands have already been synced.")

intents = discord.Intents.default()
intents.message_content = True 

bot = MyBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """This event is triggered when the bot is fully connected and ready to operate."""
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('Bot is ready and online!')
    await bot.change_presence(activity=discord.Game(name="Periquiando"))

if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        logger.critical("DISCORD_BOT_TOKEN is not set in the configuration. The bot cannot start.")
    else:
        try:
            bot.run(DISCORD_BOT_TOKEN)
        except Exception as e:
            logger.critical(f"An error occurred while running the bot: {e}", exc_info=True)