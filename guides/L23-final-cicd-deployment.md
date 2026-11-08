# L23 · Final Deployment and Review — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166048/) · Tutorial: [`dlops-io/cheese-app-aws`](https://github.com/dlops-io/cheese-app-aws) `main` @ [`5950118`](https://github.com/dlops-io/cheese-app-aws/tree/5950118b0ed97c12c799920846d3eb70b1a47385) (the whole README, plus the workflow `.github/workflows/ci_cd_aws.yml`; the course site's AWS variant, "No K8s") · Lecture's Google Cloud version, context only: [`dlops-io/cheese-app-v4`](https://github.com/dlops-io/cheese-app-v4) `main` @ [`033f187`](https://github.com/dlops-io/cheese-app-v4/tree/033f18713b9e1e7985a3080e85edab3ff01cefef) · Colab notebooks: none · Video: [AC215 · L23 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l23-final-cicd) · Made from the verified digest and real terminal captures, 2026-11-08

## 中文速览

- **做什么：** slides 讲的是 Google Cloud 版（`cheese-app-v4`：GKE、Artifact Registry、Vertex AI）；这节课和 L15 一样走 **AWS variant** `dlops-io/cheese-app-aws`。把 cheese app（Next.js `frontend`、FastAPI `api-service`、Chroma `vector-db` 和它的 loader）部署到**一台** EC2 `t2.large` 上：在 laptop 上 `bash docker-shell.sh` 起 `cheese-app-deployment` toolbox container，依次跑 README 的 6 条 `ansible-playbook`（build + push 三个 image 到 ECR → 建 security group、EBS、instance → provision → 起 containers → 起 nginx → delete）；然后 README 完全没提的 `.github/workflows/ci_cd_aws.yml` 让 commit message 里带 `/run-deploy-app` 的 push 自动 redeploy。没有 Kubernetes，没有 Pulumi，没有 ML pipeline。
- **Idea 1 · 两个 secret，各开一扇门：** IAM user 的 access key（CSV）签 AWS API call（ECR login/push、建 EC2 资源、API 调 Bedrock）；EC2 key pair 的 `.pem` 只开 SSH（Ansible 以 `ubuntu` 登录 server）。两个都放在 clone **旁边**的 `secrets/` 里（`README.md:54-60`），不进 repo。access key 一路被复制：toolbox 的 env → server 上的 `aws configure` 和 `/srv/secrets/aws-credentials` → container 的 env → GitHub repository secrets。instance role 和 GitHub OIDC 能去掉这些 copy，但不在这个 repo 里。
- **Idea 2 · toolbox 里没有 Docker engine：** `docker-shell.sh:36` 把 laptop 的 `/var/run/docker.sock` mount 进去，所以 playbook 里的 `docker build` 由 laptop 的 Docker 执行，image 落在 laptop 的 disk 上，和 toolbox 是 sibling。CI 上 runner 用同一个 `src/deployment/Dockerfile` build 同一个 toolbox，但三个 app image 是 runner 自己 `docker build` 的，toolbox 在 CI 里只负责 deploy。
- **Idea 3 · Ansible 一张图：** inventory → playbook → play → task → module。`hosts: localhost` 的 play 在 toolbox 里跑（调 AWS API，或通过 socket 调 laptop 的 Docker）；`hosts: appserver` 的 play 通过 SSH 在 server 上跑（`become: true` = sudo）。每次 run 最后看 PLAY RECAP：`failed=0` 且 `unreachable=0` 才算成功。
- **Idea 4 · 一句 commit message 就是 release 按钮：** 每次 push 到 `main` 都会触发 workflow；job 要 message 含 `/run-`（`ci_cd_aws.yml:9`），最后的 "Run Deployment Container" step 还要含 `/run-deploy-app`（`:100`）；只看这次 push 的**最后一个** commit，`contains()` 不分大小写。`fix typo /run-tests` 只 build + push，不 deploy；repo 历史里那个 `\run-deploy-app`（反斜杠）什么都没跑。tag 是 `date +%Y%m%d%H%M%S`，server 上每个 container `recreate: yes`：是原地 swap，不是 Kubernetes 那种 rolling update。按 slides 11–12 的定义，人打 keyword = 按 release，这是 continuous delivery，而且前面没有任何 test（workflow 叫 "Continuous Integration and Continuous Deployment"，其实只有 CD 那一半）。
- **最费时间的坑（toolbox，2026-11-08 实测）：** ① README 的 `sh docker-shell.sh` 在 Ubuntu/Debian 上报 `docker-shell.sh: 13: Syntax error: redirection unexpected`（`/bin/sh` 是 dash，没有 `<<<`），改用 `bash docker-shell.sh`；Mac 上没问题。② `docker-shell.sh` 要改三处：`CSV_FILE`（`:10`，README 说的，四个 `../` 改成三个）、`SECRETS_DIR`（`:26`，README 没说，不改的话 toolbox 里 `/secrets` 是空的）、`AWS_ACCOUNT_ID`（`:17`，hard-code 了作者的 account）。③ toolbox build 卡在 Helm 那行（`curl: (60) SSL certificate problem`，`Dockerfile:33-34`），而且 `set -e` 被注释掉，script 接着去 `docker run` 一个不存在的 image（exit 125）；没有 playbook 用 Helm，删掉两行 Helm 和 `helm` 这个词就能 build。④ `pip install ansible>=9.0.0` 没加引号，`>` 是 shell redirect：装上的是 ansible 6.7.0 / ansible-core 2.13.13（Python 3.8.10），根目录多了一个叫 `=9.0.0` 的 log 文件。
- **最费时间的坑（playbooks）：** ① key pair 有三个名字：README 叫 `cheese-app-ac215-key-pair`，code 要 `ac215_2024`（`inventory.yml:16`）和 `ac215_2024.pem`；最省事是 key pair 就叫 `ac215_2024`。② README 把 key-line 切换（`inventory.yml` 第 4 行注释掉、第 7 行打开）写在 setup containers 那一节，但 provision 之前就要做，否则找不到 `/root/.ssh/ac215_2024.pem`；push 给 CI 之前再切回来。③ `deploy-setup-containers.yml:151` 用 `chromadb/chroma:latest`：今天是 1.0.0，`/api/v1/heartbeat` 返回 `HTTP 410`，而 client 是 0.5.18；先 pin 成 `chromadb/chroma:0.5.18`（和 `docker-compose.yml:25` 一样）。④ CI 只 deploy 到 commit 进去的 `inventory.yml:30` 那个 IP，从不建或 provision server。
- **做完要删：** README 的 `--extra-vars cluster_state=absent` 什么都不删：两个 task skip，然后 "Create EC2 instance" 报 `'dict object' has no attribute 'group_id'`，在任何 AWS call 之前就失败。要手动在 console 里：terminate instance `cheese-app-demo`，删掉还在计费的 50 GB volume `cheese-app-demo-disk`（它比 instance 活得久），删 security group `app_security_group`、key pair、三个 ECR repository，deactivate + delete access key（只为这节课建的 user 和 `CheeseAppECRPolicy` 也删），删 GitHub 上的四个 secrets；laptop 上 `docker image rm cheese-app-deployment`（2.52 GB）。
- **Lecture slides：** Lecture 23 的 slides（38 页：motivation、automation 也就是 CI/CD、整门课的 review）和这份 guide 各节怎么对应、做 tutorial 需要的 lecture ideas，以及 slides（Google Cloud）和这个 AWS repo 不一样的地方，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 17–18 说一个 deployment container 包办 build image、跑 Vertex AI job、deploy 到 K8s；这里 CI 在 runner 上直接 `docker build` 三个 app image，toolbox 只跑两个 playbook，而且没有 ML lane。② slide 20 的 keyword 是 `/deploy-app`（GCP repo 的）；这里是 `/run-deploy-app`，任何含 `/run-` 的 message 都会 build + push。

## At a glance

**What you build.** The cheese app you have built all term (a Next.js frontend, a FastAPI API that calls Amazon Bedrock models, a Chroma vector database and its loader) goes live on **one AWS EC2 virtual machine**, behind an nginx container on port 80. In Part 1 you do it by hand, following the README top to bottom: from a toolbox container on your laptop you run five Ansible playbooks that build and push three images to ECR, create a security group, a disk and the instance, provision the instance with Docker and the AWS CLI, start the app's containers and start nginx. In Part 2 a GitHub Actions workflow that the README never mentions takes over the redeploy: a push to `main` whose commit message contains `/run-deploy-app` makes a fresh GitHub runner rebuild the three images with a new timestamp tag, push them to ECR, and run the same toolbox to recreate the containers on your server. The lecture's slides tell the same story on Google Cloud with Kubernetes; §3.8 maps one onto the other.

**Time needed** (estimates; nothing ran against AWS when this guide was checked). About 30 minutes for the console setup (policy, user, access key, key pair, three ECR repositories). The toolbox builds in about 2–3 minutes the first time (132.8 s on the recording machine). The build-and-push playbook builds three images on your laptop, including a TensorFlow API image, which can take a long time, longer under `linux/amd64` emulation on Apple silicon. Creating and provisioning the instance: 15–30 minutes, mostly waiting. Part 2: about 1 hour for your repository, the four secrets and the first `/run-deploy-app` run. Budget 3–4 hours for a first pass, plus the clean-up.

**Prerequisites.**
- An AWS account with billing, console access, and permission to create IAM policies, users and access keys. The API calls Bedrock models in `us-east-1` (§2): check that your account can use them.
- Docker on your laptop (Docker Desktop on macOS). Everything else (AWS CLI, Ansible, kubectl) is inside the toolbox image.
- For Part 2: a GitHub account and a repository of your own holding this code (§4 Part F).
- Background: L02–L04 (images, `docker-shell.sh` scripts, bind mounts), L05 and L18 (the app's services), L15 on AWS (IAM users, access keys, ECR), L20 (a deployment container driving infrastructure), L21 (GitHub Actions: workflows, jobs, steps, runners, secrets). L22 (Kubernetes) is the Google Cloud path this variant does not take.

**What it costs** (AWS's public on-demand prices, roughly; check the pricing pages). From the create step until you clean up: the `t2.large` instance by the hour (on the order of $0.09/h in `us-east-1`), its two 100 GB gp2 disks and the separate 50 GB gp3 disk (per GB-month; the 50 GB one keeps billing after the instance is gone), its public IPv4 address by the hour, ECR storage for three images per deploy (old tags are never deleted), Bedrock per token for every chat message. GitHub Actions minutes are free on public repositories and counted against your plan on private ones. Details in §2.

**Tear down, exactly** (the README's delete command deletes nothing at this commit: §4 Step 27, §6 G9):
1. EC2 console › Instances: terminate `cheese-app-demo`.
2. EC2 › Volumes: delete every `cheese-app-demo` volume still listed, attached or not; `cheese-app-demo-disk` (50 GB) outlives the instance.
3. EC2 › Security Groups: delete `app_security_group`. EC2 › Key Pairs: delete yours.
4. ECR: delete the three repositories `cheese-app-frontend-react`, `cheese-app-api-service`, `cheese-app-vector-db-cli`.
5. IAM: deactivate and delete the access key; delete the user `deployment-ac215-user` and the policy `CheeseAppECRPolicy` if you made them only for this.
6. GitHub: delete the four repository secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `AWS_SSH_KEY`), or the repository.
7. Laptop: `docker image rm cheese-app-deployment` (2.52 GB) and any app images the build playbook left; keep or `git restore` your edited files.

Paths without a repo prefix are relative to `cheese-app-aws/`, and every `path:line` refers to the pinned commit `5950118`. Placeholders: `YOUR_ACCOUNT_ID` (your 12-digit AWS account id), `<aws-access-key-id>`, `<aws-secret-access-key>`, `<EXTERNAL_IP>` (your instance's public IP), `<your-user>` (your GitHub user).

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Series decision.** The course site lists `cheese-app-aws` for L23 as the AWS variant ("No K8s") next to the Google Cloud version `cheese-app-v4`. This guide and its video follow the AWS variant, as L15 did; the lecture slides (Google Cloud) decide the concepts, the AWS repo and the captures decide the commands and outputs.
- **README sections this lecture covers:** all of `README.md` (148 lines), top to bottom:
  - [`#deployment-to-aws`](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#deployment-to-aws) (3-5) · `#apis-to-enable-in-aws-before-you-begin` (7-13, renders empty) · `#setup-aws-keys-for-authentication` (15-60) · `#create-aws-ec2-key-pair` (62-64) · `#deployment-setup` (67-72) · `#deployment-steps` (74-77) · `#create-empty-ecr-repositories` (79-85) and its sub-steps (87-143) · "Delete the Compute Instance / Persistent disk" (145-148).
  - Not in the README: `.github/workflows/ci_cd_aws.yml` (131 lines), walked as its own part (§4 Part F).
- **Primary repo:** `dlops-io/cheese-app-aws`, branch `main`, commit `5950118b0ed97c12c799920846d3eb70b1a47385`, committed 2024-11-21 18:27:08 -0500 (message "cleanup"). `git ls-remote` on 2026-11-08: `HEAD` = `refs/heads/main` = `5950118`; no other branches, no tags (`laptop/01`, `03`). 39 commits; 33 of their messages are exactly `/run-deploy-app` (`laptop/50`).
- **Context repo (the slides' Google Cloud version):** `dlops-io/cheese-app-v4`, `main`, `033f18713b9e1e7985a3080e85edab3ff01cefef` (2025-12-02). Used only to explain the slides (§3.8, §7); nothing in the walkthrough comes from it.
- **Files read in full:** `README.md`; `.github/workflows/ci_cd_aws.yml`; everything in `src/deployment/` (`Dockerfile`, `docker-shell.sh`, the two unused entrypoints, `inventory.yml`, `ansible.cfg`, `Pipfile`, `.docker-tag`, the five `deploy-*.yml` playbooks, `nginx-conf/nginx/nginx.conf`); the API's `Dockerfile`, `Pipfile`, `api/service.py` and the Bedrock and RAG utils; the vector-db `Dockerfile`, `docker-compose.yml`, `Pipfile` and the download/load parts of `cli.py`; the frontend's `Dockerfile`, `.env.*`, `next.config.js` and `src/services/Common.js`.
- **Captures (2026-11-08, 01:13–01:20 UTC).** Every step that runs on a laptop was run live and recorded to one file per command, in the video folder's [`assets/terminal/laptop/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l23-final-cicd/assets/terminal) (`laptop/NN` below), with provenance in [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l23-final-cicd/ASSETS.md).
  - The "laptop": a fresh Ubuntu 24.04.5 machine (`/bin/sh` → `dash`) with Docker Engine 29.9.3, buildx 0.38.1, git 2.43.0, bash 5.2.21; user `student`, with `~/cheese-app-aws` and `~/secrets` side by side as `README.md:55-60` draws them.
  - **No AWS account.** The CSV held AWS's header and two obviously fake placeholder values (`PLACEHOLDER_NOT_A_REAL_ACCESS_KEY`, `PLACEHOLDER_NOT_A_REAL_SECRET_KEY_000000000000`); the `.pem` was a throwaway key generated for no account. All six `ansible-playbook` commands of the README were typed at the toolbox prompt exactly as written, in README order, and each stopped at its first real error.
  - The toolbox was built from the tutorial's own Dockerfile minus its two Helm lines (§6 G3). Inside it: aws-cli 2.39.6, ansible 6.7.0 / ansible-core 2.13.13 on Python 3.8.10, Docker CLI 28.1.1, kubectl v1.28.15, no helm; collections amazon.aws 3.5.0, community.aws 3.6.0, community.docker 2.7.3, community.general 5.8.3 (bundled) and 14.0.0 (installed by `Dockerfile:56`). Versions are those at the time of recording; yours may be newer.
  - The workflow's own `run:` scripts were run by hand on the laptop (`laptop/50`–`53`); the server's side was stood in for by local containers (`laptop/60`–`68`: Chroma `latest` and `0.5.18`, the repo's `nginx.conf` in front of two stand-ins).
- **Not captured:** anything AWS or GitHub must answer: the console pages, a real instance and SSH session, the playbooks' success output, a hosted Actions run, the live site. The README documents no command output at all, so this guide describes what success looks like and labels it *expected*; no output is invented.
- **Masking.** The repo commits an account id (`src/deployment/docker-shell.sh:17`), a server IP (`src/deployment/inventory.yml:30`) and `NEXTAUTH_SECRET` values (`inventory.yml:24`, `src/frontend-react/.env.production:3`). This guide shows them only as `YOUR_ACCOUNT_ID`, `<EXTERNAL_IP>` and `<nextauth-secret>`.
- **Colab notebooks:** none for this lecture.
- **Ed lesson:** not opened; the lecture side comes from the slides (next section).

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 23: Final Deployment and Review*, 38 slides. Slide numbers are PDF page numbers; a few slides pasted in from other decks print a different footer number. The slides are not reproduced here; what follows is paraphrased. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l23-final-cicd/SLIDES.md`. After one motivation slide (4), the deck has two parts: automation, that is CI/CD and how the cheese app does it (5–20), and a review of the whole course, one picture per earlier lecture (21–37). The review slides print lecture numbers from another year's schedule; the Pointers in `SLIDES.md` map them to this year's lectures. **The slides speak Google Cloud** (GKE, Artifact Registry, Vertex AI, a service-account key, the `cheese-app-v4` repo); this guide follows the AWS repo, and §3.8 maps the terms.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 19 (the cheese app's CI/CD map); 17–18 (GitHub Actions builds and runs the deployment container); 20 (the tutorial slide: workflow file, commit keyword, the three git commands) |
| §3.1 CI, delivery, deployment; §4 Step 26; §8 Ponder 4 | 7–12, 36 (the CI/CD loop; CI defined; delivery vs deployment) |
| §3.3 The toolbox and the Docker socket; §4 Part B; §8 Ponder 1 | 17–18; 35 (in development, the source code is mounted into the containers) |
| §3.5 One VM, five containers, one front door; §4 Steps 18–21 | 37 (L22's routing: one address, `/` and `/api/` to two services) |
| §3.6 Two sieves on one commit message; §4 Part F | 18, 20 |
| §3.7 One timestamp tag; §4 Step 25 | 18 (build and push images for release, then deploy them); 19 (Build → Deploy); 36 (Release before Deploy) |
| §3.8 The term map; §7 | 17–20; 5–6 (the five operations to automate) |
| §2 Costs; §4 Part G | 15 (cost as a challenge of CD) |
| §7 Where this sits in the course | 21–37 (the review); 24 (the senior developer who builds and pushes by hand); 25 (the solution architecture) |
| §3.2 Ansible, §3.4 Identity, §5 Code tour, §6 Gotchas, §9 Errata | none (tutorial-only) |
| Background, not needed to finish the tutorial | 4 (a joke prediction web app as motivation); 13–14 (CI for ML); 16 (six CI/CD services); 22–23, 26–34 (the review of environments and containers, the audio pipeline, labeling, ChatGPT's training, RAG, agents, LoRA, distillation, training jobs, model deployment, pipelines) |

**Lecture ideas you need for this tutorial**
1. Automate five operations: data pipeline jobs, model training and deployment, frontend deployment, backend deployment, and building and pushing images (5–6). This repo automates frontend and backend deployment (always together, one keyword) and building and pushing the three app images; it has no data or training jobs (on AWS those were L15's SageMaker pipeline).
2. CI/CD is one loop: commits → build → test → (release →) deploy → monitor, with every stage after the codebase notifying the developers (7, 36). Here build, release (the tagged images landing in ECR) and deploy are wired; Test is empty, and the run's colour plus your own check of the site are the only monitoring (§3.1).
3. CI runs scripts on every push: automated tests, coding standards (style and consistency) and static analysis (defects and vulnerabilities, found without running the code) (8–10). None of them runs in `ci_cd_aws.yml`; L09 and L21 built that half.
4. Delivery vs deployment is whether a person presses release (11–12). Typing `/run-deploy-app` is that person; deploying every merge to `main`, behind tests, would be continuous deployment (Milestone 5, §8 Ponder 4).
5. CI/CD for ML also checks data quality and model performance, balances frequent runs against training cost, and releases a model only within a tolerance while watching for data drift (13–15). This repo deploys an app, not a model.
6. Don't build new machinery: the deployment container already deploys, so GitHub Actions only builds it and runs it on each commit that asks (17–18, §3.3).
7. The cheese app's map: Dev Team → GitHub → GitHub Actions (Build, Deploy) → the cloud → users (19, §1, §3.8).
8. The trigger: a workflow file in `.github/workflows` defines the steps, and a keyword in the commit message starts them; the slide's three commands are `git add`, `git commit -m "… <keyword>"`, `git push` (20, §3.6).
9. The final app is the course: every earlier lecture built one of its parts (21–37, §7).

**Where the slides and today's tutorial differ** (in each case, follow the repo at `5950118`)
- **Cloud and tools.** The slides deploy to a GKE cluster with images in Artifact Registry and a service-account key in a GitHub secret. This repo deploys to one EC2 instance running Docker containers, set up by Ansible playbooks, with images in ECR and an IAM access key plus an EC2 key pair as secrets (§3.8).
- **Slides 17–18: one deployment container does everything through a CLI** (build images, run Vertex AI jobs, deploy). Here the runner builds the three app images itself with plain `docker build` (`ci_cd_aws.yml:52-70`), and the toolbox only runs two playbooks (`:123-131`). There is no ML lane.
- **Slide 20's keyword is `/deploy-app`**, the Google Cloud repo's. Here it is `/run-deploy-app` (`ci_cd_aws.yml:100`), and any message containing `/run-` builds and pushes new images without deploying (`:9`; §3.6).
- **Slide 20's basic commands start with a bare `git add`**, which stages nothing ("Nothing specified, nothing added."). Use `git add .`. The README has no git commands at all; §4 Step 25 gives them.
- **Slides 7, 20 and 36 draw Test and Monitor stages.** The workflow is named "Continuous Integration and Continuous Deployment" (`ci_cd_aws.yml:1`) but runs no test, lint or monitoring step; slide 18's own heading, "How to Implement CD", fits it better (§3.1).
- **Slide 19 draws one chain from Model Deploy into the Backend API.** This repo has no training or model-deployment step; its API calls ready-made Bedrock models (§2).
- **Slide 18 deploys to a Kubernetes cluster** (with L22's rolling update, new pods before old ones go). On one VM, `recreate: yes` stops each container and starts the new one: a short gap per container, not a rolling update (§3.7).
- **Slide 37 (the L22 review) routes through a Kubernetes ingress controller.** Here one nginx container is the front door: `location ^~ /api/` → `api-service:9000` with the prefix stripped, everything else → `frontend:3000` (§3.5).

## Command checklist

Commands in backticks are exactly as the README writes them; placeholders such as `<External IP>` are kept. Plain items are console clicks or file edits. Items marked *(extra)* are not in the README; they come from §4, §6 and the captures. The README's commands stay in README order; where one fails or needs a change today, it is kept verbatim and the working variant follows as a note. Run `ansible-playbook` commands **inside the toolbox** (prompt `root@<container id>:/app#`), `git` and `docker` commands on the laptop, and `sudo docker …` commands on the server.

### Before the README *(extra)*

- [ ] `git ls-remote https://github.com/dlops-io/cheese-app-aws.git` — *(extra)* `HEAD` and `refs/heads/main` should still be `5950118b0ed97c12c799920846d3eb70b1a47385`; nothing else is listed (2026-11-08).
- [ ] `git clone https://github.com/dlops-io/cheese-app-aws.git` — *(extra)* the README has no clone step. Clone into a folder that will also hold `secrets/`, so the two sit side by side (`README.md:55-60`).
- [ ] `git -C cheese-app-aws log -1 --format='%H %ci %s'` — *(extra)* `5950118… 2024-11-21 18:27:08 -0500 cleanup`.
- [ ] `mkdir secrets` — *(extra)* next to the clone, not inside it.

### API's to enable in AWS before you begin

- [ ] Nothing to do: the list (`README.md:9-13`) is inside an HTML comment, and AWS has no per-service "enable API" step. *(extra)* Check that your account can use the Bedrock models the API calls in `us-east-1` (§2).

### Setup AWS Keys for Authentication

- [ ] IAM › Policies › Create policy › JSON: paste the policy from `README.md:22-44`; "Review Policy", name `CheeseAppECRPolicy`, Create Policy (`README.md:19-46`).
- [ ] `sed -n '23,43p' cheese-app-aws/README.md | python3 -m json.tool` — *(extra)* the JSON parses (echoes it back, exit 0).
- [ ] IAM › Users › Create user `deployment-ac215-user`, attach `AmazonS3FullAccess`, `AmazonEC2FullAccess`, `AmazonBedrockFullAccess` (`README.md:48`).
- [ ] Attach `CheeseAppECRPolicy` to the user too (`README.md:50`).
- [ ] The user › Create access key › Third Party Service › Create › Download .csv file (`README.md:52`).
- [ ] Save it as `secrets/deployment-ac215-user_accessKeys.csv` (`README.md:54-60`).

### Create AWS EC2 Key Pair

- [ ] EC2 › Key Pairs › Create Key Pair, download the `.pem`, save it in `secrets/` (`README.md:64`). The README names it `cheese-app-ac215-key-pair`; the code expects the key pair `ac215_2024` and the file `ac215_2024.pem` (§6 G6). Easiest: name the key pair `ac215_2024`, so the file is `secrets/ac215_2024.pem`.
- [ ] `chmod 400 ~/secrets/ac215_2024.pem` — *(extra)* SSH refuses a private key others can read (the capture did this on its throwaway key: `-r--------`, `laptop/14`).

### Deployment Setup

- [ ] Read `src/deployment/inventory.yml` against the four bullets of `README.md:69-72`: ansible user (`:3`), instance details (`:14-23`), access-key details (`:9-11`, read from the environment: nothing to type), key pair (`:4`, `:7`, `:16`).
- [ ] *(extra)* Edit `inventory.yml:16` to your key pair's name if it is not `ac215_2024`, and `inventory.yml:24` (`nextauth_secret`) to a random value of your own (e.g. from `openssl rand -base64 32`).

### Deployment Steps

- [ ] `cd cheese-app-aws/src/deployment` — the README's "Go to src/deployment folder" (`README.md:75`).
- [ ] `bash docker-shell.sh` — *(extra, optional)* run as cloned, it stops: `Error: AWS credentials file not found at ../../../../secrets/deployment-ac215-user_accessKeys.csv` (`laptop/21`). Four `../` from `src/deployment` go one level too far.
- [ ] Edit `docker-shell.sh:10` to `CSV_FILE="../../../secrets/deployment-ac215-user_accessKeys.csv"` (`README.md:76`).
- [ ] *(extra)* Edit `docker-shell.sh:26` to `export SECRETS_DIR=$(pwd)/../../../secrets/` (same fix; the README does not mention it, and without it `/secrets` is empty in the toolbox, `laptop/28`) and `docker-shell.sh:17` to your account id (`export AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"` with your 12 digits).
- [ ] *(extra, if the build fails at step 9/15)* In `Dockerfile`, delete the two `baltocdn.com` lines (`:33-34`) and the word `helm` in `:36` (§6 G3; `laptop/27` shows the diff).
- [ ] `sh docker-shell.sh` (`README.md:77`) — fails on Ubuntu/Debian: `docker-shell.sh: 13: Syntax error: redirection unexpected` (`laptop/23`). **Working variant:** `bash docker-shell.sh`. On macOS the README line works.
- [ ] `ls -la /secrets; env | grep ^AWS_ | cut -d= -f1 | sort` — *(extra, in the toolbox)* both files present; `AWS_ACCESS_KEY_ID`, `AWS_ACCOUNT_ID`, `AWS_DEFAULT_REGION`, `AWS_SECRET_ACCESS_KEY` set (`laptop/31`).
- [ ] `aws --version`, `ansible --version`, `docker --version` — *(extra, in the toolbox)* aws-cli 2.39.6, ansible-core 2.13.13, Docker 28.1.1 at the time of recording (`laptop/32`).
- [ ] `aws sts get-caller-identity` — *(extra, in the toolbox)* with your keys, your account id and user ARN; with a bad key, `InvalidClientTokenId` (`laptop/34`).
- [ ] `ansible-inventory -i inventory.yml --graph` — *(extra, in the toolbox)* `@all` → `@appserver` → one host (`laptop/35`).
- [ ] `for f in deploy-*.yml; do ansible-playbook $f -i inventory.yml --syntax-check; done` — *(extra, in the toolbox)* five `playbook: …` lines (`laptop/36`).

### Create Empty ECR Repositories

- [ ] In the ECR console, `us-east-1`, private registry (`README.md:81`), create `cheese-app-vector-db-cli` (`:83`).
- [ ] … `cheese-app-api-service` (`:84`).
- [ ] … `cheese-app-frontend-react` (`:85`).

### Build and Push Docker Containers to AWS ECR (Elastic Container Registry)

- [ ] `ansible-playbook deploy-docker-images.yml -i inventory.yml` (`README.md:89`, in the toolbox) — builds the three images on your laptop's Docker, tags them with a timestamp, pushes them, writes `.docker-tag`. *Expected:* 11 tasks, `failed=0` (§4 Step 12).
- [ ] `docker images` — *(extra, on the laptop)* the three `YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cheese-app-…:<tag>` images sit next to the toolbox.

### Create Compute Instance (VM) Server in GCP

(The heading says GCP; the playbook creates an **EC2** instance on AWS.)
- [ ] `ansible-playbook deploy-create-instance.yml -i inventory.yml --extra-vars cluster_state=present` (`README.md:94`, in the toolbox) — security group, 50 GB volume, `t2.large` instance. **Billing starts.**
- [ ] Copy the instance's public IP from the EC2 console into `inventory.yml` under `appserver:` › `hosts:` (line 30) (`README.md:97`).

### Provision Compute Instance in GCP

- [ ] *(extra, do first)* The key-line switch from the next section (`README.md:107-111`): comment out `inventory.yml:4`, uncomment `inventory.yml:7`. A laptop run needs it now; with line 4 active, Ansible looks for `/root/.ssh/ac215_2024.pem`, which is not in your toolbox (§6 G8).
- [ ] `ansible-playbook deploy-provision-instance.yml -i inventory.yml` (`README.md:102`, in the toolbox) — 38 tasks: Docker, the data disk at `/mnt/disk-1`, AWS CLI v2, `aws configure`.

### Setup Docker Containers in the  Compute Instance

- [ ] The key-line switch (`README.md:107-111`): `inventory.yml:4` (`/root/.ssh/ac215_2024.pem`, "Github Actions") commented, `inventory.yml:7` (`/secrets/ac215_2024.pem`, "no ci/cd") active, for every run from your laptop. Done above.
- [ ] *(extra)* Edit `deploy-setup-containers.yml:151` from `image: "chromadb/chroma:latest"` to `image: "chromadb/chroma:0.5.18"`, the version the clients and `src/vector-db/docker-compose.yml:25` use (§6 G10).
- [ ] `ansible-playbook deploy-setup-containers.yml -i inventory.yml` (`README.md:116`, in the toolbox) — 25 tasks: keys file, network `appnetwork`, ECR login, pull, `frontend`, `vector-db`, the loader, `api-service`.
- [ ] `ssh -i ~/secrets/ac215_2024.pem ubuntu@<EXTERNAL_IP>` — *(extra, on the laptop)* the README says "SSH into the server from the GCP console" (`README.md:120`); on AWS use SSH or EC2 Instance Connect.
- [ ] `sudo docker container ls` (`README.md:122`, on the server) — the IMAGE column shows your tag.
- [ ] `sudo docker container logs api-service -f` (`README.md:123`) — Ctrl-C to stop following.
- [ ] `sudo docker container logs frontend -f` (`README.md:124`)
- [ ] `sudo docker container logs nginx -f` (`README.md:125`) — works only after "Setup Webserver" below.
- [ ] `sudo docker exec -it api-service /bin/bash` (`README.md:130`) — `exit` to leave.
- [ ] `sudo docker exec -it nginx /bin/bash` (`README.md:131`) — after "Setup Webserver".

### Configure Nginx file for Web Server

- [ ] Nothing to create: `src/deployment/nginx-conf/nginx/nginx.conf` is already in the repo (`README.md:137`). Read `:25-27` (port 80) and `:34-55` (the two routes).

### Setup Webserver on the Compute Instance

- [ ] `ansible-playbook deploy-setup-webserver.yml -i inventory.yml` (`README.md:141`, in the toolbox) — 4 tasks: network, copy the config to `/conf`, start `nginx:stable` on 80/443, restart it.
- [ ] Open `http://<External IP>/` (`README.md:143`) — the cheese app. Port 80 only: there is no HTTPS server block (§6 G19).

### CI/CD with GitHub Actions *(extra: `.github/workflows/ci_cd_aws.yml`, not in the README)*

The server must already exist and be provisioned; CI never creates or provisions it. The README's last command (Delete, below) stays last; run it only when you are done with Part 2.
- [ ] Create an empty **private** repository on GitHub (a fork also works; then enable workflows in its Actions tab).
- [ ] `git remote set-url origin https://github.com/<your-user>/cheese-app-aws.git` — *(extra)* point the clone at your repository.
- [ ] `git push -u origin main` — *(extra)* the last commit's message is `cleanup` (no `/run-`), so nothing runs yet.
- [ ] Settings › Secrets and variables › Actions: add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `AWS_SSH_KEY` (the whole `.pem` text). Names from `ci_cd_aws.yml:21-22`, `:33`, `:81`, `:102-108`.
- [ ] Before committing: `inventory.yml:30` = your server's IP; `inventory.yml:4` active again and `:7` commented (undo the switch); the Helm fix in `Dockerfile` (if you made it); the Chroma pin in `deploy-setup-containers.yml:151`.
- [ ] `git add .` — *(extra; slide 20 shows a bare `git add`, which stages nothing)* this also stages your account id (`docker-shell.sh:17`) and your `NEXTAUTH_SECRET` (`inventory.yml:24`): keep the repository private.
- [ ] `git commit -m "your message /run-deploy-app"` — *(extra; slide 20 with this repo's keyword)*
- [ ] `git push` — *(extra)* starts the run: build and push three images, then "Run Deployment Container".
- [ ] Check: the Actions tab shows a green run of job `Explore-GitHub-Actions`; reload `http://<EXTERNAL_IP>/`; on the server `sudo docker container ls` shows the new tag. A green run means every step that ran exited 0, not that the site works.

### Delete the Compute Instance / Persistent disk

- [ ] `ansible-playbook deploy-create-instance.yml -i inventory.yml --extra-vars cluster_state=absent` (`README.md:147`, in the toolbox) — fails at this commit before any AWS call: `'dict object' has no attribute 'group_id'`, `ok=1 … failed=1 skipped=2` (`laptop/48`). **Nothing is deleted.** Use the manual list below.

### After the README *(extra)*

- [ ] EC2: terminate `cheese-app-demo`; delete every leftover `cheese-app-demo` volume (the 50 GB `cheese-app-demo-disk` outlives the instance); delete `app_security_group` and your key pair.
- [ ] ECR: delete the three repositories. IAM: deactivate and delete the access key; the user and `CheeseAppECRPolicy` if made only for this. GitHub: delete the four secrets.
- [ ] `docker image rm cheese-app-deployment` — *(extra, on the laptop)* 2.52 GB (`laptop/29`); also remove the three `…dkr.ecr…/cheese-app-…` images if the build playbook made them.
- [ ] `git status --short` — *(extra)* your edits: `Dockerfile`, `docker-shell.sh`, `inventory.yml` (`laptop/49`), plus `deploy-setup-containers.yml` (the pin) and `.docker-tag` (after a real build). Keep them or `git restore` them.

---

## 1. What you build

The cheese app goes live on one AWS virtual machine, and two kinds of automation take over from your hands.

**Part 1: Ansible from your laptop (the README).** Everything runs inside one toolbox container, `cheese-app-deployment` (Ubuntu 20.04 with the AWS CLI v2, the Docker CLI, kubectl and Ansible), started by `docker-shell.sh` in `src/deployment/`. From its shell you run five playbooks against one inventory file:

| README step | Playbook | Runs on | What it does |
| --- | --- | --- | --- |
| Build and push (`README.md:89`) | `deploy-docker-images.yml` | `localhost` = the toolbox, using your laptop's Docker through the mounted socket | ECR login; builds `cheese-app-frontend-react`, `cheese-app-api-service`, `cheese-app-vector-db-cli`, tags each `:<YYYYmmddHHMMSS>`, pushes them; writes the tag to `.docker-tag` |
| Create instance (`:94`) | `deploy-create-instance.yml`, `cluster_state=present` | `localhost` (AWS API calls with boto3) | security group `app_security_group` (22, 80, 443 open to the world), a 50 GB gp3 volume, a `t2.large` instance `cheese-app-demo` from an Ubuntu image with your key pair; waits for SSH |
| Provision (`:102`) | `deploy-provision-instance.yml` | `appserver`, over SSH, `become: true` | Docker CE, the data disk at `/mnt/disk-1`, AWS CLI v2, `aws configure` with your keys |
| Setup containers (`:116`) | `deploy-setup-containers.yml` | `appserver` | `/srv/secrets/aws-credentials`, Docker network `appnetwork`, ECR login, pulls the three images at the saved tag; starts `frontend` (3000), `vector-db` (Chroma, 8000), runs the loader once, starts `api-service` (9000) |
| Setup webserver (`:141`) | `deploy-setup-webserver.yml` | `appserver` | copies `nginx-conf/nginx/` to `/conf`, starts `nginx:stable` on 80 and 443: `/api/` → `api-service:9000`, `/` → `frontend:3000` |
| Delete (`:147`) | `deploy-create-instance.yml`, `cluster_state=absent` | `localhost` | meant to tear down; fails before any AWS call at this commit (§6 G9) |

Then you open `http://<EXTERNAL_IP>/` (`README.md:143`).

**Part 2: GitHub Actions does the redeploy** (`.github/workflows/ci_cd_aws.yml`, not in the README). On every push to `main` whose last commit message contains `/run-`, a fresh GitHub-hosted Ubuntu runner checks out the repository, logs in to AWS with repository secrets, builds the toolbox image, builds the three app images with plain `docker build`, tags them with a fresh timestamp and pushes them to ECR. If the message also contains `/run-deploy-app`, the runner starts the toolbox and runs two playbooks in it: `deploy-setup-containers.yml` with the new tag, then `deploy-setup-webserver.yml`. The server must already exist and be provisioned, and its IP must be committed in `inventory.yml`.

There are **no tests** anywhere in the workflow, although it is named "Continuous Integration and Continuous Deployment" (`ci_cd_aws.yml:1`): this is the CD half of the lecture's loop (§3.1).

```
 YOUR LAPTOP                                          GITHUB  <your-user>/cheese-app-aws
 +--------------------------------------------+       +------------------------------------------+
 | ~/secrets/  CSV access key, .pem key       | push  | .github/workflows/ci_cd_aws.yml          |
 | src/deployment$ bash docker-shell.sh       | ----> | secrets: AWS_ACCESS_KEY_ID,              |
 |  -> cheese-app-deployment (toolbox)        | main  |   AWS_SECRET_ACCESS_KEY, AWS_ACCOUNT_ID, |
 |     ansible-playbook deploy-*.yml          |       |   AWS_SSH_KEY                            |
 +---------------------+----------------------+       +--------------------+---------------------+
   build+push          | create, provision,             message has "/run-" | build+push (docker)
   (laptop Docker)     | set up over SSH              "/run-deploy-app"    | setup-containers,
                       v                                                   v setup-webserver
 +-------------------------------------------------------------------------------------------------+
 | AWS us-east-1                                                                                   |
 |  ECR: cheese-app-frontend-react / cheese-app-api-service / cheese-app-vector-db-cli  :<tag>     |
 |  EC2 t2.large "cheese-app-demo" (Ubuntu), security group 22/80/443, data disk at /mnt/disk-1    |
 |    Docker network "appnetwork":                                                                 |
 |      nginx :80 --/api/--> api-service :9000 --> vector-db :8000 (Chroma)                        |
 |            \----/------> frontend :3000                   Bedrock (Claude, Titan) <- api        |
 +-------------------------------------------------------------------------------------------------+
                                   ^ browser: http://<EXTERNAL_IP>/
```

## 2. Prerequisites and costs

### Accounts and local installs
- **AWS account** with billing and console access. The API calls Amazon Bedrock in `us-east-1`: `anthropic.claude-3-5-sonnet-20240620-v1:0` (`src/api-service/api/utils/llm_utils.py:35`), `anthropic.claude-3-sonnet-20240229-v1:0` (`llm_rag_utils.py:22`, `llm_cnn_utils.py:47`) and the embedding model `amazon.titan-embed-text-v1` (`llm_rag_utils.py:21`). The README never mentions Bedrock model access; these are models chosen in 2024, so check in the Bedrock console that your account can still use them (§9).
- **Docker** on the laptop. Nothing else: the AWS CLI, Ansible and kubectl are inside the toolbox.
- **GitHub**: a repository of your own for Part 2, with Actions enabled.

### The empty "API's to enable" section
`README.md:7-13` has a heading whose list (ECR, IAM, VPC, Security Groups, Load Balancer) is inside an HTML comment, so the section renders empty. AWS needs no per-service enablement; no load balancer is used anywhere in the code.

### Identity: one IAM user, one key pair
- **Policy `CheeseAppECRPolicy`** (`README.md:19-46`): `sts:GetCallerIdentity` plus nine ECR actions (`GetAuthorizationToken`, `BatchCheckLayerAvailability`, `PutImage`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`, `ListImages`, `BatchGetImage`, `GetDownloadUrlForLayer`) on `"Resource": "*"`. It does **not** include `ecr:CreateRepository`, which is why you create the three repositories in the console (`README.md:79-85`).
- **IAM user `deployment-ac215-user`** (`README.md:48-50`) with the AWS-managed policies `AmazonS3FullAccess`, `AmazonEC2FullAccess`, `AmazonBedrockFullAccess`, plus `CheeseAppECRPolicy`.
- **Access key** for a "Third Party Service" (`README.md:52`), downloaded as `deployment-ac215-user_accessKeys.csv` into `secrets/` beside the clone (`:54-60`). `docker-shell.sh:13` reads its second line as `AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY`.
- **EC2 key pair** (`README.md:64`): the README names it `cheese-app-ac215-key-pair`; the code expects the key pair name `ac215_2024` (`inventory.yml:16`, marked `## Change this`) and the file `ac215_2024.pem` (`inventory.yml:4`, `:7`; `docker-shell.sh:27`; `ci_cd_aws.yml:81`). Use one name everywhere (§6 G6).

### Values committed in the repo that you change
| File:line | At `5950118` | Change to |
| --- | --- | --- |
| `src/deployment/docker-shell.sh:10` | `CSV_FILE="../../../../secrets/deployment-ac215-user_accessKeys.csv"` | three `../` (`README.md:76`) |
| `docker-shell.sh:26` | `SECRETS_DIR=$(pwd)/../../../../secrets/` | three `../` (not in the README) |
| `docker-shell.sh:17` | the author's account id | your 12-digit account id |
| `src/deployment/Dockerfile:33-34`, `:36` | the Helm repository lines, `kubectl helm` | delete them and the word `helm`, if the build fails there (§6 G3) |
| `inventory.yml:4` / `:7` | the GitHub Actions key line active, the laptop line commented | swap them for laptop runs, swap back before pushing for CI (`README.md:107-111`) |
| `inventory.yml:16` | `aws_keypair_name: "ac215_2024"` | your key pair's name |
| `inventory.yml:17` | `aws_ami_id: "ami-0e86e20dae9224db8"` | keep for `us-east-1` if it still exists; image ids are per region (§9) |
| `inventory.yml:24` | a committed `NEXTAUTH_SECRET` | your own random value |
| `inventory.yml:30` | the author's server IP | your instance's public IP, after the create step (`README.md:97`) |
| `deploy-setup-containers.yml:151` | `image: "chromadb/chroma:latest"` | `image: "chromadb/chroma:0.5.18"` (§6 G10) |

### What costs money, and how to switch it off
*(AWS's public on-demand list prices for `us-east-1`, roughly; check the pricing pages before you start.)*
- **EC2 `t2.large`** (`inventory.yml:15`): billed by the hour from the create step until you terminate it, idle or not; on the order of $0.09/h.
- **EBS**: the instance's two 100 GB gp2 volumes (`deploy-create-instance.yml:47-57`, deleted with the instance) and the separate 50 GB gp3 volume `cheese-app-demo-disk` (`:27-37`), which survives the instance and bills per GB-month until you delete it.
- **Public IPv4 address** on the instance, billed by the hour.
- **ECR storage**: three images per build, a new timestamp tag every time; nothing deletes old tags.
- **Bedrock**: per token, on every chat message.
- **GitHub Actions**: free on public repositories; counted against your plan's minutes on private ones. Every `/run-` push builds three images, including the TensorFlow API.
- **Switch-off:** by hand (At a glance, "Tear down, exactly"); the README's delete command deletes nothing (§6 G9).

## 3. Concepts this tutorial teaches

### 3.1 Integration, delivery, deployment, and what this workflow is (slides 7–12, 36)
The lecture's loop runs Codebase → Build → Test → (Release →) Deploy → Monitor, with notifications back to the developers from every stage (7, 36). **Continuous integration** is the left half: many developers merge into one shared repository, and every change passes automated tests, coding standards and static analysis (8–10). **Continuous delivery** keeps every change ready to release, and a person presses the release button; **continuous deployment** ships every passing change by itself (11–12). `ci_cd_aws.yml` has build, release (the moment the tagged images land in ECR) and deploy, but no test step, and a person decides each release by typing the keyword: in the lecture's words, continuous *delivery* of the CD half. A green run means every step that ran exited 0, not that the app works; checking the site is the Monitor box. Milestone 5's version puts L21's tests in front and deploys every merge to `main`.

### 3.2 Ansible in one picture: inventory, playbook, play, task, module
- **Inventory** (`src/deployment/inventory.yml`): group `all` with variables (`:2-25`) and one child group `appserver` with one host, the server's IP (`:27-30`). `ansible-inventory -i inventory.yml --graph` prints `@all` → `@appserver` → that host (`laptop/35`).
- **Playbook** = a list of plays. Each play names its `hosts:` (`localhost` or `appserver`), optionally `connection: ssh` and `become: true` (sudo on the server), and a list of **tasks**; each task calls one **module** (`shell`, `file`, `copy`, `apt`, `docker_image`, `docker_container`, `docker_network`, `ec2_group`, `ec2_vol`, `amazon.aws.ec2_instance`, …) with arguments.
- **Where tasks run.** `hosts: localhost` plays run inside the toolbox (Ansible's controller): their AWS modules call the AWS API with boto3, their Docker modules talk to your laptop's Docker through the socket. `hosts: appserver` plays SSH to the server as `ubuntu` (`inventory.yml:3`) with the `.pem` key and run each module there. Lookups such as `lookup('env', …)` always run on the controller: that is how your keys reach the server.
- **Declarative modules converge.** `state: present` / `state: started` describe what should be true; re-running reports `ok` instead of `changed`. `shell:` tasks run every time. The `when:` lines (`deploy-create-instance.yml:24`, `:37`, `:74`, …) are meant to make one playbook create and delete (§6 G9).
- **Reading a run.** Every run ends with a PLAY RECAP line per host: success means `failed=0` and `unreachable=0`.
- **Trust on first use, switched off.** `ansible.cfg:2` sets `host_key_checking = False`, and `inventory.yml:8` passes `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`: a fresh server's host key is accepted blindly. Convenient for a course, a trade-off to know about.
- Compared with L20's Pulumi, which describes the infrastructure you want and computes a plan, Ansible runs an ordered list of tasks against the machines in an inventory.

### 3.3 One toolbox, two operators, sibling containers (slides 17–18, 35)
The same `src/deployment/Dockerfile` builds the toolbox on your laptop (`docker-shell.sh:32`) and on the runner (`ci_cd_aws.yml:41-44`). The toolbox has the Docker CLI but no Docker engine: the host's socket is mounted (`docker-shell.sh:36`, `ci_cd_aws.yml:114`), so every `docker build` or `docker push` from inside is carried out by the host's engine, and the images land on the host's disk as **siblings** of the toolbox. That is why the build playbook's paths are `/frontend-react`, `/api-service`, `/vector-db` (`deploy-docker-images.yml:21`, `:34`, `:47`): `docker-shell.sh:40-42` mounts the three app folders at exactly those paths. It is also why `docker system prune -a` from inside would sweep your laptop.
- **Laptop:** the deployment folder at `/app` (`docker-shell.sh:37`), `secrets/` at `/secrets` (`:38`), an interactive shell (`-ti`, `:35`) where you type the playbooks.
- **Runner:** the deployment folder at `/deployment` (`ci_cd_aws.yml:115`), the runner-made secrets folder at `/root/.ssh` (`:116`), a `bash -c` string that runs two playbooks (`:123-131`), and no app folders: CI builds the app images with plain `docker build` on the runner (`:52-70`), not with the playbook.
- `ENTRYPOINT` is commented out (`Dockerfile:62`; `CMD ["/bin/bash"]`, `:64`), so the two entrypoint scripts never run. Nothing breaks: the AWS CLI and boto3 read `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_DEFAULT_REGION` from the environment (`docker-shell.sh:43-45`), and the build playbook (`deploy-docker-images.yml:9`) and the CI step (`ci_cd_aws.yml:129`) log in to ECR themselves.
- Slide 17's premise is exactly this: the deployment container already exists, so GitHub Actions only builds and runs it. The workflow stays thin; the deploy logic lives in the playbooks.

### 3.4 Two secrets, and where the access key travels
- **The access key** (CSV) signs calls to the AWS API: ECR logins and pushes, the security group, volume and instance, the API's Bedrock calls. **The key pair's private key** (`.pem`) opens SSH to the server as `ubuntu`. Neither can do the other's job.
- The access key travels: CSV in `secrets/` → shell variables (`docker-shell.sh:13-15`) → the toolbox's environment (`:43-46`) → Ansible variables through `lookup('env', …)` (`inventory.yml:9-11`, `deploy-setup-containers.yml:8-11`) → the server, twice: `aws configure` (`deploy-provision-instance.yml:288-292`) and `/srv/secrets/aws-credentials`, mode 0600 (`deploy-setup-containers.yml:36-44`, mounted into `api-service` at `/secrets`, `:194`) → the environment of `api-service` (`:184-186`) and of the loader (`:166-168`) → in CI, the repository secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (`ci_cd_aws.yml:21-22`, `:102-103`). The `.pem` goes to GitHub as `AWS_SSH_KEY` (`:81`, `:108`).
- Every copy is one more place to protect. AWS's documented alternatives, not in this repository: an **instance role** (the server gets short-lived credentials without a key file) and **GitHub OIDC** (the workflow assumes a role with a token GitHub issues per run, no stored keys).

### 3.5 One VM, five containers, one front door (slide 37)
On the Docker network `appnetwork` (`deploy-setup-containers.yml:47-53`) containers reach each other by name. `nginx` publishes 80 and 443 (`deploy-setup-webserver.yml:29-31`) and is the only entry the security group lets in besides SSH (`deploy-create-instance.yml:12-21`); ports 3000, 8000 and 9000 are published on the server but closed by the security group.
- `location ^~ /api/ { proxy_pass http://api-service:9000/; … }` (`nginx.conf:35-44`): because `proxy_pass` ends with a path (`/`), nginx replaces the matched prefix `/api/` with it, so the browser's `/api/newsletters` reaches FastAPI as `/newsletters`, where `api/service.py:25` mounts that router. Captured with stand-ins (§4 Step 20).
- `location / { proxy_pass http://frontend:3000; … }` (`nginx.conf:47-55`).
- The frontend calls `/api/…` on the same host: `.env.production:2` sets `NEXT_PUBLIC_BASE_API_URL=/api`, read by `src/services/Common.js:2`.
- Data: Chroma persists to `/mnt/disk-1/chromadb` (`deploy-setup-containers.yml:162`), the API's `/persistent` to `/mnt/disk-1/persistent` (`:193`), on the disk the provision playbook mounts (`deploy-provision-instance.yml:159-176`).
- The vector database is filled once per deploy by a throwaway container: `cheese-app-vector-db-cli … cli.py --download --load --chunk_type recursive-split` (`deploy-setup-containers.yml:164-173`).
- Slide 37 draws the same shape with a Kubernetes ingress controller: one address, `/` to the frontend, `/api/` to the API.

### 3.6 Two sieves on one string: the commit message (slides 18, 20)
`on: push: branches: [ "main" ]` (`ci_cd_aws.yml:3-5`) starts a workflow run on every push to `main`. Two `contains()` filters then read the same string, `github.event.head_commit.message`:
- job level, `if: contains(github.event.head_commit.message, '/run-')` (`:9`): without `/run-`, the whole job is skipped;
- step level, `if: contains(github.event.head_commit.message, '/run-deploy-app')` (`:100`): only the last step, "Run Deployment Container", is gated.

| message | job (build, push three images) | deploy step | the server |
| --- | --- | --- | --- |
| `update readme` | skipped | — | unchanged |
| `fix typo /run-tests` | runs | skipped | unchanged, old tag; three new images in ECR |
| `your message /run-deploy-app` | runs | runs | redeployed |
| `/RUN-DEPLOY-APP` | runs | runs | redeployed: GitHub documents `contains()` on strings as case-insensitive |
| `\run-deploy-app` | skipped | — | unchanged: a backslash, so `/run-` is not in it |

`head_commit` is the last commit of the push: a push of three commits is judged by the last message only. The repository's own history shows the button in use: 33 of its 39 commit messages are `/run-deploy-app`, and one is `\run-deploy-app` (`laptop/50`). Slide 20's keyword, `/deploy-app`, belongs to the Google Cloud repo.

### 3.7 One timestamp, followed from build to running container (slides 18–19, 36)
- **By hand:** `date +%Y%m%d%H%M%S` (`deploy-docker-images.yml:12`) → registered as `tag` (`:13`) → image names `<registry>/cheese-app-…:{{ tag.stdout }}` (`:23`, `:36`, `:49`) → pushed (`:25-56`) → `echo {{ tag.stdout}} > .docker-tag` (`:58`), in your clone's `src/deployment` (mounted at `/app`). The committed `.docker-tag` holds `20241121211313`, the author's last tag.
- **By CI:** `echo $(date +%Y%m%d%H%M%S) > …/.docker-tag` and `DOCKER_TAG=…` appended to `$GITHUB_ENV`, a file GitHub reads between steps (`ci_cd_aws.yml:46-50`) → `docker tag …:latest …:${{ env.DOCKER_TAG }}` and `docker push` (`:57-70`) → the deploy step's `env:` (`:106`) → `-e DOCKER_TAG` into the toolbox (`:121`) and `--extra-vars "… docker_tag=$DOCKER_TAG"` (`:130`).
- **On the server:** `deploy-setup-containers.yml` copies `.docker-tag` over (`:67-71`); sets `docker_tag` from the `DOCKER_TAG` environment variable if it is set in the toolbox (`:101-104`), else from the file (`:106-114`); in CI the extra variable outranks both. It pulls the three images at that tag (`:120-129`) and recreates each container (`recreate: yes`, `:136`, `:153`, `:180`). From your laptop the toolbox never has `DOCKER_TAG` (`docker-shell.sh:43-47`), so a run by hand uses the file.
- **Swap, not roll.** Each container is stopped and replaced in place on one machine, with a short gap; L22's Kubernetes rolling update started new pods before the old ones went. "Release" in the lecture's loop is the moment the timestamped images land in ECR.

### 3.8 Same lecture, other cloud: the term map (slides 17–20)
| Slides (Google Cloud, `cheese-app-v4`) | This repo (AWS, `cheese-app-aws`) |
| --- | --- |
| Artifact Registry ("GCR") | ECR, three repositories created by hand |
| GKE cluster, Deployments, rolling update | one EC2 instance; `docker_container` with `recreate: yes` |
| Pulumi programs (`pulumi up`) | Ansible playbooks (`ansible-playbook`) |
| service-account JSON key; secret `GOOGLE_APPLICATION_CREDENTIALS` | IAM access key (CSV) and EC2 key pair; secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `AWS_SSH_KEY` |
| `google-github-actions/auth` | `aws-actions/configure-aws-credentials@v4` (`ci_cd_aws.yml:19`) |
| commit keyword `/deploy-app` | `/run-deploy-app` (and `/run-` for build-and-push only) |
| ingress / Google load balancer | one `nginx` container on port 80 |
| Vertex AI pipelines from CI | none in this repo; the AWS ML pipeline is L15's `ml-workflow-aws` (SageMaker) |
| Gemini, Vertex AI embeddings | Bedrock: Claude 3 / 3.5 Sonnet, Titan embeddings |

## 4. Step-by-step walkthrough

Steps follow the README order, with the workflow (Part F) placed before the README's last step, the delete. Commands in code spans are verbatim from the README unless marked *(extra)*.

**About the outputs below.** They are real, trimmed (`…` marks cut lines) from the 2026-11-08 captures (`laptop/NN` = `assets/terminal/laptop/NN-*.txt` in the video folder; `[exit N]` lines omitted). The recording machine had **no AWS account**: every command that talks to AWS ran exactly as the README writes it and stopped at its first real error, with obviously fake placeholder keys. Where your run should succeed, the guide says what to look for, labelled *expected*. Differences you will see:
- Your toolbox prompt shows a different container id on every start (`root@<container id>:/app#`).
- Every Ansible command in this toolbox first prints cryptography's `CryptographyDeprecationWarning: Python 3.8 is no longer supported …` pair; it is cut below.
- Versions may be newer than these "at the time of recording" numbers.

### Part 0: before you start

**Step 0. Clone, check the commit, make `secrets/`** *(extra)*.
- **Action:** `git ls-remote https://github.com/dlops-io/cheese-app-aws.git`, then `git clone https://github.com/dlops-io/cheese-app-aws.git` and `mkdir secrets` in the same parent folder.
- **Checkpoint** (captured, `laptop/01`, `03`):
  ```
  5950118b0ed97c12c799920846d3eb70b1a47385	HEAD
  5950118b0ed97c12c799920846d3eb70b1a47385	refs/heads/main
  ```
  ```
  5950118b0ed97c12c799920846d3eb70b1a47385 2024-11-21 18:27:08 -0500 cleanup
  * main
    remotes/origin/HEAD -> origin/main
    remotes/origin/main
  ```
  `src/` holds `api-service`, `deployment`, `frontend-react`, `frontend-simple` and `vector-db` (`laptop/04`).

### Part A: one-time setup in the AWS console (`README.md:7-72`)

**Step 1. "API's to enable"** (`README.md:7-13`). Nothing to do: the list is an HTML comment. Check Bedrock model access for the models in §2.

**Step 2. Policy `CheeseAppECRPolicy`** (`README.md:19-46`).
- **Action:** IAM › Policies › Create policy › JSON; paste `README.md:22-44`; "Review Policy"; name `CheeseAppECRPolicy`; Create Policy.
- **Extra check** (captured, `laptop/10`): `sed -n '23,43p' cheese-app-aws/README.md | python3 -m json.tool` echoes the policy back (`"Version": "2012-10-17"`, … `"sts:GetCallerIdentity"`, nine `ecr:` actions, … `"Resource": "*"`), exit 0.
- **Under the hood:** one identity check and nine ECR actions (log in, push, pull) on any resource. No `ecr:CreateRepository`: that is why Step 11 is manual.

**Step 3. IAM user** (`README.md:48-50`). Create `deployment-ac215-user`, attach `AmazonS3FullAccess`, `AmazonEC2FullAccess`, `AmazonBedrockFullAccess`, then also `CheeseAppECRPolicy`.

**Step 4. Access key** (`README.md:52-60`).
- **Action:** the user › Create access key › Third Party Service › confirm › Create › Download .csv; save as `secrets/deployment-ac215-user_accessKeys.csv`.
- **Why beside the clone:** a file outside the repository cannot be committed by accident.
- **Checkpoint** (captured with placeholder files, `laptop/12`):
  ```
  cheese-app-aws
  secrets
  total 8
  -rw------- 1 student student 1675 Nov  8 01:14 cheese-app-ac215-key-pair.pem
  -rw-r--r-- 1 student student  115 Nov  8 01:14 deployment-ac215-user_accessKeys.csv
  ```
  (The capture's key file kept the README's name; name yours `ac215_2024.pem`, Step 5.)

**Step 5. EC2 key pair** (`README.md:62-64`).
- **Action:** EC2 › Key Pairs › Create Key Pair; download the `.pem` into `secrets/`. Name it `ac215_2024` so it matches the code.
- **Extra check** (captured, `laptop/13`): the README and the code use different names:
  ```
  README.md:64:- AWS Console -> EC2 -> Key Pairs -> Create Key Pair -> Key Pair Name: cheese-app-ac215-key-pair -> …
  …
  src/deployment/inventory.yml:4:    ansible_ssh_private_key_file: "/root/.ssh/ac215_2024.pem" ## Github Actions
  src/deployment/inventory.yml:7:    # ansible_ssh_private_key_file: "{{ lookup('env', 'AWS_SSH_KEY') | default('/secrets/ac215_2024.pem', true) }}"
  src/deployment/inventory.yml:16:    aws_keypair_name: "ac215_2024"  ## Change this
  src/deployment/docker-shell.sh:27:export SSH_KEY_PATH="/secrets/ac215_2024.pem"  # Path inside container
  .github/workflows/ci_cd_aws.yml:81:          echo "${{ secrets.AWS_SSH_KEY }}" > ~/.ssh/ac215_2024.pem
  …
  ```
- **Extra:** `chmod 400` on the key (captured, `laptop/14`: `-r-------- … cheese-app-ac215-key-pair.pem`).

**Step 6. Deployment Setup** (`README.md:67-72`).
- **Action:** read `inventory.yml` (excerpt in §5). Ansible logs in as `ubuntu` (`:3`); line 4 points at the key for GitHub Actions, line 7 (commented) at the key on your laptop; lines 9-11 read your keys from the environment; lines 14-23 hold the region, `t2.large`, the key pair name, the Ubuntu image id and the disk names and sizes. Change line 16 if your key pair is not `ac215_2024`, and line 24 to your own random `NEXTAUTH_SECRET`. Line 30 (the host) comes in Step 14.

### Part B: start the toolbox (`README.md:74-77`)

**Step 7. Go to `src/deployment`** (`README.md:75`). `pwd` → `/home/student/cheese-app-aws/src/deployment`; `ls -a` lists the five playbooks, `inventory.yml`, `ansible.cfg`, `Dockerfile`, `docker-shell.sh`, `nginx-conf` and `.docker-tag` (`laptop/20`).

**Step 8. Fix the CSV path** (`README.md:76`).
- **As cloned** *(extra, captured, `laptop/21`)*: `bash docker-shell.sh` prints
  ```
  Error: AWS credentials file not found at ../../../../secrets/deployment-ac215-user_accessKeys.csv
  ```
  Four `../` from `~/cheese-app-aws/src/deployment` end at `/home/secrets`, one level too far.
- **Action:** edit `docker-shell.sh:10` to `CSV_FILE="../../../secrets/deployment-ac215-user_accessKeys.csv"`. Captured with `sed` as the editor (`laptop/22`): the line now reads that, and `ls -l ../../../secrets/deployment-ac215-user_accessKeys.csv` finds the 115-byte file.
- **Also** (not in the README): `SECRETS_DIR` on line 26 has the same four `../`, and line 17 hard-codes the author's account id. Fix both now (Step 9 shows what happens otherwise):
  ```
  CSV_FILE="../../../secrets/deployment-ac215-user_accessKeys.csv"
      export AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"
  export SECRETS_DIR=$(pwd)/../../../secrets/
  ```
  (`sed -n '10p;17p;26p' docker-shell.sh` after the edits, `laptop/30`; put your own 12 digits on line 17. `aws sts get-caller-identity --query Account --output text` prints them once your key works.)
- **Note:** run the script from `src/deployment`. The paths are relative to your current folder, so `bash src/deployment/docker-shell.sh` from the repo root does not find the file.

**Step 9. Start the toolbox: `sh docker-shell.sh`** (`README.md:77`).
- **As written, on Ubuntu** (captured, `laptop/23`):
  ```
  $ sh docker-shell.sh
  docker-shell.sh: 13: Syntax error: redirection unexpected
  ```
  exit 2. On Ubuntu and Debian `/bin/sh` is `dash` (`laptop/24`: `/bin/sh -> dash`), which has no here-string `<<<`; and `sh file` ignores the script's own first line `#!/bin/bash`. On macOS `/bin/sh` runs bash and the README line works. **Fix:** `bash docker-shell.sh`.
- **With the Dockerfile as committed** (captured, `laptop/25`): the build runs layers 1-8 (AWS CLI, Docker CE), then fails at the Helm key:
  ```
   => ERROR [ 9/15] RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | gpg --dearmo  1.4s
  …
  1.415 curl: (60) SSL certificate problem: unable to get local issuer certificate
  …
  1.417 gpg: no valid OpenPGP data found.
  …
  ERROR: failed to build: failed to solve: process "/bin/sh -c curl -fsSL … did not complete successfully: exit code: 2
  Unable to find image 'cheese-app-deployment:latest' locally
  docker: Error response from daemon: failed to resolve reference "docker.io/library/cheese-app-deployment:latest": docker.io/library/cheese-app-deployment:latest: not found
  ```
  exit 125. Two lessons: `Dockerfile:33` (`curl https://baltocdn.com/helm/signing.asc`) failed certificate verification on the recording machine, from inside the build and from the laptop itself (`laptop/26`, `curl: (60)`); and because `set -e` is commented out (`docker-shell.sh:4`), the script went on to `docker run` an image that was never built. Read the build output, not just the last line. Whether your machine trusts that certificate's root was not determined (§9); no playbook uses Helm, so the fix is to delete the two Helm lines and the word `helm` (`laptop/27`):
  ```
  -    curl https://baltocdn.com/helm/signing.asc | apt-key add -&& \
  -    echo "deb https://baltocdn.com/helm/stable/debian/ all main" | tee /etc/apt/sources.list.d/helm-stable-debian.list && \
       apt-get update && \
  -    apt-get install -y --no-install-recommends kubectl helm python3.9 python3-pip && \
  +    apt-get install -y --no-install-recommends kubectl python3.9 python3-pip && \
  ```
- **Without Helm, before the `SECRETS_DIR` fix** (captured, `laptop/28`): `Building 132.8s (20/20) FINISHED`, the prompt appears, and `/secrets` is **empty**:
  ```
  root@b0ed47a6a572:/app# ls -la /secrets; pwd; ls
  total 8
  drwxr-xr-x 2 root root 4096 Nov  8 01:17 .
  drwxr-xr-x 1 root root 4096 Nov  8 01:17 ..
  /app
  Dockerfile  Pipfile.lock  deploy-create-instance.yml  deploy-provision-instance.yml  deploy-setup-webserver.yml  …
  ```
  Docker mounted an empty folder that it created for the wrong path. The image is 2.52 GB on disk (`laptop/29`).
- **After all three edits** (captured, `laptop/31`; the rebuild re-runs only the `ADD . /app` layer, 17.1 s):
  ```
  root@912e38fd4195:/app# ls -la /secrets; env | grep ^AWS_ | cut -d= -f1 | sort
  total 16
  …
  -r-------- 1 1001 1001 1675 Nov  8 01:14 cheese-app-ac215-key-pair.pem
  -rw-r--r-- 1 1001 1001  115 Nov  8 01:14 deployment-ac215-user_accessKeys.csv
  AWS_ACCESS_KEY_ID
  AWS_ACCOUNT_ID
  …
  AWS_DEFAULT_REGION
  AWS_SECRET_ACCESS_KEY
  ```
  (The cut line is a variable of the recording machine only.) **Checkpoint:** you are at `root@<container id>:/app#`, with your CSV and `ac215_2024.pem` in `/secrets`.

**Step 10. Look around the toolbox** *(extra)*.
- **Versions** (captured, `laptop/32`):
  ```
  root@14b2d3549916:/app# aws --version
  aws-cli/2.39.6 Python/3.14.8 Linux/6.18.44-fc-v310 exe/x86_64.ubuntu.20
  root@14b2d3549916:/app# ansible --version
  …
  ansible [core 2.13.13]
    config file = /app/ansible.cfg
  …
    python version = 3.8.10 (default, Mar 18 2025, 20:04:55) [GCC 9.4.0]
  …
  root@14b2d3549916:/app# docker --version
  Docker version 28.1.1, build 4eba377
  root@14b2d3549916:/app# kubectl version --client 2>&1 | head -1
  Client Version: v1.28.15
  ```
  `pip3 show ansible` reports ansible 6.7.0, although `Dockerfile:37` says `ansible>=9.0.0`.
- **Where the pin went** (captured, `laptop/33`): unquoted, `>=9.0.0` is a shell redirect. `ls /` shows a file named `=9.0.0` next to `app`, `secrets` and the three app folders; it holds pip's log:
  ```
  Collecting ansible
    Downloading ansible-6.7.0-py3-none-any.whl (42.8 MB)
  …
  Successfully installed … ansible-6.7.0 ansible-core-2.13.13 … boto3-1.37.38 botocore-1.37.38 …
  ```
  Leave it for this lecture: the provision playbook's `args: warn: false` (`deploy-provision-instance.yml:56-57`) only works on this old ansible-core (§6 G1).
- **Who am I** (captured, `laptop/34`):
  ```
  root@46f4abf4a195:/app# aws sts get-caller-identity
  aws: [ERROR]: An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: The security token included in the request is invalid.
  ```
  *Expected* with your key: a JSON with your `UserId`, `Account` and the user's ARN.
- **Inventory and syntax** (captured, `laptop/35`, `36`):
  ```
  @all:
    |--@appserver:
    |  |--<EXTERNAL_IP>
    |--@ungrouped:
  ```
  ```
  playbook: deploy-create-instance.yml
  [WARNING]: Collection community.general does not support Ansible version 2.13.13
  [DEPRECATION WARNING]: community.general.docker_image has been deprecated. The redirection of community.general.docker_image to community.docker.docker_image
  will be removed in community.general 18.0.0. …
  playbook: deploy-docker-images.yml
  playbook: deploy-provision-instance.yml
  playbook: deploy-setup-containers.yml
  playbook: deploy-setup-webserver.yml
  ```
  All five pass. The two warnings come from `Dockerfile:56` installing the newest `community.general` (14.0.0) next to this old Ansible; they appear on every run that loads `docker_image`. `--list-tasks` (`laptop/37`) counts 9, 11, 38, 25 and 4 tasks for create-instance, docker-images, provision-instance, setup-containers and setup-webserver.
- **Under the hood:** the socket mount (`docker-shell.sh:36`) means the toolbox drives your laptop's Docker. A build from inside lands on your laptop's disk (§3.3).

### Part C: registry and images (`README.md:79-90`)

**Step 11. Three empty ECR repositories** (`README.md:79-85`). In `us-east-1`, private: `cheese-app-vector-db-cli`, `cheese-app-api-service`, `cheese-app-frontend-react`. Your policy can push to them but not create them.

**Step 12. Build and push** (`README.md:89`): `ansible-playbook deploy-docker-images.yml -i inventory.yml`.
- **Under the hood** (`deploy-docker-images.yml`): `hosts: localhost`. "Login to AWS ECR" pipes `aws ecr get-login-password` into `docker login` (`:8-9`); a timestamp from `date +%Y%m%d%H%M%S` is registered as `tag` (`:11-13`); each of the three images is built from the mounted folder with `platform: linux/amd64/v2` and pushed (`:18-56`); the tag is saved to `.docker-tag` (`:57-58`); the last task runs `docker system prune -a` (`:59-60`).
- **Captured** (`laptop/40`, first real error):
  ```
  PLAY [Build docker images and push them to ECR] ****…
  TASK [Login to AWS ECR] ****…
  fatal: [localhost]: FAILED! => {… "stderr_lines": ["", "aws: [ERROR]: An error occurred (UnrecognizedClientException) when calling the GetAuthorizationToken operation: The security token included in the request is invalid.", "Error: Cannot perform an interactive login from a non TTY device"], …}
  PLAY RECAP ****…
  localhost                  : ok=0    changed=0    unreachable=0    failed=1    skipped=0    rescued=0    ignored=0
  ```
  The second error follows from the first: `docker login` received an empty password. No image was built (`laptop/41`: only the toolbox and `ubuntu:20.04`).
- **Expected with your keys:** all 11 tasks run, three images are built on your laptop and pushed, `.docker-tag` holds your new tag, and the recap says `failed=0`. Building the TensorFlow API image takes a while.
- **The last task:** without `-f`, `docker system prune -a` asks `Are you sure you want to continue? [y/N]`, gets no answer and removes nothing (captured with stdin closed, `laptop/67`, exit 0). If it ever ran, it would prune your laptop's images, not the toolbox's.

### Part D: the machine (`README.md:92-103`)

**Step 13. Create the instance** (`README.md:94`): `ansible-playbook deploy-create-instance.yml -i inventory.yml --extra-vars cluster_state=present`.
- **Under the hood** (`deploy-create-instance.yml`, `hosts: localhost`, AWS API calls through boto3): security group `app_security_group` with 80, 443 and 22 open to `0.0.0.0/0` (`:7-24`); a 50 GB gp3 volume `cheese-app-demo-disk` in `us-east-1a` (`:27-37`); the `t2.large` instance `cheese-app-demo` with your key pair and two 100 GB gp2 volumes of its own (`:40-61`); wait for `running` (`:65-74`); wait for SSH (`:76-82`); attach the 50 GB volume at `/dev/sdf` (`:85-92`); a second SSH wait and `add_host` (`:102-108`). **From here, the meter runs.**
- **Captured** (`laptop/42`):
  ```
  TASK [Gathering Facts] ****…
  ok: [localhost]
  TASK [Create security group] ****…
  An exception occurred during task execution. … botocore.exceptions.ClientError: An error occurred (AuthFailure) when calling the DescribeSecurityGroups operation: AWS was not able to validate the provided access credentials
  …
  localhost                  : ok=1    changed=0    unreachable=0    failed=1    skipped=0    rescued=0    ignored=0
  ```
- **Expected with your keys:** the tasks report `changed`, the recap says `failed=0`, and the EC2 console lists `cheese-app-demo` as running.
- **Watch the attach task.** The instance already maps its own 100 GB volume at `/dev/sdf` (`:53-57`), and the attach asks for `/dev/sdf` again (§6 G15, not tested). If it fails, the server still works on its own second disk; delete the spare 50 GB volume when you clean up.
- **A kind note:** the heading says "in GCP"; it came over from the Google Cloud README.

**Step 14. Put the server's IP in the inventory** (`README.md:97`). Copy the instance's public IPv4 address from the EC2 console into `inventory.yml` line 30, under `appserver:` › `hosts:`. Captured with a placeholder host name (`laptop/43`):
```
  children:
    appserver:
      hosts:
        EXTERNAL_IP:
```
*(extra)* The same address from the CLI: `aws ec2 describe-instances --filters Name=tag:Name,Values=cheese-app-demo --query "Reservations[].Instances[].PublicIpAddress"`.

**Step 15. Switch the key line now** (`README.md:107-111`, listed later in the README). Comment out `inventory.yml:4` and uncomment `inventory.yml:7`. Captured (`laptop/45`):
```
    ansible_user: ubuntu
    # ansible_ssh_private_key_file: "/root/.ssh/ac215_2024.pem" ## Github Actions

    ## from local mac
    ansible_ssh_private_key_file: "{{ lookup('env', 'AWS_SSH_KEY') | default('/secrets/ac215_2024.pem', true) }}"
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
```
Line 7 reads `/secrets/ac215_2024.pem` (`AWS_SSH_KEY` is not set in your toolbox), so the file in `~/secrets` must have that exact name. With line 4 active, Ansible looks for `/root/.ssh/ac215_2024.pem`, which your toolbox does not have.

**Step 16. Provision** (`README.md:102`): `ansible-playbook deploy-provision-instance.yml -i inventory.yml`.
- **Under the hood:** `hosts: appserver`, over SSH as `ubuntu`, `become: true`. 38 tasks: clean out old Docker apt sources, add Docker's key and repository (the release code name from `lsb_release`, or `focal` for any Ubuntu release not in its list, `:18-28`), install Docker CE; format `/dev/xvdf` if it has no filesystem and mount it at `/mnt/disk-1` (`:159-176`); disable unattended upgrades; install Python packages; install AWS CLI v2; `aws configure set …` with your keys (`:288-292`): your access key now has a copy on the server; start Docker.
- **Captured** (`laptop/44`; the host is the placeholder from Step 14):
  ```
  PLAY [Configure app server instance] ****…
  TASK [Gathering Facts] ****…
  fatal: [EXTERNAL_IP]: UNREACHABLE! => {"changed": false, "msg": "Failed to connect to the host via ssh: ssh: Could not resolve hostname external_ip: Name or service not known", "unreachable": true}
  …
  EXTERNAL_IP                : ok=0    changed=0    unreachable=1    failed=0    skipped=0    rescued=0    ignored=0
  ```
- **Expected on a real server:** "Gathering Facts" `ok`, then a long run of `ok`/`changed`, ending `failed=0 … unreachable=0`.
- **If it fails:** `no such identity: /root/.ssh/ac215_2024.pem` → you skipped Step 15; `UNPROTECTED PRIVATE KEY FILE!` → `chmod 400` the key (§6 G7); `UNREACHABLE` with a timeout → wrong IP, or the instance is not running.

### Part E: containers and web server (`README.md:105-143`)

**Step 17. Two fixes before the containers** *(extra)*.
- **Pin Chroma.** `deploy-setup-containers.yml:151` starts `chromadb/chroma:latest`. Captured with the image as pulled on 2026-11-08 (`laptop/60`):
  ```
  "1.0.0"
  {"error":"Unimplemented","message":"The v1 API is deprecated. Please use /v2 apis"} HTTP 410
  {"nanosecond heartbeat":1794100762858126382} HTTP 200
  ```
  (version, `/api/v1/heartbeat`, `/api/v2/heartbeat`). The clients pin `chromadb` 0.5.18 (`src/vector-db/Pipfile:14`, `src/api-service/Pipfile:19`) and speak `/api/v1`; `chromadb/chroma:0.5.18`, the image `src/vector-db/docker-compose.yml:25` uses, answers `"0.5.18"` and `/api/v1/heartbeat` → `HTTP 200` (`laptop/61`). Edit line 151 to `image: "chromadb/chroma:0.5.18"`.
- **The loader's `-it`.** "Load Vector DB" runs `docker run --rm -it …` in a `shell` task (`:164-173`). Docker refuses `-t` when stdin is not a terminal (captured, `laptop/66`: `cannot attach stdin to a TTY-enabled container because stdin is not a terminal`, exit 1). Whether Ansible's SSH session gives this task a terminal was not tested; if the task fails with that message, drop `-it`.

**Step 18. Set up the containers** (`README.md:116`): `ansible-playbook deploy-setup-containers.yml -i inventory.yml`.
- **Under the hood** (`hosts: appserver`, 25 tasks): writes your keys to `/srv/secrets/aws-credentials`, mode 0600 (`:36-44`); creates the network `appnetwork` (`:47-53`) and `/mnt/disk-1/persistent`, `/mnt/disk-1/chromadb` (`:56-65`); copies `.docker-tag` (`:67-71`); logs the server in to ECR; picks the tag (`:101-114`, §3.7); pulls the three images (`:120-129`); starts `frontend` on 3000 with `NEXTAUTH_SECRET`/`NEXTAUTH_URL` (`:131-145`) and `vector-db` on 8000 (`:148-162`); runs the loader once to download pre-computed chunks and embeddings and load them into collection `recursive-split-collection` (`:164-173`); starts `api-service` on 9000 with your keys, `CHROMADB_HOST`/`PORT` and two volumes (`:175-194`); prints network info.
- **Captured** (`laptop/46`): the same `UNREACHABLE! … Could not resolve hostname external_ip` at "Gathering Facts", `unreachable=1`.
- **Expected on a real server:** `failed=0`; the "Debug final docker tag" task prints `Using docker tag: <your tag>`.

**Step 19. Look around on the server** (`README.md:120-132`).
- **Action:** the README says "from the GCP console"; on AWS, `ssh -i ~/secrets/ac215_2024.pem ubuntu@<EXTERNAL_IP>` *(extra)* or EC2 Instance Connect in the console. Then `sudo docker container ls`, `sudo docker container logs api-service -f`, `sudo docker container logs frontend -f`, `sudo docker container logs nginx -f`, `sudo docker exec -it api-service /bin/bash`, `sudo docker exec -it nginx /bin/bash`. The two `nginx` lines work only after Step 21.
- **What to look for:** `frontend`, `vector-db` and `api-service` `Up`, each IMAGE ending in your tag. A local stand-in for the shape of the listing (captured on the laptop without `sudo`, after Step 20's demo; the two Python stand-ins are not the app; `laptop/63`):
  ```
  NAMES         IMAGE                       PORTS
  nginx         nginx:stable                0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
  frontend      python:3.12-slim-bookworm
  api-service   python:3.12-slim-bookworm
  ```

**Step 20. "Configure Nginx file"** (`README.md:136-137`). The file exists: `src/deployment/nginx-conf/nginx/nginx.conf`. One `server` on `listen 80` (`:25-27`); `location ^~ /api/` → `proxy_pass http://api-service:9000/;` (`:35-37`); `location /` → `proxy_pass http://frontend:3000;` (`:47-48`).
- **Predict:** the browser asks for `/api/newsletters`. Which path does `api-service` receive?
- **Captured** *(extra, `laptop/62`)*: the repo's `nginx.conf`, run as `deploy-setup-webserver.yml` runs it (`nginx:stable` on `appnetwork`, ports 80/443), in front of two stand-ins named `api-service` and `frontend` that answer with the path they receive:
  ```
  api-service received /newsletters
  api-service received /chat/llm
  frontend received /
  frontend received /chat
  HTTP 301
  ```
  (for `/api/newsletters`, `/api/chat/llm`, `/`, `/chat`, and `/api` without its last slash). The trailing `/` in `proxy_pass` replaces the matched `/api/`; FastAPI mounts its routers without the prefix (`api/service.py:25-30`), so they fit. nginx's log shows the five requests (`laptop/64`); the image reports `nginx version: nginx/1.30.6` (`laptop/65`).

**Step 21. Set up the web server** (`README.md:141`): `ansible-playbook deploy-setup-webserver.yml -i inventory.yml`.
- **Under the hood** (4 tasks): ensure `appnetwork`; copy `./nginx-conf/nginx` to `/conf`; start `nginx:stable` with `recreate: yes`, ports 80 and 443, `/conf/nginx/nginx.conf` mounted as `/etc/nginx/nginx.conf` (`:23-35`); restart it.
- **Captured** (`laptop/47`): `UNREACHABLE!` at "Gathering Facts", like Step 16.

**Step 22. Open the site** (`README.md:143`): `http://<External IP>/`. *Expected:* the cheese app's front page; its chat calls go to `/api/…` on the same address. Port 443 is open and forwarded to nginx, but nginx has no `listen 443` server: there is no HTTPS (§6 G19). If chat answers with HTTP 500, see §6 G10–G12.

### Part F: CI/CD with GitHub Actions (not in the README; `.github/workflows/ci_cd_aws.yml`)

**Step 23. Your own repository** *(extra)*.
- **Action:** create an empty private repository; `git remote set-url origin https://github.com/<your-user>/cheese-app-aws.git`; `git push -u origin main`. A fork also works (then enable workflows in its Actions tab).
- **Checkpoint:** the push starts no job: the last message is `cleanup`, with no `/run-` (§3.6).

**Step 24. Four repository secrets** *(extra)*. Settings › Secrets and variables › Actions › New repository secret: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `AWS_SSH_KEY` (the whole `.pem` text). The names come from `ci_cd_aws.yml:21-22`, `:33`, `:81` and `:102-108`; the README never lists them. Your access key now has a copy on GitHub, and your SSH key a second one.

**Step 25. Read what the runner does, then push the keyword.**
- **The steps** (`ci_cd_aws.yml`): four `echo` lines (`:12-15`) → checkout (`:16-17`) → `aws-actions/configure-aws-credentials@v4` with two secrets and `us-east-1` (`:18-23`) → `aws sts get-caller-identity`, `aws s3 ls` (`:25-28`) → ECR login with `${{ secrets.AWS_ACCOUNT_ID }}` (`:30-33`) → `ls` (`:38-40`) → **build the toolbox** from the committed Dockerfile (`:41-44`) → a timestamp into `.docker-tag` and `$GITHUB_ENV` (`:46-50`) → `docker build`, `docker tag`, `docker push` for the frontend, the vector-db CLI and the API (`:52-70`) → write `~/.ssh/config` and `~/.ssh/ac215_2024.pem` from `AWS_SSH_KEY`, `chmod 600`, copy both into `src/deployment/secrets/` on the runner (`:72-90`) → list them (`:92-97`) → **only with `/run-deploy-app`:** run the toolbox (`:99-131`).
- **The tag step, by hand** *(extra, captured, `laptop/51`)*:
  ```
  DOCKER_TAG=20261108011909
  ```
- **The SSH step, by hand** *(extra, captured, `laptop/52`)*: both listings show `ac215_2024.pem` (1675 bytes) and `config` (65 bytes), `-rw-------`.
- **The deploy step, by hand** *(extra, captured with the placeholder key, `laptop/53`)*:
  ```
  Deploying with tag: 20261108011909
  total 16
  drwx------ 2 root root 4096 Nov  8 01:19 .
  drwx------ 1 root root 4096 Nov  8 01:19 ..
  -rw------- 1 root root 1675 Nov  8 01:19 ac215_2024.pem
  -rw------- 1 root root   65 Nov  8 01:19 config

  aws: [ERROR]: An error occurred (UnrecognizedClientException) when calling the GetAuthorizationToken operation: The security token included in the request is invalid.
  Error: Cannot perform an interactive login from a non TTY device
  ```
  exit 1: the `&&` chain stops at the ECR login, so neither playbook runs. With your secrets, the chain goes on to `deploy-setup-containers.yml … --extra-vars "… docker_tag=$DOCKER_TAG" -vv`, then `deploy-setup-webserver.yml`.
- **Commit four things first:** `inventory.yml:30` = your server's IP (CI deploys to whatever is committed); `inventory.yml:4` active and `:7` commented again (undo Step 15: the runner puts the key in `/root/.ssh`); the Helm fix (the runner builds the toolbox from the committed Dockerfile; whether a GitHub runner hits the same certificate error was not tested); the Chroma pin.
- **Action:** `git add .`, `git commit -m "your message /run-deploy-app"`, `git push` (slide 20's three commands, with `git add .` and this repo's keyword). `git add .` also commits your account id (`docker-shell.sh:17`) and your `NEXTAUTH_SECRET` (`inventory.yml:24`): keep the repository private. Never commit the CSV or the `.pem`.
- **Checkpoint (expected):** the Actions tab shows job `Explore-GitHub-Actions` green; "Run Deployment Container" ran. Reload `http://<EXTERNAL_IP>/`; on the server, `sudo docker container ls` shows the new tag in the IMAGE column. Green means every step that ran exited 0, not that the site works.

**Step 26. Delivery or deployment?** (slides 11–12) By the lecture's definitions, typing `/run-deploy-app` is a person pressing release: continuous delivery, with nothing tested first. Deploying every merge to `main`, behind L21's tests, would make it continuous deployment (§8 Ponder 4, D2).

### Part G: teardown (`README.md:145-148`, and what is missing)

**Step 27. The README's delete** (`README.md:147`): `ansible-playbook deploy-create-instance.yml -i inventory.yml --extra-vars cluster_state=absent`.
- **Predict:** which of the first three tasks run? (Look at their `when:` lines, `deploy-create-instance.yml:24`, `:37`, and the instance task at `:40-61`.)
- **Captured** (`laptop/48`):
  ```
  TASK [Create security group] ****…
  skipping: [localhost]
  TASK [Create EBS volume] ****…
  skipping: [localhost]
  TASK [Create EC2 instance] ****…
  fatal: [localhost]: FAILED! => {"msg": "The task includes an option with an undefined variable. The error was: 'dict object' has no attribute 'group_id'\n\nThe error appears to be in '/app/deploy-create-instance.yml': line 40, column 7, …"}
  …
  localhost                  : ok=1    changed=0    unreachable=0    failed=1    skipped=2    rescued=0    ignored=0
  ```
  The instance task has no `when:` and needs `security_group.group_id` (`:45`), which the skipped task never set. It fails before any AWS call. Even past it, "Remove EBS volume" needs `ebs_volume.volume_id`, which only a create run registers (`:95-100`), and no task terminates the instance. **Nothing is deleted.**

**Step 28. Clean up by hand** *(extra)*. The list in At a glance ("Tear down, exactly"). Cost is one of the challenges the lecture names for CD (slide 15): this server bills until you finish the list.

## 5. Code tour

### Key files
| Path | Lines | Role |
| --- | --- | --- |
| `README.md` | 148 | the deployment steps |
| `.github/workflows/ci_cd_aws.yml` | 131 | the CI/CD workflow (not in the README) |
| `src/deployment/Dockerfile` | 65 | the toolbox image |
| `src/deployment/docker-shell.sh` | 49 | start the toolbox on a laptop |
| `src/deployment/inventory.yml` | 30 | hosts and variables |
| `src/deployment/deploy-docker-images.yml` | 60 | build and push |
| `src/deployment/deploy-create-instance.yml` | 108 | security group, EBS volume, EC2 instance |
| `src/deployment/deploy-provision-instance.yml` | 297 | Docker, disk, AWS CLI on the server |
| `src/deployment/deploy-setup-containers.yml` | 208 | the app's containers |
| `src/deployment/deploy-setup-webserver.yml` | 38 | nginx |
| `src/deployment/nginx-conf/nginx/nginx.conf` | 57 | the routes |
| `src/deployment/ansible.cfg` | 2 | `host_key_checking = False` |
| `src/deployment/docker-entrypoint.sh`, `docker-entrypoint_working.sh` | — | unused (`ENTRYPOINT` commented out) |

### Excerpt 1: the two sieves (`ci_cd_aws.yml:3-9`, `:99-100`)
```yaml
on:
  push:
    branches: [ "main" ]

jobs:
  Explore-GitHub-Actions:
    if: contains(github.event.head_commit.message, '/run-')
```
```yaml
      - name: Run Deployment Container
        if: contains(github.event.head_commit.message, '/run-deploy-app')
```

### Excerpt 2: logging in to AWS in CI (`ci_cd_aws.yml:18-33`)
```yaml
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1  
          
      - name: Verify AWS Credentials
        run: |
          aws sts get-caller-identity
          aws s3 ls

      - name: Login to Amazon ECR
        id: login-ecr
        run: |
          aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com
```

### Excerpt 3: one image, one timestamp (`ci_cd_aws.yml:46-58`)
```yaml
      - name: Generate Docker tag
        run: |
          echo $(date +%Y%m%d%H%M%S) > ${{ github.workspace }}/src/deployment/.docker-tag
          export DOCKER_TAG=$(cat ${{ github.workspace }}/src/deployment/.docker-tag)
          echo "DOCKER_TAG=$DOCKER_TAG" >> $GITHUB_ENV
      
      - name: Build and Push Docker Images
        run: |
          # Frontend React
          cd ${{ github.workspace }}/src/frontend-react/
          docker build -t cheese-app-frontend-react -f Dockerfile .
          docker tag cheese-app-frontend-react:latest ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/cheese-app-frontend-react:${{ env.DOCKER_TAG }}
          docker push ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/cheese-app-frontend-react:${{ env.DOCKER_TAG }}
```
(`:60-70` repeat this for `vector-db` and `api-service`.)

### Excerpt 4: running the toolbox in CI (`ci_cd_aws.yml:113-131`)
```yaml
          docker run --rm --name cheese-app-deployment \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v ${{ github.workspace }}/src/deployment:/deployment \
            -v ${{ github.workspace }}/src/deployment/secrets:/root/.ssh \
            -e AWS_ACCESS_KEY_ID \
            -e AWS_SECRET_ACCESS_KEY \
            -e AWS_DEFAULT_REGION \
            -e AWS_ACCOUNT_ID \
            -e DOCKER_TAG \
            cheese-app-deployment \
            /bin/bash -c "cd /deployment && \
```
…then (`:124-131`) `chown`/`chmod` of `/root/.ssh`, `ls -la /root/.ssh`, the ECR login, `ANSIBLE_STDOUT_CALLBACK=debug ansible-playbook deploy-setup-containers.yml -i inventory.yml --extra-vars "… docker_tag=$DOCKER_TAG" -vv`, and `ansible-playbook deploy-setup-webserver.yml -i inventory.yml`. `-e NAME` without a value copies the variable from the step's `env:` (`:101-108`).

### Excerpt 5: reading the CSV (`docker-shell.sh:9-21`, account id masked)
```bash
# Read AWS credentials from CSV file
CSV_FILE="../../../../secrets/deployment-ac215-user_accessKeys.csv"
if [ -f "$CSV_FILE" ]; then
    # Skip the header line and read the second line, removing any quotes and whitespace
    IFS=',' read -r AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY <<< "$(sed -n '2p' "$CSV_FILE" | tr -d '"' | tr -d ' ')"
    export AWS_ACCESS_KEY_ID=$(echo "$AWS_ACCESS_KEY_ID" | tr -d '\r')
    export AWS_SECRET_ACCESS_KEY=$(echo "$AWS_SECRET_ACCESS_KEY" | tr -d '\r')
    export AWS_DEFAULT_REGION="us-east-1"
    export AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"
else
    echo "Error: AWS credentials file not found at $CSV_FILE"
    exit 1
fi
```
`<<<` (a here-string) is a bash feature: this is the line `dash` rejects (§6 G2). The `tr -d '\r'` lines strip Windows line endings from the CSV.

### Excerpt 6: the toolbox run on a laptop (`docker-shell.sh:32-48`)
```bash
docker build -t $IMAGE_NAME --platform=linux/amd64 -f Dockerfile .

# Run the container
docker run --rm --name $IMAGE_NAME -ti \
-v /var/run/docker.sock:/var/run/docker.sock \
-v "$BASE_DIR":/app \
-v "$SECRETS_DIR":/secrets \
-v "$HOME/.ssh":/home/app/.ssh \
-v "$BASE_DIR/../api-service":/api-service \
-v "$BASE_DIR/../frontend-react":/frontend-react \
-v "$BASE_DIR/../vector-db":/vector-db \
-e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
-e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
-e AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION \
-e AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID \
-e SSH_KEY_PATH=$SSH_KEY_PATH \
$IMAGE_NAME
```
The container runs as root (the Dockerfile creates user `app`, `:39-42`, but never switches to it), so `/home/app/.ssh` is not root's `~/.ssh`. `SSH_KEY_PATH` is passed in but nothing reads it; the inventory's laptop line uses `AWS_SSH_KEY` or falls back to `/secrets/ac215_2024.pem` (`inventory.yml:7`).

### Excerpt 7: the inventory (`inventory.yml:1-30`, masked)
```yaml
all:
  vars:
    ansible_user: ubuntu
    ansible_ssh_private_key_file: "/root/.ssh/ac215_2024.pem" ## Github Actions

    ## from local mac
    # ansible_ssh_private_key_file: "{{ lookup('env', 'AWS_SSH_KEY') | default('/secrets/ac215_2024.pem', true) }}"   
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
    aws_access_key: "{{ lookup('env','AWS_ACCESS_KEY_ID') }}"
    aws_secret_key: "{{ lookup('env','AWS_SECRET_ACCESS_KEY') }}"
    aws_account_id: "{{ lookup('env','AWS_ACCOUNT_ID') }}"
    aws_application_credentials: "/secrets/deployment-ac215-user_accessKeys.csv"

    aws_region: "us-east-1"
    aws_instance_type: "t2.large"
    aws_keypair_name: "ac215_2024"  ## Change this 
    aws_ami_id: "ami-0e86e20dae9224db8"  
    docker_network_name: "appnetwork"
    machine_instance_name: "cheese-app-demo"
    machine_disk_size: 100
    persistent_disk_name: "cheese-app-demo-disk"
    persistent_disk_size: 50
    aws_instance_name: "cheese-app-demo"
    nextauth_secret: "<nextauth-secret>"
    nextauth_url: "http://{{ inventory_hostname }}"

  children:
    appserver:
      hosts:
        <EXTERNAL_IP>:
```
Unused at this commit: `aws_application_credentials`, `machine_instance_name`, `nextauth_url` (the container gets `NEXTAUTH_URL` directly, `deploy-setup-containers.yml:145`).

### Excerpt 8: build and push with Ansible (`deploy-docker-images.yml:1-30`)
```yaml
- name: "Build docker images and push them to ECR"
  hosts: localhost
  gather_facts: false
  vars:
    aws_account_id: "{{ lookup('env','AWS_ACCOUNT_ID') }}"
    ecr_registry: "{{ aws_account_id }}.dkr.ecr.{{ aws_region }}.amazonaws.com"
  tasks:
  - name: Login to AWS ECR
    shell: "aws ecr get-login-password --region {{ aws_region }} | docker login --username AWS --password-stdin {{ ecr_registry }}"

  - name: "Get timestamp for docker tag"
    shell: "(date +%Y%m%d%H%M%S)"
    register: tag
  - name: Print tag
    debug:
      var: tag

  - name: Build frontend container image
    community.general.docker_image:
      build:
        path: /frontend-react
        platform: linux/amd64/v2
      name: "{{ ecr_registry }}/cheese-app-frontend-react:{{ tag.stdout}}"
      source: build
  - name: Push frontend image to ECR
    community.general.docker_image:
      name: "{{ ecr_registry }}/cheese-app-frontend-react:{{ tag.stdout}}"
      repository: "{{ ecr_registry }}/cheese-app-frontend-react:{{ tag.stdout}}"
      push: yes
      source: local
```
`community.general.docker_image` is a redirect to `community.docker.docker_image`; with today's collections it prints the deprecation warning shown in §4 Step 10.

### Excerpt 9: create, and the teardown that cannot work (`deploy-create-instance.yml:39-46`, `:94-100`)
```yaml
    # # Replace GCP instance with EC2 instance
    - name: Create EC2 instance
      amazon.aws.ec2_instance:
        instance_type: "{{ aws_instance_type }}"
        image_id: "{{ aws_ami_id }}"
        region: "{{ aws_region }}"
        security_group: "{{ security_group.group_id }}"
        key_name: "{{ aws_keypair_name }}"
```
```yaml
    # Replace GCP disk removal with EBS volume removal
    - name: Remove EBS volume
      ec2_vol:
        region: "{{ aws_region }}"
        id: "{{ ebs_volume.volume_id }}"
        state: absent
      when: cluster_state == "absent"
```
The create task has no `when:` and no `state:`; nothing in the file terminates the instance.

### Excerpt 10: pick the tag, run a container (`deploy-setup-containers.yml:101-114`, `:131-145`)
```yaml
    - name: Set docker tag from environment if available
      set_fact:
        docker_tag: "{{ lookup('env', 'DOCKER_TAG') }}"
      when: lookup('env', 'DOCKER_TAG') != ""

    - name: Set docker tag from file if environment variable is not set
      block:
        - name: Read docker tag from file
          shell: "cat .docker-tag"
          register: tag_file
        - name: Set docker tag from file
          set_fact:
            docker_tag: "{{ tag_file.stdout }}"
      when: lookup('env', 'DOCKER_TAG') == ""
```
```yaml
    - name: Create frontend container
      docker_container:
        name: "frontend"
        image: "{{ aws_account_id }}.dkr.ecr.{{ aws_region }}.amazonaws.com/cheese-app-frontend-react:{{ docker_tag }}"
        state: started
        recreate: yes
        pull: yes
        restart: yes
        published_ports:
          - 3000:3000
        networks:
          - name: "{{docker_network_name}}"
        env:
          NEXTAUTH_SECRET: "{{ nextauth_secret }}"  
          NEXTAUTH_URL: "http://{{ inventory_hostname }}"  
```
`lookup('env', …)` reads the environment of the controller (the toolbox), not of the server. `cat .docker-tag` runs on the server, in the SSH user's home, where `:67-71` copied the file.

### Excerpt 11: the loader run (`deploy-setup-containers.yml:164-173`)
```yaml
    - name: Load Vector DB
      shell: docker run --rm -it 
        -e AWS_ACCESS_KEY_ID="{{ aws_access_key }}" 
        -e AWS_SECRET_ACCESS_KEY="{{ aws_secret_key }}" 
        -e AWS_DEFAULT_REGION="{{ aws_region }}"
        -e CHROMADB_HOST="vector-db" 
        -e CHROMADB_PORT="8000" 
        --network "{{docker_network_name}}" 
        "{{ aws_account_id }}.dkr.ecr.{{ aws_region }}.amazonaws.com/cheese-app-vector-db-cli:{{ docker_tag }}" 
        cli.py --download --load --chunk_type recursive-split
```

### Excerpt 12: the routes (`nginx.conf:34-37`, `:46-48`)
```nginx
		# API - Make this location block handle all /api paths
		location ^~ /api/ {
			# Remove the rewrite since we want to preserve the full path after /api/
			proxy_pass http://api-service:9000/;
```
```nginx
		# Frontend
		location / {
			proxy_pass http://frontend:3000;
```
Each block also sets `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Real-IP`, `Host`, `proxy_redirect off` and `proxy_buffering off`. Despite the comment on line 36, the trailing `/` strips the `/api/` prefix (§4 Step 20).

### Excerpt 13: the toolbox's install line (`Dockerfile:30-37`)
```dockerfile
# Kubernetes & Ansible
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg && \
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list  && \
    curl https://baltocdn.com/helm/signing.asc | apt-key add -&& \
    echo "deb https://baltocdn.com/helm/stable/debian/ all main" | tee /etc/apt/sources.list.d/helm-stable-debian.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends kubectl helm python3.9 python3-pip && \
    pip install ansible>=9.0.0 openshift docker apache-libcloud boto3 botocore pipenv
```
Two of this lecture's surprises live here: the Helm repository (§6 G3) and the unquoted `>=` (§6 G1).

## 6. Gotchas and common errors

Captured ones first; *(reasoned, not run)* marks the rest.

- **G1. `pip install ansible>=9.0.0` is a shell redirect, not a version pin** (`Dockerfile:37`). Unquoted, `>=9.0.0` sends pip's output to a file named `=9.0.0` in `/` and installs whatever pip picks: ansible 6.7.0 / ansible-core 2.13.13 on Python 3.8.10 (captured, `laptop/32`, `33`). Quoting it (`"ansible>=9.0.0"`) would stop the build on this base image (Ansible 9 needs a newer Python), and a newer base image brings an ansible-core that rejects `args: warn: false` in the provision playbook (`deploy-provision-instance.yml:56-57`). Leave it as it is for this lecture; §8 C7 walks the trade-off.
- **G2. `sh docker-shell.sh` fails on Linux** (`README.md:77`, `docker-shell.sh:13`): `docker-shell.sh: 13: Syntax error: redirection unexpected`, exit 2 (captured, `laptop/23`). `/bin/sh` is `dash` on Ubuntu and Debian, without `<<<`. Fix: `bash docker-shell.sh`.
- **G3. The toolbox did not build as committed** (`Dockerfile:33-34`): `curl: (60) SSL certificate problem: unable to get local issuer certificate`, `gpg: no valid OpenPGP data found.`, exit code 2 at step 9 of 15 (captured, `laptop/25`; the same `curl: (60)` from the laptop itself, `laptop/26`). Helm's repository has also moved (its new key URL answers `302`, `laptop/26`). No playbook uses Helm: delete the two Helm lines and the word `helm` (`laptop/27`). The same Dockerfile is built by CI (`ci_cd_aws.yml:41-44`), so commit the fix.
- **G4. No `set -e` in `docker-shell.sh`** (`:4` is commented). After the failed build it runs `docker run` on an image that does not exist: `Unable to find image 'cheese-app-deployment:latest' locally` … `not found`, exit 125 (captured, `laptop/25`). Read the build output, not the last line.
- **G5. The README's CSV path and the script's disagree, and the README misses two lines.** `README.md:76` has three `../`, `docker-shell.sh:10` four: as cloned, `Error: AWS credentials file not found` (captured, `laptop/21`). `SECRETS_DIR` (`:26`) has the same four `../`: the toolbox starts with an **empty** `/secrets` (captured, `laptop/28`). The account id is hard-coded (`:17`): leave it, and every ECR login and image name points at someone else's registry (*reasoned, not run*).
- **G6. Three names for one key pair.** README `cheese-app-ac215-key-pair` (`:64`), inventory `aws_keypair_name: "ac215_2024"` (`inventory.yml:16`), key file `ac215_2024.pem` (`inventory.yml:4`, `:7`; `ci_cd_aws.yml:81`, `:85`, `:90`, `:107`, `:126`) (captured grep, `laptop/13`). `key_name` must match the key pair's name in EC2, and the file must be where the inventory looks. Easiest: name the key pair `ac215_2024`.
- **G7. SSH refuses a key others can read:** `WARNING: UNPROTECTED PRIVATE KEY FILE!` *(standard OpenSSH behaviour, not run here)*. `chmod 400` the `.pem` (captured, `laptop/14`). CI does this for its own copy (`ci_cd_aws.yml:84-85`, `:124-127`).
- **G8. The key line is a manual toggle, and the README places it late** (`README.md:107-111`, after the provision step). The committed `inventory.yml:4` is for GitHub Actions (`/root/.ssh/…`); a laptop run needs line 7 (`/secrets/…`) from the provision step on. Switch back before pushing, or CI looks in `/secrets`, which it does not have.
- **G9. The teardown does not tear anything down** (`README.md:147`). With `cluster_state=absent`, the security-group and volume tasks are skipped, and the un-gated "Create EC2 instance" fails on `security_group.group_id`: `'dict object' has no attribute 'group_id'`, `ok=1 … failed=1 skipped=2`, before any AWS call (captured, `laptop/48`). Past that, "Remove EBS volume" needs a volume id only a create run registers, and no task terminates the instance *(reasoned)*. Delete by hand; §8 B5 rewrites the playbook.
- **G10. `chromadb/chroma:latest` on the server vs `chromadb` 0.5.18 in the clients** (`deploy-setup-containers.yml:151`; `src/vector-db/Pipfile:14`, `src/api-service/Pipfile:19`). On 2026-11-08 `latest` reports `"1.0.0"` and answers `/api/v1/heartbeat` with `HTTP 410` (`The v1 API is deprecated. Please use /v2 apis`), while `0.5.18` answers `HTTP 200` (captured, `laptop/60`, `61`). Expect the loader to fail and the API, which connects to Chroma at import time (`llm_rag_utils.py:73-77`), not to start *(reasoned, not run)*. Fix: `chromadb/chroma:0.5.18`, as `src/vector-db/docker-compose.yml:25` already does.
- **G11. The downloaded embeddings may not match the AWS embedding model** *(reasoned, not run)*. `cli.py --download` fetches `cheese-books-embeddings.zip` from the `dlops-io/datasets` v4.0 release (`src/vector-db/cli.py:479`); an inspection of the zip on 2026-11-08 found 256-number vectors in it, while the API embeds questions with Titan `amazon.titan-embed-text-v1` (`llm_rag_utils.py:21`), which `cli.py:36` says is 1536-dimensional (`:41` keeps the old `# EMBEDDING_DIMENSION = 256`). A 1536-number query against a 256-dimension collection would be rejected: the RAG chat route would fail; the plain LLM chat does not use Chroma.
- **G12. App bugs in `llm_rag_utils.py`** *(read, not run)*: it uses `json` without importing it, so a RAG chat request would end as HTTP 500. Not a deployment problem; worth knowing when you debug the chat.
- **G13. `docker run -it` inside an Ansible `shell` task** (`deploy-setup-containers.yml:165`). Docker refuses `-t` without a terminal: `cannot attach stdin to a TTY-enabled container because stdin is not a terminal`, exit 1 (captured locally, `laptop/66`). Whether Ansible's SSH session provides a terminal here was not tested. If the task fails, drop `-it`.
- **G14. `docker system prune -a` as the build playbook's last task** (`deploy-docker-images.yml:59-60`). Without `-f` it prompts, gets no answer and removes nothing (captured, `laptop/67`). If it ever ran, it would prune your laptop's images.
- **G15. Two disks want `/dev/sdf`** *(reasoned, not run)*. The instance maps a 100 GB volume at `/dev/sdf` (`deploy-create-instance.yml:53-57`), then "Attach EBS volume" asks for `/dev/sdf` again (`:85-92`). Expect the attach to fail and the 50 GB volume to stay detached and billed; the provision playbook then formats and mounts the instance's own `/dev/xvdf`. The 50 GB volume is also pinned to zone `us-east-1a` (`:30`), while the instance may launch in another zone.
- **G16. "Wait for SSH" runs from the toolbox** (`:76-82`, `:102-104`). If your network blocks outbound port 22, the play times out after 120 s although the instance is fine *(reasoned)*.
- **G17. A `/run-` commit without `deploy-app` still builds and pushes** (`ci_cd_aws.yml:9` vs `:100`). Three more images in ECR, the server on the old tag.
- **G18. CI deploys to whatever IP is committed** (`inventory.yml:30`). A new instance, or a stopped and started one, has a new public IP; CI then fails with an SSH timeout until the file is updated *(reasoned)*.
- **G19. Port 443 is open, but there is no HTTPS.** The security group opens 80, 443 and 22 (`deploy-create-instance.yml:12-21`), nginx publishes 80 and 443 (`deploy-setup-webserver.yml:29-31`), but `nginx.conf` has only `listen 80` (`:25-27`). Ports 3000, 8000 and 9000 are published on the server but closed by the security group: good, everything goes through nginx.
- **G20. SSH open to the world** (`deploy-create-instance.yml:19-21`, port 22 from `0.0.0.0/0`), and host keys accepted blindly (`ansible.cfg:2`, `inventory.yml:8`). Fine for a class demo; restrict port 22 to your IP in practice.
- **G21. Secrets in the repository.** A `NEXTAUTH_SECRET` is committed (`inventory.yml:24`, `src/frontend-react/.env.production:3`) and so is an account id (`docker-shell.sh:17`). Use your own values, keep your repository private, and never commit the CSV or the `.pem`: `secrets/` sits outside the clone for this reason (`README.md:54-60`). In CI, `src/deployment/secrets/` exists on the runner only (`ci_cd_aws.yml:88-90`).
- **G22. Warnings on every Ansible command in this toolbox.** cryptography's `Python 3.8 is no longer supported`, `Collection community.general does not support Ansible version 2.13.13`, and the `docker_image` redirect deprecation (captured, `laptop/32`, `36`, `40`). They are warnings; the recap decides.

## 7. Where this sits in the course

### The lecture's Google Cloud version, and how this repo differs (slides 17–20)
The slides present `dlops-io/cheese-app-v4`: GitHub Actions authenticates to Google Cloud with a service-account key stored as a repository secret, builds the deployment container and runs Pulumi in it to push images to Artifact Registry and roll the GKE Deployments; a second workflow submits the L15 pipeline to Vertex AI. That repo's own README says the CI part is not implemented (`cheese-app-v4/README.md:157`). `cheese-app-aws` keeps the pattern (commit keyword → fresh runner → the same toolbox container → deploy with a new timestamp tag) and swaps every component (§3.8). Two differences to keep in mind:
1. **No Kubernetes and no Pulumi:** one server with Docker containers, set up by Ansible. The slides' "deploy to the K8s cluster" becomes "recreate the containers on the server".
2. **No ML lane:** nothing here runs a training pipeline. On AWS, L15's `ml-workflow-aws` (SageMaker) is the series' ML pipeline.

### The review: the course on one server (slides 21–37)
The lecture closes with one picture per earlier lecture; on this deployment they land as follows (this year's lecture numbers; the slides print another year's):

| Part of the deployment | Lectures |
| --- | --- |
| the EC2 server and its containers; pipenv inside an image | L01–L02 (VMs, environments, containers) |
| containers sharing storage; the team workflow where a senior developer builds and pushes images by hand (slide 24), now the runner's job | L03–L04 |
| frontend and API execute, ECR and the disk hold state (slide 25's solution architecture) | the app-design lecture |
| the loader, Chroma and the RAG chat route | L05 (RAG) |
| the API's agent routes | L06–L07 (agents) |
| ready-made models through Bedrock instead of your own fine-tuned ones | L08 (fine-tuning, LoRA, distillation); L11 (labeling) sits outside this server |
| training jobs, model deployment, pipelines: beside this server (L15's SageMaker pipeline on AWS) | L13, L15 |
| the API and frontend containers | L18 |
| the CI loop with tests and release, the half this workflow lacks | L09, L21 |
| routing one address to several services: here, nginx | L20, L22 |

### What comes next
Milestone 5 asks for the full loop: put L21's tests in front of the deploy and deploy every merge to `main` (§8 D2). Beyond the tutorial: replace the copied keys with an instance role and GitHub OIDC (§3.4, §8 D1), add HTTPS on port 443, and avoid the per-deploy gap (§8 D3).

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l23-final-cicd/exercises.md) in the video folder. Their outputs are the 2026-11-08 captures and extra checks run for them (`assets/exercise-checks/`); nothing touched AWS or ran on GitHub, so whatever only AWS or GitHub can show is answered from the code at `5950118` and from AWS's or GitHub's documentation, and the answer says so.

**The questions the video stops on** (each is answered right after its timer): Inside the toolbox, Ansible runs `docker build` for the frontend: whose disk does the image land on? · The browser asks nginx for `/api/newsletters`: which path does `api-service` receive? · You push `fix typo /run-tests` to `main`: nothing, build-and-push only, or a full deploy? · Is typing `/run-deploy-app` continuous delivery or continuous deployment, and what would make it the other? · With `cluster_state=absent`, which of the first three tasks of `deploy-create-instance.yml` run?

<details><summary>Answers to the five ponders</summary>

- **Ponder 1:** your laptop's. The toolbox has the Docker CLI but no engine; the socket mount (`docker-shell.sh:36`) sends the build to your laptop's engine, so the image is a sibling of the toolbox.
- **Ponder 2:** `/newsletters`. `location ^~ /api/` matches (`nginx.conf:35`), and `proxy_pass http://api-service:9000/;` (`:37`) replaces the matched prefix with `/` (captured with stand-ins, `laptop/62`).
- **Ponder 3:** build-and-push only. `/run-` passes the job condition (`ci_cd_aws.yml:9`); `/run-deploy-app` is missing, so "Run Deployment Container" (`:100`) is skipped and the server keeps the old tag. Three new images in ECR.
- **Ponder 4:** continuous delivery: a person presses release by typing the keyword (slides 11–12). Continuous deployment: every merge to `main` deploys by itself, behind L21's tests, with no keyword (Milestone 5).
- **Ponder 5:** "Create security group" and "Create EBS volume" are skipped (`when:` at lines 24 and 37); "Create EC2 instance" has no `when:`, runs, and fails on the undefined `security_group.group_id` before any AWS call (`laptop/48`). Nothing is deleted.
</details>

### Test yourself: the five questions from the end of the video

**Q1. Name the two secrets, what each opens, and three places the access key ends up after one deploy. What would an instance role and GitHub OIDC remove?**
<details><summary>Answer</summary>

The IAM access key (CSV) signs AWS API calls: ECR, EC2, Bedrock. The key pair's `.pem` opens SSH to the server as `ubuntu`. The access key ends up in your laptop's `secrets/` and the toolbox's environment; on the server in root's AWS configuration (`deploy-provision-instance.yml:288-292`), in `/srv/secrets/aws-credentials` (`deploy-setup-containers.yml:36-44`) and in the environment of `api-service` and the loader (`:184-186`, `:166-168`); and on GitHub as two repository secrets. An instance role removes the server's copies; GitHub OIDC removes the two key secrets on GitHub. Neither removes the `.pem` or your laptop's CSV.
</details>

**Q2. Why does `sh docker-shell.sh` fail on Ubuntu but work on a Mac? And what did the unquoted `pip install ansible>=9.0.0` actually do?**
<details><summary>Answer</summary>

`sh file` asks `/bin/sh` to read it and ignores the shebang; on Ubuntu `/bin/sh` is dash, which has no here-string `<<<` (line 13): `Syntax error: redirection unexpected` (`laptop/23`, `24`). On macOS `/bin/sh` runs bash. In the Dockerfile's `RUN` line, `>` is an output redirect: pip's log went to a file named `=9.0.0` in `/`, and pip installed an unpinned Ansible, 6.7.0 / core 2.13.13 on Python 3.8 (`laptop/32`, `33`). Quoting it would not get Ansible 9 on this base image.
</details>

**Q3. Where do the tasks of a `hosts: localhost` play run, and of a `hosts: appserver` play? And why can the toolbox fill the disk of your laptop?**
<details><summary>Answer</summary>

`localhost` plays run inside the toolbox (Ansible's controller): their AWS modules call the AWS API from there, their Docker modules talk to a Docker engine from there. `appserver` plays run on the server, over SSH as `ubuntu`, with `become: true`; lookups such as `lookup('env', …)` still run in the toolbox. The toolbox has no Docker engine of its own: `docker-shell.sh:36` mounts your laptop's socket, so the build playbook's three images land on your laptop's disk, beside the 2.52 GB toolbox image.
</details>

**Q4. Follow one timestamp from `date` to a running container. Where is it written down, and how does the server choose between `DOCKER_TAG` and `.docker-tag`?**
<details><summary>Answer</summary>

By hand: `date +%Y%m%d%H%M%S` → `tag` → the three image names → pushed to ECR → `.docker-tag` in your clone → copied to the server → pulled → containers recreated. By CI: `.docker-tag` and `$GITHUB_ENV` on the runner (`ci_cd_aws.yml:46-50`) → `docker tag` / `docker push` → `-e DOCKER_TAG` and `--extra-vars … docker_tag=$DOCKER_TAG`. It is written in `.docker-tag`, `$GITHUB_ENV`, the ECR tags and the IMAGE column of `sudo docker container ls`. The choice is made in the toolbox: `DOCKER_TAG` set and non-empty → `set_fact` from it (`deploy-setup-containers.yml:101-104`); otherwise `cat .docker-tag` on the server (`:106-114`). From your laptop it is always the file; in CI the extra variable outranks both.
</details>

**Q5. Which of these deploy: `update readme`, `fix typo /run-tests`, `/RUN-DEPLOY-APP`, `\run-deploy-app`? In the lecture's words, is this pipeline continuous delivery or continuous deployment?**
<details><summary>Answer</summary>

Only `/RUN-DEPLOY-APP` (`contains()` ignores case). `update readme`: nothing runs. `fix typo /run-tests`: build and push only. `\run-deploy-app`: a backslash, so `/run-` is not in it; nothing runs (a real commit of this repository, `laptop/50`). In the lecture's words it is continuous delivery, without the CI half in front: a person presses release, and no test runs.
</details>

### Hands-on (predict, then run)

- **B1. Where did the pin go?** In your toolbox, predict, then run `ls /`, `ansible --version` and a look into `/=9.0.0`; rewrite the line so the pin works and say why it still would not install Ansible 9 here.
- **B2. Which tag will the server use?** Run the playbook's own tag-choosing lines (`deploy-setup-containers.yml:101-118`) on `localhost` with no variable, with `DOCKER_TAG`, and with an extra variable too.
- **B3. Take away nginx's trailing slash.** Run the repo's `nginx.conf` in front of two stand-ins, `curl` `/api/newsletters`, then remove the `/` after `9000` and repeat.
- **B4. A build that fails, with and without `set -e`.** Break the toolbox build on purpose and run the script twice.
- **B5. Make the delete delete.** In a copy of `deploy-create-instance.yml`, gate the instance task with `when: cluster_state == "present"` and predict which task fails next; then replace "Remove EBS volume" with tasks that find the instance, the 50 GB volume and the security group by name and delete them: in what order, and why?
- **B6. See your own toolbox from inside it.** `docker ps` and `docker images` at the toolbox prompt: whose containers and images are they?
- **B7. More messages for the sieves.** `deploy /run-deploy`, `redeploy: /run-deploy-app-now`, and a push of three commits `/run-deploy-app`, `wip`, `fix lint`: job and deploy step, yes or no?

### Debugging

- **C1.** "credentials file not found" after the CSV fix, when the script is started from the repository root.
- **C2.** Which of the build playbook's two RED lines is the error, and which follows from it?
- **C3.** `no such identity: /root/.ssh/ac215_2024.pem` on the provision step from your laptop.
- **C4.** `UNPROTECTED PRIVATE KEY FILE!` after the key switch, and why the CI copy never has it.
- **C5.** The laptop deploy worked, the CI deploy fails with `no such identity: /secrets/ac215_2024.pem`.
- **C6.** nginx won't stay up: `host not found in upstream "api-service"`.
- **C7.** "I quoted the pin, now provision fails": `Unsupported parameters for (ansible.legacy.command) module: warn`.

### Think

- **D1.** Fewer copies of the keys: what changes, file by file, for an instance role and GitHub OIDC, and what stays a long-lived secret?
- **D2.** From delivery to deployment: the edits that make this workflow continuous deployment, as Milestone 5 asks, without losing the keyword's safety.
- **D3.** Swap, not roll: what a visitor sees during a deploy, and how one machine could avoid the gap.
- **D4.** You terminated the instance and stopped there: what is still on your bill?
- **D5.** Why `linux/amd64` in the script and the playbook but plain `docker build` in CI, and what happens on an Apple-silicon Mac?

---

## 9. Errata and open questions

**Errata (with evidence)**
1. **`sh docker-shell.sh` (`README.md:77`) fails on Linux:** `docker-shell.sh: 13: Syntax error: redirection unexpected` (`laptop/23`). Use `bash docker-shell.sh`.
2. **The README's CSV fix is not enough** (`README.md:76`): `SECRETS_DIR` (`docker-shell.sh:26`) needs the same change (empty `/secrets`, `laptop/28`), and the account id (`:17`) is hard-coded. The README mentions neither.
3. **The toolbox does not build as committed on the recording machine** (`Dockerfile:33-34`, Helm's repository: `laptop/25`, `26`), and `docker-shell.sh` has no `set -e` (`:4`), so the failure is followed by `docker run` of a missing image (exit 125).
4. **`pip install ansible>=9.0.0` is a redirect** (`Dockerfile:37`): ansible 6.7.0 / core 2.13.13, and a file `/=9.0.0` (`laptop/32`, `33`).
5. **Key-pair name:** README `cheese-app-ac215-key-pair` (`:64`) vs code `ac215_2024` (`inventory.yml:16` and the `.pem` paths) (`laptop/13`).
6. **The key-line switch** (`README.md:107-111`) is listed under "Setup Docker Containers" but is needed from the provision step on (§4 Step 15).
7. **Headings "Create Compute Instance (VM) Server in GCP" (`README.md:92`) and "Provision Compute Instance in GCP" (`:99`)**, and "SSH into the server from the GCP console" (`:120`): the playbooks create and provision an EC2 instance; use SSH or EC2 Instance Connect. Carried over from the Google Cloud README.
8. **"API's to enable in AWS"** (`README.md:7-13`) renders empty (its list is an HTML comment); the README never mentions Bedrock model access.
9. **"Configure Nginx file"** (`README.md:136-137`) says to create `nginx.conf`; it already exists.
10. **The delete command deletes nothing** (`README.md:147`): `'dict object' has no attribute 'group_id'`, before any AWS call (`laptop/48`); no task terminates the instance.
11. **`chromadb/chroma:latest`** (`deploy-setup-containers.yml:151`) is 1.0.0 today and answers the 0.5.18 clients' `/api/v1` with HTTP 410 (`laptop/60`, `61`).
12. **The README never mentions the GitHub Actions workflow**, its four secrets or the keyword `/run-deploy-app`; they live only in `ci_cd_aws.yml` and the commit history.
13. **The workflow is named "Continuous Integration and Continuous Deployment"** (`ci_cd_aws.yml:1`) but runs no test (§3.1).
14. *(reasoned, not run)* `/dev/sdf` used twice and the volume pinned to `us-east-1a` (`deploy-create-instance.yml:30`, `:53-57`, `:85-92`); the embeddings' size vs Titan's (G11); `json` not imported in `llm_rag_utils.py` (G12).
15. **The lecture slides and this repo differ** in cloud, keyword, who builds the images, Test/Monitor stages, the ML lane, rolling update vs recreate, routing, and slide 20's bare `git add`: see [Lecture slides](#lecture-slides). In each case, follow the repo.

**Open questions (could not determine here)**
- **Helm's repository on your machine.** Whether `baltocdn.com` passes certificate verification on a student laptop or a GitHub runner today, i.e. whether the unchanged build (and `ci_cd_aws.yml:41-44`) fails for you. The recording machine's CA store did not trust the root of the certificate it served on 2026-11-08.
- **The Ubuntu image** `ami-0e86e20dae9224db8` (`inventory.yml:17`): which release it is, and whether it is still available in `us-east-1` (needs AWS credentials). The provision playbook falls back to Docker's `focal` repository for any release not in its list (`deploy-provision-instance.yml:18-28`).
- **Bedrock models:** whether `anthropic.claude-3-sonnet-20240229-v1:0` and `anthropic.claude-3-5-sonnet-20240620-v1:0` are still served in `us-east-1`, and whether model access must be requested first.
- **"Load Vector DB" under Ansible:** whether `docker run -it` gets a terminal over Ansible's SSH session (G13).
- **The `/dev/sdf` attach** and the fixed `us-east-1a` zone (G15).
- **Every success output.** No AWS account and no GitHub run were available; the PLAY RECAPs with `failed=0`, the Actions run page and the live site are *expected*, not observed.
- **The Ed lesson** was not opened; the lecture side comes from the slides.

---

## Links

- README sections, `cheese-app-aws` (pinned commit):
  - [Deployment to AWS](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#deployment-to-aws) · [Setup AWS Keys for Authentication](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#setup-aws-keys-for-authentication) · [Create AWS EC2 Key Pair](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#create-aws-ec2-key-pair) · [Deployment Setup](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#deployment-setup) · [Deployment Steps](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#deployment-steps) · [Create Empty ECR Repositories](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/README.md#create-empty-ecr-repositories)
  - The workflow: [`.github/workflows/ci_cd_aws.yml`](https://github.com/dlops-io/cheese-app-aws/blob/5950118b0ed97c12c799920846d3eb70b1a47385/.github/workflows/ci_cd_aws.yml) · the playbooks: [`src/deployment/`](https://github.com/dlops-io/cheese-app-aws/tree/5950118b0ed97c12c799920846d3eb70b1a47385/src/deployment)
- The lecture's Google Cloud version (context, pinned): [`dlops-io/cheese-app-v4` @ `033f187`](https://github.com/dlops-io/cheese-app-v4/tree/033f18713b9e1e7985a3080e85edab3ff01cefef)
- Video folder: [`videos/ac215-l23-final-cicd`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l23-final-cicd) · [captures and provenance (`ASSETS.md`)](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l23-final-cicd/ASSETS.md) · [exercises](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l23-final-cicd/exercises.md)
- Ed lesson: [L23 · Final Deployment and Review](https://edstem.org/us/courses/97373/lessons/166048/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for this lecture.
- Previous lecture: [L22 · Scaling: Kubernetes (cloud)](L22-kubernetes-cloud.md) (`cheese-app-v3` on GKE, the Google Cloud path)
- Referenced: [L15 · ML workflows](L15-vertex-ml-workflows.md) (the AWS precedent: `ml-workflow-aws`, SageMaker) · [L20 · Deployment: Pulumi](L20-deployment-pulumi.md) · [L21 · CI/CD with GitHub Actions II](L21-cicd-github-actions.md) (the tests this workflow lacks)
