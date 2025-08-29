import time

import pandas as pd
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="ufo-country-fixer/1.0")

df = pd.read_csv(r"data\interim\country_nan.csv")

# Ensure output columns exist
for col in ["results_city", "results_state", "results_country"]:
    if col not in df.columns:
        df[col] = pd.NA

# --- helpers ---------------------------------------------------------------


def is_missing(x):
    # Robust missing check: handles None, NaN, <NA>, empty strings
    return pd.isna(x) or (isinstance(x, str) and x.strip() == "")


ALLOWED = {"ca", "us", "au", "de", "gb"}

# For Canada, mapping full province/territory names to 2-letter codes (short list).
CA_NAME_TO_CODE = {
    "alberta": "ab",
    "british columbia": "bc",
    "manitoba": "mb",
    "new brunswick": "nb",
    "newfoundland and labrador": "nl",
    "northwest territories": "nt",
    "nova scotia": "ns",
    "nunavut": "nu",
    "ontario": "on",
    "prince edward island": "pe",
    "quebec": "qc",
    "saskatchewan": "sk",
    "yukon": "yt",
}


def extract_subdivision_code(address: dict, country_code: str):
    """
    Try to get a 2–3 letter subdivision code for US/CA using ISO3166-2 keys first.
    Falls back to a small name->code map for Canada.
    """
    # Prefer ISO3166-2-lvl* keys like "US-CA" / "CA-BC"
    for k in (
        "ISO3166-2-lvl8",
        "ISO3166-2-lvl7",
        "ISO3166-2-lvl6",
        "ISO3166-2-lvl5",
        "ISO3166-2-lvl4",
        "ISO3166-2-lvl3",
        "ISO3166-2-lvl2",
    ):
        iso = address.get(k)
        if isinstance(iso, str) and "-" in iso:
            ctry, sub = iso.split("-", 1)
            if ctry.lower() == country_code and 1 <= len(sub) <= 3:
                return sub.lower()

    # Some Nominatim instances expose 'state_code'
    sc = address.get("state_code")
    if isinstance(sc, str) and 1 <= len(sc) <= 3:
        return sc.lower()

    # Canada fallback from full name
    if country_code == "ca":
        name = (address.get("state") or "").strip().lower()
        return CA_NAME_TO_CODE.get(name)

    # For the US, if ISO keys are missing, you'd need a full name->code map (50 entries).
    # We skip that to keep this script compact.
    return None


# --- select rows to process ------------------------------------------------

# You said both state & country are missing; target rows with missing results_country.
# (If you want to require BOTH missing in the *original* columns, change the mask accordingly.)
need_mask = df["results_country"].apply(is_missing)

total = int(need_mask.sum())
print(f"Rows needing reverse geocode for country: {total}")

processed = 0

# --- main loop -------------------------------------------------------------
for idx, row in df.loc[need_mask].iterrows():
    lat, lon = row.get("latitude"), row.get("longitude")

    # If coords missing, bucket to ROW and continue
    if pd.isna(lat) or pd.isna(lon):
        df.loc[idx, ["results_city", "results_state", "results_country"]] = [
            "",
            "",
            "rof",
        ]
        processed += 1
        continue

    # Retry a few times for transient errors
    last_error = None
    for attempt in range(3):
        try:
            print(f"Processing {idx}: ({lat}, {lon}) [{processed + 1}/{total}]")
            loc = geolocator.reverse(
                (float(lat), float(lon)), exactly_one=True, language="en", timeout=15
            )

            address = (
                loc.raw.get("address", {}) if (loc and hasattr(loc, "raw")) else {}
            )

            country_code = (address.get("country_code") or "").lower()
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("hamlet")
                or ""
            )

            if country_code in ALLOWED:
                country_final = country_code
                # Only set state code for US/CA
                if country_code in {"us", "ca"}:
                    state_code = extract_subdivision_code(address, country_code) or ""
                else:
                    state_code = ""  # no state for AU/GB/DE
            else:
                country_final = "rof"
                state_code = ""

            df.loc[idx, ["results_city", "results_state", "results_country"]] = [
                city,
                state_code,
                country_final,
            ]
            break  # success → exit retry loop

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))  # small backoff then retry
            continue
        except Exception as e:
            last_error = e
            # Hard fail → bucket to ROW
            df.loc[idx, ["results_city", "results_state", "results_country"]] = [
                "",
                "",
                "rof",
            ]
            break

    if last_error:
        print(f"Index {idx} finished with status; last_error={last_error}")

    processed += 1
    time.sleep(1.1)  # respect Nominatim rate limits

    # Save progress every 500 rows
    if processed % 500 == 0:
        df.to_csv(r"data\interim\country_nan_mapped.partial.csv", index=True)
        print(f"Checkpoint saved at {processed}/{total}")

# Final save
df.to_csv(r"data\interim\country_nan_mapped.csv", index=True)
print("Process completed.")
