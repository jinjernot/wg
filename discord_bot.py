import discord
from discord import app_commands
from discord.ext import tasks
import logging
import requests
import datetime

from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_ACTIVE_TRADES_CHANNEL_ID
from config_messages.discord_messages import *

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    tree.copy_global_to(guild=MY_GUILD)
    await tree.sync(guild=MY_GUILD)

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


@tree.command(name="active_trades", description="Get a list of currently active trades.")
async def active_trades_command(interaction: discord.Interaction):
    """Handles the /active_trades slash command."""
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
        
        # --- THIS SECTION IS CORRECTED ---
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Live data")
        # --- END OF CORRECTION ---

        await interaction.followup.send(embed=embed, ephemeral=True)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        logger.error(f"Could not connect to Flask app for active trades: {e}")


@tree.command(name="toggle_offers", description="Turn all trading offers on or off.")
@app_commands.describe(status="The desired status for your offers")
@app_commands.choices(status=[
    app_commands.Choice(name="On", value="on"),
    app_commands.Choice(name="Off", value="off"),
])
async def toggle_offers_command(interaction: discord.Interaction, status: app_commands.Choice[str]):
    """Handles the /toggle_offers command by calling the specific turn-on/off routes."""
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

@tree.command(name="send_message", description="Send a manual message to a trade chat.")
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

# --- Starting the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or "YOUR_SECRET_BOT_TOKEN_HERE" in DISCORD_BOT_TOKEN:
        logger.error("Discord Bot Token is not configured. Please set DISCORD_BOT_TOKEN in your config file.")
    else:
        client.run(DISCORD_BOT_TOKEN)