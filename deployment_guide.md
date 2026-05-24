# ☁️ DataSutram Echo — AWS EC2 Docker Deployment Guide

This guide details the step-by-step process of provisioning an AWS EC2 instance, installing Docker, building the container, configuring security firewall rules, and launching **DataSutram Echo** so it is securely accessible via the instance's Public IP.

---

## 🛠️ Step 1: Provision the EC2 Instance on AWS

1. **Log in to AWS Console** and navigate to the **EC2 Dashboard**.
2. Click **Launch Instance**.
3. **Configure Settings:**
   * **Name:** `voice-analytics-ai-server`
   * **Amazon Machine Image (AMI):** Select **Ubuntu Server 22.04 LTS** (or **Amazon Linux 2023**).
   * **Instance Type:** Select `t3.small` or `t3.medium` (recommended for handling API network requests and background pipeline tasks smoothly).
   * **Key Pair:** Select or create a key pair (`.pem`) to securely connect via SSH.
4. **Configure Network Security (Crucial for Access):**
   * Under **Network Settings**, click **Edit**.
   * Keep standard rules: **Allow SSH traffic** from your IP (or Anywhere if testing).
   * Click **Add Security Group Rule** to configure application traffic:
     * **Type:** `Custom TCP`
     * **Port Range:** `8000` (The default application port)
     * **Source:** `Anywhere-IPv4` (`0.0.0.0/0`)
     * **Description:** `Allow Voice Analytics AI Dashboard access`
   * *(Optional)* If you plan to serve the app directly on port `80` (standard HTTP), also check **Allow HTTP traffic from the internet**.
5. Click **Launch Instance**.

---

## 🔑 Step 2: SSH Connect to Your Instance

From your local machine, open a terminal (or PowerShell on Windows) and run:

```bash
# Set secure permissions on your key pair file (Mac/Linux only)
chmod 400 your-key.pem

# SSH into the EC2 instance (Replace with your actual Public IP / DNS)
ssh -i "your-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

---

## 📦 Step 3: Install Docker on the EC2 Instance

Once logged inside the EC2 virtual machine, install the Docker daemon:

```bash
# Update local packages database
sudo apt-get update -y
sudo apt-get upgrade -y

# Install Docker engine
sudo apt-get install docker.io -y

# Start and enable the Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to the 'docker' group to run commands without 'sudo'
sudo usermod -aG docker ubuntu

# Log out and log back in to apply group changes
exit
```
*Now SSH back into the server:*
```bash
ssh -i "your-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

---

## 📁 Step 4: Clone Code & Configure Secrets

Clone your repository directly onto the EC2 host:

```bash
# Clone the repository
git clone <your-repository-url> voice-analytics-ai
cd voice-analytics-ai

# Create the environment configuration file
nano .env
```

Paste your production keys into the `.env` editor:
```ini
SARVAM_API_KEY=your_sarvam_api_key
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name

LOGIN_EMAIL=admin@audatec.in
LOGIN_PASSWORD_HASH=$2b$12$jlBiHRzApNBl1BZiPiQsAObTcNjr0rrxsY9zCPVn42DWL9WWmWP0e
SECRET_KEY=audatec_super_secret_session_key_123456
```
*(Press `Ctrl + O` to save, `Enter` to confirm, and `Ctrl + X` to exit the nano editor).*

---

## 🚀 Step 5: Build & Run the Docker Container

### Option A: Run on Port 8000 (Requires port in URL)
Build the container and run it, binding the host's port `8000` to the container's port `8000`:
```bash
# Build the Docker image
docker build -t voice-analytics-ai .

# Run the container in background detached mode with a volume mount for uploads
docker run -d \
  --name voice-analytics \
  --env-file .env \
  -p 8000:8000 \
  -v voice_uploads:/workspace/uploads \
  --restart unless-stopped \
  voice-analytics-ai
```

### Option B: Run on Port 80 (Access via IP alone - Recommended)
If you want to access the dashboard directly via the Public IP **without appending `:8000`** in the browser, bind the host's standard web port `80` to the container's internal `8000`:
> ⚠️ *Note: Make sure "Allow HTTP traffic" is checked in your EC2 Security Group rules.*

```bash
docker run -d \
  --name voice-analytics \
  --env-file .env \
  -p 80:8000 \
  -v voice_uploads:/workspace/uploads \
  --restart unless-stopped \
  voice-analytics-ai
```

---

## 🌐 Step 6: Access & Monitor the App

1. Find the **Public IPv4 address** of your EC2 instance from the AWS Dashboard.
2. In your web browser, enter:
   * **If using Option A:** `http://<EC2_PUBLIC_IP>:8000`
   * **If using Option B:** `http://<EC2_PUBLIC_IP>`
3. **Log in** using your administrative credentials:
   * **Email:** `admin@audatec.in`
   * **Password:** `admin123`

### Operational Commands
To monitor the health and behavior of the running application inside the EC2 container:

```bash
# View live-streamed container logs
docker logs -f voice-analytics

# Inspect container status and health state
docker ps

# Restart the container
docker restart voice-analytics

# Stop the container
docker stop voice-analytics
```

---

## 🛡️ Step 7: Production Enhancements (Next Steps)
For a robust public production environment, it is highly recommended to secure communication:
1. **Domain Mapping:** Route a custom domain (e.g. `analytics.yourcompany.com`) to the EC2 Public IP via AWS Route 53 or your DNS provider.
2. **SSL/HTTPS Termination:** Setup a reverse proxy like **Nginx** or **Traefik** on the host machine to handle SSL termination using **Let's Encrypt** (Certbot), forwarding traffic securely to the running docker container.
