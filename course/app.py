"""Launch with streamlit run course/app.py from the project root."""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
from predict import FareModel

RESULTS = ROOT / "course" / "results"
st.set_page_config(page_title="FlightSense AI · INT395", layout="wide")


@st.cache_resource
def load_model():
    return FareModel(root=str(ROOT / "dist"))


def choose_number(label, low, high, default, step):
    if low == high:
        st.caption(f"{label} · {low:g} (only value observed)")
        return low
    return st.number_input(label, min_value=low, max_value=high, value=default, step=step)


def estimate(model):
    remaining = model.options
    selections = [
        ("source_city", "From"), ("destination_city", "To"), ("class", "Cabin"),
        ("airline", "Airline"), ("stops", "Stops"), ("departure_time", "Departure"),
        ("arrival_time", "Arrival"),
    ]
    cols = st.columns(2)
    for i, (field, title) in enumerate(selections):
        with cols[i % 2]:
            selected = st.selectbox(title, sorted({r[field] for r in remaining}),
                                    format_func=lambda s: str(s).replace("_", " "))
        remaining = [r for r in remaining if r[field] == selected]
    option = remaining[0]
    with cols[1]:
        duration = choose_number("Duration in hours", float(option["durationMin"]), float(option["durationMax"]),
                                 float(option["durationMedian"]), .01)
    low, high = int(option["daysMin"]), int(option["daysMax"])
    days = choose_number("Days before departure", low, high, min(high, max(low, 14)), 1)
    result = model.predict({**option, "duration": duration, "days_left": days})
    st.metric("Estimated historical airfare", f"₹{result['price']:,.0f}")
    st.caption(f"Calibrated fare range ₹{result['low']:,.0f} – ₹{result['high']:,.0f}. "
               "Actual fares depend on inventory, demand and the travel date.")


def evidence():
    results = json.loads((RESULTS / "practicals.json").read_text())
    st.header("Which economy quotes are expensive?")
    score = results["classification"]
    st.write(f"An expensive ticket costs more than ₹{score['threshold_inr']:,.0f}, the 75th percentile "
             f"in the training partition. Testing used {score['test_quotes']:,} quotes whose flight numbers "
             "were excluded from training.")
    metrics = st.columns(3)
    for col, key, label in zip(metrics, ["precision", "recall", "roc_auc"], ["Precision", "Recall", "ROC AUC"]):
        col.metric(label, f"{score[key]:.3f}")
    confusion = pd.DataFrame(score["confusion_matrix"], index=["Actual standard", "Actual expensive"],
                             columns=["Predicted standard", "Predicted expensive"])
    st.dataframe(confusion)
    st.write("Importance is the average reduction in test-sample ROC AUC after shuffling a feature.")
    st.bar_chart(pd.Series(score["permutation_auc_drop"], name="ROC AUC reduction").sort_values())
    st.header("How fares vary with booking lead time")
    st.image(str(RESULTS / "lead_time_profile.png"))
    st.header("Forecasting median economy fare by departure date")
    st.image(str(RESULTS / "departure_forecast.png"))
    ts = results["departure_date_series"]
    st.dataframe(pd.Series(ts["mae_inr"], name="Holdout MAE (INR)").round(2))
    st.caption("42 departure dates for training and seven for evaluation. The route mix changes daily. "
               "This experiment measures a market-level daily statistic, separate from individual fares.")


st.title("FlightSense AI")
st.caption("INT395 · Supervised Learning · Historical Indian domestic fares from 2022")
predict_tab, practical_tab = st.tabs(["Fare estimate", "Course practicals"])
with predict_tab:
    estimate(load_model())
with practical_tab:
    evidence()
