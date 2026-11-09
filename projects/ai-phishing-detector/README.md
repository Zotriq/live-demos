# AI Phishing Detector 🛡️

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)

A machine learning app that detects phishing in two places: **suspicious URLs** and **scam emails**.
Paste a link or an email and it labels it as **Safe** or **Phishing** instantly.

## Features

- **URL analyzer:** measures 10 warning signs straight from the link (raw IP, `@` tricks, look-alike hyphens, stacked subdomains, shorteners, missing HTTPS…) and classifies it with a Random Forest (90.5% accuracy on held-out data), plus a rule layer for red flags that are dangerous on their own
- **Explains every verdict:** Safe / Suspicious / Phishing, with the reasons in plain English
- **Email classifier:** turns email text into word-count vectors and classifies it with a Naive Bayes model, and shows the scam-typical words it found
- **Two trained models** saved as `.pkl` files for instant predictions, with no retraining needed
- **Simple web UI** built with Streamlit
- **Full training notebook** (`code/system.ipynb`) covering data cleaning, exploration, training and evaluation

## How it works

```
URL   ──► 10 link features ──► Random Forest + red-flag rules ──┐
                                                          ├──► Safe / Phishing
Email ──► word counts ──► Naive Bayes ─────────────────────────┘
```

## Getting started

```bash
git clone https://github.com/Zotriq/ai-phishing-detector.git
cd ai-phishing-detector
pip install streamlit scikit-learn joblib numpy pandas

cd code
streamlit run app.py
```

Run the app from inside `code/`, because that's where the trained model files are.

## Project structure

```
code/
  app.py                  Streamlit app
  detector.py             Detection logic shared by the app and the live demo
  url_features.py         The 10 URL features and their plain-English explanations
  train_url_model.py      Retrains url_model.pkl (python train_url_model.py)
  system.ipynb            Data analysis and model training
  url_model.pkl           URL classifier
  email_model.pkl         Email classifier
  email_vectorizer.pkl    TF-IDF vectorizer
datasets/
  dataseturl.csv          Labeled URL dataset
  emailscam.csv           Labeled email dataset
```

## Tech stack

Python · scikit-learn · pandas · NumPy · Streamlit · joblib
