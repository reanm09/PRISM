import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.rag.ingestion.ingest import run_ingestion

if __name__ == "__main__":
    run_ingestion()
