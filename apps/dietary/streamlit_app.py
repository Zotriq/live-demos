import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib import ui  # noqa: E402

BACKEND = ui.project_path("dietary-estimation-system") / "backend"
sys.path.insert(0, str(BACKEND))
from food_pipeline import FoodPipeline  # noqa: E402

SAMPLES = {"Nachos platter": BACKEND / "test-images" / "1.jpg", "Spring rolls, fries & wings": BACKEND / "test-images" / "test_image.jpg"}

st.set_page_config(page_title="Dietary Estimation · Zohaib Tariq", page_icon="🍽️", layout="wide")


@st.cache_resource(show_spinner="Loading the YOLOv8 segmentation model and the weight regressor…")
def pipeline() -> FoodPipeline:
    return FoodPipeline(str(BACKEND / "food_pipeline_model" / "food_pipeline_model"))


ui.header(
    "Dietary Estimation System",
    "Take a photo of a meal and get calories, protein and fat for each food on the plate. A YOLOv8 segmentation "
    "model finds each food and its outline, a trained regressor estimates the portion weight from the outline size "
    "and food density, and a nutrition table turns weight into nutrients.",
    "dietary-estimation-system",
    flow=["Meal photo", "YOLOv8 segments each food (43 classes)", "Regressor predicts weight", "Nutrition lookup per 100 g", "Totals"],
    note="Portion weights are estimates from a single photo with no reference object, so treat them as rough guides.",
)

left, right = st.columns([3, 2])
with left:
    pick = st.pills("Sample photos", list(SAMPLES), default=list(SAMPLES)[0])
    up = st.file_uploader("…or upload your own meal photo", type=["jpg", "jpeg", "png", "webp"])
    if up:
        img = cv2.imdecode(np.frombuffer(up.getvalue(), np.uint8), cv2.IMREAD_COLOR)
    elif pick:
        img = cv2.imread(str(SAMPLES[pick]))
    else:
        img = None
    if img is not None:
        scale = 1024 / max(img.shape[:2])
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale)
        with st.spinner("Detecting food…"):
            model = pipeline()
            result = model.process_image_array(img)
            annotated = model.cnn_model(img, verbose=False)[0].plot()
        st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), caption="What the model sees: each food's outline and label")
with right:
    if img is None:
        st.info("Pick a sample or upload a photo.")
    elif "individual_items" not in result:
        st.warning(result.get("message", "No food found."))
    else:
        total = result["grand_summation"]
        a, b = st.columns(2)
        a.metric("Calories", f"{total['total_calories_kcal']:.0f} kcal")
        b.metric("Estimated weight", f"{total['total_weight_g']:.0f} g")
        a.metric("Protein", f"{total['total_protein_g']:.0f} g")
        b.metric("Fat", f"{total['total_fat_g']:.0f} g")
        df = pd.DataFrame(result["individual_items"]).rename(columns={
            "food_name": "Food", "weight_g": "Weight (g)", "calories_kcal": "kcal", "protein_g": "Protein (g)", "fat_g": "Fat (g)"})
        st.dataframe(df, hide_index=True, width="stretch")
        st.caption("Recognises 43 dishes (Food-101 style classes), e.g. burgers, sushi, salads, pancakes, samosa, tacos.")
ui.footer()
