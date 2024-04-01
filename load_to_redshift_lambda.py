import os
import psycopg2
from dotenv import load_dotenv
import boto3
import logging

load_dotenv('/Users/david/Library/CloudStorage/OneDrive-Personal/GitHub/cashback-data-pipeline', verbose=True,
            override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redshift_endpoint = os.getenv('REDSHIFT_ENDPOINT')
redshift_dbname = os.getenv('REDSHIFT_DBNAME')
redshift_user = os.getenv('REDSHIFT_USER')
redshift_pass = os.getenv('REDSHIFT_PASS')
redshift_port = os.getenv('REDSHIFT_PORT')
iam_role = os.getenv('IAM_ROLE')
glue_database = os.getenv('GLUE_DATABASE')
glue_table_name = os.getenv('GLUE_TABLE_NAME')
redshift_target_table = 'cashback'
region_name = 'eu-west-1'

# Mapping from Glue data types to Redshift data types
DATA_TYPE_MAPPING = {
    'int': 'INTEGER',
    'bigint': 'BIGINT',
    'string': 'VARCHAR(256)',
    'double': 'DOUBLE PRECISION',
    'boolean': 'BOOLEAN',
    'timestamp': 'TIMESTAMP'
}


def glue_schema_to_redshift_ddl(glue_client, glue_database, glue_table_name):
    table = glue_client.get_table(DatabaseName=glue_database, Name=glue_table_name)
    columns = table['Table']['StorageDescriptor']['Columns']

    column_ddl_parts = []
    for col in columns:
        col_name = col['Name']
        glue_type = col['Type']
        redshift_type = DATA_TYPE_MAPPING.get(glue_type, 'VARCHAR(256)')
        column_ddl_parts.append(f"{col_name} {redshift_type}")

    return ', '.join(column_ddl_parts)


def create_spectrum_schema(cursor, iam_role, glue_database, glue_table_name):
    create_schema_query = f"""
    CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum_schema
    FROM DATA CATALOG DATABASE '{glue_database}'
    IAM_ROLE '{iam_role}'
    REGION 'eu-west-1';
    """

    cursor.execute(create_schema_query)
    logger.info("External schema 'spectrum_schema' created")


def create_redshift_table_from_spectrum(cursor, redshift_table_name: str, column_ddl: str):
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS public.{redshift_table_name} (
        {column_ddl}
    );
    """
    cursor.execute(create_table_sql)
    logger.info(f"Redshift table '{redshift_table_name}' created")


# Initialize a Glue client
glue_client = boto3.client('glue', region_name=region_name)

# Retrieve the DDL from Glue
column_ddl = glue_schema_to_redshift_ddl(glue_client, glue_database, glue_table_name)


def copy_data_to_redshift(cursor, redshift_table, glue_table_name):
    copy_query = f"""
    INSERT INTO {redshift_table}
    SELECT * FROM spectrum_schema.{glue_table_name} s
    WHERE NOT EXISTS (
        SELECT 1 FROM {redshift_table} r WHERE r.id = s.id
    );
    """
    cursor.execute(copy_query)
    rows_inserted = cursor.rowcount
    logger.info(f"Inserted {rows_inserted} row(s) into Redshift table")


conn = None
try:
    conn = psycopg2.connect(
        dbname=redshift_dbname,
        user=redshift_user,
        password=redshift_pass,
        host=redshift_endpoint,
        port=redshift_port
    )
    with conn.cursor() as cursor:
        create_spectrum_schema(cursor, iam_role, glue_database, glue_table_name)
        create_redshift_table_from_spectrum(cursor, redshift_target_table, column_ddl)
        copy_data_to_redshift(cursor, redshift_target_table, glue_table_name)
    conn.commit()
except Exception as error:
    if conn:
        conn.rollback()
    print(f"An error occurred: {error}")
finally:
    if conn and not conn.closed:
        conn.close()
