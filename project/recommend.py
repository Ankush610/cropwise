"""Recommend crops for one farm: suitability (crop model) -> net return (district yield x forecast price - CACP cost) -> SHAP reasons.

Used by the ranking notebook, the Streamlit app and the agent's tools.
"""
import datetime
from functools import lru_cache

import joblib
import pandas as pd
import shap

import data

QUINTALS_PER_TONNE = 10
MIN_SUITABILITY = 0.05  # below this a crop isn't shown, unless it's the only one
NEAR_TIE = 0.8  # net return re-orders only crops at least this suitable relative to the top crop (notebook 07)
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


MODEL_FILE = "crop_model.joblib"  # in models/; notebooks 04 and 08 set "kaggle_crop_model.joblib" before the first call


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


def recommend(N: float, P: float, K: float, ph: float, district: str, state: str | None = None,
              sow: datetime.date | None = None, top: int = 3) -> tuple[dict, pd.DataFrame]:
    """Top `top` suitable crops (suitability >= MIN_SUITABILITY), in suitability order, except that crops within
    NEAR_TIE of the top crop's suitability are ordered by net return (gross revenue x (1 - cost share)).

    N, P, K are kg/ha as printed on a Soil Health Card. Suitability is the share of farmland that districts with
    similar soil and weather put under the crop (district model, notebook 09).
    The model decides what fits; money only breaks near-ties (notebook 07: multiplying suitability by revenue put the
    wrong crop first more often). Returns (inputs, table). `inputs` holds the model features plus where the weather
    came from. A near-tie crop with no yield or price goes last among the near-ties.
    """
    if min(N, P, K) < 0 or not 3 <= ph <= 10:
        raise ValueError("N, P, K must be >= 0 and pH between 3 and 10")
    sow = sow or datetime.date.today()
    d = find_district(district, state)
    inputs = {"N": N, "P": P, "K": K, "ph": ph, **weather(d["lat"], d["lon"]),
              "district": d["district_name"], "state": d["state_name"], "sow": sow.isoformat()}

    m = _model()
    X = pd.DataFrame([inputs])[m["features"]]
    proba = pd.Series(m["model"].predict_proba(X)[0], index=m["classes"]).nlargest(top)
    proba = proba[(proba >= MIN_SUITABILITY) | (proba == proba.max())]

    rows = []
    for crop, p in proba.items():
        y, y_src = _yield(crop, d)
        price, p_src, mape = _price(crop, d["state_name"], sow)
        revenue = y * QUINTALS_PER_TONNE * price
        share, c_src = _cost_share(crop, d["state_name"])
        rows.append({"crop": crop, "suitability": p, "yield_t_ha": y, "yield_source": y_src,
                     "price_rs_q": price, "price_source": p_src, "price_mape": mape, "revenue_rs_ha": revenue,
                     "cost_share": share, "cost_source": c_src, "net_rs_ha": revenue * (1 - share)})
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
    X = pd.DataFrame([inputs])[m["features"]]
    return _explainer()(X)[0, :, m["classes"].index(crop)]


if __name__ == "__main__":
    inputs, table = recommend(250, 20, 230, 6.8, "Raipur", sow=datetime.date(2026, 11, 4))  # Soil Health Card scale
    print(inputs, table, sep="\n")
    assert 1 <= len(table) <= 3 and table["suitability"].between(0, 1).all()
    near, rest = table[table["near_tie"]], table[~table["near_tie"]]
    assert table["near_tie"].is_monotonic_decreasing and len(near)  # near-ties first, top crop always one
    assert near["net_rs_ha"].dropna().is_monotonic_decreasing and rest["suitability"].is_monotonic_decreasing
    e = explain(inputs, table["crop"].iloc[0])
    p = _model()["forest"].predict_proba(pd.DataFrame([inputs])[_model()["features"]])[0]
    assert abs(e.base_values + e.values.sum() - p[_model()["classes"].index(table["crop"].iloc[0])]) < 1e-6  # SHAP adds up
    print(pd.Series(e.values, index=e.feature_names).round(3))
    assert _price("rice", "Punjab", datetime.date(2026, 6, 15))[:2] == (2441.0, "MSP 2026-27")
    assert _price("rice", "Odisha", datetime.date(2026, 6, 15))[1] != "MSP 2026-27"
    print("ok")
