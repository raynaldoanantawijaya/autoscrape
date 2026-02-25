#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  Universal Film/Drama Scraper (Menu 4: Link Lainnya)         ║
║  Teknik gabungan dari DrakorKita + ZeldaEternity + Azarug    ║
║  • Listing: requests+BS4 structured card selectors           ║
║  • Detail: requests+BS4 metadata, episodes, downloads        ║
║  • Video: AJAX via admin-ajax.php, Playwright fallback       ║
║  • Verifikasi: Retry hingga 3x untuk setiap episode          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ─── Setup ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_scrape")
os.makedirs(OUTPUT_DIR, exist_ok=True)

log = logging.getLogger("scrapers.custom")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Domain iklan yang harus diabaikan pada iframe
AD_DOMAINS = [
    'dtscout.com', 'doubleclick', 'googlesyndication', 'adnxs.com',
    'popads', 'popcash', 'propeller', 'onclick', 'adsterra',
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
    'klik.best',
]


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAS UMUM
# ═══════════════════════════════════════════════════════════════════════════════

def _get_html(url: str, retries: int = 3) -> str | None:
    """Fetch HTML dengan retry progresif."""
    for attempt in range(retries):
        try:
            timeout = 15 + (attempt * 10)
            resp = SESSION.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                log.debug(f"Gagal fetch {url} setelah {retries}x: {e}")
    return None


def _is_ad_iframe(src: str) -> bool:
    """Deteksi apakah iframe src adalah iklan/sosmed."""
    if not src or src.startswith('about:'):
        return True
    src_lower = src.lower()
    return any(ad in src_lower for ad in AD_DOMAINS)


def _get_base_url(url: str) -> str:
    """Ekstrak base URL (scheme + domain)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _extract_post_id(soup) -> str:
    """Ekstrak WordPress post ID dari class body (postid-XXXXX) atau article."""
    body = soup.select_one("body")
    if body:
        for cls in body.get("class", []):
            if cls.startswith("postid-"):
                return cls.replace("postid-", "")
    article = soup.select_one("article")
    if article:
        art_id = article.get("id", "")
        m = re.search(r'post-(\d+)', art_id)
        if m:
            return m.group(1)
    # Fallback: cari di shortlink atau input hidden
    shortlink = soup.select_one('link[rel="shortlink"]')
    if shortlink:
        href = shortlink.get("href", "")
        m = re.search(r'\?p=(\d+)', href)
        if m:
            return m.group(1)
    return ""


def _title_clean(t: str) -> str:
    """Bersihkan judul dari prefix/suffix umum."""
    t = re.sub(r'\s+', ' ', t).strip()
    # Hapus prefix umum
    for prefix in ["Nonton ", "Download ", "Streaming ", "Permalink ke: "]:
        if t.startswith(prefix):
            t = t[len(prefix):]
    # Hapus suffix umum
    t = re.sub(r'\s*Subtitle Indonesia\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*Sub Indo\s*$', '', t, flags=re.I)
    return t.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 1: LISTING CRAWLER — Temukan daftar film dari halaman beranda/kategori
# ═══════════════════════════════════════════════════════════════════════════════

# Selector prioritas untuk menemukan "kartu film" di berbagai theme WordPress
CARD_SELECTORS = [
    "article.item",                     # Azarug / LK21 / Rebahin theme
    ".gmr-box-content",                 # GMR theme
    "article",                          # ZeldaEternity / generic WP theme
    "a[href*='/detail/']",             # DrakorKita pattern (direct link cards)
    ".bsx",                             # Alternative WP streaming theme
    ".movie-item",                      # Movie theme
]

TITLE_SELECTORS = [
    ".entry-title a", "h2 a", "h3 a", ".title a", ".tt a", "h4 a",
]


def _fetch_listing_page(url: str, base_url: str) -> list[dict]:
    """Ekstrak daftar film dari satu halaman listing menggunakan structured selectors."""
    html = _get_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = []

    # Coba setiap selector sampai menemukan kartu film
    cards = []
    used_selector = ""
    for selector in CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            used_selector = selector
            break

    if not cards:
        log.debug(f"  Tidak ada kartu film ditemukan di {url}")
        return []

    log.debug(f"  Menggunakan selector '{used_selector}' — {len(cards)} kartu")

    for card in cards:
        # Cari link dan judul
        title = ""
        detail_url = ""

        # Metode 1: Cari dari title selectors di dalam kartu
        for ts in TITLE_SELECTORS:
            title_el = card.select_one(ts)
            if title_el:
                title = title_el.get_text(strip=True)
                detail_url = title_el.get("href", "")
                break

        # Metode 2: Jika kartu itu sendiri adalah <a> tag (DrakorKita style)
        if not detail_url and card.name == "a":
            detail_url = card.get("href", "")
            # Cari judul dari child elements
            for child_sel in [".title", "h3", "h4", ".name", ".tt"]:
                te = card.select_one(child_sel)
                if te:
                    title = te.get_text(strip=True)
                    break
            if not title:
                # Fallback: gunakan teks terpanjang yang bukan durasi
                for txt in card.stripped_strings:
                    if len(txt) > 5 and not re.match(r'^\d{1,2}:\d{2}', txt):
                        title = txt
                        break

        # Metode 3: Fallback ke <a> pertama di dalam kartu
        if not detail_url:
            first_a = card.select_one("a[href]")
            if first_a:
                detail_url = first_a.get("href", "")
                if not title:
                    title = first_a.get("title", "") or first_a.get_text(strip=True)

        if not detail_url or not title:
            continue

        # Normalisasi URL
        if not detail_url.startswith("http"):
            detail_url = urljoin(base_url, detail_url)

        # Filter: skip link yang bukan halaman film
        url_lower = detail_url.lower()
        skip_patterns = ['/genre/', '/category/', '/tag/', '/year/', '/country/',
                         '/page/', '/author/', 'javascript:', '#', 'mailto:',
                         'facebook.com', 'twitter.com', 'instagram.com']
        if any(p in url_lower for p in skip_patterns):
            continue

        # Bersihkan judul
        title = _title_clean(title)
        if len(title) < 3:
            continue

        # Poster
        poster = ""
        img = card.select_one("img")
        if img:
            poster = img.get("data-src") or img.get("src") or ""

        # Quality badge
        quality = ""
        q_el = card.select_one(".gmr-quality-item a, .gmr-quality-item, .quality")
        if q_el:
            quality = q_el.get_text(strip=True)

        # Rating
        rating = ""
        r_el = card.select_one(".gmr-rating-item, .rating")
        if r_el:
            rating = r_el.get_text(strip=True)

        items.append({
            "title": title,
            "detail_url": detail_url,
            "poster": poster,
            "quality": quality,
            "rating": rating,
        })

    return items


def _detect_next_page(soup, current_url: str, base_url: str) -> str | None:
    """Deteksi URL halaman selanjutnya dari pagination."""
    # Metode 1: CSS selector klasik
    next_btn = soup.select_one('a.next.page-numbers, a.next, a[rel="next"], .pagination .next a, .nav-next a')
    if next_btn:
        href = next_btn.get("href", "")
        if href and href != current_url:
            return href if href.startswith("http") else urljoin(base_url, href)

    # Metode 2: Cari berdasarkan teks "Next" atau "→"
    for a in soup.select('a[href]'):
        txt = a.get_text(strip=True).lower()
        if txt in ['next', 'next »', '»', '→', 'selanjutnya', 'berikutnya']:
            href = a.get("href", "")
            if href and href != current_url and 'javascript' not in href:
                return href if href.startswith("http") else urljoin(base_url, href)

    return None


def crawl_film_listings(start_url: str, max_pages: int = 9999, max_films: int = 99999) -> list[dict]:
    """Crawl daftar film dari halaman beranda/kategori TANPA BATAS sampai habis."""
    base_url = _get_base_url(start_url)
    all_films = []
    seen_urls = set()
    current_url = start_url
    consecutive_empty = 0  # Hitung halaman kosong berturut-turut

    for page_num in range(1, max_pages + 1):
        log.info(f"  📄 Halaman {page_num}: {current_url}")

        films = _fetch_listing_page(current_url, base_url)

        # Deduplicate
        new_count = 0
        for f in films:
            if f["detail_url"] not in seen_urls:
                seen_urls.add(f["detail_url"])
                all_films.append(f)
                new_count += 1

        log.info(f"     → {new_count} judul baru (total: {len(all_films)})")

        if not films or new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                log.info(f"  ✓ 2 halaman kosong berturut-turut, semua film sudah terkumpul.")
                break
        else:
            consecutive_empty = 0

        # Cari halaman berikutnya
        html = _get_html(current_url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            next_url = _detect_next_page(soup, current_url, base_url)
            if next_url and next_url != current_url:
                current_url = next_url
                time.sleep(0.5)
            else:
                # Coba pola /page/N/ manual
                if page_num == 1 and '?' not in start_url:
                    next_try = f"{start_url.rstrip('/')}/page/2/"
                    test_html = _get_html(next_try)
                    if test_html:
                        current_url = next_try
                        time.sleep(0.5)
                    else:
                        break
                else:
                    # Increment page number di URL
                    m = re.search(r'/page/(\d+)/', current_url)
                    if m:
                        next_num = int(m.group(1)) + 1
                        current_url = re.sub(r'/page/\d+/', f'/page/{next_num}/', current_url)
                        time.sleep(0.5)
                    else:
                        break
        else:
            break

    return all_films


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2: DETAIL SCRAPER — Scrape metadata, episodes, downloads dari 1 film
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_video_embeds_via_ajax(post_id: str, page_url: str, base_url: str) -> list[dict]:
    """Ambil video embed URLs via WordPress AJAX endpoint (teknik ZeldaEternity)."""
    embeds = []
    if not post_id:
        return embeds

    ajax_url = f"{base_url}/wp-admin/admin-ajax.php"

    for tab in ["p1", "p2", "p3", "p4"]:
        try:
            resp = SESSION.post(ajax_url, data={
                "action": "muvipro_player_content",
                "tab": tab,
                "post_id": post_id,
            }, headers={
                **HEADERS,
                "Referer": page_url,
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=10)

            if resp.status_code == 200 and resp.text.strip():
                frag = BeautifulSoup(resp.text, "html.parser")
                iframe = frag.select_one("iframe")
                if iframe:
                    src = iframe.get("src") or iframe.get("SRC") or ""
                    if src and not _is_ad_iframe(src):
                        embeds.append({"server": tab, "url": src})
        except Exception:
            pass

    return embeds


def scrape_detail(detail_url: str, base_url: str) -> dict:
    """Scrape halaman detail film/series: metadata, episodes, downloads, video."""
    result = {
        "title": "",
        "detail_url": detail_url,
        "type": "Movie",
        "poster": "",
        "sinopsis": "",
        "genres": [],
        "cast": [],
        "directors": [],
        "year": "",
        "country": "",
        "rating": "",
        "quality": "",
        "duration": "",
        "episodes": [],
        "total_episodes": 0,
        "download_links": [],
        "video_embed": "",
        "video_servers": [],
    }

    html = _get_html(detail_url, retries=5)
    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # ── JUDUL ──
    # Prioritas: h1[itemprop=headline] > h1.entry-title > 2nd h1 (DrakorKita: 1st h1 = site title)
    h1_headline = soup.select_one('h1[itemprop="headline"]')
    h1_entry = soup.select_one('h1.entry-title')
    all_h1 = soup.select('h1')

    if h1_headline:
        result["title"] = _title_clean(h1_headline.get_text(strip=True))
    elif h1_entry:
        result["title"] = _title_clean(h1_entry.get_text(strip=True))
    elif len(all_h1) >= 2:
        # DrakorKita: h1 pertama = "Drama Korea" (site title), h1 kedua = judul film
        result["title"] = _title_clean(all_h1[1].get_text(strip=True))
    elif all_h1:
        result["title"] = _title_clean(all_h1[0].get_text(strip=True))

    # Fallback dari slug
    if not result["title"] or result["title"].lower() in ['drama korea', 'nonton', 'streaming']:
        slug = detail_url.rstrip("/").split("/")[-1]
        parts = slug.split("-")
        if len(parts) >= 2 and len(parts[-1]) <= 5 and parts[-1].isalnum():
            parts = parts[:-1]
        result["title"] = " ".join(parts).title()

    # ── POSTER ──
    for sel in ["img.wp-post-image", ".thumb img", ".gmr-movie-data img",
                 ".poster img", "img[itemprop='image']"]:
        img = soup.select_one(sel)
        if img:
            result["poster"] = img.get("data-src") or img.get("src") or ""
            break

    # ── SINOPSIS ──
    content = soup.select_one(".entry-content, .desc, .sinopsis")
    if content:
        paragraphs = content.select("p")
        valid = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
        result["sinopsis"] = "\n".join(valid[:3])

    if not result["sinopsis"]:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result["sinopsis"] = meta_desc.get("content", "")

    # ── METADATA (.gmr-moviedata / .gmr-movie-meta / .infox .spe / .anf li) ──
    meta_selectors = [".gmr-moviedata", ".gmr-movie-meta", ".gmr-movie-meta-list .gmr-movie-meta",
                      ".infox .spe span", ".anf li"]
    for meta_sel in meta_selectors:
        for meta_div in soup.select(meta_sel):
            label_full = meta_div.get_text(" ", strip=True).lower()

            if "genre" in label_full and not result["genres"]:
                result["genres"] = [a.get_text(strip=True) for a in meta_div.select("a")] or \
                                   [g.strip() for g in label_full.split(":")[-1].split(",") if g.strip()]
            elif any(k in label_full for k in ["pemain", "cast", "bintang", "aktor"]) and not result["cast"]:
                result["cast"] = [a.get_text(strip=True) for a in meta_div.select("a")] or \
                                 [c.strip() for c in label_full.split(":")[-1].split(",") if c.strip()]
            elif any(k in label_full for k in ["sutradara", "director", "direksi"]) and not result["directors"]:
                result["directors"] = [a.get_text(strip=True) for a in meta_div.select("a")] or \
                                      [d.strip() for d in label_full.split(":")[-1].split(",") if d.strip()]
            elif any(k in label_full for k in ["rilis", "tahun", "year", "release"]) and not result["year"]:
                links = meta_div.select("a")
                if links:
                    result["year"] = links[0].get_text(strip=True)
                else:
                    m = re.search(r'(\d{4})', label_full)
                    if m:
                        result["year"] = m.group(1)
            elif any(k in label_full for k in ["negara", "country"]) and not result["country"]:
                result["country"] = ", ".join(a.get_text(strip=True) for a in meta_div.select("a"))
            elif any(k in label_full for k in ["rating", "imdb"]) and not result["rating"]:
                m = re.search(r'[\d.]+', label_full)
                if m:
                    result["rating"] = m.group(0)
            elif any(k in label_full for k in ["kualitas", "quality"]) and not result["quality"]:
                links = meta_div.select("a")
                result["quality"] = links[0].get_text(strip=True) if links else ""
            elif any(k in label_full for k in ["durasi", "duration"]) and not result["duration"]:
                m = re.search(r'[\d]+\s*(?:min|menit|jam)', label_full, re.IGNORECASE)
                result["duration"] = m.group(0) if m else ""

    # ── FALLBACK METADATA: DrakorKita ".anf li" dengan " : " separator ──
    if not result["genres"] or not result["cast"]:
        info_fields = {}
        for li in soup.select(".anf li"):
            text = li.get_text(" ", strip=True)
            if " : " in text:
                key, _, value = text.partition(" : ")
                info_fields[key.strip().lower()] = value.strip()
        # Juga cek standalone <span> dengan " : "
        if not info_fields:
            for span in soup.select("span"):
                text = span.get_text(" ", strip=True)
                if " : " in text and len(text) < 150:
                    key, _, value = text.partition(" : ")
                    k = key.strip().lower()
                    if k and k not in ("sinopsis", "informasi") and k not in info_fields:
                        info_fields[k] = value.strip()

        if not result["year"] and info_fields.get("first_air_date"):
            result["year"] = info_fields["first_air_date"]
        if not result["type"]:
            result["type"] = info_fields.get("type", "Movie")
        result["status"] = info_fields.get("status", "")
        result["season"] = info_fields.get("season", "")

    # ── FALLBACK GENRE: DrakorKita (.gnr a) ──
    if not result["genres"]:
        gnr = soup.select_one(".gnr")
        if gnr:
            result["genres"] = [a.get_text(strip=True) for a in gnr.select("a") if a.get_text(strip=True)]
        else:
            # URL-param based genre links
            infox = soup.select_one(".infox, .detail-content")
            search_area = infox if infox else soup
            result["genres"] = [a.get_text(strip=True) for a in search_area.select("a[href*='genre=']") if a.get_text(strip=True)]

    # ── FALLBACK CAST: DrakorKita (a[href*='cast=']) ──
    if not result["cast"]:
        cast_area = soup.select_one(".desc-wrap") or soup.select_one(".infox") or soup
        raw_cast = [a.get_text(strip=True) for a in cast_area.select("a[href*='cast=']") if a.get_text(strip=True)]
        # Fix DrakorKita merged "Lee Na-youngas Yoon Ra-young" → "Lee Na-young"
        # Pattern: actor name ends with lowercase, then "as" merges, then role starts with uppercase
        cleaned = []
        for c in raw_cast:
            # Find pattern: lowercase letter + "as" + uppercase letter → split and keep left part
            m = re.search(r'^(.+?[a-z])as\s*[A-Z]', c)
            if m:
                c = m.group(1)
            c = c.strip()
            if c and c not in cleaned:
                cleaned.append(c)
        result["cast"] = cleaned

    # ── FALLBACK DIRECTORS: DrakorKita (a[href*='crew=']) ──
    if not result["directors"]:
        crew_area = soup.select_one(".desc-wrap") or soup.select_one(".infox") or soup
        result["directors"] = [a.get_text(strip=True) for a in crew_area.select("a[href*='crew=']") if a.get_text(strip=True)]

    # ── EPISODE LIST ──
    ep_selectors = [
        ".gmr-listseries a",
        ".episodelist a",
        "ul.lstep li a",
        ".list-episode li a",
        ".eplister li a",
    ]
    episodes = []
    seen_ep = set()
    for ep_sel in ep_selectors:
        for ep_link in soup.select(ep_sel):
            ep_url = ep_link.get("href", "")
            ep_text = ep_link.get_text(strip=True)
            if ep_url and ep_url not in seen_ep and ep_text:
                # Filter: hanya link episode yang valid (biasanya /eps/ atau /episode/)
                if not ep_url.startswith("http"):
                    ep_url = urljoin(base_url, ep_url)
                seen_ep.add(ep_url)
                episodes.append({"label": ep_text, "url": ep_url})

    if episodes:
        result["type"] = "TV Series"
        result["total_episodes"] = len(episodes)
        result["episodes"] = episodes

    # ── DOWNLOAD LINKS ──
    downloads = []
    dl_area = soup.select_one("#download, .download, .gmr-download-list, .soraddlx")
    if dl_area:
        for a in dl_area.select("a[href]"):
            href, text = a.get("href", ""), a.get_text(strip=True)
            if href and "javascript" not in href.lower() and "klik.best" not in href:
                downloads.append({"text": text or "Download", "url": href})
    else:
        # DrakorKita: tombol #nonot
        dl_btn = soup.select_one("#nonot, a[id='nonot']")
        if dl_btn:
            dl_url = dl_btn.get("href", "")
            if dl_url and dl_url != "#":
                downloads.append({"text": "DOWNLOAD", "url": dl_url})
        else:
            # Fallback: cari tombol download
            for a in soup.select("a[href]"):
                txt = a.get_text(strip=True).lower()
                if "download" in txt or "unduh" in txt:
                    href = a.get("href", "")
                    if href and "javascript" not in href.lower():
                        downloads.append({"text": a.get_text(strip=True), "url": href})

    result["download_links"] = downloads

    # ── VIDEO EMBED via AJAX (cepat, tanpa browser) ──
    post_id = _extract_post_id(soup)
    if post_id:
        embeds = _fetch_video_embeds_via_ajax(post_id, detail_url, base_url)
        if embeds:
            result["video_embed"] = embeds[0]["url"]
            result["video_servers"] = embeds

    # ── FALLBACK: Jika AJAX gagal, cek iframe statis ──
    if not result["video_embed"]:
        iframe = soup.select_one("iframe[src]")
        if iframe:
            src = iframe.get("src", "")
            if not _is_ad_iframe(src):
                result["video_embed"] = src

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3: EPISODE SCRAPER — Scrape video embed per episode DENGAN VERIFIKASI
# ═══════════════════════════════════════════════════════════════════════════════

def _scrape_episode_video(ep_url: str, base_url: str) -> dict:
    """Scrape video embed dari halaman episode tunggal."""
    result = {"url": ep_url, "video_embed": "", "video_servers": [], "download_links": []}

    html = _get_html(ep_url, retries=3)
    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # AJAX dulu (paling cepat)
    post_id = _extract_post_id(soup)
    if post_id:
        embeds = _fetch_video_embeds_via_ajax(post_id, ep_url, base_url)
        if embeds:
            result["video_embed"] = embeds[0]["url"]
            result["video_servers"] = embeds

    # Fallback iframe statis
    if not result["video_embed"]:
        iframe = soup.select_one("iframe[src]")
        if iframe:
            src = iframe.get("src", "")
            if not _is_ad_iframe(src):
                result["video_embed"] = src

    # Download links episode
    dl_area = soup.select_one("#download, .download, .gmr-download-list, .soraddlx")
    if dl_area:
        for a in dl_area.select("a[href]"):
            href, text = a.get("href", ""), a.get_text(strip=True)
            if href and "javascript" not in href.lower() and "klik.best" not in href:
                result["download_links"].append({"text": text or "Download", "url": href})

    return result


def extract_iframe_from_page(url: str, browser_path: str = None) -> list[str]:
    """Playwright fallback: Buka halaman dan ambil semua iframe valid (bukan iklan)."""
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
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 768}
                )
                page = ctx.new_page()

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass

                page.wait_for_timeout(3000)

                # Klik tombol server untuk memunculkan iframe
                page.evaluate("""() => {
                    let btns = document.querySelectorAll('.btn-svr, .server-btn, .gmr-player-btn');
                    if (btns.length > 0) btns[0].click();
                }""")
                page.wait_for_timeout(2000)

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


def _scrape_episodes_with_verification(episodes: list, base_url: str, max_retries: int = 5) -> list:
    """Scrape semua episode secara paralel DENGAN GARANSI verifikasi multi-ronde."""
    log.info(f"     📺 Scraping {len(episodes)} episode secara paralel...")

    browser_path = None
    for candidate in ["/usr/bin/chromium", "/usr/bin/chromium-browser",
                      "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
        if os.path.isfile(candidate):
            browser_path = candidate
            break

    # ── RONDE 1: Requests + AJAX (cepat, paralel 8 thread) ──
    results = [None] * len(episodes)

    def _worker(idx, ep):
        ep_data = _scrape_episode_video(ep["url"], base_url)
        return idx, ep_data

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_worker, i, ep): i for i, ep in enumerate(episodes)}
        for f in as_completed(futures):
            try:
                idx, data = f.result()
                results[idx] = {
                    "label": episodes[idx]["label"],
                    "url": episodes[idx]["url"],
                    "video_embed": data["video_embed"],
                    "video_servers": data["video_servers"],
                    "download_links": data["download_links"],
                }
            except Exception as e:
                log.debug(f"     Worker error: {e}")

    # Pastikan semua slot terisi (walau kosong)
    for i in range(len(results)):
        if results[i] is None:
            results[i] = {
                "label": episodes[i]["label"],
                "url": episodes[i]["url"],
                "video_embed": "",
                "video_servers": [],
                "download_links": [],
            }

    filled_r1 = sum(1 for r in results if r.get("video_embed"))
    log.info(f"     → Ronde 1 (AJAX): {filled_r1}/{len(episodes)} episode mendapat video")

    # ── RONDE 2: Re-try AJAX untuk yang gagal (kadang server lambat) ──
    missing = [(i, results[i]) for i in range(len(results)) if not results[i].get("video_embed")]
    if missing:
        log.info(f"     ⚠ {len(missing)} episode belum dapat. Re-try AJAX...")
        time.sleep(1)
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(_worker, i, ep): (i, ep) for i, ep in missing}
            for f in as_completed(futures):
                try:
                    idx, data = f.result()
                    if data["video_embed"]:
                        results[idx]["video_embed"] = data["video_embed"]
                        results[idx]["video_servers"] = data["video_servers"]
                        results[idx]["download_links"] = data.get("download_links", [])
                except Exception:
                    pass

        filled_r2 = sum(1 for r in results if r.get("video_embed"))
        log.info(f"     → Ronde 2 (AJAX retry): {filled_r2}/{len(episodes)} episode")

    # ── RONDE 3-5: Playwright fallback untuk yang masih gagal ──
    missing = [(i, results[i]) for i in range(len(results)) if not results[i].get("video_embed")]

    if missing:
        log.info(f"     🔧 {len(missing)} episode masih kosong. Melancarkan Playwright...")
        for retry_round in range(1, max_retries + 1):
            still_missing = []
            for i, ep in missing:
                try:
                    iframes = extract_iframe_from_page(ep["url"], browser_path)
                    if iframes:
                        results[i]["video_embed"] = iframes[0]
                        results[i]["video_servers"] = [{"server": f"pw_{j}", "url": u} for j, u in enumerate(iframes)]
                    else:
                        still_missing.append((i, ep))
                except Exception:
                    still_missing.append((i, ep))

            if not still_missing:
                log.info(f"     ✓ Semua episode 100% terverifikasi! (Playwright ronde {retry_round})")
                break
            missing = still_missing
            if retry_round < max_retries:
                log.info(f"     ⚠ Masih {len(missing)} episode kosong, retry Playwright ronde {retry_round+1}...")
                time.sleep(2)  # Jeda sebelum retry
            else:
                log.info(f"     ⚠ {len(missing)} episode tetap kosong setelah {max_retries} ronde Playwright")

    # ── LAPORAN FINAL ──
    filled = sum(1 for r in results if r.get("video_embed"))
    total = len(episodes)
    pct = round(filled / total * 100, 1) if total else 0
    log.info(f"     ✓ Episode selesai: {filled}/{total} ({pct}%) berhasil diambil videonya")
    if filled < total:
        log.info(f"     ℹ {total - filled} episode mungkin memang belum punya video di server sumber")

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE UTAMA
# ═══════════════════════════════════════════════════════════════════════════════

def run_custom_scrape(url: str, output_name: str = "custom_film"):
    """Pipeline scraper universal: Listing → Detail → Episode → Verifikasi → JSON."""
    log.info(f"🚀 Memindai Struktur URL: {url}")
    timestamp = int(time.time())
    base_url = _get_base_url(url)

    # ── FASE 1: Deteksi — Apakah ini Katalog atau Detail Film? ──
    html = _get_html(url)
    if not html:
        log.error("✗ Gagal memuat URL.")
        return

    soup = BeautifulSoup(html, "html.parser")

    # Cek apakah ini halaman DETAIL (sudah ada episode list atau iframe video)
    ep_check = soup.select(".gmr-listseries a, .episodelist a, ul.lstep li a")
    iframe_check = soup.select_one("iframe[src]")
    has_iframe = iframe_check and not _is_ad_iframe(iframe_check.get("src", ""))

    found_films = []

    if ep_check or has_iframe:
        # Halaman DETAIL tunggal
        title = ""
        h1 = soup.select_one("h1.entry-title, h1")
        if h1:
            title = _title_clean(h1.get_text(strip=True))
        found_films = [{"title": title or "Unknown", "detail_url": url}]
        log.info(f"✓ URL terdeteksi sebagai Halaman Detail Film (Episode: {len(ep_check)}, Iframe: {'✓' if has_iframe else '✗'})")
    else:
        # Halaman KATALOG — crawl listing
        log.info("✓ URL terdeteksi sebagai Halaman Katalog. Memulai crawling...")
        found_films = crawl_film_listings(url)  # Tanpa batas — crawl sampai habis

        if not found_films:
            log.error("✗ Tidak ada film ditemukan di halaman ini.")
            return

    log.info(f"✓ Total {len(found_films)} judul ditemukan.\n")

    # ── FASE 2: Tanya User ──
    def _ask(prompt, default=""):
        suffix = f" [{default}]" if default else ""
        try:
            val = input(f"  ?  {prompt}{suffix}: ").strip()
            return val if val else default
        except (KeyboardInterrupt, EOFError):
            return default

    if len(found_films) > 1:
        # Tampilkan preview
        for i, f in enumerate(found_films[:8]):
            title_short = f['title'][:60] if f.get('title') else 'Unknown'
            print(f"  {i+1}. {title_short}")
        if len(found_films) > 8:
            print(f"  ... dan {len(found_films) - 8} lainnya.")
        print()

        limit_str = _ask(f"Berapa film yang ingin di-scrape? (1-{len(found_films)}, 'all' untuk semua)", "all")
        if limit_str.lower() != 'all':
            try:
                limit = int(limit_str)
                found_films = found_films[:limit]
            except ValueError:
                log.error("Input tidak valid, membatalkan.")
                return

    # ── FASE 3: Scrape Detail + Episode secara Paralel ──
    log.info(f"\n🚀 Memulai Deep-Scrape {len(found_films)} Film/Drama...\n")

    all_results = []
    lock = threading.Lock()
    completed = [0]

    def _process_film(film_info):
        f_url = film_info.get("detail_url", film_info.get("url", ""))
        f_title = film_info.get("title", "Unknown")

        try:
            # Scrape detail halaman film
            detail = scrape_detail(f_url, base_url)

            # Gunakan judul dari listing jika detail gagal mendapat judul
            if not detail["title"]:
                detail["title"] = f_title

            # Jika ada episode, scrape semua episode dengan verifikasi
            if detail["episodes"]:
                ep_results = _scrape_episodes_with_verification(
                    detail["episodes"], base_url, max_retries=2
                )
                detail["episode_embeds"] = ep_results
                detail["total_episodes"] = len(ep_results)
            else:
                # Film biasa tanpa episode — video embed sudah diambil di scrape_detail
                detail["episode_embeds"] = []

                # Jika AJAX + static iframe gagal, coba Playwright sebagai backup
                if not detail["video_embed"]:
                    try:
                        iframes = extract_iframe_from_page(f_url)
                        if iframes:
                            detail["video_embed"] = iframes[0]
                            detail["video_servers"] = [{"server": f"pw_{j}", "url": u} for j, u in enumerate(iframes)]
                    except Exception:
                        pass

            with lock:
                all_results.append(detail)
                completed[0] += 1

                # Log progress
                v = 1 if detail.get("video_embed") else 0
                e = detail.get("total_episodes", 0)
                ep_filled = sum(1 for ep in detail.get("episode_embeds", []) if ep and ep.get("video_embed"))
                dl = len(detail.get("download_links", []))
                g = len(detail.get("genres", []))

                parts = []
                if e:
                    parts.append(f"📺 {ep_filled}/{e} Eps")
                if v:
                    parts.append(f"🎬 Video ✓")
                if dl:
                    parts.append(f"📥 {dl} DL")
                if g:
                    parts.append(f"🏷️ {g} Genre")

                summary = " | ".join(parts) if parts else "⚠ Minimal data"
                title_short = detail['title'][:45] + "..." if len(detail['title']) > 45 else detail['title']
                log.info(f"  ✓ [{completed[0]}/{len(found_films)}] {title_short} — {summary}")

        except Exception as exc:
            with lock:
                completed[0] += 1
                log.error(f"  ✗ [{completed[0]}/{len(found_films)}] {f_title}: {exc}")

    # Gunakan max 5 workers untuk detail (masing-masing bisa spawn sub-threads untuk episodes)
    with ThreadPoolExecutor(max_workers=min(len(found_films), 5)) as executor:
        tasks = {executor.submit(_process_film, f): f for f in found_films}
        try:
            for future in as_completed(tasks):
                future.result()
        except KeyboardInterrupt:
            log.warning("⚠ Dibatalkan user.")
            executor.shutdown(wait=False, cancel_futures=True)

    # ── SIMPAN HASIL ──
    safe_name = re.sub(r'[^A-Za-z0-9_]+', '_', output_name).strip('_').lower()
    full_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{timestamp}.json")

    output_data = {
        "metadata": {
            "scraper_name": "Universal Film Scraper v3.0",
            "source_url": url,
            "scrape_date": datetime.now().isoformat(),
            "total_films": len(all_results),
            "execution_time_sec": round(time.time() - timestamp, 1),
        },
        "data": all_results
    }

    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    size_kb = round(os.path.getsize(full_path) / 1024, 1)

    log.info(f"\n{'═'*60}")
    log.info(f"✓ SELESAI UNIVERSAL SCRAPE!")
    log.info(f"  Berhasil: {len(all_results)} Judul")
    log.info(f"  File: {full_path} ({size_kb} KB)")
    log.info(f"{'═'*60}")
