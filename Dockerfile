FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

RUN dnf install -y git

RUN pip install pipenv

COPY Pipfile* ./

RUN pip install --upgrade cython
RUN pip install --upgrade pip

RUN pipenv install --system --deploy

COPY glue_crawler_lambda.py ${LAMBDA_TASK_ROOT}

CMD ["glue_crawler_lambda.lambda_handler"]