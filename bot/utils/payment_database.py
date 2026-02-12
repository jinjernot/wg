import aiosqlite
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class PaymentDatabase:
    def __init__(self, db_path: str = "data/customer_payments.db"):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize the database and create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS customer_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    note TEXT,
                    recorded_by TEXT NOT NULL,
                    date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info(f"Payment database initialized at {self.db_path}")
    
    async def record_payment(
        self, 
        customer_name: str, 
        amount: float, 
        recorded_by: str,
        note: Optional[str] = None
    ) -> int:
        """
        Record a new payment.
        
        Args:
            customer_name: Name of the customer
            amount: Payment amount in MXN
            recorded_by: Discord username who recorded the payment
            note: Optional note about the payment
            
        Returns:
            The ID of the newly created payment record
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO customer_payments (customer_name, amount, note, recorded_by, date_recorded)
                VALUES (?, ?, ?, ?, ?)
                """,
                (customer_name, amount, note, recorded_by, datetime.now())
            )
            await db.commit()
            payment_id = cursor.lastrowid
            logger.info(f"Recorded payment #{payment_id}: {customer_name} - ${amount:,.2f} MXN by {recorded_by}")
            return payment_id
    
    async def get_customer_history(self, customer_name: str) -> List[Dict]:
        """
        Get all payment records for a specific customer.
        
        Args:
            customer_name: Name of the customer
            
        Returns:
            List of payment records as dictionaries
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, customer_name, amount, note, recorded_by, date_recorded
                FROM customer_payments
                WHERE customer_name = ?
                ORDER BY date_recorded DESC
                """,
                (customer_name,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_customer_total(self, customer_name: str) -> float:
        """
        Get the total amount paid by a specific customer.
        
        Args:
            customer_name: Name of the customer
            
        Returns:
            Total payment amount in MXN
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT SUM(amount) as total FROM customer_payments WHERE customer_name = ?",
                (customer_name,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row[0] is not None else 0.0
    
    async def get_all_payments(self) -> List[Dict]:
        """
        Get all payment records across all customers.
        
        Returns:
            List of all payment records as dictionaries
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, customer_name, amount, note, recorded_by, date_recorded
                FROM customer_payments
                ORDER BY date_recorded DESC
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_all_customers(self) -> List[str]:
        """
        Get a list of all unique customer names.
        
        Returns:
            List of customer names
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT DISTINCT customer_name FROM customer_payments ORDER BY customer_name"
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_statistics(self) -> Dict:
        """
        Get summary statistics across all payments.
        
        Returns:
            Dictionary with statistics
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get overall totals
            async with db.execute(
                """
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(amount) as total_amount,
                    COUNT(DISTINCT customer_name) as total_customers
                FROM customer_payments
                """
            ) as cursor:
                overall = dict(await cursor.fetchone())
            
            # Get per-customer totals
            async with db.execute(
                """
                SELECT 
                    customer_name,
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount
                FROM customer_payments
                GROUP BY customer_name
                ORDER BY total_amount DESC
                """
            ) as cursor:
                per_customer = [dict(row) for row in await cursor.fetchall()]
            
            return {
                "overall": overall,
                "per_customer": per_customer
            }
