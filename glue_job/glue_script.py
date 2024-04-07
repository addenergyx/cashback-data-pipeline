import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col, when, abs as spark_abs, date_format

# Set up Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
args = getResolvedOptions(sys.argv, ['JOB_NAME'])

job.init(args['JOB_NAME'], args)

# Read CSV files from S3
rewards_df = spark.read.csv("s3://cashback-bucket/staging/rewards.csv", header=True)
transactions_df = spark.read.csv("s3://cashback-bucket/staging/transactions.csv", header=True)

# Perform join operation
joined_df = rewards_df.join(transactions_df, rewards_df["reference_id"] == transactions_df["transaction_id"], "left")

# Calculate transaction_amount
joined_df = joined_df.withColumn("transaction_amount", spark_abs(col("amount")) / 100)

# Select necessary fields
selected_fields_df = joined_df.select("reward_id", "transaction_id", "description", "plu_amount", "date",
                                      "available", "reason", "createdAt", "updatedAt",
                                      "rebate_rate", "fiat_amount_rewarded", "currency",
                                      "reference_type", "reward_type", "transaction_amount")

# Rename columns using withColumnRenamed
selected_fields_df = selected_fields_df.withColumnRenamed("createdAt", "created_at") \
    .withColumnRenamed("updatedAt", "updated_at") \
    .withColumnRenamed("date", "transaction_date")

selected_fields_df = selected_fields_df.withColumn("transaction_timestamp", col("transaction_date").cast("timestamp"))
selected_fields_df = selected_fields_df.withColumn("transaction_date", date_format(col("transaction_date"), "yyyy-MM-dd"))

# Calculate plu_price based on rebate_rate and amount
selected_fields_df = selected_fields_df.withColumn("plu_price",
                                                   when(col("rebate_rate") == 0.0,
                                                        col("fiat_amount_rewarded") / col("plu_amount")
                                                        ).otherwise(
                                                       ((spark_abs(col("transaction_amount")) / 100) * col("rebate_rate")) / col(
                                                           "plu_amount")
                                                   )
                                                   )


selected_fields_df = selected_fields_df.withColumn("fiat_amount_rewarded", spark_abs(col("fiat_amount_rewarded")) / 100)

# Convert data types
selected_fields_df = selected_fields_df.withColumn("reward_id", col("reward_id").cast("string"))
selected_fields_df = selected_fields_df.withColumn("transaction_id", col("transaction_id").cast("string"))
selected_fields_df = selected_fields_df.withColumn("rebate_rate", col("rebate_rate").cast("integer"))
selected_fields_df = selected_fields_df.withColumn("reward_type", col("reward_type").cast("string"))
selected_fields_df = selected_fields_df.withColumn("reference_type", col("reference_type").cast("string"))
# selected_fields_df = selected_fields_df.withColumn("available",
#                                                    when(col("available") == "TRUE", True)
#                                                    .when(col("available") == "FALSE", False)
#                                                    .otherwise(None)  # None is equivalent to null or NaN
#                                                    )
selected_fields_df = selected_fields_df.withColumn("available", col("available").cast("boolean"))
selected_fields_df = selected_fields_df.withColumn("reason", col("reason").cast("string"))
selected_fields_df = selected_fields_df.withColumn("fiat_amount_rewarded", col("fiat_amount_rewarded").cast("string"))
selected_fields_df = selected_fields_df.withColumn("created_at", col("created_at").cast("timestamp"))
selected_fields_df = selected_fields_df.withColumn("updated_at", col("updated_at").cast("timestamp"))
selected_fields_df = selected_fields_df.withColumn("currency", col("currency").cast("string"))
selected_fields_df = selected_fields_df.withColumn("description", col("description").cast("string"))
selected_fields_df = selected_fields_df.withColumn("plu_amount", col("plu_amount").cast("double"))
selected_fields_df = selected_fields_df.withColumn("transaction_amount", col("transaction_amount").cast("double"))

# Write DataFrame to Parquet file in S3
selected_fields_df.write.partitionBy("transaction_date").parquet("s3://cashback-bucket/datawarehouse/transformed_data"
                                                                 ".parquet", mode="overwrite")

job.commit()
