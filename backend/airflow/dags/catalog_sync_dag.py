"""
Airflow DAG: keep the assistant's semantic catalog index in sync with MySQL.

Daily:
  1. wait for MySQL,
  2. sync the index (a no-op when the catalog hasn't changed -- see
     app/catalog/index.py),
  3. verify: indexed vectors == rows marked 'complete' or 'partial'.

Set AGENTIC_SALESMAN_BACKEND_DIR to the backend/ directory if this file is
deployed outside the repository.
"""
import os
import sys
from datetime import datetime, timedelta

from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.sensors.sql import SqlSensor
from airflow.providers.mysql.hooks.mysql import MySqlHook

from airflow import DAG

MYSQL_CONN_ID = "retail_shop_mysql"

default_args = {
    "owner": "agentic-salesman",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}


def _backend_on_path() -> None:
    backend_dir = os.environ.get(
        "AGENTIC_SALESMAN_BACKEND_DIR", os.path.join(os.path.dirname(__file__), "..", "..")
    )
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


def sync_index(**_):
    _backend_on_path()
    from app.catalog.index import CatalogIndex

    report = CatalogIndex().sync()
    print(f"rebuilt={report.rebuilt} indexed={report.indexed} "
          f"partial={len(report.partial)} rejected={len(report.rejected)}")
    return {"indexed": report.indexed, "rebuilt": report.rebuilt}


def verify_index(**_):
    _backend_on_path()
    from app.catalog.index import CatalogIndex

    vectors = len(CatalogIndex().store.get(include=[]).get("ids", []))
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    try:
        expected = hook.get_first(
            "SELECT COUNT(*) FROM products WHERE ingestion_status IN ('complete', 'partial')"
        )[0]
    except Exception as exc:  # column missing: fall back to all rows
        print(f"ingestion_status unavailable ({exc}); comparing against all rows")
        expected = hook.get_first("SELECT COUNT(*) FROM products")[0]

    print(f"vectors={vectors} expected={expected}")
    if vectors != expected:
        raise ValueError(f"Index drift: {vectors} vectors vs {expected} indexable rows")
    return vectors


with DAG(
    dag_id="catalog_index_sync",
    description="Keep the assistant's catalog index in sync with MySQL",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["agentic-salesman", "catalog"],
) as dag:
    wait_for_mysql = SqlSensor(
        task_id="wait_for_mysql", conn_id=MYSQL_CONN_ID, sql="SELECT 1",
        mode="reschedule", poke_interval=30, timeout=300,
    )
    sync = PythonOperator(task_id="sync_index", python_callable=sync_index)
    verify = PythonOperator(task_id="verify_index", python_callable=verify_index)

    wait_for_mysql >> sync >> verify
