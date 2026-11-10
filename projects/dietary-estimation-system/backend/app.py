import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from food_pipeline import FoodPipeline

app = FastAPI(title="Dietary Estimation API")

# Allow your local React instance to connect without hitting a CORS firewall
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pipeline once on server startup
pipeline = FoodPipeline(model_dir="./food_pipeline_model/food_pipeline_model")

@app.post("/predict")
async def analyze_meal_image(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img_array is None:
        return {"error": "Invalid file uploaded. Must be a clear image."}
        
    output_report = pipeline.process_image_array(img_array)
    return output_report