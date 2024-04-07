data "aws_iam_policy_document" "glue_execution_assume_role_policy" {
  statement {
    sid     = ""
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "data_lake_policy" {
  statement {
    effect    = "Allow"
    resources = ["*"]
    actions = [
      "glue:*",
      "s3:*",
      "logs:*",
      "lambda:*",
      "cloudwatch:GenerateQuery"
    ]
  }
}

resource "aws_iam_role" "cashback_lambdas_function_role" {
  name = "cashback-lambdas-role"

  assume_role_policy = jsonencode({
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "states.amazonaws.com",
            "glue.amazonaws.com",
            "redshift.amazonaws.com",
            "iam.amazonaws.com",
            "redshift-serverless.amazonaws.com"
          ]
        }
      },
    ]
  })
}

resource "aws_iam_policy" "data_lake_access_policy" {
  name        = "s3DataLakePolicy-${var.s3_bucket}"
  description = "allows for running glue job in the glue console and access my s3_bucket"
  policy      = data.aws_iam_policy_document.data_lake_policy.json
  tags = {
    Application = var.project
  }
}

resource "aws_iam_policy" "redshift_access_policy" {
  name        = "cashback-pipeline-redshiftAccessPolicy"
  description = "Redshift access policy"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          # https://stackoverflow.com/a/71711659
          "redshift:*",
          "s3:*",
          "sqlworkbench:*",
          "sts:*",
          "secretsmanager:*",
          "s3-object-lambda:*",
          "ec2:*",
          "sns:*",
          "cloudwatch:*",
          "tag:*",
          "redshift-data:*",
          "sqlworkbench:*",
          "redshift-serverless:*"
        ],
        Effect   = "Allow",
        Resource = ["*"]
      },
    ]
  })
}

resource "aws_iam_role" "glue_service_role" {
  name               = "aws_glue_job_runner"
  assume_role_policy = data.aws_iam_policy_document.glue_execution_assume_role_policy.json
  tags = {
    Application = var.project
  }
}

resource "aws_iam_role_policy_attachment" "glue_data_lake_permissions" {
  role       = aws_iam_role.glue_service_role.name
  policy_arn = aws_iam_policy.data_lake_access_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_data_lake_permissions" {
  role       = aws_iam_role.cashback_lambdas_function_role.name
  policy_arn = aws_iam_policy.data_lake_access_policy.arn
}

resource "aws_iam_role_policy_attachment" "redshift_lambda_permissions" {
  role       = aws_iam_role.cashback_lambdas_function_role.name
  policy_arn = aws_iam_policy.redshift_access_policy.arn
}
