"""Load the project datasets. Downloads are cached in data/raw so each source is fetched once."""
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

KAGGLE_DATASET = "atharvaingle/crop-recommendation-dataset"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_PARAMS = {"T2M": "temperature", "RH2M": "humidity", "PRECTOTCORR": "rainfall"}

# Kaggle label -> APMC commodity names (both files' spellings). No price data for kidneybeans.
APMC_NAMES = {
    "rice": ["Paddy(Dhan)(Common)", "Paddy(Common)"],  # farmers sell paddy, not milled rice
    "maize": ["Maize"],
    "chickpea": ["Bengal Gram(Gram)(Whole)"],
    "pigeonpeas": ["Arhar (Tur/Red Gram)(Whole)", "Red Gram/Arhar/Tur(Whole)"],
    "mothbeans": ["Moath Dal"],  # proxy: only the split dal is traded, priced above whole grain
    "mungbean": ["Green Gram (Moong)(Whole)"],
    "blackgram": ["Black Gram (Urd Beans)(Whole)"],
    "lentil": ["Lentil (Masur)(Whole)"],
    "pomegranate": ["Pomegranate"],
    "banana": ["Banana"],
    "mango": ["Mango", "Mango (Raw-Ripe)"],
    "grapes": ["Grapes"],
    "watermelon": ["Water Melon"],
    "muskmelon": ["Karbuja(Musk Melon)"],
    "apple": ["Apple"],
    "orange": ["Orange"],
    "papaya": ["Papaya"],
    "coconut": ["Coconut"],
    "cotton": ["Cotton"],
    "jute": ["Jute"],
    "coffee": ["Coffee"],
}
# Kaggle label -> DES district APY crop name. No muskmelon. Fruits stop between 2003 and 2019 and are thin.
APY_NAMES = {
    "rice": "Rice", "maize": "Maize", "chickpea": "Gram", "kidneybeans": "Rajmash Kholar",
    "pigeonpeas": "Arhar/Tur", "mothbeans": "Moth", "mungbean": "Moong(Green Gram)", "blackgram": "Urad",
    "lentil": "Masoor", "pomegranate": "Pome Granet", "banana": "Banana", "mango": "Mango", "grapes": "Grapes",
    "watermelon": "Water Melon", "apple": "Apple", "orange": "Orange", "papaya": "Papaya", "coconut": "Coconut",
    "cotton": "Cotton(Lint)", "jute": "Jute", "coffee": "Coffee",
}
# APY labels everything "Tonnes" but these are not. Factor turns them into tonnes of what the mandi prices.
APY_TO_TONNES = {
    "cotton": 0.17 / 0.34,  # bales of lint (170 kg) -> kapas, at ~34% ginning outturn
    "jute": 0.18,  # bales of 180 kg
    "coconut": 0.0006,  # ponytail: nuts at ~0.6 kg each, an assumption; check against Kerala farm-gate data
}
APY_URL = (
    "https://ckandev.indiadataportal.com/dataset/f2bbc28c-6c7c-462b-9064-ea4c4213d466/resource/"
    "f980409d-49a2-42ae-9eb0-182365005c04/download/crop-wise-area-production-yield.csv"
)
# CACP cost-of-cultivation crop name -> Kaggle label. CACP surveys no fruit.
CACP_NAMES = {
    "Paddy": "rice", "Maize": "maize", "Gram": "chickpea", "Tur (Arhar)": "pigeonpeas", "Moong": "mungbean",
    "Urad": "blackgram", "Lentil": "lentil", "Masur": "lentil", "Cotton": "cotton", "Jute": "jute",
}
# India Data Portal mirror of Agmarknet (manual download): file, date column, commodity column
APMC_FILES = [
    ("APMC_Arrivals_And_Prices__Old_Data_download.zip", "report_date", "commodity"),  # 2021-01-01 .. 2025-10-26
    ("APMC_Arrivals_And_Prices__New_Source_download.zip", "date", "commodity_name"),  # 2025-10-27 .. 2026-05-31
]


def kaggle_crops() -> pd.DataFrame:
    """Kaggle Crop Recommendation: N, P, K, temperature, humidity, ph, rainfall, label (22 crops)."""
    path = RAW / "Crop_recommendation.csv"
    if not path.exists():
        import kagglehub

        RAW.mkdir(parents=True, exist_ok=True)
        src = Path(kagglehub.dataset_download(KAGGLE_DATASET))
        shutil.copy(src / "Crop_recommendation.csv", path)
    return pd.read_csv(path)


def nasa_weather(lat: float, lon: float, start: int = 2015, end: int = 2024) -> pd.DataFrame:
    """Monthly NASA POWER weather for one point: temperature (°C), humidity (%), rainfall (mm in the month)."""
    path = RAW / "nasa_power" / f"{lat:.2f}_{lon:.2f}_{start}_{end}.json"
    if not path.exists():
        r = requests.get(
            POWER_URL,
            params={
                "parameters": ",".join(POWER_PARAMS),
                "community": "AG",
                "latitude": lat,
                "longitude": lon,
                "start": start,
                "end": end,
                "format": "JSON",
            },
            timeout=60,
        )
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)

    df = pd.DataFrame(json.loads(path.read_text())["properties"]["parameter"]).rename(columns=POWER_PARAMS)
    df = df[~df.index.str.endswith("13")]  # month "13" is POWER's annual summary
    df.index = pd.to_datetime(df.index, format="%Y%m")
    df = df.mask(df == -999)  # POWER's missing-value marker
    df["rainfall"] *= df.index.days_in_month  # POWER gives mm/day averages
    return df


def mandi_prices() -> pd.DataFrame:
    """Monthly mandi price per Kaggle crop and state: median modal price (Rs/quintal) over all market-days, n = rows.

    Built once from the APMC zips in data/raw/apmc/ (3.6 GB + 0.8 GB CSV, ~30 s), cached in data/processed/.
    """
    path = PROCESSED / "prices_monthly.csv"
    if not path.exists():
        names = {n.replace(" ", ""): crop for crop, ns in APMC_NAMES.items() for n in ns}
        parts = []
        for file, date, com in APMC_FILES:
            z = zipfile.ZipFile(RAW / "apmc" / file)
            csv = next(n for n in z.namelist() if n.endswith(".csv"))
            cols = [date, "state_name", com, "modal_price", "price_unit"]
            for ch in pd.read_csv(z.open(csv), usecols=cols, chunksize=2_000_000):
                ch["crop"] = ch[com].str.replace(" ", "").map(names)
                ch = ch[ch["crop"].notna() & ch["price_unit"].str.contains("Quintal") & (ch["modal_price"] > 0)]
                parts.append(
                    pd.DataFrame(
                        {"crop": ch["crop"], "state": ch["state_name"].str.title(), "month": ch[date].str[:7], "price": ch["modal_price"]}
                    )
                )
        df = pd.concat(parts)
        out = df.groupby(["crop", "state", "month"])["price"].agg(price="median", n="size").reset_index()
        PROCESSED.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
    return pd.read_csv(path, parse_dates=["month"])


def district_yield() -> pd.DataFrame:
    """Yield (t/ha) and area (ha) per Kaggle crop and district: mean of each district's last 5 reported years.

    Source: DES district-wise area, production, yield 1997-98 to 2022-23 (India Data Portal), cached in data/raw/apy/.
    last_year shows how stale a yield is: most fruits stop between 2003 and 2019.
    """
    path = PROCESSED / "district_yield.csv"
    if not path.exists():
        raw = RAW / "apy" / "crop-wise-area-production-yield.csv"
        if not raw.exists():
            r = requests.get(APY_URL, timeout=300, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_bytes(r.content)
        df = pd.read_csv(raw)
        df["crop"] = df["crop_name"].map({v: k for k, v in APY_NAMES.items()})
        df = df[df["crop"].notna()]
        # Some years have a "Total" row as well as the seasons: use Total when present, else sum the seasons
        k = ["crop", "district_code", "year"]
        cols = ["area", "production"]
        total = df[df["season"] == "Total"].groupby(k)[cols].sum()
        seasons = df[df["season"] != "Total"].groupby(k)[cols].sum()
        yr = total.combine_first(seasons).reset_index()
        yr = yr[(yr["area"] > 0) & (yr["production"] > 0)]  # zero production is treated as missing
        yr["yield"] = yr["production"] / yr["area"] * yr["crop"].map(APY_TO_TONNES).fillna(1)
        yr = yr.sort_values("year").groupby(["crop", "district_code"]).tail(5)
        names = df.sort_values("year").groupby("district_code")[["state_name", "district_name"]].last()
        out = (
            yr.groupby(["crop", "district_code"])
            .agg(yield_t_ha=("yield", "mean"), area_ha=("area", "mean"), years=("year", "size"), last_year=("year", "max"))
            .reset_index()
            .join(names, on="district_code")
        )
        PROCESSED.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
    return pd.read_csv(path)


def district_coords() -> pd.DataFrame:
    """Latitude/longitude per LGD district code: median over that district's APMC markets. Districts without a market are missing."""
    path = PROCESSED / "district_coords.csv"
    if not path.exists():
        parts = []
        for file, _, _ in APMC_FILES:
            z = zipfile.ZipFile(RAW / "apmc" / file)
            csv = next(n for n in z.namelist() if n.endswith(".csv"))
            for ch in pd.read_csv(z.open(csv), usecols=["district_code", "latitude", "longitude"], chunksize=2_000_000):
                parts.append(ch.drop_duplicates())
        m = pd.concat(parts).drop_duplicates()
        m = m[m["latitude"].between(6, 38) & m["longitude"].between(68, 98)]  # drop points outside India
        out = m.groupby("district_code").agg(lat=("latitude", "median"), lon=("longitude", "median"), markets=("latitude", "size"))
        PROCESSED.mkdir(parents=True, exist_ok=True)
        out.to_csv(path)
    return pd.read_csv(path)


def cost_shares() -> pd.DataFrame:
    """CACP cost A2+FL (paid-out costs + family labour) as a share of gross value per crop and state.

    Median of the last 5 survey years (2017-18 to 2021-22). Costs are older than our prices, so the app applies the
    share to current revenue, assuming costs moved with prices. Columns: crop, state, a2fl_share;
    state "All India" is the median over all surveyed states and years.
    """
    c = pd.read_csv(RAW / "cost" / "cost-of-cultivation.csv")
    c = c[c["crop_name"].isin(CACP_NAMES) & (c["year"] >= "2017-18")]
    share = c["cul_cost_a2fl"] / (c["main_product_value"] + c["by_product_value"].fillna(0))
    crop = c["crop_name"].map(CACP_NAMES).rename("crop")
    by_state = share.groupby([crop, c["state_name"].rename("state")]).median()
    india = share.groupby(crop).median().to_frame("a2fl_share").assign(state="All India").set_index("state", append=True)
    return pd.concat([by_state.rename("a2fl_share").to_frame(), india]).reset_index()
