from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import pytz

from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.filter_data import filter_fundings_this_month
from core.bitso.filter_sender import filter_sender_name
from core.bitso.export import export_to_csv, export_failed_to_csv
import bitso_config


def process_user_funding(user: str, api_key: str, api_secret: str) -> tuple[list, list]:

    print(f"\nProcessing user: {user}")

    if not api_key or not api_secret:
        print(f"Missing credentials for {user}. Skipping...")
        return [], []

    fundings = fetch_funding_transactions_for_user(user, api_key, api_secret)
    filtered = filter_fundings_this_month(fundings)

    export_to_csv(filtered, filename=f'bitso_deposits_{user}.csv')
    export_failed_to_csv(fundings, filename=f'bitso_failed_deposits_{user}.csv')

    return filtered, fundings


def generate_growth_chart(all_fundings: list, filename: str = 'bitso_this_month_income.png'):
    """
    Generates and saves a bar chart of daily income for the current month.

    Args:
        all_fundings (list): A list of all funding transaction dictionaries.
        filename (str): The name of the file to save the chart to.
    """
    print(f"\nGenerating daily income bar chart for this month...")

    if not all_fundings:
        print("No funding data available to generate a bar chart.")
        return

    # Filter for successful/completed transactions only
    successful_fundings = [f for f in all_fundings if f.get('status') == 'complete']

    if not successful_fundings:
        print("No successful funding data found to generate a bar chart.")
        return

    df = pd.DataFrame(successful_fundings)

    # Convert data types for processing
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['amount'] = pd.to_numeric(df['amount'])

    # Define and convert to Mexico City timezone
    mexico_tz = pytz.timezone('America/Mexico_City')
    df['created_at'] = df['created_at'].dt.tz_convert(mexico_tz)

    # Filter for transactions in the current month using Mexico City time
    now = datetime.now(mexico_tz)
    this_month_df = df[(df['created_at'].dt.year == now.year) &
                       (df['created_at'].dt.month == now.month)]

    if this_month_df.empty:
        print("No income data found for the current month. Bar chart not generated.")
        return

    # Group by day and sum the amounts.
    this_month_df.set_index('created_at', inplace=True)
    daily_income = this_month_df['amount'].resample('D').sum()

    # Create and style the bar chart
    plt.figure(figsize=(12, 7))
    daily_income.plot(kind='bar', color='skyblue', edgecolor='black')

    # Improve formatting
    plt.title(f'Feria lavada: {now.strftime("%B %Y")}', fontsize=16, fontweight='bold')
    plt.xlabel('Dia del mes', fontsize=12)
    plt.ylabel('Dinero para la pension', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    # Format x-axis to show only the day number
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d'))
    plt.xticks(rotation=0)
    plt.tight_layout()

    # Save the chart to a file
    plt.savefig(filename)
    print(f"Success! Daily income bar chart saved to {filename}")
    plt.close()


def main():
    combined_data = []
    all_fundings_data = []

    for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
        user_data, all_fundings = process_user_funding(user, api_key, api_secret)
        combined_data.extend(user_data)
        all_fundings_data.extend(all_fundings)

    if combined_data:
        print("\nGenerating combined summary for all accounts...")
        filter_sender_name(combined_data, filename='bitso_sum_by_sender_name_all.csv')
    else:
        print("\nNo data found for any user.")

    if all_fundings_data:
        print("\nGenerating combined summary of failed deposits for all accounts...")
        export_failed_to_csv(all_fundings_data, filename='bitso_failed_deposits_all.csv')
        
        # Generate the growth chart from all funding data
        generate_growth_chart(all_fundings_data)

if __name__ == '__main__':
    main()