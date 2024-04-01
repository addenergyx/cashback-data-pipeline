import pandas as pd
import s3fs
import pyarrow.parquet as pq
import pyarrow as pa

s3_filesystem = s3fs.S3FileSystem()


def read_csv_from_s3(bucket, key):
    file_path = f's3://{bucket}/{key}'
    return pd.read_csv(file_path)


# Function to write a DataFrame to a Parquet in S3
def write_df_to_parquet_s3(df, bucket, key):
    file_path = f's3://{bucket}/{key}'
    with s3_filesystem.open(file_path, 'wb') as f:
        table = pa.Table.from_pandas(df)
        pq.write_table(table, f, compression='snappy')


BUCKET = 'cashback-bucket'

rewards_df = read_csv_from_s3(BUCKET, 'staging/rewards.csv')
transactions_df = read_csv_from_s3(BUCKET, 'staging/transactions.csv')

joined_df = pd.merge(rewards_df, transactions_df, left_on='reference_id', right_on='transaction_id', how='left')

selected_fields_df = joined_df[["reward_id", "transaction_id", "description", "plu_amount", "date",
                                "available", "reason", "createdAt", "updatedAt",
                                "rebate_rate", "fiat_amount_rewarded", "currency",
                                "reference_type", "reward_type", "amount"]]

selected_fields_df = selected_fields_df.rename(columns={'createdAt': 'created_at', 'updatedAt': 'updated_at',
                                                        'date': 'transaction_date'})

# Changing data types of columns
selected_fields_df['reward_id'] = selected_fields_df['reward_id'].astype(str)
selected_fields_df['transaction_id'] = selected_fields_df['transaction_id'].astype(str)
selected_fields_df['amount'] = pd.to_numeric(selected_fields_df['amount'], errors='coerce')
selected_fields_df['rebate_rate'] = pd.to_numeric(selected_fields_df['rebate_rate'], downcast='integer',
                                                  errors='coerce')
selected_fields_df['reward_type'] = selected_fields_df['reward_type'].astype(str)
selected_fields_df['reference_type'] = selected_fields_df['reference_type'].astype(str)
selected_fields_df['available'] = selected_fields_df['available'].astype(bool)
selected_fields_df['reason'] = selected_fields_df['reason'].astype(str)
selected_fields_df['fiat_amount_rewarded'] = selected_fields_df['fiat_amount_rewarded'].astype(str)
selected_fields_df['created_at'] = pd.to_datetime(selected_fields_df['created_at'])
selected_fields_df['updated_at'] = pd.to_datetime(selected_fields_df['updated_at'])
selected_fields_df['currency'] = selected_fields_df['currency'].astype(str)
selected_fields_df['transaction_date'] = pd.to_datetime(selected_fields_df['transaction_date'])
selected_fields_df['description'] = selected_fields_df['description'].astype(str)
selected_fields_df['plu_amount'] = pd.to_numeric(selected_fields_df['plu_amount'], errors='coerce')

# Write the final DataFrame to a Parquet file in S3
write_df_to_parquet_s3(selected_fields_df, BUCKET, 'datawarehouse/transformed_data.parquet')
