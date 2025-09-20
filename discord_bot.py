# jinjernot/wg/wg-58e87644bc389c5c3f8f57d6d639116b58c265f7/discord_bot.py
import discord
from discord import app_commands
from discord.ext import tasks
import logging
import requests
import datetime
import os
from bitso_reports import generate_growth_chart, process_user_funding
import bitso_config
from dateutil.parser import parse as date_parse


from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_ACTIVE_TRADES_CHANNEL_ID
from config_messages.discord_messages import *

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- THIS IS NO LONGER STRICTLY NEEDED FOR COMMAND SYNCING BUT CAN BE KEPT FOR OTHER USES ---
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)
ACTIVE_TRADES_CHANNEL_ID = DISCORD_ACTIVE_TRADES_CHANNEL_ID


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

# --- Bot Events & Background Task ---
@client.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
    # --- CHANGED: Sync commands globally instead of to a specific guild ---
    await tree.sync()

    logger.info(f'Logged in as {client.user}. Bot is ready!')
    await client.change_presence(activity=discord.Game(name="/status for info"))

    if not post_live_trades.is_running():
        post_live_trades.start()

@tasks.loop(minutes=2)
async def post_live_trades():
    """A background task that re-uses the logic from /active_trades to post a summary."""
    channel = client.get_channel(ACTIVE_TRADES_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find channel {ACTIVE_TRADES_CHANNEL_ID}. Live feed is disabled.")
        return

    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        if response.status_code != 200:
            logger.error(f"Live feed update failed: Server responded with {response.status_code}")
            return

        trades = response.json()

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
                formatted_status = format_status_for_discord(status)

                embed.add_field(
                    name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                    value=f"**Amount**: {amount}\n**Status**:{formatted_status}",
                    inline=False
                )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Last updated")

        await channel.purge(limit=10, check=lambda m: m.author == client.user)
        await channel.send(embed=embed)

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Flask app for live trades task: {e}")

@post_live_trades.before_loop
async def before_post_live_trades():
    """Ensures the bot is ready before the task starts."""
    await client.wait_until_ready()


# --- Slash Commands ---
@tree.command(name="status", description="Check the status of the trading bot.")
async def status_command(interaction: discord.Interaction):
    """Handles the /status slash command."""
    await interaction.response.defer(ephemeral=True)

    embed_data = {}
    try:
        response = requests.get("http://127.0.0.1:5001/trading_status", timeout=5)
        if response.status_code == 200:
            status = response.json().get("status")
            if status == "Running":
                embed_data = STATUS_EMBED["running"]
            else:
                embed_data = STATUS_EMBED["stopped"]
        else:
            embed_data = STATUS_EMBED["error"].copy()
            embed_data["description"] = embed_data["description"].format(status_code=response.status_code)

    except requests.exceptions.RequestException as e:
        embed_data = STATUS_EMBED["unreachable"]
        logger.error(f"Could not connect to Flask app for status check: {e}")

    await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)


@tree.command(name="trades", description="Get a list of currently active trades.")
async def active_trades_command(interaction: discord.Interaction):
    """Handles the /trades slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        if response.status_code != 200:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.", ephemeral=True)
            return

        trades = response.json()

        if not trades:
            embed = discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed_data = ACTIVE_TRADES_EMBED.copy()
        embed_data["title"] = embed_data["title"].format(trade_count=len(trades))
        embed = discord.Embed.from_dict(embed_data)

        for trade in trades[:10]:
            buyer = trade.get('responder_username', 'N/A')
            amount = f"{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}"
            payment_method = trade.get('payment_method_name', 'N/A')
            account_name = trade.get('account_name_source', 'N/A')
            status = trade.get('trade_status', 'N/A')
            formatted_status = format_status_for_discord(status)

            embed.add_field(
                name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                value=f"**Amount**: {amount}\n**Method**: {payment_method}\n**Account**: {account_name}\n**Status**:{formatted_status}",
                inline=False
            )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Live data")

        await interaction.followup.send(embed=embed, ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for active trades: {e}")


@tree.command(name="offers", description="Turn all trading offers on or off.")
@app_commands.describe(status="The desired status for your offers")
@app_commands.choices(status=[
    app_commands.Choice(name="On", value="on"),
    app_commands.Choice(name="Off", value="off"),
])
async def toggle_offers_command(interaction: discord.Interaction, status: app_commands.Choice[str]):
    """Handles the /offers command by calling the specific turn-on/off routes."""
    await interaction.response.defer(ephemeral=True)

    url = "http://127.0.0.1:5001/offer/toggle"
    is_enabled = True if status.value == "on" else False

    try:
        response = requests.post(url, json={"enabled": is_enabled}, timeout=15)

        if response.status_code == 200:
            data = response.json()
            embed_data = TOGGLE_OFFERS_EMBED["success"].copy()
            embed_data["title"] = embed_data["title"].format(status=status.name)
            embed_data["description"] = embed_data["description"].format(message=data.get("message", f"Offers are now {status.name}."))
            if status.value == 'off':
                embed_data['color'] = COLORS['error']

            embed = discord.Embed.from_dict(embed_data)
        else:
            embed_data = TOGGLE_OFFERS_EMBED["error"].copy()
            embed_data["description"] = embed_data["description"].format(status_code=response.status_code)
            embed = discord.Embed.from_dict(embed_data)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /toggle_offers: {e}")

@tree.command(name="bot", description="Start or stop the trading bot process.")
@app_commands.describe(action="Choose whether to start or stop the bot")
@app_commands.choices(action=[
    app_commands.Choice(name="Start", value="start"),
    app_commands.Choice(name="Stop", value="stop"),
])
async def bot_command(interaction: discord.Interaction, action: app_commands.Choice[str]):
    """Handles starting and stopping the bot."""
    await interaction.response.defer(ephemeral=True)

    endpoint = "/start_trading" if action.value == "start" else "/stop_trading"
    url = f"http://127.0.0.1:5001{endpoint}"

    try:
        response = requests.post(url, timeout=10)
        data = response.json()

        if data.get("success"):
            if action.value == "start":
                embed_data = BOT_CONTROL_EMBEDS["start_success"].copy()
            else:
                embed_data = BOT_CONTROL_EMBEDS["stop_success"].copy()
            embed_data["description"] = embed_data["description"].format(message=data.get("message"))
        else:
            embed_data = BOT_CONTROL_EMBEDS["error"].copy()
            embed_data["title"] = embed_data["title"].format(action=action.name)
            embed_data["description"] = embed_data["description"].format(message=data.get("message", "An unknown error occurred."))

        await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /bot command: {e}")

@tree.command(name="settings", description="Change a bot setting.")
@app_commands.describe(
    setting="The setting you want to change",
    status="The new status for the setting"
)
@app_commands.choices(setting=[
    app_commands.Choice(name="Night Mode", value="night_mode_enabled"),
    app_commands.Choice(name="AFK Mode", value="afk_mode_enabled"),
    app_commands.Choice(name="Verbose Logging", value="verbose_logging_enabled"),
])
@app_commands.choices(status=[
    app_commands.Choice(name="On", value="true"),
    app_commands.Choice(name="Off", value="false"),
])
async def settings_command(interaction: discord.Interaction, setting: app_commands.Choice[str], status: app_commands.Choice[str]):
    """Handles changing application settings."""
    await interaction.response.defer(ephemeral=True)

    url = "http://127.0.0.1:5001/update_setting"
    is_enabled = True if status.value == "true" else False
    payload = {"key": setting.value, "enabled": is_enabled}

    try:
        response = requests.post(url, json=payload, timeout=10)
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

@tree.command(name="message", description="Send a manual message to a trade chat.")
@app_commands.describe(
    trade_hash="The hash of the trade",
    account_name="The account name handling the trade (e.g., Davidvs_Paxful)",
    message="The message you want to send"
)
async def send_message_command(interaction: discord.Interaction, trade_hash: str, account_name: str, message: str):
    """Handles sending a manual message to a trade."""
    await interaction.response.defer(ephemeral=True)

    url = "http://127.0.0.1:5001/send_manual_message"
    payload = {
        "trade_hash": trade_hash,
        "account_name": account_name,
        "message": message
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
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

@tree.command(name="user", description="Get the trading history for a specific user.")
@app_commands.describe(username="The username of the trader to look up.")
async def user_profile_command(interaction: discord.Interaction, username: str):
    """Handles the /user slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        url = f"http://127.0.0.1:5001/user_profile/{username}"
        response = requests.get(url, timeout=10)

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

            if stats.get("platforms"):
                platform_stats = []
                for platform, data in stats["platforms"].items():
                    platform_stats.append(f"**{platform.capitalize()}**: {data['trades']} trades (${data['volume']:.2f})")
                embed.add_field(name="Platform Activity", value="\n".join(platform_stats), inline=False)

            if stats.get("accounts"):
                account_stats = []
                for owner, count in stats["accounts"].items():
                    account_stats.append(f"**{owner.capitalize()}**: {count} trades")
                embed.add_field(name="Handled By", value="\n".join(account_stats), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        elif response.status_code == 404:
            embed_data = USER_NOT_FOUND_EMBED.copy()
            embed_data["description"] = embed_data["description"].format(username=username)
            embed = discord.Embed.from_dict(embed_data)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.", ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /user_profile: {e}")

@tree.command(name="bitso", description="Get a summary of Bitso deposits for the current month.")
async def bitso_summary_command(interaction: discord.Interaction):
    """Handles the /bitso slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        url = "http://127.0.0.1:5001/bitso_summary"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                deposits_by_sender = data.get("deposits_by_sender", [])
                total_deposits = data.get("total_deposits", 0.0)

                description_lines = [f"**{name}:** `${amount:,.2f}`" for name, amount in deposits_by_sender]
                description = "\n".join(description_lines)

                embed = discord.Embed(
                    title="💰 Bitso Deposits",
                    description=description,
                    color=discord.Color.green()
                )
                embed.add_field(name="Total", value=f"**`${total_deposits:,.2f}`**")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"Error: {data.get('error', 'An unknown error occurred.')}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.", ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /bitso_summary: {e}")

@tree.command(name="bitso_chart", description="Generate and post a chart of Bitso income for a specific month.")
@app_commands.describe(month="The month to generate the report for (e.g., 'August' or 'August 2023')")
async def bitso_chart_command(interaction: discord.Interaction, month: str = None):
    """Handles the /bisto_chart slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        # 1. Determine the date
        if month:
            try:
                target_date = date_parse(month)
            except ValueError:
                await interaction.followup.send("Invalid month format. Please use a format like 'August' or 'August 2023'.", ephemeral=True)
                return
        else:
            target_date = datetime.datetime.now()

        year, month = target_date.year, target_date.month

        # 2. Fetch data
        all_fundings_data = []
        for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
            _, fundings = process_user_funding(user, api_key, api_secret, year, month)
            all_fundings_data.extend(fundings)

        if not all_fundings_data:
            await interaction.followup.send(f"No Bitso funding data found for {target_date.strftime('%B %Y')}.", ephemeral=True)
            return

        # 3. Generate chart
        chart_filename = f"bitso_income_{year}_{month}.png"
        generate_growth_chart(all_fundings_data, year, month, filename=chart_filename)

        if not os.path.exists(chart_filename):
            await interaction.followup.send("Could not generate the chart. Check the logs.", ephemeral=True)
            return

        # 4. Send chart to Discord
        with open(chart_filename, "rb") as f:
            discord_file = discord.File(f)
            await interaction.followup.send(file=discord_file, ephemeral=True)

        # 5. Clean up the generated file
        os.remove(chart_filename)

    except Exception as e:
        logger.error(f"Error in /bitso_chart command: {e}")
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

# --- Starting the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or "YOUR_SECRET_BOT_TOKEN_HERE" in DISCORD_BOT_TOKEN:
        logger.error("Discord Bot Token is not configured. Please set DISCORD_BOT_TOKEN in your config file.")
    else:
        client.run(DISCORD_BOT_TOKEN)# jinjernot/wg/wg-58e87644bc389c5c3f8f57d6d639116b58c265f7/discord_bot.py
import discord
from discord import app_commands
from discord.ext import tasks
import logging
import requests
import datetime
import os
from bitso_reports import generate_growth_chart, process_user_funding
import bitso_config
from dateutil.parser import parse as date_parse


from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_ACTIVE_TRADES_CHANNEL_ID
from config_messages.discord_messages import *

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- THIS IS NO LONGER STRICTLY NEEDED FOR COMMAND SYNCING BUT CAN BE KEPT FOR OTHER USES ---
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)
ACTIVE_TRADES_CHANNEL_ID = DISCORD_ACTIVE_TRADES_CHANNEL_ID


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

# --- Bot Events & Background Task ---
@client.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
    # --- CHANGED: Sync commands globally instead of to a specific guild ---
    await tree.sync()

    logger.info(f'Logged in as {client.user}. Bot is ready!')
    await client.change_presence(activity=discord.Game(name="/status for info"))

    if not post_live_trades.is_running():
        post_live_trades.start()

@tasks.loop(minutes=2)
async def post_live_trades():
    """A background task that re-uses the logic from /active_trades to post a summary."""
    channel = client.get_channel(ACTIVE_TRADES_CHANNEL_ID)
    if not channel:
        logger.error(f"Could not find channel {ACTIVE_TRADES_CHANNEL_ID}. Live feed is disabled.")
        return

    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        if response.status_code != 200:
            logger.error(f"Live feed update failed: Server responded with {response.status_code}")
            return

        trades = response.json()

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
                formatted_status = format_status_for_discord(status)

                embed.add_field(
                    name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                    value=f"**Amount**: {amount}\n**Status**:{formatted_status}",
                    inline=False
                )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Last updated")

        await channel.purge(limit=10, check=lambda m: m.author == client.user)
        await channel.send(embed=embed)

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Flask app for live trades task: {e}")

@post_live_trades.before_loop
async def before_post_live_trades():
    """Ensures the bot is ready before the task starts."""
    await client.wait_until_ready()


# --- Slash Commands ---
@tree.command(name="status", description="Check the status of the trading bot.")
async def status_command(interaction: discord.Interaction):
    """Handles the /status slash command."""
    await interaction.response.defer(ephemeral=True)

    embed_data = {}
    try:
        response = requests.get("http://127.0.0.1:5001/trading_status", timeout=5)
        if response.status_code == 200:
            status = response.json().get("status")
            if status == "Running":
                embed_data = STATUS_EMBED["running"]
            else:
                embed_data = STATUS_EMBED["stopped"]
        else:
            embed_data = STATUS_EMBED["error"].copy()
            embed_data["description"] = embed_data["description"].format(status_code=response.status_code)

    except requests.exceptions.RequestException as e:
        embed_data = STATUS_EMBED["unreachable"]
        logger.error(f"Could not connect to Flask app for status check: {e}")

    await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)


@tree.command(name="trades", description="Get a list of currently active trades.")
async def active_trades_command(interaction: discord.Interaction):
    """Handles the /trades slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        if response.status_code != 200:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.", ephemeral=True)
            return

        trades = response.json()

        if not trades:
            embed = discord.Embed.from_dict(NO_ACTIVE_TRADES_EMBED)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed_data = ACTIVE_TRADES_EMBED.copy()
        embed_data["title"] = embed_data["title"].format(trade_count=len(trades))
        embed = discord.Embed.from_dict(embed_data)

        for trade in trades[:10]:
            buyer = trade.get('responder_username', 'N/A')
            amount = f"{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}"
            payment_method = trade.get('payment_method_name', 'N/A')
            account_name = trade.get('account_name_source', 'N/A')
            status = trade.get('trade_status', 'N/A')
            formatted_status = format_status_for_discord(status)

            embed.add_field(
                name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                value=f"**Amount**: {amount}\n**Method**: {payment_method}\n**Account**: {account_name}\n**Status**:{formatted_status}",
                inline=False
            )

        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Live data")

        await interaction.followup.send(embed=embed, ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for active trades: {e}")


@tree.command(name="offers", description="Turn all trading offers on or off.")
@app_commands.describe(status="The desired status for your offers")
@app_commands.choices(status=[
    app_commands.Choice(name="On", value="on"),
    app_commands.Choice(name="Off", value="off"),
])
async def toggle_offers_command(interaction: discord.Interaction, status: app_commands.Choice[str]):
    """Handles the /offers command by calling the specific turn-on/off routes."""
    await interaction.response.defer(ephemeral=True)

    url = "http://127.0.0.1:5001/offer/toggle"
    is_enabled = True if status.value == "on" else False

    try:
        response = requests.post(url, json={"enabled": is_enabled}, timeout=15)

        if response.status_code == 200:
            data = response.json()
            embed_data = TOGGLE_OFFERS_EMBED["success"].copy()
            embed_data["title"] = embed_data["title"].format(status=status.name)
            embed_data["description"] = embed_data["description"].format(message=data.get("message", f"Offers are now {status.name}."))
            if status.value == 'off':
                embed_data['color'] = COLORS['error']

            embed = discord.Embed.from_dict(embed_data)
        else:
            embed_data = TOGGLE_OFFERS_EMBED["error"].copy()
            embed_data["description"] = embed_data["description"].format(status_code=response.status_code)
            embed = discord.Embed.from_dict(embed_data)

        await interaction.followup.send(embed=embed, ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /toggle_offers: {e}")

@tree.command(name="bot", description="Start or stop the trading bot process.")
@app_commands.describe(action="Choose whether to start or stop the bot")
@app_commands.choices(action=[
    app_commands.Choice(name="Start", value="start"),
    app_commands.Choice(name="Stop", value="stop"),
])
async def bot_command(interaction: discord.Interaction, action: app_commands.Choice[str]):
    """Handles starting and stopping the bot."""
    await interaction.response.defer(ephemeral=True)

    endpoint = "/start_trading" if action.value == "start" else "/stop_trading"
    url = f"http://127.0.0.1:5001{endpoint}"

    try:
        response = requests.post(url, timeout=10)
        data = response.json()

        if data.get("success"):
            if action.value == "start":
                embed_data = BOT_CONTROL_EMBEDS["start_success"].copy()
            else:
                embed_data = BOT_CONTROL_EMBEDS["stop_success"].copy()
            embed_data["description"] = embed_data["description"].format(message=data.get("message"))
        else:
            embed_data = BOT_CONTROL_EMBEDS["error"].copy()
            embed_data["title"] = embed_data["title"].format(action=action.name)
            embed_data["description"] = embed_data["description"].format(message=data.get("message", "An unknown error occurred."))

        await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /bot command: {e}")

@tree.command(name="settings", description="Change a bot setting.")
@app_commands.describe(
    setting="The setting you want to change",
    status="The new status for the setting"
)
@app_commands.choices(setting=[
    app_commands.Choice(name="Night Mode", value="night_mode_enabled"),
    app_commands.Choice(name="AFK Mode", value="afk_mode_enabled"),
    app_commands.Choice(name="Verbose Logging", value="verbose_logging_enabled"),
])
@app_commands.choices(status=[
    app_commands.Choice(name="On", value="true"),
    app_commands.Choice(name="Off", value="false"),
])
async def settings_command(interaction: discord.Interaction, setting: app_commands.Choice[str], status: app_commands.Choice[str]):
    """Handles changing application settings."""
    await interaction.response.defer(ephemeral=True)

    url = "http://127.0.0.1:5001/update_setting"
    is_enabled = True if status.value == "true" else False
    payload = {"key": setting.value, "enabled": is_enabled}

    try:
        response = requests.post(url, json=payload, timeout=10)
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

@tree.command(name="message", description="Send a manual message to a trade chat.")
@app_commands.describe(
    trade_hash="The hash of the trade",
    account_name="The account name handling the trade (e.g., Davidvs_Paxful)",
    message="The message you want to send"
)
async def send_message_command(interaction: discord.Interaction, trade_hash: str, account_name: str, message: str):
    """Handles sending a manual message to a trade."""
    await interaction.response.defer(ephemeral=True)

    url = "http://127.0.0.1:5001/send_manual_message"
    payload = {
        "trade_hash": trade_hash,
        "account_name": account_name,
        "message": message
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
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

@tree.command(name="user", description="Get the trading history for a specific user.")
@app_commands.describe(username="The username of the trader to look up.")
async def user_profile_command(interaction: discord.Interaction, username: str):
    """Handles the /user slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        url = f"http://127.0.0.1:5001/user_profile/{username}"
        response = requests.get(url, timeout=10)

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

            if stats.get("platforms"):
                platform_stats = []
                for platform, data in stats["platforms"].items():
                    platform_stats.append(f"**{platform.capitalize()}**: {data['trades']} trades (${data['volume']:.2f})")
                embed.add_field(name="Platform Activity", value="\n".join(platform_stats), inline=False)

            if stats.get("accounts"):
                account_stats = []
                for owner, count in stats["accounts"].items():
                    account_stats.append(f"**{owner.capitalize()}**: {count} trades")
                embed.add_field(name="Handled By", value="\n".join(account_stats), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)

        elif response.status_code == 404:
            embed_data = USER_NOT_FOUND_EMBED.copy()
            embed_data["description"] = embed_data["description"].format(username=username)
            embed = discord.Embed.from_dict(embed_data)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.", ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /user_profile: {e}")

@tree.command(name="bitso", description="Get a summary of Bitso deposits for the current month.")
async def bitso_summary_command(interaction: discord.Interaction):
    """Handles the /bitso slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        url = "http://127.0.0.1:5001/bitso_summary"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                deposits_by_sender = data.get("deposits_by_sender", [])
                total_deposits = data.get("total_deposits", 0.0)

                description_lines = [f"**{name}:** `${amount:,.2f}`" for name, amount in deposits_by_sender]
                description = "\n".join(description_lines)

                embed = discord.Embed(
                    title="💰 Bitso Deposits",
                    description=description,
                    color=discord.Color.green()
                )
                embed.add_field(name="Total", value=f"**`${total_deposits:,.2f}`**")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(f"Error: {data.get('error', 'An unknown error occurred.')}", ephemeral=True)
        else:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.", ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for /bitso_summary: {e}")

@tree.command(name="bitso_chart", description="Generate and post a chart of Bitso income for a specific month.")
@app_commands.describe(month="The month to generate the report for (e.g., 'August' or 'August 2023')")
async def bitso_chart_command(interaction: discord.Interaction, month: str = None):
    """Handles the /bisto_chart slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        # 1. Determine the date
        if month:
            try:
                target_date = date_parse(month)
            except ValueError:
                await interaction.followup.send("Invalid month format. Please use a format like 'August' or 'August 2023'.", ephemeral=True)
                return
        else:
            target_date = datetime.datetime.now()

        year, month = target_date.year, target_date.month

        # 2. Fetch data
        all_fundings_data = []
        for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
            _, fundings = process_user_funding(user, api_key, api_secret, year, month)
            all_fundings_data.extend(fundings)

        if not all_fundings_data:
            await interaction.followup.send(f"No Bitso funding data found for {target_date.strftime('%B %Y')}.", ephemeral=True)
            return

        # 3. Generate chart
        chart_filename = f"bitso_income_{year}_{month}.png"
        generate_growth_chart(all_fundings_data, year, month, filename=chart_filename)

        if not os.path.exists(chart_filename):
            await interaction.followup.send("Could not generate the chart. Check the logs.", ephemeral=True)
            return

        # 4. Send chart to Discord
        with open(chart_filename, "rb") as f:
            discord_file = discord.File(f)
            await interaction.followup.send(file=discord_file, ephemeral=True)

        # 5. Clean up the generated file
        os.remove(chart_filename)

    except Exception as e:
        logger.error(f"Error in /bitso_chart command: {e}")
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

# --- Starting the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or "YOUR_SECRET_BOT_TOKEN_HERE" in DISCORD_BOT_TOKEN:
        logger.error("Discord Bot Token is not configured. Please set DISCORD_BOT_TOKEN in your config file.")
    else:
        client.run(DISCORD_BOT_TOKEN)