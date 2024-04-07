APP_NAME ?= cashback-data-pull-repo
APP_VERSION = 0.0.1

AWS_ACCOUNT_ID ?= xxxxxxxxxxxxx
AWS_ECR_REGION ?= eu-west-1
AWS_ECR_REPO = $(APP_NAME)

TAG ?= $(APP_VERSION)

# Marking all targets as phony, as they are not file-generating targets
.PHONY: docker/build docker/push docker/run docker/test docker/build-all

docker/build :
	@echo "Building Docker image..."
	pipenv update # To prevent "Your Pipfile.lock (...) is out of date." error message
	docker build -t $(APP_NAME):$(APP_VERSION) .

docker/push : docker/build
	aws ecr get-login-password --region $(AWS_ECR_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com
	docker tag $(APP_NAME):$(APP_VERSION) $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)

docker/run :
	docker run -p 9000:8080 $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/$(AWS_ECR_REPO):$(TAG)

docker/test :
	curl -XPOST 'http://localhost:9000/2015-03-31/functions/function/invocations' -d '{}'

docker/build-all:
	pipenv update
	aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com

	docker build --pull --no-cache -t card-api-data-pull -f PullDataDockerfile .
	docker tag card-api-data-pull:latest $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/card-api-data-pull-repo:latest
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/card-api-data-pull-repo:latest

	docker build --pull --no-cache -t redshift-loader -f RedShiftDockerfile .
	docker tag redshift-loader:latest $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/redshift-loader-repo:latest
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_ECR_REGION).amazonaws.com/redshift-loader-repo:latest

terraform/init :
	terraform -chdir=infra init -upgrade

terraform/plan : terraform/init
	terraform -chdir=infra plan --input=false

terraform/apply :
	terraform -chdir=infra apply --input=false -auto-approve

terraform/plan-destroy :
	terraform -chdir=infra plan -destroy

terraform/destroy :
	terraform -chdir=infra destroy --input=false -auto-approve

#glue/upload:
#	cd glue_job && python setup.py bdist_wheel
#	aws s3 cp glue_job/dist/elt.py s3://cashback-bucket/glue-script/
#	aws s3 cp glue_job/dist/glue_python_shell_module-0.1-py3-none-any.whl s3://cashback-bucket/lib/