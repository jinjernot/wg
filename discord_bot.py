import discord
from discord import app_commands
from discord.ext import tasks
import logging
import requests
import datetime
# --- UPDATED IMPORT ---
from config import DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_ACTIVE_TRADES_CHANNEL_ID

# --- Basic Setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Now loaded from config.py) ---
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID) 
ACTIVE_TRADES_CHANNEL_ID = DISCORD_ACTIVE_TRADES_CHANNEL_ID


# --- Bot Events & Background Task ---
@client.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
    tree.copy_global_to(guild=MY_GUILD)
    await tree.sync(guild=MY_GUILD)
    
    logger.info(f'Logged in as {client.user}. Bot is ready!')
    await client.change_presence(activity=discord.Game(name="/status for info"))
    
    # Start the background task
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
        
        # --- This logic is copied directly from your /active_trades command ---
        if not trades:
            embed = discord.Embed(
                title="📊 Live Active Trades",
                description="No active trades found at the moment.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title=f"📊 Live Active Trades ({len(trades)})",
                description="This list updates automatically.",
                color=0x0000ff
            )
            for trade in trades[:20]: # Limit to 20 to avoid Discord limits
                buyer = trade.get('responder_username', 'N/A')
                amount = f"{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}"
                status = trade.get('trade_status', 'N/A')
                
                embed.add_field(
                    name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                    value=f"**Amount**: {amount}\n**Status**: `{status}`",
                    inline=False
                )
        
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        embed.set_footer(text="Last updated")
        
        # Clean the channel and post the new message
        await channel.purge(limit=10, check=lambda m: m.author == client.user)
        await channel.send(embed=embed)

    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Flask app for live trades task: {e}")

@post_live_trades.before_loop
async def before_post_live_trades():
    """Ensures the bot is ready before the task starts."""
    await client.wait_until_ready()


# --- Slash Commands ---
# ... (all your other slash commands like /status, /bot, etc., remain here unchanged) ...

@tree.command(name="status", description="Check the status of the trading bot.")
async def status_command(interaction: discord.Interaction):
    """Handles the /status slash command."""
    await interaction.response.defer(ephemeral=True)
    
    status_text = "Unknown"
    color = 0x808080
    
    try:
        response = requests.get("http://127.0.0.1:5001/trading_status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "Running":
                status_text = "✅ Trading process is **Running**."
                color = 0x00ff00
            else:
                status_text = "❌ Trading process is **Stopped**."
                color = 0xff0000
        else:
            status_text = f"⚠️ Could not get status. The web server responded with: {response.status_code}"
            color = 0xffa500

    except requests.exceptions.RequestException as e:
        status_text = "⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running."
        color = 0xffa500
        logger.error(f"Could not connect to Flask app for status check: {e}")

    embed = discord.Embed(title="Bot Status", description=status_text, color=color)
    await interaction.followup.send(embed=embed)


@tree.command(name="active_trades", description="Get a list of currently active trades.")
async def active_trades_command(interaction: discord.Interaction):
    """Handles the /active_trades slash command."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        response = requests.get("http://127.0.0.1:5001/get_active_trades", timeout=10)
        if response.status_code != 200:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.")
            return
            
        trades = response.json()
        
        if not trades:
            embed = discord.Embed(title="Active Trades", description="No active trades found.", color=0x00ff00)
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(title=f"📊 Active Trades ({len(trades)})", color=0x0000ff)
        for trade in trades[:10]: # Limit to 10 trades to avoid hitting Discord limits
            buyer = trade.get('responder_username', 'N/A')
            amount = f"{trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', '')}"
            payment_method = trade.get('payment_method_name', 'N/A')
            account_name = trade.get('account_name_source', 'N/A')
            
            embed.add_field(
                name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                value=f"**Amount**: {amount}\n**Method**: {payment_method}\n**Account**: {account_name}",
                inline=False
            )
            
        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send("⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running.")
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

    endpoint = "/offer/toggle"
    url = f"http://127.0.0.1:5001{endpoint}"
    is_enabled = True if status.value == "on" else False
    
    try:
        response = requests.post(url, json={"enabled": is_enabled}, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            message = data.get("message", f"Offers are now {status.name}.")
            color = 0x00ff00 if status.value == "on" else 0xff0000
            embed = discord.Embed(title=f"✅ Offers Toggled {status.name}", description=message, color=color)
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title="❌ Error Toggling Offers", description=f"The server responded with: {response.status_code}", color=0xffa500)
            await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send("⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running.")
        logger.error(f"Could not connect to Flask app for /toggle_offers: {e}")


@tree.command(name="summary", description="Get a summary of today's trading activity.")
async def summary_command(interaction: discord.Interaction):
    """Handles the /summary slash command."""
    await interaction.response.defer(ephemeral=True)

    try:
        response = requests.get("http://127.0.0.1:5001/get_summary", timeout=10)
        if response.status_code != 200:
            await interaction.followup.send(f"Error: The web server responded with status code {response.status_code}.")
            return
            
        stats = response.json()
        
        embed = discord.Embed(title=f"📊 Daily Summary for {datetime.date.today().isoformat()}", color=0x3498DB)
        embed.add_field(name="Total Trades Today", value=f"**{stats['total_trades']}**", inline=True)
        embed.add_field(name="Total Volume", value=f"**${stats['total_volume']:.2f}**", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=False) # Divider
        embed.add_field(name="✅ Successful", value=f"**{stats['successful_trades']}**", inline=True)
        embed.add_field(name="💰 Paid (Pending BTC)", value=f"**{stats['paid_trades']}**", inline=True)
        embed.add_field(name="🏃 Active", value=f"**{stats['active_trades']}**", inline=True)

        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send("⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running.")
        logger.error(f"Could not connect to Flask app for /summary: {e}")




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
            color = 0x00ff00 if action.value == "start" else 0xff0000
            embed = discord.Embed(
                title=f"Bot {action.name}ed Successfully",
                description=data.get("message"),
                color=color
            )
        else:
            embed = discord.Embed(
                title=f"Error {action.name}ing Bot",
                description=data.get("message", "An unknown error occurred."),
                color=0xffa500
            )
        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send("⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running.")
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
            embed = discord.Embed(
                title="⚙️ Setting Updated",
                description=f"**{setting.name}** has been turned **{status.name}**.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="❌ Error Updating Setting",
                description=data.get("error", "An unknown server error occurred."),
                color=0xff0000
            )
        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException:
        await interaction.followup.send("⚠️ **Web server is unreachable.**")

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
            embed = discord.Embed(
                title="✉️ Message Sent",
                description=f"Successfully sent message to `{trade_hash}`.",
                color=0x3498DB
            )
            embed.add_field(name="Message", value=message)
        else:
            embed = discord.Embed(
                title="❌ Failed to Send Message",
                description=data.get("error", "An unknown error occurred."),
                color=0xff0000
            )
        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException:
        await interaction.followup.send("⚠️ **Web server is unreachable.**")



# --- Starting the Bot ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or "YOUR_SECRET_BOT_TOKEN_HERE" in DISCORD_BOT_TOKEN:
        logger.error("Discord Bot Token is not configured. Please set DISCORD_BOT_TOKEN in your config file.")
    else:
        client.run(DISCORD_BOT_TOKEN)