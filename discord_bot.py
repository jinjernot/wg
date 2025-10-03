import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import logging
import os
import datetime
from config import (
    DISCORD_BOT_TOKEN, 
    DISCORD_GUILD_ID, 
    DISCORD_ACTIVE_TRADES_CHANNEL_ID,
    REPORTS_DIR
)
from config_messages.discord_messages import (
    STATUS_EMBED, 
    BOT_CONTROL_EMBEDS, 
    SETTINGS_EMBEDS, 
    SERVER_UNREACHABLE, 
    COLORS,
    NO_ACTIVE_TRADES_EMBED, 
    ACTIVE_TRADES_EMBED, 
    SEND_MESSAGE_EMBEDS,
    USER_PROFILE_EMBED, 
    USER_NOT_FOUND_EMBED, 
    TOGGLE_OFFERS_EMBED
)
import bitso_config
from core.api.wallet import get_wallet_balances
from core.bitso.bitso_reports import generate_growth_chart, process_user_funding
from dateutil.parser import parse as date_parse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
GUILD_OBJECT = discord.Object(id=DISCORD_GUILD_ID)

last_known_trades_state = set()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}. Bot is ready!')
    await bot.change_presence(activity=discord.Game(name="/status for info"))
    refresh_live_trades_channel.start()

@bot.event
async def setup_hook():
    logger.info("Running setup_hook to sync commands...")
    try:
        synced = await bot.tree.sync(guild=GUILD_OBJECT)
        logger.info(f"--- Successfully synced {len(synced)} command(s). ---")
    except Exception as e:
        logger.error(f"Failed to sync commands on startup: {e}", exc_info=True)

def format_status_for_discord(status):
    status_lower = status.lower()
    if 'paid' in status_lower:
        return f"```diff\n+ {status}\n```"
    elif 'dispute' in status_lower:
        return f"```fix\n{status}\n```"
    elif 'active' in status_lower:
        return f"```ini\n[{status}]\n```"
    return f"`{status}`"

@tasks.loop(seconds=60)
async def refresh_live_trades_channel():
    global last_known_trades_state
    channel = bot.get_channel(DISCORD_ACTIVE_TRADES_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find channel with ID {DISCORD_ACTIVE_TRADES_CHANNEL_ID}.")
        return
    
    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        trades = response.json() if response.status_code == 200 else []
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Flask app to refresh live trades: {e}")
        return

    current_trades_state = {(trade.get('trade_hash'), trade.get('trade_status')) for trade in trades}

    if current_trades_state == last_known_trades_state:
        return

    logger.info("Change detected in active trades. Refreshing channel.")

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

    await channel.purge(limit=10, check=lambda m: m.author == bot.user)
    await channel.send(embed=embed)
    
    last_known_trades_state = current_trades_state
    logger.info("Successfully refreshed the active trades channel with new data.")

@refresh_live_trades_channel.before_loop
async def before_refresh():
    await bot.wait_until_ready()

@bot.tree.command(name="status", description="Check the status of the trading bot.", guild=GUILD_OBJECT)
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed_data = {}
    try:
        response = requests.get("http://127.0.0.1:5001/trading_status", timeout=5)
        if response.status_code == 200:
            status_json = response.json().get("status")
            embed_data = STATUS_EMBED["running"] if status_json == "Running" else STATUS_EMBED["stopped"]
        else:
            embed_data = STATUS_EMBED["error"].copy()
            embed_data["description"] = embed_data["description"].format(status_code=response.status_code)
    except requests.exceptions.RequestException:
        embed_data = STATUS_EMBED["unreachable"]
    await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)

@bot.tree.command(name="bot", description="Start or stop the trading bot process.", guild=GUILD_OBJECT)
@app_commands.describe(action="Choose whether to start or stop the bot")
@app_commands.choices(action=[
    app_commands.Choice(name="Start", value="start"),
    app_commands.Choice(name="Stop", value="stop"),
])
async def bot_control(interaction: discord.Interaction, action: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    endpoint = "/start_trading" if action.value == "start" else "/stop_trading"
    try:
        response = requests.post(f"http://127.0.0.1:5001{endpoint}", timeout=10)
        data = response.json()
        if data.get("success"):
            embed_data = BOT_CONTROL_EMBEDS[f"{action.value}_success"].copy()
            embed_data["description"] = embed_data["description"].format(message=data.get("message"))
        else:
            embed_data = BOT_CONTROL_EMBEDS["error"].copy()
            embed_data["title"] = embed_data["title"].format(action=action.name)
            embed_data["description"] = embed_data["description"].format(message=data.get("message", "An unknown error occurred."))
        await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="settings", description="Change a bot setting.", guild=GUILD_OBJECT)
@app_commands.describe(setting="The setting you want to change", status="The new status for the setting")
@app_commands.choices(setting=[
    app_commands.Choice(name="Night Mode", value="night_mode_enabled"),
    app_commands.Choice(name="AFK Mode", value="afk_mode_enabled"),
    app_commands.Choice(name="Verbose Logging", value="verbose_logging_enabled"),
], status=[
    app_commands.Choice(name="On", value="true"),
    app_commands.Choice(name="Off", value="false"),
])
async def settings(interaction: discord.Interaction, setting: app_commands.Choice[str], status: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    payload = {"key": setting.value, "enabled": status.value == "true"}
    try:
        response = requests.post("http://127.0.0.1:5001/update_setting", json=payload, timeout=10)
        data = response.json()
        if response.status_code == 200 and data.get("success"):
            embed_data = SETTINGS_EMBEDS["success"].copy()
            embed_data["description"] = embed_data["description"].format(setting_name=setting.name, status_name=status.name)
        else:
            embed_data = SETTINGS_EMBEDS["error"].copy()
            embed_data["description"] = embed_data["description"].format(error=data.get("error", "An unknown server error occurred."))
        await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="balance", description="Check the wallet balances of all accounts.", guild=GUILD_OBJECT)
async def balance(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        balances = get_wallet_balances()
        embed = discord.Embed(title="💰 Wallet Balances", color=COLORS.get("info", 0x5865F2))
        if not balances:
            embed.description = "Could not fetch any wallet balances."
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        for account_name, balance_data in balances.items():
            if "error" in balance_data:
                value = f"❌ Error: {balance_data['error']}"
            else:
                filtered_balances = {code: amount for code, amount in balance_data.items() if float(amount) != 0}
                if filtered_balances:
                    value = "\n".join([f"**{code.upper()}:** `{amount}`" for code, amount in filtered_balances.items()])
                else:
                    value = "No active balances."
            embed.add_field(name=f"--- {account_name} ---", value=value, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"An error occurred in the balance command: {e}")
        await interaction.followup.send("An unexpected error occurred while fetching balances.", ephemeral=True)

@bot.tree.command(name="bitso", description="Get a summary of Bitso deposits for a specific month.", guild=GUILD_OBJECT)
@app_commands.describe(month="The month to get the summary for (e.g., 'August' or 'August 2023'). Defaults to the current month.")
async def bitso(interaction: discord.Interaction, month: str = None):
    await interaction.response.defer(ephemeral=True)
    try:
        params = {}
        if month:
            params['month'] = month
        response = requests.get("http://127.0.0.1:5001/bitso_summary", params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                deposits = data.get("deposits_by_sender", [])
                total = data.get("total_deposits", 0.0)
                month_str = data.get("month_str", "Current Month")
                description = "\n".join([f"**{name}:** `${amount:,.2f}`" for name, amount in deposits])
                embed = discord.Embed(title=f"💰 Bitso Deposits for {month_str}", description=description, color=discord.Color.green())
                embed.add_field(name="Total", value=f"**`${total:,.2f}`**")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"Error: {data.get('error', 'Unknown error.')}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error: Server responded with {response.status_code}.", ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="bitso_chart", description="Generate a chart of Bitso income for a specific month.", guild=GUILD_OBJECT)
@app_commands.describe(month="The month to generate the report for (e.g., 'August' or 'August 2023')")
async def bitso_chart(interaction: discord.Interaction, month: str = None):
    await interaction.response.defer(ephemeral=True)
    try:
        target_date = date_parse(month) if month else datetime.datetime.now()
        year, month_num = target_date.year, target_date.month
        all_fundings = []
        for user, (key, secret) in bitso_config.API_KEYS.items():
            _, fundings = process_user_funding(user, key, secret, year, month_num)
            all_fundings.extend(fundings)
        if not all_fundings:
            await interaction.followup.send(f"No Bitso funding data found for {target_date.strftime('%B %Y')}.", ephemeral=True)
            return
        chart_filename = f"bitso_income_{year}_{month_num}.png"
        chart_filepath = os.path.join(REPORTS_DIR, chart_filename)
        generate_growth_chart(all_fundings, year, month_num, filename=chart_filename)
        if os.path.exists(chart_filepath):
            await interaction.followup.send(file=discord.File(chart_filepath), ephemeral=True)
            os.remove(chart_filepath)
        else:
            await interaction.followup.send("Could not generate the chart.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

@bot.tree.command(name="charts", description="Generate and display charts for your trading activity.", guild=GUILD_OBJECT)
async def charts(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        response = requests.post("http://127.0.0.1:5001/generate_charts", timeout=60)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                chart_paths = data.get("charts", {})
                files = [discord.File(fp) for fp in chart_paths.values() if os.path.exists(fp)]
                if files:
                    await interaction.followup.send(files=files, ephemeral=True)
                else:
                    await interaction.followup.send("Charts generated, but no files were found.", ephemeral=True)
            else:
                await interaction.followup.send(f"Error: {data.get('error', 'Unknown error.')}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error: Server responded with {response.status_code}.", ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="offers", description="Turn all trading offers on or off.", guild=GUILD_OBJECT)
@app_commands.describe(status="The desired status for your offers")
@app_commands.choices(status=[
    app_commands.Choice(name="On", value="on"),
    app_commands.Choice(name="Off", value="off"),
])
async def offers(interaction: discord.Interaction, status: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    is_enabled = status.value == "on"
    try:
        response = requests.post("http://127.0.0.1:5001/offer/toggle", json={"enabled": is_enabled}, timeout=15)
        data = response.json()
        if response.status_code == 200 and data.get("success"):
            embed_data = TOGGLE_OFFERS_EMBED["success"].copy()
            embed_data["title"] = embed_data["title"].format(status=status.name)
            embed_data["description"] = data.get("message", f"Offers are now {status.name}.")
            if not is_enabled:
                embed_data['color'] = COLORS['error']
        else:
            embed_data = TOGGLE_OFFERS_EMBED["error"].copy()
            embed_data["description"] = data.get("error", "Unknown server error.")
        await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="list_offers", description="Lists all of your active offers.", guild=GUILD_OBJECT)
async def list_offers(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        response = requests.get("http://127.0.0.1:5001/get_offers", timeout=15)
        offers_list = response.json() if response.status_code == 200 else []
        if not offers_list:
            await interaction.followup.send("You have no active offers.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Your Active Offers ({len(offers_list)})", color=COLORS["info"])
        for offer in offers_list[:20]:
            status = "✅ On" if offer.get('enabled') else "❌ Off"
            embed.add_field(
                name=f"{offer.get('payment_method_name', 'N/A')} ({offer.get('account_name', 'N/A')})",
                value=f"**Margin**: {offer.get('margin', 'N/A')}%\n"
                      f"**Range**: {offer.get('fiat_amount_range_min', 'N/A')} - {offer.get('fiat_amount_range_max', 'N/A')} {offer.get('fiat_currency_code', '')}\n"
                      f"**Status**: {status}\n"
                      f"**Hash**: `{offer.get('offer_hash', 'N/A')}`",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="toggle_offer", description="Turn a specific offer on or off.", guild=GUILD_OBJECT)
@app_commands.describe(offer_hash="The hash of the offer to toggle", account_name="The account that owns the offer (e.g., David_Noones)", status="The desired status")
@app_commands.choices(status=[app_commands.Choice(name="On", value="on"), app_commands.Choice(name="Off", value="off")])
async def toggle_offer(interaction: discord.Interaction, offer_hash: str, account_name: str, status: app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    is_enabled = status.value == "on"
    payload = {"offer_hash": offer_hash, "account_name": account_name, "enabled": is_enabled}
    try:
        response = requests.post("http://127.0.0.1:5001/offer/toggle_single", json=payload, timeout=15)
        data = response.json()
        if response.status_code == 200 and data.get("success"):
            embed = discord.Embed(title=f"✅ Offer Status Updated", description=f"Successfully turned **{status.name}** the offer `{offer_hash}`.", color=COLORS["success"] if is_enabled else COLORS["error"])
        else:
            embed = discord.Embed(title=f"❌ Error Updating Offer", description=f"Failed to update offer `{offer_hash}`.\n**Reason**: {data.get('error', 'Unknown error.')}", color=COLORS["error"])
        await interaction.followup.send(embed=embed, ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="trades", description="Get a list of currently active trades.", guild=GUILD_OBJECT)
async def trades(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        trades_list = response.json() if response.status_code == 200 else []
        if not trades_list:
            await interaction.followup.send(embed=discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED), ephemeral=True)
            return
        embed_data = ACTIVE_TRADES_EMBED.copy()
        embed_data["title"] = embed_data["title"].format(trade_count=len(trades_list))
        embed = discord.Embed.from_dict(embed_data)
        for trade in trades_list[:10]:
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

@bot.tree.command(name="message", description="Send a manual message to a trade chat.", guild=GUILD_OBJECT)
@app_commands.describe(trade_hash="The hash of the trade", account_name="The account name handling the trade (e.g., Davidvs_Paxful)", message="The message you want to send")
async def message(interaction: discord.Interaction, trade_hash: str, account_name: str, message: str):
    await interaction.response.defer(ephemeral=True)
    payload = {"trade_hash": trade_hash, "account_name": account_name, "message": message}
    try:
        response = requests.post("http://127.0.0.1:5001/send_manual_message", json=payload, timeout=15)
        data = response.json()
        if response.status_code == 200 and data.get("success"):
            embed_data = SEND_MESSAGE_EMBEDS["success"].copy()
            embed_data["description"] = embed_data["description"].format(trade_hash=trade_hash)
            embed = discord.Embed.from_dict(embed_data)
            embed.add_field(name=SEND_MESSAGE_EMBEDS["success"]["field_name"], value=message)
        else:
            embed_data = SEND_MESSAGE_EMBEDS["error"].copy()
            embed_data["description"] = embed_data["description"].format(error=data.get("error", "An unknown error occurred."))
            embed = discord.Embed.from_dict(embed_data)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

@bot.tree.command(name="user", description="Get the trading history for a specific user.", guild=GUILD_OBJECT)
@app_commands.describe(username="The username of the trader to look up.")
async def user(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
    try:
        response = requests.get(f"http://127.0.0.1:5001/user_profile/{username}", timeout=10)
        if response.status_code == 200:
            stats = response.json()
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
        elif response.status_code == 404:
            embed = discord.Embed.from_dict(USER_NOT_FOUND_EMBED)
            embed.description = embed.description.format(username=username)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"Error: Server responded with {response.status_code}.", ephemeral=True)
    except requests.exceptions.RequestException:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

if __name__ == "__main__":
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.critical(f"An error occurred while running the bot: {e}", exc_info=True)