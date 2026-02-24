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

def _scrape_single_url(name: str, url: str):
    """Scrape satu URL menggunakan AUTO-DETECT penuh (SSR → Direct → Capture → DOM)."""
    info(f"Scraping [{name}]: {Fore.CYAN}{url}{Style.RESET_ALL}")
    timestamp = int(time.time())
    result = None
    used_technique = ""

    # ── Langkah 1: SSR Parser — Next.js / Nuxt (paling cepat, tanpa browser) ──
    info(f"  → Teknik ①: SSR Parser (Next.js / Nuxt)...")
    ssr = technique_ssr_parser(url)
    if ssr:
        ok(f"  SSR data ditemukan! (__NEXT_DATA__ / __NUXT__)")
        result = {"technique": "ssr_parser", "ssr_data": ssr}
        used_technique = "SSR Parser"
    else:
        # ── Langkah 2: Direct Request + BeautifulSoup (cepat, tanpa browser) ──
        info(f"  → Teknik ②: Direct Request + BeautifulSoup...")
        data = technique_direct_request(url, category="general")
        tables = data.get("tables", []) if data else []
        inline = data.get("inline_json", []) if data else []

        if tables:
            ok(f"  {len(tables)} tabel ditemukan via Direct Request")
            result = {"technique": "direct_request", "tables": tables,
                      "inline_json": inline}
            used_technique = "Direct Request"
        else:
            # ── Langkah 3: Network Capture (browser, intercept XHR/API JSON) ──
            warn(f"  Direct Request kurang data, mencoba Network Capture (browser)...")
            info(f"  → Teknik ③: Network Capture (Intercept XHR/API)...")
            nc_data = technique_network_capture(url)
            captured = nc_data.get("captured_apis", {}) if nc_data else {}
            next_data = nc_data.get("__NEXT_DATA__") if nc_data else None
            nuxt_data = nc_data.get("__NUXT__") if nc_data else None

            if captured or next_data or nuxt_data:
                api_count = len(captured)
                ok(f"  {api_count} API endpoint tertangkap via Network Capture")
                result = {"technique": "network_capture",
                          "captured_apis": captured, "api_count": api_count}
                if next_data:
                    result["__NEXT_DATA__"] = next_data
                if nuxt_data:
                    result["__NUXT__"] = nuxt_data
                used_technique = "Network Capture"
            else:
                # ── Langkah 4: DOM Extraction (browser, konten visible di halaman) ──
                warn(f"  Network Capture tidak menangkap API, mencoba DOM Extraction...")
                info(f"  → Teknik ④: DOM Extraction (visible page content)...")
                dom_data = technique_dom_extraction(
                    url,
                    selectors=["table", '[class*="price"]', '[class*="harga"]',
                               '[class*="card"]', '[class*="product"]', 'article']
                )
                if dom_data and (dom_data.get("tables") or dom_data.get("articles")):
                    t = len(dom_data.get("tables", []))
                    a = len(dom_data.get("articles", []))
                    ok(f"  {t} tabel + {a} item via DOM Extraction")
                    result = {"technique": "dom_extraction", **dom_data}
                    used_technique = "DOM Extraction"

    if not result:
        err(f"  Tidak ada data yang ditemukan dari {url} (semua 4 teknik gagal)")
        return

    # ── Simpan ──
    domain_slug = _domain(url).replace(".", "_")
    out_path = os.path.join(OUTPUT_DIR, f"{domain_slug}_{timestamp}.json")
    out = {
        "metadata": {"url": url, "source": name,
                      "technique_used": used_technique,
                      "scrape_date": datetime.now().isoformat()},
        "data": result
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)

    size = round(os.path.getsize(out_path) / 1024, 1)
    show_result(f"{name} BERHASIL DI-SCRAPE ({used_technique})",
                os.path.abspath(out_path), 1)
    info(f"Ukuran file: {size} KB")

    # ── Preview ──
    head("Preview Data:")
    tbls = result.get("tables", [])
    if tbls:
        for tbl in tbls[:2]:
            rows = tbl.get("rows", [])[:5]
            for row in rows:
                if isinstance(row, dict):
                    vals = " | ".join(f"{v}" for v in list(row.values())[:4])
                else:
                    vals = " | ".join(str(c) for c in row[:4])
                print(f"    {Fore.CYAN}→{Style.RESET_ALL} {vals}")

    apis = result.get("captured_apis", {})
    if apis:
        info(f"  API endpoint yang tertangkap:")
        for api_url in list(apis.keys())[:5]:
            short = api_url[:80] + ("..." if len(api_url) > 80 else "")
            print(f"    {Fore.GREEN}→{Style.RESET_ALL} {short}")

    ssr_d = result.get("ssr_data")
    if ssr_d and isinstance(ssr_d, dict):
        keys = list(ssr_d.get("props", {}).get("pageProps", {}).keys())[:5]
        if keys:
            info(f"  SSR pageProps keys: {', '.join(keys)}")

    arts = result.get("articles", [])
    if arts:
        for a in arts[:5]:
            judul = a.get("judul", "")[:70]
            if judul:
                print(f"    {Fore.CYAN}→{Style.RESET_ALL} {judul}")


def run_scrape_emas():
    """Scrape harga emas — pilih satu sumber."""
    print_header("① SCRAPE HARGA EMAS")

    sources = [
        ("Galeri24",          "https://galeri24.co.id/"),
        ("Harga-Emas.org",    "https://harga-emas.org/"),
        ("Antam Logam Mulia", "https://www.logammulia.com/id/harga-emas-hari-ini"),
    ]

    print(f"  {Fore.CYAN}Pilih sumber:{Style.RESET_ALL}\n")
    for i, (name, url) in enumerate(sources, 1):
        print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}. {name}  {Fore.CYAN}{url}{Style.RESET_ALL}")
    print(f"    {Fore.YELLOW}{len(sources)+1}{Style.RESET_ALL}. Masukkan URL lain...\n")

    choice = ask(f"Pilihan (1-{len(sources)+1})", "1")

    try:
        idx = int(choice) - 1
    except ValueError:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    if 0 <= idx < len(sources):
        name, url = sources[idx]
    elif idx == len(sources):
        url = ask("Masukkan URL sumber harga emas")
        if not url:
            err("URL kosong!")
            input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
            return
        
        default_name = _domain(url).title()
        name = ask(f"Nama sumber [{default_name}]", default_name)
        if not name:
            name = default_name
    else:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    print()
    _scrape_single_url(name, url)
    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: CRYPTO
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_crypto():
    """Scrape cryptocurrency — pilih satu sumber."""
    print_header("② SCRAPE CRYPTOCURRENCY")

    sources = [
        ("CoinMarketCap",   "https://coinmarketcap.com/"),
        ("CoinGecko",       "https://www.coingecko.com/"),
    ]

    print(f"  {Fore.CYAN}Pilih sumber:{Style.RESET_ALL}\n")
    for i, (name, url) in enumerate(sources, 1):
        print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}. {name}  {Fore.CYAN}{url}{Style.RESET_ALL}")
    print(f"    {Fore.YELLOW}{len(sources)+1}{Style.RESET_ALL}. Masukkan URL lain...\n")

    choice = ask(f"Pilihan (1-{len(sources)+1})", "1")

    try:
        idx = int(choice) - 1
    except ValueError:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    if 0 <= idx < len(sources):
        name, url = sources[idx]
    elif idx == len(sources):
        url = ask("Masukkan URL sumber crypto")
        if not url:
            err("URL kosong!")
            input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
            return
            
        default_name = _domain(url).title()
        name = ask(f"Nama sumber [{default_name}]", default_name)
        if not name:
            name = default_name
    else:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    print()
    _scrape_single_url(name, url)
    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: BERITA
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_berita():
    """Scrape berita — pilih satu sumber."""
    print_header("③ SCRAPE BERITA")

    sources = [
        ("Kompas.com",     "https://www.kompas.com/"),
        ("Detik.com",      "https://www.detik.com/"),
        ("CNN Indonesia",  "https://www.cnnindonesia.com/"),
        ("Tribunnews",     "https://www.tribunnews.com/"),
        ("Tempo.co",       "https://tempo.co/"),
        ("Liputan6",       "https://liputan6.com/"),
        ("Antaranews",     "https://www.antaranews.com/"),
    ]

    print(f"  {Fore.CYAN}Pilih sumber berita:{Style.RESET_ALL}\n")
    for i, (name, url) in enumerate(sources, 1):
        print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}. {name}  {Fore.CYAN}{url}{Style.RESET_ALL}")
    print(f"    {Fore.YELLOW}{len(sources)+1}{Style.RESET_ALL}. Masukkan URL lain...\n")

    choice = ask(f"Pilihan (1-{len(sources)+1})", "1")

    try:
        idx = int(choice) - 1
    except ValueError:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    if 0 <= idx < len(sources):
        name, url = sources[idx]
    elif idx == len(sources):
        url = ask("Masukkan URL sumber berita")
        if not url:
            err("URL kosong!")
            input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
            return
            
        default_name = _domain(url).title()
        name = ask(f"Nama sumber [{default_name}]", default_name)
        if not name:
            name = default_name
    else:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    print()
    _scrape_single_url(name, url)
    input(f"  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: SAHAM
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_saham():
    """Scrape data saham — pilih IDX atau Pluang."""
    print_header("④ SCRAPE SAHAM / STOCKS")

    sources = [
        ("Bursa Efek Indonesia (IDX)", "Scrape 900+ saham IHSG & Ringkasan Perdagangan/Broker"),
        ("Pluang (Saham AS)",          "https://pluang.com/saham-as"),
    ]

    print(f"  {Fore.CYAN}Pilih sumber:{Style.RESET_ALL}\n")
    for i, (name, url) in enumerate(sources, 1):
        print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}. {name}  {Fore.CYAN}{url}{Style.RESET_ALL}")
    print(f"    {Fore.YELLOW}{len(sources)+1}{Style.RESET_ALL}. Masukkan URL lain...\n")

    choice = ask(f"Pilihan (1-{len(sources)+1})", "1")

    try:
        idx = int(choice) - 1
    except ValueError:
        err("Pilihan tidak valid.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    if idx == 0:
        # IDX Scraping
        ok("Memulai scraping data dari Bursa Efek Indonesia (IDX)...")
        from scrape_idx import scrape_idx_all
        res = scrape_idx_all()
        if res:
            timestamp = int(time.time())
            out_path = os.path.join(OUTPUT_DIR, f"idx_combined_{timestamp}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
            
            size = round(os.path.getsize(out_path) / 1024, 1)
            show_result("IDX SCRAPE BERHASIL (Metadata + Summary + Broker)", out_path, 1)
            info(f"Ukuran file : {size} KB")
            info(f"Total Saham : {res['metadata']['total_stocks']}")
            info(f"Total Broker: {res['metadata']['total_brokers']}")
        else:
            err("Gagal scrape data IDX.")
            
    elif idx == 1:
        # Pluang Scraping
        name, url = sources[1]
        print()
        _scrape_single_url("Pluang", url, technique="ssr")  # Pluang bagus pakai SSR

    elif idx == len(sources):
        url = ask("Masukkan URL sumber data saham")
        if not url:
            err("URL kosong!")
            input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
            return
        
        default_name = _domain(url).title()
        name = ask(f"Nama sumber [{default_name}]", default_name)
        if not name:
            name = default_name
            
        print()
        _scrape_single_url(name, url)
        
    else:
        err("Pilihan tidak valid.")

    input(f"\n  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER KHUSUS: CUSTOM URL (SMART AUTO-DETECT)
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_custom():
    """Smart scraper dengan auto-detect teknik terbaik untuk URL apapun."""
    print_header("⑤ SCRAPE URL CUSTOM")

    print(f"""  {Fore.CYAN}Teknik yang tersedia:{Style.RESET_ALL}
    {Fore.YELLOW}Auto-detect{Style.RESET_ALL} — Pipeline lengkap (Direct -> Network Capture -> DOM -> Dekripsi -> JS Extractor)
""")

    url = ask("URL yang akan di-scrape")
    if not url:
        warn("URL kosong, batal.")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    info(f"Target: {url}")
    print()

    # Jalankan pipeline utama dari main.py
    try:
        subprocess.run([sys.executable, "main.py", url],
                       cwd=os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        err(f"Gagal menjalankan scraper: {e}")

    input(f"\n  {Fore.YELLOW}[Enter untuk kembali ke menu]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPE ALL
# ══════════════════════════════════════════════════════════════════════════════

def run_scrape_all():
    """Jalankan semua scraper sekaligus menggunakan pipeline main.py."""
    print_header("⑥ SCRAPE ALL — SEMUA SEKALIGUS")

    warn("Mode ini akan menjalankan scraper pipeline ke beberapa target utama.")
    warn("Estimasi waktu: ~2-5 menit total.")
    confirm = ask("Lanjutkan? (y/n)", "y")
    if confirm.lower() != "y":
        return

    targets = [
        ("① Galeri24 (Harga Emas)",      "https://galeri24.co.id/"),
        ("② CoinMarketCap (Crypto)",   "https://coinmarketcap.com/"),
        ("③ Kompas.com (Berita)",       "https://www.kompas.com/"),
        ("④ Pluang (Saham)",            "https://pluang.com/saham-as"),
        ("⑤ TradingEconomics (Forex)",  "https://id.tradingeconomics.com/currencies"),
    ]

    results = []
    total = len(targets)

    for i, (name, url) in enumerate(targets, 1):
        head(f"[{i}/{total}] Scraping {name}...")
        t0 = time.time()
        try:
            print(f"  {Fore.CYAN}→ URL: {url}{Style.RESET_ALL}\n")
            # Call main.py process
            res = subprocess.run([sys.executable, "main.py", url],
                                 cwd=os.path.dirname(os.path.abspath(__file__)))
            
            elapsed = round(time.time() - t0, 1)
            if res.returncode == 0:
                ok(f"Selesai dalam {elapsed}s")
                results.append((name, "✓ OK", elapsed))
            else:
                err(f"Gagal dalam {elapsed}s (Exit code: {res.returncode})")
                results.append((name, "✗ GAGAL", elapsed))

        except Exception as e:
            elapsed = round(time.time() - t0, 1)
            err(f"Error: {e}")
            results.append((name, f"✗ {e}", elapsed))

    # Ringkasan
    head("RINGKASAN HASIL")
    print()
    for name, status, elapsed in results:
        color = Fore.GREEN if "OK" in status else Fore.RED
        print(f"  {color}{status:<8}{Style.RESET_ALL} {name} ({elapsed}s)")

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
# SCRAPE FILM (Menu 9)
# ══════════════════════════════════════════════════════════════════════════════

def _estimate_time(num_films: int, with_episodes: bool) -> str:
    """Hitung estimasi waktu scraping."""
    # Benchmarks dari test: 30 film/listing-page, ~1s/page, ~1s/detail, ~2.5s/ep, avg 10 ep/film
    pages = (num_films + 29) // 30  # 30 film per halaman
    listing_sec = pages * 1.5
    detail_sec = num_films * 1.2
    episode_sec = num_films * 10 * 2.5 if with_episodes else 0  # avg 10 ep/film

    total_sec = listing_sec + detail_sec + episode_sec
    if total_sec < 60:
        return f"{int(total_sec)} detik"
    elif total_sec < 3600:
        return f"{int(total_sec // 60)} menit {int(total_sec % 60)} detik"
    else:
        hours = int(total_sec // 3600)
        mins = int((total_sec % 3600) // 60)
        return f"{hours} jam {mins} menit"


def _run_drakorkita_submenu():
    """Sub-menu DrakorKita dengan estimasi waktu."""
    print(f"""
  {Fore.CYAN}Menu DrakorKita:{Style.RESET_ALL}

    {Fore.YELLOW}1{Style.RESET_ALL}. Quick Scrape — 1 judul (masukkan URL)
    {Fore.YELLOW}2{Style.RESET_ALL}. Scrape Banyak Film — Pilih jumlah film
    {Fore.YELLOW}3{Style.RESET_ALL}. Filter Genre — Pilih genre tertentu
    {Fore.YELLOW}0{Style.RESET_ALL}. Kembali
""")
    choice = ask("Pilihan (0-3)", "2")

    try:
        from scrape_drakorkita import quick_scrape, run_full_scrape
    except ImportError as e:
        err(f"Gagal import scrape_drakorkita: {e}")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    if choice == "0":
        return

    elif choice == "1":
        url = ask("URL detail drama (contoh: https://drakorkita3.nicewap.sbs/detail/...)")
        if not url:
            err("URL kosong!")
            return
        with_eps = ask("Scrape video embed per episode? (y/n)", "y").lower() == "y"

        # Estimasi 1 judul
        est = _estimate_time(1, with_eps)
        print(f"\n  {Fore.CYAN}⏱  Estimasi waktu: {Fore.WHITE}{Style.BRIGHT}{est}{Style.RESET_ALL}")
        confirm = ask("Lanjutkan? (y/n)", "y")
        if confirm.lower() != "y":
            info("Dibatalkan.")
            return

        print()
        result = quick_scrape(url, with_episodes=with_eps)
        if result:
            ok(f"Judul: {result.get('title', '?')}")
            ok(f"Episode: {result.get('total_episodes', 0)}")
            ok(f"Genre: {', '.join(result.get('genres', []))}")
            ok(f"Cast: {', '.join(result.get('cast', [])[:5])}")
            if result.get("sinopsis"):
                head("Sinopsis:")
                print(f"    {result['sinopsis'][:200]}...")

    elif choice == "2":
        # ── Pilih jumlah film ──
        print(f"""
  {Fore.CYAN}Pilih jumlah film:{Style.RESET_ALL}

    {Fore.YELLOW}1{Style.RESET_ALL}. 30 film     (1 halaman)
    {Fore.YELLOW}2{Style.RESET_ALL}. 100 film    (4 halaman)
    {Fore.YELLOW}3{Style.RESET_ALL}. 500 film    (17 halaman)
    {Fore.YELLOW}4{Style.RESET_ALL}. 1000 film   (34 halaman)
    {Fore.YELLOW}5{Style.RESET_ALL}. SEMUA       (~11.779 judul, ~400 halaman)
    {Fore.YELLOW}6{Style.RESET_ALL}. Custom      (masukkan jumlah sendiri)
""")
        qty_choice = ask("Pilihan (1-6)", "1")
        presets = {"1": 30, "2": 100, "3": 500, "4": 1000, "5": 0}

        if qty_choice in presets:
            num_films = presets[qty_choice]
        elif qty_choice == "6":
            custom = ask("Masukkan jumlah film yang ingin di-scrape")
            try:
                num_films = int(custom)
                if num_films <= 0:
                    raise ValueError
            except ValueError:
                err("Jumlah tidak valid!")
                return
        else:
            err("Pilihan tidak valid!")
            return

        # ── Pilih apakah scrape video embed ──
        with_eps = ask("Scrape video embed per episode? (y/n)", "y").lower() == "y"

        # ── Hitung estimasi ──
        display_num = "SEMUA (~11.779)" if num_films == 0 else str(num_films)
        actual_for_est = num_films if num_films > 0 else 11779
        pages = (actual_for_est + 29) // 30

        est_without = _estimate_time(actual_for_est, False)
        est_with = _estimate_time(actual_for_est, True)
        est = est_with if with_eps else est_without

        print(f"""
  {Fore.CYAN}╔══════════════════════════════════════════════════════╗
  ║  📊 ESTIMASI SCRAPING                                ║
  ╠══════════════════════════════════════════════════════╣{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  Jumlah film     : {Fore.WHITE}{Style.BRIGHT}{display_num:>10}{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  Halaman listing  : {Fore.WHITE}{pages:>10}{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  Video per episode : {Fore.WHITE}{'Ya' if with_eps else 'Tidak':>10}{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}                                                      {Fore.CYAN}║{Style.RESET_ALL}""")

        if with_eps:
            print(f"  {Fore.CYAN}║{Style.RESET_ALL}  {Fore.YELLOW}Tahap 1:{Style.RESET_ALL} Crawl listing       ~{int(pages*1.5):>5} detik         {Fore.CYAN}║{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}║{Style.RESET_ALL}  {Fore.YELLOW}Tahap 2:{Style.RESET_ALL} Detail per judul     ~{int(actual_for_est*1.2):>5} detik         {Fore.CYAN}║{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}║{Style.RESET_ALL}  {Fore.YELLOW}Tahap 3:{Style.RESET_ALL} Video embed episode  ~{int(actual_for_est*25):>5} detik         {Fore.CYAN}║{Style.RESET_ALL}")
        else:
            print(f"  {Fore.CYAN}║{Style.RESET_ALL}  {Fore.YELLOW}Tahap 1:{Style.RESET_ALL} Crawl listing       ~{int(pages*1.5):>5} detik         {Fore.CYAN}║{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}║{Style.RESET_ALL}  {Fore.YELLOW}Tahap 2:{Style.RESET_ALL} Detail per judul     ~{int(actual_for_est*1.2):>5} detik         {Fore.CYAN}║{Style.RESET_ALL}")

        print(f"""  {Fore.CYAN}║{Style.RESET_ALL}                                                      {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  ⏱  {Fore.WHITE}{Style.BRIGHT}ESTIMASI TOTAL: {est:>20}{Style.RESET_ALL}          {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")

        confirm = ask(f"Mulai scraping {display_num} film? (y/n)", "y")
        if confirm.lower() != "y":
            info("Scraping dibatalkan.")
            return

        print()
        ok("🚀 Mulai scraping...")
        print()

        run_full_scrape(
            max_pages=pages if num_films > 0 else None,
            max_details=num_films if num_films > 0 else None,
            scrape_episodes=with_eps,
        )

    elif choice == "3":
        genres = ["Action", "Adventure", "Comedy", "Crime", "Drama", "Family",
                  "Fantasy", "Horror", "Mystery", "Romance", "Sci-Fi", "Thriller"]
        print(f"\n  {Fore.CYAN}Genre tersedia:{Style.RESET_ALL}")
        for i, g in enumerate(genres, 1):
            print(f"    {Fore.YELLOW}{i:>2}{Style.RESET_ALL}. {g}")
        g_choice = ask(f"Pilih genre (1-{len(genres)})", "1")
        try:
            genre = genres[int(g_choice) - 1]
        except (ValueError, IndexError):
            err("Pilihan tidak valid.")
            return

        num_films_str = ask("Berapa judul yang ingin di-scrape? (kosong = semua)", "30")
        try:
            num_films = int(num_films_str) if num_films_str else 0
        except ValueError:
            num_films = 30

        with_eps = ask("Scrape video embed per episode? (y/n)", "y").lower() == "y"

        actual = num_films if num_films > 0 else 500
        est = _estimate_time(actual, with_eps)
        pages = (actual + 29) // 30

        print(f"\n  {Fore.CYAN}⏱  Estimasi: {Fore.WHITE}{Style.BRIGHT}{est}{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}Genre: {Fore.WHITE}{genre}{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}Jumlah: {Fore.WHITE}{num_films if num_films > 0 else 'Semua'}{Style.RESET_ALL}")

        confirm = ask("\nMulai? (y/n)", "y")
        if confirm.lower() != "y":
            info("Dibatalkan.")
            return

        print()
        run_full_scrape(
            max_pages=pages if num_films > 0 else None,
            max_details=num_films if num_films > 0 else None,
            filter_params={"genre": genre},
            scrape_episodes=with_eps,
        )


def _run_custom_film_scrape():
    """Scrape film/drama dari URL lain (bukan DrakorKita)."""
    url = ask("Masukkan URL situs film/drama")
    if not url:
        err("URL kosong!")
        return

    name = ask("Nama sumber (kosong = otomatis dari domain)", "")
    if not name:
        match = re.search(r"(?:https?://)?(?:www\.)?([^/]+)", url)
        name = match.group(1).replace(".", "_").title() if match else "Custom_Film"

    print()
    info(f"Scraping film dari: {Fore.CYAN}{url}{Style.RESET_ALL}")
    info(f"Nama sumber: {name}")
    print()

    _scrape_single_url(f"Film_{name}", url)


def _run_zeldaeternity_submenu():
    """Sub-menu ZeldaEternity (INDOFILM)."""
    print(f"""
  {Fore.CYAN}Menu ZeldaEternity (INDOFILM):{Style.RESET_ALL}

    {Fore.YELLOW}1{Style.RESET_ALL}. Quick Scrape — 1 judul (masukkan URL)
    {Fore.YELLOW}2{Style.RESET_ALL}. Scrape Banyak Film — Pilih jumlah
    {Fore.YELLOW}3{Style.RESET_ALL}. Filter Kategori — Movie / Anime / Donghua / Serial TV
    {Fore.YELLOW}0{Style.RESET_ALL}. Kembali
""")
    choice = ask("Pilihan (0-3)", "2")

    try:
        from scrape_zeldaeternity import quick_scrape, run_full_scrape
    except ImportError as e:
        err(f"Gagal import scrape_zeldaeternity: {e}")
        input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
        return

    if choice == "0":
        return

    elif choice == "1":
        url = ask("URL detail film/series (contoh: https://zeldaeternity.com/the-housemaid-2025-2/)")
        if not url:
            err("URL kosong!")
            return
        with_eps = ask("Scrape video/download per episode? (y/n)", "y").lower() == "y"
        est = _estimate_time(1, with_eps)
        print(f"\n  {Fore.CYAN}⏱  Estimasi: {Fore.WHITE}{Style.BRIGHT}{est}{Style.RESET_ALL}")
        confirm = ask("Lanjutkan? (y/n)", "y")
        if confirm.lower() != "y":
            info("Dibatalkan.")
            return
        print()
        result = quick_scrape(url, with_episodes=with_eps)
        if result:
            ok(f"Judul: {result.get('title', '?')}")
            ok(f"Tipe: {result.get('type', '?')}")
            ok(f"Genre: {', '.join(result.get('genres', []))}")
            ok(f"Episode: {result.get('total_episodes', 0)}")
            if result.get("download_links"):
                ok(f"Download: {len(result['download_links'])} link")
            if result.get("sinopsis"):
                head("Sinopsis:")
                print(f"    {result['sinopsis'][:200]}...")

    elif choice == "2":
        print(f"""
  {Fore.CYAN}Pilih jumlah film:{Style.RESET_ALL}

    {Fore.YELLOW}1{Style.RESET_ALL}. 30 film     (1-2 halaman)
    {Fore.YELLOW}2{Style.RESET_ALL}. 100 film    (5-6 halaman)
    {Fore.YELLOW}3{Style.RESET_ALL}. 500 film    (25 halaman)
    {Fore.YELLOW}4{Style.RESET_ALL}. 1000 film   (50 halaman)
    {Fore.YELLOW}5{Style.RESET_ALL}. SEMUA
    {Fore.YELLOW}6{Style.RESET_ALL}. Custom
""")
        qty_choice = ask("Pilihan (1-6)", "1")
        presets = {"1": 30, "2": 100, "3": 500, "4": 1000, "5": 0}

        if qty_choice in presets:
            num_films = presets[qty_choice]
        elif qty_choice == "6":
            custom = ask("Masukkan jumlah film")
            try:
                num_films = int(custom)
                if num_films <= 0:
                    raise ValueError
            except ValueError:
                err("Jumlah tidak valid!")
                return
        else:
            err("Pilihan tidak valid!")
            return

        with_eps = ask("Scrape video/download per episode? (y/n)", "y").lower() == "y"

        display_num = "SEMUA" if num_films == 0 else str(num_films)
        actual = num_films if num_films > 0 else 5000
        pages = (actual + 19) // 20  # ~20 film/page

        est = _estimate_time(actual, with_eps)
        print(f"""
  {Fore.CYAN}╔══════════════════════════════════════════════════════╗
  ║  📊 ESTIMASI SCRAPING INDOFILM                       ║
  ╠══════════════════════════════════════════════════════╣{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  Jumlah film     : {Fore.WHITE}{Style.BRIGHT}{display_num:>10}{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  Video/download  : {Fore.WHITE}{'Ya' if with_eps else 'Tidak':>10}{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}║{Style.RESET_ALL}  ⏱  {Fore.WHITE}{Style.BRIGHT}ESTIMASI: {est:>24}{Style.RESET_ALL}          {Fore.CYAN}║{Style.RESET_ALL}
  {Fore.CYAN}╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")

        confirm = ask(f"Mulai scraping {display_num} film? (y/n)", "y")
        if confirm.lower() != "y":
            info("Dibatalkan.")
            return

        print()
        ok("🚀 Mulai scraping...")
        print()

        run_full_scrape(
            max_pages=pages if num_films > 0 else None,
            max_details=num_films if num_films > 0 else None,
            scrape_episodes=with_eps,
        )

    elif choice == "3":
        categories = [
            ("box-office", "Box Office"),
            ("movie", "Movie"),
            ("anime", "Anime"),
            ("donghua", "Donghua"),
            ("serial-tv", "Serial TV"),
            ("animasi", "Animasi"),
        ]
        print(f"\n  {Fore.CYAN}Kategori:{Style.RESET_ALL}")
        for i, (_, label) in enumerate(categories, 1):
            print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}. {label}")
        cat_choice = ask(f"Pilih (1-{len(categories)})", "1")
        try:
            cat_slug, cat_name = categories[int(cat_choice) - 1]
        except (ValueError, IndexError):
            err("Pilihan tidak valid.")
            return

        num_str = ask("Berapa judul? (kosong = semua)", "30")
        try:
            num = int(num_str) if num_str else 0
        except ValueError:
            num = 30

        with_eps = ask("Scrape video/download per episode? (y/n)", "y").lower() == "y"

        actual = num if num > 0 else 500
        est = _estimate_time(actual, with_eps)
        print(f"\n  {Fore.CYAN}⏱  Estimasi: {Fore.WHITE}{Style.BRIGHT}{est}{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}Kategori: {Fore.WHITE}{cat_name}{Style.RESET_ALL}")

        confirm = ask("\nMulai? (y/n)", "y")
        if confirm.lower() != "y":
            return

        print()
        pages = (actual + 19) // 20
        run_full_scrape(
            max_pages=pages if num > 0 else None,
            max_details=num if num > 0 else None,
            scrape_episodes=with_eps,
            category_url=f"https://zeldaeternity.com/category/{cat_slug}/",
        )


def _save_azarug_result(res):
    if res and res.get("data"):
        timestamp = int(time.time())
        out_path = os.path.join(OUTPUT_DIR, f"azarug_{timestamp}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
            
        size = round(os.path.getsize(out_path) / 1024, 1)
        show_result("AZARUG SCRAPE BERHASIL", out_path, 1)
        info(f"Ukuran file : {size} KB")
        info(f"Total Film  : {res['metadata']['total_items']}")
    else:
        err("Scraping gagal atau tidak menemukan film.")

def _run_azarug_submenu():
    """Submenu interaktif khusus untuk Azarug."""
    print_header("🎬 AZARUG SCRAPER")
    
    print(f"""
  Menu Azarug:

    {Fore.YELLOW}1{Style.RESET_ALL}. Quick Scrape — 1 judul (masukkan URL)
    {Fore.YELLOW}2{Style.RESET_ALL}. Scrape Banyak Film — Pilih jumlah
    {Fore.YELLOW}3{Style.RESET_ALL}. Filter Kategori — Movie / TV Series / Genre
    {Fore.YELLOW}0{Style.RESET_ALL}. Kembali
""")

    choice = ask("Pilihan (0-3)", "2")

    if choice == "0":
        return
        
    elif choice == "1":
        url = ask("Masukkan URL detail film Azarug")
        if not url:
            return
        from scrape_azarug import scrape_azarug
        res = scrape_azarug(url, limit=1, max_pages=1, show_progress=True)
        _save_azarug_result(res)

    elif choice == "2":
        url = "https://azarug.org/"
        presets = {
            "1": {"label": "30 film", "count": 30, "pages": 2},
            "2": {"label": "100 film", "count": 100, "pages": 6},
            "3": {"label": "Semua / Custom", "count": 0, "pages": 0}
        }
        
        print(f"\n  {Fore.CYAN}Pilih batas jumlah film:{Style.RESET_ALL}")
        for k, v in presets.items():
            print(f"    {Fore.YELLOW}{k}{Style.RESET_ALL}. {v['label']} " + (f"(max {v['pages']} halaman)" if v['pages'] else ""))
            
        qty_choice = ask("Pilihan", "1")
        if qty_choice not in presets:
            err("Pilihan tidak valid")
            return
            
        if qty_choice == "3":
            custom_str = ask("Masukkan jumlah film khusus (contoh: 500)", "500")
            try:
                num = int(custom_str)
            except ValueError:
                num = 500
            pages = (num + 19) // 20
        else:
            num = presets[qty_choice]["count"]
            pages = presets[qty_choice]["pages"]
        
        print(f"\n  {Fore.CYAN}Mulai mengekstrak {num} film dari {url}...{Style.RESET_ALL}")
        
        from scrape_azarug import scrape_azarug
        res = scrape_azarug(url, limit=num, max_pages=pages, show_progress=True)
        _save_azarug_result(res)

    elif choice == "3":
        categories = [
            ("movie", "Movie"),
            ("tv-series", "TV Series"),
            ("korean", "Drama Korea"),
            ("anime", "Anime"),
            ("action", "Action"),
        ]
        print(f"\n  {Fore.CYAN}Kategori / Genre:{Style.RESET_ALL}")
        for i, (_, label) in enumerate(categories, 1):
            print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}. {label}")
        cat_choice = ask(f"Pilih (1-{len(categories)})", "1")
        try:
            cat_slug, cat_name = categories[int(cat_choice) - 1]
        except (ValueError, IndexError):
            err("Pilihan tidak valid.")
            return

        num_str = ask("Berapa judul? (kosong = 30)", "30")
        try:
            num = int(num_str) if num_str else 30
        except ValueError:
            num = 30

        url = f"https://azarug.org/category/{cat_slug}/"
        if cat_slug in ["action", "anime"]:
             url = f"https://azarug.org/genre/{cat_slug}/"
             
        pages = (num + 19) // 20
        
        print(f"\n  {Fore.CYAN}Mulai mengekstrak {num} film dari {url}...{Style.RESET_ALL}")
        
        from scrape_azarug import scrape_azarug
        res = scrape_azarug(url, limit=num, max_pages=pages, show_progress=True)
        _save_azarug_result(res)


def run_scrape_film():
    """Menu utama Scrape Film."""
    print_header("🎬 SCRAPE FILM / DRAMA / SERIES")

    print(f"""  {Fore.CYAN}Pilih sumber film:{Style.RESET_ALL}

    {Fore.YELLOW}1{Style.RESET_ALL}. 🎭  DrakorKita — Drama Korea, Jepang, China, dll
                 (drakorkita3.nicewap.sbs — 11.779 judul)
    {Fore.YELLOW}2{Style.RESET_ALL}. 🎬  ZeldaEternity (INDOFILM) — Film, Anime, Donghua, Series
                 (zeldaeternity.com — Ribuan judul)
    {Fore.YELLOW}3{Style.RESET_ALL}. 🍿  Azarug — Film & Series (Standard WP Theme)
                 (azarug.org — Ribuan judul)
    {Fore.YELLOW}4{Style.RESET_ALL}. 🌐  Link Lainnya — Scrape murni dari URL situs film lain
    {Fore.YELLOW}0{Style.RESET_ALL}. 🔙  Kembali
""")

    choice = ask("Pilihan (0-4)", "1")

    if choice == "0":
        return
    elif choice == "1":
        _run_drakorkita_submenu()
    elif choice == "2":
        _run_zeldaeternity_submenu()
    elif choice == "3":
        _run_azarug_submenu()
    elif choice == "4":
        _run_custom_film_scrape()
    else:
        err("Pilihan tidak valid.")

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
# ══════════════════════════════════════════════════════════════════════════════
# LIHAT HASIL SCRAPE
# ══════════════════════════════════════════════════════════════════════════════

def run_view_results():
    """Lihat dan jelajahi hasil scraping yang tersimpan — auto-kategorisasi."""

    # ── Definisi kategori berdasarkan pola nama file / folder ──
    CATEGORIES = {
        "🎬 Film / Drama / Series": {
            "patterns": ["drakorkita", "zelda", "indofilm", "azarug", "film_", "drama", "movie", "series"],
            "subdir": "drakorkita",
        },
        "🥇 Harga Emas": {
            "patterns": ["emas", "gold", "galeri24", "logam_mulia"],
        },
        "₿  Cryptocurrency": {
            "patterns": ["crypto", "coinmarketcap", "bitcoin", "coin"],
        },
        "📰 Berita / News": {
            "patterns": ["kompas", "news", "berita", "artikel"],
        },
        "📈 Saham / Stocks": {
            "patterns": ["saham", "stock", "pluang"],
        },
        "💱 Mata Uang / Currency": {
            "patterns": ["trading", "currency", "forex", "kurs"],
        },
        "📁 Lainnya": {
            "patterns": [],  # catch-all
        },
    }

    def _categorize_file(filepath):
        """Tentukan kategori file berdasarkan nama."""
        fname = os.path.basename(filepath).lower()
        parent = os.path.dirname(filepath).lower()
        fullpath = os.path.join(parent, fname)

        for cat_name, cat_info in CATEGORIES.items():
            if cat_name == "📁 Lainnya":
                continue
            # Cek subdir
            subdir = cat_info.get("subdir", "")
            if subdir and subdir in fullpath:
                return cat_name
            # Cek patterns
            for pat in cat_info.get("patterns", []):
                if pat in fname or pat in parent:
                    return cat_name
        return "📁 Lainnya"

    def _collect_all_files():
        """Kumpulkan semua JSON dari OUTPUT_DIR dan subdirektori."""
        all_files = []
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for f in files:
                if f.endswith(".json") and not f.startswith("."):
                    all_files.append(os.path.join(root, f))
        return sorted(all_files, key=os.path.getmtime, reverse=True)

    def _show_drama_detail(data, filepath):
        """Tampilkan detail lengkap film/drama."""
        # Cek apakah ini file listing atau full detail
        dramas = data.get("dramas", [])
        if not dramas:
            # Cek key 'data' dari output Azarug / scraper generik
            inner_data = data.get("data", [])
            if isinstance(inner_data, list):
                dramas = inner_data

        if not dramas and isinstance(data, dict):
            # Mungkin single drama
            if data.get("title"):
                dramas = [data]

        if not dramas:
            # Tampilkan raw utuh tanpa dipotong
            head("Data JSON Mentah (Seluruhnya):")
            print(f"    {json.dumps(data, indent=2, ensure_ascii=False)}")
            return

        head(f"Total: {len(dramas)} judul")
        print()

        page = 0
        per_page = 10
        while True:
            start = page * per_page
            end = min(start + per_page, len(dramas))

            for i, d in enumerate(dramas[start:end], start + 1):
                title = d.get("title", "?")
                eps = d.get("total_episodes", 0)
                genres = ", ".join(d.get("genres", []))
                status = d.get("status", "")
                ep_embeds = d.get("episode_embeds", [])
                video_count = sum(1 for e in ep_embeds if e.get("video_embed"))

                status_icon = "🟢" if status == "Ongoing" else "🔵" if status == "Complete" else "⚪"

                print(f"  {Fore.YELLOW}{i:>4}{Style.RESET_ALL}. {status_icon} {Fore.WHITE}{Style.BRIGHT}{title}{Style.RESET_ALL}")
                print(f"        {Fore.CYAN}Genre:{Style.RESET_ALL} {genres or '-'}")
                print(f"        {Fore.CYAN}Status:{Style.RESET_ALL} {status or '-'}  |  {Fore.CYAN}Episode:{Style.RESET_ALL} {eps}")

                if video_count:
                    print(f"        {Fore.GREEN}✓ {video_count} video embed tersedia{Style.RESET_ALL}")

                cast = d.get("cast", [])
                if cast:
                    print(f"        {Fore.CYAN}Cast:{Style.RESET_ALL} {', '.join(cast[:3])}" +
                          (f" +{len(cast)-3} lagi" if len(cast) > 3 else ""))
                print()

            # Navigasi
            total_pages = (len(dramas) + per_page - 1) // per_page
            print(f"  {Fore.CYAN}Halaman {page+1}/{total_pages}{Style.RESET_ALL}  |  ", end="")

            nav_opts = []
            if page > 0:
                nav_opts.append(f"{Fore.YELLOW}p{Style.RESET_ALL}=sebelum")
            if end < len(dramas):
                nav_opts.append(f"{Fore.YELLOW}n{Style.RESET_ALL}=berikut")
            nav_opts.append(f"{Fore.YELLOW}[nomor]{Style.RESET_ALL}=detail")
            nav_opts.append(f"{Fore.YELLOW}0{Style.RESET_ALL}=kembali")
            print("  ".join(nav_opts))

            nav = ask("Navigasi", "0")

            if nav == "0":
                return
            elif nav.lower() == "n" and end < len(dramas):
                page += 1
                clear()
                print_header("🎬 Daftar Film/Drama")
                continue
            elif nav.lower() == "p" and page > 0:
                page -= 1
                clear()
                print_header("🎬 Daftar Film/Drama")
                continue
            elif nav.isdigit():
                idx = int(nav) - 1
                if 0 <= idx < len(dramas):
                    drama = dramas[idx]
                    clear()
                    print_header(f"🎬 {drama.get('title', '?')}")

                    for k in ["alternative_title", "type", "status", "season",
                              "episode_count", "country", "first_air_date",
                              "video_length", "score", "total_ratings", "views", "posted_on"]:
                        v = drama.get(k, "")
                        if v:
                            if isinstance(v, list):
                                v = ", ".join(v)
                            label = k.replace("_", " ").title()
                            print(f"  {Fore.CYAN}{label}:{Style.RESET_ALL} {v}")

                    genres = drama.get("genres", [])
                    if genres:
                        print(f"  {Fore.CYAN}Genre:{Style.RESET_ALL} {', '.join(genres)}")

                    directors = drama.get("directors", [])
                    if directors:
                        print(f"  {Fore.CYAN}Director:{Style.RESET_ALL} {', '.join(directors)}")

                    cast = drama.get("cast", [])
                    if cast:
                        print(f"\n  {Fore.CYAN}Cast:{Style.RESET_ALL}")
                        for c in cast:
                            print(f"    {Fore.GREEN}→{Style.RESET_ALL} {c}")

                    sinopsis = drama.get("sinopsis", "")
                    if sinopsis:
                        print(f"\n  {Fore.CYAN}Sinopsis:{Style.RESET_ALL}")
                        print(f"    {sinopsis[:400]}")

                    poster = drama.get("poster", "")
                    if poster:
                        print(f"\n  {Fore.CYAN}Poster:{Style.RESET_ALL} {poster}")

                    # Episode embeds
                    ep_embeds = drama.get("episode_embeds", [])
                    episodes = drama.get("episodes", [])
                    if ep_embeds:
                        print(f"\n  {Fore.CYAN}Video Embed per Episode:{Style.RESET_ALL}")
                        for ep in ep_embeds:
                            ep_num = ep.get("episode", "?")
                            embed = ep.get("video_embed", "")
                            icon = f"{Fore.GREEN}✓{Style.RESET_ALL}" if embed else f"{Fore.RED}✗{Style.RESET_ALL}"
                            print(f"    {icon} Ep {ep_num}: {Fore.BLUE}{embed[:70]}{Style.RESET_ALL}" if embed else
                                  f"    {icon} Ep {ep_num}: -")
                    elif episodes:
                        print(f"\n  {Fore.CYAN}Daftar Episode ({len(episodes)}):{Style.RESET_ALL}")
                        for ep in episodes[:20]:
                            print(f"    → Episode {ep.get('episode', '?')}")
                        if len(episodes) > 20:
                            print(f"    {Fore.YELLOW}... +{len(episodes)-20} episode lagi{Style.RESET_ALL}")

                    # Video Links Khusus Azarug (video_players)
                    vidi = drama.get("video_players", [])
                    if vidi:
                        print(f"\n  {Fore.CYAN}Video Stream / Players:{Style.RESET_ALL}")
                        for v in vidi:
                            print(f"    {Fore.GREEN}→{Style.RESET_ALL} {v}")

                    # Download links
                    dl = drama.get("download_links", [])
                    if dl:
                        print(f"\n  {Fore.CYAN}Download:{Style.RESET_ALL}")
                        for link in dl:
                            print(f"    {Fore.GREEN}→{Style.RESET_ALL} {link.get('description', link.get('text', 'DOWNLOAD'))}: {link.get('url', '')}")

                    input(f"\n  {Fore.YELLOW}[Enter untuk kembali ke daftar]{Style.RESET_ALL}")
                    clear()
                    print_header("🎬 Daftar Film/Drama")

    def _show_generic_content(data, filepath):
        """Tampilkan konten generik (emas, crypto, berita, dll)."""
        fname = os.path.basename(filepath)
        sz = round(os.path.getsize(filepath) / 1024, 1)
        info(f"Ukuran: {sz} KB")
        info(f"Path: {filepath}")
        print()

        # Metadata
        meta = data.get("metadata", {})
        if meta:
            head("Metadata:")
            for k, v in meta.items():
                print(f"    {Fore.CYAN}{k}{Style.RESET_ALL}: {v}")
            print()

        inner = data.get("data", data)

        # Tabel
        tables = []
        if isinstance(inner, dict):
            tables = inner.get("tables", [])
        if tables:
            head(f"Tabel ({len(tables)} ditemukan):")
            for ti, tbl in enumerate(tables, 1):
                headers = tbl.get("headers", [])
                rows = tbl.get("rows", [])
                if headers:
                    print(f"\n    {Fore.YELLOW}Tabel {ti}{Style.RESET_ALL} — Kolom: {' | '.join(str(h) for h in headers[:8])}")
                for row in rows:
                    if isinstance(row, dict):
                        vals = " | ".join(f"{v}" for v in list(row.values())[:8])
                    else:
                        vals = " | ".join(str(c) for c in row[:8])
                    print(f"      {Fore.CYAN}→{Style.RESET_ALL} {vals}")
            print()

        # Articles / Berita
        articles = []
        if isinstance(inner, dict):
            articles = inner.get("articles", [])
        if not articles:
            articles = data.get("articles", [])
        if articles:
            head(f"Artikel/Berita ({len(articles)} item):")
            for a in articles:
                judul = a.get("judul", a.get("title", ""))[:80]
                url_art = a.get("url", "")[:70]
                tgl = a.get("tanggal", a.get("date", ""))
                if judul:
                    print(f"    {Fore.CYAN}→{Style.RESET_ALL} {judul}")
                    if tgl:
                        print(f"      {Fore.YELLOW}{tgl}{Style.RESET_ALL}")
                    if url_art:
                        print(f"      {Fore.BLUE}{url_art}{Style.RESET_ALL}")
            print()

        # Stocks
        stocks = data.get("stocks", [])
        if stocks:
            head(f"Stocks ({len(stocks)} ticker):")
            for s in stocks:
                if isinstance(s, dict):
                    sym = s.get("symbol", s.get("ticker", "?"))
                    name_ = s.get("name", s.get("companyName", ""))
                    price = s.get("price", s.get("lastPrice", "?"))
                    print(f"    {Fore.GREEN}{sym:>6}{Style.RESET_ALL}  {name_[:40]:40}  ${price}")
            print()

        # Captured APIs
        apis = {}
        if isinstance(inner, dict):
            apis = inner.get("captured_apis", {})
        if apis:
            head(f"API Endpoint Tertangkap ({len(apis)}):")
            for api_url in list(apis.keys()):
                short = api_url[:90] + ("..." if len(api_url) > 90 else "")
                body = apis[api_url]
                body_type = type(body).__name__
                body_len = len(body) if isinstance(body, (list, dict)) else "-"
                print(f"    {Fore.GREEN}→{Style.RESET_ALL} {short}")
                print(f"      {Fore.CYAN}Type: {body_type}, Items: {body_len}{Style.RESET_ALL}")
            print()

    # ══════════════════════════════════════════════════════════════
    # Main loop
    # ══════════════════════════════════════════════════════════════

    while True:
        clear()
        print_header("📂 LIHAT HASIL SCRAPE")

        all_files = _collect_all_files()
        if not all_files:
            err("Belum ada file hasil scrape.")
            info("Jalankan scraper terlebih dahulu.")
            input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
            return

        # Kategorisasi
        categorized = {}
        for cat_name in CATEGORIES:
            categorized[cat_name] = []
        for fp in all_files:
            cat = _categorize_file(fp)
            categorized[cat].append(fp)

        # Tampilkan kategori
        total_files = len(all_files)
        total_size = sum(os.path.getsize(f) for f in all_files)
        print(f"  {Fore.CYAN}Total: {total_files} file ({round(total_size/1024/1024, 1)} MB){Style.RESET_ALL}\n")

        cat_keys = [k for k in CATEGORIES if categorized.get(k)]
        for i, cat_name in enumerate(cat_keys, 1):
            files = categorized[cat_name]
            cat_size = sum(os.path.getsize(f) for f in files)
            sz_str = f"{round(cat_size/1024, 1)} KB" if cat_size < 1024*1024 else f"{round(cat_size/1024/1024, 1)} MB"
            print(f"    {Fore.YELLOW}{i}{Style.RESET_ALL}  {cat_name}  {Fore.CYAN}({len(files)} file, {sz_str}){Style.RESET_ALL}")

        print(f"\n    {Fore.YELLOW}0{Style.RESET_ALL}  🔙 Kembali ke menu utama\n")

        choice = ask(f"Pilih kategori (0-{len(cat_keys)})", "0")

        if choice == "0":
            return

        try:
            cat_idx = int(choice) - 1
            if cat_idx < 0 or cat_idx >= len(cat_keys):
                raise ValueError
        except ValueError:
            err("Pilihan tidak valid.")
            time.sleep(1)
            continue

        selected_cat = cat_keys[cat_idx]
        cat_files = categorized[selected_cat]

        # ── Tampilkan file dalam kategori ──
        while True:
            clear()
            print_header(f"📂 {selected_cat}")
            print(f"  {Fore.CYAN}{len(cat_files)} file tersedia:{Style.RESET_ALL}\n")

            page_size = 20
            for i, fp in enumerate(cat_files[:page_size], 1):
                fname = os.path.basename(fp)
                # Potong nama agar muat
                display_name = fname[:55] if len(fname) > 55 else fname
                sz = round(os.path.getsize(fp) / 1024, 1)
                ts = os.path.getmtime(fp)
                dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                print(f"    {Fore.YELLOW}{i:>2}{Style.RESET_ALL}. {display_name:55}  {Fore.CYAN}{sz:>8} KB{Style.RESET_ALL}  {dt}")

            if len(cat_files) > page_size:
                print(f"\n    {Fore.YELLOW}...{Style.RESET_ALL} dan {len(cat_files) - page_size} file lainnya")

            print(f"\n    {Fore.YELLOW} c{Style.RESET_ALL}. Hapus semua file")
            print(f"    {Fore.YELLOW} d{Style.RESET_ALL}. Hapus file tertentu")
            print(f"    {Fore.YELLOW} 0{Style.RESET_ALL}. Kembali ke daftar kategori\n")

            file_choice = ask(f"Pilih file (1-{min(len(cat_files), page_size)}, c, d, atau 0)", "0")

            if file_choice == "0":
                break

            if file_choice.lower() == "c":
                if ask(f"YAKIN ingin menghapus SEMUA {len(cat_files)} file di kategori '{selected_cat}'? (y/n)", "n").lower() == "y":
                    count = 0
                    for f in cat_files:
                        try:
                            os.remove(f)
                            count += 1
                        except Exception as e:
                            logger.error(f"Gagal menghapus {f}: {e}")
                    cat_files.clear()
                    ok(f"Berhasil menghapus {count} file!")
                    time.sleep(1)
                    break # Kembali ke daftar kategori karena sudah kosong
                continue

            if file_choice.lower() == "d":
                del_c = ask(f"Nomor file yang akan dihapus (1-{min(len(cat_files), page_size)})")
                try:
                    di = int(del_c) - 1
                    if 0 <= di < len(cat_files):
                        fn = os.path.basename(cat_files[di])
                        if ask(f"Yakin hapus {fn}? (y/n)", "n").lower() == "y":
                            os.remove(cat_files[di])
                            cat_files.pop(di)
                            ok(f"File {fn} berhasil dihapus!")
                            time.sleep(1)
                except ValueError:
                    err("Pilihan tidak valid.")
                    time.sleep(1)
                continue

            try:
                fidx = int(file_choice) - 1
            except ValueError:
                err("Pilihan tidak valid.")
                time.sleep(1)
                continue

            if fidx < 0 or fidx >= min(len(cat_files), page_size):
                err("Nomor file tidak valid.")
                time.sleep(1)
                continue

            # ── Tampilkan isi file ──
            filepath = cat_files[fidx]
            fname = os.path.basename(filepath)
            clear()
            print_header(f"📄 {fname}")

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                err(f"Gagal membaca file: {e}")
                input(f"  {Fore.YELLOW}[Enter]{Style.RESET_ALL}")
                continue

            # Pilih tampilan berdasarkan kategori
            if selected_cat.startswith("🎬"):
                _show_drama_detail(data, filepath)
            else:
                _show_generic_content(data, filepath)

            input(f"\n  {Fore.YELLOW}[Enter untuk kembali ke daftar file]{Style.RESET_ALL}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════



MENU_OPTIONS = {
    "1": ("🥇  Scrape Harga Emas",        run_scrape_emas),
    "2": ("₿   Scrape Crypto",            run_scrape_crypto),
    "3": ("📰  Scrape Berita",            run_scrape_berita),
    "4": ("📈  Scrape Saham / Stocks",    run_scrape_saham),
    "5": ("🌐  Scrape URL Custom",        run_scrape_custom),
    "6": ("⚡  SCRAPE ALL (Semua Data)", run_scrape_all),
    "7": ("🚀  Jalankan API Server",      run_api_server),
    "8": ("📂  Lihat Hasil Scrape",       run_view_results),
    "9": ("🎬  Scrape Film / Drama",       run_scrape_film),
    "0": ("🚪  Keluar",                   None),
}

def main_menu():
    while True:
        clear()
        print(BANNER)

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
                try:
                    handler()
                except KeyboardInterrupt:
                    print(f"\n\n  {Fore.YELLOW}⚠ Dibatalkan (Ctrl+C){Style.RESET_ALL}")
                    time.sleep(1)
        else:
            warn("Pilihan tidak valid. Coba lagi.")
            time.sleep(1)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
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
    except KeyboardInterrupt:
        print(f"\n\n  {Fore.CYAN}Sampai jumpa! 👋{Style.RESET_ALL}\n")
        sys.exit(0)
