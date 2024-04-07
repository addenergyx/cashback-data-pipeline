terraform {
  required_version = "~> 1.7.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.30.0"
    }
    ## ..
  }
}

provider "aws" {
  region  = var.aws_region # Set your desired AWS region
  profile = "default"
}

## Uncomment the following block to use the S3 backend for Terraform state.
#terraform {
#  backend "s3" {
#    bucket = "adriano-data-uploads"
#    key    = "infra/terraform.tfstate"
#    region = "eu-west-1"
#    profile = "default"
#  }
#}