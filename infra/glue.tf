resource "aws_s3_object" "glue_job_script_s3" {
  bucket = var.s3_bucket
  key    = "glue-script/glue_script.py"
  source = "${local.glue_src_path}glue_script.py"
  etag   = filemd5("${local.glue_src_path}glue_script.py") # Checksum check on the file, does a deployment only if the file has changed
}

resource "aws_glue_job" "glue_job_script" {
  glue_version      = "4.0"                                                                       #optional
  max_retries       = 0                                                                           #optional
  name              = "CashbackDeployScript"                                                      #required
  description       = "test the deployment of an aws glue job to aws glue service with terraform" #description
  role_arn          = aws_iam_role.glue_service_role.arn                                          #required
  number_of_workers = 2                                                                           #optional, defaults to 5 if not set
  worker_type       = "G.1X"                                                                      #optional
  timeout           = "10"                                                                        #optional
  execution_class   = "FLEX"                                                                      #optional
  tags = {
    project = var.project #optional
  }
  command {
    name            = "glueetl"                                          #optional
    script_location = "s3://${var.s3_bucket}/glue-script/glue_script.py" #required
  }
  default_arguments = {
    "--class"                   = "GlueApp"
    "--enable-job-insights"     = "true"
    "--enable-auto-scaling"     = "false"
    "--enable-glue-datacatalog" = "true"
    "--job-language"            = "python"
    "--job-bookmark-option"     = "job-bookmark-disable"
    #    "--datalake-formats"        = "iceberg"
    #    "--conf"                    = "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions  --conf spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog  --conf spark.sql.catalog.glue_catalog.warehouse=s3://tnt-erp-sql/ --conf spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog  --conf spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO"
  }
}

resource "aws_glue_catalog_database" "cashback_db" {
  name        = "cashback_db"
  description = "metadata for cashback data"
  tags = {
    project = var.project
  }
}


resource "aws_glue_crawler" "cashback_data_crawler" {
  name          = "cashback_data_crawler"
  role          = aws_iam_role.glue_service_role.arn
  database_name = aws_glue_catalog_database.cashback_db.name

  s3_target {
    path = "s3://${var.s3_bucket}/${var.glue_table_name}/"
  }

  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING" #default
  }
  tags = {
    project = var.project
  }
}