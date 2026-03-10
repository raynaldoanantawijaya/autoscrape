"""Test IDX stock scraping via option 3 custom URL."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from menu import _scrape_single_url

print("Testing IDX stock summary scraping...")
_scrape_single_url("Idx.Co.Id", "https://www.idx.co.id/id/data-pasar/ringkasan-perdagangan/ringkasan-saham/")
