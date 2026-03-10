from menu import _scrape_single_url
import os

print("Testing ID Investing.com wrapper...")
os.makedirs("hasil_scrape", exist_ok=True)
_scrape_single_url("Id.Investing.Com", "https://id.investing.com/crypto/currencies")
