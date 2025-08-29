import time

import pandas as pd
from geopy.exc import GeocoderServiceError
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="usa_state_app")

df = pd.read_csv(r"data\interim\canada_nan_cities_mapped.csv")

# Ensure result columns exist
for col in ["results_city", "results_state"]:
    if col not in df.columns:
        df[col] = pd.NA


def is_missing(x):
    if x is None:
        return True
    if isinstance(x, float) and pd.isna(x):
        return True
    s = str(x).strip()
    return s == "" or s.lower() in {"nan", "none"}


# Mask: only rows that still need a state
need_state_mask = df["results_state"].apply(is_missing)

total = int(need_state_mask.sum())
print(f"Rows needing reverse geocode for state: {total}")

processed = 0
for idx, row in df.loc[need_state_mask].iterrows():
    lat, lon = row["latitude"], row["longitude"]

    try:
        print(
            f"Processing index {idx} → lat: {lat}, lon: {lon} ({processed + 1}/{total})"
        )

        location = geolocator.reverse(
            (float(lat), float(lon)), exactly_one=True, language="en"
        )
        address = (
            location.raw.get("address", {})
            if location and hasattr(location, "raw")
            else {}
        )

        # city fallback: sometimes it's 'town' or 'village'
        city = (
            address.get("city") or address.get("town") or address.get("village") or ""
        )
        state = address.get("state", "")

        # Write back into the same row
        df.loc[idx, "results_city"] = city
        df.loc[idx, "results_state"] = state

        print(f"Done → City: {city}, State: {state}")

    except GeocoderServiceError as e:
        print(f"Service error at index {idx}: {e}")
        # leave as missing or set empty strings explicitly
        df.loc[idx, "results_city"] = ""
        df.loc[idx, "results_state"] = ""
    except Exception as e:
        print(f"Error at index {idx}: {e}")
        df.loc[idx, "results_city"] = ""
        df.loc[idx, "results_state"] = ""

    processed += 1
    time.sleep(1)  # Respect Nominatim 1 req/sec

# Save
df.to_csv(r"data\interim\canada_nan_cities_mapped.csv", index=False)
print("Process completed.")
