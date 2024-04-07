# Configure redshift cluster. This will fall under free tier as of June 2022.
resource "aws_redshift_cluster" "cashback_redshift_cluster" {
  cluster_identifier     = "cashback-redshift-cluster"
  skip_final_snapshot    = true # must be set so we can destroy redshift with terraform destroy
  master_username        = "awsuser"
  master_password        = var.db_password
  node_type              = "dc2.large"
  cluster_type           = "single-node"
  publicly_accessible    = "true"
  iam_roles              = [aws_iam_role.cashback_lambdas_function_role.arn]
  vpc_security_group_ids = [aws_security_group.sg_redshift.id]
  database_name          = "dev"
  port                   = 5439
}

# Configure security group for Redshift allowing all inbound/outbound traffic
resource "aws_security_group" "sg_redshift" {
  name = "sg_redshift"
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}