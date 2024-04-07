variable "image_tag" {
  description = "tag of the image to be used for the lambda function"
  default     = "latest"
}

#data "aws_ecr_repository" "data_pull_ecr_repo" {
#  name = "card-api-data-pull-repo"
#}
#
#data "aws_ecr_repository" "redshift_loader_ecr_repo" {
#  name = "redshift-loader-repo"
#}

data "aws_caller_identity" "current" {}

locals {
  prefix              = "git"
  account_id          = data.aws_caller_identity.current.account_id
  ecr_repository_name = "${local.prefix}-demo-lambda-container"
  ecr_image_tag       = "latest"
}

resource "aws_ecr_repository" "data_pull_ecr_repo" {
  name = "card-api-data-pull-repo"
  force_delete = true # this is to delete the repository even if it has images in it
}

resource "aws_ecr_repository" "redshift_loader_ecr_repo" {
  name = "redshift-loader-repo"
  force_delete = true
}

#https://hands-on.cloud/terraform-docker-lambda-example

#A null resource is basically something that doesn't create anything on its own,
#but you can use it to define provisioners blocks.
#They also have a “trigger” attribute, which can be used to recreate the resource
resource "null_resource" "ecr_image" {
  # rebuild and push the Docker image if the Python or Dockerfile changes (based on MD5 hash).
  triggers = {
    python_file = md5(file("${path.module}/../pull_data_glue_job_lambda.py"))
    docker_file = md5(file("${path.module}/../PullDataDockerfile"))
  }

  provisioner "local-exec" {
    #   logs into ECR, builds a Docker image from a local path, tags it, and pushes it to the created ECR repository.
    command = <<EOF
           aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com
           cd ${path.module}/..
           docker build -t ${aws_ecr_repository.data_pull_ecr_repo.repository_url}:${local.ecr_image_tag} -f PullDataDockerfile .
           docker push ${aws_ecr_repository.data_pull_ecr_repo.repository_url}:${local.ecr_image_tag}
       EOF
  }
}

resource "null_resource" "redshift_ecr_image" {
  # rebuild and push the Docker image if the Python or Dockerfile changes (based on MD5 hash).
  triggers = {
    python_file = md5(file("${path.module}/../load_to_redshift_lambda.py"))
    docker_file = md5(file("${path.module}/../RedShiftDockerfile"))
  }

  provisioner "local-exec" {
    #   logs into ECR, builds a Docker image from a local path, tags it, and pushes it to the created ECR repository.
    command = <<EOF
           aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com
           cd ${path.module}/..
           docker build -t ${aws_ecr_repository.redshift_loader_ecr_repo.repository_url}:${local.ecr_image_tag} -f RedShiftDockerfile .
           docker push ${aws_ecr_repository.redshift_loader_ecr_repo.repository_url}:${local.ecr_image_tag}
       EOF
  }
}

#A data source is something which Terraform expects to exist.
data "aws_ecr_image" "lambda_image" {
  depends_on = [
    null_resource.ecr_image
  ]
  repository_name = aws_ecr_repository.data_pull_ecr_repo.name
  image_tag       = local.ecr_image_tag
}

data "aws_ecr_image" "redshift_lambda_image" {
  depends_on = [
    null_resource.redshift_ecr_image
  ]
  repository_name = aws_ecr_repository.redshift_loader_ecr_repo.name
  image_tag       = local.ecr_image_tag
}

resource "aws_lambda_function" "data_pull_lambda" {
  depends_on = [
    null_resource.ecr_image
  ]
  function_name = "card-api-data-pull-lambda"
  role          = aws_iam_role.cashback_lambdas_function_role.arn
  timeout       = 300
  image_uri     = "${aws_ecr_repository.data_pull_ecr_repo.repository_url}@${data.aws_ecr_image.lambda_image.id}"
  package_type  = "Image"
}

output "lambda_name" {
  value = aws_lambda_function.data_pull_lambda.id
}

#resource "aws_lambda_function" "data_pull_lambda" {
#  function_name = "data-pull-lambda"
#  timeout       = 180 # seconds
##  image_uri     = "${data.aws_ecr_repository.data_pull_ecr_repo.repository_url}:${var.image_tag}"
##  image_uri     = "${aws_ecr_repository.data_pull_ecr_repo.repository_url}:${var.image_tag}"
#  image_uri = "${aws_ecr_repository.data_pull_ecr_repo.repository_url}@${data.aws_ecr_image.lambda_image.id}"
#  package_type  = "Image"
#  role          = aws_iam_role.cashback_lambdas_function_role.arn
#}

resource "aws_lambda_function" "redshift_loader_lambda" {
  depends_on = [
    null_resource.redshift_ecr_image
  ]

  function_name = "redshift-loader-lambda"
  timeout       = 180 # seconds
  #  image_uri     = "${aws_ecr_repository.redshift_loader_ecr_repo.repository_url}:${var.image_tag}"
  image_uri    = "${aws_ecr_repository.redshift_loader_ecr_repo.repository_url}@${data.aws_ecr_image.redshift_lambda_image.id}"
  package_type = "Image"
  role         = aws_iam_role.cashback_lambdas_function_role.arn

  environment {
    variables = {
      REDSHIFT_ENDPOINT = aws_redshift_cluster.cashback_redshift_cluster.dns_name
      REDSHIFT_PORT     = aws_redshift_cluster.cashback_redshift_cluster.port
      REDSHIFT_DBNAME   = aws_redshift_cluster.cashback_redshift_cluster.database_name
      REDSHIFT_USER     = aws_redshift_cluster.cashback_redshift_cluster.master_username
      REDSHIFT_PASS     = aws_redshift_cluster.cashback_redshift_cluster.master_password
      IAM_ROLE          = aws_iam_role.cashback_lambdas_function_role.arn
      REDSHIFT_PORT     = aws_redshift_cluster.cashback_redshift_cluster.port
      GLUE_DATABASE     = aws_glue_catalog_database.cashback_db.name
      GLUE_TABLE_NAME   = var.glue_table_name
    }
  }

}

resource "aws_sfn_state_machine" "cashback_state_machine" {
  name     = "cashback-pipeline-orchestration"
  role_arn = aws_iam_role.cashback_lambdas_function_role.arn

  definition = <<EOF
{
  "Comment": "A description of my state machine",
  "StartAt": "DataPull Lambda Invoke",
  "States": {
    "DataPull Lambda Invoke": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.data_pull_lambda.arn}"
      },
      "Retry": [
        {
          "ErrorEquals": [
            "Lambda.ServiceException",
            "Lambda.AWSLambdaException",
            "Lambda.SdkClientException",
            "Lambda.TooManyRequestsException"
          ],
          "IntervalSeconds": 1,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "Next": "Glue StartJobRun"
    },
    "Glue StartJobRun": {
      "Type": "Task",
      "Resource": "arn:aws:states:::glue:startJobRun.sync",
      "Parameters": {
        "JobName": "${aws_glue_job.glue_job_script.name}"
      },
      "Next": "StartCrawler"
    },
    "StartCrawler": {
      "Type": "Task",
      "Parameters": {
        "Name": "${aws_glue_crawler.cashback_data_crawler.name}"
      },
      "Resource": "arn:aws:states:::aws-sdk:glue:startCrawler",
      "Next": "GetCrawler"
    },
    "GetCrawler": {
      "Type": "Task",
      "Next": "Choice",
      "Parameters": {
        "Name": "${aws_glue_crawler.cashback_data_crawler.name}"
      },
      "Resource": "arn:aws:states:::aws-sdk:glue:getCrawler"
    },
    "Choice": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.Crawler.State",
          "StringEquals": "RUNNING",
          "Next": "Wait"
        }
      ],
      "Default": "RedShift Load Lambda Invoke"
    },
    "Wait": {
      "Type": "Wait",
      "Seconds": 5,
      "Next": "GetCrawler"
    },
    "RedShift Load Lambda Invoke": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "${aws_lambda_function.redshift_loader_lambda.arn}"
      },
      "Retry": [
        {
          "ErrorEquals": [
            "Lambda.ServiceException",
            "Lambda.AWSLambdaException",
            "Lambda.SdkClientException",
            "Lambda.TooManyRequestsException"
          ],
          "IntervalSeconds": 1,
          "MaxAttempts": 3,
          "BackoffRate": 2
        }
      ],
      "End": true
    }
  }
}
EOF
}