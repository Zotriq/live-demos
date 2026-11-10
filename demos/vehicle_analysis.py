import importlib.util
import json
import os

import pandas as pd
import streamlit as st

from lib import llm, ui

repo = ui.project_path("AI-vehicle-analysis")
if llm.groq_key():
    os.environ.setdefault("GROQ_API_KEY", llm.groq_key())  # read by ChatGroq
# Load the project's main.py under its own name (another demo also has a main.py).
_spec = importlib.util.spec_from_file_location("vehicle_analysis_main", repo / "main.py")
vehicle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vehicle)

FLEET = json.loads(vehicle.SAMPLE_DATA.read_text())
QUESTIONS = {
    "34": "Can you share a deep analysis for car id 34?",
    "55": "Vehicle 55 keeps overheating. What's going on and what should we fix?",
    "72": "Is vehicle 72 due for anything soon?",
}

ui.header(
    "AI Vehicle Analysis",
    "Ask about any vehicle in plain English. The AI pulls the vehicle ID out of the question, fetches its work-order "
    "history, normalises it, and writes a service-advisor report: what was done, recurring problems, and what to do next.",
    "AI-vehicle-analysis",
    flow=["Question", "LLM (JSON mode) extracts vehicle ID", "Fetch work orders", "Normalise records", "Maintenance report"],
    note="The real deployment reads a client's fleet API; this demo uses a sample fleet in the same data format.",
)

cols = st.columns(len(FLEET))
for col, (vid, rec) in zip(cols, FLEET.items()):
    col.metric(f"Vehicle {vid}", rec["vehicle_name"].split(" (")[0], f"{len(rec['workorders']) // 2} work orders", delta_color="off")

pick = st.pills("Example questions", list(QUESTIONS.values()), default=QUESTIONS["55"])
query = st.text_input("Your question (mention a vehicle ID: 34, 55 or 72)", value=pick or "")
if st.button("Analyse", type="primary") and query.strip():
    try:
        with st.spinner("Extracting the vehicle, fetching its history and writing the report…"):
            st.session_state.vehicle_result = vehicle.analyze(query)
    except (ValueError, vehicle.VehicleNotFound) as exc:
        st.warning(str(exc))
    except Exception as exc:
        llm.friendly_error(exc)

res = st.session_state.get("vehicle_result")
if res:
    vid = str(res["vehicle_id"])
    st.caption(f"Vehicle extracted from your question: **{vid}** · {FLEET.get(vid, {}).get('vehicle_name', '')}")
    left, right = st.columns([3, 2])
    with left:
        st.markdown(res["analysis"])
    with right:
        st.markdown("**Work orders the AI read** (normalised from the raw API format)")
        rows = [{"Date": r["repair_date"], "Odometer (km)": r["odometer_km"], "Cost": r["total_cost"],
                 "Work done": "; ".join(t["service_task"] for t in r["services_performed"])} for r in res["parsed_vehicle_data"]]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
ui.footer()
