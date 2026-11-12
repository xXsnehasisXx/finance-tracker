"""Run the API:  python backend/run.py   (or: uvicorn app.main:app --app-dir backend --port 8000)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=False)
