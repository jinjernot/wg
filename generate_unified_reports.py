"""
Generate Unified Exchange Reports
Combines Bitso and Binance deposit reports into a single unified view

Usage:
    python generate_unified_reports.py [year] [month]
    
Examples:
    python generate_unified_reports.py              # Current month
    python generate_unified_reports.py 2026 1       # January 2026
"""
import sys
from datetime import datetime
from core.reports.unified_reports import generate_unified_reports


def main():
    # Get year and month from command line or use current
    if len(sys.argv) >= 3:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
    else:
        now = datetime.now()
        year = now.year
        month = now.month
    
    print(f"Generating unified reports for {year}-{month:02d}...")
    generate_unified_reports(year, month)
    print("\n✅ Done!")


if __name__ == '__main__':
    main()
