#!/usr/bin/env python3
"""
DrakorKita Scraper — Scrape semua drama/film dari drakorkita3.nicewap.sbs
Fitur:
  • Crawl daftar semua film/series dengan pagination
  • Scrape detail per judul: sinopsis, metadata, cast, genre, poster
  • Ambil daftar episode + link video embed per episode
  • Simpan ke JSON per judul dan overview gabungan
"""

import os
import sys
import re
import json
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# ── Setup ────────────────────────────────────────────────────────────────────
BASE_URL = "https://drakorkita3.nicewap.sbs"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_scrape", "drakorkita")
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("drakorkita")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
SESSION.mount("http://", adapter)
SESSION.mount("https://", adapter)
SESSION.headers.update(HEADERS)


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 1: Crawl daftar film dari /all?page=N
# ══════════════════════════════════════════════════════════════════════════════

def fetch_listing_page(page: int = 1, params: dict = None) -> list[dict]:
    """Ambil daftar film dari halaman listing."""
    url = f"{BASE_URL}/all"
    p = {"page": page}
    if params:
        p.update(params)

    try:
        resp = SESSION.get(url, params=p, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Gagal fetch listing page {page}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []

    # Pattern durasi yang harus di-skip (misalnya "1:09:03", "47:04")
    duration_pattern = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')

    # Setiap item ada di <a> dengan href ke /detail/...
    for card in soup.select("a[href*='/detail/']"):
        href = card.get("href", "")
        if "/detail/" not in href:
            continue

        # Extract slug dari URL
        slug = href.rstrip("/").split("/")[-1]

        # Cari judul — skip teks durasi dan teks pendek
        title_text = ""
        title_el = card.select_one(".title, h3, h4, .name, .tt")
        if title_el:
            title_text = title_el.get_text(strip=True)
        else:
            # Fallback: ambil teks yang BUKAN durasi dan cukup panjang
            for txt in card.stripped_strings:
                txt = txt.strip()
                # Skip durasi, angka pendek, rating, episode labels
                if (len(txt) > 5
                    and not duration_pattern.match(txt)
                    and not txt.replace(".", "").isdigit()
                    and not txt.startswith("E")
                    and "480p" not in txt and "720p" not in txt
                    and "1080p" not in txt and "WEB" not in txt):
                    title_text = txt
                    break

        # Jika masih tidak ada, buat dari slug
        if not title_text or duration_pattern.match(title_text):
            # "positively-yours-2026-eot" → "Positively Yours 2026"
            parts = slug.split("-")
            # Hapus suffix random (4 char hash setelah tahun)
            if len(parts) >= 2 and len(parts[-1]) <= 5 and parts[-1].isalnum():
                parts = parts[:-1]
            title_text = " ".join(parts).title()

        # Cari poster image
        poster = ""
        img = card.select_one("img")
        if img:
            poster = img.get("data-src") or img.get("src") or ""
            if poster and not poster.startswith("http"):
                poster = urljoin(BASE_URL, poster)

        # Cari rating — biasanya angka kecil di akhir card
        rating = ""
        all_texts = [t.strip() for t in card.stripped_strings]
        for txt in reversed(all_texts):
            if re.match(r'^\d\.?\d?$', txt) and float(txt) <= 10:
                rating = txt
                break

        # Cari episode info
        episode_info = ""
        for txt in all_texts:
            if txt.startswith("E") and ("/" in txt or "END" in txt):
                episode_info = txt
                break

        # Normalisasi URL
        detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)

        if title_text or slug:
            items.append({
                "title": title_text,
                "slug": slug,
                "detail_url": detail_url,
                "poster": poster,
                "rating": rating,
                "episode_info": episode_info,
            })

    # Deduplicate berdasarkan slug
    seen = set()
    unique = []
    for item in items:
        if item["slug"] not in seen:
            seen.add(item["slug"])
            unique.append(item)

    return unique


def crawl_all_listings(max_pages: int = None, params: dict = None) -> list[dict]:
    """Crawl semua halaman listing."""
    all_items = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            break

        log.info(f"📄 Crawling halaman {page}...")
        items = fetch_listing_page(page, params)

        if not items:
            log.info(f"  Halaman {page} kosong, selesai.")
            break

        all_items.extend(items)
        log.info(f"  → {len(items)} judul ditemukan (total: {len(all_items)})")

        page += 1
        time.sleep(0.5)  # Sopan, jangan terlalu cepat

    return all_items


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 2: Scrape detail per judul
# ══════════════════════════════════════════════════════════════════════════════

def scrape_detail(detail_url: str) -> dict | None:
    """Scrape halaman detail: sinopsis, info, cast, genre, poster, episode list.
    Menggunakan selector CSS spesifik DrakorKita:
      title  → h1[itemprop=headline]  |  poster → .thumb img
      genre  → .gnr a                 |  info   → .infox .spe span
      eps    → .btn-svr               |  server → .btn-sv
    """
    try:
        resp = SESSION.get(detail_url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Gagal fetch detail {detail_url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {"url": detail_url}

    # ── Judul ──
    # Prioritas: h1[itemprop="headline"], lalu h1 kedua (yang bukan site title)
    headline = soup.select_one('h1[itemprop="headline"]')
    if headline:
        result["title"] = headline.get_text(strip=True)
    else:
        all_h1 = soup.select("h1")
        # H1 pertama biasanya site title, ambil yang kedua
        if len(all_h1) >= 2:
            result["title"] = all_h1[1].get_text(strip=True)
        elif all_h1:
            result["title"] = all_h1[0].get_text(strip=True)
        else:
            result["title"] = ""

    # Bersihkan prefix umum dari title
    title = result.get("title", "")
    for prefix in ["Nonton ", "Download "]:
        if title.startswith(prefix):
            title = title[len(prefix):]
    # Hapus "Subtitle Indonesia" di akhir
    title = re.sub(r'\s*Subtitle Indonesia\s*$', '', title)
    
    # Fallback Slug Parser jika title kosong
    if not title:
        slug = detail_url.rstrip("/").split("/")[-1]
        parts = slug.split("-")
        if len(parts) >= 2 and len(parts[-1]) <= 5 and parts[-1].isalnum():
            parts = parts[:-1]
        title = " ".join(parts).title()

    result["title"] = title.strip()

    # ── Judul Alternatif / Korea ──
    alter = soup.select_one("span.alter")
    if alter:
        result["alternative_title"] = alter.get_text(strip=True)

    # ── Poster (.thumb img) ──
    poster_img = soup.select_one(".thumb img")
    if poster_img:
        result["poster"] = poster_img.get("data-src") or poster_img.get("src") or ""
    else:
        # Fallback
        poster_img = soup.select_one(".poster img, img[itemprop='image']")
        result["poster"] = (poster_img.get("data-src") or poster_img.get("src") or "") if poster_img else ""

    # ── Banner / Backdrop ──
    banner_el = soup.select_one(".bigcover img, .banner img, .backdrop img")
    if banner_el:
        result["banner"] = banner_el.get("data-src") or banner_el.get("src") or ""

    # ── Sinopsis ──
    # Cari di .desc, .sinopsis, atau teks setelah header Sinopsis
    sinopsis_div = soup.select_one(".desc, .sinopsis")
    if sinopsis_div:
        result["sinopsis"] = sinopsis_div.get_text(strip=True)
    else:
        synopsis_header = soup.find(string=re.compile(r"Sinopsis", re.I))
        if synopsis_header:
            parent = synopsis_header.find_parent()
            if parent:
                next_el = parent.find_next_sibling()
                if next_el:
                    result["sinopsis"] = next_el.get_text(strip=True)
                else:
                    next_p = parent.find_next("p")
                    if next_p:
                        result["sinopsis"] = next_p.get_text(strip=True)

    if "sinopsis" not in result or not result.get("sinopsis"):
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            result["sinopsis"] = meta.get("content", "")

    # ── Informasi detail dari <li> parent class=anf DAN <span> standalone ──
    info_fields = {}
    # Cara 1: LI di dalam .anf
    for li in soup.select(".anf li"):
        text = li.get_text(" ", strip=True)
        if " : " in text:
            key, _, value = text.partition(" : ")
            key = key.strip()
            value = value.strip()
            if key and value:
                key_clean = key.lower().replace(" ", "_")
                info_fields[key_clean] = value
    # Cara 2: Standalone <span> yang punya " : " (fallback)
    if not info_fields:
        for span in soup.select("span"):
            text = span.get_text(" ", strip=True)
            if " : " in text and len(text) < 150:
                key, _, value = text.partition(" : ")
                key = key.strip()
                value = value.strip()
                if key and value and key.lower() not in ("sinopsis", "informasi"):
                    key_clean = key.lower().replace(" ", "_")
                    if key_clean not in info_fields:
                        info_fields[key_clean] = value

    # Map ke field standar
    result["type"] = info_fields.get("type", "")
    result["status"] = info_fields.get("status", "")
    result["season"] = info_fields.get("season", "")
    result["episode_count"] = info_fields.get("episode_count", "")
    result["first_air_date"] = info_fields.get("first_air_date", "")
    result["video_length"] = info_fields.get("video_length", "")
    result["views"] = info_fields.get("views", "")
    result["posted_on"] = info_fields.get("posted_on", "")

    # Sisanya yang tidak ter-map
    for k, v in info_fields.items():
        if k not in result:
            result[k] = v

    # ── Genre dari .gnr a (scoped, bukan sidebar) ──
    genres = []
    gnr_container = soup.select_one(".gnr")
    if gnr_container:
        for a in gnr_container.select("a"):
            g = a.get_text(strip=True)
            if g and g not in genres:
                genres.append(g)
    else:
        # Fallback: ambil dari link genre, tapi scope ke area detail saja
        infox = soup.select_one(".infox, .detail-content")
        search_area = infox if infox else soup
        for a in search_area.select("a[href*='genre=']"):
            g = a.get_text(strip=True)
            if g and g not in genres:
                genres.append(g)
    result["genres"] = genres

    # ── Cast (dari .desc-wrap atau .infox, bukan sidebar) ──
    cast = []
    cast_area = soup.select_one(".desc-wrap") or soup.select_one(".infox") or soup
    for a in cast_area.select("a[href*='cast=']"):
        c = a.get_text(strip=True)
        # Fix merged text: "Choi Jin-hyukas Kang Du-jun" → "Choi Jin-hyuk as Kang Du-jun"
        c = re.sub(r'(\w)(as )([A-Z])', r'\1 as \3', c)
        if c and c not in cast:
            cast.append(c)

    # Jika cast masih kosong, coba parse dari Stars info field
    if not cast:
        stars_text = info_fields.get("stars", "")
        if stars_text:
            for part in stars_text.split(","):
                part = part.strip()
                part = re.sub(r'(\w)(as )([A-Z])', r'\1 as \3', part)
                if part and part not in cast:
                    cast.append(part)

    result["cast"] = cast

    # ── Director ──
    directors = []
    crew_area = cast_area  # Same scoped area
    for a in crew_area.select("a[href*='crew=']"):
        d = a.get_text(strip=True)
        if d and d not in directors:
            directors.append(d)
    if not directors and info_fields.get("director"):
        directors = [info_fields["director"]]
    result["directors"] = directors

    # ── Country ──
    country = []
    for a in crew_area.select("a[href*='country=']"):
        c = a.get_text(strip=True)
        if c and c not in country:
            country.append(c)
    if not country and info_fields.get("country"):
        country = [info_fields["country"]]
    result["country"] = country

    # ── Score & Ratings ──
    score_el = soup.find(string=re.compile(r"Score\s*:", re.I))
    if score_el:
        parent = score_el.find_parent()
        if parent:
            score_text = parent.get_text(strip=True)
            match = re.search(r'[\d.]+', score_text)
            if match:
                result["score"] = match.group()

    rating_el = soup.find(string=re.compile(r"\d+\s*Rating", re.I))
    if rating_el:
        match = re.search(r'(\d+)\s*Rating', rating_el, re.I)
        if match:
            result["total_ratings"] = match.group(1)

    # ── Episode list ──
    # Episode buttons (.btn-svr) are loaded via JS, not in static HTML.
    # We derive episode count from metadata and generate episode list.
    episodes = []
    ep_count_str = result.get("episode_count", "") or ""
    ep_count = 0
    try:
        ep_count = int(re.search(r'\d+', ep_count_str).group()) if ep_count_str else 0
    except (AttributeError, ValueError):
        pass

    # Juga coba parse dari title ("Episode 1 - 12" → 12)
    if not ep_count:
        ep_match = re.search(r'Episode\s+\d+\s*-\s*(\d+)', result.get("title", ""), re.I)
        if ep_match:
            ep_count = int(ep_match.group(1))

    for i in range(1, ep_count + 1):
        episodes.append({"episode": str(i)})

    result["episodes"] = episodes
    result["total_episodes"] = ep_count

    # ── Video Servers (.btn-sv) ──
    servers = []
    for srv_btn in soup.select(".btn-sv"):
        srv_name = srv_btn.get_text(strip=True)
        if srv_name:
            servers.append(srv_name)
    # Dedup
    result["servers"] = list(dict.fromkeys(servers))

    # ── Video Iframe src ──
    iframe = soup.select_one("iframe[src]")
    if iframe:
        src = iframe.get("src", "")
        if src and not src.startswith("about:"):
            result["video_embed"] = src

    # ── Download button / links ──
    download_links = []
    dl_btn = soup.select_one("#nonot, a[id='nonot']")
    if dl_btn:
        dl_url = dl_btn.get("href", "")
        if dl_url and dl_url != "#":
            download_links.append({"text": "DOWNLOAD", "url": dl_url})
    result["download_links"] = download_links

    return result


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 3: Scrape episode embed dengan Playwright (opsional, untuk video URL)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_episodes_with_browser(detail_url: str, total_eps: int) -> list[dict]:
    """Gunakan Playwright untuk klik setiap episode dan ambil iframe src."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("Playwright belum terinstall, mencoba install otomatis...")
        import subprocess
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "playwright"],
                          check=True, capture_output=True)
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                          check=True, capture_output=True)
            from playwright.sync_api import sync_playwright
            log.info("✓ Playwright berhasil diinstall!")
        except Exception as e:
            log.error(f"Gagal install Playwright: {e}")
            log.error("Install manual: pip install playwright && playwright install chromium")
            return []

    episodes_data = []

    # Cari browser path
    browser_path = None
    for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser",
                      "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
        if os.path.isfile(candidate):
            browser_path = candidate
            break

    with sync_playwright() as p:
        launch_args = {"headless": True}
        if browser_path:
            launch_args["executable_path"] = browser_path

        try:
            browser = p.chromium.launch(**launch_args)
        except Exception:
            browser = p.chromium.launch(headless=True)

        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1366, "height": 768}
        )
        page = ctx.new_page()

        try:
            page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)
        except Exception:
            pass

        # Smart-wait Fase 1: Tunggu .btn-svr (tombol episode) muncul dulu (max 10 detik)
        # Iframe sering muncul LEBIH CEPAT dari tombol episode, jadi kita HARUS
        # prioritaskan menunggu tombol episode agar tidak salah deteksi sebagai "Film Single".
        buttons_found = False
        for _attempt in range(10):
            btn_count = page.evaluate("""() => document.querySelectorAll('.btn-svr').length""")
            if btn_count > 0:
                buttons_found = True
                break
            page.wait_for_timeout(1000)

        # Smart-wait Fase 2: Jika tombol tidak ditemukan, tunggu iframe saja (max 5 detik lagi)
        if not buttons_found:
            for _attempt in range(5):
                has_iframe = page.evaluate("""() => {
                    const iframe = document.querySelector('iframe');
                    return iframe && iframe.src && !iframe.src.startsWith('about:');
                }""")
                if has_iframe:
                    break
                page.wait_for_timeout(1000)

        # Ambil daftar episode dengan JavaScript (cari .btn-svr buttons)
        ep_info = page.evaluate("""() => {
            const btns = document.querySelectorAll('.btn-svr');
            return Array.from(btns).map((b, i) => ({
                index: i,
                text: b.textContent.trim(),
                mid: b.getAttribute('data-mid') || '',
                tag: b.getAttribute('data-tag') || ''
            }));
        }""")

        if not ep_info:
            # Fallback: cari tombol angka 1-N (tanpa strict check thd totalEps barangkali metadata salah)
            ep_info = page.evaluate("""(totalEps) => {
                const results = [];
                const buttons = document.querySelectorAll('button, a.btn');
                for (const btn of buttons) {
                    const txt = btn.textContent.trim();
                    if (/^\\d+$/.test(txt)) {
                        const num = parseInt(txt);
                        if (num >= 1) {
                            results.push({index: results.length, text: txt});
                        }
                    }
                }
                return results;
            }""", total_eps)

        # Ambil iframe src awal (halaman load pertama)
        initial_src = page.evaluate("""() => {
            const iframe = document.querySelector('iframe');
            return iframe ? iframe.src : '';
        }""")

        if not ep_info:
            if initial_src:
                log.info(f"  Film Single / Movie terdeteksi. Menyimpan iframe utama...")
                episodes_data.append({
                    "episode": "1",
                    "video_embed": initial_src,
                })
                browser.close()
                return episodes_data
            else:
                log.warning(f"  Tidak ada tombol episode & tidak ada iframe video ditemukan.")
                browser.close()
                return []

        if initial_src:
            episodes_data.append({
                "episode": ep_info[0]["text"] if ep_info else "1",
                "video_embed": initial_src,
            })
            log.info(f"  Ep {ep_info[0]['text'] if ep_info else '1'}: {initial_src[:60]}...")

        # Klik setiap episode tombol via JavaScript (bypass iframe interception)
        for i, ep in enumerate(ep_info):
            # Skip episode pertama kalau sudah diambil dari initial page
            if i == 0 and initial_src:
                continue

            try:
                # Klik episode button via JavaScript (tidak terblokir iframe)
                clicked = page.evaluate(f"""(idx) => {{
                    const btns = document.querySelectorAll('.btn-svr');
                    if (btns[idx]) {{
                        btns[idx].click();
                        return true;
                    }}
                    return false;
                }}""", i)

                if not clicked:
                    log.warning(f"  Ep {ep['text']}: tombol tidak ditemukan")
                    continue

                # Tunggu iframe update
                page.wait_for_timeout(2500)

                # Ambil iframe src baru via JavaScript
                src = page.evaluate("""() => {
                    const iframe = document.querySelector('iframe');
                    return iframe ? iframe.src : '';
                }""")

                episodes_data.append({
                    "episode": ep["text"],
                    "video_embed": src or "",
                })
                log.info(f"  Ep {ep['text']}: {src[:60]}..." if src else f"  Ep {ep['text']}: no embed")

            except Exception as e:
                log.warning(f"  Ep {ep['text']} error: {e}")
                episodes_data.append({"episode": ep["text"], "video_embed": "", "error": str(e)})

        # Ambil semua server names
        servers = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('.btn-sv')).map(b => b.textContent.trim()).filter(t => t);
        }""")

        # Tambahkan server info ke setiap episode
        for ep_data in episodes_data:
            ep_data["servers_available"] = servers

        browser.close()

    return episodes_data


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 4: Pipeline utama
# ══════════════════════════════════════════════════════════════════════════════

def run_full_scrape(max_pages: int = None, scrape_episodes: bool = False,
                    max_details: int = None, filter_params: dict = None):
    """
    Pipeline lengkap: Listing → Detail → (Opsional: Episode embeds).
    
    Args:
        max_pages: Batasi jumlah halaman listing (None = semua ~400 halaman)
        scrape_episodes: Jika True, gunakan Playwright untuk ambil video embed per episode
        max_details: Batasi jumlah detail halaman yang di-scrape (None = semua)
        filter_params: Parameter filter untuk listing (misal: {"media_type": "tv"})
    """
    timestamp = int(time.time())

    print(f"\n{'═'*60}")
    print(f"  🎬 DrakorKita Full Scraper")
    print(f"  Target: {BASE_URL}")
    print(f"  Max halaman: {max_pages or 'Semua'}")
    print(f"  Scrape video embed: {'Ya' if scrape_episodes else 'Tidak'}")
    print(f"{'═'*60}\n")

    # Step 1: Crawl listing
    log.info("LANGKAH 1: Crawl daftar drama/film...")
    all_items = crawl_all_listings(max_pages=max_pages, params=filter_params)
    log.info(f"✓ Total {len(all_items)} judul ditemukan\n")

    if not all_items:
        log.error("Tidak ada judul yang ditemukan!")
        return

    # Simpan daftar listing
    listing_path = os.path.join(OUTPUT_DIR, f"drakorkita_listing_{timestamp}.json")
    with open(listing_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "source": BASE_URL,
                "scrape_date": datetime.now().isoformat(),
                "total_titles": len(all_items),
                "pages_crawled": max_pages or "all",
            },
            "titles": all_items
        }, f, ensure_ascii=False, indent=2)
    log.info(f"📁 Daftar listing disimpan: {listing_path}\n")

    # Step 2: Scrape detail untuk setiap judul
    log.info("LANGKAH 2: Scrape detail per judul...")
    details = []
    total = min(len(all_items), max_details) if max_details else len(all_items)

    for i, item in enumerate(all_items[:total], 1):
        try:
            log.info(f"[{i}/{total}] {item['title'] or item['slug']}...")
            detail = scrape_detail(item["detail_url"])

            if detail:
                # Merge listing info
                detail["listing_poster"] = item.get("poster", "")
                detail["listing_rating"] = item.get("rating", "")
                details.append(detail)

                # Opsional: Scrape episode embeds
                if scrape_episodes and detail.get("total_episodes", 0) > 0:
                    log.info(f"  → Scraping {detail['total_episodes']} episode embeds...")
                    ep_data = scrape_episodes_with_browser(item["detail_url"],
                                                            detail["total_episodes"])
                    detail["episode_embeds"] = ep_data

            time.sleep(0.3)  # Rate limiting

        except KeyboardInterrupt:
            log.warning(f"\n⚠ Dihentikan oleh user (Ctrl+C) setelah {len(details)} judul.")
            log.info("Menyimpan data yang sudah ter-scrape...")
            break

    log.info(f"\n✓ Total {len(details)} detail berhasil di-scrape\n")

    # Step 3: Simpan semua detail
    full_path = os.path.join(OUTPUT_DIR, f"drakorkita_full_{timestamp}.json")
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "source": BASE_URL,
                "scrape_date": datetime.now().isoformat(),
                "total_titles_scraped": len(details),
                "episodes_scraped": scrape_episodes,
            },
            "dramas": details
        }, f, ensure_ascii=False, indent=2, default=str)

    size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)
    log.info(f"{'═'*60}")
    log.info(f"✓ SELESAI!")
    log.info(f"  Total judul: {len(details)}")
    log.info(f"  File: {full_path}")
    log.info(f"  Ukuran: {size_mb} MB")
    log.info(f"{'═'*60}")

    return full_path


# ══════════════════════════════════════════════════════════════════════════════
# QUICK SCRAPE: Scrape 1 judul saja (untuk test)
# ══════════════════════════════════════════════════════════════════════════════

def quick_scrape(url: str, with_episodes: bool = False) -> dict | None:
    """Scrape satu judul drama/film beserta detailnya."""
    log.info(f"🎬 Quick scrape: {url}")
    detail = scrape_detail(url)

    if not detail:
        log.error("Gagal scrape detail.")
        return None

    if with_episodes and detail.get("total_episodes", 0) > 0:
        log.info(f"  → Scraping {detail['total_episodes']} episode embeds...")
        detail["episode_embeds"] = scrape_episodes_with_browser(url, detail["total_episodes"])

    # Simpan
    slug = url.rstrip("/").split("/")[-1]
    timestamp = int(time.time())
    out_path = os.path.join(OUTPUT_DIR, f"{slug}_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2, default=str)

    size_kb = round(os.path.getsize(out_path) / 1024, 1)
    log.info(f"✓ Disimpan: {out_path} ({size_kb} KB)")
    return detail


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DrakorKita Drama/Film Scraper")
    parser.add_argument("--url", help="Quick scrape satu URL detail drama")
    parser.add_argument("--pages", type=int, default=None, help="Max halaman listing (default: semua)")
    parser.add_argument("--max-details", type=int, default=None, help="Max judul yang di-detail")
    parser.add_argument("--with-episodes", action="store_true", help="Scrape video embed per episode (butuh Playwright)")
    parser.add_argument("--type", choices=["movie", "tv"], help="Filter tipe: movie atau tv")
    parser.add_argument("--status", choices=["ended", "returning series"], help="Filter status")
    parser.add_argument("--genre", help="Filter genre (misal: Romance)")
    parser.add_argument("--year", help="Filter tahun (misal: 2026)")

    args = parser.parse_args()

    if args.url:
        quick_scrape(args.url, with_episodes=args.with_episodes)
    else:
        params = {}
        if args.type:
            params["media_type"] = args.type
        if args.status:
            params["status"] = args.status
        if args.genre:
            params["genre"] = args.genre
        if args.year:
            params["year"] = args.year

        run_full_scrape(
            max_pages=args.pages,
            scrape_episodes=args.with_episodes,
            max_details=args.max_details,
            filter_params=params if params else None,
        )
