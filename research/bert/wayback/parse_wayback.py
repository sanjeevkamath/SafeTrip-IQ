# TODO: Create a cleaner that cleans the data into bert usable format

import sys
import requests
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup


def fetch_xml(url: str) -> str:
    """Download XML from the given URL and return it as text."""
    print(f"[INFO] Fetching XML from: {url}", file=sys.stderr)
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.text


def extract_items(xml_text: str):
    """Parse XML text and yield (title, raw_description_html, clean_text)."""
    root = ET.fromstring(xml_text)

    # This works for most RSS-like feeds: <rss><channel><item>...</item></channel></rss>
    items = root.findall(".//item")
    print(f"[INFO] Found {len(items)} <item> entries", file=sys.stderr)

    for item in items:
        title = (item.findtext("title") or "").strip()
        desc_html = (item.findtext("description") or "").strip()

        # description is usually HTML inside CDATA — parse it to get visible text
        soup = BeautifulSoup(desc_html, "html.parser")
        # separator=" " ensures words from different tags don't get smashed together
        clean_text = soup.get_text(separator=" ", strip=True)

        yield title, desc_html, clean_text







# --- USER CONFIGURABLE SECTION ---
INPUT_URLS = [

    # Example:
    "https://web.archive.org/web/20250201014500/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20180124025525/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20180627054211/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20180623062509/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20181207085201/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20190220104217/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20190424115939/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20190628053232/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20190725011802/https://travel.state.gov/_res/rss/TAsTWs.xml"
    

    # Add more URLs if needed
]
OUTPUT_FILE = "BERT/wayback/old_advisories_minimal.txt"  # Change this to your desired output file path
# --- END USER CONFIGURABLE SECTION ---

def main():
    if not INPUT_URLS:
        print("Please set at least one URL in INPUT_URLS at the top of the script.", file=sys.stderr)
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_file:
        for url in INPUT_URLS:
            xml_text = fetch_xml(url)

            

            for idx, (title, desc_html, clean_text) in enumerate(extract_items(xml_text), start=1):
                out_file.write(f"### ITEM {idx} ###\n")
                if title:
                    out_file.write(f"TITLE: {title}\n")
                out_file.write("\n")
                out_file.write(clean_text + "\n")
                out_file.write("\n" + "=" * 80 + "\n\n")


if __name__ == "__main__":
    main()
