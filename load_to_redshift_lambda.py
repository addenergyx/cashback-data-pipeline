import os
import psycopg2
from dotenv import load_dotenv
import boto3
import logging

# load_dotenv('.env', verbose=True, override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

redshift_endpoint = os.getenv('REDSHIFT_ENDPOINT')
redshift_dbname = os.getenv('REDSHIFT_DBNAME')
redshift_user = os.getenv('REDSHIFT_USER')
redshift_pass = os.getenv('REDSHIFT_PASS')
redshift_port = os.getenv('REDSHIFT_PORT')
iam_role = os.getenv('IAM_ROLE')
glue_database = 'cashback_db'
glue_table_name = os.getenv('GLUE_TABLE_NAME')
redshift_target_table = 'cashback'
region_name = os.getenv('AWS_REGION', 'eu-west-1')

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

    # Columns used for partitioning the data are not included in ColumnList
    partition_keys = table['Table']['PartitionKeys']

    columns += partition_keys

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
    REGION '{region_name}';
    """

    cursor.execute(create_schema_query)
    logger.info("External schema 'spectrum_schema' created")

    # You might want to query the table to make sure everything is set up properly
    # query_table = f"SELECT * FROM spectrum_schema.{glue_table_name} LIMIT 10;"

    # query_table = f"select Column_name from Information_schema.columns where Table_name like '{glue_table_name}';"

    # cursor.execute(create_schema_query)
    # cursor.execute(query_table)

    # Fetch the result of the query if necessary
    # result = cursor.fetchall()
    # for row in result:
    #     print(row)


def create_redshift_table_from_spectrum(cursor, redshift_table_name: str, column_ddl: str):
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS public.{redshift_table_name} (
        {column_ddl}
    );
    """
    cursor.execute(create_table_sql)
    logger.info(f"Redshift table '{redshift_table_name}' created")


def copy_data_to_redshift(cursor, redshift_table, glue_table_name):
    copy_query = f"""
    INSERT INTO {redshift_table} 
    SELECT * 
    FROM spectrum_schema.{glue_table_name} s
    WHERE NOT EXISTS (
        SELECT 1 FROM {redshift_table} r WHERE r.reward_id = s.reward_id
    );
    """

    cursor.execute(copy_query)
    rows_inserted = cursor.rowcount
    logger.info(f"Inserted {rows_inserted} row(s) into Redshift table")


def lambda_handler(event, context):
    # Initialize a Glue client
    glue_client = boto3.client('glue', region_name=region_name)

    # Retrieve the DDL from Glue
    column_ddl = glue_schema_to_redshift_ddl(glue_client, glue_database, glue_table_name)

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
            conn.close()
        logger.error(f"An error occurred: {error}")
        return {
            'statusCode': 500,
            'body': 'Error copying data to Redshift!'
        }
    finally:
        if conn and not conn.closed:
            conn.close()

    logger.info("Data successfully copied to Redshift!")
    return {
        'statusCode': 200,
        'body': 'Data successfully copied to Redshift!'
    }

#
# if not os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
#     print(lambda_handler(None, None))
