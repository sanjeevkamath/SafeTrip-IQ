from sklearn.preprocessing import StandardScaler
import pandas as pd

# Load the CSV file
data = pd.read_csv('clustering/data/unified_cleaned.csv')  # Load the CSV file

# Reverse undesired direction
for col in ['gpi_score', 'numbeo_crime_index', 'gti_score']:
    data[col] = data[col].max() - data[col]

scaler = StandardScaler()
cols = ['gpi_score', 'ppi_score', 'numbeo_safety_index', 'numbeo_crime_index', 'gti_score']
data[cols] = scaler.fit_transform(data[cols])


# Save the updated DataFrame back to the CSV file
data.to_csv('clustering/data/unified_cleaned.csv', index=False)  # Save the updated DataFrame
