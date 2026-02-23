#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  ZeldaEternity (INDOFILM) Full Scraper                      ║
║  Target: https://zeldaeternity.com/                          ║
║  Scrape: Judul, Sinopsis, Genre, Cast, Download, Episode     ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import time
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ─── Konfigurasi ────────────────────────────────────────────────────────────
BASE_URL = "https://zeldaeternity.com"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil_scrape", "zeldaeternity")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ZeldaEternity")


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 1: Crawl listing pages
# ══════════════════════════════════════════════════════════════════════════════

def fetch_listing_page(url: str) -> list[dict]:
    """Ambil daftar film/series dari satu halaman listing."""
    try:
        resp = SESSION.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Gagal fetch listing {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []

    for article in soup.select("article"):
        # Judul & URL
        title_el = article.select_one(".entry-title a, h2 a, .title a")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        detail_url = title_el.get("href", "")
        if not detail_url:
            continue

        # Poster
        img = article.select_one("img")
        poster = ""
        if img:
            poster = img.get("data-src") or img.get("src") or ""

        # Quality badge
        quality = ""
        q_el = article.select_one(".gmr-quality-item a, .quality")
        if q_el:
            quality = q_el.get_text(strip=True)

        # Tipe (movie vs tv)
        is_tv = "/tv/" in detail_url

        items.append({
            "title": title,
            "detail_url": detail_url,
            "poster": poster,
            "quality": quality,
            "type": "TV Series" if is_tv else "Movie",
        })

    return items


def get_total_pages(url: str) -> int:
    """Cari total halaman dari pagination."""
    try:
        resp = SESSION.get(url, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        pages = soup.select("ul.page-numbers li a.page-numbers")
        nums = []
        for p in pages:
            txt = p.get_text(strip=True)
            if txt.isdigit():
                nums.append(int(txt))
        return max(nums) if nums else 1
    except Exception:
        return 1


def crawl_all_listings(category_url: str = None, max_pages: int = None) -> list[dict]:
    """Crawl semua halaman listing."""
    base = category_url or BASE_URL
    all_items = []
    seen_urls = set()

    # Deteksi total halaman
    total = get_total_pages(base)
    if max_pages:
        total = min(total, max_pages)

    for page_num in range(1, total + 1):
        if page_num == 1:
            url = base
        else:
            url = f"{base.rstrip('/')}/page/{page_num}/"

        log.info(f"📄 Crawling halaman {page_num}/{total}...")
        items = fetch_listing_page(url)

        new_count = 0
        for item in items:
            if item["detail_url"] not in seen_urls:
                seen_urls.add(item["detail_url"])
                all_items.append(item)
                new_count += 1

        log.info(f"  → {new_count} judul baru (total: {len(all_items)})")

        if not items:
            log.info("  Halaman kosong, berhenti.")
            break

        time.sleep(0.5)

    return all_items


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 2: Scrape detail page
# ══════════════════════════════════════════════════════════════════════════════

def scrape_detail(detail_url: str) -> dict | None:
    """Scrape halaman detail film/series."""
    try:
        resp = SESSION.get(detail_url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Gagal fetch detail {detail_url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    title = ""
    h1 = soup.select_one("h1.entry-title")
    if h1:
        title = h1.get_text(strip=True)

    # ── Poster ──
    poster = ""
    img = soup.select_one("img.wp-post-image, .thumb img, .gmr-movie-data img")
    if img:
        poster = img.get("data-src") or img.get("src") or ""

    # ── Sinopsis ──
    sinopsis = ""
    content = soup.select_one(".entry-content")
    if content:
        paragraphs = content.select("p")
        sinopsis_parts = []
        for p in paragraphs:
            txt = p.get_text(strip=True)
            # Skip paragraphs yang terlalu pendek atau hanya link promo
            if len(txt) > 30 and "indofilm" not in txt.lower():
                sinopsis_parts.append(txt)
            if len(sinopsis_parts) >= 3:
                break
        sinopsis = "\n".join(sinopsis_parts)

    # ── Metadata dari .gmr-moviedata ──
    genres = []
    year = ""
    country = ""
    directors = []
    cast = []
    duration = ""
    quality = ""
    rating = ""
    network = ""

    for meta_div in soup.select(".gmr-moviedata"):
        label = meta_div.get_text(strip=True)

        # Genre
        if "genre" in label.lower():
            genres = [a.get_text(strip=True) for a in meta_div.select("a")]

        # Year / Rilis
        elif "rilis" in label.lower() or "tahun" in label.lower():
            year_links = meta_div.select("a")
            if year_links:
                year = year_links[0].get_text(strip=True)
            else:
                m = re.search(r'(\d{4})', label)
                if m:
                    year = m.group(1)

        # Country / Negara
        elif "negara" in label.lower() or "country" in label.lower():
            country_links = meta_div.select("a")
            country = ", ".join(a.get_text(strip=True) for a in country_links) if country_links else ""

        # Director / Direksi
        elif "direksi" in label.lower() or "director" in label.lower() or "sutradara" in label.lower():
            directors = [a.get_text(strip=True) for a in meta_div.select("a")]

        # Cast / Pemain
        elif "pemain" in label.lower() or "cast" in label.lower() or "bintang" in label.lower():
            cast = [a.get_text(strip=True) for a in meta_div.select("a")]

        # Duration
        elif "durasi" in label.lower() or "duration" in label.lower():
            m = re.search(r'[\d]+\s*(?:min|menit|jam)', label, re.IGNORECASE)
            if m:
                duration = m.group(0)
            else:
                # Ambil teks setelah label
                txt = label.replace("Durasi:", "").replace("Duration:", "").strip()
                if txt:
                    duration = txt

        # Quality
        elif "kualitas" in label.lower() or "quality" in label.lower():
            q_links = meta_div.select("a")
            quality = q_links[0].get_text(strip=True) if q_links else ""

        # Network
        elif "network" in label.lower() or "jaringan" in label.lower():
            network = ", ".join(a.get_text(strip=True) for a in meta_div.select("a"))

        # Rating
        elif "rating" in label.lower() or "imdb" in label.lower():
            m = re.search(r'[\d.]+', label)
            if m:
                rating = m.group(0)

    # ── Tags ──
    tags = []
    for tag_link in soup.select('.gmr-moviedata a[href*="/tag/"]'):
        tags.append(tag_link.get_text(strip=True))

    # ── Episode list (untuk TV Series) ──
    episodes = []
    for ep_link in soup.select(".gmr-listseries a.button, .gmr-listseries a"):
        ep_text = ep_link.get_text(strip=True)
        ep_url = ep_link.get("href", "")
        # HANYA ambil link episode yang mengarah ke /eps/ URL
        if ep_text and ep_url and "/eps/" in ep_url:
            episodes.append({
                "label": ep_text,
                "url": ep_url,
            })

    # ── Download links (untuk Movie) ──
    download_links = []
    dl_section = soup.select_one("#download")
    if dl_section:
        for a in dl_section.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href and "klik.best" not in href:
                download_links.append({"text": text or "Download", "url": href})
    else:
        # Fallback: cari h3 Download dan ambil link setelahnya
        for h3 in soup.select("h3"):
            if "download" in h3.get_text(strip=True).lower():
                # Ambil sibling links
                next_el = h3.find_next_sibling()
                while next_el and next_el.name in ("ul", "ol", "p", "div"):
                    for a in next_el.select("a[href]"):
                        href = a.get("href", "")
                        text = a.get_text(strip=True)
                        if href and "klik.best" not in href:
                            download_links.append({"text": text or "Download", "url": href})
                    next_el = next_el.find_next_sibling()
                    if next_el and next_el.name in ("h3", "h2", "h1"):
                        break
                break

    # ── Video embed (jika ada iframe langsung di halaman) ──
    video_embed = ""
    iframe = soup.select_one(".gmr-embed-responsive iframe, .video-embed iframe, iframe")
    if iframe:
        src = iframe.get("src") or iframe.get("data-src") or ""
        if src and "ad" not in src.lower() and "klik" not in src.lower():
            video_embed = src

    is_tv = "/tv/" in detail_url or len(episodes) > 0

    return {
        "title": title,
        "detail_url": detail_url,
        "type": "TV Series" if is_tv else "Movie",
        "poster": poster,
        "sinopsis": sinopsis,
        "genres": genres,
        "year": year,
        "country": country,
        "directors": directors,
        "cast": cast,
        "duration": duration,
        "quality": quality,
        "rating": rating,
        "network": network,
        "tags": tags,
        "total_episodes": len(episodes),
        "episodes": episodes,
        "download_links": download_links,
        "video_embed": video_embed,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 3: Scrape episode video/download links
# ══════════════════════════════════════════════════════════════════════════════

def scrape_episode_page(ep_url: str) -> dict:
    """Scrape halaman episode untuk ambil video embed dan download links."""
    result = {
        "url": ep_url,
        "video_embed": "",
        "servers": [],
        "download_links": [],
    }

    try:
        resp = SESSION.get(ep_url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"    Gagal fetch episode {ep_url}: {e}")
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Video iframe
    iframe = soup.select_one(".gmr-embed-responsive iframe")
    if not iframe:
        # Fallback: cari iframe manapun yang bukan iklan
        for ifr in soup.select("iframe"):
            src = ifr.get("src", "") or ifr.get("data-src", "")
            if src and "ad" not in src.lower() and "klik" not in src.lower() and "google" not in src.lower():
                iframe = ifr
                break
    if iframe:
        src = iframe.get("src") or iframe.get("data-src") or ""
        if src and "ad" not in src.lower() and "klik" not in src.lower():
            result["video_embed"] = src

    # Server options
    for srv in soup.select('a[id^="player"], .gmr-server-wrap a'):
        srv_name = srv.get_text(strip=True)
        srv_data = srv.get("data-em", "") or srv.get("href", "")
        if srv_name:
            result["servers"].append({"name": srv_name, "data": srv_data})

    # Download links — cek beberapa lokasi
    dl_links_found = []

    # 1) #download section
    dl_section = soup.select_one("#download")
    if dl_section:
        for a in dl_section.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href and "klik.best" not in href:
                dl_links_found.append({"text": text or "Download", "url": href})

    # 2) ul.gmr-download-list
    if not dl_links_found:
        for a in soup.select("ul.gmr-download-list a[href], .dl-box a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href and "klik.best" not in href:
                dl_links_found.append({"text": text or "Download", "url": href})

    # 3) Fallback: h3 Download + sibling links
    if not dl_links_found:
        for h3 in soup.select("h3"):
            if "download" in h3.get_text(strip=True).lower():
                next_el = h3.find_next_sibling()
                while next_el and next_el.name in ("ul", "ol", "p", "div"):
                    for a in next_el.select("a[href]"):
                        href = a.get("href", "")
                        text = a.get_text(strip=True)
                        if href and "klik.best" not in href:
                            dl_links_found.append({"text": text or "Download", "url": href})
                    next_el = next_el.find_next_sibling()
                    if next_el and next_el.name in ("h3", "h2", "h1"):
                        break
                break

    # 4) Last resort: cari link ke kagefiles/imaxstreams/peytonepre/iplayerhls
    if not dl_links_found:
        for a in soup.select('a[href*="kagefiles"], a[href*="imaxstreams"], a[href*="peytonepre"], a[href*="iplayerhls"]'):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            dl_links_found.append({"text": text or "Download", "url": href})

    result["download_links"] = dl_links_found
    return result


# ══════════════════════════════════════════════════════════════════════════════
# LANGKAH 4: Pipeline utama
# ══════════════════════════════════════════════════════════════════════════════

def quick_scrape(url: str, with_episodes: bool = False) -> dict | None:
    """Scrape satu judul film/series langsung dari URL detail."""
    log.info(f"Quick scrape: {url}")
    detail = scrape_detail(url)
    if not detail:
        return None

    if with_episodes and detail.get("episodes"):
        log.info(f"  → Scraping {len(detail['episodes'])} episode...")
        ep_data = []
        for i, ep in enumerate(detail["episodes"], 1):
            try:
                log.info(f"    Episode {i}/{len(detail['episodes'])}: {ep['label']}...")
                ep_result = scrape_episode_page(ep["url"])
                ep_data.append({
                    "label": ep["label"],
                    **ep_result,
                })
                time.sleep(0.3)
            except KeyboardInterrupt:
                log.warning(f"\n⚠ Dihentikan setelah {i-1} episode.")
                break
        detail["episode_details"] = ep_data

    # Simpan
    slug = url.rstrip("/").split("/")[-1]
    path = os.path.join(OUTPUT_DIR, f"zelda_{slug}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)
    log.info(f"✓ Disimpan: {path}")

    return detail


def run_full_scrape(
    max_pages: int = None,
    max_details: int = None,
    scrape_episodes: bool = False,
    category_url: str = None,
    filter_params: dict = None,
):
    """Scrape penuh: listing → detail → episode."""
    timestamp = int(time.time())

    print(f"""
{'='*60}
  🎬 ZeldaEternity (INDOFILM) Full Scraper
  Target: {BASE_URL}
  Max halaman: {max_pages or 'semua'}
  Scrape episode detail: {'Ya' if scrape_episodes else 'Tidak'}
{'='*60}
""")

    # Step 1: Crawl listings
    log.info("LANGKAH 1: Crawl daftar film/series...")
    base = category_url or BASE_URL

    # Filter berdasarkan kategori
    if filter_params:
        cat = filter_params.get("category", "")
        if cat:
            base = f"{BASE_URL}/category/{cat}/"

    all_items = crawl_all_listings(base, max_pages)
    log.info(f"✓ Total {len(all_items)} judul ditemukan\n")

    if not all_items:
        log.warning("Tidak ada judul ditemukan!")
        return

    # Simpan listing
    listing_path = os.path.join(OUTPUT_DIR, f"zelda_listing_{timestamp}.json")
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

    # Step 2: Scrape detail
    log.info("LANGKAH 2: Scrape detail per judul...")
    details = []
    total = min(len(all_items), max_details) if max_details else len(all_items)

    for i, item in enumerate(all_items[:total], 1):
        try:
            log.info(f"[{i}/{total}] {item['title']}...")
            detail = scrape_detail(item["detail_url"])

            if detail:
                # Log info movie: download & video
                if detail.get("download_links"):
                    log.info(f"  📥 {len(detail['download_links'])} download link")
                if detail.get("video_embed"):
                    log.info(f"  🎬 Video: {detail['video_embed'][:60]}")

                details.append(detail)

                # Opsional: Scrape episode details
                if scrape_episodes and detail.get("episodes"):
                    log.info(f"  → Scraping {len(detail['episodes'])} episode (video + download)...")
                    ep_data = []
                    vid_count = 0
                    dl_count = 0
                    for j, ep in enumerate(detail["episodes"], 1):
                        try:
                            ep_result = scrape_episode_page(ep["url"])
                            ep_data.append({
                                "label": ep["label"],
                                **ep_result,
                            })
                            v = "✓" if ep_result.get("video_embed") else "✗"
                            d = len(ep_result.get("download_links", []))
                            if ep_result.get("video_embed"):
                                vid_count += 1
                            dl_count += d
                            log.info(f"    {ep['label']}: Video={v}  Download={d} link")
                            time.sleep(0.3)
                        except KeyboardInterrupt:
                            log.warning(f"\n⚠ Episode scraping dihentikan.")
                            break
                    detail["episode_details"] = ep_data
                    log.info(f"  ✓ {vid_count}/{len(ep_data)} video, {dl_count} download link total")

            time.sleep(0.3)

        except KeyboardInterrupt:
            log.warning(f"\n⚠ Dihentikan oleh user (Ctrl+C) setelah {len(details)} judul.")
            log.info("Menyimpan data yang sudah ter-scrape...")
            break

    log.info(f"\n✓ Total {len(details)} detail berhasil di-scrape\n")

    # Step 3: Simpan
    full_path = os.path.join(OUTPUT_DIR, f"zelda_full_{timestamp}.json")
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

    sz = round(os.path.getsize(full_path) / 1024 / 1024, 2)
    log.info(f"{'='*60}")
    log.info(f"✓ SELESAI!")
    log.info(f"  Total judul: {len(details)}")
    log.info(f"  File: {full_path}")
    log.info(f"  Ukuran: {sz} MB")
    log.info(f"{'='*60}")

    return details


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ZeldaEternity (INDOFILM) Scraper")
    parser.add_argument("--pages", type=int, default=None, help="Max halaman listing")
    parser.add_argument("--max-details", type=int, default=None, help="Max judul detail")
    parser.add_argument("--with-episodes", action="store_true", help="Scrape episode video/download")
    parser.add_argument("--url", type=str, default=None, help="Quick scrape satu URL")
    parser.add_argument("--category", type=str, default=None,
                        help="Filter kategori (movie, anime, donghua, serial-tv)")
    args = parser.parse_args()

    try:
        if args.url:
            quick_scrape(args.url, with_episodes=args.with_episodes)
        else:
            cat_url = None
            if args.category:
                cat_url = f"{BASE_URL}/category/{args.category}/"
            run_full_scrape(
                max_pages=args.pages,
                max_details=args.max_details,
                scrape_episodes=args.with_episodes,
                category_url=cat_url,
            )
    except KeyboardInterrupt:
        print("\n\n⚠ Dihentikan oleh user.")
        sys.exit(0)
