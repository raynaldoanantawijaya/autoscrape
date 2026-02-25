import requests
from bs4 import BeautifulSoup

def analyze_body(url):
    print(f"\n{'='*50}\nAnalyzing {url}\n{'='*50}")
    headers = {"User-Agent": "Mozilla/5.0"}
    html = requests.get(url, headers=headers).text
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try finding any link that has "episode", "eps", looks like a number, or is in a list
    candidates = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True).lower()
        if 'episode' in text or 'eps' in text or text.isdigit():
            parent_class = " ".join(a.parent.get('class', []))
            parent_parent_class = " ".join(a.parent.parent.get('class', [])) if a.parent.parent else ""
            candidates.append(f"TEXT: {text} | HREF[:80]: {href[:80]}\n  -> parent: {parent_class} | parent_parent: {parent_parent_class}")
            
    for c in list(set(candidates))[:20]:
        print(c)

if __name__ == "__main__":
    analyze_body('https://xdrakor63.nicewap.sbs/detail/love-next-door-2024-d7l/')
