import discord
from discord import app_commands
from discord.ext import commands
import requests
import json
import os
from config import DISCORD_GUILD_ID
from config_messages.discord_messages import TOGGLE_OFFERS_EMBED, COLORS, SERVER_UNREACHABLE

MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)


class OfferCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="search_offers", description="Search public offers on Noones for buyers or sellers.")
    @app_commands.describe(
        payment_method="The payment method slug (e.g., bank-transfer)",
        crypto="The crypto code (e.g., BTC)",
        fiat="The fiat code (e.g., MXN)",
        trade_direction="Whether to search for 'buy' or 'sell' offers"
    )
    @app_commands.choices(trade_direction=[
        app_commands.Choice(name="Sellers (Competitors)", value="sell"),
        app_commands.Choice(name="Buyers (Customers)", value="buy")
    ])
    async def search_offers_command(self, interaction: discord.Interaction, payment_method: str, crypto: str, fiat: str, trade_direction: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        
        fiat_to_country = {"MXN": "MX"}
        country = fiat_to_country.get(fiat.upper(), fiat.upper()[:2])

        payload = {
            "crypto_code": crypto,
            "fiat_code": fiat,
            "payment_method": payment_method,
            "trade_direction": trade_direction.value,
            # --- Send the payment method country filter ---
            "payment_method_country_iso": country,
            # --- ADDED FIAT COUNTRY FILTER ---
            "country_code": country
        }
        
        json_filename = f"{crypto.lower()}_{fiat.lower()}_{payment_method}_search.json"
        
        try:
            response = requests.post("http://127.0.0.1:5001/offer/search", json=payload, timeout=20)
            data = response.json()

            if not data.get("success"):
                await interaction.followup.send(f"Error: {data.get('error', 'Unknown server error.')}", ephemeral=True)
                return

            # --- MODIFIED: Get full data and attach as file ---
            full_data = data.get("data", {})
            
            # --- FIX FOR INCONSISTENT API RESPONSE ---
            offers = []
            if isinstance(full_data, dict):
                offers = full_data.get("offers", [])
            elif isinstance(full_data, list):
                offers = full_data  # The data *is* the list of offers
            # --- END FIX ---
            
            try:
                with open(json_filename, "w", encoding="utf-8") as f:
                    # Dump full_data, which will be either the list or dict
                    json.dump(full_data, f, indent=4) 
                json_file = discord.File(json_filename, filename=f"full_response_{json_filename}")
            except Exception as e:
                await interaction.followup.send(f"Could not create results file: {e}", ephemeral=True)
                return
            # --- END MODIFICATION ---

            if not offers:
                await interaction.followup.send("No public offers found for this market. See attached file for full API response.", file=json_file, ephemeral=True)
                os.remove(json_filename)
                return

            embed_title_prefix = "Top 5 Competitors" if trade_direction.value == "sell" else "Top 5 Buyers"
            embed = discord.Embed(
                title=f"{embed_title_prefix} for {crypto.upper()}/{fiat.upper()} ({payment_method})",
                description="See attached file for the full, raw API response.",
                color=COLORS["info"]
            )
            
            for offer in offers[:5]:
                username = offer.get('offer_owner_username', 'N/A')
                total_trades = offer.get('total_successful_trades', 0)
                reputation = (
                    f"+{offer.get('offer_owner_feedback_positive', 0)} / "
                    f"-{offer.get('offer_owner_feedback_negative', 0)}"
                )
                last_seen = offer.get('last_seen_string', 'N/A')

                field_value = (
                    f"**User:** {username} ({reputation})\n"
                    f"**Trades:** {total_trades}\n"
                    f"**Status:** {last_seen}\n"
                    f"**Range:** {offer.get('fiat_amount_range_min')} - {offer.get('fiat_amount_range_max')} {fiat.upper()}\n"
                    f"**Margin:** `{offer.get('margin')}%`"
                )
                
                embed.add_field(
                    name=f"@{username}",
                    value=field_value,
                    inline=False
                )
            
            # --- MODIFIED: Send embed and file ---
            await interaction.followup.send(embed=embed, file=json_file, ephemeral=True)
            os.remove(json_filename)

        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        except Exception as e: # <--- THIS IS THE CATCH BLOCK
            await interaction.followup.send(f"An unexpected error occurred: {e}", ephemeral=True) # <--- THIS IS THE ERROR MESSAGE
            if os.path.exists(json_filename):
                os.remove(json_filename)


    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="offers", description="Turn all trading offers on or off.")
    @app_commands.describe(status="The desired status for your offers")
    @app_commands.choices(status=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ])
    async def toggle_offers_command(self, interaction: discord.Interaction, status: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        is_enabled = status.value == "on"
        try:
            response = requests.post(
                "http://127.0.0.1:5001/offer/toggle", json={"enabled": is_enabled}, timeout=15)
            data = response.json()
            if response.status_code == 200 and data.get("success"):
                embed_data = TOGGLE_OFFERS_EMBED["success"].copy()
                embed_data["title"] = embed_data["title"].format(
                    status=status.name)
                embed_data["description"] = data.get(
                    "message", f"Offers are now {status.name}.")
                if not is_enabled:
                    embed_data['color'] = COLORS['error']
            else:
                embed_data = TOGGLE_OFFERS_EMBED["error"].copy()
                embed_data["description"] = data.get(
                    "error", "Unknown server error.")
            await interaction.followup.send(embed=discord.Embed.from_dict(embed_data), ephemeral=True)
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="list_offers", description="Lists all of your active offers.")
    async def list_offers_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            response = requests.get(
                "http://127.0.0.1:5001/get_offers", timeout=15)
            offers = response.json() if response.status_code == 200 else []
            if not offers:
                await interaction.followup.send("You have no active offers.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"Your Active Offers ({len(offers)})", color=COLORS["info"])
            for offer in offers[:20]:
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

    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="toggle_offer", description="Turn a specific offer on or off.")
    @app_commands.describe(offer_hash="The hash of the offer to toggle", account_name="The account that owns the offer (e.g., David_Noones)", status="The desired status")
    @app_commands.choices(status=[app_commands.Choice(name="On", value="on"), app_commands.Choice(name="Off", value="off")])
    async def toggle_offer_command(self, interaction: discord.Interaction, offer_hash: str, account_name: str, status: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        is_enabled = status.value == "on"
        payload = {"offer_hash": offer_hash,
                   "account_name": account_name, "enabled": is_enabled}
        try:
            response = requests.post(
                "http://127.0.0.1:5001/offer/toggle_single", json=payload, timeout=15)
            data = response.json()
            if response.status_code == 200 and data.get("success"):
                embed = discord.Embed(title=f"✅ Offer Status Updated",
                                      description=f"Successfully turned **{status.name}** the offer `{offer_hash}`.", color=COLORS["success"] if is_enabled else COLORS["error"])
            else:
                embed = discord.Embed(title=f"❌ Error Updating Offer",
                                      description=f"Failed to update offer `{offer_hash}`.\n**Reason**: {data.get('error', 'Unknown error.')}", color=COLORS["error"])
            await interaction.followup.send(embed=embed, ephemeral=True)
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(OfferCommands(bot))