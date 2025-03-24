import threading

from core.trade_processor import process_trades
from config import ACCOUNTS

def main():
    
    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=process_trades, args=(account,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
