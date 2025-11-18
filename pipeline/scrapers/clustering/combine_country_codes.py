import pandas as pd
import pycountry

'''
# This script added isov3 country codes to the clustering_copy_csv file
df1 = pd.read_csv("clustering/data/clustering_copy.csv")   
df2 = pd.read_csv("raw_datasets/political_violence_index.csv")  


country = pycountry.countries.get(alpha_2='DE')
print(country.alpha_3)

def iso2_to_iso3(code):
    if pd.isna(code):  # Check for NA values
        print(f"NA code encountered.")
        return code
    try:
        country = pycountry.countries.get(alpha_2=code)
        return country.alpha_3

    except:
        return None


df1["iso3"] = df1["iso2"].apply(lambda x: iso2_to_iso3(x))

df1.to_csv("clustering/data/clustering_copy.csv", index=False)
'''


# Load your CSV files
clustering = pd.read_csv('clustering/data/clustering_copy.csv')
political_violence = pd.read_csv('raw_datasets/political_violence_index.csv')

# Merge on 'iso3'
combined = pd.merge(clustering, political_violence[['iso3', 'pvi_score']], on='iso3', how='left')

# Select columns: iso3 first, then clustering's numerical scores, then pvi_score
cols = ['iso3', 'gpi_score', 'ppi_score', 'numbeo_safety_index', 'gti_score', 'numbeo_crime_index', 'pvi_score']
combined = combined[cols]

# Save combined data to CSV
combined.to_csv('clustering/data/combined_output.csv', index=False)

print('Combined CSV saved as combined_output.csv')
