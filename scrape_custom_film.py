import os
import re
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_scrape")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
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

def heuristik_cari_film_list(page, base_url: str):
    """Cari link yang kemungkinan menuju ke halaman Film/Drama dari halaman beranda/kategori."""
    links = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a')).map(a => {
            return {
                text: a.innerText.trim(),
                href: a.href,
                className: a.className,
                title: a.title
            }
        });
    }""")
    
    film_links = []
    seen = set()
    
    # Keyword penghindar (jangan klik link ini)
    blacklist = [
        'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
        '/genre/', '/category/', '/tag/', '/year/', '/country/', '/page/',
        '/about', '/contact', '/dmca', '/login', '/register', 't.me/',
        '#', 'javascript:', 'mailto:'
    ]
    
    for link in links:
        url = link['href']
        text = link['title'] or link['text']
        
        if not url or not text:
            continue
            
        url_lower = url.lower()
        if any(b in url_lower for b in blacklist):
            continue
            
        # Asumsi heuristik: 
        # 1. URL menuju ke path direktori yang cukup panjang (biasanya slug judul film)
        # Atau 2. Ada pola movie / tv / series di URL
        url_parts = url.rstrip('/').split('/')
        is_film = False
        
        # Validasi struktur URL
        if base_url in url and len(url_parts) > 3:
            slug = url_parts[-1]
            if len(slug) > 5 and '-' in slug: # slug kemungkinan judul film
                is_film = True
        
        # Pola eksplisit
        if '/movie/' in url_lower or '/tv/' in url_lower or '/series/' in url_lower or '/drama/' in url_lower:
            is_film = True
            
        # Pengecualian tambahan: kalau teksnya mengandung hal navigasi
        if any(nav in text.lower() for nav in ["next", "prev", "home", "beranda", "semua"]):
            is_film = False
            
        if is_film and url not in seen:
            seen.add(url)
            film_links.append({"title": title_clean(text), "url": url})
            
    return film_links

def title_clean(t):
    # Bersihkan spasi kosong dan newline berlebih
    return re.sub(r'\s+', ' ', t).strip()

def run_custom_scrape(url: str, output_name: str = "custom_film"):
    """Pipeline scraper heuristik: Deteksi Halaman Utama vs Halaman Detail Film."""
    log.info(f"🚀 Memindai Struktur URL: {url}")
    timestamp = int(time.time())
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright belum terinstall.")
        return
        
    browser_path = None
    for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
        if os.path.isfile(candidate):
            browser_path = candidate
            break

    found_films = []
    
    # ── FASE 1: Buka halaman & Deteksi (Katalog vs Single Film) ──
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
            
            # Cek apakai ini katalog film atau sudah masuk halaman detail film tunggal
            episodes_links = heuristik_cari_episode(page, url)
            frame_srcs = page.evaluate("""() => Array.from(document.querySelectorAll('iframe')).map(f => f.src);""")
            main_iframes = [s for s in frame_srcs if not _is_ad_iframe(s)]
            
            if episodes_links or main_iframes:
                # Ini kemungkinan besar SUDAH halaman Film detail tunggal
                title = page.title()
                if title:
                    title = title.split('-')[0].split('|')[0].strip()
                found_films = [{"title": title or "Unknown", "url": url}]
                log.info(f"✓ URL ini terdeteksi sebagai Halaman Detail Film (Episode: {len(episodes_links)}, Iframe: {len(main_iframes)})")
            else:
                # Ini kemungkinan Halaman Beranda / Kategori Web
                log.info("✓ Tidak ada video/episode di URL ini. Memindai daftar tautan film...")
                found_films = heuristik_cari_film_list(page, url)
                if not found_films:
                    log.error("✗ Heuristik gagal menemukan link film atau episode aktif di halaman ini.")
                    browser.close()
                    return
                log.info(f"✓ Heuristik menemukan {len(found_films)} judul film/series di halaman beranda.")
                
        except Exception as e:
            log.error(f"Gagal memuat URL: {e}")
            browser.close()
            return
            
        browser.close()

    # ── FASE 2: Tanya User (Jika banyak film) ──
    from modules.interaction import ask
    
    if len(found_films) > 1:
        print()
        log.info(f"Daftar Film yang Ditemukan (Total: {len(found_films)}):")
        for i, f in enumerate(found_films[:5]):
            print(f"  {i+1}. {f['title'][:60]}")
        if len(found_films) > 5:
            print(f"  ... dan {len(found_films) - 5} lainnya.")
        
        print()
        limit_str = ask(f"Berapa film yang ingin di-scrape? (1-{len(found_films)}, 'all' untuk semua)", "all")
        if limit_str.lower() != 'all':
            try:
                limit = int(limit_str)
                found_films = found_films[:limit]
            except:
                log.error("Input tidak valid, membatalkan.")
                return

    # ── FASE 3: Proses Scrape Penuh per Judul Secara BERSAMAAN ──
    log.info(f"\n🚀 Memulai Auto-Scrape {len(found_films)} Film/Drama secara PARALEL...\n")
    
    all_results = []
    
    # Limit max 5 worker pararel untuk scrape full page untuk mencegah lag parah
    # karena masing-masing page juga bisa open 10 iframe paralel lagi di dalam.
    lock = threading.Lock()
    completed = [0]
    
    def _scrape_single_film(film_info):
        f_url = film_info["url"]
        f_title = film_info["title"]
        
        detail_data = {
            "source_url": f_url,
            "title": f_title,
            "video_embeds": [],
            "episodes": []
        }
        
        try:
            with sync_playwright() as p:
                launch_args = {"headless": True}
                if browser_path:
                    launch_args["executable_path"] = browser_path
                    
                try:
                    b_local = p.chromium.launch(**launch_args)
                except:
                    b_local = p.chromium.launch(headless=True)
                    
                ctx_local = b_local.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                page_local = ctx_local.new_page()
                
                try:
                    page_local.goto(f_url, wait_until="domcontentloaded", timeout=30000)
                    page_local.wait_for_timeout(3000)
                    
                    real_title = page_local.title()
                    if real_title:
                        detail_data["title"] = real_title.split('-')[0].split('|')[0].strip()
                        
                    ep_links = heuristik_cari_episode(page_local, f_url)
                    frame_srcs = page_local.evaluate("""() => Array.from(document.querySelectorAll('iframe')).map(f => f.src);""")
                    main_iframes = [s for s in frame_srcs if not _is_ad_iframe(s)]
                    detail_data["video_embeds"] = main_iframes
                except:
                    ep_links = []
                b_local.close()

            # Ekstrak Episode
            if ep_links:
                results_ep = [{"label": ep["label"], "url": ep["url"], "video_embeds": []} for ep in ep_links]
                
                # paralel episode dalam film
                def _ep_worker(index, ep):
                    results_ep[index]["video_embeds"] = extract_iframe_from_page(ep["url"], browser_path)

                # Gunakan 3 thread per film untuk episode agar komputer tidak crash
                with ThreadPoolExecutor(max_workers=3) as ex_ep:
                    t_ep = {ex_ep.submit(_ep_worker, i, ep): i for i, ep in enumerate(ep_links)}
                    for f in as_completed(t_ep):
                        f.result()
                        
                detail_data["episodes"] = results_ep
                
                # Verifikasi 1 Ronde Cukup untuk custom
                missing = [(i, ep) for i, ep in enumerate(detail_data["episodes"]) if not ep["video_embeds"]]
                for i, ep in missing:
                    retry_frames = extract_iframe_from_page(ep["url"], browser_path)
                    if retry_frames:
                        detail_data["episodes"][i]["video_embeds"] = retry_frames
            
            with lock:
                all_results.append(detail_data)
                completed[0] += 1
                v = len(detail_data["video_embeds"])
                e = len(detail_data["episodes"])
                log.info(f"  ✓ [{completed[0]}/{len(found_films)}] {detail_data['title'][:40]} | 🎬 {v} Vid | 📺 {e} Eps")
                
        except Exception as e:
            with lock:
                completed[0] += 1
                log.error(f"  ✗ [{completed[0]}/{len(found_films)}] {f_title} Gagal: {e}")

    with ThreadPoolExecutor(max_workers=min(len(found_films), 3)) as executor:
        tasks = {executor.submit(_scrape_single_film, f): f for f in found_films}
        try:
            for future in as_completed(tasks):
                future.result()
        except KeyboardInterrupt:
            log.warning("⚠ Dibatalkan user.")
            executor.shutdown(wait=False, cancel_futures=True)

    # ── SIMPAN HASIL ──
    safe_name = re.sub(r'[^A-Za-z0-9_]+', '_', output_name).strip('_').lower()
    full_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{timestamp}.json")
    
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "source_url": url,
                "scrape_date": datetime.now().isoformat(),
                "technique": "heuristic_playwright_parallel",
                "total_films": len(all_results)
            },
            "data": all_results
        }, f, ensure_ascii=False, indent=2)

    log.info(f"{'═'*60}")
    log.info(f"✓ SELESAI AUTO-SCRAPE KUSTOM!")
    log.info(f"  Berhasil: {len(all_results)} Judul")
    log.info(f"  File: {full_path}")
    log.info(f"{'═'*60}")
