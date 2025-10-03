import discord
from discord.ext import commands
import logging
import os
import asyncio
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID

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
    # The automatic sync on startup can sometimes be unreliable with stubborn caches.
    # We will rely on the manual sync command for now.
    logger.info("Bot is ready. Use the !sync command to update slash commands.")

# --- Manual Sync Command ---
@bot.command()
@commands.guild_only() # Optional: Restricts the command to a server
@commands.is_owner()  # Ensures only you (the bot owner) can run this
async def sync(ctx: commands.Context):
    """
    Manually syncs slash commands to the current guild.
    """
    logger.info(f"'{ctx.author}' is attempting to manually sync commands...")
    await ctx.send("Syncing commands to the server...")
    try:
        # This is a forceful way to sync commands to a specific guild
        synced = await bot.tree.sync(guild=ctx.guild)
        
        message = f"Successfully synced **{len(synced)}** command(s) to this server."
        logger.info(message)
        await ctx.send(message)
    except Exception as e:
        message = f"Failed to sync commands: {e}"
        logger.error(message, exc_info=True)
        await ctx.send(message)

async def load_cogs():
    """Loads all cogs from the 'bot/cogs' directory."""
    cogs_path = os.path.join('bot', 'cogs')
    for filename in os.listdir(cogs_path):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'bot.cogs.{filename[:-3]}')
                logger.info(f"Loaded cog: {filename}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)

async def main():
    """Main function to load cogs and run the bot."""
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_BOT_TOKEN)

# --- Starting the Bot ---
if __name__ == "__main__":
    asyncio.run(main())