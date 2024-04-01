#FROM public.ecr.aws/lambda/python:3.12
##FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12
#
#RUN dnf install -y git
#
#RUN pip install pipenv
#
#COPY Pipfile Pipfile.lock ./
#
#RUN pip install --upgrade cython
#RUN pip install --upgrade pip
#
#RUN pipenv install --system --deploy
#
## Copy function code
#COPY pull_data.py ${LAMBDA_TASK_ROOT}
#COPY .env ${LAMBDA_TASK_ROOT}
#
#CMD ["pull_data_glue_job_lambda.lambda_handler"]

FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

RUN dnf install -y git

RUN pip install pipenv

COPY Pipfile* ./

RUN pip install --upgrade cython
RUN pip install --upgrade pip

RUN pipenv install --system --deploy

COPY pull_data_glue_job_lambda.py api.py ${LAMBDA_TASK_ROOT}

CMD ["pull_data_glue_job_lambda.lambda_handler"]