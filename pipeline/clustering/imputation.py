#Implement Imputation Using Clustering Techniques

from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler
import pandas as pd

df = pd.read_csv("clustering/data/clustering_data.csv")

core_cols = ['gpi_score', 'ppi_score', 'gti_score', 'pvi_score']
aux_cols  = ['numbeo_safety_index', 'numbeo_crime_index']

X_full = df[core_cols + aux_cols]

# Step 1: Impute using all six
imputer = KNNImputer(n_neighbors=5)
X_imputed = imputer.fit_transform(X_full)

# Step 2: Create new DataFrame
df_imputed = df.copy()
df_imputed[core_cols + aux_cols] = X_imputed

# Step 3: Drop the Numbeo columns (auxiliary only)
df_final = df_imputed.drop(columns=aux_cols)

# Step 4: Standardize before clustering
scaler = StandardScaler()
df_scaled = pd.DataFrame(scaler.fit_transform(df_final[core_cols]), columns=core_cols)

# Optional: Save results
df_scaled['iso3'] = df['iso3']
df_scaled.to_csv("clustering/data/clustering_ready.csv", index=False)


