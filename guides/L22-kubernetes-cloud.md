# L22 · Scaling: Kubernetes (cloud) — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166047/) · Tutorial: [`dlops-io/cheese-app-v3`](https://github.com/dlops-io/cheese-app-v3) `main` @ [`3ecef56`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a) (README sections "Deployment with Scaling using Kubernetes" and "Create & Deploy Cluster", plus the optional warm-up "Create Simple Kubernetes Cluster Tutorial"; not branch `cluster-updates`, see §7) · Colab: none for this lecture · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 把 L20 跑在一台 VM 上的四个 cheese-app container（Next.js `frontend`、FastAPI `api`、ChromaDB `vector-db`、一次性的 `vector-db-loader`）搬到 managed Kubernetes（GKE）上，全部用 Pulumi Python 描述。还是 L20 那个 deployment container，新 project 叫 `deploy_k8s`：custom VPC + Cloud Router + **Cloud NAT**、regional GKE cluster（**private nodes**、**Workload Identity**）、一个 node pool（`n2d-standard-2`，`us-central1-a`，autoscaling 1–2 nodes）、namespace `cheese-app-namespace`、2 个 PVC、3 个 Deployment + ClusterIP Service、1 个 loader Job，再用 Helm 装 F5 NGINX Ingress Controller。最后 app 在 `http://<LB-IP>.sslip.io`。
- **Idea 1 · desired state：** 你不“运行” container，只是把 object 写进 API server。Deployment → ReplicaSet → Pod，controller 一直对比 desired 和 actual：delete 一个 Pod，ReplicaSet 马上补一个；换 image tag 就是 rolling update。Job 是 run-to-completion 版本。Pulumi 会等 loader Job *Complete* 之后才去建 API Deployment。
- **Idea 2 · label、Service、cluster DNS、namespace：** Pod 会死、IP 会变；Service 用 label selector（`run: api` 等）给一个稳定的名字和 virtual IP，所以 API 直接连 `vector-db:8000`。`kubectl` 默认只看 `default` namespace，记得加 `-n cheese-app-namespace`。
- **Idea 3 · 一个 request 怎么走：** sslip.io DNS → GCP network load balancer → NGINX controller Pod（看 **Host header** + path prefix）→ Service → Pod。`/api-service` prefix **不会被剥掉**，所以 API 用 `ROOT_PATH=/api-service` mount 所有 route；调 API 的是**浏览器**，不是 frontend Pod。
- **Idea 4 · 没有 key file 的 identity：** kubeconfig 里的 user 是 `gke-gcloud-auth-plugin` exec plugin，没有密码。Pod 走 Workload Identity：KSA `api-ksa` 上的 annotation + IAM 的 `roles/iam.workloadIdentityUser` binding，两边都要有，Pod 才能以 GSA `gcp-service` 的身份调 Vertex AI。L20 的 `gcp-service.json` 在 cluster 里用不到。
- **Idea 5 · 两层 scaling：** Pod 层（`replicas`、HPA）和 node 层（cluster autoscaler，这里 1–2 nodes）。scheduler 按 resource **requests** 打包（一个 frontend Pod 就 request 2 Gi）。`deploy_k8s` 里**没有 HPA，也没有 `replicas` 字段**，只有 node autoscaler；Milestone 5 要你 demo scaling，自己用 `kubectl scale`。PVC 是 ReadWriteOnce：`api` / `vector-db` 跨 node 多开会卡在 Multi-Attach error，加 node 也没用。
- **最费时间的坑：** ① `deployment` SA 那 6 个 role 都不能改 service account 的 IAM policy，`pulumi up` 很可能停在 `api-gsa-wi-user` 报 403：先以 project owner 身份在 `gcp-service` 上给它 `roles/iam.serviceAccountAdmin`（§2）。Artifact Registry 的 `cheese-app-repository` 也没有任何 code 去建。② kubeconfig 只活在这次 `--rm` container 里，重开 container 后 `kubectl` 报 `connection refused`：跑 `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>`。
- **README 过时的地方和易错点：** debugging 段的 namespace `cheese-app-cluster-namespace` 和 init container `wait-for-chromadb` 都已经不存在；outputs block 里的 `nginx_ingress_ip` 现在叫 `ip_address`；用裸 IP 打开只会得到 NGINX 的 404，一定要用 `app_url`（sslip.io 名字）。另外 code 里写死的 `gemini-2.0-flash-001` 按 L20 guide 的核查已于 2026-06-01 retired：`/api-service/status` 正常但 chat 失败时，先怀疑 model，再查 Workload Identity。
- **做完要删（当天就删）：** cluster 开着大约 $5–8/天。在 `/app/deploy_k8s` 跑 `pulumi destroy --stack dev --refresh -y`，再用 `gcloud compute forwarding-rules list`、`gcloud compute disks list`（找 `pvc-…`）、`gcloud compute firewall-rules list` 等查漏网的 LB 和 disk（这些删除是 asynchronous 的）；Artifact Registry 的 image 是 `retain_on_delete=True`，要手动删；L20 的 VM 和 warm-up 的 `test-cluster` 如果还在，也要删。

## At a glance

**What you build.** The same four cheese-app containers that ran on one VM in L20 (Next.js frontend, FastAPI API, ChromaDB and a one-shot loader) run on a managed GKE cluster that a new Pulumi project, `deploy_k8s`, describes in Python: a private-node regional cluster with a 1–2-node autoscaling pool behind Cloud NAT, Workload Identity for the API's Vertex AI calls, two persistent volumes, three Deployments with Services, a loader Job, and an NGINX Ingress controller behind a GCP load balancer. You end with the app at `http://<LB-IP>.sslip.io`, explore it with `kubectl`, scale the frontend by hand, and remove everything with one `pulumi destroy`.

**What "scaling" means in this code.** The program has **no HorizontalPodAutoscaler and no `replicas` field**. Every Deployment runs one Pod. The only automatic scaling is the **node pool autoscaler** (1–2 nodes, `src/deployment/deploy_k8s/create_cluster.py:63-66`). Manual and Pod-level scaling (`kubectl scale`, HPA) are explained in §3.6 and practised in Step 12 and §8. Milestone 5 asks you to demonstrate manual scaling (`milestone5.md:39`).

**Time needed** (estimate; the stack was not run for this guide). Optional warm-up: about 20 minutes. One-time setup (APIs, the extra IAM role, starting the container): about 30 minutes. Images: nothing if you built them in L20; otherwise tens of minutes under amd64 emulation on Apple Silicon (the API image installs TensorFlow). `pulumi up` for the cluster and app: roughly 15–25 minutes. Exploring, scaling and one redeploy: about 1 h. Destroy and the leftover checks: about 15 minutes. In total about 2.5–3 h; plan to destroy the same day.

**Prerequisites.**
- A GCP project with billing enabled, and its project ID. The README commands and `src/deployment/docker-shell.sh:13` hard-code the instructor's `ac215-project`.
- Docker Desktop and `git`. Everything else (gcloud, kubectl 1.34, Helm, Pulumi, `gke-gcloud-auth-plugin`, uv) lives in the L20 deployment container.
- From L20: the `deployment` service account and its key at `secrets/deployment.json`, **next to** the repo folder. With a clone at `~/Desktop/AC215/cheese-app-v3`, the deployment container looks for secrets in `~/Desktop/AC215/secrets/` (three levels up from `src/deployment`, `src/deployment/docker-shell.sh:9`). The `gcp-service` account must exist too, but only its e-mail is used here.
- APIs: Compute Engine, Service Usage, Cloud Resource Manager, Artifact Registry, **Kubernetes Engine**, plus **Vertex AI** for the running app (§2).
- One IAM grant the README does not list: `deployment` needs permission to edit `gcp-service`'s IAM policy (§2).
- Background: containers and ports (L2–L4), service accounts (L10), the app itself (L18), and the deployment toolbox, the `deploy_images` stack and the single-VM deployment (L20).

**What it costs.** About **$5–8 per day** while the cluster is up (approximate list prices, not from the repo): the regional cluster's management fee (about $0.10/h; GKE's free-tier credit only covers zonal and Autopilot clusters), 1–2 `n2d-standard-2` nodes (about $0.085/h each plus a 50 GB boot disk), the external network load balancer (about $0.025/h plus traffic), Cloud NAT, and two small persistent disks. Artifact Registry images (about $0.10/GB-month) and L20's VM, if it still runs, are **not** removed by this lecture's `pulumi destroy`. Details in §2.

**Tear down, exactly** (details in §2 and §4 Step 14):
1. Inside the deployment container: `cd /app/deploy_k8s`, then `pulumi destroy --stack dev --refresh -y` (README line 511). Checkpoint: `Resources: N deleted`.
2. Check for leftovers, because load-balancer and disk deletions are asynchronous: `gcloud container clusters list`, `gcloud compute forwarding-rules list`, `gcloud compute disks list` (look for `pvc-...` disks), `gcloud compute addresses list` and `gcloud compute firewall-rules list` (look for `k8s-...` rules on `cheese-app-vpc`). Delete anything left by hand, then run `pulumi destroy` again.
3. Artifact Registry images: delete them in the console. `deploy_images` uses `retain_on_delete=True` (`deploy_images/__main__.py:31`).
4. L20's VM, if still running: `pulumi destroy` in `deploy_single_vm`.
5. The warm-up cluster, if you made one: `kubectl delete -f deploy-k8s-tic-tac-toe.yml`, then `gcloud container clusters delete test-cluster --zone us-east1-c`.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Course-site entry:** `tutorials_demo.md:279-284` → "Lecture 22: Scaling: Kubernetes (cloud)", one tutorial: "Deployment with Scaling using Kubernetes (cloud)", linking to `cheese-app-v3#deployment-with-scaling-using-kubernetes`.
- **Repositories used:**

| repo | branch | commit (full hash) | commit date | role |
|---|---|---|---|---|
| `dlops-io/cheese-app-v3` | `main` (default) | `3ecef56fea879ac480d260c0906cd95baf05179a` | 2025-11-28 16:00:06 -0500 | **the tutorial** |
| `dlops-io/cheese-app-v3` | `cluster-updates` | `e55178c0f66d8636d00e7deea7e744640bb8d595` | 2025-11-20 22:45:10 +0530 | a TA's experimental K8s branch, compared in §7 |
| `dlops-io/cheese-app-v3` | `pipenv` | `0012c9a512b1a266f4c87fad09d84a3b52470f5b` | 2025-04-23 08:26:16 -0400 | the older Ansible version of the same K8s deployment (comparison only) |
| `dlops-io/cheese-app-v4` | `main` (default) | `033f18713b9e1e7985a3080e85edab3ff01cefef` | 2025-12-02 14:13:03 -0500 | next lecture (L23); used to show what changes next and to support two errata |
| `dlops-io/llm-rag` | `main` (default) | `e17a39f35bc07b440f573def480adaf4703f8b91` | 2026-10-07 21:34:23 -0400 | evidence only (ChromaDB mount path, §9) |

- **README sections covered** (in `cheese-app-v3/README.md`):
  - [`#deployment-with-scaling-using-kubernetes`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#deployment-with-scaling-using-kubernetes), README lines 392–434. It contains `#apis-to-enable-in-gcp-for-project` (396), `#start-deployment-docker-container` (404) and `#build-and-push-docker-containers-to-gcr` (415).
  - [`#create--deploy-cluster`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#create--deploy-cluster), README lines 436–512. This is a sibling **H2**, not a subsection, so the course-site link alone does not land on it. It contains `#try-some-kubectl-commands` (476), `#if-you-want-to-shell-into-a-container-in-a-pod` (488), `#view-the-app` (495) and `#delete-cluster` (509).
  - Optional warm-up: [`#create-simple-kubernetes-cluster-tutorial`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#create-simple-kubernetes-cluster-tutorial), README lines 517–581 (tic-tac-toe on a plain `gcloud` cluster).
  - The K8s half of [`#debugging-containers`](https://github.com/dlops-io/cheese-app-v3?tab=readme-ov-file#debugging-containers), README lines 618–657. It is partly outdated (§9).
  - Reused from L20: service accounts, README lines 236–259.
- **Path convention:** every `path:line` is relative to the `cheese-app-v3/` repository root at the `main` commit above, unless a prefix names another source: `cluster-updates:` (that branch), `pipenv:` (that branch), `cheese-app-v4:` or `llm-rag:`. `tutorials_demo.md` and `milestone5.md` are files of the course-site source (`2026-AC215`). Every reference was checked with `sed -n`/`grep -n`. Code blocks headed `path:start-end` were copied from those exact line ranges and checked mechanically. Verified against the repos on 2026-10-13 (adversarial check).
- **Ed lesson:** not accessible when these sources were checked. This guide is built from the course site and the repositories.
- **Colab notebooks:** none for this lecture.

</details>

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept; replace `ac215-project` with your project ID and `api-c4fb784b-2llgs` with your own Pod name). Plain items are console clicks or checks. Items marked *(extra)* are not in the README; they come from §2, §3, §4, §6 and §8 of this guide. From `sh docker-shell.sh` on, everything runs inside the deployment container (prompt in `/app`). The warm-up sits at the end of the README but is listed first, because it is the gentler first contact with `kubectl`. The Kubernetes part of "Debugging Containers" (README lines 618–657) comes after "Delete Cluster" (README lines 509–512) in the README; here it is listed before it, because it needs the running cluster.

### Before the README *(extra)*

- [ ] `git clone https://github.com/dlops-io/cheese-app-v3.git` — *(extra)* get the code (skip if you kept your L20 clone). If you use this workspace's `tools/sync_tutorials.py`, the clone is `tutorials/cheese-app-v3`.
- [ ] `git -C cheese-app-v3 rev-parse HEAD` — *(extra)* compare with `3ecef56fea879ac480d260c0906cd95baf05179a`; a different hash means the repo has changed since this guide was made.
- [ ] *(extra)* Check that `deployment.json` is in the `secrets/` folder **next to** the repo folder (`~/Desktop/AC215/secrets/` for a clone at `~/Desktop/AC215/cheese-app-v3`).

### Create Simple Kubernetes Cluster Tutorial *(optional warm-up, README lines 517–581)*

*API's to enable in GCP for Project* (README lines 519–525)
- [ ] Enable Compute Engine API, Service Usage API, Cloud Resource Manager API, Google Container Registry API and Kubernetes Engine API — Container Registry is obsolete (§9 erratum 6); Artifact Registry API is what the main tutorial uses.

*Start Deployment Docker Container* (README lines 527–536)
- [ ] `cd deployment` — the folder is `src/deployment` from the repo root.
- [ ] `sh docker-shell.sh` — builds `cheese-app-deployment` for `linux/amd64` and runs it with your code at `/app` and secrets at `/secrets`; prints `Container is running!!!`, the Pulumi bucket messages, then a root prompt in `/app`. (`docker-shell.bat` does not exist; on Windows use WSL.)
- [ ] `gcloud --version` — Google Cloud SDK version lines.
- [ ] `kubectl version` — before any cluster exists this prints `The connection to the server localhost:8080 was refused`; harmless.
- [ ] `kubectl version --client` — `Client Version: v1.34.x`.
- [ ] `gcloud auth list` — `deployment@<project>.iam.gserviceaccount.com` is active.

*Create Cluster* (README lines 539–542)
- [ ] `gcloud container clusters create test-cluster --num-nodes 2 --zone us-east1-c` — a zonal cluster with two nodes in the project's `default` VPC; takes several minutes and writes the kubeconfig for you.

*Checkout the cluster in GCP* (README lines 544–549)
- [ ] Kubernetes Engine → click the cluster name → Nodes tab → click a node to see its Pods.
- [ ] Compute Engine → the cluster's VMs.

*Try some kubectl commands* (README lines 551–560)
- [ ] `kubectl get all` — the current (`default`) namespace only.
- [ ] `kubectl get all --all-namespaces` — every namespace.
- [ ] `kubectl get pods --all-namespaces` — system Pods in `kube-system`/`gke-*`.
- [ ] `kubectl get componentstatuses` — prints a deprecation warning (deprecated since Kubernetes 1.19) and may show little.
- [ ] `kubectl get nodes` — 2 nodes `Ready`.

*Deploy the App* (README lines 563–566)
- [ ] `kubectl apply -f deploy-k8s-tic-tac-toe.yml` — a Deployment with 2 replicas of `dlops/tic-tac-toe` plus a `LoadBalancer` Service, port 80 → 8080.

*Get the Loadbalancer external IP* (README lines 568–571)
- [ ] `kubectl get services` — row `web` shows `EXTERNAL-IP <pending>`, then a real IP after 1–2 minutes.

*View the App* (README lines 573–575)
- [ ] Copy the `External IP` and go to `http://<YOUR EXTERNAL IP>` — the game.
- [ ] `kubectl delete pod <one web pod>` — *(extra)* then `kubectl get pods`: a replacement Pod appears (§3.2).

*Delete Cluster* (README lines 578–581)
- [ ] `kubectl delete -f deploy-k8s-tic-tac-toe.yml` — *(extra)* run first, so GKE removes the load balancer while the cluster still exists.
- [ ] `gcloud container clusters delete test-cluster --zone us-east1-c` — deletes the warm-up cluster.
- [ ] `gcloud compute forwarding-rules list` — *(extra)* should be empty.

### Deployment with Scaling using Kubernetes

*API's to enable in GCP for Project* (README lines 396–402)
- [ ] Enable Compute Engine API, Service Usage API, Cloud Resource Manager API, Artifact Registry API and Kubernetes Engine API.
- [ ] *(extra)* Check that the Vertex AI API is enabled too (the API Pods call Gemini and the embedding model).

*Service accounts* (README lines 236–259, done in L20)
- [ ] `deployment` with Compute Admin, Compute OS Login, Artifact Registry Administrator, Kubernetes Engine Admin, Service Account User, Storage Admin; its JSON key saved as `secrets/deployment.json`.
- [ ] `gcp-service` with Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader. No key is needed in K8s; only its e-mail is used.
- [ ] *(extra)* Let `deployment` write the Workload Identity binding. Run once from Cloud Shell, or any shell where *you* are logged in as project owner (§2; or add "Service Account Admin" to `deployment` project-wide in the console):
  ```
  gcloud iam service-accounts add-iam-policy-binding gcp-service@<PROJECT>.iam.gserviceaccount.com \
    --member=serviceAccount:deployment@<PROJECT>.iam.gserviceaccount.com --role=roles/iam.serviceAccountAdmin
  ```

*Start Deployment Docker Container* (README lines 404–413)
- [ ] *(extra)* Set `GCP_PROJECT` to your project ID in `src/deployment/docker-shell.sh:13` (the L20 step at README line 267).
- [ ] `cd deployment` — `src/deployment` from the repo root.
- [ ] `sh docker-shell.sh` — starts the deployment container; if it already runs in another terminal, this execs into it.
- [ ] `gcloud --version` — SDK version lines.
- [ ] `kubectl version` — expected to fail with `connection ... refused` before a cluster exists; harmless.
- [ ] `kubectl version --client` — `Client Version: v1.34.x`.
- [ ] `gcloud auth list` — `deployment@<project>.iam.gserviceaccount.com` active.
- [ ] `gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us` — *(extra)* only if you did not create it in L20; no code creates it.

*Build and Push Docker Containers to GCR* (README lines 415–434; only if you have NOT already done this in L20)
- [ ] cd into `deploy_images` — `/app/deploy_images`.
- [ ] `pulumi stack init dev` — creates the `dev` stack; state goes to the GCS bucket.
- [ ] `pulumi config set gcp:project ac215-project --stack dev` — your project ID.
- [ ] `pulumi stack select dev` — *(extra)* instead of `init` if you get `stack 'dev' already exists`.
- [ ] `pulumi preview --stack dev` — the plan, without changes.
- [ ] `pulumi up --stack dev -y` — builds the three images for `linux/amd64` and pushes them with timestamp tags; `Outputs:` lists `cheese-app-api-service-tags`, `cheese-app-frontend-react-tags` and `cheese-app-vector-db-cli-tags`.

### Create & Deploy Cluster

*(README lines 436–507)*
- [ ] cd into `deploy_k8s` from the `deployment` folder — `cd ../deploy_k8s` from `deploy_images`, i.e. `/app/deploy_k8s`.
- [ ] `pulumi stack init dev` — the `dev` stack of project `deploy-k8s`, in the same state bucket.
- [ ] `pulumi config set gcp:project ac215-project` — your project ID.
- [ ] `pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com --stack dev` — the node pool's identity; your project in the e-mail.
- [ ] `pulumi config set security:gcp_ksa_service_account_email gcp-service@ac215-project.iam.gserviceaccount.com --stack dev` — the Google SA the Pods act as; your project in the e-mail.
- [ ] `pulumi config` — *(extra)* the three keys show *your* values (a missing key silently becomes `"None"`, §6 item 6).
- [ ] `pulumi preview --stack dev --refresh` — about 23 resources to create; many values show as `output<string>`.
- [ ] `pulumi up --stack dev --refresh -y` — network, cluster, node pool, namespace, KSA, IAM binding, PVCs, Deployments, Services, loader Job, Helm release and Ingress; roughly 15–25 minutes; ends with `Outputs:` including `app_url` and `ip_address`.

*Try some kubectl commands* (README lines 476–486)
- [ ] `kubectl get all` — only `service/kubernetes`: you are in `default`.
- [ ] `kubectl get all --all-namespaces` — the app's objects appear under `cheese-app-namespace`.
- [ ] `kubectl get pods --all-namespaces` — every Pod, system Pods included.
- [ ] `kubectl get componentstatuses` — deprecated; a warning.
- [ ] `kubectl get nodes` — 1 node (2 if the autoscaler added one).
- [ ] `kubectl get all -n cheese-app-namespace` — *(extra)* `frontend-…`, `vector-db-…`, `api-…`, the NGINX controller Pod, a `Completed` loader Pod and `job.batch/vector-db-loader 1/1`.
- [ ] `kubectl get pvc,ingress,serviceaccount -n cheese-app-namespace` — *(extra)* both PVCs `Bound`, the Ingress with host `<IP>.sslip.io`, the KSA `api-ksa`.
- [ ] `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>` — *(extra)* only if kubectl says `connection refused`, `no configuration` or `Unauthorized` (a new container session has no kubeconfig).

*If you want to shell into a container in a Pod* (README lines 488–492)
- [ ] `kubectl get pods --namespace=cheese-app-namespace` — find your `api-…` Pod name.
- [ ] `kubectl get pod api-c4fb784b-2llgs --namespace=cheese-app-namespace` — one Pod (use your Pod name).
- [ ] `kubectl exec --stdin --tty api-c4fb784b-2llgs --namespace=cheese-app-namespace  -- /bin/bash` — a shell in the API container (use your Pod name).
- [ ] `env | grep -E "ROOT_PATH|CHROMADB"` — *(extra)* inside the Pod: `ROOT_PATH=/api-service`, `CHROMADB_HOST=vector-db`, `CHROMADB_PORT=8000`.
- [ ] `ls /persistent` — *(extra)* `chat-history/<model>/` and the `experiments/` CNN model download.
- [ ] `python -c "import socket; print(socket.gethostbyname('vector-db'))"` — *(extra)* the vector-db Service's cluster IP.

*View the App* (README lines 495–507)
- [ ] From the terminal view the results of Pulumi — the README's `Outputs:` block is older; the current keys are `app_url`, `cluster_endpoint`, `cluster_name`, `ingress_name` (`cheese-app-ingress`), `ip_address`, `kubeconfig`, `namespace`.
- [ ] Go to `app_url` — the home page loads and the footer shows `API version: 3.0`.
- [ ] `curl http://<IP>.sslip.io/api-service/status` — *(extra)* from your laptop: `{"version":"3.0"}`; `http://<IP>.sslip.io/api-service/docs` shows Swagger.
- [ ] *(extra)* Open `/chat?model=llm-rag` and send a message; a reply proves Workload Identity and Chroma work (read the model note in §4 Step 10 first).

*Scale* *(extra, §4 Step 12; needed for Milestone 5)*
- [ ] `kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace` — *(extra)* two more frontend Pods, 2 Gi request each.
- [ ] `kubectl get pods -n cheese-app-namespace -o wide -w` — *(extra)* watch them go `Pending` → `Running`, and on which node.
- [ ] `kubectl get nodes -w` — *(extra)* watch the cluster autoscaler add node #2 if needed.
- [ ] `kubectl autoscale deployment frontend --cpu-percent=50 --min=1 --max=3 -n cheese-app-namespace` — *(extra, optional)* an HPA for the frontend (read §8 E6 before trying `api`).
- [ ] `kubectl get hpa -n cheese-app-namespace` — *(extra)* TARGETS such as `cpu: 2%/50%`.
- [ ] `kubectl delete hpa frontend api -n cheese-app-namespace` — *(extra)* removes the HPAs (drop `api` if you only created the frontend one).
- [ ] `kubectl scale deployment frontend --replicas=1 -n cheese-app-namespace` — *(extra)* back to one; the extra node goes after a cool-down of roughly 10 minutes.

*Redeploy a new version* *(extra, §4 Step 13; what L23 automates)*
- [ ] *(extra)* Change something visible, e.g. `"version": "3.0"` in `src/api-service/api/service.py:36`.
- [ ] `cd /app/deploy_images && pulumi up --stack dev -y` — *(extra)* new timestamp tags for all three images.
- [ ] `cd /app/deploy_k8s && pulumi up --stack dev --refresh -y` — *(extra)* rolling update; the loader Job is replaced and the vector DB reloaded. Checkpoint: the footer shows the new API version.

### Debugging Containers, Kubernetes part

*(README lines 618–657; use while the cluster is up. The `sudo docker` commands above them are for L20's VM.)* As written, these fail: the namespace `cheese-app-cluster-namespace` and the init container `wait-for-chromadb` belong to the pre-refactor program (§6 item 4, §8 E3). The corrected forms follow.
- [ ] `kubectl logs -n cheese-app-cluster-namespace job/vector-db-loader -c wait-for-chromadb` — init-container logs; fails (namespace, and no init container).
- [ ] `kubectl logs -n cheese-app-cluster-namespace job/vector-db-loader -c vector-db-loader` — loader logs; fails (namespace).
- [ ] `kubectl describe job vector-db-loader -n cheese-app-cluster-namespace` — Job status; fails (namespace).
- [ ] `kubectl get pods -n cheese-app-cluster-namespace | grep vector-db-loader` — find the loader Pod; fails (namespace).
- [ ] `kubectl logs -n cheese-app-cluster-namespace <pod-name>` — logs of that Pod; fails (namespace).
- [ ] `kubectl logs -n cheese-app-cluster-namespace vector-db-loader-9gr5m` — the same with an example Pod name; fails (namespace).
- [ ] `kubectl logs -n cheese-app-cluster-namespace <pod-name> -c wait-for-chromadb` — init container; fails (namespace, no init container).
- [ ] `kubectl logs -n cheese-app-cluster-namespace vector-db-loader-wlfdx -c wait-for-chromadb` — example; fails likewise.
- [ ] `kubectl logs -n cheese-app-cluster-namespace <pod-name> -c vector-db-loader` — main container; fails (namespace).
- [ ] `kubectl logs -n cheese-app-cluster-namespace vector-db-loader-wlfdx -c vector-db-loader` — example; fails (namespace).
- [ ] `kubectl logs job/vector-db-loader -n cheese-app-cluster-namespace` — most recent loader Pod; fails (namespace).
- [ ] `kubectl logs job/vector-db-loader -n cheese-app-cluster-namespace --previous` — logs of a restarted Pod's previous run; fails (namespace).
- [ ] `kubectl logs deployment/api -n cheese-app-cluster-namespace` — API Pod logs; fails (namespace).
- [ ] `kubectl logs deployment/api -n cheese-app-cluster-namespace -f` — follow them; fails (namespace).
- [ ] `kubectl logs -n cheese-app-namespace job/vector-db-loader` — *(extra)* the working loader-log command (README line 646 with the namespace fixed).
- [ ] `kubectl describe job vector-db-loader -n cheese-app-namespace` — *(extra)* the working Job status (README line 626, fixed).
- [ ] `kubectl logs deployment/api -n cheese-app-namespace -f` — *(extra)* the working API log follow (README line 656, fixed).
- [ ] `kubectl describe pod <name> -n cheese-app-namespace` — *(extra)* explains `Pending`, `ImagePullBackOff`, Multi-Attach.
- [ ] `kubectl get events -n cheese-app-namespace --sort-by=.lastTimestamp` — *(extra)* recent events, newest last.
- [ ] `kubectl config set-context --current --namespace=cheese-app-namespace` — *(extra)* make the app namespace the default for this session.
- [ ] `kubectl port-forward svc/api 9000:9000 -n cheese-app-namespace &` — *(extra)* reach the ClusterIP API from inside the deployment container (it publishes no ports).
- [ ] `curl localhost:9000/api-service/status` — *(extra)* in the same container, through the port-forward.
- [ ] `kubectl get storageclass` — *(extra)* the default StorageClass behind the PVCs.
- [ ] `kubectl exec deploy/vector-db -n cheese-app-namespace -- ls /data /chroma/chroma` — *(extra)* where Chroma actually keeps its data (§6 item 14).
- [ ] `kubectl delete job vector-db-loader -n cheese-app-namespace` — *(extra)* after fixing a failed loader; then rerun `pulumi up --refresh`, which recreates it (§6 item 9).

### Create & Deploy Cluster → Delete Cluster

*(README lines 509–512)*
- [ ] `pulumi destroy --stack dev --refresh -y` — run it **in `/app/deploy_k8s`**: deletes Ingress and Helm release, workloads and PVCs, namespace and KSA, node pool, cluster, NAT, router, subnet and VPC in reverse dependency order.
- [ ] `gcloud container clusters list` — *(extra)* no `cheese-app-cluster`.
- [ ] `gcloud compute forwarding-rules list` — *(extra)* no leftover load-balancer rules.
- [ ] `gcloud compute disks list` — *(extra)* look for `pvc-...` disks.
- [ ] `gcloud compute addresses list` — *(extra)* SSL mode only: `cheese-app-global-ip`.
- [ ] `gcloud compute firewall-rules list` — *(extra)* `k8s-...` rules on `cheese-app-vpc`.
- [ ] *(extra)* Delete the Artifact Registry images in the console (`retain_on_delete=True`), and L20's VM if it still runs (`pulumi destroy` in `deploy_single_vm`).

---

## 1. What you build

You take the same four cheese-app containers that ran on one VM in L20 (Next.js `frontend`, FastAPI `api`, ChromaDB `vector-db`, a one-shot `vector-db-loader`) and run them on a **managed Kubernetes cluster (GKE)**, described entirely in Python with Pulumi. A new Pulumi project, `deploy_k8s`, is run from the same deployment container as L20. It creates:
- a custom VPC and subnet with a Cloud Router and **Cloud NAT**, so nodes without public IPs can still reach Docker Hub and GitHub;
- a **regional GKE cluster** with **private nodes**, **Workload Identity** and a separate **node pool** (`n2d-standard-2`, zone `us-central1-a`, autoscaling 1–2 nodes);
- a Kubernetes **namespace** `cheese-app-namespace` with a **Kubernetes service account** (`api-ksa`) mapped to the `gcp-service` Google service account, so no JSON key enters the cluster;
- two **PersistentVolumeClaims**, three **Deployments** with **ClusterIP Services**, and one **Job** that loads the vector DB;
- the **F5 NGINX Ingress Controller** installed by **Helm**, exposed through a GCP **network load balancer**, and an **Ingress** that sends `/api-service…` to the API and everything else to the frontend.

The app ends up at `http://<LB-IP>.sslip.io`, a free wildcard DNS name that resolves to the IP inside it. An alternative HTTPS path (Google-managed certificate on a GCE L7 load balancer) exists in the code but is switched off (`src/deployment/deploy_k8s/__main__.py:17`).

```
 YOUR LAPTOP (Docker Desktop)                                     control path (who creates what)
 +------------------------------------------------------------------------------------------+
 | container "cheese-app-deployment" (linux/amd64)  gcloud | kubectl 1.34 | helm | pulumi    |
 |   GOOGLE_APPLICATION_CREDENTIALS=/secrets/deployment.json  (acts as SA "deployment")      |
 |   /app/deploy_images  --pulumi up-->  3 images (amd64, tag YYYYmmddHHMMSS)                |
 |   /app/deploy_k8s     --pulumi up-->  GCP resources + K8s objects (via kubeconfig whose    |
 |                                        exec plugin is gke-gcloud-auth-plugin)              |
 +------+----------------------+---------------------------+---------------------------------+
        | state                | push                      | GCP APIs (compute, container, iam)
        v                      v                           | + Kubernetes API (https, public endpoint)
  GCS <proj>-pulumi-     Artifact Registry                 v
  state-bucket           us-docker.pkg.dev/<proj>/cheese-app-repository/...
  deploy-images/dev --StackReference (image tags)--> deploy-k8s/dev

                                                                  data path (who calls whom)
 Browser --DNS: 34.x.y.z.sslip.io -> 34.x.y.z--> GCP external network LB :80
                                                 (made by GKE for the Service of type LoadBalancer)
 +------------------------- VPC "cheese-app-vpc", subnet 10.0.0.0/19, us-central1 --------------------------+
 |  GKE "cheese-app-cluster": regional control plane (Google-run, public endpoint)                         |
 |  node pool: n2d-standard-2, us-central1-a, 1..2 nodes, private IPs only                                  |
 |  namespace "cheese-app-namespace"                                                                         |
 |                                                                                                           |
 |   [Pod nginx-f5-...-nginx-ingress-controller]  reads Ingress "cheese-app-ingress" (host 34.x.y.z.sslip.io) |
 |        |  path /api-service* (prefix kept)          |  path /*                                              |
 |        v                                            v                                                     |
 |   Service "api" ClusterIP :9000              Service "frontend" ClusterIP :3000                            |
 |        | selector run=api                           | selector run=frontend                                 |
 |        v                                            v                                                     |
 |   [Pod api-...] uvicorn :9000                [Pod frontend-...] node server.js :3000                      |
 |     ROOT_PATH=/api-service                     (HTML + JS; the browser then calls /api-service/...)       |
 |     /persistent <- PVC persistent-pvc 5Gi (RWO disk)                                                     |
 |     KSA api-ksa ==Workload Identity==> GSA gcp-service ---> Vertex AI (Gemini, embeddings)               |
 |        | CHROMADB_HOST=vector-db, port 8000 (cluster DNS)                                                 |
 |        v                                                                                                  |
 |   Service "vector-db" ClusterIP :8000 --> [Pod vector-db-...] chromadb/chroma :8000                       |
 |                                             /chroma/chroma <- PVC chromadb-pvc 10Gi (RWO disk)           |
 |                                                  ^                                                       |
 |   [Job vector-db-loader] (runs once): cli.py --download --load --chunk_type recursive-split               |
 |                                                                                                           |
 |  Egress to the internet (Docker Hub, GitHub, NGINX image): Cloud Router + Cloud NAT "cheese-app-nat"     |
 |  Egress to Google APIs (Artifact Registry pulls, Vertex AI): Private Google Access on the subnet          |
 +-----------------------------------------------------------------------------------------------------------+
```

---

## 2. Prerequisites and costs

### Accounts and local installs
- A GCP project with billing enabled. GKE is not free (see the cost table below).
- **Docker Desktop** and `git`. All other tools (gcloud, kubectl, helm, Pulumi, `gke-gcloud-auth-plugin`, uv) live inside the deployment container (`src/deployment/Dockerfile:30`, `:33-41`, `:44`, `:47`, `:54`).
- Expected folder layout:
  ```
  ~/Desktop/AC215/
  ├── cheese-app-v3/          # git clone
  └── secrets/
      └── deployment.json     # needed by L22
                              # (gcp-service.json and ssh-key-deployment* are only used by L20's VM path)
  ```

### GCP APIs to enable (README lines 396–402)
Compute Engine, Service Usage, Cloud Resource Manager, Artifact Registry and **Kubernetes Engine API**. Two more are not in this list but the code needs them:
- **Vertex AI API**: the API pods call Gemini and the embedding model (`src/api-service/api/utils/llm_rag_utils.py:29`). You probably enabled it in earlier lectures.
- **IAM Service Account Credentials API**: Google's Workload Identity documentation lists it. The sources do not confirm whether it is strictly required (§9).

### Artifact Registry repository: still missing from the README
`deploy_images` pushes to `us-docker.pkg.dev/{project}/cheese-app-repository` (`src/deployment/deploy_images/__main__.py:14-15`). No code creates it. If you did not create it in L20, run this once inside the deployment container. The command is a suggested addition and does not appear in the repo:
```
gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us
```

### Service accounts (README lines 236–259) and one missing role
| SA | used by | roles listed in README | key file |
|---|---|---|---|
| `deployment` | everything in the deployment container: Pulumi's GCP and Kubernetes providers, `gcloud`, `kubectl`. **Also the node pool's identity** (`src/deployment/deploy_k8s/create_cluster.py:50`). | Compute Admin, Compute OS Login, Artifact Registry Administrator, Kubernetes Engine Admin, Service Account User, Storage Admin (README 241–246) | `secrets/deployment.json` → `/secrets/deployment.json` (`src/deployment/docker-shell.sh:9,16`) |
| `gcp-service` | the **API and loader Pods**, through Workload Identity (`create_cluster.py:150-189`). Only the API actually calls Vertex AI (query embeddings and Gemini); the loader's `--download --load` makes no Google call (Excerpt 8). | Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader (README 253–255) | **none needed in K8s**. Only its *email* is used, as Pulumi config. |

**Missing role (very likely needed):** `create_cluster.py:184-189` creates a `gcp.serviceaccount.IAMMember` that grants `roles/iam.workloadIdentityUser` on the `gcp-service` account. Writing an IAM policy on a service account needs `iam.serviceAccounts.setIamPolicy`. None of the six roles above includes it: Service Account User only grants `actAs`. Unless your `deployment` SA has broader rights, `pulumi up` will stop at `api-gsa-wi-user` with a 403. Fix (suggested, not in the README; run once from Cloud Shell or any shell where *you* are logged in as project owner):
```
gcloud iam service-accounts add-iam-policy-binding gcp-service@<PROJECT>.iam.gserviceaccount.com \
  --member=serviceAccount:deployment@<PROJECT>.iam.gserviceaccount.com --role=roles/iam.serviceAccountAdmin
```
A simpler but broader alternative is to add "Service Account Admin" to `deployment` at the project level in the console.

### Environment variables and config the code expects
| name | set where | read where |
|---|---|---|
| `GCP_PROJECT` | `src/deployment/docker-shell.sh:13` (**edit this**) | `docker-entrypoint.sh:11,17`; bucket name `:17` of docker-shell.sh |
| `GCP_REGION`, `GCP_ZONE` | `docker-shell.sh:14-15` | only `deploy_images/__main__.py:10` (`os.environ["GCP_REGION"]`, required but then unused: the registry host `us-docker.pkg.dev` is hard-coded at `:15`). `deploy_k8s` **hard-codes** `us-central1` (`deploy_k8s/__main__.py:15`) and `us-central1-a` (`create_cluster.py:71`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | `docker-shell.sh:16,44` | gcloud activation (`docker-entrypoint.sh:10`) and both Pulumi GCP providers |
| `PULUMI_BUCKET` | `docker-shell.sh:17` | `docker-entrypoint.sh:15-23`, where `pulumi login gs://<proj>-pulumi-state-bucket` runs |
| `USE_GKE_GCLOUD_AUTH_PLUGIN=True` | `docker-shell.sh:45` | kubectl auth through `gke-gcloud-auth-plugin` (installed at `Dockerfile:30`) |
| `PULUMI_CONFIG_PASSPHRASE=""` | `src/deployment/Dockerfile:51` | Pulumi's secrets manager. An empty passphrase means no prompts. |
| Pulumi config `gcp:project` | `pulumi config set …` (README 441) | `deploy_k8s/__main__.py:13-14`, `create_cluster.py:167` |
| Pulumi config `security:gcp_service_account_email` | README 442 | `create_cluster.py:9` → node pool SA (`:50`) |
| Pulumi config `security:gcp_ksa_service_account_email` | README 443 | `create_cluster.py:10-12` → KSA annotation (`:158`) and IAM binding (`:179-181`) |
| Pod env `CHROMADB_HOST=vector-db`, `CHROMADB_PORT=8000`, `GCP_PROJECT`, `ROOT_PATH=/api-service`, `GCS_BUCKET_NAME` | `setup_containers.py:292-313` (api), `:215-226` (loader) | `src/api-service/api/utils/llm_rag_utils.py:24-25`, `src/api-service/api/service.py:13` |

**Replace `ac215-project` everywhere** in the README commands (lines 421, 441–443) with your project ID. The committed `src/deployment/deploy_k8s/Pulumi.dev.yaml:3-6` contains the instructor's values. `pulumi config set` overwrites them, but only for the keys you set.

### What costs money, and how to switch it off
These are approximate us-central1 list prices, not taken from the repo and not checked against today's price list. Check the GCP pricing calculator.

| resource (created by) | rough price | removed by `pulumi destroy` in `deploy_k8s`? |
|---|---|---|
| GKE cluster management fee (`create_cluster.py:20-41`). The cluster is **regional** (`location=region`, `:24`), and the GKE free-tier credit only covers zonal/Autopilot clusters. | ≈ $0.10/h ≈ $2.40/day | yes |
| 1–2 × `n2d-standard-2` nodes, 50 GB boot disk each (`:44-72`) | ≈ $0.085/h per node + disk | yes |
| External network load balancer for the NGINX Service (`setup_loadbalancer.py:22-24`) | ≈ $0.025/h + traffic | yes. Deleting the Service makes GKE delete the LB, asynchronously. |
| Cloud NAT gateway + logging (`create_network.py:37-48`) | small hourly fee + $/GB processed | yes |
| 2 persistent disks for the PVCs, 5 Gi + 10 Gi (`setup_containers.py:17-46`) | cents per day | yes, when the PVCs are deleted (default reclaim policy *Delete*), also asynchronously |
| SSL mode only: global static IP, HTTPS LB, managed cert (`setup_loadbalancer_ssl.py:12-31`) | ≈ $0.025/h+ | yes |
| Artifact Registry images (`deploy_images`, `retain_on_delete=True`, `deploy_images/__main__.py:31`) | ~$0.10/GB-month | **no**. Delete them in the console. |
| L20's VM, if still running | see the L20 guide | **no**. Run `pulumi destroy` in `deploy_single_vm`. |

Rough total while the cluster is up: **about $5–8 per day**. Tear down the same day:
```
cd /app/deploy_k8s
pulumi destroy --stack dev --refresh -y        # README line 511
```
Then check for leftovers. These commands are additions, not in the README; LB and disk deletions are asynchronous and can be orphaned if the cluster disappears first:
```
gcloud container clusters list
gcloud compute forwarding-rules list
gcloud compute disks list            # look for pvc-... disks
gcloud compute addresses list        # SSL mode: cheese-app-global-ip
gcloud compute firewall-rules list   # k8s-... rules on cheese-app-vpc
```

---

## 3. Concepts this tutorial teaches

### 3.1 Cluster = control plane + node pools of VMs
- **Explanation:** a Kubernetes cluster is a *brain* plus *muscle*.
  - The brain is the **control plane**: API server, scheduler, controllers and the etcd database. On GKE, Google runs it and you never see its VMs. You talk to it over HTTPS (`cluster.endpoint`).
  - The muscle is **nodes**: ordinary Compute Engine VMs running a container runtime (`cos_containerd`, `create_cluster.py:52`) and the kubelet agent.
  - Nodes come in **node pools**: groups of identical VMs (same machine type, disk and service account). The code deletes GKE's default pool (`remove_default_node_pool=True`, `:28`) and creates its own (`:44-72`) so it controls these settings.
  - This cluster is **regional** (control plane replicated across the zones of `us-central1`, `:24`), but its nodes live in **one zone** (`node_locations=["us-central1-a"]`, `:71`).
  - The nodes are **private**: no public IPs (`enable_private_nodes`, `:31`). Outbound internet traffic goes through **Cloud NAT** (`create_network.py:37-48`). Google APIs are reached through **Private Google Access** (`create_network.py:22`).
- **Mental model:** you hand the brain a list of wishes ("I want one frontend Pod"). The brain decides which muscle carries each one out.
- **Analogy:** an air-traffic control tower (control plane) and a fleet of runways (nodes). You never land planes yourself. You file flight plans.
- **Misconception:** "the cluster is one big computer". It is several separate VMs. A Pod lives on exactly one node, and a disk attached to one node is not visible on another (see 3.5).

### 3.2 Desired state: Pods, Deployments, ReplicaSets, Jobs
- **Explanation:**
  - A **Pod** is the smallest schedulable unit: one or more containers sharing a network namespace (one IP) and volumes.
  - You almost never create Pods directly. A **Deployment** says "keep N copies of this Pod template running". It creates a **ReplicaSet** (one per template version), and the ReplicaSet creates the Pods. Names show this chain: Deployment `api` → ReplicaSet `api-c4fb784b` → Pod `api-c4fb784b-2llgs` (README 491).
  - **Controllers** loop forever: observe actual state, compare it with desired state, act. Delete a Pod and the ReplicaSet makes a new one. Change the image tag and the Deployment rolls out a new ReplicaSet.
  - A **Job** is the run-to-completion cousin. It retries failed Pods up to `backoffLimit` times (`setup_containers.py:206`) and then stops, with `restart_policy="Never"` (`:210`).
- **Mental model:** a thermostat. You set the temperature and it keeps correcting. `kubectl` and Pulumi set temperatures; they do not "run" things.
- **Analogy:** a restaurant manager with a staffing chart ("2 cooks on shift"). If a cook goes home sick, the manager calls in a replacement without being asked.
- **Misconception:** "Pulumi/kubectl starts my containers". They write *objects* into the API server. The kubelet on a node starts containers, possibly minutes later.

### 3.3 Labels, Services, cluster DNS and namespaces
- **Explanation:**
  - Pods are mortal and get new IPs every time they restart. A **Service** gives a *stable* virtual IP and DNS name in front of "all Pods whose labels match my selector". In this code that is `run: frontend`, `run: api` and `run: vector-db` (`setup_containers.py:59,63,106`, `:122,126,191`, `:254,258,340`).
  - `type="ClusterIP"` (`:98`) means reachable only inside the cluster.
  - Cluster DNS makes the Service name resolvable. That is why the API reaches Chroma at host `vector-db`, port `8000` (`:297-304`). Inside the same namespace the short name works. The full name is `vector-db.cheese-app-namespace.svc.cluster.local`.
  - A **namespace** (`cheese-app-namespace`, `create_cluster.py:141-145`) is a folder for objects. Names must be unique within it, and `kubectl` only looks in the `default` namespace unless you pass `-n`.
- **Mental model:** the label is a sticker on each Pod. The Service is a mail-forwarding address that delivers to whoever currently wears the matching sticker.
- **Analogy:** a company's switchboard number. Employees (Pods) come and go, the number stays.
- **Misconception:** "Service = Pod". A Service has no process of its own. It is a routing rule (kube-proxy/iptables), and the NGINX controller even bypasses it and sends traffic straight to the Pod IPs it lists.
- **Second misconception:** `kubectl get all` shows everything. It shows the *current* namespace only. Use `-n cheese-app-namespace` or `--all-namespaces`.

### 3.4 How a request reaches a Pod: LoadBalancer → Ingress controller → Service → Pod
- **Explanation:** an **Ingress** is only a *rule object*: host + path → Service:port (`setup_loadbalancer.py:62-117`). It does nothing until an **Ingress controller** implements it. Here that controller is the F5 NGINX Ingress Controller, installed by a Helm chart (`:11-46`). Its own Service has `type: LoadBalancer` (`:22-24`), so GKE creates a GCP **external network load balancer** with a public IP. A request travels:
  1. Browser asks DNS for `34.9.143.147.sslip.io`, and sslip.io answers `34.9.143.147` (`:60`).
  2. TCP :80 hits the GCP load balancer, which forwards to a node, which forwards to the NGINX controller Pod.
  3. NGINX matches the **Host header** (`host=host`, `:79`) and the **path prefix**: `/api-service` → Service `api` port 9000 (`:84-91`); `/` → Service `frontend` port 3000 (`:96-104`).
  4. NGINX proxies to one of the Pods behind that Service.
  5. The prefix is **not stripped**. The API therefore mounts all its routes under `ROOT_PATH=/api-service` (`setup_containers.py:309-312` → `src/api-service/api/service.py:13,49-50`).
  6. The frontend Pod only serves the page. It is the **browser** that then calls `/api-service/...`, because `NEXT_PUBLIC_BASE_API_URL=/api-service` is baked into the production build (`src/frontend-react/.env.production:2`, copied at `src/frontend-react/Dockerfile:28`). That request makes the same trip through the load balancer.
- **Mental model:** a hotel. The load balancer is the street door, NGINX is the receptionist who reads your booking (host + path), the Service is the corridor sign, and the Pod is the room.
- **Analogy:** the L20 nginx container on the VM did the same job. On K8s, the config file is *generated* from the Ingress object.
- **Misconception:** "a ClusterIP Service is reachable from my laptop". It is not. Only the LoadBalancer Service has an external IP. To reach a ClusterIP for debugging, use `kubectl port-forward` (suggested; not in the README). Note that kubectl runs *inside* the deployment container, so the forwarded port opens on the container's localhost, not your laptop's: `docker-shell.sh:34-50` publishes no ports (no `-p`). Run the `curl` in the same container, e.g. `kubectl port-forward svc/api 9000:9000 -n cheese-app-namespace &` then `curl localhost:9000/api-service/status`.

### 3.5 Persistent storage: PVC → PV → disk
- **Explanation:**
  - Container file systems are thrown away when the container restarts.
  - A **PersistentVolumeClaim** asks for storage ("10 Gi, ReadWriteOnce", `setup_containers.py:33-46`). GKE's default **StorageClass** (on current clusters `standard-rwo`, a balanced persistent disk; check with `kubectl get storageclass`) dynamically creates a **PersistentVolume** backed by a GCE persistent disk.
  - The disk is attached to whichever node runs the Pod that mounts the claim: `/chroma/chroma` (`:147-152`) and `/persistent` (`:286-291`).
  - **ReadWriteOnce** means one *node* at a time can mount it read-write.
  - `fs_group=1000` (`:262-264`) makes the kubelet give the mounted volume group ownership GID 1000 (group-writable, setgid) and adds GID 1000 to the container processes. A fresh disk is otherwise owned by root. The API image runs as user `app`, uid 1000 (`src/api-service/Dockerfile:30,35`), and must write chat history (`src/api-service/api/utils/chat_utils.py:9`) and the downloaded CNN model (`src/api-service/api/utils/llm_cnn_utils.py:34,114-134`) there.
  - The PVCs replace L20's `/mnt/disk-1/...` host folders.
- **Mental model:** a claim ticket. The Pod shows the ticket, and the cloud wheels the same disk to whatever node the Pod lands on.
- **Analogy:** a locker you rent. You can move offices, but the locker key only opens it for one office at a time (RWO).
- **Misconception:** "the PVC is shared storage, so I can scale the API to many replicas". Not across nodes. A second API replica on the other node fails with a Multi-Attach error. Scaling stateful pieces needs ReadWriteMany storage (e.g. Filestore) or an external store such as GCS.

### 3.6 Scaling at two levels: Pods (replicas, HPA) and nodes (cluster autoscaler)
- **Explanation:**
  - **Pod-level scaling** changes the number of replicas of a Deployment. You can do it by hand (`kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace`) or automatically with a **HorizontalPodAutoscaler**. An HPA reads CPU/memory from the metrics server and adjusts `replicas` between a min and a max so that average *utilization as a percentage of the requested resources* stays near a target.
  - **Node-level scaling** is the **cluster autoscaler**, enabled by `autoscaling=…min_node_count=1, max_node_count=2` (`create_cluster.py:63-66`). It adds a node when Pods are **Pending** because no node has enough *requested* CPU/memory left, and removes underused nodes later.
  - The two levels interact through **resource requests**. The frontend requests `cpu: 250m, memory: 2Gi` (`setup_containers.py:79-82`), Chroma `100m/128Mi` (`:153-156`), NGINX `100m/128Mi` (`setup_loadbalancer.py:26-35`), and the API **nothing**.
- **What this repo does:** only the node autoscaler. All Deployments default to 1 replica and **there is no HPA**. The README title says "Scaling" but no scaling step exists (§9).
- **Mental model:** replicas are *workers*, nodes are *desks*. The HPA hires workers when the existing ones are busy. The cluster autoscaler buys desks when hired workers have nowhere to sit, but never more than 2 here.
- **Analogy:** a supermarket opens more checkout lanes (Pods) when queues grow, and the landlord adds floor space (nodes) only when lanes physically don't fit.
- **Misconception:** "HPA scales on actual memory use, so requests don't matter". The scheduler packs Pods by **requests**, and the HPA's CPU percentage is computed *relative to the request*. A Deployment with no requests (the API here) gives the HPA no denominator, so it shows `<unknown>`.

### 3.7 Identity inside and outside the cluster
- **Explanation:** four identities are in play.
  1. **You → GCP:** the deployment container runs `gcloud auth activate-service-account` with `deployment.json` (`docker-entrypoint.sh:10`). Pulumi's GCP provider uses the same file (`GOOGLE_APPLICATION_CREDENTIALS`).
  2. **You → Kubernetes API:** a kubeconfig whose user entry is an **exec plugin**, `gke-gcloud-auth-plugin` (`create_cluster.py:104-116`). Every kubectl or Pulumi-Kubernetes call runs the plugin, which mints a short-lived Google token from gcloud's active account. GKE maps that account's IAM role (Kubernetes Engine Admin) to cluster permissions. There are no static cluster passwords.
  3. **Nodes → GCP:** the node pool runs as the `deployment` SA (`:50`) with limited OAuth scopes (`:54-61`). Image pulls from Artifact Registry use this identity.
  4. **Pods → GCP (Workload Identity):**
     - The cluster gets an identity pool `<project>.svc.id.goog` (`:35-37`).
     - The Kubernetes service account `api-ksa` is annotated with the Google SA email (`:150-160`).
     - An IAM binding lets `serviceAccount:<project>.svc.id.goog[cheese-app-namespace/api-ksa]` act as `gcp-service` (`:167-189`).
     - Pods that set `service_account_name=api-ksa` (`setup_containers.py:209,261`) get Google tokens for `gcp-service` from the **GKE metadata server** (a DaemonSet on every node that intercepts the metadata address `169.254.169.254` for Pods; it is not the VM's own metadata server, which would hand out the node SA). Google client libraries find them automatically (Application Default Credentials). No JSON key is mounted.
- **Mental model:** a badge-swap desk. Inside the building (cluster) you wear a K8s badge (`api-ksa`). At the door to Google's services, the desk swaps it for a Google badge (`gcp-service`), but only because IAM has a rule saying that swap is allowed.
- **Analogy:** a hotel key card that also opens the gym because the front desk linked the two.
- **Misconception:** "the Pod uses the node's service account". Not with Workload Identity: Pods see only their KSA's mapped GSA. Without the annotation or binding, Vertex AI calls fail with 403.
- **Before/after:** the older Ansible version uploaded `gcp-service.json` as a K8s Secret and mounted it (`pipenv:src/deployment/deploy-k8s-cluster.yml:134-138,235,247-249`). Workload Identity removes that long-lived key.

### 3.8 Driving Kubernetes from Pulumi: providers, Helm releases, awaits and stack references
- **Explanation:**
  - `deploy_k8s` uses **two providers**: `pulumi_gcp` for cloud resources, and an explicit `k8s.Provider` built from a kubeconfig *generated from the cluster's outputs* (`create_cluster.py:77-138`). Every K8s object passes `provider=k8s_provider`, so it is created in the new cluster and not in whatever `~/.kube/config` points at.
  - `depends_on=[node_pool]` (`:137`) stops Pulumi from creating Pods before there are nodes.
  - Helm charts are installed as one resource, `k8s.helm.v3.Release` (`setup_loadbalancer.py:11-46`). Its outputs (`status.name`, `status.namespace`) are used to look up the Service the chart created (`:49-58`).
  - Pulumi **waits for readiness**. A Deployment must become *Available*, a Job must reach *Complete* and fails at once on *Failed*, and an Ingress must get a load-balancer address. Each wait times out after 10 minutes. (This is from the pulumi-kubernetes 4.23.0 docstrings for `Job`, `Deployment` and `Ingress`, the version locked in `src/deployment/uv.lock`.)
  - So the chain `vector-db Deployment → vector-db Service → loader Job → api Deployment` (`setup_containers.py:170-172, 193-195, 239-242, 319-321`) means the **API is not even created until the vector DB is loaded**.
  - Images come from the other stack through `StackReference("organization/deploy-images/dev")` (`:10-14`). Every `deploy_images` run makes new timestamp tags, and the next `deploy_k8s` up triggers a rolling update.
- **Mental model:** Pulumi is the general contractor. GCP and Kubernetes are subcontractors. The kubeconfig is the contractor's site pass, created right after the site (cluster) exists.
- **Misconception:** "after `pulumi up`, kubectl is configured on my laptop". Only inside *this* container session. The `gcloud container clusters get-credentials` Command (`create_cluster.py:192-199`) writes `/root/.kube/config` in a container started with `--rm` (`docker-shell.sh:34`), and it runs only once, on create.

---

## 4. Step-by-step walkthrough

The order follows the README. Part 0 is the optional warm-up at the end of the README (lines 517–581). It is the gentlest first contact with `kubectl` and is worth doing first if you have 20 minutes. It costs a few cents. Commands and checks marked "not in the README" are additions written from the code or standard `gcloud`/`kubectl` usage.

### Part 0 (optional warm-up): a throw-away cluster with tic-tac-toe

**0.0 Enable the APIs.** README 519–525: Compute Engine, Service Usage, Cloud Resource Manager, "Google Container Registry API" (obsolete, erratum 6; Artifact Registry API is what the main tutorial uses) and Kubernetes Engine API.

**0.1 Start the deployment container.** README 527–536.
```
cd deployment
sh docker-shell.sh
```
- Under the hood: builds `cheese-app-deployment` for `linux/amd64` (`src/deployment/docker-shell.sh:31`) and runs it with your code at `/app` and secrets at `/secrets` (`:34-50`). The entrypoint activates the `deployment` SA, configures Docker for Artifact Registry and runs `pulumi login gs://…` (`docker-entrypoint.sh:10-23`).
- Checkpoint: the entrypoint prints `Container is running!!!`, then the Pulumi bucket messages, then a root prompt in `/app`.
- If it fails: `docker-shell.bat` (README 529) does not exist in the repo; on Windows use WSL. A `gcloud auth` error means `secrets/deployment.json` is not at `../../../secrets/` relative to `src/deployment`.

**0.2 Create a cluster.** README 541.
```
gcloud container clusters create test-cluster --num-nodes 2 --zone us-east1-c
```
- Under the hood: a **zonal** cluster in the project's `default` VPC, with the default machine type and two nodes. This is the imperative "click-ops in the terminal" way.
- Checkpoint (expected, not captured): after several minutes gcloud prints a table with `test-cluster`, its master IP and `NUM_NODES 2`. gcloud also writes the kubeconfig for you.
- If it fails: `Kubernetes Engine API has not been used` → enable it (README 525). `network "default" not found` → your project has no default VPC. Add `--network`/`--subnetwork`, or use the main tutorial.

**0.3 Look around.** README 545–549 (console) and 552–560:
```
kubectl get all
kubectl get all --all-namespaces
kubectl get pods --all-namespaces
```
```
kubectl get componentstatuses
kubectl get nodes
```
- Checkpoint: `kubectl get nodes` lists 2 nodes `Ready`. `--all-namespaces` shows system Pods in `kube-system`/`gke-*`. `get componentstatuses` prints a deprecation warning (deprecated since Kubernetes 1.19) and may show little.

**0.4 Deploy and expose the app.** README 565, 570.
```
kubectl apply -f deploy-k8s-tic-tac-toe.yml
kubectl get services
```
- Under the hood: `src/deployment/deploy-k8s-tic-tac-toe.yml:2-22` is a Deployment with `replicas: 2` of `dlops/tic-tac-toe` (container port 8080). `:24-35` is a Service of `type: LoadBalancer` mapping port 80 → 8080. The YAML file is in `/app` because `/app` is `src/deployment`.
- Checkpoint: the row `web` (type `LoadBalancer`, `PORT(S) 80:<nodePort>/TCP`) shows `EXTERNAL-IP <pending>` and after 1–2 minutes a real IP. `http://<EXTERNAL-IP>` shows the game (README 574–575).
- Try: `kubectl delete pod <one web pod>` then `kubectl get pods`. A new one appears (3.2).

**0.5 Delete.** README 580.
```
gcloud container clusters delete test-cluster --zone us-east1-c
```
- Tip (not in the README): run `kubectl delete -f deploy-k8s-tic-tac-toe.yml` first, so GKE removes the load balancer while the cluster still exists. Then check `gcloud compute forwarding-rules list` is empty.

### Part A: one-time setup

**Step 1. Enable the APIs.** README 396–402. Add Vertex AI API if it is not already on (§2).

**Step 2. Service accounts and the extra role.**
- README 236–259 creates `deployment` and `gcp-service`. Put `deployment.json` in `~/Desktop/AC215/secrets/`.
- Grant the extra role from §2 so Pulumi can write the Workload Identity binding.
- Checkpoint: in the console under IAM → Service accounts → `gcp-service` → Permissions, `deployment@…` appears with Service Account Admin (or deployment has it project-wide).

**Step 3. Start the deployment container and check tools.** README 404–413.
- Before the first run, set `GCP_PROJECT` to your project ID in `src/deployment/docker-shell.sh:13`. The K8s section does not repeat this; it is the L20 step at README 267. The README's `cd deployment` (405) means `src/deployment` from the repo root.
```
gcloud --version
kubectl version
kubectl version --client
gcloud auth list
```
- Under the hood: same as 0.1. If the container is already running in another terminal, `docker-shell.sh` *execs* into it instead of starting a new one (`docker-shell.sh:23-25`).
- Checkpoint: Google Cloud SDK version lines. `kubectl version --client` prints `Client Version: v1.34.x` (pinned by `Dockerfile:33`). `gcloud auth list` shows `deployment@<project>.iam.gserviceaccount.com` as active.
- Expected failure: plain `kubectl version` (README 409) also tries to reach a server. Before any cluster exists you get `The connection to the server localhost:8080 was refused`. This is harmless.

### Part B: images

**Step 4. Build and push images (skip if you did it in L20).** README 415–434.
```
cd deploy_images
pulumi stack init dev
pulumi config set gcp:project ac215-project --stack dev
pulumi preview --stack dev
pulumi up --stack dev -y
```
(replace `ac215-project`)
- Under the hood: three `docker_build.Image` resources build `../../api-service`, `../../frontend-react` and `../../vector-db` for `linux/amd64` (`deploy_images/__main__.py:23-32,43-52,62-71`), tag them `us-docker.pkg.dev/<proj>/cheese-app-repository/<name>:<YYYYmmddHHMMSS>` (`:13-15,25`) and push them. The stack outputs `cheese-app-…-tags` (`:35,54,74`) are what `deploy_k8s` will read.
- Checkpoint: `Outputs:` lists `cheese-app-api-service-tags`, `cheese-app-frontend-react-tags` and `cheese-app-vector-db-cli-tags`. The images appear in Artifact Registry.
- If it fails: `Repository "cheese-app-repository" not found` → create it (§2). Very slow builds on Apple Silicon → expected: the builds run in your laptop's Docker engine (the container talks to it through the mounted socket, `docker-shell.sh:35`) and are forced to `linux/amd64` (`deploy_images/__main__.py:28`), so they are emulated; the API image also installs `tensorflow==2.19.0` (`src/api-service/pyproject.toml:13`).

### Part C: the cluster and the app

**Step 5. Initialise the `deploy_k8s` stack.** README 437–444.
```
pulumi stack init dev
pulumi config set gcp:project ac215-project
pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com --stack dev
pulumi config set security:gcp_ksa_service_account_email gcp-service@ac215-project.iam.gserviceaccount.com --stack dev
```
First `cd ../deploy_k8s` (README 437 says "cd into `deploy_k8s` from the `deployment` folder"), and replace every `ac215-project` with your project ID.
- Under the hood: creates `.pulumi/stacks/deploy-k8s/dev.json` in the state bucket (project name from `src/deployment/deploy_k8s/Pulumi.yaml:1`) and writes the three keys into `Pulumi.dev.yaml`.
- Checkpoint: `pulumi config` lists `gcp:project`, `security:gcp_service_account_email` and `security:gcp_ksa_service_account_email` with *your* values. The leftover keys `security:ssh_user` and `deploy-k8s:setupSSL` (`Pulumi.dev.yaml:4,7`) are unused.
- If it fails: `stack 'dev' already exists` → `pulumi stack select dev`.

**Step 6. Preview.** README 449.
```
pulumi preview --stack dev --refresh
```
- Checkpoint: about 23 resources to `create` (counted from the program: 4 network + 2 cluster/pool + provider + namespace + KSA + IAM member + command + 2 PVCs + 3 Deployments + 3 Services + Job + Helm release + Ingress + the stack itself). Many values show as `output<string>`, because they are unknown until the cluster exists. The `StackReference` and `nginx-ingress-service` are *reads* of things that already exist, not creates.

**Step 7. Create everything.** README 454.
```
pulumi up --stack dev --refresh -y
```
- Under the hood, in dependency order (`src/deployment/deploy_k8s/__main__.py:19-40`):
  1. VPC `cheese-app-vpc` (custom subnets, `create_network.py:7-13`), subnet `10.0.0.0/19` with Private Google Access (`:16-25`), Cloud Router (`:28-34`), Cloud NAT (`:37-48`).
  2. GKE cluster (`create_cluster.py:20-41`). This is the slow part: GKE first creates a temporary default pool and then removes it (`:28-29`). Then the node pool (`:44-72`).
  3. The kubeconfig string (`:77-131`) → `k8s.Provider` (`:134-138`) → namespace (`:141-145`), KSA (`:151-162`), IAM binding (`:184-189`) and a local `gcloud container clusters get-credentials` (`:192-199`), so `kubectl` works in this container.
  4. PVCs (`setup_containers.py:17-46`). The frontend Deployment and Service (`:51-111`) and the vector-db Deployment and Service (`:114-196`) are created in parallel.
  5. The loader Job (`:199-243`). Pulumi waits until it **completes**: download from GitHub (`src/vector-db/cli.py:479-495`) and load into Chroma (`:271-311`). Only then does it create the API Deployment and Service (`setup_containers.py:246-343`).
  6. In parallel with 4–5: the Helm release of the F5 NGINX controller (`setup_loadbalancer.py:11-46`). Pulumi waits until its LoadBalancer Service has an IP, reads that IP (`:49-59`) and builds the `sslip.io` host (`:60`). The Ingress (`:62-117`) comes **last**: besides its explicit `depends_on=[nginx_helm]` (`:115`), it uses `api_service.metadata["name"]` and `frontend_service.metadata["name"]` (`:88`, `:101`), which are outputs, so Pulumi also waits for both Services, and therefore for the loader Job and the API Deployment. Pulumi then waits until the Ingress has endpoints and a load-balancer address (3.8).
- Checkpoint: a total run time of roughly 15–25 minutes (estimate), then outputs. The README (498–506) shows an **older** output set. With the current code you should see:
  ```
  Outputs:
      app_url         : "http://<IP>.sslip.io"
      cluster_endpoint: "<control-plane IP>"
      cluster_name    : "cheese-app-cluster"
      ingress_name    : "cheese-app-ingress"
      ip_address      : "<IP>"
      kubeconfig      : [secret]
      namespace       : "cheese-app-namespace"
  ```
  The keys come from `__main__.py:43-49` and the Ingress name from `setup_loadbalancer.py:65`. README shows `nginx_ingress_ip` and `ingress_name: "nginx-ingress"`, both from before commit `44ceff4`.
- README 457–474 then shows a Mermaid diagram of the traffic path (Browser → LoadBalancer Service → NGINX Ingress Controller → Frontend Service :3000 for `/`, API Service :9000 for `/api-service`; API → Vector-DB Service :8000). Its dotted edge `V -.->|one-time load| J` (466) points from the vector-db Service to the loader Job; the data actually flows from the Job into the vector DB.
- If it fails:
  - `api-gsa-wi-user` 403 → the missing role (§2).
  - The Job times out or fails → read its logs (Step 11).
  - `Quota … exceeded` → §6.
  - After any failure, fix the cause and rerun the same command. Pulumi resumes from the state file.

**Step 8. Explore with kubectl.** README 477–486.
```
kubectl get all
kubectl get all --all-namespaces
kubectl get pods --all-namespaces
```
```
kubectl get componentstatuses
kubectl get nodes
```
- Checkpoint: plain `kubectl get all` shows only `service/kubernetes`, because you are in `default`. The app lives in `cheese-app-namespace`. These commands are not in the README:
  ```
  kubectl get all -n cheese-app-namespace
  kubectl get pvc,ingress,serviceaccount -n cheese-app-namespace
  ```
  You should see Pods `frontend-…`, `vector-db-…`, `api-…`, `nginx-f5-…-nginx-ingress-controller-…`, a `vector-db-loader-…` Pod in `Completed`, and `job.batch/vector-db-loader 1/1`. Both PVCs should be `Bound`, and the Ingress should show the host `<IP>.sslip.io`. `kubectl get nodes` shows 1 node (2 if the autoscaler added one).
- If kubectl says `connection refused`, `no configuration` or `Unauthorized`: you are in a new container session (the kubeconfig is not persisted). Re-create it (not in the README):
  ```
  gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>
  ```

**Step 9. Shell into a Pod.** README 489–492.
```
kubectl get pods --namespace=cheese-app-namespace
kubectl get pod api-c4fb784b-2llgs --namespace=cheese-app-namespace
kubectl exec --stdin --tty api-c4fb784b-2llgs --namespace=cheese-app-namespace  -- /bin/bash
```
- Replace `api-c4fb784b-2llgs` with *your* Pod name from the first command.
- Inside, try (not in the README):
  - `env | grep -E "ROOT_PATH|CHROMADB"`.
  - `ls /persistent`: `chat-history/<model>/` (`src/api-service/api/utils/chat_utils.py:23`) plus the `experiments/` CNN model download (`llm_cnn_utils.py:34`).
  - `python -c "import socket; print(socket.gethostbyname('vector-db'))"`: the Service's cluster IP.

**Step 10. View the app.** README 496–507: open `app_url`.
- Checkpoints:
  - The home page loads, and the footer shows `API version: 3.0`. The footer calls `GET /api-service/status` (`src/frontend-react/src/components/layout/Footer.jsx:18`, `src/frontend-react/src/services/DataService.js:63`, served by `src/api-service/api/service.py:34-36`). Seeing "3.0" proves the whole browser → LB → NGINX → API path works.
  - From your laptop (not in the README): `curl http://<IP>.sslip.io/api-service/status` → `{"version":"3.0"}`. `http://<IP>.sslip.io/api-service/docs` shows Swagger.
  - Send a RAG chat message. The chat page defaults to the plain `llm` model (`src/frontend-react/src/app/chat/page.jsx:23`), so pick the RAG model (URL `/chat?model=llm-rag`). A reply proves Workload Identity (Vertex AI) and Chroma both work.
- **Model note** (from the [L20 guide](L20-deployment-pulumi.md), §9 erratum 20, which checked the same API code against Google's model list; the README does not mention it): every LLM helper hard-codes `GENERATIVE_MODEL = "gemini-2.0-flash-001"` (`src/api-service/api/utils/llm_rag_utils.py:23`, also `llm_utils.py:22`, `llm_agent_utils.py:21`, `llm_cnn_utils.py:30`), and Google's Vertex AI model-versions page lists `gemini-2.0-flash` as retired on 2026-06-01. If `/api-service/status` works but every chat fails, suspect the model before Workload Identity: switch `GENERATIVE_MODEL` to a model Vertex AI still serves and redeploy (Step 13).
- If it fails:
  - **404 from nginx** when you use the bare IP → you must use the `sslip.io` name (host rule, `setup_loadbalancer.py:79`).
  - **502/503 for the first minute** → the API is still importing TensorFlow and downloading the CNN model (`llm_cnn_utils.py:149`), and there is no readiness probe.
  - **Chat 500/403** → check the API logs (Step 11) for `PERMISSION_DENIED` (Workload Identity), a missing collection (loader/Chroma), or a model-not-found error (the model note above).

**Step 11. Logs and debugging.** README 618–657, with the namespace corrected. The README uses `cheese-app-cluster-namespace` and an init container `wait-for-chromadb`; neither exists in the current code (§9).
```
kubectl logs -n cheese-app-namespace job/vector-db-loader
kubectl describe job vector-db-loader -n cheese-app-namespace
kubectl logs deployment/api -n cheese-app-namespace -f
```
- These are README lines 646, 626 and 656 with the namespace fixed. Drop `-c wait-for-chromadb` from any README command: the Pod has a single container named `vector-db-loader` (`setup_containers.py:213`). `kubectl describe pod <name> -n cheese-app-namespace` and `kubectl get events -n cheese-app-namespace --sort-by=.lastTimestamp` (not in the README) explain Pending and ImagePullBackOff states.

**Step 12. Scale (not in the README; needed for Milestone 5).**
```
kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace
kubectl get pods -n cheese-app-namespace -o wide -w
kubectl get nodes -w
```
- Under the hood: the Deployment's ReplicaSet creates two more Pods, each requesting 2 Gi of memory (`setup_containers.py:80`). If they do not fit on the node, they stay `Pending` until the cluster autoscaler adds node #2 (`create_cluster.py:63-66`). The NGINX controller automatically load-balances across all three Pods: the Ingress → Service → endpoints list grows.
- Optional HPA: `kubectl autoscale deployment frontend --cpu-percent=50 --min=1 --max=3 -n cheese-app-namespace`, then `kubectl get hpa -n cheese-app-namespace`. See §8 E6 before trying this on `api`.
- Scale back down with `--replicas=1`. The autoscaler removes the extra node after a cool-down of roughly 10 minutes.
- Note: `pulumi up` does not manage `replicas` in this program, so it should not undo a `kubectl scale`. Verify this yourself (§9, open questions).

**Step 13. Redeploy a new version (optional; this is what L23 automates).** Change something visible, e.g. `"version": "3.0"` in `src/api-service/api/service.py:36`. Then run the two commands below. They condense `cheese-app-v4:src/deployment/deploy-k8s-update.sh:2-9`, which does the same with `cd` and `pulumi stack select dev` lines and without `--refresh`:
```
cd /app/deploy_images && pulumi up --stack dev -y
cd /app/deploy_k8s && pulumi up --stack dev --refresh -y
```
- Under the hood: new timestamp tags → the image field of the Deployments changes → rolling update. The loader Job's pod template changes too (every `deploy_images` run retags all three images, even unchanged ones), so Pulumi has to *replace* that Job (a Job's template is immutable), and the vector DB gets reloaded: `load()` deletes and recreates the collection (`src/vector-db/cli.py:284-292`), so RAG answers can fail while it runs (the API looks the collection up per request, `src/api-service/api/utils/llm_rag_utils.py:92`).
- Checkpoint: the footer shows the new API version.
- If it fails: an API Pod stuck in `ContainerCreating` with `Multi-Attach error` → §6, item 10.

**Step 14. Delete everything.** README 510–512.
```
pulumi destroy --stack dev --refresh -y
```
- Under the hood: Pulumi deletes in reverse dependency order: Ingress and Helm release → Services/Deployments/Job/PVCs → namespace/KSA → provider → node pool → cluster → NAT → router → subnet → VPC. `deletion_protection=False` (`create_cluster.py:25`) is what allows the cluster deletion.
- Checkpoint: `Resources: N deleted`. Then run the leftover checks from §2.

---

## 5. Code tour

```
src/deployment/                       # same toolbox as L20 (Dockerfile, docker-shell.sh, docker-entrypoint.sh, ...)
├── Dockerfile                        # adds kubectl 1.34 (:33-41), helm (:44), gke-gcloud-auth-plugin (:30)
├── docker-shell.sh                   # USE_GKE_GCLOUD_AUTH_PLUGIN=True (:45); container is --rm (:34)
├── deploy_images/__main__.py         # stack "deploy-images": build+push 3 amd64 images, export tags
├── deploy_k8s/                       # Pulumi project "deploy-k8s"  (L22)
│   ├── Pulumi.yaml                   # name: deploy-k8s, runtime python via uv
│   ├── Pulumi.dev.yaml               # instructor's config (gcp:project, security:*, unused setupSSL/ssh_user)
│   ├── Pulumi.ssl.yaml               # a second stack "ssl" config (no setupSSL key; flag is hard-coded)
│   ├── __main__.py                   # orchestrates: network → cluster → containers → load balancer; exports
│   ├── create_network.py             # VPC, subnet (Private Google Access), Cloud Router, Cloud NAT
│   ├── create_cluster.py             # GKE cluster, node pool, kubeconfig, k8s Provider, namespace, KSA, WI binding
│   ├── setup_containers.py           # 2 PVCs, frontend/vector-db/api Deployments+Services, loader Job
│   ├── setup_loadbalancer.py         # F5 NGINX Ingress via Helm, LB IP → sslip.io host, Ingress  (USED)
│   └── setup_loadbalancer_ssl.py     # GCE L7 + static IP + ManagedCertificate + HTTPS redirect (OFF)
├── deploy-k8s-tic-tac-toe.yml        # warm-up: Deployment (2 replicas) + LoadBalancer Service
├── emoji.yaml                        # demo: ConfigMap-served page, 2 replicas, LoadBalancer (not in README)
└── visualizer.yaml                   # demo: dockersamples/visualizer (a Docker Swarm tool; not in README)
src/api-service/api/service.py        # all routes in api_app, mounted at ROOT_PATH (K8s: /api-service)
src/frontend-react/.env.production    # NEXT_PUBLIC_BASE_API_URL=/api-service (browser-side calls)
src/vector-db/cli.py                  # loader: --download (GitHub zip) and --load (into Chroma)
```

### Excerpt 1: Cloud NAT, the way out for private nodes
`src/deployment/deploy_k8s/create_network.py:36-48`
```python
    # Configure Cloud NAT to allow private instances to access the internet
    nat = gcp.compute.RouterNat(
        f"{app_name}-nat",
        name=f"{app_name}-nat",
        router=router.name,
        region=region,
        nat_ip_allocate_option="AUTO_ONLY",
        source_subnetwork_ip_ranges_to_nat="ALL_SUBNETWORKS_ALL_IP_RANGES",
        log_config=gcp.compute.RouterNatLogConfigArgs(
            enable=True, filter="ERRORS_ONLY"
        ),
        opts=pulumi.ResourceOptions(depends_on=[router]),
    )
```
- The nodes have no public IPs (Excerpt 2), so without this NAT they could not pull `chromadb/chroma` from Docker Hub (`setup_containers.py:132`) or the NGINX controller image. The loader could not download from GitHub (`src/vector-db/cli.py:487`), and the API could not fetch its CNN model (`src/api-service/api/utils/llm_cnn_utils.py:124`).
- `AUTO_ONLY`: Google picks the NAT's public IPs. `ALL_SUBNETWORKS_ALL_IP_RANGES` NATs the node IPs *and* the Pod IP ranges.
- NAT is outbound-only. Inbound traffic arrives through the load balancer instead.
- Google APIs (Artifact Registry, Vertex AI) do not need the NAT, thanks to `private_ip_google_access=True` on the subnet (`create_network.py:22`).

### Excerpt 2: the cluster: private nodes, Workload Identity
`src/deployment/deploy_k8s/create_cluster.py:28-41`
```python
        remove_default_node_pool=True,  # Remove default pool to use custom node pools
        initial_node_count=1,
        private_cluster_config={
            "enable_private_nodes": True,  # Nodes use private IPs only
            "enable_private_endpoint": False,  # Control plane accessible via public endpoint
            "master_ipv4_cidr_block": "172.0.0.0/28",  # CIDR for GKE control plane
        },
        workload_identity_config={
            "workload_pool": f"{project}.svc.id.goog"
        },  # Enable Workload Identity for secure service account access
        gateway_api_config={
            "channel": "CHANNEL_STANDARD",  # Enable Gateway API for advanced ingress
        },
    )
```
- `:28-29` GKE always creates a default pool. The program asks for the minimum and deletes it immediately, then adds its own pool.
- `:31` private nodes. `:32` keeps a **public control-plane endpoint**, which is why `kubectl` and Pulumi on your laptop can reach the API server.
- `:33` a /28 range for the Google-managed control plane's peering. 172.0.0.0/28 is *not* RFC 1918 private space (that would be 172.16.0.0/12). It worked for the course, but see §9.
- `:35-37` enables the Workload Identity pool used in Excerpt 5.
- `:38-40` enables the Gateway API CRDs. Nothing in this program uses them.

### Excerpt 3: the node pool and its autoscaler
`src/deployment/deploy_k8s/create_cluster.py:63-71`
```python
        autoscaling=gcp.container.NodePoolAutoscalingArgs(
            min_node_count=1,  # Minimum nodes to keep running
            max_node_count=2,  # Maximum nodes for scale-up
        ),
        management=gcp.container.NodePoolManagementArgs(
            auto_repair=True,  # Automatically repair unhealthy nodes
            auto_upgrade=True,  # Automatically upgrade to new GKE versions
        ),
        node_locations=["us-central1-a"],
```
- `:63-66` the **cluster autoscaler**. These are per-zone limits, and with one zone (`:71`) they are total limits: 1 to 2 VMs. It reacts to *Pending Pods*, not to CPU load.
- `:68` auto-repair recreates a node that fails health checks. `:69` auto-upgrade means GKE will occasionally drain and replace your nodes. Pods move, and RWO disks follow them (3.5, Excerpt 9).
- `:71` pins the nodes to one zone of the regional cluster. With three zones, every count would triple, and so would the bill.
- Context, `:48-53`: `initial_node_count=1`, `service_account=service_account_email` (the `deployment` SA), `machine_type="n2d-standard-2"` (AMD EPYC = amd64; this is why images must be built for `linux/amd64`), `cos_containerd`, 50 GB disk.

### Excerpt 4: a kubeconfig made from outputs, and the first K8s object
`src/deployment/deploy_k8s/create_cluster.py:133-145`
```python
    # Create Kubernetes provider using GKE cluster credentials to deploy K8s resources
    k8s_provider = k8s.Provider(
        "gke_k8s_v2",
        kubeconfig=cluster_kubeconfig,  # Use the kubeconfig generated from the GKE cluster
        opts=ResourceOptions(depends_on=[node_pool]),  # Wait for node pool to be ready
    )

    # Create Kubernetes namespace for application deployments
    namespace = k8s.core.v1.Namespace(
        f"{app_name}-namespace",
        metadata={"name": f"{app_name}-namespace"},
        opts=ResourceOptions(provider=k8s_provider),
    )
```
- `cluster_kubeconfig` (`:77-131`) is YAML built inside `.apply` from `cluster.name`, `cluster.endpoint` and `cluster.master_auth`: server `https://<endpoint>` (`:93`), the cluster CA (`:90-92`), and a user that runs `gke-gcloud-auth-plugin` (`:108-115`). There is no password or token in it.
- `:137` makes every K8s resource wait for nodes.
- `:144` `provider=k8s_provider` sends this object to *this* cluster. Every K8s resource in `setup_*.py` repeats it.
- `:143` gives the namespace an explicit name, `cheese-app-namespace`. Pulumi does not add a random suffix when `metadata.name` is set. That is why the README's `--namespace=cheese-app-namespace` works.

### Excerpt 5: a Kubernetes service account that "is" a Google service account
`src/deployment/deploy_k8s/create_cluster.py:150-160`
```python
    ksa_name = "api-ksa"
    api_ksa = k8s.core.v1.ServiceAccount(
        "api-ksa",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name=ksa_name,
            namespace=namespace.metadata["name"],
            annotations={
                # Critical: map KSA → GSA (Google Service Account) for Workload Identity
                "iam.gke.io/gcp-service-account": f"{ksa_service_account_email}",
            },
        ),
```
- The annotation is one half of the handshake: it is the KSA saying "I want to be `gcp-service@…`".
- The other half is the IAM grant on the Google side: `role="roles/iam.workloadIdentityUser"` for member `serviceAccount:<project>.svc.id.goog[cheese-app-namespace/api-ksa]` (`:167-189`). Both are needed.
- `:158` uses an f-string. If `security:gcp_ksa_service_account_email` is not set, the annotation silently becomes the string `"None"` (§6).

### Excerpt 6: labels connect a Deployment to its Pods
`src/deployment/deploy_k8s/setup_containers.py:57-64`
```python
        spec=k8s.apps.v1.DeploymentSpecArgs(
            selector=k8s.meta.v1.LabelSelectorArgs(
                match_labels={"run": "frontend"},  # Select pods with this label
            ),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels={"run": "frontend"},  # Label assigned to pods
                ),
```
- The selector (`:58-60`) must match the template's labels (`:62-64`). Kubernetes rejects a Deployment whose selector does not match its own template.
- No `replicas` field, so the default is 1. Scaling is a one-line change here (`replicas=3`) or a `kubectl scale`.
- The rest of the template: the image comes from the other stack (`:69-71`), `image_pull_policy="IfNotPresent"` (`:72`), container port 3000 (`:73-78`), and requests/limits (`:79-82`). The scheduler packs by requests; a container that exceeds its memory limit is OOM-killed.

### Excerpt 7: a Service is a label query with a stable name
`src/deployment/deploy_k8s/setup_containers.py:97-106`
```python
        spec=k8s.core.v1.ServiceSpecArgs(
            type="ClusterIP",  # Internal only - not exposed outside cluster
            ports=[
                k8s.core.v1.ServicePortArgs(
                    port=3000,  # Service port
                    target_port=3000,  # Container port to forward to
                    protocol="TCP",
                )
            ],
            selector={"run": "frontend"},  # Route traffic to pods with this label
```
- `:98` reachable only inside the cluster.
- `:101-102` `port` is what callers use; `target_port` is the container's port. They happen to be equal here. In tic-tac-toe they differ: 80 → 8080 (`src/deployment/deploy-k8s-tic-tac-toe.yml:30-32`).
- `:106` the same label as Excerpt 6. Every Pod with `run=frontend`, from any ReplicaSet, becomes an endpoint.
- The Service's `metadata.name="frontend"` (`:94`) becomes its DNS name. The vector-db Service is named `vector-db` (`:179`), which is exactly what `CHROMADB_HOST` says (`:298-299`).

### Excerpt 8: a run-to-completion Job with a cloud identity
`src/deployment/deploy_k8s/setup_containers.py:205-214`
```python
        spec=k8s.batch.v1.JobSpecArgs(
            backoff_limit=3,  # Retry up to 4 times on failure
            template=k8s.core.v1.PodTemplateSpecArgs(
                spec=k8s.core.v1.PodSpecArgs(
                    service_account_name=ksa_name,  # Use Workload Identity for GCP access
                    restart_policy="Never",  # Don't restart pod on completion
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name="vector-db-loader",
                            image=vector_db_cli_tag.apply(lambda tags: tags[0]),
```
- `:206` `backoffLimit: 3` means three *retries* after the first failure, so four attempts at most.
- `:209` the loader runs as `api-ksa`, so any Vertex AI call it made would get `gcp-service` credentials without a key file. For *this* Job it is not strictly needed: `--download --load` fetches precomputed embeddings (`cheese-books-embeddings.zip`, `src/vector-db/cli.py:487`) and passes them to Chroma as `embeddings=` (`:153-159`), so no Vertex AI call is made. `genai.Client(vertexai=True, …)` at import (`:38-39`) only builds a client object. The identity would matter for `--embed`, `--query` or `--chat`.
- `:210` a failed attempt makes a *new Pod*. The container is not restarted in place.
- `:227-233` passes `args=["cli.py", "--download", "--load", "--chunk_type", "recursive-split"]`. `args` replaces the image's CMD and keeps its ENTRYPOINT (`src/vector-db/Dockerfile:51`), so the entrypoint runs `uv run python cli.py …` (`src/vector-db/docker-entrypoint.sh:22`). The `cluster-updates` branch used `command=` here, which replaces the ENTRYPOINT (§8 E5).
- `:239-242` the Job depends on the vector-db Service. The API Deployment depends on the Job (`:319-321`), and Pulumi waits for Job completion (3.8).

### Excerpt 9: the API Pod: identity, file permissions, persistent disk
`src/deployment/deploy_k8s/setup_containers.py:260-272`
```python
                spec=k8s.core.v1.PodSpecArgs(
                    service_account_name=ksa_name,  # Use KSA for Workload Identity (GCP access)
                    security_context=k8s.core.v1.PodSecurityContextArgs(
                        fs_group=1000,
                    ),
                    volumes=[
                        k8s.core.v1.VolumeArgs(
                            name="persistent-vol",
                            persistent_volume_claim=k8s.core.v1.PersistentVolumeClaimVolumeSourceArgs(
                                claim_name=persistent_pvc.metadata.name,  # Temporary storage (lost on restart)
                            ),
                        )
                    ],
```
- `:261` Vertex AI calls in `api/utils/*.py` authenticate as `gcp-service` through Workload Identity.
- `:262-264` `fsGroup: 1000` matches the `app` user (uid 1000) in the API image, so it can write to the new disk.
- `:265-272` the volume is the 5 Gi PVC, mounted at `/persistent` (`:286-291`). The comment on `:269` is wrong: a PVC survives Pod restarts. That is its whole point. What *is* lost on restart is anything outside `/persistent`, e.g. the in-memory `chat_sessions` dict, which the API rebuilds from the files on disk (`src/api-service/api/routers/llm_chat.py:107-111`).
- `:309-312` (not shown) sets `ROOT_PATH=/api-service`, Excerpt 12.
- No `resources` are set for the API container. It is the first candidate for eviction under memory pressure, and HPA on CPU can't work for it.

### Excerpt 10: from a Helm release to a public hostname
`src/deployment/deploy_k8s/setup_loadbalancer.py:48-60`
```python
    # Get the service created by Helm to extract the LoadBalancer IP
    nginx_service = k8s.core.v1.Service.get(
        "nginx-ingress-service",
        pulumi.Output.concat(
            nginx_helm.status.namespace,
            "/",
            nginx_helm.status.name,
            "-nginx-ingress-controller",  # often resolves to <release-name>-ingress-nginx-controller
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider, depends_on=[nginx_helm]),
    )
    ip_address = nginx_service.status.load_balancer.ingress[0].ip
    host = ip_address.apply(lambda ip: f"{ip}.sslip.io")
```
- `Service.get` *reads* an object that Helm created. Pulumi does not manage it.
- The ID is `<namespace>/<release-name>-nginx-ingress-controller`. The release has no explicit `name` in `:11-46`, so Pulumi auto-generates it from `nginx-f5`. The comment on `:55` describes the *community* ingress-nginx chart's naming, not this F5 chart.
- `:59` the external IP assigned by GCP to the chart's `type: LoadBalancer` Service (`:22-24`). It is ephemeral: destroy and recreate, and you get a new IP and a new URL.
- `:60` sslip.io turns the IP into a hostname with no DNS setup. That gives the Ingress a `host` to match, and is required for a managed certificate in SSL mode (`setup_loadbalancer_ssl.py:18,29`).

### Excerpt 11: the routing table
`src/deployment/deploy_k8s/setup_loadbalancer.py:81-94`
```python
                        paths=[
                            # API service
                            k8s.networking.v1.HTTPIngressPathArgs(
                                path="/api-service",
                                path_type="Prefix",
                                backend=k8s.networking.v1.IngressBackendArgs(
                                    service=k8s.networking.v1.IngressServiceBackendArgs(
                                        name=api_service.metadata["name"],
                                        port=k8s.networking.v1.ServiceBackendPortArgs(
                                            number=9000
                                        ),
                                    )
                                ),
                            ),
```
- `:84-85` `Prefix` matching is per path element: `/api-service`, `/api-service/` and `/api-service/llm-rag/chats` match, `/api-servicex` does not. The longest matching path wins, so `/` (`:97`) catches the rest.
- `:88` the backend is referenced by Service *name* (`api`) and port (`:90`). Pulumi waits until those Services have endpoints before declaring the Ingress ready.
- Not shown: `:76` `ingress_class_name="nginx"`, the class the Helm chart creates and marks as default (`:38-42`). `:79` `host=host` restricts the rule to the sslip.io name. `:69` a `cert-manager.io/cluster-issuer` annotation for a cert-manager that is never installed (§9).
- Compare with L20's nginx.conf, where `proxy_pass http://api-service:9000/;` *strips* the prefix (README 192). Here nothing strips it, hence Excerpt 12.

### Excerpt 12: why the API needs `ROOT_PATH`
`src/api-service/api/service.py:48-50`
```python
# Mount your API under ROOT-PATH to match the Ingress rule
app = FastAPI(title="API Server", description="API Server", version="v1")
app.mount(ROOT_PATH, api_app)
```
- `ROOT_PATH = os.getenv("ROOT_PATH", "")` (`:13`). On the L20 VM it is empty, so routes live at `/`. In K8s it is `/api-service` (`setup_containers.py:309-312`), so `GET /api-service/status` reaches `api_app`'s `/status` (`:34-36`).
- The same image works behind both proxies, only an env var differs. The `cluster-updates` branch hard-coded `/api-service` (`cluster-updates:src/api-service/api/service.py:40`), which would break the VM path.
- Consequence: `GET /` on the API Pod itself returns 404. That matters for load-balancer health checks in SSL mode (§9, and the `BackendConfig` that v4 adds).

---

## 6. Gotchas and common errors

1. **`kubectl version` fails right after starting the container.**
   - Symptom: `The connection to the server localhost:8080 was refused`.
   - Cause: README 409 runs it before a cluster or kubeconfig exists.
   - Fix: ignore it, or use `kubectl version --client` (README 410).

2. **`kubectl` worked yesterday, not today.**
   - Symptom: the same `connection refused`, or `current-context is not set`.
   - Cause: the kubeconfig is written by a one-time Pulumi Command (`create_cluster.py:192-199`) into a `--rm` container (`docker-shell.sh:34`). It is gone after you exit, and the Command does not rerun on later `pulumi up`s.
   - Fix: `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>`.

3. **`kubectl get all` shows nothing of the app.**
   - Cause: default namespace.
   - Fix: add `-n cheese-app-namespace` (README 490–492 do), or `kubectl config set-context --current --namespace=cheese-app-namespace`.

4. **README debugging commands fail.**
   - Symptom: `namespaces "cheese-app-cluster-namespace" not found`, or `container wait-for-chromadb is not valid`.
   - Cause: README 620–656 were written for the pre-refactor program (namespace `{cluster_name}-namespace` and an init container, still visible at `3149e56:src/deployment/deploy_k8s/__main__.py`). The current namespace is `cheese-app-namespace` (`create_cluster.py:143`) and the Job has one container (`setup_containers.py:213`).
   - Fix: use Step 11.

5. **`pulumi up` fails at `api-gsa-wi-user` with 403 / `iam.serviceAccounts.setIamPolicy`.**
   - Cause: the README's role list (241–246) doesn't allow editing a service account's IAM policy.
   - Fix: §2.

6. **You forgot or mistyped the `security:*` config.**
   - Symptom: an IAM error mentioning `serviceAccounts/None`; a node pool running as the default compute SA; Pods getting 403.
   - Cause: `pulumi.Config("security").get(...)` returns `None` silently (`create_cluster.py:9-12`), and f-strings turn that into `"None"` (`:158,180`).
   - Fix: `pulumi config` to check; then set the keys with *your* project ID.

7. **ImagePullBackOff or `exec format error`.**
   - Causes:
     - Images were pushed for arm64 (e.g. built natively on a Mac outside `deploy_images`). The nodes are amd64 (`n2d`), and `deploy_images` forces amd64 (`deploy_images/__main__.py:28`).
     - The Artifact Registry repo doesn't exist.
     - Docker Hub images can't be pulled because the NAT is missing.
   - Fix: rebuild with `deploy_images`. Check `kubectl describe pod`.

8. **`StackReference` error: `unknown stack "organization/deploy-images/dev"`** (or missing `…-tags` outputs).
   - Cause: Step 4 not done in *this* state bucket (`setup_containers.py:10-14`).
   - Fix: run `deploy_images` first.

9. **`pulumi up` sits on `vector-db-loader` for 10 minutes, then fails.**
   - Cause: the Job never completed. Possible reasons:
     - Chroma isn't accepting connections yet: there is no readiness probe, and `backoffLimit` is 3.
     - GitHub can't be reached (no NAT).
     - Chroma was OOM-killed at its 256 Mi limit (`setup_containers.py:155`).
   - Fix: Step 11 logs. After fixing, delete the Job (`kubectl delete job vector-db-loader -n cheese-app-namespace`) and rerun `pulumi up --refresh`, which recreates it. Because the API Deployment depends on the Job (`:319-321`), **no API Pods exist until this succeeds**.

10. **Multi-Attach error for the API.**
    - Symptom: `Multi-Attach error for volume "pvc-…" Volume is already used by pod(s) api-…`, Pod stuck in `ContainerCreating`.
    - Cause: `persistent-pvc` is ReadWriteOnce (`setup_containers.py:24`). A second API Pod on a different node, from scaling or from a rolling update that schedules the new Pod on node #2, cannot attach the disk. The same applies to `vector-db` (`:40`).
    - Fix: keep API/vector-db at 1 replica and scale down before updates if needed. A better fix (a suggestion, not in the repo) is `strategy: Recreate` for these Deployments, or ReadWriteMany storage.

11. **Pods `Pending` with `Insufficient memory` / `max node group size reached`.**
    - Cause: the frontend requests 2 Gi per replica (`setup_containers.py:80`) and the pool stops at 2 nodes (`create_cluster.py:65`).
    - Fix: fewer replicas, a smaller request, or a higher `max_node_count`.

12. **404 when opening `http://<IP>/`.**
    - Cause: the Ingress rule has `host=<IP>.sslip.io` (`setup_loadbalancer.py:79`), and a request with `Host: <IP>` matches no rule.
    - Fix: use `app_url`.

13. **502/503 right after deploy, or after an API restart.**
    - Cause: no readiness probe. The API Pod is marked Ready as soon as its container starts, but the production command `uv run uvicorn api.service:app --host 0.0.0.0 --port 9000 --lifespan on` (`src/api-service/docker-entrypoint.sh:19`) only listens after importing the app: TensorFlow, the CNN model download (`llm_cnn_utils.py:149`) and a Chroma `HttpClient` created at import (`src/api-service/api/utils/llm_rag_utils.py:57`). If Chroma is unreachable at that moment, the import can fail and the Pod restarts (CrashLoopBackOff) instead of serving.
    - Fix: wait a minute. Long-term, add a readinessProbe on `/api-service/status` (a suggestion, not in the repo).

14. **RAG answers stop working after the vector-db Pod restarts.**
    - Possible cause: the Deployment uses the unpinned `chromadb/chroma` image (`setup_containers.py:132`) with data at `/chroma/chroma` (`:150`). Chroma 1.x images appear to store data under `/data`; the course's own `llm-rag` mounts `/data` (`llm-rag:docker-compose.yml:24`). If so, the PVC isn't actually used, the collection lives in the container's writable layer, and the one-time Job won't reload it. `IS_PERSISTENT=TRUE` (`setup_containers.py:140-142`) also appears to be a 0.x-only server setting. Because the image has no tag, Kubernetes defaults its `imagePullPolicy` to `Always`, so a restarted Pod may also come up on a newer Chroma release than before.
    - Fix: rerun the Job (item 9). Check where the data lives with `kubectl exec deploy/vector-db -n cheese-app-namespace -- ls /data /chroma/chroma` (not in the README). Pin an image and mount the path that version uses.

15. **Quota errors** (`N2D_CPUS`, `SSD_TOTAL_GB`, `IN_USE_ADDRESSES`).
    - Cause: new or free-trial projects have small regional quotas. GKE's temporary default pool for a regional cluster may briefly add nodes in several zones before it is removed (`create_cluster.py:28-29`). L20's VM may still be running.
    - Fix: destroy L20's stack; request a quota increase.

16. **Leftover billable resources after `destroy`.**
    - Cause: deleting a LoadBalancer Service or a PVC triggers *asynchronous* GCP deletions. If the cluster is deleted first, forwarding rules, firewall rules or `pvc-…` disks can be orphaned, and the VPC deletion may then fail with "resource is in use".
    - Fix: §2 leftover checks; delete leftovers by hand, then `pulumi destroy` again.

17. **Apple Silicon.**
    - The toolbox image is amd64 (`docker-shell.sh:31`) and runs under emulation: slower, but correct. The three app images are also built for amd64 (`deploy_images/__main__.py:28`) by your laptop's Docker engine through the mounted socket (`docker-shell.sh:35`), so they are emulated too.
    - Do not build cheese-app images natively with plain `docker build` for the cluster; use `deploy_images`.

18. **Secrets hygiene.**
    - `deployment.json` lives outside the repo (`docker-shell.sh:9`). Keep it there.
    - Committed and harmless but worth noticing: the instructor's project ID and SA emails (`deploy_k8s/Pulumi.dev.yaml:3-6`), and `NEXTAUTH_SECRET` in `src/frontend-react/.env.production:3`.
    - Pulumi marks `kubeconfig` as `[secret]` in outputs (README 503). It contains no credentials anyway, only the exec-plugin instructions.

19. **Version skew.**
    - kubectl is pinned to 1.34 (`Dockerfile:33`), while GKE auto-upgrades the cluster (`create_cluster.py:69`). kubectl supports ±1 minor version; beyond that, expect warnings.
    - `kubectl get componentstatuses` (README 484) is deprecated.

---

## 7. Where this sits in the course

- **Before:**
  - L2–L4: containers, Docker networks and ports.
  - L10: GCP service accounts.
  - L18: cheese-app-v2, the app itself, run locally.
  - L19 "Scaling: Kubernetes (local)": its tutorial is still "coming soon" (`tutorials_demo.md` Lecture 19 entry).
  - **L20**: the same repo's deployment toolbox, the `deploy_images` stack, and the single-VM deployment with nginx.
  - L21: CI on GitHub Actions (`cheese-app-ci-cd`).
- **This lecture adds:** an orchestrator. Restarts, placement, service discovery, rolling updates, node autoscaling, per-Pod cloud identity and managed load balancing replace the hand-wired VM.
- **Next, L23 (`cheese-app-v4`):** wires `deploy_images` + `deploy_k8s` into GitHub Actions ("Deploy updates to the Kubernetes cluster upon merging", `milestone5.md:47`). The core sequence is `cheese-app-v4:src/deployment/deploy-k8s-update.sh:2-9`. v4's `deploy_k8s` differs from v3's in these ways (`diff -r` of the two `deploy_k8s` folders):
  - `setupSSL` and an optional `domain` come from stack config (`cheese-app-v4:src/deployment/deploy_k8s/__main__.py:17-21`), and v4's `Pulumi.dev.yaml:7` sets `setupSSL: "true"`. A set `domain` replaces the `<ip>.sslip.io` host in both load-balancer modes (`cheese-app-v4:src/deployment/deploy_k8s/setup_loadbalancer.py:60-63`, `setup_loadbalancer_ssl.py:18-21`).
  - A `BackendConfig` health check on `/api-service/` plus NEG annotations for the API Service (`cheese-app-v4:src/deployment/deploy_k8s/setup_containers.py:324-345,353-356`); the API Service also depends on it (`:369-371`).
  - In SSL mode: the FrontendConfig moves to `networking.gke.io/v1beta1` and now depends on the managed certificate (`cheese-app-v4:src/deployment/deploy_k8s/setup_loadbalancer_ssl.py:39,46`); the GCE class moves to the `kubernetes.io/ingress.class: gce` annotation (`:56`); the annotation key becomes `networking.gke.io/v1beta1.frontend-config` (`:59`); the API path becomes `/api-service` instead of `/api-service/` (`:70`).
  - The SSL `app_url` becomes `https://` (`cheese-app-v4:src/deployment/deploy_k8s/__main__.py:41`).

**Single VM (L20) → Kubernetes (L22)**, same app:

| concern | L20 `deploy_single_vm` | L22 `deploy_k8s` |
|---|---|---|
| machines | 1 VM `n2d-standard-2` with public IP | node pool of 1–2 `n2d-standard-2`, private IPs (`create_cluster.py:44-72`) |
| network | VPC + 3 firewall rules | custom VPC/subnet + Cloud Router/NAT (`create_network.py`); GKE manages firewall rules |
| run containers | Docker provider over SSH, `docker.Container` | Deployments + Job (`setup_containers.py`) |
| container discovery | Docker network `appnetwork`, container names | Services + cluster DNS (`vector-db`, `api`, `frontend`) |
| persistence | `/mnt/disk-1/{persistent,chromadb}` on a 50 GB data disk | PVCs 5 Gi + 10 Gi (`setup_containers.py:17-46`) |
| GCP credentials in containers | `gcp-service.json` copied to the VM, `GOOGLE_APPLICATION_CREDENTIALS` | Workload Identity, no key (`create_cluster.py:147-189`) |
| reverse proxy | nginx container + hand-written `nginx.conf` (strips `/api-service/`) | F5 NGINX Ingress Controller via Helm + Ingress object (prefix kept, `ROOT_PATH`) |
| public address | `http://<VM IP>/` | `http://<LB IP>.sslip.io` |
| restart on crash | Docker restart policy | ReplicaSet controller, node auto-repair |
| scaling | none | node autoscaler 1–2; `kubectl scale`/HPA possible |

**Files this lecture adds on top of L20** (all already in v3 `main`; line counts by `wc -l`):
```
 src/deployment/deploy_k8s/__main__.py               |  49   orchestration + exports
 src/deployment/deploy_k8s/create_network.py         |  50   VPC, subnet, router, NAT
 src/deployment/deploy_k8s/create_cluster.py         | 201   cluster, pool, kubeconfig, provider, ns, KSA/WI
 src/deployment/deploy_k8s/setup_containers.py       | 345   PVCs, 3 Deployments, 3 Services, Job
 src/deployment/deploy_k8s/setup_loadbalancer.py     | 119   Helm NGINX + Ingress (used)
 src/deployment/deploy_k8s/setup_loadbalancer_ssl.py | 102   GCE L7 + cert (off)
 src/deployment/deploy_k8s/Pulumi{,.dev,.ssl}.yaml   |  22
 src/deployment/deploy-k8s-tic-tac-toe.yml, emoji.yaml, visualizer.yaml | 147  demos
 src/api-service/api/service.py                      |  ROOT_PATH mount (shared with L20)
```

**The `cluster-updates` branch: what it changes.** It forked from `main` at `3149e56` ("Using docker provider instead of command", 2025-11-17) and has 4 commits by one TA: `ec86699` "GKE deployment for private networking and Workload Identity", `980d9db` "added f5 nginx", `4cc742b` "tls update" and `e55178c` "updated gce l7". `main` then received 20 more commits and **was not merged with it**. `main` re-implemented the same ideas as the modular files above. Against the fork point (`git diff --stat 3149e56 origin/cluster-updates`: 7 files, +1859/−333):
```
 src/api-service/api/service.py             |   37 +-   hard-codes app.mount("/api-service", api_app)
 src/deployment/.dockerignore               |    1 +    pulumi-plugins
 src/deployment/deploy_k8s/Pulumi.dev.yaml  |    8 +    clusterName, initialNodeCount: 2, machineType, disk as config
 src/deployment/deploy_k8s/Pulumi.dev2.yaml |   11 +    a second "-test" stack
 src/deployment/deploy_k8s/__main__.py      |  716 ++-- one 634-line file
 src/deployment/deploy_k8s/dump.py          | 1411 +    scratch: commented-out older variants (Bitnami/F5 nginx, cert-manager + Let's Encrypt)
 src/deployment/docker-shell.sh             |    8 +-   SECRETS_DIR → ../../../secrets/ac215-project/
```
Meaningful differences from `main`:
1. **One file, config-driven** (`cluster-updates:src/deployment/deploy_k8s/__main__.py:9-22`). Most resource names carry a `-test` suffix: network `cheese-app-vpc-test` (`:35`), namespace `deployments-test` (`:173`), the vector-db and frontend objects, the loader Job (`:399`). The cluster name comes from config (`cheese-app-cluster` in its `Pulumi.dev.yaml`), and the KSA `api-ksa` and the API objects `api` keep plain names. Main split this into modules and hard-codes the values.
2. **Ingress = GCE L7 HTTPS only.** A global static IP (`:541-546`), a `ManagedCertificate` for `<ip>.sslip.io` (`:550-560`), a `FrontendConfig` HTTPS redirect (`:562-572`) and an Ingress with the `kubernetes.io/ingress.class: gce` annotation (`:580`). There is no NGINX. Main kept F5 NGINX as the default and moved this design to `setup_loadbalancer_ssl.py`, behind `setupSSL = False`.
3. **ChromaDB pinned to `chromadb/chroma:0.5.6`** (`:328`), still mounted at `/chroma/chroma` (`:346`). Main un-pinned it in `c4f4a92` ("updated k8s deployment using pulumi", which replaced `chromadb/chroma:0.5.6` with the wrong image name `chromadb/latest` (a repository called `latest`, not a tag)); `a236118` ("chroma fix") then corrected that to the untagged `chromadb/chroma`.
4. **Loader Job uses `command=[ "cli.py", … ]`** (`:426-432`). That overrides the image ENTRYPOINT and would fail to start (§8 E5). It also has `backoff_limit=4` and `fs_group` (`:403,407-409`). Main uses `args=` (`setup_containers.py:227-233`).
5. The API Deployment depends only on the vector-db Service (`:513-515`), not on the Job, so the API may start before the DB is loaded.
6. `application_url` is hard-coded to `https://temp.instel.ai` (`:634`). The real app URL is not exported.

Use `main` for the tutorial. Read `cluster-updates` as a record of how the HTTPS design was explored.

**The `pipenv` branch** (2025-04-23) is the previous Ansible implementation of the same cluster: `pipenv:src/deployment/deploy-k8s-cluster.yml`, run by `ansible-playbook … --extra-vars cluster_state=present|absent` (`pipenv:README.md` lines 386, 429). It installs nginx-ingress with Helm (`:69-81`), uses `NodePort` Services (`:277,296`) and imports `gcp-service.json` as a K8s Secret (`:134-138`). Workload Identity and Pulumi state are what v3 `main` adds over it.

---

## 8. Exercises

**E1 (hands-on: self-healing).** Run `kubectl get pods -n cheese-app-namespace -w` in one terminal. In another, delete the frontend Pod. Predict what the watch shows, then do it.
*Worked answer:* the old Pod goes `Terminating`. Within seconds a new `frontend-<same RS hash>-<new suffix>` Pod goes `Pending → ContainerCreating → Running`. The ReplicaSet saw 0 of 1 desired Pods and created one (3.2). The RS hash stays the same because the template didn't change. While it restarts, the page may briefly fail, because there is only 1 replica and no readiness probe.

**E2 (hands-on: requests and the node autoscaler).** First predict, then run `kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace` and then `--replicas=5`. Watch `kubectl get nodes` and `kubectl get pods -o wide`. Use `kubectl describe node` (look at *Allocatable* and *Allocated resources*) to check your prediction.
*Worked answer:*
- Each frontend Pod requests 2 Gi memory and 250m CPU (`setup_containers.py:80`). An `n2d-standard-2` has 8 GB, of which GKE keeps a reserve for the system, so only around 6 Gi is allocatable. System Pods, NGINX (128 Mi) and Chroma (128 Mi) also take a share.
- So roughly two frontend Pods fit per node. At 3 replicas one Pod goes `Pending` with `Insufficient memory`. The cluster autoscaler adds node #2 within a few minutes (max 2, `create_cluster.py:65`), and the Pod schedules there.
- At 5 replicas, about four fit on two nodes. The rest stay `Pending`, and the events say the node group's max size is reached.
- Scale back to 1. The extra node is removed after the autoscaler's cool-down.

**E3 (debugging: README command).** `kubectl logs -n cheese-app-cluster-namespace job/vector-db-loader -c wait-for-chromadb` (README 620) prints `Error from server (NotFound): namespaces "cheese-app-cluster-namespace" not found`. Why? After fixing the namespace, the next error is about the container name. Why?
*Worked answer:* the README section was written for the pre-refactor single-file program, which named the namespace `{cluster_name}-namespace` and gave the Job an init container `wait-for-chromadb` (visible at `git show 3149e56:src/deployment/deploy_k8s/__main__.py`). The current program names the namespace `cheese-app-namespace` (`create_cluster.py:143`), and the Job has only the container `vector-db-loader` (`setup_containers.py:213`). Use `kubectl logs -n cheese-app-namespace job/vector-db-loader`.

**E4 (debugging: 404 on the raw IP).** `curl http://34.9.143.147/` returns an nginx 404, but `curl http://34.9.143.147.sslip.io/` works. Both go to the same IP. Why?
*Worked answer:* the TCP path is the same. The difference is the HTTP `Host` header. The Ingress rule has `host=<IP>.sslip.io` (`setup_loadbalancer.py:79`), so NGINX has no rule for `Host: 34.9.143.147` and answers with its default 404. `curl -H "Host: 34.9.143.147.sslip.io" http://34.9.143.147/` would work too.

**E5 (debugging: `command` vs `args`).** On the `cluster-updates` branch the loader is written as `command=["cli.py", "--download", "--load", "--chunk_type", "recursive-split"]` (`cluster-updates:src/deployment/deploy_k8s/__main__.py:426-432`). Main uses `args=[...]` with the same list (`setup_containers.py:227-233`). Predict the loader Pod's status on the branch.
*Worked answer:* in Kubernetes, `command` replaces the image's ENTRYPOINT and `args` replaces its CMD. The vector-db image's ENTRYPOINT is `/bin/bash docker-entrypoint.sh` (`src/vector-db/Dockerfile:51`), which activates the venv and runs `uv run python $args` (`src/vector-db/docker-entrypoint.sh:12,22`). With `command=`, the runtime tries to exec a binary called `cli.py`, which is not on `$PATH` (and is not an executable file anyway). The Pod fails with a `StartError` / `RunContainerError` (`exec: "cli.py": executable file not found in $PATH`), Job retries until `backoffLimit`, and Pulumi marks the Job failed. With `args=`, the entrypoint receives `cli.py --download …` exactly as `docker run image cli.py …` did in L20.

**E6 (hands-on + conceptual: HPA needs requests).** Run
`kubectl autoscale deployment frontend --cpu-percent=50 --min=1 --max=3 -n cheese-app-namespace`
and the same for `api`. Then run `kubectl get hpa -n cheese-app-namespace`. Predict the TARGETS column for each.
*Worked answer:*
- `frontend` shows something like `cpu: 2%/50%`. Its container requests `250m` (`setup_containers.py:80`), so the metrics server's usage can be expressed as a percentage of the request.
- `api` shows `cpu: <unknown>/50%` and events like "missing request for cpu". The API container has no `resources` at all (`setup_containers.py:274-314`), so there is no denominator.
- Even with requests, scaling `api` past one node hits the RWO disk (§6, item 10).
- Clean up with `kubectl delete hpa frontend api -n cheese-app-namespace`.

**E7 (conceptual: Workload Identity).** Suppose you remove `service_account_name=ksa_name` from the API Pod spec (`setup_containers.py:261`) and run `pulumi up`. The Pod starts fine. What fails, when, and with what kind of error?
*Worked answer:*
- The Pod now runs as the namespace's `default` KSA, which has no `iam.gke.io/gcp-service-account` annotation and no `workloadIdentityUser` binding.
- On a Workload-Identity node the metadata server still hands out a token, but it is the bare workload-pool identity with no IAM roles on your project. Pods never see the node's `deployment` SA.
- Startup works: the TensorFlow model download is from GitHub, and `genai.Client(...)` only builds a client.
- The first chat message fails: the call to Vertex AI returns `403 PERMISSION_DENIED`, and the API answers 500. (The token behaviour follows GKE's documentation and was not tested; the 403 follows from the missing role.)

**E8 (conceptual: dependency design).** Why does `setup_containers.py:319-321` make the API Deployment depend on the loader *Job*, while `cluster-updates` makes it depend only on the vector-db Service? Give one advantage and one disadvantage of each.
*Worked answer:*
- **Main:** Pulumi waits for Job *Complete* (pulumi-kubernetes awaits Jobs), so the API never serves RAG queries against an empty collection.
  - Advantage: a consistent first start.
  - Disadvantage: a broken loader blocks the whole API for the 10-minute await timeout. Every image update that replaces the Job also re-gates the API rollout.
- **cluster-updates:** the API starts in parallel.
  - Advantage: faster deploys, and the frontend and API work even if the loader fails.
  - Disadvantage: early RAG requests can fail with a missing collection, and an operator may not notice the loader failed.

---

## 9. Errata and open questions

### Errata (with evidence)

1. **README outputs block is outdated.**
   - README 498–506 shows `nginx_ingress_ip` and `ingress_name: "nginx-ingress"`.
   - The code exports `ip_address` (`deploy_k8s/__main__.py:48`), and the Ingress is named `cheese-app-ingress` (`setup_loadbalancer.py:63-65`). Both were renamed in commit `44ceff4` ("Added SSL loadbalancer", 2025-11-21), after the README text.
2. **README debugging section uses names that no longer exist.**
   - README 620–656 uses namespace `cheese-app-cluster-namespace` and container `wait-for-chromadb`.
   - Current namespace: `cheese-app-namespace` (`create_cluster.py:143`). The Job has no init container (`setup_containers.py:199-243`).
   - The names come from the pre-refactor program at `3149e56`.
3. **No scaling step, despite the title.**
   - The README title is "Deployment & Scaling" (README 1, 392), but there are no `replicas`, no `kubectl scale` and no HPA anywhere in `main` (`git grep` for `HorizontalPodAutoscaler`, `replicas` and `autoscal` finds only the node pool, `create_cluster.py:63`, and the demo YAMLs).
   - Milestone 5 requires a scaling demonstration (`milestone5.md:39`).
4. **Missing IAM role for the Workload Identity binding.**
   - `create_cluster.py:184-189` writes an IAM policy on the `gcp-service` SA, which needs `iam.serviceAccounts.setIamPolicy`. The `deployment` role list (README 241–246) doesn't include a role that has it.
   - v4's README list doesn't either (`cheese-app-v4:README.md` lines 44–51).
   - This was not run. The conclusion rests on the documented contents of those predefined roles.
5. **The Artifact Registry repository is never created** (`deploy_images/__main__.py:4,14-15`). The same erratum appears in the L20 guide.
6. **Outdated registry wording.**
   - README 415 says "Build and Push Docker Containers to GCR", but the code pushes to Artifact Registry (`us-docker.pkg.dev`, `deploy_images/__main__.py:15`).
   - The warm-up asks you to enable "Google Container Registry API" (README 524). Container Registry has been shut down in favour of Artifact Registry.
7. **`kubectl version` (README 409) errors before a cluster exists.** It's harmless but confusing at the first checkpoint.
8. **SSL mode is undocumented and probably broken in v3.**
   - `setupSSL = False` is hard-coded (`deploy_k8s/__main__.py:17`). The config key `deploy-k8s:setupSSL` (`Pulumi.dev.yaml:7`) is never read, `Pulumi.ssl.yaml` has no such key, and `src/deployment/README.md` is only the heading `# SSL Setup`.
   - v4 changes exactly the lines that look wrong:
     - FrontendConfig `apiVersion` `networking.gke.io/v1` (`setup_loadbalancer_ssl.py:36`) → `v1beta1` (`cheese-app-v4:…/setup_loadbalancer_ssl.py:39`).
     - The class moves from `ingress_class_name="gce"` (`:59`) to the annotation (`cheese-app-v4:…:56`).
     - A `BackendConfig` health check on `/api-service/` is added for the API (`cheese-app-v4:src/deployment/deploy_k8s/setup_containers.py:324-345`). Without it, GCE's default health check hits `/`, which the `ROOT_PATH`-mounted API answers with 404.
     - The FrontendConfig annotation key changes from `networking.gke.io/frontend-config` (`setup_loadbalancer_ssl.py:55`) to `networking.gke.io/v1beta1.frontend-config` (`cheese-app-v4:…:59`). GKE's documented key appears to be `networking.gke.io/v1beta1.FrontendConfig`, so the HTTPS redirect may be ignored in both versions (unverified).
     - The SSL API path changes from `/api-service/` (`setup_loadbalancer_ssl.py:67`) to `/api-service` (`cheese-app-v4:…:70`).
   - The SSL `app_url` is still built with `http://` (`deploy_k8s/__main__.py:49`).
9. **Dead or misleading annotations and comments.**
   - `cert-manager.io/cluster-issuer: letsencrypt-prod` (`setup_loadbalancer.py:69`) refers to a cert-manager that is never installed. It is a leftover of the experiment in `cluster-updates:src/deployment/deploy_k8s/dump.py:1176-1203`.
   - `setup_loadbalancer.py:55` describes the community chart's service naming, not this F5 chart's.
   - "Temporary storage (lost on restart)" (`setup_containers.py:269`) and "Temporary file storage" (`:289`) are wrong for a PVC.
   - "Retry up to 4 times" (`:206`) for `backoff_limit=3` is off by one: it means 3 retries, 4 attempts.
   - "(placeholder - needs to be filled)" (`:71,278`) is stale.
   - Unused: `base_config` and `initial_node_count` (`create_cluster.py:8,13`), and the Pod env `GCS_BUCKET_NAME` (`setup_containers.py:294-295`), which no API code reads (`grep -rn GCS_BUCKET_NAME src/api-service/api` finds nothing).
10. **ChromaDB image unpinned, mount path possibly stale.**
    - `image="chromadb/chroma"` (`setup_containers.py:132`) is mounted at `/chroma/chroma` (`:150`). That is the 0.x layout: the `cluster-updates` branch pins `0.5.6` with the same path (`cluster-updates:…/__main__.py:328,346`).
    - The course's newer `llm-rag` mounts `chromadb/chroma:latest` at `/data` (`llm-rag:docker-compose.yml:19,24`).
    - If current images persist to `/data`, the 10 Gi PVC is unused and the vector DB is lost whenever its Pod restarts. The image was not inspected to confirm this.
11. **Control-plane CIDR outside RFC 1918.** `master_ipv4_cidr_block: "172.0.0.0/28"` (`create_cluster.py:33`; same on `cluster-updates:…:90`) is public address space; RFC 1918's 172 block is 172.16.0.0/12. It evidently worked for the course, but `172.16.0.0/28` would be the conventional choice.
12. **Kubeconfig convenience is ephemeral.**
    - The `connect-k8s-command` (`create_cluster.py:192-199`) runs once, inside a `--rm` container, so later sessions have no kubeconfig and the README never says how to restore it.
    - It passes the *region* to `--zone` (`:197`), see the open questions.
13. **Demo manifest that cannot work on Kubernetes.** `visualizer.yaml:18` runs `dockersamples/visualizer`, a Docker Swarm visualizer that needs the Docker socket and Swarm. It is not referenced in the README. `emoji.yaml` (added by `11bd16e`) isn't referenced either.
14. **Anchor structure.** The course link points at `#deployment-with-scaling-using-kubernetes` (README 392), but the actual cluster steps are under a separate H2, "Create & Deploy Cluster" (README 436). Readers following the course link may stop at line 434.
15. **README 318–322** ("Deployment Setup … inventory.yml") are Ansible-era leftovers in the shared prerequisites. The SSH/OS Login steps before them (282–316) are only needed for L20's `security:ssh_user`; none of this is needed for `deploy_k8s`.
16. **README Mermaid diagram edge reversed.** `V -.->|one-time load| J` (README 466) draws the arrow from the vector-db Service to the loader Job; the Job writes into the vector DB (`setup_containers.py:199-243`, `src/vector-db/cli.py:271-311`).
17. **Unused env var in `deploy_images`.** `location = os.environ["GCP_REGION"]` (`deploy_images/__main__.py:10`) is required but never used; the registry host is hard-coded (`:15`). Likewise `artifactregistry` is imported (`:4`) but unused.

### Open questions (could not be determined from the sources)

- **Ed lesson content:** https://edstem.org/us/courses/97373/lessons/166047/ was not accessible. Slides or announcements there may update any of the above.
- **`gcloud container clusters get-credentials … --zone us-central1`** (`create_cluster.py:195-197`): gcloud probably forwards the value as the cluster *location*, so it would work for a regional cluster, but this was not run. `--region us-central1` is the unambiguous form.
- **ChromaDB persistence path** in the image `chromadb/chroma` pulled today (§6, item 14; erratum 10).
- **Whether the IAM Service Account Credentials API must be enabled** for Workload Identity in a fresh project.
- **Whether `deployment` in the instructors' project had extra roles** that hid erratum 4.
- **Exact Helm release name** that Pulumi generates for `nginx-f5`, and whether chart `nginx-ingress` `2.3.1` from `https://helm.nginx.com/stable` (`setup_loadbalancer.py:13-17`) is still served. The code's lookup relies on both (`:49-58`).
- **Does `pulumi up --refresh` revert a manual `kubectl scale`?** The program never sets `replicas`, and pulumi-kubernetes 4.x uses server-side apply, so the manual value is expected to survive. Verify with `kubectl get deploy -n cheese-app-namespace` after an update.
- **GKE version in October 2026 vs kubectl 1.34** in the toolbox: the size of the skew depends on the release channel at the time you create the cluster.
- **Current prices and free-tier rules** for GKE management fees, NAT and load balancers. The numbers in §2 are approximate and were not checked against the current price list.
- **Run time and memory:** the stack was not run. The 15–25 minute estimate and whether Chroma fits in its 256 Mi limit during the load (`setup_containers.py:155`) are unverified.
- **Chroma client at API import:** `chromadb.HttpClient(...)` (`src/api-service/api/utils/llm_rag_utils.py:57`, chromadb 1.3.0 per `src/api-service/uv.lock`) is created at import. It probably contacts the server (tenant/database check) and raises if Chroma is down, which would crash-loop the API (§6, item 13); not verified by running it.
- **FrontendConfig annotation key** in SSL mode (erratum 8): whether GKE honours `networking.gke.io/frontend-config` or `networking.gke.io/v1beta1.frontend-config`, or only the documented `networking.gke.io/v1beta1.FrontendConfig`.

---

## Links

**cheese-app-v3 README** (`main` @ `3ecef56`)
- [Deployment with Scaling using Kubernetes](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deployment-with-scaling-using-kubernetes): [API's to enable in GCP for Project](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#apis-to-enable-in-gcp-for-project) · [Start Deployment Docker Container](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#start-deployment-docker-container) · [Build and Push Docker Containers to GCR](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#build-and-push-docker-containers-to-gcr)
- [Create & Deploy Cluster](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create--deploy-cluster): [Try some kubectl commands](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#try-some-kubectl-commands) · [If you want to shell into a container in a Pod](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#if-you-want-to-shell-into-a-container-in-a-pod) · [View the App](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#view-the-app) · [Delete Cluster](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#delete-cluster)
- Optional warm-up, [Create Simple Kubernetes Cluster Tutorial](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-simple-kubernetes-cluster-tutorial): [Create Cluster](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#create-cluster) · [Checkout the cluster in GCP](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#checkout-the-cluster-in-gcp) · [Try some kubectl commands](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#try-some-kubectl-commands-1) · [Deploy the App](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#deploy-the-app) · [Get the Loadbalancer external IP](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#get-the-loadbalancer-external-ip) · [View the App](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#view-the-app-1) · [Delete Cluster](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#delete-cluster-1)
- [Debugging Containers](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#debugging-containers) (the `kubectl` half is partly outdated, §9) · reused from L20: [Setup GCP Service Account for deployment](https://github.com/dlops-io/cheese-app-v3/blob/3ecef56fea879ac480d260c0906cd95baf05179a/README.md#setup-gcp-service-account-for-deployment)
- Code at the pinned commit: [`src/deployment/deploy_k8s/`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a/src/deployment/deploy_k8s) · latest README on [`main`](https://github.com/dlops-io/cheese-app-v3#deployment-with-scaling-using-kubernetes)
- Context branches and repos cited in §7 and §9 (pinned commits): [`cluster-updates` @ `e55178c`](https://github.com/dlops-io/cheese-app-v3/tree/e55178c0f66d8636d00e7deea7e744640bb8d595) · [`pipenv` @ `0012c9a`](https://github.com/dlops-io/cheese-app-v3/tree/0012c9a512b1a266f4c87fad09d84a3b52470f5b) · [`dlops-io/cheese-app-v4` @ `033f187`](https://github.com/dlops-io/cheese-app-v4/tree/033f18713b9e1e7985a3080e85edab3ff01cefef) · [`dlops-io/llm-rag` @ `e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91)

**Course**
- Ed lesson: [L22 · Scaling: Kubernetes (cloud)](https://edstem.org/us/courses/97373/lessons/166047/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/) · [Milestone 5](https://harvard-iacs.github.io/2026-AC215/milestone5/)
- Colab notebooks: none for this lecture.
- Previous lecture: [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md) (`cheese-app-ci-cd`). L19 · Scaling: Kubernetes (local) has no tutorial yet ("coming soon" on the course site), so it has no guide.
- Next lecture: [L23 · Final Deployment and Review](L23-final-cicd-deployment.md) (`cheese-app-v4`: the same cluster, deployed by GitHub Actions)
- Referenced in §7: [L20 · Deployment: Pulumi](L20-deployment-pulumi.md) (the toolbox, `deploy_images` and the single-VM deployment) · [L18 · APIs + Frontend](L18-apis-frontend.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md) · [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md)
