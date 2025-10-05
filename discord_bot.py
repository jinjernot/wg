import discord
from discord.ext import commands
import logging
import os
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID

# --- Standard Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Custom Bot Class for Reliable Cog Loading & Command Syncing ---
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A flag to ensure we only sync commands once on startup
        self.synced = False

    async def load_all_cogs(self):
        """Finds and loads all Python files in the bot/cogs directory."""
        cogs_path = os.path.join('bot', 'cogs')
        logger.info("--- Loading Cogs ---")
        for filename in os.listdir(cogs_path):
            if filename.endswith('.py'):
                try:
                    # The path to the extension is bot.cogs.filename (without .py)
                    await self.load_extension(f'bot.cogs.{filename[:-3]}')
                    logger.info(f"  [+] Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"  [-] Failed to load cog {filename}: {e}", exc_info=True)

    async def setup_hook(self):
        """
        This is the most important part of the bot's startup.
        It runs after the bot logs in but before it's fully connected.
        This is the correct place to load cogs and sync slash commands.
        """
        await self.load_all_cogs()

        # We only want to sync the commands once.
        if not self.synced:
            logger.info("--- Syncing Slash Commands ---")
            try:
                # The `guild` parameter is crucial. It tells Discord to sync the commands
                # immediately to your specific server, which is much faster than global syncing.
                synced = await self.tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID))
                logger.info(f"  [+] Successfully synced {len(synced)} command(s) to the guild.")
                self.synced = True
            except Exception as e:
                logger.error(f"  [-] Failed to sync commands on startup: {e}", exc_info=True)
        else:
            logger.info("Commands have already been synced.")

# --- Bot Initialization ---
# Define the necessary intents for the bot to function.
intents = discord.Intents.default()
intents.message_content = True # Required for message-related events if you use them.

# Create an instance of our custom Bot class.
bot = MyBot(command_prefix="!", intents=intents)

# --- Bot Events ---
@bot.event
async def on_ready():
    """This event is triggered when the bot is fully connected and ready to operate."""
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('Bot is ready and online!')
    # Set a custom status for the bot.
    await bot.change_presence(activity=discord.Game(name="/status for info"))

# --- Starting the Bot ---
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        logger.critical("DISCORD_BOT_TOKEN is not set in the configuration. The bot cannot start.")
    else:
        try:
            # This is the main entry point that runs the bot.
            bot.run(DISCORD_BOT_TOKEN)
        except Exception as e:
            logger.critical(f"An error occurred while running the bot: {e}", exc_info=True)