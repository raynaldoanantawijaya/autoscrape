import os
import sys
import json
import time
from urllib.parse import urlparse

# Initialize project dan logger
import init_project
init_project.init_project()
import log_setup

import logging
logger = logging.getLogger(__name__)

from config import settings
from modules import direct_request, network_capture, analysis, js_extractor, interaction, decryption, fallback, anti_detect
from modules.proxy_manager import proxy_manager

def main(url):
    logger.info(f"=== Memulai Auto Web Scraper untuk: {url} ===")
    
    # Tentukan proksi jika digunakan
    req_proxy = proxy_manager.get_proxy_for_requests()
    playwright_proxy = proxy_manager.get_proxy_for_playwright()
    
    if req_proxy:
        logger.info(f"Menggunakan Proxy: {playwright_proxy.get('server')}")

    # ---------------------------------------------------------
    # LAYER 1: Direct Request ke Endpoint Umum
    # ---------------------------------------------------------
    try:
        logger.info("-> [Layer 1] Memulai Direct Request")
        data = direct_request.try_common_endpoints(url, timeout=15, proxies=req_proxy)
        if data:
            return save_data(data, url, "direct_api")
    except Exception as e:
        logger.error(f"Error pada Layer 1: {e}")

    # ---------------------------------------------------------
    # LAYER 2: Network Capture dengan Playwright (Mode Ringan)
    # ---------------------------------------------------------
    try:
        logger.info("-> [Layer 2] Memulai Network Capture & Parsing Murni")
        capture_result = network_capture.capture(
            url, 
            stealth_config=anti_detect.apply_stealth,
            proxies=playwright_proxy
        )
        
        # Cek CAPTCHA
        captcha_type = anti_detect.detect_captcha(capture_result.html_content)
        if captcha_type:
            logger.warning(f"=== CAPTCHA TERDETEKSI ({captcha_type}) ===")
            # Fallback memanggil layanan 3rd party solver
            fallback.solve_captcha_external(capture_result.html_content, url, captcha_type)
            
        data = analysis.find_json(capture_result, settings.TARGET_KEYWORDS)
        if data:
            return save_data(data, url, "network_capture")
    except Exception as e:
        logger.error(f"Error pada Layer 2: {e}")
        capture_result = None

    # ---------------------------------------------------------
    # LAYER 3: Deteksi Enkripsi & Reverse Engineering Awal
    # ---------------------------------------------------------
    if capture_result:
        try:
            if analysis.is_encrypted(capture_result):
                logger.info("-> [Layer 3] Terindikasi Enkripsi, Mencoba Dekripsi Basic")
                decrypted_data = decryption.try_decrypt(capture_result, url)
                if decrypted_data:
                    return save_data(decrypted_data, url, "decrypted_traffic")
        except Exception as e:
            logger.error(f"Error pada Layer 3: {e}")

    # ---------------------------------------------------------
    # LAYER 4: Simulasi Interaksi & Ekstraksi JS
    # ---------------------------------------------------------
    try:
        logger.info("-> [Layer 4] Memulai Interaksi Aktif (Scroll, Klik Load More)")
        interaction_result = interaction.simulate_and_capture(
            url, 
            stealth_config=anti_detect.apply_stealth,
            proxies=playwright_proxy
        )
        
        data = analysis.find_json(interaction_result, settings.TARGET_KEYWORDS)
        if data:
            return save_data(data, url, "interaction_capture")
            
        logger.info("-> [Layer 4] Ekstraksi Endpoint dari file JS Halaman")
        js_endpoints = js_extractor.extract_from_js(url, html_content=interaction_result.html_content, proxies=req_proxy)
        
        if js_endpoints:
            logger.info(f"Mencoba direct hit ke {len(js_endpoints)} endpoint yang diekstrak dari JS...")
            parsed_url = urlparse(url)
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            for ep in js_endpoints:
                try:
                    target_ep = ep if ep.startswith("http") else f"{base_domain}{ep if ep.startswith('/') else '/' + ep}"
                    ep_data = direct_request.request(target_ep, proxies=req_proxy)
                    if ep_data:
                        body_str = json.dumps(ep_data).lower()
                        if any(kw.lower() in body_str for kw in settings.TARGET_KEYWORDS):
                            return save_data(ep_data, target_ep, "js_extracted_api")
                except Exception as endpoint_err:
                    logger.debug(f"Gagal hit JS endpoint {ep}: {endpoint_err}")
    except Exception as e:
        logger.error(f"Error pada Layer 4: {e}")

    # ---------------------------------------------------------
    # LAYER 5: Fallback ke Layanan Eksternal (Web Unlocker)
    # ---------------------------------------------------------
    try:
        if settings.USE_WEB_UNLOCKER:
            logger.info("-> [Layer 5] Semua strategi lokal gagal, beralih ke Fallback Eksternal")
            data = fallback.use_web_unlocker(url)
            if data:
                return save_data(data, url, "fallback_unlocker")
        else:
            logger.info("-> [Layer 5] Web Unlocker dimatikan di setting. Lewati Fallback.")
    except Exception as e:
        logger.error(f"Error pada Layer 5: {e}")

    logger.error("=== Kegagalan Scraping: Tidak ada data relevan (JSON) yang ditemukan. ===")
    logger.info("Coba cek manual file HAR di folder har/ untuk menelusuri traffic secara mendalam.")
    return None

def save_data(data, source_url, method):
    """
    Menyimpan data JSON ke folder hasil_scrape/ dan
    memberikan output yang sangat jelas ke terminal tentang lokasi file.
    """
    import json, os, time
    from urllib.parse import urlparse
    
    try:
        os.makedirs('hasil_scrape', exist_ok=True)
        
        # Buat nama file aman
        domain = urlparse(source_url).netloc.replace('.', '_')
        if not domain:
            domain = "unknown"
            
        filename = f"hasil_scrape/{domain}_{method}_{int(time.time())}.json"
        
        final_data = {
            "metadata": {
                "source_url": source_url,
                "method": method,
                "timestamp": int(time.time()),
                "domain": domain
            },
            "data": data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
            
        abs_path = os.path.abspath(filename)
        
        # Jika scraper berhasil menemukan data Emas Terstruktur
        if isinstance(data, dict) and "structured_gold_prices" in data:
            providers = list(data["structured_gold_prices"].keys())
            prov_str = ", ".join(providers)
            print(f"\n" + "="*70)
            print(f"🎉 SUKSES! HARGA EMAS BERHASIL DIEKSTRAK")
            print(f"📌 Terdeteksi Provider: {prov_str}")
            print(f"📂 Lokasi File Asli: {abs_path}")
            print("="*70 + "\n")
            logger.info(f"=== SUKSES: Data Emas ({prov_str}) disimpan ke {filename} ===")
        else:
            print(f"\n" + "="*70)
            print(f"✅ SUKSES! DATA BERHASIL DISIMPAN")
            print(f"📂 Lokasi File Asli: {abs_path}")
            print("="*70 + "\n")
            logger.info(f"=== SUKSES: Data di luar emas (General) disimpan ke: {filename} ===")
            
        return filename
    except Exception as e:
        logger.error(f"Gagal menyimpan data ke file {filename}: {e}")
        return None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python main.py <URL>")
        sys.exit(1)
        
    target_url = sys.argv[1]
    if not target_url.startswith("http"):
        target_url = "https://" + target_url
        
    try:
        main(target_url)
    except KeyboardInterrupt:
        logger.warning("\nDihentikan oleh pengguna (Ctrl+C).")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Terjadi error fatal: {e}", exc_info=True)
        sys.exit(1)
