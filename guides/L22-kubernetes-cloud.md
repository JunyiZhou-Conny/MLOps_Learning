# L22 · Scaling: Kubernetes (cloud) — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166047/) · Tutorial: [`dlops-io/cheese-app-v3`](https://github.com/dlops-io/cheese-app-v3) `main` @ [`3ecef56`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a) (README sections "Deployment with Scaling using Kubernetes" and "Create & Deploy Cluster", plus the optional warm-up "Create Simple Kubernetes Cluster Tutorial"; `main` re-checked with `git ls-remote` on 2026-11-07; comparison branches `cluster-updates` and `pipenv`, see §7) · Colab: none for this lecture · Video: [AC215 · L22 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l22-kubernetes-cloud) · Made from the verified digest and real terminal captures, 2026-11-07

## 中文速览

- **做什么：** 把 L20 跑在一台 VM 上的四个 cheese-app container（Next.js `frontend`、FastAPI `api`、ChromaDB `vector-db`、一次性的 `vector-db-loader`）搬到 managed Kubernetes（GKE）上，全部用 Pulumi Python 描述。还是 L20 那个 deployment toolbox，新 project 叫 `deploy_k8s`：custom VPC + Cloud Router + **Cloud NAT**、regional GKE cluster（**private nodes**、**Workload Identity**）、一个 node pool（`n2d-standard-2`，`us-central1-a`，autoscaling 1–2 nodes）、namespace `cheese-app-namespace`、2 个 PVC、3 个 Deployment + ClusterIP Service、1 个 loader Job，再用 Helm 装 F5 NGINX Ingress Controller。`pulumi preview` 的 plan 是 **`+ 23 to create`**（2026-11-07 capture）。最后 app 在 `http://<LB-IP>.sslip.io`。
- **Idea 1 · desired state：** 你不“运行” container，只是把 object 写进 API server。Deployment → ReplicaSet（名字里带 Pod template 的 hash）→ Pod，controller 一直对比 desired 和 actual：delete 一个 Pod，ReplicaSet 马上补一个（capture 里 1 秒后就是 `ContainerCreating`，名字保留 hash、换新 suffix）。Job 是 run-to-completion 版本。Pulumi 会等 loader Job *Complete* 之后才去建 API Deployment。
- **Idea 2 · label、Service、cluster DNS、namespace：** Pod 会死、IP 会变；Service 用 label selector（`run: api` 等）给一个稳定的名字和 virtual IP，所以 API 直接连 `vector-db:8000`。`kubectl` 默认只看 `default` namespace（`kubectl get all` 只有 `service/kubernetes`），记得加 `-n cheese-app-namespace`。
- **Idea 3 · 一个 request 怎么走：** sslip.io DNS → GCP network load balancer → NGINX controller Pod（看 **Host header** + path prefix）→ Service → Pod。`/api-service` prefix **不会被剥掉**，所以 API 用 `ROOT_PATH=/api-service` mount 所有 route；调 API 的是**浏览器**，不是 frontend Pod。用裸 IP 打开只会得到 NGINX 的 404。
- **Idea 4 · 没有 key file 的 identity：** kubeconfig 里的 user 是 `gke-gcloud-auth-plugin` exec plugin，没有密码。Pod 走 Workload Identity：KSA `api-ksa` 上的 annotation + IAM 的 `roles/iam.workloadIdentityUser` binding，两边都要有，Pod 才能以 GSA `gcp-service` 的身份调 Vertex AI。L20 的 `gcp-service.json` 在 cluster 里用不到。
- **Idea 5 · 两层 scaling：** Pod 层（`replicas`、HPA）和 node 层（cluster autoscaler，这里 1–2 nodes）。scheduler 按 resource **requests** 打包（一个 frontend Pod 就 request 2 Gi）。`deploy_k8s` 里**没有 HPA，也没有 `replicas` 字段**，Milestone 5 要你 demo scaling，自己用 `kubectl scale`。PVC 是 ReadWriteOnce：`api` / `vector-db` 跨 node 多开会卡在 Multi-Attach error，加 node 也没用。
- **最费时间的坑：** ① toolbox 照 commit 的样子 build 不起来（和 L20 一样）：`Dockerfile:4` 的 `bullseye` 改成 `bookworm`，`Dockerfile:30` 的 `google-cloud-sdk…` 改成 `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin`，两处一行的修改之后 92 秒 build 完。② 如果 `deploy_images` 没有在同一个 state bucket 里 `pulumi up` 过，`deploy_k8s` 的 preview 直接报 `setup_containers.py", line 70` … `TypeError: 'NoneType' object is not subscriptable`。③ `deployment` SA 那 6 个 role 都不能改 service account 的 IAM policy，`pulumi up` 很可能停在 `api-gsa-wi-user`：先给它 `gcp-service` 上的 Service Account Admin（§2，未在真 project 上测过）；`cheese-app-repository` 也没有 code 去建。④ kubeconfig 只活在这次 `--rm` container 里，重开后 `kubectl` 报 `The connection to the server localhost:8080 was refused`：跑 `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>`。
- **README 过时的地方：** debugging 段的 14 条 `kubectl` 全部失败（namespace `cheese-app-cluster-namespace` 不存在，init container `wait-for-chromadb` 也没有了），`<pod-name>` 会被 shell 当成 redirection；outputs block 里的 `nginx_ingress_ip` 现在叫 `ip_address`；`kubectl version --client` 显示的是 gcloud 的 `v1.35.9-dispatcher`，不是 Dockerfile pin 的 1.34。另外 code 里写死的 `gemini-2.0-flash-001` 按 L20 guide 的核查已于 2026-06-01 retired：`/api-service/status` 正常但 chat 失败时，先怀疑 model，再查 Workload Identity。
- **做完要删（当天就删）：** cluster 开着大约 $5–8/天。在 `/app/deploy_k8s` 跑 `pulumi destroy --stack dev --refresh -y`，再用 `gcloud compute forwarding-rules list`、`gcloud compute disks list`（找 `pvc-…`）、`gcloud compute firewall-rules list` 等查漏网的 LB 和 disk（这些删除是 asynchronous 的）；Artifact Registry 的 image 是 `retain_on_delete=True`，要手动删；L20 的 VM 和 warm-up 的 `test-cluster` 如果还在，也要删（warm-up 先 `kubectl delete -f`，再删 cluster）。
- **Lecture slides：** 老师的 Lecture 22 slides（45 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天 repo 不一样的 14 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的三处：① slides 说 Kubernetes 会按 CPU、memory 自动 scale，但 `deploy_k8s` 里没有 `replicas` 也没有 HPA，只有 node autoscaler（1–2 nodes），Milestone 5 要的 scaling 得你自己用 `kubectl scale` 做。② slides 用 `gcloud` 建、删 cluster，用 `get-credentials … --zone us-east1-c` 连上；cheese app 的 cluster 由 `pulumi up` / `pulumi destroy` 管，每次新开 container 都要跑 `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>`。③ slides 里每个 app 各有一个 `LoadBalancer` Service；cheese app 的三个 Service 都是 `ClusterIP`，只有 NGINX Ingress controller 有 external IP。另外，slides 画的 master nodes 和 Docker runtime，在 GKE 上分别是 Google 管的 control plane 和 containerd。

## At a glance

**What you build.** The same four cheese-app containers that ran on one VM in L20 (Next.js frontend, FastAPI API, ChromaDB and a one-shot loader) run on a managed GKE cluster that a new Pulumi project, `deploy_k8s`, describes in Python: a private-node regional cluster with a 1–2-node autoscaling pool behind Cloud NAT, Workload Identity for the API's Vertex AI calls, two persistent volumes, three Deployments with Services, a loader Job, and an NGINX Ingress controller behind a GCP load balancer. You end with the app at `http://<LB-IP>.sslip.io`, explore it with `kubectl`, scale the frontend by hand, and remove everything with one `pulumi destroy`.

**What "scaling" means in this code.** The program has **no HorizontalPodAutoscaler and no `replicas` field**. Every Deployment runs one Pod. The only automatic scaling is the **node pool autoscaler** (1–2 nodes, `src/deployment/deploy_k8s/create_cluster.py:63-66`). Manual and Pod-level scaling (`kubectl scale`, HPA) are explained in §3.6 and practised in Step 12 and §8. Milestone 5 asks you to demonstrate manual scaling (`milestone5.md:39`).

**Time needed** (estimate; the GKE stack itself could not be run for this guide, see *Versions and sources*). Optional warm-up: about 20 minutes. One-time setup (APIs, the extra IAM role, the two Dockerfile fixes, building and starting the toolbox: the build took 92.3 s on an amd64 machine on 2026-11-07): about 30 minutes. Images: nothing if you built them in L20; otherwise tens of minutes under amd64 emulation on Apple Silicon (the API image installs TensorFlow). `pulumi up` for the cluster and app: roughly 15–25 minutes. Exploring, scaling and one redeploy: about 1 h. Destroy and the leftover checks: about 15 minutes. In total about 2.5–3 h; plan to destroy the same day.

**Prerequisites.**
- A GCP project with billing enabled, and its project ID. The README commands and `src/deployment/docker-shell.sh:13` hard-code the instructor's `ac215-project`.
- Docker Desktop and `git`. Everything else (gcloud, kubectl, Helm, Pulumi, `gke-gcloud-auth-plugin`, uv) lives in the L20 deployment toolbox, which needs the same two one-line Dockerfile fixes as in L20 before it builds (§2).
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
- **Pin re-checked 2026-11-07:** `git ls-remote` gave `HEAD` = `main` = `3ecef56…`, `cluster-updates` = `e55178c…`, `pipenv` = `0012c9a…`; the remote has one more, unmerged staff branch (`work/‹staff›`), not used here.
- **Terminal captures (the strongest evidence in this guide).** Recorded 2026-11-07 (20:47–21:16 UTC) in a sandbox with **no GCP project, no Google account and no credentials**, in three layers:
  - *Laptop and toolbox, live:* a fresh Docker 29.8.2 engine standing in for a laptop with Docker Desktop; the clone; `sh docker-shell.sh` failing as committed, the two fixes, the toolbox built and started; every gcloud, Pulumi and kubectl command of the README's K8s sections typed at the toolbox prompt. Commands that need Google stop at their first honest error (`You do not currently have an active account selected`, `PULUMI_ACCESS_TOKEN must be set …`, `invalid_grant: account not found`). The key in `secrets/` was a well-formed placeholder for no account, and `GCP_PROJECT` was set to `your-gcp-project`.
  - *Pulumi on its local file backend* (`pulumi login --local`, a recording workaround, not a step for you): the README's stack, config, `preview`, `up` and `destroy` commands on the unchanged programs, up to their first Google call. With a capture-only stand-in image stack (placeholder tags, nothing built), `deploy_k8s`'s real plan appears (`+ 23 to create`) and `pulumi up` stops at the first resource, the VPC.
  - *A stand-in cluster:* kind v0.31.0 (Kubernetes in Docker), one control plane and two workers, Kubernetes v1.34.11, in the same laptop engine. The toolbox's own kubectl ran the README's kubectl commands verbatim against it. It is **not GKE**: no cloud load balancer (`EXTERNAL-IP` stays `<pending>`), no node pool or autoscaler, no Workload Identity, and its control-plane Pods are visible. Outputs from it are labelled *stand-in* below.
  - Versions seen: Google Cloud SDK 592.0.0 (gke-gcloud-auth-plugin 0.5.21), kubectl = gcloud's dispatcher (`v1.35.9-dispatcher` with no cluster; `v1.34.12-gke.300…` against the 1.34 stand-in), Helm v3.22.1, Pulumi v3.274.1, uv 0.13.7, toolbox Python 3.13.18; Pulumi plugins kubernetes 4.23.0, gcp 9.3.0, docker-build 0.0.15, command 1.1.3, docker 4.9.0.
  - Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l22-kubernetes-cloud/assets/terminal) (`laptop/`, `kind/`, `expected/`, with `capture.sh` and `run_steps.sh`); provenance in `ASSETS.md` in the same video folder. File names such as `laptop/b03` or `kind/k53` below point there. Where the digest predicted an output and the captures differ (the kubectl version, the error for a missing image stack, the wording of the debugging errors), this guide follows the captures.
- **Not captured, because they need a Google account and billing:** the GKE cluster itself, `pulumi up` creating it, the real `Outputs:` block, the cheese-app Pods, the app in a browser, a RAG chat reply and a real `pulumi destroy`. Those steps show the README's own output (labelled *expected*) or describe what to look for.
- **Path convention:** every `path:line` is relative to the `cheese-app-v3/` repository root at the `main` commit above, unless a prefix names another source: `cluster-updates:` (that branch), `pipenv:` (that branch), `cheese-app-v4:` or `llm-rag:`. `tutorials_demo.md` and `milestone5.md` are files of the course-site source (`2026-AC215`). Every reference was checked with `sed -n`/`grep -n`. Code blocks headed `path:start-end` were copied from those exact line ranges and checked mechanically. Verified against the repos on 2026-10-13 (adversarial check) and re-checked on 2026-11-07; the course-site files were not available on 2026-11-07, so their line numbers are carried over from the first check.
- **Ed lesson:** not accessible when these sources were checked. This guide is built from the course site and the repositories.
- **Colab notebooks:** none for this lecture.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 22: Scaling: Kubernetes (cloud)*, 45 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l22-kubernetes-cloud/SLIDES.md`. The deck teaches Kubernetes itself (why it exists, the parts of a cluster, `kubectl`) and runs the optional warm-up by hand. For the cheese app it only hands over to the README (slide 41), so everything inside `deploy_k8s` is tutorial-only. The README's one picture is a Mermaid diagram of the request path; the slides add the motivation story (5, 9, 13) and the parts of a cluster (22–26).

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 13 (the app on Kubernetes), 21–22 (the cheese app on one VM, then aimed at a cluster), 41 (handover to the README) |
| §2 Prerequisites and costs; *Tear down, exactly* | 32, 34 (`gcloud` and `kubectl`, here preinstalled in the deployment container), 40, 44 |
| Checklist *Create Simple Kubernetes Cluster Tutorial*; §4 Part 0 | 32–40: create (32–33), check the tools and the cluster (34–36), the console (37), tic-tac-toe (38–39), delete (40) |
| Checklist *Deployment with Scaling using Kubernetes* and *Create & Deploy Cluster*; §4 Steps 1–11 and 13 | 41 only: the Pulumi steps are tutorial-only. The `kubectl` checks use the commands of slides 27–29 and 34–36 |
| §3.1 Cluster = control plane + node pools | 17–19, 22–26 (node pools, regional clusters, private nodes and NAT are tutorial-only) |
| §3.2 Desired state | 7, 11, 15, 18, 25, 30, 36, 39 (ReplicaSets and Jobs are tutorial-only) |
| §3.3 Labels, Services, cluster DNS and namespaces | 29, 35, 39 (labels and DNS are tutorial-only; namespaces too, apart from slide 29's passing mention of the default namespace) |
| §3.4 How a request reaches a Pod | 5, 21, 24–26, 38–39 (Ingress, Helm and `sslip.io` are tutorial-only) |
| §3.5 Persistent storage; §3.7 Identity; §3.8 Pulumi | none, except 33 (`get-credentials`) for §3.7 and 41 for §3.8 |
| §3.6 Scaling; §4 Step 12 | 12, 15, 18, 39 (`replicas: 2`), 43 |
| §4 Step 14 | 40, 44 |
| §6 gotchas 1, 2 and 19 | 33–35 |
| §7 Where this sits in the course | 4–15, 20, 43 |
| §5, §8, §9 | none, except §5 excerpts 6–7 (slide 39's two objects, with the labels the slide leaves out) and §8 Q1 (the restart that Support did by hand, slide 7) |

**Lecture ideas you need for this tutorial**
1. One VM is a single point of failure: when a container crashes, someone has to notice, SSH in and restart it, and backup copies on more VMs still need a human to switch to them (slides 4–11).
2. Kubernetes automates three jobs that operators do by hand: failover, load balancing and scaling. It orchestrates containers across a cluster of VMs called nodes (slides 12–15, 17, 19).
3. You declare what should run (Pods, Services, Deployments), and Kubernetes keeps it that way (slides 18, 30).
4. A cluster is a control plane that decides plus worker nodes that run the containers. On GKE, Google runs the control plane and you only see the workers (slides 22–23, 36).
5. Inside the control plane: the API server is the single entry point, etcd stores the cluster's state, the scheduler places Pods on nodes, and the controllers watch, replace, and ask the cloud for nodes and IP addresses (slides 24–25).
6. On each worker: the kubelet runs the Pods the API server assigns to it, kube-proxy routes Service traffic, and the container runtime runs the containers (slides 24, 26).
7. `kubectl` talks only to the API server, always in the form `kubectl [command] [TYPE] [NAME] [flags]`; `-n cheese-app-namespace` is just a flag (slides 27–29).
8. `gcloud` creates, connects to and deletes clusters; `kubectl` manages what runs inside them. For the cheese app, Pulumi does `gcloud`'s part (slides 32–36, 40).
9. A Deployment says what runs in a Pod and how many copies, and keeps them running. A Service routes traffic to those Pods, so any one of them may die. A Service of type `LoadBalancer` gets an external IP (slides 38–39).
10. Delete the cluster when you are done (slides 40, 44).

**Where the slides and today's tutorial differ** (in each case the repo, as verified here, is what runs today)
- Slide 18 promises scaling on CPU, memory or custom metrics, slide 15 ticks "Scaling" and slide 43 promises automatic adjustment to load. The cheese app sets no `replicas` and has no HPA; only the node pool scales itself, from 1 to 2 nodes. Scale Pods yourself with `kubectl scale` (§3.6, §4 Step 12, §9 erratum 3).
- Slides 8, 13 and 15 promise failover to a backup. Every cheese-app Deployment runs one Pod, so a crash means a restart, not a switch. The nodes sit in one zone, and the API and the vector DB cannot have a replica on a second node because their disks are ReadWriteOnce (§3.5, §6 item 10).
- Slide 13 runs one cluster per component. The cheese app runs everything in one cluster and one namespace, `cheese-app-namespace` (§1).
- Slides 32–33 create the warm-up cluster with `--num-nodes 1`; the README (line 541) uses `--num-nodes 2`. The slides' outputs show old versions (GKE 1.20 on slides 33 and 36, kubectl 1.22 on slide 34) (§4 Part 0).
- Slides 32 and 40 create and delete clusters with `gcloud`, and slide 34 says you need `kubectl` to create one. The cheese-app cluster is created by `pulumi up` and removed by `pulumi destroy`, and `kubectl` never creates clusters (§4 Steps 7, 14).
- Slide 33 connects with `get-credentials … --zone us-east1-c --project ac215-project`. For the cheese app, run `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>` in each new container session (§6 item 2).
- Slides 32 and 34 say to install `gcloud` and `kubectl`. They are already in the deployment container (kubectl is gcloud's dispatcher, `v1.35.9-dispatcher` on 2026-11-07), together with Helm and `gke-gcloud-auth-plugin`, which the slides do not list (§2).
- Slide 35 runs `kubectl get componentstatuses` and shows healthy components. The command has been deprecated since Kubernetes 1.19 and prints a warning (§4 Part 0, step 0.3; §6 item 19).
- Slide 23 draws the control plane as master nodes. On GKE Google runs it and you never see its machines: `kubectl get nodes` lists only workers (§3.1).
- Slides 19, 22 and 26 say the nodes run Docker. GKE nodes run containerd (`cos_containerd`), and Docker-built images run unchanged (§3.1).
- Slides 38–39 expose each app with its own `LoadBalancer` Service. In the cheese app the three Services are `ClusterIP`: only the NGINX Ingress controller's Service gets an external IP, and an Ingress routes by host and path (§3.3, §3.4).
- Slide 39's YAML leaves out `metadata.name`, the selector and the Pod template, so Kubernetes would reject it. The real `deploy-k8s-tic-tac-toe.yml` links the Deployment and the Service through the label `run: web`; the cheese app does the same with `run: frontend` (§5 excerpts 6–7).
- Slide 21 labels the vector DB link "TCP/IP 5432". ChromaDB listens on 8000, and a fifth container, the loader, becomes a Job in L22 (§1).
- Slide 29 port-forwards "so you can open it in your browser". The deployment container publishes no ports, so the forwarded port is reachable only inside the container: `curl` it there (§3.4).

## Command checklist

Commands in backticks are exactly as the README writes them, in README order (placeholders kept: replace `ac215-project` with your project ID and `api-c4fb784b-2llgs` with your own Pod name, and replace an angle-bracket placeholder together with its brackets). Plain items are console clicks or checks. Items marked *(extra)* are not in the README; they come from §2, §3, §4, §6 and §8 of this guide. Where a command fails as printed today, it stays verbatim and the working variant follows as a note, with the capture that shows it (`laptop/…`, `kind/…` in the video folder's `assets/terminal/`). From `sh docker-shell.sh` on, everything runs inside the deployment toolbox (prompt `root@<id>:/app#`).

Two ordering notes. The README puts the optional warm-up, *Create Simple Kubernetes Cluster Tutorial*, after the cheese-app deployment; the lecture (slides 32–40) and the video do it first, because it is the gentler first contact with `kubectl`, so consider doing it first. The Kubernetes part of *Debugging Containers* comes last in the README but needs the running cheese-app cluster: use it before *Delete Cluster*.

### Before the README *(extra)*

- [ ] `git clone https://github.com/dlops-io/cheese-app-v3.git` — *(extra)* get the code, or keep your L20 clone (`Cloning into 'cheese-app-v3'...`). If you use this workspace's `tools/sync_tutorials.py`, the clone is `tutorials/cheese-app-v3`.
- [ ] `git -C cheese-app-v3 log -1 --format='%H %ci %s'` — *(extra)* the capture shows `3ecef56fea879ac480d260c0906cd95baf05179a 2025-11-28 16:00:06 -0500 v4->v3` (`laptop/p02`); a different hash means the repo has changed since this guide was made.
- [ ] *(extra)* `deployment.json` sits in the `secrets/` folder **next to** the repo folder (`~/Desktop/AC215/secrets/` for a clone at `~/Desktop/AC215/cheese-app-v3`; `docker-shell.sh:9` looks three levels up from `src/deployment`).

### Deployment with Scaling using Kubernetes

*API's to enable in GCP for Project* (README lines 396–402)
- [ ] Search for and enable Compute Engine API, Service Usage API, Cloud Resource Manager API, Artifact Registry API and Kubernetes Engine API.
- [ ] *(extra)* Check that the Vertex AI API is enabled too (the API Pods call Gemini and the embedding model).

*Service accounts* (README lines 236–259, done in L20)
- [ ] `deployment` with Compute Admin, Compute OS Login, Artifact Registry Administrator, Kubernetes Engine Admin, Service Account User, Storage Admin; its JSON key saved as `secrets/deployment.json`.
- [ ] `gcp-service` with Storage Object Viewer, Vertex AI Administrator, Artifact Registry Reader. No key is needed in K8s; only its e-mail is used.
- [ ] *(extra)* Let `deployment` write the Workload Identity binding. Run once from Cloud Shell, or any shell where *you* are logged in as project owner (§2; or add "Service Account Admin" to `deployment` project-wide in the console). Not tested against a real project:
  ```
  gcloud iam service-accounts add-iam-policy-binding gcp-service@<PROJECT>.iam.gserviceaccount.com \
    --member=serviceAccount:deployment@<PROJECT>.iam.gserviceaccount.com --role=roles/iam.serviceAccountAdmin
  ```

*Start Deployment Docker Container* (README lines 404–413)
- [ ] *(extra)* Set `GCP_PROJECT` to your project ID on line 13 of `src/deployment/docker-shell.sh` (the L20 step at README line 267); the capture used the placeholder: `13:export GCP_PROJECT="your-gcp-project" # Change to your GCP Project` (`laptop/b01`).
- [ ] `cd deployment` — the folder is `src/deployment` from the repo root.
- [ ] `sh docker-shell.sh` — builds `cheese-app-deployment` for `linux/amd64` and runs it with your code at `/app` and secrets at `/secrets`; if the container already runs in another terminal, it attaches to it. As committed it does **not** build today: `ERROR [ 2/16] RUN apt-get update …`, 22 × `E: Failed to fetch …/debian-security/pool/updates/… 404  Not Found`, then `Unable to find image 'cheese-app-deployment:latest' locally` and `pull access denied`, exit 125 (`laptop/b02`). Working variant: the two edits below, then run it again.
- [ ] *(extra)* Fix 1, in `src/deployment/Dockerfile:4`: `FROM python:3.13-slim-bullseye` → `FROM python:3.13-slim-bookworm` (`laptop/b02a`).
- [ ] *(extra)* Fix 2, in `src/deployment/Dockerfile:30`: `google-cloud-sdk google-cloud-sdk-gke-gcloud-auth-plugin` → `google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin` (`laptop/b02a`). The auth plugin in this line is what every `kubectl` call to GKE runs. With both, `[+] Building 92.3s (21/21) FINISHED`, `Container is running!!!` and a prompt in `/app` (`laptop/b03`); with your key, the entrypoint then activates `deployment` and logs Pulumi in to `gs://<project>-pulumi-state-bucket`.
- [ ] `gcloud --version` — `Google Cloud SDK 592.0.0` … `gke-gcloud-auth-plugin 0.5.21`, `kubectl 1.35.9` (`laptop/b10`).
- [ ] `kubectl version` — `Client Version: v1.35.9-dispatcher`, then `The connection to the server localhost:8080 was refused - did you specify the right host or port?`, exit 1: no cluster yet; harmless (`laptop/b11`).
- [ ] `kubectl version --client` — `Client Version: v1.35.9-dispatcher` (`laptop/b12`). Not the 1.34 the Dockerfile pins: Google's own `kubectl` package wins and dispatches to a client that matches each cluster (§6 item 19).
- [ ] `gcloud auth list` — yours lists `deployment@<project>.iam.gserviceaccount.com` as active. The capture, with a key for no account, says `No credentialed accounts.` (`laptop/b13`).
- [ ] `gcloud artifacts repositories create cheese-app-repository --repository-format=docker --location=us` — *(extra)* only if you did not create it in L20; no code creates it. Not run in the captures.

*Build and Push Docker Containers to GCR* (README lines 415–434; only if you have NOT already done this, in the same state bucket)
- [ ] cd into `deploy_images` — `/app/deploy_images`.
- [ ] `pulumi stack init dev` — `Created stack 'dev'`; the state goes to the GCS bucket. `error: PULUMI_ACCESS_TOKEN must be set for login during non-interactive CLI sessions` means the entrypoint's bucket login failed earlier: scroll up in the toolbox output (`laptop/b20`, §6 item 22).
- [ ] `pulumi config set gcp:project ac215-project --stack dev` — your project ID; prints nothing.
- [ ] `pulumi stack select dev` — *(extra)* instead of `init` if you get `stack 'dev' already exists`.
- [ ] `pulumi preview --stack dev` — downloads the provider plugins, then `+ docker-build:index:Image build-cheese-app-…` × 3 with `warning: Skipping preview build because some inputs are unknown.`, three `…-tags` outputs stamped with the current time, `+ 4 to create` (`laptop/c03`, local backend).
- [ ] `pulumi up --stack dev -y` — builds the three images for `linux/amd64` and pushes them with timestamp tags; `Outputs:` lists `cheese-app-api-service-tags`, `cheese-app-frontend-react-tags` and `cheese-app-vector-db-cli-tags`. Not run to the end in the captures (no account; L20's captures show the same build up to the push's `403`).

### Create & Deploy Cluster

*(README lines 436–455)*
- [ ] cd into `deploy_k8s` from the `deployment` folder — `cd ../deploy_k8s` from `deploy_images`, i.e. `/app/deploy_k8s`.
- [ ] `pulumi stack init dev` — `Created stack 'dev'` (project `deploy-k8s`, same state bucket).
- [ ] `pulumi config set gcp:project ac215-project` — your project ID. It has no `--stack`; it works because `stack init` selected `dev`.
- [ ] `pulumi config set security:gcp_service_account_email deployment@ac215-project.iam.gserviceaccount.com --stack dev` — the node pool's identity; your project in the e-mail.
- [ ] `pulumi config set security:gcp_ksa_service_account_email gcp-service@ac215-project.iam.gserviceaccount.com --stack dev` — the Google SA the API Pods act as; your project in the e-mail.
- [ ] `pulumi config` — *(extra)* your three keys, plus two leftovers from the committed `Pulumi.dev.yaml` that the program never reads: `setupSSL false` and `security:ssh_user sa_…` (`laptop/c12`). A misspelt key name would show up here; a missing key silently becomes `"None"` later (§6 item 6).
- [ ] `pulumi preview --stack dev --refresh` — the plan: network, subnet, cluster, router, NAT, node pool, the `gke_k8s_v2` provider, `connect-k8s-command`, namespace, Helm release `nginx-f5`, two PVCs, `api-ksa`, `api-gsa-wi-user`, three Deployments, three Services, the Job and the Ingress, plus two reads: `+ 23 to create` (`laptop/c20`, with placeholder image tags). If it stops at `File "/app/deploy_k8s/setup_containers.py", line 70` … `TypeError: 'NoneType' object is not subscriptable` (`laptop/c13`), `deploy_images` has not finished a `pulumi up` in this state bucket: run it first (§6 item 8).
- [ ] `pulumi up --stack dev --refresh -y` — creates everything in dependency order, roughly 15–25 minutes (estimate); ends with `Outputs:` including `app_url` and `ip_address`. In the capture, without an account, the first resource fails: `gcp:compute:Network cheese-app-vpc **creating failed**` … `invalid_grant` (`laptop/c21`).

*Try some kubectl commands* (README lines 476–486)
- [ ] `kubectl get all` — only `service/kubernetes`: you are in the `default` namespace (stand-in `kind/k03`).
- [ ] `kubectl get all --all-namespaces` — the app's objects appear under `cheese-app-namespace`, system objects under `kube-system`.
- [ ] `kubectl get pods --all-namespaces` — every Pod, system Pods included.
- [ ] `kubectl get componentstatuses` — `Warning: v1 ComponentStatus is deprecated in v1.19+`, then `controller-manager`, `scheduler`, `etcd-0` `Healthy` on the stand-in (`kind/k06`); GKE may show less.
- [ ] `kubectl get nodes` — 1 node `Ready` (2 if the autoscaler added one); GKE does not list its control plane.
- [ ] `kubectl get all -n cheese-app-namespace` — *(extra)* `frontend-…`, `vector-db-…`, `api-…`, the NGINX controller Pod, a `Completed` loader Pod and `job.batch/vector-db-loader 1/1`.
- [ ] `kubectl get pvc,ingress,serviceaccount -n cheese-app-namespace` — *(extra)* both PVCs `Bound`, the Ingress with host `<IP>.sslip.io`, the KSA `api-ksa`.
- [ ] `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>` — *(extra)* in every new toolbox session: without it, all five commands above print `The connection to the server localhost:8080 was refused` (`laptop/b40`–`b44`), because the kubeconfig Pulumi wrote left with the old `--rm` container (§6 item 2).

*If you want to shell into a container in a Pod* (README lines 488–493)
- [ ] `kubectl get pods --namespace=cheese-app-namespace` — find your `api-…` Pod name. On a cluster without the app: `No resources found in cheese-app-namespace namespace.` (`kind/k20`).
- [ ] `kubectl get pod api-c4fb784b-2llgs --namespace=cheese-app-namespace` — one Pod. `api-c4fb784b-2llgs` is the README author's Pod: use yours from the line above (`kind/k21` shows the `NotFound` you get otherwise).
- [ ] `kubectl exec --stdin --tty api-c4fb784b-2llgs --namespace=cheese-app-namespace  -- /bin/bash` — a shell in the API container (use your Pod name).
- [ ] `env | grep -E "ROOT_PATH|CHROMADB"` — *(extra)* inside the Pod: `ROOT_PATH=/api-service`, `CHROMADB_HOST=vector-db`, `CHROMADB_PORT=8000` (read from the code, not captured).
- [ ] `ls /persistent` — *(extra)* `chat-history/<model>/` and the `experiments/` CNN model download.
- [ ] `python -c "import socket; print(socket.gethostbyname('vector-db'))"` — *(extra)* the vector-db Service's cluster IP.

*View the App* (README lines 495–507)
- [ ] From the terminal view the results of Pulumi — the README's `Outputs:` block is older than the code: today's keys are `app_url`, `cluster_endpoint`, `cluster_name`, `ingress_name` (`cheese-app-ingress`), `ip_address` (not `nginx_ingress_ip`), `kubeconfig`, `namespace`.
- [ ] Go to `app_url` — the home page loads and the footer shows `API version: 3.0`. Not the bare IP: that answers NGINX's `404 Not Found`.
- [ ] `curl http://<IP>.sslip.io/api-service/status` — *(extra)* from your laptop: `{"version":"3.0"}`; `http://<IP>.sslip.io/api-service/docs` shows Swagger.
- [ ] *(extra)* Open `/chat?model=llm-rag` and send a message; a reply proves Workload Identity and Chroma work (read the model note in §4 Step 10 first).

*Scale* *(extra, §4 Step 12; needed for Milestone 5)*
- [ ] `kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace` — *(extra)* two more frontend Pods, 2 Gi request each (stand-in, on the game: `kind/k55`).
- [ ] `kubectl get pods -n cheese-app-namespace -o wide -w` — *(extra)* watch them go `Pending` → `Running`, and on which node.
- [ ] `kubectl get nodes -w` — *(extra)* watch the cluster autoscaler add node #2 if needed.
- [ ] `kubectl autoscale deployment frontend --cpu-percent=50 --min=1 --max=3 -n cheese-app-namespace` — *(extra, optional)* an HPA for the frontend (read §8 B7 first).
- [ ] `kubectl get hpa -n cheese-app-namespace` — *(extra)* TARGETS such as `cpu: 2%/50%`.
- [ ] `kubectl delete hpa frontend -n cheese-app-namespace` — *(extra)* removes the HPA.
- [ ] `kubectl scale deployment frontend --replicas=1 -n cheese-app-namespace` — *(extra)* back to one; the extra node goes after a cool-down of roughly 10 minutes.

*Redeploy a new version* *(extra, §4 Step 13; what L23 automates)*
- [ ] *(extra)* Change something visible, e.g. `"version": "3.0"` in `src/api-service/api/service.py:36`.
- [ ] `cd /app/deploy_images && pulumi up --stack dev -y` — *(extra)* new timestamp tags for all three images.
- [ ] `cd /app/deploy_k8s && pulumi up --stack dev --refresh -y` — *(extra)* rolling update; the loader Job is replaced and the vector DB reloaded. Checkpoint: the footer shows the new API version.

*Delete Cluster* (README lines 509–512)
- [ ] `pulumi destroy --stack dev --refresh -y` — run it **in `/app/deploy_k8s`**: deletes Ingress and Helm release, workloads and PVCs, namespace and KSA, node pool, cluster, NAT, router, subnet and VPC in reverse dependency order. Ends with `Resources: - N deleted` and a note that the stack's history and config remain (`pulumi stack rm dev` removes them) (`laptop/c23`, local backend).
- [ ] `gcloud container clusters list` — *(extra)* no `cheese-app-cluster`.
- [ ] `gcloud compute forwarding-rules list` — *(extra)* no leftover load-balancer rules.
- [ ] `gcloud compute disks list` — *(extra)* look for `pvc-...` disks.
- [ ] `gcloud compute addresses list` — *(extra)* SSL mode only: `cheese-app-global-ip`.
- [ ] `gcloud compute firewall-rules list` — *(extra)* `k8s-...` rules on `cheese-app-vpc`.
- [ ] *(extra)* Delete the Artifact Registry images in the console (`retain_on_delete=True`), and L20's VM if it still runs (`pulumi destroy` in `deploy_single_vm`).

### Create Simple Kubernetes Cluster Tutorial *(optional warm-up, README lines 517–581)*

*API's to enable in GCP for Project* (README lines 519–525)
- [ ] Enable Compute Engine API, Service Usage API, Cloud Resource Manager API, Google Container Registry API and Kubernetes Engine API — Container Registry has been shut down (§9 erratum 6): enable Artifact Registry API instead.

*Start Deployment Docker Container* (README lines 527–536)
- [ ] `cd deployment` — the folder is `src/deployment` from the repo root.
- [ ] Run `sh docker-shell.sh` or `docker-shell.bat` for windows — the same toolbox, with the same two fixes. `docker-shell.bat` does not exist in the repo; on Windows use WSL.
- [ ] `gcloud --version` — SDK version lines.
- [ ] `kubectl version` — before a cluster: `connection … refused`, harmless. Against a 1.34 cluster the dispatcher picks a matching client: `Client Version: v1.34.12-gke.300…`, `Server Version: v1.34.11` (stand-in, `kind/k02`).
- [ ] `kubectl version --client` — `Client Version: v1.35.9-dispatcher`.
- [ ] `gcloud auth list` — `deployment@<project>.iam.gserviceaccount.com` active.

*Create Cluster* (README lines 539–542)
- [ ] `gcloud container clusters create test-cluster --num-nodes 2 --zone us-east1-c` — a zonal cluster with two nodes in the project's `default` VPC; takes several minutes, then writes the kubeconfig for you. The capture stops at once: `ERROR: (gcloud.container.clusters.create) You do not currently have an active account selected.` (`laptop/b15`). Billed per node-hour while it exists.
- [ ] `kind create cluster --name test-cluster --image kindest/node:v1.34.11 --config kind-test-cluster.yaml` — *(extra, recording workaround only)* the stand-in the captures use from here on (one control plane, two workers); not a step for you.

*Checkout the cluster in GCP* (README lines 544–549)
- [ ] Kubernetes Engine → click the cluster name → Nodes tab → click a node to see its Pods.
- [ ] Compute Engine → the cluster's VMs.

*Try some kubectl commands* (README lines 551–561)
- [ ] `kubectl get all` — only `service/kubernetes ClusterIP 10.96.0.1 … 443/TCP` (stand-in `kind/k03`).
- [ ] `kubectl get all --all-namespaces` — every namespace (`kind/k04`).
- [ ] `kubectl get pods --all-namespaces` — system Pods in `kube-system`; on the stand-in, also the control plane (`etcd-…`, `kube-apiserver-…`, `kube-controller-manager-…`, `kube-scheduler-…`), which GKE hides (`kind/k05`).
- [ ] `kubectl get componentstatuses` — the deprecation warning, then three `Healthy` rows (`kind/k06`).
- [ ] `kubectl get nodes` — your 2 nodes `Ready`; the stand-in lists 3 including `control-plane` (`kind/k07`).

*Deploy the App* (README lines 563–566)
- [ ] `kubectl apply -f deploy-k8s-tic-tac-toe.yml` — `deployment.apps/web created`, `service/web created` (`kind/k10`): a Deployment with 2 replicas of `dlops/tic-tac-toe` plus a `LoadBalancer` Service, port 80 → 8080.

*Get the Loadbalancer external IP* (README lines 568–571)
- [ ] `kubectl get services` — row `web`, type `LoadBalancer`, `EXTERNAL-IP <pending>`, `80:<nodePort>/TCP` (`kind/k11`); on GKE a real IP after 1–2 minutes. The stand-in has no cloud and stays `<pending>` (`kind/k13`, 43 s later).

*View the App* (README lines 573–575)
- [ ] Copy the `External IP` from the `kubectl get services`
- [ ] Go to `http://<YOUR EXTERNAL IP>` — the game.
- [ ] `kubectl port-forward service/web 8080:80` — *(extra)* the stand-in's way in; then `curl -i http://localhost:8080/` in the **same** toolbox → `HTTP/1.1 200 OK`, `<!DOCTYPE html>` (`kind/k57`). The toolbox publishes no ports, so a browser on your laptop cannot reach it.
- [ ] `kubectl delete pod <one web pod>` — *(extra)* then `kubectl get pods -l run=web`: a replacement Pod in `ContainerCreating` at once, `Running` 15 s later (`kind/k53`, `k54`; §3.2).

*Delete Cluster* (README lines 578–581)
- [ ] `kubectl delete -f deploy-k8s-tic-tac-toe.yml` — *(extra)* run first, so GKE removes the load balancer while the cluster still exists (`deployment.apps "web" deleted`, `service "web" deleted`, `kind/k80`).
- [ ] `gcloud container clusters delete test-cluster --zone us-east1-c` — deletes the warm-up cluster (capture: the same "no active account" error, `laptop/b51`).
- [ ] `gcloud compute forwarding-rules list` — *(extra)* should be empty.

### Debugging Containers

*`sudo docker` commands* (README lines 593–615): these are for L20's VM, not for this lecture's cluster; the L20 guide covers them.
- [ ] `sudo docker container ls` · `sudo docker image ls` — *(L20's VM)* running containers, images.
- [ ] `sudo docker container logs api-service -f` · `sudo docker container logs frontend -f` · `sudo docker container logs nginx -f` — *(L20's VM)* follow logs.
- [ ] `sudo docker exec -it api-service /bin/bash` · `sudo docker exec -it frontend /bin/bash` · `sudo docker exec -it nginx /bin/bash` — *(L20's VM)* a shell in each.

*`kubectl` commands* (README lines 618–657; use while the cheese-app cluster is up). As written, all 14 fail today (`kind/k30`–`k43`): the namespace `cheese-app-cluster-namespace` and the init container `wait-for-chromadb` belong to the pre-refactor program (§6 item 4, §8 C1), and `<pod-name>` is read by the shell as a redirection (§6 item 21). The working forms follow the README's list.
- [ ] `kubectl logs -n cheese-app-cluster-namespace job/vector-db-loader -c wait-for-chromadb` — init-container logs; captured: `error: error from server (NotFound): namespaces "cheese-app-cluster-namespace" not found in namespace "cheese-app-cluster-namespace"`.
- [ ] `kubectl logs -n cheese-app-cluster-namespace job/vector-db-loader -c vector-db-loader` — loader logs; the same error.
- [ ] `kubectl describe job vector-db-loader -n cheese-app-cluster-namespace` — Job status; `Error from server (NotFound): namespaces "cheese-app-cluster-namespace" not found`.
- [ ] `kubectl get pods -n cheese-app-cluster-namespace | grep vector-db-loader` — find the loader Pod; `No resources found in cheese-app-cluster-namespace namespace.`
- [ ] `kubectl logs -n cheese-app-cluster-namespace <pod-name>` — `bash: … syntax error near unexpected token 'newline'` (`kind/k34`).
- [ ] `kubectl logs -n cheese-app-cluster-namespace vector-db-loader-9gr5m` — an example Pod name; namespace error.
- [ ] `kubectl logs -n cheese-app-cluster-namespace <pod-name> -c wait-for-chromadb` — `bash: line 1: pod-name: No such file or directory` (`kind/k36`).
- [ ] `kubectl logs -n cheese-app-cluster-namespace vector-db-loader-wlfdx -c wait-for-chromadb` — example; namespace error (and no init container).
- [ ] `kubectl logs -n cheese-app-cluster-namespace <pod-name> -c vector-db-loader` — `pod-name: No such file or directory` (`kind/k38`).
- [ ] `kubectl logs -n cheese-app-cluster-namespace vector-db-loader-wlfdx -c vector-db-loader` — example; namespace error.
- [ ] `kubectl logs job/vector-db-loader -n cheese-app-cluster-namespace` — most recent loader Pod; namespace error.
- [ ] `kubectl logs job/vector-db-loader -n cheese-app-cluster-namespace --previous` — a restarted container's previous run; namespace error.
- [ ] `kubectl logs deployment/api -n cheese-app-cluster-namespace` — API Pod logs; namespace error.
- [ ] `kubectl logs deployment/api -n cheese-app-cluster-namespace -f` — follow them; namespace error.
- [ ] `kubectl logs -n cheese-app-namespace job/vector-db-loader` — *(extra)* the working loader-log command (README line 646 with the namespace fixed). On a Job that exists (stand-in `hello-job`), `kubectl logs job/…` prints the container's output (`kind/k61`).
- [ ] `kubectl describe job vector-db-loader -n cheese-app-namespace` — *(extra)* the working Job status (README line 626, fixed): look for `Pods Statuses: 0 Active (0 Ready) / 1 Succeeded / 0 Failed` (stand-in, `kind/k62`).
- [ ] `kubectl get pods -n cheese-app-namespace | grep vector-db-loader` — *(extra)* README line 631, fixed; then `kubectl logs -n cheese-app-namespace vector-db-loader-<suffix>` with the name it prints.
- [ ] `kubectl logs deployment/api -n cheese-app-namespace -f` — *(extra)* the working API log follow (README line 656, fixed).
- [ ] `kubectl describe pod <name> -n cheese-app-namespace` — *(extra)* explains `Pending`, `ImagePullBackOff`, Multi-Attach (replace `<name>`, brackets included).
- [ ] `kubectl get events -n cheese-app-namespace --sort-by=.lastTimestamp` — *(extra)* recent events, newest last (stand-in: `Killing` → `SuccessfulCreate` → `Scheduled` → `Pulled` → `Created` → `Started`, `kind/k64`).
- [ ] `kubectl config set-context --current --namespace=cheese-app-namespace` — *(extra)* make the app namespace the default for this session.
- [ ] `kubectl port-forward svc/api 9000:9000 -n cheese-app-namespace &` — *(extra)* reach the ClusterIP API from inside the toolbox (it publishes no ports).
- [ ] `curl localhost:9000/api-service/status` — *(extra)* in the same toolbox, through the port-forward.
- [ ] `kubectl get storageclass` — *(extra)* the default StorageClass behind the PVCs.
- [ ] `kubectl exec deploy/vector-db -n cheese-app-namespace -- ls /data /chroma/chroma` — *(extra)* where Chroma actually keeps its data (§6 item 14; the image may not ship `ls`).
- [ ] `kubectl delete job vector-db-loader -n cheese-app-namespace` — *(extra)* after fixing a failed loader; then rerun `pulumi up --stack dev --refresh -y`, which recreates it (§6 item 9).

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
 | container "cheese-app-deployment" (linux/amd64)  gcloud | kubectl | helm | pulumi         |
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
 Browser --DNS: <IP>.sslip.io -> <IP>-----------> GCP external network LB :80
                                                 (made by GKE for the Service of type LoadBalancer)
 +------------------------- VPC "cheese-app-vpc", subnet 10.0.0.0/19, us-central1 --------------------------+
 |  GKE "cheese-app-cluster": regional control plane (Google-run, public endpoint)                         |
 |  node pool: n2d-standard-2, us-central1-a, 1..2 nodes, private IPs only                                  |
 |  namespace "cheese-app-namespace"                                                                         |
 |                                                                                                           |
 |   [Pod nginx-f5-...-nginx-ingress-controller]  reads Ingress "cheese-app-ingress" (host <IP>.sslip.io)      |
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

### The toolbox needs two one-line fixes before it builds
`sh docker-shell.sh` builds `src/deployment/Dockerfile`, the same toolbox as L20, and as committed it fails, exactly as in the L20 captures of 2026-11-05 (captured again 2026-11-07, `laptop/b02`):
- `Dockerfile:4` starts `FROM python:3.13-slim-bullseye`. Debian 11's security packages are gone from `deb.debian.org`, so `apt-get install` at `Dockerfile:11-12` fails with 22 × `404  Not Found`. `docker-shell.sh` does not stop on that error, runs `docker run` anyway, and the last lines you see are `Unable to find image 'cheese-app-deployment:latest' locally` and `pull access denied`: scroll up to the first red line.
- `Dockerfile:30` installs `google-cloud-sdk google-cloud-sdk-gke-gcloud-auth-plugin`; Google's repository now names these packages `google-cloud-cli` and `google-cloud-cli-gke-gcloud-auth-plugin` (in L20 this was the second failure, after fix 1).

The fix, both in one edit (`laptop/b02a`):
```diff
-FROM python:3.13-slim-bullseye
+FROM python:3.13-slim-bookworm
...
-    apt-get install -y google-cloud-sdk google-cloud-sdk-gke-gcloud-auth-plugin jq docker-ce
+    apt-get install -y google-cloud-cli google-cloud-cli-gke-gcloud-auth-plugin jq docker-ce
```
With both, the toolbox built in 92.3 s on an amd64 machine (`laptop/b03`); on Apple Silicon it is emulated and much slower. Fix 2 matters twice in this lecture: the GKE auth plugin is what the cluster's kubeconfig runs for every `kubectl` and Pulumi-Kubernetes call (§3.7).

One surprise in the built toolbox: `Dockerfile:33-41` adds the Kubernetes project's apt repository and pins `K8S_MINOR=1.34`, but Google's repository also ships a package named `kubectl` (version `1:592.0.0-0`) that wins, and `/usr/bin/kubectl` links to gcloud's **dispatcher** (`laptop/b14`). `kubectl version --client` says `v1.35.9-dispatcher` (`laptop/b12`); against a 1.34 server it runs a matching client, `v1.34.12-gke.300…` (stand-in, `kind/k02`). Harmless, and it makes version skew with GKE's auto-upgrades a smaller worry (§6 item 19).

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
  - You almost never create Pods directly. A **Deployment** says "keep N copies of this Pod template running". It creates a **ReplicaSet** (one per template version), and the ReplicaSet creates the Pods. Names show this chain: Deployment `api` → ReplicaSet `api-c4fb784b` → Pod `api-c4fb784b-2llgs` (README 491). On the stand-in the warm-up's game shows the same: Deployment `web` → ReplicaSet `web-5cd9789488` (selector `pod-template-hash=5cd9789488,run=web`) → Pods `web-5cd9789488-5h48s` and `web-5cd9789488-bmkj5`, on different workers (`kind/k50`). The hash is computed from the Pod template, so it changes only when the template does.
  - **Controllers** loop forever: observe actual state, compare it with desired state, act. Delete a Pod and the ReplicaSet makes a new one: on the stand-in, the replacement `web-5cd9789488-lmk52` was `ContainerCreating` 1 s after the delete and `Running` 15 s later (`kind/k53`, `k54`). Change the image tag and the Deployment rolls out a new ReplicaSet.
  - A **Job** is the run-to-completion cousin. It retries failed Pods up to `backoffLimit` times (`setup_containers.py:206`) and then stops, with `restart_policy="Never"` (`:210`).
- **Mental model:** a thermostat. You set the temperature and it keeps correcting. `kubectl` and Pulumi set temperatures; they do not "run" things.
- **Analogy:** a restaurant manager with a staffing chart ("2 cooks on shift"). If a cook goes home sick, the manager calls in a replacement without being asked.
- **Misconception:** "Pulumi/kubectl starts my containers". They write *objects* into the API server. The kubelet on a node starts containers, possibly minutes later.

### 3.3 Labels, Services, cluster DNS and namespaces
- **Explanation:**
  - Pods are mortal and get new IPs every time they restart. A **Service** gives a *stable* virtual IP and DNS name in front of "all Pods whose labels match my selector". In this code that is `run: frontend`, `run: api` and `run: vector-db` (`setup_containers.py:59,63,106`, `:122,126,191`, `:254,258,340`).
  - `type="ClusterIP"` (`:98`) means reachable only inside the cluster.
  - Cluster DNS makes the Service name resolvable. That is why the API reaches Chroma at host `vector-db`, port `8000` (`:297-304`). Inside the same namespace the short name works. The full name is `vector-db.cheese-app-namespace.svc.cluster.local`. On the stand-in, a throw-away Pod resolved `web.default.svc.cluster.local` to `10.96.52.79`, the `web` Service's CLUSTER-IP, and `wget http://web` returned the game's page (`kind/k52`).
  - A **namespace** (`cheese-app-namespace`, `create_cluster.py:141-145`) is a folder for objects. Names must be unique within it, and `kubectl` only looks in the `default` namespace unless you pass `-n`.
- **Mental model:** the label is a sticker on each Pod. The Service is a mail-forwarding address that delivers to whoever currently wears the matching sticker.
- **Analogy:** a company's switchboard number. Employees (Pods) come and go, the number stays.
- **Misconception:** "Service = Pod". A Service has no process of its own. It is a routing rule (kube-proxy/iptables), and the NGINX controller even bypasses it and sends traffic straight to the Pod IPs it lists.
- **Second misconception:** `kubectl get all` shows everything. It shows the *current* namespace only. Use `-n cheese-app-namespace` or `--all-namespaces`.

### 3.4 How a request reaches a Pod: LoadBalancer → Ingress controller → Service → Pod
- **Explanation:** an **Ingress** is only a *rule object*: host + path → Service:port (`setup_loadbalancer.py:62-117`). It does nothing until an **Ingress controller** implements it. Here that controller is the F5 NGINX Ingress Controller, installed by a Helm chart (`:11-46`). Its own Service has `type: LoadBalancer` (`:22-24`), so GKE creates a GCP **external network load balancer** with a public IP. A request travels:
  1. Browser asks DNS for `<IP>.sslip.io`, and sslip.io answers `<IP>` (`:60`).
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
  - The disk is attached to whichever node runs the Pod that mounts the claim: `/chroma/chroma` (`:147-152`) and `/persistent` (`:286-291`). Caveat: today's unpinned `chromadb/chroma` image writes to `/data`, not `/chroma/chroma`, so the Chroma claim is mounted but unused (§6 item 14).
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
  2. **You → Kubernetes API:** a kubeconfig whose user entry is an **exec plugin**, `gke-gcloud-auth-plugin` (`create_cluster.py:104-116`). Every kubectl or Pulumi-Kubernetes call runs the plugin, which mints a short-lived Google token from gcloud's active account. GKE maps that account's IAM role (Kubernetes Engine Admin) to cluster permissions. There are no static cluster passwords. Contrast: the stand-in's kubeconfig authenticates with an embedded `client-certificate-data` (`kind/k65`).
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

The order follows the lecture: Part 0 is the optional warm-up that the README keeps at its end (lines 517–581); the lecture runs it first (slides 32–40), and it is the gentlest first contact with `kubectl`, worth 20 minutes and a few cents. Parts A–C then follow the README's cheese-app sections. Commands and checks marked "not in the README" are additions written from the code or standard `gcloud`/`kubectl` usage.

Outputs below come from the 2026-11-07 captures (files in the video folder's `assets/terminal/`, trimmed with `…`). Three labels: **captured** (the toolbox in a laptop's Docker engine, no Google account, so cloud commands stop at their first error), **stand-in** (the same kubectl against a kind cluster, Kubernetes v1.34.11: a real API server, but not GKE) and **expected** (what the README or the code says you see with a real project; not recorded here). Pod names, hashes, NodePorts and private `10.x` addresses differ on every cluster.

### Part 0 (optional warm-up): a throw-away cluster with tic-tac-toe

**0.0 Enable the APIs.** README 519–525: Compute Engine, Service Usage, Cloud Resource Manager, "Google Container Registry API" (shut down, erratum 6: enable Artifact Registry API instead) and Kubernetes Engine API.

**0.1 Start the deployment toolbox.** README 527–536: `cd deployment`, `sh docker-shell.sh`, then the version and auth checks. It is the same toolbox as Part A, Step 3: apply the two Dockerfile fixes first (§2). `docker-shell.bat` (README 529) does not exist in the repo; on Windows use WSL.

**0.2 Create a cluster.** README 541.
```
gcloud container clusters create test-cluster --num-nodes 2 --zone us-east1-c
```
- Under the hood: a **zonal** cluster in the project's `default` VPC, with the default machine type and two nodes. This is the imperative way: one command, no state file. Slide 32 creates one node; the README two, so the game's two copies can land on different machines.
- Captured (no account):
  ```
  ERROR: (gcloud.container.clusters.create) You do not currently have an active account selected.
  Please run:

    $ gcloud auth login
  …
  ```
  (`laptop/b15`.) With your key, gcloud works for several minutes, then prints a table with `test-cluster`, its location and `NUM_NODES 2`, and writes the kubeconfig for you (expected; nothing in the repo records this output).
- If it fails: `Kubernetes Engine API has not been used` → enable it (README 525). `network "default" not found` → your project has no default VPC. Add `--network`/`--subnetwork`, or use the main tutorial.
- From here the captures continue on a **stand-in** cluster made with kind (one control plane, two workers), a recording workaround that is not in the README and not a step for you:
  ```
  Creating cluster "test-cluster" ...
   ✓ Ensuring node image (kindest/node:v1.34.11) 🖼
   ✓ Preparing nodes 📦 📦 📦
  …
   ✓ Joining worker nodes 🚜
  Set kubectl context to "kind-test-cluster"
  ```
  (`kind/k01`.) Same API server, same kubectl, same YAML; no Google, so no cloud load balancer, and its control plane is a container you can see.

**0.3 Look around.** README 545–549 (console: Kubernetes Engine → cluster → Nodes → a node's Pods; Compute Engine → the node VMs) and 552–560:
```
kubectl get all
kubectl get all --all-namespaces
kubectl get pods --all-namespaces
```
```
kubectl get componentstatuses
kubectl get nodes
```
- Stand-in outputs:
  ```
  $ kubectl get all
  NAME                 TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
  service/kubernetes   ClusterIP   10.96.0.1    <none>        443/TCP   10m

  $ kubectl get pods --all-namespaces
  NAMESPACE            NAME                                                 READY   STATUS    …
  kube-system          coredns-66bc5c9577-bcrjr                             1/1     Running   …
  kube-system          etcd-test-cluster-control-plane                      1/1     Running   …
  kube-system          kube-apiserver-test-cluster-control-plane            1/1     Running   …
  kube-system          kube-controller-manager-test-cluster-control-plane   1/1     Running   …
  kube-system          kube-proxy-5nxfz                                     1/1     Running   …
  kube-system          kube-scheduler-test-cluster-control-plane            1/1     Running   …
  …
  $ kubectl get componentstatuses
  Warning: v1 ComponentStatus is deprecated in v1.19+
  NAME                 STATUS    MESSAGE   ERROR
  controller-manager   Healthy   ok
  scheduler            Healthy   ok
  etcd-0               Healthy   ok

  $ kubectl get nodes
  NAME                         STATUS   ROLES           AGE   VERSION
  test-cluster-control-plane   Ready    control-plane   12m   v1.34.11
  test-cluster-worker          Ready    <none>          11m   v1.34.11
  test-cluster-worker2         Ready    <none>          11m   v1.34.11
  ```
  (`kind/k03`, `k05`, `k06`, `k07`.) `get all` shows only the Service `kubernetes`, the door to the API server itself, because it looks in the `default` namespace. With `--all-namespaces` the control plane appears by name (etcd, API server, controller manager, scheduler): the four parts of slides 24–25. On GKE those stay hidden, and `kubectl get nodes` lists your two workers only. `get componentstatuses` is deprecated (since Kubernetes 1.19); `get nodes` is the better check.
- Also try (not in the README) `kubectl version`: against the stand-in the dispatcher picked a matching client, `Client Version: v1.34.12-gke.300.1+…`, `Server Version: v1.34.11` (`kind/k02`).

**0.4 Deploy and expose the app.** README 565, 570.
```
kubectl apply -f deploy-k8s-tic-tac-toe.yml
kubectl get services
```
- Under the hood: `src/deployment/deploy-k8s-tic-tac-toe.yml:2-22` is a Deployment with `replicas: 2` of `dlops/tic-tac-toe` (container port 8080). `:24-35` is a Service of `type: LoadBalancer` mapping port 80 → 8080. Both carry the label `run: web`, which is what links them. The YAML file is in `/app` because `/app` is `src/deployment`.
- Stand-in:
  ```
  $ kubectl apply -f deploy-k8s-tic-tac-toe.yml
  deployment.apps/web created
  service/web created

  $ kubectl get services
  NAME         TYPE           CLUSTER-IP    EXTERNAL-IP   PORT(S)        AGE
  kubernetes   ClusterIP      10.96.0.1     <none>        443/TCP        10m
  web          LoadBalancer   10.96.52.79   <pending>     80:31366/TCP   0s
  ```
  (`kind/k10`, `k11`; 43 s later still `<pending>`, `k13`.) On GKE the controllers ask Google for a load balancer, and after 1–2 minutes `EXTERNAL-IP` shows a real address; `http://<EXTERNAL-IP>` then shows the game (README 574–575; expected). kind has no cloud to ask, so it stays `<pending>`.
- Stand-in way in (not in the README): `kubectl port-forward service/web 8080:80`, then `curl -i http://localhost:8080/` in the same toolbox → `HTTP/1.1 200 OK` … `<!DOCTYPE html>` (`kind/k57`). The toolbox publishes no ports (`docker-shell.sh:34-50`), so this works inside the toolbox, not in your laptop's browser.
- Try (not in the README): `kubectl delete pod <one web pod>`, then `kubectl get pods -l run=web`:
  ```
  pod "web-5cd9789488-5h48s" deleted from default namespace
  NAME                   READY   STATUS              RESTARTS   AGE
  web-5cd9789488-bmkj5   1/1     Running             0          3m13s
  web-5cd9789488-lmk52   0/1     ContainerCreating   0          1s
  ```
  (stand-in, `kind/k53`; 15 s later both `Running`, `k54`.) The new name keeps the ReplicaSet's hash with a new suffix (§3.2).
- And `kubectl scale deployment web --replicas=4` (not in the README): four Pods spread over both workers, and the Service's endpoint list grows to four (`kind/k55`); scale back to 2.

**0.5 Delete.** README 580.
```
gcloud container clusters delete test-cluster --zone us-east1-c
```
- Tip (not in the README): run `kubectl delete -f deploy-k8s-tic-tac-toe.yml` first (`deployment.apps "web" deleted`, `service "web" deleted`, stand-in `kind/k80`), so GKE removes the cloud load balancer while the cluster still exists. Then check that `gcloud compute forwarding-rules list` is empty.
- Captured: the same "You do not currently have an active account selected" error (`laptop/b51`); the stand-in was deleted with `kind delete cluster --name test-cluster` (`kind/k81`).

### Part A: one-time setup

**Step 1. Enable the APIs.** README 396–402. Add Vertex AI API if it is not already on (§2).

**Step 2. Service accounts and the extra role.**
- README 236–259 creates `deployment` and `gcp-service`. Put `deployment.json` in `~/Desktop/AC215/secrets/`, next to the repo folder.
- Grant the extra role from §2 so Pulumi can write the Workload Identity binding (not tested against a real project).
- Checkpoint: in the console under IAM → Service accounts → `gcp-service` → Permissions, `deployment@…` appears with Service Account Admin (or deployment has it project-wide).

**Step 3. Start the deployment toolbox and check tools.** README 404–413.
- Before the first run, set `GCP_PROJECT` to your project ID in `src/deployment/docker-shell.sh:13`. The K8s section does not repeat this; it is the L20 step at README 267. The README's `cd deployment` (405) means `src/deployment` from the repo root.
```
cd deployment
sh docker-shell.sh
```
- Captured as committed (`laptop/b02`):
  ```
  Container 'cheese-app-deployment' is not running. Building and starting new container...
  …
   => ERROR [ 2/16] RUN apt-get update &&     apt-get install -y curl apt-transport-https ca-ce  5.0s
  …
  4.957 E: Failed to fetch https://deb.debian.org/debian-security/pool/updates/main/d/distro-info-data/…  404  Not Found …
  …
  ERROR: failed to build: failed to solve: process "/bin/sh -c apt-get update && …" did not complete successfully …
  Unable to find image 'cheese-app-deployment:latest' locally
  docker: Error response from daemon: pull access denied for cheese-app-deployment, repository does not exist …
  ```
  (The capture's mirror lines read `https://` and end in the recording proxy's address; yours read `http://` and your mirror's address.) Apply the two one-line fixes from §2, then run `sh docker-shell.sh` again.
- Captured after the fixes (`laptop/b03`):
  ```
  [+] Building 92.3s (21/21) FINISHED
  …
  Container is running!!!
  Architecture: x86_64
  Environment ready! Virtual environment activated.
  Python version: Python 3.13.18
  UV version: uv 0.13.7 (x86_64-unknown-linux-gnu)
  ERROR: (gcloud.auth.activate-service-account) There was a problem refreshing auth tokens for account deployment@your-gcp-project.iam.gserviceaccount.com: ('invalid_grant: Invalid grant: account not found', …
  …
  Logging into Pulumi using GCS bucket: gs://your-gcp-project-pulumi-state-bucket
  error: could not log in to the state backend …
  …
  root@<id>:/app#
  ```
  The `invalid_grant` lines are the recording's key, which belongs to no account. With your real `deployment.json`, the same place says the account was activated, the state bucket is created if missing, and Pulumi logs in to it.
- Under the hood: builds `cheese-app-deployment` for `linux/amd64` (`docker-shell.sh:31`) and runs it with `--rm`, your code at `/app`, secrets at `/secrets` and the Docker socket mounted (`:34-50`). The entrypoint activates the `deployment` SA, configures Docker for Artifact Registry and runs `pulumi login gs://…` (`docker-entrypoint.sh:10-23`). If the container is already running in another terminal, `docker-shell.sh` *execs* into it instead of starting a new one (`docker-shell.sh:23-25`).
```
gcloud --version
kubectl version
kubectl version --client
gcloud auth list
```
- Captured (`laptop/b10`–`b13`):
  ```
  $ gcloud --version
  Google Cloud SDK 592.0.0
  …
  gke-gcloud-auth-plugin 0.5.21
  gsutil 5.38
  kubectl 1.35.9
  …
  $ kubectl version
  Client Version: v1.35.9-dispatcher
  Kustomize Version: v5.7.1
  The connection to the server localhost:8080 was refused - did you specify the right host or port?

  $ kubectl version --client
  Client Version: v1.35.9-dispatcher
  Kustomize Version: v5.7.1

  $ gcloud auth list

  No credentialed accounts.
  …
  ```
- Checkpoints: plain `kubectl version` (README 409) also asks a server, and before any cluster exists there is none, so `connection … refused` is expected and harmless. The client is gcloud's dispatcher, not the 1.34 the Dockerfile pins (§2). `gcloud auth list` should show `deployment@<project>.iam.gserviceaccount.com` as active (expected); `No credentialed accounts.` means the key was not found or not activated (check `../../../secrets/deployment.json` relative to `src/deployment`).

### Part B: images

**Step 4. Build and push images (skip if you did it in L20, into the same state bucket).** README 415–434.
```
cd deploy_images
pulumi stack init dev
pulumi config set gcp:project ac215-project --stack dev
pulumi preview --stack dev
pulumi up --stack dev -y
```
(replace `ac215-project`)
- Captured against the GCS backend (no login): each of these prints `error: PULUMI_ACCESS_TOKEN must be set for login during non-interactive CLI sessions`, exit 3 (`laptop/b20`–`b23`). That message means the entrypoint's `pulumi login gs://…` failed, so Pulumi falls back to its cloud service; the cause is the first red line of the toolbox start-up, not this command (§6 item 22).
- The captures then point Pulumi at a local folder (`pulumi login --local`, a recording workaround, not a step for you). There, `pulumi stack init dev` prints `Created stack 'dev'` and the config set prints nothing (`laptop/c01`, `c02`), and the preview shows the plan (`laptop/c03`):
  ```
   +  pulumi:pulumi:Stack deploy-images-dev create
   +  docker-build:index:Image build-cheese-app-vector-db-cli create
   +  docker-build:index:Image build-cheese-app-frontend-react create
   +  docker-build:index:Image build-cheese-app-api-service create
  …
      warning: Skipping preview build because some inputs are unknown.
  …
  Outputs:
      cheese-app-api-service-ref    : [unknown]
      cheese-app-api-service-tags   : [
          [0]: "us-docker.pkg.dev/ac215-project/cheese-app-repository/cheese-app-api-service:20261107205032"
      ]
  …
  Resources:
      + 4 to create
  ```
  A preview builds nothing; the tags carry the time of the run, so every run makes new ones.
- Under the hood of `pulumi up`: three `docker_build.Image` resources build `../../api-service`, `../../frontend-react` and `../../vector-db` for `linux/amd64` (`deploy_images/__main__.py:23-32,43-52,62-71`), tag them `us-docker.pkg.dev/<proj>/cheese-app-repository/<name>:<YYYYmmddHHMMSS>` (`:13-15,25`) and push them. The stack outputs `cheese-app-…-tags` (`:35,54,74`) are what `deploy_k8s` will read.
- Checkpoint (expected): `Outputs:` lists `cheese-app-api-service-tags`, `cheese-app-frontend-react-tags` and `cheese-app-vector-db-cli-tags`, and the images appear in Artifact Registry. `pulumi up` was not run in the L22 captures (the API image is about 5 GB and the push needs an account); L20's captures show the same build up to the push's `403 Forbidden`.
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
- Under the hood: creates `.pulumi/stacks/deploy-k8s/dev.json` in the state bucket (project name from `src/deployment/deploy_k8s/Pulumi.yaml:1`) and writes the three keys into `Pulumi.dev.yaml`. `security:gcp_service_account_email` becomes the node pool's identity (`create_cluster.py:9`, `:50`); `security:gcp_ksa_service_account_email` the Google account the API Pods act as (`:10-12`).
- Captured (local backend): `Created stack 'dev'`; the three config sets print nothing (`laptop/c10`, `c11`). Then `pulumi config` (not in the README, `laptop/c12`):
  ```
  KEY                                     VALUE
  setupSSL                                false
  gcp:project                             ac215-project
  pulumi:tags                             {"pulumi:template":"python"}
  security:gcp_ksa_service_account_email  gcp-service@ac215-project.iam.gserviceaccount.com
  security:gcp_service_account_email      deployment@ac215-project.iam.gserviceaccount.com
  security:ssh_user                       sa_000000000000000000000
  ```
  (The `sa_` number is masked here.) Yours shows your project in the three keys. `setupSSL` and `security:ssh_user` are leftovers from the committed `Pulumi.dev.yaml` (`:4,7`) that `deploy_k8s` never reads.
- If it fails: `stack 'dev' already exists` → `pulumi stack select dev`.

**Step 6. Preview.** README 449.
```
pulumi preview --stack dev --refresh
```
- Captured when `deploy_images` has no outputs in this backend (`laptop/c13`):
  ```
   +  pulumi:pulumi:Stack deploy-k8s-dev create read pulumi:pulumi:StackReference organization/deploy-images/dev
  …
      File "/app/deploy_k8s/setup_containers.py", line 70, in <lambda>
        lambda tags: tags[0]
                     ~~~~^^^
      TypeError: 'NoneType' object is not subscriptable

  Resources:
      + 2 to create
      1 errored
  ```
  The program asked the images stack for its tags (`setup_containers.py:10-14`) and got nothing. README 416's "only required if you have NOT already done this" means: done once, with `pulumi up`, into this same state bucket.
- Captured with a capture-only stand-in image stack that exports placeholder tags (nothing built; `laptop/c20`):
  ```
   +  gcp:compute:Network cheese-app-vpc create
   +  gcp:compute:Subnetwork cheese-app-subnet create
   +  gcp:container:Cluster cheese-app-cluster create
   +  gcp:compute:Router cheese-app-router create
   +  gcp:compute:RouterNat cheese-app-nat create
   +  gcp:container:NodePool cheese-app-pool create
   +  pulumi:providers:kubernetes gke_k8s_v2 create
   +  command:local:Command connect-k8s-command create
   +  kubernetes:core/v1:Namespace cheese-app-namespace create
   +  kubernetes:helm.sh/v3:Release nginx-f5 create
   +  kubernetes:core/v1:PersistentVolumeClaim persistent-pvc create
   +  kubernetes:core/v1:ServiceAccount api-ksa create
   +  kubernetes:core/v1:PersistentVolumeClaim chromadb-pvc create
   +  gcp:serviceaccount:IAMMember api-gsa-wi-user create
   +  kubernetes:apps/v1:Deployment frontend create
   +  kubernetes:apps/v1:Deployment vector-db create
   +  kubernetes:core/v1:Service frontend-service create
   +  pulumi:pulumi:Stack deploy-k8s-dev create read kubernetes:core/v1:Service nginx-ingress-service
   +  kubernetes:core/v1:Service vector-db-service create
   +  kubernetes:batch/v1:Job vector-db-loader create
   +  kubernetes:apps/v1:Deployment api create
   +  kubernetes:core/v1:Service api-service create
   +  kubernetes:networking.k8s.io/v1:Ingress cheese-app-ingress create
  …
  Outputs:
      app_url         : [unknown]
      cluster_endpoint: [unknown]
      cluster_name    : "cheese-app-cluster"
  …
  Resources:
      + 23 to create
  ```
- Checkpoint: **`+ 23 to create`**: 22 resources (the `gke_k8s_v2` provider and the local `connect-k8s-command` among them) plus the stack itself. The `StackReference` and `nginx-ingress-service` lines are *reads* of things that already exist, not creates. Only `cluster_name` is known at preview time; everything else waits for the cluster. Your preview shows real image tags.

**Step 7. Create everything.** README 454.
```
pulumi up --stack dev --refresh -y
```
- Captured (local backend, no account; `laptop/c21`): the plan again, then
  ```
  Updating (dev):
  …
   +  gcp:compute:Network cheese-app-vpc **creating failed** error: 1 error occurred:
  …
      error:   sdk-v2/provider2.go:572: sdk.helper_schema: Error creating Network: Post "https://compute.googleapis.com/compute/beta/projects/ac215-project/global/networks?alt=json": oauth2: cannot fetch token: 400 Bad Request
      Response: {"error":"invalid_grant","error_description":"Invalid grant: account not found"}: provider=google-beta@9.3.0
  …
  ```
  The VPC is the first resource that needs Google; nothing past it was created. What follows is expected behaviour, from the code.
- Under the hood, in dependency order (`src/deployment/deploy_k8s/__main__.py:19-40`):
  1. VPC `cheese-app-vpc` (custom subnets, `create_network.py:7-13`), subnet `10.0.0.0/19` with Private Google Access (`:16-25`), Cloud Router (`:28-34`), Cloud NAT (`:37-48`).
  2. GKE cluster (`create_cluster.py:20-41`). This is the slow part: GKE first creates a temporary default pool and then removes it (`:28-29`). Then the node pool (`:44-72`).
  3. The kubeconfig string (`:77-131`) → `k8s.Provider` (`:134-138`) → namespace (`:141-145`), KSA (`:151-162`), IAM binding (`:184-189`) and a local `gcloud container clusters get-credentials` (`:192-199`), so `kubectl` works in this toolbox session.
  4. PVCs (`setup_containers.py:17-46`). The frontend Deployment and Service (`:51-111`) and the vector-db Deployment and Service (`:114-196`) are created in parallel.
  5. The loader Job (`:199-243`). Pulumi waits until it **completes**: download from GitHub (`src/vector-db/cli.py:479-495`) and load into Chroma (`:271-311`). Only then does it create the API Deployment and Service (`setup_containers.py:246-343`).
  6. In parallel with 4–5: the Helm release of the F5 NGINX controller (`setup_loadbalancer.py:11-46`). Pulumi waits until its LoadBalancer Service has an IP, reads that IP (`:49-59`) and builds the `sslip.io` host (`:60`). The Ingress (`:62-117`) comes **last**: besides its explicit `depends_on=[nginx_helm]` (`:115`), it uses `api_service.metadata["name"]` and `frontend_service.metadata["name"]` (`:88`, `:101`), which are outputs, so Pulumi also waits for both Services, and therefore for the loader Job and the API Deployment. Pulumi then waits until the Ingress has endpoints and a load-balancer address (3.8).
- Checkpoint (expected): a total run time of roughly 15–25 minutes (estimate), then outputs. The README (498–506) shows an **older** output set (`expected/readme-pulumi-outputs.txt`, IPs replaced by placeholders):
  ```
  Outputs:
      app_url         : "http://<IP>.sslip.io"
      cluster_endpoint: "<control-plane IP>"
      cluster_name    : "cheese-app-cluster"
      ingress_name    : "nginx-ingress"
      kubeconfig      : [secret]
      namespace       : "cheese-app-namespace"
      nginx_ingress_ip: "<IP>"
  ```
  With the current code the keys are `app_url`, `cluster_endpoint`, `cluster_name`, `ingress_name`, `ip_address`, `kubeconfig` and `namespace` (`__main__.py:43-49`), and the Ingress is named `cheese-app-ingress` (`setup_loadbalancer.py:65`). `nginx_ingress_ip` and `nginx-ingress` date from before commit `44ceff4`.
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
- Captured without a cluster (`laptop/b40`–`b44`): each prints five `memcache.go … dial tcp 127.0.0.1:8080: connect: connection refused` lines, then `The connection to the server localhost:8080 was refused - did you specify the right host or port?`, exit 1. You see exactly this in any **new** toolbox session: the kubeconfig that Pulumi's `connect-k8s-command` wrote went away with the old `--rm` container. Reconnect (not in the README):
  ```
  gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>
  ```
  (The code passes the region to `--zone`, `create_cluster.py:195-197`; `--region` says what it means. Captured only up to the "no active account" error, `laptop/b52`.)
- Checkpoint (expected): plain `kubectl get all` shows only `service/kubernetes`, because you are in `default` (as on the stand-in, `kind/k03`). The app lives in `cheese-app-namespace`. These commands are not in the README:
  ```
  kubectl get all -n cheese-app-namespace
  kubectl get pvc,ingress,serviceaccount -n cheese-app-namespace
  ```
  You should see Pods `frontend-…`, `vector-db-…`, `api-…`, `nginx-f5-…-nginx-ingress-controller-…`, a `vector-db-loader-…` Pod in `Completed`, and `job.batch/vector-db-loader 1/1`. Both PVCs should be `Bound`, and the Ingress should show the host `<IP>.sslip.io`. `kubectl get nodes` shows 1 node (2 if the autoscaler added one), and no control plane.

**Step 9. Shell into a Pod.** README 489–492.
```
kubectl get pods --namespace=cheese-app-namespace
kubectl get pod api-c4fb784b-2llgs --namespace=cheese-app-namespace
kubectl exec --stdin --tty api-c4fb784b-2llgs --namespace=cheese-app-namespace  -- /bin/bash
```
- Replace `api-c4fb784b-2llgs` with *your* Pod name from the first command: it is the README author's. On the stand-in, which has no cheese app, the first prints `No resources found in cheese-app-namespace namespace.` and the other two `Error from server (NotFound): namespaces "cheese-app-namespace" not found` (`kind/k20`–`k22`).
- The same mechanism on a Pod that exists (stand-in, not in the README): `kubectl exec --stdin --tty deployment/web -- /bin/sh`, then `hostname; ls` → `web-5cd9789488-5h48s`, `Dockerfile docker-shell.sh index.html script.js style.css` (`kind/k51`).
- Inside the API Pod, try (not in the README; read from the code, not captured):
  - `env | grep -E "ROOT_PATH|CHROMADB"`.
  - `ls /persistent`: `chat-history/<model>/` (`src/api-service/api/utils/chat_utils.py:23`) plus the `experiments/` CNN model download (`llm_cnn_utils.py:34`).
  - `python -c "import socket; print(socket.gethostbyname('vector-db'))"`: the Service's cluster IP.

**Step 10. View the app.** README 496–507: open `app_url`. Nothing in this step could be captured (no deployment); the checkpoints are expected behaviour, from the code.
- Checkpoints:
  - The home page loads, and the footer shows `API version: 3.0`. The footer calls `GET /api-service/status` (`src/frontend-react/src/components/layout/Footer.jsx:18`, `src/frontend-react/src/services/DataService.js:63`, served by `src/api-service/api/service.py:34-36`). Seeing "3.0" proves the whole browser → LB → NGINX → API path works.
  - From your laptop (not in the README): `curl http://<IP>.sslip.io/api-service/status` → `{"version":"3.0"}`. `http://<IP>.sslip.io/api-service/docs` shows Swagger.
  - Send a RAG chat message. The chat page defaults to the plain `llm` model (`src/frontend-react/src/app/chat/page.jsx:23`), so pick the RAG model (URL `/chat?model=llm-rag`). A reply proves Workload Identity (Vertex AI) and Chroma both work.
- **Model note** (from the [L20 guide](L20-deployment-pulumi.md), §9 erratum 20, which checked the same API code against Google's model list; the README does not mention it): every LLM helper hard-codes `GENERATIVE_MODEL = "gemini-2.0-flash-001"` (`src/api-service/api/utils/llm_rag_utils.py:23`, also `llm_utils.py:22`, `llm_agent_utils.py:21`, `llm_cnn_utils.py:30`), and Google's Vertex AI model-versions page lists `gemini-2.0-flash` as retired on 2026-06-01. If `/api-service/status` works but every chat fails, suspect the model before Workload Identity: switch `GENERATIVE_MODEL` to a model Vertex AI still serves and redeploy (Step 13).
- If it fails:
  - **404 from nginx** when you use the bare IP → you must use the `sslip.io` name (host rule, `setup_loadbalancer.py:79`).
  - **502/503 for the first minute** → the API is still importing TensorFlow and downloading the CNN model (`llm_cnn_utils.py:149`), and there is no readiness probe.
  - **Chat 500/403** → check the API logs (Step 11) for `PERMISSION_DENIED` (Workload Identity), a missing collection (loader/Chroma), or a model-not-found error (the model note above).

**Step 11. Logs and debugging.** README 618–657. As printed, all 14 lines fail today:
```
$ kubectl logs -n cheese-app-cluster-namespace job/vector-db-loader -c wait-for-chromadb
error: error from server (NotFound): namespaces "cheese-app-cluster-namespace" not found in namespace "cheese-app-cluster-namespace"

$ kubectl logs -n cheese-app-cluster-namespace <pod-name>
bash: -c: line 1: syntax error near unexpected token `newline'
…
$ kubectl logs -n cheese-app-cluster-namespace <pod-name> -c wait-for-chromadb
bash: line 1: pod-name: No such file or directory
```
(stand-in, `kind/k30`, `k34`, `k36`; the others in `k31`–`k43` fail the same ways.) The README uses `cheese-app-cluster-namespace` and an init container `wait-for-chromadb`; neither exists in the current code (§9 erratum 2). And `<pod-name>` is not a kubectl argument but two shell redirections, so the shell fails before kubectl runs. The working forms:
```
kubectl logs -n cheese-app-namespace job/vector-db-loader
kubectl describe job vector-db-loader -n cheese-app-namespace
kubectl logs deployment/api -n cheese-app-namespace -f
```
- These are README lines 646, 626 and 656 with the namespace fixed. Drop `-c wait-for-chromadb` from any README command: the Pod has a single container named `vector-db-loader` (`setup_containers.py:213`).
- On a Job that exists (stand-in `hello-job`, not in the README): `kubectl logs job/hello-job` prints `loading...`, `done` (`kind/k61`), and `kubectl describe job hello-job` shows `Pods Statuses: 0 Active (0 Ready) / 1 Succeeded / 0 Failed` and the events `SuccessfulCreate`, `Completed` (`kind/k62`). For the loader, look for the same `1 Succeeded`.
- `kubectl describe pod <name> -n cheese-app-namespace` and `kubectl get events -n cheese-app-namespace --sort-by=.lastTimestamp` (not in the README) explain Pending and ImagePullBackOff states.

**Step 12. Scale (not in the README; needed for Milestone 5).**
```
kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace
kubectl get pods -n cheese-app-namespace -o wide -w
kubectl get nodes -w
```
- Under the hood: the Deployment's ReplicaSet creates two more Pods, each requesting 2 Gi of memory (`setup_containers.py:80`). If they do not fit on the node, they stay `Pending` until the cluster autoscaler adds node #2 (`create_cluster.py:63-66`). The NGINX controller automatically load-balances across all three Pods: the Ingress → Service → endpoints list grows.
- The same command on the stand-in's game (`kubectl scale deployment web --replicas=4`, `kind/k55`):
  ```
  deployment.apps/web scaled
  Waiting for deployment "web" rollout to finish: 2 of 4 updated replicas are available...
  …
  NAME                   READY   STATUS    RESTARTS   AGE     IP           NODE                   …
  web-5cd9789488-5h48s   1/1     Running   0          2m18s   10.244.1.2   test-cluster-worker2   …
  web-5cd9789488-bmkj5   1/1     Running   0          2m18s   10.244.2.2   test-cluster-worker    …
  web-5cd9789488-gmbqz   1/1     Running   0          1s      10.244.2.3   test-cluster-worker    …
  web-5cd9789488-grq79   1/1     Running   0          1s      10.244.1.4   test-cluster-worker2   …
  ```
  Same ReplicaSet hash: scaling is not a template change. The stand-in has no autoscaler, so the node half of this step is expected behaviour only.
- Optional HPA: `kubectl autoscale deployment frontend --cpu-percent=50 --min=1 --max=3 -n cheese-app-namespace`, then `kubectl get hpa -n cheese-app-namespace`. See §8 B7 before trying this on `api`.
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
- Captured on the local backend, where only the stack and its reads existed (`laptop/c23`):
  ```
  Destroying (dev):
  …
   -  pulumi:pulumi:Stack deploy-k8s-dev deleted (0.00s)
  Resources:
      - 1 deleted

  Duration: 1s

  The resources in the stack have been deleted, but the history and configuration associated with the stack are still maintained.
  If you want to remove the stack completely, run `pulumi stack rm dev`.
  ```
  Yours lists every resource being deleted and ends with `Resources: - N deleted` (expected). Then run the leftover checks from §2.

---

## 5. Code tour

```
src/deployment/                       # same toolbox as L20 (Dockerfile, docker-shell.sh, docker-entrypoint.sh, ...)
├── Dockerfile                        # base image (:4, fix 1), gcloud + gke-gcloud-auth-plugin (:30, fix 2), kubectl repo 1.34 (:33-41), helm (:44)
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
- `:227-233` passes `args=["cli.py", "--download", "--load", "--chunk_type", "recursive-split"]`. `args` replaces the image's CMD and keeps its ENTRYPOINT (`src/vector-db/Dockerfile:51`), so the entrypoint runs `uv run python cli.py …` (`src/vector-db/docker-entrypoint.sh:22`). The `cluster-updates` branch used `command=` here, which replaces the ENTRYPOINT (§8 C4).
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
- The ID is `<namespace>/<release-name>-nginx-ingress-controller`. The release has no explicit `name` in `:11-46`, so Pulumi auto-generates it from `nginx-f5`. The comment on `:55` describes the *community* ingress-nginx chart's naming, not this F5 chart. Checked on 2026-11-07 against the chart's registry: `nginx-ingress` 2.3.1 is still served, and its templates name the controller Service `<release>-nginx-ingress-controller`, so the lookup matches.
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
   - Symptom: `Client Version: v1.35.9-dispatcher`, then `The connection to the server localhost:8080 was refused - did you specify the right host or port?`, exit 1 (`laptop/b11`).
   - Cause: README 409 runs it before a cluster or kubeconfig exists.
   - Fix: ignore it, or use `kubectl version --client` (README 410).

2. **`kubectl` worked yesterday, not today.**
   - Symptom: the same `connection refused` (five `memcache.go … connect: connection refused` lines first, `laptop/b40`), or `current-context is not set`.
   - Cause: the kubeconfig is written by a one-time Pulumi Command (`create_cluster.py:192-199`) into a `--rm` container (`docker-shell.sh:34`). It is gone after you exit, and the Command does not rerun on later `pulumi up`s.
   - Fix: `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <PROJECT>`.

3. **`kubectl get all` shows nothing of the app.**
   - Cause: default namespace.
   - Fix: add `-n cheese-app-namespace` (README 490–492 do), or `kubectl config set-context --current --namespace=cheese-app-namespace`.

4. **README debugging commands fail.**
   - Symptom: `error: error from server (NotFound): namespaces "cheese-app-cluster-namespace" not found in namespace "cheese-app-cluster-namespace"` (`kind/k30`), or, with the namespace fixed, `container wait-for-chromadb is not valid for pod …`.
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

8. **`deploy_k8s` preview fails with a Python error: `File "/app/deploy_k8s/setup_containers.py", line 70` … `TypeError: 'NoneType' object is not subscriptable`** (captured, `laptop/c13`), or `unknown stack "organization/deploy-images/dev"`.
   - Cause: the images stack exists in this state bucket but never finished a `pulumi up` there, so its `…-tags` outputs are `None` and `tags[0]` fails (`setup_containers.py:10-14`, `:69-71`); if the stack does not exist at all, the error is `unknown stack` instead. Logging in to a different bucket, or skipping Step 4 because "it was done in L20" in another project, has the same effect.
   - Fix: run `pulumi up --stack dev -y` in `deploy_images` into this same bucket, then preview again: `+ 23 to create` (`laptop/c20`).

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
    - Cause (checked 2026-11-07 against Docker Hub, without running the image): the Deployment uses the unpinned `chromadb/chroma` image (`setup_containers.py:132`) with the PVC at `/chroma/chroma` (`:150`). Today's `latest` is the Rust 1.x server (`CMD ["run","/config.yaml"]`), and its `/config.yaml` is the single line `persist_path: "/data"`; the course's own `llm-rag` mounts `/data` (`llm-rag:docker-compose.yml:24`). So the PVC is mounted where nothing writes, the collection lives in the container's writable layer, and the one-time Job won't reload it. `IS_PERSISTENT=TRUE` (`setup_containers.py:140-142`) also appears to be a 0.x-only server setting. Because the image has no tag, Kubernetes defaults its `imagePullPolicy` to `Always`, so a restarted Pod may also come up on a newer Chroma release than before.
    - Fix: rerun the Job (item 9). Check where the data lives with `kubectl exec deploy/vector-db -n cheese-app-namespace -- ls /data /chroma/chroma` (not in the README; the Rust image may not ship `ls`). Lasting fix: change `mount_path` to `/data`, or pin `chromadb/chroma:0.5.6` as `cluster-updates` does.

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

19. **Version skew, and a kubectl that is not the pinned one.**
    - `Dockerfile:33` pins kubectl 1.34, but in the built toolbox `/usr/bin/kubectl` is gcloud's dispatcher from Google's `kubectl` package (`1:592.0.0-0`), which outranks the 1.34 package (`laptop/b14`). It reports `v1.35.9-dispatcher` with no cluster (`laptop/b12`) and runs a client that matches the server: `v1.34.12-gke.300…` against a 1.34 cluster (`kind/k02`). GKE auto-upgrades the cluster (`create_cluster.py:69`); the dispatcher should keep the client within kubectl's ±1 minor-version support.
    - `kubectl get componentstatuses` (README 484) is deprecated: `Warning: v1 ComponentStatus is deprecated in v1.19+` (`kind/k06`).

20. **`sh docker-shell.sh` fails, then the last line blames the image.**
    - Symptom: `ERROR [ 2/16] RUN apt-get update …`, 22 × `404  Not Found` from `debian-security`, then `Unable to find image 'cheese-app-deployment:latest' locally` and `pull access denied`, exit 125 (`laptop/b02`).
    - Cause: the base image `python:3.13-slim-bullseye` (`Dockerfile:4`) points apt at Debian 11 security packages that have moved; `docker-shell.sh` does not stop when the build fails, so `docker run` tries to pull an image that was never built. After fix 1 alone, the build stops at `google-cloud-sdk` (L20's captures): Google renamed the packages (`Dockerfile:30`).
    - Fix: the two one-line edits in §2; then `[+] Building 92.3s (21/21) FINISHED` (`laptop/b03`). Read the first red line of a build, not the last.

21. **A README command prints a shell error, not a kubectl error.**
    - Symptom: `syntax error near unexpected token 'newline'` (README 634, `kind/k34`) or `pod-name: No such file or directory` (README 638 and 642, `kind/k36`, `k38`).
    - Cause: `<pod-name>` is a placeholder, and the shell reads `<` and `>` as redirections before kubectl runs.
    - Fix: replace the whole placeholder, brackets included, with a Pod name from `kubectl get pods -n cheese-app-namespace | grep vector-db-loader`. The README's sample names (`api-c4fb784b-2llgs`, `vector-db-loader-9gr5m`, `vector-db-loader-wlfdx`) are the author's, not yours: `Error from server (NotFound)` (`kind/k21`).

22. **Every Pulumi command says `error: PULUMI_ACCESS_TOKEN must be set for login during non-interactive CLI sessions`** (or, in a terminal, offers a browser login to Pulumi Cloud).
    - Cause: the toolbox entrypoint's `pulumi login gs://<project>-pulumi-state-bucket` failed (`docker-entrypoint.sh:15-23`), so Pulumi has no backend and falls back to its cloud service. The real error is earlier, in the start-up output: `invalid_grant`, `could not log in to the state backend`, `BucketNotFoundException` (`laptop/b03`, `b20`).
    - Fix: check `gcloud auth list`, the key's name and folder (`../../../secrets/deployment.json` from `src/deployment`) and `GCP_PROJECT` in `docker-shell.sh:13`, then restart the toolbox. Do not switch to Pulumi Cloud or `pulumi login --local`: the stacks and their cross-stack reference live in the GCS bucket.

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
4. **Loader Job uses `command=[ "cli.py", … ]`** (`:426-432`). That overrides the image ENTRYPOINT and would fail to start (§8 C4). It also has `backoff_limit=4` and `fs_group` (`:403,407-409`). Main uses `args=` (`setup_containers.py:227-233`).
5. The API Deployment depends only on the vector-db Service (`:513-515`), not on the Job, so the API may start before the DB is loaded.
6. `application_url` is hard-coded to `https://temp.instel.ai` (`:634`). The real app URL is not exported.

Use `main` for the tutorial. Read `cluster-updates` as a record of how the HTTPS design was explored.

**The `pipenv` branch** (2025-04-23) is the previous Ansible implementation of the same cluster: `pipenv:src/deployment/deploy-k8s-cluster.yml`, run by `ansible-playbook … --extra-vars cluster_state=present|absent` (`pipenv:README.md` lines 386, 429). It installs nginx-ingress with Helm (`:69-81`), uses `NodePort` Services (`:277,296`) and imports `gcp-service.json` as a K8s Secret (`:134-138`). Workload Identity and Pulumi state are what v3 `main` adds over it.

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l22-kubernetes-cloud/exercises.md) in the video folder. Their outputs are the 2026-11-07 captures and extra checks run for them on a second kind stand-in cluster of the same version (`assets/exercise-checks/`: manifests, scripts and logs). Nothing there used a Google account: kind is not GKE (no cloud load balancer, no node pool, no autoscaler, no Workload Identity), and whatever only GKE can show is worked out from the code, the lecture and Kubernetes' documented behaviour, and labelled so. The hands-on tasks run on the warm-up's test cluster (namespace `default`) or on your cheese-app cluster (add `-n cheese-app-namespace`); every task creates something, so delete it afterwards, and delete the cluster the same day. Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. Which control-plane part decides where a new Pod runs, and which notices that a Pod died?**
<details><summary>Answer</summary>

The **scheduler** (`kube-scheduler`) picks a node for every Pod that has none, from the nodes' free capacity counted in *requests*, and their taints. The **controllers** (`kube-controller-manager`), here the ReplicaSet controller, watch through the API server, see "desired 2, actual 1" and create a new Pod; the scheduler places it, and that node's **kubelet** starts its container. Nobody calls anybody: each part watches the API server, which stores the wish in etcd (slides 24–26). One delete on the stand-in shows the chain in the events: `Killing · kubelet`, `SuccessfulCreate · replicaset-controller`, `Scheduled · default-scheduler`, then `Pulled`, `Created`, `Started` (`kind/k53`, `k54`, `k64`). If only the **container** crashes, the Pod stays and the kubelet restarts the container in place (same name, `RESTARTS` goes up); the ReplicaSet acts when a **Pod** is gone.
</details>

**Q2. Why does `kubectl get all` show only `service/kubernetes`, and what flag fixes it?**
<details><summary>Answer</summary>

kubectl looks in one **namespace** at a time, and without a flag that is `default` (or your context's namespace). In `default` there is only the Service `kubernetes`, the door to the API server itself (`kind/k03`). The cheese app lives in `cheese-app-namespace` (`create_cluster.py:141-145`). Fixes: `-n cheese-app-namespace` (or `--namespace=…`, as README 490–492 write it); `--all-namespaces` (`-A`) for every namespace; or `kubectl config set-context --current --namespace=cheese-app-namespace`. The warm-up's game does show up in `get all`, because `deploy-k8s-tic-tac-toe.yml` names no namespace and lands in `default`.
</details>

**Q3. How does the `web` Service know which Pods are its own, and why does the API reach Chroma at `vector-db:8000`?**
<details><summary>Answer</summary>

**Labels.** The Deployment's template stamps every Pod with `run: web` (`deploy-k8s-tic-tac-toe.yml:13-14`); the Service's `selector: run: web` (`:33-34`) is a query that is re-run all the time, and its result is the endpoint list, `endpoints/web 10.244.1.2:8080,10.244.2.2:8080` on the stand-in (`kind/k50`). Take the label off a Pod and it drops out of the list at once, still running (B1). **Names.** A Service gets a stable virtual IP and a DNS name, `<service>.<namespace>.svc.cluster.local` (`kind/k52`). The cheese app's Chroma Service is `vector-db` on 8000 (`setup_containers.py:176-196`), and the API Pod gets `CHROMADB_HOST=vector-db`, `CHROMADB_PORT=8000` (`:297-304`). The short name works because a Pod's DNS search list starts with its own namespace (B5). It is L20's "containers find each other by name on a Docker network", now done by cluster DNS, and it survives every Pod replacement because the name belongs to the Service.
</details>

**Q4. Trace one click from `<IP>.sslip.io` to the API Pod. Why does the bare IP answer 404?**
<details><summary>Answer</summary>

1. **DNS:** sslip.io answers `<IP>.sslip.io` with `<IP>` itself; the program builds the host name from the load balancer's IP (`setup_loadbalancer.py:59-60`).
2. **Load balancer:** `<IP>` belongs to the `type: LoadBalancer` Service of the Helm release `nginx-f5` (`:11-46`, read back at `:49-58`); GKE's controllers asked Google for it. It forwards to a node.
3. **NGINX Ingress controller:** compares the **`Host` header** with the rule `host=<IP>.sslip.io` (`:79`), then the path: `/api-service` (Prefix) → Service `api`:9000 (`:83-93`), everything else → `frontend`:3000 (`:96-106`).
4. **Service → Pod:** the `api` Service (selector `run: api`, `setup_containers.py:325-343`) forwards to an API Pod on 9000.
5. **The prefix is kept:** the API receives `/api-service/status`; with `ROOT_PATH=/api-service` (`setup_containers.py:309-312`, `service.py:13, 50`) it answers `{"version":"3.0"}` (`service.py:34-36`), the call the footer makes.

**The bare IP:** same load balancer and controller, but the browser sends `Host: <IP>`. No rule has that host, so the controller's default server answers `404 Not Found`. Checked on the stand-in with the same chart and version and stand-in backends: with the sslip host, `/api-service/status` reached the `api` stand-in unchanged; with the bare IP, `404 Not Found`. The cloud load balancer itself was not checked.
</details>

**Q5. Why can the frontend scale to 3 but the API cannot, and what does the autoscaler add?**
<details><summary>Answer</summary>

- **Frontend:** keeps nothing on disk, and every copy requests `cpu: 250m`, `memory: 2Gi` (`setup_containers.py:79-82`). `kubectl scale deployment frontend --replicas=3 -n cheese-app-namespace` asks for three; a copy that does not fit stays `Pending`.
- **Autoscaler** (`create_cluster.py:63-66`, 1–2 nodes) is the **node** level: it adds a node when a Pod is `Pending` for lack of room, up to two, and removes under-used ones. It never adds Pods.
- **API:** mounts `persistent-pvc`, a `ReadWriteOnce` disk that attaches to one node at a time (`setup_containers.py:17-30`, `:265-271`). A copy on the other node waits in `ContainerCreating` with a `Multi-Attach error`; more nodes cannot help, because the limit is the disk. It also has no `resources` block, so the scheduler cannot plan for it and a CPU-based Pod autoscaler cannot work (B7).

So scaling here is: nodes automatically (1–2), Pods by hand (`kubectl scale`, as Milestone 5 asks), and only for stateless Deployments with requests. The Multi-Attach and autoscaler behaviour rest on the code and GKE's documentation; kind cannot show them.
</details>

### Hands-on (predict, then run)

- **B1 · Take a Pod out of its Service.** Relabel one web Pod `run=debug`. *(Three Pods: the ReplicaSet makes a replacement; the relabelled Pod keeps running, leaves the endpoint list and loses its `ownerReferences`. Delete it yourself: a real trick to pull a misbehaving Pod out of traffic and keep it for inspection.)*
- **B2 · Change the template.** `kubectl set env deployment/web COLOR=blue`, then `kubectl rollout undo`. *(A new template means a new ReplicaSet `web-<new hash>`, the old one scaled to 0 and kept; the undo scales the old one back. `--replicas` is not a template change and keeps the same ReplicaSet, `kind/k55`.)*
- **B3 · A crash is not a delete.** A container that exits with code 1 after 8 s. *(The same Pod stays; the kubelet restarts the container with growing waits: `CrashLoopBackOff`. Only `kubectl delete pod` makes a new Pod.)*
- **B4 · The NodePort on a node with no web Pod.** *(It answers `200`: kube-proxy on every node forwards it. A `LoadBalancer` Service is a NodePort Service with a cloud load balancer in front.)*
- **B5 · Names across namespaces.** *(From `default`, `vector-db` does not resolve and the full `vector-db.cheese-app-namespace.svc.cluster.local` does; from inside `cheese-app-namespace` the short name works. API and Chroma must share a namespace for `CHROMADB_HOST=vector-db`.)*
- **B6 · Requests decide the packing.** A Pod requesting 3 CPUs, scaled to 3 on 4-CPU workers. *(One per worker, the third `Pending` with `0/3 nodes are available: 1 node(s) had untolerated taint(s), 2 Insufficient cpu`. On GKE the autoscaler would add the second node; not run here.)*
- **B7 · A Pod autoscaler needs requests.** `kubectl autoscale deployment web --cpu-percent=50 --min=2 --max=4`. *(No requests: `cpu: <unknown>/50%`, `missing request for cpu`; with `--requests=cpu=50m`: `cpu: 0%/50%`. On the cheese app, `frontend` would work, `api` would not.)*
- **B8 · Follow the Ingress.** Who answers `/`, `/status`, `/api-service/status`, `/api-service`, `/api-servicex/status` and the bare IP? *(Frontend; frontend; API `200 {"version":"3.0"}`; API `307` to `/api-service/`; surprisingly the **API** with `404`, because the F5 controller writes a plain nginx prefix `location /api-service {` that matches characters, not path segments; the controller's own `404`.)*

### Debugging

- **C1 · The README's first debugging line** (`kind/k30`): wrong namespace, and after fixing it, `container wait-for-chromadb is not valid`: the pre-refactor program had an init container. Use `kubectl logs -n cheese-app-namespace job/vector-db-loader`.
- **C2 · Angle brackets** (`kind/k34`, `k36`): shell redirections, so the messages never mention kubectl; replace placeholders with their brackets.
- **C3 · kubectl worked yesterday** (`laptop/b40`–`b45`): no kubeconfig in the new `--rm` toolbox; `gcloud container clusters get-credentials cheese-app-cluster --region us-central1 --project <your project>`.
- **C4 · `command` or `args`?** (`cluster-updates` vs `main`): `command` replaces the image's ENTRYPOINT, so the runtime looks for a program `cli.py` and fails with `exec: "cli.py": executable file not found in $PATH` (checked with an image of the same shape); `args` replaces CMD and works.
- **C5 · "Retry up to 4 times"**: `backoff_limit=3` means 3 retries, 4 Pods, `BackoffLimitExceeded` after a little over a minute (checked on the stand-in).
- **C6 · Read the scheduler's message**: untolerated taint (the control plane) plus `Insufficient cpu`; lower the request, scale down, or add room. For the frontend it would say `Insufficient memory`.
- **C7 · `ImagePullBackOff`**: images never pushed in this project, the repository `cheese-app-repository` never created, or nodes running as an account without registry read access; an arm64 image pulls but fails with `exec format error`.
- **C8 · A Python error in a Kubernetes preview** (`laptop/c13`): `deploy_images` never finished `pulumi up` in this state bucket (§6 item 8).
- **C9 · A typo that fails late**: a misspelt config key reads as `None` and becomes the text `"None"` in the KSA annotation and the IAM binding; `pulumi config` shows it before `up`.
- **C10 · A bug on line 74?** `deploy_images/__main__.py:74` exports `frontend_image.tags` as the vector-db tags, but the variable was reassigned at line 62, so the value is right (`laptop/c03`): confusing, not wrong.

### Think

- **D1 · Why does the API wait for the loader?** *(`main`: never serves an empty collection, but a broken loader blocks the whole API; `cluster-updates`: faster and independent, but early RAG requests fail and nobody notices. Middle way: start the API with a readiness check.)*
- **D2 · One replica can still clash.** *(Yes: `RollingUpdate` starts the new Pod first; on the other node it cannot attach the RWO disk, and the rollout stalls. Use `strategy: Recreate` or shared storage.)*
- **D3 · What to delete first.** *(LoadBalancer Services and PVCs are cleaned up in the background by the cluster's controllers; delete the cluster first and forwarding rules, firewall rules or `pvc-…` disks can stay and keep billing. Registry images are kept on purpose.)*
- **D4 · Workload Identity instead of a key.** *(`api-ksa` is annotated with `gcp-service@…` and bound with `roles/iam.workloadIdentityUser`; GKE's metadata server hands the Pod short-lived tokens. Without `service_account_name`, the Pod starts but the first Vertex AI call is refused.)*
- **D5 · The database forgets.** *(The PVC is mounted at `/chroma/chroma`, but today's Chroma writes `/data`, so the data died with the Pod. Rerun the loader; for good, mount at `/data` or pin `chromadb/chroma:0.5.6`.)*

---

## 9. Errata and open questions

### Errata (with evidence)

1. **README outputs block is outdated.**
   - README 498–506 shows `nginx_ingress_ip` and `ingress_name: "nginx-ingress"` (and sample IP addresses; this guide shows them as `<IP>`).
   - The code exports `ip_address` (`deploy_k8s/__main__.py:48`), and the Ingress is named `cheese-app-ingress` (`setup_loadbalancer.py:63-65`). Both were renamed in commit `44ceff4` ("Added SSL loadbalancer", 2025-11-21), after the README text.
2. **README debugging section uses names that no longer exist.**
   - README 620–656 uses namespace `cheese-app-cluster-namespace` and container `wait-for-chromadb`.
   - Current namespace: `cheese-app-namespace` (`create_cluster.py:143`). The Job has no init container (`setup_containers.py:199-243`).
   - The names come from the pre-refactor program at `3149e56`. Captured 2026-11-07 on the stand-in: all 14 lines fail as printed, 11 with the namespace error or `No resources found`, and the three `<pod-name>` lines with shell redirection errors (`kind/k30`–`k43`; §6 items 4 and 21).
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
7. **`kubectl version` (README 409) errors before a cluster exists.** It's harmless but confusing at the first checkpoint: `The connection to the server localhost:8080 was refused - did you specify the right host or port?` (`laptop/b11`).
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
10. **ChromaDB image unpinned, mount path stale.**
    - `image="chromadb/chroma"` (`setup_containers.py:132`) is mounted at `/chroma/chroma` (`:150`). That is the 0.x layout: the `cluster-updates` branch pins `0.5.6` with the same path (`cluster-updates:…/__main__.py:328,346`).
    - The course's newer `llm-rag` mounts `chromadb/chroma:latest` at `/data` (`llm-rag:docker-compose.yml:19,24`).
    - Confirmed on 2026-11-07 from the registry (image config and its `/config.yaml` layer, no image run): today's `chromadb/chroma:latest` persists to `/data`. The 10 Gi PVC is therefore unused and the vector DB is lost whenever its Pod restarts (§6 item 14).
11. **Control-plane CIDR outside RFC 1918.** `master_ipv4_cidr_block: "172.0.0.0/28"` (`create_cluster.py:33`; same on `cluster-updates:…:90`) is public address space; RFC 1918's 172 block is 172.16.0.0/12. It evidently worked for the course, but `172.16.0.0/28` would be the conventional choice.
12. **Kubeconfig convenience is ephemeral.**
    - The `connect-k8s-command` (`create_cluster.py:192-199`) runs once, inside a `--rm` container, so later sessions have no kubeconfig and the README never says how to restore it.
    - It passes the *region* to `--zone` (`:197`), see the open questions.
13. **Demo manifest that cannot work on Kubernetes.** `visualizer.yaml:18` runs `dockersamples/visualizer`, a Docker Swarm visualizer that needs the Docker socket and Swarm. It is not referenced in the README. `emoji.yaml` (added by `11bd16e`) isn't referenced either.
14. **Anchor structure.** The course link points at `#deployment-with-scaling-using-kubernetes` (README 392), but the actual cluster steps are under a separate H2, "Create & Deploy Cluster" (README 436). Readers following the course link may stop at line 434.
15. **README 318–322** ("Deployment Setup … inventory.yml") are Ansible-era leftovers in the shared prerequisites. The SSH/OS Login steps before them (282–316) are only needed for L20's `security:ssh_user`; none of this is needed for `deploy_k8s`.
16. **README Mermaid diagram edge reversed.** `V -.->|one-time load| J` (README 466) draws the arrow from the vector-db Service to the loader Job; the Job writes into the vector DB (`setup_containers.py:199-243`, `src/vector-db/cli.py:271-311`).
17. **Unused env var in `deploy_images`.** `location = os.environ["GCP_REGION"]` (`deploy_images/__main__.py:10`) is required but never used; the registry host is hard-coded (`:15`). Likewise `artifactregistry` is imported (`:4`) but unused.
18. **The deployment toolbox does not build as committed** (captured 2026-11-05 for L20 and again 2026-11-07, `laptop/b02`): `Dockerfile:4` (Debian 11 base, security pool moved) and `Dockerfile:30` (renamed Google packages). Fixes in §2; with both, it builds in 92.3 s (`laptop/b03`).
19. **The kubectl pin has no effect.** `Dockerfile:33-41` installs kubectl 1.34 from pkgs.k8s.io, but Google's `kubectl` package (`1:592.0.0-0`) wins and `/usr/bin/kubectl` is gcloud's dispatcher: `v1.35.9-dispatcher` (`laptop/b12`, `b14`). Harmless.
20. **`docker-shell.bat` (README 529) does not exist** in the repo; on Windows use WSL.

### Open questions (could not be determined from the sources)

- **Ed lesson content:** https://edstem.org/us/courses/97373/lessons/166047/ was not accessible. Slides or announcements there may update any of the above.
- **`gcloud container clusters get-credentials … --zone us-central1`** (`create_cluster.py:195-197`): gcloud probably forwards the value as the cluster *location*, so it would work for a regional cluster, but this was not run. `--region us-central1` is the unambiguous form.
- **Whether the IAM Service Account Credentials API must be enabled** for Workload Identity in a fresh project.
- **Whether `deployment` in the instructors' project had extra roles** that hid erratum 4.
- **Exact Helm release name** that Pulumi generates for `nginx-f5` (the random suffix is visible only in a real run). Resolved on 2026-11-07: chart `nginx-ingress` `2.3.1` is still listed at `https://helm.nginx.com/stable` (`setup_loadbalancer.py:13-17`), and its templates name the controller Service so that the lookup at `:49-58` matches.
- **Does `pulumi up --refresh` revert a manual `kubectl scale`?** The program never sets `replicas`, and pulumi-kubernetes 4.x uses server-side apply, so the manual value is expected to survive. Verify with `kubectl get deploy -n cheese-app-namespace` after an update.
- **GKE version at the time you create the cluster:** it depends on the release channel. The toolbox's kubectl dispatcher picked a matching client for a 1.34 server (`kind/k02`); whether it does the same for every GKE version was not checked.
- **Current prices and free-tier rules** for GKE management fees, NAT and load balancers. The numbers in §2 are approximate and were not checked against the current price list.
- **Run time and memory:** the GKE stack could not be run here (no account; `pulumi up` stops at the VPC, `laptop/c21`). The 15–25 minute estimate and whether Chroma fits in its 256 Mi limit during the load (`setup_containers.py:155`) are unverified.
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

**Video and companion files**
- [AC215 · L22 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l22-kubernetes-cloud) (two parts: the test cluster and Kubernetes itself; the cheese app on GKE) · [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l22-kubernetes-cloud/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l22-kubernetes-cloud/assets/terminal) · [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l22-kubernetes-cloud/ASSETS.md) · [`SLIDES.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l22-kubernetes-cloud/SLIDES.md)

**Course**
- Ed lesson: [L22 · Scaling: Kubernetes (cloud)](https://edstem.org/us/courses/97373/lessons/166047/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/) · [Milestone 5](https://harvard-iacs.github.io/2026-AC215/milestone5/)
- Colab notebooks: none for this lecture.
- Previous lecture: [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md) (`cheese-app-ci-cd`). L19 · Scaling: Kubernetes (local) has no tutorial yet ("coming soon" on the course site), so it has no guide.
- Next lecture: [L23 · Final Deployment and Review](L23-final-cicd-deployment.md) (`cheese-app-v4`: the same cluster, deployed by GitHub Actions)
- Referenced in §7: [L20 · Deployment: Pulumi](L20-deployment-pulumi.md) (the toolbox, `deploy_images` and the single-VM deployment) · [L18 · APIs + Frontend](L18-apis-frontend.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md) · [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md)
