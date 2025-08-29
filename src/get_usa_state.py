import time

import pandas as pd
from geopy.exc import GeocoderServiceError
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="usa_state_app")

df = pd.read_csv("data/interim/usa_nan_states.csv")

results_city = []
results_state = []

for i, (lat, lon) in enumerate(zip(df["latitude"], df["longitude"]), start=1):
    try:
        print(f"Processing row {i}/{len(df)} → lat: {lat}, lon: {lon}...")

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

        results_city.append(city)
        results_state.append(state)

        print(f"Done → City: {city}, State: {state}")

    except GeocoderServiceError as e:
        print(f"Service error at row {i}: {e}")
        results_city.append("")
        results_state.append("")
    except Exception as e:
        print(f"Error at row {i}: {e}")
        results_city.append("")
        results_state.append("")

    # Respect Nominatim 1 req/sec
    time.sleep(1)

df["results_city"] = results_city
df["results_state"] = results_state

df.to_csv("data/interim/usa_nan_cities_mapped.csv", index=True)

print("Process completed.")
