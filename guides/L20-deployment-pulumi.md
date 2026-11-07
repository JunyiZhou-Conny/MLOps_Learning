# L20 · Deployment: Pulumi — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166045/) · Tutorial: [`dlops-io/cheese-app-v3`](https://github.com/dlops-io/cheese-app-v3) `main` @ [`3ecef56`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a) (README sections "Deployment to GCP (Manual)" and "Deployment to GCP (Single VM Instance)"; `main` re-checked with `git ls-remote` on 2026-11-05) · Colab: none for this lecture · Video: [AC215 · L20 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l20-deployment-pulumi) · Made from the verified digest and real terminal captures, 2026-11-05

## 中文速览

- **做什么：** 把 cheese app（Next.js frontend、FastAPI `api-service`、ChromaDB vector DB、一次性的 `vector-db-cli` loader）部署到**一台** Compute Engine VM 上，前面挡一个 nginx reverse proxy（port 80）。做两遍：(A) **手动**：`docker-hub.sh` 把 image push 到 Docker Hub，在 console 里点出一台 N2D VM，SSH 进去敲 21 条命令；(B) **用 Pulumi 写成 code**：laptop 上跑一个 deployment container（toolbox），里面两个 Pulumi project：`deploy_images`（build `linux/amd64` image，push 到 Artifact Registry，tag 是 timestamp）和 `deploy_single_vm`（VPC、3 条 firewall rule、50 GB data disk、`n2d-standard-2` Ubuntu 22.04 VM，SSH 进去 provision，再用 Docker-over-SSH 起 5 个 container）。2026-11-05 的 capture 在一台 Debian 12 stand-in 上把 Part A 从 `get-docker.sh` 一直跑到 nginx 在 port 80 返回首页；Part B 没有 GCP 账号，每条命令都停在它第一个真实的 error。
- **Idea 1 · IaC 是 declarative：** Part A 是 imperative recipe（"点这个、跑那个"），21 条命令没法 repeat、review、undo。Pulumi 的 Python program 只描述 end state；`pulumi up` 比较三样东西：desired（code）、state（GCS bucket 里的记录）、reality（cloud）。plan 是 desired 和 state 的 diff；`--refresh` 先去读 reality；`-y` 跳过确认，所以没人看 plan。
- **Idea 2 · project / stack / StackReference：** 两个 project（`deploy-images`、`deploy-single-vm`），stack 都叫 `dev`。`pulumi config set` 写的是你 checkout 里的 `Pulumi.dev.yaml`。`deploy_images` 每跑一次都生成新的 timestamp tag，`deploy_single_vm` 用 `StackReference("organization/deploy-images/dev")` 读这些 tag，于是三个 app container 被 replace：发新版本 = 先 `up` images，再 `up` VM。
- **Idea 3 · provider 和 identity：** `gcp` resource（VM、disk、firewall）Pulumi 能读回来；`remote.Command` 是 escape hatch，Pulumi 只记得"这个 script 跑过"，所以 script 必须 idempotent（`blkid … || mkfs.ext4`）。Docker provider 的 `host` 是 `ssh://sa_…@<ip>`。两个 service account：`deployment`（建 infra、push image、SSH，留在 laptop）和 `gcp-service`（app 调 Vertex AI，放到 VM 上）。
- **Idea 4 · nginx 是唯一的门：** firewall 只开 80/443/22；`location ^~ /api-service/` + `proxy_pass http://api-service:9000/;` 末尾那个 `/` 把 prefix 剥掉，API 收到 `/status`。nginx 启动时要 resolve 每个 upstream 名字：capture 里 `docker stop frontend` 再 restart nginx，nginx 直接 `Exited (1)`：`host not found in upstream "frontend"`，port 80 整个不通（`http://localhost/ -> 000`），API 那条路也一起断了（`vm/58`）。
- **最费时间的坑 ①：toolbox build 不起来。** `sh docker-shell.sh` 照原样跑会失败两次：`FROM python:3.13-slim-bullseye` 的 security repo 已经搬到 archive，`apt-get install` 一串 `404 Not Found`（改成 `python:3.13-slim-bookworm`）；接着 `google-cloud-sdk` 这个 package 已经没有了（改成 `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin`）。script 没开 `set -e`，build 失败后还是会 `docker run`，最后报 `pull access denied`：一定要往上看第一个 error。两处一改，91.9 s build 完。
- **最费时间的坑 ②：placeholder 和别人的值。** README 里的 `<USER NAME>`、`<YOUR GCP_PROJECT>` 在 shell 里是 redirection，原样敲会得到 `syntax error near unexpected token 'newline'` 或 `YOUR: No such file or directory`：连尖括号一起换掉。`ac215-project`、README 作者的 `sa_…` 用户名都要换成你自己的；`ssh-keygen` 空 passphrase（Enter 两次）；Artifact Registry 的 `cheese-app-repository` 没有任何 step 去建，先 `gcloud artifacts repositories create …`。如果 `pulumi stack init dev` 开始问你 Pulumi Cloud 登录，或者报 `PULUMI_ACCESS_TOKEN must be set`，说明 entrypoint 里的 `pulumi login gs://…` 已经失败了：回去看 `deployment.json`。
- **Part A 的几个意外（都在 capture 里）：** public `dlops/cheese-app-api-service` image 比 code 旧，`/status` 返回 404，用 `/` 检查（`{"message":"Welcome to AC215"}`）；README 用 `echo '…'` 写 `nginx.conf`，里面的单引号把 `log_format` 吃掉了，access log 只剩 `-[]`；Chroma 1.0.0 把数据写在 `/data`，README mount 的 `docker-volumes/chromadb` 是空的；interactive 那条 `api-service` 和 detached 的同名，会 `Conflict`。chat 用的 `gemini-2.0-flash-001` 已在 2026-06-01 retired，要换 model 再 redeploy。
- **做完要删：** 在 `deploy_single_vm` 里 `pulumi destroy --stack dev --refresh -y`（container、VM、disk、firewall、VPC 全删）；Artifact Registry 的 image 是 `retain_on_delete=True`，要 `gcloud artifacts repositories delete cheese-app-repository --location=us`；state bucket 最后删；Part A 手动建的 VM README 没让你删，去 console Delete（连 boot disk）；laptop 上还有 2.61 GB 的 toolbox image 和 `multi-arch` builder；课程结束时去 IAM 删掉两把 service-account key。
- **Lecture slides：** 老师的 Lecture 20 slides（30 页）和这份 guide 各节怎么对应、做 tutorial 需要的 9 个 lecture ideas，以及 slides 和今天 repo 不一样的 9 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 21–28 写的 Google Container Registry (GCR) 已经 retired，code push 到的是 Artifact Registry，而且 `cheese-app-repository` 要你自己先建。② slides 25–26 讲的是 VM 这边只用 `gcp-service` 这把权限窄的 key；但 README 让 VM 以 `deployment@…` 的身份运行，Pulumi pull image 用的也是 deployment 的凭证。`gcp-service` 的 key 被 mount 进 `api-service` 和 loader，给 Vertex AI 用；VM 上用它做的 docker 登录只对你手动敲的 `docker pull` 有用。另外 slides 里的 models GCS bucket（slide 26 的 "class bucket"）和 NFS persistent volume 在 v3 里都对不上：model 从 GitHub release 下载，disk 是挂在 `/mnt/disk-1` 的一块普通 disk。

## At a glance

**What you build.** The cheese app (Next.js frontend, FastAPI `api-service`, ChromaDB and a one-shot `vector-db-cli` loader) running on one Compute Engine VM behind an nginx reverse proxy on port 80, deployed twice. First by hand: images on Docker Hub, a VM clicked together in the console, 21 shell commands over SSH. Then as code, with two Pulumi projects run from a deployment container ("the toolbox") on your laptop: `deploy_images` builds timestamp-tagged `linux/amd64` images and pushes them to Artifact Registry; `deploy_single_vm` creates the VPC, firewall rules, data disk and VM, provisions the VM over SSH and starts five containers through a Docker provider that talks to the VM's Docker daemon over SSH. You end with a URL `http://<instance_ip>/`, a state file in a GCS bucket and one command (`pulumi destroy`) that removes it all.

**What the captures show.** The real terminal outputs quoted in this guide come from 2026-11-05 runs without any Google account, Docker Hub login or key. Part A ran completely on a fresh Debian 12 machine standing in for the VM, up to nginx answering on port 80 with the frontend and the API behind it. Part B ran in the toolbox built from `src/deployment/` (after two one-line fixes, §4 B3) up to each command's first real error; the Pulumi programs then ran on Pulumi's local file backend until their first Google call. Console steps are described from the README; nothing is invented.

**Time needed** (estimate). Part A: about 1–1.5 h, less if you skip your own Docker Hub push and run the public `dlops/...` images (§4 A2). Part B: about 2–3 h the first time: service accounts and keys, building the toolbox (92 s in the capture, after the fixes), `deploy_images` (the api-service image includes TensorFlow; under emulation on Apple Silicon expect tens of minutes; the frontend image alone took about 2½ minutes in the capture, `laptop/b35b`) and `deploy_single_vm` (several minutes; `update-system` and the image pulls are the slow parts). Add about 1 h for the exercises.

**Prerequisites.**
- A GCP project with billing enabled, and its **project ID**. The committed scripts, the `Pulumi.dev.yaml` stack files and the README commands hardcode `ac215-project`.
- Docker Desktop (or Docker Engine) with BuildKit. Nothing else is installed locally: gcloud, Pulumi, kubectl, Helm and uv live in the toolbox image (`src/deployment/Dockerfile:28-55`), which needs two one-line edits before it builds today (§4 B3).
- Part A only: a Docker Hub account and an access token (README lines 19–21).
- APIs: Compute Engine, Service Usage, Cloud Resource Manager, Artifact Registry (README lines 231–234), plus the **Vertex AI API** for the running app.
- Credentials: two service accounts with JSON keys, `deployment.json` and `gcp-service.json`, in a `secrets/` folder **next to** the repo folder (§2).
- Background: L18 (the cheese app as local containers), L10 (service accounts and the `secrets/` convention), L1–L2 (VMs, Docker on a VM), L14 (Artifact Registry, tags vs digests).

**What it costs.** The VM (`n2d-standard-2`) is about $0.08–0.09/hour, about $2/day, and the two 50 GB `pd-standard` disks about $4/month together; the ephemeral IP adds a small hourly charge. Artifact Registry stores several GB (TensorFlow in api-service; the public api image is 5.07 GB on disk, `vm/60`), with a new tag on every `pulumi up`, at about $0.10/GB-month above the free tier. The state bucket costs cents; Vertex AI bills per token. The two surprise bills: the **Part A VM, which the README never tells you to delete**, and the registry images, which **survive** `pulumi destroy`. Details and prices: §2.

**Tear down, exactly** (details in §2 and §4 A10, B13):
1. Part A VM: Console → Compute Engine → VM instances → select it → **Delete** (with its boot disk).
2. Part B, inside the toolbox, in `/app/deploy_single_vm`: `pulumi destroy --stack dev --refresh -y`. It deletes the containers through SSH, then the VM, data disk, firewalls and VPC. Checkpoint: `Resources: - N deleted`, and Compute Engine → VM instances is empty.
3. Artifact Registry images: `pulumi destroy` in `deploy_images` only removes them from state (`retain_on_delete=True`). Delete them in the console or with `gcloud artifacts repositories delete cheese-app-repository --location=us`.
4. The state bucket `<proj>-pulumi-state-bucket`: keep it while any stack still has resources; delete it last (`gcloud storage rm -r gs://<proj>-pulumi-state-bucket`).
5. On the laptop: the toolbox image (`cheese-app-deployment`, 2.61 GB), the `multi-arch` builder (`docker buildx rm multi-arch`), `src/deployment/pulumi-plugins/`. Docker Hub images from Part A: free, optional.
6. When the course ends: delete the service-account JSON keys in IAM. They are long-lived credentials.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site `harvard-iacs.github.io/2026-AC215/tutorials_demo/`, "Lecture 20: Deployment: Pulumi", with two tutorials: "Deployment of the full app to GCP (Manual)" and "Deployment to GCP with Pulumi"), in `cheese-app-v3/README.md`:
  - [`#deployment-to-gcp-manual`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#deployment-to-gcp-manual), README lines 4–222
  - [`#deployment-to-gcp-single-vm-instance`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#deployment-to-gcp-single-vm-instance), README lines 225–383, including `#apis-to-enable-in-gcp-before-you-begin`, `#setup-docker-container-pulumi-docker-kubernetes`, `#ssh-setup`, `#deployment-single-vm-instance`, `#build-and-push-docker-containers-to-google-artifact-registry` and `#create-compute-instance-vm--deploy-containers`
  - [`#delete-the-compute-instance--persistent-disk`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#delete-the-compute-instance--persistent-disk), README lines 387–390
  - The course site links the repo's default branch, unpinned. On 2026-11-05 `git ls-remote` gave `HEAD` = `main` = `3ecef56` (`laptop/p03`).
- **Repositories used:**

| repo | branch | commit (full hash) | commit date | role |
|---|---|---|---|---|
| `dlops-io/cheese-app-v3` | `main` (default) | `3ecef56fea879ac480d260c0906cd95baf05179a` | Fri Nov 28 16:00:06 2025 -0500 | **the tutorial** |
| `dlops-io/cheese-app-v3` | `cluster-updates` | `e55178c0f66d8636d00e7deea7e744640bb8d595` | Thu Nov 20 22:45:10 2025 +0530 | K8s experiments, mostly for L22 (see §7) |
| `dlops-io/cheese-app-v3` | an unmerged staff work branch | `d1e860d` on 2026-11-05 | Thu Nov 5 17:19 2026 -0500 | **context only, not followed** (§7, §9) |
| `dlops-io/cheese-app-v2` | `2025` (was `main` until 2026-11-05) | `14f2a1420b43e9f24e977a9e67b53d7e2614013d` | Sun Nov 16 09:16:15 2025 -0500 | the 2025 app v3 grew from, used for the v2 → v3 diff (v2 `main` is now a refactored app, §7) |
| `dlops-io/cheese-app-v3` | `pipenv` | `0012c9a512b1a266f4c87fad09d84a3b52470f5b` | Wed Apr 23 08:26:16 2025 -0400 | old Ansible-based version (an ancestor of `main`), used only for the Ansible → Pulumi mapping in §7 |
| `dlops-io/cheese-app-v4` | `main` (default) | `033f18713b9e1e7985a3080e85edab3ff01cefef` | Tue Dec 2 14:13:03 2025 -0500 | used only to confirm that v4's `deploy_images/` and `deploy_single_vm/` are identical to v3's |

- **Versions in the captures (2026-11-05).** VM stand-in: Debian 12 (bookworm) x86_64, Docker 29.9.3 from `get-docker.sh`, `chromadb/chroma:latest` = Chroma 1.0.0, `nginx:stable` = nginx 1.30.6, frontend image Next.js 15.0.2, api and loader images Python 3.12.12. Laptop stand-in: Docker 29.8.2, buildx v0.37.2, git 2.54.0. Toolbox (after the two fixes): Python 3.13.18, uv 0.13.7, Google Cloud SDK 592.0.0 (gke-gcloud-auth-plugin 0.5.21, gsutil 5.38, kubectl 1.35.9), Pulumi v3.274.0, provider plugins gcp 9.3.0, docker 4.9.0, docker-build 0.0.15, command 1.1.3, kubernetes 4.23.0. Yours may be newer.
- **Path convention.** Every `path:line` in this guide is relative to the `cheese-app-v3/` repository root at the `main` commit above unless another repo is named. Short names are used where the folder is clear:
  - `src/deployment/`: `docker-shell.sh`, `docker-entrypoint.sh`, `Dockerfile` (unless another folder is named), `docker_config.json`, and the folders `deploy_images/`, `deploy_single_vm/`, `deploy_k8s/`; `nginx.conf` is `src/deployment/nginx-conf/nginx/nginx.conf`.
  - `src/deployment/deploy_single_vm/`: `create_instance.py`, `provision_instance.py`, `setup_containers.py`, `setup_webserver.py`, their `*_using_command.py` variants, and `Pulumi.dev.yaml` when cited without a folder.
  - `src/api-service/`: `api/service.py` and `api/utils/…` (`llm_rag_utils.py` and the other `llm_*_utils.py`). Under `src/frontend-react/`: `.env.production`, `Footer.jsx` (`src/components/layout/`), `DataService.js` (`src/services/`). `src/vector-db/`: `cli.py`.
  - Capture files are named like `vm/58` or `laptop/b02d`: they live in the video folder's [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l20-deployment-pulumi/assets/terminal), with their provenance in [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l20-deployment-pulumi/ASSETS.md).
  - Every reference was checked with `sed -n`/`grep -n` against the pinned commit. Code blocks headed `path:start-end` are copied mechanically from those exact line ranges.
- **Names and ids.** The README's own OS Login user (a 21-digit `sa_` number of the course project) is written `sa_000000000000000000000` in this guide, as in the video. `ac215-project` is kept as printed: it is the value you replace.
- **External sources:** Google's Vertex AI "Model versions and lifecycle" page (docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, fetched 2026-11-05) for the model retirement dates in §6 and §9; Chroma's cookbook ("Running Chroma") for the server image's persistence path, which the capture confirms (`vm/25`).
- **Ed lesson:** not accessible when these sources were checked; the course site and the repositories were used instead.
- **Colab notebooks:** none for this lecture.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 20: Deployment: Pulumi*, 30 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l20-deployment-pulumi/SLIDES.md`. The README has no diagrams, so slides 7 and 21–27 are the only pictures of the system you build; the diagram in §1 shows the same system from the code's side.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 5, 7 (the goal picture), 24, 27 |
| §2 APIs, service accounts and keys; checklist *API's to enable*, *Setup GCP Service Account* | 20, 25–26 |
| §2 costs; *Tear down, exactly*; checklist *Delete the Compute Instance*; §4 B13 | 15 (`pulumi destroy`), 29 |
| Checklist *Deployment to GCP (Manual)*; §4 A0–A10 | 8 |
| Checklist *Deployment to GCP (Single VM Instance)*; §4 B1–B11 | 19–28: B1–B8 are step 1 (19–20); B9 is step 2 (21); B10 is steps 3–6 (22–24); B11 is the test (27); 28 links the README section |
| §3.1 Infrastructure as Code | 9–12, 17 |
| §3.2 The engine loop | 12, 14, 16 |
| §3.3 Projects, stacks, config, state, secrets | 13, 15, 18 (projects, the GCS backend and secrets are tutorial-only) |
| §3.4 Outputs and the DAG; §3.5 Image tags and StackReference | none (tutorial-only) |
| §3.6 Providers | 14 (cloud providers only; the command and docker providers are tutorial-only) |
| §3.7 Identity | 20, 25–26 |
| §3.8 Reverse proxy | 7, 8 (stage 4), 24 |
| §7 Where this sits in the course | 4, 5, 9 |
| §5, §6, §8, §9 | mostly none: §5 excerpt 6 (a resource declared in the shape of slide 17's example), §6 gotcha 18 (`--refresh`, slide 16), §6 gotcha 19 (the VM runs as `deployment`, against slides 25–26) and §9 erratum 3 (the GCR name on slides 21–28) |

**Lecture ideas you need for this tutorial**
1. Everything so far runs on your own computer. Deploying puts it on a server that users can reach: here, one GCP VM running the app's containers behind NGINX on port 80 (slides 5, 7).
2. The manual route has four stages: push the images, prepare a VM, run the containers on their own network, and put NGINX in front as a reverse proxy. Keeping track of all those steps is the reason to automate (slides 8–9).
3. Pulumi is infrastructure as code in a real programming language (Python here), kept in GitHub. The program declares what should exist, and Pulumi works out how to create it (slides 10–11, 17).
4. How Pulumi works: the CLI runs your program on one machine (here, the deployment container), compares the desired state with the current one, and calls the providers' APIs to create, update or delete resources (slide 14).
5. `pulumi up` shows a preview and asks before applying. `--yes` skips the question, `--stack` picks the stack, and `--refresh` re-reads reality first. `preview`, `destroy`, `refresh`, `stack` and `config` are the other everyday commands (slides 15–16).
6. A stack is one isolated copy of the infrastructure (dev, staging, prod) with its own state and config (slide 18).
7. The automated deployment has six steps, and the code follows them in order: set up the local container, build and push the images, create the VM, provision it, start the containers, add the web server (slides 19, 21–24).
8. Two service accounts split the powers: `deployment` (admin on your group's project) builds the infrastructure, and `gcp-service` (read images, call Vertex AI) is for the running app (slides 20, 25–26).
9. Test from a browser on port 80, and delete everything when you are done (slides 27, 29).

**Where the slides and today's tutorial differ** (in each case the repo, as verified here, is what runs today)
- Slides 21–28 say Google Container Registry (GCR); slides 19–20 say GAR. The code pushes to Artifact Registry (`us-docker.pkg.dev/<proj>/cheese-app-repository`), Container Registry is retired, and you must create the repository yourself (§2, §9 errata 1 and 3).
- Slides 20, 25 and 26 have `gcp-service` read the images on the VM. Pulumi's Docker provider pulls with the deployment container's credentials, that is, as `deployment`. The `gcp-service` login on the VM only helps a `docker pull` you type by hand (§3.7).
- Slides 25–26 put only the narrow key on the VM side. The VM itself runs as `deployment@…` (README line 355 sets `security:gcp_service_account_email` to it), limited only by its scopes. The `gcp-service` key is mounted into `api-service` and the loader for Vertex AI, which slide 26 does not draw (§3.7, §6 gotcha 19).
- Slides 7 and 22–27 have the VM read models from a GCS bucket (the "class bucket" of slide 26). In v3 the API downloads its model from a GitHub release into `/persistent/experiments` (`llm_cnn_utils.py:34`, `:122-124`), `GCS_BUCKET_NAME` is never read, and the only bucket in use is the Pulumi state bucket, which no slide shows (§2, §9 erratum 13).
- Slides 7 and 22–27 draw an NFS "GCE Persistent Volume" (labelled "Leaderboard" on 22–27). It is a 50 GB block disk mounted at `/mnt/disk-1`, holding `/persistent` (the model and chat history) and ChromaDB's folder, and there is no leaderboard (§4 B10, §6 gotcha 23).
- Slide 23 labels the frontend HTTP 80. It listens on 3000, as slides 7 and 24 say; only nginx has port 80 (§1).
- Slides 8 and 28 name only the API and the frontend (plus nginx), and slides 7, 24, 26 and 27 draw four containers (23 draws three, before nginx). Both routes run five: the vector DB, the one-shot loader, `api-service`, `frontend` and `nginx` (§4 A6–A8, B10; §9 erratum 14).
- Slide 18 suggests stack names like `cheese-app-dev`. The tutorial uses a stack called `dev` in each of two projects (`deploy-images`, `deploy-single-vm`). Keep those names, because `StackReference("organization/deploy-images/dev")` depends on them (§3.5, §5 excerpt 9).
- Slide 14 says Pulumi manages infrastructure through cloud APIs. Steps 4–6 go through SSH instead: provisioning runs create-only shell scripts that Pulumi cannot look into (so they must be idempotent), and the containers are managed through the VM's Docker daemon (§3.6).


## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept: replace `ac215-project`, `<YOUR GCP_PROJECT>` and the README's `sa_000000000000000000000` user with your own values, and remove the angle brackets together with the placeholder text). Plain items are console clicks or checks. Items marked *(extra)* are not in the README; they come from §2, §4 and §6 of this guide. Where a command fails as printed today, it stays verbatim and the working variant follows as a note, with the capture that shows it. Part A runs on your laptop and then on the VM over SSH. Part B runs on your laptop and in the console up to `sh docker-shell.sh`, and inside the toolbox (prompt `root@<id>:/app#`) from then on.

### Before the README *(extra)*

- [ ] `git clone https://github.com/dlops-io/cheese-app-v3.git` — *(extra)* get the code (`Cloning into 'cheese-app-v3'...`). If you use this workspace's `tools/sync_tutorials.py`, the clone is `tutorials/cheese-app-v3`.
- [ ] `git -C cheese-app-v3 log -1 --format='%H %ci %s'` — *(extra)* the capture shows `3ecef56fea879ac480d260c0906cd95baf05179a 2025-11-28 16:00:06 -0500 v4->v3`; a different hash means the repo has changed since this guide was made (§7, §9).
- [ ] `mkdir -p secrets` — *(extra)* in the folder that holds the clone, **next to** it, not inside it: `docker-shell.sh:9` looks three levels up from `src/deployment`. With a clone at `~/Desktop/AC215/cheese-app-v3` that is `~/Desktop/AC215/secrets/`; with `tools/sync_tutorials.py` it is `tutorials/secrets/`.

### Deployment to GCP (Manual)

*Ensure you have all your container built and works locally* (README lines 10–16)
- [ ] vector-db: ChromaDB is up and running.
- [ ] api-service: go to `http://localhost:9000/docs` and make sure you can see the API Docs — with v3 code this page says "No operations defined in spec!" (§9 erratum 4).
- [ ] `http://localhost:9000/status` — *(extra)* the reliable check for v3 code: `{"version":"3.0"}`.
- [ ] frontend-react: go to `http://localhost:3000/` and make sure you can see the home page.

*Push Docker Images to Docker Hub* (README lines 18–35)
- [ ] Sign up in Docker Hub and create an [Access Token](https://hub.docker.com/settings/security); open a new terminal.
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — stores your Docker Hub credentials. Typed as printed it fails: `bash: -c: line 1: syntax error near unexpected token 'newline'` (`laptop/a01`), because `<` and `>` are redirections. Working variant: `echo "$TOKEN" | docker login -u yourname --password-stdin` (also keeps the token out of your shell history).
- [ ] *(extra)* Change `DOCKER_USERNAME="dlops"` to your Docker Hub user in `src/api-service/docker-hub.sh:11` (same line in `src/frontend-react/` and `src/vector-db/`); otherwise the push fails with `push access denied … insufficient_scope: authorization failed` (`laptop/a02`).
- [ ] `sh docker-hub.sh` — in `src/api-service`, outside the docker shell: recreates a buildx builder `multi-arch`, builds `linux/amd64,linux/arm64` and pushes.
- [ ] `sh docker-hub.sh` — in `src/frontend-react`: the production build (`Dockerfile`, not `Dockerfile.dev`), `linux/amd64` only.
- [ ] `sh docker-hub.sh` — in `src/vector-db`: builds and pushes the `vector-db-cli` image.
- [ ] `docker buildx use default` — *(extra)* switches back from the `multi-arch` builder, which `--use` made current (`laptop/a03`); a tidy reset (§6 gotcha 3).

*Install Docker on VM* (README lines 39–51)
- [ ] Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances): defaults, except Machine Type **N2D**, disk size **50 GB** (OS & Storage), and **Allow HTTP traffic** + **Allow HTTPS traffic** (Networking).
- [ ] SSH into your newly created instance.
- [ ] `curl -fsSL https://get.docker.com -o get-docker.sh` — downloads Docker's install script (silent).
- [ ] `sudo sh get-docker.sh` — installs Docker Engine on the VM.
- [ ] `sudo docker --version` — prints a version (`Docker version 29.9.3, build 5457199` in the capture).

*Create folders and give permissions* (README lines 53–68; the README lists these six commands twice, as bullets and again as a code block, so run them once, from your home directory)
- [ ] `sudo mkdir persistent-folder` — for the api-service's `/persistent`.
- [ ] `sudo mkdir secrets` — for `gcp-service.json`.
- [ ] `sudo mkdir -p conf/nginx` — for `nginx.conf`.
- [ ] `sudo chmod 0777 persistent-folder` — world-writable (demo-grade).
- [ ] `sudo chmod 0777 secrets` — world-writable (demo-grade).
- [ ] `sudo chmod -R 0777 conf` — world-writable, recursively.

*Add secrets file* (README lines 70–75)
- [ ] `echo '<___Json Key___>' > secrets/gcp-service.json` — paste the `gcp-service` key's JSON in place of the placeholder, inside the single quotes (works because the key contains no `'`). Run as printed, the file just contains `<___Json Key___>` (`vm/18`).

*Create Docker network* (README lines 78–81)
- [ ] `sudo docker network create cheese-app-network` — a bridge network, so containers find each other by name; prints the network id.

*Run vector-db* (README lines 83–98)
- [ ] `sudo docker pull chromadb/chroma:latest` — the unpinned ChromaDB server image (Chroma 1.0.0 on 2026-11-05, `vm/24`).
- [ ] `sudo docker stop cheese-app-vector-db || true` — stops an old container if there is one; the first time it prints `Error response from daemon: No such container: cheese-app-vector-db` and still succeeds.
- [ ] `sudo docker rm cheese-app-vector-db || true` — removes it (same harmless error the first time).
- [ ] Start ChromaDB (detached, port 8000, `--restart always`); prints the container id. The mount misses Chroma 1.x's data path `/data` (§6 gotcha 23; fix: `-v ./docker-volumes/chromadb:/data`):
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
- [ ] Download the pre-computed embeddings and load them (change `GCP_PROJECT=ac215-project` to your project); it logs 11 `Processing file:` lines, inserts 14,356 chunks in the capture, and exits. It makes no Google call:
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
- [ ] Start the API (detached; without `-e DEV=1` the image's entrypoint runs production uvicorn). The first start pulls a 5.07 GB image:
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
- [ ] `curl -s -i http://localhost:9000/` — *(extra)* on the VM: `{"message":"Welcome to AC215"}` (`vm/33`). `/status` returns `404 {"detail":"Not Found"}` with the public image, which predates v3's `/status` (`vm/34`, §6 gotcha 24).
- [ ] Optional, interactive mode "like we did in development" (README lines 131–145): `--rm -ti` plus `-e DEV=1` drops you into a shell where you start the server with `uvicorn_server`. Run while the detached container exists, it fails: `docker: Error response from daemon: Conflict. The container name "/api-service" is already in use …` (`vm/38`). Working variant: `sudo docker rm -f api-service` first, and start the detached one again after `exit` (`vm/39-41`).
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

*Run frontend* (README lines 147–151)
- [ ] `sudo docker run -d --name frontend -p 3000:3000 --network cheese-app-network dlops/cheese-app-frontend-react` — the production Next.js server on port 3000 (`▲ Next.js 15.0.2`, `BASE_API_URL: /api-service`).
- [ ] `sudo docker container ls` — *(extra)* `cheese-app-vector-db`, `api-service` and `frontend` are up.

*Add NGINX config file* (README lines 153–214)
- [ ] Create `nginx.conf` (README lines 156–213) — routes `/api-service/` to `api-service:9000/` and everything else to `frontend:3000`. Quoting bug: the `log_format` lines contain single quotes, so the written file loses its log variables (58 lines, `log_format  main   - []`, `vm/45`; §4 A8; fix in the next item). It prints nothing and exits 0.
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
- [ ] Open `http://<Your VM IP Address>/` — the frontend loads (`<title>Formaggio</title>`). *(extra)* On the VM: `curl -s http://localhost/api-service/` → `{"message":"Welcome to AC215"}` through nginx (`vm/49`). Chat additionally needs a Vertex AI model that still exists (§9 erratum 20).

*Tear down* *(extra; missing from the README)*
- [ ] *(extra)* Delete the VM: Compute Engine → VM instances → select → Delete, with its boot disk. Left running it costs about $2/day.

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
- [ ] cd into `deployment` — the folder is `src/deployment`.
- [ ] Go into `docker-shell.sh` and change `GCP_PROJECT` to your project id: line 13, `export GCP_PROJECT="ac215-project" # Change to your GCP Project`.
- [ ] `ls ../../../secrets` — *(extra)* from `src/deployment`: `deployment.json` and `gcp-service.json` are there.
- [ ] `sh docker-shell.sh` — builds `cheese-app-deployment` for `linux/amd64` and starts it with the Docker socket, code and secrets mounted; the entrypoint logs in as the deployment SA, creates the state bucket if missing and runs `pulumi login gs://…`. As committed it does **not** build today: `[ 2/16]` fails with 22 `E: Failed to fetch …debian-security… 404 Not Found` and the script then prints `pull access denied` (`laptop/b02`). Working variant: the two edits below, then run it again.
- [ ] *(extra)* Fix 1, in `src/deployment/Dockerfile:4`: `FROM python:3.13-slim-bullseye` → `FROM python:3.13-slim-bookworm` (`laptop/b02a`).
- [ ] *(extra)* Fix 2, in `src/deployment/Dockerfile:30`: `google-cloud-sdk google-cloud-sdk-gke-gcloud-auth-plugin` → `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin` (`laptop/b02b`, `b02c`). With both, `[+] Building 91.9s (21/21) FINISHED` and a prompt in `/app` (`laptop/b02d`).
- [ ] `gcloud --version` — the gcloud SDK in the toolbox (`Google Cloud SDK 592.0.0`).
- [ ] `pulumi version` — the Pulumi CLI (`v3.274.0`).
- [ ] `kubectl version --client` — kubectl, used in L22 (`Client Version: v1.35.9-dispatcher`: gcloud's bundled kubectl comes first on `PATH`).
- [ ] `gcloud auth list` — the active account must be `deployment@<your-project>.iam.gserviceaccount.com`. `No credentialed accounts.` (`laptop/b06`) means the entrypoint's login failed: fix `secrets/deployment.json` before going on.
- [ ] `gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us` — *(extra)* creates the registry repository that `deploy_images` pushes to and that nothing else creates (§2, §9 erratum 1).

*Configuring OS Login for service account* (README lines 283–291)
- [ ] `gcloud compute project-info add-metadata --project <YOUR GCP_PROJECT> --metadata enable-oslogin=TRUE` — turns on OS Login for the project. Typed as printed: `bash: line 1: YOUR: No such file or directory` (`laptop/b08`); replace `<YOUR GCP_PROJECT>` brackets and all.
- [ ] `gcloud compute project-info add-metadata --project ac215-project --metadata enable-oslogin=TRUE` — the README's example (line 290), with `ac215-project` to replace. Without an active account: `You do not currently have an active account selected.` (`laptop/b09`).

*Create SSH key for service account* (README lines 293–298)
- [ ] `cd /secrets` — the container's view of your laptop's `secrets/` folder.
- [ ] `ssh-keygen -f ssh-key-deployment` — creates the key pair; **press Enter twice (empty passphrase)**, because Pulumi cannot type one.
- [ ] `cd /app` — back to `src/deployment` (the Pulumi programs).

*Providing public SSH keys to instances* (README lines 300–316)
- [ ] `gcloud compute os-login ssh-keys add --key-file=/secrets/ssh-key-deployment.pub` — registers the key with the deployment SA's OS Login profile; **copy the `username: sa_<digits>`** from the output.

*Deployment Setup* (README lines 318–322)
- [ ] Skip it: `inventory.yml` is a leftover from the old Ansible version and does not exist on `main` (`ls: cannot access 'inventory.yml'`, `laptop/b13`; §9 erratum 2).

*Build and Push Docker Containers to Google Artifact Registry* (README lines 327–345)
- [ ] cd into `deploy_images` — `/app/deploy_images`.
- [ ] `pulumi stack init dev` — creates the `dev` stack; its state goes to the GCS bucket (`Created stack 'dev'`). If it offers `Connect to Pulumi Cloud …` / `Press <ENTER> to log in with your browser`, do not press Enter: Pulumi is not logged in to your bucket (`laptop/b14`, §6 gotcha 27).
- [ ] `pulumi config set gcp:project ac215-project` — use your project ID; writes `Pulumi.dev.yaml` in your checkout.
- [ ] `pulumi stack select dev` — *(extra)* instead of `init` if you get `stack 'dev' already exists`.
- [ ] `pulumi preview --stack dev --refresh` — shows the plan without changing anything: three `docker-build:index:Image` creates and the `…-tags` outputs with a timestamp tag.
- [ ] `pulumi up --stack dev --refresh -y` — builds the three images for amd64 and pushes them with timestamp tags; expect about `+ 4 created` and `Outputs:` with `cheese-app-api-service-tags` and others.

*Create Compute Instance (VM) & Deploy Containers* (README lines 347–383)
- [ ] cd into `deploy_single_vm` from the `deployment` folder — `cd ../deploy_single_vm`.
- [ ] `pulumi stack init dev` — the `dev` stack of the `deploy-single-vm` project, in the same state bucket.
- [ ] `pulumi config set gcp:project ac215-project` — your project ID.
- [ ] `pulumi config set security:ssh_user sa_000000000000000000000` — **your** `sa_…` username from OS Login (the README prints its own account's number here).
- [ ] `pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com` — your project in the e-mail.
- [ ] `pulumi config` — *(extra)* check the three values before deploying.
- [ ] `pulumi preview --stack dev --refresh` — about 30 resources to create. It starts with `gcp:compute:Disk cheese-app-demo-disk`, `gcp:compute:Network cheese-app-network` and the firewalls `allow-http`, `allow-https`, `allow-ssh`; the Ubuntu image lookup is its first Google call (`laptop/b43`).
- [ ] `pulumi up --stack dev --refresh -y` — creates the network, firewalls, disk and VM, provisions it over SSH and starts the containers; ends with `Outputs:` including `instance_ip`.
- [ ] Go to `http://<instance_ip>/` — the footer shows "Frontend version: 1" and "API version: 3.0".
- [ ] `curl http://<instance_ip>/api-service/status` — *(extra)* `{"version":"3.0"}`.
- [ ] SSH into the server from the GCP console, or `ssh -i /secrets/ssh-key-deployment sa_…@<instance_ip>` — *(extra)* from the toolbox (the exported `ssh_command` omits `-i`).
- [ ] `sudo docker container ls` — the running containers.
- [ ] `sudo docker container logs api-service -f` — follow the API log (Ctrl-C to stop).
- [ ] `sudo docker container logs frontend -f` — follow the frontend log.
- [ ] `sudo docker container logs nginx -f` — follow the nginx log.
- [ ] `sudo docker exec -it api-service /bin/bash` — a shell inside the api-service container (`app@<id>:/app$`; `exit` to leave).
- [ ] `sudo docker exec -it nginx /bin/bash` — a shell inside the nginx container (`root@<id>:/#`; `nginx -v` → `nginx/1.30.6` in the capture).

*Redeploy after a code change* *(extra, §4 B12)*
- [ ] *(extra)* `pulumi up --stack dev --refresh -y` in `deploy_images` (new tags), then in `deploy_single_vm`. Read the preview before `-y`: `frontend`, `vector-db-loader` and `api-service` show `+-` replace.

### Delete the Compute Instance / Persistent disk

*(README lines 387–390)*
- [ ] `pulumi destroy --stack dev --refresh -y` — run it **in `deploy_single_vm`**: deletes containers, VM, disk, firewalls and VPC in reverse dependency order. It keeps the stack's history and config ("If you want to remove the stack completely, run `pulumi stack rm dev`", `laptop/b45`).
- [ ] `gcloud artifacts repositories delete cheese-app-repository --location=us` — *(extra)* the images survive `pulumi destroy` (`retain_on_delete=True`).
- [ ] `pulumi stack rm dev` — *(extra, optional)* deletes a stack and its history; it also deletes that folder's `Pulumi.dev.yaml` unless you pass `--preserve-config`.
- [ ] `gcloud storage rm -r gs://<proj>-pulumi-state-bucket` — *(extra)* the state bucket, last, once no stack holds anything; then the service-account JSON keys in IAM when the course ends.
- [ ] `docker buildx rm multi-arch` and `docker image rm cheese-app-deployment` — *(extra)* on the laptop, after leaving the toolbox.

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
- Docker Desktop (or Docker Engine) with BuildKit. Nothing else needs installing locally: gcloud, Pulumi, kubectl, Helm and uv all live in the deployment image, the toolbox (`src/deployment/Dockerfile:28-55`). As committed it no longer builds: change `Dockerfile:4` to `FROM python:3.13-slim-bookworm` and the packages on `:30` to `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin` (§4 B3, captured 2026-11-05).
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
- Baked into the image: `PULUMI_CONFIG_PASSPHRASE=""` (`Dockerfile:51`). Stack secrets are encrypted with an **empty passphrase**. Inside the toolbox `env` shows `PULUMI_CONFIG_PASSPHRASE=` (empty) next to the variables below (`laptop/b07`).
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
| GCS state bucket `<proj>-pulumi-state-bucket` (`docker-entrypoint.sh:15-20`) | cents | keep it while any stack exists; delete it last (`gcloud storage rm -r gs://<proj>-pulumi-state-bucket`) |
| Vertex AI calls (each chat/RAG request) | per token | stop the VM |
| **Part A manual VM** | same as the VM row | **the README never tells you to delete it.** Delete it in the console (Compute Engine → VM instances → Delete) |
| Docker Hub images (Part A) | free | optional |
| laptop disk: the toolbox image (2.61 GB, `laptop/b36`), the `multi-arch` BuildKit builder, the builder pulumi-docker-build starts, `src/deployment/pulumi-plugins/` | disk only | `docker image rm cheese-app-deployment`, `docker buildx rm multi-arch`, `docker buildx use default`; delete the plugins folder (it is `.gitignore`d) |

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
- **Secrets.** Values marked secret (`pulumi config set --secret …`, or provider inputs such as pulumi-command's `connection`, which carries your private key) are encrypted in config and state with the stack's secrets provider. Here that is the *passphrase* provider with `PULUMI_CONFIG_PASSPHRASE=""` (`Dockerfile:51`) and a salt committed in `Pulumi.dev.yaml:1`. All three committed salts were made with the empty passphrase (checked for the digest), so `pulumi config set` works without a prompt (`laptop/b32`). In practice the encryption protects nothing: real protection comes from **who can read the bucket**.
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
- **The public Part A image is different.** `dlops/cheese-app-api-service:latest` predates the `ROOT_PATH` mount and `/status` (`vm/36`), and its entrypoint starts uvicorn with `--root-path /api-service` (`vm/37`), which only changes the `servers` entry of its `/openapi.json` to `/api-service` (`vm/50`). Routing behind nginx works the same: `/api-service/` reaches its `/` route (`vm/49`).
- **Analogy.** A hotel receptionist: "Room service, extension 9000" is routed to the kitchen, and the kitchen hears only "extension 9000".
- **Misconception.** "Opening port 9000 in the firewall would be simpler." It would expose the API on a second origin (`http://<ip>:9000`). Cross-origin calls only work here because the API allows every origin (`allow_origins=["*"]`, `api/service.py:19-25`), which is itself a smell. You would also need a second port secured with TLS, and the IP would have to be baked into the frontend at build time (`NEXT_PUBLIC_*` values are compiled in).

---


## 4. Step-by-step walkthrough

Steps follow the README order: A0–A10 for "Deployment to GCP (Manual)", B1–B13 for "Deployment to GCP (Single VM Instance)" and the delete section. Commands are verbatim from the README unless marked *(extra)*.

**About the outputs below.** Outputs labelled *captured* are real, trimmed (`…`) from the 2026-11-05 captures (file named with each block; `[exit N]` lines omitted unless they matter; container ids, timestamps and private addresses shortened). The capture machines had **no Google account, no Docker Hub login and no key**, so:
- `vm/…` is a fresh Debian 12 x86_64 machine named `cheese-app-vm` standing in for the VM you create in the console. It had a GCP image's baseline (sudo, curl, python3) and Docker from the README's own `get-docker.sh`. Everything in Part A after the SSH step ran on it as printed; the `curl` checks of the site ran on the machine itself, not from a browser.
- `laptop/…` is a fresh Docker engine standing in for your laptop. The toolbox ran in it after the two fixes in B3, and every command that needs Google shows its **first real error**. The two Pulumi programs then also ran on Pulumi's local file backend (`pulumi login --local`, not a README step and not something you should do) until their first Google call.
- *Expected* output is the README's own printed snippet; what only the cloud can show is described, never invented.

Versions are those of the recording day (see *At a glance*); yours may be newer.

### Part A: manual deployment (README lines 4–222)

**A0. Check that everything runs locally (README lines 10–16).** *(not captured)*
- Action: have *this repo's* (v3) containers running locally: ChromaDB, api-service at `http://localhost:9000/docs`, frontend at `http://localhost:3000/`. If you followed L18 after 2026-11-05, your cheese-app-v2 is the refactored `main`, a different app from the one v3 deploys (§7); run v3's own `src/*/docker-shell.sh` here.
- Checkpoint: the home page loads. For v3 code use **`http://localhost:9000/status` → `{"version":"3.0"}`** as the API check rather than `/docs`: in v3, `/docs` is served by the *outer* FastAPI app (`api/service.py:49`), which has no routes, so the page says "No operations defined in spec!" (§9 erratum 4).

**A1. Log in to Docker Hub (README line 21).**
- Command: `docker login -u <USER NAME> -p <ACCESS TOKEN>`. Replace each placeholder **including the angle brackets**. *Captured* as printed (`laptop/a01`):
  ```
  $ docker login -u <USER NAME> -p <ACCESS TOKEN>
  bash: -c: line 1: syntax error near unexpected token `newline'
  bash: -c: line 1: `docker login -u <USER NAME> -p <ACCESS TOKEN>'
  ```
  The shell reads `<` and `>` as redirections. Prefer `echo "$TOKEN" | docker login -u yourname --password-stdin`, which keeps the token out of your shell history.
- If it fails with `unauthorized`: create a new access token at hub.docker.com → Settings → Security.

**A2. Build, tag and push the three images (README lines 24–35): `sh docker-hub.sh` in `api-service`, `frontend-react` and `vector-db`.**
- Under the hood (`src/api-service/docker-hub.sh:20-35`): deletes and recreates a buildx builder named `multi-arch` with `--use` (`:27`), builds for `linux/amd64,linux/arm64` (`:31`; the frontend builds `linux/amd64` only, `src/frontend-react/docker-hub.sh:31,35`), then builds again with `--push` (`:35`). The first build only warms the cache: a docker-container builder keeps its result in the build cache unless told to `--load` or `--push`.
- **Before running:** change `DOCKER_USERNAME="dlops"` (`src/api-service/docker-hub.sh:11`; same line in the other two scripts) to *your* Docker Hub user. *Captured* in `src/frontend-react` without that change and without a login (`laptop/a02`):
  ```
  $ sh docker-hub.sh
  Docker Username: dlops
  Building production image...
  Creating new multi-arch builder...
  multi-arch
  Building multi-arch image...
  #0 building with "multi-arch" instance using docker-container driver
  …
  #14 DONE 59.2s
  …
  #18 21.78  ✓ Compiled successfully
  …
  WARNING: No output specified with docker-container driver. Build result will only remain in the build cache. To push result image into registry use --push or to load image into docker use --load
  Pushing multi-arch image to registry...
  …
  ERROR: failed to build: failed to solve: failed to push dlops/cheese-app-frontend-react: push access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
  ```
  The build itself works (step `#14` is `npm ci`, `#18` the Next.js build); only the push needs your account and your user name.
- Checkpoint: the images appear under your Docker Hub account.
- Side effect: `multi-arch` is now the current builder (*captured*, `laptop/a03`: `multi-arch*  docker-container … v0.34.2`). Run `docker buildx use default` afterwards to switch back (§6 gotcha 3).
- Shortcut: the later `docker run` commands use the public `dlops/...` images, so you can skip this step if you only want to practise the VM part. Those images are older than `3ecef56` (A7, §6 gotcha 24).

**A3. Create the VM in the console (README lines 40–44).** Machine type N2D, 50 GB disk, tick "Allow HTTP traffic" and "Allow HTTPS traffic". The ticks put the network tags `http-server` and `https-server` on the VM, which the default VPC's firewall rules for ports 80 and 443 match.

**A4. SSH in and install Docker (README lines 46–51).**
- Commands (README lines 48–49): `curl -fsSL https://get.docker.com -o get-docker.sh` (silent), then `sudo sh get-docker.sh`. *Captured* (`vm/02`, `vm/03`):
  ```
  $ sudo sh get-docker.sh
  # Executing docker install script, commit: ada7a567e59b3935bd601bb21e422da50e80e376
  + sh -c apt-get -qq update >/dev/null
  …
  + sh -c echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list
  …
  + sh -c DEBIAN_FRONTEND=noninteractive apt-get -y -qq install docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-ce-rootless-extras docker-buildx-plugin docker-model-plugin >/dev/null
  …
  To run Docker as a non-privileged user, consider setting up the
  Docker daemon in rootless mode for your user:
  …
  $ sudo docker --version
  Docker version 29.9.3, build 5457199
  ```
  The stand-in also printed `WARNING: unable to enable the docker service`, because a container has no systemd; on a real VM systemd starts Docker at this point.
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
then `echo '<___Json Key___>' > secrets/gcp-service.json` (README line 74) and `sudo docker network create cheese-app-network` (README line 80). All six folder commands are silent. *Captured* (`vm/16`, `vm/18`, `vm/19`):
```
$ ls -la
…
drwxrwxrwx 3 root    root     4096 Nov  5 22:07 conf
-rw-r--r-- 1 student student 23866 Nov  5 22:07 get-docker.sh
drwxrwxrwx 2 root    root     4096 Nov  5 22:07 persistent-folder
drwxrwxrwx 2 root    root     4096 Nov  5 22:07 secrets
$ cat secrets/gcp-service.json
<___Json Key___>
$ sudo docker network create cheese-app-network
570b3ab4d9c8…
```
- Paste your `gcp-service` key's JSON where the placeholder is (inside the single quotes; it works because a key file contains no `'`). The capture ran the line as printed, so the "key" is the placeholder; nothing in Part A needed a real one except chat.
- The `0777` permissions are demo-grade. Run every later command from this same directory: the `$(pwd)/…` and `./docker-volumes/…` mounts are relative to it.

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
- The first `stop` and `rm` print `Error response from daemon: No such container: cheese-app-vector-db`; `|| true` keeps the exit status 0, so a script would go on. *Captured* checks after the start (`vm/24`, `vm/25`; *extra*):
  ```
  $ sudo docker ps; curl -s http://localhost:8000/api/v2/heartbeat; echo; curl -s http://localhost:8000/api/v2/version; echo
  CONTAINER ID   IMAGE             …   PORTS                    NAMES
  6eb3a99fc218   chromadb/chroma   …   0.0.0.0:8000->8000/tcp   cheese-app-vector-db
  {"nanosecond heartbeat":…}
  "1.0.0"
  $ sudo docker logs cheese-app-vector-db 2>&1 | head -30
  ==========
  persist_path: "/data"
  …
  Saving data to: /data
  Connect to Chroma at: http://localhost:8000
  ```
  `persist_path: "/data"` is the reason the README's mount at `/chroma/chroma` stays empty (§6 gotcha 23).
- Then the loader:
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
- Under the hood: `cli.py --download` fetches *pre-computed* embeddings from a GitHub release (`src/vector-db/cli.py:487`), and `--load` drops and re-creates the `recursive-split-collection` (`:286-292`). No Google call is made, so the placeholder key did not matter. *Captured* (`vm/27`):
  ```
  Container is running!!!
  Architecture: x86_64
  …
  Python version: Python 3.12.12
  UV version: uv 0.9.9
  …
  CLI Arguments: Namespace(chunk=False, embed=False, load=True, query=False, chat=False, get=False, agent=False, download=True, chunk_type='recursive-split')
  download()
  load()
  Creating collection: recursive-split-collection
  Collection 'recursive-split-collection' did not exist. Creating new.
  …
  Number of files to process: 11
  Processing file: outputs/embeddings-recursive-split-The book of The Cheese Being traits and stories of Ye Olde Cheshire Cheese.jsonl
  Shape: (923, 3)
  …
  Inserted 163 items...
  Finished inserting 163 items into collection 'recursive-split-collection'
  ```
  The 11 files add up to **14,356** chunks. Change `GCP_PROJECT=ac215-project` to your project anyway.
- *Captured*, where the data went (`vm/28`, *extra*): `docker-volumes/chromadb` on the VM is empty, while inside the container `/data` holds `chroma.sqlite3` (36,474,880 bytes). The chunks live in the container's writable layer: they survive a restart, not a `docker rm`.

**A7. Start api-service and frontend (README lines 118–127, 150).**
- The detached `docker run` (README lines 118–127) pulls the image the first time (`Unable to find image 'dlops/cheese-app-api-service:latest' locally`, then the pull and the container id, `vm/30`). Change `-e GCP_PROJECT=ac215-project` (README line 124) to your project. Without `-e DEV=1` the entrypoint runs production uvicorn. *Captured* start-up log (`vm/31`, *extra*):
  ```
  $ sudo docker logs api-service 2>&1 | head -60
  Container is running!!!
  …
  The following commands are available:
      uvicorn_server
          Run the Uvicorn Server
  …(TensorFlow CPU/CUDA notices)…
  Loading CNN Model...
  best_model_path: /persistent/experiments/experiment_1760994796/mobilenetv2_train_base_True.keras
  Model: "mobilenetv2_train_base_True"
  …
   Total params: 2,422,470 (9.24 MB)
  …
  INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
  ```
  The API downloads its CNN model from a GitHub release on start-up into `/persistent`, so the first start needs a few seconds and outbound internet. The image is **5.07 GB** (`vm/32`).
- *Captured* API checks on the VM (`vm/33`, `vm/34`, *extra*):
  ```
  $ curl -s -i http://localhost:9000/
  HTTP/1.1 200 OK
  …
  {"message":"Welcome to AC215"}
  $ curl -s -i http://localhost:9000/status
  HTTP/1.1 404 Not Found
  …
  {"detail":"Not Found"}
  ```
  The public image is older than the code you are reading: its `api/service.py` has `@app.get("/")`, `@app.get("/square_root/")` and six routers, and 0 matches for `ROOT_PATH`, `mount` or `/status` (`vm/36`). Use `/` here; an image you build from `3ecef56` (A2, with your user name in the `docker run` lines) answers `/status` with `{"version":"3.0"}`. Unlike v3 code, this image's `/docs` is a real Swagger page whose `/openapi.json` lists `/`, `/llm-agent/…`, `/llm-cnn/…`, `/llm-rag/…` and more (`vm/35`).
- Optional (README lines 131–145): the interactive variant `sudo docker run --rm -ti --name api-service … -e DEV=1 …`. *Captured* while the detached container runs (`vm/38`):
  ```
  docker: Error response from daemon: Conflict. The container name "/api-service" is already in use by container "433a46beec04…". You have to remove (or rename) that container to be able to reuse that name.
  ```
  It is an alternative, not an extra step. `sudo docker rm -f api-service` first; then it opens a shell `app@<id>:/app$` with the same banner, where `uvicorn_server` starts the dev server; `exit`, and start the detached one again (`vm/39-41`). nginx and the frontend find the API by this name.
- Frontend (README line 150): `sudo docker run -d --name frontend -p 3000:3000 --network cheese-app-network dlops/cheese-app-frontend-react`. *Captured* check (`vm/43`, *extra*):
  ```
  NAMES                  IMAGE                             PORTS
  frontend               dlops/cheese-app-frontend-react   0.0.0.0:3000->3000/tcp
  api-service            dlops/cheese-app-api-service      0.0.0.0:9000->9000/tcp
  cheese-app-vector-db   chromadb/chroma                   0.0.0.0:8000->8000/tcp
  <title>Formaggio</title>
     ▲ Next.js 15.0.2
  …
   ✓ Ready in 67ms
  BASE_API_URL: /api-service
  ```

**A8. nginx config and container (README lines 156–219).**
- The `echo '…' > conf/nginx/nginx.conf` of README lines 156–213 is silent and exits 0 (`vm/44`).
- **Quoting bug:** the `echo '…'` wraps a config that itself contains single quotes (the `log_format` lines 165–167). Bash closes and reopens the quoted string there, so the `$variables` between the inner quotes are expanded by the shell, as empty variables. *Captured* (`vm/45`, *extra*):
  ```
  $ wc -l conf/nginx/nginx.conf; sed -n '7,13p' conf/nginx/nginx.conf | cat -A | cut -c1-90
  58 conf/nginx/nginx.conf
  http {$
      include       /etc/nginx/mime.types;$
      default_type  application/octet-stream;$
      log_format  main   - []  $
                          $
                         ;$
      access_log  /var/log/nginx/access.log  main;$
  ```
  nginx still starts and routes correctly, but every access-log line is just `-[]` (`vm/51`). Fix: write the file with a quoted heredoc (`cat > conf/nginx/nginx.conf <<'EOF'` … `EOF`), or `scp` the repo's `src/deployment/nginx-conf/nginx/nginx.conf` (exercise B2).
- Command (README line 219): `sudo docker run -d --name nginx -v $(pwd)/conf/nginx/nginx.conf:/etc/nginx/nginx.conf -p 80:80 --network cheese-app-network nginx:stable`. *Captured* (`vm/47`, *extra*):
  ```
  $ sudo docker container ls
  CONTAINER ID   IMAGE                             …   PORTS                    NAMES
  225928af4aee   nginx:stable                      …   0.0.0.0:80->80/tcp       nginx
  f6ddb0d7038d   dlops/cheese-app-frontend-react   …   0.0.0.0:3000->3000/tcp   frontend
  a18ad0b0f412   dlops/cheese-app-api-service      …   0.0.0.0:9000->9000/tcp   api-service
  6eb3a99fc218   chromadb/chroma                   …   0.0.0.0:8000->8000/tcp   cheese-app-vector-db
  ```

**A9. Open `http://<Your VM IP Address>/` (README line 222).** The frontend loads. *Captured* from the VM itself (`vm/48`, `vm/49`, *extra*):
```
$ curl -s -i http://localhost/ | head -8; curl -s http://localhost/ | grep -o '<title>[^<]*</title>'
HTTP/1.1 200 OK
Server: nginx
…
<title>Formaggio</title>
$ curl -s -i http://localhost/api-service/; echo; curl -s -i http://localhost/api-service/status; echo
HTTP/1.1 200 OK
Server: nginx
…
{"message":"Welcome to AC215"}
HTTP/1.1 404 Not Found
Server: nginx
…
{"detail":"Not Found"}
```
nginx stripped the `/api-service` prefix: `/api-service/` reached the API's `/` route, which returned its welcome message. (The API's own log still lists the request as `GET /api-service/ … 200 OK`, `vm/53`, because this image starts uvicorn with `--root-path /api-service`, `vm/37`, and uvicorn logs the path with that root path.) The `404` is the old image again (A7). Chat needs the `gcp-service` key to have Vertex AI access, **and** a generative model that still exists: the code calls `gemini-2.0-flash-001`, which Google's model-versions page lists as retired on 2026-06-01 (§6 gotcha 22).
- *Captured*, why one missing container takes the whole site down (`vm/58`, `vm/59`, *extra*):
  ```
  $ sudo docker stop frontend; sudo docker restart nginx; sleep 3; sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}'; …
  NAMES                  STATUS
  nginx                  Exited (1) 3 seconds ago
  frontend               Exited (0) 13 seconds ago
  api-service            Up 10 minutes
  cheese-app-vector-db   Up 16 minutes
  nginx: [emerg] host not found in upstream "frontend" in /etc/nginx/nginx.conf:48
  http://localhost/ -> 000
  $ sudo docker start frontend nginx; …
  http://localhost/ -> 200
  ```
  nginx resolves every `proxy_pass` host when it starts; with `frontend` gone it refuses to start, and the API's path goes down with it. Start the frontend first, then nginx.
- The README's container checks (lines 373–382) work on this VM too, with the same container names except `cheese-app-vector-db`. *Captured* (`vm/56`, `vm/57`):
  ```
  $ sudo docker exec -it api-service /bin/bash
  app@a18ad0b0f412:/app$ ls
  Dockerfile  api                   docker-hub.sh    news-letters  pyproject.toml
  _test.py    docker-entrypoint.sh  docker-shell.sh  podcasts      uv.lock
  app@a18ad0b0f412:/app$ exit
  $ sudo docker exec -it nginx /bin/bash
  root@225928af4aee:/# nginx -v
  nginx version: nginx/1.30.6
  ```

**A10. Tear down (missing from README).** Delete the VM in the console, with its boot disk, before Part B. Leaving it running costs about $2/day. Images on the stand-in took 6.1 GB (`vm/60`: chroma 640 MB, api-service 5.07 GB, frontend 232 MB, nginx 163 MB).

### Part B: Pulumi deployment (README lines 225–390)

**B1. Enable the APIs (README lines 229–234).** Also check that Vertex AI API is enabled (see §2).

**B2. Create the two service accounts and keys (README lines 236–259).** Save them as `deployment.json` and `gcp-service.json` in the `secrets/` folder **next to** the repo folder (not inside it).
- Checkpoint: `ls ../../../secrets` from `src/deployment` shows both files. The capture's layout (`laptop/p05`): one folder holding `cheese-app-v3/` and `secrets/` side by side, `secrets/` with `deployment.json` and `gcp-service.json`.

**B2½. Create the Artifact Registry repository (not in the README).** Use the `gcloud artifacts repositories create … --location=us` command in §2, inside the toolbox after B4.

**B3. Start the toolbox (README lines 265–268).**
- Action: edit `export GCP_PROJECT="ac215-project" # Change to your GCP Project` (`src/deployment/docker-shell.sh:13`), then `cd src/deployment` and `sh docker-shell.sh`.
- **As committed it does not build today.** *Captured* (`laptop/b02`):
  ```
  $ sh docker-shell.sh
  Container 'cheese-app-deployment' is not running. Building and starting new container...
  …
   => ERROR [ 2/16] RUN apt-get update &&     apt-get install -y curl apt-transport-https ca-ce  4.0s
  …
  4.000 E: Failed to fetch https://deb.debian.org/debian-security/pool/updates/main/c/curl/curl_7.74.0-1.3%2bdeb11u16_amd64.deb  404  Not Found [IP: …]
  …(22 such lines)…
  ERROR: failed to build: failed to solve: process "/bin/sh -c apt-get update &&     apt-get install -y curl apt-transport-https ca-certificates gnupg lsb-release openssh-client" did not complete successfully: exit code: 100
  Unable to find image 'cheese-app-deployment:latest' locally
  docker: Error response from daemon: pull access denied for cheese-app-deployment, repository does not exist or may require 'docker login': denied: requested access to the resource is denied
  ```
  (The capture's URLs read `https://` only because of the recording machine's proxy, whose address is cut here; yours read `http://` and end in your mirror's address. The 404s are the same.) `Dockerfile:4` is `FROM python:3.13-slim-bullseye`, Debian 11, whose security updates have moved to `archive.debian.org`. `set -e` is commented out (`docker-shell.sh:4`), so after the failed build the script still runs `docker run`, and Docker looks for `cheese-app-deployment` on Docker Hub: read the **first** error, not the last.
- **Fix 1** (`laptop/b02a`): `FROM python:3.13-slim-bookworm` on line 4. Running `sh docker-shell.sh` again, steps 2–7 pass and step 8 fails. *Captured* (`laptop/b02b`):
  ```
   => ERROR [ 8/16] RUN apt-get update &&     apt-get install -y google-cloud-sdk google-cloud-  3.4s
  …
  3.380 Package google-cloud-sdk is not available, but is referred to by another package.
  …
  3.380 However the following packages replace it:
  3.380   google-cloud-cli
  …
  3.383 E: Package 'google-cloud-sdk' has no installation candidate
  3.383 E: Package 'google-cloud-sdk-gke-gcloud-auth-plugin' has no installation candidate
  ```
- **Fix 2**: install the packages apt names. Both edits together (`laptop/b02c`):
  ```diff
  -FROM python:3.13-slim-bullseye
  +FROM python:3.13-slim-bookworm
  …
   RUN apt-get update && \
  -    apt-get install -y google-cloud-sdk google-cloud-sdk-gke-gcloud-auth-plugin jq docker-ce
  +    apt-get install -y google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin jq docker-ce
  ```
- Under the hood, once it builds:
  - Builds `cheese-app-deployment` for `linux/amd64` (`docker-shell.sh:31`; 2.61 GB, `laptop/b36`). On Apple Silicon it runs under emulation; expect a platform warning and `Architecture: x86_64` (`docker-entrypoint.sh:4`).
  - Mounts the socket, code, secrets and Docker config (`:34-50`).
  - The entrypoint activates the deployment SA (`docker-entrypoint.sh:10`), sets the project (`:11`), registers the Artifact Registry credential helper (`:13`), creates the state bucket if needed (`:15-20`), runs `pulumi login gs://…` (`:23`), lists the stacks (`:27`) and opens `/bin/bash` (`:30`).
- *Captured* with both fixes and a well-formed key that belongs to **no** account (`laptop/b02d`), every entrypoint step and its honest error:
  ```
  [+] Building 91.9s (21/21) FINISHED                                                  docker:default
  …
  Container is running!!!
  Architecture: x86_64
  Environment ready! Virtual environment activated.
  Python version: Python 3.13.18
  UV version: uv 0.13.7 (x86_64-unknown-linux-gnu)
  ERROR: (gcloud.auth.activate-service-account) There was a problem refreshing auth tokens for account deployment@your-gcp-project.iam.gserviceaccount.com: ('invalid_grant: Invalid grant: account not found', …
  …
  Updated property [core/project].
  …
  Adding credentials for: us-docker.pkg.dev
  gcloud credential helpers already registered correctly.
  Bucket does not exist. Creating...
  …
  Creating gs://your-gcp-project-pulumi-state-bucket/...
  You are attempting to access protected data with no configured
  credentials. …
  Logging into Pulumi using GCS bucket: gs://your-gcp-project-pulumi-state-bucket
  error: could not log in to the state backend "gs://your-gcp-project-pulumi-state-bucket": … oauth2: cannot fetch token: …
  Response: {"error":"invalid_grant","error_description":"Invalid grant: account not found"}
  Available Pulumi stacks in GCS:
  …
  BucketNotFoundException: 404 gs://your-gcp-project-pulumi-state-bucket bucket does not exist.
  No stacks found.
  root@3e978a898fa8:/app#
  ```
- Checkpoint with a real key (*expected*, from the script's own messages): no `ERROR` after the version lines, `Bucket does not exist. Creating...` the first time (`Bucket already exists. Skipping creation.` later), `Logging into Pulumi using GCS bucket: gs://<proj>-pulumi-state-bucket` with no error after it, and the prompt `root@<id>:/app#`. A second terminal running `sh docker-shell.sh` attaches to the same container (`docker-shell.sh:23-25`) and re-runs the entrypoint inside it. The container is started with `--rm` (`:34`), so it disappears when the first shell exits; the state stays in the bucket.
- *Captured* environment inside the toolbox (`laptop/b07`, *extra*): `GCP_PROJECT`, `GCP_REGION=us-central1`, `GCP_ZONE=us-central1-a`, `GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json`, `PULUMI_BUCKET=gs://<proj>-pulumi-state-bucket`, `PULUMI_CONFIG_PASSPHRASE=` (empty), `USE_GKE_GCLOUD_AUTH_PLUGIN=True`; `/secrets` holds the two keys plus an empty `.ssh` folder that the mount at `docker-shell.sh:38` created; `docker ps` inside lists the laptop's containers, because the toolbox drives the laptop's Docker through the socket.
- If it fails:
  - The first `ERROR` line is `invalid_grant` or `Unable to read file [/secrets/deployment.json]` → the key is wrong, revoked, misnamed, or the `secrets/` folder is in the wrong place.
  - `AccessDeniedException: 403` on `gsutil mb` → the SA lacks Storage Admin.
  - Bucket name taken → bucket names are global, so change `PULUMI_BUCKET` (`docker-shell.sh:17`).

**B4. Check the tools (README lines 270–278).** *Captured* (`laptop/b03`–`b06`):
```
$ gcloud --version
Google Cloud SDK 592.0.0
…
gke-gcloud-auth-plugin 0.5.21
gsutil 5.38
kubectl 1.35.9
…
$ pulumi version
v3.274.0
$ kubectl version --client
Client Version: v1.35.9-dispatcher
Kustomize Version: v5.7.1
$ gcloud auth list

No credentialed accounts.
…
```
Checkpoint: with your key, `gcloud auth list` shows `deployment@<your-project>.iam.gserviceaccount.com` marked active. `kubectl` here is gcloud's bundled 1.35, which comes first on `PATH`, not the 1.34 the Dockerfile installs from the Kubernetes repository (`Dockerfile:33-41`); it does not matter for L20.

**B5. Turn on OS Login for the project (README lines 286, 290).**
- Command: `gcloud compute project-info add-metadata --project <YOUR GCP_PROJECT> --metadata enable-oslogin=TRUE`, with your project ID **in place of the whole `<YOUR GCP_PROJECT>`**. *Captured* as printed (`laptop/b08`): `bash: line 1: YOUR: No such file or directory`, the same redirection trap as A1. The README's example (line 290) fills in `ac215-project`; *captured* without an account (`laptop/b09`): `ERROR: (gcloud.compute.project-info.add-metadata) You do not currently have an active account selected.`
- Checkpoint with your account (*expected*): gcloud reports the project metadata updated.

**B6. Create the SSH key (README lines 295–297).**
```
cd /secrets
ssh-keygen -f ssh-key-deployment
cd /app
```
- **Press Enter twice at the passphrase prompt (empty passphrase).** Pulumi's SSH connection (`create_instance.py:157-161`) and the Docker provider (`setup_containers.py:83-90`) cannot type a passphrase. *Captured* (`laptop/b10`, `b11`):
  ```
  Generating public/private rsa key pair.
  Enter passphrase (empty for no passphrase):
  Enter same passphrase again:
  Your identification has been saved in ssh-key-deployment
  Your public key has been saved in ssh-key-deployment.pub
  The key fingerprint is:
  SHA256:… root@<container id>
  …
  $ ls -la /secrets
  …
  -rw------- 1 root app  2602 Nov  5 23:14 ssh-key-deployment
  -rw-r--r-- 1 root app   571 Nov  5 23:14 ssh-key-deployment.pub
  ```
  Because `/secrets` is your laptop's `secrets/` folder, the key pair survives the `--rm` container. Never commit it.

**B7. Register the public key with OS Login (README line 302).**
- Command: `gcloud compute os-login ssh-keys add --key-file=/secrets/ssh-key-deployment.pub`. *Captured* without an account (`laptop/b12`): the same `You do not currently have an active account selected.`
- Checkpoint (*expected*, the README's own snippet, README lines 306–314, with the account number and uid/gid replaced by zeros):
  ```
  - accountId: ac215-project
      gid: '0000000000'
      homeDirectory: /home/sa_000000000000000000000
      name: users/deployment@ac215-project.iam.gserviceaccount.com/projects/ac215-project
      operatingSystemType: LINUX
      primary: true
      uid: '0000000000'
  	...
      username: sa_000000000000000000000
  ```
  **Copy your own `username`.** You need it in B10 (`security:ssh_user`).

**B8. "Deployment Setup" (README lines 318–322): skip it.** It tells you to edit `inventory.yml`, a file from the old Ansible version that does not exist on `main`. *Captured* (`laptop/b13`): `ls: cannot access 'inventory.yml': No such file or directory`, and no such file anywhere in the toolbox.

**B9. Build and push the images with Pulumi (README lines 327–345).**
- Commands, from `/app/deploy_images`:
```
pulumi stack init dev
pulumi config set gcp:project ac215-project
```
  Replace `ac215-project` with your project ID. Then (README lines 339 and 344): `pulumi preview --stack dev --refresh` and `pulumi up --stack dev --refresh -y`.
- *Captured* after the failed login of B3 (`laptop/b14`, `b15`):
  ```
  $ pulumi stack init dev
  Connect to Pulumi Cloud for state storage, config management, team collaboration, and more.

  Run `pulumi login --help` for alternative login options.

  Press <ENTER> to log in with your browser, or
  $ pulumi config set gcp:project ac215-project
  error: PULUMI_ACCESS_TOKEN must be set for login during non-interactive CLI sessions
  ```
  Pulumi was never logged in to the bucket, so it offers its own cloud service. Every later Pulumi command of the README failed the same way (`laptop/b16`–`b22`, exit 3). Do not log in to Pulumi Cloud: go back to B3, fix the key, and leave and re-enter the toolbox (§6 gotcha 27).
- *Captured* on the local file backend instead (*extra*, `laptop/b31`–`b34`): `Created stack 'dev'`; `pulumi config` lists `gcp:project  ac215-project`; and the preview, limited with `--target` to the frontend image (one image of three, to save disk):
  ```
  Previewing update (dev):
  Downloading plugin kubernetes-4.23.0: starting
  Downloading plugin docker-4.9.0: starting
  Downloading plugin command-1.1.3: starting
  Downloading plugin gcp-9.3.0: starting
  Downloading plugin docker-build-0.0.15: starting
  …
   +  pulumi:pulumi:Stack deploy-images-dev create
   +  docker-build:index:Image build-cheese-app-frontend-react create
  …
      warning: Skipping preview build because some inputs are unknown.

  Outputs:
      cheese-app-api-service-ref    : [unknown]
      cheese-app-api-service-tags   : [unknown]
      cheese-app-frontend-react-ref : [unknown]
      cheese-app-frontend-react-tags: [
          [0]: "us-docker.pkg.dev/ac215-project/cheese-app-repository/cheese-app-frontend-react:20261105233500"
      ]
  …
  Resources:
      + 2 to create
  ```
  The tag is the time the program ran (`deploy_images/__main__.py:13`); a second run a few seconds later already planned `…:20261105233502` (`laptop/b35`).
- Under the hood: three `docker_build.Image` resources (`deploy_images/__main__.py:23-71`) build `../../api-service`, `../../frontend-react` and `../../vector-db` (= `/api-service`, … inside the container) for amd64 on your laptop's Docker daemon, tag them `us-docker.pkg.dev/<proj>/cheese-app-repository/<name>:<YYYYmmddHHMMSS>`, and push. pulumi-docker-build starts its own BuildKit builder container for this.
- *Captured* `pulumi up` for the frontend image on the local backend (`laptop/b35b`, *extra*): the real build ran inside `pulumi up`, then the push needed Google:
  ```
   +  docker-build:index:Image build-cheese-app-frontend-react creating (77s) #13 DONE 71.1s
  …
   +  docker-build:index:Image build-cheese-app-frontend-react creating (144s) #17 DONE 54.2s
  …
   +  docker-build:index:Image build-cheese-app-frontend-react creating (148s) #21 ERROR: failed to push us-docker.pkg.dev/ac215-project/cheese-app-repository/cheese-app-frontend-react:20261105233941: failed to authorize: failed to fetch anonymous token: …
  …
      error: failed to solve: failed to fetch anonymous token: unexpected status from GET request to https://us-docker.pkg.dev/v2/token?scope=…: 403 Forbidden
  …
  Resources:
      3 unchanged
      2 errored

  Duration: 2m31s
  ```
  `#13` is `npm ci`, `#17` the Next.js build. The credential helper had no account, so the push went out anonymously and was refused.
- Checkpoint with your key (*expected*): three `docker-build:index:Image` resources created (the summary also counts the stack itself, so about `+ 4 created`), plus `Outputs:` with `cheese-app-api-service-ref`, `cheese-app-api-service-tags`, …. The repository shows three images in the console. The api-service build is the slowest because of TensorFlow.
- If it fails:
  - `failed to fetch anonymous token … 403 Forbidden` → no credentials reached Docker: check `gcloud auth list` and that the entrypoint printed `Adding credentials for: us-docker.pkg.dev`.
  - `name unknown: Repository "cheese-app-repository" not found` → do B2½ (not reproduced here; the digest's reading of the code).
  - `denied: Permission "artifactregistry.repositories.uploadArtifacts" denied` → check the SA roles and that you are on the right project.
  - Timeout after 30 min → `CustomTimeouts(create="30m")` (`:30`); re-run, and the BuildKit cache makes the retry faster.
  - `stack 'dev' already exists` → run `pulumi stack select dev`.

**B10. Create the VM and deploy (README lines 347–367).**
- Commands: `cd ../deploy_single_vm`, then
```
pulumi stack init dev
pulumi config set gcp:project ac215-project
pulumi config set security:ssh_user sa_000000000000000000000
pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com
```
  Replace the project ID **and** the `sa_…` username with yours (the README prints its own account's number). Then `pulumi preview --stack dev --refresh` and `pulumi up --stack dev --refresh -y`.
- *Captured* on the local backend (`laptop/b42`, `b43`, *extra*): `pulumi config` lists the four keys (`gcp:project`, `pulumi:tags`, `security:gcp_service_account_email`, `security:ssh_user`) with whatever you typed, so check them here. The preview:
  ```
  $ pulumi preview --stack dev --refresh
  Previewing update (dev):
  …
   +  pulumi:pulumi:Stack deploy-single-vm-dev create
   +  gcp:compute:Disk cheese-app-demo-disk create
   +  gcp:compute:Network cheese-app-network create
   +  gcp:compute:Firewall allow-http create
   +  gcp:compute:Firewall allow-https create
   +  gcp:compute:Firewall allow-ssh create
  …
      error: Program failed with an unhandled exception:
      Traceback (most recent call last):
        File "/app/deploy_single_vm/__main__.py", line 15, in <module>
          instance, instance_ip, connection, persistent_disk, network = create_instance()
        File "/app/deploy_single_vm/create_instance.py", line 100, in create_instance
          ubuntu_image = gcp.compute.get_image(
  …
      * error retrieving image information: Get "https://compute.googleapis.com/compute/beta/projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts?alt=json&prettyPrint=false": oauth2: cannot fetch token: 400 Bad Request
      Response: {"error":"invalid_grant","error_description":"Invalid grant: account not found"}

  Resources:
      + 6 to create
      1 errored
  ```
  Declaring resources costs nothing, so the network, the firewalls and the disk are planned first; the first call that needs Google is the lookup of the newest Ubuntu 22.04 image. `pulumi up --stack dev --refresh -y` stopped at the same place and created nothing (`laptop/b44`).
- Under the hood, in dependency order (`deploy_single_vm/__main__.py:14-26`):
  1. `create_instance()`: VPC `cheese-app-network` with auto subnets (`create_instance.py:45-48`), firewalls for 80, 443 and 22 (`:51-89`), a `pd-standard` 50 GB disk (`:92-97`), the latest `ubuntu-2204-lts` image (`:100-103`), and the VM (`:106-149`) with that disk attached, an ephemeral STANDARD-tier IP, network tags `http-server`/`https-server`, and the deployment SA. Pulumi appends a random suffix to the physical names (no `name=` is given).
  2. `provision_instance()`: format the disk only if it has no filesystem (`provision_instance.py:24-32`), add an fstab entry and mount it at `/mnt/disk-1` (`:34-57`), stop the apt timers (`:60-70`), `apt-get upgrade` (`:73-81`), install base packages (`:83-98`), install Docker CE from Docker's repo (`:101-121`), `pip3 install requests docker` (`:124-131`), add the user to the docker group, `chmod 666 /var/run/docker.sock` (`:134-156`).
  3. `setup_containers()`: read image tags from the other stack (`setup_containers.py:27-31`), upload `gcp-service.json` to `/srv/secrets` (`:34-63`), create `/mnt/disk-1/{persistent,chromadb}` (`:66-76`), create the Docker-over-SSH provider (`:79-98`), the `appnetwork` bridge (`:101-106`) and the containers `frontend` (`:110-129`), `vector-db` (`:132-167`), `vector-db-loader` (`:170-205`, one-shot `rm=True`) and `api-service` (`:208-247`).
  4. `setup_webserver()`: `/conf/nginx` (`setup_webserver.py:31-39`), upload `nginx.conf` with checksum triggers (`:42-68`), the `nginx` container on 80/443 (`:71-102`), then `docker container restart nginx` (`:105-113`).
- Checkpoint with your key (*expected*; nothing in the repo records this run): about 30 resources created, followed by `Outputs:` with `instance_ip`, `instance_name`, `persistent_disk_name`, `ssh_command`, `ssh_user` and `zone` (`deploy_single_vm/__main__.py:29-34`). Expect the whole run to take several minutes; `update-system` and the image pulls are the slow parts.
- If it fails:
  - `Missing required configuration variable 'security:ssh_user'` → B10 config not set.
  - `unknown stack "organization/deploy-images/dev"` → do B9 first, in the same state bucket.
  - SSH `handshake failed` / `Permission denied (publickey)` → wrong `sa_` user, key not added (B7), OS Login not enabled (B5), or the key has a passphrase (`ssh: this private key is passphrase protected`).
  - `Quota 'N2D_CPUS' exceeded` or `ZONE_RESOURCE_POOL_EXHAUSTED` → change `machine_type` (`create_instance.py:38`) or `GCP_ZONE` (`docker-shell.sh:15`).
  - `Could not get lock /var/lib/dpkg/lock-frontend` → unattended upgrades raced you; run `pulumi up` again.

**B11. Verify (README lines 369–383).** *(no Pulumi VM in the captures; the same commands ran on the Part A stand-in, A9)*
- Open `http://<instance_ip>/`. In the footer you should see "Frontend version: 1" and "API version: 3.0", which the frontend fetches from `/status` (`Footer.jsx`, `DataService.js` `GetStatus`). These images are built from your checkout, so `/status` exists here, unlike A7.
- `curl http://<instance_ip>/api-service/status` returns `{"version":"3.0"}`.
- SSH in from the GCP console, or from the toolbox with `ssh -i /secrets/ssh-key-deployment sa_…@<instance_ip>` (not in the README; the exported `ssh_command` omits `-i`, see §6). Then run:
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
- The Pulumi VM names the vector DB `vector-db` (not `cheese-app-vector-db`) and runs a fifth, one-shot `vector-db-loader` that is gone after it finishes. Each `logs -f` follows until Ctrl-C. On the stand-in the api log ends with the requests that came through nginx (`vm/53`: `"GET /api-service/ HTTP/1.1" 200 OK`, `"GET /api-service/status HTTP/1.1" 404 Not Found` with the old image), and the nginx log shows the mangled `-[]` lines of A8 (`vm/55`); the Pulumi VM uses the repo's own `nginx.conf`, with a working `log_format`.
- `http://<ip>/api-service/docs` will **not** show a usable Swagger UI with v3 code (§9 erratum 4). Use `/api-service/status` instead. A chat request is only a valid test after you switch `GENERATIVE_MODEL` to a model Vertex AI still serves (§6 gotcha 22).

**B12. Redeploy after a code change (implied by the design).** Run `pulumi up` in `deploy_images` (new timestamp tags), then `pulumi up` in `deploy_single_vm`. The preview shows `+-` replace for `frontend`, `vector-db-loader` and `api-service`. Editing `nginx.conf` alone re-runs only the upload, move and restart resources (checksum triggers). Read the preview before `-y`: if Canonical has published a newer Ubuntu 22.04 image since your last run, the VM itself may be planned for replacement (§6 gotcha 20).

**B13. Destroy (README line 389).**
- Command: `pulumi destroy --stack dev --refresh -y`
- Run it **inside `deploy_single_vm`**. It deletes the containers through SSH first, then the VM, disk, firewalls and VPC, in reverse dependency order.
- Running it in `deploy_images` removes the images from *state only* (`retain_on_delete=True`), so delete the registry images yourself.
- *Captured* on the local backend, with an empty stack (`laptop/b45`, *extra*):
  ```
  $ pulumi destroy --stack dev --refresh -y
  Previewing destroy (dev):

  Resources:

  Destroying (dev):

  Resources:

  Duration: 1s

  The resources in the stack have been deleted, but the history and configuration associated with the stack are still maintained.
  If you want to remove the stack completely, run `pulumi stack rm dev`.
  ```
  So a later `pulumi up` works without `stack init`. Run `pulumi stack rm dev` only if you want to delete a stack and its history completely; by default it also deletes that folder's `Pulumi.dev.yaml` from your checkout unless you pass `--preserve-config`. The stacks' full names are `organization/deploy-images/dev` and `organization/deploy-single-vm/dev` (`laptop/b46`), the name `setup_containers.py:27` refers to.
- Checkpoint with your key: `Resources: - N deleted`, and Compute Engine → VM instances is empty. Then the registry, the bucket and the laptop leftovers (*At a glance*, *Tear down*).

---


## 5. Code tour

```
src/deployment/
├── Dockerfile                    # deployment toolbox image: python 3.13 (bullseye: see §4 B3) + gcloud + docker-ce + kubectl 1.34 + helm + pulumi + uv
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
3. **`docker-hub.sh` leaves `multi-arch` as your current builder.**
   - Symptom: `docker buildx ls` marks `multi-arch*` (docker-container driver) as current after Part A (`laptop/a03`); a `docker buildx build` without `--load` or `--push` then ends with `WARNING: No output specified with docker-container driver. Build result will only remain in the build cache` (`laptop/a02`).
   - Cause: `docker buildx create … --use --name multi-arch` (`docker-hub.sh:27`).
   - Not reproduced: the older worry that a plain `docker build -t x .` would no longer produce a runnable local image. On Docker 29.8 / buildx 0.37 it still did (`laptop/a04`: `docker run hello-node` printed `v20.20.2`).
   - Fix: `docker buildx use default` (`laptop/a05`), the tidy reset; `docker buildx rm multi-arch` when you are done.
4. **Apple Silicon is slow or times out.**
   - Symptom: platform warning on `docker run`, `Architecture: x86_64`, the api-service build takes tens of minutes, and possibly a 30-minute timeout.
   - Cause: the toolbox is built `--platform=linux/amd64` (`docker-shell.sh:31`) and the images target `LINUX_AMD64` (`deploy_images/__main__.py:28`), which is emulated on ARM. The VM *is* amd64, so this is required.
   - Fix: be patient and re-run (cache), or give Docker Desktop more CPU/RAM.
5. **Wrong project / instructor values.**
   - Symptom: `403 … Permission denied on resource project ac215-project` or SSH failures for the README's `sa_…` user.
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
9. **`pulumi stack init dev` says it already exists.** You re-entered the container; state persists in the bucket. Use `pulumi stack select dev`. The committed `encryptionsalt` lines (`deploy_images/Pulumi.dev.yaml:1`, `deploy_single_vm/Pulumi.dev.yaml:1`, `deploy_single_vm/Pulumi.dev-test.yaml:1`) were made with the **empty** passphrase, which the toolbox sets (`Dockerfile:51`), so no `incorrect passphrase` error is expected (`laptop/b31`-`b33` worked with them). If you ever set a different passphrase, delete the `encryptionsalt` line and re-initialise; these config files hold no secrets.
10. **Every `pulumi up` rebuilds and redeploys.**
    - Symptom: the images preview always shows `~ update ×3`, and the VM stack then replaces three containers.
    - Cause: `timestamp_tag` is `datetime.now()` (`deploy_images/__main__.py:13`).
    - Fix: accept it, or tag with a git SHA or content hash for reproducibility (§8, exercise E6).
11. **nginx restarts in a loop at first boot.**
    - Symptom: `sudo docker container logs nginx` shows `nginx: [emerg] host not found in upstream "api-service" in /etc/nginx/nginx.conf:37` (or `"frontend"` … `:48`).
    - Cause: nginx resolves upstream names at start-up, and in the Docker-provider version nginx depends only on the provider (`setup_webserver.py:38`), not on the api-service/frontend containers (the older variant did, `setup_webserver_using_command.py:44`). `restart="always"` (`setup_webserver.py:75`) makes it recover once api-service exists.
    - Fix: wait, or add `deploy_api_service` and `deploy_frontend` to nginx's `depends_on`. The mechanism was reproduced on the Part A stand-in: with `frontend` stopped, `docker restart nginx` gave `Exited (1)` and `host not found in upstream "frontend" in /etc/nginx/nginx.conf:48`, and port 80 stopped answering (`vm/58`); the first-boot race on the Pulumi VM itself was not reproduced.
12. **The whole site is down after a VM reboot.**
    - Symptom: after `sudo reboot`, `http://<ip>/` *and* `http://<ip>/api-service/status` both fail, and `sudo docker container ls -a` shows `frontend` exited and `nginx` restarting.
    - Cause: the frontend container has no `restart` policy (`setup_containers.py:110-129`), unlike vector-db (`:136`), api-service (`:212`) and nginx (`setup_webserver.py:75`), and unlike the command variant (`setup_containers_using_command.py:101`). So the frontend stays stopped, its name no longer resolves on `appnetwork`, and nginx refuses to start (gotcha 11) and loops on `restart=always`. The API itself is up (`curl localhost:9000/status` on the VM works), but nothing on port 80 forwards to it. The nginx half is the captured `vm/58`; the reboot itself was not run.
    - Fix: `sudo docker start frontend` (nginx comes up on its next restart), and for good add `restart="always"` to the frontend and `pulumi up`.
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
16. **Swagger looks empty or broken (v3 code).**
    - Symptom: with images built from `3ecef56`, `localhost:9000/docs` shows "No operations defined in spec!"; `http://<ip>/api-service/docs` loads a page that can't fetch `/openapi.json`.
    - Cause: the outer app at `api/service.py:49` owns `/docs`. The public Part A image is older and shows a full Swagger page (`vm/35`).
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
    - Cause: every LLM helper hardcodes `GENERATIVE_MODEL = "gemini-2.0-flash-001"` (`src/api-service/api/utils/llm_utils.py:22`, `llm_rag_utils.py:23`, `llm_agent_utils.py:21`, `llm_cnn_utils.py:30`). Google's "Model versions and lifecycle" page (fetched 2026-11-05) lists `gemini-2.0-flash` under *Retired models*, retired 2026-06-01, recommended upgrade `gemini-3.5-flash-lite`. `text-embedding-004` is listed as retiring 2027-04-01, so query embeddings still work for now. The public Part A image has the same constant in the same four files (`vm/36`).
    - Fix: change `GENERATIVE_MODEL` to a model the page lists as available (its recommended upgrade is `gemini-3.5-flash-lite`). Do **not** pick `gemini-2.5-flash`: the same page gives it a retirement date of 2026-10-20, already past. Then `pulumi up` in `deploy_images` and in `deploy_single_vm`.
23. **ChromaDB data is not on the persistent disk.**
    - Symptom: after the `vector-db` container is replaced, the collection is empty until the loader runs again.
    - Cause: the code mounts the disk at `/chroma/chroma` and sets `IS_PERSISTENT=TRUE` (`setup_containers.py:145-156`; README lines 93–95 for Part A), and it runs the unpinned `chromadb/chroma:latest`. Chroma's own cookbook says current 1.x server images persist to **`/data`** and calls `IS_PERSISTENT` a legacy variable. Confirmed on 2026-11-05 with Chroma 1.0.0 (`vm/24`): the log says `persist_path: "/data"` (`vm/25`), `docker-volumes/chromadb` stays empty and `/data/chroma.sqlite3` (36 MB) sits inside the container (`vm/28`). The data therefore lives in the container's writable layer.
    - Fix: mount `/mnt/disk-1/chromadb` at `/data` (`setup_containers.py:150-155`; Part A: `-v ./docker-volumes/chromadb:/data`), or pin an older 0.x image tag. In this tutorial it matters little, because the loader drops and reloads the collection on every deployment.

24. **Part A's public images are older than the code you are reading.**
    - Symptom: on the manual VM, `curl localhost:9000/status` returns `HTTP/1.1 404 Not Found` `{"detail":"Not Found"}` (`vm/34`), and through nginx `/api-service/status` does too (`vm/49`), although `service.py:34-36` has the route; the footer shows no API version.
    - Cause: README lines 103, 127 and 150 run `dlops/cheese-app-…:latest`. The api-service image's `api/service.py` has no `ROOT_PATH`, `mount` or `/status` (0 matches) and still has `/square_root/` (`vm/36`).
    - Fix: check with `curl localhost:9000/` (`{"message":"Welcome to AC215"}`, `vm/33`), or build and push your own images (A2, after changing `DOCKER_USERNAME`) and use `<you>/cheese-app-…` in the `docker run` lines. Part B is unaffected: `deploy_images` builds from your checkout.
25. **The toolbox does not build as committed.**
    - Symptom: `sh docker-shell.sh` stops at `[ 2/16]` with 22 `E: Failed to fetch …/debian-security/… 404 Not Found` lines, then prints `Unable to find image 'cheese-app-deployment:latest' locally` and `pull access denied` (`laptop/b02`). After fixing that, step `[ 8/16]` fails with `E: Package 'google-cloud-sdk' has no installation candidate` (`laptop/b02b`).
    - Cause: `Dockerfile:4` is `FROM python:3.13-slim-bullseye` (Debian 11), whose security updates moved to `archive.debian.org`; and Google's apt repository no longer carries the transitional `google-cloud-sdk` / `google-cloud-sdk-gke-gcloud-auth-plugin` packages (`Dockerfile:29-30`; apt names `google-cloud-cli` as the replacement). `docker-shell.sh` runs `docker run` even after a failed build, because `set -e` is commented out (`:4`).
    - Fix: `FROM python:3.13-slim-bookworm` and `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin` (the diff in §4 B3). With both, the build finished in 91.9 s (`laptop/b02d`). Always read the first error of a long log.
26. **Angle-bracket placeholders typed literally.**
    - Symptom: `docker login -u <USER NAME> -p <ACCESS TOKEN>` → `syntax error near unexpected token 'newline'` (`laptop/a01`); `--project <YOUR GCP_PROJECT>` → `bash: line 1: YOUR: No such file or directory` (`laptop/b08`).
    - Cause: `<` and `>` are shell redirections.
    - Fix: replace the whole placeholder, brackets included.
27. **Pulumi asks you to log in to Pulumi Cloud.**
    - Symptom: `pulumi stack init dev` prints `Connect to Pulumi Cloud for state storage …` and `Press <ENTER> to log in with your browser, or` (`laptop/b14`); without a terminal every Pulumi command says `error: PULUMI_ACCESS_TOKEN must be set for login during non-interactive CLI sessions` (`laptop/b15`-`b22`).
    - Cause: the entrypoint's `pulumi login $PULUMI_BUCKET` (`docker-entrypoint.sh:23`) failed, usually because the key login before it failed (`laptop/b02d`: `invalid_grant: Invalid grant: account not found`, then `could not log in to the state backend`). Pulumi then falls back to its own cloud service.
    - Fix: do not press Enter and do not use `pulumi login --local` (your state belongs in the bucket, where the other stack and your next session find it). Check `gcloud auth list`, `secrets/deployment.json` and `GCP_PROJECT`, leave the toolbox and run `sh docker-shell.sh` again.
28. **`Conflict. The container name "/api-service" is already in use`.**
    - Symptom: the README's interactive `api-service` command (lines 133–144) fails with exit 125 (`vm/38`).
    - Cause: the detached container from lines 118–127 still runs under the same name.
    - Fix: `sudo docker rm -f api-service` first, and start the detached one again afterwards (`vm/39-41`).
29. **The registry push is refused with `anonymous token … 403 Forbidden`.**
    - Symptom: `pulumi up` in `deploy_images` builds the image, then `failed to authorize: failed to fetch anonymous token: … 403 Forbidden` (`laptop/b35b`).
    - Cause: Docker had no credentials for `us-docker.pkg.dev`: the gcloud credential helper (`docker_config.json`, `docker-entrypoint.sh:13`) had no active account.
    - Fix: get `gcloud auth list` to show the deployment account (gotcha 27). A *different* error, `name unknown: Repository "cheese-app-repository" not found`, means the push is authorised but the repository is missing (gotcha 1).

---

## 7. Where this sits in the course

- **Before:**
  - L1–L2: VMs and "run app on VM using Docker" by hand (simple-translate).
  - L3–L4: multi-container apps and Docker networks/ports (mega-pipeline, port_toy).
  - L10: GCP auth and service accounts (cheese-app-v0).
  - L14: serverless Cloud Run, where Google ran the box for you.
  - L18: **cheese-app-v2**, the FastAPI api-service, React frontend and ChromaDB, all *local* containers. v2 `main` was refactored on 2026-11-05 (L18's video follows it). v3 is still built on the **2025** v2 (now branch `2025`, `14f2a14`): the app deployed here is that 2025 app plus the v3 changes below, not the one L18 now builds.
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

**v2 → v3 diff** (v2 at `14f2a14`, now branch `2025`; `git diff --no-index --stat` of the two `src/` trees: 46 files changed, 3716 insertions(+), 108 deletions(−), re-checked 2026-11-05):
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

**An unmerged staff work branch** (context only). On 2026-11-05 a staff branch of `cheese-app-v3` moved to `d1e860d` ("Refactor for kind"): it rewrites the README (447 insertions, 528 deletions against `3ecef56`) and replaces `deploy_single_vm/` with `deploy_vm/` plus `k8s/`. The course site still links `main`. If that work is merged, Part B of this guide no longer matches the README: compare `git ls-remote https://github.com/dlops-io/cheese-app-v3` with the hash at the top.

Use `main` for L20.

---


## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l20-deployment-pulumi/exercises.md) in the video folder. Their outputs are the 2026-11-05 captures and extra checks run for them (`assets/exercise-checks/`: nginx and FastAPI stand-ins, two small Pulumi projects on the local file backend, an ext4 image file, a test SSH server). Nothing there used a Google account; whatever only the cloud can show is worked out from the code and labelled so. Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. Trace `http://<instance_ip>/api-service/status`: which gate, which container, which location block, and which character makes the API see `/status`?**
<details><summary>Answer</summary>

The **gate** is the firewall rule `allow-http` (`create_instance.py:51-62`): port 80 from `0.0.0.0/0` to VMs tagged `http-server`, which the VM carries (`:134`; on the Part A VM the *Allow HTTP traffic* tick added the same tag). Nothing opens 3000, 9000 or 8000. The **container** on host port 80 is `nginx` (`setup_webserver.py:71-102`). The **location block** is `location ^~ /api-service/ {` (`nginx.conf:35`): a prefix match that stops the regex search; everything else falls through to `location /` (`:47`) and the frontend. The **character** is the final `/` of `proxy_pass http://api-service:9000/;` (`:37`): a `proxy_pass` with a URI part replaces the matched prefix with that URI, so the API receives `/status`, resolved by Docker's DNS on `appnetwork`. The v3 API runs without `ROOT_PATH` on the Pulumi VM, so `/status` answers `{"version":"3.0"}` (`api/service.py:34-36`). On the Part A VM the same trip ends in a 404 because the public image predates `/status` (`vm/49`).
</details>

**Q2. What three things does `pulumi up` compare, what does `--refresh` change, and what does `-y` skip?**
<details><summary>Answer</summary>

**Desired state** (what the program declares now), **state** (what Pulumi recorded after its last run, in `gs://<project>-pulumi-state-bucket`, `docker-shell.sh:17`, `docker-entrypoint.sh:23`) and **reality** (what exists in the cloud and on the VM). The plan is desired vs state. **`--refresh`** first reads every resource through its provider and updates the state, then diffs: in the stand-in, after `docker rm -f`, `pulumi preview` said `3 unchanged` and `pulumi preview --refresh` said `+ 1 to create`. Refresh only helps for resources a provider can read; a `remote.Command` is not re-checked. **`-y`** answers yes to "Do you want to perform this update?": the plan is still printed, but nobody reads it before it is applied. Without it, in a non-interactive shell: `error: --yes or --skip-preview or --preview-only must be passed in to proceed when running in non-interactive mode`.
</details>

**Q3. Name the two service accounts, where each key sits (laptop, VM), and what each may do.**
<details><summary>Answer</summary>

| | `deployment` → `deployment.json` | `gcp-service` → `gcp-service.json` |
| --- | --- | --- |
| roles (README) | Compute Admin, Compute OS Login, Artifact Registry Administrator, Kubernetes Engine Admin, Service Account User, Storage Admin (README:241-246) | Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader (README:253-255) |
| where | laptop: `secrets/`, mounted into the toolbox as `/secrets` (`docker-shell.sh:9, 16, 37`) | laptop `secrets/`; uploaded by Pulumi to `/srv/secrets/gcp-service.json` on the VM (`setup_containers.py:44-63`) and mounted into the loader and `api-service` (`:180-188`, `:220-236`) |
| used for | gcloud login, state bucket, Pulumi's Google provider, image push, SSH through OS Login | the app's Vertex AI calls (Gemini, embeddings) |
| may | create and delete VMs, disks, networks, buckets, registries; log in to VMs | read objects and images, call Vertex AI |

Two footnotes from the code: the VM's *attached* identity is `security:gcp_service_account_email`, which the README sets to `deployment@…` (README:355, `create_instance.py:135-145`), limited by its scopes; and Pulumi's Docker provider pulls images with the toolbox's credentials (`setup_containers.py:92-96`). The SSH key is not a service-account key: its private half stays in `secrets/` (`-rw-------`, `laptop/b11`), its public half goes into the deployment account's OS Login profile.
</details>

**Q4. Which of slide 19's six steps can Pulumi inspect afterwards, and which does it only remember running? Why must those scripts be safe to run twice?**
<details><summary>Answer</summary>

Step 1 (setup, `docker-shell.sh`) is not Pulumi at all. Step 2 (images) and step 3 (VM: network, firewalls, disk, instance) are real resources that `--refresh` reads back. Step 4 (provisioning) is nine `remote.Command`s: Pulumi stores the script and its output, not what it changed. Steps 5 and 6 mix both: the Docker network and the containers are inspectable, the commands that copy secrets, make folders, upload `nginx.conf` and restart nginx are only remembered. Pulumi may run such a script again whenever it re-creates that resource (a changed script or trigger, a run that stopped halfway), so each is written to be idempotent: `blkid … || mkfs.ext4 …` formats only an empty disk (`provision_instance.py:29`), `grep -q … || … tee -a /etc/fstab` adds the mount once (`:50-52`), `mkdir -p`, `groupadd docker || true`. Checked on an image file: the guarded line run twice keeps the data; plain `mkfs.ext4` without a terminal reformats without asking.
</details>

**Q5. What survives `pulumi destroy` in `deploy_single_vm`, and how do you clean it up?**
<details><summary>Answer</summary>

`destroy` deletes the containers over SSH, the VM, the data disk, the three firewalls and the network; the commands are dropped from state without running anything. What survives: the registry images (another stack, and `retain_on_delete=True`, `deploy_images/__main__.py:31, 51, 70`) and the repository you created (`gcloud artifacts repositories delete cheese-app-repository --location=us`); both stacks' history and config (`laptop/b45`; `pulumi stack rm dev` if you are done for good); the state bucket (`gcloud storage rm -r gs://<project>-pulumi-state-bucket`, last); the Part A VM and its boot disk (console); your Docker Hub images (free); the service accounts, keys and OS Login key (delete the keys when the course ends); and on the laptop the 2.61 GB toolbox image, the `multi-arch` builder and `src/deployment/pulumi-plugins/`. The gcloud lines were not run in the captures; check **VM instances**, **Disks** and **Artifact Registry** in the console afterwards.
</details>

### Hands-on (predict, then run)

- **B1 · Follow the slash.** On the Part A VM, which container answers `/`, `/api-service/`, `/api-service/status`, `/api-servicex/status` and `/api-service`, and which path does it receive? Then delete the last `/` of `proxy_pass http://api-service:9000/;`. *(Answer: `/api-servicex/…` goes to the frontend; `/api-service` gets a `301` from nginx itself; without the slash the API receives `/api-service/status` and answers 404: the job `ROOT_PATH` does in L22.)*
- **B2 · Save the access log.** Write `nginx.conf` with a quoted heredoc instead of `echo '…'` and compare. *(Echo: 58 lines, `log_format  main   - []`, access lines `-[]`; heredoc: 57 lines, full log lines; both pass `nginx -t`.)*
- **B3 · Stop, don't restart.** Stop only the frontend, then restart nginx. *(Before the restart `/` fails but the API path still works; after it nginx is `Exited (1)` with `host not found in upstream "frontend"`, and nothing answers on port 80, `vm/58`.)*
- **B4 · Format twice.** Run `blkid -o value -s TYPE disk.img || mkfs.ext4 -q disk.img` twice on a 64 MB image file with a file written in between. *(The second run prints `ext4` and keeps the file; plain `mkfs.ext4` erases it.)*
- **B5 · Run it again.** Predict `pulumi preview` in `deploy_images` with no code change, `pulumi up` without `-y` in a script, and a second `pulumi stack init dev`. *(Three images change because of the timestamp tag; `--yes or --skip-preview or --preview-only must be passed`; `stack … already exists`, use `stack select`.)*
- **B6 · Images first, then the VM.** Which resources does `deploy_single_vm` change after new images? *(`frontend`, `vector-db-loader` and `api-service` are replaced; VM, disk, firewalls, `vector-db`, `nginx` and the provisioning commands are untouched.)*
- **B7 · Drift.** Someone runs `sudo docker rm -f nginx`, or deletes `/conf/nginx/nginx.conf`. *(Without `--refresh` no change; with it `+ create` for the nginx container. The deleted file is invisible to Pulumi; change the file or `--replace` the upload.)*
- **B8 · Your values, not the README's.** Run the README's four config lines as printed and `pulumi config`. *(The README's project and OS Login user, `laptop/b42`; set yours, and `git status` on the laptop shows both `Pulumi.dev.yaml` files modified.)*

### Debugging

- **C1 · Two angle-bracket errors** (`laptop/a01`, `b08`): the same cause, shell redirections; replace placeholders with their brackets.
- **C2 · `sh docker-shell.sh` fails, then runs anyway** (`laptop/b02`): Debian 11's security repository has moved; `set -e` is commented out, so the last error (`pull access denied`) hides the first. Fix 1: `bookworm`.
- **C3 · After fix 1** (`laptop/b02b`): `google-cloud-sdk` has no installation candidate; fix 2: `google-cloud-cli`.
- **C4 · Pulumi wants a browser** (`laptop/b14`, `b15`): the entrypoint's `pulumi login gs://…` failed; scroll up to the first red line (`invalid_grant`), check `gcloud auth list`, the key's name and folder, and `GCP_PROJECT`. Do not use Pulumi Cloud or `pulumi login --local`.
- **C5 · "The container name is already in use"** (`vm/38`): the interactive `api-service` is an alternative to the detached one; `docker rm -f` first.
- **C6 · nginx won't stay up**: `host not found in upstream "api-service" in /etc/nginx/nginx.conf:37` means the API container is not running on that network; find out why, start it, then nginx.
- **C7 · The exported SSH command doesn't work**: `ssh_command` omits `-i /secrets/ssh-key-deployment` (`deploy_single_vm/__main__.py:34`).
- **C8 · `unknown stack "organization/deploy-images/dev"`**: run `deploy_images` first, in the same backend, without renaming its project or stack.
- **C9 · A safer key?** A passphrase makes the first remote command fail with `ssh: this private key is passphrase protected`; protect the key by its place and mode instead.
- **C10 · `/status` says 404 on the Part A VM** (`vm/34`, `vm/36`): the public image is older than the code; use `/`, or build and push your own images.
- **C11 · The push is refused** (`laptop/b35b`): `anonymous token … 403` means no credentials reached Docker; `Repository … not found` means nobody created `cheese-app-repository`.
- **C12 · The vector data isn't on the disk** (`vm/28`): Chroma 1.x writes `/data`; mount `docker-volumes/chromadb` (Pulumi: `/mnt/disk-1/chromadb`, `setup_containers.py:150-155`) there instead of `/chroma/chroma`.

### Think

- **D1 · One public door.** Why is publishing 8000 and 9000 on the VM harmless, and what would a firewall rule for them expose? *(The unauthenticated vector DB and a second, nginx-free door to every API route, paid Vertex AI chats included. Debug through SSH or an SSH tunnel.)*
- **D2 · A tag that only changes with the code.** How would a re-run with no code change become a no-op, and what is lost? *(A commit SHA or content hash passed in as stack config; a base-image rebuild no longer redeploys unless the tag changes.)*
- **D3 · Reboot.** After `sudo reboot` on the Pulumi VM, which URLs work, and which one-line change makes it "all of them"? *(None through port 80: the frontend has no restart policy, so nginx cannot start; add `restart="always"` to `deploy_frontend`.)*
- **D4 · Try the narrow key.** Run the VM as `gcp-service`: what changes, and does anything need `deployment`? *(One config value; a running VM needs `allow_stopping_for_update=True`; nothing in the code needs the VM to be `deployment`, not tested end to end.)*
- **D5 · When is `-y` dangerous?** *(A newer Ubuntu image can turn a routine `up` into a VM replacement, new IP included; preview first, or pin the image.)*
- **D6 · One VM.** Three ways this deployment goes down that Cloud Run or Kubernetes would survive, and one thing it does better. *(Host failure or reboot, a container nginx waits for, a traffic spike, an outage on every deploy; simplicity and a predictable bill.)*

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
   - Effect: on the Pulumi VM, `http://<ip>/api-service/docs` serves the outer docs page, whose `/openapi.json` request then goes to the frontend. Use `/status` instead. (The public Part A image is older and does show its routes at `/docs`, `vm/35`; there `/status` is the check that fails, erratum 25.)
5. **The manual `nginx.conf` echo mangles `log_format`.**
   - Evidence: README lines 156–213 wrap the config in single quotes, but lines 165–167 contain single quotes too. Reproduced 2026-11-05 by running README lines 156–213 as printed: the file has 58 lines and line 10 reads `log_format  main   - []  ` followed by two whitespace-only lines and `;` (`vm/45`); every access-log line is `-[]` (`vm/51`).
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
18. **Committed config contains instructor values.** The `Pulumi.dev.yaml` files (`deploy_single_vm/Pulumi.dev.yaml:3-5`) and README commands (lines 333, 353–355, 290) use `ac215-project` and the README author's own OS Login user (a 21-digit `sa_` number, written `sa_000000000000000000000` in this guide). README line 267 mentions only `docker-shell.sh`.
19. **K8s-section leftovers in the same README** (relevant to L22): README line 529 mentions `docker-shell.bat`, which does not exist, and line 524 lists the retired Container Registry API.
20. **The generative model is retired.**
    - Evidence: `GENERATIVE_MODEL = "gemini-2.0-flash-001"` in `src/api-service/api/utils/llm_utils.py:22`, `llm_rag_utils.py:23`, `llm_agent_utils.py:21`, `llm_cnn_utils.py:30` (and `src/vector-db/cli.py:30`). Google's "Model versions and lifecycle" page (docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, fetched 2026-11-05) lists `gemini-2.0-flash` under *Retired models* with retirement date 2026-06-01 and recommended upgrade `gemini-3.5-flash-lite`. It lists `text-embedding-004` with retirement date 2027-04-01.
    - Effect: the deployment succeeds and `/status` works, but chat endpoints fail until the model name is updated (§6 gotcha 22).
21. **ChromaDB persistence path is out of date for `chromadb/chroma:latest`.**
    - Evidence: `setup_containers.py:134, 145-156` and README lines 93–97 use `IS_PERSISTENT=TRUE` plus a mount at `/chroma/chroma` on an unpinned `latest` image. Chroma's cookbook ("Running Chroma") says current server images persist to `/data` and that `IS_PERSISTENT` is a legacy variable for the v1.x Docker setup.
    - Confirmed 2026-11-05 with Chroma 1.0.0 on the Part A stand-in (`vm/24`, `vm/25`, `vm/28`).
   - Effect: the vector data is not on `/mnt/disk-1`. The impact is low because the loader reloads the collection on every deployment.
22. **README path shorthand.** README lines 266 and 349 say `cd into deployment`; the folder is `src/deployment`.

23. **The toolbox's base image is past its support.**
    - Evidence: `src/deployment/Dockerfile:4` `FROM python:3.13-slim-bullseye`. On 2026-11-05 `apt-get install` at `:11-12` fails with 22 `404 Not Found` errors from `debian-security` (`laptop/b02`): Debian 11's security updates moved to `archive.debian.org`.
    - Effect: `sh docker-shell.sh` (README line 268) fails as committed. Fix: `python:3.13-slim-bookworm`.
24. **The gcloud package names are gone.**
    - Evidence: `Dockerfile:29-30` installs `google-cloud-sdk google-cloud-sdk-gke-gcloud-auth-plugin`; apt answers `Package google-cloud-sdk is not available … However the following packages replace it: google-cloud-cli` and `has no installation candidate` (`laptop/b02b`).
    - Effect: the build fails at step 8 even on a supported base. Fix: `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin`.
25. **Part A runs public images that predate the code.**
    - Evidence: README lines 103, 127, 150 use `dlops/cheese-app-…` (`latest`); the api-service image has no `/status` and no `ROOT_PATH` mount (`vm/34`, `vm/36`), and its entrypoint differs from the repo's (`--root-path /api-service`, `vm/37`).
    - Effect: the v3 API check fails on the manual VM; the footer shows no API version.
26. **Placeholders in angle brackets inside commands.**
    - Evidence: README line 21 (`<USER NAME>`, `<ACCESS TOKEN>`) and line 286 (`<YOUR GCP_PROJECT>`) put placeholders inside code spans; typed as shown they are redirections (`laptop/a01`, `b08`).
27. **The interactive api-service command reuses the detached container's name.**
    - Evidence: README lines 118–127 and 133–144 both use `--name api-service`; run in order, the second fails with `Conflict` (`vm/38`). The README calls it an alternative ("If you want to run in interactive mode") but does not say to remove the first.

### Open questions (could not be determined from the sources)
- **Ed lesson content:** edstem.org was not accessible when the sources were checked. Any extra steps, slides or announcements there (e.g. creating the registry, a shared class project, pre-made keys) are unknown.
- **Pulumi passphrase (resolved):** all three committed `encryptionsalt` lines work with the empty passphrase (§6 gotcha 9).
- **Loader under `--refresh`:** how the Docker provider treats the `rm=True`, `restart="no"` loader container (`setup_containers.py:170-205`) on later `pulumi up --refresh` runs. Most likely Pulumi sees it as deleted and re-creates it, which re-loads the collection (harmless, because `load()` drops and re-creates it at `cli.py:286-292`). Whether a very fast exit can make the create step itself report "container exited" was not verified.
- **ChromaDB persistence path (resolved, see errata 21):** on 2026-11-05 `chromadb/chroma:latest` was Chroma 1.0.0 and wrote to `/data`. A later `latest` may differ again.
- **Replacement model (see errata 20):** which current model the course will switch to (Google recommends `gemini-3.5-flash-lite` for `gemini-2.0-flash`), and whether that changes answers or latency. `text-embedding-004` is listed as available until 2027-04-01. If it is replaced too, the pre-computed embeddings downloaded by `cli.py --download` (`src/vector-db/cli.py:487`) would no longer match the query embeddings.
- **Pulumi uv toolchain venv:** whether Pulumi's `toolchain: uv` uses the pre-built venv at `/home/app/.venv` (`Dockerfile:8,70`) or creates its own on first run. Either way it works, but the first `pulumi up` may spend time syncing dependencies.
- **Unpinned versions:** the Pulumi CLI installed by `curl … get.pulumi.com` (`Dockerfile:47`), Helm (installed from the `main`-branch `get-helm-3` script, `Dockerfile:44`), the gcloud SDK and docker-ce packages (`Dockerfile:30`), the kubectl *patch* version (only the minor is pinned, `K8S_MINOR=1.34`, `Dockerfile:33`), and the `chromadb/chroma:latest` and `nginx:stable` images are all unpinned. On 2026-11-05 they were Pulumi v3.274.0, Google Cloud SDK 592.0.0 with kubectl 1.35.9 first on `PATH`, Chroma 1.0.0 and nginx 1.30.6 (*At a glance*). Exact behaviour on your run date may differ.
- **Upstream changes:** on 2026-11-05 `main` is still `3ecef56`, but an unmerged staff branch shows a refactor in progress (§7), and cheese-app-v2's `main` was replaced by the same kind of refactor that day. Compare `git ls-remote https://github.com/dlops-io/cheese-app-v3` with the hash at the top of this guide (`3ecef56fea879ac480d260c0906cd95baf05179a`).
- **The Pulumi VM itself:** no run with a real project is recorded anywhere in the repo, so the exact `pulumi up` output, resource count and timing of `deploy_single_vm` are described from the code, not quoted.


---

## Links

**cheese-app-v3 README** (`main` @ `3ecef56`)
- [Deployment to GCP (Manual)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-to-gcp-manual): [Ensure you have all your container built and works locally](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#ensure-you-have-all-your-container-built-and-works-locally) · [Push Docker Images to Docker Hub](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#push-docker-images-to-docker-hub) · [Running Docker Containers on VM](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#running-docker-containers-on-vm) · [Install Docker on VM](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#install-docker-on-vm) · [Create folders and give permissions](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-folders-and-give-permissions) · [Add secrets file](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#add-secrets-file) · [Create Docker network](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-docker-network) · [Run vector-db](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-vector-db) · [Run vector-db-cli](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-vector-db-cli) · [Run api-service](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-api-service) · [Run frontend](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-frontend) · [Add NGINX config file](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#add-nginx-config-file) · [Run NGINX Web Server](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-nginx-web-server)
- [Deployment to GCP (Single VM Instance)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-to-gcp-single-vm-instance): [API's to enable in GCP before you begin](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#apis-to-enable-in-gcp-before-you-begin) · [Setup GCP Service Account for deployment](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#setup-gcp-service-account-for-deployment) · [Setup Docker Container (Pulumi, Docker, Kubernetes)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#setup-docker-container-pulumi-docker-kubernetes) · [Run `deployment` container](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#run-deployment-container) · [SSH Setup](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#ssh-setup) · [Configuring OS Login for service account](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#configuring-os-login-for-service-account) · [Create SSH key for service account](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-ssh-key-for-service-account) · [Providing public SSH keys to instances](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#providing-public-ssh-keys-to-instances) · [Deployment Setup](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-setup) (skip) · [Deployment (Single VM Instance)](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-single-vm-instance) · [Build and Push Docker Containers to Google Artifact Registry](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#build-and-push-docker-containers-to-google-artifact-registry) · [Create Compute Instance (VM) & Deploy Containers](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-compute-instance-vm--deploy-containers)
- [Delete the Compute Instance / Persistent disk](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#delete-the-compute-instance--persistent-disk)
- Code at the pinned commit: [`src/deployment/`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a/src/deployment) · latest README on [`main`](https://github.com/dlops-io/cheese-app-v3#deployment-to-gcp-manual)

**Course**
- Video: [AC215 · L20 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l20-deployment-pulumi) · [exercises](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l20-deployment-pulumi/exercises.md) · [capture provenance (ASSETS.md)](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l20-deployment-pulumi/ASSETS.md)
- Ed lesson: [L20 · Deployment: Pulumi](https://edstem.org/us/courses/97373/lessons/166045/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for this lecture.
- Previous lecture with a tutorial: [L18 · APIs + Frontend](L18-apis-frontend.md) (cheese-app-v2, the app this lecture deploys). L19 · Scaling: Kubernetes (local) has no tutorial yet ("coming soon" on the course site), so it has no guide.
- Next lecture: [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md) (`cheese-app-ci-cd`)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II](L03-containers-2-mega-pipeline.md) · [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md) · [L14 · Serverless Deployment: Cloud Functions, Cloud Run](L14-serverless-deployment.md) · [L22 · Scaling: Kubernetes (cloud)](L22-kubernetes-cloud.md) · [L23 · Final Deployment and Review](L23-final-cicd-deployment.md)
