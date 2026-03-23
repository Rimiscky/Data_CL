"""
Script d'upload des données brutes vers MinIO (Data Lake S3-compatible).
Crée les buckets et uploade les fichiers du Data Lake local.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logger import get_logger  # noqa: E402
from config.settings import RAW_API_DIR, RAW_SCRAPING_DIR, RAW_METEO_DIR, WAREHOUSE_DIR  # noqa: E402

logger = get_logger("minio_upload")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password")

BUCKETS = {
    "raw-energy": RAW_API_DIR,
    "raw-scraping": RAW_SCRAPING_DIR,
    "raw-meteo": RAW_METEO_DIR,
    "warehouse": WAREHOUSE_DIR,
}


def get_minio_client():
    """Crée un client MinIO."""
    try:
        from minio import Minio
        return Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )
    except ImportError:
        logger.error("minio non installé — pip install minio")
        sys.exit(1)


def ensure_buckets(client):
    """Crée les buckets s'ils n'existent pas."""
    for bucket_name in BUCKETS:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info("Bucket créé: %s", bucket_name)
        else:
            logger.info("Bucket existe: %s", bucket_name)


def upload_directory(client, bucket_name, local_dir):
    """Uploade tous les fichiers d'un répertoire vers un bucket."""
    local_path = Path(local_dir)
    if not local_path.exists():
        logger.warning("Répertoire inexistant: %s", local_path)
        return 0

    count = 0
    for file_path in local_path.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith("."):
            object_name = str(file_path.relative_to(local_path))
            client.fput_object(bucket_name, object_name, str(file_path))
            count += 1

    logger.info("Bucket %s: %d fichiers uploadés", bucket_name, count)
    return count


def main():
    logger.info("=" * 50)
    logger.info("  Upload Data Lake → MinIO")
    logger.info("=" * 50)

    client = get_minio_client()
    ensure_buckets(client)

    total = 0
    for bucket_name, local_dir in BUCKETS.items():
        total += upload_directory(client, bucket_name, local_dir)

    logger.info("Total: %d fichiers uploadés vers MinIO", total)
    logger.info("Console MinIO: http://localhost:9001")
    logger.info("  → User: admin / Password: password")


if __name__ == "__main__":
    main()
