# Use a base image of Python
FROM python:3.9-slim

RUN apt-get update && apt-get install -y libsndfile1

# Set the working directory inside the container
WORKDIR /app

# Copy the necessary files to the working directory
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app/ .
