import boto3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def lambda_handler(event, context):
    glue_client = boto3.client('glue')
    crawler_name = 'cashback_crawler'
    glue_client.start_crawler(Name=crawler_name)

    logger.info(f"Crawler {crawler_name} started successfully!")

    return {
        'statusCode': 200,
        'body': f'Crawler {crawler_name} started successfully!'
    }


if __name__ == '__main__':
    print(lambda_handler(None, None))
