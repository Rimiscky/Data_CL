"""
DAG Airflow — Pipeline orchestré multi-sources et multi-régions.

Orchestration : Ingestion multi-sources → ETL → Chargement DB → Dashboard → Gouvernance
Sources : ODRE (énergie), RTE (génération), Open-Meteo. Planification : tous les jours à 6h UTC
"""
import sys
from datetime import timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.dates import days_ago

# Remonte à la racine du projet pour accéder à config.settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from config.settings import REGIONS
except ImportError:
    REGIONS = ["idf", "provence", "bretagne", "nouvelle-aquitaine"]


ALERT_EMAIL = "rimiscky@gmail.com"
AIRFLOW_ROOT = "/opt/airflow"


# ──────────────────────────────────────────────────────────────
# Callables Python pour PythonOperator
# Les imports sont à l'intérieur des fonctions : chaque worker
# Airflow charge ses propres modules sans conflit de chemin.
# ──────────────────────────────────────────────────────────────

def _ingest_odre_region(region: str) -> None:
    import sys
    sys.path.insert(0, AIRFLOW_ROOT)
    from src.ingestion.odre_client import ODREClient
    from src.ingestion.data_saver import DataSaver
    from config.settings import RAW_API_DIR

    saver = DataSaver(RAW_API_DIR)
    with ODREClient.for_region(region) as client:
        data = client.fetch_all_consumption(max_records=500)
    saver.save_json(data, prefix=f"odre_consommation_{region}")
    saver.save_csv(data, prefix=f"odre_consommation_{region}")
    print(f"Ingestion {region.upper()}: {len(data)} enregistrements")


def _ingest_meteo() -> None:
    import sys
    sys.path.insert(0, AIRFLOW_ROOT)
    from scripts.ingest import ingest_meteo
    ingest_meteo()


def _ingest_rte() -> None:
    import sys
    sys.path.insert(0, AIRFLOW_ROOT)
    from scripts.ingest import ingest_rte_realtime
    ingest_rte_realtime(max_records=500)


# ──────────────────────────────────────────────────────────────
# DAG
# ──────────────────────────────────────────────────────────────

default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email": [ALERT_EMAIL],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": days_ago(1),
}


with DAG(
    dag_id="energy_pipeline_multi_sources",
    default_args=default_args,
    description="Pipeline énergie × météo multi-régions (ODRE, RTE, Météo)",
    schedule_interval="0 6 * * *",
    catchup=False,
    tags=["energy", "meteo", "rte", "multi-region", "etl"],
    params={"regions": REGIONS},
) as dag:

    # ──────────────────────────────────────────────────────
    # Ingestion : Énergie (API ODRE) - Multi-régions
    # ──────────────────────────────────────────────────────
    with TaskGroup("ingest_energy_group") as ingest_energy_group:
        for region in REGIONS:
            PythonOperator(
                task_id=f"ingest_odre_{region}",
                python_callable=_ingest_odre_region,
                op_kwargs={"region": region},
            )

    # ──────────────────────────────────────────────────────
    # Ingestion : Météo Open-Meteo - Multi-régions
    # ──────────────────────────────────────────────────────
    ingest_meteo = PythonOperator(
        task_id="ingest_meteo_open_meteo",
        python_callable=_ingest_meteo,
    )

    # ──────────────────────────────────────────────────────
    # Ingestion : RTE - Génération d'électricité
    # ──────────────────────────────────────────────────────
    ingest_rte = PythonOperator(
        task_id="ingest_rte_generation",
        python_callable=_ingest_rte,
    )

    # ──────────────────────────────────────────────────────
    # ETL (Extract → Transform → Load)
    # ──────────────────────────────────────────────────────
    run_etl = BashOperator(
        task_id="run_etl",
        bash_command=f"cd {AIRFLOW_ROOT} && python scripts/run_etl.py",
    )

    # ──────────────────────────────────────────────────────
    # Chargement en base PostgreSQL
    # ──────────────────────────────────────────────────────
    load_to_postgres = BashOperator(
        task_id="load_to_postgres",
        bash_command=f"cd {AIRFLOW_ROOT} && python scripts/load_to_db.py",
    )

    # ──────────────────────────────────────────────────────
    # Dashboard (énergie + croisé)
    # ──────────────────────────────────────────────────────
    generate_dashboard = BashOperator(
        task_id="generate_dashboard",
        bash_command=f"cd {AIRFLOW_ROOT} && python scripts/run_dashboard.py",
    )

    # ──────────────────────────────────────────────────────
    # Gouvernance (qualité)
    # ──────────────────────────────────────────────────────
    run_governance = BashOperator(
        task_id="run_governance",
        bash_command=f"cd {AIRFLOW_ROOT} && python scripts/run_governance.py",
    )

    # ──────────────────────────────────────────────────────
    # Publication des dashboards vers le serveur HTTP
    # ──────────────────────────────────────────────────────
    publish_dashboards = BashOperator(
        task_id="publish_dashboards",
        bash_command=(
            "mkdir -p /home/ubuntu/www/dashboards && "
            f"cp -r {AIRFLOW_ROOT}/output/dashboards/* /home/ubuntu/www/dashboards/"
        ),
    )

    # ──────────────────────────────────────────────────────
    # Nettoyage des fichiers anciens (rétention)
    # ──────────────────────────────────────────────────────
    cleanup_old_files = BashOperator(
        task_id="cleanup_old_files",
        bash_command=(
            f"find {AIRFLOW_ROOT}/data/raw -type f -mtime +7 -delete && "
            f"find {AIRFLOW_ROOT}/data/warehouse -type f -mtime +30 -delete && "
            f"find {AIRFLOW_ROOT}/logs -type f -mtime +14 -delete && "
            "echo 'Nettoyage terminé'"
        ),
    )

    # ──────────────────────────────────────────────────────
    # Dépendances : Orchestration du pipeline
    # ──────────────────────────────────────────────────────
    # 1. Ingestions en parallèle (ODRE multi-région, Météo, RTE)
    # 2. ETL (attend tous les ingests)
    # 3. Chargement DB
    # 4. Dashboard + Gouvernance (en parallèle)
    # 5. Publication des dashboards (après génération)
    # 6. Nettoyage (après tout le reste)
    [ingest_energy_group, ingest_meteo, ingest_rte] >> run_etl
    run_etl >> load_to_postgres
    load_to_postgres >> [generate_dashboard, run_governance]
    generate_dashboard >> publish_dashboards
    [publish_dashboards, run_governance] >> cleanup_old_files
