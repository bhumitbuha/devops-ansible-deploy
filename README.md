# Containerized App Deployment with Docker and Ansible

**Author:** Bhumit Buha
**Stack:** Python, Flask, Docker, Docker Compose, Ansible
**Runs on:** Local machine. No cloud account required.
**Environments:** Dev (port 5000), Staging (port 5001)

---

## What This Project Does

This is an automated deployment pipeline for a containerized Python Flask service. The app itself is intentionally minimal. The focus is on the infrastructure and tooling around it.

The pipeline does the following without any manual steps:

1. Verifies the Docker daemon is running and creates the required network
2. Builds a multi-stage Docker image from source
3. Stops any existing container and deploys a fresh one with the correct environment variables
4. Hits the `/health` endpoint and asserts the version and status match expectations
5. Writes a timestamped deployment record to an artifacts file
6. Supports a separate rollback playbook that tears down the current container and brings back a prior image version

Everything is driven by Ansible roles and variables. Run the same playbook twice and it safely reaches the desired state without side effects. That is idempotency in practice.

---

## Project Structure

```
devops-ansible-deploy/
├── app/
│   ├── app.py                          # Flask application (3 endpoints)
│   ├── requirements.txt                # flask, gunicorn
│   └── Dockerfile                      # Multi-stage build, non-root user, HEALTHCHECK
│
├── ansible/
│   ├── deploy.yml                      # Main deployment playbook
│   ├── rollback.yml                    # Rollback to a prior image version
│   ├── group_vars/
│   │   └── all.yml                     # Shared variables (version, ports, paths)
│   ├── inventory/
│   │   └── hosts.ini                   # Target hosts (localhost via local connection)
│   └── roles/
│       ├── docker_setup/
│       │   └── tasks/main.yml          # Verify Docker, create network, prune images
│       ├── app_deploy/
│       │   └── tasks/main.yml          # Build image, stop old container, start new one
│       └── health_check/
│           └── tasks/main.yml          # HTTP health check, version assertion, artifact
│
├── docker-compose.yml                  # Dev environment (app + Redis, port 5000)
├── docker-compose.staging.yml          # Staging overrides (port 5001, resource limits)
├── artifacts/                          # Auto-generated deployment records
└── .gitignore
```

---

## Related Project

This pipeline is designed as the **Deploy** stage companion to the Jenkins CI pipeline:

- **[ps-deployment-toolkit-jenkins](https://github.com/bhumitbuha/ps-deployment-toolkit-jenkins)**: Groovy Jenkinsfile pipeline that handles build, parallel testing, and artifact packaging. Its Deploy stage triggers this Ansible playbook.

Together they form a complete CI/CD pipeline: Jenkins builds and tests; Ansible deploys, validates, and can roll back.

---

## Prerequisites

### Docker Desktop

Download and install from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop).
Start Docker Desktop and wait for the engine to show as running before proceeding.

Verify:
```bash
docker --version
docker compose version
```

### Ansible

Ansible runs natively on Linux and macOS. On Windows it runs inside WSL (Windows Subsystem for Linux).

**Windows. Install WSL first (run in PowerShell as Administrator):**
```powershell
wsl --install
```
Restart your machine, then open the Ubuntu app and run:
```bash
sudo apt update && sudo apt install python3-pip -y
pip3 install ansible
ansible-galaxy collection install community.docker
```

**macOS / Linux:**
```bash
pip install ansible
ansible-galaxy collection install community.docker
```

Verify:
```bash
ansible --version
ansible-galaxy collection list | grep community.docker
```

### Python 3 (for running the app locally without Docker)

```bash
python --version   # must be 3.9+
```

---

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/devops-ansible-deploy.git
cd devops-ansible-deploy
```

### 2. Deploy to Dev

From the project root (inside WSL on Windows, or terminal on macOS/Linux):

```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=dev"
```

You will see each Ansible role execute task by task. When it completes, the app is live at `http://localhost:5000`.

### 3. Verify it is running

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
curl http://localhost:5000/metrics
```

Or open those URLs in a browser.

### 4. Check container status

```bash
docker ps
docker logs devops-demo-app-dev
docker inspect devops-demo-app-dev
```

---

## All Commands

### Deploy to Dev

```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=dev"
```

### Deploy to Staging

```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=staging"
```

Staging runs on port 5001 with memory and CPU limits applied via the `docker-compose.staging.yml` override file.

### Run with Verbose Output

```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=dev" -vv
```

The `-vv` flag shows the full module invocations and return values for each task. It is useful for seeing what Ansible is doing under the hood.

### Test Idempotency

Run the deploy playbook twice in a row:

```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=dev"
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=dev"
```

On the second run, tasks that find the system already in the desired state report `ok` instead of `changed`. No containers are unnecessarily restarted. That is idempotency, a core principle of Ansible configuration management.

### Rollback to a Prior Version

```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/rollback.yml -e "env=dev" -e "version=1.0.0"
```

The rollback playbook stops and removes the current container, then starts the specified image version and validates the `/health` endpoint before declaring success.

### Build the Docker Image Manually

```bash
cd app
docker build -t devops-demo-app:1.0.0 .
docker run -p 5000:5000 -e APP_ENV=dev -e APP_VERSION=1.0.0 devops-demo-app:1.0.0
```

### Run with Docker Compose (Dev)

```bash
docker compose up --build
```

### Run with Docker Compose (Staging)

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
```

---

## API Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| GET | `/` | Service info | `service`, `version`, `environment`, `status`, `timestamp` |
| GET | `/health` | Health check | `{"status": "ok", "version": "1.0.0"}` |
| GET | `/metrics` | Runtime metrics | `environment`, `uptime_check`, `version` |

Example response from `GET /`:
```json
{
  "service": "ps-deployment-toolkit API",
  "version": "1.0.0",
  "environment": "dev",
  "status": "healthy",
  "timestamp": "2026-05-17T14:13:31.782058"
}
```

---

## How the Ansible Roles Work

### `docker_setup`

Runs first. Checks that the Docker daemon is reachable, prints the Docker version, ensures the named bridge network exists (creates it if not), and prunes any dangling images to keep the environment clean.

### `app_deploy`

Builds the Docker image from `app/Dockerfile` using `force_source: true` so a fresh image is always produced. Removes the existing container if one is running (this is idempotent and does not error if it does not exist), then starts a new container with the correct port mapping, environment variables, and network attachment.

### `health_check`

Polls `http://localhost:5000/health` with configurable retries and delay until the app responds with HTTP 200. Uses Ansible's `assert` module to validate that the response body contains the expected `status` and `version` values. Also hits `/metrics` and writes a timestamped deployment record to `artifacts/deploy-record-dev.txt`.

---

## Dockerfile (Multi-Stage Build)

The Dockerfile uses a two-stage build to keep the final image lean:

- **Stage 1 (builder):** Uses `python:3.11-slim` and installs all pip dependencies into the standard site-packages location.
- **Stage 2 (runtime):** Starts from a fresh `python:3.11-slim` and copies only the installed packages and the gunicorn executable from the builder. No build tools, no pip cache.
- Runs as a non-root user (`appuser`) for security.
- Has a `HEALTHCHECK` instruction so Docker itself monitors the `/health` endpoint every 30 seconds.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_VERSION` | `1.0.0` | Application version, returned in all responses |
| `APP_ENV` | `dev` | Environment name (`dev` or `staging`) |
| `PORT` | `5000` | Port the gunicorn server binds to |

These are set in `ansible/group_vars/all.yml` and passed into the container at deploy time.

---

## Artifacts

After each successful deployment, Ansible writes a record to `artifacts/deploy-record-<env>.txt`:

```
DEPLOYMENT RECORD
=================
Timestamp: 2026-05-17T14:16:34Z
Environment: dev
Version: 1.0.0
Health: PASSING
Container: devops-demo-app-dev
```

---

## Troubleshooting

**Docker daemon not running:**
Open Docker Desktop and wait for the engine status to show green before running any commands.

**Ansible not found on Windows:**
Ansible must be installed inside WSL, not in PowerShell. Open the Ubuntu WSL terminal and run the install commands from there.

**Port 5000 already in use:**
```bash
docker rm -f devops-demo-app-dev
```
Then re-run the playbook.

**community.docker collection missing:**
```bash
ansible-galaxy collection install community.docker
```

**Health check failing:**
The container may need more time to start. Increase `health_check_delay` in `ansible/group_vars/all.yml` from `10` to `20` and re-run.

---

## Author

**Bhumit Buha**
Ottawa, ON
bhumitbuha2016@gmail.com
[linkedin.com/in/buha0006](https://linkedin.com/in/buha0006)
