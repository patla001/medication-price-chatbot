
# uv run pip install -r requirements.txt
sudo lsof -ti:8000 | xargs sudo kill -9
source .venv/bin/activate
python -m uvicorn main:app --reload --port 8000