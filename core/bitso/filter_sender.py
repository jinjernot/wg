import pandas as pd
import bitso_config

def filter_sender_name(fundings, filename='bitso_sum_by_sender_name.csv'):
    data = []
    for f in fundings:
        # Exclude fundings with a status of 'failed'
        if f.get('status') == 'failed':
            continue

        details = f.get('details', {}) or {}
        clabe = details.get('sender_clabe')
        amount_str = f.get('amount', 0)

        try:
            amount = float(amount_str)
        except ValueError:
            print(f"Invalid amount: {amount_str}. Skipping.")
            continue

        name = bitso_config.ACCOUNT.get(clabe, clabe)
        data.append({
            'Sender Name': name,
            'Amount': amount
        })

    df = pd.DataFrame(data)
    df = df.dropna(subset=['Sender Name'])

    summary = (
        df.groupby('Sender Name', as_index=False)
        .sum(numeric_only=True)
    )

    # Sort alphabetically
    summary = summary.sort_values(by='Sender Name')

    # Compute total
    total_amount = summary['Amount'].sum()
    total_row = pd.DataFrame([{'Sender Name': 'Total', 'Amount': total_amount}])

    # Append total at the end
    summary = pd.concat([summary, total_row], ignore_index=True)

    # Format Amounts
    summary['Amount'] = summary['Amount'].apply(lambda x: f"${x:,.2f}")

    summary.to_csv(filename, index=False)
    print(f"Sum of deposits by Sender Name saved to {filename}")
    print(f"Total amount from all senders: ${total_amount:,.2f}")