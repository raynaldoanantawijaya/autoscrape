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

    # Setiap item ada di <a> dengan href ke /detail/...
    for card in soup.select("a[href*='/detail/']"):
        href = card.get("href", "")
        if "/detail/" not in href:
            continue

        # Cari judul
        title_text = ""
        title_el = card.select_one(".title, h3, h4, .name")
        if title_el:
            title_text = title_el.get_text(strip=True)
        else:
            # Fallback: ambil teks panjang dari card
            texts = [t.strip() for t in card.stripped_strings if len(t.strip()) > 5]
            title_text = texts[0] if texts else ""

        # Cari poster image
        poster = ""
        img = card.select_one("img")
        if img:
            poster = img.get("data-src") or img.get("src") or ""
            if poster and not poster.startswith("http"):
                poster = urljoin(BASE_URL, poster)

        # Cari rating
        rating = ""
        rating_el = card.select_one(".rating, .score, .vote")
        if rating_el:
            rating = rating_el.get_text(strip=True)

        # Cari episode info
        episode_info = ""
        ep_el = card.select_one(".episode, .ep, .quality")
        if ep_el:
            episode_info = ep_el.get_text(strip=True)

        # Normalisasi URL
        detail_url = href if href.startswith("http") else urljoin(BASE_URL, href)

        # Extract slug dari URL
        slug = href.rstrip("/").split("/")[-1]

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
    """Scrape halaman detail: sinopsis, info, cast, genre, poster, episode list."""
    try:
        resp = SESSION.get(detail_url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Gagal fetch detail {detail_url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {"url": detail_url}

    # ── Judul ──
    h1 = soup.select_one("h1")
    result["title"] = h1.get_text(strip=True) if h1 else ""

    # ── Poster ──
    poster_img = soup.select_one(".poster img, .thumbnail img, .detail img")
    if poster_img:
        result["poster"] = poster_img.get("data-src") or poster_img.get("src") or ""
    else:
        result["poster"] = ""

    # ── Banner / Backdrop ──
    banner_img = soup.select_one(".banner img, .backdrop img, .movie-bg img")
    if banner_img:
        result["banner"] = banner_img.get("data-src") or banner_img.get("src") or ""

    # ── Sinopsis ──
    synopsis_el = soup.find(string=re.compile(r"Sinopsis", re.I))
    if synopsis_el:
        parent = synopsis_el.find_parent()
        if parent:
            # Ambil teks setelah header sinopsis
            next_p = parent.find_next("p")
            if next_p:
                result["sinopsis"] = next_p.get_text(strip=True)
            else:
                # Coba ambil sibling text
                sibling = parent.find_next_sibling()
                if sibling:
                    result["sinopsis"] = sibling.get_text(strip=True)

    if "sinopsis" not in result:
        # Fallback: cari meta description
        meta = soup.find("meta", {"name": "description"})
        if meta:
            result["sinopsis"] = meta.get("content", "")

    # ── Informasi detail (Type, Status, Season, Episode Count, dll) ──
    info_section = soup.find(string=re.compile(r"Informasi", re.I))
    if info_section:
        info_parent = info_section.find_parent()
        if info_parent:
            info_container = info_parent.find_parent() or info_parent
            for li in info_container.find_all("li"):
                text = li.get_text(strip=True)
                if ":" in text:
                    key, _, value = text.partition(":")
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()
                    if key and value:
                        result[key] = value

    # ── Genre ──
    genres = []
    for a in soup.select("a[href*='genre=']"):
        g = a.get_text(strip=True)
        if g and g not in genres:
            genres.append(g)
    result["genres"] = genres

    # ── Cast ──
    cast = []
    for a in soup.select("a[href*='cast=']"):
        c = a.get_text(strip=True)
        if c and c not in cast:
            cast.append(c)
    result["cast"] = cast

    # ── Director ──
    directors = []
    for a in soup.select("a[href*='crew=']"):
        d = a.get_text(strip=True)
        if d and d not in directors:
            directors.append(d)
    result["directors"] = directors

    # ── Country ──
    country = []
    for a in soup.select("a[href*='country=']"):
        c = a.get_text(strip=True)
        if c and c not in country:
            country.append(c)
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

    # ── Episode List ──
    episodes = []
    ep_buttons = soup.select("[data-episode], .btn-svr, .ep-btn, [class*='episode']")

    if ep_buttons:
        for btn in ep_buttons:
            ep_num = btn.get("data-episode") or btn.get_text(strip=True)
            ep_data = {
                "episode": ep_num,
                "movie_id": btn.get("data-movieid", ""),
                "tag": btn.get("data-tag", ""),
            }
            # Hindari duplikat
            if ep_data not in episodes:
                episodes.append(ep_data)
    else:
        # Fallback: cari tombol angka episode
        for btn in soup.select("a.btn, button.btn, .episode-btn"):
            text = btn.get_text(strip=True)
            if text.isdigit():
                episodes.append({"episode": text})

    result["episodes"] = episodes
    result["total_episodes"] = len(episodes)

    # ── Video Servers ──
    servers = []
    for srv_btn in soup.select("[data-server], .server-btn, .btn-server"):
        srv_name = srv_btn.get_text(strip=True)
        srv_id = srv_btn.get("data-server", "")
        if srv_name:
            servers.append({"name": srv_name, "id": srv_id})
    result["servers"] = servers

    # ── Video Iframe src ──
    iframe = soup.select_one("iframe[src]")
    if iframe:
        result["video_embed"] = iframe.get("src", "")

    # ── Download button / links ──
    download_links = []
    for a in soup.select("a[href*='download'], a[id='nonot'], .download-btn a"):
        dl_url = a.get("href", "")
        dl_text = a.get_text(strip=True)
        if dl_url and dl_url != "#":
            download_links.append({"text": dl_text, "url": dl_url})
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
        log.warning("Playwright tidak tersedia, skip scraping video embed.")
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

        page.wait_for_timeout(2000)

        for ep in range(1, total_eps + 1):
            try:
                # Klik tombol episode
                ep_btn = page.locator(f"[data-episode='{ep}'], button:text('{ep}')").first
                if ep_btn.is_visible():
                    ep_btn.click()
                    page.wait_for_timeout(2000)

                    # Ambil iframe src
                    iframe = page.locator("iframe").first
                    src = iframe.get_attribute("src") if iframe.is_visible() else ""

                    # Ambil semua server options
                    server_info = []
                    for srv in page.locator("[data-server], .btn-server, .server-btn").all():
                        srv_name = srv.inner_text()
                        if srv_name:
                            server_info.append(srv_name.strip())

                    episodes_data.append({
                        "episode": ep,
                        "video_embed": src or "",
                        "servers_available": server_info,
                    })
                    log.info(f"  Episode {ep}: {src[:60]}..." if src else f"  Episode {ep}: no embed")
            except Exception as e:
                log.warning(f"  Episode {ep} error: {e}")
                episodes_data.append({"episode": ep, "video_embed": "", "error": str(e)})

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
