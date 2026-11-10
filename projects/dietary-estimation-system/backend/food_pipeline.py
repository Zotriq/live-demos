import numpy as np
import pandas as pd
import joblib
import cv2
from ultralytics import YOLO
from pathlib import Path

class FoodPipeline:
    def __init__(self, model_dir="./food_pipeline_model"):
        self.model_dir = Path(model_dir)
        
        # Load all 3 structural components into RAM instantly
        self.cnn_model = YOLO(self.model_dir / "yolov8_best.pt")
        self.regressor = joblib.load(self.model_dir / "weight_regressor.joblib")
        self.nutrition_df = pd.read_excel(self.model_dir / "nutrition_database.xlsx")
        
        # Your exact 43-class volume density configuration maps
        self.physical_properties = {
            "-":                      {"thickness": 1.0, "density": 1.00},
            "beef carpaccio":         {"thickness": 0.1, "density": 1.04},
            "beet salad":             {"thickness": 1.2, "density": 1.02},
            "breakfast burrito":      {"thickness": 3.5, "density": 0.95},
            "caesar salad":           {"thickness": 1.5, "density": 0.85},
            "caprese salad":          {"thickness": 0.8, "density": 1.01},
            "chicken quesadilla":     {"thickness": 0.5, "density": 1.10},
            "chicken wings":          {"thickness": 1.2, "density": 1.00},
            "clam chowder":           {"thickness": 4.0, "density": 1.08},
            "club sandwich":          {"thickness": 4.5, "density": 0.88},
            "deviled eggs":           {"thickness": 2.0, "density": 1.03},
            "dumplings":              {"thickness": 1.5, "density": 1.05},
            "eggplant":               {"thickness": 3.0, "density": 0.85},
            "falafel":                {"thickness": 1.8, "density": 0.98},
            "french fries":           {"thickness": 0.8, "density": 0.90},
            "french toast":           {"thickness": 1.5, "density": 0.92},
            "fried rice":             {"thickness": 2.0, "density": 0.95},
            "gnocchi":                {"thickness": 1.2, "density": 1.06},
            "greek salad":            {"thickness": 1.5, "density": 0.92},
            "guacamole":              {"thickness": 2.5, "density": 1.02},
            "gyoza":                  {"thickness": 1.2, "density": 1.04},
            "hamburger":              {"thickness": 1.5, "density": 1.10},
            "hot dog":                {"thickness": 1.1, "density": 1.02},
            "hummus":                 {"thickness": 2.0, "density": 1.05},
            "ice cream":              {"thickness": 3.0, "density": 0.75},
            "lentil soup":            {"thickness": 4.0, "density": 1.06},
            "macaroni and cheese":    {"thickness": 2.5, "density": 1.04},
            "molokhia":               {"thickness": 4.0, "density": 1.05},
            "mussels":                {"thickness": 2.2, "density": 1.05},
            "nachos":                 {"thickness": 2.5, "density": 0.80},
            "omelette":               {"thickness": 0.6, "density": 1.05},
            "onion rings":            {"thickness": 0.7, "density": 0.85},
            "pancakes":               {"thickness": 0.8, "density": 0.88},
            "samosa":                 {"thickness": 2.5, "density": 0.92},
            "sashimi":                {"thickness": 0.5, "density": 1.05},
            "spring rolls":           {"thickness": 1.5, "density": 0.95},
            "steak":                  {"thickness": 2.0, "density": 1.06},
            "stuffed grape leaves":   {"thickness": 1.2, "density": 1.02},
            "sushi":                  {"thickness": 1.8, "density": 1.05},
            "sweet potato":           {"thickness": 1.4, "density": 0.95},
            "tacos":                  {"thickness": 3.0, "density": 0.85},
            "waffles":                {"thickness": 1.2, "density": 0.85},
            "default":                {"thickness": 1.0, "density": 1.00}
        }

    def process_image_array(self, img_array):
        results = self.cnn_model(img_array, verbose=False)[0]
        
        if not results.masks:
            return {"message": "No food items detected on the plate."}
            
        meal_results = []
        total_cal, total_protein, total_fat, total_weight = 0.0, 0.0, 0.0, 0.0
        
        for box, mask in zip(results.boxes, results.masks):
            class_idx = int(box.cls[0])
            class_name = self.cnn_model.names[class_idx]
            lookup_key = class_name.lower().strip()
            
            # 1. Feature Calculations
            binary_mask = mask.data[0].cpu().numpy()
            v_mask = float(np.sum(binary_mask)) 
            
            xyxy = box.xyxy[0].cpu().numpy()
            box_w = xyxy[2] - xyxy[0]
            box_h = xyxy[3] - xyxy[1]
            v_cnn = float(box_w / box_h) if box_h > 0 else 1.0
            
            props = self.physical_properties.get(lookup_key, self.physical_properties["default"])
            thickness, density = props["thickness"], props["density"]
            
            # 2. Regressor Estimation
            features = np.array([[v_mask, v_cnn, thickness, density]])
            predicted_weight = max(15.0, float(self.regressor.predict(features)[0]))
            
            # 3. Spreadsheet Calorie Multiplication
            matched_food = self.nutrition_df[self.nutrition_df['name'].str.contains(class_name, case=False, na=False)]
            if not matched_food.empty:
                cal_100g = float(matched_food.iloc[0].get('calories', 140.0))
                prot_100g = float(matched_food.iloc[0].get('protein', 8.0))
                fat_100g = float(matched_food.iloc[0].get('fat', 5.0))
            else:
                cal_100g, prot_100g, fat_100g = 140.0, 8.0, 5.0
                
            scale = predicted_weight / 100.0
            item_cal, item_prot, item_fat = cal_100g * scale, prot_100g * scale, fat_100g * scale
            
            total_weight += predicted_weight
            total_cal += item_cal
            total_protein += item_prot
            total_fat += item_fat
            
            meal_results.append({
                "food_name": class_name,
                "weight_g": round(predicted_weight, 2),
                "calories_kcal": round(item_cal, 1),
                "protein_g": round(item_prot, 1),
                "fat_g": round(item_fat, 1)
            })
            
        return {
            "individual_items": meal_results,
            "grand_summation": {
                "total_weight_g": round(total_weight, 2),
                "total_calories_kcal": round(total_cal, 1),
                "total_protein_g": round(total_protein, 1),
                "total_fat_g": round(total_fat, 1)
            }
        }


if __name__ == "__main__":
    import os
    
    print("⏳ Initializing FoodPipeline and loading machine learning models...")
    # Initialize the pipeline class
    tester = FoodPipeline(model_dir="./food_pipeline_model/food_pipeline_model")
    print("🚀 Models successfully loaded into memory!")
    

    test_image_name = "./test-images/1.jpg"
    
    if not os.path.exists(test_image_name):
        print(f"\n❌ Error: Could not find '{test_image_name}' inside your backend folder.")
        print("👉 Please drop a sample food image into the 'backend' folder and rename it to 'test_food.jpg' so we can test it!")
    else:
        print(f"\n📸 Loading and decoding '{test_image_name}'...")
        # Read the local image file into an OpenCV matrix array
        img = cv2.imread(test_image_name)
        
        print("🧠 Processing image through segmentation, regression, and nutrition matrix...")
        # Fire your processing pipeline function
        report = tester.process_image_array(img)
        
        # Print out your clean structural output payload!
        import json
        print("\n🎉 PIPELINE TEST REPORT EXECUTED SUCCESSFULLY:\n")
        print(json.dumps(report, indent=2))