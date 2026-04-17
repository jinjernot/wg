import discord
from discord.ext import commands
import logging
import os
import asyncio
import time
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID
from core.utils.connection_guard import wait_for_internet
from core.messaging.alerts.telegram_alert import send_bot_online_alert, send_bot_offline_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reconnect backoff settings
_BACKOFF_INITIAL  = 10    # seconds — first retry delay
_BACKOFF_FACTOR   = 2     # multiply delay by this each failure
_BACKOFF_MAX      = 300   # cap at 5 minutes

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


def _make_bot() -> MyBot:
    """Creates a fresh bot instance for each reconnect attempt."""
    return MyBot(command_prefix="!", intents=intents)


@discord.ext.commands.Cog.listener.__func__  # not used directly — kept for reference
async def on_ready_handler(bot_instance):
    logger.info(f'Logged in as {bot_instance.user} (ID: {bot_instance.user.id})')
    logger.info('Bot is ready and online!')
    await bot_instance.change_presence(activity=discord.Game(name="Periquiando"))


def _run_bot_with_reconnect():
    """
    Runs the Discord bot in a reconnect loop.

    discord.py handles brief network blips internally. This outer loop
    handles prolonged outages where bot.run() fully exits. On each
    disconnection it:
      1. Waits until internet is actually reachable
      2. Backs off with exponential delay (10s → 20s → 40s … max 5min)
      3. Sends Telegram alerts on loss and recovery
      4. Creates a fresh bot instance and retries
    """
    reconnect_count = 0
    backoff = _BACKOFF_INITIAL

    while True:
        bot = _make_bot()

        # Register on_ready on the fresh instance
        @bot.event
        async def on_ready():
            logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
            logger.info('Bot is ready and online!')
            await bot.change_presence(activity=discord.Game(name="Periquiando"))

        if reconnect_count == 0:
            logger.info("Starting Discord bot...")
        else:
            logger.info(f"Reconnect attempt #{reconnect_count}...")
            try:
                send_bot_online_alert()
            except Exception:
                pass  # Don't block reconnect if Telegram is also down

        try:
            bot.run(DISCORD_BOT_TOKEN)
            # bot.run() returning normally (e.g. KeyboardInterrupt propagated as SystemExit)
            logger.info("Bot shut down cleanly.")
            break

        except KeyboardInterrupt:
            logger.info("Bot stopped by user (KeyboardInterrupt).")
            break

        except SystemExit:
            logger.info("Bot received SystemExit — stopping reconnect loop.")
            break

        except Exception as e:
            reconnect_count += 1
            logger.error(
                f"Discord bot crashed (disconnect #{reconnect_count}): {e}",
                exc_info=True
            )

            # Notify via Telegram that the bot went offline
            try:
                send_bot_offline_alert(reason=f"Auto-reconnecting after disconnect #{reconnect_count}: {e}")
            except Exception:
                pass  # Telegram may also be down — silently continue

            # Wait for internet before burning a reconnect attempt
            logger.info("Checking internet connectivity before reconnecting...")
            wait_for_internet(retry_interval=30, label="DiscordBot")

            # Exponential backoff
            logger.info(
                f"Waiting {backoff}s before reconnecting "
                f"(attempt #{reconnect_count + 1})..."
            )
            time.sleep(backoff)
            backoff = min(backoff * _BACKOFF_FACTOR, _BACKOFF_MAX)


if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        logger.critical("DISCORD_BOT_TOKEN is not set in the configuration. The bot cannot start.")
    else:
        _run_bot_with_reconnect()