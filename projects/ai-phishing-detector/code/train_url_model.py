"""Retrain the URL model on the features url_features.py can compute from a link.

    python train_url_model.py
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from url_features import FEATURES

HERE = Path(__file__).parent
df = pd.read_csv(HERE.parent / "datasets" / "dataseturl.csv")
X = df[FEATURES]
y = (df["Result"] == -1).astype(int)  # 1 = phishing

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
model = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=42)
model.fit(X_train, y_train)

pred = model.predict(X_test)
print(f"accuracy: {accuracy_score(y_test, pred):.3f}")
print(classification_report(y_test, pred, target_names=["legitimate", "phishing"]))

joblib.dump({"model": model, "features": FEATURES}, HERE / "url_model.pkl")
print("saved url_model.pkl")
