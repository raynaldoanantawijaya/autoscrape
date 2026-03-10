import os
import sys
import glob
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    class _Noop:
        def getattr(self, _): pass
    Fore = Style = _Noop()

def info(msg): print(f"  {Fore.CYAN}ℹ{Style.RESET_ALL} {msg}")
def ok(msg): print(f"  {Fore.GREEN}✓{Style.RESET_ALL} {msg}")
def err(msg): print(f"  {Fore.RED}✗{Style.RESET_ALL} {msg}")

from menu import run_scrape_emas, run_scrape_crypto, run_scrape_saham
from push_github import push_file_to_github

def find_newest_file(subfolder_name):
    """Mencari file JSON terbaru dalam folder hasil_scrape/<subfolder_name>"""
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_scrape", subfolder_name)
    if not os.path.exists(base_dir):
        return None
        
    files = glob.glob(os.path.join(base_dir, "*.json"))
    if not files:
        return None
        
    # Sort files by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def job_emas():
    info("Mulai Scrape Emas...")
    target_repo = os.environ.get("GITHUB_REPO_EMAS")
    if not target_repo:
        info("Skip push Emas: GITHUB_REPO_EMAS belum di setting")
        return
        
    run_scrape_emas()
    latest_file = find_newest_file("emas")
    
    if latest_file:
        pat = os.environ.get("GITHUB_PAT")
        if not pat:
            err("GITHUB_PAT tidak ditemukan!")
            return
            
        username = os.environ.get("GITHUB_USERNAME", "autobot")
        
        # Inject PAT into URL
        from urllib.parse import urlparse, quote
        parsed = urlparse(target_repo)
        safe_user = quote(username)
        safe_token = quote(pat)
        auth_repo_url = f"https://{safe_user}:{safe_token}@{parsed.netloc}{parsed.path}"
        
        target_name = "api_emas.json"
        
        ok(f"Pushing {os.path.basename(latest_file)} ke {target_repo} sebagai {target_name}...")
        push_file_to_github(latest_file, auth_repo_url, target_name)
    else:
        err("Gagal menemukan hasil JSON Emas")


def job_crypto():
    info("Mulai Scrape Crypto (CoinMarketCap & Investing.com)...")
    target_repo = os.environ.get("GITHUB_REPO_CRYPTO")
    if not target_repo:
        info("Skip push Crypto: GITHUB_REPO_CRYPTO belum di setting")
        return
        
    run_scrape_crypto()
    latest_file = find_newest_file("crypto")
    
    if latest_file:
        pat = os.environ.get("GITHUB_PAT")
        if not pat:
            err("GITHUB_PAT tidak ditemukan!")
            return
            
        username = os.environ.get("GITHUB_USERNAME", "autobot")
        
        from urllib.parse import urlparse, quote
        parsed = urlparse(target_repo)
        safe_user = quote(username)
        safe_token = quote(pat)
        auth_repo_url = f"https://{safe_user}:{safe_token}@{parsed.netloc}{parsed.path}"
        
        target_name = "api_crypto.json"
        
        ok(f"Pushing {os.path.basename(latest_file)} ke {target_repo} sebagai {target_name}...")
        push_file_to_github(latest_file, auth_repo_url, target_name)
    else:
        err("Gagal menemukan hasil JSON Crypto")


def job_saham():
    info("Mulai Scrape Saham (IDX)...")
    target_repo = os.environ.get("GITHUB_REPO_SAHAM")
    if not target_repo:
        info("Skip push Saham: GITHUB_REPO_SAHAM belum di setting")
        return
        
    run_scrape_saham()
    latest_file = find_newest_file("saham")
    
    if latest_file:
        pat = os.environ.get("GITHUB_PAT")
        if not pat:
            err("GITHUB_PAT tidak ditemukan!")
            return
            
        username = os.environ.get("GITHUB_USERNAME", "autobot")
        
        from urllib.parse import urlparse, quote
        parsed = urlparse(target_repo)
        safe_user = quote(username)
        safe_token = quote(pat)
        auth_repo_url = f"https://{safe_user}:{safe_token}@{parsed.netloc}{parsed.path}"
        
        target_name = "api_saham.json"
        
        ok(f"Pushing {os.path.basename(latest_file)} ke {target_repo} sebagai {target_name}...")
        push_file_to_github(latest_file, auth_repo_url, target_name)
    else:
        err("Gagal menemukan hasil JSON Saham")


if __name__ == "__main__":
    print(f"\n{Fore.MAGENTA}=========================================={Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}   🤖 MEMULAI AUTO-BOT SCRAPER RUNNER     {Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}=========================================={Style.RESET_ALL}\n")
    
    if not os.environ.get("GITHUB_PAT"):
        warn("Peringatan: GITHUB_PAT env variable tidak ditemukan. Push ke github mungkin gagal.")
    
    # Run sequentially so Playwright doesn't clash
    try:
        job_saham()
        job_emas()
        job_crypto()
        print(f"\n{Fore.GREEN}✔ Selesai semua tugas Auto-Bot.{Style.RESET_ALL}\n")
    except Exception as e:
        print(f"\n{Fore.RED}✘ Terjadi kesalahan fatal pada Auto-Bot: {e}{Style.RESET_ALL}\n")
        sys.exit(1)
