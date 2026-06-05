# GitHub Actions Server Preflight

Status: first staging/server readiness workflow.
Last updated: 2026-06-05.

This runbook explains the manual GitHub Actions preflight that verifies SSH connectivity and basic host readiness before any BANXUM deployment workflow is enabled.

The current server is shared with another project. The preflight workflow is intentionally read-only. It must not stop services, restart containers, prune Docker resources, write deployment directories, or change system packages.

## Workflow

Workflow file:

- `.github/workflows/server-preflight.yml`

Trigger:

- Manual only, through `workflow_dispatch`.

The workflow:

- validates the required SSH secrets exist.
- creates a temporary private key on the GitHub runner.
- trusts the host key with `ssh-keyscan`.
- connects to the server over SSH.
- prints a small readiness report.
- does not modify the remote server.

## Required GitHub Actions Secrets

Create these secrets in the GitHub repository Actions secrets.

- `BANXUM_SSH_HOST`: server host or IP, host only.
- `BANXUM_SSH_USER`: SSH user, currently `ec2-user`.
- `BANXUM_SSH_PORT`: SSH port, usually `22`.
- `BANXUM_SSH_PRIVATE_KEY`: full private key content for the deployment SSH key.

Repository-level secrets are enough for the first read-only preflight. Later, when GitHub permissions allow managing Environments, move these into `staging` and `production` environment secrets so each environment can use separate values.

Attempted automated secret setup from the local GitHub CLI on 2026-06-05 failed because the currently authenticated token cannot write repository or environment Actions secrets. Add the secrets manually in GitHub, or re-authenticate `gh` with sufficient repository administration/Actions-secret permissions.

## How To Run

1. Open GitHub repository.
2. Go to `Settings -> Secrets and variables -> Actions`.
3. Add the four repository secrets above.
4. Go to `Actions -> Server Preflight`.
5. Click `Run workflow`.
6. Select `staging` for the input label.
7. Run.

Expected successful output includes:

- `ssh_connection_status=ok`.
- `remote_user=...`.
- `git_available=yes/no`.
- `docker_available=yes/no`.
- `compose_v2_available=yes/no`.
- disk and memory summary.
- common listening ports.

## Local Connection Test Result

Local read-only SSH preflight on 2026-06-05 before bootstrap:

- SSH connection: ok.
- Remote user: `ec2-user`.
- OS/kernel: Amazon Linux 2023 on ARM64.
- Git: not available.
- Docker: not available.
- Docker Compose v2: not available.
- Podman: not available.
- Node: not available.
- Python 3: available.
- Existing BANXUM directories in home or `/opt`: none found.
- Root disk: 60 GB total, about 44 GB available.
- Memory: about 8 GB total, about 5.8 GB available.
- Common web/app/db/cache ports checked by the preflight did not appear occupied.

Bootstrap performed on 2026-06-05:

- Installed only `git` and `docker` through Amazon Linux `dnf`.
- Did not run a system upgrade.
- Started and enabled Docker.
- Added `ec2-user` to the Docker group.
- Installed Docker Compose as the Docker CLI plugin under `/usr/local/lib/docker/cli-plugins/docker-compose` from the official Docker Compose GitHub release for Linux ARM64, after verifying the release SHA-256 checksum.
- Did not stop, restart, prune, or modify any arbitrage bot process/service.

Local read-only SSH preflight after bootstrap:

- Git: available, `git version 2.50.1`.
- Docker: available, Docker service active, `Docker version 25.0.14`.
- Docker Compose: available, `Docker Compose version v5.1.4`.
- Docker without sudo for `ec2-user`: yes.
- Running Docker containers: 0.
- BANXUM Docker containers: 0.
- Root disk: 60 GB total, about 44 GB available.
- Memory: about 8 GB total, about 5.7 GB available.
- Common web/app/db/cache ports checked by the preflight did not appear occupied.

## Shared-Server Safety Rules

Before enabling a real deploy workflow:

- Do not use `docker system prune`, `docker container prune`, `docker volume prune`, or global cleanup commands.
- Do not run `docker compose down` outside a BANXUM-specific project name.
- Use a unique Compose project name, for example `banxum_staging` and later `banxum_prod`.
- Use a dedicated deployment directory, for example `/opt/banxum/staging`, after confirming the server owner is comfortable with that path.
- Do not bind default local-development ports such as `5432`, `6379`, `9000`, `9001`, or `5173` on public interfaces.
- Prefer binding internal app ports to `127.0.0.1` only, then route public traffic through a reverse proxy.
- Do not install packages, Docker, Git, or reverse-proxy services until Garanta confirms this will not interfere with the arbitrage bot project.

## Next Step Before Deployment

The host now has Git, Docker, and Docker Compose available for `ec2-user`, so the next deploy workflow can use a BANXUM-only Docker Compose project.

The next safe infrastructure step is a deployment plan, reviewed before execution, that creates:

- A BANXUM-only deployment directory.
- A BANXUM-only Docker Compose project name.
- BANXUM-specific `.env` files written from GitHub secrets.
- Separate staging/prod Compose project names, volumes, and ports.
- A reverse proxy/TLS plan once the domain is available.

The deploy workflow must only touch BANXUM paths and BANXUM Compose project names.
