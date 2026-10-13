# L20 · Deployment: Pulumi — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166045/) · Tutorial: [`dlops-io/cheese-app-v3`](https://github.com/dlops-io/cheese-app-v3) `main` @ [`3ecef56`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a) (README sections "Deployment to GCP (Manual)" and "Deployment to GCP (Single VM Instance)"; not branch `cluster-updates`, see §7) · Colab: none for this lecture · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 把 L18 的 cheese app（Next.js frontend、FastAPI `api-service`、ChromaDB vector DB、一次性的 `vector-db-cli` loader）部署到**一台** Compute Engine VM 上，前面挡一个 nginx reverse proxy（port 80）。做两遍：(A) **手动**：image push 到 Docker Hub，在 console 里点出一台 N2D VM，SSH 进去敲大约 20 条命令（其中 11 条 `docker`）；(B) **用 Pulumi 写成 code**：laptop 上跑一个 deployment container，里面两个 Pulumi project：`deploy_images`（build `linux/amd64` image，push 到 Artifact Registry，tag 是 timestamp）和 `deploy_single_vm`（VPC、3 条 firewall rule、50 GB data disk、`n2d-standard-2` Ubuntu 22.04 VM，SSH 进去 provision，再用 Docker-over-SSH 起 5 个 container）。最后得到 `http://<instance_ip>/`、GCS bucket 里的一份 state，和一条能全删的 `pulumi destroy`。
- **Idea 1 · IaC 是 declarative：** Part A 是 imperative recipe（"点这个、跑那个"）。Pulumi 的 Python program 只描述 end state；跑 `__main__.py` 只是 *register* resource，每个 constructor 立刻返回 Output，真正的创建由 engine 按 dependency 顺序、并行去做。
- **Idea 2 · engine loop：** `pulumi up` = program → resource graph → 和 state 做 diff（`--refresh` 先去 cloud 读一遍 reality）→ plan（`+` create、`~` update、`+-` replace、`-` delete）→ 调 provider（gcp、command、docker、docker-build）。三棵树：desired（code）、state（bucket）、reality（cloud）。state 只是 Pulumi 的记忆：删了 state，VM 照样跑、照样计费。
- **Idea 3 · project / stack / config / backend：** 两个 project（`deploy-images`、`deploy-single-vm`），stack 都叫 `dev`。`pulumi config set` 改的是你 git checkout 里的 `Pulumi.dev.yaml`。state 存在 self-managed GCS backend `gs://<proj>-pulumi-state-bucket`；passphrase 是空的（`Dockerfile:51`），真正的保护是谁能读这个 bucket。
- **Idea 4 · Output、DAG、StackReference：** VM 的 IP 是一个 `Output`，要 `.apply` 才拿得到；把 Output 传给别的 resource 就是 implicit dependency。`deploy_images` 每跑一次就生成新的 timestamp tag，`deploy_single_vm` 用 `StackReference("organization/deploy-images/dev")` 读这些 tag，于是 container 被 replace。所以"发新版本" = 先 `up` images，再 `up` VM；用 `:latest` 的话 Pulumi 看不到 diff，永远不会 redeploy。
- **Idea 5 · provider 和 identity：** `remote.Command` 是 escape hatch，`create` script 只跑一次，所以 script 必须 idempotent（`blkid … || mkfs.ext4`）。Docker provider 的 `host` 是 `ssh://sa_…@<ip>`：laptop 上的 Pulumi 通过 SSH tunnel 控制 VM 上的 Docker daemon。两个 service account：`deployment`（建 infra，同时也是 VM 的 runtime SA）和 `gcp-service`（app 调 Vertex AI 用）。SSH user 是 OS Login 分配的 `sa_<数字>`。nginx 的 `proxy_pass http://api-service:9000/;` 末尾那个 `/` 会把 `/api-service` prefix 剥掉；L22 的 K8s ingress 不剥，所以 v3 的 API 多了 `ROOT_PATH`。
- **最费时间的坑：** ① Artifact Registry 的 `cheese-app-repository` 没有任何 code 或 README step 去建，第一次 push 就报 `name unknown`：先跑 `gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us`。② `ssh-keygen` 一定要空 passphrase（Enter 两次）；`security:ssh_user` 填你自己 `gcloud compute os-login ssh-keys add` 输出里的 `sa_…`，不是 README 里 instructor 的 `sa_100110341521630214262`，`gcp:project` 也要换成你的 project ID。③ `secrets/` 文件夹放在 repo 文件夹**旁边**（`src/deployment` 往上三层），不是 repo 里面。④ Apple Silicon 上全是 amd64 emulation，api-service（带 TensorFlow）要 build 几十分钟，可能撞上 30 min timeout，重跑一次（有 cache）就好。
- **deploy 成功但 chat 不工作：** code 里写死的 `gemini-2.0-flash-001` 已经在 2026-06-01 retired，`/api-service/status` 能返回 `{"version":"3.0"}`，但 chat 会失败，要把 `GENERATIVE_MODEL` 改成现役 model（比如某个 `gemini-2.5-flash` 版本）再 redeploy。v3 的 `/docs` 看不到任何 API（被 outer app 占了），检查用 `/status`。
- **做完要删：** 在 `deploy_single_vm` 里跑 `pulumi destroy --stack dev --refresh -y`（container、VM、两块 disk、firewall、VPC、IP 全删）；Artifact Registry 里的 image 是 `retain_on_delete=True`，destroy 不删，要 `gcloud artifacts repositories delete cheese-app-repository --location=us`；Part A 手动建的 VM README 没让你删，去 console Delete；state bucket 最后删；课程结束时去 IAM 删掉 service-account 的 JSON key。

## At a glance

**What you build.** The cheese app from L18 (Next.js frontend, FastAPI `api-service`, ChromaDB and a one-shot `vector-db-cli` loader) running on one Compute Engine VM behind an nginx reverse proxy on port 80, deployed first by hand (Docker Hub images, a VM clicked together in the console, about 20 shell commands over SSH) and then as code with two Pulumi projects run from a deployment container on your laptop. `deploy_images` builds timestamp-tagged `linux/amd64` images and pushes them to Artifact Registry; `deploy_single_vm` creates the VPC, firewall rules, data disk and VM, provisions the VM over SSH and starts five containers through a Docker provider that talks to the VM's Docker daemon over SSH, leaving you a URL `http://<instance_ip>/`, a state file in a GCS bucket and one command (`pulumi destroy`) that removes it all.

**Time needed** (estimate). Part A: about 1–1.5 h, less if you skip your own Docker Hub push and run the public `dlops/...` images (§4 A2). Part B: about 2–3 h the first time: service accounts and keys, building the deployment image, `deploy_images` (the api-service image includes TensorFlow; under emulation on Apple Silicon expect tens of minutes) and `deploy_single_vm` (several minutes; `update-system` and the image pulls are the slow parts). Add about 1 h for the exercises.

**Prerequisites.**
- A GCP project with billing enabled, and its **project ID**. The committed scripts, the `Pulumi.dev.yaml` stack files and the README commands hardcode the instructor's `ac215-project`.
- Docker Desktop (or Docker Engine) with BuildKit. Nothing else is installed locally: gcloud, Pulumi, kubectl, Helm and uv live in the deployment image (`src/deployment/Dockerfile:28-55`). A macOS/Linux shell (WSL on Windows).
- Part A only: a Docker Hub account and an access token (README lines 19–21).
- APIs: Compute Engine, Service Usage, Cloud Resource Manager, Artifact Registry (README lines 231–234), plus the **Vertex AI API** for the running app.
- Credentials: two service accounts with JSON keys, `deployment.json` and `gcp-service.json`, in a `secrets/` folder **next to** the repo folder (§2).
- Background: L18 (cheese-app-v2 running as local containers), L10 (service accounts and the `secrets/` convention), L1–L2 (VMs, Docker on a VM), L14 (Artifact Registry, tags vs digests).

**What it costs.** The VM (`n2d-standard-2`) is about $0.08–0.09/hour, about $2/day, and the two 50 GB `pd-standard` disks about $4/month together; the ephemeral IP adds a small hourly charge. Artifact Registry stores several GB (TensorFlow in api-service), with a new tag on every `pulumi up`, at about $0.10/GB-month above the free tier. The state bucket costs cents; Vertex AI bills per token. The two surprise bills: the **Part A VM, which the README never tells you to delete**, and the registry images, which **survive** `pulumi destroy`. Details and prices: §2.

**Tear down, exactly** (details in §2 and §4 A10, B13):
1. Part A VM: Console → Compute Engine → VM instances → select it → **Delete**.
2. Part B, inside the deployment container, in `/app/deploy_single_vm`: `pulumi destroy --stack dev --refresh -y`. It deletes the containers through SSH, then the VM, data disk, firewalls and VPC. Checkpoint: `Resources: - N deleted`, and Compute Engine → VM instances is empty.
3. Artifact Registry images: `pulumi destroy` in `deploy_images` only removes them from state (`retain_on_delete=True`). Delete them in the console or with `gcloud artifacts repositories delete cheese-app-repository --location=us`.
4. The state bucket `<proj>-pulumi-state-bucket`: keep it while any stack still has resources; delete it last.
5. Docker Hub images from Part A: free, optional.
6. When the course ends: delete the service-account JSON keys in IAM. They are long-lived credentials.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site source `tutorials_demo.md:257-266`, "Lecture 20: Deployment: Pulumi", with two tutorials: "Deployment of the full app to GCP (Manual)" and "Deployment to GCP with Pulumi"), in `cheese-app-v3/README.md`:
  - [`#deployment-to-gcp-manual`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#deployment-to-gcp-manual), README lines 4–222
  - [`#deployment-to-gcp-single-vm-instance`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#deployment-to-gcp-single-vm-instance), README lines 225–383, including `#apis-to-enable-in-gcp-before-you-begin`, `#setup-docker-container-pulumi-docker-kubernetes`, `#ssh-setup`, `#deployment-single-vm-instance`, `#build-and-push-docker-containers-to-google-artifact-registry` and `#create-compute-instance-vm--deploy-containers`
  - [`#delete-the-compute-instance--persistent-disk`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#delete-the-compute-instance--persistent-disk), README lines 387–390
  - Lecture date: Nov 12 per the course schedule (`_modules/week-11.md:9-11`, which labels the entry "Lecture 19"; `tutorials_demo.md:257` numbers it 20).
- **Repositories used:**

| repo | branch | commit (full hash) | commit date | role |
|---|---|---|---|---|
| `dlops-io/cheese-app-v3` | `main` (default) | `3ecef56fea879ac480d260c0906cd95baf05179a` | Fri Nov 28 16:00:06 2025 -0500 | **the tutorial** |
| `dlops-io/cheese-app-v3` | `cluster-updates` | `e55178c0f66d8636d00e7deea7e744640bb8d595` | Thu Nov 20 22:45:10 2025 +0530 | K8s experiments, mostly for L22 (see §7) |
| `dlops-io/cheese-app-v2` | `main` (default) | `14f2a1420b43e9f24e977a9e67b53d7e2614013d` | Sun Nov 16 09:16:15 2025 -0500 | the previous app version (L18), used for the v2 → v3 diff |
| `dlops-io/cheese-app-v3` | `pipenv` | `0012c9a512b1a266f4c87fad09d84a3b52470f5b` | Wed Apr 23 08:26:16 2025 -0400 | old Ansible-based version (an ancestor of `main`), used only for the Ansible → Pulumi mapping in §7 |
| `dlops-io/cheese-app-v4` | `main` (default) | `033f18713b9e1e7985a3080e85edab3ff01cefef` | Tue Dec 2 14:13:03 2025 -0500 | used only to confirm that v4's `deploy_images/` and `deploy_single_vm/` are identical to v3's |

- **Path convention.** Every `path:line` in this guide is relative to the `cheese-app-v3/` repository root at the `main` commit above unless another repo is named. Short names are used where the folder is clear:
  - `src/deployment/`: `docker-shell.sh`, `docker-entrypoint.sh`, `Dockerfile` (unless another folder is named), `docker_config.json`, and the folders `deploy_images/`, `deploy_single_vm/`, `deploy_k8s/`; `nginx.conf` is `src/deployment/nginx-conf/nginx/nginx.conf`.
  - `src/deployment/deploy_single_vm/`: `create_instance.py`, `provision_instance.py`, `setup_containers.py`, `setup_webserver.py`, their `*_using_command.py` variants, and `Pulumi.dev.yaml` when cited without a folder.
  - `src/api-service/`: `api/service.py` and `api/utils/…` (`llm_rag_utils.py` and the other `llm_*_utils.py`). Under `src/frontend-react/`: `.env.production`, `Footer.jsx` (`src/components/layout/`), `DataService.js` (`src/services/`). `src/vector-db/`: `cli.py`.
  - Every reference was checked with `sed -n`/`grep -n` against the pinned commit. Code blocks headed `path:start-end` are copied mechanically from those exact line ranges; all 14 excerpts in §5 were re-verified line for line against the repo on 2026-10-13.
- **External sources:** Google's Vertex AI "Model versions" page (docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, last updated 2026-10-10) for the model retirement dates in §6 and §9; Chroma's cookbook ("Running Chroma") for the server image's persistence path.
- **Ed lesson:** not accessible when these sources were checked; the course site and the repositories were used instead.
- **Colab notebooks:** none for this lecture.

</details>

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept; replace `ac215-project`, `<YOUR GCP_PROJECT>` and the instructor's `sa_100110341521630214262` with your own values). Plain items are console clicks or checks. Items marked *(extra)* are not in the README; they come from §2, §4 and §6 of this guide. Part A runs on your laptop and then on the VM over SSH. Part B runs on your laptop and in the console up to `sh docker-shell.sh`, and inside the deployment container (prompt in `/app`) from then on.

### Before the README *(extra)*

- [ ] `git clone https://github.com/dlops-io/cheese-app-v3.git` — *(extra)* get the code. If you use this workspace's `tools/sync_tutorials.py`, the clone is `tutorials/cheese-app-v3`.
- [ ] `git -C cheese-app-v3 rev-parse HEAD` — *(extra)* compare with `3ecef56fea879ac480d260c0906cd95baf05179a`; a different hash means the instructor has updated the repo since this guide was made.
- [ ] *(extra)* Create a `secrets/` folder **next to** the repo folder, not inside it: `docker-shell.sh:9` looks three levels up from `src/deployment`. With a clone at `~/Desktop/AC215/cheese-app-v3` that is `~/Desktop/AC215/secrets/`; with `tools/sync_tutorials.py` it is `tutorials/secrets/`.

### Deployment to GCP (Manual)

*Ensure you have all your container built and works locally* (README lines 10–16)
- [ ] vector-db: ChromaDB is up and running.
- [ ] api-service: go to `http://localhost:9000/docs` and make sure you can see the API Docs — in v3 this page says "No operations defined in spec!" (§9 erratum 4).
- [ ] `http://localhost:9000/status` — *(extra)* the reliable API check: `{"version":"3.0"}`.
- [ ] frontend-react: go to `http://localhost:3000/` and make sure you can see the home page.

*Push Docker Images to Docker Hub* (README lines 18–35)
- [ ] Sign up in Docker Hub and create an [Access Token](https://hub.docker.com/settings/security); open a new terminal.
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — stores your Docker Hub credentials in the local Docker config (prefer `--password-stdin`, so the token stays out of your shell history).
- [ ] *(extra)* Change `DOCKER_USERNAME="dlops"` to your Docker Hub user in `src/api-service/docker-hub.sh:11` (same line in `src/frontend-react/` and `src/vector-db/`); otherwise the push fails with "requested access to the resource is denied".
- [ ] `sh docker-hub.sh` — in `src/api-service`, outside the docker shell: recreates a buildx builder `multi-arch`, builds `linux/amd64,linux/arm64` and pushes.
- [ ] `sh docker-hub.sh` — in `src/frontend-react`: the production build (`Dockerfile`, not `Dockerfile.dev`), `linux/amd64` only.
- [ ] `sh docker-hub.sh` — in `src/vector-db`: builds and pushes the `vector-db-cli` image.
- [ ] `docker buildx use default` — *(extra)* switches back from the `multi-arch` builder, which `--use` made your default in every terminal (§6 gotcha 3).

*Install Docker on VM* (README lines 39–51)
- [ ] Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances): defaults, except Machine Type **N2D**, disk size **50 GB** (OS & Storage), and **Allow HTTP traffic** + **Allow HTTPS traffic** (Networking).
- [ ] SSH into your newly created instance.
- [ ] `curl -fsSL https://get.docker.com -o get-docker.sh` — downloads Docker's install script.
- [ ] `sudo sh get-docker.sh` — installs Docker Engine on the VM.
- [ ] `sudo docker --version` — prints a version.

*Create folders and give permissions* (README lines 53–68)
- [ ] `sudo mkdir persistent-folder` — for the api-service's `/persistent`.
- [ ] `sudo mkdir secrets` — for `gcp-service.json`.
- [ ] `sudo mkdir -p conf/nginx` — for `nginx.conf`.
- [ ] `sudo chmod 0777 persistent-folder` — world-writable (demo-grade).
- [ ] `sudo chmod 0777 secrets` — world-writable (demo-grade).
- [ ] `sudo chmod -R 0777 conf` — world-writable, recursively.

*Add secrets file* (README lines 70–75)
- [ ] `echo '<___Json Key___>' > secrets/gcp-service.json` — paste the `gcp-service` key's JSON in place of the placeholder (works because the key contains no `'`).

*Create Docker network* (README lines 78–81)
- [ ] `sudo docker network create cheese-app-network` — a bridge network, so containers find each other by name.

*Run vector-db* (README lines 83–98)
- [ ] `sudo docker pull chromadb/chroma:latest` — the unpinned ChromaDB server image.
- [ ] `sudo docker stop cheese-app-vector-db || true` — stops an old container if there is one.
- [ ] `sudo docker rm cheese-app-vector-db || true` — removes it.
- [ ] Start ChromaDB (detached, port 8000, `--restart always`):
  ```
  sudo docker run -d \
      --name cheese-app-vector-db \
      --network cheese-app-network \
      -p 8000:8000 \
      -e IS_PERSISTENT=TRUE \
      -e ANONYMIZED_TELEMETRY=FALSE \
      -v ./docker-volumes/chromadb:/chroma/chroma \
      --restart always \
      chromadb/chroma
  ```

*Run vector-db-cli* (README lines 100–113)
- [ ] `sudo docker pull dlops/cheese-app-vector-db-cli` — the loader image.
- [ ] Download the pre-computed embeddings and load them (change `GCP_PROJECT=ac215-project` to your project); it logs "Processing file:" lines and exits:
  ```
  sudo docker run --rm \
      -e GCP_PROJECT=ac215-project \
      -e CHROMADB_HOST=cheese-app-vector-db \
      -e CHROMADB_PORT=8000 \
      -e GOOGLE_APPLICATION_CREDENTIALS="/secrets/gcp-service.json" \
      -v "$(pwd)/secrets/":/secrets \
      --network cheese-app-network \
      dlops/cheese-app-vector-db-cli \
      cli.py --download --load --chunk_type recursive-split
  ```

*Run api-service* (README lines 115–145)
- [ ] Start the API (detached; without `-e DEV=1` the entrypoint runs production uvicorn):
  ```
  sudo docker run -d --name api-service \
  -v "$(pwd)/persistent-folder/":/persistent \
  -v "$(pwd)/secrets/":/secrets \
  -p 9000:9000 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-service.json \
  -e GCS_BUCKET_NAME=cheese-app-models \
  -e GCP_PROJECT=ac215-project \
  -e CHROMADB_HOST=cheese-app-vector-db \
  -e CHROMADB_PORT=8000 \
  --network cheese-app-network dlops/cheese-app-api-service
  ```
- [ ] Optional, interactive mode "like we did in development" (README lines 131–145): `--rm -ti` plus `-e DEV=1` drops you into a shell where you start the server with `uvicorn_server`. It reuses `--name api-service`, so stop and remove the detached container first.
  ```
  sudo docker run --rm -ti --name api-service \
  -v "$(pwd)/persistent-folder/":/persistent \
  -v "$(pwd)/secrets/":/secrets \
  -p 9000:9000 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-service.json \
  -e GCP_PROJECT=ac215-project \
  -e GCP_PROJECT_ID=ac215-project \
  -e CHROMADB_HOST=cheese-app-vector-db \
  -e CHROMADB_PORT=8000 \
  -e GCS_BUCKET_NAME=cheese-app-models \
  -e DEV=1 \
  --network cheese-app-network dlops/cheese-app-api-service
  ```
- [ ] `curl localhost:9000/status` — *(extra)* on the VM: `{"version":"3.0"}`.

*Run frontend* (README lines 147–151)
- [ ] `sudo docker run -d --name frontend -p 3000:3000 --network cheese-app-network dlops/cheese-app-frontend-react` — the production Next.js server on port 3000.
- [ ] `sudo docker container ls` — *(extra)* `api-service` and `frontend` are running.

*Add NGINX config file* (README lines 153–214)
- [ ] Create `nginx.conf` (README lines 156–213) — routes `/api-service/` to `api-service:9000/` and everything else to `frontend:3000`. Quoting bug: the `log_format` lines contain single quotes, so the written file loses its log variables (§4 A8; fix in the next item).
  ```
  echo 'user  nginx;
  error_log  /var/log/nginx/error.log warn;
  pid        /var/run/nginx.pid;
  events {
      worker_connections  1024;
  }
  http {
      include       /etc/nginx/mime.types;
      default_type  application/octet-stream;
      log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                        '$status $body_bytes_sent "$http_referer" '
                        '"$http_user_agent" "$http_x_forwarded_for"';
      access_log  /var/log/nginx/access.log  main;
      sendfile        on;
      tcp_nopush     on;
      keepalive_timeout  65;
  	types_hash_max_size 2048;
  	server_tokens off;
      gzip  on;
  	gzip_disable "msie6";

  	ssl_protocols TLSv1 TLSv1.1 TLSv1.2; # Dropping SSLv3, ref: POODLE
      ssl_prefer_server_ciphers on;

  	server {
  		listen 80;

  		server_name localhost;

  		error_page   500 502 503 504  /50x.html;
  		location = /50x.html {
  			root   /usr/share/nginx/html;
  		}
  		# API 
  		location ^~ /api-service/ {
  			# Remove the rewrite since we want to preserve the full path after /api-service/
  			proxy_pass http://api-service:9000/;
  			proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  			proxy_set_header X-Forwarded-Proto $scheme;
  			proxy_set_header X-Real-IP $remote_addr;
  			proxy_set_header Host $http_host;
  			proxy_redirect off;
  			proxy_buffering off;
  		}
  		
  		# Frontend
  		location / {
  			proxy_pass http://frontend:3000;
  			proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  			proxy_set_header X-Forwarded-Proto $scheme;
  			proxy_set_header X-Real-IP $remote_addr;
  			proxy_set_header Host $http_host;
  			proxy_redirect off;
  			proxy_buffering off;
  		}
  	}
  }
  ' > conf/nginx/nginx.conf
  ```
- [ ] *(extra)* Better: write the same config with a quoted heredoc (`cat > conf/nginx/nginx.conf <<'EOF'` … `EOF`), or `scp` the repo's `src/deployment/nginx-conf/nginx/nginx.conf` to the VM.

*Run NGINX Web Server* (README lines 216–222)
- [ ] `sudo docker run -d --name nginx -v $(pwd)/conf/nginx/nginx.conf:/etc/nginx/nginx.conf -p 80:80 --network cheese-app-network nginx:stable` — the reverse proxy on port 80.
- [ ] Open `http://<Your VM IP Address>/` — the frontend loads. Chat additionally needs a Vertex AI model that still exists (§9 erratum 20).

*Tear down* *(extra; missing from the README)*
- [ ] *(extra)* Delete the VM: Compute Engine → VM instances → Delete. Left running it costs about $2/day.

### Deployment to GCP (Single VM Instance)

*API's to enable in GCP before you begin* (README lines 229–234)
- [ ] Search for and enable: Compute Engine API, Service Usage API, Cloud Resource Manager API, Artifact Registry API.
- [ ] *(extra)* Check that the Vertex AI API is enabled too (the api-service calls Gemini and `text-embedding-004`).

*Setup GCP Service Account for deployment* (README lines 236–259)
- [ ] IAM & Admin → Service accounts → create `deployment` with Compute Admin, Compute OS Login, Artifact Registry Administrator, Kubernetes Engine Admin, Service Account User, Storage Admin.
- [ ] Actions ⋮ → Create key → JSON; copy the file into `secrets/` and rename it `deployment.json`.
- [ ] Create `gcp-service` with Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader.
- [ ] Create its JSON key; copy it into `secrets/` and rename it `gcp-service.json`.

*Run `deployment` container* (README lines 265–280)
- [ ] Edit `export GCP_PROJECT="ac215-project" # Change to your GCP Project` (`src/deployment/docker-shell.sh:13`) to your project ID.
- [ ] cd into `deployment` — the folder is `src/deployment`.
- [ ] `ls ../../../secrets` — *(extra)* from `src/deployment`: `deployment.json` and `gcp-service.json` are there.
- [ ] `sh docker-shell.sh` — builds `cheese-app-deployment` for `linux/amd64`, starts it with the Docker socket, code and secrets mounted; the entrypoint logs in as the deployment SA, creates the state bucket if missing and runs `pulumi login gs://…`. You land at a bash prompt in `/app`.
- [ ] `gcloud --version` — the gcloud SDK in the toolbox.
- [ ] `pulumi version` — the Pulumi CLI.
- [ ] `kubectl version --client` — kubectl (used in L22).
- [ ] `gcloud auth list` — the active account is `deployment@<your-project>.iam.gserviceaccount.com`.
- [ ] `gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us` — *(extra)* creates the registry repository that `deploy_images` pushes to and that nothing else creates (§2, §9 erratum 1).

*Configuring OS Login for service account* (README lines 283–291)
- [ ] `gcloud compute project-info add-metadata --project <YOUR GCP_PROJECT> --metadata enable-oslogin=TRUE` — turns on OS Login for the project (project-wide metadata).

*Create SSH key for service account* (README lines 293–298)
- [ ] `cd /secrets` — the container's view of your host `secrets/` folder.
- [ ] `ssh-keygen -f ssh-key-deployment` — creates the key pair; **press Enter twice (empty passphrase)**, because Pulumi cannot type one.
- [ ] `cd /app` — back to `src/deployment` (the Pulumi programs).

*Providing public SSH keys to instances* (README lines 300–316)
- [ ] `gcloud compute os-login ssh-keys add --key-file=/secrets/ssh-key-deployment.pub` — registers the key with the deployment SA's OS Login profile; **copy the `username: sa_<digits>`** from the output.

*Deployment Setup* (README lines 318–322)
- [ ] Skip it: `inventory.yml` is a leftover from the old Ansible version and does not exist on `main` (§9 erratum 2).

*Build and Push Docker Containers to Google Artifact Registry* (README lines 327–345)
- [ ] cd into `deploy_images` — `/app/deploy_images`.
- [ ] `pulumi stack init dev` — creates the `dev` stack; its state goes to the GCS bucket.
- [ ] `pulumi config set gcp:project ac215-project` — use your project ID; writes `Pulumi.dev.yaml` in your checkout.
- [ ] `pulumi stack select dev` — *(extra)* instead of `init` if you get `stack 'dev' already exists`.
- [ ] `pulumi preview --stack dev --refresh` — shows the plan without changing anything.
- [ ] `pulumi up --stack dev --refresh -y` — builds the three images for amd64 and pushes them with timestamp tags; expect about `+ 4 created` and `Outputs:` with `cheese-app-api-service-tags` and others.

*Create Compute Instance (VM) & Deploy Containers* (README lines 347–383)
- [ ] cd into `deploy_single_vm` from the `deployment` folder — `cd ../deploy_single_vm`.
- [ ] `pulumi stack init dev` — the `dev` stack of the `deploy-single-vm` project, in the same state bucket.
- [ ] `pulumi config set gcp:project ac215-project` — your project ID.
- [ ] `pulumi config set security:ssh_user sa_100110341521630214262` — **your** `sa_…` username from OS Login.
- [ ] `pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com` — your project in the e-mail.
- [ ] `pulumi config` — *(extra)* check the three values before deploying.
- [ ] `pulumi preview --stack dev --refresh` — about 30 resources to create.
- [ ] `pulumi up --stack dev --refresh -y` — creates the network, firewalls, disk and VM, provisions it over SSH and starts the containers; ends with `Outputs:` including `instance_ip`.
- [ ] Go to `http://<instance_ip>/` — the footer shows "Frontend version: 1" and "API version: 3.0".
- [ ] `curl http://<instance_ip>/api-service/status` — *(extra)* `{"version":"3.0"}`.
- [ ] SSH into the server from the GCP console, or `ssh -i /secrets/ssh-key-deployment sa_…@<instance_ip>` — *(extra)* from the deployment container (the exported `ssh_command` omits `-i`).
- [ ] `sudo docker container ls` — the running containers.
- [ ] `sudo docker container logs api-service -f` — follow the API log (Ctrl-C to stop).
- [ ] `sudo docker container logs frontend -f` — follow the frontend log.
- [ ] `sudo docker container logs nginx -f` — follow the nginx log.
- [ ] `sudo docker exec -it api-service /bin/bash` — a shell inside the api-service container.
- [ ] `sudo docker exec -it nginx /bin/bash` — a shell inside the nginx container.

*Redeploy after a code change* *(extra, §4 B12)*
- [ ] *(extra)* `pulumi up --stack dev --refresh -y` in `deploy_images` (new tags), then in `deploy_single_vm`. Read the preview before `-y`: `frontend`, `vector-db-loader` and `api-service` show `+-` replace.

### Delete the Compute Instance / Persistent disk

*(README lines 387–390)*
- [ ] `pulumi destroy --stack dev --refresh -y` — run it **in `deploy_single_vm`**: deletes containers, VM, disk, firewalls and VPC in reverse dependency order.
- [ ] `gcloud artifacts repositories delete cheese-app-repository --location=us` — *(extra)* the images survive `pulumi destroy` (`retain_on_delete=True`).
- [ ] `pulumi stack rm dev` — *(extra, optional)* deletes a stack and its history; it also deletes that folder's `Pulumi.dev.yaml` unless you pass `--preserve-config`.
- [ ] *(extra)* Delete the state bucket `<proj>-pulumi-state-bucket` last, and the service-account JSON keys in IAM when the course ends.

---

## 1. What you build

You take the cheese app (a Next.js frontend, a FastAPI `api-service`, a ChromaDB vector DB and a one-shot `vector-db-cli` loader) and put it on **one Google Compute Engine VM** behind an **nginx reverse proxy** on port 80. You do it twice. First you do it **by hand**: push images to Docker Hub, click a VM together in the console, SSH in and type about 20 shell commands (11 of them `docker` commands, README lines 48–219). Then you do it **as code with Pulumi**, in two Pulumi projects run from a "deployment" container on your laptop. `deploy_images` builds the three images for `linux/amd64` and pushes them to **Artifact Registry** with timestamp tags. `deploy_single_vm` creates a VPC, three firewall rules, a 50 GB data disk and an `n2d-standard-2` Ubuntu 22.04 VM. It then provisions the VM over SSH (mounting the disk and installing Docker), uploads the `gcp-service` key, and starts the five containers through a **Docker provider that talks to the VM's Docker daemon over SSH**. Afterwards you have a URL `http://<instance_ip>/`, a state file in a GCS bucket that records everything that exists, and one command (`pulumi destroy`) that removes it all.

```
 YOUR LAPTOP  (Docker Desktop)
 +--------------------------------------------------------------------------------+
 | container "cheese-app-deployment"  (built --platform=linux/amd64, runs as root)|
 |   tools: gcloud, pulumi, kubectl, helm, uv, docker CLI, ssh                    |
 |   /app            <- src/deployment          (Pulumi programs live here)       |
 |   /secrets        <- ../../../secrets        (deployment.json, gcp-service.json,|
 |                                               ssh-key-deployment[.pub])        |
 |   /api-service /frontend-react /vector-db   <- build contexts                  |
 |   /var/run/docker.sock  ---> host Docker daemon (BuildKit does the builds)     |
 +-----+-------------------------------+------------------------------+----------+
       | pulumi login gs://...         | (1) cd deploy_images         | (2) cd deploy_single_vm
       v                               |     pulumi up                |     pulumi up
 +---------------------------+         v                              v
 | GCS bucket                |   +-------------------------------+   GCP APIs (Compute Engine)
 | <proj>-pulumi-state-bucket|   | Artifact Registry (multi-reg.)|   + SSH (pulumi-command)
 |  .pulumi/stacks/          |   | us-docker.pkg.dev/<proj>/     |   + Docker API over ssh://
 |   deploy-images/dev       |   |  cheese-app-repository/       |        |
 |   deploy-single-vm/dev    |   |   cheese-app-api-service:<ts> |        |
 +---------------------------+   |   cheese-app-frontend-react:<ts>       |
        ^ StackReference         |   cheese-app-vector-db-cli:<ts>|<--pull-+
        | "organization/deploy-  +-------------------------------+        |
        |  images/dev" (image tags flow from stack 1 to stack 2)          v
 +--------------------------------------------------------------------------------------+
 | VPC "cheese-app-network-<suffix>" (auto subnets)                                     |
 | firewall: tcp:80 -> tag http-server | tcp:443 -> tag https-server | tcp:22 -> all VMs|
 |            (all from 0.0.0.0/0)                                                      |
 |  +--------------------------------------------------------------------------------+  |
 |  | VM "cheese-app-demo-<suffix>"  n2d-standard-2, Ubuntu 22.04, us-central1-a      |  |
 |  |   runs as SA deployment@<proj>  | ephemeral external IP (STANDARD tier)         |  |
 |  |   boot disk 50 GB  | data disk 50 GB pd-standard mounted at /mnt/disk-1         |  |
 |  |   /srv/secrets/gcp-service.json      /conf/nginx/nginx.conf                     |  |
 |  |                                                                                |  |
 |  |   Docker bridge network "appnetwork"                                           |  |
 |  |   +---------+  /api-service/x -> /x  +-------------+  vector-db:8000 +-------+ |  |
 |  | ->| nginx   |---------------------->| api-service |---------------->|vector-| |  |
 |  | 80| :80,:443|                       | :9000       |                 |db     | |  |
 |  |   |         |  /  (everything else)  +------+------+                 |chroma | |  |
 |  |   |         |------------------>+----------+ |  /persistent ->      |:8000  | |  |
 |  |   +---------+                   | frontend | |  /mnt/disk-1/        +---^---+ |  |
 |  |                                 | :3000    | |  persistent            |      |  |
 |  |                                 +----------+ v                        | load |  |
 |  |                                   Vertex AI (Gemini, text-embedding)  |      |  |
 |  |                                   via /secrets/gcp-service.json  +----+----+ |  |
 |  |                                                                  |vector-db| |  |
 |  |                                                                  |-loader  | |  |
 |  |                                                                  |(rm=True)| |  |
 |  |                                                                  +---------+ |  |
 |  +--------------------------------------------------------------------------------+  |
 +--------------------------------------------------------------------------------------+
        ^
 Browser: http://<instance_ip>/            -> nginx -> frontend:3000
          http://<instance_ip>/api-service/... -> nginx strips prefix -> api-service:9000/...
```

Ports 3000, 8000 and 9000 are also published on the VM host (`setup_containers.py:114-119, 138-143, 213-218`), but the GCP firewall only opens 80/443/22, so the outside world reaches the app **only through nginx**.

---

## 2. Prerequisites and costs

### Accounts and local installs
- A GCP project with billing enabled. You need its **project ID**; the committed shell scripts (`src/deployment/docker-shell.sh:13`, `src/api-service/docker-shell.sh:11`, `src/vector-db/docker-shell.sh:9`), the `Pulumi.dev.yaml` stack files and the README commands hardcode the instructor's `ac215-project`. The Python Pulumi code itself reads the project from config.
- Docker Desktop (or Docker Engine) with BuildKit. Nothing else needs installing locally: gcloud, Pulumi, kubectl, Helm and uv all live in the deployment image (`src/deployment/Dockerfile:28-55`).
- For Part A (manual) only: a Docker Hub account and access token (README lines 19–21).
- macOS/Linux shell. `docker-shell.sh` uses `$(pwd)`; on Windows use WSL.

### GCP APIs to enable (README lines 231–234)
Compute Engine API, Service Usage API, Cloud Resource Manager API, Artifact Registry API. The running app also needs **Vertex AI API** (the api-service calls Gemini and `text-embedding-004`, `src/api-service/api/utils/llm_rag_utils.py:21-23`). You enabled it in earlier lectures. The state bucket needs Cloud Storage, which is on by default.

### Artifact Registry repository: missing from the README
`deploy_images` pushes to `us-docker.pkg.dev/{project}/cheese-app-repository` (`src/deployment/deploy_images/__main__.py:14-15`). **No code and no README step creates that repository.** `artifactregistry` is imported on line 4 but never used. Create it once, in the **`us` multi-region** to match the `us-docker.pkg.dev` host. This command is a suggested addition; it does not appear in the repo:
```
gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us
```

### Service accounts and keys (README lines 236–259)
| file (host) | path in deployment container | SA roles (README) | used by |
|---|---|---|---|
| `<parent-of-repo>/secrets/deployment.json` | `/secrets/deployment.json` = `$GOOGLE_APPLICATION_CREDENTIALS` (`src/deployment/docker-shell.sh:16`) | Compute Admin, Compute OS Login, Artifact Registry Administrator, Kubernetes Engine Admin, Service Account User, Storage Admin | gcloud login (`docker-entrypoint.sh:10`), Pulumi GCP provider, state bucket, image push, **and it is the VM's runtime SA** (`create_instance.py:135-145`) |
| `<parent-of-repo>/secrets/gcp-service.json` | `/secrets/gcp-service.json` | Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader | uploaded to the VM as `/srv/secrets/gcp-service.json` (`setup_containers.py:44-63`) and mounted into api-service and loader as `/secrets/gcp-service.json` with `GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-service.json` (`setup_containers.py:180-187, 220, 232-236`) |
| `<parent>/secrets/ssh-key-deployment` and `.pub` | `/secrets/ssh-key-deployment[.pub]` | registered to the deployment SA's OS Login profile (README line 302) | `create_instance.py:10-13` (pulumi-command SSH), `setup_containers.py:84-85` (Docker-over-SSH) |

### Environment variables and config the code expects
- Exported by `docker-shell.sh:13-17` and passed into the container (`:44-49`): `GCP_PROJECT`, `GCP_REGION` (`us-central1`), `GCP_ZONE` (`us-central1-a`), `GOOGLE_APPLICATION_CREDENTIALS`, `PULUMI_BUCKET` (`gs://$GCP_PROJECT-pulumi-state-bucket`), and `USE_GKE_GCLOUD_AUTH_PLUGIN=True`, which only matters for L22.
- Baked into the image: `PULUMI_CONFIG_PASSPHRASE=""` (`Dockerfile:51`). Stack secrets are encrypted with an **empty passphrase**.
- Read from the environment, not from stack config: `GCP_ZONE` (`deploy_single_vm/__main__.py:12`, `create_instance.py:32`), `GCP_REGION` (`create_instance.py:31`, `deploy_images/__main__.py:10`; in both files the resulting `location` variable is never used, but a missing variable still raises `KeyError`).
- Pulumi stack config: `gcp:project` (both stacks), `security:ssh_user` and `security:gcp_service_account_email` (`deploy_single_vm` only; read via `pulumi.Config("security").require(...)` at `create_instance.py:27-30`).

### What costs money, and how to switch it off
Prices are approximate on-demand list prices. Check the GCP pricing calculator for your region.

| resource (created by) | rough cost | how to remove |
|---|---|---|
| VM `n2d-standard-2` (`create_instance.py:38`) | about $0.08–0.09/hour, about $2/day | `pulumi destroy --stack dev --refresh -y` in `deploy_single_vm` |
| boot disk 50 GB + data disk 50 GB `pd-standard` (`create_instance.py:36,39,92-97`) | about $0.04/GB-month, about $4/month together | same destroy (the data disk is a stack resource and is **deleted** too) |
| ephemeral external IPv4 | small hourly charge while in use | same destroy |
| Artifact Registry images (several GB because api-service includes TensorFlow; a new tag on every `pulumi up`) | about $0.10/GB-month above the free tier | **not** removed by `pulumi destroy` in `deploy_images` (`retain_on_delete=True`, `deploy_images/__main__.py:31,51,70`). Delete in the console or with `gcloud artifacts repositories delete cheese-app-repository --location=us` (not in the repo) |
| GCS state bucket `<proj>-pulumi-state-bucket` (`docker-entrypoint.sh:15-20`) | cents | keep it while any stack exists; delete it last |
| Vertex AI calls (each chat/RAG request) | per token | stop the VM |
| **Part A manual VM** | same as the VM row | **the README never tells you to delete it.** Delete it in the console (Compute Engine → VM instances → Delete) |
| Docker Hub images (Part A) | free | optional |

Also delete the **service-account JSON keys** in IAM when the course ends. They are long-lived credentials.

---

## 3. Concepts this tutorial teaches

### 3.1 Infrastructure as Code (IaC): manual → script → declarative
- **Explanation.** Part A is an *imperative recipe*: "click this, run that". Pulumi is *declarative*: your Python program describes the end state (a VM of this size, these firewall rules, these containers), and the engine works out which API calls get the world there. The same program can create, update or destroy, and it lives in git next to the app.
- **Mental model.** Your code is a *blueprint*. Pulumi is a contractor that compares the blueprint with an *inventory list* (the state file) and the real building, and only does the difference.
- **Analogy.** Manual is cooking from memory. IaC is a recipe card plus a pantry inventory, so a second cook reproduces the dish exactly and can also "uncook" it (destroy).
- **Misconception.** "Pulumi Python runs the commands line by line, like a script." It does not. Running `__main__.py` only *registers* resources: each constructor returns immediately with Outputs. Creation happens asynchronously (it can start while your program is still running), in parallel, in dependency order, decided by the engine.
- **Course history.** The previous course version did the same five steps with Ansible playbooks (`deploy-create-instance.yml`, `deploy-provision-instance.yml`, … on the `pipenv` branch). The Pulumi modules map one-to-one onto them (see §7).

### 3.2 The Pulumi engine loop: program → graph → diff → provider calls
- **Explanation.** `pulumi up` runs your program and collects a graph of resources with URNs such as `…::gcp:compute/instance:Instance::cheese-app-demo`. It loads the last *state* (with `--refresh` it first asks the cloud what really exists), diffs desired against current, shows a plan (`+ create`, `~ update`, `+-` replace, `- delete`), and then calls **providers** (gcp, command, docker, docker-build) to carry out each step. `pulumi preview` runs only the plan step. `pulumi destroy` plans "delete everything" and runs the graph in reverse order.
- **Mental model.** Three trees: *desired* (from code), *state* (from the bucket), *reality* (from the cloud). `--refresh` syncs state with reality, and `up` moves reality to desired.
- **Analogy.** `git diff` and `git apply` for cloud resources.
- **Misconception.** "`pulumi up` re-runs everything each time." It only changes resources whose inputs changed. In this repo, though, *some inputs change on every run*: the timestamp tag at `deploy_images/__main__.py:13`. See 3.5.

### 3.3 Projects, stacks, config, state backends and secrets
- **Project** = a folder with `Pulumi.yaml`. Here there are two: `name: deploy-images` and `name: deploy-single-vm` (`deploy_images/Pulumi.yaml:1`, `deploy_single_vm/Pulumi.yaml:1`), both using `runtime: python` with `toolchain: uv`.
- **Stack** = one named instance of a project (`dev`; the repo also has stray `dev-test` and, for k8s, `ssl` stack files). Each stack has its own **config** file `Pulumi.<stack>.yaml` and its own **state**.
- **Config** = namespaced key/values. `gcp:project` is read by the GCP provider *and* by your code (`pulumi.Config("gcp").require("project")`). `security:ssh_user` uses an arbitrary namespace the authors made up. Set them with `pulumi config set …`, which **writes to the YAML file in your git checkout**.
- **State backend** = where the state JSON lives. These programs use a *self-managed* GCS backend (`pulumi login $PULUMI_BUCKET`, `docker-entrypoint.sh:23`), so there is no Pulumi Cloud account. State files are at `gs://<proj>-pulumi-state-bucket/.pulumi/stacks/<project>/<stack>.json`; the entrypoint lists that prefix at `:27`.
- **Secrets.** Values marked secret (`pulumi config set --secret …`, or provider inputs such as pulumi-command's `connection`, which carries your private key) are encrypted in config and state with the stack's secrets provider. Here that is the *passphrase* provider with `PULUMI_CONFIG_PASSPHRASE=""` (`Dockerfile:51`) and a salt committed in `Pulumi.dev.yaml:1`. In practice the encryption protects nothing: real protection comes from **who can read the bucket**.
- **Analogy.** Project = class, stack = instance, config = constructor arguments, state = the instance's memory dump, kept in a safe (the bucket).
- **Misconception.** "The state is the infrastructure." State is only Pulumi's *memory* of it. If you delete a container by hand, state is wrong until you `--refresh`. If you delete the state, Pulumi forgets the VM, and the VM keeps running and billing.

### 3.4 Outputs, `apply`, and the dependency DAG
- **Explanation.** Many values only exist after a resource is created, such as the VM's IP. Pulumi represents them as `Output[T]`, a promise. You transform them with `.apply(...)` (`create_instance.py:152-154` digs `nat_ip` out of `network_interfaces`; `setup_containers.py:81` builds `ssh://user@ip`). Passing an Output into another resource creates an **implicit dependency**. `opts=ResourceOptions(depends_on=[...])` adds **explicit** ones. `provision_instance.py` chains nine `remote.Command`s, each `depends_on` the previous one.
- **Mental model.** A DAG. The engine walks it and does independent branches in parallel. For example, the frontend container (depends only on the network and `create_dirs`, `setup_containers.py:125-128`) can start while the loader is still running.
- **Analogy.** A kitchen ticket rail: a dish cannot be plated before its sauce is done, but two sauces can cook at once.
- **Misconception.** "`print(instance_ip)` shows the IP." It prints an Output object. Use `pulumi.export` (`deploy_single_vm/__main__.py:30`) or `.apply`.

### 3.5 Immutable image tags and cross-stack references
- **Explanation.** `deploy_images` tags every image with a timestamp computed when the program runs (`deploy_images/__main__.py:13`), pushes it (`push=True`, `:29`), and exports the tag list (`:35`). `deploy_single_vm` reads those exports through `pulumi.StackReference("organization/deploy-images/dev")` (`setup_containers.py:27-31`) and uses `tags[0]` as the container image. A new tag forces the Docker provider to replace the container, so "deploy a new version" = "`up` images, then `up` VM".
- **Mental model.** Two stacks joined by a pipe that carries one fact: *which image versions are current*.
- **Analogy.** A bakery stamps each batch with a date. The shop shelf always takes the newest dated batch rather than "the bread".
- **Misconception.** "Use `:latest`, it's simpler." With `:latest` the desired state never changes, so Pulumi sees no diff and never redeploys. This is also why the `chromadb/chroma:latest` and `nginx:stable` containers never update on their own.
- **Side effect.** Because the timestamp is new on *every* run, `pulumi preview` in `deploy_images` always shows three updates and every `up` rebuilds and pushes. BuildKit's cache keeps the rebuild cheap, but registry storage grows.

### 3.6 Providers as drivers, including the "escape hatch" and Docker-over-SSH
- **gcp** (`pulumi_gcp`): Network, Firewall, Disk, Instance, `get_image` (`create_instance.py:45-149`). This is a real declarative API, so Pulumi can read state back.
- **command** (`pulumi_command.remote`): runs shell scripts over SSH (`Command`) and copies files (`CopyToRemote`). This is an **escape hatch**: Pulumi only knows "I ran this `create` script once". It cannot see the VM's actual packages. These resources have no `delete`/`update` scripts, so they do not re-run unless their inputs or `triggers` change (`setup_webserver.py:53,66,111`). Scripts therefore have to be **idempotent** (`blkid … || mkfs.ext4`, `groupadd docker || true`, `if ! grep -q '/mnt/disk-1' /etc/fstab; then echo … | sudo tee -a /etc/fstab; fi`).
- **docker** (`pulumi_docker`): a provider instance whose `host` is `ssh://sa_…@<ip>` (`setup_containers.py:79-98`). Pulumi on your laptop talks to the **VM's** Docker daemon through an SSH tunnel, using the `ssh` binary installed in the deployment image (`Dockerfile:12`). Containers become first-class resources that can be diffed and replaced.
- **docker-build** (`pulumi_docker_build`): BuildKit builds with `platforms=[LINUX_AMD64]` and `push=True`, run on your **host's** Docker daemon through the mounted socket (`docker-shell.sh:35`).
- **Misconception.** "The deployment container builds images inside itself." It drives the host daemon through `/var/run/docker.sock` ("Docker-out-of-Docker"). That is why the build contexts are mounted at `/api-service` etc. (`docker-shell.sh:41-43`) and referenced as `../../api-service` from `/app/deploy_images`.

### 3.7 Identity: who is authenticated where
- **Laptop → GCP APIs:** the deployment SA key (`/secrets/deployment.json`), activated by `gcloud auth activate-service-account` (`docker-entrypoint.sh:10`) and read by Pulumi providers through `GOOGLE_APPLICATION_CREDENTIALS`.
- **Laptop → registry (push):** Docker `credHelpers` → `gcloud` (`docker_config.json:2-5`, mounted as `/root/.docker/config.json`, `docker-shell.sh:39`).
- **Laptop → VM shell:** SSH key `ssh-key-deployment`, registered to the deployment SA's **OS Login** profile (README lines 286, 302). The Linux username is `sa_<numeric id>`, the value you put in `security:ssh_user`. With OS Login on, the instance metadata `ssh-keys` (`create_instance.py:133`) is ignored, and `sudo` works because Compute Admin includes OS *Admin* Login permission. "Service Account User" is needed both to log in to a VM that runs as an SA and to attach the SA to the VM.
- **VM → registry (pull):** the Docker provider supplies registry auth for `us-docker.pkg.dev` (`setup_containers.py:92-96`), resolved from the deployment container's Docker config, i.e. as the deployment SA. The `gcloud auth configure-docker` calls on the VM (`provision_instance.py:145-146`, `setup_containers.py:59-60`) run as the SSH user, not root, so they only help a manual `docker pull` run *without* `sudo` (the user is in the `docker` group). `setup_containers.py:59` also switches that user's gcloud identity to the `gcp-service` SA. A `sudo docker pull` reads root's Docker config instead and gets no credential helper.
- **Containers → Vertex AI:** the `gcp-service` key mounted at `/secrets/gcp-service.json`.
- **Misconception.** "One service account is enough." It would work, but the split is deliberate: a powerful SA that *builds infrastructure* and a narrow SA that the *running app* uses. (Note that the VM itself still runs as the powerful SA, `Pulumi.dev.yaml:5`. That is a least-privilege smell worth noticing.)

### 3.8 Reverse proxy, path prefixes and `ROOT_PATH`
- **Explanation.** The browser only knows one origin, `http://<ip>`. The frontend is built with `NEXT_PUBLIC_BASE_API_URL=/api-service` (`src/frontend-react/.env.production:2`, copied in at build time by `src/frontend-react/Dockerfile:28`), so it calls `/api-service/podcasts/…`. Nginx matches `location ^~ /api-service/` and forwards to `proxy_pass http://api-service:9000/;`. Because `proxy_pass` ends with a `/`, nginx **replaces the matched prefix**, so FastAPI receives `/podcasts/…`. Everything else (`location /`) goes to `frontend:3000`. Container names resolve as hostnames because all containers share the `appnetwork` bridge.
- **The `ROOT_PATH` twist (new in v3).** `api/service.py` now mounts the routes under `ROOT_PATH` (`:13`, `:49-50`). On the single VM `ROOT_PATH` is unset (`""`) because nginx already stripped the prefix. On Kubernetes (L22) the ingress does *not* strip it, so `deploy_k8s/setup_containers.py:310-311` sets `ROOT_PATH=/api-service`.
- **Analogy.** A hotel receptionist: "Room service, extension 9000" is routed to the kitchen, and the kitchen hears only "extension 9000".
- **Misconception.** "Opening port 9000 in the firewall would be simpler." It would expose the API on a second origin (`http://<ip>:9000`). Cross-origin calls only work here because the API allows every origin (`allow_origins=["*"]`, `api/service.py:19-25`), which is itself a smell. You would also need a second port secured with TLS, and the IP would have to be baked into the frontend at build time (`NEXT_PUBLIC_*` values are compiled in).

---

## 4. Step-by-step walkthrough

### Part A: manual deployment (README lines 4–222)

**A0. Check that everything runs locally (README lines 10–16).**
- Action: have the v2/v3 containers running locally: ChromaDB, api-service at `http://localhost:9000/docs`, frontend at `http://localhost:3000/`.
- Checkpoint: the home page loads. Use **`http://localhost:9000/status` → `{"version":"3.0"}`** as the API check rather than `/docs`. In v3, `/docs` is served by the *outer* FastAPI app (`api/service.py:49`), which has no routes, so the page says "No operations defined in spec!". Reproduced with a minimal FastAPI test; see §9.

**A1. Log in to Docker Hub (README line 21).**
- Command: `docker login -u <USER NAME> -p <ACCESS TOKEN>`
- Under the hood: stores credentials in your local Docker config. Prefer `--password-stdin` so the token doesn't land in your shell history.
- If it fails: create an access token at hub.docker.com → Settings → Security.

**A2. Build, tag and push the three images (README lines 24–35): `sh docker-hub.sh` in `api-service`, `frontend-react` and `vector-db`.**
- Under the hood (`src/api-service/docker-hub.sh:20-35`): deletes and recreates a buildx builder named `multi-arch` with `--use`, builds for `linux/amd64,linux/arm64` (the frontend builds `linux/amd64` only, `src/frontend-react/docker-hub.sh:31,35`), then builds again with `--push`. The first build (`:31`) only warms the cache, because a docker-container builder does not load images locally.
- **Before running:** change `DOCKER_USERNAME="dlops"` (`src/api-service/docker-hub.sh:11`; same line in the other two scripts) to *your* Docker Hub user. Otherwise the push fails with "requested access to the resource is denied".
- Checkpoint: the images appear under your Docker Hub account.
- Side effect: `--use` makes `multi-arch` your default builder in every terminal. Run `docker buildx use default` afterwards (see §6).
- Shortcut: the later `docker run` commands use the public `dlops/...` images, so you can skip this step if you only want to practise the VM part.

**A3. Create the VM in the console (README lines 40–44).** Machine type N2D, 50 GB disk, tick "Allow HTTP traffic" and "Allow HTTPS traffic". This puts the default VPC firewall tags on the VM.

**A4. SSH in and install Docker (README lines 46–51).**
- Commands (README lines 48–49): `curl -fsSL https://get.docker.com -o get-docker.sh`, then `sudo sh get-docker.sh`.
- Checkpoint: `sudo docker --version` (README line 51) prints a version.

**A5. Folders, permissions, secret, network (README lines 61–81).**
```
sudo mkdir persistent-folder
sudo mkdir secrets
sudo mkdir -p conf/nginx
sudo chmod 0777 persistent-folder
sudo chmod 0777 secrets
sudo chmod -R 0777 conf
```
then `echo '<___Json Key___>' > secrets/gcp-service.json` (README line 74) and `sudo docker network create cheese-app-network` (README line 80).
- Pasting a JSON key inside single quotes works because the key contains no `'`. The `0777` permissions are demo-grade.

**A6. Start ChromaDB, then load it (README lines 86–112).**
```
sudo docker pull chromadb/chroma:latest
sudo docker stop cheese-app-vector-db || true
sudo docker rm cheese-app-vector-db || true
sudo docker run -d \
    --name cheese-app-vector-db \
    --network cheese-app-network \
    -p 8000:8000 \
    -e IS_PERSISTENT=TRUE \
    -e ANONYMIZED_TELEMETRY=FALSE \
    -v ./docker-volumes/chromadb:/chroma/chroma \
    --restart always \
    chromadb/chroma
```
```
sudo docker pull dlops/cheese-app-vector-db-cli
sudo docker run --rm \
    -e GCP_PROJECT=ac215-project \
    -e CHROMADB_HOST=cheese-app-vector-db \
    -e CHROMADB_PORT=8000 \
    -e GOOGLE_APPLICATION_CREDENTIALS="/secrets/gcp-service.json" \
    -v "$(pwd)/secrets/":/secrets \
    --network cheese-app-network \
    dlops/cheese-app-vector-db-cli \
    cli.py --download --load --chunk_type recursive-split
```
- Under the hood: `cli.py --download` fetches *pre-computed* embeddings from a GitHub release (`src/vector-db/cli.py:487`), and `--load` drops and re-creates the `recursive-split-collection` (`:286-292`).
- Change `GCP_PROJECT=ac215-project` to your project. Checkpoint: the loader logs "Processing file:" lines and exits.

**A7. Start api-service and frontend (README lines 118–127, 150).**
- Without `-e DEV=1` the entrypoint runs production uvicorn (`src/api-service/docker-entrypoint.sh:18-20, 32-38`).
- Optional (README lines 131–145): the interactive variant `sudo docker run --rm -ti --name api-service … -e DEV=1 …` drops you into a shell where you start the server with `uvicorn_server`. It uses the same `--name api-service`, so stop and remove the detached container first.
- Checkpoint: `sudo docker container ls` shows `api-service` and `frontend` running. `curl localhost:9000/status` on the VM returns `{"version":"3.0"}`.

**A8. nginx config and container (README lines 156–219).**
- Command (README line 219): `sudo docker run -d --name nginx -v $(pwd)/conf/nginx/nginx.conf:/etc/nginx/nginx.conf -p 80:80 --network cheese-app-network nginx:stable`
- **Quoting bug:** the `echo '…'` in README lines 156–213 wraps a config that itself contains single quotes (the `log_format` lines 165–167). Bash closes and reopens the quoted string there, so the `log_format` line is written as `log_format  main   - []  …;` with all `$variables` dropped (reproduced with a minimal test string). nginx still starts, but access logs lose their fields. Fix: write the file with a quoted heredoc (`cat > conf/nginx/nginx.conf <<'EOF' … EOF`) or `scp` the repo's `src/deployment/nginx-conf/nginx/nginx.conf`.

**A9. Open `http://<Your VM IP Address>/` (README line 222).** The frontend loads. Chat needs the `gcp-service` key to have Vertex AI access, **and** a generative model that still exists: the code calls `gemini-2.0-flash-001`, which Google's Vertex AI model-versions page lists as retired on 2026-06-01 (see §9).

**A10. Tear down (missing from README).** Delete the VM in the console. Leaving it running costs about $2/day.

### Part B: Pulumi deployment (README lines 225–390)

**B1. Enable the APIs (README lines 229–234).** Also check that Vertex AI API is enabled (see §2).

**B2. Create the two service accounts and keys (README lines 236–259).** Save them as `deployment.json` and `gcp-service.json` in the `secrets/` folder **next to** the repo folder (not inside it).
- Checkpoint: `ls ../../../secrets` from `src/deployment` shows both files.

**B2½. Create the Artifact Registry repository (not in the README).** Use the `gcloud artifacts repositories create … --location=us` command in §2. You can run it inside the deployment container after B3.

**B3. Start the deployment container (README lines 265–268).**
- Action: edit `export GCP_PROJECT="ac215-project" # Change to your GCP Project` (`src/deployment/docker-shell.sh:13`), then `cd src/deployment` and `sh docker-shell.sh`.
- Under the hood:
  - Builds `cheese-app-deployment` for `linux/amd64` (`docker-shell.sh:31`). On Apple Silicon it runs under emulation; expect a platform warning and `Architecture: x86_64` (`docker-entrypoint.sh:4`).
  - Mounts the socket, code, secrets and Docker config (`:34-50`).
  - The entrypoint activates the deployment SA (`docker-entrypoint.sh:10`), sets the project (`:11`), registers the Artifact Registry credential helper (`:13`), creates the state bucket if needed (`:15-20`), runs `pulumi login gs://…` (`:23`) and lists the stacks (`:27`).
- Checkpoint: "Bucket does not exist. Creating..." the first time, then "Logging into Pulumi using GCS bucket: gs://<proj>-pulumi-state-bucket" and a bash prompt in `/app`. A second terminal running `sh docker-shell.sh` attaches to the same container (`docker-shell.sh:23-25`) and re-runs the entrypoint (gcloud login, bucket check, `pulumi login`) inside it. The container is started with `--rm` (`docker-shell.sh:34`), so it disappears when the first shell exits; the state stays in the bucket.
- If it fails:
  - `ERROR: … Unable to read file [/secrets/deployment.json]` → the secrets folder is in the wrong place or misnamed.
  - `AccessDeniedException: 403` on `gsutil mb` → the SA lacks Storage Admin.
  - Bucket name taken → bucket names are global, so change `PULUMI_BUCKET` (`docker-shell.sh:17`).

**B4. Check the tools (README lines 270–278).**
```
gcloud --version
pulumi version
kubectl version --client
```
and `gcloud auth list` (README line 278). Checkpoint: the active account is `deployment@<your-project>.iam.gserviceaccount.com`.

**B5. Turn on OS Login for the project (README line 286).**
- Command: `gcloud compute project-info add-metadata --project <YOUR GCP_PROJECT> --metadata enable-oslogin=TRUE`

**B6. Create the SSH key (README lines 295–297).**
```
cd /secrets
ssh-keygen -f ssh-key-deployment
cd /app
```
- **Press Enter twice at the passphrase prompt (empty passphrase).** Pulumi's SSH connection (`create_instance.py:157-161`) and the Docker provider (`setup_containers.py:83-90`) cannot type a passphrase.

**B7. Register the public key with OS Login (README line 302).**
- Command: `gcloud compute os-login ssh-keys add --key-file=/secrets/ssh-key-deployment.pub`
- Checkpoint: YAML output with `username: sa_<digits>`. **Copy that username.** You need it in B9.

**B8. "Deployment Setup" (README lines 318–322): skip it.** It tells you to edit `inventory.yml`, a file from the old Ansible version that does not exist on `main` (§9).

**B9. Build and push the images with Pulumi (README lines 327–345).**
- Commands:
```
pulumi stack init dev
pulumi config set gcp:project ac215-project
```
  Replace `ac215-project` with your project ID. Run them from `/app/deploy_images`.
- Then (README lines 339 and 344): `pulumi preview --stack dev --refresh` and `pulumi up --stack dev --refresh -y`.
- Under the hood: three `docker_build.Image` resources (`deploy_images/__main__.py:23-71`) build `../../api-service`, `../../frontend-react` and `../../vector-db` (= `/api-service`, … inside the container) for amd64 on your host daemon, tag them `us-docker.pkg.dev/<proj>/cheese-app-repository/<name>:<YYYYmmddHHMMSS>`, and push.
- Checkpoint: three `docker-build:index:Image` resources created (the summary also counts the stack itself, so expect about `+ 4 created`), plus `Outputs:` with `cheese-app-api-service-ref`, `cheese-app-api-service-tags`, …. The repository shows three images in the console. The api-service build is the slowest because of TensorFlow; under emulation on Apple Silicon expect tens of minutes.
- If it fails:
  - `name unknown: Repository "cheese-app-repository" not found` → do B2½.
  - `denied: Permission "artifactregistry.repositories.uploadArtifacts" denied` → check the SA roles and that you are on the right project.
  - Timeout after 30 min → `CustomTimeouts(create="30m")` (`:30`); re-run, and the BuildKit cache makes the retry faster.
  - `stack 'dev' already exists` → run `pulumi stack select dev`.

**B10. Create the VM and deploy (README lines 347–367).**
- Commands: `cd ../deploy_single_vm`, then
```
pulumi stack init dev
pulumi config set gcp:project ac215-project
pulumi config set security:ssh_user sa_100110341521630214262
pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com
```
  Replace the project ID **and** the `sa_…` username with yours. Then `pulumi preview --stack dev --refresh` and `pulumi up --stack dev --refresh -y`.
- Under the hood, in dependency order (`deploy_single_vm/__main__.py:14-26`):
  1. `create_instance()`: VPC `cheese-app-network` with auto subnets (`create_instance.py:45-48`), firewalls for 80, 443 and 22 (`:51-89`), a `pd-standard` 50 GB disk (`:92-97`), the latest `ubuntu-2204-lts` image (`:100-103`), and the VM (`:106-149`) with that disk attached, an ephemeral STANDARD-tier IP, network tags `http-server`/`https-server`, and the deployment SA. Pulumi appends a random suffix to the physical names (no `name=` is given).
  2. `provision_instance()`: format the disk only if it has no filesystem (`provision_instance.py:24-32`), add an fstab entry and mount it at `/mnt/disk-1` (`:34-57`), stop the apt timers (`:60-70`), `apt-get upgrade` (`:73-81`), install base packages (`:83-98`), install Docker CE from Docker's repo (`:101-121`), `pip3 install requests docker` (`:124-131`), add the user to the docker group, `chmod 666 /var/run/docker.sock` (`:134-156`).
  3. `setup_containers()`: read image tags from the other stack (`setup_containers.py:27-31`), upload `gcp-service.json` to `/srv/secrets` (`:34-63`), create `/mnt/disk-1/{persistent,chromadb}` (`:66-76`), create the Docker-over-SSH provider (`:79-98`), the `appnetwork` bridge (`:101-106`) and the containers `frontend` (`:110-129`), `vector-db` (`:132-167`), `vector-db-loader` (`:170-205`, one-shot `rm=True`) and `api-service` (`:208-247`).
  4. `setup_webserver()`: `/conf/nginx` (`setup_webserver.py:31-39`), upload `nginx.conf` with checksum triggers (`:42-68`), the `nginx` container on 80/443 (`:71-102`), then `docker container restart nginx` (`:105-113`).
- Checkpoint: about 30 resources created, followed by `Outputs:` with `instance_ip`, `instance_name`, `persistent_disk_name`, `ssh_command`, `ssh_user` and `zone` (`deploy_single_vm/__main__.py:29-34`). Expect the whole run to take several minutes; `update-system` and the image pulls are the slow parts.
- If it fails:
  - `Missing required configuration variable 'security:ssh_user'` → B10 config not set.
  - `unknown stack "organization/deploy-images/dev"` or similar → do B9 first, in the same state bucket.
  - SSH `handshake failed` / `Permission denied (publickey)` → wrong `sa_` user, key not added (B7), OS Login not enabled (B5), or the key has a passphrase.
  - `Quota 'N2D_CPUS' exceeded` or `ZONE_RESOURCE_POOL_EXHAUSTED` → change `machine_type` (`create_instance.py:38`) or `GCP_ZONE` (`docker-shell.sh:15`).
  - `Could not get lock /var/lib/dpkg/lock-frontend` → unattended upgrades raced you; run `pulumi up` again.

**B11. Verify (README lines 369–383).**
- Open `http://<instance_ip>/`. In the footer you should see "Frontend version: 1" and "API version: 3.0", which the frontend fetches from `/status` (`Footer.jsx`, `DataService.js` `GetStatus`).
- `curl http://<instance_ip>/api-service/status` returns `{"version":"3.0"}`.
- SSH in from the GCP console, or from the deployment container with `ssh -i /secrets/ssh-key-deployment sa_…@<instance_ip>` (not in the README; the exported `ssh_command` omits `-i`, see §6). Then run:
```
sudo docker container ls
sudo docker container logs api-service -f
sudo docker container logs frontend -f
sudo docker container logs nginx -f
```
- To get a shell inside a container (README lines 379–383):
```
sudo docker exec -it api-service /bin/bash
sudo docker exec -it nginx /bin/bash
```
- `http://<ip>/api-service/docs` will **not** show a usable Swagger UI (§9). Use `/api-service/status` instead. A chat request is only a valid test after you switch `GENERATIVE_MODEL` to a model Vertex AI still serves (§9).

**B12. Redeploy after a code change (implied by the design).** Run `pulumi up` in `deploy_images` (new timestamp tags), then `pulumi up` in `deploy_single_vm`. The preview shows `+-` replace for `frontend`, `vector-db-loader` and `api-service`. Editing `nginx.conf` alone re-runs only the upload, move and restart resources (checksum triggers). Read the preview before `-y`: if Canonical has published a newer Ubuntu 22.04 image since your last run, the VM itself may be planned for replacement (§6 gotcha 20).

**B13. Destroy (README line 389).**
- Command: `pulumi destroy --stack dev --refresh -y`
- Run it **inside `deploy_single_vm`**. It deletes the containers through SSH first, then the VM, disk, firewalls and VPC, in reverse dependency order.
- Running it in `deploy_images` removes the images from *state only* (`retain_on_delete=True`), so delete the registry images yourself.
- `pulumi destroy` keeps the (now empty) stacks, so a later `pulumi up` works without `stack init`. Run `pulumi stack rm dev` only if you want to delete a stack and its history completely. By default it also deletes that folder's `Pulumi.dev.yaml` from your checkout unless you pass `--preserve-config`.
- Checkpoint: `Resources: - N deleted`, and Compute Engine → VM instances is empty.

---

## 5. Code tour

```
src/deployment/
├── Dockerfile                    # deployment toolbox image: python 3.13 + gcloud + docker-ce + kubectl 1.34 + helm + pulumi + uv
├── docker-shell.sh               # builds (amd64) & runs the toolbox; sets GCP_* env, mounts socket/secrets/code
├── docker-entrypoint.sh          # gcloud SA login, AR cred helper, create state bucket, `pulumi login gs://...`
├── docker_config.json            # Docker credHelpers → gcloud for gcr.io and us-docker.pkg.dev (mounted as /root/.docker/config.json)
├── pyproject.toml / uv.lock      # pulumi 3.204.0, pulumi-gcp 9.3.0, pulumi-command 1.1.3, pulumi-docker 4.9.0, pulumi-docker-build 0.0.15 (locked)
├── nginx-conf/nginx/nginx.conf   # reverse proxy: /api-service/ → api-service:9000/, / → frontend:3000
├── deploy_images/                # Pulumi project "deploy-images": build+push 3 images to Artifact Registry
│   ├── Pulumi.yaml, Pulumi.dev.yaml
│   └── __main__.py
├── deploy_single_vm/             # Pulumi project "deploy-single-vm"
│   ├── Pulumi.yaml, Pulumi.dev.yaml, Pulumi.dev-test.yaml
│   ├── __main__.py               # orchestrates the 4 phases + exports
│   ├── create_instance.py        # VPC, firewalls, disk, VM, SSH connection
│   ├── provision_instance.py     # 9 chained remote.Commands (disk mount, apt, docker)
│   ├── setup_containers.py       # secrets upload, Docker-over-SSH provider, 4 containers  (USED)
│   ├── setup_webserver.py        # nginx.conf upload w/ checksum + nginx container         (USED)
│   ├── setup_containers_using_command.py   # older variant: same via `docker run` strings  (NOT imported)
│   └── setup_webserver_using_command.py    # older variant                                 (NOT imported)
├── deploy_k8s/ , deploy-k8s-tic-tac-toe.yml, emoji.yaml, visualizer.yaml   # L22 (Kubernetes), not used in L20
src/api-service/api/service.py    # v3: routes mounted under ROOT_PATH; new /status endpoint
src/frontend-react/Dockerfile     # v3: 3-stage Next.js "standalone" build; bakes .env.production
src/frontend-react/.env.production# NEXT_PUBLIC_BASE_API_URL=/api-service
src/*/docker-hub.sh               # Part A: buildx multi-arch build & push to Docker Hub user "dlops"
```

### Excerpt 1: the toolbox's environment
`src/deployment/docker-shell.sh:9-17`
```bash
export SECRETS_DIR=$(pwd)/../../../secrets/
export SSH_DIR=$(pwd)/../../../secrets/
# export SECRETS_DIR=$(pwd)/../../../secrets/ac215-project/
# export SSH_DIR=$(pwd)/../../../secrets/ac215-project/
export GCP_PROJECT="ac215-project" # Change to your GCP Project
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json
export PULUMI_BUCKET="gs://$GCP_PROJECT-pulumi-state-bucket"
```
- `:9` the secrets folder is three levels up from `src/deployment`, i.e. a sibling of the repo folder. Lines `:11-12` show the instructor's per-project variant (also active on `cluster-updates`).
- `:13` is the only place you are told to edit. It also names the state bucket in `:17`.
- `:14-15` region and zone are **environment variables**, not stack config, so the Pulumi programs crash with `KeyError` if run outside this container.
- `:16` every GCP client in the container (gcloud, Pulumi providers) authenticates as the deployment SA.

### Excerpt 2: what the container can reach
`src/deployment/docker-shell.sh:34-43`
```bash
    docker run --rm --name $IMAGE_NAME -ti \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$BASE_DIR":/app \
    -v "$SECRETS_DIR":/secrets \
    -v "$SSH_DIR/.ssh":/home/app/.ssh:ro \
    -v "$(pwd)/docker_config.json":/root/.docker/config.json \
    -v "$(pwd)/pulumi-plugins":/root/.pulumi/plugins \
    -v "$BASE_DIR/../api-service":/api-service \
    -v "$BASE_DIR/../frontend-react":/frontend-react \
    -v "$BASE_DIR/../vector-db":/vector-db \
```
- `:35` the host's Docker socket gives the container control of the host daemon, which is how `deploy_images` builds images.
- `:36` your `src/deployment` is live-mounted at `/app`, so edits on the host apply immediately, and `pulumi config set` edits files in your git checkout.
- `:39` the repo's `docker_config.json` becomes the container's Docker config, which sets the credential helpers used by both the image push and the Docker-over-SSH provider's pull.
- `:40` caches provider plugins on the host so restarts don't re-download them.
- `:41-43` the app sources become build contexts at `/api-service`, `/frontend-react` and `/vector-db`.

### Excerpt 3: entrypoint: auth and state backend
`src/deployment/docker-entrypoint.sh:9-23`
```bash
# Authenticate gcloud using service account
gcloud auth activate-service-account --key-file $GOOGLE_APPLICATION_CREDENTIALS
gcloud config set project $GCP_PROJECT
# login to artifact-registry
gcloud auth configure-docker us-docker.pkg.dev --quiet
# Check if the bucket exists
if ! gsutil ls -b $PULUMI_BUCKET >/dev/null 2>&1; then
    echo "Bucket does not exist. Creating..."
    gsutil mb -p $GCP_PROJECT $PULUMI_BUCKET
else
    echo "Bucket already exists. Skipping creation."
fi

echo "Logging into Pulumi using GCS bucket: $PULUMI_BUCKET"
pulumi login $PULUMI_BUCKET
```
- `:10` makes gcloud act as the deployment SA, and `:13` lets `docker push` to `us-docker.pkg.dev` use it.
- `:15-20` idempotently create the state bucket ("create if missing", the same pattern you will see in the remote scripts).
- `:23` selects the **self-managed GCS backend**. Every `pulumi stack init/up` after this stores state in that bucket.

### Excerpt 4: building and pushing an image declaratively
`src/deployment/deploy_images/__main__.py:12-32`
```python
# 🕒 Timestamp for tagging
timestamp_tag = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
repository_name = "cheese-app-repository"
registry_url = f"us-docker.pkg.dev/{project}/{repository_name}"

# Docker Build + Push -> API Service
image_config = {
    "image_name": "cheese-app-api-service",
    "context_path": "../../api-service",
    "dockerfile": "Dockerfile"
}
api_service_image = docker_build.Image(
    f"build-{image_config["image_name"]}",
    tags=[pulumi.Output.concat(registry_url, "/", image_config["image_name"], ":", timestamp_tag)],
    context=docker_build.BuildContextArgs(location=image_config["context_path"]),
    dockerfile={"location": f"{image_config["context_path"]}/{image_config["dockerfile"]}"},
    platforms=[docker_build.Platform.LINUX_AMD64],
    push=True,
    opts=pulumi.ResourceOptions(custom_timeouts=CustomTimeouts(create="30m"),
                                retain_on_delete=True)
)
```
- `:13` evaluated **every run**, which gives new tags and so a perpetual diff.
- `:15` the multi-region `us` Artifact Registry host. The repository must already exist.
- `:24` the logical name `build-cheese-app-api-service` is the resource's identity in state. The f-string with nested `"` needs Python ≥ 3.12 (PEP 701), and the toolbox ships 3.13 (`Dockerfile:4`).
- `:28` forces amd64 so the image runs on the x86 VM even if you build on an ARM Mac.
- `:31` `retain_on_delete=True`: `pulumi destroy` forgets the image but leaves it in the registry.

### Excerpt 5: the orchestration
`src/deployment/deploy_single_vm/__main__.py:8-26`
```python
# Get project info and configuration
gcp_config = pulumi.Config("gcp")
project = gcp_config.require("project")
ssh_user = pulumi.Config("security").require("ssh_user")
zone = os.environ["GCP_ZONE"]

# Create GCP infrastructure
instance, instance_ip, connection, persistent_disk, network = create_instance()

# Provision the instance with system-level setup
configure_docker = provision_instance(connection, instance, ssh_user)

# Setup and deploy all application containers
docker_provider, docker_network = setup_containers(
    connection, configure_docker, project, instance_ip, ssh_user
)

# Setup and deploy Nginx webserver
restart_nginx = setup_webserver(connection, docker_provider, docker_network)
```
- `:10-11` `require` fails fast with a clear message if you forgot `pulumi config set`.
- `:15-26` four phases, each returning the handle the next one depends on (`connection`, `configure_docker`, `docker_provider`). Python call order is not execution order; these returned handles make the dependencies explicit.

### Excerpt 6: a firewall rule
`src/deployment/deploy_single_vm/create_instance.py:50-62`
```python
    # Create firewall rule for HTTP traffic
    firewall_http = gcp.compute.Firewall(
        "allow-http",
        network=network.self_link,
        allows=[
            gcp.compute.FirewallAllowArgs(
                protocol="tcp",
                ports=["80"],
            )
        ],
        source_ranges=["0.0.0.0/0"],
        target_tags=["http-server"],
    )
```
- `:53` attaches the rule to the new VPC (not `default`).
- `:61` the rule only applies to VMs carrying the `http-server` tag, which the instance sets at `:134`. The SSH rule (`:79-89`) has no `target_tags`, so it applies to every VM in the VPC.

### Excerpt 7: Outputs and the SSH connection
`src/deployment/deploy_single_vm/create_instance.py:151-161`
```python
    # Get the VM's public IP address (dynamically assigned)
    instance_ip = instance.network_interfaces.apply(
        lambda interfaces: interfaces[0].access_configs[0].nat_ip
    )

    # Create SSH connection configuration for remote commands
    connection = remote.ConnectionArgs(
        host=instance_ip,
        user=ssh_user,
        private_key=private_key,
    )
```
- `:152-154` the IP does not exist while your Python runs. `.apply` registers a function to run once the instance's `network_interfaces` are known.
- `:157-161` `ConnectionArgs` takes that Output as `host`, so every remote command implicitly waits for the VM. `private_key` comes from `/secrets/ssh-key-deployment` (`:10-11`).

### Excerpt 8: an idempotent remote command
`src/deployment/deploy_single_vm/provision_instance.py:23-32`
```python
    # Provision VM: Format and mount persistent disk
    format_disk = remote.Command(
        "format-persistent-disk",
        connection=connection,
        create="""
            # Format disk only if it doesn't have a filesystem
            sudo sh -c 'blkid -o value -s TYPE /dev/disk/by-id/google-persistent-disk-1 || mkfs.ext4 /dev/disk/by-id/google-persistent-disk-1'
        """,
        opts=ResourceOptions(depends_on=[instance]),
    )
```
- `:29` `blkid` succeeds (exit 0) if the disk already has a filesystem, and then `||` skips `mkfs.ext4`. Without this guard, re-creating this resource would **wipe the data disk**. `google-persistent-disk-1` is the auto device name of the second disk attached.
- `:31` waits for the instance resource. pulumi-command retries the SSH dial while the VM boots.

### Excerpt 9: the cross-stack pipe
`src/deployment/deploy_single_vm/setup_containers.py:26-31`
```python
    # Get image references from deploy_images stack
    images_stack = pulumi.StackReference("organization/deploy-images/dev")
    # Get the image tags (these are arrays, so we take the first element)
    api_service_tag = images_stack.get_output("cheese-app-api-service-tags")
    frontend_tag = images_stack.get_output("cheese-app-frontend-react-tags")
    vector_db_cli_tag = images_stack.get_output("cheese-app-vector-db-cli-tags")
```
- `:27` with a self-managed backend the fully qualified stack name is `organization/<project>/<stack>`, so this reads the `dev` stack of the `deploy-images` project from the same bucket.
- `:29-31` each export is a list of tags, and the containers use `tags[0]` (`:112, 172, 210`).

### Excerpt 10: Docker over SSH
`src/deployment/deploy_single_vm/setup_containers.py:79-98`
```python
    docker_provider = docker.Provider(
        "docker-provider",
        host=instance_ip.apply(lambda ip: f"ssh://{ssh_user}@{ip}"),
        # SSH options to handle key-based authentication and suppress host checking
        ssh_opts=[
            "-i",
            "/secrets/ssh-key-deployment",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
        ],
        # Authentication for Google Container Registry / Artifact Registry
        registry_auth=[
            {
                "address": "us-docker.pkg.dev",
            }
        ],
        opts=ResourceOptions(depends_on=[create_dirs]),
    )
```
- `:81` a provider *instance* whose endpoint is computed from an Output. Resources pick it with `opts=ResourceOptions(provider=docker_provider)` (e.g. `:126`).
- `:83-90` passed to the `ssh` binary. Host-key checking is disabled because the VM is new each time (fine for a demo, a MITM risk in production).
- `:92-96` no username or password, so credentials come from the Docker config file (credHelpers → gcloud). `:97` makes sure the VM is fully provisioned first.

### Excerpt 11: a container as a resource
`src/deployment/deploy_single_vm/setup_containers.py:207-225`
```python
    # API Service
    deploy_api_service = docker.Container(
        "deploy-api-service-container",
        image=api_service_tag.apply(lambda tags: tags[0]),
        name="api-service",
        restart="always",
        ports=[
            docker.ContainerPortArgs(
                internal=9000,
                external=9000,
            )
        ],
        envs=[
            "GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-service.json",
            f"GCP_PROJECT={project}",
            "GCS_BUCKET_NAME=cheese-app-models",
            "CHROMADB_HOST=vector-db",
            "CHROMADB_PORT=8000",
        ],
```
- `:210` changing the tag means replacing the container.
- `:212` `restart="always"` (compare the frontend at `:110-129`, which has **no** restart policy).
- `:213-218` host port 9000 is published but the firewall blocks it.
- `:220` the in-container path of the uploaded key. `:222` `GCS_BUCKET_NAME` is passed but no api code reads it.
- `:223` `vector-db` resolves through Docker DNS on `appnetwork`.

### Excerpt 12: change detection for a plain file
`src/deployment/deploy_single_vm/setup_webserver.py:41-55`
```python
    # Shared asset for nginx config
    nginx_conf_asset = pulumi.FileAsset("../nginx-conf/nginx/nginx.conf")

    # Compute checksum for nginx config
    checksum = file_checksum("../nginx-conf/nginx/nginx.conf")

    # Copy nginx configuration file triggered if checksum changes
    upload_nginx_conf = remote.CopyToRemote(
        "upload-nginx-conf",
        connection=connection,
        source=nginx_conf_asset,
        remote_path="/tmp/nginx.conf",
        triggers=[nginx_conf_asset, checksum],
        opts=ResourceOptions(depends_on=[create_nginx_conf_dir]),
    )
```
- `:42` the relative path resolves against the program directory `/app/deploy_single_vm`, so this is `src/deployment/nginx-conf/nginx/nginx.conf`.
- `:45` computed on your laptop each run. `:53` `triggers` means "replace this resource when any of these change", which re-uploads. The same triggers on the move (`:66`) and the `docker container restart nginx` command (`:105-113`) form a mini pipeline that re-runs only when the config changes.

### Excerpt 13: the reverse-proxy rule
`src/deployment/nginx-conf/nginx/nginx.conf:34-44`
```nginx
		# API - Make this location block handle all /api paths
		location ^~ /api-service/ {
			# Remove the rewrite since we want to preserve the full path after /api-service/
			proxy_pass http://api-service:9000/;
			proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
			proxy_set_header X-Forwarded-Proto $scheme;
			proxy_set_header X-Real-IP $remote_addr;
			proxy_set_header Host $http_host;
			proxy_redirect off;
			proxy_buffering off;
		}
```
- `:35` `^~` means "prefix match, and stop searching regex locations".
- `:37` the URI part `/` replaces the matched `/api-service/`, so `/api-service/llm-rag/chats` becomes `/llm-rag/chats` upstream. Despite the comment on `:36`, the prefix *is* removed.
- `:38-41` pass the client IP, scheme and host to FastAPI. `:43` `proxy_buffering off` lets streamed responses through immediately.

### Excerpt 14: the v3 API change that makes K8s possible
`src/api-service/api/service.py:12-13` and `:48-50`
```python
# Set root_path based on environment
ROOT_PATH = os.getenv("ROOT_PATH", "")
```
```python
# Mount your API under ROOT-PATH to match the Ingress rule
app = FastAPI(title="API Server", description="API Server", version="v1")
app.mount(ROOT_PATH, api_app)
```
- On the VM `ROOT_PATH` is unset, so the API is mounted at `""` and handles `/status`, `/llm-rag/...` directly.
- In K8s (`deploy_k8s/setup_containers.py:310-311`) it is `/api-service`, because the ingress forwards the full path.
- Side effect: the *outer* `app` owns `/docs` and `/openapi.json`, so Swagger shows an empty spec at the root (§9).

---

## 6. Gotchas and common errors

1. **Push to `cheese-app-repository` fails.**
   - Symptom: `pulumi up` in `deploy_images` → `name unknown: Repository "cheese-app-repository" not found` (or a 404 on push).
   - Cause: the repository is never created (`deploy_images/__main__.py:4,14-15`).
   - Fix: create it in `--location=us` (§2).
2. **Docker Hub push denied (Part A).**
   - Symptom: `requested access to the resource is denied`.
   - Cause: `DOCKER_USERNAME="dlops"` is hardcoded (`src/api-service/docker-hub.sh:11`, and the same line in `frontend-react/` and `vector-db/`).
   - Fix: set your username.
3. **Local `docker build` images "disappear" after Part A.**
   - Symptom: in later tutorials, `docker build -t x .` then `docker run x` fails with "Unable to find image".
   - Cause: `docker buildx create … --use --name multi-arch` (`docker-hub.sh:27`) made a docker-container builder your default, and it doesn't load results into the local store.
   - Fix: `docker buildx use default`.
4. **Apple Silicon is slow or times out.**
   - Symptom: platform warning on `docker run`, `Architecture: x86_64`, the api-service build takes tens of minutes, and possibly a 30-minute timeout.
   - Cause: the toolbox is built `--platform=linux/amd64` (`docker-shell.sh:31`) and the images target `LINUX_AMD64` (`deploy_images/__main__.py:28`), which is emulated on ARM. The VM *is* amd64, so this is required.
   - Fix: be patient and re-run (cache), or give Docker Desktop more CPU/RAM.
5. **Wrong project / instructor values.**
   - Symptom: `403 … Permission denied on resource project ac215-project` or SSH failures for user `sa_100110341521630214262`.
   - Cause: the committed `Pulumi.dev.yaml` files contain the instructor's project and SSH user (`deploy_single_vm/Pulumi.dev.yaml:3-5`), and the README commands hardcode them (lines 333, 353–355).
   - Fix: re-run `pulumi config set …` with your values, then `pulumi config` to check.
6. **Secrets folder in the wrong place.**
   - Symptom: entrypoint error reading `/secrets/deployment.json`, or a Pulumi `FileNotFoundError: '/secrets/ssh-key-deployment'` (`create_instance.py:10`) or `'/secrets/gcp-service.json'` (`setup_containers.py:47`).
   - Cause: `SECRETS_DIR=$(pwd)/../../../secrets/` (`docker-shell.sh:9`) only works when you start from `src/deployment`, with `secrets/` as a sibling of the repo folder.
   - Fix: run `sh docker-shell.sh` from `src/deployment` and fix the folder layout.
7. **SSH key with a passphrase.**
   - Symptom: remote commands fail to authenticate or the Docker provider hangs.
   - Cause: neither `remote.ConnectionArgs` (`create_instance.py:157-161`) nor the `ssh -i` options (`setup_containers.py:83-90`) supply a passphrase.
   - Fix: regenerate with an empty passphrase, re-add it (B7), and use the same `sa_` username.
8. **Order between stacks.**
   - Symptom: `deploy_single_vm` preview fails resolving `organization/deploy-images/dev`.
   - Cause: the StackReference (`setup_containers.py:27`) needs the images stack to exist in the same backend.
   - Fix: `pulumi up` in `deploy_images` first.
9. **`pulumi stack init dev` says it already exists.** You re-entered the container; state persists in the bucket. Use `pulumi stack select dev`. If you get `incorrect passphrase` when initialising, the committed `encryptionsalt` (`Pulumi.dev.yaml:1`) was made with a different passphrase. Deleting that line and re-initialising is safe because these config files hold no secrets. (Which passphrase the instructor used could not be verified.)
10. **Every `pulumi up` rebuilds and redeploys.**
    - Symptom: the images preview always shows `~ update ×3`, and the VM stack then replaces three containers.
    - Cause: `timestamp_tag` is `datetime.now()` (`deploy_images/__main__.py:13`).
    - Fix: accept it, or tag with a git SHA or content hash for reproducibility (§8, exercise E6).
11. **nginx restarts in a loop at first boot.**
    - Symptom: `sudo docker container logs nginx` shows `host not found in upstream "api-service:9000"`.
    - Cause: nginx resolves upstream names at start-up, and in the Docker-provider version nginx depends only on the provider (`setup_webserver.py:38`), not on the api-service/frontend containers (the older variant did, `setup_webserver_using_command.py:44`). `restart="always"` (`setup_webserver.py:75`) makes it recover once api-service exists.
    - Fix: wait, or add `deploy_api_service` and `deploy_frontend` to nginx's `depends_on`. This is an inference from the code; it was not reproduced.
12. **Frontend gone after a VM reboot.**
    - Symptom: `/` returns 502 after `sudo reboot` while `/api-service/status` works.
    - Cause: the frontend container has no `restart` policy (`setup_containers.py:110-129`), unlike vector-db (`:136`), api-service (`:212`) and nginx (`setup_webserver.py:75`), and unlike the command variant (`setup_containers_using_command.py:101`).
    - Fix: add `restart="always"`.
13. **Vector DB empty but no error.**
    - Symptom: RAG chat answers "not enough information" or errors, yet `pulumi up` succeeded.
    - Cause: `cli.py` wraps everything in `try/except` and prints the exception (`src/vector-db/cli.py:531, 577-579`), so the loader exits 0 even when ChromaDB wasn't ready yet. Pulumi only waits for the vector-db *container*, not readiness (`setup_containers.py:201-204`).
    - Fix: re-run the loader by hand on the VM (README lines 103–112, adapted: network `appnetwork`, host `vector-db`, your image tag, `-v /srv/secrets:/secrets`), or `pulumi up --refresh` (the `rm=True` loader no longer exists, so Pulumi will likely re-create it; see §9).
14. **api-service crash-loops.**
    - Symptom: `sudo docker container logs api-service` shows "Could not connect to a Chroma server" at import.
    - Cause: `chromadb.HttpClient(...)` is created at module import (`src/api-service/api/utils/llm_rag_utils.py:57`).
    - Fix: make sure `vector-db` is up. `restart="always"` retries.
15. **`ssh_command` output doesn't work.**
    - Symptom: `Permission denied (publickey)`.
    - Cause: `pulumi.export("ssh_command", …f"ssh {ssh_user}@{ip}")` (`deploy_single_vm/__main__.py:34`) omits `-i /secrets/ssh-key-deployment`.
    - Fix: add `-i`, or use the console SSH button.
16. **Swagger looks empty or broken.**
    - Symptom: `localhost:9000/docs` shows "No operations defined in spec!"; `http://<ip>/api-service/docs` loads a page that can't fetch `/openapi.json`.
    - Cause: the outer app at `api/service.py:49` owns `/docs`.
    - Fix: test with `/status`, or browse the inner docs locally with `ROOT_PATH=/api-service` at `localhost:9000/api-service/docs`.
17. **Changing zone or machine type.**
    - Changing `GCP_ZONE` replaces the disk and VM, because zone is immutable. The data disk is destroyed.
    - Changing `machine_type` on a running VM fails ("…requires stopping it… set allow_stopping_for_update") unless you add `allow_stopping_for_update=True` (§8, exercise E1). The ephemeral IP may change after a stop/start.
18. **State drift after manual fixes.** If you `docker rm` or `docker run` by hand on the VM, Pulumi's state is stale. Always use `--refresh` (the README does). Never delete the state bucket while resources exist.
19. **Security smells to remember (they are fine for a class demo):**
    - The SSH firewall rule is open to `0.0.0.0/0` (`create_instance.py:79-89`).
    - `chmod 666 /var/run/docker.sock` (`provision_instance.py:153`) gives any VM user root-equivalent access.
    - The VM runs as the highly privileged deployment SA (`create_instance.py:135-137`).
    - The empty Pulumi passphrase (`Dockerfile:51`).
    - `StrictHostKeyChecking=no` (`setup_containers.py:86-87`).
    - The frontend `.env.*` files commit a `NEXTAUTH_SECRET` (`src/frontend-react/.env.production:3`). NextAuth isn't actually wired to any sign-in route in v3, but don't copy this pattern.
    - Never `git add` the `secrets/` folder. It sits outside the repo for exactly this reason.
20. **Ubuntu image drift.** `get_image(family="ubuntu-2204-lts")` (`create_instance.py:100-103`) picks the newest 22.04 image each run, and its `self_link` is the VM's boot image (`:112`). The boot image is create-only in the GCP provider, so once Canonical publishes a newer image, the next `pulumi preview`/`up` will most likely plan to **replace the whole VM**. That gives you a new ephemeral IP, and every remote command and container is redone. The data disk is a separate resource and survives; the `blkid … ||` guard keeps it from being reformatted. Fix: pin a specific image name, or add `ignore_changes=["bootDisk.initializeParams.image"]` to the instance's `ResourceOptions`. (This is an inference from the provider's schema; it was not reproduced.) If you switch to `ubuntu-2404-lts`, `sudo pip3 install requests docker` (`provision_instance.py:128`) fails with "externally-managed-environment" (PEP 668). Those packages were only needed by the old Ansible flow, so you can delete that step.
21. **`pulumi config set` dirties your git checkout.** `/app` is your real `src/deployment` (`docker-shell.sh:36`), so `Pulumi.dev.yaml` changes show up in `git status` and conflict when you `git pull` course updates. Commit them on your own branch or stash them.
22. **Chat fails although the deployment succeeded.**
    - Symptom: `/api-service/status` works, but chat/RAG/agent requests fail. Expect a Vertex AI `NOT_FOUND` (404) model error in `sudo docker container logs api-service`; the exact message was not reproduced.
    - Cause: every LLM helper hardcodes `GENERATIVE_MODEL = "gemini-2.0-flash-001"` (`src/api-service/api/utils/llm_utils.py:22`, `llm_rag_utils.py:23`, `llm_agent_utils.py:21`, `llm_cnn_utils.py:30`). Google's Vertex AI "Model versions" page (last updated 2026-10-10) lists `gemini-2.0-flash` under *Retired models*, with retirement on 2026-06-01. `text-embedding-004` is listed as retiring 2027-04-01, so query embeddings still work for now.
    - Fix: change `GENERATIVE_MODEL` to a current model, e.g. a `gemini-2.5-flash` version, which Google names as the replacement. Then `pulumi up` in `deploy_images` and in `deploy_single_vm`.
23. **ChromaDB data is not on the persistent disk.**
    - Symptom: after the `vector-db` container is replaced, the collection is empty until the loader runs again.
    - Cause: the code mounts the disk at `/chroma/chroma` and sets `IS_PERSISTENT=TRUE` (`setup_containers.py:145-156`; README lines 93–95 for Part A), and it runs the unpinned `chromadb/chroma:latest`. Chroma's own cookbook says current 1.x server images persist to **`/data`** and calls `IS_PERSISTENT` a legacy variable. The data therefore lives in the container's writable layer.
    - Fix: mount `/mnt/disk-1/chromadb` at `/data`, or pin an older 0.x image tag. In this tutorial it matters little, because the loader drops and reloads the collection on every deployment.

---

## 7. Where this sits in the course

- **Before:**
  - L1–L2: VMs and "run app on VM using Docker" by hand (simple-translate).
  - L3–L4: multi-container apps and Docker networks/ports (mega-pipeline, port_toy).
  - L10: GCP auth and service accounts (cheese-app-v0).
  - L14: serverless Cloud Run, where Google ran the box for you.
  - L18: **cheese-app-v2**, the FastAPI api-service, React frontend and ChromaDB, all *local* containers.
  - L19 (K8s local): its tutorial is still "coming soon" on the course site.
- **This lecture adds:** the same app on a cloud VM, first manually and then reproducibly as code (Pulumi): registries, firewalls, disks, SSH/OS Login, reverse proxy, state and stacks.
- **Next:**
  - L21 (CI/CD with GitHub Actions, `cheese-app-ci-cd`) automates build and test.
  - **L22 (Kubernetes on GKE)** reuses *this* repo's deployment container and `deploy_images` stack. `deploy_k8s/` reads the same `StackReference("organization/deploy-images/dev")` (`src/deployment/deploy_k8s/setup_containers.py:10`) and adds `ROOT_PATH=/api-service` for the ingress (`:310-311`, ingress path at `deploy_k8s/setup_loadbalancer.py:84`).
  - L23 (cheese-app-v4) wires `pulumi up` into GitHub Actions. v4's `deploy_images/` and `deploy_single_vm/` sources are identical to v3's (verified with `git diff --no-index`; only `__pycache__` files differ).

**Manual step → Pulumi resource → old Ansible playbook** (playbooks are on the `pipenv` branch, `src/deployment/*.yml`):

| manual (README) | Pulumi (`src/deployment/…`) | Ansible (pipenv branch) |
|---|---|---|
| push to Docker Hub (18–35) | `deploy_images/__main__.py:23-74` → Artifact Registry | `deploy-docker-images.yml` |
| create VM in console (40–44) | `create_instance.py:45-149` | `deploy-create-instance.yml` |
| install Docker, folders (46–68) | `provision_instance.py:24-156` (+ data disk mount, new) | `deploy-provision-instance.yml` |
| secrets, network, 4 containers (70–151) | `setup_containers.py:34-247` | `deploy-setup-containers.yml` |
| nginx conf + container (153–220) | `setup_webserver.py:31-113` | `deploy-setup-webserver.yml` |
| (none) | `pulumi destroy` | `deploy-create-instance.yml --extra-vars cluster_state=absent` |

Names that changed between the manual and Pulumi versions: the Docker network is `cheese-app-network` (manual) vs `appnetwork` (Pulumi), and `cheese-app-network` is reused as the *GCP VPC* name in Pulumi. The ChromaDB container is `cheese-app-vector-db` vs `vector-db`.

**v2 → v3 diff** (`git diff --no-index --stat cheese-app-v2/src cheese-app-v3/src`: 46 files changed, 3716 insertions(+), 108 deletions(−)):
```
 src/deployment/**                            | NEW (Dockerfile, docker-shell.sh, docker-entrypoint.sh, docker_config.json,
                                              |      pyproject.toml/uv.lock, nginx-conf/, deploy_images/, deploy_single_vm/,
                                              |      deploy_k8s/, k8s demo yamls)          ~3,100 lines (670 of them uv.lock)
 src/api-service/api/service.py               |  33 +-   (ROOT_PATH mount, /status replaces /square_root, RAG+agent routers enabled)
 src/api-service/docker-hub.sh                |  37 +    (new, Part A)
 src/api-service/_test.py                     | 379 +    (new scratch test; listed in .gitignore but committed anyway)
 src/frontend-react/Dockerfile                |  64 +-   (node 18 → 20, 3-stage build, Next.js standalone, non-root user)
 src/frontend-react/next.config.js            |  26 +-   (output: "standalone"; dead rewrites removed)
 src/frontend-react/src/components/layout/Footer.jsx | 21 +- (shows Frontend/API version via /status)
 src/frontend-react/src/services/DataService.js     |  3 +  (GetStatus)
 src/frontend-react/docker-hub.sh             |  37 +    (new)
 src/vector-db/cli.py                         |  99 +-   (__main__ wrapped in try/except + traceback)
 src/vector-db/docker-hub.sh                  |  37 +    (new)
```
The meaningful changes:
1. The whole `src/deployment` toolbox and the Pulumi programs.
2. The API is mountable under a prefix (`ROOT_PATH`) and has a `/status` endpoint that the footer displays, a cheap "which version is live?" check.
3. The production frontend image is a minimal standalone server (`CMD ["node", "server.js"]`, `src/frontend-react/Dockerfile:57`) with `/api-service` baked in at build time.
4. The RAG and agent routers that v2 left commented out are enabled.

**`cluster-updates` branch** (forked from `main` at `3149e56`, "Using docker provider instead of command", 2025-11-17; 4 commits). It contains K8s work only: GKE with private networking and Workload Identity (`ec86699`), F5 nginx ingress (`980d9db`), TLS (`4cc742b`), GCE L7 (`e55178c`). The diff is mostly `deploy_k8s/__main__.py` plus a 1,411-line `deploy_k8s/dump.py` and a `Pulumi.dev2.yaml`. Relevance to L20:
- Its `api/service.py` hard-codes `app.mount("/api-service", api_app)`. Images built from that branch would **404 every API call behind the single-VM nginx**, which strips the prefix.
- Its `docker-shell.sh` points `SECRETS_DIR` at `secrets/ac215-project/`.
- It still contains `deploy_single_vm/docker_vm.py`, which `main` deleted in `d390993`.

Use `main` for L20.

---

## 8. Exercises

**E1 (hands-on, predict then run): resize the VM.** Change `machine_type = "n2d-standard-2"` to `"e2-standard-2"` (`create_instance.py:38`). Predict the preview, then run `pulumi up`.
*Worked answer:* the preview shows `~ update` on the instance (machine type is updatable in place). `up` then fails with the GCP provider's error saying that changing `machine_type` on a started instance requires stopping it and asks you to set `allow_stopping_for_update = true`. Add `allow_stopping_for_update=True` to `gcp.compute.Instance(...)` and re-run. Pulumi stops the VM, resizes it and starts it again. Because the IP is ephemeral (`create_instance.py:126-130`), it may change. The `instance_ip` Output then changes, and every resource whose `connection`/`host` depends on it shows up in the diff. That is a good reason to reserve a static IP (`gcp.compute.Address`) in a real deployment.

**E2 (hands-on): a health endpoint in nginx.** Add `location = /healthz { return 200 'ok'; }` inside the `server { … }` block of `src/deployment/nginx-conf/nginx/nginx.conf`. Predict which resources change.
*Worked answer:* only the resources whose `triggers` include the checksum: `upload-nginx-conf`, `move-nginx-conf` and `restart-nginx-container` (`setup_webserver.py:53,66,111`) are replaced (`+-`). The nginx container itself is unchanged, because its inputs (image, ports, bind mount path) are the same. `sudo mv` (`setup_webserver.py:62`) *replaces* `/conf/nginx/nginx.conf` with a new file (new inode), and a running container with a single-file bind mount keeps seeing the old file. `docker container restart nginx` then re-creates the bind mount from the path, so nginx starts with the new config. That is why the restart step is needed. `curl http://<ip>/healthz` → `ok`.

**E3 (debugging):** `pulumi up` in `deploy_images` ends with `name unknown: Repository "cheese-app-repository" not found`. Why, and what's the fix?
*Worked answer:* the program only builds and pushes (`deploy_images/__main__.py:23-32`); it never creates the repository (`artifactregistry` is imported on `:4` but unused). Artifact Registry does not create `*.pkg.dev` repositories on push. Create it in the multi-region that matches the host `us-docker.pkg.dev` (`--location=us`), or add an `artifactregistry.Repository` resource to the program and make the images `depends_on` it.

**E4 (debugging):** You open a *new* terminal, `cd src/deployment/deploy_single_vm`, and run `pulumi preview` with your laptop's own Pulumi install. It fails with `KeyError: 'GCP_ZONE'`. Why?
*Worked answer:* the zone and region are read with `os.environ[...]` (`deploy_single_vm/__main__.py:12`, `create_instance.py:31-32`), and only `docker-shell.sh` exports them (`:14-15`, passed in at `:47-48`). Outside the container you are also logged into a different backend, and `/secrets/...` paths don't exist. Use the container, or export the variables and run `pulumi login gs://<proj>-pulumi-state-bucket`. A more IaC-pure design would move zone and region into stack config (`gcp:zone`).

**E5 (conceptual): follow the request.** Trace `GET http://<ip>/api-service/podcasts/?limit=3` from the browser to Python and back. List every component and the path each one sees.
*Worked answer:*
1. The React code builds the URL from `NEXT_PUBLIC_BASE_API_URL=/api-service` (`.env.production:2`, `DataService.js` `GetPodcasts`).
2. The GCP firewall allows tcp:80 to tag `http-server` (`create_instance.py:51-62`).
3. The nginx container on host port 80 matches `location ^~ /api-service/` and `proxy_pass http://api-service:9000/;` rewrites the path to `/podcasts/?limit=3` (`nginx.conf:35-37`).
4. Docker DNS on `appnetwork` resolves `api-service`.
5. uvicorn on :9000 → outer `app` → mount at `""` (`ROOT_PATH` unset, `service.py:13,50`) → `api_app` → router prefix `/podcasts` (`service.py:41`).
6. The JSON response goes back the same way. On GKE the ingress would forward `/api-service/podcasts/...` unchanged, which is why K8s sets `ROOT_PATH=/api-service`.

**E6 (conceptual + hands-on): deterministic tags.** Why does `pulumi preview` in `deploy_images` always show three updates? Change the tagging so a re-run with no code changes is a no-op.
*Worked answer:* `timestamp_tag` comes from `datetime.now()` (`:13`), so the `tags` input differs on every run. Use something derived from the code instead. For example, read the git commit with `subprocess.check_output(["git","rev-parse","--short","HEAD"])`. Inside the deployment container this would fail as it stands: the repo's `.git` directory is not mounted (`/app` is only `src/deployment`, and the build contexts are mounted without it), and the Dockerfile never explicitly installs `git`. Mount the repo root, or compute the SHA on the host and pass it in as stack config. Alternatively, hash the build-context files. Then no code change means same tag, no diff, and no container replacement downstream. Downside: a rebuild with the same tag but changed base images won't redeploy. The `ref` export (`:34`, which includes the digest) is the most precise pin if you consume it in the VM stack.

**E7 (hands-on, predict): reboot resilience.** SSH to the VM and run `sudo reboot`. After a minute, which URLs work?
*Worked answer:* `/mnt/disk-1` is remounted from `/etc/fstab` (`provision_instance.py:50-54`). Docker restarts containers with `restart=always`: vector-db (`setup_containers.py:136`), api-service (`:212`) and nginx (`setup_webserver.py:75`). The **frontend has no restart policy** (`setup_containers.py:110-129`), so `/` returns 502 Bad Gateway, while `/api-service/status` still answers. The ephemeral IP is kept across a guest-OS reboot (unlike a stop/start). Fix: add `restart="always"` to the frontend and `pulumi up`; the preview tells you whether that container is updated or replaced.

**E8 (conceptual): drift.** Someone runs `sudo docker rm -f nginx` on the VM. What do `pulumi up -y` (no refresh) and `pulumi up --refresh -y` each do?
*Worked answer:* without `--refresh`, the diff is code vs *state*. State still says nginx exists with unchanged inputs, so Pulumi plans nothing and the site stays down. (Pulumi's Docker provider may still notice during its own reads; don't rely on it.) With `--refresh`, Pulumi first reads reality, finds the container missing, drops it from state, and the plan becomes `+ create deploy-nginx-container`. The checksum-triggered commands don't re-run, because their inputs didn't change. Takeaway: manual changes on Pulumi-managed machines create drift. Refresh, or better, make the change in code.

---

## 9. Errata and open questions

### Errata (with evidence)
1. **The Artifact Registry repository is never created.**
   - Evidence: `deploy_images/__main__.py:14-15` targets `cheese-app-repository`; `artifactregistry` is imported (`:4`) but unused; no README step creates it (README lines 327–345).
   - Effect: the first push fails.
2. **"Deployment Setup" is an Ansible leftover.**
   - Evidence: README lines 318–322 ask you to edit `inventory.yml` ("Add ssh user details in inventory.yml file"). No such file exists on `main`; it is on the `pipenv` branch (`src/deployment/inventory.yml`).
   - Effect: ignore the step; the Pulumi config commands (README lines 352–355) replace it.
3. **The course site and README say GCR; the code uses Artifact Registry.**
   - Evidence: the course site says "build and push images to GCR" (tutorials_demo.md, L20). The code pushes to `us-docker.pkg.dev` (`deploy_images/__main__.py:15`). README line 415 is headed "…to GCR", line 524 lists "Google Container Registry API", and `docker_config.json:3` and `provision_instance.py:145` still configure `gcr.io`.
4. **The README's API check (`/docs`) doesn't show the API in v3.**
   - Evidence: README line 14 says to open `http://localhost:9000/docs`. In v3, `api/service.py:49-50` mounts the routes into an *outer* FastAPI app, which owns `/docs` and `/openapi.json`. Verified with a minimal FastAPI 0.120.4 / Starlette 0.49.3 app (the versions in `src/api-service/uv.lock`): with `ROOT_PATH=""`, `/openapi.json` returns `paths=[]`; with `ROOT_PATH=/api-service`, the real spec is at `/api-service/openapi.json`.
   - Effect: on the VM, `http://<ip>/api-service/docs` serves the outer docs page, whose `/openapi.json` request then goes to the frontend. Use `/status` instead.
5. **The manual `nginx.conf` echo mangles `log_format`.**
   - Evidence: README lines 156–213 wrap the config in single quotes, but lines 165–167 contain single quotes too. Reproduced with a minimal test string: `log_format  main   - []  …;`, with the variables lost.
   - Effect: harmless for routing; the access logs are useless.
6. **Docker Hub username hardcoded.**
   - Evidence: `src/*/docker-hub.sh:11` `DOCKER_USERNAME="dlops"`. README lines 24–35 never say to change it, and the README `docker run` commands use `dlops/...` images.
7. **No teardown for the manual VM.** Part A (README lines 4–222) creates a billable VM and never deletes it.
8. **The destroy step doesn't say which directory, or that images are retained.**
   - Evidence: README line 389; `retain_on_delete=True` at `deploy_images/__main__.py:31,51,70`.
9. **SSH key passphrase isn't mentioned.** README line 296 `ssh-keygen -f ssh-key-deployment` doesn't say to leave it empty, but nothing in the code can supply one.
10. **The frontend container lost its restart policy in the Docker-provider refactor.**
    - Evidence: `setup_containers.py:110-129` has no `restart`; the older `setup_containers_using_command.py:101` had `--restart always`.
11. **nginx lost its dependency on the app containers.**
    - Evidence: `setup_webserver.py:38` depends only on `docker_provider`; the older `setup_webserver_using_command.py:44` depended on `deploy_api_service`.
12. **The loader hides failures.**
    - Evidence: `src/vector-db/cli.py:531, 577-579` catch every exception and exit 0. Added in v3 (`git diff` v2→v3 of `cli.py`).
    - Effect: Pulumi cannot detect a failed load.
13. **Cosmetic or dead code:**
    - `deploy_images/__main__.py:62` reuses the variable `frontend_image` for vector-db-cli, and `:10` `location` is unused.
    - `GCS_BUCKET_NAME` is passed (`setup_containers.py:222`, README line 123) but never read by the api code.
    - `provision_instance.py:124-131` installs `requests docker` for Ansible.
    - `docker-entrypoint.sh:5` prints "Virtual environment activated" without activating anything.
    - The Dockerfile creates user `app` (`:58-61`), but the container runs as root, so the `~/.ssh` mount (`docker-shell.sh:38`) is unused. Because it is a `-v` bind mount, Docker silently creates an empty `secrets/.ssh` folder on the host if it does not exist.
14. **README Part A intro is incomplete.** Lines 5–7 say only api-service and frontend-react are deployed, but the steps also run vector-db, vector-db-cli and nginx.
15. **README line 29 typo.** It says "`Docker.dev` file"; the file is `Dockerfile.dev`.
16. **Exported `ssh_command` omits the key.** `deploy_single_vm/__main__.py:34` produces `ssh {ssh_user}@{ip}` with no `-i /secrets/ssh-key-deployment`.
17. **Stray stack file.** `deploy_single_vm/Pulumi.dev-test.yaml` defines a `dev-test` stack without `security:ssh_user` or `security:gcp_service_account_email`, so the first `require` (`deploy_single_vm/__main__.py:11`, then `create_instance.py:27-30`) would fail if you used it.
18. **Committed config contains instructor values.** The `Pulumi.dev.yaml` files (`deploy_single_vm/Pulumi.dev.yaml:3-5`) and README commands (lines 333, 353–355, 290) use `ac215-project` and `sa_100110341521630214262`. README line 267 mentions only `docker-shell.sh`.
19. **K8s-section leftovers in the same README** (relevant to L22): README line 529 mentions `docker-shell.bat`, which does not exist, and line 524 lists the retired Container Registry API.
20. **The generative model is retired.**
    - Evidence: `GENERATIVE_MODEL = "gemini-2.0-flash-001"` in `src/api-service/api/utils/llm_utils.py:22`, `llm_rag_utils.py:23`, `llm_agent_utils.py:21`, `llm_cnn_utils.py:30` (and `src/vector-db/cli.py:30`). Google's Vertex AI "Model versions" page (docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, last updated 2026-10-10) lists `gemini-2.0-flash` under *Retired models* with retirement date 2026-06-01. It lists `text-embedding-004` with retirement date 2027-04-01.
    - Effect: the deployment succeeds and `/status` works, but chat endpoints fail until the model name is updated (§6 gotcha 22).
21. **ChromaDB persistence path is out of date for `chromadb/chroma:latest`.**
    - Evidence: `setup_containers.py:134, 145-156` and README lines 93–97 use `IS_PERSISTENT=TRUE` plus a mount at `/chroma/chroma` on an unpinned `latest` image. Chroma's cookbook ("Running Chroma") says current server images persist to `/data` and that `IS_PERSISTENT` is a legacy variable for the v1.x Docker setup.
    - Effect: the vector data is not on `/mnt/disk-1`. The impact is low because the loader reloads the collection on every deployment.
22. **README path shorthand.** README lines 266 and 349 say `cd into deployment`; the folder is `src/deployment`.

### Open questions (could not be determined from the sources)
- **Ed lesson content:** edstem.org was not accessible when the sources were checked. Any extra steps, slides or announcements there (e.g. creating the registry, a shared class project, pre-made keys) are unknown.
- **Pulumi passphrase:** whether the committed `encryptionsalt` lines (`Pulumi.dev.yaml:1`) were generated with an empty passphrase. If not, `pulumi stack init dev` with `PULUMI_CONFIG_PASSPHRASE=""` will report an incorrect passphrase.
- **Loader under `--refresh`:** how the Docker provider treats the `rm=True`, `restart="no"` loader container (`setup_containers.py:170-205`) on later `pulumi up --refresh` runs. Most likely Pulumi sees it as deleted and re-creates it, which re-loads the collection (harmless, because `load()` drops and re-creates it at `cli.py:286-292`). Whether a very fast exit can make the create step itself report "container exited" was not verified.
- **ChromaDB persistence path (mostly resolved, see errata 21):** Chroma's cookbook documents `/data` for current images. The image was not pulled to check which exact tag `latest` resolves to on your run date.
- **Replacement model (see errata 20):** which `gemini-2.5-flash` version (or later) the instructor will switch to, and whether that changes answers or latency. `text-embedding-004` is listed as available until 2027-04-01. If it is replaced too, the pre-computed embeddings downloaded by `cli.py --download` (`src/vector-db/cli.py:487`) would no longer match the query embeddings.
- **Pulumi uv toolchain venv:** whether Pulumi's `toolchain: uv` uses the pre-built venv at `/home/app/.venv` (`Dockerfile:8,70`) or creates its own on first run. Either way it works, but the first `pulumi up` may spend time syncing dependencies.
- **Unpinned versions:** the Pulumi CLI installed by `curl … get.pulumi.com` (`Dockerfile:47`), Helm (installed from the `main`-branch `get-helm-3` script, `Dockerfile:44`), the gcloud SDK and docker-ce packages (`Dockerfile:30`), the kubectl *patch* version (only the minor is pinned, `K8S_MINOR=1.34`, `Dockerfile:33`), and the `chromadb/chroma:latest` and `nginx:stable` images are all unpinned. Exact behaviour on your run date may differ from Nov 2025.
- **Upstream changes:** whether the instructor will update `cheese-app-v3` before the Fall 2026 lecture. Compare `git -C cheese-app-v3 rev-parse HEAD` with the hash at the top of this guide (`3ecef56fea879ac480d260c0906cd95baf05179a`).

---

## Links

**cheese-app-v3 README** (`main` @ `3ecef56`)
- [Deployment to GCP (Manual)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-to-gcp-manual): [Ensure you have all your container built and works locally](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#ensure-you-have-all-your-container-built-and-works-locally) · [Push Docker Images to Docker Hub](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#push-docker-images-to-docker-hub) · [Running Docker Containers on VM](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#running-docker-containers-on-vm) · [Install Docker on VM](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#install-docker-on-vm) · [Run vector-db](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-vector-db) · [Run api-service](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-api-service) · [Add NGINX config file](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#add-nginx-config-file) · [Run NGINX Web Server](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-nginx-web-server)
- [Deployment to GCP (Single VM Instance)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-to-gcp-single-vm-instance): [API's to enable in GCP before you begin](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#apis-to-enable-in-gcp-before-you-begin) · [Setup GCP Service Account for deployment](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#setup-gcp-service-account-for-deployment) · [Setup Docker Container (Pulumi, Docker, Kubernetes)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#setup-docker-container-pulumi-docker-kubernetes) · [SSH Setup](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#ssh-setup) · [Deployment Setup](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-setup) (skip) · [Deployment (Single VM Instance)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-single-vm-instance) · [Build and Push Docker Containers to Google Artifact Registry](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#build-and-push-docker-containers-to-google-artifact-registry) · [Create Compute Instance (VM) & Deploy Containers](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-compute-instance-vm--deploy-containers)
- [Delete the Compute Instance / Persistent disk](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#delete-the-compute-instance--persistent-disk)
- Code at the pinned commit: [`src/deployment/`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a/src/deployment) · latest README on [`main`](https://github.com/dlops-io/cheese-app-v3#deployment-to-gcp-manual)

**Course**
- Ed lesson: [L20 · Deployment: Pulumi](https://edstem.org/us/courses/97373/lessons/166045/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for this lecture.
- Previous lecture with a tutorial: [L18 · APIs + Frontend](L18-apis-frontend.md) (cheese-app-v2, the app this lecture deploys). L19 · Scaling: Kubernetes (local) has no tutorial yet ("coming soon" on the course site), so it has no guide.
- Next lecture: [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md) (`cheese-app-ci-cd`)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II](L03-containers-2-mega-pipeline.md) · [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md) · [L14 · Serverless Deployment: Cloud Functions, Cloud Run](L14-serverless-deployment.md) · [L22 · Scaling: Kubernetes (cloud)](L22-kubernetes-cloud.md) · [L23 · Final Deployment and Review](L23-final-cicd-deployment.md)
