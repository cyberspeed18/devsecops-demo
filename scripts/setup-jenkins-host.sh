#!/usr/bin/env bash
# Prepare an Ubuntu Jenkins host (Jenkins installed with apt) to run the demo pipelines.
# Run on the Jenkins machine:  bash scripts/setup-jenkins-host.sh
set -euo pipefail

sudo apt-get update
sudo apt-get install -y docker.io git curl
sudo systemctl enable --now docker

# let the jenkins user talk to Docker, then restart Jenkins so it picks up the group
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins

# pre-pull the images used by the pipelines (saves time on the first build)
for img in \
  node:20 node:20-alpine python:3.12-slim \
  zricethezav/gitleaks:latest semgrep/semgrep:latest hadolint/hadolint:latest \
  aquasec/trivy:latest anchore/syft:latest curlimages/curl:latest \
  ghcr.io/zaproxy/zaproxy:stable sonarsource/sonar-scanner-cli:latest
do
  sudo docker pull "$img"
done

echo "--- verify: jenkins user can run docker ---"
sudo -u jenkins docker ps
echo "OK"
