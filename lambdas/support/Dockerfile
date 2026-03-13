FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

COPY lambda_function.py ${LAMBDA_TASK_ROOT}
COPY app/ ${LAMBDA_TASK_ROOT}/app/

CMD [ "lambda_function.lambda_handler" ]
