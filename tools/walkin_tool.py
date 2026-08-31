from langchain.tools import tool
import pandas as pd
import pickle
from datetime import timedelta
import os
import sys
import logging

logger = logging.getLogger("clinic.walkin")
logging.basicConfig(level=logging.INFO)

# The pickled model's pipeline references feature_engineering.FeatureEngineering
# by module name. Make sure it's importable regardless of whether that file
# lives at the project root or inside models/ — add both to the search path.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_models_dir = os.path.join(_project_root, "models")
for _p in (_project_root, _models_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load model 
_model = None
_model_error = None

def get_model():
    global _model, _model_error
    if _model is None and _model_error is None:
        model_path = os.path.join(_models_dir, "clinic_model.pkl")
        try:
            with open(model_path, 'rb') as f:
                _model = pickle.load(f)
        except Exception as e:
            _model_error = f"{type(e).__name__}: {e} (looked for model at: {model_path})"
    return _model

@tool
def check_walkin(date_time_str: str) -> str:
    """
    Checks busyness for a walk-in visit and suggests quieter times if busy.

    Args:
        date_time_str: Date/time in format 'YYYY-MM-DD H:MM AM/PM'

    Returns:
        Prediction and suggestions if busy.
    """
    logger.info("check_walkin called with date_time_str=%r", date_time_str)
    try:
        dt = pd.to_datetime(date_time_str)
        date_str = dt.strftime('%Y-%m-%d')

        # Validate clinic hours
        if not (8 <= dt.hour < 12 or 16 <= dt.hour < 22):
            result = " Error: Time is outside clinic hours (8-12 AM, 4-10 PM)."
            logger.info("check_walkin result: %s", result)
            return result

        # Get model
        model = get_model()
        if model is None:
            result = f" Error: ML model failed to load. {_model_error}"
            logger.error("check_walkin result: %s", result)
            return result

        # Prepare input
        df = pd.DataFrame([{
            'Date': date_str,
            'Visit Time': dt.strftime('%I:%M %p').lstrip('0')
        }])

        pred = model.predict(df)[0]

        # Classify (adjust thresholds to your data)
        if pred <= 2.0:
            status = "Free"
        elif pred <= 4.0:
            status = "Normal"
        else:
            status = "Busy"

        # Build response
        response = f"🔍 **Prediction:** {status}\n\n"

        if status == "Busy":
            response += " That time is expected to be busy.\n\n"
            response += " **Quieter times nearby:**\n"

            # Suggest quieter times
            suggestions = []
            for offset in [-60, -30, 30, 60]:
                new_dt = dt + timedelta(minutes=offset)
                new_hour = new_dt.hour
                if 8 <= new_hour < 12 or 16 <= new_hour < 22:
                    time_str = new_dt.strftime('%I:%M %p').lstrip('0')
                    suggestions.append(time_str)
                    if len(suggestions) >= 2:
                        break

            if suggestions:
                for t in suggestions:
                    response += f"• {t}\n"
            else:
                response += "No alternatives found in this session."

        elif status == "Normal":
            response += " It's a reasonable time to visit."
        else:  # Free
            response += " Great time to walk in – it's free!"

        logger.info("check_walkin result: %s", response.replace(chr(10), " | "))
        return response

    except Exception as e:
        result = f" Error checking walk-in: {type(e).__name__}: {str(e)}"
        logger.error("check_walkin exception: %s", result)
        return result