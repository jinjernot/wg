import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime
from typing import Optional

from bot.utils.payment_database import PaymentDatabase

logger = logging.getLogger(__name__)

class PaymentTracker(commands.Cog):
    """Cog for tracking customer payments in MXN."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PaymentDatabase()
    
    async def cog_load(self):
        """Initialize the database when the cog loads."""
        await self.db.initialize()
        logger.info("Payment Tracker cog loaded successfully")
    
    def format_mxn(self, amount: float) -> str:
        """Format an amount as MXN currency."""
        return f"${amount:,.2f} MXN"
    
    def format_datetime(self, dt_str: str) -> str:
        """Format a datetime string for display."""
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%Y-%m-%d %I:%M %p")
        except:
            return dt_str
    
    @app_commands.command(name="record-payment", description="Record a customer payment")
    @app_commands.describe(
        customer="Customer name",
        amount="Payment amount in MXN",
        note="Optional note about the payment"
    )
    async def record_payment(
        self, 
        interaction: discord.Interaction,
        customer: str,
        amount: float,
        note: Optional[str] = None
    ):
        """Record a new customer payment."""
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Payment amount must be greater than 0.",
                ephemeral=True
            )
            return
        
        # Defer response as database operation may take time
        await interaction.response.defer()
        
        try:
            # Record the payment
            payment_id = await self.db.record_payment(
                customer_name=customer,
                amount=amount,
                recorded_by=str(interaction.user),
                note=note
            )
            
            # Create success embed
            embed = discord.Embed(
                title="💰 Payment Recorded",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Customer", value=customer, inline=True)
            embed.add_field(name="Amount", value=self.format_mxn(amount), inline=True)
            embed.add_field(name="Payment ID", value=f"#{payment_id}", inline=True)
            if note:
                embed.add_field(name="Note", value=note, inline=False)
            embed.set_footer(text=f"Recorded by {interaction.user}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error recording payment: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while recording the payment. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="payment-history", description="View payment history for a customer")
    @app_commands.describe(customer="Customer name")
    async def payment_history(
        self, 
        interaction: discord.Interaction,
        customer: str
    ):
        """View all payments for a specific customer."""
        await interaction.response.defer()
        
        try:
            # Get payment history
            payments = await self.db.get_customer_history(customer)
            
            if not payments:
                await interaction.followup.send(
                    f"📭 No payment records found for **{customer}**.",
                    ephemeral=True
                )
                return
            
            # Calculate total
            total = sum(p['amount'] for p in payments)
            
            # Create embed
            embed = discord.Embed(
                title=f"📊 Payment History: {customer}",
                description=f"Total: **{self.format_mxn(total)}** ({len(payments)} transactions)",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Add up to 10 most recent payments
            for payment in payments[:10]:
                date = self.format_datetime(payment['date_recorded'])
                amount = self.format_mxn(payment['amount'])
                note_text = f"\n📝 {payment['note']}" if payment['note'] else ""
                recorded_by = payment['recorded_by']
                
                embed.add_field(
                    name=f"#{payment['id']} - {date}",
                    value=f"💵 {amount}\n👤 {recorded_by}{note_text}",
                    inline=False
                )
            
            if len(payments) > 10:
                embed.set_footer(text=f"Showing 10 most recent of {len(payments)} total transactions")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching payment history: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while fetching payment history.",
                ephemeral=True
            )
    
    @app_commands.command(name="payment-total", description="View total amount paid by a customer")
    @app_commands.describe(customer="Customer name")
    async def payment_total(
        self, 
        interaction: discord.Interaction,
        customer: str
    ):
        """View the total amount paid by a specific customer."""
        await interaction.response.defer()
        
        try:
            # Get total
            total = await self.db.get_customer_total(customer)
            history = await self.db.get_customer_history(customer)
            
            # Create embed
            embed = discord.Embed(
                title=f"💰 Total for {customer}",
                description=f"**{self.format_mxn(total)}**",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Transactions", value=str(len(history)), inline=True)
            
            if history:
                last_payment = history[0]
                last_date = self.format_datetime(last_payment['date_recorded'])
                embed.add_field(name="Last Payment", value=last_date, inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching payment total: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while fetching the total.",
                ephemeral=True
            )
    
    @app_commands.command(name="all-payments", description="View all payment records")
    async def all_payments(self, interaction: discord.Interaction):
        """View all payment records across all customers."""
        await interaction.response.defer()
        
        try:
            # Get all payments
            payments = await self.db.get_all_payments()
            
            if not payments:
                await interaction.followup.send(
                    "📭 No payment records found.",
                    ephemeral=True
                )
                return
            
            # Calculate total
            total = sum(p['amount'] for p in payments)
            
            # Create embed
            embed = discord.Embed(
                title="📋 All Payment Records",
                description=f"Grand Total: **{self.format_mxn(total)}** ({len(payments)} transactions)",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            
            # Add up to 15 most recent payments
            for payment in payments[:15]:
                date = self.format_datetime(payment['date_recorded'])
                amount = self.format_mxn(payment['amount'])
                customer = payment['customer_name']
                note_text = f"\n📝 {payment['note']}" if payment['note'] else ""
                recorded_by = payment['recorded_by']
                
                embed.add_field(
                    name=f"#{payment['id']} - {customer} - {date}",
                    value=f"💵 {amount}\n👤 {recorded_by}{note_text}",
                    inline=False
                )
            
            if len(payments) > 15:
                embed.set_footer(text=f"Showing 15 most recent of {len(payments)} total transactions")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching all payments: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while fetching payment records.",
                ephemeral=True
            )
    
    @app_commands.command(name="payment-stats", description="View payment statistics")
    async def payment_stats(self, interaction: discord.Interaction):
        """View summary statistics across all payments."""
        await interaction.response.defer()
        
        try:
            # Get statistics
            stats = await self.db.get_statistics()
            overall = stats['overall']
            per_customer = stats['per_customer']
            
            if overall['total_transactions'] == 0:
                await interaction.followup.send(
                    "📭 No payment records found.",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="📊 Payment Statistics",
                color=discord.Color.teal(),
                timestamp=datetime.now()
            )
            
            # Overall stats
            embed.add_field(
                name="📈 Overall",
                value=(
                    f"**Total Revenue:** {self.format_mxn(overall['total_amount'] or 0)}\n"
                    f"**Transactions:** {overall['total_transactions']}\n"
                    f"**Customers:** {overall['total_customers']}"
                ),
                inline=False
            )
            
            # Per customer breakdown
            if per_customer:
                customer_text = ""
                for idx, customer in enumerate(per_customer, 1):
                    customer_text += (
                        f"**{idx}. {customer['customer_name']}**\n"
                        f"   {self.format_mxn(customer['total_amount'])} "
                        f"({customer['transaction_count']} transactions)\n"
                    )
                
                embed.add_field(
                    name="👥 By Customer",
                    value=customer_text,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching payment stats: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while fetching statistics.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(PaymentTracker(bot))
