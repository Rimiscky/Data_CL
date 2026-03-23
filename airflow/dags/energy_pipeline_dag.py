"""
DAG Airflow — Pipeline complet Énergie × Météo IDF.

Orchestration : Ingestion → ETL → Chargement DB → Dashboard → Gouvernance
Planification : tous les jours à 6h UTC
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago


default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": days_ago(1),
}

dag = DAG(
    dag_id="energy_meteo_pipeline",
    default_args=default_args,
    description="Pipeline consommation énergétique × météo Île-de-France",
    schedule_interval="0 6 * * *",  # Tous les jours à 6h UTC
    catchup=False,
    tags=["energy", "meteo", "idf", "etl"],
)


# ── Task 1 : Ingestion données énergie (API ODRE) ───────
ingest_energy = BashOperator(
    task_id="ingest_energy",
    bash_command="cd /opt/airflow && python -c \"\n"
    "import sys; sys.path.insert(0, '.')\n"
    "from src.ingestion import ODREClient, DataSaver\n"
    "from config.settings import RAW_API_DIR, ODRE_DATASET, ODRE_REGION\n"
    "saver = DataSaver(RAW_API_DIR)\n"
    "with ODREClient() as client:\n"
    "    data = client.fetch_all_consumption(dataset=ODRE_DATASET, region=ODRE_REGION, max_records=500)\n"
    "    saver.save_json(data, prefix='odre_consommation_idf')\n"
    "    saver.save_csv(data, prefix='odre_consommation_idf')\n"
    "print(f'Ingestion énergie: {len(data)} enregistrements')\n"
    "\"",
    dag=dag,
)


# ── Task 2 : Ingestion données météo (Open-Meteo) ───────
ingest_meteo = BashOperator(
    task_id="ingest_meteo",
    bash_command="cd /opt/airflow && python -c \"\n"
    "import sys; sys.path.insert(0, '.')\n"
    "from datetime import date, timedelta\n"
    "from src.ingestion import MeteoClient, DataSaver\n"
    "from config.settings import RAW_METEO_DIR\n"
    "saver = DataSaver(RAW_METEO_DIR)\n"
    "end = date.today() - timedelta(days=1)\n"
    "start = end - timedelta(days=30)\n"
    "with MeteoClient() as client:\n"
    "    df = client.fetch_weather_df(start, end)\n"
    "    saver.save_dataframe(df, prefix='meteo_idf', fmt='csv')\n"
    "print(f'Ingestion météo: {len(df)} enregistrements')\n"
    "\"",
    dag=dag,
)


# ── Task 3 : ETL (Extract → Transform → Load) ──────────
run_etl = BashOperator(
    task_id="run_etl",
    bash_command="cd /opt/airflow && python scripts/run_etl.py",
    dag=dag,
)


# ── Task 4 : Chargement en base PostgreSQL ──────────────
load_to_postgres = BashOperator(
    task_id="load_to_postgres",
    bash_command="cd /opt/airflow && python scripts/load_to_db.py",
    dag=dag,
)


# ── Task 5 : Dashboard (énergie + croisé) ───────────────
generate_dashboard = BashOperator(
    task_id="generate_dashboard",
    bash_command="cd /opt/airflow && python scripts/run_dashboard.py",
    dag=dag,
)


# ── Task 6 : Gouvernance (qualité + lignage) ────────────
run_governance = BashOperator(
    task_id="run_governance",
    bash_command="cd /opt/airflow && python -c \"\n"
    "import sys; sys.path.insert(0, '.')\n"
    "import pandas as pd\n"
    "from src.governance import DataQualityChecker\n"
    "from config.settings import WAREHOUSE_DIR, QUALITY_DIR\n"
    "df = pd.read_csv(WAREHOUSE_DIR / 'energy_consumption_idf' / 'latest.csv')\n"
    "checker = DataQualityChecker('energy_consumption_idf')\n"
    "report = checker.run_all_checks(df)\n"
    "checker.save_report(report, QUALITY_DIR)\n"
    "print(f'Qualite: {report.score:.0f}%')\n"
    "\"",
    dag=dag,
)


# ── Dépendances ─────────────────────────────────────────
# Ingestion en parallèle, puis ETL, puis DB + Dashboard + Governance
[ingest_energy, ingest_meteo] >> run_etl >> load_to_postgres
load_to_postgres >> [generate_dashboard, run_governance]
