import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend to prevent threading issues
import matplotlib.pyplot as plt
import bitso_config
import pandas as pd
import pytz
import os

from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.export import export_to_csv, export_failed_to_csv
from core.bitso.filter_data import filter_fundings_by_month
from core.bitso.filter_sender import filter_sender_name
from core.bitso.fallback_loader import load_eduardo_fallback_data

from datetime import datetime
from config import BITSO_REPORTS_DIR

os.makedirs(BITSO_REPORTS_DIR, exist_ok=True)


def process_user_funding(user: str, api_key: str, api_secret: str, year: int, month: int) -> tuple[list, list]:
    print(f"\nProcessing user: {user}")

    if not api_key or not api_secret:
        print(f"Missing credentials for {user}. Skipping...")
        return [], []

    # WORKAROUND: eduardo_ramirez account is gone, go directly to fallback CSV to avoid API timeout
    used_fallback = False
    if user == 'eduardo_ramirez':
        print(f"Skipping API call for {user}, using fallback data directly...")
        fundings = load_eduardo_fallback_data(year, month)
        used_fallback = len(fundings) > 0
    else:
        fundings = fetch_funding_transactions_for_user(user, api_key, api_secret, year=year, month=month)
    
    for f in fundings:
        f['account_user'] = user

    filtered = filter_fundings_by_month(fundings, year, month)

    deposits_filename = os.path.join(BITSO_REPORTS_DIR, f'bitso_deposits_{user}.csv')
    failed_filename = os.path.join(BITSO_REPORTS_DIR, f'bitso_failed_deposits_{user}.csv')

    # Only export to reports directory (don't overwrite the root fallback CSV)
    export_to_csv(filtered, filename=deposits_filename)
    if not used_fallback:  # Only export failed if we didn't use fallback (to preserve root CSV)
        export_failed_to_csv(fundings, filename=failed_filename)
    else:
        print(f"Skipping failed deposits export for {user} (using fallback data)")

    return filtered, fundings

def generate_growth_chart(all_fundings: list, year: int, month: int, filename: str = 'bitso_this_month_income.png'):
    """
    Generates and saves a daily bar chart of income for a specific month,
    with colors split between the first half (1-15) and second half (16-end).
    """
    print(f"\nGenerating appealing daily income bar chart for {year}-{month}...")

    if not all_fundings:
        print("No funding data available to generate a bar chart.")
        return

    # Filter out Bitso transfers and only keep successful fundings
    successful_fundings = [
        f for f in all_fundings 
        if f.get('status') == 'complete' and 
        f.get('method_name') != 'Bitso Transfer'
    ]

    if not successful_fundings:
        print("No successful funding data found to generate a bar chart.")
        return

    df = pd.DataFrame(successful_fundings)
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['amount'] = pd.to_numeric(df['amount'])

    mexico_tz = pytz.timezone('America/Mexico_City')
    df['created_at'] = df['created_at'].dt.tz_convert(mexico_tz)

    month_df = df[(df['created_at'].dt.year == year) &
                  (df['created_at'].dt.month == month)].copy()

    if month_df.empty:
        print(f"No income data found for {year}-{month}. Bar chart not generated.")
        return

    month_df.set_index('created_at', inplace=True)
    daily_income = month_df['amount'].resample('D').sum()

    # === Chart Styling (More Appealing) ===
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#1a1a2e')  # dark blue/purple background
    ax.set_facecolor('#1a1a2e')

    # Assign colors based on day of month (<= 15 vs > 15)
    # Using cyan for 1-15 and purple/pink for 16-end
    colors = ['#00d2ff' if date.day <= 15 else '#e94560' for date in daily_income.index]

    # Plot daily income
    bars = daily_income.plot(
        kind='bar',
        ax=ax,
        color=colors,
        edgecolor='#1a1a2e',
        linewidth=1.0,
        width=0.7
    )

    chart_date = datetime(year, month, 1)
    plt.title(f'Fondos Diarios: {chart_date.strftime("%B %Y")}', fontsize=20, fontweight='bold', color='white', pad=25)
    plt.xlabel('Día del mes', fontsize=14, color='#e0e0e0', labelpad=15)
    plt.ylabel('Monto (MXN)', fontsize=14, color='#e0e0e0', labelpad=15)
    
    # Grid & Spines
    ax.yaxis.grid(True, linestyle='--', alpha=0.2, color='#e0e0e0')
    ax.xaxis.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
        
    # X-axis labels (just the day number)
    x_labels = [date.strftime('%d') for date in daily_income.index]
    ax.set_xticklabels(x_labels, rotation=0, fontsize=12, fontweight='bold', color='#e0e0e0')
    plt.yticks(fontsize=12, color='#e0e0e0')
    
    # Format Y axis
    import matplotlib.ticker as ticker
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('${x:,.0f}'))
        
    # Labels on each bar
    for i, v in enumerate(daily_income):
        if v >= 100:
            # Format as $1.5k for values >= 1000 to save space, or just integer
            formatted_v = f'${v/1000:,.1f}k' if v >= 1000 else f'${v:,.0f}'
            ax.text(i, v + (daily_income.max() * 0.015), formatted_v, 
                    ha='center', va='bottom', color=colors[i], fontweight='bold', fontsize=10, rotation=90 if v >= 1000 else 0)
            
    plt.tight_layout()

    # --- Save chart to the reports directory ---
    chart_filepath = os.path.join(BITSO_REPORTS_DIR, filename)
    plt.savefig(chart_filepath, dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
    print(f"Success! Daily income bar chart saved to {chart_filepath}")
    plt.close()