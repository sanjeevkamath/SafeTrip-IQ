import json
import csv
import re

# Function to clean text safely
def clean_text(text):
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    # Remove special characters and digits except punctuation
    text = re.sub(r"[^a-zA-Z\s.,!?:;'-]", '', text)
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Load JSON
with open('unified_data/unified_travel_data.json', 'r') as file:
    data = json.load(file)

# Collect cleaned and structured data
rows = []
for entry in data:
    advisory_level = entry.get('advisory_level', '') or ""
    advisory_num = advisory_level.split(" ")[1][0] if len(advisory_level.split(" ")) > 1 else ""
    advisory_text = entry.get('advisory_text', '') or ""

    # Clean texts
    advisory_text_clean = clean_text(advisory_text)

    rows.append([advisory_num, advisory_text_clean])

# Write to CSV
with open('cleaned_travel_advisories.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Advisory_Level', 'Advisory_Text'])
    writer.writerows(rows)

no_empty = []
with open('cleaned_travel_advisories.csv', 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if row != "" and any(field.strip() for field in row):
            no_empty.append(row)

with open('cleaned_travel_advisories_no_empty.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(no_empty)
        
