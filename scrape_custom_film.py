import os
import re
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from config.settings import OUTPUT_DIR, HEADERS
import logging

log = logging.getLogger("scrapers.custom")

# Iklan yang akan dilewati saat mencari iframe
AD_DOMAINS = [
    'dtscout.com', 'doubleclick', 'googlesyndication', 'adnxs.com',
    'popads', 'popcash', 'propeller', 'onclick', 'adsterra',
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com'
]

def _is_ad_iframe(src: str) -> bool:
    """Deteksi apakah iframe src adalah iklan/sosmed."""
    if not src or src.startswith('about:'):
        return True
    
    src_lower = src.lower()
    return any(ad in src_lower for ad in AD_DOMAINS)

def extract_iframe_from_page(url: str, browser_path: str = None) -> list[str]:
    """Buka satu halaman dan ambil semua iframe valid (bukan iklan)."""
    from playwright.sync_api import sync_playwright
    
    iframes = []
    
    for _retry in range(3):
        try:
            with sync_playwright() as p:
                launch_args = {"headless": True}
                if browser_path:
                    launch_args["executable_path"] = browser_path

                try:
                    browser = p.chromium.launch(**launch_args)
                except Exception:
                    browser = p.chromium.launch(headless=True)

                ctx = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 768}
                )
                page = ctx.new_page()

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass
                
                # Tunggu sedikit agar iframe video memuat
                page.wait_for_timeout(3000)

                # Ekstrak semua iframe
                frame_srcs = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('iframe')).map(f => f.src);
                }""")
                
                for src in frame_srcs:
                    if not _is_ad_iframe(src):
                        iframes.append(src)
                
                browser.close()
                return iframes
                
        except Exception as e:
            err_msg = str(e).lower()
            if "execution context" in err_msg or "target closed" in err_msg:
                time.sleep(2)
                continue
            return []
            
    return []

def heuristik_cari_episode(page, base_url: str):
    """Gunakan Heuristik/AI sederhana untuk menebak mana link episode di sebuah halaman."""
    # Ambil semua tag A
    links = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a')).map(a => {
            return {
                text: a.innerText.trim(),
                href: a.href,
                className: a.className
            }
        });
    }""")
    
    episodes = []
    seen_urls = set()
    
    # Keyword deteksi (Case Insensitive)
    valid_keywords = ["episode", "ep ", "ep.", "part", "eps", " eps "]
    
    for link in links:
        url = link['href']
        text = link['text'].lower()
        
        if not url or url.startswith('javascript:') or url.startswith('mailto:') or url.startswith('#'):
            continue
            
        # Hindari link ke sosmed / halaman statis
        if any(b in url for b in ['facebook.com', 'twitter.com', 'instagram.com', '/about', '/contact', '/dmca']):
            continue

        is_episode = False
        
        # 1. Cek dari teks link (misal: "Episode 1", "Ep 02")
        if any(kw in text for kw in valid_keywords) and bool(re.search(r'\d+', text)):
            is_episode = True
            
        # 2. Cek dari URL (misal: domain.com/naruto-episode-5/)
        elif re.search(r'episode-\d+', url.lower()) or re.search(r'-ep-\d+', url.lower()):
            is_episode = True
            text = text or re.search(r'(?i)(episode[-\s]*\d+)', url).group(1)
            
        if is_episode and url not in seen_urls:
            seen_urls.add(url)
            # Bersihkan label
            label = re.sub(r'\s+', ' ', link['text'] or text).strip()
            if not label:
                label = f"Episode {len(episodes) + 1}"
                
            episodes.append({
                "label": label,
                "url": url
            })
            
    # Sort secara natural agar urutannya Ep 1, Ep 2, ... Ep 10
    def natural_keys(text):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]
        
    episodes.sort(key=lambda x: natural_keys(x["label"]))
    return episodes

def run_custom_scrape(url: str, output_name: str = "custom_film"):
    """Pipeline scraper heuristik untuk URL acak."""
    log.info(f"🚀 Memulai Scraper Film Universal (Heuristik AI) untuk: {url}")
    timestamp = int(time.time())
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright belum terinstall.")
        return
        
    # Cari path browser Linux
    browser_path = None
    for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
        if os.path.isfile(candidate):
            browser_path = candidate
            break

    detail_data = {
        "source_url": url,
        "title": "Unknown Title",
        "video_embeds": [],
        "episodes": []
    }
    
    episodes_links = []
    
    # ── FASE 1: Buka halaman utama & Cek Link Episode ──
    log.info("LANGKAH 1: Menganalisa halaman dengan Heuristik...")
    
    with sync_playwright() as p:
        launch_args = {"headless": True}
        if browser_path:
            launch_args["executable_path"] = browser_path
            
        try:
            browser = p.chromium.launch(**launch_args)
        except:
            browser = p.chromium.launch(headless=True)
            
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36")
        page = ctx.new_page()
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            
            # Ekstrak Titel
            title = page.title()
            if title:
                detail_data["title"] = title.split('-')[0].split('|')[0].strip()
            
            # Cari link episode
            episodes_links = heuristik_cari_episode(page, url)
            
            # Cari iframe di halaman utama (berguna jika ini Movie / tidak ada episode)
            frame_srcs = page.evaluate("""() => Array.from(document.querySelectorAll('iframe')).map(f => f.src);""")
            main_iframes = [s for s in frame_srcs if not _is_ad_iframe(s)]
            detail_data["video_embeds"] = main_iframes
            
        except Exception as e:
            log.error(f"Gagal memuat halaman utama: {e}")
            browser.close()
            return
            
        browser.close()
        
    log.info(f"✓ Judul terdeteksi: {detail_data['title']}")
    
    if episodes_links:
        log.info(f"✓ Heuristik mendeteksi {len(episodes_links)} link Episode!")
    else:
        log.info(f"✓ Tidak ada link episode terdeteksi, diasumsikan sebagai Film Tunggal (Movie)")
        if detail_data["video_embeds"]:
            log.info(f"  🎬 Ditemukan {len(detail_data['video_embeds'])} iframe video di halaman utama.")
            
    # ── FASE 2: Gempur Paralel (Jika ada Episode) ──
    if episodes_links:
        log.info(f"\nLANGKAH 2: Scrape {len(episodes_links)} Episode PARALEL (Max 10 browser)...")
        
        results_ep = [{"label": ep["label"], "url": ep["url"], "video_embeds": []} for ep in episodes_links]
        
        lock = threading.Lock()
        completed = [0]
        
        def _scrape_ep_worker(index, ep):
            iframes = extract_iframe_from_page(ep["url"], browser_path)
            with lock:
                results_ep[index]["video_embeds"] = iframes
                completed[0] += 1
                v = f"🎬 {len(iframes)} video" if iframes else "✗ Kosong"
                log.info(f"  ✓ [{completed[0]}/{len(episodes_links)}] {ep['label']} — {v}")

        with ThreadPoolExecutor(max_workers=min(len(episodes_links), 10)) as executor:
            tasks = {executor.submit(_scrape_ep_worker, i, ep): i for i, ep in enumerate(episodes_links)}
            for future in as_completed(tasks):
                future.result()
                
        detail_data["episodes"] = results_ep
        log.info("✓ Scraping paralel selesai\n")

        # ── FASE 3: Verifikasi 100% ──
        MAX_VERIFY = 3
        for rnd in range(1, MAX_VERIFY + 1):
            missing = [(i, ep) for i, ep in enumerate(detail_data["episodes"]) if not ep["video_embeds"]]
            
            if not missing:
                log.info(f"✅ VERIFIKASI: Semua episode punya video 100%!")
                break
                
            log.info(f"🔍 VERIFIKASI Ronde {rnd}/{MAX_VERIFY}: {len(missing)} episode kosong. Retry...")
            for i, ep in missing:
                log.info(f"  🔄 Retry {ep['label']}...")
                iframes = extract_iframe_from_page(ep["url"], browser_path)
                if iframes:
                    detail_data["episodes"][i]["video_embeds"] = iframes
                    log.info(f"    ✓ Berhasil dapat {len(iframes)} video!")
                else:
                    log.warning(f"    ✗ Tetap kosong.")
                    
        log.info("✓ Proses Verifikasi selesai.\n")

    # ── SIMPAN HASIL ──
    safe_name = re.sub(r'[^A-Za-z0-9_]+', '_', output_name).strip('_').lower()
    full_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{timestamp}.json")
    
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "source_url": url,
                "scrape_date": datetime.now().isoformat(),
                "technique": "heuristic_playwright_parallel",
                "episodes_found": len(episodes_links)
            },
            "data": detail_data
        }, f, ensure_ascii=False, indent=2)

    log.info(f"{'═'*60}")
    log.info(f"✓ SELESAI!")
    log.info(f"  Judul: {detail_data['title']}")
    log.info(f"  File: {full_path}")
    log.info(f"{'═'*60}")
