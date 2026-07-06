# 🚀 CityPulse AI - Deployment Guide

This guide outlines options for deploying the CityPulse AI platform to cloud hosting. Since the platform was built for the **Gen AI Academy APAC Edition**, we have highlighted **Google Cloud Run** as the primary GCP deployment route, along with easier serverless alternatives.

---

## Option 1: Google Cloud Run (Recommended for GCP Hackathons)

Google Cloud Run is a fully managed serverless container host. It scales automatically, integrates perfectly with BigQuery, and handles API requests securely.

### Step 1: Configure GCP locally
Make sure you have the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed, then run:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Build the Container Image using Cloud Build
Submit the build request to Google Cloud Build, which compiles the Docker image remotely and saves it in Artifact Registry:
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/citypulse-ai
```

### Step 3: Deploy to Cloud Run
Deploy the container, setting the environment variables for your project:
```bash
gcloud run deploy citypulse-ai \
    --image gcr.io/YOUR_PROJECT_ID/citypulse-ai \
    --platform managed \
    --region asia-east1 \
    --allow-unauthenticated \
    --set-env-vars GEMINI_API_KEY="your_gemini_api_key" \
    --set-env-vars BIGQUERY_PROJECT="YOUR_PROJECT_ID" \
    --set-env-vars BIGQUERY_DATASET="citypulse_dataset" \
    --set-env-vars BIGQUERY_TABLE="complaints"
```

### Step 4: BigQuery IAM Permissions
For BigQuery connectivity, ensure that the service account used by your Cloud Run service has the `BigQuery Admin` or `BigQuery Data Editor` + `BigQuery Job User` roles assigned.

---

## Option 2: Streamlit Community Cloud (Fastest & Free)

Streamlit offers free hosting for public GitHub repositories.

### Step 1: Push Project to GitHub
1. Create a repository on GitHub (e.g., `citypulse-ai`).
2. Initialize Git locally and push the files:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of CityPulse AI"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/citypulse-ai.git
   git push -u origin main
   ```
   *Note: Ensure your `.env` file is in `.gitignore` to avoid leaking your Gemini API key.*

### Step 2: Deploy to Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
2. Click **New app**, select your repository (`YOUR_USERNAME/citypulse-ai`), branch (`main`), and main file path (`app.py`).
3. Click **Advanced settings** and input your secrets in TOML format:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   BIGQUERY_PROJECT = "your_gcp_project_id"
   BIGQUERY_DATASET = "citypulse_dataset"
   BIGQUERY_TABLE = "complaints"
   ```
4. Click **Deploy!**

---

## Option 3: Standard Dockerized Host (VM / Compute Engine)

If you are deploying to an existing Virtual Machine (GCP Compute Engine, AWS EC2, or a Linux server):

### Step 1: Install Docker & Docker Compose
Ensure Docker and Docker Compose are installed on the remote machine.

### Step 2: Upload Files & Run Compose
Upload the project folder and start the service:
```bash
# Create a local .env file
nano .env

# Start in detached mode
docker compose up -d --build
```
Your dashboard will be available at `http://YOUR_SERVER_IP:8501`.
