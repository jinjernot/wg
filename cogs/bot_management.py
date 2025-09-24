import discord
from discord import app_commands
from discord.ext import commands
import requests
import logging
from config import DISCORD_GUILD_ID
from config_messages.discord_messages import STATUS_EMBED, BOT_CONTROL_EMBEDS, SETTINGS_EMBEDS, SERVER_UNREACHABLE, COLORS
from core.api.wallet import get_wallet_balances

logger = logging.getLogger(__name__)
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

class BotManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Check the status of the trading bot.")
    async def status_command(self, interaction: discord.Interaction):
        """Handles the /status slash command."""
        await interaction.response.defer(ephemeral=True)
        embed_data = {}
        try:
            response = requests.get("http://127.0.0.1:5001/trading_status", timeout=5)
            if response.status_code == 200:
                status = response.json().get("status")
                embed_data = STATUS_EMBED["running"] if status == "Running" else STATUS_EMBED["stopped"]
            else:
                embed_data = STATUS_EMBED["error"].copy()
                embed_data["description"] = embed_data["description"].format(status_code=response.status_code)
        except requests.exceptions.RequestException:
            embed_data = STATUS_EMBED["unreachable"]
        await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)

    @app_commands.command(name="bot", description="Start or stop the trading bot process.")
    @app_commands.describe(action="Choose whether to start or stop the bot")
    @app_commands.choices(action=[
        app_commands.Choice(name="Start", value="start"),
        app_commands.Choice(name="Stop", value="stop"),
    ])
    async def control_bot_command(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        """Handles starting and stopping the bot."""
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

    @app_commands.command(name="settings", description="Change a bot setting.")
    @app_commands.describe(setting="The setting you want to change", status="The new status for the setting")
    @app_commands.choices(setting=[
        app_commands.Choice(name="Night Mode", value="night_mode_enabled"),
        app_commands.Choice(name="AFK Mode", value="afk_mode_enabled"),
        app_commands.Choice(name="Verbose Logging", value="verbose_logging_enabled"),
    ], status=[
        app_commands.Choice(name="On", value="true"),
        app_commands.Choice(name="Off", value="false"),
    ])
    async def settings_command(self, interaction: discord.Interaction, setting: app_commands.Choice[str], status: app_commands.Choice[str]):
        """Handles changing application settings."""
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

    # --- THIS FUNCTION MUST BE INDENTED TO BE PART OF THE CLASS ---
    @app_commands.command(name="balance", description="Check the wallet balances of all accounts.")
    async def balance_command(self, interaction: discord.Interaction):
        """Fetches and displays wallet balances."""
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


async def setup(bot: commands.Bot):
    await bot.add_cog(BotManagement(bot))