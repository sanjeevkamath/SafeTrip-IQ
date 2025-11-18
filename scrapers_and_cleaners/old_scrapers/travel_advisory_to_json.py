import requests
import xml.etree.ElementTree as ET
import pandas as pd
import os
import json
import html
import re


def download_xml_file(dir_path : str):
    file_name = "travel_state_raw.xml"
    full_file_path = os.path.join(dir_path, file_name)

    url = 'https://travel.state.gov/_res/rss/TAsTWs.xml'
    response = requests.get(url)

    if response.status_code == 200:
        with open(full_file_path, "wb") as file:
            file.write(response.content)
        print("XML file downloaded successfully!")
    else:
        print(f"Error downloading file: {response.status_code}")

def create_df(path_to_xml):
    '''create a pandas df in the form of {country_id: [], country_advisory: []}.   
    return the df.'''
    try:
        xml_data = open(path_to_xml, 'r').read()  
    except FileNotFoundError:
        print(f'No xml file found at {path_to_xml}')
        raise FileNotFoundError
    # parse XML from provided path
    tree = ET.parse(path_to_xml)
    root = tree.getroot()
    channel_root = root.find('channel')

    country_id = []
    country_advisory = []
    country_advisory_text = []

    def clean_html(raw_html: str) -> str:
        """Remove HTML tags, unescape entities, and normalize whitespace."""
        if raw_html is None:
            return ""
        # Some descriptions may include CDATA wrappers; xml parser gives the inner text
        text = raw_html
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Unescape HTML entities
        text = html.unescape(text)
        # Collapse multiple whitespace and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    for element in channel_root.findall('item'):
        try:
            cid = element.find('category[@domain="Country-Tag"]').text if element.find('category[@domain="Country-Tag"]') is not None else None
            adv = element.find('category[@domain="Threat-Level"]').text if element.find('category[@domain="Threat-Level"]') is not None else None
            # description elements often contain HTML; extract inner text
            desc_el = element.find('description')
            desc_text = None
            if desc_el is not None and desc_el.text:
                desc_text = desc_el.text
            else:
                # sometimes description can have text in subelements or tail; join them
                desc_parts = []
                for child in desc_el.iter() if desc_el is not None else []:
                    if child.text:
                        desc_parts.append(child.text)
                    if child.tail:
                        desc_parts.append(child.tail)
                desc_text = ' '.join(desc_parts) if desc_parts else None

            country_id.append(cid)
            country_advisory.append(adv)
            country_advisory_text.append(clean_html(desc_text))
        except Exception as e:
            # avoid failing the whole run if one item is bad
            print(f"error while reading element with tag: {element.tag} -> {e}")

    df = pd.DataFrame({
        "country_id": country_id,
        "country_advisory": country_advisory,
        "country_advisory_text": country_advisory_text,
    })
    return df
    
def df_to_json(df : pd.DataFrame, destination_dir : str) -> None:
    '''convert a pandas df into json, saving to destination_dir'''
    json_path = os.path.join(destination_dir, "travel_advisory.json")
    json_string = df.to_json(json_path, orient='records', indent=4)
    print(f'succesfully saved json file to {destination_dir}')


def create_json(data_dir : str, destination_dir : str) -> None:
    '''create a json of the travel advisory, saving it into destination dir.
    
    params: data_dir- where the raw data will be saved to
    destination_dir- where the cleaned json will be saved to
    '''

    download_xml_file(data_dir)
    xml_path = os.path.join(data_dir, "travel_state_raw.xml")
    df = create_df(xml_path)
    df_to_json(df, destination_dir)
    print(f'succesfully downloaded {xml_path} to {destination_dir}')

create_json("raw_datasets", "cleaned_data")


