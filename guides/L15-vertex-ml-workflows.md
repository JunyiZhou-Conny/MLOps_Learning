# L15 · ML Workflows with Vertex AI — study guide

**Ed:** [lesson 166040](https://edstem.org/us/courses/97373/lessons/166040/) · **Tutorials:** [dlops-io/model-deployment](https://github.com/dlops-io/model-deployment) `main` @ [`3fbf63f`](https://github.com/dlops-io/model-deployment/tree/3fbf63f1030f762ad3b3b1c6e376144083306eda) and [dlops-io/ml-workflow](https://github.com/dlops-io/ml-workflow) `main` @ [`972ffbb`](https://github.com/dlops-io/ml-workflow/tree/972ffbb5cb148f9fa6256e7137300dff2b174e2e) · **Video:** planned · Made from the verified digest, 2026-10-12

## 中文速览

- **做什么（Part A）：** 把一个已经 train 好的 cheese classifier（MobileNetV2，`.keras`）加一个 custom serving signature，存成 SavedModel 放进 GCS bucket，然后 `Model.upload` 注册到 Vertex AI Model Registry，再 `deploy` 到一个 Endpoint，最后用 base64 JSON 调 `endpoint.predict`。
- **做什么（Part B）：** 用 Kubeflow Pipelines (KFP) v2 DSL 把 data collector → data processor → model training → model deploy 串成一个 Vertex AI Pipeline。你本地的 container 只负责 compile 出 `pipeline.yaml` 并 submit，每个 step 都是 Google 托管机器上的一个 container。
- **核心概念 1：** 把 preprocessing 放进 model 里：`serving_default` signature 吃 JPEG bytes、吐 4 个 probability；request 必须写成 `{"bytes_inputs": {"b64": ...}}`，key 要和 signature 的参数名完全一致。
- **核心概念 2：** Model（registry 里的一条记录，只记 artifact 在哪、用哪个 serving image）≠ Endpoint（一个地址）≠ DeployedModel（真正在跑、按 node-hour 计费的 VM）。只 register 不能调用，必须 deploy。
- **核心概念 3：** `@dsl.container_component` 跑你自己的 image；`@dsl.component` 是 lightweight Python component，只把 function body 拷进 YAML（所以 import 写在函数里面）。`@dsl.pipeline` 在 decoration 时就 trace 一遍，`.after()` 只排顺序、不传数据，数据全靠 GCS bucket；pipeline 以 `ml-workflow` service account 的身份运行。
- **一个反直觉的事实：** 在 `main` 上 training job 从 GitHub 下载固定的 `cheese_4_labels.zip`，根本不读 `clean.zip`，所以 data steps 和 training 之间只有顺序依赖，没有数据依赖。
- **最费时间的坑 1：** 每个 `docker-shell.sh` 都写死了老师的 project 和 bucket，`model-deployment/cli.py` 里还写死了老师的 endpoint，这些全部要改成你自己的。`--platform` 也各不相同（arm64 / amd64）：在 Intel/AMD 机器上 build arm64 image 会极慢或者直接 `exec format error`，要先把 arm64 那行改掉。
- **最费时间的坑 2：** README 没让你建 `GCS_PACKAGE_URI` 那个 bucket，也没提 `model-trainer.json`，但 pipeline 的 training step 需要 `cheese-app-trainer.tar.gz`（先跑 `sh package-trainer.sh`）。另外 `python cli.py --model_deploy` 本身有 bug（name shadowing → `TypeError`）。
- **做完马上删：** 每次 `deploy` 都会新建一个 Endpoint，`min_replica_count=1` 意味着没有流量也 24/7 计费。用 `gcloud ai endpoints undeploy-model` + `gcloud ai endpoints delete` 删掉所有 endpoint，再用 `gcloud ai models delete` 清理 Model Registry；bucket 里的文件可选删除。

## At a glance

- **What you build.** You turn a trained cheese classifier into a SavedModel that accepts raw JPEG bytes, register it in the Vertex AI Model Registry, deploy it to a Vertex AI Endpoint and query it with base64 JSON (`model-deployment`). You then chain the cheese app's stages (collect images, clean them, train on Vertex AI, register and deploy) into a Vertex AI Pipeline written with the KFP v2 DSL, compiled to `pipeline.yaml` in your container and run by Vertex (`ml-workflow`).
- **Time needed.** A rough estimate is half a day. The setup (two service accounts and keys, up to three buckets, editing five `docker-shell.sh` files) and the image builds take a good part of it. Part A's endpoint deploy commonly takes 10–20 minutes (not timed during verification). The full pipeline runs well over half an hour (not run during verification), and `run()` keeps your terminal busy until it finishes.
- **Prerequisites.**
  - A GCP project with billing enabled; everything uses `us-central1`.
  - Docker Desktop (or Docker Engine) and `git`. No local Python.
  - L13 done, ideally: its trainer key (`model-trainer.json`) and trainer bucket can be reused by `ml-workflow/src/model-training`. Without them, copy `ml-workflow.json` to `model-trainer.json` and create the `GCS_PACKAGE_URI` bucket (section 2).
  - A Docker Hub account only if you rebuild and push the step images yourself (optional).
  - Background from L2–L4 (containers talking through a bucket), L10/L11 (service-account keys, `secrets/`), L13 and L14; see section 7.
- **What it costs.**
  - Vertex AI Endpoints bill per node-hour, **24/7, even with zero traffic**. Part A uses one `n1-standard-2` node, Part B one `n1-standard-4` node, and every `--deploy` or pipeline run creates another endpoint.
  - Vertex AI Custom Training bills per minute while the job runs (`n1-standard-4`; the pipeline trains 15 epochs on CPU).
  - Vertex AI Pipelines: a small per-run fee plus the compute for each step.
  - GCS and Model Registry entries: small (storage only).
  - Check current prices on the Vertex AI pricing page; they were not verified for this guide.
- **What to tear down** (commands in the checklist's last section and in section 2):
  1. Every endpoint: Part A's `model-mobilenetv2_train_base_True.v1_endpoint` (one per `--deploy`) and Part B's `Cheese App Model_endpoint` (one per pipeline run that reaches Model Deploy, and one per `--model_deploy`). Undeploy the model, then delete the endpoint.
  2. The Model Registry entries (`gcloud ai models delete`).
  3. Optionally the bucket contents: the SavedModel, `raw.zip`, `clean.zip`, `model/`, `pipeline_root/`.
  4. Any stuck training job (Vertex AI → Training in the console).
- **How to read the references.** Paths are written from the folder that holds your clones: `ml-workflow/src/workflow/cli.py:160` means line 160 of `src/workflow/cli.py` inside your `ml-workflow` clone. Paths into the Python SDKs are prefixed with the package name. The SDK behaviour described here was checked by reading (not running) the PyPI sources of the locked versions: `google-cloud-aiplatform==1.121.0`, `kfp==2.14.6`, `difPy==4.2.1` (locked in `model-deployment/uv.lock`, `ml-workflow/src/workflow/uv.lock` and `ml-workflow/src/data-processor/uv.lock`); the workflow container locks aiplatform 1.120.0, assumed to behave the same for the calls used. The old `origin/pipenv` branches (`model-deployment` @ `5e2281a`, 2024-10-29; `ml-workflow` @ `f8fd6a2`, 2025-04-01, when the trainer still read `tfrecords.zip` from the bucket; diffs in section 7) and the AWS variants `model-deployment-aws` / `ml-workflow-aws` are not covered. There are no Colab notebooks for L15.

## Command checklist

Host steps run in the folder named in each section; every command after `sh docker-shell.sh` runs in the container shell it opens, until the next section changes folder. Commands are written exactly as the READMEs write them; *(extra)* marks commands and steps that are not in the README.

### Part A · model-deployment · Clone the github repository

- [ ] Clone or download https://github.com/dlops-io/model-deployment, side by side with your `ml-workflow` clone so both share one `secrets/` folder (layout in section 2).

### Part A · model-deployment · API's to enable in GCP for Project

- [ ] Console: search for "Vertex AI API" in the GCP search bar and click Enable.

### Part A · model-deployment · Setup GCP Credentials

- [ ] Create a folder `secrets` at the same level as the `model-deployment` folder (outside the repo, never in Git).
- [ ] Console: IAM & Admin → Service accounts → create `model-deployment` with Storage Admin, AI Platform Admin and Vertex AI Administrator.
- [ ] Console: Actions ⋮ → Manage keys → Create private key → JSON; copy the file into `secrets/` and rename it `model-deployment.json`.
- [ ] `ls ../secrets/model-deployment.json` *(extra)* — run from inside `model-deployment/`; succeeds only if the key is where `model-deployment/docker-shell.sh:7` looks.

### Part A · model-deployment · Create GCS Bucket

- [ ] Console: go to https://console.cloud.google.com/storage/browser and create your models bucket (the README's `cheese-app-models-demo` is the instructors'; bucket names are globally unique).

### Part A · model-deployment · Run `docker-shell.sh`

- [ ] *(extra)* Edit `model-deployment/docker-shell.sh:8-9`: `GCP_PROJECT` (your project **ID**) and `GCS_MODELS_BUCKET_NAME`. On an Intel/AMD machine, comment out line 15 (`--platform=linux/arm64/v8`) and uncomment line 13.
- [ ] Open a terminal inside the `model-deployment` folder.
- [ ] `sh docker-shell.sh` — builds the `model-deployment-cli` image (python 3.11, tensorflow 2.17.0, google-cloud-aiplatform 1.121.0) and opens a bash shell in it with the key activated for gcloud.

### Part A · model-deployment · Prepare Model for Deployment

- [ ] `python cli.py --prepare` — downloads the v3.0 cheese model from GitHub, wraps it in a JPEG-bytes `serving_default` signature and saves the SavedModel to `gs://<bucket>/model-mobilenetv2_train_base_True.v1`.
- [ ] `gsutil ls gs://<bucket>/model-mobilenetv2_train_base_True.v1/` *(extra)* — should list `saved_model.pb` and `variables/`, among others.
- [ ] `saved_model_cli show --dir gs://<bucket>/model-mobilenetv2_train_base_True.v1 --tag_set serve --signature_def serving_default` *(extra)* — should show an input `bytes_inputs` of dtype `DT_STRING` with shape `(-1)`.

### Part A · model-deployment · Upload & Deploy Model to Vertex AI

- [ ] `python cli.py --deploy` — registers the model in the Model Registry (`Model.upload`) and deploys it to a **new** endpoint on one `n1-standard-2` node; takes minutes.
- [ ] Copy the endpoint resource name it prints, `projects/<NUMBER>/locations/us-central1/endpoints/<ENDPOINT_ID>` (your project *number*, not your project ID).

### Part A · model-deployment · Test Predictions

- [ ] Update the endpoint uri in `cli.py`: replace the string at `model-deployment/cli.py:157` with the name you copied.
- [ ] `python cli.py --predict` — sends 5 randomly picked `data/*.jpg` images as `{"bytes_inputs": {"b64": ...}}` and prints the 4 probabilities, the argmax and the label (the README's sample output is from an old 3-class mushroom model).

### Part A · Clean up now *(extra, not in README)*

- [ ] `gcloud ai endpoints list --region=us-central1` *(extra)* — find your endpoint's ID.
- [ ] `gcloud ai endpoints describe ENDPOINT_ID --region=us-central1` *(extra)* — shows `deployedModels[].id`.
- [ ] `gcloud ai endpoints undeploy-model ENDPOINT_ID --region=us-central1 --deployed-model-id=DEPLOYED_MODEL_ID` *(extra)* — removes the billed node.
- [ ] `gcloud ai endpoints delete ENDPOINT_ID --region=us-central1` *(extra)* — deletes the endpoint. (Registry entries cost little; delete them in the final clean-up.)

### Part B · ml-workflow · Clone the github repository

- [ ] Clone or download https://github.com/dlops-io/ml-workflow next to `model-deployment/` and `secrets/`.

### Part B · ml-workflow · API's to enable in GCP for Project

- [ ] Console: enable "Vertex AI API" (already on if you did Part A in the same project).

### Part B · ml-workflow · Setup GCP Credentials

- [ ] Make sure `secrets/` sits at the same level as the `ml-workflow` folder (the one from Part A).
- [ ] Console: create the service account `ml-workflow` with Storage Admin, AI Platform Admin, Vertex AI Administrator and **Service Account User**.
- [ ] Console: Manage keys → JSON key; copy it into `secrets/` and rename it `ml-workflow.json`.
- [ ] `cp secrets/ml-workflow.json secrets/model-trainer.json` *(extra)* — run in the folder that holds `secrets/`, only if you no longer have your L13 key; `ml-workflow/src/model-training/docker-shell.sh:25` expects that file name.

### Part B · ml-workflow · Create GCS Bucket

- [ ] Console: create your `GCS_BUCKET_NAME` bucket (the README's `cheese-app-ml-workflow-demo` is the instructors').
- [ ] Console *(extra, not in README)*: create the `GCS_PACKAGE_URI` bucket for the trainer tarball, or reuse your L13 trainer bucket.
- [ ] `mkdir -p persistent-folder` *(extra)* — in the folder that holds `secrets/`, so the folder is owned by you and not by root (matters on Linux).
- [ ] *(extra)* Edit the env vars in every `docker-shell.sh` under `ml-workflow/src/` (table in section 2): `data-collector` lines 11-12, `data-processor` lines 11-12, `model-training` lines 9-12, `workflow` lines 8-12.

### Part B · ml-workflow · Run Data Collector Container & Test CLI

- [ ] Open a terminal inside the `src/data-collector` folder.
- [ ] `sh docker-shell.sh` — builds the collector image (python 3.12, `--platform=linux/amd64`) and opens bash as user `app`.
- [ ] `python cli.py --search --nums 10 --query "brie cheese" "gouda cheese" "gruyere cheese" "parmigiano cheese"` — scrapes 10 Bing images per query into `/persistent/dataset/raw/`, zips them and uploads `raw.zip` to the bucket root.
- [ ] Check your GCS bucket to see if `raw.zip` was uploaded.

### Part B · ml-workflow · Run Data Processor Container & Test CLI

- [ ] Open a terminal inside the `src/data-processor` folder.
- [ ] `sh docker-shell.sh` — builds the processor image and opens a shell.
- [ ] `python cli.py --clean` — reuses the local `raw/` folder (or downloads `raw.zip`), removes duplicates with difPy, deletes files that are not decodable JPEGs and uploads `clean.zip`.
- [ ] Check your GCS bucket to see if `clean.zip` was uploaded. Do not run `--prepare` here (broken; section 6, item 9).

### Part B · ml-workflow · Run Model Training Container & Test CLI (We did this previous lecture)

- [ ] *(extra)* On Intel/AMD, change `--platform=linux/arm64` at `ml-workflow/src/model-training/docker-shell.sh:18` first.
- [ ] Open a terminal inside the `src/model-training` folder.
- [ ] `sh docker-shell.sh` — builds the model-training image and opens a shell; needs `/secrets/model-trainer.json`.
- [ ] `sh package-trainer.sh` — tars and gzips `package/` and uploads it as `$GCS_PACKAGE_URI/cheese-app-trainer.tar.gz`; **required** by the pipeline's training step.
- [ ] `gsutil ls $GCS_PACKAGE_URI` *(extra)* — should show `cheese-app-trainer.tar.gz`.
- [ ] `python cli.py --train` — optional: a standalone Vertex AI training job (`tf-cpu.2-14.py310`, 2 epochs), billed per minute.

### Part B · ml-workflow · Build & Push Images (optional, already done for you)

- [ ] Sign up in Docker Hub and create an Access Token.
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — log in to Docker Hub.
- [ ] `docker build -t <USER NAME>/<IMAGE_NAME> -f Dockerfile .` — build and tag the image (inside `src/data-collector` and `src/data-processor`).
- [ ] `docker build -t <USER NAME>/<IMAGE_NAME> --platform=linux/amd64/v2 -f Dockerfile .` — the same on M1/M2 Macs; Vertex runs amd64.
- [ ] `docker push <USER NAME>/<IMAGE_NAME>` — push to Docker Hub.
- [ ] `sh docker-shell-push.sh` *(extra)* — the repo's alternative: a multi-arch (amd64 + arm64) `docker buildx ... --push`; set `DOCKER_USERNAME` (line 10) and run `docker login` first. If you push your own images, change `ml-workflow/src/workflow/cli.py:27-28`.

### Part B · ml-workflow · Automate Running Data Collector Container

- [ ] Open a terminal inside the `src/workflow` folder.
- [ ] `sh docker-shell.sh` — builds the workflow image (python 3.13, kfp 2.14.6, aiplatform 1.120.0, amd64) and opens a shell; `set -e` is commented out, so read the build output.
- [ ] `python cli.py --data_collector` — compiles a one-task pipeline to `data_collector.yaml` and submits it as a `PipelineJob` to Vertex AI.
- [ ] Inspect `data_collector.yaml`.
- [ ] Console: open [Vertex AI Pipelines](https://console.cloud.google.com/vertex-ai/pipelines) and follow the job's status.

### Part B · ml-workflow · Cheese App: Vertex AI Pipelines (Entire Pipeline)

- [ ] `python cli.py --pipeline` — compiles the four-step DAG (collector → processor → training → deploy) to `pipeline.yaml`, submits it and waits for the run.
- [ ] Inspect `pipeline.yaml`.
- [ ] Console: open Vertex AI Pipelines and compare the graph with the README's screenshots.
- [ ] *(extra)* Afterwards, find the new model "Cheese App Model", the new endpoint "Cheese App Model_endpoint" (billed 24/7) and `raw.zip`, `clean.zip`, `model/` in your bucket.

### Part B · ml-workflow · Test Specific Components

- [ ] `python cli.py --data_collector` — the collector as a one-task pipeline.
- [ ] `python cli.py --data_processor` — the processor as a one-task pipeline.
- [ ] `python cli.py --model_training` — the training launcher as a one-task pipeline.
- [ ] *(extra)* Before the next command, change `model_deploy(` to `model_deploy_job(` at `ml-workflow/src/workflow/cli.py:160`; otherwise it fails with a `TypeError` (section 6, item 8).
- [ ] `python cli.py --model_deploy` — registers and deploys `gs://<bucket>/model` as a one-task pipeline (creates **another** endpoint).

### Part B · ml-workflow · Vertex AI Pipelines: Samples

- [ ] Open a terminal inside the `workflow` folder.
- [ ] `sh docker-shell.sh` — the workflow container again (or reuse the open shell).
- [ ] `python cli.py --sample` — runs `sample_pipeline(a=3.0, b=4.0)`: 4 tasks, output `5.0`; overwrites the committed `sample-pipeline1.yaml`.

### Final clean-up *(extra, not in README)*

Run these in any container whose entrypoint authenticated gcloud (`model-deployment`, `workflow`, `model-training`).

- [ ] `gcloud ai endpoints list --region=us-central1` *(extra)* — every endpoint from Part A and Part B.
- [ ] `gcloud ai endpoints describe ENDPOINT_ID --region=us-central1` *(extra)* — shows `deployedModels[].id`.
- [ ] `gcloud ai endpoints undeploy-model ENDPOINT_ID --region=us-central1 --deployed-model-id=DEPLOYED_MODEL_ID` *(extra)* — removes the billed node.
- [ ] `gcloud ai endpoints delete ENDPOINT_ID --region=us-central1` *(extra)* — deletes the endpoint. Repeat the last three for each endpoint.
- [ ] `gcloud ai models list --region=us-central1` *(extra)* — the Registry entries.
- [ ] `gcloud ai models delete MODEL_ID --region=us-central1` *(extra)* — deletes one (only works once it is no longer deployed).
- [ ] `gsutil rm -r gs://<bucket>/...` *(extra)* — optional: remove bucket contents you no longer need.
- [ ] Console: Vertex AI → Training; cancel any job that is still running.

## 1. What you build

The lecture has two parts.

**Part A (model-deployment).** You take an image classifier that was already trained: MobileNetV2 fine-tuned on four cheeses, shipped as a `.keras` file in a GitHub release. You wrap it in a new serving signature, so the model itself turns raw JPEG bytes into a 224×224 float tensor. You save that SavedModel to a GCS bucket. Then you:
- register it in the Vertex AI **Model Registry** (`aiplatform.Model.upload`), together with a Google prebuilt TensorFlow serving container,
- deploy it to a Vertex AI **Endpoint** (`model.deploy`), which is a managed HTTPS URL backed by at least one always-on VM,
- send it base64-encoded JPEGs as `instances = [{"bytes_inputs": {"b64": b64str}}]` through `endpoint.predict(instances=instances)`.

**Part B (ml-workflow).** You take the cheese app's lifecycle stages and chain them into one **Vertex AI Pipeline**, written with the **Kubeflow Pipelines (KFP) v2 DSL**. The stages are: collect images from Bing, de-duplicate and clean them, train on Vertex AI, and register plus deploy. Your laptop only *compiles* the Python pipeline definition into `pipeline.yaml` and *submits* it. Google-managed machines then run each step as a container.

The steps hand data to each other through files in one GCS bucket (`raw.zip`, `clean.zip`, `model/`), not through KFP artifacts. And, as shown below, the training step does not actually read what the data steps produce.

```
PART A — model-deployment (all calls go out from your laptop; no local ports are published)

 your laptop / Docker Desktop                                      Google Cloud  (project $GCP_PROJECT, us-central1)
 +------------------------------------------+
 | container "model-deployment-cli"         |  (1) HTTP GET .zip   +-------------------------------------+
 | python 3.11, tensorflow 2.17.0,          | <------------------- | github.com/dlops-io/models v3.0     |
 | google-cloud-aiplatform 1.121.0          |                      | mobilenetv2_train_base_True.zip     |
 |                                          |                      +-------------------------------------+
 | volumes:  ./          -> /app            |  (2) tf.saved_model.save(..., gs://...)
 |           ../secrets/ -> /secrets        | -------------------> +-------------------------------------+
 | env: GOOGLE_APPLICATION_CREDENTIALS=     |                      | GCS gs://$GCS_MODELS_BUCKET_NAME/   |
 |        /secrets/model-deployment.json    |                      |   model-mobilenetv2_train_base_True |
 |      GCP_PROJECT, GCS_MODELS_BUCKET_NAME |                      |   .v1/ (saved_model.pb, variables/) |
 |                                          |                      +------------------+------------------+
 | $ python cli.py --prepare                |  (3) Model.upload (REST)                | artifact_uri
 | $ python cli.py --deploy                 | -------------------> +------------------v------------------+
 | $ python cli.py --predict                |                      | Vertex AI Model Registry            |
 |                                          |                      |  model + serving image              |
 |                                          |  (4) model.deploy    |  tf_opt-cpu.2-16                    |
 |                                          | -------------------> +------------------+------------------+
 |                                          |                                         | creates
 |                                          |  (5) endpoint.predict  JSON over HTTPS  v
 |                                          | -------------------> +-------------------------------------+
 |                                          | <------------------- | Vertex AI Endpoint (new each deploy)|
 |                                          |   predictions        |  1 x n1-standard-2 node, 24/7 $$    |
 +------------------------------------------+                      +-------------------------------------+

PART B — ml-workflow

 your laptop
 +-------------------------------------------------------------+
 | container "cheese-app-workflow" (python 3.13, kfp 2.14.6,   |
 |  aiplatform 1.120.0)  volumes: ./ -> /app, ../../../secrets |
 |  -> /secrets, docker.sock, ../data-collector, ../data-proc. |
 | $ python cli.py --pipeline                                  |
 |   a) @dsl.pipeline runs your function once -> DAG           |
 |   b) compiler.Compiler().compile -> pipeline.yaml (in ./)   |
 |   c) aip.PipelineJob(...).run(service_account=ml-workflow@) |------+ submit YAML
 +-------------------------------------------------------------+      |
                                                                      v
 Vertex AI Pipelines (Google-managed; every box = a container; identity = ml-workflow SA)
 pipeline_root = gs://$GCS_BUCKET_NAME/pipeline_root/root
  +-------------------------------------------+
  | Data Collector                            |  image dlops/cheese-app-data-collector (Docker Hub)
  |  cli.py --search --nums 50 ...            |  scrapes Bing ---------> gs://$GCS_BUCKET_NAME/raw.zip
  +--------------------+----------------------+
                       | .after()  (ordering only, no data edge)
  +--------------------v----------------------+
  | Data Processor                            |  image dlops/cheese-app-data-processor
  |  cli.py --clean                           |  raw.zip --difPy--> gs://$GCS_BUCKET_NAME/clean.zip
  +--------------------+----------------------+
                       | .after()
  +--------------------v----------------------+      launches     +------------------------------------+
  | Model Training (python:3.10 +             | ----------------> | Vertex AI Custom Training job      |
  |  pip google-cloud-aiplatform)             |  waits (see 6)    | tf-cpu.2-17.py310, n1-standard-4   |
  +--------------------+----------------------+                   | pip installs $GCS_PACKAGE_URI      |
                       |                                          |   /cheese-app-trainer.tar.gz       |
                       |                                          | downloads cheese_4_labels.zip from |
                       |                                          |   GitHub (NOT clean.zip!)          |
                       |                                          | writes SavedModel ->               |
                       |                                          |   gs://$GCS_BUCKET_NAME/model      |
                       | .after()                                 +------------------------------------+
  +--------------------v----------------------+
  | Model Deploy (python:3.10 + aiplatform)   |  Model.upload(gs://$GCS_BUCKET_NAME/model, tf2-cpu.2-12)
  |                                           |  -> Model Registry -> deploy -> NEW Endpoint (n1-standard-4)
  +-------------------------------------------+

 Local "test each stage by hand" containers, run before the pipeline:
  data-collector / data-processor / model-training images, each mounting
  ../../../secrets -> /secrets and ../../../persistent-folder -> /persistent
```

## 2. Prerequisites and costs

**Accounts and local installs**
- A GCP project with billing enabled. All code assumes region `us-central1`.
- Docker Desktop (or Docker Engine).
- `git`.
- No local Python is needed. Everything runs in containers.
- A Docker Hub account only if you rebuild and push the pipeline images yourself. That step is optional; `ml-workflow/README.md:131` says "This step has already been done for this tutorial".
- The W&B code is commented out (`model-deployment/cli.py:22-23` and `:65-77`). `WANDB_KEY` is passed into containers (`ml-workflow/src/workflow/docker-shell.sh:32`) but never read.

**GCP APIs**
- Both READMEs list only "Vertex AI API" (`model-deployment/README.md:14-16`, `ml-workflow/README.md:17-19`).
- The Cloud Storage API is normally on by default.

**Recommended folder layout**
Clone both repos side by side so they share one `secrets/` folder. The scripts compute the secrets path relative to the current directory:

```
AC215/                        <- e.g. ~/Desktop/AC215
  secrets/
     model-deployment.json    <- used by model-deployment/docker-shell.sh:21
     ml-workflow.json         <- used by data-collector, data-processor, workflow docker-shell.sh
     model-trainer.json       <- used by ml-workflow/src/model-training/docker-shell.sh:25 (!)
  persistent-folder/          <- mounted by data-collector/data-processor/model-training (create it yourself)
  model-deployment/           <- SECRETS_DIR=$(pwd)/../secrets/          (model-deployment/docker-shell.sh:7)
  ml-workflow/src/<stage>/    <- SECRETS_DIR=$(pwd)/../../../secrets/    (e.g. src/workflow/docker-shell.sh:7)
```

**Service accounts and keys**

| Key file (in `secrets/`) | Expected by | Roles from the README | Env var in container |
|---|---|---|---|
| `model-deployment.json` | `model-deployment/docker-shell.sh:21` | Storage Admin, AI Platform Admin, Vertex AI Administrator (`model-deployment/README.md:33`) | `GOOGLE_APPLICATION_CREDENTIALS=/secrets/model-deployment.json` |
| `ml-workflow.json` | `ml-workflow/src/data-collector/docker-shell.sh:24`, `ml-workflow/src/data-processor/docker-shell.sh:25`, `ml-workflow/src/workflow/docker-shell.sh:26` | Storage Admin, AI Platform Admin, Vertex AI Administrator, **Service Account User** (`ml-workflow/README.md:43`) | `GOOGLE_APPLICATION_CREDENTIALS=/secrets/ml-workflow.json` |
| `model-trainer.json` | `ml-workflow/src/model-training/docker-shell.sh:25` | from L13 (`model-training/README.md:62`) | `GOOGLE_APPLICATION_CREDENTIALS=/secrets/model-trainer.json` |

The ml-workflow README never mentions `model-trainer.json`. Either keep your L13 key, or copy `ml-workflow.json` to `model-trainer.json`.

**Environment variables to edit before running**

Every `docker-shell.sh` hard-codes the instructors' project and bucket names. You **must** change them. Bucket names are globally unique, so you cannot reuse `cheese-app-*-demo`.

| File:lines | Variables |
|---|---|
| `model-deployment/docker-shell.sh:8-9` | `GCP_PROJECT`, `GCS_MODELS_BUCKET_NAME` |
| `ml-workflow/src/data-collector/docker-shell.sh:11-12` | `GCP_PROJECT`, `GCS_BUCKET_NAME` |
| `ml-workflow/src/data-processor/docker-shell.sh:11-12` | `GCP_PROJECT`, `GCS_BUCKET_NAME` |
| `ml-workflow/src/model-training/docker-shell.sh:9-12` | `GCP_PROJECT`, `GCS_BUCKET_NAME`, `GCP_REGION`, `GCS_PACKAGE_URI` |
| `ml-workflow/src/workflow/docker-shell.sh:8-12` | `GCP_PROJECT`, `GCS_BUCKET_NAME`, `GCS_SERVICE_ACCOUNT` (`ml-workflow@<your-project-id>.iam.gserviceaccount.com`), `GCP_REGION`, `GCS_PACKAGE_URI` |

Two values are hard-coded in Python, not in env vars:
- The prediction endpoint: `model-deployment/cli.py:157`.
- The Docker Hub images the pipeline pulls: `ml-workflow/src/workflow/cli.py:27-28`. Change these only if you push your own images.

**Buckets to create**
- `GCS_MODELS_BUCKET_NAME`, for Part A (`model-deployment/README.md:37-42`).
- `GCS_BUCKET_NAME`, for Part B (`ml-workflow/README.md:47-52`). It holds `raw.zip`, `clean.zip`, `model/` and `pipeline_root/`.
- The bucket named in **`GCS_PACKAGE_URI`** (default `gs://cheese-app-trainer-code`, `ml-workflow/src/workflow/docker-shell.sh:12`). **The README does not tell you to create it**, but the training step reads `${GCS_PACKAGE_URI}/cheese-app-trainer.tar.gz` (`ml-workflow/src/workflow/model.py:26`). It also serves as `staging_bucket` and `base_output_dir` (`ml-workflow/src/workflow/model.py:23`, `:45`). Note that the value already includes `gs://`. You can point it at the trainer bucket you created in L13 (`model-training/README.md:71`, `gs://cheese-app-trainer` in `model-training/docker-shell.sh:8`).

**What costs money, and how to stop it**

| Resource | Created by | How it bills | Shut down |
|---|---|---|---|
| Vertex AI Endpoint, Part A | `model-deployment/cli.py:141-149`. No `machine_type`, so the SDK default `n1-standard-2` is used (aiplatform 1.121.0 `models.py:89`, `:2103-2105`). `min_replica_count=1` | per node-hour, **24/7, even with zero traffic** | undeploy, then delete the endpoint (commands below) |
| Vertex AI Endpoint, Part B | `ml-workflow/src/workflow/model.py:95-103` (`machine_type="n1-standard-4"`). **Each pipeline run creates another endpoint** (`Model.deploy` makes a new one when `endpoint` is not given; aiplatform `models.py:6217-6221`) | per node-hour, 24/7 | same |
| Vertex AI Custom Training | pipeline training step (`ml-workflow/src/workflow/model.py:54-63`). Default `machine_type="n1-standard-4"`, `replica_count=1` (aiplatform `training_jobs.py:7773-7774`, `CustomPythonPackageTrainingJob.run`). The pipeline passes `epochs=15` (`ml-workflow/src/workflow/cli.py:238`) | per minute while the job runs | ends by itself; cancel stuck jobs in the console under Vertex AI → Training |
| Vertex AI Pipelines | each `PipelineJob.run` | a small per-run fee plus the compute for each step | ends by itself |
| GCS | buckets above | GB-month; small | `gsutil rm -r gs://<bucket>/...` |
| Model Registry entries | every `Model.upload` | storage of artifacts only | `gcloud ai models delete` |

Cleanup commands. These are standard gcloud commands, not in the READMEs. Run them in any container where the entrypoint authenticated gcloud: `model-deployment`, `workflow`, `model-training`.

```bash
gcloud ai endpoints list --region=us-central1
gcloud ai endpoints describe ENDPOINT_ID --region=us-central1        # shows deployedModels[].id
gcloud ai endpoints undeploy-model ENDPOINT_ID --region=us-central1 --deployed-model-id=DEPLOYED_MODEL_ID
gcloud ai endpoints delete ENDPOINT_ID --region=us-central1
gcloud ai models list --region=us-central1
gcloud ai models delete MODEL_ID --region=us-central1
```

From Python, `aiplatform.Endpoint("projects/.../endpoints/ID").delete(force=True)` undeploys everything and then deletes the endpoint (aiplatform `models.py:3490`).

**Quotas.** A new project may have low CPU quotas for custom training or for model serving in `us-central1`. A failed deploy or training job will name the quota. The L13 README (`model-training/README.md`, section "Setup GPU Quotas") shows where quotas live in the console.

## 3. Concepts this tutorial teaches

### 3.1 SavedModel plus a custom serving signature: put preprocessing inside the model
- **Explanation.** A Keras model expects a float tensor `[N,224,224,3]`. A web client has a JPEG file. `prepare()` builds a TF graph function, `serving_function(bytes_inputs)`, that does three things:
  - decodes each JPEG,
  - converts it to float32 in [0,1] and resizes it,
  - calls the model.

  It saves that function as the SavedModel's `serving_default` signature (`model-deployment/cli.py:94-122`). The exported artifact is therefore "JPEG bytes in, 4 probabilities out".
- **Mental model.** A SavedModel is a *program*: a graph plus weights plus named entry points (signatures). It is more than a bag of weights. The serving container only knows how to call a named signature.
- **Analogy.** A vending machine that accepts coins. You don't hand it a sandwich recipe; the coin-to-sandwich logic is inside the machine.
- **Misconception.** "Uploading the `.keras` file is enough." The prebuilt TF serving container needs a SavedModel directory. Without the custom signature, the client would have to send 224×224×3 float arrays as JSON, which is about 150k numbers per image, and would have to reproduce the exact preprocessing. That is training/serving skew waiting to happen.

### 3.2 Model Registry vs Endpoint vs DeployedModel, and traffic split
- **Explanation.** `aiplatform.Model.upload(...)` with `display_name`, `artifact_uri` and `serving_container_image_uri` (`model-deployment/cli.py:134-138`) creates a **registry entry**. It records *where the weights are* (a GCS URI) and *which container knows how to serve them*. No machine runs yet.

  `deployed_model.deploy(...)` (`model-deployment/cli.py:141-149`) does three things:
  - creates an **Endpoint**, with a stable resource name `projects/<number>/locations/us-central1/endpoints/<id>` (the HTTPS prediction URL is built from it),
  - provisions VMs that run the serving container with the model loaded (a **DeployedModel**),
  - sets `traffic_split={"0": 100}`. Key `"0"` means "the model being deployed in this call" (aiplatform `models.py:1271`).
- **Mental model.**
  - Model = a recipe card in a library.
  - Endpoint = a restaurant's address.
  - DeployedModel = a kitchen at that address cooking from the card.

  One address can have several kitchens with a percentage of customers routed to each. That is how canary releases work.
- **Misconception.** "Registering a model makes it callable." It doesn't; only deploy does. The reverse surprise also catches people: "deleting the model deletes the endpoint". It doesn't: Vertex refuses to delete a model that is still deployed. You must undeploy it and delete the endpoint first; until you do, the endpoint keeps billing.

### 3.3 The online prediction request format
- **Explanation.** The client builds `instances = [{"bytes_inputs": {"b64": b64str}}]` and calls `result = endpoint.predict(instances=instances)` (`model-deployment/cli.py:172-174`). Each element of `instances` is one example.
  - The key `bytes_inputs` must match the **name of the signature's input argument** (`model-deployment/cli.py:107-108`).
  - The `{"b64": ...}` wrapper is the TF Serving REST convention for binary data. The serving container base64-decodes it into a `DT_STRING` tensor before the signature runs.
  - The response's `predictions[0]` is the softmax vector for the first instance. The code takes the argmax (`model-deployment/cli.py:177-178`) and maps it to a label with a hard-coded dict (`model-deployment/cli.py:30-37`).
- **Analogy.** A customs form. The field names must match exactly, and a parcel marked "b64" is unpacked by the customs officer (the serving container) before it reaches the recipient (your signature).
- **Misconception.** "I can send the base64 string directly." Without the `{"b64": ...}` wrapper, the model receives the base64 *text* as bytes, and `decode_jpeg` fails. Another one: "predictions come back with label names." You get a list of floats; the label mapping is your responsibility.

### 3.4 Prebuilt containers: the runtime half of a model
- **Explanation.** Vertex never runs "a model". It runs a container image that loads the model. Two kinds appear here:
  - **Serving images**, chosen by URI: `us-docker.pkg.dev/vertex-ai-restricted/prediction/tf_opt-cpu.2-16:latest` (`model-deployment/cli.py:128-130`) and `us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-12:latest` (`ml-workflow/src/workflow/model.py:79-81`).
  - **Training images**, e.g. `us-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest` (`ml-workflow/src/workflow/model.py:25`).
- **Mental model.** The model artifact is a cartridge and the container is the console. The cartridge must be compatible with the console's TF version.
- **Misconception.** "Any TF serving image works with any TF model." TF guarantees that newer runtimes load older models. The reverse is not guaranteed. The pipeline trains with TF 2.17 and serves with a TF 2.12 image; see section 9.

### 3.5 KFP components: container components vs lightweight Python components
- **Explanation.** A **component** is one step: a containerised program with typed inputs and outputs.
  - A `@dsl.container_component` function returns a `dsl.ContainerSpec` with `image`, `command` and `args` (`ml-workflow/src/workflow/cli.py:39-52`). Vertex runs your own image with those args. `command=[]` means "use the image's ENTRYPOINT". The compiled YAML has no `command:` key (`ml-workflow/src/workflow/pipeline.yaml:56-62`).
  - `@dsl.component(` with `base_image="python:3.10", packages_to_install=["google-cloud-aiplatform"]` (`ml-workflow/src/workflow/model.py:5-7`) makes a **lightweight Python component**. KFP copies the *source text* of your function into the YAML, together with a shell preamble that pip-installs the packages and runs it (`ml-workflow/src/workflow/pipeline.yaml:82-116`). This is why `model.py` puts `import google.cloud.aiplatform as aip` *inside* the function (`ml-workflow/src/workflow/model.py:20`): only the function body travels.
- **Analogy.**
  - A container component is a sealed, pre-packed lunchbox.
  - A Python component is a recipe card plus a shopping list, and the step cooks it on arrival.
- **Misconception.** "A Python component can use module-level imports or globals from my `cli.py`." It can't. It runs in a fresh `python:3.10` container that only has its own function body.

### 3.6 The pipeline DSL: tracing, edges, and compiling to YAML
- **Explanation.** `@dsl.pipeline` *calls your function once at decoration time*, with placeholder channels instead of real values (kfp 2.14.6 `dsl/graph_component.py:59-61`). Each component call inside it does not run anything; it records a **task** in a DAG.
- **Two kinds of edge.**
  - **Data edges** come from passing one task's `.output` into another (`ml-workflow/src/workflow/cli.py:294-297`). In the YAML they show up as `taskOutputParameter` (`ml-workflow/src/workflow/sample-pipeline1.yaml:176-193`).
  - **Ordering edges** come from `.after(task)` (`ml-workflow/src/workflow/cli.py:229`, `:244`, `:252`). They show up only as `dependentTasks` (`ml-workflow/src/workflow/pipeline.yaml:185-186`).
- **Compiling.** `compiler.Compiler().compile(...)` writes the DAG as a PipelineSpec YAML (`schemaVersion: 2.1.0`). Python values such as `GCS_BUCKET_NAME` are **baked in as constants** (`ml-workflow/src/workflow/pipeline.yaml:196-200`), so a compiled YAML is specific to one project and bucket.
- **Analogy.** Writing a play: you don't perform it, you write the script with stage directions ("enter after the processor exits"). The theatre company (Vertex) performs it later.
- **Misconception.** "`.after()` passes data." It only orders steps. In this repo all real data moves through GCS paths known by convention.

### 3.7 Submitting and running: PipelineJob, pipeline_root, service accounts, the launcher pattern
- **Explanation.** `job = aip.PipelineJob(...)` with `template_path="pipeline.yaml"`, `pipeline_root=PIPELINE_ROOT` and `enable_caching=False`, then `job.run(service_account=GCS_SERVICE_ACCOUNT)` (`ml-workflow/src/workflow/cli.py:263-270`). The SDK reads the local YAML, sends the spec inside the create request, creates a run, and (with the default `sync=True`) polls until the run finishes.
  - `pipeline_root` (`gs://<bucket>/pipeline_root/root`, `ml-workflow/src/workflow/cli.py:21`) is where KFP stores step outputs and metadata.
  - `enable_caching=False` overrides the `enableCache: true` written in the YAML.
  - The run executes **as** the `ml-workflow` service account. Your key's identity therefore needs `iam.serviceAccounts.actAs` on that account, which is why the README adds "Service Account User".
- **The launcher pattern.** The "Model Training" step does not train. It is a tiny Python container that calls `aip.CustomPythonPackageTrainingJob(...).run(...)` (`ml-workflow/src/workflow/model.py:28-63`), which starts a *second* Vertex job on another machine.
- **GCS as the shared blackboard.** Every step is a fresh container with an empty disk, so the bucket is the only shared state.
- **Analogy.** A conductor (the pipeline) cues sections, and the training section phones out to a hired soloist (Custom Training). Nobody passes sheet music by hand; it is all pinned to a shared noticeboard (GCS).
- **Misconception.** "The pipeline runs on my laptop / my container must stay open." Only submission happens locally; the run lives in Vertex. (`run()` blocks your terminal by default, but you can close it after submission.)

### 3.8 Two identities: key files locally, attached service accounts in the cloud
- **Explanation.**
  - **Locally**, each container gets a JSON key through `GOOGLE_APPLICATION_CREDENTIALS`, and the entrypoint also runs `gcloud auth activate-service-account` (`model-deployment/docker-entrypoint.sh:7`).
  - **Inside Vertex Pipelines**, the same `storage.Client()` call (`ml-workflow/src/data-collector/cli.py:29`) finds no key file. Application Default Credentials fall back to the pipeline's attached service account through the metadata server.
  - The nested training job runs without `service_account=` (`ml-workflow/src/workflow/model.py:54-63`). It therefore uses Vertex AI's default custom-training identity. That identity still has to write `gs://<bucket>/model`.
- **Misconception.** "I must bake my key into the pipeline image." Never do that. The cloud supplies credentials to the pipeline.

## 4. Step-by-step walkthrough

Conventions:
- `$` lines are run on your **host** in the folder given.
- `#` (container) lines are run in the shell that `docker-shell.sh` opens.
- Commands in quotes are copied verbatim from the README. Commands marked *(not in README)* are extra checks of your work.

### Part A — model-deployment

**A1. Enable the API, create the key and the bucket.** (`model-deployment/README.md:14-42`)
- Enable "Vertex AI API".
- Create the service account `model-deployment` with Storage Admin, AI Platform Admin and Vertex AI Administrator.
- Create a JSON key, rename it `model-deployment.json`, and put it in `../secrets/`.
- Create your models bucket.
- **Checkpoint:** `ls ../secrets/model-deployment.json` from inside `model-deployment/` succeeds.
- **If it fails:** the folder must be a *sibling* of the repo (`model-deployment/docker-shell.sh:7` uses `$(pwd)/../secrets/`).

**A2. Edit `docker-shell.sh`.**
- Set `GCP_PROJECT` (your project **ID**) and `GCS_MODELS_BUCKET_NAME` (`model-deployment/docker-shell.sh:8-9`).
- **Platform.** Line 15 forces `--platform=linux/arm64/v8`. That is right for Apple-Silicon Macs. On an Intel/AMD machine, comment out line 15 and uncomment line 13 (`#docker build -t $IMAGE_NAME -f Dockerfile .`). Otherwise every `RUN` step needs QEMU emulation, which is very slow, or fails with `exec format error` on Linux without binfmt.

**A3. Start the container.** "Run `sh docker-shell.sh`" (`model-deployment/README.md:51`).
- **Under the hood:**
  - `docker build` uses `Dockerfile`: python:3.11 slim; gcloud SDK and docker-ce from apt (`model-deployment/Dockerfile:17-37`); `uv sync --frozen` into `/.venv` (`model-deployment/Dockerfile:15`, `:58`).
  - `docker run --rm -ti` mounts the repo on `/app` and `../secrets` on `/secrets`, and passes three env vars (`model-deployment/docker-shell.sh:18-24`). No `-p` port mapping, because nothing listens locally.
  - The entrypoint activates gcloud with the key, sets the project, activates the venv and `exec`s bash (`model-deployment/docker-entrypoint.sh:7-20`).
- **You should see:** `Container is running!!!`, `Architecture: aarch64` (line 15 forces arm64, so you see this even under emulation; `x86_64` only if you switched to line 13 on an Intel/AMD machine), then `Activated service account credentials for: [model-deployment@<project>.iam.gserviceaccount.com]`, `Updated property [core/project].`, and the Python/uv versions.
- **If it fails:**
  - `ERROR: (gcloud.auth.activate-service-account) Could not read json file /secrets/model-deployment.json` → the key name or location is wrong.
  - The build takes forever → see the platform note in A2.

**A4. Prepare the model.** "Run `python cli.py --prepare`" (`model-deployment/README.md:58`).
- **Under the hood** (`model-deployment/cli.py:61-122`):
  1. `storage_client.get_bucket(GCS_MODELS_BUCKET_NAME)` checks that the bucket exists (`:62-63`).
  2. It downloads `https://github.com/dlops-io/models/releases/download/v3.0/mobilenetv2_train_base_True.zip` (about 18 MB) into `./artifacts/` and unzips it (`:80-84`). `./artifacts` is git-ignored (`model-deployment/.gitignore:5`). The zip also contains `data_details.json` with the same label map that `model-deployment/cli.py:30-37` hard-codes (asset contents verified on 2026-10-12).
  3. It loads the `.keras` model (`:90`).
  4. It builds `serving_function` (`:94-115`).
  5. It saves the SavedModel straight to `gs://<bucket>/model-mobilenetv2_train_base_True.v1` (`:27-28`, `:118-122`). Writing to `gs://` from TF works through `tensorflow-io-gcs-filesystem 0.37.1`, which the lock file only installs for Python < 3.12 (`model-deployment/uv.lock:1257`). The image uses 3.11 (`model-deployment/Dockerfile:2`).
- **You should see:** `Prepare model and save model to GCS Bucket`, TF warnings (deprecated `dtype`/`back_prop` in `tf.map_fn`), and possibly an `INFO:tensorflow:Assets written to: gs://...` line, depending on TF's log level. The reliable check is the listing below.
- **Check** *(not in README)*:
  - `gsutil ls gs://<bucket>/model-mobilenetv2_train_base_True.v1/` should list `saved_model.pb` and `variables/`, among others.
  - `saved_model_cli show --dir gs://<bucket>/model-mobilenetv2_train_base_True.v1 --tag_set serve --signature_def serving_default` should show an input `bytes_inputs` of dtype `DT_STRING` with shape `(-1)`.
- **If it fails:**
  - `404 ... bucket does not exist` → wrong bucket name in `model-deployment/docker-shell.sh:9`.
  - `403` → the bucket exists but is not yours (for example you left the instructors' `cheese-app-models-demo`), or the service account lacks Storage Admin.
  - `File system scheme 'gs' not implemented` → you changed the Python version to ≥3.12 (see section 6).

**A5. Upload and deploy.** "Run `python cli.py --deploy`" (`model-deployment/README.md:63`). The README says "This will take a few minutes" (`:64`). Endpoint deploys commonly take 10–20 minutes; this was not timed during verification.
- **Under the hood** (`model-deployment/cli.py:125-150`):
  - `cli.py` never calls `aiplatform.init()`. The SDK therefore takes the project from `google.auth.default()`, i.e. the `project_id` inside your key file, and the region from its default `us-central1` (aiplatform `initializer.py:352-388`). `GCP_PROJECT` is only used by `storage.Client` and `gcloud`.
  - `aiplatform.Model.upload(...)` registers the model with serving image `tf_opt-cpu.2-16`. It runs synchronously.
  - `deployed_model.deploy(..., sync=False)` creates a **new** endpoint named `<display_name>_endpoint` (aiplatform `models.py:6217-6221`) and deploys to it. No `machine_type` is given, so the SDK uses `n1-standard-2`.
  - Because `sync=False`, `print("endpoint:", endpoint)` runs *before* the endpoint exists. The Python process then stays alive until the background thread finishes: the SDK's `concurrent.futures` pool is joined when the interpreter exits.
- **You should see** (SDK log lines, format from the aiplatform source):
  - `Creating Model` … `Model created. Resource name: projects/<NUM>/locations/us-central1/models/<ID>`
  - `deployed_model: <...Model object...>`
  - `endpoint: <...Endpoint object at 0x...> is waiting for upstream dependencies to complete.`
  - `Creating Endpoint` … `Endpoint created. Resource name: projects/<NUM>/locations/us-central1/endpoints/<ENDPOINT_ID>`
  - `Deploying model to Endpoint : projects/.../endpoints/<ENDPOINT_ID>` (aiplatform `models.py:6242`)
  - `Using default machine_type: n1-standard-2` (logged inside the deploy call, after the line above; `models.py:2103-2105`)
  - `Deploy Endpoint model backing LRO: ...`
  - finally `Endpoint model deployed. Resource name: ...` (`models.py:6281`)

  **Copy the endpoint resource name.** The README's example is `projects/129349313346/locations/us-central1/endpoints/5072058134046965760` (`model-deployment/README.md:65`). Yours will use *your project number*, not your project ID.
- **If it fails:**
  - `403 ... aiplatform.models.upload` → missing Vertex AI role.
  - Quota errors → request CPU serving quota in `us-central1`.
  - Deploy fails with a model-load error in Cloud Logging → see section 9 about TF versions.

**A6. Predict.**
- "Update the endpoint uri in `cli.py`" (`model-deployment/README.md:69`): replace the string at `model-deployment/cli.py:157`.
- Then "Run `python cli.py --predict`" (`model-deployment/README.md:70`).
- **Under the hood** (`model-deployment/cli.py:153-184`):
  - `glob("data/*.jpg")` finds 7 of the 8 test images. `data/gouda-2.jpeg` is skipped because of the extension.
  - `np.random.randint(0, high=len(image_files) - 1, size=5)` picks 5 indices with replacement. `high` is exclusive, so the last file in the list is never picked.
  - For each picked file it base64-encodes the bytes, sends `instances = [{"bytes_inputs": {"b64": b64str}}]`, and prints the softmax, the argmax and the label.
- **You should see:** `Predict using endpoint`, then `image_files: [...]` listing up to five of the `data/*.jpg` paths (glob order is arbitrary), and five blocks of `Image:`, `Result: Prediction(predictions=[[p0, p1, p2, p3]], deployed_model_id='...', ...)`, `[p0, p1, p2, p3] k` and `Label:    <cheese>`.
  - The README's sample output (`model-deployment/README.md:72-89`) is **stale**: it shows the old 3-class mushroom model (`oyster`, `amanita`, `crimini`).
  - The model's own `model_metrics.json` reports accuracy ≈ 0.66, so expect some wrong labels.
- **If it fails:**
  - `403 Permission 'aiplatform.endpoints.predict' denied` (or `404 ... not found`) → you left the instructors' endpoint (project `129349313346`) in place, or pasted an endpoint ID you already deleted. Paste the exact resource name your `--deploy` printed.
  - `400 ... bytes_inputs` → the key name doesn't match the signature.

**A7. Clean up now** (section 2). Undeploy and delete the endpoint. Each extra `--deploy` creates another billed endpoint.

### Part B — ml-workflow

**B1. Credentials, buckets, folders.** (`ml-workflow/README.md:17-52`)
- "Vertex AI API" must be enabled (`ml-workflow/README.md:17-19`); it already is if you did Part A in the same project.
- Create the service account `ml-workflow` with Storage Admin, AI Platform Admin, Vertex AI Administrator and Service Account User. Put the key at `secrets/ml-workflow.json`.
- Create `GCS_BUCKET_NAME` **and** the `GCS_PACKAGE_URI` bucket (the README omits the second; reusing your L13 trainer bucket works).
- Create `persistent-folder/` next to `secrets/` yourself, so it is owned by your user (see section 6).
- Edit every `docker-shell.sh` (table in section 2).

**B2. Data collector, locally.**
- In `ml-workflow/src/data-collector`: "Make sure you are inside the `src/data-collector` folder and open a terminal at this location", then "Run `sh docker-shell.sh`" (`ml-workflow/README.md:82-83`).
- Then "Run `python cli.py --search --nums 10 --query "brie cheese" "gouda cheese" "gruyere cheese" "parmigiano cheese"`" (`ml-workflow/README.md:87`).
- **Under the hood:**
  - The image is python:3.12-slim, user `app`, built with `--platform=linux/amd64` (`ml-workflow/src/data-collector/docker-shell.sh:17`).
  - With no args, the entrypoint opens bash (`ml-workflow/src/data-collector/docker-entrypoint.sh:16-19`).
  - `cli.py` replaces `+` with spaces (`ml-workflow/src/data-collector/cli.py:42`) and scrapes Bing's `images/async` endpoint with a regex (`ml-workflow/src/data-collector/downloader.py:113-131`). It writes `/persistent/dataset/raw/<query>/Image_N.<ext>`, zips the folder into `raw.zip` and uploads it to the bucket root (`ml-workflow/src/data-collector/cli.py:55-66`).
- **You should see:** `[%] Downloading Image #1 from ...`, `[%] Done. Downloaded 10 images.` once per query, then `uploading file /persistent/dataset/raw.zip`.
- **Check:** "check your GCS bucket to see if `raw.zip` was uploaded" (`ml-workflow/README.md:88`).
- **If it fails:**
  - `PermissionError: [Errno 13] ... '/persistent/dataset'` → Docker created `persistent-folder` as root (Linux). Create it yourself, or `chmod 777` it.
  - `Indexed 0 Images` in a loop → Bing changed its HTML. The loop stops only when Bing returns an empty page, so it may spin.

**B3. Data processor, locally.**
- From `ml-workflow/src/data-processor`, "Run `sh docker-shell.sh`" (`ml-workflow/README.md:100-101`), then "Run `python cli.py --clean`" (`ml-workflow/README.md:105`).
- **Under the hood** (`ml-workflow/src/data-processor/cli.py:42-75`):
  - If `/persistent/dataset/raw` already exists, it **reuses the local folder** that the collector left in the shared `persistent-folder`. Otherwise it downloads `raw.zip`.
  - `cleanser.remove_duplicates` copies raw → clean and runs difPy per label (`ml-workflow/src/data-processor/cleanser.py:7-32`).
  - `verify_images` deletes any file `tf.image.decode_jpeg` cannot decode (`ml-workflow/src/data-processor/cleanser.py:35-51`).
  - It then zips and uploads `clean.zip`.
- **Checkpoint:** "check your GCS bucket to see if `clean.zip` was uploaded" (`ml-workflow/README.md:106`).
- **Do not run `--prepare`.** The import is commented out (`ml-workflow/src/data-processor/cli.py:19`), so `tfrecords` is undefined at `ml-workflow/src/data-processor/cli.py:93`, and scikit-learn (imported at `ml-workflow/src/data-processor/tfrecords.py:6`) is not in `pyproject.toml`.

**B4. Package the trainer** ("We did this previous lecture", `ml-workflow/README.md:112`).
- From `ml-workflow/src/model-training`, "Run `sh docker-shell.sh`" (`ml-workflow/README.md:117`).
  - This container expects `/secrets/model-trainer.json` (`ml-workflow/src/model-training/docker-shell.sh:25`).
  - It builds for `--platform=linux/arm64` (`:18`); change that on Intel/AMD.
- Then "Run `sh package-trainer.sh`" (`ml-workflow/README.md:122`). It tars `package/`, gzips it and runs `gsutil cp trainer.tar.gz $GCS_PACKAGE_URI/cheese-app-trainer.tar.gz` (`ml-workflow/src/model-training/package-trainer.sh:1-4`).
- **This upload is a hard prerequisite for the pipeline's training step** (`ml-workflow/src/workflow/model.py:26`).
- The optional "Run `python cli.py --train`" (`ml-workflow/README.md:123`) launches a standalone job with `tf-cpu.2-14.py310`, 2 epochs (`ml-workflow/src/model-training/cli.py:38`, `:49`).
- **Checkpoint** *(not in README)*: `gsutil ls $GCS_PACKAGE_URI` shows `cheese-app-trainer.tar.gz`.

**B5. (Optional) Build and push the step images** (`ml-workflow/README.md:130-138`).
- Already done: `dlops/cheese-app-data-collector` and `dlops/cheese-app-data-processor` exist on Docker Hub as multi-arch `latest` (amd64 + arm64), last pushed 2025-10-23 (Docker Hub API, checked on 2026-10-12).
- The README's own steps (`ml-workflow/README.md:134-138`): create a Docker Hub access token, "Login to the Hub: `docker login -u <USER NAME> -p <ACCESS TOKEN>`", "`docker build -t <USER NAME>/<IMAGE_NAME> -f Dockerfile .`" (on M1/M2 Macs "`docker build -t <USER NAME>/<IMAGE_NAME> --platform=linux/amd64/v2 -f Dockerfile .`"), then "`docker push <USER NAME>/<IMAGE_NAME>`". Run them inside `src/data-collector` and `src/data-processor`.
- The repo's alternative is `docker-shell-push.sh` (`ml-workflow/src/data-collector/docker-shell-push.sh:25-33`, `docker buildx ... --platform linux/amd64,linux/arm64 --push`); it also needs `docker login` first. Change `DOCKER_USERNAME` (`:10`) and the image names in `ml-workflow/src/workflow/cli.py:27-28`. Vertex runs **amd64**.

**B6. The workflow container.**
- From `ml-workflow/src/workflow`, "Run `sh docker-shell.sh`" (`ml-workflow/README.md:152-153`).
- **Under the hood:**
  - python:3.13, kfp 2.14.6, aiplatform 1.120.0 (`ml-workflow/src/workflow/pyproject.toml:6-10`, `uv.lock`), built for `--platform=linux/amd64` (`ml-workflow/src/workflow/docker-shell.sh:16`).
  - Mounts the Docker socket and the sibling stage folders (`ml-workflow/src/workflow/docker-shell.sh:21-25`). Neither is used in this lecture; the same mounts reappear in `cheese-app-v4/.github/workflows/ml-ci-cd-gcp.yml` (L23).
  - Note `# set -e` is commented out (`:3`). If the build fails, the script still runs the *old* image.

**B7. One-step pipeline: data collector on Vertex.** "Run `python cli.py --data_collector`" (`ml-workflow/README.md:159`).
- **Under the hood** (`ml-workflow/src/workflow/cli.py:35-76`):
  - It defines a container component whose args include `"--nums 10"` and `"--query brie+cheese gouda+cheese ..."` as *single strings*. It wraps the component in a one-task pipeline, compiles it to `data_collector.yaml`, `aip.init`s and submits.
  - On Vertex, the container's entrypoint receives the args and *re-splits them on spaces* (`ml-workflow/src/data-collector/docker-entrypoint.sh:9`, `:21`). The `+` signs exist because spaces would break the query terms apart.
- **You should see:** `Creating PipelineJob`, `PipelineJob created. Resource name: projects/<NUM>/locations/us-central1/pipelineJobs/data-collector-pipeline-<timestamp>`, `View Pipeline Job:` plus a console URL, repeated `PipelineJob projects/.../pipelineJobs/... current state:` followed on the next line by `PipelineState.PIPELINE_STATE_RUNNING` (aiplatform `pipeline_jobs.py:766-790`), and finally `PipelineJob run completed. Resource name: ...`.
- **Next:** "Inspect `data_collector.yaml`" (`ml-workflow/README.md:160`) and open the console link (`ml-workflow/README.md:161`).
- **If it fails:**
  - `403 ... iam.serviceAccounts.actAs` → add Service Account User.
  - A step in `PIPELINE_STATE_FAILED` with `exec format error` → your custom image has no amd64 variant.

**B8. The full pipeline.** "Run `python cli.py --pipeline`" (`ml-workflow/README.md:170`).
- **Under the hood** (`ml-workflow/src/workflow/cli.py:182-270`):
  - Four tasks chained by `.after()`. The collector downloads 50 images per class with a 500m CPU / 2G memory limit (`:219-224`). Training runs with `epochs=15`, `train_base=False` (`:232-245`). Deploy runs last.
  - The definition compiles to `pipeline.yaml` and is submitted with display name `cheese-app-pipeline-<uuid>`. The job's resource ID is `ml-pipeline-<timestamp>`, built from `pipelineInfo.name` (`ml-workflow/src/workflow/pipeline.yaml:169`; aiplatform `pipeline_jobs.py:269-275`).
- **Next:** "Inspect `pipeline.yaml`" and open the Vertex AI Pipelines console (`ml-workflow/README.md:171-172`).
- **You should see:** the same log pattern as B7. The console graph matches the README's images (`ml-workflow/README.md:174-178`); those screenshots still show `dlops/mushroom-app-...` image names.
- **Duration:** the run lasts as long as the slowest pieces: scraping 200 images, a 15-epoch CPU training job, and an endpoint deploy. Plan for well over half an hour; the full pipeline was not run during verification.
- **Afterwards:**
  - a new model "Cheese App Model" in the Registry,
  - a new endpoint "Cheese App Model_endpoint",
  - `gs://<bucket>/{raw.zip,clean.zip,model/}`.

  **Delete the endpoint when you are done** (section 2).

**B9. Test individual components** (`ml-workflow/README.md:183-186`).
- `python cli.py --data_collector`, `python cli.py --data_processor` and `python cli.py --model_training` work as one-task pipelines.
  - `--model_training` submits with `sync=False` (`ml-workflow/src/workflow/cli.py:151`), but the process still waits at exit, as in A5.
- **`python cli.py --model_deploy` fails.** Inside `model_deploy_pipeline` the name `model_deploy` refers to the CLI function itself (`ml-workflow/src/workflow/cli.py:154`), not the component, which is imported as `model_deploy_job` (`ml-workflow/src/workflow/cli.py:15`). Calling it with `bucket_name=` at `ml-workflow/src/workflow/cli.py:160-162` raises `TypeError: model_deploy() got an unexpected keyword argument 'bucket_name'` when `@dsl.pipeline` traces the function.
  - The committed `model_deploy.yaml` is consistent with this: it is from the old mushroom era (`ml-workflow/src/workflow/model_deploy.yaml:4`, `:47`, `sdkVersion: kfp-2.3.0` at `:82`).
  - **Fix:** change line 160 to `model_deploy_job(`.

**B10. Sample pipeline.**
- Back in the workflow container (`ml-workflow/README.md:193-195`), "Run `python cli.py --sample`" (`ml-workflow/README.md:199`).
- **Under the hood** (`ml-workflow/src/workflow/cli.py:273-314`): three Python components, `square`, `add` and `square_root`. `sample_pipeline(a=3.0, b=4.0)` computes √(a²+b²) = 5.0, passing outputs as data edges.
  - The components set no `base_image`, so kfp 2.14.6 prints a `FutureWarning` and uses `python:3.9` (kfp `dsl/component_factory.py:40`, `:575-577`).
  - The committed `sample-pipeline1.yaml` says `python:3.7` / `kfp-2.3.0` (`ml-workflow/src/workflow/sample-pipeline1.yaml:80`, `:248`) because it was compiled long ago. Your run will overwrite it.
- **You should see:** 4 tasks in the console. `square` and `square-2` run in parallel, then `add`, then `square-root`. The pipeline output parameter is `5.0`.

## 5. Code tour

```
model-deployment/
  Dockerfile              python:3.11 + gcloud + docker-ce + uv sync (runs as root; no USER line)
  docker-shell.sh         build (arm64!) + run with secrets mount and 3 env vars
  docker-entrypoint.sh    gcloud auth with key, activate /.venv, exec bash
  pyproject.toml/uv.lock  google-cloud-aiplatform 1.121.0, tensorflow 2.17.0, requests
  cli.py                  --prepare (signature + save to GCS), --deploy (upload + deploy), --predict
  data/*.jpg|.jpeg        8 sample cheese photos for --predict

ml-workflow/src/
  data-collector/         Bing scraper -> raw.zip in GCS     (image dlops/cheese-app-data-collector)
    cli.py, downloader.py, Dockerfile (USER app, /persistent), docker-entrypoint.sh (re-splits args)
    docker-shell.sh (local test), docker-shell-push.sh (multi-arch push)
  data-processor/         difPy dedupe + JPEG check -> clean.zip (image dlops/cheese-app-data-processor)
    cli.py, cleanser.py, tfrecords.py (unused), Pipfile* (stale), pyproject.toml (TF 2.19)
  model-training/         L13 trainer, adapted
    package/trainer/task.py   trains MobileNetV2, adds JPEG-bytes signature, saves gs://<bucket>/model
    package-trainer.sh        tar+gzip package/ and gsutil cp to $GCS_PACKAGE_URI
    cli.py                    standalone CustomPythonPackageTrainingJob (tf-cpu.2-14)
  workflow/               the orchestrator
    cli.py                    KFP pipelines: --data_collector/--data_processor/--model_training/
                              --model_deploy/--pipeline/--sample ; compile + PipelineJob.run
    model.py                  two lightweight Python components: model_training, model_deploy
    *.yaml                    compiled PipelineSpecs (regenerated on each run; some are stale)
```

**1. The serving function: JPEG bytes in, model input out**

`model-deployment/cli.py:100-111`
```python
    @tf.function(input_signature=[tf.TensorSpec([None], tf.string)])
    def preprocess_function(bytes_inputs):
        decoded_images = tf.map_fn(
            preprocess_image, bytes_inputs, dtype=tf.float32, back_prop=False
        )
        return {"model_input": decoded_images}

    @tf.function(input_signature=[tf.TensorSpec([None], tf.string)])
    def serving_function(bytes_inputs):
        images = preprocess_function(bytes_inputs)
        results = model_call(**images)
        return results
```

- `input_signature=[tf.TensorSpec([None], tf.string)]` fixes the input: a 1-D batch of strings of any length. Each string is one JPEG file's bytes.
- `tf.map_fn(preprocess_image, ...)` applies the per-image decode/convert/resize from `model-deployment/cli.py:94-98` to every string. `dtype=tf.float32` declares the output type; this argument is deprecated, and `fn_output_signature` is the modern name.
- The returned dict key `"model_input"` is matched to the keyword argument of the concrete function `model_call` (next excerpt).
- `serving_function`'s parameter name `bytes_inputs` becomes the **public input name** that clients must use in the JSON.

**2. Bind the model and save with the new signature**

`model-deployment/cli.py:113-122`
```python
    model_call = tf.function(prediction_model.call).get_concrete_function(
        [tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32, name="model_input")]
    )

    # Save updated model to GCS
    tf.saved_model.save(
        prediction_model,
        ARTIFACT_URI,
        signatures={"serving_default": serving_function},
    )
```

- `tf.function(prediction_model.call).get_concrete_function(...)` traces the Keras model's forward pass for a fixed input spec named `model_input`. This is the graph that `serving_function` calls.
- `tf.saved_model.save(` with `signatures={"serving_default": serving_function},` writes the SavedModel directly to `gs://` (`ARTIFACT_URI` is built at `model-deployment/cli.py:28`). `serving_default` is the signature the TF serving container calls by default.
- The same pattern is copied into the pipeline trainer at `ml-workflow/src/model-training/package/trainer/task.py:351-383`, with the destination `gs://{args.bucket_name}/model` (`:376`).

**3. Register, then deploy**

`model-deployment/cli.py:134-149`
```python
    deployed_model = aiplatform.Model.upload(
        display_name=BEST_MODEL,
        artifact_uri=ARTIFACT_URI,
        serving_container_image_uri=serving_container_image_uri,
    )
    print("deployed_model:", deployed_model)
    # Reference: https://cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform.Model#google_cloud_aiplatform_Model_deploy
    endpoint = deployed_model.deploy(
        deployed_model_display_name=BEST_MODEL,
        traffic_split={"0": 100},
        # machine_type="n1-standard-4",
        accelerator_count=0,
        min_replica_count=1,
        max_replica_count=1,
        sync=False,
    )
```

- `Model.upload` creates the registry entry. `artifact_uri` is the GCS folder; `serving_container_image_uri` (`model-deployment/cli.py:128-130`) is the runtime.
- `deploy(...)` with no `endpoint=` creates a new endpoint every time.
- `traffic_split={"0": 100}`: "0" stands for this new deployment, which gets 100% of traffic.
- `machine_type` is commented out, so the SDK picks `n1-standard-2`. `min_replica_count=1` and `max_replica_count=1` mean one always-on node, with no autoscaling and no scale-to-zero.
- `sync=False` returns at once with a placeholder `Endpoint`, which is why the following `print` shows "waiting for upstream dependencies".

**4. The prediction request**

`model-deployment/cli.py:168-178`
```python
        with open(image_files[img_idx], "rb") as f:
            data = f.read()
        b64str = base64.b64encode(data).decode("utf-8")
        # The format of each instance should conform to the deployed model's prediction input schema.
        instances = [{"bytes_inputs": {"b64": b64str}}]

        result = endpoint.predict(instances=instances)

        print("Result:", result)
        prediction = result.predictions[0]
        prediction_index = prediction.index(max(prediction))
```

- The raw bytes are base64-encoded into text, because JSON cannot carry binary.
- `{"bytes_inputs": {"b64": ...}}` has two parts: the outer key is the signature input name, and the inner `b64` tells the serving container to decode before calling the graph.
- `result.predictions[0]` is the 4-way softmax for the single instance. `prediction.index(max(prediction))` is a pure-Python argmax, and the label comes from the hard-coded `data_details["index2label"]` (`model-deployment/cli.py:36`).

**5. How the pipeline's args reach `cli.py` inside the step image**

`ml-workflow/src/data-collector/docker-entrypoint.sh:9-22`
```bash
args="$@"
echo $args

# Activate virtual environment
echo "Activating virtual environment..."
source /.venv/bin/activate

if [[ -z ${args} ]]; 
then
    # Keep a shell open
    exec /bin/bash
else
  uv run python $args
fi
```

- `args="$@"` joins all container args into **one string**.
- With no args (a local `docker run` from `docker-shell.sh`), you get an interactive shell. With args (on Vertex), it runs `uv run python $args`.
- `$args` is unquoted, so bash **word-splits** it again. That turns `"--nums 10"` into `--nums` and `10`, and `"--query brie+cheese gouda+cheese ..."` into one flag followed by four terms. This is why the pipeline writes multi-word queries with `+` (decoded at `ml-workflow/src/data-collector/cli.py:42`).

**6. A container component**

`ml-workflow/src/workflow/cli.py:39-52`
```python
    @dsl.container_component
    def data_collector():
        container_spec = dsl.ContainerSpec(
            image=DATA_COLLECTOR_IMAGE,
            command=[],
            args=[
                "cli.py",
                "--search",
                "--nums 10",
                "--query brie+cheese gouda+cheese gruyere+cheese parmigiano+cheese",
                f"--bucket {GCS_BUCKET_NAME}",
            ],
        )
        return container_spec
```

- `@dsl.container_component` turns a function that returns a `ContainerSpec` into a component.
- `command=[]` keeps the image ENTRYPOINT (`/bin/bash docker-entrypoint.sh`, `ml-workflow/src/data-collector/Dockerfile:53`), and `args` are appended to it.
- The f-string evaluates `GCS_BUCKET_NAME` **at compile time on your laptop**, so the value is frozen into the YAML (`ml-workflow/src/workflow/data_collector.yaml:15`).

**7. Wiring the DAG**

`ml-workflow/src/workflow/cli.py:216-230`
```python
    @dsl.pipeline
    def ml_pipeline():
        # Data Collector
        data_collector_task = (
            data_collector()
            .set_display_name("Data Collector")
            .set_cpu_limit("500m")
            .set_memory_limit("2G")
        )
        # Data Processor
        data_processor_task = (
            data_processor()
            .set_display_name("Data Processor")
            .after(data_collector_task)
        )
```

- Calling `data_collector()` inside a `@dsl.pipeline` function creates a `PipelineTask`; nothing runs yet.
- `.set_display_name`, `.set_cpu_limit("500m")` and `.set_memory_limit("2G")` are chained setters. The limits compile to `resources:` in `ml-workflow/src/workflow/pipeline.yaml:63-67`.
- `.after(data_collector_task)` adds an ordering-only edge (`dependentTasks` at `ml-workflow/src/workflow/pipeline.yaml:185-186`). No outputs are passed. Lines 231-253 do the same for training and deploy.

**8. Compile and submit**

`ml-workflow/src/workflow/cli.py:256-270`
```python
    compiler.Compiler().compile(ml_pipeline, package_path="pipeline.yaml")

    # Submit job to Vertex AI
    aip.init(project=GCP_PROJECT, staging_bucket=BUCKET_URI)

    job_id = generate_uuid()
    DISPLAY_NAME = "cheese-app-pipeline-" + job_id
    job = aip.PipelineJob(
        display_name=DISPLAY_NAME,
        template_path="pipeline.yaml",
        pipeline_root=PIPELINE_ROOT,
        enable_caching=False,
    )

    job.run(service_account=GCS_SERVICE_ACCOUNT)
```

- `compile(ml_pipeline, package_path="pipeline.yaml")` writes the PipelineSpec into `/app`, which is your host folder through the volume mount.
- `aip.init(project=..., staging_bucket=...)` sets SDK defaults. No `location` is passed, so it uses the SDK default `us-central1`; `GCP_REGION` is not used here.
- `generate_uuid()` (`ml-workflow/src/workflow/cli.py:31-32`) makes display names unique.
- `pipeline_root` decides where KFP writes step metadata and outputs.
- `enable_caching=False` forces every step to re-run, even with identical inputs.
- `job.run(service_account=...)` submits and blocks until the run finishes. The steps run as `ml-workflow@...`.

**9. A lightweight Python component that launches another Vertex job**

`ml-workflow/src/workflow/model.py:20-34`
```python
    import google.cloud.aiplatform as aip

    # Initialize Vertex AI SDK for Python
    aip.init(project=project, location=location, staging_bucket=staging_bucket)

    container_uri = "us-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310:latest"
    python_package_gcs_uri = f"{staging_bucket}/cheese-app-trainer.tar.gz"

    job = aip.CustomPythonPackageTrainingJob(
        display_name="cheese-app-training",
        python_package_gcs_uri=python_package_gcs_uri,
        python_module_name="trainer.task",
        container_uri=container_uri,
        project=project,
    )
```

- The import is inside the function because only the function body is shipped to the step container (`ml-workflow/src/workflow/pipeline.yaml:144-166` shows the copied source).
- `aip.init(... staging_bucket=staging_bucket)` uses the `GCS_PACKAGE_URI` bucket.
- `container_uri` is Google's prebuilt TF 2.17 CPU training image.
- `python_package_gcs_uri` points to the tarball made by `package-trainer.sh`, and `python_module_name="trainer.task"` names the module Vertex runs after pip-installing the tarball (in effect `python -m trainer.task` plus the args).
- The run itself is at `ml-workflow/src/workflow/model.py:54-63`. It passes `args=CMDARGS,` (line 56), `base_output_dir=MODEL_DIR,` (line 61) and `sync=False,` (line 62). `# replica_count=1,` and `# machine_type=TRAIN_COMPUTE,` are commented out (lines 57-58), so the SDK defaults apply (`n1-standard-4`, one replica).

**10. The deploy component**

`ml-workflow/src/workflow/model.py:88-103`
```python
    deployed_model = aip.Model.upload(
        display_name=display_name,
        artifact_uri=ARTIFACT_URI,
        serving_container_image_uri=serving_container_image_uri,
    )
    print("deployed_model:", deployed_model)
    # Reference: https://cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform.Model#google_cloud_aiplatform_Model_deploy
    endpoint = deployed_model.deploy(
        deployed_model_display_name=display_name,
        traffic_split={"0": 100},
        machine_type="n1-standard-4",
        accelerator_count=0,
        min_replica_count=1,
        max_replica_count=1,
        sync=True,
    )
```

- This is the same register/deploy pair as in Part A, but with three differences:
  - the artifact is `gs://{bucket_name}/model` (`ml-workflow/src/workflow/model.py:84`), i.e. whatever the training job wrote last;
  - the serving image is `tf2-cpu.2-12` (`ml-workflow/src/workflow/model.py:79-81`);
  - the endpoint uses `machine_type="n1-standard-4"`.
- `sync=True` makes the step wait for the deploy, so the step's success means the endpoint is live.

**11. What the compiler emits for a container step**

`ml-workflow/src/workflow/pipeline.yaml:54-67`
```yaml
    exec-data-collector:
      container:
        args:
        - cli.py
        - --search
        - --nums 50
        - --query brie+cheese gouda+cheese gruyere+cheese parmigiano+cheese
        - --bucket cheese-app-ml-workflow-demo
        image: dlops/cheese-app-data-collector
        resources:
          cpuLimit: 0.5
          memoryLimit: 2.0
          resourceCpuLimit: 500m
          resourceMemoryLimit: 2G
```

- This is the **contract Vertex executes**. Each list item becomes one argv element (hence the entrypoint re-splitting). There is no `command:` key, so the image ENTRYPOINT is used.
- `resourceCpuLimit: 500m` and `resourceMemoryLimit: 2G` come from the chained setters.
- `cheese-app-ml-workflow-demo` is the instructors' bucket, frozen in at compile time. Your compiled file will contain yours.

**12. Data edges in the sample pipeline**

`ml-workflow/src/workflow/cli.py:291-297`
```python
    # Define a Pipeline
    @dsl.pipeline
    def sample_pipeline(a: float = 3.0, b: float = 4.0) -> float:
        a_sq_task = square(x=a)
        b_sq_task = square(x=b)
        sum_task = add(x=a_sq_task.output, y=b_sq_task.output)
        return square_root(x=sum_task.output).output
```

- `a` and `b` are pipeline parameters with defaults.
- `a_sq_task.output` is a placeholder for a value that will exist only at run time. Passing it into `add(...)` creates a **data edge**: the compiler records `taskOutputParameter` and an implicit dependency (`ml-workflow/src/workflow/sample-pipeline1.yaml:176-193`).
- The pipeline's return value becomes its output parameter (`ml-workflow/src/workflow/sample-pipeline1.yaml:169-174`).

## 6. Gotchas and common errors

1. **Wrong CPU architecture in `docker build`.**
   - Symptom: very slow builds, or `exec format error` during `RUN`.
   - Cause: the scripts hard-code different platforms.
     - `model-deployment/docker-shell.sh:15`: `linux/arm64/v8`
     - `ml-workflow/src/model-training/docker-shell.sh:18`: `linux/arm64`
     - `ml-workflow/src/data-collector/docker-shell.sh:17` and `ml-workflow/src/workflow/docker-shell.sh:16`: `linux/amd64`
     - `ml-workflow/src/data-processor/docker-shell.sh:15`: native
   - Fix: on Apple Silicon, arm64 is native and amd64 is emulated (slow but works). On Intel/AMD, remove `--platform=linux/arm64...`.
2. **An image pushed from a Mac fails on Vertex.**
   - Symptom: a pipeline step fails immediately with `exec format error`.
   - Cause: Vertex runs amd64; a plain `docker build` on Apple Silicon makes arm64 only.
   - Fix: use `docker buildx ... --platform linux/amd64,linux/arm64 --push` as in `ml-workflow/src/data-collector/docker-shell-push.sh:29-33`, or the README's `--platform=linux/amd64/v2` (`ml-workflow/README.md:137`).
3. **Hard-coded instructor resources.**
   - Symptom: `403` on `cheese-app-*-demo` buckets you don't own, `403 permission denied on project ac215-project`, or `403`/`404` on the instructors' endpoint.
   - Cause: `ac215-project`, `cheese-app-*-demo`, `ml-workflow@ac215-project...` and the endpoint `projects/129349313346/.../6971931763471810560` are hard-coded (`model-deployment/docker-shell.sh:8-9`, `model-deployment/cli.py:157`, `ml-workflow/src/workflow/docker-shell.sh:8-12`).
   - Fix: replace them all. For the endpoint, paste the resource name `--deploy` printed; the SDK prints it with the project **number**.
4. **Missing trainer key.**
   - Symptom: in `ml-workflow/src/model-training`, `gcloud auth activate-service-account` complains that `/secrets/model-trainer.json` cannot be read, and then `gsutil cp` in `package-trainer.sh` fails.
   - Cause: `ml-workflow/src/model-training/docker-shell.sh:25` expects the L13 key name, while the README tells you to create `ml-workflow.json` (`ml-workflow/README.md:45`).
   - Fix: `cp secrets/ml-workflow.json secrets/model-trainer.json`, or edit line 25.
5. **Trainer tarball missing.**
   - Symptom: the pipeline's Model Training step fails, and the Vertex training job reports that it cannot find `gs://.../cheese-app-trainer.tar.gz`.
   - Cause: `package-trainer.sh` was never run against your `GCS_PACKAGE_URI`, or that bucket doesn't exist; the README omits creating it.
   - Fix: create the bucket and run B4.
6. **`persistent-folder` permission errors on Linux hosts.**
   - Symptom: `PermissionError` on `/persistent/dataset`.
   - Cause: the host folder `../../../persistent-folder/` (`ml-workflow/src/data-collector/docker-shell.sh:9`) is auto-created by Docker as root, while the container runs as `app` uid 1000 (`ml-workflow/src/data-collector/Dockerfile:31-40`).
   - Fix: `mkdir -p persistent-folder` as yourself before the first run, or `chmod 777` it.
7. **Stale local data hides bugs.**
   - Symptom: the processor works locally but fails in the pipeline (or the reverse).
   - Cause: locally, collector and processor share `persistent-folder`, and `ml-workflow/src/data-processor/cli.py:46` skips the download when `raw/` exists. On Vertex each step starts empty and *must* download `raw.zip`.
   - Fix: test with an empty `persistent-folder` before trusting the pipeline.
8. **`--model_deploy` crashes at compile time.**
   - Symptom: `TypeError: model_deploy() got an unexpected keyword argument 'bucket_name'`.
   - Cause: name shadowing at `ml-workflow/src/workflow/cli.py:154` vs `:160`.
   - Fix: call `model_deploy_job(bucket_name=GCS_BUCKET_NAME)`.
9. **`--prepare` in data-processor crashes.**
   - Symptom: `NameError: name 'tfrecords' is not defined`; after uncommenting the import, `ModuleNotFoundError: No module named 'sklearn'`.
   - Cause: `ml-workflow/src/data-processor/cli.py:19` and `ml-workflow/src/data-processor/pyproject.toml:7-14`.
   - Fix: don't use it (the README removed it in commit `dd5253d`), or add `scikit-learn` and the import.
10. **Training-step failures can be hidden.**
    - Symptom: the pipeline shows Model Training succeeded, but Model Deploy fails because there is no SavedModel at `gs://.../model` yet, or silently deploys an **older** model left there by a previous run.
    - Cause: `job.run(..., sync=False)` (`ml-workflow/src/workflow/model.py:62`). In aiplatform's `optional_sync` (`base.py:809-941`) the job runs in a `concurrent.futures` thread. The component function returns at once, and its process still waits for the thread at interpreter exit (kfp's `executor_main.py` simply returns; nothing calls `os._exit`). But an exception in that thread is only stored by the `_complete_future` callback (`base.py:274-289`) and never re-raised, so the step exits 0. This comes from reading the SDK, not from running it.
    - Fix: `sync=True` in the component.
11. **Every deploy creates a new paid endpoint.**
    - Symptom: several endpoints in the console, and a growing bill.
    - Cause: `deploy()` without `endpoint=` (`model-deployment/cli.py:141`, `ml-workflow/src/workflow/model.py:95`).
    - Fix: delete old endpoints, or pass `endpoint=aiplatform.Endpoint(...)` to reuse one.
12. **Serving runtime older than the training runtime.**
    - Symptom (possible, not observed here): deploy hangs or fails, and the model server logs in Cloud Logging report an unknown op or attribute while loading the SavedModel.
    - Cause: the model is trained by TF 2.17 (`ml-workflow/src/workflow/model.py:25`) but served by `tf2-cpu.2-12` (`ml-workflow/src/workflow/model.py:80`), five minor versions older. Part A also pairs a TF 2.17 save with an older image, `tf_opt-cpu.2-16` (`model-deployment/pyproject.toml:10`, `model-deployment/cli.py:129`), but that pairing has been in the repo since commit `7eeb93a` (2024-10-18) and the instructors' last commit `3fbf63f` is titled "Working endpoint", so it is reported to work.
    - Fix: choose a prebuilt serving image whose TF version is at least the training version.
13. **Python ≥ 3.12 breaks `gs://` saving in Part A.**
    - Symptom: `UnimplementedError: File system scheme 'gs' not implemented`.
    - Cause: `tensorflow-io-gcs-filesystem` is only locked for `python_full_version < '3.12'` (`model-deployment/uv.lock:1257`).
    - Fix: keep `FROM python:3.11-slim-bullseye` (`model-deployment/Dockerfile:2`). Its comment says "Python 3.13", which is wrong.
14. **`imghdr` and Python 3.13.**
    - `ml-workflow/src/data-collector/downloader.py:7` imports `imghdr`, which was removed in Python 3.13. The collector image pins 3.12 (`ml-workflow/src/data-collector/Dockerfile:2`). Don't "upgrade" it to 3.13 the way `ml-workflow/src/workflow/Dockerfile:2` is.
15. **Missing `actAs` permission.**
    - Symptom: `PipelineJob.run` fails with `403 ... iam.serviceAccounts.actAs`.
    - Cause: the key's account lacks Service Account User on the `GCS_SERVICE_ACCOUNT`.
    - Fix: add the role (`ml-workflow/README.md:43`).
16. **Stale image after a failed build.**
    - Symptom: you edited code but the workflow container behaves the old way.
    - Cause: `# set -e` is commented out in `ml-workflow/src/workflow/docker-shell.sh:3`, so a failed `docker build` still runs the previous image.
    - Fix: read the build output, or re-enable `set -e`.
17. **The README's expected output is from a different model.**
    - `model-deployment/README.md:72-89` shows mushroom labels and 3 probabilities. Cheese gives 4.
    - The `cli.py` docstring advertises `python cli.py --upload` (`model-deployment/cli.py:5`), but there is no such flag. Use `--prepare`.
    - `--test` is accepted but does nothing (`model-deployment/cli.py:222-226`).
18. **Label order is a hidden contract.**
    - Symptom: endpoint answers look systematically wrong when you send images to the *pipeline-trained* model using Part A's label map.
    - Cause: the trainer builds `label2index` from `os.listdir(base_path)` (`ml-workflow/src/model-training/package/trainer/task.py:113-119`), whose order depends on the filesystem. Part A hard-codes `{"0": "parmigiano", "1": "gruyere", "2": "brie", "3": "gouda"}` (`model-deployment/cli.py:36`).
    - Fix: sort the labels and save `data_details.json` next to the model. The v3.0 model zip does ship a `data_details.json`, but its order (parmigiano, gruyere, brie, gouda) is not alphabetical, so the sorting half is still missing.
19. **Unpinned runtime installs.**
    - `packages_to_install=["google-cloud-aiplatform"]` (`ml-workflow/src/workflow/model.py:6`, `:68`) installs whatever version is latest *at run time* inside `python:3.10`, so the same YAML can behave differently next month.
    - Fix: pin a version.
20. **Scraping is fragile.**
    - The Bing scraper depends on an undocumented endpoint and a regex (`ml-workflow/src/data-collector/downloader.py:113-131`). If Bing changes its HTML, `links` is empty, and `run()` keeps requesting pages until Bing returns an empty response.
    - Expect occasional empty or partial `raw.zip`.

## 7. Where this sits in the course

**What earlier lectures gave you**
- **L2–L4 (containers, mega-pipeline):** the *pattern* used here: several single-purpose containers that hand work to each other through a GCS bucket.
- **L10/L11:** service-account keys, the `secrets/` convention, and buckets.
- **L13 (`dlops-io/model-training`):**
  - serverless training on Vertex AI with `CustomPythonPackageTrainingJob`,
  - `package-trainer.sh`,
  - W&B tracking,
  - the cheese dataset `cheese_4_labels.zip` (`model-training/package/trainer/task.py:97`).
- **L14 (`serverless-deployment`):** serving your *own* container on Cloud Run / Cloud Functions.

**What L15 adds**
1. *Managed model serving*: Registry → Endpoint → online prediction with a prebuilt TF runtime and a custom signature. You don't write a web server.
2. *Orchestration*: the same stages, expressed as a KFP DAG, compiled to YAML and run by Vertex AI Pipelines under a service account.

**Concrete diff vs L13 (`model-training` → `ml-workflow/src/model-training`)**
- `cli.py`:
  - `GCS_BUCKET_URI` is split into `GCS_PACKAGE_URI` (code tarball) and `GCS_BUCKET_NAME` (data and model);
  - it now has argparse `--train`;
  - the image changes from `tf-gpu.2-14.py310` to `tf-cpu.2-14.py310`, and the GPU flags are commented out;
  - epochs drop from 15 to 2;
  - `--bucket_name` is passed.
- `task.py`:
  - W&B import, login, init and finish are commented out;
  - `--wandb_key` is replaced by `--bucket_name`;
  - **new**: the serving-signature block and `tf.saved_model.save` to `gs://{bucket_name}/model` (`ml-workflow/src/model-training/package/trainer/task.py:347-383`). This is how training hands its model to the deploy step.
- `docker-shell.sh` keeps the `model-trainer.json` key name from L13.

**Diff inside ml-workflow, `origin/pipenv` → `main`** (`git diff --stat origin/pipenv origin/main`: 42 files, +4304/−1374)
- Pipenv images (Ubuntu 20.04 for processor, training and workflow; `python:3.9-slim-buster` for the collector) became `uv` plus python-slim images in every stage, with `docker-shell-push.sh` (multi-arch) added for collector and processor.
- **Data path changed.** On `pipenv`, the trainer downloaded `tfrecords.zip` from the bucket. That file was produced by `data-processor --prepare`, which the pipeline ran then. On `main`:
  - `--prepare` is removed from the pipeline (commit `dd5253d`);
  - the trainer downloads the fixed GitHub dataset (`ml-workflow/src/model-training/package/trainer/task.py:103-107`).

  As a result, **the Data Collector and Data Processor steps no longer feed training**. The DAG still orders them first, but their outputs (`raw.zip`, `clean.zip`) are unused downstream.
- Training container moved from `tf-cpu.2-12` to `tf-cpu.2-17`; `sync=True` became `sync=False`; default epochs went from 15 to 3 (the full pipeline still passes 15).

**Diff inside model-deployment, `origin/pipenv` → `main`** (9 files, +1531/−3711)
- The image moved from Ubuntu 20.04 + Python 3.9 + Pipenv (`USER app`) to python:3.11-slim + uv (runs as root), in commit `f81735e` "migrated to uv".
- The serving image did **not** change: both branches use `vertex-ai-restricted/prediction/tf_opt-cpu.2-16` and `tensorflow==2.17.0`. The switch away from `vertex-ai/prediction/tf2-cpu.2-12` happened earlier, in commit `7eeb93a` "fixed cli for cheese data" (2024-10-18), which both branches contain.
- The endpoint ID was updated (in `f81735e`, and again in `3fbf63f` "Working endpoint").

**What comes next**
- **L16/L17** (system trade-offs; evaluating and monitoring) have no tutorial listed in `tutorials_demo.md`. The endpoint you deployed here is a concrete case for both: cost per always-on node, latency, logging.
- **L18 (cheese-app v1/v2)** builds the API and frontend. Note that `cheese-app-v2`'s API loads the `.keras` model locally (`cheese-app-v2/src/api-service/api/utils/llm_cnn_utils.py:110-137`) rather than calling a Vertex endpoint.
- **L23 (`cheese-app-v4`)** reuses this `src/workflow` folder with the same file layout. `cheese-app-v4/.github/workflows/ml-ci-cd-gcp.yml` builds the workflow container in GitHub Actions and runs `python cli.py --data_collector` and similar commands based on commit-message tags (`/run-data-collector`, `/run-ml-pipeline`, ...). Your L15 pipeline becomes the "CD for ML" target.
- **Milestones:** MS3 requires "At least one automated ML pipeline or workflow using Vertex AI Pipelines or equivalent" (`milestone3.md:55`). MS5 asks for retraining and deployment with "Validation checks to ensure only models meeting performance thresholds are deployed" (`milestone5.md:56`). This tutorial's pipeline has **no evaluation gate**, which is a natural extension for your project.

## 8. Exercises

**E1 (hands-on, predict then run).** In `ml-workflow/src/workflow/cli.py:293`, change the defaults to `a: float = 5.0, b: float = 12.0`. Predict the pipeline output, the number of tasks, and which tasks can run at the same time. Then run `python cli.py --sample`.
- *Answer:*
  - Output √(25+144) = **13.0**.
  - **4 tasks**: `square`, `square-2`, `add`, `square-root`. KFP auto-suffixes repeated component names, which is why the YAML has `square-2`.
  - `square` and `square-2` have no dependency on each other, so they can run in parallel. `add` waits for both, because it consumes both `.output`s.
  - The regenerated YAML will show `defaultValue: 5.0` and `12.0`. With kfp 2.14.6 it will also show `image: python:3.9`, not `python:3.7`.

**E2 (debugging).** `python cli.py --model_deploy` stops with `TypeError: model_deploy() got an unexpected keyword argument 'bucket_name'` before anything is submitted. Why, and why does it fail *before* compile?
- *Answer:*
  - In `ml-workflow/src/workflow/cli.py`, the component was imported as `model_deploy_job` (`:15`), and the same file defines its own zero-argument function `model_deploy()` (`:154`).
  - Inside `model_deploy_pipeline`, the call at `:160` resolves to the CLI function.
  - `@dsl.pipeline` executes the pipeline function immediately to trace it (kfp `graph_component.py:59-61`), so the error happens at decoration time, before `compiler.Compiler().compile`.
  - Fix: `model_deploy_job(bucket_name=GCS_BUCKET_NAME)`. Then regenerate the stale `model_deploy.yaml`.

**E3 (debugging, request format).** A classmate changes `model-deployment/cli.py:172` to `instances = [{"bytes_inputs": b64str}]` and gets a 400 error mentioning JPEG decoding. Explain.
- *Answer:*
  - Without the `{"b64": ...}` wrapper, the serving container passes the base64 **text** as the string tensor.
  - `tf.io.decode_jpeg` then receives ASCII characters, not JPEG bytes, and raises an invalid-JPEG error.
  - A different key such as `image_bytes` would fail differently: the signature's only input is named `bytes_inputs` (`model-deployment/cli.py:108`).

**E4 (conceptual).** Does the model deployed by `python cli.py --pipeline` learn anything from the images the Data Collector just scraped? Prove it from the code, and sketch a fix.
- *Answer:*
  - No. The training job runs `trainer.task`, which downloads `https://github.com/dlops-io/datasets/releases/download/v4.0/cheese_4_labels.zip` (`ml-workflow/src/model-training/package/trainer/task.py:103-107`) and reads `datasets/cheese` (`:112`). Nothing reads `clean.zip`.
  - The DAG edges are `.after()` only (`ml-workflow/src/workflow/cli.py:229`, `:244`), so no data is passed.
  - *Fix sketch:* add a `--data_source` path to `task.py`, and have it `storage.Client().bucket(args.bucket_name).blob("clean.zip").download_to_filename(...)` and unzip into `datasets/cheese`. The old `pipenv` branch did this with `tfrecords.zip`.
  - Better still: have the processor component *output* the GCS URI, and pass it as a parameter into `model_training_job(...)`, so the dependency becomes a real data edge.

**E5 (hands-on, canary).** Modify Part A's `deploy()` so that a second deployment reuses your existing endpoint and sends it 20% of traffic. Which arguments change?
- *Answer:*
  - Pass `endpoint=aiplatform.Endpoint("projects/<NUM>/locations/us-central1/endpoints/<ID>")`.
  - Set `traffic_split={"0": 20, "<existing_deployed_model_id>": 80}`. `"0"` is the model being deployed now; get the old ID from `endpoint.list_models()` or `gcloud ai endpoints describe`.
  - Keep the machine settings.
  - You now pay for two nodes behind one URL. After a successful rollout, undeploy the old one.

**E6 (debugging, platforms).** On a Windows/Intel laptop, `sh docker-shell.sh` in `model-deployment/` either takes 40+ minutes or dies with `exec format error` in `RUN apt-get update`. Why? Would the image run on Vertex anyway?
- *Answer:*
  - `model-deployment/docker-shell.sh:15` forces `--platform=linux/arm64/v8`, so every `RUN` needs ARM emulation (QEMU), which may not be installed.
  - Use line 13 instead.
  - The question about Vertex is a trick: this image never goes to Vertex. It only runs on your laptop and calls the APIs. The architecture of images matters for the pipeline-step images (`dlops/cheese-app-*`), which must include amd64.

**E7 (conceptual, failure semantics).** The training step uses `job.run(..., sync=False)` (`ml-workflow/src/workflow/model.py:54-63`). Suppose the Vertex training job crashes with an out-of-memory error. What does the pipeline graph show, and what gets deployed?
- *Answer:*
  - From the aiplatform source: the job runs in a `concurrent.futures` thread. The component function returns, and the Python process waits for the thread at exit, but the thread's exception is stored, not raised. The process exits 0, so the graph shows **Model Training succeeded**.
  - Model Deploy then runs on `gs://<bucket>/model`. It either fails (no model yet), or **deploys the previous run's model**, which is silently stale.
  - Fix: `sync=True`, which makes `run()` raise, so the step fails and the DAG stops.

**E8 (cost).** After doing the whole tutorial once, including `--deploy` twice by accident and `--pipeline` once, how many endpoints exist, and on which machine types?
- *Answer:* three.
  - Two from Part A: each `deploy()` without `endpoint=` creates `model-mobilenetv2_train_base_True.v1_endpoint`, on `n1-standard-2` by SDK default.
  - One from the pipeline: `Cheese App Model_endpoint` on `n1-standard-4` (`ml-workflow/src/workflow/model.py:98`).
  - All have `min_replica_count=1`, so all bill 24/7. List them with `gcloud ai endpoints list --region=us-central1`, then undeploy and delete each.

## 9. Errata and open questions

**Errata (with evidence)**
1. **`--model_deploy` is broken by name shadowing:** `ml-workflow/src/workflow/cli.py:15` imports the component as `model_deploy_job`, and `:160` calls `model_deploy(` (the CLI function at `:154`). The README tells you to run it (`ml-workflow/README.md:186`). The committed `model_deploy.yaml` is stale: mushroom names, `kfp-2.3.0` (`ml-workflow/src/workflow/model_deploy.yaml:4`, `:47`, `:82`).
2. **The pipeline's data stages don't feed training.** README line 3 says the components are "put … together", and the processor "converts images into TFRecord format" (`ml-workflow/README.md:5`). In fact:
   - TFRecords are no longer produced (`ml-workflow/src/data-processor/cli.py:19`);
   - training ignores the bucket data (`ml-workflow/src/model-training/package/trainer/task.py:103-107`).
   - README line 7 says the Model Deploy step "Updates the model signature with preprocessing logic". In the code the signature is added by the trainer (`ml-workflow/src/model-training/package/trainer/task.py:350-383`); the deploy component only uploads and deploys (`ml-workflow/src/workflow/model.py:70-104`).
3. **README omits a bucket:** `GCS_PACKAGE_URI` (`gs://cheese-app-trainer-code`, `ml-workflow/src/workflow/docker-shell.sh:12`, `ml-workflow/src/model-training/docker-shell.sh:12`) must exist and contain the trainer tarball. Only `cheese-app-ml-workflow-demo` is mentioned (`ml-workflow/README.md:52`).
4. **Key-name mismatch:** `ml-workflow/src/model-training/docker-shell.sh:25` uses `/secrets/model-trainer.json`. The README only creates `ml-workflow.json` (`ml-workflow/README.md:45`).
5. **README folder tree is wrong:** it lists a `model-deploy` folder under `src` (`ml-workflow/README.md:35`), which doesn't exist; deploy lives in `ml-workflow/src/workflow/model.py`. It also nests `src` under `images` (`:31-32`) and omits `persistent-folder`.
6. **Stale expected output:** `model-deployment/README.md:72-89` shows a 3-class mushroom model, with `image_files` such as `data/oyster_3.jpg`. The README pipeline screenshots also show `dlops/mushroom-app-...` (`ml-workflow/images/vertex-ai-pipeline-2.png`).
7. **Stale docstrings and labels:**
   - `model-deployment/cli.py:5` documents `--upload`, which doesn't exist.
   - `model-deployment/cli.py:205` describes the parser as "Data Collector CLI" (so does `ml-workflow/src/data-processor/cli.py:113`).
   - `ml-workflow/src/workflow/model.py:73` prints `"Model Training Job"` in the deploy component.
   - `ml-workflow/src/workflow/model.py:4` and `:66` label both functions "# Define a Container Component", but they are lightweight Python components (section 3.5).
   - `ml-workflow/src/model-training/package/PKG-INFO:3` says "Mushroom App Trainer".
   - `model-deployment/Dockerfile:1` says "Python 3.13" but uses 3.11.
8. **Off-by-one and extension bugs in `predict()`:** `np.random.randint(0, high=len(image_files) - 1, ...)` never picks the last file (`model-deployment/cli.py:164`), and `glob(... "*.jpg")` skips `data/gouda-2.jpeg` (`:161`).
9. **Trainer split bug:** `validation_percent = 0.2` is defined but the second split uses `test_size=test_percent` (`ml-workflow/src/model-training/package/trainer/task.py:142-153`). Validation is about 9% of the data, not 20%. `tf.distribute.MirroredStrategy()` is created but never used as a scope (`ml-workflow/src/model-training/package/trainer/task.py:67`).
10. **Serving/training TF mismatch in the pipeline:** trained with `tf-cpu.2-17` (`ml-workflow/src/workflow/model.py:25`), served with `tf2-cpu.2-12` (`ml-workflow/src/workflow/model.py:80`). Not guaranteed compatible (see 3.4). Part A uses `tf_opt-cpu.2-16` for a TF 2.17 save, a pairing the instructors report as working (commit `3fbf63f` "Working endpoint").
11. **`sync=False` in the training component** (`ml-workflow/src/workflow/model.py:62`) hides job failures from the DAG (section 6, item 10).
12. **Unused or leftover pieces:**
    - `Pipfile`/`Pipfile.lock` remain in `ml-workflow/src/data-processor/` and `ml-workflow/src/model-training/`;
    - `beautifulsoup4` is a dependency in both data images but never imported;
    - `setup.py` still installs `wandb==0.15.11` (`ml-workflow/src/model-training/package/setup.py:5`) though W&B is commented out;
    - `task_old.py` is unused;
    - the docker socket and stage-folder mounts in `ml-workflow/src/workflow/docker-shell.sh:21-25` are unused in this lecture.
13. **Lecture numbering on the course site is inconsistent:** `tutorials_demo.md` calls this Lecture 15, while `_modules/week-09.md:6-7` labels "ML Workflows with Vertex AI" as "Lecture 14".

**Open questions (could not determine from the sources)**
- Whether the `tf2-cpu.2-12` serving image actually loads the TF 2.17 SavedModel that the pipeline's trainer writes. The pipeline was not run during verification, and commit `3fbf63f` "Working endpoint" only concerns Part A's `tf_opt-cpu.2-16`.
- Whether `task.py`'s private imports `tensorflow.python.keras` (`ml-workflow/src/model-training/package/trainer/task.py:13-14`) and `sklearn` resolve inside `us-docker.pkg.dev/vertex-ai/training/tf-cpu.2-17.py310`. Commit `dd5253d` ("Fixed training job issues") and `3712396` suggest the instructors ran it.
- Whether the Docker Hub images match repo HEAD. They were pushed 2025-10-23 at 10:19Z and 11:38Z (06:19/07:38 EDT). The last commit touching `ml-workflow/src/data-processor` is `dd5253d` at 09:41 EDT the same day.
- The default identity of the nested Custom Training job (no `service_account=` at `ml-workflow/src/workflow/model.py:54-63`), and whether it can write `gs://<bucket>/model` in a fresh student project without extra IAM grants.
- Whether `.set_cpu_limit("500m")` maps to a specific Vertex machine type for that step. The YAML records it (`ml-workflow/src/workflow/pipeline.yaml:63-67`), but the machine choice is made by Vertex.
- Exact current prices and default quotas for `n1-standard-2` / `n1-standard-4` prediction nodes in `us-central1`; check the Vertex AI pricing page.
- Anything the Ed lesson adds beyond the repos (slides, recordings, extra instructions). The Ed lesson could not be opened when this guide was made.

## Links

**model-deployment README** (`main` @ `3fbf63f`)
- [Setup Environments](https://github.com/dlops-io/model-deployment#setup-environments) · [API's to enable in GCP for Project](https://github.com/dlops-io/model-deployment#apis-to-enable-in-gcp-for-project) · [Setup GCP Credentials](https://github.com/dlops-io/model-deployment#setup-gcp-credentials) · [Create a local secrets folder](https://github.com/dlops-io/model-deployment#create-a-local-secrets-folder) · [Setup GCP Service Account](https://github.com/dlops-io/model-deployment#setup-gcp-service-account) · [Create GCS Bucket](https://github.com/dlops-io/model-deployment#create-gcs-bucket)
- [Run Container](https://github.com/dlops-io/model-deployment#run-container) · [Run `docker-shell.sh`](https://github.com/dlops-io/model-deployment#run-docker-shellsh) · [Prepare Model for Deployment](https://github.com/dlops-io/model-deployment#prepare-model-for-deployment) · [Upload & Deploy Model to Vertex AI](https://github.com/dlops-io/model-deployment#upload--deploy-model-to-vertex-ai) · [Test Predictions](https://github.com/dlops-io/model-deployment#test-predictions)

**ml-workflow README** (`main` @ `972ffbb`)
- [Setup Environments](https://github.com/dlops-io/ml-workflow#setup-environments) · [Create GCS Bucket](https://github.com/dlops-io/ml-workflow#create-gcs-bucket) · [Data Collector Container](https://github.com/dlops-io/ml-workflow#data-collector-container) · [Run Data Collector Container & Test CLI](https://github.com/dlops-io/ml-workflow#run-data-collector-container--test-cli) · [Run Data Processor Container & Test CLI](https://github.com/dlops-io/ml-workflow#run-data-processor-container--test-cli) · [Run Model Training Container & Test CLI](https://github.com/dlops-io/ml-workflow#run-model-training-container--test-cli-we-did-this-previous-lecture)
- [Build & Push Images](https://github.com/dlops-io/ml-workflow#build--push-images) · [Automate Running Data Collector Container](https://github.com/dlops-io/ml-workflow#automate-running-data-collector-container) · [Cheese App: Vertex AI Pipelines](https://github.com/dlops-io/ml-workflow#cheese-app-vertex-ai-pipelines) · [Run Workflow Pipeline in Vertex AI](https://github.com/dlops-io/ml-workflow#run-workflow-pipeline-in-vertex-ai) · [Entire Pipeline](https://github.com/dlops-io/ml-workflow#entire-pipeline) · [Test Specific Components](https://github.com/dlops-io/ml-workflow#test-specific-components) · [Vertex AI Pipelines: Samples](https://github.com/dlops-io/ml-workflow#vertex-ai-pipelines-samples) · [Run Simple Pipelines](https://github.com/dlops-io/ml-workflow#run-simple-pipelines)

**Course**
- Ed lesson: https://edstem.org/us/courses/97373/lessons/166040/
- Previous lecture with a tutorial: [L14 · Serverless Deployment: Cloud Functions, Cloud Run (`guides/L14-serverless-deployment.md`)](L14-serverless-deployment.md)
- Next lecture with a tutorial: [L18 · APIs + Frontend (`guides/L18-apis-frontend.md`)](L18-apis-frontend.md)
- Also related: [L13 · Advanced Training Workflows: experiment tracking (W&B), multi-GPU, serverless training (Vertex AI) (`guides/L13-training-workflows.md`)](L13-training-workflows.md) (the trainer this pipeline launches) and [L23 · Final Deployment and Review (`guides/L23-final-cicd-deployment.md`)](L23-final-cicd-deployment.md) (runs this `src/workflow` folder from GitHub Actions)
