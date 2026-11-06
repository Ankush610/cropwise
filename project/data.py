"""Load the project datasets. Downloads are cached in data/raw so each source is fetched once."""
import datetime
import io
import json
import os
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

KAGGLE_DATASET = "atharvaingle/crop-recommendation-dataset"
POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_PARAMS = {"T2M": "temperature", "RH2M": "humidity", "PRECTOTCORR": "rainfall"}

# Crop -> APMC commodity names (both files' spellings). No price data for kidneybeans.
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
    # Added Nov 4: major crops the Kaggle list lacks
    "wheat": ["Wheat"], "soybean": ["Soyabean"], "groundnut": ["Groundnut"], "bajra": ["Bajra(Pearl Millet/Cumbu)"],
    "jowar": ["Jowar(Sorghum)"], "mustard": ["Mustard"], "sesamum": ["Sesamum(Sesame,Gingelly,Til)"],
    "ragi": ["Ragi (Finger Millet)"], "barley": ["Barley (Jau)"], "potato": ["Potato"], "onion": ["Onion"],
    "sugarcane": ["Sugarcane"],  # barely traded at mandis: cane goes to mills at the government's FRP
}
NEW_CROPS = ["wheat", "soybean", "groundnut", "bajra", "jowar", "mustard", "sesamum", "ragi", "barley", "potato", "onion",
             "sugarcane"]  # not in Kaggle; notebooks 07 and 08 leave them out to stay as run on Nov 3
# Crop -> DES district APY crop name. No muskmelon. Fruits stop between 2003 and 2019 and are thin.
APY_NAMES = {
    "rice": "Rice", "maize": "Maize", "chickpea": "Gram", "kidneybeans": "Rajmash Kholar",
    "pigeonpeas": "Arhar/Tur", "mothbeans": "Moth", "mungbean": "Moong(Green Gram)", "blackgram": "Urad",
    "lentil": "Masoor", "pomegranate": "Pome Granet", "banana": "Banana", "mango": "Mango", "grapes": "Grapes",
    "watermelon": "Water Melon", "apple": "Apple", "orange": "Orange", "papaya": "Papaya", "coconut": "Coconut",
    "cotton": "Cotton(Lint)", "jute": "Jute", "coffee": "Coffee",
    "wheat": "Wheat", "soybean": "Soyabean", "groundnut": "Groundnut", "bajra": "Bajra", "jowar": "Jowar",
    "mustard": "Rapeseed &Mustard", "sesamum": "Sesamum", "ragi": "Ragi", "barley": "Barley", "potato": "Potato",
    "onion": "Onion", "sugarcane": "Sugarcane",
}
# APY labels everything "Tonnes" but these are not. Factor turns them into tonnes of what the mandi prices.
APY_TO_TONNES = {
    "rice": 1 / 0.67,  # milled rice -> paddy, at the usual 67% outturn (Ludhiana: 4.72 t/ha rice vs 7.0 paddy reported)
    "cotton": 0.17 / 0.34,  # bales of lint (170 kg) -> kapas, at ~34% ginning outturn
    "jute": 0.18,  # bales of 180 kg
    "coconut": 0.0006,  # ponytail: nuts at ~0.6 kg each, an assumption; check against Kerala farm-gate data
}
SEASONS = ["kharif", "rabi", "summer"]  # by sowing month, see recommend.SEASON_MONTHS
# DES season -> sowing season. Winter rice is aman (sown Jun-Jul) and Summer rice is boro (sown Dec-Jan); other Winter
# crops (potato, pulses) are sown Oct-Nov.
SEASON_OF = {"Kharif": "kharif", "Autumn": "kharif", "Winter": "rabi", "Rabi": "rabi", "Summer": "summer"}
RICE_SEASON = {"Winter": "kharif", "Summer": "rabi"}
# 10-12 month or perennial crops: planted in any season, so their area is split equally across SEASONS
YEAR_ROUND = ["sugarcane", "coconut", "banana", "papaya", "mango", "orange", "grapes", "coffee", "pomegranate"]
STALE_BEFORE = "2010-2011"  # DES series that stop earlier are not current (1,105 of 13,150 crop-district series)
APY_URL = (
    "https://ckandev.indiadataportal.com/dataset/f2bbc28c-6c7c-462b-9064-ea4c4213d466/resource/"
    "f980409d-49a2-42ae-9eb0-182365005c04/download/crop-wise-area-production-yield.csv"
)
SHC_URL = (
    "https://ckandev.indiadataportal.com/dataset/9f3010cc-1d5b-48ec-83f0-62d78238523c/resource/"
    "024cf507-4281-4c89-a40e-37b5add3a4df/download/soil-nutrient-analysis.csv"
)
# Soil Health Card class -> representative value, on the scale printed on the card. Class limits from the card template
# (SHC Operational Guidelines 2015, District Manual 2017): pH 6.5/8.2 ("Normal" in between), P 28/56, K 140/280 kg/ha;
# N 280/560 kg/ha (ICAR Harit Dhara, not on the template). ponytail: middle classes at their midpoint, open-ended ones a
# fixed step beyond the limit; the file gives only class counts, so district values are estimates.
SHC_LEVELS = {
    "Nitrogen": ("N", {"Low": 210, "Medium": 420, "High": 700}),
    "Phosphorus": ("P", {"Low": 14, "Medium": 42, "High": 70}),
    "Potassium": ("K", {"Low": 105, "Medium": 210, "High": 350}),
    "Soil Ph": ("ph", {"Acidic": 5.75, "Neutral": 7.35, "Alkaline": 8.95}),
}
# CACP cost-of-cultivation crop name -> crop. CACP surveys no fruit.
CACP_NAMES = {
    "Paddy": "rice", "Maize": "maize", "Gram": "chickpea", "Tur (Arhar)": "pigeonpeas", "Moong": "mungbean",
    "Urad": "blackgram", "Lentil": "lentil", "Masur": "lentil", "Cotton": "cotton", "Jute": "jute",
    "Wheat": "wheat", "Soyabean": "soybean", "Groundnut": "groundnut", "Bajra": "bajra", "Jowar": "jowar",
    "Rapeseed & Mustard (Toria/Taramira)": "mustard", "Sesamum (Til)": "sesamum", "Ragi": "ragi", "Barley": "barley",
    "Potato": "potato", "Onion": "onion", "Sugarcane": "sugarcane",
}
# India Data Portal mirror of Agmarknet (manual download): file, date column, commodity column
APMC_FILES = [
    ("APMC_Arrivals_And_Prices__Old_Data_download.zip", "report_date", "commodity"),  # 2021-01-01 .. 2025-10-26
    ("APMC_Arrivals_And_Prices__New_Source_download.zip", "date", "commodity_name"),  # 2025-10-27 .. 2026-05-31
]
# data.gov.in "Variety-wise daily market prices" (Agmarknet, Rs/quintal, history to yesterday). Tops up the APMC zips.
DAILY_URL = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"


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
    """Monthly mandi price per crop and state: median modal price (Rs/quintal) over all market-days, n = rows.

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
    zips = pd.read_csv(path, parse_dates=["month"])
    live = daily_prices()
    df = pd.concat([zips, live[live["month"] > zips["month"].max()]], ignore_index=True) if len(live) else zips
    med = df.groupby(["crop", "state"])["price"].transform("median")
    return df[df["price"].between(med / 5, med * 5)].reset_index(drop=True)  # unit slips, e.g. Goa coconut at Rs 14 (a nut)


def fetch_daily(day: datetime.date) -> Path:
    """One day of all-India mandi prices from data.gov.in (~22k rows), cached in data/raw/apmc/daily/.
    CSV, not JSON: a 10k-row page takes ~2 s instead of ~23 s."""
    path = RAW / "apmc" / "daily" / f"{day}.csv"
    if not path.exists():
        params = {"api-key": os.environ["DATA_GOV_IN_KEY"], "format": "csv", "limit": 10000,
                  "filters[Arrival_Date]": day.strftime("%d/%m/%Y")}
        pages = []
        while not pages or len(pages[-1]) == params["limit"]:
            for attempt in range(4):
                try:
                    r = requests.get(DAILY_URL, params={**params, "offset": sum(map(len, pages))}, timeout=120,
                                     headers={"User-Agent": "curl/8"})  # python-requests' own agent gets a 502 after 60 s
                    r.raise_for_status()
                    pages.append(pd.read_csv(io.StringIO(r.text)))
                    break
                except (requests.RequestException, pd.errors.ParserError):
                    if attempt == 3:
                        raise
                    time.sleep(10 * 2**attempt)  # the API gives 502s now and then
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(pages).to_csv(path, index=False)
    return path


def daily_prices(start: datetime.date | None = None, end: datetime.date | None = None) -> pd.DataFrame:
    """Monthly prices (same columns as mandi_prices) from the data.gov.in daily files; with start/end, fetches those
    days first (needs DATA_GOV_IN_KEY). Cached in data/processed/prices_monthly_live.csv so a clone runs without them."""
    path = PROCESSED / "prices_monthly_live.csv"
    if start:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        days = [start + datetime.timedelta(d) for d in range((end - start).days + 1)]
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(fetch_daily, days))
    files = sorted((RAW / "apmc" / "daily").glob("*.csv"))
    if files:
        names = {n.replace(" ", "").lower(): crop for crop, ns in APMC_NAMES.items() for n in ns}
        df = pd.concat(pd.read_csv(f, usecols=["Arrival_Date", "Commodity", "State", "Modal_Price"]) for f in files)
        df["crop"] = df["Commodity"].str.replace(" ", "").str.lower().map(names)
        df = df[df["crop"].notna() & (df["Modal_Price"] > 0)]
        df["month"] = pd.to_datetime(df["Arrival_Date"], format="%d/%m/%Y").dt.to_period("M").dt.to_timestamp()
        out = (df.assign(state=df["State"].str.title()).groupby(["crop", "state", "month"])["Modal_Price"]
               .agg(price="median", n="size").reset_index())
        out.to_csv(path, index=False)
    return pd.read_csv(path, parse_dates=["month"]) if path.exists() else pd.DataFrame(columns=["crop", "state", "month", "price", "n"])


def _apy_raw() -> Path:
    """DES district APY CSV, downloaded once to data/raw/apy/."""
    raw = RAW / "apy" / "crop-wise-area-production-yield.csv"
    if not raw.exists():
        r = requests.get(APY_URL, timeout=300, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(r.content)
    return raw


def district_yield() -> pd.DataFrame:
    """Yield (t/ha) and area (ha) per crop and district: mean of each district's last 5 reported years.

    Source: DES district-wise area, production, yield 1997-98 to 2022-23 (India Data Portal), cached in data/raw/apy/.
    Series last reported before STALE_BEFORE are dropped (e.g. Thanjavur potato, 1997-99 only); last_year shows how
    stale the rest are: some fruits stop between 2010 and 2019.
    """
    path = PROCESSED / "district_yield.csv"
    if not path.exists():
        df = pd.read_csv(_apy_raw())
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
        out = out[out["last_year"] >= STALE_BEFORE]
        PROCESSED.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
    return pd.read_csv(path)


def district_season_area() -> pd.DataFrame:
    """Area (ha) per district, sowing season (kharif / rabi / summer) and crop: mean of each series' last 5 reported
    years; series last reported before STALE_BEFORE are dropped. Columns: district_code, season, crop, area_ha.

    DES seasons -> sowing season: SEASON_OF, except rice (RICE_SEASON). Year-round crops (YEAR_ROUND) are split
    equally across the seasons whatever their DES season; other crops' "Whole Year" area goes to their main season
    (e.g. potato -> rabi).
    """
    path = PROCESSED / "district_season_area.csv"
    if not path.exists():
        df = pd.read_csv(_apy_raw(), usecols=["district_code", "year", "season", "crop_name", "area"])
        df["crop"] = df["crop_name"].map({v: k for k, v in APY_NAMES.items()})
        df = df[df["crop"].notna() & (df["area"] > 0) & (df["season"] != "Total")]
        df["sow"] = df["season"].map(SEASON_OF)
        rice = df["crop"] == "rice"
        df.loc[rice, "sow"] = df.loc[rice, "season"].map(RICE_SEASON).fillna(df.loc[rice, "sow"])
        whole = df["season"] == "Whole Year"
        main = df[~whole].groupby(["crop", "sow"])["area"].sum().groupby("crop").idxmax().str[1]
        df.loc[whole, "sow"] = df.loc[whole, "crop"].map(main)
        # ponytail: year-round crops split equally across seasons, whatever DES calls them (UP files sugarcane as Kharif);
        # real planting windows differ by region (north: mostly spring), a planting calendar would sharpen this.
        year_round = df[df["crop"].isin(YEAR_ROUND)]
        thirds = year_round.assign(area=year_round["area"] / len(SEASONS))
        df = pd.concat([df[~df.index.isin(year_round.index)]] + [thirds.assign(sow=x) for x in SEASONS])
        df = df.groupby(["crop", "district_code", "sow", "year"])["area"].sum().reset_index()
        df = df.sort_values("year").groupby(["crop", "district_code", "sow"]).tail(5)
        out = df.groupby(["district_code", "sow", "crop"]).agg(area_ha=("area", "mean"), last_year=("year", "max")).reset_index()
        out = out[out["last_year"] >= STALE_BEFORE].rename(columns={"sow": "season"})
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


def district_soil() -> pd.DataFrame:
    """Estimated mean N, P, K (kg/ha) and pH per LGD district from Soil Health Card tests, all years pooled.

    The SHC file only counts samples per class (Low/Medium/High), so each district's value is the count-weighted mean
    of the SHC_LEVELS class values. These are soil test values: not the same scale as Kaggle's N, P, K (notebook 08).
    Built once from the 1.1 GB CSV in data/raw/shc/ (India Data Portal), cached in data/processed/. samples = N tests.
    """
    path = PROCESSED / "district_soil.csv"
    if not path.exists():
        raw = RAW / "shc" / "soil-nutrient-analysis.csv"
        if not raw.exists():
            raw.parent.mkdir(parents=True, exist_ok=True)
            with requests.get(SHC_URL, stream=True, timeout=600, headers={"User-Agent": "Mozilla/5.0"}) as r:
                r.raise_for_status()
                with open(raw, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
        cols = ["district_code", "nutrient_name", "nutrient_level", "value"]
        parts = [ch[ch["nutrient_name"].isin(SHC_LEVELS)].groupby(cols[:3])["value"].sum()
                 for ch in pd.read_csv(raw, usecols=cols, chunksize=2_000_000)]
        n = pd.concat(parts).groupby(level=[0, 1, 2]).sum().reset_index()
        n["level_value"] = [SHC_LEVELS[k][1].get(lv) for k, lv in zip(n["nutrient_name"], n["nutrient_level"])]
        n = n.dropna(subset=["level_value"]).astype({"level_value": float})
        n["weighted"] = n["level_value"] * n["value"]
        g = n.groupby(["district_code", "nutrient_name"])[["weighted", "value"]].sum()
        out = (g["weighted"] / g["value"]).unstack().rename(columns={k: v[0] for k, v in SHC_LEVELS.items()})
        out["samples"] = g["value"].xs("Nitrogen", level=1)
        out = out[out["samples"] > 0].round(2)
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
