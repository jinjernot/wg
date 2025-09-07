import discord
from discord import app_commands
import logging
import requests
from config import DISCORD_BOT_TOKEN

# --- Basic Setup ---
# We define the intents (permissions) our bot needs.
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Configure logging for the bot
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Bot Events ---
@client.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
    await tree.sync() # Sync the slash commands with Discord
    logger.info(f'Logged in as {client.user}. Bot is ready!')
    # Set a custom status
    await client.change_presence(activity=discord.Game(name="/status for info"))


# --- Slash Commands ---
@tree.command(name="status", description="Check the status of the trading bot.")
async def status_command(interaction: discord.Interaction):
    """Handles the /status slash command."""
    await interaction.response.defer(ephemeral=True) # Acknowledge the command privately
    
    status_text = "Unknown"
    color = 0x808080 # Grey
    
    try:
        # The bot communicates with the Flask app to get the trading process status
        response = requests.get("http://127.0.0.1:5001/trading_status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "Running":
                status_text = "✅ Trading process is **Running**."
                color = 0x00ff00 # Green
            else:
                status_text = "❌ Trading process is **Stopped**."
                color = 0xff0000 # Red
        else:
            status_text = f"⚠️ Could not get status. The web server responded with: {response.status_code}"
            color = 0xffa500 # Orange

    except requests.exceptions.RequestException as e:
        status_text = "⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running."
        color = 0xffa500 # Orange
        logger.error(f"Could not connect to Flask app for status check: {e}")

    # Create and send a formatted embed response
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
            
            embed.add_field(
                name=f"Trade `{trade.get('trade_hash', 'N/A')}` with {buyer}",
                value=f"**Amount**: {amount}\n**Method**: {payment_method}",
                inline=False
            )
            
        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send("⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running.")
        logger.error(f"Could not connect to Flask app for active trades: {e}")


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or "YOUR_SECRET_BOT_TOKEN_HERE" in DISCORD_BOT_TOKEN:
        logger.error("Discord Bot Token is not configured. Please set DISCORD_BOT_TOKEN in your config file.")
    else:
        client.run(DISCORD_BOT_TOKEN)