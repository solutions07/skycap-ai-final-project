# Production Dockerfile for SkyCap AI Cloud Run Deployment
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt and gunicorn
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy all necessary application files into the container
COPY app.py .
COPY intelligent_agent.py .
COPY master_knowledge_base.json .
# Copy service account credential candidates into a secure folder inside the image.
# During testing we will instruct `intelligent_agent.py` which one to use via
# the SKYCAP_TEST_CREDENTIAL environment variable so we don't need to rewrite the
# Dockerfile for each credential. This also keeps all candidate credentials
# available inside /secrets for debugging.
RUN mkdir -p /secrets
COPY service_account_key.json /secrets/service_account_key.json
COPY .env .

# Expose the port the app runs on (Cloud Run uses 8080)
EXPOSE 8080

# Define the command to run the application using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
