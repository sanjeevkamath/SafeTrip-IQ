'''PPI: Positive Peace Index
   GTI: Global Terrorism Index
   GPI: Global Peace Index'''



import pandas as pd

df = pd.read_csv("GTI.csv")    #change according to file name                     
out = df[["country","score"]].dropna()
out.columns = ["country","score"]
out.to_json("gti.json", orient="records", indent=2) #change according to file name