import discord
import requests
import logging
from discord import app_commands
from discord.ext import commands
from typing import Optional

from config import DISCORD_GUILD_ID
from config_messages.discord_messages import SERVER_UNREACHABLE

logger = logging.getLogger(__name__)
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)


class GiftCardCommands(commands.Cog):
    """Discord commands for gift card trade statistics and tracking."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="giftcards", description="Get statistics for all gift card trades")
    @app_commands.describe(
        days="Number of days to look back (e.g., 7, 30). Leave empty for all time."
    )
    async def giftcards_command(self, interaction: discord.Interaction, days: Optional[int] = None):
        """Display overall gift card trade statistics."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Build request parameters
            params = {}
            if days is not None:
                params['days'] = days
            
            # Request stats from Flask API
            response = requests.get(
                "http://127.0.0.1:5001/get_giftcard_stats",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success"):
                    stats = data.get("stats", {})
                    
                    # Create embed
                    date_range = stats.get("date_range", "All time")
                    embed = discord.Embed(
                        title=f"🎁 Gift Card Trade Statistics",
                        description=f"**Period:** {date_range}",
                        color=discord.Color.purple()
                    )
                    
                    # Overall stats
                    total_trades = stats.get("total_trades", 0)
                    total_volume = stats.get("total_volume", 0.0)
                    avg_trade = stats.get("average_trade_size", 0.0)
                    
                    embed.add_field(
                        name="📊 Overview",
                        value=f"**Total Trades:** {total_trades}\n**Total Volume:** ${total_volume:,.2f}\n**Average Trade:** ${avg_trade:,.2f}",
                        inline=False
                    )
                    
                    # Breakdown by card type
                    by_card = stats.get("by_card_type", {})
                    if by_card:
                        card_breakdown = []
                        for card_name, card_stats in sorted(by_card.items(), key=lambda x: x[1]["count"], reverse=True):
                            count = card_stats.get("count", 0)
                            volume = card_stats.get("volume", 0.0)
                            card_breakdown.append(f"**{card_name}:** {count} trades (${volume:,.2f})")
                        
                        embed.add_field(
                            name="💳 By Card Type",
                            value="\n".join(card_breakdown) if card_breakdown else "No data",
                            inline=False
                        )
                    
                    # Top buyers
                    top_buyers = stats.get("top_buyers", [])
                    if top_buyers:
                        buyers_list = []
                        for i, buyer in enumerate(top_buyers[:5], 1):
                            username = buyer.get("username", "Unknown")
                            count = buyer.get("trade_count", 0)
                            buyers_list.append(f"{i}. **{username}** - {count} trades")
                        
                        embed.add_field(
                            name="🏆 Top Buyers",
                            value="\n".join(buyers_list),
                            inline=False
                        )
                    
                    # Account breakdown
                    by_account = stats.get("by_account", {})
                    if by_account:
                        account_breakdown = []
                        for account, account_stats in sorted(by_account.items(), key=lambda x: x[1]["count"], reverse=True):
                            count = account_stats.get("count", 0)
                            volume = account_stats.get("volume", 0.0)
                            account_breakdown.append(f"**{account}:** {count} trades (${volume:,.2f})")
                        
                        embed.add_field(
                            name="👤 By Account",
                            value="\n".join(account_breakdown[:5]) if account_breakdown else "No data",
                            inline=False
                        )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    error_msg = data.get("error", "Unknown error occurred")
                    await interaction.followup.send(f"❌ Error: {error_msg}", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Server error: HTTP {response.status_code}",
                    ephemeral=True
                )
        
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in giftcards command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An unexpected error occurred: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.guilds(MY_GUILD)
    @app_commands.command(name="giftcard", description="Get statistics for a specific gift card type")
    @app_commands.describe(
        card_type="Type of gift card (amazon, uber, uber-eats, google-play)"
    )
    @app_commands.choices(card_type=[
        app_commands.Choice(name="Amazon Gift Card", value="amazon-gift-card"),
        app_commands.Choice(name="Uber Gift Card", value="uber-gift-card"),
        app_commands.Choice(name="Uber Eats", value="uber-eats"),
        app_commands.Choice(name="Google Play Gift Card", value="google-play-gift-card")
    ])
    async def giftcard_command(self, interaction: discord.Interaction, card_type: str):
        """Display statistics for a specific gift card type."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Request specific card type stats
            response = requests.get(
                "http://127.0.0.1:5001/get_giftcard_trades",
                params={"card_type": card_type},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success"):
                    trades = data.get("trades", [])
                    
                    if not trades:
                        await interaction.followup.send(
                            f"ℹ️ No trades found for **{card_type.replace('-', ' ').title()}**",
                            ephemeral=True
                        )
                        return
                    
                    # Calculate stats for this card type
                    total_volume = sum(t.get("fiat_amount_requested", 0) for t in trades if t.get("status") == "successful")
                    successful_trades = [t for t in trades if t.get("status") == "successful"]
                    avg_trade = total_volume / len(successful_trades) if successful_trades else 0
                    
                    # Get top buyers
                    buyer_counts = {}
                    for trade in successful_trades:
                        buyer = trade.get("buyer")
                        if buyer:
                            buyer_counts[buyer] = buyer_counts.get(buyer, 0) + 1
                    
                    top_buyers = sorted(buyer_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    # Create embed
                    card_name = card_type.replace("-", " ").title()
                    embed = discord.Embed(
                        title=f"🎁 {card_name} Statistics",
                        color=discord.Color.gold()
                    )
                    
                    embed.add_field(
                        name="📊 Overview",
                        value=f"**Total Trades:** {len(successful_trades)}\n**Total Volume:** ${total_volume:,.2f}\n**Average Trade:** ${avg_trade:,.2f}",
                        inline=False
                    )
                    
                    if top_buyers:
                        buyers_list = []
                        for i, (buyer, count) in enumerate(top_buyers, 1):
                            buyers_list.append(f"{i}. **{buyer}** - {count} trades")
                        
                        embed.add_field(
                            name="🏆 Top Buyers",
                            value="\n".join(buyers_list),
                            inline=False
                        )
                    
                    # Recent trades
                    recent = sorted(successful_trades, key=lambda x: x.get("completed_at", ""), reverse=True)[:3]
                    if recent:
                        recent_list = []
                        for trade in recent:
                            buyer = trade.get("buyer", "Unknown")
                            amount = trade.get("fiat_amount_requested", 0)
                            date = trade.get("completed_at", "Unknown")
                            recent_list.append(f"**{buyer}** - ${amount:,.2f} ({date[:10]})")
                        
                        embed.add_field(
                            name="🕐 Recent Trades",
                            value="\n".join(recent_list),
                            inline=False
                        )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    error_msg = data.get("error", "Unknown error occurred")
                    await interaction.followup.send(f"❌ Error: {error_msg}", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Server error: HTTP {response.status_code}",
                    ephemeral=True
                )
        
        except requests.exceptions.RequestException:
            await interaction.followup.send(SERVER_UNREACHABLE, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in giftcard command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An unexpected error occurred: {str(e)}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Load the GiftCardCommands cog."""
    await bot.add_cog(GiftCardCommands(bot))
