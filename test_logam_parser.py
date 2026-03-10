from bs4 import BeautifulSoup

html = """
<div>
  <h1 class="title">Harga Emas Hari Ini, 26 Feb 2026</h1>
  <table>
    <thead>
      <tr><th>Berat</th><th>Harga Dasar</th><th>Harga (+Pajak PPh 0.25%)</th></tr>
    </thead>
    <tbody>
      <tr><td colspan="3">Emas Batangan</td></tr>
      <tr><td>0.5 gr</td><td>1,569,500</td><td>1,573,424</td></tr>
      <tr><td>1 gr</td><td>3,039,000</td><td>3,046,598</td></tr>
      <tr><td colspan="3">Emas Batangan Gift Series</td></tr>
      <tr><td>0.5 gr</td><td>1,639,500</td><td>1,643,599</td></tr>
    </tbody>
  </table>
</div>
"""

soup = BeautifulSoup(html, 'html.parser')
table = soup.find('table')

base_title = "Harga Emas Hari Ini, 26 Feb 2026"
tables_out = []

current_title = base_title
current_headers = []
current_rows = []

# Collect header texts
thead = table.find("thead")
if thead:
    header_trs = thead.find_all("tr")
    first_texts = [th.get_text(strip=True) for th in header_trs[0].find_all(["th", "td"])]
    last_texts = [th.get_text(strip=True) for th in header_trs[-1].find_all(["th", "td"])]
    # Simplified zip logic
    current_headers = last_texts
    
# Process rows
tbody = table.find("tbody")
if tbody:
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        valid_cells = [c for c in cells if c]
        
        if len(valid_cells) == 1:
            # Sub-title encountered!
            if current_rows:
                tables_out.append({"title": current_title, "headers": current_headers, "rows": current_rows})
                current_rows = []
            
            sub_title = valid_cells[0]
            current_title = f"{base_title} - {sub_title}"
        elif len(valid_cells) >= 2:
            current_rows.append(cells)

if current_rows:
    tables_out.append({"title": current_title, "headers": current_headers, "rows": current_rows})

for i, t in enumerate(tables_out):
    print(f"--- Table {i+1} ---")
    print("Title:", t["title"])
    print("Headers:", t["headers"])
    for r in t["rows"]:
        print("Row:", r)
