import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import datetime
import logging
from config import DISCORD_ACTIVE_TRADES_CHANNEL_ID, DISCORD_GUILD_ID
from config_messages.discord_messages import (
    NO_ACTIVE_TRADES_EMBED, ACTIVE_TRADES_EMBED, SEND_MESSAGE_EMBEDS,
    USER_PROFILE_EMBED, USER_NOT_FOUND_EMBED, SERVER_UNREACHABLE
)

logger = logging.getLogger(__name__)
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)


def format_status_for_discord(status):
    """Formats the trade status with color coding for Discord embeds."""
    status_lower = status.lower()
    if 'paid' in status_lower:
        return f"```diff\n+ {status}\n```"
    elif 'dispute' in status_lower:
        return f"```fix\n{status}\n```"
    elif 'active' in status_lower:
        return f"```ini\n[{status}]\n```"
    return f"`{status}`"


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

        # Create a simple representation of the current trades' state (hash, status)
        current_trades_state = {(trade.get('trade_hash'), trade.get('trade_status')) for trade in trades}

        # If the state hasn't changed, do nothing
        if current_trades_state == self.last_known_trades_state:
            logger.info("No changes in active trades. Skipping Discord channel update.")
            return

        logger.info("Change detected in active trades. Refreshing channel.")

        # If we've reached here, it means there's a change. Proceed with the update.
        if not trades:
            embed = discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED)
        else:
            embed_data = ACTIVE_TRADES_EMBED.copy()
            embed_data["title"] = embed_data["title"].format(trade_count=len(trades))
            embed = discord.Embed.from_dict(embed_data)
            for trade in trades[:20]:
                buyer = trade.get('responder_username', 'N/A')
                amount = f"{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}"
                status = trade.get('trade_status', 'N/A')
                embed.add_field(
                    name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                    value=f"**Amount**: {amount}\n**Status**:{format_status_for_discord(status)}",
                    inline=False
                )
        
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Last updated")

        await channel.purge(limit=10, check=lambda m: m.author == self.bot.user)
        await channel.send(embed=embed)
        
        # Update the state to the new one
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
            response = requests.get(
                "http://127.0.0.1:5001/get_active_trades", timeout=10)
            trades = response.json() if response.status_code == 200 else []
            if not trades:
                await interaction.followup.send(embed=discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED), ephemeral=True)
                return

            embed_data = ACTIVE_TRADES_EMBED.copy()
            embed_data["title"] = embed_data["title"].format(
                trade_count=len(trades))
            embed = discord.Embed.from_dict(embed_data)

            for trade in trades[:10]:
                embed.add_field(
                    name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {trade.get('responder_username', 'N/A')}",
                    value=f"**Amount**: {trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}\n"
                          f"**Method**: {trade.get('payment_method_name', 'N/A')}\n"
                          f"**Account**: {trade.get('account_name_source', 'N/A')}\n"
                          f"**Status**:{format_status_for_discord(trade.get('trade_status', 'N/A'))}",
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="message", description="Send a manual message to a trade chat.")
    @app_commands.describe(trade_hash="The hash of the trade", account_name="The account name handling the trade (e.g., Davidvs_Paxful)", message="The message you want to send")
    async def send_message_command(self, interaction: discord.Interaction, trade_hash: str, account_name: str, message: str):
        await interaction.response.defer(ephemeral=True)
        payload = {"trade_hash": trade_hash,
                   "account_name": account_name, "message": message}
        try:
            response = requests.post(
                "http://127.0.0.1:5001/send_manual_message", json=payload, timeout=15)
            data = response.json()
            if response.status_code == 200 and data.get("success"):
                embed_data = SEND_MESSAGE_EMBEDS["success"].copy()
                embed_data["description"] = embed_data["description"].format(
                    trade_hash=trade_hash)
                embed = discord.Embed.from_dict(embed_data)
                embed.add_field(
                    name=SEND_MESSAGE_EMBEDS["success"]["field_name"], value=message)
            else:
                embed_data = SEND_MESSAGE_EMBEDS["error"].copy()
                embed_data["description"] = embed_data["description"].format(
                    error=data.get("error", "An unknown error occurred."))
                embed = discord.Embed.from_dict(embed_data)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
            
    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="user", description="Get the trading history for a specific user.")
    @app_commands.describe(username="The username of the trader to look up.")
    async def user_profile_command(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)
        try:
            response = requests.get(
                f"http://127.0.0.1:5001/user_profile/{username}", timeout=10)
            if response.status_code == 200:
                stats = response.json()
                embed_data = USER_PROFILE_EMBED.copy()
                embed_data["title"] = embed_data["title"].format(
                    username=stats.get('username', 'N/A'))
                issues = stats.get('canceled_trades', 0) + \
                    stats.get('disputed_trades', 0)
                successful_trades = stats.get('successful_trades', 0)
                total_trades = stats.get('total_trades', 0)
                total_volume = stats.get('total_volume', 0)
                avg_trade_size = total_volume / successful_trades if successful_trades > 0 else 0
                success_rate = (successful_trades / total_trades) * \
                    100 if total_trades > 0 else 0
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
            elif response.status_code == 404:
                embed = discord.Embed.from_dict(USER_NOT_FOUND_EMBED)
                embed.description = embed.description.format(username=username)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"Error: Server responded with {response.status_code}.", ephemeral=True)
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TradeCommands(bot))