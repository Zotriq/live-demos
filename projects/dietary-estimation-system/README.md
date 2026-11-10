# Dietary Estimation System 🍽️

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Segmentation-111F68?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-20232A?style=flat-square&logo=react&logoColor=61DAFB)

Upload a photo of a meal and get an estimate of its **calories, protein, fat and weight**, broken down for each
food item on the plate.

## How it works

```
Meal photo
  └─► YOLOv8 segmentation: finds each food item and its mask (43 food classes)
        └─► Features: mask area, box aspect ratio, typical thickness and density of that food
              └─► Regression model predicts the weight in grams
                    └─► Nutrition database lookup (per 100 g) × predicted weight
                          └─► Per-item and total calories, protein, fat
```

1. **Detection:** a custom-trained YOLOv8 segmentation model finds every food item on the plate.
2. **Portion size:** a scikit-learn regressor estimates each item's weight from its mask size and known physical properties.
3. **Nutrition:** values come from a nutrition spreadsheet and are scaled to the estimated portion.
4. **Dashboard:** a React front end shows each item plus a meal total.

## Getting started

### Backend

```bash
cd backend
pip install -r food_pipeline_model/requirements.txt
uvicorn app:app --reload        # http://127.0.0.1:8000
```

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict` | Upload an image (`file`) and get the per-item nutrition report |

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Project structure

```
backend/
  app.py                         FastAPI server
  food_pipeline.py               Detection → weight → nutrition pipeline
  Dietary_Estimation_system.ipynb  Training and experiments
  food_pipeline_model/           YOLOv8 weights, weight regressor, nutrition database
frontend/                        React + Vite dashboard
```

## Tech stack

YOLOv8 (Ultralytics) · OpenCV · scikit-learn · pandas · FastAPI · React · Vite
