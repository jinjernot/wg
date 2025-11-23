import discord
from discord.ext import commands
import aiohttp
import logging
import re
from config import DISCORD_GUILD_ID

logger = logging.getLogger(__name__)
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

class ChatBridge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

import discord
from discord.ext import commands
import aiohttp # Changed from requests to aiohttp
import logging
import re
from config import DISCORD_GUILD_ID

logger = logging.getLogger(__name__)
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

class ChatBridge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return

        if isinstance(message.channel, discord.Thread):
            match = re.match(r"Trade Log: ([\w-]+)", message.channel.name)
            if match:
                trade_hash = match.group(1)
                logger.info(f"Message in thread for trade {trade_hash}: {message.content}")

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get("http://127.0.0.1:5001/get_active_trades", timeout=10) as response:
                            if response.status == 200:
                                trades = await response.json()
                                trade_info = next((t for t in trades if t.get('trade_hash') == trade_hash), None)

                                if trade_info:
                                    account_name = trade_info.get('account_name_source')
                                    if account_name:
                                        payload = {
                                            "trade_hash": trade_hash,
                                            "account_name": account_name,
                                            "message": message.content
                                        }
                                        async with session.post("http://127.0.0.1:5001/send_manual_message", json=payload, timeout=15) as send_response:
                                            if send_response.status == 200:
                                                resp_json = await send_response.json()
                                                if resp_json.get("success"):
                                                    await message.add_reaction("✅")
                                                else:
                                                    await message.add_reaction("❌")
                                            else:
                                                await message.add_reaction("❌")
                                    else:
                                        await message.add_reaction("🤷‍♀️") # Account name not found
                                else:
                                    await message.add_reaction("🤷‍♂️") # Trade not found
                            else:
                                await message.add_reaction("🔥") # Server error
                except Exception as e:
                    logger.error(f"Error in chat bridge: {e}")
                    await message.add_reaction("🌐") # Network error

async def setup(bot: commands.Bot):
    await bot.add_cog(ChatBridge(bot))