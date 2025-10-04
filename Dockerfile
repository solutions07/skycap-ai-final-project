# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
# Copy only the requirements file first to leverage Docker's build cache.
# The following RUN command will only be re-executed if requirements.txt changes.
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application's code and data to the working directory
# Now, copy the rest of the application's code and data.
COPY app.py .
COPY intelligent_agent.py .
COPY data/master_knowledge_base.json ./data/

# Set the port the app runs on
ENV PORT 8080

# Define the command to run the application using gunicorn
CMD ["python3", "app.py"]