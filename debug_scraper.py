import requests
from bs4 import BeautifulSoup
import re

def title_clean(t):
    return re.sub(r'\s+', ' ', t).strip() if t else ""

def test_episodes(url):
    print(f"\n{'='*50}\nTesting Episodes on {url}\n{'='*50}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        html = requests.get(url, headers=headers, timeout=15).text
    except Exception as e:
        print(f"Failed to fetch: {e}")
        return
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # Simulate JS pseudo-selector logic: document.querySelectorAll('.gmr-listseries a, .episodelist a, a[href*="/eps/"], a[href*="/episode/"], .episodes a, ul.lstep li a, .list-episode li a, [class*="episode"] a');
    links = []
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(separator=' ', strip=True)
        
        # Check parent classes
        parent_classes = []
        p = a.parent
        while p and p.name != 'body':
            if p.get('class'):
                parent_classes.extend(p.get('class'))
            p = p.parent
            
        parent_class_str = " ".join(parent_classes).lower()
        
        if ('gmr-listseries' in parent_class_str or 
            'episodelist' in parent_class_str or 
            'episodes' in parent_class_str or
            'lstep' in parent_class_str or
            'list-episode' in parent_class_str or
            'episode' in parent_class_str or
            '/eps/' in href.lower() or 
            '/episode/' in href.lower()):
            
            links.append({'text': text, 'href': href, 'by_rule': 'class/href'})
            
    # Remove duplicates
    seen = set()
    unique_links = []
    for l in links:
        if l['href'] not in seen:
            seen.add(l['href'])
            unique_links.append(l)
            
    for i, l in enumerate(unique_links):
        print(f"[{i+1}] {l['text']} -> {l['href']}")

if __name__ == "__main__":
    # Test on a known series page
    test_episodes('https://azarug.org/tv/hells-paradise-season-2-2026/')
    test_episodes('https://zeldaeternity.com/tv/frieren-beyond-journeys-end-2023/')
    test_episodes('https://xdrakor63.nicewap.sbs/detail/love-next-door-2024-d7l/')
