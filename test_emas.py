"""Test emas scraping via option 1 to verify subfolder routing."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from menu import _scrape_single_url

print("Testing emas scraping (expected folder: hasil_scrape/emas)...")
_scrape_single_url("Galeri24", "https://galeri24.co.id/", subfolder="emas")
