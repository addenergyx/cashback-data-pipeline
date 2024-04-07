import json
import os
import logging
from api import PlutusApi
from common_shared_library import AWSConnector
from io import StringIO
import pandas as pd
import boto3

from dotenv import load_dotenv

load_dotenv('.env', verbose=True, override=True)

AUTH_SECRET = os.getenv('AUTH_SECRET')
USER_ID = os.getenv('USER_ID')
PASS_ID = os.getenv('PASS_ID')
CLIENT_ID = os.getenv('CLIENT_ID')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

def to_s3(df, bucket_name, file_name):
    # Connect to S3
    aws_connector = AWSConnector()
    s3 = aws_connector.connect_to_s3()

    # Convert DataFrame to CSV
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    # Upload the file
    bucket = s3.Bucket(bucket_name)
    bucket.put_object(Key=file_name, Body=csv_buffer.getvalue())

    logger.info(f"Successfully uploaded {file_name} to S3")


def fetch_data(api: PlutusApi):

    if os.getenv('USER_ID') and os.getenv('PASS_ID') and os.getenv('AUTH_SECRET') and os.getenv('CLIENT_ID'):
        try:
            transactions = api.get_transactions()
            transactions_df = pd.read_json(json.dumps(transactions))
            rewards = api.get_rewards()
            rewards_df = pd.read_json(json.dumps(rewards))
        except Exception as e:
            logger.error(f"Error fetching data from Plutus API: {str(e)}")
            transactions_df = pd.read_csv('transactions.csv')
            rewards_df = pd.read_csv('rewards.csv')
    else:
        transactions_df = pd.read_csv('transactions.csv')
        rewards_df = pd.read_csv('rewards.csv')

    transactions_df.drop(columns=['is_debit', '__typename'], inplace=True)
    transactions_df.rename(columns={'id': 'transaction_id'}, inplace=True)

    # rewards_df.drop(columns=['contis_transaction', 'approved_by', 'fiat_transaction'], inplace=True)
    rewards_df.rename(columns={'amount': 'plu_amount', 'type': 'reward_type',
                               'id': 'reward_id'}, inplace=True)

    return transactions_df, rewards_df


def clear_data_warehouse() -> None:
    aws_connector = AWSConnector()
    s3 = aws_connector.connect_to_s3()

    BUCKET = 'cashback-bucket'
    PREFIX = 'datawarehouse/'

    bucket = s3.Bucket(BUCKET)

    logger.info(f"Deleting existing files in {BUCKET}/{PREFIX}")
    for obj in bucket.objects.filter(Prefix=PREFIX):
        obj.delete()
    logger.info("Data warehouse cleared successfully!")


def start_glue_job(glue_job_name):

    glue_client = boto3.client('glue', aws_access_key_id=AWS_ACCESS_KEY,
                               aws_secret_access_key=AWS_SECRET_KEY)
    try:
        glue_client.start_job_run(JobName=glue_job_name)
        logger.info(f"Glue job '{glue_job_name}' started successfully")
    except Exception as e:
        logger.error(f"Error starting Glue job {glue_job_name}: {str(e)}")


def lambda_handler(event, context):
    api = PlutusApi(USER_ID, PASS_ID, AUTH_SECRET, CLIENT_ID)
    bucket_name = 'cashback-bucket'
    transactions_df, rewards_df = fetch_data(api)

    # transactions_json = transactions_df.to_json(orient='records')[1:-1]
    # rewards_json = rewards_df.to_json(orient='records')[1:-1]

    to_s3(transactions_df, bucket_name, 'staging/transactions.csv')
    to_s3(rewards_df, bucket_name, 'staging/rewards.csv')

    clear_data_warehouse()

    # glue_job_name = 'Cashback project'  # Replace with your actual Glue job name
    # start_glue_job(glue_job_name)

    # aws_connector = AWSConnector()
    # s3 = aws_connector.connect_to_s3()
    #
    # # # Upload transactions/rewards to S3
    # # transactions_json = json.dumps(transactions)
    # # transactions_json = transactions_json[1:-1]
    # s3.Object(bucket_name, 'staging/transactions.json').put(Body=transactions_json.encode('UTF-8'))
    # #
    # # rewards_json = json.dumps(rewards)
    # # rewards_json = rewards_json[1:-1]
    # s3.Object(bucket_name, 'staging/rewards.json').put(Body=rewards_json.encode('UTF-8'))

    return {
        'statusCode': 200,
        'body': 'Data successfully uploaded to S3'
    }


if not os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    print(lambda_handler(None, None))
