# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
# Copy only the requirements file first to leverage Docker's build cache.
# The following RUN command will only be re-executed if requirements.txt changes.
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application's code and data to the working directory
# Now, copy the rest of the application's code and data.
COPY app.py .
COPY intelligent_agent.py .
COPY search_index.py .
# Include the index builder to precompute the semantic index at build time
COPY build_index.py .
# Copy all data assets (including knowledge base)
COPY data/ ./data/

# Set the port the app runs on
ENV PORT=8080
# Vertex AI configuration (override at deploy time)
ARG GCP_PROJECT=""
ARG GCP_REGION=""
ARG VERTEX_MODEL_NAME="gemini-1.0-pro"
ENV GOOGLE_CLOUD_PROJECT=${GCP_PROJECT}
ENV GOOGLE_CLOUD_REGION=${GCP_REGION}
ENV GOOGLE_CLOUD_LOCATION=""
ENV VERTEX_MODEL_NAME=${VERTEX_MODEL_NAME}
# Optional: location/name for a precomputed semantic index (downloaded at startup by app.py)
ENV SEMANTIC_INDEX_GCS_URI=""
ENV SEMANTIC_INDEX_LOCAL_PATH=""

# Build and bake a semantic index into the image (best-effort)
# This step will attempt to embed the KB using sentence-transformers. If embedding fails
# (e.g., network or model download issues), the builder saves a stub index and continues.
RUN python3 build_index.py --kb data/master_knowledge_base.json --out semantic_index.pkl || true

# Define the command to run the application using gunicorn
# Run with gunicorn in production
CMD ["gunicorn", "-b", ":8080", "app:app"]