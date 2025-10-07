import matplotlib.pyplot as plt
import bitso_config
import pandas as pd
import pytz
import os

from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.export import export_to_csv, export_failed_to_csv
from core.bitso.filter_data import filter_fundings_by_month
from core.bitso.filter_sender import filter_sender_name

from datetime import datetime
from config import REPORTS_DIR

os.makedirs(REPORTS_DIR, exist_ok=True)


def process_user_funding(user: str, api_key: str, api_secret: str, year: int, month: int) -> tuple[list, list]:
    print(f"\nProcessing user: {user}")

    if not api_key or not api_secret:
        print(f"Missing credentials for {user}. Skipping...")
        return [], []

    fundings = fetch_funding_transactions_for_user(user, api_key, api_secret)
    for f in fundings:
        f['account_user'] = user

    filtered = filter_fundings_by_month(fundings, year, month)

    deposits_filename = os.path.join(REPORTS_DIR, f'bitso_deposits_{user}.csv')
    failed_filename = os.path.join(REPORTS_DIR, f'bitso_failed_deposits_{user}.csv')

    export_to_csv(filtered, filename=deposits_filename)
    export_failed_to_csv(fundings, filename=failed_filename)

    return filtered, fundings

def generate_growth_chart(all_fundings: list, year: int, month: int, filename: str = 'bitso_this_month_income.png'):
    """
    Generates and saves a bar chart of daily income for a specific month.
    """
    print(f"\nGenerating daily income bar chart for {year}-{month}...")

    if not all_fundings:
        print("No funding data available to generate a bar chart.")
        return

    successful_fundings = [f for f in all_fundings if f.get('status') == 'complete']

    if not successful_fundings:
        print("No successful funding data found to generate a bar chart.")
        return

    df = pd.DataFrame(successful_fundings)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['amount'] = pd.to_numeric(df['amount'])

    mexico_tz = pytz.timezone('America/Mexico_City')
    df['created_at'] = df['created_at'].dt.tz_convert(mexico_tz)

    month_df = df[(df['created_at'].dt.year == year) &
                    (df['created_at'].dt.month == month)]

    if month_df.empty:
        print(f"No income data found for {year}-{month}. Bar chart not generated.")
        return

    month_df.set_index('created_at', inplace=True)
    daily_income = month_df['amount'].resample('D').sum()

    plt.figure(figsize=(12, 7))
    daily_income.plot(kind='bar', color='skyblue', edgecolor='black')

    chart_date = datetime(year, month, 1)
    plt.title(f'Fondos: {chart_date.strftime("%B %Y")}', fontsize=16, fontweight='bold')
    plt.xlabel('Dia del mes', fontsize=12)
    plt.ylabel('Dinero para el perico', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d'))
    plt.xticks(rotation=0)
    plt.tight_layout()

    # --- Save chart to the reports directory ---
    chart_filepath = os.path.join(REPORTS_DIR, filename)
    plt.savefig(chart_filepath)
    print(f"Success! Daily income bar chart saved to {chart_filepath}")
    plt.close()