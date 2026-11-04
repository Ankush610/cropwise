"""Streamlit demo: soil card + district -> ranked crops with net return and SHAP reasons.

Run from the repo root: .venv/bin/streamlit run project/app.py
"""
import calendar
import datetime

import matplotlib.pyplot as plt
import pandas as pd
import shap
import streamlit as st

import recommend
from recommend import FEATURE_NAMES, reasons


@st.cache_data
def districts() -> pd.DataFrame:
    return recommend._tables()[2].sort_values(["state_name", "district_name"])


@st.cache_data
def area_soil(district: str, state: str) -> tuple[dict, str]:
    return recommend.area_soil(district, state)


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

    st.subheader("Soil")
    card = st.radio("Do you have a Soil Health Card?", ["Yes, I'll enter my card's values", "No, use typical values for my area"],
                    disabled=not district) == "Yes, I'll enter my card's values"
    avg, soil_source = area_soil(district, state) if district else ({"N": 250, "P": 40, "K": 210, "ph": 7.0}, "")
    if district:
        st.caption(f"Filled in from: {soil_source}. " + ("Change them to your card's values." if card else
                   "An estimate for your area, not your field: a Soil Health Card test is better."))
    key = f"{state}|{district}|{card}"  # new defaults when the district or the choice changes
    N = st.number_input("Nitrogen, N (kg/ha)", 0.0, 2000.0, float(avg["N"]), 10.0, key=f"N{key}", disabled=not card)
    P = st.number_input("Phosphorus, P (kg/ha)", 0.0, 500.0, float(avg["P"]), 1.0, key=f"P{key}", disabled=not card)
    K = st.number_input("Potassium, K (kg/ha)", 0.0, 2000.0, float(avg["K"]), 10.0, key=f"K{key}", disabled=not card)
    ph = st.number_input("Soil pH", 3.0, 10.0, float(avg["ph"]), 0.1, key=f"ph{key}", disabled=not card)
    month = st.selectbox("Sowing month", range(1, 13), datetime.date.today().month - 1, format_func=lambda m: calendar.month_name[m])
    sow = datetime.date(datetime.date.today().year, month, 1)  # only the month matters: season and harvest-month price
    st.caption(f"Season: **{recommend.season(sow)}** (kharif Jun–Sep, rabi Oct–Jan, summer Feb–May)")
    go = st.button("Recommend crops", type="primary", disabled=not district, width="stretch")

if go:
    try:
        st.session_state["result"] = recommend.recommend(N, P, K, ph, district, state, sow=sow)
        st.session_state["soil_note"] = "Soil: your Soil Health Card values." if card else f"Soil: estimated ({soil_source})."
    except ValueError as err:
        st.error(str(err))
        st.session_state.pop("result", None)

if "result" not in st.session_state:
    st.info("Choose your state and district on the left, check the soil values, then press **Recommend crops**.")
    st.stop()

inputs, table = st.session_state["result"]
st.subheader(f"{inputs['district']}, {inputs['state']} · sowing in {calendar.month_name[int(inputs['sow'][5:7])]} ({inputs['season']})")
if inputs["season_share"] < recommend.QUIET_SEASON:
    st.warning(f"Farmers in {inputs['district']} sow little in the {inputs['season']} season "
               f"({inputs['season_share']:.0%} of the area of their main season), so these picks rest on other districts.")
c = st.columns(4)
c[0].metric("Temperature", f"{inputs['temperature']:.0f} °C")
c[1].metric("Rain, whole year", f"{inputs['rainfall']:.0f} mm")
c[2].metric("Rain, kharif (Jun–Sep)", f"{inputs['rain_kharif']:.0f} mm")
c[3].metric("Rain, rabi (Nov–Feb)", f"{inputs['rain_rabi']:.0f} mm")
st.caption("Rain is the average per month. NASA POWER, 2015–2024 averages at your district's markets. "
           + st.session_state.get("soil_note", ""))

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
st.caption(" ".join([f"**Suitability** is the share of {inputs['season']} farmland that districts with similar soil and "
                     "weather put under the crop (district crop survey data). **Net return** = yield × forecast price − cultivation cost."] + notes))

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
