import joblib
import pandas as pd

from functools import lru_cache
from src.paths import ROOT

@lru_cache(maxsize=1)
def load_model():
    return joblib.load(ROOT / "models" / "ridge_model.pkl")

def predict_stint_length(gp, compound, stint):
    compound = compound.upper()
    gp_stint = f"{gp}_S{stint}"
    compound_stint = f"{compound}_S{stint}"
    
    input_data = pd.DataFrame({
        'GP': [gp],
        'Compound': [compound],
        'Stint': [stint],
        'GP_Stint': [gp_stint],
        'Compound_Stint': [compound_stint]
    })
    
    predicted_length = load_model().predict(input_data)[0]
    return (predicted_length)