import discord
from discord import app_commands
from discord.ext import commands
import logging
from core.utils.customer_metrics import get_new_customers_this_month, get_customer_growth_metrics

logger = logging.getLogger(__name__)


class MetricsCommands(commands.Cog):
    """Commands for viewing business metrics"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="new_customers", description="Show new customers for the current month")
    async def new_customers(self, interaction: discord.Interaction):
        """Display new customers for the current month"""
        await interaction.response.defer()
        
        try:
            data = get_new_customers_this_month()
            
            embed = discord.Embed(
                title=f"📊 New Customers - {data['month']}",
                color=discord.Color.green(),
                description=f"**{data['count']}** new customers this month"
            )
            
            # Add summary info
            embed.add_field(
                name="💰 Total Volume",
                value=f"${data['total_volume']:,.2f} MXN",
                inline=True
            )
            
            # Add platform breakdown
            if data['platforms']:
                platform_text = "\n".join([
                    f"**{platform}**: {info['count']} customers, ${info['volume']:,.2f}"
                    for platform, info in data['platforms'].items()
                ])
                embed.add_field(
                    name="🌐 By Platform",
                    value=platform_text,
                    inline=True
                )
            
            # Add customer list (up to 10)
            if data['customers']:
                customers_to_show = data['customers'][:10]
                customer_list = []
                for customer in customers_to_show:
                    customer_list.append(
                        f"• **{customer['username']}** - {customer['trades_count']} trade(s), "
                        f"${customer['total_volume']:,.2f} ({customer['first_trade_date']})"
                    )
                
                embed.add_field(
                    name=f"👥 Recent Customers ({len(customers_to_show)} of {data['count']})",
                    value="\n".join(customer_list) if customer_list else "No customers yet",
                    inline=False
                )
                
                if data['count'] > 10:
                    embed.set_footer(text=f"Showing 10 of {data['count']} new customers")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in /new_customers command: {e}")
            await interaction.followup.send(
                f"❌ Error fetching new customers data: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="customer_growth", description="Show customer growth over the past 6 months")
    async def customer_growth(self, interaction: discord.Interaction):
        """Display customer growth trend"""
        await interaction.response.defer()
        
        try:
            data = get_customer_growth_metrics(months_back=6)
            
            if not data.get('monthly_data'):
                await interaction.followup.send("No customer growth data available.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📈 Customer Growth (Last 6 Months)",
                color=discord.Color.blue()
            )
            
            # Create a simple text chart
            monthly_data = data['monthly_data']
            max_customers = max(m['new_customers'] for m in monthly_data) if monthly_data else 1
            
            chart_lines = []
            for month_info in monthly_data:
                month = month_info['month']
                count = month_info['new_customers']
                
                # Simple bar chart using Unicode blocks
                bar_length = int((count / max_customers) * 20) if max_customers > 0 else 0
                bar = "█" * bar_length
                
                chart_lines.append(f"`{month}` {bar} **{count}**")
            
            embed.add_field(
                name="Monthly New Customers",
                value="\n".join(chart_lines) if chart_lines else "No data",
                inline=False
            )
            
            # Calculate total and average
            total = sum(m['new_customers'] for m in monthly_data)
            avg = total / len(monthly_data) if monthly_data else 0
            
            embed.add_field(
                name="📊 Summary",
                value=f"**Total**: {total} new customers\n**Average**: {avg:.1f} per month",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in /customer_growth command: {e}")
            await interaction.followup.send(
                f"❌ Error fetching customer growth data: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(MetricsCommands(bot))
