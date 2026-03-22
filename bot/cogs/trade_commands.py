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
from dateutil.parser import isoparse
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
        # Improvement 6: More aggressive no-proof highlight
        return "```diff\n- ⚠️  PAID — NO RECEIPT\n```"
    if 'Paid' in status:
        return f"```diff\n+ {status}\n```"
    if 'Dispute' in status:
        return f"```fix\n{status}\n```"
    if 'Active' in status:
        return f"```ini\n[{status}]\n```"
    return f"`{status}`"

def _format_trade_age(started_at_str):
    """Returns a human-readable trade age string from an ISO timestamp."""
    if not started_at_str:
        return ""
    try:
        started_at = isoparse(started_at_str)
        delta = datetime.datetime.now(datetime.timezone.utc) - started_at
        total_minutes = int(delta.total_seconds() / 60)
        if total_minutes < 60:
            return f"⏱️ {total_minutes}m ago"
        hours, mins = divmod(total_minutes, 60)
        return f"⏱️ {hours}h {mins}m ago"
    except Exception:
        return ""


def create_trade_field(trade, show_account=True):
    """Creates a formatted dictionary for an embed field representing a single trade."""
    trade_hash = trade.get('trade_hash', 'N/A')
    account_name = trade.get('account_name_source', 'N/A')

    # Remove platform suffix (e.g., "Noones") since we only use one platform now
    if ' ' in account_name:
        account_name = account_name.split()[0]

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

    status_text_block = format_status_for_discord_code_block(status, has_attachment)

    # Improvement 2: Trade age
    age_str = _format_trade_age(trade.get('started_at'))

    # Improvement 3: New buyer flag instead of "0 trades ($0.00 MXN)"
    profile_data = trade.get('buyer_profile')
    buyer_stats_line = ""
    if profile_data:
        successful_trades = profile_data.get('successful_trades', 0)
        total_volume = profile_data.get('total_volume', 0.0)
        currency_code = trade.get('fiat_currency_code', '')
        if successful_trades == 0:
            buyer_stats_line = "🆕 **New Buyer**\n"
        else:
            buyer_stats_line = f"**Stats:** {successful_trades} trades (${total_volume:,.2f} {currency_code})\n"

    # Improvement 5: Only show Account line when multiple accounts are in play
    account_line = f"**Account:** {account_name}\n" if show_account else ""

    field_value = (
        f"**Buyer:** {trade.get('responder_username', 'N/A')}\n"
        f"{buyer_stats_line}"
        f"**Amount:** `{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}`\n"
        f"{account_line}"
        f"{age_str}\n"
        f"{status_text_block}"
    )

    return {
        "name": f"{status_emoji} Trade `{trade_hash}`",
        "value": field_value,
        "inline": True
    }


class ConfirmationView(discord.ui.View):
    def __init__(self, trade_hash: str, account_name: str, amount: str, thread_channel=None, original_message=None):
        super().__init__(timeout=60)
        self.trade_hash = trade_hash
        self.account_name = account_name
        self.amount = amount
        self.thread_channel = thread_channel  # Used to post public confirmation (improvement 4)
        self.original_message = original_message  # Used for timeout edit (improvement 3)

    @discord.ui.button(label="Confirm Release", style=discord.ButtonStyle.green)
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
                        await interaction.followup.send(embed=embed, ephemeral=True)

                        # Improvement 4: Post a public record in the thread
                        if self.thread_channel:
                            public_embed = discord.Embed(
                                title="✅ Crypto Released",
                                description=(
                                    f"Trade `{self.trade_hash}` was released."
                                    f"\n**Amount:** {self.amount}"
                                    f"\n**Released by:** {interaction.user.mention}"
                                ),
                                color=discord.Color.green(),
                                timestamp=datetime.datetime.now(datetime.timezone.utc)
                            )
                            public_embed.set_footer(text="WillGang Bot")
                            try:
                                await self.thread_channel.send(embed=public_embed)
                            except discord.Forbidden:
                                logger.warning(f"Could not post public release confirmation to thread {self.thread_channel.id}")
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

    # Improvement 3: Handle view timeout gracefully
    async def on_timeout(self):
        if self.original_message:
            try:
                timeout_embed = discord.Embed(
                    title="⏱️ Release Timed Out",
                    description="No response received. Release was automatically cancelled.",
                    color=discord.Color.dark_gray()
                )
                await self.original_message.edit(embed=timeout_embed, view=None)
            except Exception:
                pass  # Message may have been deleted, that's fine


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
            # Improvement 4: Summary description with totals
            from collections import defaultdict
            totals = defaultdict(float)
            for t in trades:
                try:
                    totals[t.get('fiat_currency_code', 'MXN')] += float(t.get('fiat_amount_requested', 0))
                except (ValueError, TypeError):
                    pass
            total_str = '  +  '.join(f'**${v:,.0f} {k}**' for k, v in totals.items())
            summary = f"💵 {total_str} across {len(trades)} trade{'s' if len(trades) != 1 else ''}"

            # Improvement 5: Only show account if multiple accounts
            unique_accounts = {t.get('account_name_source', '') for t in trades}
            show_account = len(unique_accounts) > 1

            embed = discord.Embed(
                title=f"📊 Active Trades ({len(trades)})",
                color=COLORS.get("info", 0x5865F2),
                description=summary
            )
            for trade in trades[:25]:
                field = create_trade_field(trade, show_account=show_account)
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

            # Improvement 4: Summary description with totals
            from collections import defaultdict
            totals = defaultdict(float)
            for t in trades:
                try:
                    totals[t.get('fiat_currency_code', 'MXN')] += float(t.get('fiat_amount_requested', 0))
                except (ValueError, TypeError):
                    pass
            total_str = '  +  '.join(f'**${v:,.0f} {k}**' for k, v in totals.items())
            summary = f"💵 {total_str} across {len(trades)} trade{'s' if len(trades) != 1 else ''}"

            # Improvement 5: Only show account if multiple accounts
            unique_accounts = {t.get('account_name_source', '') for t in trades}
            show_account = len(unique_accounts) > 1

            embed = discord.Embed(
                title=f"📊 Active Trades ({len(trades)})",
                color=COLORS.get("info", 0x5865F2),
                description=summary
            )
            for trade in trades[:10]:
                field = create_trade_field(trade, show_account=show_account)
                embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])

            await interaction.followup.send(embed=embed, ephemeral=True)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="message", description="Send a manual message to a trade chat.")
    @app_commands.describe(trade_hash="The hash of the trade", account_name="The account name handling the trade (e.g., davidvs_Noones)", message="The message you want to send")
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

        # --- Build richer confirmation embed (improvements 1 & 2) ---
        has_attachment = True
        buyer_username = "N/A"
        payment_method = "N/A"
        amount = "N/A"

        if trade_info:
            amount = f"{trade_info.get('fiat_amount_requested', 'N/A')} {trade_info.get('fiat_currency_code', '')}"
            buyer_username = trade_info.get('responder_username', 'N/A')
            payment_method = trade_info.get('payment_method_name', 'N/A')
            has_attachment = trade_info.get('has_attachment', True)

        no_proof = not has_attachment

        embed_color = discord.Color.red() if no_proof else discord.Color.orange()
        embed_title = "⚠️ WARNING — No Proof Uploaded!" if no_proof else "🔒 Confirm Trade Release"

        description_lines = [
            f"**Trade:** `{trade_hash}`",
            f"**Buyer:** {buyer_username}",
            f"**Amount:** {amount}",
            f"**Payment Method:** {payment_method}",
        ]

        if no_proof:
            description_lines.append(
                "\n🚨 **No receipt has been uploaded for this trade.**"
                "\nAre you sure you want to release without verifying proof of payment?"
            )
        else:
            description_lines.append("\n✅ Receipt uploaded. Confirm release below.")

        confirmation_embed = discord.Embed(
            title=embed_title,
            description="\n".join(description_lines),
            color=embed_color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        confirmation_embed.set_footer(text="This confirmation will expire in 60 seconds.")

        # Pass the thread channel for the public post (improvement 4)
        thread_channel = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        view = ConfirmationView(trade_hash, account_name, amount, thread_channel=thread_channel)
        msg = await interaction.followup.send(embed=confirmation_embed, view=view, ephemeral=True)
        view.original_message = msg  # Needed for timeout edit (improvement 3)


async def setup(bot: commands.Bot):
    await bot.add_cog(TradeCommands(bot))