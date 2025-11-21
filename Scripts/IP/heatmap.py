import geoip2.database
import pandas as pd
from tqdm import tqdm
import folium
from folium.plugins import HeatMap

# --- Step 1: Open MaxMind GeoLite2 DB ---
reader = geoip2.database.Reader('/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/GeoLite2-City/GeoLite2-City.mmdb')

# --- Step 2: Read IPs ---
ips = [line.strip() for line in open('/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/Analysis/Deliver/users_ips.txt') if line.strip()]

# --- Step 3: Lookup locations ---
locations = []
for ip in tqdm(ips, desc="Processing IPs"):
    try:
        response = reader.city(ip)
        lat = response.location.latitude
        lon = response.location.longitude
        if lat is not None and lon is not None:  # skip invalid coords
            locations.append((ip, lat, lon))
    except Exception:
        continue  # skip private/invalid IPs

reader.close()

# --- Step 4: Create DataFrame ---
df = pd.DataFrame(locations, columns=["ip", "lat", "lon"])

if df.empty:
    raise ValueError("No valid IPs found for mapping!")

# --- Step 5: Count duplicates (weight by frequency) ---
df_weighted = df.groupby(['lat', 'lon']).size().reset_index(name='count')

# Prepare heatmap data
heat_data = df_weighted[['lat', 'lon', 'count']].values.tolist()

# --- Step 6: Create map ---
m = folium.Map(location=[df['lat'].mean(), df['lon'].mean()], zoom_start=5)

# Add weighted heatmap
HeatMap(heat_data, radius=10, max_zoom=8, blur=15).add_to(m)

# --- Step 7: Save map ---
m.save("ip_heatmap_weighted.html")
print("🌍 Weighted heatmap saved as ip_heatmap_weighted.html")
