import pytz
from datetime import date
from dateutil import parser

def filter_fundings_by_month(fundings, year, month):
    mexico_tz = pytz.timezone('America/Mexico_City')

    start_date = date(year, month, 1)
    # Correctly calculate the end of the month
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    print(f"Filtering fundings from {start_date} to {end_date} (Mexico City time)")

    filtered = []
    for f in fundings:
        created_str = f.get('created_at')
        if not created_str:
            continue

        try:
            created_local = parser.isoparse(created_str).astimezone(mexico_tz).date()
            if start_date <= created_local < end_date:
                filtered.append(f)
        except Exception as e:
            print(f"Skipping record with bad date format: {created_str} ({e})")

    print(f"Filtered down to {len(filtered)} funding transactions")
    return filtered