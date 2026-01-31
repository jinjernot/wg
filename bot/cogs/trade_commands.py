# jinjernot/wg/wg-5555b41145cc7bfa30bd3d9892d519e559f77fce/bot/cogs/trade_commands.py

import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import aiohttp
import datetime
import logging
import re
import asyncio
from config import DISCORD_ACTIVE_TRADES_CHANNEL_ID, DISCORD_GUILD_ID
from config_messages.discord_messages import (
    NO_ACTIVE_TRADES_EMBED, ACTIVE_TRADES_EMBED, SEND_MESSAGE_EMBEDS,
    USER_PROFILE_EMBED, USER_NOT_FOUND_EMBED, SERVER_UNREACHABLE,
    RELEASE_TRADE_EMBEDS, COLORS
)
# --- ADDED IMPORT ---
from core.utils.profile import generate_user_profile

logger = logging.getLogger(__name__)
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

def format_status_for_discord_code_block(status, has_attachment=True):
    """Formats the trade status with color coding for Discord embeds using code blocks."""
    if 'Paid' in status and not has_attachment:
        return f"```diff\n- {status} (No Proof)\n```"
    if 'Paid' in status:
        return f"```diff\n+ {status}\n```"
    if 'Dispute' in status:
        return f"```fix\n{status}\n```"
    if 'Active' in status:
        return f"```ini\n[{status}]\n```"
    return f"`{status}`"

def create_trade_field(trade):
    """Creates a formatted dictionary for an embed field representing a single trade."""
    trade_hash = trade.get('trade_hash', 'N/A')
    account_name = trade.get('account_name_source', 'N/A')
    
    # Remove platform suffix (e.g., "Noones") since we only use one platform now
    if ' ' in account_name:
        account_name = account_name.split()[0]  # Keep only the first part (e.g., "Davidvs" from "Davidvs Noones")
    
    # Determine the status emoji
    status = trade.get('trade_status', 'N/A')
    has_attachment = trade.get('has_attachment', True)
    if 'Paid' in status and not has_attachment:
        status_emoji = "⚠️"
    elif 'Paid' in status:
        status_emoji = "💰"
    elif 'Dispute' in status:
        status_emoji = "⚔️"
    else:
        status_emoji = "⏳"

    # Use the function to get the colored code block for the status
    status_text_block = format_status_for_discord_code_block(status, has_attachment)

    profile_data = trade.get('buyer_profile')
    buyer_stats_line = ""
    if profile_data:
        successful_trades = profile_data.get('successful_trades', 0)
        total_volume = profile_data.get('total_volume', 0.0)
        currency_code = trade.get('fiat_currency_code', '')
        buyer_stats_line = f"**Stats:** {successful_trades} trades (${total_volume:,.2f} {currency_code})\n"

    field_value = (
        f"**Buyer:** {trade.get('responder_username', 'N/A')}\n"
        f"{buyer_stats_line}"  # <-- Add the new line here
        f"**Amount:** `{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}`\n"
        f"**Account:** {account_name}\n"
        f"{status_text_block}" # Display the status code block
    )

    return {
        # Removed the URL from the name for a cleaner look
        "name": f"{status_emoji} Trade `{trade_hash}`",
        "value": field_value,
        "inline": True
    }


class ConfirmationView(discord.ui.View):
    def __init__(self, trade_hash: str, account_name: str, amount: str):
        super().__init__(timeout=60)
        self.trade_hash = trade_hash
        self.account_name = account_name
        self.amount = amount

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        payload = {"trade_hash": self.trade_hash, "account_name": self.account_name}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://127.0.0.1:5001/release_trade", 
                    json=payload, 
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    data = await response.json()
                    if response.status == 200 and data.get("success"):
                        embed_data = RELEASE_TRADE_EMBEDS["success"].copy()
                        embed_data["description"] = embed_data["description"].format(
                            trade_hash=self.trade_hash)
                        embed = discord.Embed.from_dict(embed_data)
                    else:
                        embed_data = RELEASE_TRADE_EMBEDS["error"].copy()
                        embed_data["description"] = embed_data["description"].format(
                            error=data.get("error", "An unknown error occurred."))
                        embed = discord.Embed.from_dict(embed_data)
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Release cancelled.", ephemeral=True)
        self.stop()


class TradeCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_known_trades_state = set()
        self.refresh_live_trades_channel.start()

    def cog_unload(self):
        self.refresh_live_trades_channel.cancel()

    @tasks.loop(seconds=60)
    async def refresh_live_trades_channel(self):
        """Fetches active trades and posts a summary only if there are changes."""
        channel = self.bot.get_channel(DISCORD_ACTIVE_TRADES_CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {DISCORD_ACTIVE_TRADES_CHANNEL_ID}. Cannot refresh live feed.")
            return
        
        try:
            response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
            trades = response.json() if response.status_code == 200 else []
        except requests.exceptions.RequestException as e:
            logger.error(f"Could not connect to Flask app to refresh live trades: {e}")
            return

        current_trades_state = {(trade.get('trade_hash'), trade.get('trade_status'), trade.get('has_attachment')) for trade in trades}

        if current_trades_state == self.last_known_trades_state:
            return

        logger.info("Change detected in active trades. Refreshing channel.")

        # --- MODIFIED SECTION: Fetch profile data ---
        # Fetch profile data for all unique buyers in the trade list
        profile_cache = {}
        if trades:
            for trade in trades:
                username = trade.get('responder_username')
                if username and username not in profile_cache:
                    # This function reads from disk, so we run it in a thread to avoid blocking
                    profile_cache[username] = await asyncio.to_thread(generate_user_profile, username)
                
                # Attach the profile (or None) to the trade object
                trade['buyer_profile'] = profile_cache.get(username)
        # --- END MODIFICATION ---

        await channel.purge(limit=10, check=lambda m: m.author == self.bot.user)

        if not trades:
            embed = discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED)
        else:
            embed = discord.Embed(
                title=f"📊 Active Trades ({len(trades)})",
                color=COLORS.get("info", 0x5865F2),
                description="( ͡° ͜ʖ ͡°)"
            )
            # Add trades as fields, max 25 fields per embed
            for trade in trades[:25]:
                field = create_trade_field(trade) # trade object now contains 'buyer_profile'
                embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
        
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Last updated")
        
        await channel.send(embed=embed)
        
        self.last_known_trades_state = current_trades_state
        logger.info("Successfully refreshed the active trades channel with new data.")


    @refresh_live_trades_channel.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="trades", description="Get a list of currently active trades.")
    async def active_trades_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:5001/get_active_trades", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    trades = await response.json() if response.status == 200 else []
            if not trades:
                await interaction.followup.send(embed=discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED), ephemeral=True)
                return

            # --- MODIFIED SECTION: Fetch profile data ---
            profile_cache = {}
            if trades:
                for trade in trades:
                    username = trade.get('responder_username')
                    if username and username not in profile_cache:
                        profile_cache[username] = await asyncio.to_thread(generate_user_profile, username)
                    trade['buyer_profile'] = profile_cache.get(username)
            # --- END MODIFICATION ---

            embed = discord.Embed(
                title=f"📊 Active Trades ({len(trades)})",
                color=COLORS.get("info", 0x5865F2),
                description="A summary of your ongoing trades."
            )

            # Add trades as fields, max 10 for ephemeral messages for readability
            for trade in trades[:10]:
                field = create_trade_field(trade) # trade object now contains 'buyer_profile'
                embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])

            await interaction.followup.send(embed=embed, ephemeral=True)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="message", description="Send a manual message to a trade chat.")
    @app_commands.describe(trade_hash="The hash of the trade", account_name="The account name handling the trade (e.g., Davidvs_Paxful)", message="The message you want to send")
    async def send_message_command(self, interaction: discord.Interaction, trade_hash: str, account_name: str, message: str):
        await interaction.response.defer(ephemeral=True)
        payload = {"trade_hash": trade_hash, "account_name": account_name, "message": message}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://127.0.0.1:5001/send_manual_message", 
                    json=payload, 
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    data = await response.json()
                    if response.status == 200 and data.get("success"):
                        embed_data = SEND_MESSAGE_EMBEDS["success"].copy()
                        embed_data["description"] = embed_data["description"].format(trade_hash=trade_hash)
                        embed = discord.Embed.from_dict(embed_data)
                        embed.add_field(name=SEND_MESSAGE_EMBEDS["success"]["field_name"], value=message)
                    else:
                        embed_data = SEND_MESSAGE_EMBEDS["error"].copy()
                        embed_data["description"] = embed_data["description"].format(error=data.get("error", "An unknown error occurred."))
                        embed = discord.Embed.from_dict(embed_data)
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
            
    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="user", description="Get the trading history for a specific user.")
    @app_commands.describe(username="The username of the trader to look up.")
    async def user_profile_command(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:5001/user_profile/{username}", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    status_code = response.status
                    if status_code == 200:
                        stats = await response.json()
                        embed_data = USER_PROFILE_EMBED.copy()
                        embed_data["title"] = embed_data["title"].format(username=stats.get('username', 'N/A'))
                        issues = stats.get('canceled_trades', 0) + stats.get('disputed_trades', 0)
                        successful_trades = stats.get('successful_trades', 0)
                        total_trades = stats.get('total_trades', 0)
                        total_volume = stats.get('total_volume', 0)
                        avg_trade_size = total_volume / successful_trades if successful_trades > 0 else 0
                        success_rate = (successful_trades / total_trades) * 100 if total_trades > 0 else 0
                        embed_data["description"] = embed_data["description"].format(
                            first_trade_date=stats.get('first_trade_date', 'N/A'),
                            last_trade_date=stats.get('last_trade_date', 'N/A')
                        )
                        for field in embed_data["fields"]:
                            field["value"] = field["value"].format(
                                total_volume=total_volume,
                                avg_trade_size=avg_trade_size,
                                success_rate=f"{success_rate:.1f}",
                                successful_trades=successful_trades,
                                issues=issues
                            )
                        embed = discord.Embed.from_dict(embed_data)
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    elif status_code == 404:
                        embed = discord.Embed.from_dict(USER_NOT_FOUND_EMBED)
                        embed.description = embed.description.format(username=username)
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        await interaction.followup.send(f"Error: Server responded with {status_code}.", ephemeral=True)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="release", description="Release the crypto for a trade.")
    @app_commands.describe(trade_hash="The hash of the trade (optional, detected from thread)", account_name="The account name handling the trade (optional, detected from thread)")
    async def release_trade_command(self, interaction: discord.Interaction, trade_hash: str = None, account_name: str = None):
        await interaction.response.defer(ephemeral=True)
        trade_info = None

        if not trade_hash or not account_name:
            if isinstance(interaction.channel, discord.Thread):
                match = re.match(r"Trade Log: ([\w-]+)", interaction.channel.name)
                if match:
                    inferred_trade_hash = match.group(1)
                    if not trade_hash:
                        trade_hash = inferred_trade_hash
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get("http://127.0.0.1:5001/get_active_trades", timeout=aiohttp.ClientTimeout(total=10)) as response:
                                if response.status == 200:
                                    trades = await response.json()
                                    trade_info = next((t for t in trades if t.get('trade_hash') == trade_hash), None)
                                    if trade_info:
                                        if not account_name:
                                            account_name = trade_info.get('account_name_source')
                                    else:
                                        await interaction.followup.send("Could not find an active trade with this hash.", ephemeral=True)
                                        return
                                else:
                                    await interaction.followup.send("Could not fetch active trades to determine the account name.", ephemeral=True)
                                    return
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
                        return
                else:
                    await interaction.followup.send("This does not appear to be a trade log thread.", ephemeral=True)
                    return
            else:
                await interaction.followup.send("Please run this command in a trade log thread or provide the trade_hash and account_name.", ephemeral=True)
                return

        if not trade_hash or not account_name:
            await interaction.followup.send("Could not determine the trade_hash and/or account_name.", ephemeral=True)
            return

        amount = "N/A"
        if trade_info:
            amount = f"{trade_info.get('fiat_amount_requested', 'N/A')} {trade_info.get('fiat_currency_code', '')}"

        confirmation_embed = discord.Embed(
            title="Confirm Trade Release",
            description=f"Please confirm you want to release the trade `{trade_hash}` for the amount of **{amount}**.",
            color=discord.Color.orange()
        )
        view = ConfirmationView(trade_hash, account_name, amount)
        await interaction.followup.send(embed=confirmation_embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TradeCommands(bot))