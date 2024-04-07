locals {
  glue_src_path = "${path.root}/../glue_job/"
}

variable "project" {
  description = "Project name"
  type        = string
  default     = "Cashback_pipeline_project"
}

variable "db_password" {
  description = "Password for Redshift master DB user"
  type        = string
  default     = "DataTalks2024."
}

variable "glue_table_name" {
  description = "Glue catalog table name and S3 prefix"
  type        = string
  default     = "datawarehouse"
}

variable "s3_bucket" {
  description = "Bucket name for S3"
  type        = string
  default     = "cashback-bucket"
}

variable "aws_region" {
  description = "Region for AWS"
  type        = string
  default     = "eu-west-1"
}

#variable "card_user_id" {
#  description = "Bank account user id"
#  type        = string
#  default     = ""
#}
#
#variable "card_pass" {
#  description = "Bank account password"
#  type        = string
#  default     = ""
#}
#
#variable "card_client_id" {
#  description = "Bank account client id"
#  type        = string
#  default     = ""
#}
#
#variable "card_auth_secret" {
#  description = "Bank account auth secret"
#  type        = string
#  default     = ""
#}