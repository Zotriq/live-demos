"""Phishing detection used by both the Streamlit app and the live demo."""

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import pandas as pd

from url_features import FEATURES, HIGH_RISK, explain, extract

HERE = Path(__file__).parent
_url = joblib.load(HERE / "url_model.pkl")
_email_model = joblib.load(HERE / "email_model.pkl")
_email_vectorizer = joblib.load(HERE / "email_vectorizer.pkl")


@dataclass
class Result:
    verdict: str            # "Safe" | "Suspicious" | "Phishing"
    score: float            # model probability of phishing, 0-1
    reasons: list[str] = field(default_factory=list)


def check_url(url: str) -> Result:
    feats = extract(url)
    score = float(_url["model"].predict_proba(pd.DataFrame([feats])[FEATURES])[0][1])
    reasons = explain(feats)
    high_risk = any(feats[k] < 1 for k in HIGH_RISK)
    if score >= 0.5:
        verdict = "Phishing"
    elif high_risk or score >= 0.3:
        verdict = "Suspicious"
    else:
        verdict = "Safe"
    return Result(verdict, score, reasons)


def check_email(text: str) -> Result:
    vec = _email_vectorizer.transform([text])
    score = float(_email_model.predict_proba(vec)[0][1])
    verdict = "Phishing" if score >= 0.5 else ("Suspicious" if score >= 0.2 else "Safe")
    top = []
    if verdict != "Safe":
        vocab = _email_vectorizer.get_feature_names_out()
        log_ratio = _email_model.feature_log_prob_[1] - _email_model.feature_log_prob_[0]
        words = [(log_ratio[i], vocab[i]) for i in vec.nonzero()[1]]
        top = [f"contains scam-typical word '{w}'" for r, w in sorted(words, reverse=True)[:5] if r > 1]
    return Result(verdict, score, top)
