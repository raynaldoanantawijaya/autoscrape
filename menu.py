#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║              AUTO SCRAPER — INTERACTIVE MENU                ║
║         Semua teknik scraping dalam satu menu CLI           ║
╚══════════════════════════════════════════════════════════════╝

Fitur teknik yang terintegrasi:
  ① Direct Requests      — requests + BeautifulSoup (cepat, tanpa browser)
  ② Network Capture      — Playwright intercept XHR/JSON (Next.js, Nuxt SSR)
  ③ DOM Extraction       — Playwright JS eval (lazy-load, SPA, React)
  ④ SSR JSON Parser      — pageProps / __NEXT_DATA__ / Nuxt state extraction
  ⑤ Vue State Parser     — Reactive array dereferencing (Galeri24 style)
  ⑥ HTML Table Parser    — BeautifulSoup table → dict (TradingEconomics)
  ⑦ Multi-page Loop      — Pagination otomatis (Pluang 64 halaman)
  ⑧ Link Pattern Mining  — Regex URL pattern matching (Kompas.com)

Cara pakai:
  python menu.py          ← mode menu interaktif
  python menu.py --all    ← langsung scrape semua (non-interaktif)
"""
import os
import sys
import json
import time
import threading
import subprocess
import logging
import re
import glob
from datetime import datetime
from pathlib import Path

# ─── Colorama (terminal warna) ───────────────────────────────────────────────
try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
except ImportError:
    # Fallback tanpa warna jika colorama tidak ada
    class _Noop:
        def __getattr__(self, _): return ""
    Fore = Back = Style = _Noop()

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("menu")

OUTPUT_DIR = "hasil_scrape"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Browser Helper ──────────────────────────────────────────────────────────

def get_browser_path():
    """Cari lokasi browser chromium di sistem sebagai fallback."""
    paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

# ══════════════════════════════════════════════════════════════════════════════
# TAMPILAN / UI
# ══════════════════════════════════════════════════════════════════════════════

BANNER = f"""
{Fore.CYAN}{Style.BRIGHT}
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   ░█████╗░██╗░░░██╗████████╗░█████╗░   ░██████╗░░      │
  │   ██╔══██╗██║░░░██║╚══██╔══╝██╔══██╗  ██╔════╝░░      │
  │   ███████║██║░░░██║░░░██║░░░██║░░██║  ╚█████╗░░░      │
  │   ██╔══██║██║░░░██║░░░██║░░░██║░░██║  ░╚═══██╗░░      │
  │   ██║░░██║╚██████╔╝░░░██║░░░╚█████╔╝  ██████╔╝░░      │
  │   ╚═╝░░╚═╝░╚═════╝░░░╚═╝░░░░╚════╝   ╚═════╝░░░      │
  │                                                         │
  │         {Fore.YELLOW}S C R A P E R   M E N U{Fore.CYAN}  v2.0               │
  │              Semua Teknik. Satu Menu.                   │
  └─────────────────────────────────────────────────────────┘
{Style.RESET_ALL}"""

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_header(title: str):
    clear()
    print(BANNER)
    print(f"  {Fore.YELLOW}{'─'*57}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{Style.BRIGHT}  {title}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}{'─'*57}{Style.RESET_ALL}\n")

def ok(msg):   print(f"  {Fore.GREEN}✓{Style.RESET_ALL}  {msg}")
def err(msg):  print(f"  {Fore.RED}✗{Style.RESET_ALL}  {msg}")
def info(msg): print(f"  {Fore.CYAN}ℹ{Style.RESET_ALL}  {msg}")
def warn(msg): print(f"  {Fore.YELLOW}⚠{Style.RESET_ALL}  {msg}")
def head(msg): print(f"\n  {Fore.MAGENTA}{Style.BRIGHT}{msg}{Style.RESET_ALL}")

def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {Fore.CYAN}➤{Style.RESET_ALL}  {prompt}{suffix}: ").strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        return default

def show_result(title: str, filepath: str, count: int):
    print(f"\n  {'═'*57}")
    ok(f"{Fore.GREEN}{Style.BRIGHT}{title}")
    ok(f"Jumlah data: {Fore.YELLOW}{count}{Style.RESET_ALL} item")
    ok(f"File: {Fore.CYAN}{filepath}{Style.RESET_ALL}")
    print(f"  {'═'*57}\n")


# ══════════════════════════════════════════════════════════════════════════════
# TEKNIK 1: DIRECT REQUEST + BEAUTIFULSOUP
# Digunakan untuk: situs statis / server-side rendered HTML
# ══════════════════════════════════════════════════════════════════════════════

def technique_direct_request(url: str, category: str = "general") -> dict | None:
    """
    Teknik ①: Direct HTTP GET + BeautifulSoup parsing.
    Cocok untuk: situs HTML statis, tidak butuh JavaScript.
    """
    import requests
    from bs4 import BeautifulSoup
    import urllib3
    urllib3.disable_warnings()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Request gagal: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Ekstrak tabel HTML
    tables = []
    for table in soup.find_all("table"):
        rows = []
        headers_raw = [th.get_text(strip=True) for th in table.find_all("th")]
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells and len(cells) >= 2:
                rows.append(dict(zip(headers_raw, cells)) if headers_raw else cells)
        if rows:
            tables.append({"headers": headers_raw, "rows": rows})

    # Ekstrak semua link artikel
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if text and len(text) > 10 and href.startswith("http"):
            links.append({"text": text, "url": href})

    # Ekstrak inline JSON / ld+json
    inline_json = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            inline_json.append(json.loads(script.string or "{}"))
        except Exception:
            pass

    return {
        "url": url,
        "category": category,
        "technique": "direct_request_beautifulsoup",
        "tables": tables,
        "links": links[:100],
        "inline_json": inline_json
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEKNIK 2: PLAYWRIGHT NETWORK CAPTURE (XHR INTERCEPT)
# Digunakan untuk: Next.js, Nuxt, SPA yang load data via API
# ══════════════════════════════════════════════════════════════════════════════

def technique_network_capture(url: str) -> dict | None:
    """
    Teknik ②: Playwright intercept semua response JSON dari network.
    Tangkap XHR/Fetch API calls yang berisi data.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    import json as _json

    captured = {}

    def handle_response(response):
        try:
            ct = response.headers.get("content-type", "")
            if "json" in ct and response.status == 200:
                try:
                    body = response.json()
                    if body and isinstance(body, (dict, list)):
                        captured[response.url] = body
                except Exception:
                    pass
        except Exception:
            pass

    with sync_playwright() as p:
        browser_path = get_browser_path()
        launch_args = {"headless": True}
        if browser_path:
            launch_args["executable_path"] = browser_path
        
        try:
            browser = p.chromium.launch(**launch_args)
        except Exception:
            browser = p.chromium.launch(headless=True)

        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = ctx.new_page()
        page.on("response", handle_response)

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except PWTimeout:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass

        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        # Ambil juga __NEXT_DATA__ dan Nuxt state (lihat Teknik 4)
        next_data = page.evaluate("""
        () => {
            const el = document.getElementById('__NEXT_DATA__');
            if (el) { try { return JSON.parse(el.textContent); } catch(e) {} }
            return null;
        }
        """)

        nuxt_data = page.evaluate("""
        () => {
            if (window.__NUXT__) return window.__NUXT__;
            const el = document.getElementById('__NUXT_DATA__');
            if (el) { try { return JSON.parse(el.textContent); } catch(e) {} }
            return null;
        }
        """)

        browser.close()

    result = {"captured_apis": captured}
    if next_data:
        result["__NEXT_DATA__"] = next_data
    if nuxt_data:
        result["__NUXT__"] = nuxt_data
    return result


# ══════════════════════════════════════════════════════════════════════════════
# TEKNIK 3: PLAYWRIGHT DOM EXTRACTION (JS eval)
# Digunakan untuk: Kompas, TradingEconomics — JS-rendered content
# ══════════════════════════════════════════════════════════════════════════════

def technique_dom_extraction(url: str, selectors: list[str] = None) -> dict | None:
    """
    Teknik ③: Playwright buka halaman, tunggu render, ekstrak via JS eval.
    Bisa ekstrak tabel, artikel, card, data harga dari DOM.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    if selectors is None:
        selectors = ['article', '[class*="article"]', '[class*="card"]', 'table', 'li']

    with sync_playwright() as p:
        browser_path = get_browser_path()
        launch_args = {"headless": True}
        if browser_path:
            launch_args["executable_path"] = browser_path

        try:
            browser = p.chromium.launch(**launch_args)
        except Exception:
            browser = p.chromium.launch(headless=True)

        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="id-ID"
        )
        page = ctx.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
        except PWTimeout:
            pass

        # Tunggu konten utama
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                pass

        # Scroll untuk lazy load
        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
        page.wait_for_timeout(1000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

        # ── Ekstrak TABEL ────────────────────────────────────────────────────
        tables = page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('table').forEach(tbl => {
                const hdrs = Array.from(tbl.querySelectorAll('th')).map(h => h.innerText.trim());
                const rows = [];
                tbl.querySelectorAll('tr').forEach((tr, i) => {
                    if (i === 0 && hdrs.length) return;
                    const cells = Array.from(tr.querySelectorAll('td')).map(c => c.innerText.trim());
                    if (cells.length >= 2) {
                        rows.push(hdrs.length ? Object.fromEntries(hdrs.map((h,j) => [h, cells[j]||''])) : cells);
                    }
                });
                if (rows.length) results.push({headers: hdrs, rows});
            });
            return results;
        }
        """)

        # ── Ekstrak ARTIKEL / LINK ────────────────────────────────────────────
        articles = page.evaluate("""
        () => {
            const seen = new Set(), results = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const text = (a.innerText || a.title || '').trim();
                if (text.length < 15 || seen.has(a.href)) return;
                seen.add(a.href);
                const card = a.closest('article, [class*="article"], [class*="card"], li') || a.parentElement;
                let img = '', time_ = '';
                if (card) {
                    const imgEl = card.querySelector('img[src], img[data-src]');
                    const tEl   = card.querySelector('time, [class*="time"], [class*="date"]');
                    img   = imgEl ? (imgEl.dataset.src || imgEl.src) : '';
                    time_ = tEl  ? (tEl.getAttribute('datetime') || tEl.innerText.trim()) : '';
                }
                results.push({ judul: text, url: a.href, thumbnail: img, waktu: time_ });
            });
            return results;
        }
        """)

        browser.close()

    return {"tables": tables, "articles": articles[:200]}


# ══════════════════════════════════════════════════════════════════════════════
# TEKNIK 4: SSR JSON PARSER (Next.js pageProps / __NEXT_DATA__)
# Digunakan untuk: Pluang.com (stock data)
# ══════════════════════════════════════════════════════════════════════════════

def technique_ssr_parser(url: str) -> dict | None:
    """
    Teknik ④: Parse __NEXT_DATA__ / pageProps dari Next.js SSR.
    Data terdapat di dalam tag <script id='__NEXT_DATA__'>.
    Jauh lebih cepat dari Playwright (pakai requests biasa).
    """
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"SSR fetch gagal: {e}")
        return None

    # Cari __NEXT_DATA__
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                      resp.text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Fallback: cari JSON besar dalam script tag
    matches = re.findall(r'<script[^>]*>(window\.__NUXT__|window\.__STATE__)\s*=\s*(\{.*?\})</script>',
                         resp.text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[0][1])
        except Exception:
            pass

    return None


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: EMAS
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_emas():
    """Scrape harga emas dari berbagai sumber menggunakan teknik langsung."""
    print_header("① SCRAPE HARGA EMAS")

    sources = [
        ("Galeri24",         "https://galeri24.co.id/"),
        ("Harga-Emas.org",   "https://harga-emas.org/"),
        ("Antam Logam Mulia","https://www.logammulia.com/id/harga-emas-hari-ini"),
    ]

    info("Sumber default:")
    for i, (name, url) in enumerate(sources, 1):
        print(f"     {i}. {name}: {Fore.CYAN}{url}{Style.RESET_ALL}")

    custom = ask("Tambah URL emas lain (kosongkan untuk skip)", "")
    if custom:
        sources.append(("Custom", custom))

    head("Memulai scraping...")
    timestamp = int(time.time())
    all_results = {}

    for name, url in sources:
        info(f"Scraping [{name}]...")
        try:
            # ── Langkah 1: Coba Direct Request (cepat, tanpa browser) ──
            info(f"  → Teknik ①: Direct Request + BeautifulSoup...")
            data = technique_direct_request(url, category="emas")

            tables = data.get("tables", []) if data else []
            inline = data.get("inline_json", []) if data else []

            if tables:
                ok(f"  [{name}] {len(tables)} tabel ditemukan via Direct Request")
                all_results[name] = {
                    "technique": "direct_request",
                    "tables": tables,
                    "inline_json": inline
                }
                continue

            # ── Langkah 2: Fallback ke DOM Extraction (browser) ──
            warn(f"  [{name}] Direct Request kurang data, mencoba DOM Extraction...")
            dom_data = technique_dom_extraction(url, selectors=["table", '[class*="price"]', '[class*="harga"]'])
            if dom_data:
                dom_tables = dom_data.get("tables", [])
                dom_articles = dom_data.get("articles", [])
                if dom_tables or dom_articles:
                    ok(f"  [{name}] {len(dom_tables)} tabel + {len(dom_articles)} item via DOM Extraction")
                    all_results[name] = {
                        "technique": "dom_extraction",
                        "tables": dom_tables,
                        "articles": dom_articles[:50]
                    }
                    continue

            warn(f"  [{name}] Tidak ada data harga emas yang ditemukan")

        except Exception as e:
            err(f"[{name}] Error: {e}")

    if all_results:
        out_path = os.path.join(OUTPUT_DIR, f"emas_combined_{timestamp}.json")
        out = {
            "metadata": {
                "scrape_date": datetime.now().isoformat(),
                "sources": list(all_results.keys()),
                "total_sources": len(all_results)
            },
            "data": all_results
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        show_result("HARGA EMAS BERHASIL DI-SCRAPE", os.path.abspath(out_path), len(all_results))

        # Preview data
        head("Preview Data:")
        for src_name, src_data in all_results.items():
            tbls = src_data.get("tables", [])
            if tbls:
                tbl = tbls[0]
                rows = tbl.get("rows", [])[:3]
                for row in rows:
                    if isinstance(row, dict):
                        vals = " | ".join(f"{v}" for v in list(row.values())[:4])
                    else:
                        vals = " | ".join(str(c) for c in row[:4])
                    print(f"    {Fore.CYAN}[{src_name}]{Style.RESET_ALL} {vals}")
    else:
        err("Tidak ada data emas yang ditemukan!")

    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: CRYPTO
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_crypto():
    """Scrape data cryptocurrency menggunakan teknik langsung."""
    print_header("② SCRAPE CRYPTOCURRENCY")

    sources = [
        ("CoinMarketCap",   "https://coinmarketcap.com/"),
        ("CoinGecko",       "https://www.coingecko.com/"),
    ]

    info("Sumber default:")
    for i, (name, url) in enumerate(sources, 1):
        print(f"     {i}. {name}: {Fore.CYAN}{url}{Style.RESET_ALL}")

    custom = ask("Tambah URL crypto lain (kosongkan untuk skip)", "")
    if custom:
        sources.append(("Custom", custom))

    head("Memulai scraping...")
    timestamp = int(time.time())
    all_results = {}

    for name, url in sources:
        info(f"Scraping [{name}]...")
        try:
            # ── Langkah 1: Network Capture (intercept API JSON) ──
            info(f"  → Teknik ②: Network Capture (Playwright XHR Intercept)...")
            nc_data = technique_network_capture(url)

            captured = nc_data.get("captured_apis", {}) if nc_data else {}
            next_data = nc_data.get("__NEXT_DATA__") if nc_data else None

            if captured:
                ok(f"  [{name}] {len(captured)} API endpoint tertangkap")
                all_results[name] = {
                    "technique": "network_capture",
                    "api_count": len(captured),
                    "apis": captured
                }
                if next_data:
                    all_results[name]["__NEXT_DATA__"] = next_data
                continue

            # ── Langkah 2: DOM Extraction ──
            warn(f"  [{name}] Tidak ada API, mencoba DOM Extraction...")
            dom_data = technique_dom_extraction(url, selectors=["table", '[class*="coin"]', '[class*="crypto"]'])
            if dom_data:
                dom_tables = dom_data.get("tables", [])
                dom_articles = dom_data.get("articles", [])
                if dom_tables or dom_articles:
                    ok(f"  [{name}] {len(dom_tables)} tabel + {len(dom_articles)} item via DOM Extraction")
                    all_results[name] = {
                        "technique": "dom_extraction",
                        "tables": dom_tables,
                        "articles": dom_articles[:100]
                    }
                    continue

            warn(f"  [{name}] Tidak ada data crypto yang ditemukan")

        except Exception as e:
            err(f"[{name}] Error: {e}")

    if all_results:
        out_path = os.path.join(OUTPUT_DIR, f"crypto_combined_{timestamp}.json")
        out = {
            "metadata": {
                "scrape_date": datetime.now().isoformat(),
                "sources": list(all_results.keys()),
                "total_sources": len(all_results)
            },
            "data": all_results
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        show_result("CRYPTO BERHASIL DI-SCRAPE", os.path.abspath(out_path), len(all_results))

        # Preview
        head("Preview:")
        for src_name, src_data in all_results.items():
            count = src_data.get("api_count", 0) or len(src_data.get("tables", []))
            tech = src_data.get("technique", "unknown")
            print(f"    {Fore.CYAN}[{src_name}]{Style.RESET_ALL} {count} data via {tech}")
    else:
        err("Tidak ada data crypto yang ditemukan!")

    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: BERITA
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_berita():
    """Scrape berita dari sumber yang dipilih user."""
    print_header("③ SCRAPE BERITA")

    presets = {
        "1": ("Kompas.com",     "https://www.kompas.com/",    "kompas"),
        "2": ("Detik.com",      "https://www.detik.com/",     "detik"),
        "3": ("CNN Indonesia",  "https://www.cnnindonesia.com/","cnn"),
        "4": ("Tribunnews",     "https://www.tribunnews.com/", "tribun"),
        "5": ("Tempo.co",       "https://tempo.co/",          "tempo"),
        "6": ("Liputan6",       "https://liputan6.com/",      "liputan6"),
        "7": ("Antaranews",     "https://www.antaranews.com/", "antara"),
        "8": ("Custom URL...",  "",                           "custom"),
    }

    print(f"  {Fore.CYAN}Pilih sumber berita:{Style.RESET_ALL}\n")
    for key, (name, url, _) in presets.items():
        url_display = f"  {Fore.CYAN}{url}{Style.RESET_ALL}" if url else ""
        print(f"     {Fore.YELLOW}{key}{Style.RESET_ALL}. {name}{url_display}")

    choice = ask("\nPilihan (1-8, atau beberapa dipisah koma: 1,2,3)", "1")
    choices = [c.strip() for c in choice.split(",")]

    targets = []
    for c in choices:
        if c in presets:
            name, url, slug = presets[c]
            if not url:  # Custom
                url  = ask("Masukkan URL berita")
                name = ask("Nama sumber", "Custom")
                slug = "custom"
            targets.append((name, url, slug))

    if not targets:
        err("Tidak ada target yang dipilih.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    head(f"Scraping {len(targets)} sumber via Playwright DOM Extraction...")
    timestamp = int(time.time())
    all_articles = []

    for name, url, slug in targets:
        info(f"Scraping [{name}]: {url}")

        if slug in ("kompas", "custom") and "kompas" in url:
            # Gunakan scraper khusus Kompas
            try:
                result = subprocess.run(
                    [sys.executable, "scrape_kompas_news.py"],
                    capture_output=True, text=True, timeout=180,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "kompas_news_*.json")),
                               key=os.path.getmtime, reverse=True)
                if files:
                    with open(files[0], encoding="utf-8") as f:
                        data = json.load(f)
                    arts = data.get("articles", [])
                    all_articles.extend(arts)
                    ok(f"[{name}] {len(arts)} artikel ditemukan")
                    continue
            except Exception as e:
                warn(f"Kompas script gagal ({e}), fallback ke DOM extraction...")

        # Fallback: DOM extraction generik
        extracted = technique_dom_extraction(url)
        if extracted and extracted.get("articles"):
            arts = extracted["articles"]
            for a in arts:
                a["source"] = name
                a["source_url"] = url
            filtered = [a for a in arts if _is_article_url(a["url"])]
            all_articles.extend(filtered)
            ok(f"[{name}] {len(filtered)} artikel ditemukan")
        else:
            warn(f"[{name}] Tidak ada artikel ditemukan")

    # Deduplikasi
    seen = set()
    unique = []
    for a in all_articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)

    if unique:
        out_path = os.path.join(OUTPUT_DIR, f"berita_combined_{timestamp}.json")
        out = {
            "metadata": {
                "scrape_date": datetime.now().isoformat(),
                "sources": [t[0] for t in targets],
                "total_articles": len(unique)
            },
            "articles": unique
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        show_result("BERITA BERHASIL DI-SCRAPE", os.path.abspath(out_path), len(unique))

        # Preview
        head("5 Artikel Pertama:")
        for art in unique[:5]:
            src = art.get("source", "")
            print(f"    {Fore.CYAN}[{src}]{Style.RESET_ALL} {art['judul'][:65]}")
    else:
        err("Tidak ada artikel yang ditemukan!")

    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: SAHAM
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_saham():
    """Scrape data saham menggunakan teknik langsung."""
    print_header("④ SCRAPE SAHAM / STOCKS")

    presets = {
        "1": ("Pluang (US Stocks)", "https://pluang.com/saham-as"),
        "2": ("Custom URL...", ""),
    }

    for k, (name, url) in presets.items():
        display = f"  {Fore.CYAN}{url}{Style.RESET_ALL}" if url else ""
        print(f"     {Fore.YELLOW}{k}{Style.RESET_ALL}. {name}{display}")

    choice = ask("Pilihan (1-2)", "1")

    timestamp = int(time.time())

    if choice == "1":
        head("Scraping Pluang US Stocks via SSR Parser...")
        base_url = "https://pluang.com/saham-as"
        all_stocks = []
        page_num = 1
        max_pages = 70

        while page_num <= max_pages:
            url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
            info(f"  Halaman {page_num}...")

            data = technique_ssr_parser(url)
            if not data:
                if page_num == 1:
                    warn("SSR tidak ditemukan, mencoba DOM Extraction...")
                    dom = technique_dom_extraction(base_url)
                    if dom and dom.get("tables"):
                        all_stocks = dom["tables"]
                break

            # Ekstrak dari __NEXT_DATA__ pageProps
            try:
                page_props = data.get("props", {}).get("pageProps", {})
                stocks = page_props.get("stocks", page_props.get("data", []))
                if isinstance(stocks, list) and len(stocks) > 0:
                    all_stocks.extend(stocks)
                    ok(f"  Halaman {page_num}: {len(stocks)} ticker")
                    page_num += 1
                else:
                    break
            except Exception:
                break

        if all_stocks:
            out_path = os.path.join(OUTPUT_DIR, f"pluang_all_stocks_{timestamp}.json")
            out = {
                "metadata": {
                    "scrape_date": datetime.now().isoformat(),
                    "source": "pluang.com",
                    "total_stocks_found": len(all_stocks),
                    "pages_scraped": page_num - 1
                },
                "stocks": all_stocks
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            show_result("SAHAM BERHASIL DI-SCRAPE", os.path.abspath(out_path), len(all_stocks))

            # Preview
            head("5 Ticker Pertama:")
            for s in all_stocks[:5]:
                if isinstance(s, dict):
                    sym = s.get("symbol", s.get("ticker", "?"))
                    name_ = s.get("name", s.get("companyName", ""))
                    price = s.get("price", s.get("lastPrice", "?"))
                    print(f"    {Fore.GREEN}{sym:>6}{Style.RESET_ALL}  {name_[:40]:40}  ${price}")
        else:
            err("Tidak ada data saham yang ditemukan!")
    else:
        url = ask("Masukkan URL halaman saham")
        if not url:
            err("URL kosong!")
        else:
            info(f"Scraping via SSR Parser: {url}")
            data = technique_ssr_parser(url)
            if not data:
                info("SSR tidak ditemukan, mencoba DOM extraction...")
                data = technique_dom_extraction(url)
            if data:
                path = os.path.join(OUTPUT_DIR, f"saham_custom_{timestamp}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                show_result("SAHAM CUSTOM BERHASIL", path, 1)
            else:
                err("Tidak ada data yang ditemukan!")

    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: CUSTOM URL (SMART AUTO-DETECT)
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_custom():
    """Smart scraper dengan auto-detect teknik terbaik untuk URL apapun."""
    print_header("⑤ SCRAPE URL CUSTOM")

    print(f"""  {Fore.CYAN}Teknik yang tersedia:{Style.RESET_ALL}

    {Fore.YELLOW}auto{Style.RESET_ALL}    — Auto-detect teknik terbaik (direkomendasikan)
    {Fore.YELLOW}direct{Style.RESET_ALL}  — ① Direct Request + BeautifulSoup (cepat, tanpa browser)
    {Fore.YELLOW}capture{Style.RESET_ALL} — ② Network Capture Playwright (intercept XHR/API)
    {Fore.YELLOW}dom{Style.RESET_ALL}     — ③ DOM Extraction Playwright (konten JS-rendered)
    {Fore.YELLOW}ssr{Style.RESET_ALL}     — ④ SSR Parser Next.js / Nuxt (paling cepat)
    {Fore.YELLOW}main{Style.RESET_ALL}    — Jalankan main.py (pipeline lengkap semua layer)
""")

    url = ask("URL yang akan di-scrape")
    if not url:
        warn("URL kosong, batal.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    technique = ask("Teknik (auto/direct/capture/dom/ssr/main)", "auto")

    info(f"Target: {url}")
    info(f"Teknik: {technique}")
    print()

    timestamp = int(time.time())
    data = None

    if technique == "main":
        subprocess.run([sys.executable, "main.py", url],
                       cwd=os.path.dirname(os.path.abspath(__file__)))
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    elif technique == "direct":
        data = technique_direct_request(url)

    elif technique == "capture":
        info("Membuka browser headless (Network Capture)...")
        data = technique_network_capture(url)

    elif technique == "dom":
        info("Membuka browser headless (DOM Extraction)...")
        data = technique_dom_extraction(url)

    elif technique == "ssr":
        info("Mencoba SSR parser (tanpa browser)...")
        data = technique_ssr_parser(url)
        if not data:
            warn("SSR tidak ditemukan. Mencoba Network Capture sebagai fallback...")
            data = technique_network_capture(url)

    else:  # auto
        info("Auto-detect: mencoba SSR parser dulu (paling cepat)...")
        data = technique_ssr_parser(url)
        if data:
            ok("SSR parser berhasil!")
        else:
            warn("SSR tidak ada, mencoba Direct Request...")
            data = technique_direct_request(url)
            if data and (data.get("tables") or data.get("links")):
                ok("Direct Request berhasil!")
            else:
                warn("Direct Request kurang data, mencoba DOM Extraction (browser)...")
                data = technique_dom_extraction(url)

    if data:
        domain_slug = _domain(url).replace(".", "_")
        out_path = os.path.join(OUTPUT_DIR, f"custom_{domain_slug}_{timestamp}.json")
        output = {
            "metadata": {"url": url, "scrape_date": datetime.now().isoformat(),
                         "technique": technique},
            "data": data
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        size = round(os.path.getsize(out_path) / 1024, 1)
        show_result(f"SCRAPING SELESAI ({technique})", os.path.abspath(out_path), 1)
        info(f"Ukuran file: {size} KB")
    else:
        err("Tidak ada data yang berhasil diekstrak dari URL tersebut.")

    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPE ALL
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_all():
    """Jalankan semua scraper sekaligus menggunakan teknik langsung."""
    print_header("⑥ SCRAPE ALL — SEMUA SEKALIGUS")

    warn("Mode ini akan menjalankan semua scraper secara berurutan.")
    warn("Estimasi waktu: ~5-10 menit total.")
    confirm = ask("Lanjutkan? (y/n)", "y")
    if confirm.lower() != "y":
        return

    tasks = [
        ("① Harga Emas",                 "emas"),
        ("② Cryptocurrency",              "crypto"),
        ("③ Berita (Kompas.com)",          "berita"),
        ("④ Saham US (Pluang)",           "saham"),
        ("⑤ Mata Uang (TradingEconomics)","currency"),
    ]

    results = []
    total = len(tasks)

    for i, (name, category) in enumerate(tasks, 1):
        head(f"[{i}/{total}] {name}")
        t0 = time.time()
        try:
            if category == "emas":
                # Direct request untuk semua sumber emas
                for src_name, src_url in [("Harga-Emas.org", "https://harga-emas.org/"),
                                           ("Galeri24", "https://galeri24.co.id/")]:
                    info(f"  Scraping {src_name}...")
                    data = technique_direct_request(src_url, category="emas")
                    if data and data.get("tables"):
                        ts = int(time.time())
                        path = os.path.join(OUTPUT_DIR, f"emas_{_domain(src_url).replace('.','_')}_{ts}.json")
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump({"metadata": {"source": src_url, "scrape_date": datetime.now().isoformat()},
                                       "data": data}, f, ensure_ascii=False, indent=2)
                        ok(f"  {src_name}: {len(data['tables'])} tabel → {path}")

            elif category == "crypto":
                info(f"  Scraping CoinMarketCap via Network Capture...")
                nc_data = technique_network_capture("https://coinmarketcap.com/")
                if nc_data and nc_data.get("captured_apis"):
                    ts = int(time.time())
                    path = os.path.join(OUTPUT_DIR, f"crypto_coinmarketcap_{ts}.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(nc_data, f, ensure_ascii=False, indent=2)
                    ok(f"  {len(nc_data['captured_apis'])} API endpoint tertangkap → {path}")

            elif category == "berita":
                info(f"  Scraping Kompas.com via DOM Extraction...")
                dom = technique_dom_extraction("https://www.kompas.com/")
                if dom and dom.get("articles"):
                    ts = int(time.time())
                    path = os.path.join(OUTPUT_DIR, f"berita_kompas_{ts}.json")
                    arts = [a for a in dom["articles"] if _is_article_url(a.get("url", ""))]
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"metadata": {"scrape_date": datetime.now().isoformat(), "count": len(arts)},
                                   "articles": arts}, f, ensure_ascii=False, indent=2)
                    ok(f"  {len(arts)} artikel ditemukan → {path}")

            elif category == "saham":
                info(f"  Scraping Pluang via SSR Parser...")
                all_stocks = []
                for pg in range(1, 65):
                    url = f"https://pluang.com/saham-as?page={pg}" if pg > 1 else "https://pluang.com/saham-as"
                    data = technique_ssr_parser(url)
                    if not data:
                        break
                    try:
                        stocks = data.get("props", {}).get("pageProps", {}).get("stocks", [])
                        if stocks:
                            all_stocks.extend(stocks)
                        else:
                            break
                    except Exception:
                        break
                if all_stocks:
                    ts = int(time.time())
                    path = os.path.join(OUTPUT_DIR, f"pluang_all_stocks_{ts}.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"metadata": {"total_stocks_found": len(all_stocks)},
                                   "stocks": all_stocks}, f, ensure_ascii=False, indent=2)
                    ok(f"  {len(all_stocks)} ticker → {path}")

            elif category == "currency":
                info(f"  Scraping TradingEconomics via DOM Extraction...")
                dom = technique_dom_extraction("https://id.tradingeconomics.com/currencies",
                                                selectors=["table"])
                if dom and dom.get("tables"):
                    ts = int(time.time())
                    path = os.path.join(OUTPUT_DIR, f"tradingeconomics_currencies_{ts}.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(dom, f, ensure_ascii=False, indent=2)
                    ok(f"  {len(dom['tables'])} tabel → {path}")

            elapsed = round(time.time() - t0, 1)
            ok(f"Selesai dalam {elapsed}s")
            results.append((name, "✓ OK", elapsed))

        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            err(f"Error: {e}")
            results.append((name, f"✗ {e}", elapsed))

    # Ringkasan
    head("RINGKASAN HASIL")
    print()
    for name, status, elapsed in results:
        color = Fore.GREEN if "OK" in status else Fore.RED
        print(f"  {color}{status}{Style.RESET_ALL}  {name} ({elapsed}s)")

    print()
    ok(f"Scrape All selesai! Lihat folder {Fore.CYAN}hasil_scrape/{Style.RESET_ALL}")
    input(f"\n  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# API SERVER
# ══════════════════════════════════════════════════════════════════════════════

def run_api_server():
    """Jalankan Flask API server."""
    print_header("⑦ API SERVER")

    info("Menjalankan Flask API Server di http://localhost:5000")
    info("Tekan Ctrl+C untuk menghentikan.")
    print()

    print(f"  {Fore.CYAN}Endpoint tersedia:{Style.RESET_ALL}")
    endpoints = [
        ("GET",  "/api/status",                "Status server"),
        ("GET",  "/api/stocks",                "Semua saham AS"),
        ("GET",  "/api/stocks/<symbol>",       "Detail saham (contoh: /api/stocks/AAPL)"),
        ("GET",  "/api/gold",                  "Harga emas semua provider"),
        ("GET",  "/api/news",                  "Berita Kompas.com"),
        ("GET",  "/api/currencies",            "Mata uang TradingEconomics"),
        ("GET",  "/api/crypto",                "Data crypto"),
        ("POST", "/api/convert/word-to-pdf",   "Konversi Word → PDF"),
    ]
    for method, path, desc in endpoints:
        color = Fore.GREEN if method == "GET" else Fore.YELLOW
        print(f"    {color}{method:4}{Style.RESET_ALL}  {Fore.CYAN}{path:<35}{Style.RESET_ALL} {desc}")

    print()
    try:
        subprocess.run(
            [sys.executable, "api_server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
    except KeyboardInterrupt:
        ok("API Server dihentikan.")

    input(f"\n  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _domain(url: str) -> str:
    """Ekstrak domain dari URL."""
    match = re.search(r"(?:https?://)?(?:www\.)?([^/]+)", url)
    return match.group(1) if match else "unknown"

def _is_article_url(url: str) -> bool:
    """Cek apakah URL kemungkinan adalah artikel berita."""
    patterns = ["/read/", "/artikel/", "/berita/", "/news/", "/story/",
                "/post/", r"-\d{8}"]
    return any(p in url for p in patterns)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

def show_status_bar():
    """Tampilkan status file output terbaru."""
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json")),
                   key=os.path.getmtime, reverse=True)[:3]
    if files:
        print(f"  {Fore.YELLOW}Output terbaru:{Style.RESET_ALL}")
        for f in files:
            ts  = os.path.getmtime(f)
            dt  = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            sz  = round(os.path.getsize(f) / 1024, 1)
            print(f"    {Fore.CYAN}{dt}{Style.RESET_ALL}  {os.path.basename(f)} ({sz}KB)")
        print()

MENU_OPTIONS = {
    "1": ("🥇  Scrape Harga Emas",        run_scrape_emas),
    "2": ("₿   Scrape Crypto",            run_scrape_crypto),
    "3": ("📰  Scrape Berita",            run_scrape_berita),
    "4": ("📈  Scrape Saham / Stocks",    run_scrape_saham),
    "5": ("🌐  Scrape URL Custom",        run_scrape_custom),
    "6": ("⚡  SCRAPE ALL (Semua Data)", run_scrape_all),
    "7": ("🚀  Jalankan API Server",      run_api_server),
    "0": ("🚪  Keluar",                   None),
}

def main_menu():
    while True:
        clear()
        print(BANNER)
        show_status_bar()

        print(f"  {Fore.CYAN}MENU UTAMA:{Style.RESET_ALL}\n")
        for key, (label, _) in MENU_OPTIONS.items():
            color = Fore.RED if key == "0" else (Fore.MAGENTA if key == "6" else Fore.WHITE)
            bright = Style.BRIGHT if key in ("6",) else ""
            print(f"    {Fore.YELLOW}{key}{Style.RESET_ALL}  {color}{bright}{label}{Style.RESET_ALL}")

        print()
        choice = ask("Masukkan pilihan")

        if choice == "0":
            clear()
            print(f"\n  {Fore.CYAN}Sampai jumpa! 👋{Style.RESET_ALL}\n")
            break
        elif choice in MENU_OPTIONS:
            _, handler = MENU_OPTIONS[choice]
            if handler:
                handler()
        else:
            warn("Pilihan tidak valid. Coba lagi.")
            time.sleep(1)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--all" in sys.argv:
        run_scrape_all()
    elif "--emas" in sys.argv:
        run_scrape_emas()
    elif "--crypto" in sys.argv:
        run_scrape_crypto()
    elif "--berita" in sys.argv:
        run_scrape_berita()
    elif "--saham" in sys.argv:
        run_scrape_saham()
    elif "--api" in sys.argv:
        run_api_server()
    else:
        main_menu()
