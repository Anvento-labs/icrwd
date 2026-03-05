FROM public.ecr.aws/lambda/python:3.12

# Copy requirements stringently
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies (architecture matches the image)
RUN pip install -r requirements.txt

# Copy the rest of the application code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Set the handler appropriately
CMD [ "lambda_function.lambda_handler" ]
