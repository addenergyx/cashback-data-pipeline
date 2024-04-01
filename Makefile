APP_NAME ?= cashback-data-pull-repo
APP_VERSION = 0.0.1

AWS_ECR_ACCOUNT_ID ?= 334010140999
AWS_ECR_REGION ?= eu-west-1
AWS_ECR_REPO = $(APP_NAME)

TAG ?= $(APP_VERSION)

# Marking all targets as phony, as they are not file-generating targets
.PHONY: docker/build docker/push docker/run docker/test

docker/build :
	@echo "Building Docker image..."
	docker build -t $(APP_NAME):$(APP_VERSION) .

docker/push : docker/build
	aws ecr get-login-password --region $(AWS_ECR_REGION) | docker login --username AWS --password-stdin $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com
	docker tag $(APP_NAME):$(APP_VERSION) $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)
	docker push $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)

docker/run :
	docker run -p 9000:8080 $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)

docker/test :
	curl -XPOST 'http://localhost:9000/2015-03-31/functions/function/invocations' -d '{}'

terraform/init :
	terraform init -upgrade

terraform/plan : terraform/init
	terraform plan

glue/upload:
	cd glue_job && python setup.py bdist_wheel
	aws s3 cp glue_job/dist/elt.py s3://cashback-bucket/glue-script/
	aws s3 cp glue_job/dist/glue_python_shell_module-0.1-py3-none-any.whl s3://cashback-bucket/lib/

all:
	cd infra && terraform init -upgrade
	cd infra && terraform apply -target=aws_ecr_repository.lambda_repository -auto-approve
	make docker/push

	cd infra && terraform apply -target=aws_s3_bucket.data_bucket -auto-approve
	make glue/upload

	terraform apply

#	@echo "Building Docker image..."
#	docker build -t $(APP_NAME):$(APP_VERSION) .
#	@echo "Pushing Docker image to ECR..."
#	aws ecr get-login-password --region $(AWS_ECR_REGION) | docker login --username AWS --password-stdin $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com
#	docker tag $(APP_NAME):$(APP_VERSION) $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)
#	docker push $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)
#	@echo "Running Docker image..."
#	docker run -p 9000:8080 $(AWS_ECR_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)
#	@echo "Testing Docker image..."
#	curl -XPOST 'http://localhost:9000/2015-03-31/functions/function/invocations' -d '{}'
#	@echo "Uploading Glue job..."
#	cd glue_job && python setup.py bdist_wheel
#	aws s3 cp glue_job/dist/elt.py s3://cashback-bucket/glue-script/
#	aws s3 cp glue_job/dist/glue_python_shell_module-0.1-py3-none-any.whl s3://cashback-bucket/lib/
#	@echo "Done!"