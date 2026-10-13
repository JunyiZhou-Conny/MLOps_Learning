# L23 · Final Deployment and Review — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166048/) · Tutorial: [`dlops-io/cheese-app-v4`](https://github.com/dlops-io/cheese-app-v4) `main` @ [`033f187`](https://github.com/dlops-io/cheese-app-v4/tree/033f18713b9e1e7985a3080e85edab3ff01cefef) (README "Cheese App - Automation"; context repos [`cheese-app-v3`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a) @ `3ecef56`, [`ml-workflow`](https://github.com/dlops-io/ml-workflow/tree/972ffbb5cb148f9fa6256e7137300dff2b174e2e) @ `972ffbb`, [`cheese-app-ci-cd`](https://github.com/dlops-io/cheese-app-ci-cd/tree/b8458ff0cc1898700b32a873b4665f43f50df71e) @ `b8458ff`) · Colab notebooks: none · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 把 L22 在 GKE 上手动 `pulumi up` 部署的 Formaggio cheese app（Next.js frontend + FastAPI API + ChromaDB vector DB + loader Job）接上 GitHub Actions，让 `git push` 到 `main` 变成 deploy 按钮。commit message 里有 `/deploy-app`：一台全新的 GitHub runner build `deployment` toolbox container，跑 `deploy-k8s-update.sh`（两次 `pulumi up`，先 `deploy_images` 再 `deploy_k8s`），pod 被 rolling update。有 `/run-…`：runner build `workflow` container，把 L15 的 KFP pipeline 提交到 Vertex AI Pipelines。
- **Idea 1 · 只有 CD，没有 CI：** 两个 workflow 都叫 "Continuous Integration and Continuous Deployment"，但一个 test 都不跑，`README.md:157` 自己也承认。broken API 和好的 API ship 得一样快。L21 的 `ci.yml` 是缺的那一半，MS5 要你补上（tests on every PR、merge 到 `main` 就 deploy、≥70% coverage）。
- **Idea 2 · commit message 就是 trigger：** 每次 push 到 `main`，两个 workflow 都会 run，真正做决定的是 job-level 的 `if: contains(github.event.head_commit.message, '/deploy-app')`（`app-ci-cd-gcp.yml:9`）。`contains()` 是 substring 匹配、case-insensitive，而且只看这次 push 的**最后一个** commit。
- **Idea 3 · 同一个 toolbox container，laptop 和 runner 通用：** v4 只改了两处：`Dockerfile:72` 的 `ADD --chown=app:app . /app` 把代码 bake 进 image（runner 上没有 `/app` 的 mount）；entrypoint 有参数时把它当 script 跑（`docker-entrypoint.sh:32-40`）。image 实际由 host 的 Docker daemon build（mount 了 `/var/run/docker.sock`，即 Docker-out-of-Docker）。
- **Idea 4 · timestamp tag 接力：** `deploy_images` 每次 run 都生成新的 `%Y%m%d%H%M%S` tag，export 到 GCS bucket 里的 Pulumi state；`deploy_k8s` 用 `pulumi.StackReference("organization/deploy-images/dev")` 读回来，填进 pod template。template 一变，Kubernetes 就 rolling update。所以就算代码没改，`/deploy-app` 也会重新 build 三个 image、换掉 pod。
- **Idea 5 · 三个 identity：** repo secret `GOOGLE_APPLICATION_CREDENTIALS` 存的是 `deployment` service account 的 JSON key，一路传进 container 里的 `gcloud auth activate-service-account`；cluster 里的 API pod 走 Workload Identity（KSA `api-ksa` → GSA `gcp-service`），不需要 key；Vertex pipeline 的 step 以 `ml-workflow` SA 的身份跑。
- **最费时间的坑：** ① `README.md:162` 写的 `/run-deploy-app` 什么都不 deploy：它匹配的是 `/run-`，触发 ML workflow，然后三个 step 全部 skip。要写 `/deploy-app`。② instructor 的 `ac215-project`、bucket 名和 SA email hard-code 在两个 workflow YAML、三个 `Pulumi.dev.yaml` 和 `docker-shell.sh` 里，README 只提了一处（`README.md:78`）；全部改完，先用**不带** keyword 的 commit push。③ v4 的 `deploy_k8s/Pulumi.dev.yaml:7` 打开了 `setupSSL`，第一次 v4 `pulumi up` 会把 L22 的 NGINX ingress 换成 Google HTTPS load balancer：IP 变了，README 说的 `nginx_ingress_ip` 这个 output 根本不存在（看 `app_url`），managed certificate 也要等一阵才 Active。
- **其他会骗你的地方：** `deploy-k8s-update.sh` 没有 `set -e`，image build 失败了 run 照样可能是绿的；CI 不会重新 build data-collector / data-processor image（只有手动 `sh deploy-ml-images.sh` 会）；`/run-ml-pipeline` 每次都新建一个 Vertex endpoint（`n1-standard-4`，24/7 计费），而 app 根本不调用它。
- **做完要删：** 在 deployment container 里 `cd /app/deploy_k8s && pulumi destroy --stack dev --refresh -y`（regional GKE cluster、node、static IP + HTTPS LB、Cloud NAT、PVC disk）；Vertex AI 里每个 endpoint 先 undeploy model 再 delete；Artifact Registry 的旧 tag（`retain_on_delete=True`，destroy 不会删）；最后删掉 GitHub 上的 `GOOGLE_APPLICATION_CREDENTIALS` secret 和 `deployment` key，或者 disable 两个 workflow。

## At a glance

**What you build.** You turn the cheese app that L22 deployed to GKE by hand into a continuously deployed one: two GitHub Actions workflows watch every push to `main`, a commit message containing `/deploy-app` makes a fresh runner rebuild the three app images and roll the Kubernetes Deployments, and `/run-data-collector`, `/run-data-processor` or `/run-ml-pipeline` submits L15's Kubeflow pipeline to Vertex AI Pipelines. Both lanes run the same toolbox containers you use on your laptop, authenticate with one service-account key stored as a repository secret, and pass image tags to each other through the shared Pulumi state bucket.

**Time needed** (estimate; CD run times on a GitHub runner were not measured, §9 open question 4). With your L22 cluster and images still in place: about 1.5 h for the setup, the repository secret, one `/deploy-app` run and the checks. From scratch: add 1–2 h for building the images (slow under amd64 emulation on Apple Silicon) and creating the cluster, the slowest part. The ML lane: each `/run-ml-pipeline` runs collection, 15 epochs of training and an endpoint deploy; budget another 1–2 h, mostly waiting.

**Prerequisites.**
- A GCP project with billing, and permission to create service accounts and keys.
- A GitHub account and **your own repository** containing cheese-app-v4 (a fork, or a fresh repo). Workflows run only from `.github/workflows/` at the root of the repo that receives the push.
- Docker Desktop and git locally.
- Background: L15 (Vertex AI pipelines), L20 (the Pulumi `deployment` toolbox), L21 (GitHub Actions), L22 (the GKE cluster).
- Credentials: the `deployment` SA key at `<parent of cheese-app-v4>/secrets/deployment.json`; for a from-scratch cluster also `gcp-service`; for the ML lane also `ml-workflow` (§2).

**What it costs.** While the cluster exists, it bills around the clock: the regional cluster fee (about $0.10/h; GKE's free-tier credit does not cover regional clusters), 1–2 `n2d-standard-2` nodes (about $0.08/h each plus disk), the global static IP and HTTPS load balancer (forwarding rules about $0.025/h), Cloud NAT and two PVC disks. Every `/run-ml-pipeline` adds **another** Vertex AI endpoint at about $0.2/h, 24/7. Every `/deploy-app` adds a new set of image tags (several GB) to Artifact Registry, about $0.10/GB-month above the free tier. GitHub Actions minutes are free for public repos. Details and sources in §2.

**Tear down, exactly** (the README has no cleanup section; details in §2 and §4 Part F):
1. Inside the `deployment` container: `cd /app/deploy_k8s && pulumi destroy --stack dev --refresh -y`. This removes the cluster, nodes, IP and load balancer, NAT and router, and PVCs. Then check Compute Engine > Disks that the PVC disks are gone.
2. Console > Vertex AI > Online prediction: for **every** endpoint the pipeline created, undeploy the model, then delete the endpoint.
3. Artifact Registry: delete old tags in `cheese-app-repository`, or add a cleanup policy. `pulumi destroy` does not remove images (`retain_on_delete=True`, `deploy_images/__main__.py:31`).
4. When you are done for the term: delete the `GOOGLE_APPLICATION_CREDENTIALS` Actions secret and the `deployment` key (IAM > Service accounts > Keys), because the key can create clusters in your project; and disable the workflows (Actions tab > workflow > "…" > Disable).

Paths without a repo prefix are relative to `cheese-app-v4/`, and every `path:line` refers to the pinned commit `033f187`.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers.** The course site source (`tutorials_demo.md:288-294`) links only the anchor `#cheese-app---automation`. The README is a single page, `README.md:1-208`, and it is all in scope:
  - [`#cheese-app---automation`](https://github.com/dlops-io/cheese-app-v4#cheese-app---automation) (1-19)
  - `#setup-environments` (21-70)
  - `#ensure-kubernetes-cluster-is-up` (72-129)
  - `#setup-github-action-workflow-credentials` (133-145)
  - `#continuous-integration-and-continuous-deployment-cicd` (147-157)
  - `#frontend--backend-changes` (160-194)
  - `#ml-component-changes` (197-204)
- **Primary repo:** `dlops-io/cheese-app-v4`, branch `main`, commit `033f18713b9e1e7985a3080e85edab3ff01cefef`, committed 2025-12-02 14:13:03 -0500 (message "Test pipeline /run-ml-pipeline"). The branch has 78 commits.
  - The other branch, `origin/pipenv`, is at `31f38b1417f75350dc7c0cd5db5562df8c138744` (2025-04-29 19:34:54 -0400). It is the older Pipenv + Ansible version of the same tutorial. This lecture does not use it; it is cited only for history.
- **Context repos (diff base and upstream pieces):**
  - `dlops-io/cheese-app-v3`, `main`, `3ecef56fea879ac480d260c0906cd95baf05179a`, 2025-11-28 16:00:06 -0500. This is the app you deployed with Pulumi in L20 and on GKE in L22, and the base of the v3→v4 diff in §7.
  - `dlops-io/ml-workflow`, `main`, `972ffbb5cb148f9fa6256e7137300dff2b174e2e`, 2025-10-23 10:28:44 -0400 (L15). v4's `src/workflow/` is copied from it, and so is the trainer package the pipeline's training step expects in GCS.
  - `dlops-io/cheese-app-ci-cd`, `main`, `b8458ff0cc1898700b32a873b4665f43f50df71e`, 2025-11-13 13:59:04 -0500 (L21). It holds the CI workflow, used for comparison.
- **Files read in full:**
  - Both workflows (`.github/workflows/app-ci-cd-gcp.yml`, `ml-ci-cd-gcp.yml`).
  - Everything in `src/deployment/` except the v3 carry-overs `deploy_single_vm/`, `nginx-conf/`, `emoji.yaml`, `visualizer.yaml`, and `uv.lock`, which were only listed: `Dockerfile`, `docker-shell.sh`, `docker-entrypoint.sh`, `deploy-k8s-update.sh`, `deploy-ml-images.sh`, `docker_config.json`, `dockerignore`, `.gitignore`, `pyproject.toml`, `deploy_images/*`, `deploy_images_ml/*`, `deploy_k8s/*`.
  - All of `src/workflow/` (`Dockerfile`, `docker-shell.sh`, `docker-entrypoint.sh`, `cli.py`, `model.py`, `pyproject.toml`; the compiled `*.yaml` were grepped).
  - `src/data-collector/*` and `src/data-processor/*`: the Dockerfiles, entrypoints and shells, and the CLIs. The helpers (`downloader.py`, `cleanser.py`, `tfrecords.py`) were scanned.
  - `src/api-service/` (`Dockerfile`, `docker-entrypoint.sh`, `docker-shell.sh`, `api/service.py`; the routers and utils were grepped).
  - `src/frontend-react/` (`Dockerfile`, `.env.*`, `Common.js`, `Header.jsx`, `Footer.jsx`, `DataService.js`).
  - `src/vector-db/` (entrypoint, `docker-compose.yml`, and the `load`/`download` parts of `cli.py`).
  - `images/ci-cd.png`.
  - The full v4 git log, the last ten commits' diffs, and the v3→v4 tree diff.
- **How claims were checked:**
  - Every `path:line` was checked with `sed -n`/`grep -n`.
  - Every code excerpt in §5 was compared byte-for-byte against the file by a script.
  - No repo Dockerfile, script, Pulumi program or workflow was run. Claims that were reasoned out but could not be run are marked *(reasoned, not run)*.
  - The bash quoting behaviour in §6 #7 and Exercise E2 was tested with a separate two-line shell snippet, not the repo's files.
- **Ed lesson:** not accessible when these sources were checked. The lecture-to-tutorial mapping comes from the course-site source, `tutorials_demo.md:288-294`, which links only the v4 README anchor `#cheese-app---automation` (GCP) plus an AWS variant (`cheese-app-aws`, "No K8s"). That AWS repo was not available locally, so it is not covered here.
- **Colab notebooks:** none.

</details>

## Command checklist

Commands in backticks are exactly as the README (or the file named next to them) writes them; placeholders such as `<your-project>` are kept. Plain items are console clicks or file edits. Items marked *(extra)* are not in the README; they come from §2, §4, §6 and §8 of this guide. Run `pulumi`, `kubectl` and the `sh deploy-*.sh` scripts inside the `deployment` container; run `git` outside it ("**Do this outside the container**", `README.md:187`).

### Before the README *(extra)*

- [ ] *(extra)* Make the repo yours: fork `dlops-io/cheese-app-v4` and enable Actions on the fork's Actions tab ("I understand… enable them"), or push the code to a fresh repository of your own. Secrets are per repo, and workflows run in the repo that receives the push (§4 A0).
- [ ] *(extra)* If cheese-app-v4 sits inside an umbrella repo: move the two workflow YAMLs to the umbrella root and prefix every `${{ github.workspace }}/src/...` with `cheese-app-v4/`; add `secrets/` to the umbrella repo's `.gitignore` before putting `deployment.json` there (§2).

### Setup Environments

*Clone the github repository* (README.md:28-29)
- [ ] Clone repo from [here](https://github.com/dlops-io/cheese-app-v4). For CD, clone **your** copy (fork or new repo).

*API's to enable in GCP for Project* (README.md:31-38)
- [ ] Search for each API in the GCP search bar and enable it: Vertex AI API, Compute Engine API, Service Usage API, Cloud Resource Manager API, Google Artifact Registry API, Kubernetes Engine API.
- [ ] *(extra)* If `pulumi up` later reports `SERVICE_DISABLED` for `iam.googleapis.com`, enable the IAM API as well (§2, reasoned, not run).

*Setup GCP Service Account for deployment* (README.md:40-70)
- [ ] IAM & Admin > Service accounts: create a service account called `deployment`.
- [ ] Give it the roles Compute Admin, Compute OS Login, Container Registry Service Agent, Kubernetes Engine Admin, Service Account User, Storage Admin, Vertex AI Administrator.
- [ ] *(extra)* Also grant **Artifact Registry Administrator**, the role v3 listed (§6 #9).
- [ ] Actions column > ⋮ > "Create key" > JSON > create. Copy the downloaded file into the **secrets** folder beside `cheese-app-v4/` and rename it `deployment.json`.
- [ ] `ls ../secrets` — *(extra)* from the repo root; should show `deployment.json`.
- [ ] *(extra)* Building the cluster from scratch: also create `gcp-service` (roles in `cheese-app-v3/README.md:251-256`). ML lane: you also need `ml-workflow` (from L15).
- [ ] `gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us` — *(extra)* only if your L20/L22 image push never created the registry repository; no code or README step creates it (§2).
- [ ] *(extra)* ML lane only: your own data bucket (`GCS_BUCKET_NAME`) and trainer-code bucket (`GCS_PACKAGE_URI`) holding `cheese-app-trainer.tar.gz`, uploaded by `ml-workflow/src/model-training/package-trainer.sh:1-4` (§2).
- [ ] *(extra)* Replace the instructor's project, bucket and SA values in every file of the §2 table (`docker-shell.sh`, the three `Pulumi.dev.yaml`, both workflow YAMLs, `src/workflow/docker-shell.sh`), then commit and push **without** a trigger keyword (§4 A3).

### Ensure Kubernetes Cluster is Up

`README.md:16-17` lets you skip to "View the App" if your L22 cluster is still running; read §6 #6 first, because v4's config switches the load balancer type.

*Run `deployment` container* (README.md:76-79)
- [ ] `cd src/deployment` — "cd into `deployment`".
- [ ] Go into `docker-shell.sh` and change `GCP_PROJECT` to your project id.
- [ ] `sh docker-shell.sh` — builds `cheese-app-deployment` for `linux/amd64`, logs gcloud and Pulumi in, and leaves you at a bash prompt in `/app`.

*Build and Push Docker Containers to Google Artifact Registry* (README.md:81-91; only if you did not build and push images in the last tutorial)
- [ ] `cd deploy_images`
- [ ] `pulumi stack select dev` — selects the stack in the GCS state bucket.
- [ ] `pulumi stack init dev` — *(extra)* only if the select said `no stack named 'dev' found` (§6 #5).
- [ ] `pulumi up --stack dev -y` — builds and pushes the api-service, frontend-react and vector-db-cli images, all with one timestamp tag.
- [ ] `sh deploy-ml-images.sh` — *(extra)* from `/app`; builds and pushes the data-collector and data-processor images and writes the `deploy-images-ml/dev` stack the ML lane reads (§4 B2½).
- [ ] `cd deploy_images_ml && pulumi stack init dev && pulumi up --stack dev -y` — *(extra)* first run only, when the script's `pulumi stack select dev` fails.

*Create & Deploy Cluster* (README.md:93-103; only if you do not have a cluster running)
- [ ] `cd ../deploy_k8s` — "cd into `deploy_k8s` from the `deployment` folder".
- [ ] `pulumi stack select dev`
- [ ] `pulumi up --stack dev --refresh -y` — creates the network, cluster, workloads and HTTPS load balancer; outputs `app_url`, `ip_address` and more.
- [ ] `kubectl logs job/vector-db-loader -n cheese-app-namespace` — *(extra)* if the `vector-db-loader` Job does not finish.

*View the App (If you have a domain)* (README.md:105-123)
- [ ] Get your ingress IP: "Copy the `nginx_ingress_ip` value". v4 has no such output; copy `ip_address` instead (§9 erratum 4).
- [ ] `pulumi config set deploy-k8s:domain <your-domain>` — *(extra)* inside the container in `deploy_k8s`; then commit the changed `Pulumi.dev.yaml` and re-run `pulumi up` so the Ingress and the managed certificate use your domain (§4 B4).
- [ ] At your domain provider, add an 'A Record': Host/Name `@`, Points to/Value: the IP, TTL 3600 (or default).
- [ ] Wait for DNS propagation (can take 5-30 minutes).
- [ ] Go to `http://your-domain.com` — v4 redirects it to `https://`; it works once the certificate is Active.

*View the App (If you do not have a domain)* (README.md:125-129)
- [ ] Copy the `nginx_ingress_ip` from the terminal. In v4, use the `ip_address` or `app_url` output.
- [ ] Go to `http://<YOUR INGRESS IP>.sslip.io` — redirected to `https://<ip>.sslip.io` (the `app_url`).
- [ ] `kubectl describe managedcertificate managed-certificates -n cheese-app-namespace` — *(extra)* while HTTPS still fails: shows whether the managed cert is still provisioning.
- [ ] Check the footer: `Frontend version: 1` and `API version: 1.0.1`.

### Setup GitHub Action Workflow Credentials

*Setup* (README.md:140-145)
- [ ] Go to the repo Settings.
- [ ] Select "Secrets and variables" from the left side menu and select "Actions".
- [ ] Under "Repository secrets" click "New repository secret".
- [ ] Name: `GOOGLE_APPLICATION_CREDENTIALS`.
- [ ] Secret: copy and paste the contents of your secrets file `deployment.json`.

### Continuous Integration and Continuous Deployment (CI/CD)

- [ ] Read the three definitions (README.md:149-157): this tutorial implements only continuous deployment; no tests run.

*Frontend & Backend Changes* (README.md:160-194)
- [ ] `"version": "2.0"` — open `src/api-service/api/service.py` and change the `/status` return at line **36** (the README says line 29), currently `{"version": "1.0.1"}`.
- [ ] `export const APP_VERSION = 2.2;` — `src/frontend-react/src/services/Common.js` line 3.
- [ ] `` className={`fixed w-full top-0 z-50 transition-all duration-300 ${isScrolled ? 'bg-sky-700' : 'bg-transparent' `` — `src/frontend-react/src/components/layout/Header.jsx` line **41** (the README says 69); it currently reads `bg-sky-800`. The colour shows only after you scroll down 50 px.
- [ ] `git add .` — outside the container.
- [ ] `git commit -m "update frontend and backend version and header color /deploy-app"` — the keyword is `/deploy-app`, not README.md:162's `/run-deploy-app` (§6 #1).
- [ ] `git push`
- [ ] Actions tab: open the run named `<you> submitted a CI CD Action for App Deployment` and follow "Build Deployment Container" and "Run Deploy App". The ML workflow's run for the same push shows its job as skipped.
- [ ] Reload `app_url` and scroll: the footer reads `Frontend version: 2.2` and `API version: 2.0`, and the header turns sky blue.
- [ ] `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <your-project>` — *(extra)* inside your local deployment container.
- [ ] `kubectl get deploy -n cheese-app-namespace -o wide` — *(extra)* the IMAGES column shows the new `:<timestamp>`.
- [ ] `kubectl rollout history deployment/api -n cheese-app-namespace` — *(extra)* one more revision per deploy.

*ML Component Changes* (README.md:197-204)
- [ ] `sh deploy-ml-images.sh` — *(extra)* in the deployment container, first, whenever you changed `src/data-collector` or `src/data-processor`: CI does not rebuild those images (§6 #3).
- [ ] `/run-ml-pipeline` — in the commit message, then push: runs the entire Vertex AI pipeline (collect → process → train → deploy) and creates **another** billed endpoint.
- [ ] `/run-data-collector` — in the commit message, then push: runs only the data collector pipeline (writes `gs://<bkt>/raw.zip`).
- [ ] `/run-data-processor` — in the commit message, then push: runs only the data processor pipeline (writes `gs://<bkt>/clean.zip`).
- [ ] Vertex AI > Pipelines: the run appears; for the full pipeline, four green nodes, a new model in Model Registry and a new endpoint under Online prediction. §4 Part E does the three keywords cheapest first: collector, processor, full pipeline.

### If something goes wrong *(extra)*

- [ ] `git commit --allow-empty -m "redeploy /deploy-app" && git push` — *(extra)* the keyword was not in the **last** commit of the push (§6 #2).
- [ ] `pulumi cancel` — *(extra)* in the stack's folder, clears a stale lock left by a crashed run (§6 #11).

### After the README *(extra)*

*Trace one image tag through three places* (§8 E8)
- [ ] `pulumi stack output cheese-app-api-service-tags --stack dev` — *(extra)* in `/app/deploy_images`; prints `…/cheese-app-api-service:<ts>`.
- [ ] `kubectl get deploy api -n cheese-app-namespace -o jsonpath='{.spec.template.spec.containers[0].image}'` — *(extra)* the same `<ts>` on the live Deployment.
- [ ] `kubectl rollout status deployment/api -n cheese-app-namespace` — *(extra)* if the tag is older: is the rollout still running?

*Clean up* (§4 Part F)
- [ ] `cd /app/deploy_k8s && pulumi destroy --stack dev --refresh -y` — *(extra)* inside the deployment container; deletes the cluster and everything `deploy_k8s` created.
- [ ] *(extra)* Compute Engine > Disks: check that the PVC disks are gone.
- [ ] *(extra)* Vertex AI > Online prediction: undeploy and delete every endpoint the pipeline created.
- [ ] *(extra)* Artifact Registry: delete old tags (or add a cleanup policy).
- [ ] *(extra)* Delete the Actions secret and the SA key, or disable the workflows.

---

## 1. What you build

v3 left you with the full Formaggio cheese app running on a GKE cluster: a Next.js frontend, a FastAPI API, a ChromaDB vector DB and its loader Job, behind an Ingress. You deployed it by hand by running `pulumi up` inside the `deployment` container on your laptop. v4 adds the last layer of the course: **a `git push` to `main` becomes the deploy button.**

Two GitHub Actions workflows listen to every push to `main`. They read the **commit message** to decide what to do:

- **`/deploy-app` in the message** (`app-ci-cd-gcp.yml:9`): a fresh GitHub-hosted Ubuntu VM checks out the repo and authenticates to GCP with a service-account key stored as a repository secret. It builds the same `deployment` toolbox container you use locally and runs `deploy-k8s-update.sh` inside it. That script runs `pulumi up` twice:
  1. In `deploy_images`, it rebuilds the API, frontend and vector-db-cli images, tags them with a fresh timestamp, and pushes them to Artifact Registry.
  2. In `deploy_k8s`, it reads those new tags from the shared Pulumi state and patches the Kubernetes Deployments. Kubernetes then rolls the pods over to the new images.
- **`/run-…` in the message** (`ml-ci-cd-gcp.yml:9`): another fresh VM builds the `workflow` container (L15's Kubeflow Pipelines (KFP) CLI). Depending on the exact keyword, it submits the data-collector pipeline, the data-processor pipeline, or the full collect → process → train → deploy pipeline to **Vertex AI Pipelines**.

The README itself admits (`README.md:157`) that only the CD part is implemented: no tests run in these workflows. The deployed app is served at `https://<static-ip>.sslip.io`, not at v3's `http://<nginx-ip>.sslip.io`, because v4's `Pulumi.dev.yaml` turns on the HTTPS load balancer (`deploy_k8s/Pulumi.dev.yaml:7`).

```
 YOUR LAPTOP (bootstrap once; edit code; git push)                 GITHUB  <you>/cheese-app-v4
 +---------------------------------------------+   git push main   +------------------------------------------+
 | cheese-app-v4/src/{api-service,frontend-... }| ----------------> | .github/workflows/app-ci-cd-gcp.yml      |
 | ../secrets/deployment.json  (never in git)  |                   | .github/workflows/ml-ci-cd-gcp.yml       |
 | sh docker-shell.sh -> cheese-app-deployment |                   | Actions secret GOOGLE_APPLICATION_       |
 |   (pulumi up by hand: first images+cluster) |                   |   CREDENTIALS = contents of deployment.json|
 +---------------------------------------------+                   +------------------------------------------+
                                                     msg contains "/deploy-app" |        | msg contains "/run-"
                     +----------------------------------------------------------+        +---------------------+
                     v                                                                                         v
 RUNNER VM A (ubuntu-latest, fresh per run)                               RUNNER VM B (ubuntu-latest, fresh per run)
 +------------------------------------------------------------+          +----------------------------------------------+
 | auth@v1: writes key file, exports GOOGLE_APPLICATION_CRED. |          | auth@v1 (same secret)                        |
 | docker build src/deployment -> cheese-app-deployment       |          | docker build src/workflow -> cheese-app-workflow|
 | docker run ... cheese-app-deployment deploy-k8s-update.sh  |          | docker run ... python cli.py --data_collector |
 |  +- container (root): gcloud, pulumi, kubectl, uv ------+  |          |                 | --data_processor | --pipeline|
 |  | 1) deploy_images: pulumi up --> /var/run/docker.sock |  |          |  reads deploy-images-ml/dev.json from GCS     |
 |  |    builds 3 linux/amd64 images on the runner daemon  |  |          |  compiles KFP YAML, aip.PipelineJob.run()     |
 |  | 2) deploy_k8s:    pulumi up --> GKE API server       |  |          +----------------------------------------------+
 |  +-----------------------------------------------------+  |               | read state              | submit (runs as
 +------------------------------------------------------------+               |                         v  ml-workflow SA)
        | push :<YYYYmmddHHMMSS>     | read+write state                       |     VERTEX AI PIPELINES
        v                            v                                        |     Data Collector  -> gs://<bkt>/raw.zip
 ARTIFACT REGISTRY             GCS gs://<proj>-pulumi-state-bucket <----------+     Data Processor  -> gs://<bkt>/clean.zip
 us-docker.pkg.dev/<proj>/      .pulumi/stacks/deploy-images/dev.json                Model Training  (trainer tar from
 cheese-app-repository/         .pulumi/stacks/deploy-images-ml/dev.json               gs://cheese-app-trainer-code) -> gs://<bkt>/model
  cheese-app-api-service:<ts>   .pulumi/stacks/deploy-k8s/dev.json                   Model Deploy -> Model Registry + NEW Endpoint
  cheese-app-frontend-react:<ts>                                                       (n1-standard-4, 1 replica, billed 24/7)
  cheese-app-vector-db-cli:<ts>
  cheese-app-data-{collector,processor}:<ts>  (built only by deploy-ml-images.sh, by hand)
        | image pull (nodes run as the deployment SA)
        v
 GKE cheese-app-cluster (regional us-central1; 1-2 n2d-standard-2 nodes in us-central1-a; private nodes + Cloud NAT)
 namespace cheese-app-namespace
   Deployment frontend  (Next.js :3000)                     <- Service frontend :3000 (ClusterIP)
   Deployment api       (FastAPI :9000, PVC persistent-pvc 5Gi at /persistent) <- Service api :9000 (NEG + BackendConfig)
   Deployment vector-db (chromadb/chroma :8000, PVC chromadb-pvc 10Gi)         <- Service vector-db :8000
   Job vector-db-loader (cli.py --download --load --chunk_type recursive-split) --> vector-db:8000
   Ingress cheese-app-ingress (class gce = Google HTTPS LB, global static IP, Google-managed cert, HTTP->HTTPS)
       /            -> frontend:3000
       /api-service -> api:9000      (api mounts its routes under ROOT_PATH=/api-service)
        ^
        |  https://<static-ip>.sslip.io
     BROWSER  (footer shows "Frontend version" from the bundle + "API version" from GET /api-service/status)

 api pods --Workload Identity: KSA api-ksa -> GSA gcp-service--> Vertex AI Gemini (chat, RAG, agent)
 api pods --HTTPS--> github.com/dlops-io/models release v4.0 (CNN .keras)   <-- NOT the Vertex endpoint the ML lane creates
```

---

## 2. Prerequisites and costs

### Accounts and local installs
- A GCP project with billing. You need permission to create service accounts and keys.
- A GitHub account and **your own repository** containing cheese-app-v4. GitHub only runs workflow files that sit in `.github/workflows/` at the **root** of the repository that receives the push.
  - So if you keep all course material in one umbrella repo (for example `MLOps_Learning/` with `cheese-app-v4/` as a subfolder), these workflows will never fire.
  - In that case, either give cheese-app-v4 its own repo, or move the two YAML files to the umbrella repo's root. Then change every `${{ github.workspace }}/src/...` to `${{ github.workspace }}/cheese-app-v4/src/...` (`app-ci-cd-gcp.yml:34,41-47`; `ml-ci-cd-gcp.yml:34,41-44,61-64,81-84`).
  - Also in that layout, `src/deployment/docker-shell.sh:9`'s `$(pwd)/../../../secrets/` resolves to `<umbrella>/secrets/`, which is **inside** the umbrella repo. Add `secrets/` to the umbrella repo's `.gitignore` before you put `deployment.json` there.
  - If you **fork** `dlops-io/cheese-app-v4` instead, Actions are disabled on forks until you enable them on the fork's Actions tab.
- Docker Desktop and git locally. On Apple Silicon, `docker-shell.sh` builds the toolbox for `linux/amd64` (`src/deployment/docker-shell.sh:32`), so it runs under emulation: slow but correct.
- Optional: a domain name (`README.md:105-123`). Without one, the app uses `<ip>.sslip.io`.

### GCP APIs (README.md:31-38)
Vertex AI, Compute Engine, Service Usage, Cloud Resource Manager, Artifact Registry and Kubernetes Engine.

*(Reasoned, not run.)* The Workload Identity binding (`deploy_k8s/create_cluster.py:184-189`) calls the IAM API. If `pulumi up` reports `SERVICE_DISABLED` for `iam.googleapis.com`, enable it.

### Service accounts, keys and secrets: where the code expects them

| Identity | Who uses it | Roles | Where the code expects it |
|---|---|---|---|
| `deployment` | You, inside the `deployment` container; **and** both GitHub workflows; **and** the GKE nodes (`deploy_k8s/create_cluster.py:50`) | Listed in `README.md:44-51`: Compute Admin, Compute OS Login, Container Registry Service Agent, Kubernetes Engine Admin, Service Account User, Storage Admin, Vertex AI Administrator. v3 listed **Artifact Registry Administrator** instead of Container Registry Service Agent (`cheese-app-v3/README.md:243`); keep that role too (see §6 #9). | Local: key at `<parent of cheese-app-v4>/secrets/deployment.json`. `docker-shell.sh:9` sets `SECRETS_DIR=$(pwd)/../../../secrets/`, `:38` mounts it at `/secrets`, and `:14` sets `GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json`. CI: an Actions repository secret named exactly `GOOGLE_APPLICATION_CREDENTIALS` whose value is the whole JSON (`README.md:141-145`; `app-ci-cd-gcp.yml:21`, `ml-ci-cd-gcp.yml:21`). |
| `gcp-service` | API pods and the vector-db loader Job, via Workload Identity (`create_cluster.py:150-189`, `setup_containers.py:209,261`) | **Not in the v4 README.** v3 lists Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader (`cheese-app-v3/README.md:251-256`). | Its email goes in `deploy_k8s/Pulumi.dev.yaml:6` (`security:gcp_ksa_service_account_email`). No key file is needed in the cluster. |
| `ml-workflow` | Vertex AI pipeline steps run **as** it (`src/workflow/cli.py:110,157,316`) | **Not in the v4 README.** It comes from L15 (`ml-workflow` README). | Email in `GCS_SERVICE_ACCOUNT` (`ml-ci-cd-gcp.yml:51,71,91`; `docker-shell.sh:17`). The submitter (the `deployment` SA in CI) needs `actAs` on it; that is what "Service Account User" provides. |

Also note `src/deployment/docker-shell.sh:10,39`, which mounts `secrets/.ssh` read-only into the container. It is a leftover from the single-VM tutorial and is not needed for GKE.

### Buckets and artifacts that must already exist
- **Pulumi state bucket** `gs://<GCP_PROJECT>-pulumi-state-bucket`. It is created automatically by `src/deployment/docker-entrypoint.sh:15-20` (the name comes from `docker-shell.sh:15`).
- **Artifact Registry repository** `cheese-app-repository` in the `us` multi-region. No code or README step creates it: `artifactregistry` is imported at `deploy_images/__main__.py:4` but never used, and the v3 README does not create it either. If your L20/L22 image push worked, it already exists. Otherwise, run this command once (a suggested command; it does not appear in the repo):
  ```sh
  gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us
  ```
- **For the ML lane only** (none of this is in the v4 README; it all comes from L15):
  - The data bucket (`GCS_BUCKET_NAME`, default `cheese-app-ml-workflow-demo`). Bucket names are global, so you need your own name.
  - The trainer-code bucket (`GCS_PACKAGE_URI`, which already includes `gs://`; default `gs://cheese-app-trainer-code`) holding `$GCS_PACKAGE_URI/cheese-app-trainer.tar.gz`, uploaded by `ml-workflow/src/model-training/package-trainer.sh:1-4`. `src/workflow/model.py:26` reads it.
  - The `deploy-images-ml/dev` Pulumi stack, created by `src/deployment/deploy-ml-images.sh`. The README never mentions it, yet `src/workflow/cli.py:29` reads it.

### Values hard-coded to the instructor's project (change all of them)

| File:line | Value |
|---|---|
| `src/deployment/docker-shell.sh:11,16-18` | `GCP_PROJECT="ac215-project"`, bucket names, `ml-workflow@ac215-project…` (the README only mentions `GCP_PROJECT`, at `README.md:78`) |
| `src/deployment/deploy_images/Pulumi.dev.yaml:3`, `deploy_images_ml/Pulumi.dev.yaml:3`, `deploy_k8s/Pulumi.dev.yaml:3,5,6` | `gcp:project: ac215-project`, SA emails |
| `.github/workflows/app-ci-cd-gcp.yml:52,55` | `GCP_PROJECT=ac215-project`, `PULUMI_BUCKET=gs://ac215-project-pulumi-state-bucket` |
| `.github/workflows/ml-ci-cd-gcp.yml:48-54` (repeated at `68-74`, `88-94`) | project, `GCS_BUCKET_NAME`, `GCS_SERVICE_ACCOUNT`, `GCS_PACKAGE_URI`, `PULUMI_BUCKET` (no `gs://` here) |
| `src/workflow/docker-shell.sh:8-13` | the same ML values, for running the workflow container locally |

Stack **config** lives in the committed `Pulumi.dev.yaml` files, while stack **state** lives in the bucket. The CI runner only sees what you committed, so your edited `Pulumi.dev.yaml` files must be pushed.

### What costs money, and how to switch it off
Prices are approximate list prices from GCP's public pricing pages; nothing was billed while checking this guide. Check the current pages.

| Resource | Created by | Rough cost | Shut down with |
|---|---|---|---|
| GKE **regional** cluster `cheese-app-cluster` (`location=region`, `create_cluster.py:24`) | `deploy_k8s` | Cluster fee about $0.10/h. GKE's free-tier credit covers zonal/Autopilot clusters, not regional ones. | `pulumi destroy --stack dev --refresh -y` in `deploy_k8s` (`cheese-app-v3/README.md:511`) |
| 1–2 × `n2d-standard-2` nodes, 50 GB disk each (`create_cluster.py:14-15,63-66`) | `deploy_k8s` | about $0.08/h per node plus disk | same destroy |
| Global static IP and HTTPS load balancer, Google-managed cert (`setup_loadbalancer_ssl.py:12-17`) | `deploy_k8s` (SSL mode) | forwarding rules about $0.025/h, plus traffic | same destroy |
| Cloud NAT and router (`create_network.py:28-48`) | `deploy_k8s` | small hourly fee plus per-GB processing | same destroy |
| PVCs 5 Gi + 10 Gi (`setup_containers.py:17-46`) | `deploy_k8s` | a few cents per day | same destroy; check that the disks disappear under Compute Engine > Disks |
| Artifact Registry images (several GB; **a new tag on every deploy**, `deploy_images/__main__.py:13`) | every `/deploy-app` | about $0.10/GB-month above the free tier | **not** removed by destroy (`retain_on_delete=True`, `deploy_images/__main__.py:31`). Delete old tags, or add a cleanup policy. |
| Vertex AI **Endpoint** with 1 × `n1-standard-4` replica (`src/workflow/model.py:95-103`) | every `/run-ml-pipeline` creates **another** endpoint | about $0.2/h **each, 24/7** | Console > Vertex AI > Online prediction: undeploy the model, then delete the endpoint |
| Vertex AI pipeline runs and the training job | `/run-*` | per-run fee plus training compute | they stop by themselves |
| GitHub Actions minutes | every push to `main` | free for public repos; private repos use the plan's monthly quota | — |

When you are done for the term:
1. Delete the `GOOGLE_APPLICATION_CREDENTIALS` secret and the `deployment` key (IAM > Service accounts > Keys). The key can create clusters in your project.
2. Disable the workflows (Actions tab > workflow > "…" > Disable).

---

## 3. Concepts this tutorial teaches

### 3.1 Continuous Integration vs Delivery vs Deployment, and "git as the control panel"
- **Explanation:** The README defines three terms (`README.md:151-155`):
  - **Continuous integration** tests every change.
  - **Continuous delivery** makes every change *releasable*.
  - **Continuous deployment** *releases* every change automatically.

  v4 does deployment without the integration part (`README.md:157`). In v4 the *repository* becomes the control panel: you no longer type `pulumi up`; you type a commit message.
- **Mental model:** a pipeline of gates between "I saved a file" and "a user sees it": commit → build → (test) → package → release → run. CI fills the early gates. CD removes the human from the last ones.
- **Analogy:** a restaurant. CI is the kitchen tasting every dish. Continuous delivery means the dish is plated and waiting at the pass. Continuous deployment means a conveyor belt carries every plated dish to the table.
- **Common misconception:** "We have GitHub Actions, so we have CI/CD." The v4 workflows are named "Continuous Integration and Continuous Deployment" (`app-ci-cd-gcp.yml:1`), but they never run a test. A broken API ships just as fast as a working one.

### 3.2 Event → workflow → job-level filter on the commit message
- **Explanation:**
  - Both workflows trigger on *every* push to `main` (`on: push: branches: ["main"]`, `app-ci-cd-gcp.yml:3-5`, `ml-ci-cd-gcp.yml:3-5`). The *job* then decides whether to run: `if: contains(github.event.head_commit.message, '/deploy-app')` (`app-ci-cd-gcp.yml:9`) or `'/run-'` (`ml-ci-cd-gcp.yml:9`).
  - Inside the ML job, three step-level `if:`s pick which pipeline to submit (`ml-ci-cd-gcp.yml:37,57,77`).
  - Three properties of `contains()` and `head_commit` matter, all from GitHub's documented behaviour:
    1. It is a **substring** test.
    2. It is **case-insensitive**.
    3. It looks only at the **last** commit of the push.
- **Mental model:** each push drops a string into two sieves. The app sieve has one hole (`/deploy-app`). The ML sieve has a coarse hole (`/run-`) that admits the job, then three finer holes that admit steps.
- **Analogy:** an email server routing on a subject-line keyword, like "[URGENT]".
- **Common misconceptions:**
  - "No keyword means no workflow run." The workflow *runs* on every push; only its job is skipped, which is why each push shows two entries in the Actions tab.
  - "The README's `/run-deploy-app` (`README.md:162`) deploys the app." It contains `/run-`, not `/deploy-app`. It wakes the **ML** job, which builds the workflow container and then skips all three steps. The app is never deployed.

### 3.3 The toolbox container runs the same on your laptop and on a CI runner
- **Explanation:** the `deployment` image bundles gcloud, the GKE auth plugin, Docker (the `docker-ce` package, of which only the client is used), kubectl, Helm, Pulumi and uv (`src/deployment/Dockerfile:14-55`). v4 makes it CI-ready with two small edits:
  1. It **bakes the code into the image** with `ADD --chown=app:app . /app` (`Dockerfile:72`). A runner has no `-v "$BASE_DIR":/app` mount, unlike `docker-shell.sh:37`.
  2. The entrypoint now **runs its arguments** as a script instead of always opening a shell (`docker-entrypoint.sh:32-40`).

  The container does not run its own Docker daemon. It talks to the host's daemon through the mounted socket `/var/run/docker.sock` (`app-ci-cd-gcp.yml:39`, `docker-shell.sh:36`); this is "Docker-out-of-Docker". Images built by Pulumi inside the container are really built by the laptop's or the runner's daemon.
- **Mental model:** a portable workshop in a crate. On your laptop you climb in and work by hand (interactive shell). On the runner a robot opens the crate and pushes one button (`deploy-k8s-update.sh`).
- **Analogy:** a pilot's checklist binder that works the same in the simulator and in the real cockpit.
- **Common misconception:** "CI runs my local container." It rebuilds the image from the committed `src/deployment/` on a fresh VM (`app-ci-cd-gcp.yml:32-35`). Your local `pulumi-plugins/` cache, local edits you did not commit, and the `secrets/` folder do not exist there.

### 3.4 Immutable timestamp tags and a cross-stack reference produce a rolling update
- **Explanation:**
  1. `deploy_images` computes `timestamp_tag = datetime.datetime.now().strftime("%Y%m%d%H%M%S")` on **every** run (`deploy_images/__main__.py:13`). Each image is pushed as `us-docker.pkg.dev/<proj>/cheese-app-repository/<name>:<timestamp>` and the tag list is exported (`:25,34-35`).
  2. `deploy_k8s` reads those exports through `pulumi.StackReference("organization/deploy-images/dev")` (`setup_containers.py:10-14`) and plugs `tags[0]` into the pod templates of the frontend and api Deployments (`:69-71`, `:276-278`) and of the loader Job (`:214`).
  3. A changed image string means a changed pod template. Pulumi patches the Deployment, and Kubernetes replaces pods one at a time (the default RollingUpdate strategy).
- **Mental model:** a relay race. The timestamp is the baton, passed from the image stack, through the state bucket, to the K8s stack, and into the pods.
- **Analogy:** printing a new edition of a book with a new ISBN instead of pasting corrections into the old copies. The library (the cluster) swaps editions on the shelf one copy at a time.
- **Common misconceptions:**
  - "Only the component I changed is redeployed." Every `/deploy-app` rebuilds and re-tags **all three** images. The API, the frontend and the loader Job all roll, even if you touched one CSS class *(reasoned, not run)*.
  - "Using `:latest` would be simpler." With a fixed tag the pod template would not change, so Kubernetes would not roll anything. `image_pull_policy="IfNotPresent"` (`setup_containers.py:72,279`) would also keep the cached old image on the node.

### 3.5 Shared remote state is the integration point
- **Explanation:**
  - Your laptop, runner A and runner B have no shared disk. What they share is the Pulumi state bucket: `pulumi login $PULUMI_BUCKET` (`docker-entrypoint.sh:23`). The images stack writes outputs there, and the K8s stack reads them.
  - The ML workflow doesn't even use Pulumi. It downloads the raw state file `.pulumi/stacks/deploy-images-ml/dev.json` with the GCS client and digs out the `pulumi:pulumi:Stack` resource's outputs (`src/workflow/cli.py:28-57`).
  - DIY (bucket) backends lock a stack during an update. Two overlapping pushes therefore make the second `pulumi up` fail with a "stack is locked" error, because the workflows declare no `concurrency:` group *(reasoned, not run)*.
- **Mental model:** a shared whiteboard in a hallway. Each worker writes results on it and reads others' results from it.
- **Analogy:** a restaurant's order tickets on a rail. The kitchen (images stack) clips a ticket, and the waiter (K8s stack) reads it.
- **Common misconception:** "CI state is separate from my laptop's." They are the *same* stacks. A local `pulumi up` and a CI run can overwrite each other's tags, and a local `pulumi destroy` destroys what CI deployed.

### 3.6 Identity: who is authenticated where
- **Explanation:** five hops carry one identity.
  1. The repository secret holds the `deployment` SA's JSON key.
  2. `google-github-actions/auth@v1` (`app-ci-cd-gcp.yml:18-21`) writes it to a credentials file on the runner and exports `GOOGLE_APPLICATION_CREDENTIALS` with that path (documented behaviour of the action).
  3. `docker run --mount type=bind,source=$GOOGLE_APPLICATION_CREDENTIALS,target=/secrets/deployment.json` puts the file at the path the container expects (`app-ci-cd-gcp.yml:49-50`).
  4. The entrypoint runs `gcloud auth activate-service-account --key-file …` and `gcloud auth configure-docker us-docker.pkg.dev` (`docker-entrypoint.sh:10-13`). From then on, image pushes (credentials from the `gcloud` credential helper in `docker_config.json:2-5`), Pulumi's GCP provider (which reads the key via `GOOGLE_APPLICATION_CREDENTIALS`), and Pulumi's Kubernetes provider, whose generated kubeconfig calls `gke-gcloud-auth-plugin` (`create_cluster.py:107-114`), all act as `deployment`.
  5. Inside the cluster, pods use a *different* identity. The KSA `api-ksa` is annotated to impersonate the `gcp-service` GSA (`create_cluster.py:150-189`), so the API can call Gemini without any key file.

  In the ML lane, Vertex AI runs the pipeline steps as a third identity, `ml-workflow`, because `job.run(service_account=GCS_SERVICE_ACCOUNT)` asks it to (`src/workflow/cli.py:110`).
- **Mental model:** a key card that is photocopied at each door: GitHub vault → runner file → container file → gcloud login → cluster. Then two separate badges (`gcp-service`, `ml-workflow`) are issued *by Google* to workloads that never see a key.
- **Analogy:** a valet key (the JSON key) versus a hotel issuing room cards to guests (Workload Identity).
- **Common misconception:** "The `Configure Docker Client` step (`app-ci-cd-gcp.yml:24-26`) is what lets the images push." It configures the *runner's* Docker for `gcr.io`. The push is driven from inside the container, with credentials from the container's own config (the bind-mounted `docker_config.json` plus the entrypoint's `configure-docker us-docker.pkg.dev`). That step is redundant here.

### 3.7 Two loops, one map: the app CD loop and the ML loop (and where they don't touch)
- **Explanation:** v4's diagram (`images/ci-cd.png`) draws one big cycle: Data Collector → Data Processor → Model Training → Model Deploy → Backend API → Frontend → Users, all driven by Dev Team commits through GitHub Actions. The code implements **two separate loops**:
  - The **app loop:** `/deploy-app` → images → GKE.
  - The **ML loop:** `/run-…` → Vertex AI pipeline → a new Vertex endpoint.

  The arrow "Model Deploy → Backend API" is *not* implemented. The API loads a fixed CNN from a GitHub release at import time (`src/api-service/api/utils/llm_cnn_utils.py:110-149`, URL at `:124`). The trainer the pipeline runs also downloads a fixed dataset from a GitHub release (`ml-workflow/src/model-training/package/trainer/task.py:103-104`) rather than the `clean.zip` the processor just wrote.
- **Mental model:** two gears drawn next to each other, with the connecting tooth (model registry → API) left for you to build in MS5.
- **Analogy:** a bakery with a test kitchen. The test kitchen (ML loop) perfects recipes, and the shop (app loop) sells bread. Until someone carries the new recipe card from the test kitchen to the shop, customers get the old bread.
- **Common misconception:** "Running `/run-ml-pipeline` updates what users see." It creates a new Vertex endpoint that nothing in the app calls.

### 3.8 A cloud load balancer in front of Kubernetes: Ingress class, health checks, certificates
- **Explanation:**
  - With `setupSSL: "true"` (`deploy_k8s/Pulumi.dev.yaml:7`), `__main__.py:37-41` uses `setup_loadbalancer_ssl`. The Ingress is annotated `kubernetes.io/ingress.class: gce` (`setup_loadbalancer_ssl.py:56`), so **GKE creates a Google HTTPS load balancer** with a reserved global IP, a Google-managed certificate for `<ip>.sslip.io` (or your domain), and an HTTP→HTTPS redirect.
  - A Google load balancer health-checks each backend. The API only answers under `/api-service` (`src/api-service/api/service.py:49-50` mounts it at `ROOT_PATH`). So v4 adds a `BackendConfig` whose health check probes `/api-service/` on port 9000 (`setup_containers.py:325-345`), and annotates the Service to use it with container-native load balancing (NEG) (`:353-356`).
  - v3's default path, with `setupSSL` false, was an NGINX ingress controller installed by Helm behind a plain L4 LoadBalancer (`setup_loadbalancer.py:11-46`).
- **Mental model:** NGINX mode is a doorman you hire and run inside the building. GCE mode rents Google's front desk outside the building, and that desk phones each room to check someone is home.
- **Analogy:** a building receptionist (the LB) who calls each office (backend) every 10 s. If nobody answers three times, visitors are not sent there.
- **Common misconception:** "HTTPS works right after `pulumi up`." Google-managed certificates take a while to become Active after DNS points at the IP. Until then, HTTPS fails, and HTTP is redirected to HTTPS.

---

## 4. Step-by-step walkthrough

The README has six parts. Below, each README step is numbered in order. Steps the README needs but omits are marked **(not in README)**. Commands in `bash` blocks are copied verbatim from the README. Commands in `sh` blocks are suggested additions, or come from another file named next to them.

### Part A: one-time setup (README.md:21-70)

**A0. Make the repo yours (not in README).**
- Action: `README.md:29` only says "Clone repo from here". For CD you need a GitHub repo *you* can push to, with your own secrets: a fork, or a fresh repo you push this code to.
- Under the hood: workflows run in the repo that receives the push. Secrets are per-repo.
- Checkpoint: your repo's **Actions** tab lists two workflows. Both have the same name, "Continuous Integration and Continuous Deployment" (`app-ci-cd-gcp.yml:1`, `ml-ci-cd-gcp.yml:1`).
- If it fails: a fork shows "Workflows aren't being run on this forked repository". Click "I understand… enable them".

**A1. Enable APIs (README.md:31-38).** Search for and enable the six APIs in the console.
- Checkpoint: APIs & Services > Enabled APIs lists them.

**A2. Create the `deployment` service account and key (README.md:40-55).**
- Grant the roles listed in `README.md:44-51`, and add **Artifact Registry Administrator** (see §6 #9).
- Create a JSON key and save it as `secrets/deployment.json` **beside** the repo folder (`README.md:57-70`).
- If you are building the cluster from scratch, also create `gcp-service` (`cheese-app-v3/README.md:251-256`). For the ML lane you also need `ml-workflow` (from L15).
- Files involved: `src/deployment/docker-shell.sh:9` (`SECRETS_DIR=$(pwd)/../../../secrets/`), which resolves from `src/deployment/` to the folder beside `cheese-app-v4/`.
- Checkpoint: `ls ../secrets` (from the repo root) shows `deployment.json`.

**A3. Replace the instructor's project values (only partly in README).**
- `README.md:78` says to change `GCP_PROJECT` in `docker-shell.sh`. You also need every row of the table in §2: the `Pulumi.dev.yaml` files, both workflow YAMLs, and the ML bucket and SA names.
- Then commit these edits **without** a trigger keyword. Otherwise CI starts before your cluster exists.
- Note: the pinned commit's own message is "Test pipeline /run-ml-pipeline", so pushing the unmodified clone to a new repo makes that commit the push's `head_commit` and starts the ML workflow. Push after this A3 commit instead.

### Part B: make sure the cluster is up (README.md:72-129)

`README.md:16-17` says you can skip to "View the App" if your L22 cluster is still running. See §6 #6 for why that is risky: v4's config switches the load balancer type.

**B1. Run the `deployment` container (README.md:76-79).**
- Action: `cd src/deployment`, then run `sh docker-shell.sh` (the README writes this inline at `README.md:79`).
- Under the hood:
  - `docker-shell.sh:24-26` re-enters an already-running container if one exists.
  - Otherwise `:32` builds `cheese-app-deployment` for `linux/amd64`, and `:35-56` runs it with these mounts: the Docker socket, the code at `/app`, `secrets` at `/secrets`, `docker_config.json` as `/root/.docker/config.json`, a `pulumi-plugins` cache, and the five app folders at `/api-service`, `/frontend-react`, `/vector-db`, `/data-collector`, `/data-processor`.
  - The entrypoint (`docker-entrypoint.sh:10-27`) activates the SA, sets the project, configures Docker for `us-docker.pkg.dev`, creates or reuses the state bucket, runs `pulumi login gs://…`, and lists stacks.
- Checkpoint: you see `Container is running!!!`, then `Bucket already exists. Skipping creation.` (or `Bucket does not exist. Creating...`), `Logging into Pulumi using GCS bucket: gs://<proj>-pulumi-state-bucket`, a listing under `Available Pulumi stacks in GCS:`, and a bash prompt in `/app`.
- If it fails:
  - An `ERROR: (gcloud.auth.activate-service-account)` line saying `/secrets/deployment.json` cannot be read → the key is not at `../../../secrets/deployment.json` relative to `src/deployment`. (Exact wording depends on the gcloud version; not run.)
  - A very slow first build is normal on Apple Silicon (emulated amd64). See §6 #12 about the build context.

**B2. Build and push the app images (README.md:81-91).** Inside the container:
- Action: `cd deploy_images`, then:
  ```bash
  pulumi stack select dev
  ```
  ```bash
  pulumi up --stack dev -y
  ```
- Under the hood: three `docker_build.Image` resources (`deploy_images/__main__.py:23-74`) build `../../api-service`, `../../frontend-react` and `../../vector-db` (that is, the `/api-service`, `/frontend-react` and `/vector-db` mounts) for `linux/amd64` on your host's Docker daemon. They push them with tag `<YYYYmmddHHMMSS>` and export `*-ref` and `*-tags`.
- Checkpoint: an `Outputs:` block with `cheese-app-api-service-tags`, `cheese-app-frontend-react-tags` and `cheese-app-vector-db-cli-tags`, all ending in the same timestamp. The images then appear in Artifact Registry.
- If it fails:
  - `no stack named 'dev' found` → you never created it in this bucket. Run `pulumi stack init dev` (from `cheese-app-v3/README.md:420`), then retry.
  - `Repository "cheese-app-repository" not found` → create it (§2).
  - `denied: Permission "artifactregistry.repositories.uploadArtifacts" denied` → add Artifact Registry Administrator or Writer to `deployment`.

**B2½. Build and push the ML images (not in README).** Still inside the container, from `/app`:
```sh
sh deploy-ml-images.sh        # src/deployment/deploy-ml-images.sh:1-3
```
- Under the hood: the script runs `cd deploy_images_ml`, `pulumi stack select dev` and `pulumi up --stack dev -y`. That builds `cheese-app-data-collector` and `cheese-app-data-processor` (`deploy_images_ml/__main__.py:18-54`) and writes the stack file `src/workflow/cli.py:29` later reads.
- On the first run, `pulumi stack select dev` fails with `no stack named 'dev' found`. Do `cd deploy_images_ml && pulumi stack init dev && pulumi up --stack dev -y` once. (Not in the repo: it combines the script with v3's init step.)
- Checkpoint: the bucket now has `.pulumi/stacks/deploy-images-ml/dev.json`.

**B3. Create and deploy the cluster (README.md:93-103).**
- Action: `cd ../deploy_k8s`, then:
  ```bash
  pulumi stack select dev
  ```
  ```bash
  pulumi up --stack dev --refresh -y
  ```
- Under the hood, `deploy_k8s/__main__.py:24-46` runs:
  1. `create_network`: VPC, subnet, router, NAT.
  2. `create_cluster`: a regional GKE cluster with private nodes and Workload Identity; a node pool of 1–2 `n2d-standard-2` nodes in `us-central1-a` running as the `deployment` SA; a kubeconfig built for `gke-gcloud-auth-plugin`; the namespace; the KSA plus its IAM binding; and a `gcloud container clusters get-credentials` local command.
  3. `setup_containers`: two PVCs; the frontend, vector-db and api Deployments and Services; the loader Job; and the BackendConfig.
  4. A load balancer: SSL mode, because `Pulumi.dev.yaml:7` is `"true"`.
- Checkpoint: `setupSSL: True` and `domain: None` are printed (`__main__.py:20-21`). Then `Outputs:` lists `app_url`, `cluster_endpoint`, `cluster_name`, `ingress_name`, `ip_address`, `kubeconfig` and `namespace` (`__main__.py:49-55`). A first create takes a long time; the cluster is the slow part.
- If it fails:
  - 403 / permission errors naming `ac215-project`, or errors about the SA emails → you have not replaced the instructor's values in `deploy_k8s/Pulumi.dev.yaml:3,5,6`. (`deploy_k8s/__main__.py:14` reads the project with `.get`, so a missing `gcp:project` does not produce Pulumi's "Missing required configuration variable" error here; `deploy_images/__main__.py:9` uses `.require` and does.)
  - 403 on `api-gsa-wi-user` → your `deployment` SA cannot set IAM policy on `gcp-service` (see §6 #10).
  - The `vector-db-loader` Job does not finish → read its logs: `kubectl logs job/vector-db-loader -n cheese-app-namespace` (suggested; not in the README).

**B4. View the app (README.md:105-129).**
- Action: open the `app_url` output, `https://<ip>.sslip.io`.
- The README says to copy `nginx_ingress_ip` (`README.md:107,126`). **No such output exists in v4**; use `ip_address`/`app_url`. The README's `http://<YOUR INGRESS IP>.sslip.io` (`:127`) is redirected to HTTPS.
- **If you have a domain (`README.md:105-123`):** the README's steps are an A record pointing at the ingress IP, a wait for DNS, then `http://your-domain.com`. In v4's SSL mode you also have to tell Pulumi the host name, otherwise the Ingress rule and the managed certificate are for `<ip>.sslip.io` only (`setup_loadbalancer_ssl.py:18-21`, `deploy_k8s/__main__.py:19`). The instructor's `deploy-k8s:domain: formaggio.dlops.io` line was deleted in commit `a533054`. Suggested fix (not in the repo), inside the container in `deploy_k8s`: `pulumi config set deploy-k8s:domain <your-domain>`, commit the changed `Pulumi.dev.yaml`, re-run `pulumi up`, point the A record at the `ip_address` output, and open `https://<your-domain>` once the certificate is Active.
- Checkpoint: the Formaggio home page loads. The footer shows `Frontend version: 1` and `API version: 1.0.1` (`Footer.jsx:37`; `Common.js:3`; `service.py:36`). `APP_VERSION = 1.0` is a JavaScript number, so it renders as `1`.
- If it fails:
  - A certificate error, or `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`, means the managed cert is still provisioning. Wait, and check it with `kubectl describe managedcertificate managed-certificates -n cheese-app-namespace` (suggested; not in the README).
  - A 502 on `/api-service/...` means the backend health check is failing. Check that the BackendConfig exists (`setup_containers.py:325-345`).

### Part C: GitHub credentials (README.md:133-145)

**C1. Add the repository secret.**
- Action: repo **Settings → Secrets and variables → Actions → New repository secret**. Name: `GOOGLE_APPLICATION_CREDENTIALS`. Value: the full contents of `deployment.json` (`README.md:141-145`).
- Under the hood: `${{ secrets.GOOGLE_APPLICATION_CREDENTIALS }}` is injected into `auth@v1` (`app-ci-cd-gcp.yml:21`, `ml-ci-cd-gcp.yml:21`) and masked in logs.
- If it fails: `the GitHub Action workflow must specify exactly one of "workload_identity_provider" or "credentials_json"` means the secret name is misspelled or the secret is empty. That is the auth action's error for an empty input.

### Part D: app changes trigger a deploy (README.md:160-194)

**D1. Change the API version.**
- Action: `README.md:164-171` says to edit `service.py` "line 29" to return `"version": "2.0"`. In the current code the endpoint is at `src/api-service/api/service.py:34-36` and returns `{"version": "1.0.1"}`; line 29 is the `/` route. Edit line 36.

**D2. Change the frontend version.** `README.md:173-177` is correct: `src/frontend-react/src/services/Common.js:3` is `export const APP_VERSION = 1.0;`. Set it to `2.2`.

**D3. Change the header colour.**
- `README.md:179-184` points to "line 69" of `Header.jsx`. The `className` is actually at `src/frontend-react/src/components/layout/Header.jsx:41`, and it currently reads `bg-sky-800`, because the instructor's demo commit `e8f6d3c` changed 700→800. Change it to `bg-sky-700` (or any Tailwind colour).
- The colour shows only after you scroll down 50 px (`Header.jsx:23`).

**D4. Commit with the keyword and push, outside the container (README.md:186-194).**
```bash
git add .
git commit -m "update frontend and backend version and header color /deploy-app"
git push
```
- Ignore `README.md:162`, which says the keyword is `/run-deploy-app`. The workflow tests for `/deploy-app` (`app-ci-cd-gcp.yml:9`). `README.md:188` and the example commit are right.

**D5. Watch the run.** Actions tab → the run named `<you> submitted a CI CD Action for App Deployment` (`app-ci-cd-gcp.yml:2`).
- Steps, in order (`app-ci-cd-gcp.yml:12-56`):
  1. Four `echo` lines show the message, the event (`push`), the OS (`Linux`) and the branch (`refs/heads/main`).
  2. Checkout.
  3. Auth.
  4. gcloud setup.
  5. Docker configure.
  6. Two more `echo` lines (`:27-28`).
  7. `ls` of the workspace. It shows `README.md`, `images` and `src`, plus the auth action's `gha-creds-*.json` file.
  8. "Build Deployment Container".
  9. "Run Deploy App". This log shows the same entrypoint banner as B1, the argument `deploy-k8s-update.sh` echoed (`docker-entrypoint.sh:33`), then two Pulumi updates: images first, then K8s.
- The parallel ML workflow run for the same push shows its job as **skipped**.
- If it fails, see §6. Most common: wrong secret, wrong project or bucket names in the YAML, missing Artifact Registry permission, or a stack lock from an overlapping run.

**D6. Verify.**
- Reload `app_url` and scroll. The footer should read `Frontend version: 2.2` and `API version: 2.0`, and the header turns sky blue.
- Optional, inside your local deployment container (suggested commands, not in the README):
```sh
gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <your-project>
kubectl get deploy -n cheese-app-namespace -o wide          # IMAGES column shows the new :<timestamp>
kubectl rollout history deployment/api -n cheese-app-namespace
```

### Part E: ML changes trigger Vertex AI pipelines (README.md:197-204)

**E1. Data collector.**
- Action: commit with `/run-data-collector` in the message (`README.md:203`) and push.
- Under the hood:
  1. `ml-ci-cd-gcp.yml:32-35` builds `src/workflow`.
  2. `:36-55` runs `cheese-app-workflow python cli.py --data_collector`. The workflow entrypoint activates the key and runs `uv run python cli.py --data_collector` (`src/workflow/docker-entrypoint.sh:14-28`).
  3. `cli.py:64-110` reads the latest collector tag from the Pulumi state file, compiles a one-step KFP pipeline into `data_collector.yaml`, and submits it as `cheese-app-data-collector-<8 chars>` to run as `ml-workflow`. `job.run(...)` blocks until the run ends, so the Actions step stays "in progress" for the whole pipeline, and turns red if the Vertex run fails (the SDK raises on a failed pipeline).
  4. On Vertex, the collector container runs `uv run python cli.py --search --nums 10 --query brie+cheese … --bucket <bkt>` (`src/data-collector/docker-entrypoint.sh:21`, `src/workflow/cli.py:79-84`) and uploads `raw.zip` (`src/data-collector/cli.py:63-66`).
- Checkpoint: Vertex AI → Pipelines shows the run, and `gs://<bkt>/raw.zip` exists.

**E2. Data processor.** Commit with `/run-data-processor` (`README.md:204`).
- Under the hood: the same flow with `--data_processor` (`ml-ci-cd-gcp.yml:56-75`, `cli.py:113-157`). The processor runs `--clean`, which downloads `raw.zip`, de-duplicates and verifies the images, and uploads `clean.zip` (`src/data-processor/cli.py:42-75`).

**E3. Full pipeline.** Commit with `/run-ml-pipeline` (`README.md:202`).
- Under the hood: `cli.py:221-316` builds a four-task pipeline chained with `.after()`: Data Collector (50 images per query) → Data Processor → Model Training (15 epochs, `mobilenetv2`) → Model Deploy.
  - Training launches a separate Vertex custom job from the trainer tarball (`model.py:25-63`).
  - Deploy uploads `gs://<bkt>/model` and deploys it to a **new endpoint** (`model.py:84-103`).
- Checkpoint: four green nodes in the Vertex pipeline graph, a new model in Model Registry, and a new endpoint under Online prediction.
- If it fails:
  - `404 … .pulumi/stacks/deploy-images-ml/dev.json` → do B2½.
  - `403 … iam.serviceAccounts.actAs` → the `deployment` SA lacks Service Account User on `ml-workflow`.
  - A training step failing to find `cheese-app-trainer.tar.gz` → upload it (§2).
- Note: the training component calls `job.run(..., sync=False)` (`model.py:62`). Tracing the SDK (see the [L15 guide](L15-vertex-ml-workflows.md)) shows that the component's process still waits for the job at exit, but an exception in the background thread is not re-raised. So a failed training job can leave the step green.

### Part F: clean up (not in README)
Run this inside the deployment container (the command is from `cheese-app-v3/README.md:511`; the console steps are additions):
```sh
cd /app/deploy_k8s && pulumi destroy --stack dev --refresh -y
```
Then, in the console:
1. Undeploy and delete every Vertex AI endpoint the pipeline created.
2. Delete old Artifact Registry tags.
3. Delete the Actions secret and the SA key, or disable the workflows.

---

## 5. Code tour

### Key files
```
cheese-app-v4/
├── .github/workflows/
│   ├── app-ci-cd-gcp.yml        # on push to main + "/deploy-app": build deployment image, run deploy-k8s-update.sh
│   └── ml-ci-cd-gcp.yml         # on push to main + "/run-": build workflow image, submit a Vertex pipeline
├── images/ci-cd.png             # the course-wide CI/CD picture (README.md:11)
├── README.md                    # the tutorial (208 lines)
└── src/
    ├── api-service/             # FastAPI; api/service.py mounts everything under ROOT_PATH (/api-service in K8s)
    ├── frontend-react/          # Next.js; Common.js (APP_VERSION), layout/Header.jsx (colour), layout/Footer.jsx (shows versions)
    ├── vector-db/               # ChromaDB loader CLI (image cheese-app-vector-db-cli; run as a K8s Job)
    ├── data-collector/          # NEW in v4: Bing image scraper -> gs://<bkt>/raw.zip (Vertex pipeline step)
    ├── data-processor/          # NEW in v4: dedupe/verify -> gs://<bkt>/clean.zip (Vertex pipeline step)
    ├── workflow/                # NEW in v4: KFP pipeline CLI (from L15 ml-workflow) + Pulumi-state lookup of image tags
    │   ├── cli.py, model.py     # pipelines and the training/deploy components
    │   └── *.yaml               # compiled pipeline specs (build artefacts, overwritten on each run)
    └── deployment/              # the toolbox container
        ├── Dockerfile           # gcloud, kubectl, helm, pulumi, uv; v4 bakes the code in (ADD . /app)
        ├── docker-shell.sh      # local: build + run interactively with mounts
        ├── docker-entrypoint.sh # auth, state-bucket login, then shell OR run the given script
        ├── deploy-k8s-update.sh # NEW: what CI runs: deploy_images then deploy_k8s
        ├── deploy-ml-images.sh  # NEW: build ML images (nothing calls it automatically)
        ├── deploy_images/       # Pulumi: build+push api/frontend/vector-db-cli with a timestamp tag
        ├── deploy_images_ml/    # NEW Pulumi project: build+push data-collector/processor
        ├── deploy_k8s/          # Pulumi: network, GKE, workloads, ingress (SSL mode on in v4)
        └── deploy_single_vm/    # v3 carry-over (L20), unused here
```

### Excerpt 1: the trigger

**`.github/workflows/app-ci-cd-gcp.yml:1-9`**
```yaml
name: Continuous Integration and Continuous Deployment
run-name: ${{ github.actor }} submitted a CI CD Action for App Deployment
on:
  push:
    branches: [ "main" ]

jobs:
  Explore-GitHub-Actions:
    if: contains(github.event.head_commit.message, '/deploy-app')
```
- `name` is identical in both workflow files, so tell them apart by `run-name`, which is evaluated per run.
- `on.push.branches` means pushes to other branches, PRs and tags never trigger it. A merged PR triggers it via the merge commit's message.
- The job-level `if` gates the whole job. Skipped jobs cost no runner time.
- `head_commit` is the **last** commit of the push.
- `Explore-GitHub-Actions` is a leftover name from GitHub's starter template. The ML file uses the same job id.

### Excerpt 2: checkout and authentication

**`.github/workflows/app-ci-cd-gcp.yml:16-26`**
```yaml
      - name: Check out repository code
        uses: actions/checkout@v4
      - id: 'auth'
        uses: google-github-actions/auth@v1
        with:
          credentials_json: '${{ secrets.GOOGLE_APPLICATION_CREDENTIALS }}'
      - name: Configure Google Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
      - name: Configure Docker Client
        run: |-
          gcloud auth configure-docker # --quiet #authenticate to gcr
```
- `checkout@v4` puts the pushed commit into `$GITHUB_WORKSPACE`.
- `auth@v1` with `credentials_json` writes the key to a file in the workspace and exports `GOOGLE_APPLICATION_CREDENTIALS`. The later "Run Deploy App" step's `docker run` uses that variable (Excerpt 3).
- `setup-gcloud@v1` puts gcloud on the runner's PATH.
- The last step configures the *runner's* Docker for `gcr.io`-style hosts. Nothing in this workflow pushes from the runner's own Docker client, so it is redundant. `# --quiet` is commented out, so the command runs without `--quiet`.

### Excerpt 3: running the toolbox in CI

**`.github/workflows/app-ci-cd-gcp.yml:36-49`**
```yaml
      - name: Run Deploy App
        run: |-
          docker run --rm --name cheese-app-deployment \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v $HOME/.ssh:/home/app/.ssh \
            -v "${{ github.workspace }}/src/deployment/docker_config.json":/root/.docker/config.json \
            -v "${{ github.workspace }}/src/deployment/pulumi-plugins":/root/.pulumi/plugins \
            -v ${{ github.workspace }}/src/frontend-react:/frontend-react \
            -v ${{ github.workspace }}/src/api-service:/api-service \
            -v ${{ github.workspace }}/src/vector-db:/vector-db \
            -v ${{ github.workspace }}/src/data-collector:/data-collector \
            -v ${{ github.workspace }}/src/data-processor:/data-processor \
            --volume $GITHUB_WORKSPACE:/workspace \
            --mount type=bind,source=$GOOGLE_APPLICATION_CREDENTIALS,target=/secrets/deployment.json \
```
- There is no `-it`: this is non-interactive.
- The Docker socket gives the container the runner's daemon, so Pulumi's image builds happen there.
- The app folders are mounted at the **same absolute paths** as locally (`docker-shell.sh:42-46`). That is why `deploy_images/__main__.py:20`'s relative `../../api-service`, resolved from `/app/deploy_images`, finds `/api-service` both locally and in CI.
- There is **no** `-v …:/app` mount. Code under `/app` comes from the image (Excerpt 4).
- `src/deployment/pulumi-plugins` is git-ignored (`src/deployment/.gitignore:1`, `/pulumi-*`), so on the runner that mount source does not exist and Docker creates an empty directory. Pulumi's provider plugins are therefore downloaded again on every run *(reasoned, not run)*.
- The last line bind-mounts the key file the auth action wrote.
- The following lines (`:50-56`) set `GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json`, `USE_GKE_GCLOUD_AUTH_PLUGIN=True`, project, zone, region and `PULUMI_BUCKET`, and finally name the image and the argument `deploy-k8s-update.sh`.

### Excerpt 4: baking the code into the image

**`src/deployment/Dockerfile:63-75`**
```dockerfile
# Set the working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY --chown=app:app pyproject.toml uv.lock* ./

# Install Python dependencies
RUN uv sync --frozen

ADD --chown=app:app . /app

# Start a new shell to use the installed SDK
ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]
```
- The lock-first copy keeps the `uv sync` layer cached when only code changes. It installs into `/home/app/.venv` (`UV_PROJECT_ENVIRONMENT`, `Dockerfile:8`), which the Pulumi projects use through `toolchain: uv` (`deploy_images/Pulumi.yaml:3-6`).
- The `ADD` line is the one-line v3→v4 change that makes CI possible: the image now *contains* `deploy-k8s-update.sh`, `deploy_images/` and `deploy_k8s/`.
- Locally, `docker-shell.sh:37` still mounts your working tree over `/app`, so local edits win there.
- There is no `USER` line, so the container runs as root. The Docker credential helper config is therefore read from `/root/.docker/config.json`.

### Excerpt 5: interactive or scripted

**`src/deployment/docker-entrypoint.sh:29-40`**
```bash
# Run Bash for interactive mode
#/bin/bash

args="$@"
echo $args

if [[ -z ${args} ]]; 
then
    /bin/bash
else
  /bin/bash $args
fi
```
- With no arguments (local `docker-shell.sh`), you get a shell.
- With `deploy-k8s-update.sh` (CI), bash runs that script in `/app`.
- Because `/bin/bash $args` is the **last** command, its exit code becomes the container's exit code, which `docker run --rm` passes to the Actions step. That is how a failure reaches the red ✗, but only if the script itself exits non-zero (Excerpt 6).
- Lines `10-27`, above this excerpt, do the gcloud and Pulumi login every time the container starts.

### Excerpt 6: the deploy script CI runs

**`src/deployment/deploy-k8s-update.sh:1-9`**
```bash

cd deploy_images
pulumi stack select dev
pulumi up --stack dev -y

cd ..
cd deploy_k8s
pulumi stack select dev
pulumi up --stack dev -y
```
- The order matters: images first, so the K8s stack's `StackReference` sees the new tags.
- There is no `--refresh`, so Pulumi trusts its state and won't notice manual `kubectl` edits.
- There is no `set -e`, so the script's exit code is that of the last `pulumi up` only. A failed image build followed by a no-op K8s update reports **success** (§6 #4).

### Excerpt 7: build, push and export an image

**`src/deployment/deploy_images/__main__.py:23-35`**
```python
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
# Export references to stack
pulumi.export("cheese-app-api-service-ref", api_service_image.ref)
pulumi.export("cheese-app-api-service-tags", api_service_image.tags)
```
- `timestamp_tag` (from `:13`) changes on every run, so `tags` changes, so Pulumi rebuilds and pushes even when the code is identical.
- `LINUX_AMD64` matches the GKE nodes (`n2d` = AMD x86). On an Apple Silicon laptop this is an emulated build. On the GitHub runner it is native.
- `retain_on_delete=True` means `pulumi destroy` does not delete images from the registry.
- The `"…"` quotes nested inside the f-strings need Python ≥ 3.12. The container uses 3.13 (`Dockerfile:4`).
- The exported `-tags` list is what Excerpt 8 consumes.

### Excerpt 8: the cross-stack pipe

**`src/deployment/deploy_k8s/setup_containers.py:8-14`**
```python
    # Get image references from deploy_images stack
    # For local backend, use: "organization/project/stack"
    images_stack = pulumi.StackReference("organization/deploy-images/dev")
    # Get the image tags (these are arrays, so we take the first element)
    api_service_tag = images_stack.get_output("cheese-app-api-service-tags")
    frontend_tag = images_stack.get_output("cheese-app-frontend-react-tags")
    vector_db_cli_tag = images_stack.get_output("cheese-app-vector-db-cli-tags")
```
- With a DIY (bucket) backend, the organization is the literal `organization`. `deploy-images` is the project name from `deploy_images/Pulumi.yaml:1`, and `dev` is the stack.
- `get_output` returns a lazy `Output`. It resolves at deploy time to whatever the images stack *last* exported.

### Excerpt 9: the tag lands in the pod template

**`src/deployment/deploy_k8s/setup_containers.py:273-285`**
```python
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name="api",
                            image=api_service_tag.apply(
                                lambda tags: tags[0]
                            ),  # API container image (placeholder - needs to be filled)
                            image_pull_policy="IfNotPresent",
                            ports=[
                                k8s.core.v1.ContainerPortArgs(
                                    container_port=9000,  # API server port
                                    protocol="TCP",
                                )
                            ],
```
- `.apply(lambda tags: tags[0])` turns the exported list into the single image string.
- When it differs from the live Deployment's, Pulumi patches `spec.template`, and Kubernetes starts a rolling update.
- The comment "placeholder - needs to be filled" is stale; it *is* filled.
- `IfNotPresent` is safe only because every tag is unique.
- The same pattern feeds the frontend (`:69-71`) and the loader Job (`:214`).

### Excerpt 10: v4's HTTPS front door

**`src/deployment/deploy_k8s/setup_loadbalancer_ssl.py:50-61`**
```python
    ingress = k8s.networking.v1.Ingress(
        f"{app_name}-ingress",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=f"{app_name}-ingress",
            namespace=namespace.metadata.name,
            annotations={
                "kubernetes.io/ingress.class": "gce",
                "kubernetes.io/ingress.global-static-ip-name": ip_address.name,
                "networking.gke.io/managed-certificates": "managed-certificates",
                "networking.gke.io/v1beta1.frontend-config": "https-redirect",
            },
        ),
```
- `ingress.class: gce` hands the Ingress to GKE's built-in controller, which provisions a Google external HTTPS LB.
- `global-static-ip-name` pins it to the `GlobalAddress` from `:12-17`.
- `managed-certificates` names the `ManagedCertificate` (`:24-34`) for the host. The host is `<ip>.sslip.io` because no `deploy-k8s:domain` is set: it was removed in commit `a533054`.
- The `frontend-config` annotation applies the HTTP→HTTPS redirect (`:37-47`).
- Paths `/api-service` and `/` follow at `:62-97`.
- Together with the API's BackendConfig health check (`setup_containers.py:325-345`, wired via the Service annotations at `:353-356`), these are the v4 changes that make the GCE load balancer work.

### Excerpt 11: an ML step in CI

**`.github/workflows/ml-ci-cd-gcp.yml:36-46`**
```yaml
      - name: Run Data Collector
        if: contains(github.event.head_commit.message, '/run-data-collector')
        run: |-
          docker run --rm --name cheese-app-workflow \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v ${{ github.workspace }}/src/frontend-react:/frontend-react \
            -v ${{ github.workspace }}/src/api-service:/api-service \
            -v ${{ github.workspace }}/src/data-collector:/data-collector \
            -v ${{ github.workspace }}/src/data-processor:/data-processor \
            --mount type=bind,source=$GOOGLE_APPLICATION_CREDENTIALS,target=/secrets/deployment.json \
            -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json \
```
- A step-level `if` runs inside the job admitted by `'/run-'`.
- The socket and the four source mounts are copied from the deploy job but unused. The workflow container only talks to GCP APIs, and it builds **no** images.
- In CI the pipeline is submitted with the `deployment` key. Locally, `src/workflow/docker-shell.sh:27` uses `ml-workflow.json` instead.
- The env lines that follow (`:47-54`) must match your project. Note `PULUMI_BUCKET` here is a bare bucket name (`:54`), because `cli.py` passes it to `storage.Client().bucket()`.

### Excerpt 12: reading Pulumi state without Pulumi

**`src/workflow/cli.py:36-51`**
```python
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(stack_path)

    # Download and parse JSON
    stack_content = blob.download_as_text()
    stack_data = json.loads(stack_content)

    # Extract outputs from the stack resource
    outputs = {}
    for resource in (
        stack_data.get("checkpoint", {}).get("latest", {}).get("resources", [])
    ):
        if resource.get("type") == "pulumi:pulumi:Stack":
            outputs = resource.get("outputs", {})
            break
```
- This is the only diff between v4's `workflow/cli.py` and L15's `ml-workflow/src/workflow/cli.py`. L15 hard-coded `dlops/cheese-app-*` Docker Hub images; v4 looks up the newest Artifact Registry tags.
- `stack_path` is `.pulumi/stacks/deploy-images-ml/dev.json` (`:29`).
- In a Pulumi checkpoint file, stack outputs live on the root resource of type `pulumi:pulumi:Stack`.
- If the file is missing, `download_as_text()` raises `NotFound` (404) and the CI step fails.
- It reads **whatever was last built**. CI never rebuilds these images (§6 #3).

---

## 6. Gotchas and common errors

1. **`/run-deploy-app` deploys nothing.**
   - Symptom: you follow `README.md:162`. The "App Deployment" run shows the job skipped, and the "ML Tasks" run builds a container and skips every step.
   - Cause: `app-ci-cd-gcp.yml:9` tests `'/deploy-app'`. In `/run-deploy-app` the character before `deploy` is `-`, not `/`. `/run-` still matches `ml-ci-cd-gcp.yml:9`.
   - Fix: use `/deploy-app` (`README.md:188,192`).

2. **Keyword in the wrong commit of a multi-commit push.**
   - Symptom: you pushed three commits, the first one says `/deploy-app`, and nothing deploys.
   - Cause: only `github.event.head_commit.message`, the last commit, is checked (`app-ci-cd-gcp.yml:9`). The same applies to a merged PR: the merge or squash commit's message is what counts.
   - Fix (suggested): `git commit --allow-empty -m "redeploy /deploy-app" && git push`, or put the keyword in the PR title before squash-merging.

3. **The ML pipeline runs old data-collector or data-processor code.**
   - Symptom: you edit `src/data-collector/cli.py`, push with `/run-data-collector`, and the logs on Vertex show the old behaviour.
   - Cause: `ml-ci-cd-gcp.yml` builds only `src/workflow` (`:32-35`). The step images come from the last `deploy-images-ml` state (`src/workflow/cli.py:29,67-69`), which is only updated by `deploy-ml-images.sh`, run by hand.
   - The Ansible-era version said this explicitly: `#ansible-playbook deploy-docker-images-ml.yml -i inventory.yml # Uncomment to rebuild ML images` (`git show origin/pipenv:src/deployment/run-data-collector.sh`).
   - Fix: run `sh deploy-ml-images.sh` in the deployment container first, or add a step to `ml-ci-cd-gcp.yml` that runs `cheese-app-deployment deploy-ml-images.sh` before the workflow container.

4. **A green deploy that deployed nothing** *(reasoned, not run)*.
   - Symptom: `deploy_images` fails (permission, disk, build error), but the run is green and the site is unchanged.
   - Cause: `deploy-k8s-update.sh:1-9` has no `set -e`. The K8s `pulumi up` then sees unchanged tags, reports no changes, and exits 0. That exit code propagates through `docker-entrypoint.sh:39` and `docker run`.
   - Fix: add `set -e` as the first line of the script.

5. **`no stack named 'dev' found`.**
   - Symptom: `pulumi stack select dev` errors (README B2/B3, or `deploy-ml-images.sh:2`).
   - Cause: the v4 README never runs `pulumi stack init` (compare `cheese-app-v3/README.md:420,440`). A new state bucket, or one that never had `deploy-images-ml`, has no such stack.
   - Fix: `pulumi stack init dev` once per project directory, then `pulumi up --stack dev -y`.

6. **Your L22 URL stops working after the first CD run.**
   - Symptom: the old `http://<nginx-ip>.sslip.io` is dead. A new IP appears, and HTTPS shows certificate errors for a while.
   - Cause: v3 had `deploy-k8s:setupSSL: "false"` (`cheese-app-v3/src/deployment/deploy_k8s/Pulumi.dev.yaml:7`), and v3's program ignored that key anyway: it hard-coded `setupSSL = False` (`cheese-app-v3/src/deployment/deploy_k8s/__main__.py:17`). v4 reads the key (`deploy_k8s/__main__.py:18`) and sets it to `"true"` (`deploy_k8s/Pulumi.dev.yaml:7`). The first v4 `pulumi up` replaces the NGINX Helm release and L4 LoadBalancer with a GCE Ingress, a new global IP and a managed cert. The README still describes the NGINX output (`README.md:107,126`).
   - Fix: decide which mode you want. Set `deploy-k8s:setupSSL` accordingly, and commit it **before** the first `/deploy-app`. Read the new `app_url` output.

7. **The commit message breaks the workflow (verified with bash).**
   - Symptom: the first `echo` step fails with `` unexpected EOF while looking for matching `"' ``.
   - Cause: `${{ github.event.head_commit.message }}` is pasted into the shell script *before* bash runs (`app-ci-cd-gcp.yml:12`, `ml-ci-cd-gcp.yml:12`). An unbalanced `"` in the message, as in `fix 5" screen /deploy-app`, makes the script syntactically invalid. Backticks or `$(…)` in a message are **executed**: in a local bash test, the message `` use `date +%Y` here /deploy-app `` printed `use 2026 here`. That is a script-injection hole.
   - Fix: pass the message through an env var instead: `env: MSG: ${{ github.event.head_commit.message }}` and `run: echo "Comment $MSG"`.

8. **Hard-coded instructor values.**
   - Symptom: `403 … ac215-project`, `AccessDenied` on `gs://cheese-app-ml-workflow-demo`, or `Bucket … not found`.
   - Cause: the workflow YAMLs, `Pulumi.dev.yaml` files and shell scripts embed `ac215-project`, the instructor's buckets and the SA emails (§2 table). The README only mentions one of them (`README.md:78`).
   - Fix: change them all, and commit.

9. **Artifact Registry permission.**
   - Symptom: `denied: Permission "artifactregistry.repositories.uploadArtifacts" denied` during `deploy_images`, or pods stuck in `ImagePullBackOff`.
   - Cause: v4's role list (`README.md:44-51`) drops v3's **Artifact Registry Administrator** (`cheese-app-v3/README.md:243`) in favour of "Container Registry Service Agent". That is a Google-managed service-agent role, and whether it grants Artifact Registry upload could not be confirmed. Storage Admin does not cover `*.pkg.dev`. The nodes pull as the same SA (`create_cluster.py:50`).
   - Fix: grant `deployment` Artifact Registry Administrator (or Writer).

10. **Workload Identity binding fails on a fresh cluster** *(reasoned, not run)*.
    - Symptom: `pulumi up` in `deploy_k8s` fails on `api-gsa-wi-user` with `iam.serviceAccounts.setIamPolicy` denied.
    - Cause: `gcp.serviceaccount.IAMMember` (`create_cluster.py:184-189`) sets IAM policy on the `gcp-service` SA. None of the listed `deployment` roles obviously includes `iam.serviceAccounts.setIamPolicy`; Service Account User grants `actAs`, not policy editing.
    - Fix: run that first `pulumi up` as a project Owner, or grant `deployment` "Service Account Admin" on `gcp-service`.

11. **Overlapping pushes lock the stack** *(reasoned, not run)*.
    - Symptom: the second run fails with a message that the stack is locked by another update.
    - Cause: both runs, and your laptop, share `gs://<proj>-pulumi-state-bucket`. Neither workflow declares `concurrency:`.
    - Fix: add `concurrency: { group: deploy-app, cancel-in-progress: false }` to the workflow. If a crashed run leaves a stale lock, run `pulumi cancel` in that stack.

12. **The `dockerignore` file is ignored.**
    - Symptom: `sh docker-shell.sh` sends a huge build context, and the image contains your local `pulumi-plugins/`.
    - Cause: the file is named `src/deployment/dockerignore` without the leading dot, and Docker only reads `.dockerignore`. Meanwhile `docker-shell.sh:21` creates `pulumi-plugins/` inside the build context, and `Dockerfile:72` `ADD`s everything.
    - Fix: rename it to `.dockerignore`.

13. **Every deploy rebuilds everything, slowly, and fills the registry.**
    - Symptom: long "Run Deploy App" steps, and Artifact Registry growing by several GB per deploy.
    - Causes:
      - A new timestamp on every run (`deploy_images/__main__.py:13`).
      - No layer cache on a fresh runner. The API image installs `tensorflow==2.19.0` (`src/api-service/pyproject.toml:13`).
      - `retain_on_delete=True` (`:31`).
    - Fixes: use a content-based tag (for example `${{ github.sha }}` passed in as config), add an Artifact Registry cleanup policy, and consider build caching.

14. **The API rollout can stall on its ReadWriteOnce volume** *(reasoned, not run)*.
    - Symptom: `pulumi up` waits for `deployment/api` until it times out. The new pod shows `Multi-Attach error`.
    - Cause: the api pod mounts `persistent-pvc` with `ReadWriteOnce` (`setup_containers.py:24,265-272,286-290`). The default RollingUpdate starts the new pod *before* stopping the old one. If the scheduler places it on the second autoscaled node, the disk cannot attach.
    - Fix: give the api Deployment `strategy=Recreate`, or drop the RWO volume. Also don't scale `api` past 1 replica for MS5 scaling demos; scale `frontend` instead.

15. **Every `/run-ml-pipeline` leaves another billed endpoint.**
    - Symptom: the Vertex AI Online prediction list grows, and so does the bill.
    - Cause: `deployed_model.deploy(...)` without an `endpoint=` argument (`src/workflow/model.py:95-103`) creates a new endpoint each time, with `min_replica_count=1`.
    - Fix: undeploy and delete after each demo, or change the code to reuse one endpoint.

16. **`python cli.py --model_deploy` crashes** (not reachable from CI, but tempting to try locally).
    - Symptom: `TypeError: model_deploy() got an unexpected keyword argument 'bucket_name'`.
    - Cause: `src/workflow/cli.py:199` calls `model_deploy(...)`, which resolves to the CLI function defined at `:193`, not the component imported as `model_deploy_job` (`:18`). The [L15 guide](L15-vertex-ml-workflows.md) documents the same bug in `ml-workflow/src/workflow/cli.py:154,160`.
    - Fix: call `model_deploy_job(bucket_name=GCS_BUCKET_NAME)`.

17. **Two `PULUMI_BUCKET` formats.** `deployment` expects `gs://…` (`docker-shell.sh:15`, `app-ci-cd-gcp.yml:55`; used by `gsutil` and `pulumi login`). `workflow` expects a bare bucket name (`ml-ci-cd-gcp.yml:54`, `src/workflow/docker-shell.sh:13`; used by `storage.Client().bucket()`). Copy-pasting between them gives a GCS API error when `cli.py` downloads the state file (if `gs://` reaches `cli.py`; the client does not strip the prefix), or `gsutil` and `pulumi login` failures (if the prefix is missing in `deployment`). This is *(reasoned, not run)*.

18. **Secrets in the repo.**
    - `src/frontend-react/.env.development:5` and `.env.production:3` commit a `NEXTAUTH_SECRET`.
    - The Actions secret holds a long-lived key of a very powerful SA. Anyone who can push a workflow file to your repo can read it.
    - Fixes: regenerate the NextAuth secret for your own deployment. For your project, consider keyless GitHub→GCP auth: Workload Identity Federation, `workload_identity_provider` in `google-github-actions/auth`.

19. **Old action versions.** `google-github-actions/auth@v1` and `setup-gcloud@v1` (`app-ci-cd-gcp.yml:19,23`) are older majors; newer ones exist. Whether v1 still runs without warnings on today's runners was not checked. If a run warns about deprecated Node versions, bump the majors.

---

## 7. Where this sits in the course

### What the previous lectures gave you, and what v4 adds
- **L20 (Pulumi, cheese-app-v3):** the `deployment` toolbox container, Pulumi with a GCS state bucket, the `deploy_images` stack with timestamp tags, and a single-VM deployment.
- **L21 (GitHub Actions CI, cheese-app-ci-cd):** workflow anatomy, runners, secrets, and test jobs on every push or PR (`cheese-app-ci-cd/.github/workflows/ci.yml`).
- **L22 (GKE, cheese-app-v3):** the `deploy_k8s` stack: network, cluster, Deployments, Services, PVCs, loader Job, NGINX ingress and Workload Identity, all run by hand from your laptop.
- **L15 (Vertex AI ML workflow, ml-workflow):** data-collector and data-processor containers, the trainer package, KFP pipelines, and Vertex endpoints.
- **L23 adds** the glue: a push-triggered runner that executes the L20/L22 toolbox non-interactively (app lane), and the L15 pipeline CLI (ML lane), with image tags flowing through Pulumi state.
- **Next:** there is no later tutorial. Next come MS5 (due 12/11) and the 12/10 showcase (`milestone5.md`). MS5 asks for more than v4 shows (`milestone5.md:41-56`):
  - unit tests across every container, and integration tests of the API on every PR;
  - deploy **on merge to main**, not on a keyword;
  - ≥70% coverage;
  - automated retraining triggered by new data;
  - validation thresholds before deploying a model.

  v4 is the skeleton; L21's `ci.yml` is the missing CI half.

### Whole-course recap map (which lecture built which box)
```
 L1 venv/uv, VM ──> L2-L4 containers, compose, networks ──> L10 cloud auth, buckets, SA keys (secrets/)
        │                                 │
        ▼                                 ▼
 L5 RAG / ChromaDB ─────────► src/vector-db (loader Job) ─────────┐
 L6-L7 agents, harness ─────► api routers llm_agent / newsletter ─┤
 L8 finetuning (Gemini) ────► api llm_chat (base gemini-2.0-flash-001, not a tuned model) ┤
 L13 training (W&B, Vertex) ► trainer package ──┐                 │
 L15 ML workflow (KFP) ─────► src/workflow, data-collector/processor ──► VERTEX PIPELINES ──► endpoint (unused by app)
 L18 APIs + frontend ───────► src/api-service + src/frontend-react ┤
 L9/L21 tests + CI ─────────► (not wired into v4 — add for MS5)    │
 L20 Pulumi toolbox ────────► src/deployment, deploy_images ───────┤
 L19/L22 Kubernetes ────────► deploy_k8s (GKE, ingress, PVC, WI) ──┤
 L23 CD (this) ─────────────► .github/workflows: git push ──► runner ──► Pulumi ──► GKE  (+ /run-* ──► Vertex)
 Not in v4: L11 DVC/labeling, L14 Cloud Run/Functions (alternative serving), L16-L17 tradeoffs & monitoring
```
The arrows into `src/...` folders are based on the course map (`tutorials_demo.md`) and on v4's folder names. Only `src/workflow/` was diffed against its L15 origin, so treat the other arrows as provenance by topic, not a file-level diff. One check: the API's chat, RAG and agent utils all call the base `gemini-2.0-flash-001` (`src/api-service/api/utils/llm_utils.py:22`, `llm_rag_utils.py:23`, `llm_agent_utils.py:21`), so the L8 fine-tuned model is not wired in.

### v3 → v4 diff (main vs main)
`git diff --no-index --stat` over `git archive HEAD` of both repos (abridged). Total: **66 files changed, 5498 insertions(+), 1011 deletions(-)**.
```
 /dev/null => v4/.github/workflows/app-ci-cd-gcp.yml              |   56 +
 /dev/null => v4/.github/workflows/ml-ci-cd-gcp.yml               |   96 +
 {v3 => v4}/README.md                                             |  689 +--   (rewritten)
 /dev/null => v4/images/ci-cd.png                                 |  Bin
 v3/src/api-service/_test.py => /dev/null                         |  379 -
 {v3 => v4}/src/api-service/api/service.py                        |    2 +-    ("3.0" -> "1.0.1")
 /dev/null => v4/src/data-collector/* (9 files)                   |  new
 /dev/null => v4/src/data-processor/* (10 files)                  |  new
 /dev/null => v4/src/workflow/* (14 files)                        |  new
 {v3 => v4}/src/deployment/Dockerfile                             |    2 +     (ADD . /app)
 {v3 => v4}/src/deployment/docker-entrypoint.sh                   |   12 +-    (run "$@" as a script)
 {v3 => v4}/src/deployment/docker-shell.sh                        |   10 +-    (ML env vars, 2 new mounts)
 /dev/null => v4/src/deployment/deploy-k8s-update.sh              |    9 +
 /dev/null => v4/src/deployment/deploy-ml-images.sh               |    3 +
 /dev/null => v4/src/deployment/deploy_images_ml/* (3 files)      |  new
 {v3 => v4}/src/deployment/deploy_k8s/Pulumi.dev.yaml             |    2 +-    (setupSSL false -> true)
 {v3 => v4}/src/deployment/deploy_k8s/__main__.py                 |   14 +-    (setupSSL/domain from config)
 {v3 => v4}/src/deployment/deploy_k8s/setup_containers.py         |   31 ++-    (BackendConfig + NEG annotations)
 {v3 => v4}/src/deployment/deploy_k8s/setup_loadbalancer.py       |    7 +-    (domain option)
 {v3 => v4}/src/deployment/deploy_k8s/setup_loadbalancer_ssl.py   |   17 +-    (gce class annotation, v1beta1, domain)
 v3/src/deployment/{.docker-tag,.python-version,README.md,deploy-k8s-tic-tac-toe.yml} => /dev/null
 /dev/null => v4/src/deployment/*/__pycache__/*.pyc (6 files)     |  Bin       (accidentally committed)
 {v3 => v4}/src/frontend-react/src/components/layout/Header.jsx   |    2 +-    (bg-black/90 -> bg-sky-800)
```
The meaningful changes:
1. **CD workflows** (new).
2. **Toolbox made CI-runnable:** code baked in (`Dockerfile:72`), entrypoint runs a script (`docker-entrypoint.sh:32-40`), one-shot deploy script.
3. **ML lane:** `deploy_images_ml` plus `src/workflow`. The workflow is L15's code plus the Pulumi-state lookup in `cli.py:28-57`.
4. **Load balancer switched to Google HTTPS by config**, with a BackendConfig health check for the `/api-service` root path.
5. Demo edits to the version string and header colour.

In-class history: the 2025-12-02 commits `42d360c` → `033f187` show the instructor discovering that the ML workflow still called `sh run-ml-pipeline.sh` and `sh run-data-processor.sh`, scripts that no longer existed after the Pulumi refactor. The final commit replaced them with `python cli.py --pipeline` and `--data_processor` (`git show 033f187`).

---

## 8. Exercises

**E1 (hands-on, predict then run).** Set `APP_VERSION = 2.3` in `Common.js:3` and change `service.py:36` to `{"version": "2.1"}`. Commit with the message `Release /Deploy-App` (capital letters). Before pushing, predict: does the app redeploy, and what will the footer show?

*Worked answer:*
- Yes. GitHub's `contains()` is case-insensitive, so `/Deploy-App` matches `'/deploy-app'` (`app-ci-cd-gcp.yml:9`).
- After the run, all three images get a new timestamp tag and the Deployments roll. The footer then shows `Frontend version: 2.3` (a JS number, from the rebuilt bundle) and `API version: 2.1`, fetched from `/api-service/status` (`Footer.jsx:18-21`, `DataService.js:64`).
- If the frontend still shows the old number, hard-refresh. The browser may cache the old JS chunk.

**E2 (debugging).** A teammate's push of `fix 5" phone layout /deploy-app` produced a red run that failed in the very first step with `` unexpected EOF while looking for matching `"' ``. Nothing was deployed. Why, and how do you make the workflow immune?

*Worked answer:*
- `${{ … }}` expressions are substituted into the `run:` text before bash parses it. The step `echo "Comment ${{ github.event.head_commit.message }}"` (`app-ci-cd-gcp.yml:12`) becomes `echo "Comment fix 5" phone layout /deploy-app"`, which has an unbalanced quote. Bash exits with code 2, and the job stops.
- This exact failure was reproduced with a local bash snippet. A message with `` `cmd` `` would even execute `cmd`.
- Fix: map the expression into an environment variable and reference that:
  ```yaml
  - env:
      MSG: ${{ github.event.head_commit.message }}
    run: echo "Comment $MSG"
  ```

**E3 (debugging).** You pushed two commits together: `header colour /deploy-app`, then `typo in README`. Nothing deployed. Explain, and give two fixes.

*Worked answer:*
- `github.event.head_commit` is the **last** commit of the push, `typo in README`, which lacks the keyword.
- Fix 1: `git commit --allow-empty -m "redeploy /deploy-app" && git push`.
- Fix 2: amend the last commit's message before pushing (`git commit --amend`).
- Long-term fix: stop relying on messages. Trigger on push to `main` with `paths:` filters, or add `workflow_dispatch` for a manual "Run workflow" button.

**E4 (conceptual + hands-on).** Make the ML lane actually use new collector code. Write the extra step you would add to `ml-ci-cd-gcp.yml` before "Run Data Collector".

*Worked answer:*
- The workflow container reads the newest tag from `deploy-images-ml/dev.json` (`src/workflow/cli.py:29,67-69`). So the step must update that stack first, by reusing the deployment toolbox exactly like the app workflow does.
- Copy "Build Deployment Container" (`app-ci-cd-gcp.yml:32-35`) and the `docker run` block (`:37-56`), with two changes: guard it with `if: contains(github.event.head_commit.message, '/run-')`, and replace the final `deploy-k8s-update.sh` with `deploy-ml-images.sh`.
- The mounts `/data-collector` and `/data-processor` (`:46-47`) already match `deploy_images_ml/__main__.py:20,40`'s `../../data-collector` and `../../data-processor`, resolved from `/app/deploy_images_ml`.
- Expected effect: a new `:<timestamp>` for both ML images in the state file, then the collector step compiles a pipeline pointing at that tag. You can confirm it by grepping the compiled `data_collector.yaml` for `image:`.

**E5 (debugging, reasoned).** A `/deploy-app` run is green, but the site did not change. The "Run Deploy App" log shows an error from the `deploy_images` update, then `deploy_k8s` reporting no changes. Why green?

*Worked answer:*
- `deploy-k8s-update.sh` has no `set -e` (`:1-9`). Bash keeps going after the failed `pulumi up`, and the script's status is that of the last command, the K8s update.
- The K8s update had nothing to do: the images stack did not export new tags, so the StackReference returned the old ones. It therefore exits 0.
- `docker-entrypoint.sh:39` runs the script as its last command, so 0 becomes the container's and the step's exit code.
- Fix: add `set -e` (or `set -euo pipefail`) at the top of `deploy-k8s-update.sh`.

**E6 (conceptual).** Why did v4 have to add `ADD --chown=app:app . /app` to the deployment Dockerfile, when v3 worked fine without it?

*Worked answer:*
- Locally, `docker-shell.sh:37` bind-mounts your working tree onto `/app`, so the Pulumi programs are visible in the container.
- The CI `docker run` (`app-ci-cd-gcp.yml:38-56`) mounts the app folders and `/workspace`, but nothing at `/app`. Without baking the code in, `/app` would contain only `pyproject.toml` and `uv.lock` (from the `COPY` at `Dockerfile:67`). Even the entrypoint would be missing: `ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]` (`Dockerfile:75`) is a path relative to `WORKDIR /app`, and v3 only had that file through the mount. So the container would fail before reaching `deploy-k8s-update.sh`, which would not exist either.
- An alternative design would mount `-v $GITHUB_WORKSPACE/src/deployment:/app` in CI. Baking the code makes the image self-contained.

**E7 (design, MS5).** Turn v4 into what MS5 asks for: tests on every PR, and deploy on merge to `main`. Sketch the workflow structure.

*Worked answer:*
- One workflow with `on: pull_request: branches: [main]` runs L21's build, lint and test jobs (`cheese-app-ci-cd/.github/workflows/ci.yml`) per container, with coverage ≥70%.
- Branch protection on `main` requires those checks.
- A second workflow with `on: push: branches: [main]`, and no message filter, has a `test` job and a `deploy` job with `needs: test`. The deploy job runs the toolbox with `deploy-k8s-update.sh`, plus `set -e`.
- Add `concurrency: { group: deploy-main, cancel-in-progress: false }` to serialize Pulumi updates.
- Optionally add `paths:` filters, so that ML-only changes trigger the ML lane instead.
- Replace the JSON key with Workload Identity Federation.

**E8 (hands-on, trace).** After one successful deploy, find the *same* image tag in three places and show they agree.

*Worked answer, inside the deployment container (commands not in the README):*
1. In `/app/deploy_images`, run `pulumi stack output cheese-app-api-service-tags --stack dev`. It prints a list with `…/cheese-app-api-service:<ts>`.
2. In the Actions log of the "Run Deploy App" step, the `Outputs:` of the images update show the same `<ts>`.
3. After `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <proj>`, run `kubectl get deploy api -n cheese-app-namespace -o jsonpath='{.spec.template.spec.containers[0].image}'`.

All three show the same string because of the StackReference (`setup_containers.py:10-12`) and `.apply(lambda tags: tags[0])` (`:276-278`). If (3) shows an older tag, the K8s update failed or is still rolling. Check with `kubectl rollout status deployment/api -n cheese-app-namespace`.

---

## 9. Errata and open questions

### Errata (with evidence)
1. **Wrong trigger keyword in prose.** `README.md:162` says the action runs when the commit has `/run-deploy-app`. The workflow requires `/deploy-app` (`app-ci-cd-gcp.yml:9`). `README.md:188,192` are correct.
2. **Wrong file location and content for the API version.** `README.md:165-171` says "line 29" and shows `@app.get("/status")` returning `"version": "2.0"`. The real code is `@api_app.get("/status")` at `src/api-service/api/service.py:34`, returning `{"version": "1.0.1"}` at `:36`.
3. **Wrong line for the header colour.** `README.md:181` says line 69. The `className` is at `Header.jsx:41` (line 69 is `aria-label="Toggle menu"`), and its current value is `bg-sky-800`, not the README's snippet value.
4. **Non-existent output name.** `README.md:107,116,126` tell you to copy `nginx_ingress_ip`. v4 exports `ip_address` and `app_url` (`deploy_k8s/__main__.py:54-55`). Since `setupSSL` is `"true"` (`Pulumi.dev.yaml:7`), there is no NGINX controller at all, and `http://<ip>.sslip.io` (`README.md:127`) redirects to HTTPS. The name was already stale in v3: `cheese-app-v3/README.md:505` shows `nginx_ingress_ip`, while v3's code exports `ip_address` (`cheese-app-v3/src/deployment/deploy_k8s/__main__.py:48`).
5. **Missing setup steps.** The README omits:
   - `pulumi stack init dev` (compare `cheese-app-v3/README.md:420,440`);
   - creating the Artifact Registry repository (no code does it);
   - creating `gcp-service` and `ml-workflow` SAs, the ML buckets and the trainer tarball;
   - running `deploy-ml-images.sh` (required by `src/workflow/cli.py:29`);
   - editing the hard-coded project, bucket and SA values in both workflow YAMLs and in the `Pulumi.dev.yaml` files;
   - for the "If you have a domain" path (`README.md:105-123`), setting `deploy-k8s:domain` so the Ingress host and managed certificate use the domain (`deploy_k8s/__main__.py:19`, `setup_loadbalancer_ssl.py:18-21`);
   - any cleanup.
6. **Role list.** `README.md:47` replaces v3's Artifact Registry Administrator (`cheese-app-v3/README.md:243`) with "Container Registry Service Agent", a service-agent role. Pushing to and pulling from `us-docker.pkg.dev` likely needs an Artifact Registry role (see open question 2).
7. **"CI/CD" naming.** Both workflows are named "Continuous Integration and Continuous Deployment" (`:1`), and the section is "CI/CD", but `README.md:157` concedes no CI is implemented. No tests run.
8. **`images/ci-cd.png` overstates the integration.** It draws Model Deploy → Backend API. The API loads a fixed model from `github.com/dlops-io/models` (`llm_cnn_utils.py:124`), and the trainer uses a fixed dataset (`ml-workflow/src/model-training/package/trainer/task.py:103-104`), not the processor's output.
9. **Leftover test text.** `README.md:208` reads `AJ TESTING !!! AGAIN` (commits `42d360c`, `e0ef89c`, `82f5d57`). `.gitignore:1` reads `# misc added some comment` (commit `1020f0e`).
10. **Mis-named ignore file.** `src/deployment/dockerignore` lacks the leading dot and has no effect.
11. **Committed bytecode.** `src/deployment/deploy_images/__pycache__/__main__.cpython-313.pyc` and five `deploy_single_vm/__pycache__/*.pyc` files are tracked, despite `*.pyc` in `src/deployment/.gitignore:3`.
12. **Bugs and stale comments:**
    - `src/workflow/cli.py:199` calls the wrong `model_deploy` (§6 #16).
    - `src/data-processor/cli.py:19` comments out `import tfrecords`, yet `:93` uses it, so `--prepare` would raise `NameError` (not used by the pipeline, which runs only `--clean`). So `README.md:6`'s "converts images to TF Records" does not happen in v4's pipeline.
    - `deploy_images/__main__.py:62,73-74` reuses the variable `frontend_image` for the vector-db image (harmless).
    - `deploy_images_ml/__main__.py:17,37` comments say "API Service" and "Frontend".
    - `setup_containers.py:206` says "Retry up to 4 times" for `backoff_limit=3`.
    - `setup_containers.py:269` calls the PersistentVolumeClaim "Temporary storage (lost on restart)", and `:289` calls its mount "Temporary file storage"; a PVC survives pod restarts.
13. **Compiled pipeline YAMLs are stale artefacts.** `src/workflow/data_processor.yaml:14` still points at `dlops/cheese-app-data-processor`, while `data_collector.yaml:16` and `pipeline.yaml:62,74` pin the instructor's images `us-docker.pkg.dev/ac215-project/cheese-app-repository/…:20251128233532`. They are overwritten on every run (`cli.py:94,141,302`), so they are only misleading to read.
14. **Course-site numbering.** `tutorials_demo.md:288` calls this "Lecture 23", while the schedule (`_modules/week-14.md`) lists "Final Deployment and Review" as "Lecture 22" on Dec 1.

### Open questions (could not determine from the sources)
1. What Ed lesson 166048 adds beyond the README (slides, demo recording). Ed was not accessible.
2. Whether "Container Registry Service Agent" alone lets the `deployment` SA push to Artifact Registry and lets nodes pull, since `Storage Admin` does not cover `*.pkg.dev`. IAM was not tested.
3. Whether Pulumi replaces the `vector-db-loader` Job cleanly on each deploy. Its pod template changes because the image tag changes, and Kubernetes Job templates are immutable. The instructor's consecutive `/deploy-app` commits on 2025-11-29 and 2025-12-02 suggest it works, but the run logs were not visible.
4. How long a CD run takes on a GitHub-hosted runner, and whether the runner's disk is enough for the TensorFlow-based API image plus the toolbox image. Not measured.
5. Whether a Google-managed certificate for an `<ip>.sslip.io` hostname becomes Active in practice. The instructor removed the custom domain in commit `a533054` while keeping SSL on, but there is no evidence of the resulting certificate status.
6. Whether `google-github-actions/auth@v1` and `setup-gcloud@v1` still run cleanly on today's runner images.
7. The AWS variant (`dlops-io/cheese-app-aws`, linked at `tutorials_demo.md:294`) was not available locally.

---

## Links

- README sections (pinned commit): [Cheese App - Automation](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#cheese-app---automation) · [Setup Environments](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#setup-environments) · [Ensure Kubernetes Cluster is Up](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#ensure-kubernetes-cluster-is-up) · [Setup GitHub Action Workflow Credentials](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#setup-github-action-workflow-credentials) · [Continuous Integration and Continuous Deployment (CI/CD)](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#continuous-integration-and-continuous-deployment-cicd) · [Frontend & Backend Changes](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#frontend--backend-changes) · [ML Component Changes](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/README.md#ml-component-changes) · latest README on [`main`](https://github.com/dlops-io/cheese-app-v4#cheese-app---automation)
- Workflows (pinned commit): [`app-ci-cd-gcp.yml`](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/.github/workflows/app-ci-cd-gcp.yml) · [`ml-ci-cd-gcp.yml`](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/.github/workflows/ml-ci-cd-gcp.yml)
- Ed lesson: [L23 · Final Deployment and Review](https://edstem.org/us/courses/97373/lessons/166048/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/) · [Milestone 5](https://harvard-iacs.github.io/2026-AC215/milestone5/)
- Colab notebooks: none for L23.
- Previous lecture: [L22 · Scaling: Kubernetes (cloud)](L22-kubernetes-cloud.md) (the GKE cluster this lecture automates)
- Next lecture: none. L23 is the last lecture; MS5 and the final showcase follow.
- Referenced in §7: [L15 · ML Workflows with Vertex AI](L15-vertex-ml-workflows.md) · [L20 · Deployment: Pulumi](L20-deployment-pulumi.md) · [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md)
