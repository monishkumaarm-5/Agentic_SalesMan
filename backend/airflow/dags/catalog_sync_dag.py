"""
Airflow DAG: Catalog Vectorization Sync

Daily:
1. Wait for MySQL
2. Count products in MySQL (for logging/observability)
3. Sync embeddings to ChromaDB -- DATABASE/SQL_CONNECTOR.py's per-row
   completeness gate (TOOLS/product_schema.py) means not every MySQL row
   necessarily gets embedded; an incomplete one gets a best-effort LLM
   normalization pass and, failing that, is skipped and stamped
   ingestion_status='complete'/'incomplete' (needs
   sql/add_ingestion_status.sql run once against the database).
4. Verify products marked ingestion_status='complete' == ChromaDB vector
   count -- NOT total row count, since incomplete rows are deliberately
   excluded from the vector store, not a sync failure.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.mysql.sensors.mysql import MySqlSensor
from airflow.providers.mysql.hooks.mysql import MySqlHook


# --------------------------------------------------
# Configuration
# --------------------------------------------------

default_args = {
    "owner": "agentic-salesman",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": False,
}


MYSQL_CONN_ID = "retail_shop_mysql"


# --------------------------------------------------
# Task 1: Check MySQL Row Count
# --------------------------------------------------

def check_row_count(**context):
    """Total MySQL row count -- logged for observability only. The
    authoritative post-sync comparison in verify_collection() runs its
    own fresh "complete" count instead of trusting this XCom, since rows
    that only became complete during THIS run's sync (via the LLM
    normalization pass) wouldn't be reflected in a pre-sync count."""

    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)

    sql = "SELECT COUNT(*) FROM products"

    row_count = hook.get_first(sql)[0]

    print(f"MySQL product count (pre-sync, all rows): {row_count}")

    context["ti"].xcom_push(
        key="mysql_row_count",
        value=row_count
    )

    return row_count


# --------------------------------------------------
# Task 2: Sync Embeddings
# --------------------------------------------------

def sync_embeddings():

    import sys
    import os

    backend_dir = os.environ.get(
        "AGENTIC_SALESMAN_BACKEND_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

    sys.path.insert(0, backend_dir)

    from DATABASE.SQL_CONNECTOR import DB_CONNECTOR

    connector = DB_CONNECTOR()

    categories = connector.get_categories()

    print(f"Sync complete.")
    print(f"Categories: {categories}")

    return {
        "categories": categories,
        "count": len(categories)
    }


# --------------------------------------------------
# Task 3: Verify ChromaDB
# --------------------------------------------------

def verify_collection(**context):
    """Compares ChromaDB's vector count against MySQL rows stamped
    ingestion_status='complete' -- a fresh, POST-sync query, not the
    pre-sync total from check_row_count's XCom, so a row that only
    became complete during this run's LLM normalization pass counts
    correctly. On a database that hasn't run
    sql/add_ingestion_status.sql yet, every row's ingestion_status is
    still NULL; this falls back to the old total-row-count comparison
    in that case so the DAG doesn't start failing before the migration
    has been applied."""

    import sys
    import os

    backend_dir = os.environ.get(
        "AGENTIC_SALESMAN_BACKEND_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..")
    )

    sys.path.insert(0, backend_dir)

    from DATABASE.SQL_CONNECTOR import DB_CONNECTOR

    connector = DB_CONNECTOR()

    store = connector.vector_database()

    vector_count = len(
        store.get(include=[]).get("ids", [])
    )

    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)

    try:
        complete_count = hook.get_first(
            "SELECT COUNT(*) FROM products WHERE ingestion_status = 'complete'"
        )[0]
        total_count = hook.get_first(
            "SELECT COUNT(*) FROM products WHERE ingestion_status IS NULL"
        )[0]
        migration_applied = True
    except Exception as exc:
        print(f"ingestion_status column not available yet ({exc}); "
              f"falling back to total row count -- run sql/add_ingestion_status.sql")
        complete_count = context["ti"].xcom_pull(
            task_ids="check_row_count",
            key="mysql_row_count"
        )
        total_count = 0
        migration_applied = False

    print(f"MySQL 'complete' product count: {complete_count}")
    if migration_applied and total_count:
        print(f"({total_count} row(s) not yet evaluated by a sync -- ingestion_status is NULL)")
    print(f"ChromaDB count: {vector_count}")

    if complete_count != vector_count:

        raise ValueError(
            f"Collection drift detected: "
            f"{vector_count} vectors vs "
            f"{complete_count} MySQL rows marked complete."
        )

    print("Verification passed!")

    return vector_count


# --------------------------------------------------
# DAG
# --------------------------------------------------

with DAG(
    dag_id="catalog_vectorization_sync",

    description="Daily catalog embedding synchronization",

    default_args=default_args,

    schedule_interval="@daily",

    start_date=datetime(2025, 1, 1),

    catchup=False,

    tags=[
        "agentic-salesman",
        "catalog",
        "embeddings"
    ],

) as dag:

    # Wait until MySQL is available
    wait_for_mysql = MySqlSensor(
        task_id="wait_for_mysql",

        mysql_conn_id=MYSQL_CONN_ID,

        sql="SELECT 1",

        mode="reschedule",

        poke_interval=30,

        timeout=300,
    )


    # Get MySQL product count
    count_task = PythonOperator(
        task_id="check_row_count",

        python_callable=check_row_count,
    )


    # Synchronize embeddings
    sync_task = PythonOperator(
        task_id="sync_embeddings",

        python_callable=sync_embeddings,
    )


    # Verify synchronization
    verify_task = PythonOperator(
        task_id="verify_collection",

        python_callable=verify_collection,
    )


    # Task dependency
    wait_for_mysql >> count_task >> sync_task >> verify_task