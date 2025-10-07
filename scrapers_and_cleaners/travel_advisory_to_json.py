import requests
import xml.etree.ElementTree as ET
import pandas as pd
import os


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

# def create_df(path_to_xml):
#     xml_data = open(path_to_xml, 'r').read()  
#     root = ET.XML(xml_data)  
    
#     country_name = []
#     country_id = []
#     country_advisory = []
#     for i, child in enumerate(root):
#         print
#         country_name.append([subchild.text for subchild in child])
#         country_id.append(child.tag)
#         country_advisory.append()

#     df = pd.DataFrame(data).T  
#     df.columns = cols  
    

download_xml_file("raw_datasets")
# create_df('downloaded_file.xml')

# xml_data = open('downloaded_file.xml', 'r').read()  
# tree = ET.parse('../raw_datasets/downloaded_file.xml')  
# root = tree.getroot()   
# channel_root = root.find('channel')


# count = 0
# for element in channel_root.findall('item'):
#     try: 
#         print(element.find('category[@domain="Country-Tag"]').text)
#         count += 1
#     except Exception:
#         print(element.tag)


# print (count)

