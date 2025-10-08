import requests
import xml.etree.ElementTree as ET
import pandas as pd
import os
import json


def download_xml_file(dir_path : str):
    file_name = "tavel_state_raw.xml"
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

    root = ET.XML(xml_data)  
    country_id = []
    country_advisory = []
    tree = ET.parse('raw_datasets/tavel_state_raw.xml')  
    root = tree.getroot()   
    channel_root = root.find('channel')
    for element in channel_root.findall('item'):
        try: 
            country_id.append(element.find('category[@domain="Country-Tag"]').text)
            country_advisory.append(element.find('category[@domain="Threat-Level"]').text)
        except Exception:
            print("error while reading element with tag: " + element.tag)


    df = pd.DataFrame({"country_id" : country_id, "country_advisory" : country_advisory})  
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
    xml_path = os.path.join(data_dir, "tavel_state_raw.xml")
    df = create_df(xml_path)
    df_to_json(df, destination_dir)
    print(f'succesfully downloaded {xml_path} to {destination_dir}')

create_json("raw_datasets", "cleaned_data")


