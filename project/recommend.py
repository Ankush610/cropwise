"""Recommend crops for one farm: suitability (crop model) -> net return (district yield x forecast price - CACP cost) -> SHAP reasons.

Used by the ranking notebook, the Streamlit app and the agent's tools.
"""
import datetime
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import shap

import data

QUINTALS_PER_TONNE = 10
ACRES_PER_HECTARE = 2.471  # the app shows farmers acres; the models and paper stay in hectares
MIN_SUITABILITY = 0.05  # below this a crop isn't shown, unless it's the only one
NEAR_TIE = 0.8  # net return re-orders only crops at least this suitable relative to the top crop (notebook 07)
MAX_TOP = 10  # most crops a farmer can ask for; the quietest season (summer) offers 17, and past ~10 most fall below MIN_SUITABILITY
# Months from sowing to sale. Crops not listed are perennial: they sell every year, so they get the 12-month mean price.
GROW_MONTHS = {
    "rice": 4, "maize": 4, "chickpea": 4, "kidneybeans": 4, "lentil": 4, "jute": 4, "pigeonpeas": 6, "cotton": 6,
    "mothbeans": 3, "mungbean": 3, "blackgram": 3, "watermelon": 3, "muskmelon": 3,
    "wheat": 5, "soybean": 4, "groundnut": 4, "bajra": 3, "jowar": 4, "mustard": 4, "sesamum": 3, "ragi": 4, "barley": 4,
    "potato": 4, "onion": 4, "sugarcane": 12,
}

# Minimum support price, Rs/quintal: paddy (common) KMS 2026-27, wheat RMS 2026-27. In these states the government buys
# most of the crop at MSP, so mandi data is thin (Punjab paddy: 20 months) and MSP is what farmers get.
MSP = {"rice": 2441, "wheat": 2585}
PROCUREMENT_STATES = {"Punjab", "Haryana"}


MIN_TESTS = 100  # a district's Soil Health Card average is used only with at least this many tests (as in training)
NEAREST = 3  # districts without one get the mean of this many nearest districts that have one


# Sowing month -> season (data.SEASONS). The crop model is trained on DES area by season (notebook 11).
SEASON_MONTHS = {"kharif": (6, 7, 8, 9), "rabi": (10, 11, 12, 1), "summer": (2, 3, 4, 5)}
QUIET_SEASON = 0.1  # below this share of the district's main-season area, the app warns that little is sown then

FEATURE_NAMES = {
    "N": "Nitrogen", "P": "Phosphorus", "K": "Potassium", "ph": "Soil pH", "temperature": "Temperature (year)",
    "humidity": "Humidity", "rainfall": "Rainfall (year)", "rain_kharif": "Kharif rainfall", "rain_rabi": "Rabi rainfall",
    "temp_kharif": "Kharif temperature", "temp_rabi": "Rabi temperature", "season_code": "Season",
}

MODEL_FILE = "crop_model.joblib"  # in models/; notebooks set "annual_crop_model.joblib" (09, 10) or "kaggle_crop_model.joblib" (04, 08)


@lru_cache
def _model() -> dict:
    return joblib.load(data.ROOT / "models" / MODEL_FILE)


@lru_cache
def _explainer() -> shap.TreeExplainer:
    return shap.TreeExplainer(_model()["forest"])


@lru_cache
def _tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    yields = data.district_yield()
    prices = pd.read_csv(data.PROCESSED / "price_forecast.csv", parse_dates=["month"])
    prices["moy"] = prices["month"].dt.month
    coords = data.district_coords().astype({"district_code": int})
    districts = yields.drop_duplicates("district_code")[["district_code", "state_name", "district_name"]].merge(coords)
    return yields, prices, districts, data.cost_shares()


def find_district(name: str, state: str | None = None) -> pd.Series:
    """District row (code, state, name, lat, lon) by name, case-insensitive. Pass `state` when the name is ambiguous."""
    d = _tables()[2]
    hit = d[d["district_name"].str.lower() == name.strip().lower()]
    if state:
        hit = hit[hit["state_name"].str.lower() == state.strip().lower()]
    if len(hit) != 1:
        found = (hit["district_name"] + ", " + hit["state_name"]).tolist()
        raise ValueError(f"District {name!r}: {'ambiguous, pass state: ' + str(found) if found else 'not found or has no coordinates'}")
    return hit.iloc[0]


@lru_cache
def _soil() -> pd.DataFrame:
    soil = data.district_soil()
    return _tables()[2].merge(soil[soil["samples"] >= MIN_TESTS], on="district_code")


def area_soil(district: str, state: str | None = None) -> tuple[dict, str]:
    """Typical N, P, K (kg/ha) and pH for a farmer without a Soil Health Card, and where they came from: the district's
    card average, else the mean of the NEAREST closest districts that have one. An estimate for the area, not the field."""
    d = find_district(district, state)
    soil = _soil()
    own = soil[soil["district_code"] == d["district_code"]]
    if len(own):
        rows, source = own, f"Soil Health Card average for {d['district_name']}"
    else:  # ponytail: flat-earth distance, fine at district scale
        dist = ((soil["lat"] - d["lat"]) ** 2 + ((soil["lon"] - d["lon"]) * np.cos(np.radians(d["lat"]))) ** 2) ** 0.5
        rows = soil.loc[dist.nsmallest(NEAREST).index]
        source = "Mean of nearest districts with Soil Health Card data: " + ", ".join(rows["district_name"])
    v = rows[["N", "P", "K", "ph"]].mean()
    return {"N": round(float(v["N"])), "P": round(float(v["P"]), 1), "K": round(float(v["K"])), "ph": round(float(v["ph"]), 2)}, source


def season(sow: datetime.date) -> str:
    return next(s for s, months in SEASON_MONTHS.items() if sow.month in months)


@lru_cache
def _season_area() -> pd.DataFrame:
    """Sown area (ha) per district and season, all crops."""
    return data.district_season_area().groupby(["district_code", "season"])["area_ha"].sum().unstack(fill_value=0)


def season_share(district_code: int, s: str) -> float:
    """The district's area sown in season `s` as a share of its biggest season (NaN if DES has no area)."""
    a = _season_area()
    if district_code not in a.index:
        return float("nan")
    row = a.loc[district_code]
    return float(row.get(s, 0) / row.max())


def weather(lat: float, lon: float) -> dict:
    """NASA POWER 2015-2024: mean temperature (°C), humidity (%) and mean monthly rainfall (mm), for the whole year
    and for kharif (Jun-Sep) and rabi (Nov-Feb). The season values help the district model (notebook 09)."""
    w = data.nasa_weather(round(lat, 2), round(lon, 2))
    kharif, rabi = w[w.index.month.isin([6, 7, 8, 9])].mean(), w[w.index.month.isin([11, 12, 1, 2])].mean()
    out = {**w.mean()[["temperature", "humidity", "rainfall"]],
           "rain_kharif": kharif["rainfall"], "rain_rabi": rabi["rainfall"],
           "temp_kharif": kharif["temperature"], "temp_rabi": rabi["temperature"]}
    return {k: round(float(v), 1) for k, v in out.items()}


def _yield(crop: str, district: pd.Series) -> tuple[float, str]:
    """Yield in t/ha: the district's own, else its state's median district, else India's."""
    y = _tables()[0]
    y = y[y["crop"] == crop]
    for rows, source in [
        (y[y["district_code"] == district["district_code"]], "district"),
        (y[y["state_name"] == district["state_name"]], "state median"),
        (y, "India median"),
    ]:
        if len(rows):
            return float(rows["yield_t_ha"].median()), source
    return float("nan"), "no yield data"


def _price(crop: str, state: str, sow: datetime.date) -> tuple[float, str, float]:
    """Forecast Rs/quintal when the crop is sold: MSP for paddy and wheat in procurement states, else the state's series,
    else All India. Returns (price, source, mape); mape is NaN for MSP (a fixed price, not a forecast)."""
    if crop in MSP and state in PROCUREMENT_STATES:
        return float(MSP[crop]), "MSP 2026-27", float("nan")
    p = _tables()[1]
    p = p[p["crop"] == crop]
    if crop in GROW_MONTHS:  # the forecast covers 12 months, so month-of-year picks one
        p = p[p["moy"] == (sow.month - 1 + GROW_MONTHS[crop]) % 12 + 1]
    for source in (state, "All India"):
        rows = p[p["state"] == source]
        if len(rows):
            return float(rows["price"].mean()), source, float(rows["mape"].iloc[0])
    return float("nan"), "no price data", float("nan")


def _cost_share(crop: str, state: str) -> tuple[float, str]:
    """CACP A2+FL cost as a share of gross value: the state's, else All India, else the median field crop's (assumed)."""
    c = _tables()[3]
    for source in (state, "All India"):
        rows = c[(c["crop"] == crop) & (c["state"] == source)]
        if len(rows):
            return float(rows["a2fl_share"].iloc[0]), f"CACP {source}"
    assumed = float(c.loc[c["state"] == "All India", "a2fl_share"].median())
    if crop in GROW_MONTHS:
        return assumed, "assumed (no CACP data)"
    return assumed, "assumed (no CACP data; orchard set-up and years before first harvest not counted)"


def per_acre(crop: str, yield_t_ha: float, net_rs_ha: float) -> dict:
    """Farmer units: yield in quintals an acre, net return an acre, and that net spread over the crop's months in the
    field (grow_months; None for a perennial, spread over a year), so short and long crops compare fairly."""
    months = GROW_MONTHS.get(crop)
    net = net_rs_ha / ACRES_PER_HECTARE
    return {"grow_months": months, "yield_q_acre": round(yield_t_ha * QUINTALS_PER_TONNE / ACRES_PER_HECTARE, 1),
            "net_rs_acre": round(net, 0), "net_rs_acre_month": round(net / (months or 12), 0)}


def recommend(N: float, P: float, K: float, ph: float, district: str, state: str | None = None,
              sow: datetime.date | None = None, top: int = 3) -> tuple[dict, pd.DataFrame]:
    """Top `top` (clamped to 1..MAX_TOP) suitable crops (suitability >= MIN_SUITABILITY), in suitability order, except that crops within
    NEAR_TIE of the top crop's suitability are ordered by net return (gross revenue x (1 - cost share)).

    N, P, K are kg/ha as printed on a Soil Health Card. Suitability is the share of the season's farmland that districts
    with similar soil and weather put under the crop; the season comes from the sowing month (season model, notebook 11).
    The model decides what fits; money only breaks near-ties (notebook 07: multiplying suitability by revenue put the
    wrong crop first more often). Returns (inputs, table). `inputs` holds the model features plus the season, how much
    the district sows in it (season_share) and the district. A near-tie crop with no yield or price goes last among the
    near-ties.
    """
    if min(N, P, K) < 0 or not 3 <= ph <= 10:
        raise ValueError("N, P, K must be >= 0 and pH between 3 and 10")
    sow = sow or datetime.date.today()
    d = find_district(district, state)
    s = season(sow)
    inputs = {"N": N, "P": P, "K": K, "ph": ph, **weather(d["lat"], d["lon"]), "season_code": data.SEASONS.index(s),
              "season": s, "season_share": season_share(int(d["district_code"]), s),
              "district": d["district_name"], "state": d["state_name"], "sow": sow.isoformat()}

    m = _model()
    X = pd.DataFrame([inputs])[m["features"]]
    proba = pd.Series(m["model"].predict_proba(X)[0], index=m["classes"])
    if "season_crops" in m:  # only crops grown that season in >= 5% of districts (notebook 11)
        proba = proba[proba.index.isin(m["season_crops"][s])]
    proba = proba.nlargest(min(max(int(top), 1), MAX_TOP))
    proba = proba[(proba >= MIN_SUITABILITY) | (proba == proba.max())]

    rows = []
    for crop, p in proba.items():
        y, y_src = _yield(crop, d)
        price, p_src, mape = _price(crop, d["state_name"], sow)
        revenue = y * QUINTALS_PER_TONNE * price
        share, c_src = _cost_share(crop, d["state_name"])
        rows.append({"crop": crop, "suitability": p, "yield_t_ha": y, "yield_source": y_src,
                     "price_rs_q": price, "price_source": p_src, "price_mape": mape, "revenue_rs_ha": revenue,
                     "cost_share": share, "cost_source": c_src, "net_rs_ha": revenue * (1 - share),
                     **per_acre(crop, y, revenue * (1 - share))})
    table = pd.DataFrame(rows)  # already in suitability order
    near = table["suitability"] >= NEAR_TIE * table["suitability"].iloc[0]
    table["near_tie"] = near
    table = pd.concat([table[near].sort_values("net_rs_ha", ascending=False, na_position="last", kind="stable"), table[~near]])
    table = table.round({"suitability": 3, "yield_t_ha": 2, "price_rs_q": 0, "revenue_rs_ha": 0, "cost_share": 2,
                         "net_rs_ha": 0}).reset_index(drop=True)
    table.index += 1
    return inputs, table


def explain(inputs: dict, crop: str) -> shap.Explanation:
    """SHAP values for one crop: how much each input pushed it up or down from the average.

    The district model has no calibration step, so the values add up to the suitability shown. (The Kaggle model, kept
    for notebooks 04 and 08, explains its forest before isotonic calibration; the pushes point the same way.)
    Plot with shap.plots.waterfall(explain(inputs, crop)).
    """
    m = _model()
    if crop not in m["classes"]:
        raise ValueError(f"Unknown crop {crop!r}; the model knows: {', '.join(m['classes'])}")
    X = pd.DataFrame([inputs])[m["features"]]
    return _explainer()(X)[0, :, m["classes"].index(crop)]


def reasons(e: shap.Explanation) -> str:
    """Plain sentence: the two inputs that pushed this crop up most, and the one that pushed it down most."""
    s = pd.Series(e.values, index=[FEATURE_NAMES[f] for f in e.feature_names])
    up = [f for f, v in s.nlargest(2).items() if v > 0]
    down = s.idxmin() if s.min() < 0 else None
    text = f"Helped most by: {', '.join(up)}." if up else "Nothing pushed this crop up much."
    return text + (f" Held back most by: {down}." if down else "")


def check_crop(inputs: dict, crop: str) -> dict:
    """One crop for a farm already run through recommend(), whether or not it made the top 3: suitability, rank among
    the crops offered that season, yield, harvest price, net return and the SHAP reason. Answers "why not X?"."""
    e = explain(inputs, crop)  # raises on an unknown crop
    m = _model()
    proba = pd.Series(m["model"].predict_proba(pd.DataFrame([inputs])[m["features"]])[0], index=m["classes"])
    offered = proba[proba.index.isin(m["season_crops"][inputs["season"]])] if "season_crops" in m else proba
    d = find_district(inputs["district"], inputs["state"])
    y, y_src = _yield(crop, d)
    price, p_src, mape = _price(crop, d["state_name"], datetime.date.fromisoformat(inputs["sow"]))
    share, c_src = _cost_share(crop, d["state_name"])
    return {"crop": crop, "suitability": round(float(proba[crop]), 3), "season": inputs["season"],
            "offered_this_season": crop in offered.index,
            "rank": int((offered > proba[crop]).sum()) + 1 if crop in offered.index else None, "out_of": len(offered),
            "yield_t_ha": round(y, 2), "yield_source": y_src, "price_rs_q": round(price, 0), "price_source": p_src,
            "price_mape": mape, "net_rs_ha": round(y * QUINTALS_PER_TONNE * price * (1 - share), 0), "cost_source": c_src,
            **per_acre(crop, y, y * QUINTALS_PER_TONNE * price * (1 - share)), "reason": reasons(e)}


def price_outlook(crop: str, state: str | None = None) -> dict:
    """12-month mandi price forecast (Rs/quintal): the state's series, else All India; MSP for paddy and wheat in
    procurement states."""
    if crop in MSP and state in PROCUREMENT_STATES:
        return {"crop": crop, "source": "MSP 2026-27 (fixed government price)", "price_rs_q": MSP[crop]}
    p = _tables()[1]
    p = p[p["crop"] == crop]
    for source in (state, "All India"):
        rows = p[p["state"] == source].sort_values("month")
        if len(rows):
            return {"crop": crop, "source": source, "forecast_error_pct": float(rows["mape"].iloc[0]),
                    "months": [{"month": m.strftime("%b %Y"), "price_rs_q": round(float(v))}
                               for m, v in zip(rows["month"], rows["price"])]}
    raise ValueError(f"No price data for {crop!r}")


if __name__ == "__main__":
    inputs, table = recommend(250, 40, 210, 6.8, "Raipur", sow=datetime.date(2026, 11, 4))  # Soil Health Card scale
    print(inputs, table, sep="\n")
    assert 1 <= len(table) <= 3 and table["suitability"].between(0, 1).all()
    near, rest = table[table["near_tie"]], table[~table["near_tie"]]
    assert table["near_tie"].is_monotonic_decreasing and len(near)  # near-ties first, top crop always one
    assert near["net_rs_ha"].dropna().is_monotonic_decreasing and rest["suitability"].is_monotonic_decreasing
    assert per_acre("rice", 2.471, 24710) == {"grow_months": 4, "yield_q_acre": 10.0, "net_rs_acre": 10000, "net_rs_acre_month": 2500}
    assert per_acre("mango", 1, 2471 * 12)["net_rs_acre_month"] == 1000  # perennial: a year
    e = explain(inputs, table["crop"].iloc[0])
    p = _model()["forest"].predict_proba(pd.DataFrame([inputs])[_model()["features"]])[0]
    assert abs(e.base_values + e.values.sum() - p[_model()["classes"].index(table["crop"].iloc[0])]) < 1e-6  # SHAP adds up
    print(pd.Series(e.values, index=e.feature_names).round(3))
    top = check_crop(inputs, table["crop"].iloc[0])
    assert top["suitability"] == table["suitability"].iloc[0] and top["offered_this_season"], top
    assert check_crop(inputs, "jute")["rank"] in (None, *range(2, 28))
    assert len(price_outlook("onion", "Maharashtra")["months"]) == 12 and "months" not in price_outlook("wheat", "Punjab")
    assert _price("rice", "Punjab", datetime.date(2026, 6, 15))[:2] == (2441.0, "MSP 2026-27")
    assert _price("rice", "Odisha", datetime.date(2026, 6, 15))[1] != "MSP 2026-27"
    assert [season(datetime.date(2026, m, 1)) for m in (1, 3, 6, 10)] == ["rabi", "summer", "kharif", "rabi"]
    assert area_soil("Vidisha")[1].startswith("Soil Health Card average")
    soil, src = area_soil("Ludhiana", "Punjab")  # 1 SHC test only
    assert src.startswith("Mean of nearest") and 3 <= soil["ph"] <= 10, src
    print(soil, src)
    many = recommend(250, 40, 210, 6.8, "Raipur", sow=datetime.date(2026, 11, 4), top=99)[1]
    assert len(table) <= len(many) <= MAX_TOP and many["crop"].iloc[0] == table["crop"].iloc[0], many
    assert len(recommend(250, 40, 210, 6.8, "Raipur", sow=datetime.date(2026, 11, 4), top=1)[1]) == 1
    print("ok")
