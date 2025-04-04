# main.py (in root)

import uvicorn
from app.main import app  # This assumes your FastAPI instance is named `app` in app/main.py

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
