"""Streamlit demo: soil card + district -> ranked crops with net return and SHAP reasons.

Run from the repo root: .venv/bin/streamlit run project/app.py
"""
import datetime

import matplotlib.pyplot as plt
import pandas as pd
import shap
import streamlit as st

import data
import recommend

FEATURE_NAMES = {
    "N": "Nitrogen", "P": "Phosphorus", "K": "Potassium", "ph": "Soil pH", "temperature": "Temperature (year)",
    "humidity": "Humidity", "rainfall": "Rainfall (year)", "rain_kharif": "Kharif rainfall", "rain_rabi": "Rabi rainfall",
    "temp_kharif": "Kharif temperature", "temp_rabi": "Rabi temperature",
}


@st.cache_data
def districts() -> pd.DataFrame:
    soil = data.district_soil()
    soil = soil[soil["samples"] >= 100]
    return recommend._tables()[2].merge(soil, on="district_code", how="left").sort_values(["state_name", "district_name"])


def reasons(e: shap.Explanation) -> str:
    """Plain sentence: the two inputs that pushed this crop up most, and the one that pushed it down most."""
    s = pd.Series(e.values, index=[FEATURE_NAMES[f] for f in e.feature_names])
    up = [f for f, v in s.nlargest(2).items() if v > 0]
    down = s.idxmin() if s.min() < 0 else None
    text = f"Helped most by: {', '.join(up)}." if up else "Nothing pushed this crop up much."
    return text + (f" Held back most by: {down}." if down else "")


st.set_page_config(page_title="Crop recommendation", layout="wide")
st.title("Crop recommendation")
st.caption("Enter your Soil Health Card values and district. The model suggests up to 3 crops, ranked, with the "
           "expected net return and the reasons.")

d = districts()
with st.sidebar:
    st.header("Your farm")
    state = st.selectbox("State", sorted(d["state_name"].unique()), index=None, placeholder="Choose a state")
    names = d.loc[d["state_name"] == state, "district_name"].tolist() if state else []
    district = st.selectbox("District", names, index=None, placeholder="Choose a district", disabled=not state)
    row = d[(d["state_name"] == state) & (d["district_name"] == district)].iloc[0] if district else None
    has_avg = row is not None and pd.notna(row["N"])

    st.subheader("Soil (from your Soil Health Card)")
    if row is not None:
        st.caption("Filled in with your district's average from Soil Health Card tests. Change them to your card's values."
                   if has_avg else "No Soil Health Card average for this district: please enter your card's values.")
    avg = row if has_avg else {"N": 250.0, "P": 20.0, "K": 230.0, "ph": 7.0}
    key = f"{state}|{district}"  # new defaults when the district changes
    N = st.number_input("Nitrogen, N (kg/ha)", 0.0, 2000.0, float(round(avg["N"])), 10.0, key=f"N{key}")
    P = st.number_input("Phosphorus, P (kg/ha)", 0.0, 500.0, float(round(avg["P"], 1)), 1.0, key=f"P{key}")
    K = st.number_input("Potassium, K (kg/ha)", 0.0, 2000.0, float(round(avg["K"])), 10.0, key=f"K{key}")
    ph = st.number_input("Soil pH", 3.0, 10.0, float(round(avg["ph"], 1)), 0.1, key=f"ph{key}")
    sow = st.date_input("Sowing date", datetime.date.today())
    go = st.button("Recommend crops", type="primary", disabled=not district, width="stretch")

if go:
    try:
        st.session_state["result"] = recommend.recommend(N, P, K, ph, district, state, sow=sow)
    except ValueError as err:
        st.error(str(err))
        st.session_state.pop("result", None)

if "result" not in st.session_state:
    st.info("Choose your state and district on the left, check the soil values, then press **Recommend crops**.")
    st.stop()

inputs, table = st.session_state["result"]
st.subheader(f"{inputs['district']}, {inputs['state']} · sowing {inputs['sow']}")
c = st.columns(4)
c[0].metric("Temperature", f"{inputs['temperature']:.0f} °C")
c[1].metric("Rain, whole year", f"{inputs['rainfall']:.0f} mm")
c[2].metric("Rain, kharif (Jun–Sep)", f"{inputs['rain_kharif']:.0f} mm")
c[3].metric("Rain, rabi (Nov–Feb)", f"{inputs['rain_rabi']:.0f} mm")
st.caption("Rain is the average per month. NASA POWER, 2015–2024 averages at your district's markets.")

show = pd.DataFrame({
    "Crop": table["crop"].str.title(),
    "Suitability": table["suitability"],
    "Net return (Rs/ha)": table["net_rs_ha"],
    "Yield (t/ha)": table["yield_t_ha"],
    "Price at harvest (Rs/quintal)": table["price_rs_q"],
    "Price forecast error": table["price_mape"].map(lambda m: f"{m:.0f}%" if pd.notna(m) else "–"),
    "Price source": table["price_source"],
    "Cost source": table["cost_source"],
    "Yield source": table["yield_source"],
}, index=table.index)
st.dataframe(show, width="stretch", column_config={
    "Suitability": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
    "Net return (Rs/ha)": st.column_config.NumberColumn(format="localized"),
    "Price at harvest (Rs/quintal)": st.column_config.NumberColumn(format="localized"),
})
notes = []
if table["near_tie"].sum() > 1:
    notes.append("Crops marked equally suitable are ordered by net return.")
if (table["net_rs_ha"] < 0).any():
    notes.append("A negative net return means the government cost survey (CACP) found costs above the crop's value in your state.")
if table["price_source"].str.startswith("MSP").any():
    notes.append("MSP is the government's support price: in Punjab and Haryana most paddy and wheat is bought at MSP, "
                 "so it is used instead of a forecast.")
if table["price_mape"].gt(30).any():
    notes.append("Prices with a forecast error above 30% are uncertain: the market for that crop swings a lot.")
st.caption(" ".join(["**Suitability** is the share of farmland that districts with similar soil and weather put under "
                     "the crop (district crop survey data). **Net return** = yield × forecast price − cultivation cost."] + notes))

st.subheader("Why these crops?")
tabs = st.tabs(table["crop"].str.title().tolist())
for tab, crop in zip(tabs, table["crop"]):
    with tab:
        e = recommend.explain(inputs, crop)
        st.write(reasons(e))
        e.feature_names = [FEATURE_NAMES[f] for f in e.feature_names]
        fig = plt.figure()
        shap.plots.waterfall(e, max_display=8, show=False)
        st.pyplot(plt.gcf(), clear_figure=True)
        plt.close(fig)
        st.caption("Bars show how much each input moved this crop's suitability up (red) or down (blue) from the average "
                   "district. They add up to the suitability shown above.")
