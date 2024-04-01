provider "aws" {
  region = "eu-west-1" # Replace with your AWS region
}

resource "aws_ecr_repository" "lambda_repository" {
  name                 = "cashback-data-pull-repo"
  image_tag_mutability = "MUTABLE"
}

resource "aws_iam_role" "lambda_execution_role" {
  name = "data_engineering_lambda_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
      },
    ],
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda_policy"
  description = "IAM policy for Lambda to access S3, Glue, and ECR"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "s3:*",
          "glue:StartJobRun",
          "glue:GetJob",
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetRepositoryPolicy",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*",
        Effect   = "Allow",
      },
    ],
  })
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

resource "aws_lambda_function" "lambda_function" {
  function_name = "cashback_data_pull_lambda"
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "pull_data_glue_job.lambda_handler" # This is still required but not used for container images

  image_uri = "${aws_ecr_repository.lambda_repository.repository_url}:latest"

  package_type = "Image"

  timeout     = 120 # Set the timeout value as needed
  memory_size = 512 # Adjust the memory size as needed

  environment {
    variables = {
      AUTH_SECRET = var.card_auth_secret
      USER_ID     = var.card_user_id
      PASS_ID     = var.card_pass
      CLIENT_ID   = var.card_client_id
    }
  }
}

resource "aws_s3_bucket" "data_bucket" {
  bucket = var.s3_bucket
}

resource "aws_glue_job" "glue_job" {
  name     = "cashback_glue_job"
  role_arn = aws_iam_role.lambda_execution_role.arn

  command {
    script_location = "s3://${aws_s3_bucket.data_bucket.bucket}/glue-script/etl.py"
    python_version  = "3"
  }

  default_arguments = {
    "--extra-py-files"            = "s3://${aws_s3_bucket.data_bucket.bucket}/lib/glue_python_shell_module-0.1-py3-none-any.whl"
    "--additional-python-modules" = "s3://${aws_s3_bucket.data_bucket.bucket}/lib/glue_python_shell_module-0.1-py3-none-any.whl"
  }
}

# Output the ECR repository URL
output "ecr_repository_url" {
  value = aws_ecr_repository.lambda_repository.repository_url
}

# Output the S3 bucket name
output "s3_bucket_name" {
  value = aws_s3_bucket.data_bucket.bucket
}


# Configure redshift cluster. This will fall under free tier as of June 2022.
resource "aws_redshift_cluster" "redshift" {
   cluster_identifier = "redshift-cluster-pipeline"
   skip_final_snapshot = true # must be set so we can destroy redshift with terraform destroy
   master_username    = "awsuser"
   master_password    = var.db_password
   node_type          = "dc2.large"
   cluster_type       = "single-node"
   publicly_accessible = "true"
   iam_roles = [aws_iam_role.redshift_role.arn]
   vpc_security_group_ids = [aws_security_group.sg_redshift.id]

}

# Configure security group for Redshift allowing all inbound/outbound traffic
resource "aws_security_group" "sg_redshift" {
   name        = "sg_redshift"
   ingress {
     from_port       = 0
     to_port         = 0
     protocol        = "-1"
     cidr_blocks      = ["0.0.0.0/0"]
   }
   egress {
     from_port       = 0
     to_port         = 0
     protocol        = "-1"
     cidr_blocks      = ["0.0.0.0/0"]
   }
}

# Create S3 Read only access role. This is assigned to Redshift cluster so that it can read data from S3
resource "aws_iam_role" "redshift_role" {
   name = "RedShiftLoadRole"
   managed_policy_arns = ["arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"]
   assume_role_policy = jsonencode({
     Version = "2012-10-17"
     Statement = [
       {
         Action = "sts:AssumeRole"
         Effect = "Allow"
         Sid    = ""
         Principal = {
           Service = "redshift.amazonaws.com"
         }
       },
     ]
   })
}

