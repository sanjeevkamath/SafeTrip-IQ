import plotly.express as px
import pandas as pd
import os

# read the file your KMeans step wrote
df = pd.read_csv("clustering/output/clustering_output.csv")

# remove any rows with missing ISO3 codes
df = df.dropna(subset=["iso3"])
df["iso3"] = df["iso3"].str.upper()

# build an interactive choropleth
fig = px.choropleth(
    df,
    locations="iso3",
    color="cluster",
    hover_name="iso3",
    hover_data={"gpi_score": True, "ppi_score": True, "gti_score": True, "pvi_score": True, "iso3": False},
    locationmode="ISO-3",
    color_continuous_scale="Viridis",
    title="K-Means Clusters by Country"
)

fig.update_geos(showframe=False, showcoastlines=True, projection_type="natural earth")
fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))

os.makedirs("clustering/output", exist_ok=True)
fig.write_html("clustering/output/clusters_map.html")

print("✅ Map saved to clustering/output/clusters_map.html")
