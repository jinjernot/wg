import bitso_config
import requests
import datetime
import discord
import os

from core.bitso.bitso_reports import generate_growth_chart, process_user_funding
from dateutil.parser import parse as date_parse
from discord import app_commands
from discord.ext import commands

from config_messages.discord_messages import SERVER_UNREACHABLE
from config import DISCORD_GUILD_ID
from config import REPORTS_DIR

#MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

class BitsoCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="bitso", description="Get a summary of Bitso deposits for a specific month.")
    @app_commands.describe(month="The month to get the summary for (e.g., 'August' or 'August 2023'). Defaults to the current month.")
    async def bitso_summary_command(self, interaction: discord.Interaction, month: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            params = {}
            if month:
                params['month'] = month
            response = requests.get(
                "http://127.0.0.1:5001/bitso_summary", params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    deposits = data.get("deposits_by_sender", [])
                    total = data.get("total_deposits", 0.0)
                    month_str = data.get("month_str", "Current Month")
                    description = "\n".join(
                        [f"**{name}:** `${amount:,.2f}`" for name, amount in deposits])
                    embed = discord.Embed(
                        title=f"💰 Bitso Deposits for {month_str}", description=description, color=discord.Color.green())
                    embed.add_field(name="Total", value=f"**`${total:,.2f}`**")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(f"Error: {data.get('error', 'Unknown error.')}", ephemeral=True)
            else:
                await interaction.followup.send(f"Error: Server responded with {response.status_code}.", ephemeral=True)
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

    @app_commands.command(name="bitso_chart", description="Generate a chart of Bitso income for a specific month.")
    @app_commands.describe(month="The month to generate the report for (e.g., 'August' or 'August 2023')")
    async def bitso_chart_command(self, interaction: discord.Interaction, month: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            target_date = date_parse(
                month) if month else datetime.datetime.now()
            year, month_num = target_date.year, target_date.month

            all_fundings = []
            for user, (key, secret) in bitso_config.API_KEYS.items():
                _, fundings = process_user_funding(
                    user, key, secret, year, month_num)
                all_fundings.extend(fundings)

            if not all_fundings:
                await interaction.followup.send(f"No Bitso funding data found for {target_date.strftime('%B %Y')}.", ephemeral=True)
                return

            chart_filename = f"bitso_income_{year}_{month_num}.png"
            chart_filepath = os.path.join(REPORTS_DIR, chart_filename)

            generate_growth_chart(all_fundings, year,
                                  month_num, filename=chart_filename)

            if os.path.exists(chart_filepath):
                await interaction.followup.send(file=discord.File(chart_filepath), ephemeral=True)
                os.remove(chart_filepath)
            else:
                await interaction.followup.send("Could not generate the chart.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BitsoCommands(bot))