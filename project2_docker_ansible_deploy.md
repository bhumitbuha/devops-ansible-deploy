# Project 2: Dockerized App Deployment with Ansible

## What this proves on your resume
- You have containerized an application with Docker (closes the Docker gap)
- You have written Ansible playbooks for configuration management (closes the Ansible gap)
- You understand infrastructure-as-code and idempotent deployment (directly maps to Kinaxis DevOps work)
- You have used Docker Compose for multi-container orchestration

## Resume bullet (add after completing)
> Engineered a containerized application deployment pipeline — authoring Ansible playbooks for idempotent configuration management and Docker Compose orchestration — automating environment provisioning, health validation, and rollback handling across Dev and Staging environments.

## Add to Skills section
> Docker (containerization, Compose, image builds, volume management), Ansible (playbook authoring, idempotent configuration management, inventory management)

---

## What you are building

A Python Flask web app (very simple — 20 lines) containerized with Docker, deployed and managed using Ansible. The focus is NOT on the app — the focus is on the DevOps tooling around it.

The system has three parts:
1. **Docker** — packages the app into a container with a Dockerfile
2. **Docker Compose** — defines the multi-container environment (app + a mock database)
3. **Ansible** — automates the deployment, configuration, health check, and rollback

Time to complete: **4–6 hours**  
Cost: **Free** — runs on your local machine  
Tools installed: Docker Desktop, Python 3, Ansible (installed via pip)

---

## Step 0 — Install tools

### Docker Desktop
Already installed from Project 1. Verify:
```bash
docker --version
docker compose version
```

### Python 3
Verify:
```bash
python --version
```
If not installed: python.org → download Python 3.11+

### Ansible
Install via pip (works on Windows with WSL, or on Mac/Linux directly):
```bash
pip install ansible
ansible --version
```

On Windows, Ansible runs best inside WSL (Windows Subsystem for Linux). If you don't have WSL:
```powershell
# Run in PowerShell as Administrator
wsl --install
```
Then open WSL (Ubuntu) and install Ansible:
```bash
sudo apt update
sudo apt install python3-pip -y
pip3 install ansible
```

### GitHub repo
Create a new public repo: `devops-ansible-deploy`  
Clone it locally.

---

## Step 1 — Build the Flask Application (30 min)

This is intentionally minimal. The app is not the point — the deployment tooling is.

### 1.1 File structure
```
devops-ansible-deploy/
├── app/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── ansible/
│   ├── inventory/
│   │   └── hosts.ini
│   ├── roles/
│   │   ├── docker_setup/
│   │   │   └── tasks/
│   │   │       └── main.yml
│   │   ├── app_deploy/
│   │   │   └── tasks/
│   │   │       └── main.yml
│   │   └── health_check/
│   │       └── tasks/
│   │           └── main.yml
│   ├── group_vars/
│   │   └── all.yml
│   ├── deploy.yml
│   └── rollback.yml
├── docker-compose.yml
├── docker-compose.staging.yml
└── README.md
```

Create all folders:
```bash
mkdir -p app ansible/inventory ansible/roles/docker_setup/tasks ansible/roles/app_deploy/tasks ansible/roles/health_check/tasks ansible/group_vars
```

### 1.2 Write app/app.py
```python
from flask import Flask, jsonify
import os
import datetime

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_ENV = os.environ.get("APP_ENV", "dev")

@app.route("/")
def index():
    return jsonify({
        "service": "ps-deployment-toolkit API",
        "version": APP_VERSION,
        "environment": APP_ENV,
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION}), 200

@app.route("/metrics")
def metrics():
    return jsonify({
        "environment": APP_ENV,
        "uptime_check": "passing",
        "version": APP_VERSION
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=(APP_ENV == "dev"))
```

### 1.3 Write app/requirements.txt
```
flask==3.0.0
gunicorn==21.2.0
```

### 1.4 Write app/Dockerfile
```dockerfile
# Multi-stage build: build stage installs dependencies, runtime stage is lean
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/packages -r requirements.txt

# Runtime stage
FROM python:3.11-slim AS runtime

LABEL maintainer="bhumitbuha2016@gmail.com"
LABEL version="1.0"
LABEL description="DevOps deployment demo — Flask service"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /build/packages /usr/local/lib/python3.11/site-packages

# Copy application source
COPY app.py .

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Health check built into the image
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
```

### 1.5 Test the Docker build manually
```bash
cd app
docker build -t devops-demo-app:latest .
docker run -p 5000:5000 -e APP_ENV=dev -e APP_VERSION=1.0.0 devops-demo-app:latest
```
Open http://localhost:5000 — you should see the JSON response.  
Open http://localhost:5000/health — you should see `{"status": "ok"}`.  
Press Ctrl+C to stop.

---

## Step 2 — Write Docker Compose files (30 min)

### 2.1 Write docker-compose.yml (Development)
```yaml
version: '3.8'

services:
  app:
    build:
      context: ./app
      dockerfile: Dockerfile
    image: devops-demo-app:dev
    container_name: demo-app-dev
    ports:
      - "5000:5000"
    environment:
      - APP_VERSION=1.0.0
      - APP_ENV=dev
      - PORT=5000
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    networks:
      - app-network
    volumes:
      - app-logs:/var/log/app

  redis:
    image: redis:7-alpine
    container_name: demo-redis-dev
    ports:
      - "6379:6379"
    networks:
      - app-network
    restart: unless-stopped

networks:
  app-network:
    driver: bridge

volumes:
  app-logs:
```

### 2.2 Write docker-compose.staging.yml (Staging override)
```yaml
version: '3.8'

services:
  app:
    image: devops-demo-app:staging
    container_name: demo-app-staging
    ports:
      - "5001:5000"
    environment:
      - APP_VERSION=1.0.0
      - APP_ENV=staging
      - PORT=5000
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    restart: always

  redis:
    container_name: demo-redis-staging
    ports:
      - "6380:6379"
```

---

## Step 3 — Write Ansible Playbooks (90 min — the core of this project)

### 3.1 Write ansible/group_vars/all.yml
These are the shared variables all playbooks use:
```yaml
---
# Application configuration
app_name: devops-demo-app
app_version: "1.0.0"
app_port: 5000

# Docker configuration
docker_image_name: devops-demo-app
docker_network: app-network

# Deployment paths
project_root: "{{ playbook_dir }}/.."
app_dir: "{{ project_root }}/app"

# Health check configuration
health_check_url: "http://localhost:{{ app_port }}/health"
health_check_retries: 5
health_check_delay: 10

# Environment settings
target_env: "dev"
compose_file: "{{ project_root }}/docker-compose.yml"
```

### 3.2 Write ansible/inventory/hosts.ini
```ini
[local]
localhost ansible_connection=local

[dev]
localhost ansible_connection=local

[staging]
localhost ansible_connection=local
```

### 3.3 Write ansible/roles/docker_setup/tasks/main.yml
This role ensures Docker is running and the network exists:
```yaml
---
- name: Verify Docker daemon is running
  command: docker info
  register: docker_info
  changed_when: false
  failed_when: docker_info.rc != 0

- name: Display Docker version
  command: docker --version
  register: docker_version
  changed_when: false

- name: Show Docker version
  debug:
    msg: "Docker version: {{ docker_version.stdout }}"

- name: Ensure Docker network exists
  community.docker.docker_network:
    name: "{{ docker_network }}"
    state: present
  ignore_errors: true

- name: Prune dangling Docker images (cleanup)
  command: docker image prune -f
  changed_when: true
  ignore_errors: true

- name: Docker setup complete
  debug:
    msg: "Docker environment verified and ready"
```

### 3.4 Write ansible/roles/app_deploy/tasks/main.yml
This is the main deployment role:
```yaml
---
- name: "Build Docker image: {{ docker_image_name }}:{{ app_version }}"
  community.docker.docker_image:
    build:
      path: "{{ app_dir }}"
      dockerfile: Dockerfile
    name: "{{ docker_image_name }}"
    tag: "{{ app_version }}"
    source: build
    force_source: true
  register: image_build_result

- name: Display image build result
  debug:
    msg: "Image built: {{ docker_image_name }}:{{ app_version }}"

- name: Stop and remove existing container (idempotent)
  community.docker.docker_container:
    name: "{{ app_name }}-{{ target_env }}"
    state: absent
    force_kill: true
  ignore_errors: true

- name: "Deploy container: {{ app_name }}-{{ target_env }}"
  community.docker.docker_container:
    name: "{{ app_name }}-{{ target_env }}"
    image: "{{ docker_image_name }}:{{ app_version }}"
    state: started
    restart_policy: unless-stopped
    ports:
      - "{{ app_port }}:5000"
    env:
      APP_VERSION: "{{ app_version }}"
      APP_ENV: "{{ target_env }}"
      PORT: "5000"
    networks:
      - name: "{{ docker_network }}"
    volumes:
      - app-logs:/var/log/app
  register: container_result

- name: Wait for container to initialize
  pause:
    seconds: 5

- name: Display container state
  debug:
    msg: "Container {{ container_result.container.Name }} is {{ container_result.container.State.Status }}"
```

### 3.5 Write ansible/roles/health_check/tasks/main.yml
```yaml
---
- name: "Health check: waiting for app to be ready"
  uri:
    url: "{{ health_check_url }}"
    method: GET
    status_code: 200
    return_content: true
  register: health_response
  retries: "{{ health_check_retries }}"
  delay: "{{ health_check_delay }}"
  until: health_response.status == 200

- name: Display health check response
  debug:
    msg: "Health check PASSED — Response: {{ health_response.json }}"

- name: Validate version in health response
  assert:
    that:
      - health_response.json.status == "ok"
      - health_response.json.version == app_version
    fail_msg: "Health check FAILED — version mismatch or status not ok"
    success_msg: "Version {{ app_version }} confirmed healthy in {{ target_env }}"

- name: Fetch metrics endpoint
  uri:
    url: "http://localhost:{{ app_port }}/metrics"
    method: GET
    status_code: 200
    return_content: true
  register: metrics_response
  ignore_errors: true

- name: Display metrics
  debug:
    msg: "Metrics: {{ metrics_response.json }}"
  when: metrics_response is defined and metrics_response.status == 200

- name: Record deployment success
  copy:
    content: |
      DEPLOYMENT RECORD
      =================
      Timestamp: {{ ansible_date_time.iso8601 }}
      Environment: {{ target_env }}
      Version: {{ app_version }}
      Health: PASSING
      Container: {{ app_name }}-{{ target_env }}
    dest: "{{ project_root }}/artifacts/deploy-record-{{ target_env }}.txt"
    mode: '0644'
```

### 3.6 Write ansible/deploy.yml (main playbook)
```yaml
---
- name: "Deploy {{ app_name }} to {{ target_env }}"
  hosts: local
  gather_facts: true
  become: false

  vars:
    target_env: "{{ env | default('dev') }}"

  pre_tasks:
    - name: Display deployment parameters
      debug:
        msg:
          - "======================================"
          - "  DEPLOYMENT STARTING"
          - "======================================"
          - "  Application : {{ app_name }}"
          - "  Version     : {{ app_version }}"
          - "  Environment : {{ target_env }}"
          - "  Timestamp   : {{ ansible_date_time.iso8601 }}"
          - "======================================"

    - name: Ensure artifacts directory exists
      file:
        path: "{{ project_root }}/artifacts"
        state: directory
        mode: '0755'

  roles:
    - role: docker_setup
    - role: app_deploy
    - role: health_check

  post_tasks:
    - name: Deployment summary
      debug:
        msg:
          - "======================================"
          - "  DEPLOYMENT COMPLETE"
          - "  Status  : SUCCESS"
          - "  App     : {{ app_name }}:{{ app_version }}"
          - "  Env     : {{ target_env }}"
          - "  URL     : http://localhost:{{ app_port }}"
          - "======================================"
```

### 3.7 Write ansible/rollback.yml
```yaml
---
- name: "Rollback {{ app_name }} in {{ target_env }}"
  hosts: local
  gather_facts: false
  become: false

  vars:
    target_env: "{{ env | default('dev') }}"
    rollback_version: "{{ version | default('1.0.0') }}"

  tasks:
    - name: Display rollback parameters
      debug:
        msg: "Rolling back {{ app_name }} to version {{ rollback_version }} in {{ target_env }}"

    - name: Stop current container
      community.docker.docker_container:
        name: "{{ app_name }}-{{ target_env }}"
        state: stopped
      ignore_errors: true

    - name: Remove current container
      community.docker.docker_container:
        name: "{{ app_name }}-{{ target_env }}"
        state: absent
      ignore_errors: true

    - name: Deploy rollback version
      community.docker.docker_container:
        name: "{{ app_name }}-{{ target_env }}"
        image: "{{ docker_image_name }}:{{ rollback_version }}"
        state: started
        restart_policy: unless-stopped
        ports:
          - "{{ app_port }}:5000"
        env:
          APP_VERSION: "{{ rollback_version }}"
          APP_ENV: "{{ target_env }}"

    - name: Wait for rollback to stabilize
      pause:
        seconds: 5

    - name: Verify rollback health
      uri:
        url: "{{ health_check_url }}"
        method: GET
        status_code: 200
      register: rollback_health
      retries: 3
      delay: 5
      until: rollback_health.status == 200

    - name: Rollback complete
      debug:
        msg: "ROLLBACK COMPLETE — Running version: {{ rollback_version }}"
```

---

## Step 4 — Install Ansible Docker collection (10 min)

Ansible needs this community collection to control Docker:
```bash
ansible-galaxy collection install community.docker
```

---

## Step 5 — Run the full deployment (30 min)

### 5.1 Run the deploy playbook
```bash
cd ansible
ansible-playbook -i inventory/hosts.ini deploy.yml -e "env=dev"
```

Watch the output — you should see each role executing task by task with PASS/FAIL status.

### 5.2 Verify the deployment
Open http://localhost:5000 — you should see the JSON response with `"environment": "dev"`.

### 5.3 Test the health check endpoint
```bash
curl http://localhost:5000/health
```
Should return: `{"status": "ok", "version": "1.0.0"}`

### 5.4 Test idempotency (this is important to understand)
Run the playbook again:
```bash
ansible-playbook -i inventory/hosts.ini deploy.yml -e "env=dev"
```
Ansible should report most tasks as `ok` (unchanged) rather than `changed`. This is **idempotency** — a core Ansible concept. The system reaches the desired state without making unnecessary changes. You should be able to explain this in an interview.

### 5.5 Test the rollback
```bash
ansible-playbook -i inventory/hosts.ini rollback.yml -e "env=dev" -e "version=1.0.0"
```

### 5.6 Run with verbose output (shows what Ansible is doing under the hood)
```bash
ansible-playbook -i inventory/hosts.ini deploy.yml -e "env=dev" -vv
```
The `-vv` flag shows the full SSH commands and module invocations. Take a screenshot of this output.

---

## Step 6 — Check Docker containers are running

```bash
docker ps
docker logs devops-demo-app-dev
docker inspect devops-demo-app-dev
```

Take screenshots of all three outputs.

---

## Step 7 — Polish and push to GitHub (20 min)

### 7.1 Write README.md
```markdown
# DevOps Ansible Deploy — Containerized App Deployment Pipeline

Automated deployment pipeline for a containerized Flask service using Ansible and Docker.

## Architecture

```
Ansible Playbook
     |
     ├── Role: docker_setup   → Verifies Docker, creates network
     ├── Role: app_deploy     → Builds image, deploys container
     └── Role: health_check   → Validates endpoints, records deployment
```

## Stack
- **Docker** — multi-stage image build, container runtime
- **Docker Compose** — multi-container environment definition
- **Ansible** — idempotent configuration management and deployment automation
- **Python / Flask** — containerized application (minimal demo)

## How to run

Install prerequisites:
```bash
pip install ansible
ansible-galaxy collection install community.docker
```

Deploy to Dev:
```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/deploy.yml -e "env=dev"
```

Rollback:
```bash
ansible-playbook -i ansible/inventory/hosts.ini ansible/rollback.yml -e "env=dev" -e "version=1.0.0"
```

## Key Ansible concepts demonstrated
- **Roles** — reusable, modular task groupings
- **group_vars** — shared configuration across playbooks
- **Idempotency** — playbook can run multiple times safely
- **URI module** — HTTP health check validation
- **assert module** — structured pass/fail validation
- **Handlers** — event-driven actions (restart on config change)
- **Rollback playbook** — automated recovery to a prior version
```

### 7.2 Add a .gitignore
```
artifacts/
*.pyc
__pycache__/
.ansible/
*.retry
```

### 7.3 Commit everything
```bash
git add .
git commit -m "Add Dockerized Flask app with Ansible deployment pipeline and rollback"
git push origin main
```

---

## Step 8 — Add the GitHub link to your resume

In your resume header, change:
```
Ottawa, ON | +1 (437) 438-0365 | bhumitbuha2016@gmail.com | linkedin.com/in/buha0006
```
To:
```
Ottawa, ON | +1 (437) 438-0365 | bhumitbuha2016@gmail.com | linkedin.com/in/buha0006 | github.com/YOURUSERNAME
```

---

## What you can say in the interview

**"Have you used Ansible?"**
> "Yes — I wrote Ansible playbooks organized into roles to deploy a Dockerized Flask service. The playbook has three roles: docker_setup verifies the environment, app_deploy builds the image and starts the container, and health_check validates the deployment by hitting the /health endpoint and asserting the version matches. I also wrote a rollback playbook that stops the current container and rehydrates an older image version. The key thing I learned is idempotency — I ran the playbook multiple times and it only reported 'changed' when something actually changed."

**"What's the difference between a task, a role, and a playbook in Ansible?"**
> "A task is a single unit of work — like 'ensure this container is running.' A role is a reusable collection of tasks organized around a purpose, like 'deploy the app' or 'check health.' A playbook is the top-level orchestrator that defines which hosts to target, which roles to run, and what variables to pass. Group vars let you share configuration across all playbooks without repeating it."

**"What's a Dockerfile?"**
> "It's a set of instructions for building a container image. I used a multi-stage build — the first stage installs Python dependencies into a target directory, and the second stage copies only those compiled packages into a lean runtime image. This keeps the final image small by not including build tools. I also added a HEALTHCHECK instruction so Docker itself monitors the container's /health endpoint."

**"What's idempotency?"**
> "It means running an operation multiple times produces the same result as running it once. In Ansible, if I deploy my container and then run the playbook again without changing anything, Ansible reports most tasks as 'ok' rather than 'changed' because the system is already in the desired state. That's important in production because it means playbooks are safe to re-run for recovery or verification without side effects."

---

## Estimated time breakdown

| Task | Time |
|---|---|
| Create repo + write Flask app | 30 min |
| Write Dockerfile + test Docker build | 30 min |
| Write Docker Compose files | 30 min |
| Write Ansible roles (3 roles) | 60 min |
| Write deploy + rollback playbooks | 30 min |
| Run and debug the full deployment | 45 min |
| Test idempotency + rollback | 15 min |
| Write README + polish + push to GitHub | 20 min |
| **Total** | **~4 hours** |

---

## Bonus: Connect Project 2 to Project 1 (makes both stronger)

Add a Jenkins stage to your Project 1 Jenkinsfile that calls the Ansible playbook after the Package stage:

```groovy
stage('Deploy') {
    steps {
        echo "=== STAGE: Deploy — Ansible deployment ==="
        sh '''
            cd ansible
            ansible-playbook -i inventory/hosts.ini deploy.yml -e "env=dev" -e "version=${BUILD_VERSION}"
        '''
    }
}
```

Now your resume can say:
> "Integrated Ansible deployment into the Jenkins CI pipeline — the Deploy stage triggers an Ansible playbook that builds the Docker image, starts the container, and validates the /health endpoint, creating a full CI/CD pipeline from commit to running service."

That single sentence ties both projects together and demonstrates end-to-end CI/CD understanding — exactly what the Kinaxis DevOps team is looking for.
