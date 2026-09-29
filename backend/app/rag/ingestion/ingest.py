import json
import logging
import sys

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("PRISM.RAG.Ingest")


def run_ingestion():
    from app.rag.ingestion.pipeline import IngestionPipeline

    logger.info("Initializing PRISM Mock Knowledge Ingestion Pipeline...")
    pipeline = IngestionPipeline()
    result = pipeline.run()

    print("\n" + "=" * 50)
    print(" PRISM KNOWLEDGE INGESTION SUMMARY")
    print("=" * 50)
    print(f"Status:          {result['status']}")
    print(f"Documents:       {result.get('document_count')}")
    print(f"Chunks:          {result.get('chunk_count')}")
    print(f"Vector Dim:      {result.get('dimension')}")
    print(f"Embedding Time:  {result.get('embedding_time_ms')} ms")
    print(f"Total Time:      {result.get('total_time_ms')} ms")
    print("=" * 50)
    print("Ingested Records:")
    for rec in result.get("records", []):
        print(f" - [{rec['title']}] ({rec['category']}) -> ID: {rec['chunk_id']}")
    print("=" * 50 + "\n")
    return result


if __name__ == "__main__":
    try:
        run_ingestion()
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        sys.exit(1)
