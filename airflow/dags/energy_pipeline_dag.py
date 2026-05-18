"""
DAG Airflow — Pipeline orchestré multi-sources et multi-régions.

Orchestration : Ingestion multi-sources → ETL → Chargement DB → Dashboard → Gouvernance
Sources : ODRE (énergie), RTE (génération), Open-Meteo, Météo-Concept ? Planification : tous les jours à 6h UTC
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.dates import days_ago

# Régions configurées (miroir de config/settings.py REGIONS)
REGIONS = ["idf", "provence", "bretagne", "nouvelle-aquitaine"]


def on_failure_callback(context):
    """Callback appelé en cas d'erreur."""
    task = context["task"]
    execution_date = context["execution_date"]
    print(f"Task '{task.task_id}' échouée à {execution_date}")


default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": days_ago(1),
    "on_failure_callback": on_failure_callback,
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
            BashOperator(
                task_id=f"ingest_odre_{region}",
                bash_command=(
                    "cd /opt/airflow && python -c \""
                    "import sys; sys.path.insert(0, '.'); "
                    "from src.ingestion.odre_client import ODREClient; "
                    "from src.ingestion.data_saver import DataSaver; "
                    "from config.settings import RAW_API_DIR; "
                    "saver = DataSaver(RAW_API_DIR); "
                    f"client = ODREClient.for_region('{region}'); "
                    "data = client.fetch_all_consumption(max_records=500); "
                    f"saver.save_json(data, prefix='odre_consommation_{region}'); "
                    f"saver.save_csv(data, prefix='odre_consommation_{region}'); "
                    "client.close(); "
                    f"print(f'Ingestion {region.upper()}: {{len(data)}} enregistrements')"
                    "\""
                ),
            )

    # ──────────────────────────────────────────────────────
    # Ingestion : Météo Open-Meteo - Multi-régions
    # ──────────────────────────────────────────────────────
    ingest_meteo = BashOperator(
        task_id="ingest_meteo_open_meteo",
        bash_command=(
            "cd /opt/airflow && python -c \""
            "import sys; sys.path.insert(0, '.'); "
            "from scripts.ingest import ingest_meteo; "
            "ingest_meteo()"
            "\""
        ),
    )

    # ──────────────────────────────────────────────────────
    # Ingestion : RTE - Génération d'électricité
    # ──────────────────────────────────────────────────────
    ingest_rte = BashOperator(
        task_id="ingest_rte_generation",
        bash_command=(
            "cd /opt/airflow && python -c \""
            "import sys; sys.path.insert(0, '.'); "
            "from scripts.ingest import ingest_rte_realtime; "
            "ingest_rte_realtime(max_records=500)"
            "\""
        ),
    )

    # ──────────────────────────────────────────────────────
    # ETL (Extract → Transform → Load)
    # ──────────────────────────────────────────────────────
    run_etl = BashOperator(
        task_id="run_etl",
        bash_command="cd /opt/airflow && python scripts/run_etl.py",
    )

    # ──────────────────────────────────────────────────────
    # Chargement en base PostgreSQL
    # ──────────────────────────────────────────────────────
    load_to_postgres = BashOperator(
        task_id="load_to_postgres",
        bash_command="cd /opt/airflow && python scripts/load_to_db.py",
    )

    # ──────────────────────────────────────────────────────
    # Dashboard (énergie + croisé)
    # ──────────────────────────────────────────────────────
    generate_dashboard = BashOperator(
        task_id="generate_dashboard",
        bash_command="cd /opt/airflow && python scripts/run_dashboard.py",
    )

    # ──────────────────────────────────────────────────────
    # Gouvernance (qualité)
    # ──────────────────────────────────────────────────────
    run_governance = BashOperator(
        task_id="run_governance",
        bash_command="cd /opt/airflow && python scripts/run_governance.py",
    )

    # ──────────────────────────────────────────────────────
    # Publication des dashboards vers le serveur HTTP
    # ──────────────────────────────────────────────────────
    publish_dashboards = BashOperator(
        task_id="publish_dashboards",
        bash_command=(
            "mkdir -p /home/ubuntu/www/dashboards && "
            "cp -r /opt/airflow/output/dashboards/* /home/ubuntu/www/dashboards/"
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
    [ingest_energy_group, ingest_meteo, ingest_rte] >> run_etl
    run_etl >> load_to_postgres
    load_to_postgres >> [generate_dashboard, run_governance]
    generate_dashboard >> publish_dashboards
