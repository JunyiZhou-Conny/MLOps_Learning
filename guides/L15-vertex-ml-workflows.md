# L15 · ML Workflows with Vertex AI (followed on AWS: SageMaker endpoints and SageMaker Pipelines) — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166040/) · Tutorials (the series follows the AWS pair; the course map's GCP repos are context only): [`dlops-io/model-deployment-aws`](https://github.com/dlops-io/model-deployment-aws) `main` @ [`077f4db`](https://github.com/dlops-io/model-deployment-aws/tree/077f4dbc7b13ccef208c65a8e29489331261029e) (Part A) and [`dlops-io/ml-workflow-aws`](https://github.com/dlops-io/ml-workflow-aws) `main` @ [`f165c6e`](https://github.com/dlops-io/ml-workflow-aws/tree/f165c6e17895d3d6c33a150d349f4b2649c807db) (Part B) · Video: [AC215 · L15 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-vertex-ml-workflows) · Made from the verified digest and real terminal captures, 2026-11-05

## 中文速览

- **做什么（Part A, `model-deployment-aws`）：** 把一个已经 train 好的 cheese classifier（MobileNetV2，4 个 class，GitHub release 里的 `.keras`）部署到 Amazon SageMaker：`python cli.py --prepare` export 成 SavedModel（version folder `1/`）→ 打包 `model.tar.gz` → 上传 S3；`--deploy` 一次建出 SageMaker **Model** + **endpoint configuration** + **endpoint**（1 台 `ml.m5.xlarge`）；`--predict` 发 5 张图；`--delete` 清理。
- **做什么（Part B, `ml-workflow-aws`）：** 先在各自的 container 里手动跑 data collector（Bing 抓图 → `raw.zip`）、data processor（difPy 去重 → `clean.zip`，再转 TFRecords → `tfrecords.zip`）、model training（本地 1 个 epoch，或提交 SageMaker training job），再把 image push 到**你自己的 ECR**，最后用 `python cli.py --pipeline` 把五步 `DataCollector → DataProcessor → ModelTraining → CreateModel → DeployModel`（Lambda）串成一个 SageMaker Pipeline。
- **Idea 1 · Slides 讲 Vertex AI，tutorial 用 AWS：** GCS bucket → S3；Model Registry → 一个普通的 SageMaker Model（README 叫它 "Model Registry"，code 里没有 model package）；Endpoint → endpoint configuration + endpoint；Vertex AI Pipelines（KFP DSL compile 成 YAML）→ SageMaker Pipelines（SDK step classes，`upsert` 成 JSON definition，再 `start`）；service account → laptop 上用 IAM user 的 access key，云上用 IAM role。
- **Idea 2 · Preprocessing 放在哪：** Part A 的 export 只换了 *format*，signature 还是吃 float `(-1, 224, 224, 3)`、吐 4 个数，所以 client 自己 resize、除以 255，每张图发 224·224·3 = 150,528 个 float 的 JSON。Part B 的 trainer 才做了 slides 13–14 说的事：把 JPEG decode/resize 写进 `serving_default`，endpoint 直接收 bytes。
- **Idea 3 · Pipeline 的箭头来自 property reference：** 一个 step 的 input 写成另一个 step 的 `.properties...`（一个运行时才有值的 placeholder），这就是 edge；`steps=[...]` 的顺序不决定 run 的顺序。真正的数据是靠 bucket 根目录的 `raw.zip` / `clean.zip` / `tfrecords.zip` 按文件名传的，declared folders 是空的。每个 step 有 30 天 cache。你的 laptop 只负责 define、建 deploy Lambda、`upsert` 和 `start`，然后马上返回；`DeployModel` 变绿时 endpoint 可能还没 `InService`。
- **今天（2026-11-05）一定会踩的两个坑：** ① `Pipfile` 写的是 `sagemaker = "*"` 又没有用 lock，build 时 resolve 到 SDK 3（Python 3.9 上是 3.13.1，3.11 上是 3.29.0），它根本没有 `sagemaker.tensorflow`、`sagemaker.processing`、`sagemaker.workflow`，`cli.py` 一 import 就 `ModuleNotFoundError`；改成 `sagemaker = "<3"`（得到 2.257.7）。② 三个 `docker-shell.sh` 写死 `--platform=linux/arm64/v8`（"M1/2 chip macs use this line"），在 x86_64 Linux 上第一个 `RUN` 就 `exec /bin/sh: exec format error`；改用脚本里被注释掉的那行 plain `docker build`。
- **其他费时间的坑：** Option 2 export 的 key 进不了 Part A 的 container（`docker run` 没有 `-e AWS_ACCESS_KEY_ID`）；`--prepare` 第一件事是 `create_bucket`，没有 credentials 就什么都没下载；README 的 `--predict` 示例输出是 3 个数、0 = gouda，今天的 model 是 4 个数、0 = parmigiano；trainer 里 `num_classes = 3`（gouda 的 label 是 3）；Linux 上 Docker 把不存在的 `persistent-folder` 建成 root 所有，本地 training 存 model 时 `PermissionError`（先自己 `mkdir`）；直接粘贴 `export REGION=us-east-1 [YOUR DEVELOPMENT REGION]` 会报错，没有 account id 时 ECR URI 以 `.` 开头，`|| true` 把 create-repository 的错误吞掉；README 说 Build & Push "already done"，但 pipeline 从**你自己的** ECR 拉 image；Ubuntu 上 `sh` 是 dash，`docker-shell.sh` 的 key check 失效，用 `bash docker-shell.sh`。
- **做完要删：** endpoint 没有流量也 24/7 计费，不会 scale to zero。Part A 每次 `--deploy` 都建一个带时间戳的新 endpoint，`--delete` 只删最后一个；Part B 有 `cheese-app-endpoint`（pipeline 的 Lambda 建的）和每次 `--model_deploy` 新建的 `cheese-app-endpoint-<8 chars>`。按 endpoint → endpoint config → model 的顺序删，再删 `sagemaker-deploy-model-lambda-*` Lambda functions、`cheese-pipeline`、两个 ECR repositories 和 buckets；最后 `aws sagemaker list-endpoints` 应该是空的。
- **Lecture slides：** 老师的 Lecture 15 slides（42 页，讲 Vertex AI）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天 AWS tutorial/captures 不一样的 12 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 13–14 把 preprocessing 放进 model 的 serving signature；Part A 的 AWS code 没这样做（client 发 float），Part B 的 trainer 做了。② slides 11、16–17 说 serverless、autoscaling；这两个 endpoint 都固定 1 台 instance，没有流量也 24/7 计费，每次 deploy 还多一个 endpoint。

## At a glance

**What you build.** In Part A you take a cheese classifier that was trained earlier (MobileNetV2 with four classes, shipped as a `.keras` file in a GitHub release), export it as a TensorFlow SavedModel inside `model.tar.gz`, upload it to S3, and serve it from a SageMaker endpoint that `--predict` calls with JSON. In Part B you run the Cheese App's data collector, data processor and trainer by hand, each in its own container, push the two data images to your own Amazon ECR, and then let one SageMaker Pipeline run all four stages plus a deploy step that a Lambda function performs. The lecture slides teach the same two ideas on Vertex AI; §7 maps one vocabulary onto the other.

**Time needed** (estimate). Console set-up (two IAM users, three roles, two buckets): about 45 minutes. First image builds: the Part A image took 400.6 s on the capture machine (`laptop/25`), the data processor 183.8 s for its lock and install alone (`laptop/67`), the trainer's `pipenv sync` 70.0 s (`laptop/72`). The Part A deploy "will take several minutes to complete (typically 5-10 minutes)" (README A:127). The full pipeline was not run here (no AWS account); a 15-epoch training job on CPU is the longest step. The follow-along video is about 30 minutes in two parts. With the extras in §4 and the exercises, budget a long afternoon.

**Prerequisites.**
- An AWS account with billing. Both READMEs use `us-east-1`.
- Docker and `git` on your laptop; the **AWS CLI v2 on the host** (Part B's scripts call `aws configure get …` before they build; Part A's Option 1 needs `aws configure`).
- No local Python: everything else runs in containers.
- Background: containers and `docker-shell.sh` (L2–L4), the cheese collector/processor/TFRecords (L6–L9), the trainer package and a managed training job (L13), serverless serving on Cloud Run (L14).

**What it costs** (no prices here; check AWS's SageMaker pricing page).
- Every **endpoint** bills per instance-hour, **24/7, even with zero traffic**: Part A `ml.m5.xlarge`, Part B `ml.m5.large`.
- **Training jobs** (`ml.m5.xlarge`) and **Processing jobs** (`ml.t3.medium`) bill while they run and stop by themselves.
- S3, ECR and Lambda: small, but they accumulate.

**Tear down, exactly** (commands in the checklist's last section and in §2):
1. Every endpoint: Part A's `model-mobilenetv2-train-base-True-v1-endpoint-<timestamp>` (one per `--deploy`), Part B's `cheese-app-endpoint` and every `cheese-app-endpoint-<8 chars>` (one per `--model_deploy`).
2. Their endpoint configurations and models.
3. The Lambda functions `sagemaker-deploy-model-lambda-*` (one per `--pipeline`) and the pipeline `cheese-pipeline`.
4. The ECR repositories `cheese-app-data-collector` and `cheese-app-data-processor`, then both buckets.
5. Check: `aws sagemaker list-endpoints` returns an empty list.

**How to read the references.** `A:127` is line 127 of README A (`model-deployment-aws/README.md`), `B:233` line 233 of README B (`ml-workflow-aws/README.md`). Code paths are written from the folder that holds your clones: `ml-workflow-aws/src/workflow/cli.py:219` is line 219 of that file. `laptop/25` is capture file `assets/terminal/laptop/25-*.txt` in the [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-vertex-ml-workflows/assets/terminal); `laptop/25:32` is its line 32.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Series decision.** The course map lists the GCP repos `dlops-io/model-deployment` and `dlops-io/ml-workflow`; this series follows their AWS counterparts. The lecture slides (Vertex AI) decide the concepts; the two AWS READMEs and the captures decide what is shown.
- **Part A:** `dlops-io/model-deployment-aws`, branch `main`, commit `077f4dbc7b13ccef208c65a8e29489331261029e`, committed 2025-08-25 17:13:00 −0300 ("Merge pull request #1 from dlops-io/itamar/aws-initial-commit"). Re-checked with `git ls-remote` on 2026-11-05: `HEAD` = `main` = `077f4db`. Other refs (not used): branches `itamar/aws-initial-commit` @ `1e34bff` and `itamar/new-trained-mobile-net` @ `00a4f08` (both merged), tag `v1.0` @ `6ecc50b`, whose release asset `mobilenetv2_train_base_True.zip` is what `--prepare` downloads (`cli.py:84-88`).
- **Part B:** `dlops-io/ml-workflow-aws`, branch `main`, commit `f165c6e17895d3d6c33a150d349f4b2649c807db`, committed 2025-08-19 08:50:13 −0400 ("Migrate ml-workflow from GCP to AWS"). `git ls-remote` on 2026-11-05: `main` = `HEAD` = `f165c6e`; no other branches or tags. Same commit as the [exam edition](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-exam).
- **README sections:** README A from top to bottom: Setup Environments (A:6-52), Run Container (A:54-148), Clean Up Resources (A:150-176), Troubleshooting (A:178-197). README B from top to bottom: Setup Environments (B:11-81), Run Data Collector (B:88-100), Run Data Processor (B:107-120), Run Model Training (B:126-145), Build & Push Images (B:152-203), Automate Running Data Collector Container (B:210-224), Cheese App: SageMaker Pipelines (B:226-248).
- **Terminal captures (the strongest evidence in this guide).** 2026-11-05, 04:00–05:50 UTC, in a fresh `docker:29.8.2-dind` "laptop" (linux/x86_64, user `student` uid 1000, git 2.54.0, AWS CLI 2.34.63), with **no AWS account**: keys either missing (Part A) or obviously fake placeholders (Part B). Every local step ran for real (the Bing scrape, difPy, TFRecords, one epoch of training); every AWS call stops at its honest first error. Two capture-only stand-ins are labelled as such: the exported model served by the public `tensorflow/serving:2.13.1` image (`laptop/45-48`), and the pipeline definition built offline with a placeholder account (`laptop/92`). Files and provenance: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-vertex-ml-workflows/assets/terminal) and `ASSETS.md` in the video folder.
- **Versions inside the images at the time of recording:** Part A image (with the `<3` pin): Ubuntu 20.04, Python 3.9.5, TensorFlow 2.18.0, Keras 3.10.0, sagemaker 2.257.7, boto3 1.42.97, 4.01 GB. Data collector: `python:3.11-slim`, Python 3.11.18, from its committed lock. Data processor: TensorFlow 2.13.1, difPy 4.2.1, dask 2026.8.0, resolved at build. Trainer: TensorFlow 2.20.0, Keras 3.11.2, sagemaker 2.250.0, from its committed lock. Workflow image (with the pin): sagemaker 2.257.7, AWS CLI 2.39.4.
- **Third-party code read, not run, for SDK behaviour:** `sagemaker==2.250.0` (the version the trainer's and the workflow's `Pipfile.lock` record), `botocore==1.40.11`, `difPy==4.2.1`.
- **Colab notebooks:** none for L15. **Ed lesson:** not opened; the lecture side is the slide digest below.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 15: ML Workflows with Vertex AI*, 42 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The full slide digest lives in the Explainer_Videos repo, in `videos/ac215-l15-vertex-ml-workflows/SLIDES.md`. The deck is written for Google Cloud (Vertex AI, GCS, Kubeflow Pipelines); this guide follows the AWS tutorials, so the slides supply the ideas and the AWS READMEs and captures supply the commands. The two README diagrams are lecture drawings: `model-deployment-aws/images/serverless-model-deployment.png` follows slide 12's five steps, and `ml-workflow-aws/images/ml-pipeline.png` is the graph on slide 37.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §7 Where this sits in the course | 6–8 (roadmap, the four Cheese App components, L14 recap), 10 (the Vertex AI console map), 19 |
| §1 Part A diagram; checklist *Part A*; §4 A1–A9 | 11–12, 15 |
| §1 Part B diagram; checklist *Part B*; §4 B1–B12 | 20–21, 34, 37–39 |
| §2 costs; checklist *Clean up* | 11 (the cost alert), 41 |
| §3.1 Where preprocessing lives; §5 excerpts 1, 4 | 12–14 |
| §3.2 Model, endpoint configuration, endpoint | 11–12, 15–17 |
| §3.3 The request | 13 (the goal: raw bytes only; the JSON format itself is tutorial-only) |
| §3.5 Step kinds; §4 B5, B8; §5 excerpt 5 | 27–28, 34–37 |
| §3.6 Property references and the definition; §5 excerpt 6 | 25–30, 33–34, 40 |
| §3.7 Where the data really flows | 20–21, 37 |
| §3.4 Prebuilt containers, §3.8 Two identities, §6, §8, §9 | none (tutorial-only), except the local login in §3.8, which slide 36 shows for gcloud |

**Lecture ideas you need for this tutorial**
1. Collector, processor and training already exist. This lecture adds Model Deploy, then automates all four (slides 6–7, 20–21).
2. Serverless model deployment puts a trained model behind a managed endpoint (online or batch, CPU or GPU), and an online endpoint costs money for as long as it is up (slide 11; slide 41's image-only "DELETE!!" reads as the clean-up reminder).
3. Deployment takes five steps, all driven from one CLI container: get the saved model, update its signature, upload it to GCS, upload it to the Model Registry, deploy an endpoint (slides 12, 15).
4. Put the preprocessing inside the model's serving signature so the endpoint accepts raw image bytes. Otherwise every client preprocesses a little differently ("client-side brittleness"), and one central copy is also easier to roll back (slides 13–14).
5. Use Vertex AI Online Prediction to serve trained models, and Cloud Run when ML is one part of a larger application (slides 16–17).
6. Workflow management runs the steps in dependency order and makes runs repeatable; it also covers scheduling, monitoring and resources (slides 19, 22).
7. Vertex AI Pipelines is Kubeflow Pipelines, managed for you. You describe the steps in a Python DSL and set up no Kubernetes (slides 24–27).
8. Writing a pipeline takes three moves: `@dsl.component` functions, a `@dsl.pipeline` that wires them by passing `.output`, and a compile to YAML. The SDK's `aip.PipelineJob(...).run()` then submits the YAML (slides 28–33).
9. Your own step containers must be callable. One image opens a shell when given no arguments (development) and runs the CLI when given arguments (production). Push them to a registry the pipeline service can pull from, and describe the DAG (slides 34–36).
10. The whole chain: DSL → compiler (YAML) → SDK → Kubeflow → Vertex AI Pipelines. Each container is a worker, and the DAG sets their order (slide 40).

**Where the slides and today's tutorial differ** (the AWS repos at the pinned commits and the 2026-11-05 captures show what runs today)
1. **The platform.** The slides speak Vertex AI on Google Cloud; the tutorial runs on AWS. The ideas carry over one to one (§7's table): GCS → S3, Vertex endpoint → SageMaker endpoint configuration + endpoint, Vertex AI Pipelines → SageMaker Pipelines, Artifact Registry → ECR, service account → IAM user key locally and IAM role in the cloud.
2. **Slides 13–14 move preprocessing into the model.** Part A does not: its export keeps the model's float input (`inputs['input']` `DT_FLOAT` `(-1, 224, 224, 3)`, `laptop/43`), and `--predict` resizes and divides by 255 on your laptop (`cli.py:221-225`). Part B's trainer does exactly what slide 14 shows (`task.py:276-318`). README A's "Prepare the model in TensorFlow SavedModel format" (A:115) is a format change, not the lecture's signature change (§3.1).
3. **Slides 12 and 15 upload to the Model Registry.** Both READMEs say "Model Registry" (A:7, B:7), but the code creates a plain SageMaker Model (`cli.py:151-159`; the pipeline's `CreateModel` step); no model package group is used (§3.2).
4. **Slides 11, 16 and 17 promise serverless scaling.** Both deploys pin one always-on instance (`initial_instance_count=1`, `cli.py:168-170`; `"InitialInstanceCount": 1`, `deploy_model_lambda.py:25-36`). It bills 24/7 with zero traffic, never scales to zero, and each `--deploy` makes a new endpoint (§2).
5. **Slides 16–17 list versioning, A/B testing and drift detection.** The tutorial uses none of them: one production variant `AllTraffic` with weight 1, no monitoring schedule (Exercise D1).
6. **Slide 37's Data Processor "Convert to TF Records".** Here the AWS repo agrees with the slide (the GCP repo no longer does): `--prepare` writes real TFRecord shards (`laptop/68`: `train_0000.tfrecords`, `val_0000.tfrecords`), and training reads TFRecords.
7. **Slides 19, 22 and 37 draw data flowing down the chain.** The edges are property references, but the step code moves the data itself, by file name, through the bucket root (`raw.zip`, `clean.zip`, `tfrecords.zip`); the folders the steps declare stay empty (§3.7).
8. **Slides 29 and 33 compile to YAML and call `PipelineJob(...).run()`.** SageMaker's SDK builds the pipeline from step objects, `upsert` sends a JSON definition (`laptop/92` shows it, built offline), and `start()` returns at once (`src/workflow/cli.py:320-328`, §3.6).
9. **Slide 34 pushes images to a Google registry; slide 39 lists "Build & Push Image".** The pipeline pulls `cheese-app-data-collector:latest` and `cheese-app-data-processor:latest` from **your** account's ECR (`src/workflow/cli.py:35-36`), so README B's "This step has already been done for this tutorial" (B:153) does not hold for you. Images for SageMaker must be amd64 (§4 B8).
10. **Slide 35's Dockerfile sketch** (`python:3.9-slim-buster`, `ENTRYPOINT ["uv", "shell"]`). The real images use `ubuntu:20.04` (Part A) or `python:3.11-slim` (Part B) with pipenv, and the entrypoints end in `pipenv shell` (Part A, trainer, workflow) or the two-mode `exec bash` / `exec "$@"` (collector, processor).
11. **Slide 36's development branch logs in to gcloud.** The collector's and processor's entrypoints only branch on arguments; credentials come from your key as environment variables locally and from the execution role on SageMaker. SageMaker even replaces the image's entrypoint: `Processor(entrypoint=["python3", "/app/cli.py"])` (`src/workflow/cli.py:175`) (§3.5, §3.8).
12. **Slides 22 and 24 promise reproducible runs.** `sagemaker = "*"` with no lock in use resolves to SDK 3 today and breaks every import (`laptop/22-23`, `85-86`); the fix is `sagemaker = "<3"`. Slide 30 calls the SDK the chef and slide 40 the operator who sends the recipe: slide 40 is right, the SDK submits and returns, and SageMaker runs the steps.

## Command checklist

Commands in backticks are exactly as the READMEs write them (placeholders kept). Plain items are console clicks. Items marked *(extra)* are not in the README; they come from §4, where the real output of every captured command is shown. Host commands run in the folder named in each section; every command after `sh docker-shell.sh` runs in the container shell it opens, until the next `exit`. Your bucket names replace `cheese-app-models-demo` and `cheese-app-ml-workflow-demo`, and your account id replaces `<ACCOUNT_ID>`.

### Part A · `model-deployment-aws` (README A)

*Clone the github repository* (A:9-10)
- [ ] Clone or download the repository — the README only links it. *(extra)* The usual command: `git clone https://github.com/dlops-io/model-deployment-aws.git`, then `cd model-deployment-aws`.
- [ ] `git log -1 --format='%H %ci %s'` — *(extra)* `077f4dbc7b13… 2025-08-25 … Merge pull request #1 …`, or a newer commit.

*AWS Services to Enable* (A:12-16)
- [ ] Make sure you can use Amazon S3, Amazon SageMaker and AWS IAM in your account.

*Create AWS IAM User* (A:21-30)
- [ ] AWS Console → IAM → create user `model-deployment`; attach `AmazonS3FullAccess`, `AmazonSageMakerFullAccess`, `IAMFullAccess`; create access keys and save the Access Key ID and Secret Access Key.
  - Note: `cli.py` never creates a role, so `IAMFullAccess` (A:28, "needed for SageMaker to create execution roles") is broader than the code needs; least privilege says leave it off if your course setup allows.

*Create SageMaker Execution Role* (A:32-44)
- [ ] IAM → Roles → Create role → trusted entity **SageMaker**; attach `AmazonSageMakerFullAccess` and `AmazonS3FullAccess`; name it `SageMakerExecutionRole`; copy its ARN (`arn:aws:iam::<ACCOUNT_ID>:role/SageMakerExecutionRole`) for `SAGEMAKER_ROLE`.

*Create S3 Bucket* (A:46-52)
- [ ] S3 console → create a bucket `cheese-app-models-demo` [REPLACE WITH YOUR UNIQUE BUCKET NAME]; bucket names are global.

*Configure AWS Credentials · Option 1 (recommended)* (A:64-75)
- [ ] `aws configure` — on your laptop: Access Key ID, Secret Access Key, region (e.g. `us-east-1`), output `json`. Writes `~/.aws/credentials` and `~/.aws/config`, which the container mounts.
- [ ] `aws sts get-caller-identity` — *(extra)* your user's `Arn` ending in `user/model-deployment`; captured without keys: `Unable to locate credentials`.

*Configure AWS Credentials · Option 2* (A:77-83)
- [ ] `export AWS_ACCESS_KEY_ID=your_access_key_id`
- [ ] `export AWS_SECRET_ACCESS_KEY=your_secret_access_key`
- [ ] `export AWS_REGION=us-east-1`
  - Note: these set variables in your laptop's shell only. `docker-shell.sh:22-28` passes `AWS_REGION`, `S3_MODELS_BUCKET_NAME` and `SAGEMAKER_ROLE` into the container, not the two keys, so Option 2 alone leaves the container without credentials. Use Option 1, or add `-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY` to the `docker run` line.

*Update Configuration* (A:85-90)
- [ ] Edit `docker-shell.sh` lines 7-9: `S3_MODELS_BUCKET_NAME` (your bucket), `SAGEMAKER_ROLE` (your role's ARN), `AWS_REGION`.
  - Note: line 8 ships the tutorial author's own role ARN; replace the whole value with yours.
- [ ] *(extra, x86_64 Linux / Windows / Intel Mac)* Swap the build lines: activate line 17 `docker build -t $IMAGE_NAME -f Dockerfile .` and comment out line 19 (`--platform=linux/arm64/v8`, "M1/2 chip macs use this line"). Without it, captured: `exec /bin/sh: exec format error` at `[ 2/14]`. On an Apple-silicon Mac leave line 19 as it is.
- [ ] *(extra, everyone, today)* In `Pipfile` line 10 change `sagemaker = "*"` to `sagemaker = "<3"`. Without it the build resolves the SageMaker SDK 3 (3.13.1 on this image's Python 3.9 at the time of recording), and `cli.py` fails at its imports.

*Quick Start Commands* (A:92-108)
- [ ] `chmod +x docker-shell.sh` — makes the script executable (it already is in a fresh clone).
- [ ] `sh docker-shell.sh` — builds `model-deployment-cli-aws` and opens the container: `Container is running!!!`, `Testing AWS connectivity...`, your identity (or the credentials error), then a pipenv shell with the prompt `(app) app@<id>:/app$`.
  - Note: the block's next four lines are `python cli.py --prepare`, `python cli.py --deploy`, `python cli.py --predict` and `python cli.py --delete`; the next sections explain each. Tick them there.
- [ ] `python cli.py --help` — *(extra)* the four flags (plus `--test`, which does nothing); the help texts still say "GCS Bucket" and "Vertex AI".

*Prepare Model for Deployment* (A:110-117)
- [ ] `python cli.py --prepare` — creates the bucket if needed, downloads the release zip, exports a SavedModel into `artifacts/model-mobilenetv2_train_base_True.v1/1`, tars it into `model.tar.gz`, uploads it to `s3://<bucket>/model-mobilenetv2_train_base_True.v1/model.tar.gz`.
- [ ] `aws s3 ls s3://<bucket>/model-mobilenetv2_train_base_True.v1/` — *(extra)* `model.tar.gz` is there.

*Upload & Deploy Model to SageMaker* (A:119-129)
- [ ] `python cli.py --deploy` — creates the Model, an endpoint configuration and the endpoint `model-mobilenetv2-train-base-True-v1-endpoint-<YYYYmmddHHMMSS>` on one `ml.m5.xlarge`, waits until it is in service ("typically 5-10 minutes", A:127) and writes `endpoint_config.json`. **The meter starts here.**

*Test Predictions* (A:131-148)
- [ ] `python cli.py --predict` — sends five randomly chosen sample photos (repeats are normal) and prints each result and label.
  - Note: README A's sample output (A:136-148) shows three numbers per photo and index 0 = `gouda`; today's model has **four** outputs and `cli.py:42` maps 0 = `parmigiano`.

*Clean Up Resources · Using AWS Console* (A:154-157)
- [ ] SageMaker → Endpoints → select your endpoint → Delete.

*Clean Up Resources · Using AWS CLI* (A:159-164)
- [ ] `aws sagemaker delete-endpoint --endpoint-name <your-endpoint-name>`
- [ ] `aws sagemaker delete-endpoint-config --endpoint-config-name <your-endpoint-config-name>`
- [ ] `aws sagemaker delete-model --model-name <your-model-name>`
  - Note: replace each `<…>` before running: pasted as written, bash reads `<` as a redirection (captured: `syntax error near unexpected token 'newline'`). The endpoint name is in `endpoint_config.json`; the endpoint configuration has the same name as the endpoint; the model is `model-mobilenetv2-train-base-True-v1`. `aws sagemaker list-endpoints` *(extra)* lists them all.

*Clean Up Resources · Using the CLI Script* (A:166-176)
- [ ] `python cli.py --delete` — deletes the endpoint named in `endpoint_config.json`, the matching endpoint configurations and model, and the S3 objects under `model-mobilenetv2_train_base_True.v1/`. It does not delete the bucket, and it only knows the **last** `--deploy`.
- [ ] `aws sagemaker list-endpoints` — *(extra)* should list none of yours; delete any leftover endpoint from an earlier `--deploy` with the CLI commands above.

### Part B · `ml-workflow-aws` (README B)

*Clone the github repository* (B:15-16)
- [ ] Clone or download the repository. *(extra)* `git clone https://github.com/dlops-io/ml-workflow-aws.git`, next to your Part A clone; `git log -1` shows `f165c6e…`.

*AWS Services* (B:18-24)
- [ ] Amazon SageMaker AI → *Set up for single user (Quick setup)*; Amazon SageMaker Unified Studio → *Create domain* (only to view the pipeline later); Amazon S3, Amazon ECR and AWS Lambda are used below.

*Create S3 Bucket* (B:26-30)
- [ ] Create a bucket `cheese-app-ml-workflow-demo` [REPLACE WITH YOUR BUCKET NAME].
- [ ] *(extra)* Put your bucket name into all four `docker-shell.sh` files (the README never says so): `src/data-collector/docker-shell.sh:10`, `src/data-processor/docker-shell.sh:10`, `src/model-training/docker-shell.sh:9-10` (also `S3_PACKAGE_URI`, which includes `s3://`), `src/workflow/docker-shell.sh:8-9`.

*Create IAM User* (B:35-43)
- [ ] IAM → Users → Create user `ml-workflow-user`; attach `AmazonS3FullAccess`, `AmazonSageMakerFullAccess`, `AmazonEC2ContainerRegistryFullAccess`, `AWSLambda_FullAccess`.

*Create Access Keys* (B:45-49)
- [ ] `ml-workflow-user` → Security credentials → Create access key → Command Line Interface (CLI) → download the `.csv` file.

*Install AWS CLI* (B:51-53)
- [ ] `brew install awscli` — macOS (or AWS's installer).
- [ ] `sudo snap install aws-cli --classic` — Linux (or AWS's curl installer).
- [ ] `aws --version` — *(extra)* `aws-cli/2.x` (2.34.63 on the capture laptop).

*Configure AWS CLI* (B:55-63)
- [ ] `aws configure` — the two keys from the `.csv`, region `us-east-1`, output `json`.
- [ ] `aws configure list` — *(extra)* shows the key's last four characters and where each value comes from.

*Test Configuration* (B:65-69)
- [ ] `aws sts get-caller-identity` — your user's identity (`…:user/ml-workflow-user`).
- [ ] `aws s3 ls` — lists your buckets.

*Create IAM Roles* (B:71-81)
- [ ] Role `CheeseAppSageMakerExecutionRole`: AWS Service → SageMaker → *SageMaker - Execution*; policies `AmazonSageMakerFullAccess`, `AmazonS3FullAccess`, `AmazonEC2ContainerRegistryFullAccess`.
- [ ] Role `CheeseAppLambdaExecutionRole`: AWS Service → Lambda; policies `AWSLambda_FullAccess`, `AmazonSageMakerFullAccess`.
  - Note: type both names exactly: the code builds `arn:aws:iam::<account>:role/CheeseAppSageMakerExecutionRole` and `…/CheeseAppLambdaExecutionRole` from your account id (`src/workflow/model.py:26-30`, `:40-44`).

*Run Data Collector Container & Test CLI* (B:88-100), in `src/data-collector`
- [ ] *(extra, Linux)* `mkdir -p ../../../persistent-folder` once, before the first `docker-shell.sh`: otherwise Docker creates it owned by root, and the trainer cannot write into it later (§6 #8).
- [ ] `sh docker-shell.sh` — reads your key and region from the host's AWS CLI, builds `cheese-app-data-collector` (`--platform=linux/amd64`) and opens a root shell `root@<id>:/app#`.
  - Note: on Debian/Ubuntu `sh` is dash, which does not understand the script's `[[ … ]]`, so its "AWS not configured" check silently passes; run `bash docker-shell.sh` there. On macOS `sh` behaves like bash.
- [ ] `python cli.py --search --nums 10 --query "brie cheese" "gouda cheese" "gruyere cheese" "parmigiano cheese"` — scrapes 10 images per query from Bing into `/persistent/dataset/raw/<query>/`, zips them into `raw.zip` and uploads it to the bucket root.
- [ ] Check your S3 bucket for `raw.zip`. *(extra)* `aws s3 ls s3://<bucket>/` on the host.

*Run Data Processor Container & Test CLI* (B:107-120), in `src/data-processor`
- [ ] *(extra, x86_64)* Swap the build lines in `docker-shell.sh`: activate line 29 `docker build -t $IMAGE_NAME -f Dockerfile .`, comment out line 31 (`--platform=linux/arm64/v8`). Captured as written: `exec /bin/sh: exec format error`.
- [ ] `sh docker-shell.sh` — builds `cheese-app-data-processor` (it locks its dependencies at build time: about 3 minutes) and opens a root shell.
- [ ] `python cli.py --clean` — uses the local `raw/` (or downloads `raw.zip`), removes duplicates with difPy and undecodable JPEGs, uploads `clean.zip`.
- [ ] Check your S3 bucket for `clean.zip`.
- [ ] `python cli.py --prepare` — splits 80/20, writes `train_0000.tfrecords` / `val_0000.tfrecords`, uploads `tfrecords.zip`.
- [ ] Check your S3 bucket for `tfrecords.zip`.

*Run Model Training Container & Test CLI* (B:126-145), in `src/model-training`
- [ ] *(extra, x86_64)* Swap the build lines in `docker-shell.sh` the same way (activate line 30, comment out line 32).
- [ ] `sh docker-shell.sh` — builds `cheese-app-training-cli` from its committed lock and opens `(app) app@<id>:/app$`.
- [ ] `python -m package.trainer.task --epochs=1 --batch_size=4 --bucket_name=cheese-app-ml-workflow-demo` — local training on `/persistent/dataset/tfrecords`, then saves the bytes-in SavedModel to `/persistent/model/1`.
  - Note: put your bucket name in `--bucket_name` (it is only used if the local TFRecords are missing). On Linux, if `persistent-folder` was created by Docker, the save fails with `PermissionError: [Errno 13] Permission denied: '/persistent/model'`; fix on the host with `sudo chown -R $USER ../../../persistent-folder` and run again.
- [ ] `sh package-trainer.sh` — tars `package/` into `trainer.tar.gz` and copies it to `$S3_PACKAGE_URI/cheese-app-trainer.tar.gz`.
- [ ] `python cli.py --train` — submits a SageMaker training job `cheese-<8 chars>` (15 epochs, `ml.m5.xlarge`) and returns at once (`wait=False`).
- [ ] SageMaker AI console → Training → Training jobs → the job starting with `cheese-` → details, logs, metrics. **The training meter runs until the job ends.**

*Build & Push Images · Pushing Docker Image to Docker Hub* (B:155-162), in `src/data-collector` and again in `src/data-processor`
- [ ] Sign up in Docker Hub and create an Access Token.
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>`
- [ ] `docker build -t <USER NAME>/<IMAGE_NAME> -f Dockerfile .`
- [ ] `docker build -t <USER NAME>/<IMAGE_NAME> --platform=linux/amd64/v2 -f Dockerfile .` — instead of the line above, on M1/2 Macs.
- [ ] `docker push <USER NAME>/<IMAGE_NAME>`
  - Note: README B says "This step has already been done for this tutorial" (B:153), but the pipeline pulls both images from **your** ECR (`src/workflow/cli.py:35-36`), so you need them there. Docker Hub is only the route the README takes to ECR; you can also tag your local `cheese-app-data-collector` image for ECR directly. Whatever you push must be **amd64**.

*Build & Push Images · Pushing Docker Image to Amazon ECR* (B:164-203), on the host
- [ ] `export REGION=us-east-1 [YOUR DEVELOPMENT REGION]`
  - Note: pasted as written, bash prints ``export: `[YOUR': not a valid identifier`` and ``export: `REGION]': not a valid identifier`` (captured). Type `export REGION=us-east-1`.
- [ ] `export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)`
- [ ] `export REPO=cheese-app-data-collector  # or cheese-app-data-processor`
- [ ] `export TAG=latest`
- [ ] `export ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG"`
- [ ] `docker pull <YOUR_DOCKER_HUB_USERNAME>/$REPO:$TAG` — (1) pull from Docker Hub (if needed).
- [ ] `aws ecr create-repository --repository-name "$REPO" --region "$REGION" || true` — (2) create the ECR repository. `|| true` also hides real errors (captured: exit 0 after `UnrecognizedClientException`); `aws ecr describe-repositories --repository-names "$REPO"` *(extra)* confirms it exists.
- [ ] (3) Authenticate Docker to ECR, one command over two lines (B:185-186):
  ```bash
  aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
  ```
- [ ] `docker tag <YOUR_DOCKER_HUB_USERNAME>/$REPO:$TAG "$ECR_URI"` — (4) tag the image for ECR.
- [ ] `docker push "$ECR_URI"` — (5) push.
- [ ] `aws ecr list-images --repository-name "$REPO" --region "$REGION" --output table` — (6) verify.
- [ ] `echo "ECR URI: $ECR_URI"` — (7) must start with your 12-digit account id; `ECR URI: .dkr.ecr…` (a leading dot) means `ACCOUNT_ID` is empty.
- [ ] Repeat the block for both images: `cheese-app-data-collector` and `cheese-app-data-processor` (B:201-203).

*Automate Running Data Collector Container* (B:210-224), in `src/workflow`
- [ ] *(extra, everyone, today)* In `src/workflow/Pipfile` line 9 change `sagemaker = "*"` to `sagemaker = "<3"` (the Dockerfile copies only the `Pipfile`, so the committed lock is never used; without the pin the build installs SDK 3.29.0 and every import fails).
- [ ] `sh docker-shell.sh` — builds `cheese-app-workflow` (amd64 only) and opens a pipenv shell; the banner prints `AWS Region`, `S3 Bucket`, `Package URI` and your identity.
- [ ] `python cli.py --data_collector` — runs the collector image from your ECR as a standalone SageMaker Processing job `cheese-app-data-collector-<8 chars>` (`ml.t3.medium`, 10 images per query) and streams its log.
- [ ] SageMaker AI → Processing → Processing jobs: inspect the job's status.

*Cheese App: SageMaker Pipelines · Entire Pipeline* (B:226-240)
- [ ] `python cli.py --pipeline` — builds the five steps, creates the deploy Lambda in your account, upserts `cheese-pipeline`, starts an execution and prints its ARN. **Training and the endpoint `cheese-app-endpoint` bill from here.**
- [ ] SageMaker → SageMaker Unified Studio → Build → ML Pipelines: inspect the run until all five steps are green.
- [ ] `aws sagemaker describe-endpoint --endpoint-name cheese-app-endpoint --query EndpointStatus` — *(extra)* wait for `InService`: a green `DeployModel` only means the Lambda asked for the endpoint.

*Cheese App: SageMaker Pipelines · Test Specific Components* (B:243-248)
- [ ] `python cli.py --data_collector` — the collector alone (Processing job).
- [ ] `python cli.py --data_processor` — the processor alone (`--clean --prepare`, Processing job).
- [ ] `python cli.py --model_training` — a training job, waits for it.
- [ ] `python cli.py --model_deploy` — deploys the newest `model-output/cheese-*/` artifact to a **new** endpoint `cheese-app-endpoint-<8 chars>` (`ml.m5.large`).

### Clean up after both parts *(extra, not in README B)*
- [ ] `aws sagemaker list-endpoints --query 'Endpoints[].EndpointName'` — every endpoint still billing.
- [ ] `aws sagemaker delete-endpoint --endpoint-name cheese-app-endpoint` — and the same for each `cheese-app-endpoint-<8 chars>` and any leftover Part A endpoint.
- [ ] `aws sagemaker list-endpoint-configs` and `aws sagemaker list-models` — then `aws sagemaker delete-endpoint-config --endpoint-config-name <name>` and `aws sagemaker delete-model --model-name <name>` for each of yours.
- [ ] `aws lambda list-functions --query 'Functions[].FunctionName'` — then `aws lambda delete-function --function-name sagemaker-deploy-model-lambda-<8 chars>` for each.
- [ ] `aws sagemaker delete-pipeline --pipeline-name cheese-pipeline`
- [ ] `aws ecr delete-repository --repository-name cheese-app-data-collector --force` and the same for `cheese-app-data-processor`.
- [ ] `aws s3 rb s3://<bucket> --force` — for each of your two buckets (deletes the contents too).
- [ ] `aws sagemaker list-endpoints` — empty.
- [ ] On your laptop: `docker image ls` and `docker image rm …` for the five images (the Part A image alone is 4.01 GB); delete `persistent-folder` beside your clones.

---

## 1. What you build

The lecture has two halves, and so does the tutorial.

**Part A (`model-deployment-aws`): serve one model.** You take an image classifier that was already trained (MobileNetV2 with a 128-unit dense layer and a 4-way softmax, shipped as `mobilenetv2_train_base_True.keras` in the repo's `v1.0` GitHub release) and put it behind a SageMaker endpoint. One CLI container does everything from your laptop:
- `--prepare` creates the bucket if needed, downloads the model, re-exports it as a TensorFlow **SavedModel** under a version folder `1/`, packs that folder into `model.tar.gz`, and uploads it (`cli.py:66-123`).
- `--deploy` creates a SageMaker **Model** (the S3 artifact plus AWS's prebuilt TensorFlow Serving 2.13 container), an **endpoint configuration** and an **endpoint** on one `ml.m5.xlarge`, and writes the endpoint's name to `endpoint_config.json` (`cli.py:126-185`).
- `--predict` resizes and normalises five random sample photos **on your laptop**, sends each as JSON floats, and prints the four probabilities and the label (`cli.py:188-239`).
- `--delete` removes the endpoint, its configuration, the model and the S3 artifact (`cli.py:242-312`).

**Part B (`ml-workflow-aws`): automate the whole workflow.** You run the Cheese App's stages by hand first, each in its own container that mounts a shared `persistent-folder` beside your clones, then hand them to **SageMaker Pipelines**:
- The data collector scrapes images from Bing and uploads `raw.zip`; the data processor removes duplicates (`clean.zip`) and writes TFRecords (`tfrecords.zip`); the trainer trains MobileNetV2 and saves a model whose serving signature takes JPEG bytes.
- `python cli.py --pipeline` in the workflow container builds five typed steps, `DataCollector` → `DataProcessor` → `ModelTraining` → `CreateModel` → `DeployModel` (`src/workflow/cli.py:157-328`), sends the definition to SageMaker and starts a run. AWS-managed machines run every step: the two data steps run **your images from your ECR**, training runs your trainer package inside AWS's TensorFlow 2.13 training container, and a **Lambda** function creates or updates the endpoint `cheese-app-endpoint`.

```
PART A - model-deployment-aws (every call goes out from your laptop; no ports are published)

 your laptop (Docker)
 +----------------------------------------------+  (1) GET release zip  +------------------------------------+
 | container model-deployment-cli-aws           | <-------------------- | github.com/dlops-io/               |
 | ubuntu:20.04, Python 3.9, pipenv             |                       |  model-deployment-aws  (v1.0 asset)|
 | tensorflow 2.18.0, sagemaker 2.x (pin "<3")  |                       +------------------------------------+
 | volumes: ./ -> /app ; ~/.aws -> /home/app/.aws  (2) export -> artifacts/<BEST_MODEL>/1/ -> model.tar.gz
 | env: AWS_REGION, S3_MODELS_BUCKET_NAME,      |  (3) upload_file      +------------------------------------+
 |      SAGEMAKER_ROLE   (no key variables!)    | --------------------> | S3  s3://<bucket>/model-mobilenet  |
 |                                              |                       |   v2_train_base_True.v1/model.tar.gz|
 | (app)$ python cli.py --prepare               |                       +-----------------+------------------+
 | (app)$ python cli.py --deploy                |  (4) TensorFlowModel(...).deploy        | model_data (read by the role)
 | (app)$ python cli.py --predict               | --------------------> +-----------------v------------------+
 | (app)$ python cli.py --delete                |                       | Model (+ TF Serving 2.13 image)    |
 |   identity: IAM user's access key            |                       | Endpoint config (1 x ml.m5.xlarge) |
 |                                              |  (5) JSON floats      | Endpoint  ...-endpoint-<timestamp> |
 |                                              | --------------------> |   bills 24/7 while it exists       |
 |                                              | <-------------------- | {"predictions": [[p0,p1,p2,p3]]}   |
 +----------------------------------------------+                       +------------------------------------+

PART B - ml-workflow-aws

 your laptop: container cheese-app-workflow (python:3.11-slim, AWS CLI v2, sagemaker 2.x with the pin)
   (app)$ python cli.py --pipeline
     a) build 5 step objects (their .properties are placeholders)
     b) create the deploy Lambda in your account          c) Pipeline("cheese-pipeline").upsert(role) ; .start()
                                                                 |  JSON definition
                                                                 v
 SageMaker Pipelines  (runs as CheeseAppSageMakerExecutionRole; each step cached 30 days)
  DataCollector   Processing, ml.t3.medium, image <ACCOUNT_ID>.dkr.ecr.<region>.amazonaws.com/cheese-app-data-collector
       |          python3 /app/cli.py --search --nums 50 ...  -> boto3 -> s3://<b>/raw.zip
       | ref: Outputs["raw-data"].S3Output.S3Uri
  DataProcessor   Processing, ml.t3.medium, image .../cheese-app-data-processor
       |          --clean --prepare -> s3://<b>/clean.zip, s3://<b>/tfrecords.zip
       | ref: Outputs["tfrecords"].S3Output.S3Uri
  ModelTraining   Training, ml.m5.xlarge, AWS tensorflow-training 2.13 image + s3://<b>/cheese-app-trainer.tar.gz
       |          15 epochs, batch 16, saves the bytes-in signature -> s3://<b>/model-output/<job>/output/model.tar.gz
       | ref: ModelArtifacts.S3ModelArtifacts
  CreateModel     SageMaker Model + tensorflow-inference 2.13 image
       | ref: ModelName
  DeployModel     Lambda (as CheeseAppLambdaExecutionRole): new endpoint config <name>-<MM-DD-HH-MM-SS>,
                  then create or update the endpoint "cheese-app-endpoint" (1 x ml.m5.large, bills 24/7)

 Before the pipeline, by hand (README order): data-collector, data-processor and model-training containers,
 each mounting ../../../persistent-folder -> /persistent and getting your access key as environment variables.
```

---

## 2. Prerequisites and costs

**Accounts and local installs**
- An AWS account with billing. Both READMEs use `us-east-1` (A:72, B:62).
- Docker (Desktop or Engine) and `git`.
- The **AWS CLI v2 on your host**. Part B's `docker-shell.sh` files run `aws configure get …` on the host before they build (`src/data-collector/docker-shell.sh:13-26`), and Part A's recommended Option 1 is `aws configure` (A:64-75). README B tells you how to install it (B:51-53).
- No local Python is needed.
- A Docker Hub account only if you take the README's Docker Hub route to ECR (B:155-162).
- W&B: `WANDB_KEY` is passed into the workflow container (`src/workflow/docker-shell.sh:43`), but no code reads it. Leave it empty.

**AWS services the READMEs name**
- Part A: S3, SageMaker, IAM (A:12-16).
- Part B: SageMaker AI (Quick setup for a single user), SageMaker Unified Studio (a domain, only for viewing the pipeline), S3, ECR, Lambda (B:18-24).

**Identities to create**

| What | README | Policies | Used by |
|---|---|---|---|
| IAM user `model-deployment` + access key | A:21-30 | `AmazonS3FullAccess`, `AmazonSageMakerFullAccess`, `IAMFullAccess` | your laptop, via `~/.aws` mounted into the container |
| Role `SageMakerExecutionRole` (trusted entity SageMaker) | A:32-44 | `AmazonSageMakerFullAccess`, `AmazonS3FullAccess` | the Part A model and endpoint, through `SAGEMAKER_ROLE` (`docker-shell.sh:8`, `cli.py:131-132`) |
| IAM user `ml-workflow-user` + access key (CLI use case) | B:35-49 | `AmazonS3FullAccess`, `AmazonSageMakerFullAccess`, `AmazonEC2ContainerRegistryFullAccess`, `AWSLambda_FullAccess` | your laptop, via `aws configure`; the scripts pass it to the containers as `-e AWS_ACCESS_KEY_ID …` |
| Role `CheeseAppSageMakerExecutionRole` (SageMaker - Execution) | B:72-76 | `AmazonSageMakerFullAccess`, `AmazonS3FullAccess`, `AmazonEC2ContainerRegistryFullAccess` | the pipeline and every Processing/Training job; **name hard-coded** (`src/workflow/model.py:28`, `src/model-training/cli.py:33`) |
| Role `CheeseAppLambdaExecutionRole` (trusted entity Lambda) | B:78-81 | `AWSLambda_FullAccess`, `AmazonSageMakerFullAccess` | the deploy Lambda; name hard-coded (`src/workflow/model.py:42`) |

**Values to edit before running** (every script hard-codes the tutorial's bucket, and S3 bucket names are global)

| File:lines | Variables |
|---|---|
| `model-deployment-aws/docker-shell.sh:7-9` | `S3_MODELS_BUCKET_NAME`, `SAGEMAKER_ROLE` (your role's ARN; line 8 ships the author's), `AWS_REGION` (A:85-90) |
| `ml-workflow-aws/src/data-collector/docker-shell.sh:10` | `S3_BUCKET_NAME` |
| `ml-workflow-aws/src/data-processor/docker-shell.sh:10` | `S3_BUCKET_NAME` |
| `ml-workflow-aws/src/model-training/docker-shell.sh:9-10` | `S3_BUCKET_NAME`, `S3_PACKAGE_URI` (with `s3://`) |
| `ml-workflow-aws/src/workflow/docker-shell.sh:8-9` | `S3_BUCKET_NAME`, `S3_PACKAGE_URI` |

README B never says to edit these files; it only says "[REPLACE WITH YOUR BUCKET NAME]" (B:30). The local-training command also names the bucket (B:136).

**Today's two build fixes** (§4 A5 and B6–B9; both captured): the plain build line instead of `--platform=linux/arm64/v8` on any non-Apple-silicon machine (`model-deployment-aws/docker-shell.sh:19`, `src/data-processor/docker-shell.sh:31`, `src/model-training/docker-shell.sh:32`), and `sagemaker = "<3"` in `model-deployment-aws/Pipfile:10` and `src/workflow/Pipfile:9`.

**Where things live**

| Thing | Where | Set by |
|---|---|---|
| Part A exported model | `model-deployment-aws/artifacts/` (git-ignored, `.gitignore:33`): the release zip, the `.keras`, and `model-mobilenetv2_train_base_True.v1/1/` + `model.tar.gz` | `--prepare` |
| Part A endpoint name | `model-deployment-aws/endpoint_config.json` (git-ignored, `.gitignore:41`) | `--deploy`; read by `--predict` and `--delete` |
| Part A artifact in S3 | `s3://<bucket>/model-mobilenetv2_train_base_True.v1/model.tar.gz` | `--prepare` |
| Part B shared data | `persistent-folder/` next to your two clones (`../../../persistent-folder` from `src/<stage>`), mounted on `/persistent` | Docker creates it if missing (as root on Linux) |
| Part B data in S3 | bucket root: `raw.zip`, `clean.zip`, `tfrecords.zip`, `cheese-app-trainer.tar.gz`; `model-output/<job>/output/model.tar.gz` | the stage CLIs, `package-trainer.sh`, the training job |
| Step images | `<ACCOUNT_ID>.dkr.ecr.<region>.amazonaws.com/cheese-app-data-collector:latest` and `…/cheese-app-data-processor:latest` | your push (B:164-203) |

**What costs money, and how to stop it**

| Resource | Created by | How it bills | Shut down |
|---|---|---|---|
| Part A endpoint | each `--deploy` (`cli.py:164-174`): 1 × `ml.m5.xlarge`, a **new timestamped endpoint every time** | per instance-hour, **24/7, even with zero traffic** | `python cli.py --delete` (last deploy only) or the three CLI commands (A:159-164) |
| `cheese-app-endpoint` | the pipeline's Lambda (`src/workflow/deploy_model_lambda.py:25-58`): 1 × `ml.m5.large`; later runs **update** it | 24/7 | `aws sagemaker delete-endpoint …` (README B has no clean-up section) |
| `cheese-app-endpoint-<8 chars>` | each `--model_deploy` (`src/workflow/model.py:170-175`): 1 × `ml.m5.large`, a **new endpoint each call** | 24/7 | same |
| Training jobs | `--train`, `--model_training`, the pipeline: 1 × `ml.m5.xlarge`, 15 epochs | while running | end by themselves |
| Processing jobs | `--data_collector`, `--data_processor`, the pipeline: 1 × `ml.t3.medium` | while running | end by themselves |
| Lambda functions | each `--pipeline` creates `sagemaker-deploy-model-lambda-<8 chars>` (`src/workflow/cli.py:294-303`), never deleted | per invocation (tiny); clutter | `aws lambda delete-function` |
| S3, ECR | two buckets, two repositories | storage | empty and delete |

"Serverless" in the lecture means no server for *you* to manage. It does not mean scale to zero: unlike your Cloud Run service in L14, these endpoints keep their instance running until you delete them. Delete the **endpoint** first: the model and the configuration are only descriptions.

---

## 3. Concepts this tutorial teaches

### 3.1 SavedModel and its serving signature: where does preprocessing live? (slides 12–14)
- **Explanation.** A serving container does not run "a Keras model"; it runs a **SavedModel**: a graph, weights and named entry points (signatures). TensorFlow Serving calls `serving_default`.
  - **Part A** loads the `.keras` model and calls Keras 3's `prediction_model.export(model_export_path)` (`cli.py:106-109`). That exports the model *as it is*. Captured with `saved_model_cli` (`laptop/43`): `inputs['input']` `DT_FLOAT` `(-1, 224, 224, 3)`, `outputs['output_0']` `(-1, 4)`. So the client resizes each photo to 224×224, divides by 255 and sends floats (`cli.py:221-225`): preprocessing lives on the **client**.
  - **Part B's trainer** does what the lecture recommends. After training it defines `preprocess_image` (decode the JPEG, convert to float32, resize to 224×224), maps it over a batch of strings in `preprocess_function`, chains it into the model call in `serving_function`, and saves the model with `signatures={"serving_default": serving_function}` (`src/model-training/package/trainer/task.py:276-318`). That artifact is "JPEG bytes in, scores out": preprocessing lives on the **server**.
- **Version folder.** TensorFlow Serving expects `<model>/<version>/saved_model.pb`. Part A exports into `artifacts/<BEST_MODEL>/1` (`cli.py:102-104`) and tars it with `arcname="1"` (`:117`): captured, every entry of `model.tar.gz` starts with `1/` (`laptop/42`). The trainer writes `$SM_MODEL_DIR/1` (`task.py:304-307`), and SageMaker tars `/opt/ml/model` itself.
- **Mental model.** A SavedModel is a program with a front door. Part A's door says "send me pixels"; the trainer's door says "send me a photo".
- **Analogy.** A shop that only accepts pre-cut fabric (every customer cuts it a little differently) versus one that takes the whole roll and cuts it the same way every time.
- **Common misconception.** "Re-saving in SavedModel format changes the signature." It doesn't; only an explicit `signatures=` (or a custom export) does.

### 3.2 SageMaker Model vs endpoint configuration vs endpoint (slides 11–12, 15–17)
- **Explanation.** Three separate API objects:
  - **Model**: where the artifact is (`model_data`, the S3 URI of `model.tar.gz`), which container serves it (the SDK turns `framework_version="2.13"` into AWS's `tensorflow-inference` 2.13 image), and which role reads it (`cli.py:151-159`). No machine runs yet.
  - **Endpoint configuration**: a list of *production variants*: which model, which instance type, how many instances, what weight. The Lambda writes one by hand: `"VariantName": "AllTraffic"`, `"InitialVariantWeight": 1`, `"InitialInstanceCount": 1` (`deploy_model_lambda.py:25-36`).
  - **Endpoint**: the live HTTPS service built from one configuration. `TensorFlowModel.deploy(...)` creates all three in one call (`cli.py:168-174`); the SDK names the configuration after the endpoint.
- **Updating.** To roll out a new model you create a *new* configuration and call `update_endpoint` on the existing endpoint (`deploy_model_lambda.py:47-52`): the name stays, the instances behind it are replaced. Several variants with different weights in one configuration are how A/B tests work (slide 16's "model versioning and A/B testing"; not used here).
- **Mental model.** Model = a catalogue card; endpoint configuration = the staffing plan (which card, which machine, how many); endpoint = the shop's address with the lights on.
- **Common misconceptions.** "Creating the model makes it callable" — only an endpoint is. "This is the Model Registry" — the READMEs say so (A:7, B:7), but the code creates plain Models, not model packages in a registry group. "Deleting the model stops the bill" — the endpoint is what bills.

### 3.3 The online prediction request (slide 13)
- **Explanation.** `sagemaker.Predictor(..., serializer=JSONSerializer(), deserializer=JSONDeserializer())` (`cli.py:200-205`) turns a Python dict into JSON and POSTs it to the endpoint; AWS's TF Serving container passes it to TensorFlow Serving's REST API. The body is `{"instances": [arr.tolist()]}` (`cli.py:225`): one instance is one 224×224×3 nested list of floats. The answer is `{"predictions": [[p0, p1, p2, p3]]}`; the code takes the argmax (`cli.py:231-232`) and maps it with a hard-coded dict: `0 parmigiano, 1 gruyere, 2 brie, 3 gouda` (`cli.py:41-42`).
- **Size.** One photo is 224·224·3 = **150,528** numbers; as JSON text that is a few megabytes per request (Exercise B1 measures it). That is the cost of client-side preprocessing the lecture warns about, and the reason for the trainer's bytes-in signature.
- **The other format (not exercised by the repos).** For a string-tensor input like the trainer's `bytes_inputs`, TensorFlow Serving's REST convention wraps binary data as `{"b64": "<base64>"}`. Neither AWS repo calls the pipeline's endpoint, so no repo code shows that request.
- **Common misconception.** "Predictions come back with label names." You get floats; the label map is yours, and it must match the training order.

### 3.4 Prebuilt framework containers: the runtime half of a model
- **Explanation.** SageMaker never runs a bare model; it runs a container image that loads it, and the code never writes a TensorFlow image URI: the SDK picks it from `framework_version` and `py_version`.
  - Serving: `TensorFlowModel(..., framework_version="2.13")` → `tensorflow-inference:2.13` (`model-deployment-aws/cli.py:154`, `src/workflow/cli.py:279`, `src/workflow/model.py:165`).
  - Training: `TensorFlow(..., framework_version="2.13", py_version="py310")` → `tensorflow-training:2.13` (`src/model-training/cli.py:59-60`, `src/workflow/cli.py:255-256`).
  - Processing: `Processor(image_uri=...)` runs *your* image from ECR (`src/workflow/cli.py:170-178`).
- **Version skew.** Part A exports with TensorFlow 2.18 (`Pipfile:12`) and is served by TF Serving 2.13: newer TF writing, older TF reading. The capture's local stand-in (the public `tensorflow/serving:2.13.1`, not SageMaker's image) loaded it with one warning, `NodeDef mentions attribute debug_name which is not in the op definition … Unknown attributes will be ignored`, then `Successfully loaded servable version {name: cheese version: 1}` (`laptop/46`).
- **Mental model.** The artifact is a cartridge; the container is the console. The console must be able to read the cartridge.

### 3.5 Pipeline steps: four kinds, and the callable container (slides 28, 34–37)
- **Explanation.** SageMaker Pipelines has typed steps; this pipeline uses four:
  - **ProcessingStep** with `Processor(image_uri=..., entrypoint=["python3", "/app/cli.py"])` (`src/workflow/cli.py:170-197`): run *your* container with arguments. This is the slides' container component.
  - **TrainingStep** with a `TensorFlow` estimator (`:249-270`): SageMaker starts the training job *as* the step, so a failed job fails the step.
  - **ModelStep** with `model.create(instance_type="ml.m5.large")` (`:276-288`): creates the SageMaker Model; the definition calls it `CreateModel-CreateModel` (`laptop/92:246`).
  - **LambdaStep** (`:297-315`): call a Lambda function with inputs; here it deploys.
- **"Make the container callable" (slides 35–36).** The collector and processor images have exactly the lecture's two-mode entrypoint: no arguments → `exec bash` (what `docker-shell.sh` gives you, `root@<id>:/app#` in `laptop/60`); arguments → `exec "$@"` (`src/data-collector/docker-entrypoint.sh:4-8`). SageMaker does not even use it: `Processor(entrypoint=[...])` replaces the image's entrypoint with `python3 /app/cli.py`, and the job's arguments are appended.
- **Common misconception.** "Every step is a container I build." Only the two Processing steps run your images; training and serving use AWS's framework images plus your code and artifact.

### 3.6 The DAG comes from property references (slides 25–30, 33–34, 40)
- **Explanation.** While `pipeline()` runs on your laptop, nothing executes in the cloud. `step_collect.properties.ProcessingOutputConfig.Outputs["raw-data"].S3Output.S3Uri` (`src/workflow/cli.py:219-220`) is a **placeholder** for a value that will exist only after the collector's job has run; using it as the processor's input creates the edge collector → processor. The same holds for the processor's `tfrecords` output into training (`:266-267`), `step_train.properties.ModelArtifacts.S3ModelArtifacts` into the model (`:277`), and `step_create_model.properties.ModelName` into the Lambda (`:309`).
- **What the definition looks like.** Built offline in the capture (`laptop/92`, placeholder account, not sent): five steps `DataCollector` (Processing), `DataProcessor` (Processing), `ModelTraining` (Training), `CreateModel-CreateModel` (Model), `DeployModel` (Lambda), and each reference became a `Get`, for example `{"Get": "Steps.DataCollector.ProcessingOutputConfig.Outputs['raw-data'].S3Output.S3Uri"}` (`laptop/92:143`).
- **Order.** `Pipeline(steps=[...])` (`:320-324`) is a set, not a schedule: SageMaker derives the order from the references. An explicit `depends_on=[...]` would add an ordering-only edge; this repo has none.
- **Definition and run.** `sm_pipeline.upsert(role_arn=role)` (`:326`) creates or updates the pipeline `cheese-pipeline` from the JSON definition; `sm_pipeline.start()` (`:327`) starts an execution and returns at once; `:328` prints its ARN. Your terminal does not wait. This is the AWS counterpart of the slides' compile-to-YAML plus `PipelineJob(...).run()` (slides 29, 33).
- **Caching.** Every step has `CacheConfig(enable_caching=True, expire_after="30d")` (`:165`; `"ExpireAfter": "30d"` in `laptop/92`). A step whose arguments did not change reuses its previous result for 30 days, so a second run within a month does not scrape again.
- **Analogy.** A recipe whose step 3 says "take the bowl from step 2": the reference *is* the arrow.
- **Common misconceptions.** "The list order is the run order" — no. "The property is a string I can print" — it is a reference resolved at run time.

### 3.7 Where the data really flows (slides 20–21, 37)
- **Explanation.** Each step runs on a fresh machine; S3 is the shared state. The steps *declare* folders: collector output `/opt/ml/processing/output` → `s3://<b>/raw` (`src/workflow/cli.py:189-195`); processor input `.../raw` → `/opt/ml/processing/input`, outputs `.../output/clean` → `s3://<b>/clean` and `.../output/tfrecords` → `s3://<b>/tfrecords` (`:216-235`). But the step code never touches those folders. The collector zips `/persistent/dataset/raw` and calls `s3_client.upload_file(zip_file, S3_BUCKET_NAME, "raw.zip")` (`src/data-collector/cli.py:55-65`); the processor downloads `raw.zip` itself when its local `raw/` is missing and uploads `clean.zip` and `tfrecords.zip` to the bucket root (`src/data-processor/cli.py:41-49`, `:68`, `:95`). The real handoff is a **file-name convention** in the bucket root.
- **Training input.** The training step's channel is the processor's declared `s3://<b>/tfrecords` (`:266-267`). The trainer looks for `tfrecords.zip` in its input channel and otherwise reads `train*`/`val*` files there (`task.py:71-86`). How the README's successful run found its data is not provable from the code alone (§9, open question 1).
- **Mental model.** The pipeline draws arrows between boxes; the boxes pass notes through a shared drawer (the bucket) by agreed file names.
- **Common misconception.** "Declaring an output uploads my data." SageMaker uploads only what the code writes into the declared local folder.

### 3.8 Two identities: access keys on your laptop, roles in the cloud
- **Explanation.**
  - **Locally**, containers use the IAM *user's* access key: Part A through the mounted `~/.aws` (`model-deployment-aws/docker-shell.sh:24`); Part B through `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` read from your `aws configure` and passed with `-e` (`src/data-collector/docker-shell.sh:14-16`, `:37-39`). boto3 finds them by itself (captured: `INFO:botocore.credentials:Found credentials in environment variables.`, `laptop/90`).
  - **In the cloud**, jobs run as an IAM *role*: the pipeline and its jobs as `CheeseAppSageMakerExecutionRole`, the Lambda as `CheeseAppLambdaExecutionRole`, the Part A model as your `SAGEMAKER_ROLE`. The same `boto3.client('s3')` call inside the collector then gets the role's temporary credentials. No key travels into an image.
  - `_resolve_role()` first tries `sagemaker.get_execution_role()`, which only works when the caller already *is* a role (a SageMaker notebook); on a laptop it fails and the code builds the ARN from your account id (`src/workflow/model.py:19-34`). Captured without a valid key: `RuntimeError: Unable to derive SageMaker execution role. Please ensure CheeseAppSageMakerExecutionRole exists in your AWS account.` (`laptop/73:313`).
- **Mental model.** The key is your badge at the building's front door; the role is the uniform a worker inside puts on for one job.
- **Common misconception.** "Bake my key into the step image so the cloud job can use S3." Never: the role does that. README A's security warning (A:56-58) applies to your edited `docker-shell.sh` too.

---

## 4. Step-by-step walkthrough

Steps follow README order: A1–A9 for README A, B1–B12 for README B. Commands are verbatim from the README unless marked *(extra)*.

**About the outputs below.** Outputs labelled *captured* are real, trimmed (`…`) from the 2026-11-05 captures in `assets/terminal/laptop/` (file named with each block; `[exit N]` lines omitted unless they matter). The capture laptop had **no AWS account**, so:
- every console step is described from the README's own field values;
- every AWS call is shown up to its honest first error: `Unable to locate credentials` in Part A (no keys at all), AWS's own `InvalidClientTokenId` / `InvalidAccessKeyId` in Part B (obviously fake placeholder keys);
- what only the cloud shows is either *recorded* (README A's own `--predict` output) or *expected* (what the code prints on success), never invented;
- two *local stand-ins* show what the cloud would do, labelled as such: the exported model served by the public TensorFlow Serving 2.13.1 image, and the pipeline definition built offline.

Container ids, timestamps and scraped URLs will differ for you; versions may be newer. The SageMaker SDK 2.x prints a `SageMakerV2DeprecationWarning` and TensorFlow prints CUDA/oneDNN notices on every start; they are trimmed below and are harmless.

### Part A — `model-deployment-aws` (README A)

**A1 · Clone** (A:9-10). *Captured* (`laptop/10`, `11`, `12`):
```
$ git clone https://github.com/dlops-io/model-deployment-aws.git
Cloning into 'model-deployment-aws'...
$ git log -1 --format='%H %ci %s'
077f4dbc7b13ccef208c65a8e29489331261029e 2025-08-25 17:13:00 -0300 Merge pull request #1 from dlops-io/itamar/aws-initial-commit
$ ls -la; ls data
…
-rwxr-xr-x    1 student  student       2095 Nov  5 04:28 Dockerfile
-rwxr-xr-x    1 student  student        230 Nov  5 04:28 Pipfile
-rw-r--r--    1 student  student       7138 Nov  5 04:28 README.md
-rw-r--r--    1 student  student      12818 Nov  5 04:28 cli.py
drwxr-sr-x    2 student  student       4096 Nov  5 04:28 data
-rwxr-xr-x    1 student  student        157 Nov  5 04:28 docker-entrypoint.sh
-rwxr-xr-x    1 student  student        851 Nov  5 04:28 docker-shell.sh
…
brie-1.jpg
brie-2.jpg
gouda-1.jpg
gouda-2.jpeg
gruyere-1.jpg
gruyere-2.jpg
parmigiano-1.jpg
parmigiano-2.jpg
```
Eight sample photos, two per cheese. There is no `Pipfile.lock`: it is git-ignored (`.gitignore:68`), so the image resolves its versions when you build it.

**A2 · Services, IAM user, execution role, bucket** (A:12-52). Console only (see the checklist). The role's ARN has the shape `arn:aws:iam::<ACCOUNT_ID>:role/SageMakerExecutionRole`; README A's example (A:43) uses AWS's documentation placeholder account in the same shape. Keep your real access key out of every file and screenshot (A:56-58).

**A3 · Credentials** (A:60-83). Option 1 runs `aws configure` on your laptop. *Captured* without keys (both key prompts answered with Enter, `laptop/13`, `14`, `15`):
```
$ aws configure

Tip: You can deliver temporary credentials to the AWS CLI using your AWS Console session by running the command 'aws login'.

AWS Access Key ID [None]:
AWS Secret Access Key [None]:
Default region name [None]: us-east-1
Default output format [None]: json
$ ls -la ~/.aws; cat ~/.aws/config
…
-rw-------    1 student  student         43 Nov  5 04:28 config
[default]
region = us-east-1
output = json
$ aws sts get-caller-identity

aws: [ERROR]: An error occurred (NoCredentials): Unable to locate credentials. You can configure credentials by running "aws login".
```
With your real key, `~/.aws/credentials` exists too and the last command prints a JSON with `UserId`, `Account` and an `Arn` ending in `user/model-deployment`. The *Tip* line is new in recent AWS CLI versions; the README's flow is unchanged.

Option 2 sets three variables in your laptop's shell. *Captured* with the README's own placeholder values (`laptop/16`): AWS answers `An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: The security token included in the request is invalid.` More important: whatever you export here never reaches the container, because `docker-shell.sh` passes only three variables (`:25-27`). Use Option 1.

**A4 · Update configuration** (A:85-90). Edit `docker-shell.sh` lines 7-9. *Captured* after the edit, with placeholders (`laptop/17`):
```
export IMAGE_NAME=model-deployment-cli-aws
export BASE_DIR=$(pwd)
export S3_MODELS_BUCKET_NAME="your-models-bucket-placeholder"
export SAGEMAKER_ROLE="arn:aws:iam::<ACCOUNT_ID>:role/SageMakerExecutionRole"
export AWS_REGION="us-east-1"
```
(The capture used an all-zero placeholder account.) Line 8 as committed holds the tutorial author's own role ARN: replace the whole value.

**A5 · Build and run the container** (A:96-99): `chmod +x docker-shell.sh` (silent; the file is already `-rwxr-xr-x`, `laptop/18-19`), then `sh docker-shell.sh`.
- **As written, on an x86_64 machine** (`laptop/20`, *captured*): the arm64 `ubuntu:20.04` is pulled, then
  ```
  #6 [ 2/14] RUN apt-get update &&     apt-get install -y curl apt-transport-https ca-certificates gnupg lsb-release openssh-client unzip
  #6 0.128 exec /bin/sh: exec format error
  …
  ERROR: failed to build …
  ```
  Line 19 builds `--platform=linux/arm64/v8` ("M1/2 chip macs use this line"). On an Intel/AMD machine without arm64 emulation the first `RUN` cannot execute. Fix: use the script's own commented line 17 (`laptop/21`):
  ```
  docker build -t $IMAGE_NAME -f Dockerfile .
  # M1/2 chip macs use this line
  #docker build -t $IMAGE_NAME --platform=linux/arm64/v8 -f Dockerfile .
  ```
  On an Apple-silicon Mac, line 19 is native and works.
- **The second fix: pin the SageMaker SDK.** `Pipfile:10` says `sagemaker = "*"`, and the Dockerfile runs `pipenv lock && pipenv sync` at build time, so you get the newest release. At the time of recording that is **SDK 3.13.1** on this image's Python 3.9, together with `torch==2.8.0`, fifteen `nvidia-*-cu12` packages and `mlflow==3.1.4`: *captured* `185 packages would be installed` (`laptop/22`, a dry run of pip's resolver). SDK 3 is a rewrite without the 2.x modules `cli.py` imports (`laptop/23`, *captured*):
  ```
  sagemaker is a namespace package: ['/usr/local/lib/python3.9/site-packages/sagemaker']
  its modules: ['ai_registry', 'core', 'lineage', 'mlops', 'serve', 'train']
  >>> import sagemaker; from sagemaker.tensorflow import TensorFlowModel
  ModuleNotFoundError: No module named 'sagemaker.tensorflow'
  >>> from sagemaker import get_execution_role
  ImportError: cannot import name 'get_execution_role' from 'sagemaker' (…)
  >>> from sagemaker.serializers import JSONSerializer
  ModuleNotFoundError: No module named 'sagemaker.serializers'
  ```
  On the capture machine the unpinned build spent more than 13 minutes in `pipenv lock` and then ran out of disk; it was not kept. Fix: `sagemaker = "<3"` (`laptop/24`):
  ```
  -sagemaker = "*"
  +sagemaker = "<3"
  ```
  `"*"` is a constraint that allows anything; `"<3"` keeps you on the major version the code was written for.
- **With both fixes** (`laptop/25`, *captured*, build log trimmed):
  ```
  [+] Building 400.6s (19/19) FINISHED
   …
   => [13/14] RUN cd /app && pipenv lock && pipenv sync                       334.7s
   …
  Container is running!!!
  Testing AWS connectivity...

  aws: [ERROR]: An error occurred (NoCredentials): Unable to locate credentials. You can configure credentials by running "aws login".
  Launching subshell in virtual environment...
  (app) app@6fd3f31d3da7:/app$ python --version; which python pipenv aws
  Python 3.9.5
  /home/app/.local/share/virtualenvs/app-4PlAip0Q/bin/python
  …
  (app) app@6fd3f31d3da7:/app$ pip list 2>/dev/null | grep -i -E "^(tensorflow|keras|sagemaker|sagemaker-core|boto3|numpy|pillow) "
  boto3                        1.42.97
  keras                        3.10.0
  …
  sagemaker                    2.257.7
  sagemaker-core               1.0.78
  tensorflow                   2.18.0
  ```
  The entrypoint has no `set -e`: a failed identity check prints its error and the shell opens anyway. With your key, you see your identity JSON instead. The image is 4.01 GB (`laptop/26`).
- *(extra)* `python cli.py --help` (`laptop/25`, *captured*):
  ```
  usage: cli.py [-h] [--prepare] [--deploy] [--predict] [--test] [--delete]

  Data Collector CLI
  …
    --prepare   Prepare model and save model to GCS Bucket
    --deploy    Deploy saved model to Vertex AI
    --predict   Make prediction using the endpoint from Vertex AI
    --test      Test deployment to Vertex AI
  ```
  Leftover words from the GCP version of this repo: the code talks to S3 and SageMaker.

**A6 · Prepare** (A:110-117): `python cli.py --prepare`. README A lists four actions; the code does five, in this order (`cli.py:66-123`): (1) `s3_client.create_bucket(...)` (`:71-82`), (2) download and unzip the release into `./artifacts/` (`:84-88`), (3) load the `.keras` (`:90-95`), (4) `prediction_model.export(...)` into `artifacts/model-mobilenetv2_train_base_True.v1/1` (`:98-112`), (5) tar `1/` into `model.tar.gz` and upload it to `<BEST_MODEL>/model.tar.gz` (`:114-123`).
- *Captured* without credentials (`laptop/27`): the command stops at step 1, before anything is downloaded.
  ```
  Prepare model and save model to GCS Bucket
  …
  │ /app/cli.py:73 in prepare
  │ ❱  73 │   │   │   s3_client.create_bucket(Bucket=S3_MODELS_BUCKET_NAME)
  …
  NoCredentialsError: Unable to locate credentials
  (app) app@974c4bf53d84:/app$ ls -la artifacts
  ls: cannot access 'artifacts': No such file or directory
  ```
  boto3 also prints a `PythonDeprecationWarning` (it drops Python 3.9 in 2026); harmless here.
- *Captured, local half only* (`laptop/40`, *extra · capture stub*: `cli.py`'s own `prepare()` in the same image, with the S3 client replaced by a stub that sends nothing):
  ```
  [capture stub] create_bucket({'Bucket': 'your-models-bucket-placeholder'}) NOT sent: no AWS account in this recording
  Using Keras 3 export()
  Saved artifact at './artifacts/model-mobilenetv2_train_base_True.v1/1'. The following endpoints are available:

  * Endpoint 'serve'
    args_0 (POSITIONAL_ONLY): List[TensorSpec(shape=(None, 224, 224, 3), dtype=tf.float32, name='input')]
  Output Type:
    TensorSpec(shape=(None, 4), dtype=tf.float32, name=None)
  …
  Uploading model to s3://your-models-bucket-placeholder/model-mobilenetv2_train_base_True.v1/model.tar.gz
  RuntimeError: [capture stub] upload_file(...) NOT sent: no AWS account in this recording
  ```
  With your key, the last line is instead `Model uploaded successfully to S3` (*expected*, `cli.py:123`).
- *(extra)* What the export wrote (`laptop/41`, `42`, `43`, *captured*):
  ```
  $ tar tzvf artifacts/model-mobilenetv2_train_base_True.v1/model.tar.gz
  drwxr-sr-x app/app         0 1970-01-01 00:00:00 1/
  drwxr-sr-x app/app         0 1970-01-01 00:00:00 1/assets/
  -rw-r--r-- app/app        57 1970-01-01 00:00:00 1/fingerprint.pb
  -rw-r--r-- app/app   1713230 1970-01-01 00:00:00 1/saved_model.pb
  drwxr-sr-x app/app         0 1970-01-01 00:00:00 1/variables/
  -rw-r--r-- app/app  19438488 1970-01-01 00:00:00 1/variables/variables.data-00000-of-00001
  -rw-r--r-- app/app     29718 1970-01-01 00:00:00 1/variables/variables.index
  $ docker run --rm --entrypoint pipenv -v "$PWD":/app model-deployment-cli-aws run saved_model_cli show --dir /app/artifacts/model-mobilenetv2_train_base_True.v1/1 --tag_set serve --signature_def serving_default
  …
  The given SavedModel SignatureDef contains the following input(s):
    inputs['input'] tensor_info:
        dtype: DT_FLOAT
        shape: (-1, 224, 224, 3)
  …
  The given SavedModel SignatureDef contains the following output(s):
    outputs['output_0'] tensor_info:
        dtype: DT_FLOAT
        shape: (-1, 4)
  …
  Method name is: tensorflow/serving/predict
  ```
  Everything sits under `1/` (the version folder TensorFlow Serving expects), the input is floats, and there are **four** outputs.

**A7 · Deploy** (A:119-129): `python cli.py --deploy`. Under the hood (`cli.py:126-185`): a `sagemaker.Session()`; the role from `SAGEMAKER_ROLE`; `TensorFlowModel(model_data=…, framework_version="2.13", name="model-mobilenetv2-train-base-True-v1")` (`:151-159`); an endpoint name with a UTC timestamp (`:163-167`); `.deploy(initial_instance_count=1, instance_type="ml.m5.xlarge", …)` (`:168-174`), which waits until the endpoint is in service; then `endpoint_config.json` (`:180-185`).
- *Captured* without credentials (`laptop/28`):
  ```
  Deploy model
  …
  Deploying model to SageMaker endpoint...
  │ /app/cli.py:168 in deploy
  …
  NoCredentialsError: Unable to locate credentials
  ```
- *Expected* with your key (from the code's prints; README A shows no sample): the SDK's progress dashes for several minutes, then `Model deployed successfully!`, `Endpoint name: model-mobilenetv2-train-base-True-v1-endpoint-<timestamp>` and `Endpoint configuration saved to endpoint_config.json`. Check *(extra)*: SageMaker → Endpoints shows it `InService`.

**A8 · Predict** (A:131-148): `python cli.py --predict`. Under the hood (`cli.py:188-239`): read `endpoint_config.json`; list `data/*.jpg` and `data/*.jpeg` (all eight); draw five indices **with replacement** (`np.random.randint`, unseeded, `:216`); for each photo: RGB, resize 224×224, `/255.0`, send `{"instances": [arr.tolist()]}`, print the result, the argmax and the label.
- *Captured* without an endpoint (`laptop/29`); each call's error is caught and printed, so the command exits 0:
  ```
  Predict using endpoint
  Error: endpoint_config.json not found. Please deploy the model first.
  You can also manually set the endpoint name in the code.
  image_files: ['data/brie-1.jpg', 'data/gruyere-2.jpg', 'data/parmigiano-2.jpg', 'data/brie-2.jpg', 'data/parmigiano-1.jpg']
  Image: data/parmigiano-2.jpg
  Error invoking endpoint: Unable to locate credentials
  Make sure the endpoint 'model-mobilenetv2-train-base-True-v1-endpoint' exists and is in service
  Image: data/brie-2.jpg
  …
  ```
  `image_files:` prints the first five names of an unsorted list, not the five drawn. The fallback name (no timestamp) never exists: if you see it, `endpoint_config.json` is missing (Exercise C10).
- *Recorded*: README A's own output against a live endpoint (A:137-147), trimmed:
  ```
  Image: data/brie-2.jpg
  Result: {'predictions': [[0.0887121782, 0.0439011417, 0.867386699]]}
  [0.0887121782, 0.0439011417, 0.867386699] 2
  Label:    brie
  Image: data/gouda-1.jpg
  Result: {'predictions': [[0.986440122, 0.00689249625, 0.0066674049]]}
  [0.986440122, 0.00689249625, 0.0066674049] 0
  Label:    gouda
  ```
  Three numbers and index 0 = gouda: that output comes from an older three-class model. Today's release has **four** outputs, and `cli.py:42` maps 0 = parmigiano.
- *Captured with a local stand-in* (`laptop/45-47`, *extra · local stand-in, not SageMaker*): the exported folder served by the public `tensorflow/serving:2.13.1` image, and `cli.py`'s own `predict()` with only the SageMaker client swapped for a plain HTTP POST of the same JSON. The server loaded the TF 2.18 export with one warning about an unknown `debug_name` attribute (`laptop/46`). Five predictions, four numbers each:
  ```
  …
  Image: data/gruyere-1.jpg
  Result: {'predictions': [[0.0575376712, 0.699525177, 0.0486632437, 0.194273904]]}
  [0.0575376712, 0.699525177, 0.0486632437, 0.194273904] 1
  Label:    gruyere
  Image: data/parmigiano-1.jpg
  Result: {'predictions': [[0.0162430592, 0.00305783958, 0.97726506, 0.00343393325]]}
  [0.0162430592, 0.00305783958, 0.97726506, 0.00343393325] 2
  Label:    brie
  …
  Image: data/gouda-2.jpeg
  Result: {'predictions': [[0.00427136, 0.18224588, 0.0100982478, 0.803384542]]}
  [0.00427136, 0.18224588, 0.0100982478, 0.803384542] 3
  Label:    gouda
  ```
  `parmigiano-1` → `brie` at 0.977 is a real mistake of the released model (its own `model_metrics.json` reports an accuracy of 0.724). A confident answer is not a correct one.

**A9 · Clean up** (A:150-176). Three ways: the console (SageMaker → Endpoints → Delete), the three `aws sagemaker delete-*` commands, or `python cli.py --delete`.
- *Captured* (`laptop/30`): `Delete endpoint, model, and S3 artifacts`, then `NoCredentialsError: Unable to locate credentials` at its first SageMaker call (`cli.py:270`).
- *Captured*, the README's CLI line pasted as written (`laptop/31`):
  ```
  $ aws sagemaker delete-endpoint --endpoint-name <your-endpoint-name>
  bash: -c: line 1: syntax error near unexpected token `newline'
  ```
  `<` and `>` are shell redirections: replace the placeholder with the real name first (`laptop/32`, with a placeholder name: `(NoCredentials): Unable to locate credentials`).
- `--delete` removes the endpoint in `endpoint_config.json`, every endpoint configuration whose name contains `model-mobilenetv2-train-base-True-v1`, the model, every S3 object under `model-mobilenetv2_train_base_True.v1/`, and the local `endpoint_config.json` (`cli.py:242-312`). It does not delete the bucket, and it knows only the **last** deploy: run `--deploy` twice and one endpoint keeps billing (Exercise B7).

### Part B — `ml-workflow-aws` (README B)

**B1 · Clone, services, bucket** (B:15-30). *Captured* (`laptop/50-52`): `Cloning into 'ml-workflow-aws'...`, `f165c6e17895d3d6c33a150d349f4b2649c807db 2025-08-19 08:50:13 -0400 Migrate ml-workflow from GCP to AWS`, and the tree: four folders under `src/` (`data-collector`, `data-processor`, `model-training`, `workflow`), of which only the collector, the trainer and the workflow have a `Pipfile.lock`. Clone it next to `model-deployment-aws`: `../../../persistent-folder` from any `src/<stage>` folder is then a folder beside both clones.

**B2 · IAM user, access key, AWS CLI, configure** (B:33-63). *Captured* with obviously fake placeholder keys (`laptop/55`, `56`):
```
$ aws configure
AWS Access Key ID [None]: PLACEHOLDER_NOT_A_REAL_ACCESS_KEY
AWS Secret Access Key [None]: PLACEHOLDER_NOT_A_REAL_SECRET_KEY_000000000000
Default region name [us-east-1]:
Default output format [json]:
$ aws configure list
NAME       : VALUE                    : TYPE             : LOCATION
profile    : <not set>                : None             : None
access_key : ****************_KEY     : shared-credentials-file :
secret_key : ****************0000     : shared-credentials-file :
region     : us-east-1                : config-file      : ~/.aws/config
```
You type the two values from the downloaded `.csv` (B:49).

**B3 · Test configuration** (B:65-69). *Captured* (`laptop/53` without keys, `laptop/57` with the placeholders):
```
$ aws sts get-caller-identity
aws s3 ls

aws: [ERROR]: An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: The security token included in the request is invalid.

aws: [ERROR]: An error occurred (InvalidAccessKeyId) when calling the ListBuckets operation: The AWS Access Key Id you provided does not exist in our records.
```
With no keys at all both say `Unable to locate credentials`. With your real key you see your identity and your buckets.

**B4 · IAM roles** (B:71-81). Console only. Type the names exactly: `CheeseAppSageMakerExecutionRole` and `CheeseAppLambdaExecutionRole` (§2).

**B5 · Data collector** (B:88-100), in `src/data-collector`: `sh docker-shell.sh`, then the `--search` command.
- *Captured* before any key existed (`laptop/54`): the script's own check stops it, nothing is built.
  ```
  $ sh docker-shell.sh
  AWS not configured. Run: aws configure
  ```
  This is what a Mac shows. On Debian/Ubuntu, `sh` is dash, which does not understand `[[ … ]]`: the check prints `[[: not found` and the script builds anyway (tested by the digest's author with the same structure; not captured here). Run `bash docker-shell.sh` on Linux.
- *Captured* with the placeholder keys (`laptop/60`, trimmed from 666 lines):
  ```
  [+] Building 40.4s (11/11) FINISHED
  …
  root@7ee040c53cfb:/app# python cli.py --search --nums 10 --query "brie cheese" "gouda cheese" "gruyere cheese" "parmigiano cheese"
  CLI Arguments: Namespace(search=True, nums=10, query=['brie cheese', 'gouda cheese', 'gruyere cheese', 'parmigiano cheese'], bucket='')
  S3_BUCKET_NAME: cheese-app-ml-workflow-demo
  Searching for: brie cheese
  [%] Downloading Images to /persistent/dataset/raw/brie cheese
  [!!]Indexing page: 1
  [%] Indexed 10 Images on Page 1.
  …
  [%] Downloading Image #1 from https://…
  [%] File Downloaded !
  …
  [%] Done. Downloaded 10 images.
  Searching for: gouda cheese
  …
  [%] Done. Downloaded 10 images.
  uploading file /persistent/dataset/raw.zip
  …
  boto3.exceptions.S3UploadFailedError: Failed to upload /persistent/dataset/raw.zip to cheese-app-ml-workflow-demo/raw.zip: An error occurred (InvalidAccessKeyId) when calling the CreateMultipartUpload operation: …
  root@7ee040c53cfb:/app# for d in /persistent/dataset/raw/*; do echo "$(ls "$d" | wc -l) $d"; done
  10 /persistent/dataset/raw/brie cheese
  10 /persistent/dataset/raw/gouda cheese
  10 /persistent/dataset/raw/gruyere cheese
  10 /persistent/dataset/raw/parmigiano cheese
  ```
  The scrape is real: 40 images from Bing on 2026-11-05, with a few skipped links on the way (`[!] Issue getting: …`: an HTTP 404 or 403, an invalid image). The prompt is `root@…#`: the collector's two-mode entrypoint opened bash because no arguments were given. Only the upload needs AWS.
- *(extra)* On the laptop, Docker created the missing mount folder, **owned by root** (`laptop/61`, *captured*):
  ```
  drwxr-sr-x    3 root     root          4096 Nov  5 05:12 persistent-folder
  ```
  The collector and processor run as root and don't mind; the trainer runs as `app` and will (B7). Create the folder yourself before the first run.

**B6 · Data processor** (B:107-120), in `src/data-processor`: `sh docker-shell.sh`, then `python cli.py --clean` and `python cli.py --prepare`.
- As written on x86_64 (`laptop/65`, *captured*): `exec /bin/sh: exec format error` at the first `RUN` (line 31 builds arm64). Swap to line 29 (`laptop/66`). The image locks its dependencies at build time (no lock in the repo): *captured* `Locking dependencies...`, `✔ Success!`, `Installing dependencies from Pipfile.lock`, step `DONE 183.8s` (`laptop/67`).
- *Captured* (`laptop/68`, trimmed):
  ```
  root@fa32e95fc9d7:/app# python cli.py --clean
  S3_BUCKET_NAME: cheese-app-ml-workflow-demo
  Cleaning dataset
  Labels: ['parmigiano cheese', 'gruyere cheese', 'brie cheese', 'gouda cheese']
  Processing label: parmigiano cheese
  difPy preparing files: [100%]
  difPy searching files: [100%]
  Search Results:
   {}

  Lower Quality Files:
   []
  …
  uploading file /persistent/dataset/clean.zip
  …
  boto3.exceptions.S3UploadFailedError: Failed to upload /persistent/dataset/clean.zip to cheese-app-ml-workflow-demo/clean.zip: An error occurred (InvalidAccessKeyId) …
  root@fa32e95fc9d7:/app# python cli.py --prepare
  S3_BUCKET_NAME: cheese-app-ml-workflow-demo
  Prepare dataset for training
  Label Directories: ['parmigiano cheese', 'gruyere cheese', 'brie cheese', 'gouda cheese']
  …
  Full size of the dataset: 40
  train_xy count: 32
  validate_xy count: 8
  Creating shard: 0  from records: 0 to 33
  /persistent/dataset/tfrecords/train_0000.tfrecords
  Total shards created: 1
  Creating shard: 0  from records: 0 to 9
  /persistent/dataset/tfrecords/val_0000.tfrecords
  Total shards created: 1
  uploading file /persistent/dataset/tfrecords.zip
  …
  boto3.exceptions.S3UploadFailedError: Failed to upload /persistent/dataset/tfrecords.zip to cheese-app-ml-workflow-demo/tfrecords.zip: …
  ```
  `--clean` used the local `raw/` folder the collector had just filled (both containers mount the same `persistent-folder`), so it did not need `raw.zip` from S3. difPy found no duplicates among these 40 images, so `clean/` also has 10 per label. The two TFRecord files are 4.8 MB and 1.2 MB. Versions in this image at the time of recording: TensorFlow 2.13.1, difPy 4.2.1, dask 2026.8.0.
- Labels come from the folder names, i.e. from your `--query` strings: `tfrecords.py:11-16` maps exactly `"parmigiano cheese"` → 0, `"gruyere cheese"` → 1, `"brie cheese"` → 2, `"gouda cheese"` → 3. Any other query makes `--prepare` fail with a `KeyError` (Exercise B5).

**B7 · Model training** (B:126-145), in `src/model-training`: `sh docker-shell.sh`; local training; `sh package-trainer.sh`; `python cli.py --train`.
- As written on x86_64 (`laptop/70`): `exec format error` again (line 32); swap to line 30. The image installs from its committed lock (`pipenv sync`, 70.0 s, `laptop/72`): *captured* `Python 3.11.18`, tensorflow 2.20.0, keras 3.11.2, sagemaker 2.250.0, boto3 1.40.11 (`laptop/73`). This image is not affected by the SDK 3 problem.
- **Local training** (B:136), *captured* (`laptop/73`, trimmed):
  ```
  (app) app@caf8386567eb:/app$ python -m package.trainer.task --epochs=1 --batch_size=4 --bucket_name=cheese-app-ml-workflow-demo
  …
  tensorflow version 2.20.0
  …
  Number of replicas: 1
  …
  TFRecords found at /persistent/dataset/tfrecords
  Downloading data from https://storage.googleapis.com/tensorflow/keras-applications/mobilenet_v2/mobilenet_v2_weights_tf_dim_ordering_tf_kernels_1.0_224_no_top.h5
  …
  │ dense (Dense)                        │ (None, 128)                 │         163,968 │
  │ dense_1 (Dense)                      │ (None, 3)                   │             387 │
  …
  8/8 ━━━━━━━━━━━━━━━━━━━━ 5s 195ms/step - accuracy: 0.4062 - loss: 108.4501 - val_accuracy: 0.6250 - val_loss: 107.7770
  Training execution time (mins) 0.07589625120162964
  Change model signature and save
  …
  File "/app/package/trainer/task.py", line 312, in <module>
    os.makedirs(ARTIFACT_URI, exist_ok=True)
  …
  PermissionError: [Errno 13] Permission denied: '/persistent/model'
  ```
  Three things to read here. (1) The last layer has **3** outputs: `task.py:68` sets `num_classes = 3`, while the processor writes labels 0–3, so gouda (label 3) gets an all-zero target (§9 erratum 6; fix: `num_classes = 4`). (2) The loss of about 108 is mostly the model's L1 regularization terms, not cross-entropy; one epoch on 32 images is a smoke test of the code path, not a useful model. (3) The save fails because this container runs as `app` (uid 1000) and the root-owned `persistent-folder` from B5 refuses it. That is a Linux effect (Docker Desktop on a Mac maps the mount to your user). Fix on the host: `sudo chown -R $USER ../../../persistent-folder`, or create the folder before B5. The successful save after that fix was not captured; `task.py:303-322` shows what it writes (`/persistent/model/1` with the bytes-in signature).
  Keras also warns `Your input ran out of data` (the dataset is smaller than the steps it expected) and that the inputs' structure does not match when the signature is traced; both are harmless here.
- **Remote training** (B:138-139), *captured* (`laptop/73`):
  ```
  (app) app@caf8386567eb:/app$ sh package-trainer.sh
  package/
  package/trainer/
  package/trainer/task.py
  package/trainer/__init__.py
  package/setup.py
  package/setup.cfg
  package/PKG-INFO
  upload failed: ./trainer.tar.gz to s3://cheese-app-ml-workflow-demo/cheese-app-trainer.tar.gz An error occurred (InvalidAccessKeyId) when calling the PutObject operation: …
  (app) app@caf8386567eb:/app$ python cli.py --train
  …
  Train Model
  …
  RuntimeError: Unable to derive SageMaker execution role. Please ensure CheeseAppSageMakerExecutionRole exists
  in your AWS account.
  ```
  `trainer.tar.gz` is 3,632 bytes: the trainer package is small, the heavy parts are AWS's training image. With your key, `--train` submits `cheese-<8 chars>` (entry point `package/trainer/task.py` inside that tarball, `ml.m5.xlarge`, TF 2.13, 15 epochs, batch 16; `src/model-training/cli.py:53-74`) and returns at once (`wait=False`). Follow it in the console (B:141-145).

**B8 · Build & push images** (B:152-203). README B says "This step has already been done for this tutorial" (B:153), but the pipeline pulls `cheese-app-data-collector:latest` and `cheese-app-data-processor:latest` from your own account's ECR (`src/workflow/cli.py:35-36`): you must push both. They must be **amd64**: SageMaker runs amd64 images (README B:161 builds with `--platform=linux/amd64/v2` on M1/2 Macs).
- *Captured*, the variable block pasted as written plus step 7 (`laptop/80`):
  ```
  $ export REGION=us-east-1 [YOUR DEVELOPMENT REGION]
  export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  export REPO=cheese-app-data-collector  # or cheese-app-data-processor
  export TAG=latest
  export ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO:$TAG"
  echo "ECR URI: $ECR_URI"
  bash: line 1: export: `[YOUR': not a valid identifier
  bash: line 1: export: `REGION]': not a valid identifier

  aws: [ERROR]: An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: The security token included in the request is invalid.
  ECR URI: .dkr.ecr.us-east-1.amazonaws.com/cheese-app-data-collector:latest
  ```
  Two lessons: the bracket note is not part of the command (`REGION` is still set, but bash complains), and when the account lookup fails nothing stops: the URI just starts with a dot. Always read step 7's output.
- *Captured*, step 2 (`laptop/81`): `aws: [ERROR]: An error occurred (UnrecognizedClientException) when calling the CreateRepository operation: The security token included in the request is invalid.` and exit status **0**: `|| true` exists so the command can be re-run when the repository already exists, but it also hides every other error.
- Steps 1 and 3–6 (pull, login, tag, push, list) need an account and a Docker Hub image; they were not run. With an account, step 6 prints a table with the `latest` tag.

**B9 · The workflow container and one Processing job** (B:210-224), in `src/workflow`: `sh docker-shell.sh`, then `python cli.py --data_collector`.
- **SDK 3 again.** The Dockerfile copies only the `Pipfile` and runs `pipenv install` (`src/workflow/Dockerfile:40-42`), so the committed `Pipfile.lock` (sagemaker 2.250.0) never enters the image (`laptop/87`, *captured*: `Pipfile.lock pins sagemaker ==2.250.0 and boto3 ==1.40.11`; the build log says `Pipfile.lock not found, creating...`, `laptop/89`). Unpinned, it resolves **sagemaker 3.29.0** at the time of recording (`laptop/85`), and the imports fail (`laptop/86`, *captured*):
  ```
  >>> from sagemaker.processing import ProcessingInput, ProcessingOutput, Processor
  ModuleNotFoundError: No module named 'sagemaker.processing'
  >>> from sagemaker.workflow.pipeline import Pipeline
  ModuleNotFoundError: No module named 'sagemaker.workflow'
  >>> from sagemaker.tensorflow import TensorFlow
  ModuleNotFoundError: No module named 'sagemaker.tensorflow'
  ```
  Same fix as Part A: `sagemaker = "<3"` in `src/workflow/Pipfile` (`laptop/88`), which gave 2.257.7.
- *Captured* with the pin and the placeholder keys (`laptop/90`, trimmed):
  ```
  Container is running!!!
  AWS Region: us-east-1
  S3 Bucket: cheese-app-ml-workflow-demo
  Package URI: s3://cheese-app-ml-workflow-demo

  aws: [ERROR]: An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: The security token included in the request is invalid.
  …
  (app) app@4fa2d10fae99:/app$ python cli.py --data_collector
  …
  INFO:botocore.credentials:Found credentials in environment variables.
  │ /app/cli.py:32 in <module>
  │    31 sts_client = boto3.client('sts')
  │ ❱  32 ACCOUNT_ID = sts_client.get_caller_identity()['Account']
  …
  ClientError: An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: The
  security token included in the request is invalid.
  ```
  `cli.py` looks up your account id at import time (it needs it for the ECR image URIs, `:31-36`), so **every** flag stops on this line without a valid key: the capture shows the same traceback for `--pipeline`, `--data_processor`, `--model_training` and `--model_deploy`. Also captured: `bash: docker: command not found` inside this container; the Docker socket is mounted (`docker-shell.sh:34`) but the image has no Docker CLI, and nothing in the tutorial needs it.
- *Expected* with your key: `processor.run(…, logs=True, wait=True)` (`src/workflow/cli.py:44-80`) starts `cheese-app-data-collector-<8 chars>` on `ml.t3.medium` and streams the job's log (the same scraper output as B5, from AWS's machine) until the job ends; it scrapes 10 images per query (`:66`), the pipeline 50 (`:185`).

**B10 · The pipeline** (B:226-240): `python cli.py --pipeline`. Under the hood: §3.5–3.7. With your key it prints `Using derived SageMaker execution role: arn:aws:iam::<ACCOUNT_ID>:role/CheeseAppSageMakerExecutionRole`, `Using derived Lambda execution role: …`, then `SageMaker Pipeline started: arn:aws:sagemaker:<region>:<ACCOUNT_ID>:pipeline/cheese-pipeline/execution/<id>` and returns.
- *Captured* (`laptop/90`): stops at `cli.py:32` like every flag.
- *Captured, built offline* (`laptop/92`, *extra · built offline, not sent*: `cli.py`'s own `pipeline()` in the workflow image, account lookups answered with a placeholder, `upsert()` replaced by printing the definition), trimmed:
  ```
  Using derived SageMaker execution role: arn:aws:iam::<ACCOUNT_ID>:role/CheeseAppSageMakerExecutionRole
  …
  UserWarning: Running within a PipelineSession, there will be No Wait, No Logs, and No Job being started.
  …
  Using derived Lambda execution role: arn:aws:iam::<ACCOUNT_ID>:role/CheeseAppLambdaExecutionRole
  …
        "Name": "DataCollector",
        "Type": "Processing",
  …
        "CacheConfig": {
          "Enabled": true,
          "ExpireAfter": "30d"
  …
        "Name": "DataProcessor",
        "Type": "Processing",
  …
                  "Get": "Steps.DataCollector.ProcessingOutputConfig.Outputs['raw-data'].S3Output.S3Uri"
  …
        "Name": "ModelTraining",
        "Type": "Training",
  …
                    "Get": "Steps.DataProcessor.ProcessingOutputConfig.Outputs['tfrecords'].S3Output.S3Uri"
  …
        "Name": "CreateModel-CreateModel",
        "Type": "Model",
  …
              "Get": "Steps.ModelTraining.ModelArtifacts.S3ModelArtifacts"
  …
        "Name": "DeployModel",
        "Type": "Lambda",
  …
            "Get": "Steps.CreateModel-CreateModel.ModelName"
  …
  [capture stub] Pipeline.upsert() and start() NOT sent: no AWS account in this recording
  ```
  (The capture used an all-zero placeholder account where `<ACCOUNT_ID>` stands.) The `Get` entries are the property references from §3.6: this JSON, not a YAML file, is what SageMaker receives. "No Wait, No Logs" is the SDK telling you that inside a pipeline definition `processor.run(...)` only *describes* a job. The real definition also carries image URIs from AWS's public Deep Learning Containers registry; that account number is AWS's, not yours.
- **In the console** (B:234): SageMaker Unified Studio → Build → ML Pipelines. README B's two images show the five boxes running, then all green.
- **Green is not ready.** `DeployModel` returns as soon as the Lambda has asked for the endpoint (`deploy_model_lambda.py:53-65`); the endpoint is still `Creating`. Wait for `InService` before calling it (A:191).

**B11 · Test specific components** (B:243-248): `--data_collector`, `--data_processor` (a Processing job with `--clean --prepare`), `--model_training` (`model.py:51-100`: like `--train`, but it waits), `--model_deploy` (`model.py:103-178`: finds the newest `model-output/cheese-*/` folder and deploys it to a **new** endpoint `cheese-app-endpoint-<8 chars>`). *Captured*: each stops at `cli.py:32` (`laptop/90`). Note that `--model_deploy` only sees jobs named `cheese-*` (from `--train`/`--model_training`), not the pipeline's training jobs, and each call leaves one more endpoint billing.

**B12 · Clean up** *(not in README B)*. Use the checklist's last section. `aws sagemaker list-endpoints` should come back empty; slide 41's "DELETE!!" is the lecture's version of this step.

---

## 5. Code tour

```
model-deployment-aws/                 (main @ 077f4db)
  Dockerfile            ubuntu:20.04 + AWS CLI v2 (by architecture) + docker-ce + python3.9 + pipenv;
                        USER app (uid 1000); RUN pipenv lock && pipenv sync   (no lock in git: .gitignore:68)
  Pipfile               boto3, sagemaker ("*": pin it "<3"), pillow, tensorflow==2.18.0, numpy, requests; python 3.9
  docker-shell.sh       bucket, role ARN, region (7-9); arm64 build (19); mounts ./ and ~/.aws; no key variables
  docker-entrypoint.sh  "Container is running!!!"; aws sts get-caller-identity; pipenv shell
  cli.py                --prepare / --deploy / --predict / --delete   (--test is defined but does nothing)
  data/                 8 sample photos (2 per cheese; gouda-2 is .jpeg)

ml-workflow-aws/src/                  (main @ f165c6e)
  data-collector/   python:3.11-slim, root, committed lock; two-mode entrypoint; Bing scraper -> raw.zip
  data-processor/   python:3.11-slim, root, lock made at build; difPy + JPEG check -> clean.zip; TFRecords -> tfrecords.zip
  model-training/   python:3.11-slim, USER app, committed lock (TF 2.20, sagemaker 2.250.0); pipenv shell
    package/trainer/task.py   MobileNetV2 + Dense(128) + Dense(num_classes=3!); bytes-in signature; saves <dir>/1
    package-trainer.sh        tar package/ -> trainer.tar.gz -> $S3_PACKAGE_URI/cheese-app-trainer.tar.gz
    cli.py                    a standalone SageMaker training job (wait=False)
  workflow/         python:3.11-slim, AWS CLI v2 (x86_64 only), pipenv install from the Pipfile alone ("*": pin it)
    cli.py                    --data_collector / --data_processor / --model_training / --model_deploy / --pipeline
    model.py                  role helpers, model_training(), model_deploy()
    deploy_model_lambda.py    the Lambda handler: new endpoint config, then create or update the endpoint
```

**1. The export and the version folder** (`model-deployment-aws/cli.py:106-117`):
```python
    # Export using Keras 3 export() if available, otherwise fall back to tf.saved_model.save
    if hasattr(prediction_model, "export"):
        print("Using Keras 3 export()")
        prediction_model.export(model_export_path)
    else:
        print("Using tf.saved_model.save()")
        tf.saved_model.save(prediction_model, model_export_path)

    # Create tar.gz archive for SageMaker
    model_tar_path = f"{local_model_dir}/model.tar.gz"
    with tarfile.open(model_tar_path, "w:gz") as tar:
        tar.add(model_export_path, arcname="1")
```
`export()` keeps the model's own float input; `arcname="1"` puts the version folder at the top of the tarball (`laptop/42`).

**2. Model, then endpoint** (`model-deployment-aws/cli.py:151-174`):
```python
    tensorflow_model = TensorFlowModel(
        model_data=model_data,
        role=role,
        framework_version="2.13",
        sagemaker_session=sagemaker_session,
        name=BEST_MODEL.replace(".", "-").replace(
            "_", "-"
        ),  # SageMaker naming requirements
    )

    # Deploy model to endpoint
    print("Deploying model to SageMaker endpoint...")
    # Create a timestamped endpoint name to avoid collisions
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    endpoint_name = (
        BEST_MODEL.replace(".", "-").replace("_", "-") + f"-endpoint-{ts}"
    )
    predictor = tensorflow_model.deploy(
        initial_instance_count=1,
        instance_type="ml.m5.xlarge",
        endpoint_name=endpoint_name,
        serializer=JSONSerializer(),
        deserializer=JSONDeserializer(),
    )
```
`framework_version="2.13"` chooses the serving image; the timestamp is why every `--deploy` creates another endpoint; `initial_instance_count=1` is the always-on instance.

**3. Client-side preprocessing and the request** (`model-deployment-aws/cli.py:221-228`):
```python
        with Image.open(img_path) as img:
            img = img.convert("RGB").resize((224, 224))
            arr = np.asarray(img, dtype=np.float32) / 255.0

        payload = {"instances": [arr.tolist()]}

        try:
            result = predictor.predict(payload)
```

**4. The bytes-in signature** (`ml-workflow-aws/src/model-training/package/trainer/task.py:276-301`, then `:314-318`): the lecture's slide 14 in this repo.
```python
# Preprocess Image
def preprocess_image(bytes_input):
    decoded = tf.io.decode_jpeg(bytes_input, channels=3)
    decoded = tf.image.convert_image_dtype(decoded, tf.float32)
    resized = tf.image.resize(decoded, size=(224, 224))
    return resized


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


model_call = tf.function(model.call).get_concrete_function(
    [tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32, name="model_input")]
)
```
```python
tf.saved_model.save(
    model,
    ARTIFACT_URI,
    signatures={"serving_default": serving_function},
)
```

**5. The callable container** (`ml-workflow-aws/src/data-collector/docker-entrypoint.sh:3-8`):
```bash
set -euo pipefail
if [[ $# -eq 0 ]]; then
  exec bash            # local interactive shell
else
  exec "$@"
fi
```

**6. An edge is a property reference** (`ml-workflow-aws/src/workflow/cli.py:212-223`, and `:262-268` for training):
```python
    step_process = ProcessingStep(
        name="DataProcessor",
        processor=data_processor,
        job_arguments=["--clean", "--prepare", "--bucket", S3_BUCKET_NAME],
        inputs=[
            ProcessingInput(
                input_name="raw-data",
                source=step_collect.properties.ProcessingOutputConfig
                    .Outputs["raw-data"].S3Output.S3Uri,
                destination="/opt/ml/processing/input",
            )
        ],
```
```python
    step_train = TrainingStep(
        name="ModelTraining",
        estimator=estimator,
        inputs={
            "training": step_process.properties.ProcessingOutputConfig
                .Outputs["tfrecords"].S3Output.S3Uri
        },
```

**7. Build, upsert, start** (`ml-workflow-aws/src/workflow/cli.py:320-328`):
```python
    sm_pipeline = Pipeline(
        name="cheese-pipeline",
        steps=[step_collect, step_process, step_train, step_create_model, step_deploy_lambda],
        sagemaker_session=sm_pipe_sess,
    )

    sm_pipeline.upsert(role_arn=role)
    execution = sm_pipeline.start()
    print(f"SageMaker Pipeline started: {execution.arn}")
```
Lines 294–303, just above, create `Lambda(function_name=f"sagemaker-deploy-model-lambda-{current_time}", …)`: a new function name on every run, created in your account while `upsert` generates the definition.

**8. Create or update** (`ml-workflow-aws/src/workflow/deploy_model_lambda.py:39-58`):
```python
    # Check if an endpoint exists and update or create it
    list_endpoints_response = sm_client.list_endpoints(
        SortBy="CreationTime",
        SortOrder="Descending",
        NameContains=endpoint_name,
    )
    print(f"list_endpoints_response: {list_endpoints_response}")

    if len(list_endpoints_response["Endpoints"]) > 0:
        print("Updating Endpoint with new Endpoint Configuration")
        update_endpoint_response = sm_client.update_endpoint(
            EndpointName=endpoint_name, EndpointConfigName=endpoint_config_name
        )
        print(f"update_endpoint_response: {update_endpoint_response}")
    else:
        print("Creating Endpoint")
        create_endpoint_response = sm_client.create_endpoint(
            EndpointName=endpoint_name, EndpointConfigName=endpoint_config_name
        )
        print(f"create_endpoint_response: {create_endpoint_response}")
```
`NameContains` is a substring match: `cheese-app-endpoint-<8 chars>` from `--model_deploy` matches too (§6 #13).

**9. The real data handoff** (`ml-workflow-aws/src/data-collector/cli.py:63-65`; the processor does the same with `clean.zip` and `tfrecords.zip`, `src/data-processor/cli.py:68`, `:95`):
```python
        # Upload to S3 bucket
        print("uploading file", zip_file)
        s3_client.upload_file(zip_file, S3_BUCKET_NAME, "raw.zip")
```

**Small facts worth knowing**
- `model-deployment-aws/cli.py:32`: `BEST_MODEL = "model-mobilenetv2_train_base_True.v1"`; the SageMaker model name is that string with `.` and `_` replaced by `-`.
- `model-deployment-aws/cli.py:41-42`: the label map `parmigiano 0, gruyere 1, brie 2, gouda 3`, the same order as the processor's `tfrecords.py:11-16`.
- `src/workflow/cli.py:66` vs `:185`: the standalone collector job scrapes 10 images per query, the pipeline's 50.
- `src/workflow/deploy_model_lambda.py:21`: the endpoint configuration name gets a `-%m-%d-%H-%M-%S` suffix, so every run makes a new configuration.
- `src/workflow/cli.py:165`: `CacheConfig(enable_caching=True, expire_after="30d")`, shared by all five steps.

---

## 6. Gotchas and common errors

1. **`exec /bin/sh: exec format error` at the first `RUN`.** `model-deployment-aws/docker-shell.sh:19`, `src/data-processor/docker-shell.sh:31` and `src/model-training/docker-shell.sh:32` build `linux/arm64/v8`. On x86_64 without emulation the build fails (captured, `laptop/20`, `65`, `70`); Docker Desktop on Intel Macs and Windows emulates it slowly. Use the commented plain build line. `src/data-collector/docker-shell.sh:31` and `src/workflow/docker-shell.sh:29` build `linux/amd64`, which Apple-silicon Macs emulate; the workflow image can only be amd64 (its Dockerfile downloads the x86_64 AWS CLI).
2. **`ModuleNotFoundError: No module named 'sagemaker.tensorflow'` (or `'sagemaker.processing'`).** `sagemaker = "*"` plus no lock in use → SDK 3 (3.13.1 on Python 3.9, 3.29.0 on 3.11 at the time of recording; `laptop/22`, `85`) → the 2.x imports fail (`laptop/23`, `86`). Fix: `sagemaker = "<3"` in both Pipfiles. The trainer image is safe: it copies its committed lock.
3. **Option 2 credentials never reach the Part A container** (`docker-shell.sh:22-28`). Use Option 1 or add `-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY`.
4. **`--prepare` fails before downloading anything.** It creates the bucket first (`cli.py:71-82`); without credentials, `NoCredentialsError` at `cli.py:73` (`laptop/27`). If someone else owns the bucket name, the code prints `Bucket … already exists`, continues, and the upload then fails with access denied: pick a unique name.
5. **`sh docker-shell.sh` on Linux skips the key check.** Dash does not know `[[`; under dash the script prints `[[: not found` and builds anyway. Run `bash docker-shell.sh` on Linux; on macOS `sh` is fine.
6. **Placeholders pasted as written.** `<your-endpoint-name>` → `syntax error near unexpected token 'newline'` (`laptop/31`); `export REGION=us-east-1 [YOUR DEVELOPMENT REGION]` → two `not a valid identifier` errors (`laptop/80`). Replace before running.
7. **An ECR URI that starts with a dot.** `ACCOUNT_ID` came back empty (the `aws sts` call failed), and nothing stopped (`laptop/80`). `|| true` after `create-repository` hides its errors too (`laptop/81`).
8. **`PermissionError: [Errno 13] Permission denied: '/persistent/model'`** after local training, on Linux. Docker created `persistent-folder` as root (`laptop/61`); the trainer runs as `app` (uid 1000) (`laptop/73`). Create the folder yourself first, or `sudo chown -R $USER ../../../persistent-folder`.
9. **Query strings are labels.** `tfrecords.py:11-16` knows exactly `"brie cheese"`, `"gouda cheese"`, `"gruyere cheese"`, `"parmigiano cheese"`; any other `--query` makes `--prepare` raise `KeyError`.
10. **Stale local data wins.** The processor downloads from S3 only if its local folder is missing (`src/data-processor/cli.py:41`), and so does local training. All stage containers share `persistent-folder`, so an old `raw/`, `clean/` or `tfrecords/` there is used instead of the bucket's. Delete the folder to start fresh.
11. **`num_classes = 3`** (`task.py:68`) while the data has four labels: the captured model summary ends in `(None, 3)` (`laptop/73`). Fix: `4`.
12. **Every run leaves endpoints behind.** Part A: one per `--deploy`, and `--delete` knows only the last. Part B: one per `--model_deploy`; the pipeline's endpoint stays up after the run. All bill 24/7. `aws sagemaker list-endpoints` is your friend.
13. **The Lambda's name check is a substring match** (`deploy_model_lambda.py:40-44`). If a `cheese-app-endpoint-<8 chars>` exists and `cheese-app-endpoint` does not, the Lambda calls `update_endpoint` on a name that does not exist, and `DeployModel` fails (from the code; not run here; Exercise C8).
14. **The Lambda runtime.** `Lambda(...)` (`src/workflow/cli.py:297-303`) passes no `runtime`, and the 2.x SDK then creates the function on `python3.8`, a runtime AWS has deprecated. If your account refuses it, `upsert` fails with AWS's message; add `runtime="python3.12"` (Exercise C9). Not run here.
15. **`DeployModel` is green before the endpoint is ready.** The Lambda returns after `create_endpoint`/`update_endpoint`; wait for `InService`.
16. **Caching hides re-runs.** Steps whose arguments did not change are reused for 30 days: the collector does not scrape again, and a re-uploaded trainer tarball under the same S3 name may not retrain (Exercise D3).
17. **`--train` returns immediately** (`fit(wait=False)`, `src/model-training/cli.py:74`): a failed job shows only in the console or `aws sagemaker describe-training-job`. The workflow's `--model_training` waits.
18. **The workflow container has no `docker`.** The socket is mounted (`src/workflow/docker-shell.sh:34`), but `docker` is not installed (`bash: docker: command not found`, `laptop/90`). Build and push images on the host.
19. **The Bing scraper can spin.** `downloader.py` loops until it has `--nums` images; if Bing returns pages with no usable links, it keeps requesting pages. Stop it with Ctrl-C and try again later. (The capture got all 40 images.)

---

## 7. Where this sits in the course

**Before.** L13 trained the cheese model as a managed training job and packaged the trainer (`package/`, `package-trainer.sh`): `ml-workflow-aws/src/model-training` is that trainer, adapted to SageMaker. L14 served a container on Cloud Run; README A calls the model's origin "the serverless training we did in the previous tutorials" (A:111). Earlier, L2–L4 built the `docker-shell.sh` pattern and containers that talk through a shared folder, and L10–L11 introduced cloud credentials kept out of code.

**This lecture.** Two halves, matching the deck's sections 2 and 3: serverless model deployment (slides 9–17) and ML workflow management with a managed pipeline service (slides 18–40). The deck is written for Vertex AI; the AWS tutorials implement the same ideas on SageMaker.

**Vertex AI (slides) ↔ AWS (tutorial)**

| Slides (Vertex AI / GCP) | AWS tutorial | Where |
|---|---|---|
| GCS bucket | S3 bucket | both READMEs |
| upload to Model Registry (slide 12, step 4) | create a SageMaker **Model** (not a model package in a registry) | `model-deployment-aws/cli.py:151-159`; the pipeline's `CreateModel` |
| deploy to an Endpoint (step 5) | endpoint configuration + endpoint | `cli.py:168-174`; `deploy_model_lambda.py` |
| update the model signature (slides 13–14) | Part A: not done (the client sends floats); the trainer does it | `cli.py:221-225`; `task.py:276-318` |
| prebuilt serving container | `TensorFlowModel(framework_version="2.13")` → TF Serving 2.13 image | `cli.py:154` |
| Vertex AI Pipelines on Kubeflow, KFP DSL (slides 24–29) | SageMaker Pipelines, SageMaker Python SDK step classes | `src/workflow/cli.py:157-328` |
| compile to YAML, `PipelineJob(...).run()` (slides 29, 33) | `Pipeline(...).upsert(role_arn)` sends a JSON definition; `.start()` returns at once | `cli.py:320-328`; `laptop/92` |
| `.output` wiring makes the DAG (slide 29) | step **property references** make the DAG | `cli.py:219-220`, `:266-267`, `:277`, `:309` |
| container component, image in a registry the service can pull (slides 34–36) | ProcessingStep with `Processor(image_uri=<your ECR>)` | `cli.py:170-197`; README B Build & Push |
| two-mode entrypoint (slide 36) | the same script, without a cloud login | `src/data-collector/docker-entrypoint.sh` |
| Model Training step (slide 37) | a native TrainingStep | `cli.py:249-270` |
| Model Deploy step (slide 37) | ModelStep + LambdaStep | `cli.py:276-315` |
| service-account key locally / attached service account in the cloud | IAM user access key locally / execution roles in the cloud | §3.8 |
| Cloud Functions (slide 8's recap) | Lambda (used here for the deploy step) | `deploy_model_lambda.py` |
| Vertex Online Prediction vs Cloud Run (slides 16–17) | SageMaker endpoint vs a container service; the tutorial uses only the endpoint | §3.2, Exercise D1 |

**After.** L18 builds the app's API and frontend; an API service is what would call a prediction endpoint like this one. L21 and L23 automate builds and deployment with GitHub Actions, which is also how a pipeline like `cheese-pipeline` gets triggered on a schedule or a push (nothing schedules it in this tutorial).

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l15-vertex-ml-workflows/exercises.md) in the video folder. Their outputs are the 2026-11-05 captures and the extra checks run for them (`assets/exercise-checks/`); nothing there touched an AWS account, and whatever only AWS can show is quoted from the README, the code, the SDK's source or AWS's documentation, and says which. Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. Your laptop and the SageMaker endpoint both reach S3. Which identity does each use, and why do Option 2's exported keys never reach the Part A container?**
<details><summary>Answer</summary>

Your laptop and the CLI container sign requests with the **IAM user's access key** (`model-deployment`, A:21-30), which `aws configure` writes to `~/.aws/credentials` and `docker-shell.sh:24` mounts into the container. The endpoint acts as the **execution role** you passed in `SAGEMAKER_ROLE` (`role=role`, `cli.py:153`), whose `AmazonS3FullAccess` lets SageMaker fetch `model.tar.gz`; your key never leaves your laptop. Option 2's `export` lines set variables in your laptop's shell, and a container sees only what `docker run` passes with `-e`: `docker-shell.sh:25-27` passes `AWS_REGION`, `S3_MODELS_BUCKET_NAME` and `SAGEMAKER_ROLE`, not the keys. Use Option 1, or add `-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY`.
</details>

**Q2. Name the three things `--deploy` creates. Which is the address, and which bills while nobody calls it?**
<details><summary>Answer</summary>

One `tensorflow_model.deploy(...)` call (`cli.py:168-174`) creates a **SageMaker Model** (`model-mobilenetv2-train-base-True-v1`: the tarball's S3 URI, the TF Serving 2.13 image, the role), an **endpoint configuration** (named after the endpoint; one variant `AllTraffic` on one `ml.m5.xlarge`), and the **endpoint** `model-mobilenetv2-train-base-True-v1-endpoint-<timestamp>`, which is the address `--predict` calls. The **endpoint** bills: its instance runs around the clock with zero traffic. "Serverless" here means no server for you to manage, not scale to zero. The Model and the configuration are descriptions; that is why every clean-up list removes the endpoint first.
</details>

**Q3. Where does preprocessing sit in Part A, and where in the Part B trainer? Give the lecture's two reasons to put it in the model.**
<details><summary>Answer</summary>

**Part A: in the client.** `--predict` converts to RGB, resizes to 224 × 224 and divides by 255 (`cli.py:221-223`), then sends floats (`:225`); the exported signature confirms it: `inputs['input']` `DT_FLOAT` `(-1, 224, 224, 3)`, `outputs['output_0']` `(-1, 4)` (`laptop/43`). **Part B: inside the model.** `task.py` wraps `preprocess_image` (decode the JPEG, convert to float32, resize) and the model into `serving_function`, whose input is a batch of JPEG strings, and saves it as `serving_default` (`task.py:276-318`). README B:7 gives this job to Model Deploy; the trainer does it. **The lecture's reasons (slide 13):** client-side brittleness (every client must repeat the steps exactly, and one that forgets `÷ 255` gets confident nonsense), and one copy in the model is easier to version and roll back. A bonus you can measure (Exercise B1): a bytes-in request carries the JPEG, a few kilobytes, instead of megabytes of JSON.
</details>

**Q4. Which lines make `ModelTraining` wait for `DataProcessor`? What would a literal `s3://…/tfrecords` string change?**
<details><summary>Answer</summary>

`src/workflow/cli.py:265-268`: the training input is `step_process.properties.ProcessingOutputConfig.Outputs["tfrecords"].S3Output.S3Uri`, a **property reference**; in the definition it becomes `{"Get": "Steps.DataProcessor.ProcessingOutputConfig.Outputs['tfrecords'].S3Output.S3Uri"}` (`laptop/92:212`), and that `Get` is the edge. With the literal `f"s3://{S3_BUCKET_NAME}/tfrecords"` the path is the same but the edge is gone: `ModelTraining` depends on nothing, so SageMaker can start it at once, in parallel with the collector, on whatever old or missing data the prefix holds (the exercise check shows the order computed from the offline definition). To keep a literal path, add `depends_on=[step_process]`.
</details>

**Q5. Which two one-line fixes did today's tutorial need, and which one would an Apple-silicon Mac not need?**
<details><summary>Answer</summary>

(1) **The plain build line** instead of `--platform=linux/arm64/v8` (`docker-shell.sh:19` in Part A; also the processor and the trainer): on Intel/AMD without emulation the first `RUN` fails with `exec /bin/sh: exec format error` (`laptop/20`). An Apple-silicon Mac does **not** need this one: arm64 is native there. (2) **`sagemaker = "<3"`** in `Pipfile:10` and `src/workflow/Pipfile:9`: `"*"` with no lock in use resolved SDK 3 (3.13.1 on Python 3.9), which lacks `sagemaker.tensorflow`, `serializers` and `get_execution_role` (`laptop/22-23`). Everyone needs this one. Careful on the Mac: images you push to ECR for SageMaker must be **amd64** (README B:161's `--platform=linux/amd64/v2`).
</details>

### Hands-on (predict, then run)

- **B1. How big is one request?** Measure the JSON `--predict` sends for one photo (150,528 floats) and compare it with the JPEG.
- **B2. Star or pin?** Predict which `sagemaker` version `"*"`, `"<3"` and the lock's `==2.250.0` install on Python 3.9, then dry-run them.
- **B3. Read the model's front door.** Predict the exported signature's input dtype and shape, the number of outputs, and the tarball's top folder; check with `saved_model_cli` and `tar tzvf`.
- **B4. One flag or two?** Predict what `python cli.py` does with no flag, with `--test`, and with two flags at once, in Part A and in the workflow container.
- **B5. Labels are folder names.** Which label does `gouda cheese` get, and what happens to `--prepare` after `--query "cheddar cheese"` or `"Brie cheese"`?
- **B6. Reverse the list.** Reverse `steps=[…]` in a copy of `src/workflow/cli.py` and predict the run order; then replace the training input with a literal path.
- **B7. Deploy twice, delete once.** Predict which endpoints, configurations and models are left after `--deploy`, `--deploy`, `--delete`; check with `aws sagemaker list-endpoints`.

### Debugging

- **C1.** `exec /bin/sh: exec format error` at `[ 2/14]`, nothing built.
- **C2.** `ModuleNotFoundError: No module named 'sagemaker.tensorflow'` (and `'sagemaker.processing'` in the workflow container) though nobody changed the code.
- **C3.** Option 2 with real keys, and the banner still says `Unable to locate credentials`.
- **C4.** An ECR URI that starts with a dot, after two `not a valid identifier` errors.
- **C5.** `syntax error near unexpected token 'newline'` after pasting README A:161.
- **C6.** `PermissionError: [Errno 13] Permission denied: '/persistent/model'` on a Linux laptop.
- **C7.** On Ubuntu, `docker-shell.sh: 18: [[: not found` and the image builds without any keys.
- **C8.** `DeployModel` fails on the second pipeline run, after `--model_deploy`.
- **C9.** `upsert` fails while creating the Lambda, with a message about the runtime.
- **C10.** `--predict` says `endpoint_config.json not found` and calls an endpoint name without a timestamp.

### Think

- **D1.** Endpoint or Cloud Run: what keeps billing at zero traffic, and when would you pick which (slides 16–17)?
- **D2.** Count the meters after following both READMEs in order, including the four component flags.
- **D3.** Does the 30-day cache know about your `num_classes = 4` fix?
- **D4.** Same photo, same numbers? The processor, the trainer's signature and Part A's client each preprocess differently.
- **D5.** Keys, roles and least privilege: why no key in `docker-shell.sh` or an image, and does `cli.py` need `IAMFullAccess`?
- **D6.** What if the arrows were missing: delete the collector's `outputs=[…]` and the processor's `inputs=[…]`. Does the data still arrive, and does the order hold?

---

## 9. Errata and open questions

**Errata (evidence-based, `077f4db` / `f165c6e`, checked against the 2026-11-05 captures)**
1. **Unpinned `sagemaker` breaks both CLI images today.** `model-deployment-aws/Pipfile:10` and `src/workflow/Pipfile:9` say `"*"`; Part A ignores its lock in git (`.gitignore:68`), and the workflow Dockerfile never copies its lock (`Dockerfile:40-42`). The build resolves SDK 3 and every import fails (`laptop/22-23`, `85-87`). Fix: `sagemaker = "<3"`.
2. **arm64 build lines** in three `docker-shell.sh` files fail on x86_64 (`laptop/20`, `65`, `70`). Fix: the commented plain line.
3. **README A Option 2** (A:77-83): the keys never reach the container (`docker-shell.sh:22-28`).
4. **README A's sample output** (A:136-148): three numbers per image and 0 = gouda; the released model has four outputs (`laptop/43`) and `cli.py:42` maps 0 = parmigiano.
5. **"Model Registry"** (A:7, B:7): both repos create plain SageMaker Models; no model package group is used. And B:7 gives the signature update to Model Deploy, while the trainer does it (`task.py:276-318`).
6. **`num_classes = 3`** (`src/model-training/package/trainer/task.py:68`) while the processor writes labels 0–3 (`tfrecords.py:11-16`); captured `dense_1 (Dense) (None, 3)` (`laptop/73`). Gouda gets an all-zero target. Fix: `4`.
7. **"This step has already been done for this tutorial"** (B:153): the pipeline pulls both images from **your** ECR (`src/workflow/cli.py:35-36`). The Docker Hub user to pull from (`<YOUR_DOCKER_HUB_USERNAME>`) is not named anywhere.
8. **`export REGION=us-east-1 [YOUR DEVELOPMENT REGION]`** (B:169) errors when pasted (`laptop/80`), and B:182's `|| true` hides real errors (`laptop/81`).
9. **`--prepare` creates the bucket first** (`cli.py:71-82`), a step README A's list (A:113-117) does not mention; without credentials it stops before downloading (`laptop/27`).
10. **Leftover GCP wording:** `cli.py:318` "save model to GCS Bucket", help texts "Vertex AI" and the parser title "Data Collector CLI" (`laptop/25`), and a `--test` flag that does nothing.
11. **Linux specifics the READMEs don't mention:** `sh` is dash there, so the key check misfires (use `bash`), and Docker creates `persistent-folder` as root, so the trainer cannot save (`laptop/61`, `73`).
12. **Minor:** `ml-workflow-aws/README.md:88` repeats "& Test CLI" in its heading; `IAMFullAccess` (A:28) is broader than the code needs; README B has no clean-up section although its endpoints bill 24/7.

**Open questions / could not determine here** (no AWS account in the capture sandbox)
1. **How the pipeline's training step finds its data.** Its channel is the processor's declared prefix `s3://<b>/tfrecords` (`src/workflow/cli.py:266-267`), which the processor never writes into; the processor uploads `tfrecords.zip` to the bucket root. An S3 key prefix `tfrecords` also matches the key `tfrecords.zip`, and README B's image shows a successful run, but where SageMaker places that file inside the channel, and so whether `task.py:71-86` finds it, was not verified.
2. **TF 2.18 export on SageMaker's TF Serving 2.13 image.** The public `tensorflow/serving:2.13.1` loaded it with a warning (`laptop/46`); SageMaker's own image was not tried.
3. **The Lambda runtime.** Whether AWS still lets a given account create `python3.8` functions on 2026-11-05 was not checked; §6 #14 gives the fix either way.
4. **Console labels** (SageMaker AI, Unified Studio → Build → ML Pipelines, Processing jobs, Training jobs) come from the READMEs; they were not seen live.
5. **Run times and the full pipeline** (endpoint creation, the 15-epoch training job, the whole run) were not measured here.
6. **The Ed lesson** was not opened.

---

## Links

- README sections, Part A (pinned commit): [Setup Environments](https://github.com/dlops-io/model-deployment-aws/blob/077f4dbc7b13ccef208c65a8e29489331261029e/README.md#setup-environments) · [Run Container](https://github.com/dlops-io/model-deployment-aws/blob/077f4dbc7b13ccef208c65a8e29489331261029e/README.md#run-container) · [Clean Up Resources](https://github.com/dlops-io/model-deployment-aws/blob/077f4dbc7b13ccef208c65a8e29489331261029e/README.md#clean-up-resources) · [Troubleshooting](https://github.com/dlops-io/model-deployment-aws/blob/077f4dbc7b13ccef208c65a8e29489331261029e/README.md#troubleshooting) · latest README on [`main`](https://github.com/dlops-io/model-deployment-aws)
- README sections, Part B (pinned commit): [Setup Environments](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/README.md#setup-environments) · [Build & Push Images](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/README.md#build--push-images) · [Automate Running Data Collector Container](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/README.md#automate-running-data-collector-container) · [Cheese App: SageMaker Pipelines](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/README.md#cheese-app-sagemaker-pipelines) · latest README on [`main`](https://github.com/dlops-io/ml-workflow-aws)
- Repo files: [`model-deployment-aws/cli.py`](https://github.com/dlops-io/model-deployment-aws/blob/077f4dbc7b13ccef208c65a8e29489331261029e/cli.py) · [`ml-workflow-aws/src/workflow/cli.py`](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/src/workflow/cli.py) · [`deploy_model_lambda.py`](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/src/workflow/deploy_model_lambda.py) · [`trainer/task.py`](https://github.com/dlops-io/ml-workflow-aws/blob/f165c6e17895d3d6c33a150d349f4b2649c807db/src/model-training/package/trainer/task.py)
- AWS docs linked by README A: [SageMaker](https://docs.aws.amazon.com/sagemaker/) · [SageMaker TensorFlow Serving](https://sagemaker.readthedocs.io/en/stable/frameworks/tensorflow/deploying_tensorflow_serving.html) · [S3](https://docs.aws.amazon.com/s3/) · [IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- The course's GCP versions (context only): [`dlops-io/model-deployment`](https://github.com/dlops-io/model-deployment) · [`dlops-io/ml-workflow`](https://github.com/dlops-io/ml-workflow)
- Ed lesson: [L15 · ML Workflows with Vertex AI](https://edstem.org/us/courses/97373/lessons/166040/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-vertex-ml-workflows) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l15-vertex-ml-workflows/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-vertex-ml-workflows/assets/terminal) · the concept-first [exam edition](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l15-exam)
- Previous lecture: [L14 · Serverless deployment](L14-serverless-deployment.md) · next: [L18 · APIs and frontend](L18-apis-frontend.md)
- Referenced in §7: [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II (mega-pipeline)](L03-containers-2-mega-pipeline.md) · [L10 · Connecting to the Cloud](L10-cloud-connect-cheese-app-v0.md) · [L11 · Data labeling and versioning](L11-data-labeling-versioning.md) · [L13 · Training workflows](L13-training-workflows.md) · [L21 · CI/CD with GitHub Actions](L21-cicd-github-actions.md) · [L23 · Final CI/CD deployment](L23-final-cicd-deployment.md)
