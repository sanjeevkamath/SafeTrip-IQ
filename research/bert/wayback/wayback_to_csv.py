#!/usr/bin/env python3

"""
Parses archived State Department XML feeds and produces a minimal CSV:
label,text_advisory

- label is the EXACT advisory "Level X" from the <title> (1,2,3,4)
- NO merging of levels
- text_advisory is cleaned advisory body text (no "Country – Level X" included)
"""

import sys
import csv
import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup


# ---------------------- CONFIGURATION ----------------------

INPUT_URLS = [
    "https://web.archive.org/web/20190621071528/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20190830102705/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20230720185701/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20211031061529/https://travel.state.gov/_res/rss/TAsTWs.xml",
    "https://web.archive.org/web/20240718125410/https://travel.state.gov/_res/rss/TAsTWs.xml"
]

OUTPUT_CSV = "BERT/wayback/old_advisories_minimal_pt2.csv"

# -----------------------------------------------------------


def fetch_xml(url: str) -> str:
    """Download XML from the given URL and return it as text."""
    print(f"[INFO] Fetching XML from: {url}", file=sys.stderr)
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.text


def extract_items(xml_text: str):
    """Yield dicts: {title, body_text}."""
    root = ET.fromstring(xml_text)

    items = root.findall(".//item")
    print(f"[INFO] Found {len(items)} items", file=sys.stderr)

    for item in items:
        title = (item.findtext("title") or "").strip()
        desc_html = (item.findtext("description") or "").strip()

        # description is HTML inside CDATA → strip into text
        soup = BeautifulSoup(desc_html, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)

        yield {
            "title": title,
            "body_text": body_text,
        }


# Pattern: "<Country> – Level X"
TITLE_PATTERN = re.compile(
    r"^(?P<country>.+?)\s+[–-]\s+Level\s*(?P<level>\d)",
)


# Optional boilerplate removal to reduce noise
BOILERPLATE_REMOVE = [
    r"Read the Safety and Security section.*?\. ",
    r"Read the Safety and Security section.*?$",
    r"If you decide to travel to .*?:",
    r"Enroll in the Smart Traveler Enrollment Program.*?\. ",
    r"Follow the Department of State on Facebook and Twitter.*?\. ",
    r"U\.S\. citizens who travel abroad should always have a contingency plan.*?\. ",
    r"Review the Traveler’s Checklist.*?\. ",
    r"Review the Crime and Safety Report.*?\. ",
    r"Review the Crime and Safety Reports.*?\. ",
]

def should_skip_short_advisory(text: str, label: int) -> bool:
    """
    Remove advisories that are extremely short or almost pure boilerplate.

    Examples that will be removed:
      "Exercise normal precautions in Grenada. Review the Traveler’s Checklist."
      "Exercise normal precautions in Norway. Review the Traveler’s Checklist."
    """

    # Word count rule — removes super short advisories
    if len(text.split()) < 20:
        return True

    # Pattern that catches the trivial Level 1 advisories
    SHORT_LEVEL1_PATTERN = re.compile(
        r"^Exercise normal precautions\b.*$", re.IGNORECASE
    )

    if label == 1 and SHORT_LEVEL1_PATTERN.match(text):
        return True

    return False


def clean_text_for_bert(body: str) -> str:
    """
    Clean advisory body text for BERT:

    - DOES NOT include the title or the Level text
    - Strips boilerplate
    - Normalizes whitespace
    """
    text = body.strip()

    # Remove boilerplate phrases
    for pattern in BOILERPLATE_REMOVE:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def main():
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["label", "text_advisory"])

        for url in INPUT_URLS:
            xml_text = fetch_xml(url)

            for item in extract_items(xml_text):
                title = item["title"]
                body = item["body_text"]

                if not title or not body:
                    continue

                # Extract Level from the title
                m = TITLE_PATTERN.match(title)
                if not m:
                    print(f"[WARN] Could not parse Level: {title}", file=sys.stderr)
                    continue

                raw_level = int(m.group("level"))  # EXACT label (1,2,3,4)

                # Clean body text
                text = clean_text_for_bert(body)

                # Skip extremely short advisories
                if should_skip_short_advisory(text, raw_level):
                    continue


                writer.writerow([raw_level, text])

    print(f"[INFO] Wrote minimal CSV (no merging) to: {OUTPUT_CSV}", file=sys.stderr)


if __name__ == "__main__":
    main()
