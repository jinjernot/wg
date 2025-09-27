import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
from config import DISCORD_GUILD_ID
from config_messages.discord_messages import SERVER_UNREACHABLE

MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)


class ChartCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="charts", description="Generate and display charts for your trading activity.")
    async def charts_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            response = requests.post(
                "http://127.0.0.1:5001/generate_charts", timeout=60)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    chart_paths = data.get("charts", {})
                    files = [discord.File(
                        fp) for fp in chart_paths.values() if os.path.exists(fp)]
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


async def setup(bot: commands.Bot):
    await bot.add_cog(ChartCommands(bot))
