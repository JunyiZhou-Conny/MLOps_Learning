# L14 · Serverless Deployment: Cloud Functions, Cloud Run — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166039/) · Tutorial: [`dlops-io/serverless-deployment`](https://github.com/dlops-io/serverless-deployment) `main` @ [`4eaf343`](https://github.com/dlops-io/serverless-deployment/tree/4eaf3433a3430f51306e67247287a124d0c35710) (legacy branch `pipenv` @ [`fb0cb7f`](https://github.com/dlops-io/serverless-deployment/tree/fb0cb7f3fe85fc5f5aad975a5b599d202c5db9b8), which matches the Docker Hub image the README deploys) · Video: planned · Made from the verified digest, 2026-10-12

## 中文速览

- **做什么：** 把 L1/L2 的 Simple Translate 变成一个 HTTP endpoint（`?text=Good afternoon everyone&src=en&dest=fr` 直接返回翻译文本），用两种 serverless 方式 deploy 到 GCP，全程不碰 VM：(A) **Cloud Run functions**，在 console 的 inline editor 里贴 `main.py` + `requirements.txt`；(B) **Cloud Run service**，直接部署 Docker Hub 上现成的 image `dlops/simple-translate-http:latest`。Bonus (C) 是一个 **Cloud Run job**，挂一个 service account 去调 Vertex AI 上的 Gemini。
- **Idea 1 · scale to zero：** serverless 不是没有 server，而是平台替你管 server 的生命周期：有 request 才起 instance，流量没了就缩到 0，request-based billing 只按忙的时间收钱。代价是 cold start（`min instances` 设成 1 能缓解，但它会一直计费）。
- **Idea 2 · function = 你没写 Dockerfile 的 container：** Cloud Build + buildpacks 帮你 build 成 image，存进 Artifact Registry，进程就是 `functions-framework --target <entry point>`。repo 里的 `docker-entrypoint.sh:18` 就是这个过程的手动版。
- **Idea 3 · container contract：** 监听 `$PORT`（默认 8080）、bind `0.0.0.0`、linux/amd64、不依赖本地 state。functions-framework 的 `_cli.py:32-33` 两行就搞定前两条；`-p 8080:8080` 和 `EXPOSE` 对 Cloud Run 没有意义。
- **Idea 4 · tag vs digest：** deploy 时 `:latest` 被 resolve 成 digest 并钉在 revision 上，别人推新 image 你的 service 不会变，要重新 deploy。而且这个 `:latest` 其实是 2024 年的 pipenv build（Python 3.9.17），不是 repo `main` 里的 uv 代码。
- **Idea 5 · 两种 IAM 身份：** invoker 决定谁能调用（"Allow public access" 经典做法是给 `allUsers` 加 `roles/run.invoker`）；runtime service account 是 container 出去调 Vertex AI 时的身份，由 metadata server 发 token，不需要 JSON key。两者互不影响。
- **最费时间的坑：** ① function 的 "Function entry point" 必须和 `def` 名字一致：README 里是 `hello_http`，repo 的 `main.py` 是 `translate_http`，贴错就报 `File /workspace/main.py is expected to contain a function named ...`。② Job 显示 *Succeeded* 不代表成功：image 里写死的 `gemini-1.5-flash-001` 已下线，exception 被 `cli.py:51-52` 吞掉，一定要看 Logs，别看 status badge。（Apple Silicon 上自己 build image 要加 `--platform=linux/amd64`。）
- **做完要删：** function、service、job；Artifact Registry 里 function build 自动生成的 repo/image（`cloud-run-source-deploy` 或 `gcf-artifacts`，做了 Step 11 还有你自己的 `ac215-images`）；Cloud Storage 里的 source bucket（`run-sources-…` 或 `gcf-v2-sources-…`）。README 没有 cleanup 这一节，照 §4 Step 12 做。
- **Lecture slides：** 老师的 Lecture 14 slides（17 页）和这份 guide 各节怎么对应、做 tutorial 需要的 9 个 lecture ideas，以及 slides 和今天 README/repo 不一样的 5 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slide 10 的 code sketch 用位置参数 `translate(text,src,dest)`，但 googletrans 的第二个参数是 `dest`，要像 README 一样写 `src=`/`dest=`；② "只为运行时间付费" 只在默认的 request-based billing + min instances 0 下成立，function build 留下的 image 和 source bucket 照样收费。

## At a glance

**What you build.** The Simple Translate app as an HTTP endpoint (`…/?text=Good afternoon everyone&src=en&dest=fr` returns the translation as plain text), deployed on Google Cloud without a VM in two ways: as a Cloud Run function pasted into the console's inline editor, and as a Cloud Run service that serves the prebuilt image `dlops/simple-translate-http:latest`. The bonus is a Cloud Run job (`dlops/simple-translate-gemini`) that translates with Gemini on Vertex AI, authenticating as an attached service account with no key file.

**Time needed** (estimate). About 1.5 h for the three README sections; every deploy takes "a few minutes" (README.md:71). Add about 1 h for the optional local Docker rehearsal (slow on Apple Silicon, where amd64 is emulated) and about 1 h for the extensions (lock-down with identity tokens, your own image through Artifact Registry).

**Prerequisites.**
- A GCP project with billing enabled (Tutorial 0 / `ac215-setup`) and the Cloud Console in a browser. The README is entirely click-ops; it has no `gcloud` commands.
- Optional, for the local rehearsal and the extensions: Docker Desktop (with Rosetta/QEMU emulation on Apple Silicon), `git`, `uv`, the `gcloud` CLI.
- Background: Simple Translate (L1–L2), ports and `$PORT` (L4), service accounts and key files (L3, L10).
- Credentials: none for paths A and B. APIs: the console prompts for them; the CLI equivalent is in §2. The job (path C) also needs the Vertex AI API and a service account with Vertex AI User (§2).

**What it costs.** With request-based billing and minimum instances 0 (the console defaults), the tutorial uses a tiny fraction of Cloud Run's monthly free tier (§2). Money goes to Cloud Build minutes on every (re)deploy of the function, Artifact Registry storage, Cloud Run job execution time and Gemini tokens. The real surprise bills come from minimum instances ≥ 1, instance-based billing, images left in Artifact Registry, and a public URL that someone scripts against.

**Tear down, exactly** (the README has no cleanup section; details in §2 and §4 Step 12):
1. The Cloud Run function (path A): Console → Cloud Run → select the function → Delete.
2. The Cloud Run service (path B): `gcloud run services delete SERVICE --region=REGION`, or delete it in the console.
3. The Cloud Run job (path C): `gcloud run jobs delete NAME --region=us-central1`.
4. Artifact Registry: the auto-created repository that holds your function's image (`cloud-run-source-deploy` or `gcf-artifacts`; check Artifact Registry → Repositories), plus `ac215-images` if you did Step 11.
5. Cloud Storage: the auto-created function-source bucket (name starts with `run-sources-…` or `gcf-v2-sources-…`).
6. Next day: confirm in Billing → Reports.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site source `tutorials_demo.md:193`): `#running-app-as-cloud-function` (README.md:5-81) and `#running-app-in-cloud-run` (README.md:88-113). The same README has a bonus section that the course site does not link: `#setup-cloud-run-job--service-account` (README.md:121-147).
- **Primary repo:** `dlops-io/serverless-deployment`, branch `main`, commit `4eaf3433a3430f51306e67247287a124d0c35710`, committed 2025-10-20 21:53:06 -0400 ("updates").
  - Legacy branch `pipenv`: commit `fb0cb7f3fe85fc5f5aad975a5b599d202c5db9b8`, 2025-03-25 18:18:10 -0400. This is the pre-`uv` code. Its `main.py`, `Dockerfile` and `docker-entrypoint.sh` match byte for byte the files inside the Docker Hub image that the README deploys.
- **Prebuilt container images the README deploys.** They are not built anywhere in the repo. Both were inspected read-only through the Docker Hub registry API:
  - `dlops/simple-translate-http:latest`. Digest `sha256:77751cec931697312d687d5011d8f05da3b6141ef1e596a3e92eb605b3442cfa`, pushed 2024-10-22, `linux/amd64` variant `v2` only, Python 3.9.17 (`python:3.9-slim-buster` base), built with **pipenv**. Its `Pipfile.lock` pins **functions-framework 3.4.0**, Flask 2.3.3, gunicorn 20.1.0, googletrans 4.0.0rc1 (not the 3.9.2 / 3.1.2 / 23.0.0 of `main`'s `uv.lock`).
  - `dlops/simple-translate-gemini:latest`. Digest `sha256:ec05eb27230d90d5341a47667a0cd1481e800d7fa6086677f2d9724f1ade7f77`, pushed 2024-10-21, `linux/amd64` only, Python 3.11.4, pipenv. Its source code is in no public repo; it was read from the image's small `ADD . /` layer.
- **Context repos** (read for this guide; none of them is run in this lecture): `simple-translate` main `62f821bfe09fc1c2ecb0f14354b1f205777c0efa` (2026-09-08), `port_toy` main `d190c7122fc35cc1f7e15e467d2babdfc24b5c0c` (2026-09-20), `model-training` main `b9aee1cc1923dd1f673093ad3ff5bb023049b4ff` (2025-10-16), `model-deployment` main `3fbf63f1030f762ad3b3b1c6e376144083306eda` (2025-10-23), `mega-pipeline` main `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc` (2026-09-27).
- **External source:** GoogleCloudPlatform/functions-framework-python tag `v3.9.2`, the exact version locked in `uv.lock:135-136`; files `src/functions_framework/_cli.py`, `_function_registry.py` and `_http/gunicorn.py`. Verified to match byte for byte the PyPI wheel whose sha256 is pinned at `uv.lock:151`. `functions-framework 3.4.0` from PyPI (hash matches the Docker Hub image's `Pipfile.lock`) was also read, because that is what path (B) actually runs.
- **Ed lesson:** not accessible when these sources were checked; the course site source `tutorials_demo.md:188-194`, which links the two README sections above, was used instead.
- **Colab notebooks:** none for L14. **AWS variant:** "Coming Soon" (`tutorials_demo.md:194`).

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 14: Serverless Deployment: Cloud Functions, Cloud Run*, 17 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l14-serverless-deployment/SLIDES.md`.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §7 Where this sits in the course | 5 (Cheese App roadmap), 6 (the four components; "Model Deploy" is next), 9 (serverless across L13–L15) |
| §1 What you build | 10 (one app, four deployment options) |
| §3.1 Serverless, scale to zero; §3.3 billing | 8, 11, 14 |
| §3.2 Cold starts | 16 |
| §3.4 Functions vs services; checklist *Running App as Cloud Function*; §4 Steps 2–6 | 10–12 |
| Checklist *Running App in Cloud Run*; §4 Steps 7–8 | 10 (cell 4), 14, 15 |
| §3.8 Services vs jobs; checklist *Setup Cloud Run (Job + Service Account)*; §4 Step 10 | 14 (names *service* and *job* only) |
| §6 Gotchas | 16 ("limited control and debugging") |
| §2 clean-up, §3.5 container contract, §3.6 tags and digests, §3.7 IAM, §5 code tour, §8 exercises, §9 errata | none (tutorial-only) |

**Lecture ideas you need for this tutorial**
1. Your project has reached deployment. Of the four Cheese App components, the collector, processor and training are done, and "Model Deploy" is next (slides 5–6).
2. Serverless means code runs only when it is needed and you set up no servers, so you pay for use, not for an idle machine (slide 8).
3. Serverless is a family on GCP: the Vertex AI training job (L13), Cloud Functions and Cloud Run (today), then Vertex AI model deployment and pipelines (L15) (slide 9).
4. The same app can be deployed four ways: as a code file or a container, on a VM or serverless. L1–L2 covered the two VM options. Path A is the serverless file, path B the serverless container (slide 10).
5. A Cloud Function runs lightweight code with no server to manage. An event starts it (here, an HTTP request); you pay for the time it runs; it scales on its own (slide 11).
6. Deploying a function takes four steps: open the Functions page, enable the APIs, write the code, deploy (slide 12).
7. Cloud Run runs a whole container you bring, either as a *service* (path B) or as a *job* (path C) (slide 14).
8. Deploying to Cloud Run takes three steps: open the Cloud Run page, enable the APIs, deploy a Docker image (slide 15).
9. Serverless has three downsides: vendor lock-in, cold starts after idle time, and limited control when debugging (slide 16).

**Where the slides and today's tutorial differ** (in each case, use the README and repo at `4eaf343`)
- The slides say "Cloud Function(s)" at `console.cloud.google.com/functions`. The product is now *Cloud Run functions*, under Cloud Run (README.md:8), and that link redirects there. Your URL ends in `run.app` (§4 Step 6).
- Slide 10 draws a function as a bare `main.py`, and slide 11 says there are no containers to manage. In fact Cloud Build turns your source into a container image in Artifact Registry, which you delete afterwards (§3.4, §2).
- Slide 10's sketch calls `translator.translate(text,src,dest)` positionally and ends with `return = results.text`. googletrans orders the arguments `translate(text, dest, src)`, so pass `src=` and `dest=` by name, as README.md:57 and `main.py:25` do.
- Slides 11 and 14 say you pay only while code runs. That holds for compute with request-based billing and min instances 0, the defaults. Cloud Build minutes, Artifact Registry images and source buckets cost money anyway (§2, §4 Step 12).
- Slide 12's "Create a python code file" is shorthand. The console needs `main.py`, `requirements.txt` and a Function entry point equal to the `def` name, `hello_http` (§4 Steps 3–5, §6 #5).

## Command checklist

The README is entirely console clicks; the only things it has you type are the code, the dependency list, an image name, query strings and one container argument. Those are in backticks below, exactly as the README writes them. Plain items are console steps. Items marked *(extra)* are not in the README; they come from §4 of this guide.

### Before the README *(extra)*

- [ ] `cd ~/Desktop/AC215 && git clone https://github.com/dlops-io/serverless-deployment.git && cd serverless-deployment && git log -1 --format='%h %ci'` — *(extra)* get the code; expect `4eaf343 2025-10-20 21:53:06 -0400` (Step 0). If you use this workspace's `tools/sync_tutorials.py`, the clone is in `tutorials/serverless-deployment` instead.
- [ ] `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudfunctions.googleapis.com logging.googleapis.com aiplatform.googleapis.com` — *(extra)* CLI equivalent of the console's "enable APIs" popups (§2).
- [ ] `sh docker-shell.sh` — *(extra)* builds image `simple-translate` for `linux/amd64/v2`; it runs nothing, because the `docker run` lines are commented out (`docker-shell.sh:14-18`).
- [ ] `docker run --rm -ti --name simple-translate -p 8080:8080 simple-translate` — *(extra)* starts functions-framework on port 8080; after the startup banner the container stays silent.
- [ ] `curl "http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=fr"` — *(extra)* in a second terminal; prints the French text, and the container logs `request_json:`, `request_args:` and `Output:`.
- [ ] `docker stop simple-translate` — *(extra)* stops it from another terminal; needed if you ran without `-ti`, where Ctrl-C does nothing (bash is PID 1 and does not `exec` the server).

### Running App as Cloud Function

*Setup Cloud Function* (README.md:7-14)
- [ ] In GCP go to [Cloud Run -> Functions](https://console.cloud.google.com/functions).
- [ ] Click the "{...} Write a function" button.
- [ ] If the "enable required APIs" popup shows up, click "ENABLE" (link a billing account first if it fails).

*Create a Cloud Function* (README.md:16-71)
- [ ] Under Configure -> "Service Name", add a name (e.g. `simple-translate`).
- [ ] Under Endpoint URL -> "Runtime", select "Python 3.10" (if it is missing or marked deprecated, pick Python 3.12).
- [ ] Under Authentication, select "Allow public access".
- [ ] Click "Create" at the bottom.
- [ ] Replace the code in `main.py` with the block at README.md:24-62 (the function is `hello_http`; leave "Function entry point" as `hello_http`).
- [ ] Replace the content of `requirements.txt` with `functions-framework==3.*` and `googletrans==4.0.0rc1` (two lines).
- [ ] Click "Save and Deploy" (possibly labelled "Save and redeploy" today) and wait a few minutes for the green check.

*Test Cloud Function* (README.md:73-81)
- [ ] Copy the URL from the function details page and open it with no parameters: a Spanish sentence (default `dest="es"`). Yours looks like `https://<name>-<project-number>.<region>.run.app`, not the README's `cloudfunctions.net` URL.
- [ ] `?text=Good afternoon everyone&src=en&dest=fr` — append to the URL; French.
- [ ] `?text=Very cool concept&src=en&dest=el` — append to the URL; Greek.
- [ ] `?text=Ready to go home?&src=en&dest=hi` — append to the URL; Hindi.
- [ ] `curl -G "https://YOUR-URL/" --data-urlencode "text=Ready to go home?" -d src=en -d dest=hi` — *(extra)* the same test from a terminal, with the spaces URL-encoded.
- [ ] *(extra)* Open the **Logs** tab and find the `request_json:`, `request_args:` and `Output:` lines.

### Running App in Cloud Run

*Setup Cloud Run (Service)* (README.md:90-93)
- [ ] In GCP go to [Cloud Run](https://console.cloud.google.com/run).
- [ ] Click "Deploy container".
- [ ] If the API popup shows up, enable the API (Cloud Run Admin API).

*Deploy Container* (README.md:95-103)
- [ ] Select "Deploy one revision from an existing container image" and put in the image name `dlops/simple-translate-http:latest`.
- [ ] Give your Cloud Run a `Service name`.
- [ ] Under Authentication, select "Allow public access".
- [ ] Click "Create" and wait a few minutes; the form should match `images/cloud-run-create.png` (request-based billing, auto scaling, min instances 0).
- [ ] `gcloud run deploy simple-translate-run --image=docker.io/dlops/simple-translate-http:latest --region=us-central1 --allow-unauthenticated` — *(extra)* the CLI equivalent of the clicks above.

*Test Cloud Run* (README.md:105-113)
- [ ] Copy the URL from the service details page and open it with no parameters: the default is now `"Welcome to AC215"` in Spanish (the image's `main.py:15`), not the README function's cheese sentence.
- [ ] `?text=Good afternoon everyone&src=en&dest=fr` — append to the URL; French.
- [ ] `?text=Very cool concept&src=en&dest=el` — append to the URL; Greek.
- [ ] `?text=Ready to go home?&src=en&dest=hi` — append to the URL; Hindi.
- [ ] *(extra)* In **Revisions**, note the image digest; in **Metrics**, watch the instance count drop back to 0 after the service has been idle for a while.

*Lock it down and call it with an identity token* *(extra, Step 9)*
- [ ] `gcloud run services get-iam-policy simple-translate-run --region=us-central1` — *(extra)* shows whether public access comes from an `allUsers` binding.
- [ ] `gcloud run services remove-iam-policy-binding simple-translate-run --region=us-central1 --member=allUsers --role=roles/run.invoker` — *(extra)* if `allUsers` is listed: remove the public binding (or Console: Service → Security → Authentication → "Require authentication").
- [ ] `gcloud run services update simple-translate-run --region=us-central1 --invoker-iam-check` — *(extra)* if `allUsers` is not listed but the URL is still public: turn the invoker IAM check back on.
- [ ] `curl -i "https://YOUR-URL/?text=hello&dest=fr"` — *(extra)* expect `403`.
- [ ] `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" "https://YOUR-URL/?text=hello&dest=fr"` — *(extra)* expect `200` (as project owner you already have `run.invoker`).

### Setup Cloud Run (Job + Service Account)

*(README.md:121-147; bonus, not linked from the course site)*
- [ ] *(extra)* In your own project, create a service account (e.g. `translate-job`) and grant it Vertex AI User (`roles/aiplatform.user`); enable the Vertex AI API. You need Service Account User (`roles/iam.serviceAccountUser`) on it to attach it; project Owners already have that permission. The README's screenshot uses `mega-pipeline`, which exists only in the instructor's project.
- [ ] In GCP go to [Cloud Run](https://console.cloud.google.com/run).
- [ ] Click "Deploy container" and pick "Job".
- [ ] Container Image URL: `dlops/simple-translate-gemini`.
- [ ] Job name: give a unique job name.
- [ ] Expand the section "Container(s), Volumes, Connections, Security".
- [ ] Select the "SECURITY" tab and pick the "Service Account" that has access to Vertex AI (Gemini).
- [ ] Select the check box "Execute job immediately".
- [ ] To pass arguments: select the "CONTAINER(S)" tab and, in the SETTINGS area, fill in Container arguments:
- [ ] `cli.py --text Ready+to+go+home?` — the container arguments (one chip in `images/cloud-run-job-02.png`); `+` stands for a space.
- [ ] *(extra)* Click "Create" (the README omits this click; the screenshot's button is "Create").
- [ ] *(extra)* Jobs → your job → Executions → Logs: look for `Input: Ready to go home?` and `Generated text:` (Italian), or `Error occurred while generating content: …`. The status badge can say *Succeeded* either way.

### After the README *(extra)*

*Ship your own build through Artifact Registry (Step 11)*
- [ ] `gcloud artifacts repositories create ac215-images --repository-format=docker --location=us-central1` — *(extra)* creates a Docker repository in Artifact Registry.
- [ ] `gcloud auth configure-docker us-central1-docker.pkg.dev` — *(extra)* lets `docker push` authenticate to that registry host.
- [ ] `docker build --platform=linux/amd64 -t us-central1-docker.pkg.dev/PROJECT_ID/ac215-images/simple-translate-http:v1 .` — *(extra)* builds the current `main` code (uv, Python 3.12) for amd64.
- [ ] `docker push us-central1-docker.pkg.dev/PROJECT_ID/ac215-images/simple-translate-http:v1` — *(extra)* pushes it with an immutable tag.
- [ ] `gcloud run deploy simple-translate-mine --image=us-central1-docker.pkg.dev/PROJECT_ID/ac215-images/simple-translate-http:v1 --region=us-central1 --allow-unauthenticated` — *(extra)* deploys your own image as a public service.

*Clean up (Step 12)*
- [ ] `gcloud run services delete NAME --region=us-central1` — *(extra)* deletes the function and each service (run it once per name).
- [ ] `gcloud run jobs delete NAME --region=us-central1` — *(extra)* deletes the job.
- [ ] *(extra)* Artifact Registry: delete your `ac215-images` repository and the images in the auto-created one from the function deploy (`cloud-run-source-deploy` or `gcf-artifacts`).
- [ ] *(extra)* Cloud Storage: delete the auto-created source bucket (`run-sources-…` or `gcf-v2-sources-…`).
- [ ] *(extra)* Over the next day, confirm in Billing → Reports that nothing is still charging.

---

## 1. What you build

You take the Simple Translate app from Lectures 1 and 2 and turn it into a **web endpoint**. A URL like `…/?text=Good afternoon everyone&src=en&dest=fr` comes back with the translation as plain text. You deploy that endpoint two ways on Google Cloud, plus a bonus run-to-completion job that translates with Gemini instead, and none of them involves a VM.

- **(A) Cloud Run functions** (formerly "Cloud Functions"). You paste a Python function into the console's inline editor. Google builds a container for you and runs it.
- **(B) Cloud Run service.** You point Cloud Run at a container image that is already built (`dlops/simple-translate-http:latest` on Docker Hub), and it serves that image.
- **(C) Bonus: Cloud Run job.** A run-to-completion container (`dlops/simple-translate-gemini`) runs under a **service account** so that it can call Gemini on Vertex AI without any key file.

In every case the platform starts container instances only when requests (or job executions) arrive. It scales them back to zero afterwards and bills only for the time they are busy. The repo's own code (`main.py`, `Dockerfile`, `docker-entrypoint.sh`) is the "do it yourself" version of path (A). Your container runs Google's `functions-framework`, which is exactly what the Cloud Functions platform injects for you. You can rehearse it locally with Docker.

```
                         YOUR LAPTOP (optional local rehearsal - not in README)
 +---------------------------------------------------------------------------------+
 | serverless-deployment/                                                          |
 |   sh docker-shell.sh  --docker build--> image "simple-translate" (linux/amd64/v2) |
 |   docker run -p 8080:8080 simple-translate                                       |
 |     +-------------------- container (user "app", WORKDIR /app) ---------------+ |
 |     | bash docker-entrypoint.sh                                                | |
 |     |   uv run functions-framework --target translate_http                     | |
 |     |     gunicorn  bind 0.0.0.0:$PORT (default 8080)                          | |
 |     |       Flask app -> main.translate_http(request)                          | |
 |     +--------------------------------------------^-----------------------------+ |
 |   curl "http://localhost:8080/?text=...&src=en&dest=fr" --+  (host 8080 -> 8080) |
 +---------------------------------------------------------------------------------+

                    GOOGLE CLOUD PROJECT  (region e.g. us-central1)
 (A) Cloud Run functions                         (B) Cloud Run service
 +------------------------------+               +-----------------------------------+
 | console inline editor        |               | Docker Hub: dlops/simple-         |
 |  main.py + requirements.txt  |               |  translate-http:latest            |
 |        | upload source       |               |   (tag resolved to a digest at    |
 |        v                     |               |    deploy time)                   |
 | Cloud Build (buildpacks)     |               +----------------+------------------+
 |        | push image          |                                |
 |        v                     |                                v
 | Artifact Registry repo       |               +-----------------------------------+
 |        | deploy revision     |               | Cloud Run revision                |
 |        v                     |               |  instances 0..N, each runs        |
 | Cloud Run revision           |               |  pipenv run functions-framework   |
 |  functions-framework         |               |  --target translate_http on $PORT |
 |  --target hello_http on $PORT|               +----------------^------------------+
 +--------------^---------------+                                |
                |  HTTPS  https://<name>-<project#>.<region>.run.app/?text=...
                |                                                |
        +-------+------------------------------------------------+-------+
        | Google front end -> IAM check: does caller have roles/run.invoker?|
        |   "Allow public access"  ==  allUsers has roles/run.invoker       |
        +---------------------------------^---------------------------------+
                                          |
                               browser / curl (you)

  Each instance then makes an outbound HTTPS call:
  googletrans 4.0.0rc1 -> Google's *unofficial* web-translate endpoint (no credentials)

 (C) Cloud Run job (bonus)
 +----------------------------------------------------------------------------------+
 | job "simple-translate-gemini" -> task container dlops/simple-translate-gemini     |
 |   args: cli.py --text Ready+to+go+home?                                          |
 |   pipenv run python cli.py ...  --(token from metadata server, as the ATTACHED   |
 |                                    service account)--> Vertex AI Gemini API      |
 +----------------------------------------------------------------------------------+
```

---

## 2. Prerequisites and costs

**Accounts and local installs**
- A GCP project with billing enabled, which you already have from Tutorial 0 / `ac215-setup`.
- In a browser: the Cloud Console. The README is entirely click-ops. It contains no `gcloud` commands.
- Optional (for the local rehearsal and the extensions in §4): Docker Desktop, `git`, `uv`, and the `gcloud` CLI.
- On Apple Silicon: Docker Desktop with Rosetta/QEMU emulation, because `docker-shell.sh:11` builds `linux/amd64/v2`.

**GCP APIs to enable**
- Path (A): the console pops up an "Enable required APIs" dialog (README.md:10-14). The screenshot `images/cloud-function-enable-apis.png` lists **Cloud Build API, Cloud Functions API, Cloud Logging API and Cloud Pub/Sub API**. That screenshot predates the move to "Cloud Run → Functions", and today's dialog may also ask for the Cloud Run Admin API and the Artifact Registry API. Click ENABLE on whatever it lists.
- Path (B): Cloud Run Admin API (`run.googleapis.com`), which the console prompts for (README.md:93).
- Path (C): additionally the Vertex AI API (`aiplatform.googleapis.com`).
- CLI equivalent (not in the README):
  `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudfunctions.googleapis.com logging.googleapis.com aiplatform.googleapis.com`

**Service accounts, keys and secrets: where the code expects them**
- **Paths (A) and (B) need no credentials at all.**
  - `grep` for `secret`, `GOOGLE_`, `PORT` and `environ` across the repo finds nothing in code.
  - `googletrans` calls a public, unauthenticated web endpoint.
  - The repo has no `secrets/` folder and no `GOOGLE_APPLICATION_CREDENTIALS`.
  - The only environment variables the code reads are `DEV`, read by `docker-entrypoint.sh:14`, and `PORT`/`HOST`, read implicitly by functions-framework (`_cli.py:32-33`).
- **Path (C) needs a service account attached to the job as its runtime identity.** You do not need a JSON key (README.md:123, 134).
  - The screenshot `images/cloud-run-job-01.png` picks a service account named `mega-pipeline`. That account lives in the instructor's project.
  - In your own project, create one, e.g. `translate-job`, and give it **Vertex AI User** (`roles/aiplatform.user`).
  - You, the deployer, also need **Service Account User** (`roles/iam.serviceAccountUser`) on that account in order to attach it (project Owners already have the `iam.serviceAccounts.actAs` permission it grants).
- For local runs, the gemini image's own (unpublished) `docker-shell.sh` mounts `../secrets/` at `/secrets` and sets `GOOGLE_APPLICATION_CREDENTIALS="/secrets/mega-pipeline.json"` (image file `/docker-shell.sh:9-10,18-22`). On Cloud Run that file does not exist. The metadata server supplies the token instead, which is the point README.md:123 makes.

**What costs money, and how to shut it down.** The README has no cleanup section, so this list is added.

| Billable resource | Created by | How to remove |
|---|---|---|
| Cloud Run service (CPU, memory and requests while serving) | path B | Console → Cloud Run → select service → Delete, or `gcloud run services delete SERVICE --region=REGION` |
| Cloud Run function (same billing as a Cloud Run service) plus **Cloud Build** minutes for every (re)deploy | path A | Console → Cloud Run → select the function → Delete |
| **Artifact Registry** storage for the image Cloud Build produced for your function. It sits in an auto-created repository, typically `cloud-run-source-deploy` or `gcf-artifacts` depending on how the function was created; check Artifact Registry → Repositories | path A | Delete the image or the repository in Artifact Registry |
| Cloud Storage bucket holding uploaded function source (auto-created, name starts with `run-sources-…` or `gcf-v2-sources-…`) | path A | Delete the bucket in Cloud Storage |
| Cloud Run job executions (vCPU and memory seconds) plus **Gemini tokens** | path C | Delete the job; there is nothing to stop unless it is running |
| Cloud Logging ingestion (free allotment, then per GiB) | all | Normally negligible |

Cost intuition (verify current prices at cloud.google.com/run/pricing):
- With **request-based billing**, which is the default radio button in `images/cloud-run-create.png`, Cloud Run's monthly free tier has been 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests per billing account. This tutorial uses a tiny fraction of that.
- The real ways to get a surprise bill:
  - Setting **minimum instances ≥ 1**. One always-on vCPU for 30 days is 30 × 86,400 = 2,592,000 vCPU-seconds, about 14× the free tier.
  - Choosing **instance-based billing**.
  - Leaving images in Artifact Registry.
  - Leaving a **public** endpoint up that someone scripts against.

---

## 3. Concepts this tutorial teaches

### 3.1 Serverless = you hand over the server's lifecycle — scale to zero, scale out
- **Explanation:** "Serverless" does not mean there are no servers. It means you no longer decide *when* a server exists.
  - You give the platform a unit of code (a function or a container image) plus limits (memory, CPU, maximum instances, concurrency).
  - The platform starts instances when requests arrive, adds more as traffic grows, and removes them all when traffic stops. That last step is **scale to zero**.
- **Mental model:** a thermostat-controlled fleet. The input is the number of in-flight requests. The output is the number of instances, ⌈in-flight / concurrency⌉ roughly, clamped between min-instances and max-instances.
- **Analogy:** a VM is a restaurant that keeps its kitchen staffed 24/7. Serverless is a ghost kitchen that calls in cooks only when orders arrive, and sends them home when the queue is empty.
- **Misconception:** "Serverless means stateless code is optional" or "my instance will remember the last request." Instances are disposable. Anything in memory or on the in-memory filesystem can disappear between requests. Treat each instance as an amnesiac.

### 3.2 Cold starts and the min-instances knob
- **Explanation:** when a request arrives and no warm instance is free, Cloud Run must:
  1. get the image ready,
  2. start the container,
  3. run your entrypoint, here `bash` → `uv run` (or `pipenv run` in the Docker Hub image) → Python imports Flask, gunicorn and googletrans → gunicorn binds the port,
  4. only then hand over the request.

  That added latency is the **cold start**. `images/cloud-run-create.png` shows "Minimum number of instances: 0 — Set to 1 to reduce cold starts".
- **Mental model:** latency = cold-start tax (paid once per new instance) + per-request work. Global-scope work in the module the server loads, such as imports or a module-level `translator = Translator()` (the pattern `cli.py:11` uses; the server itself never imports `cli.py`), is paid during the cold start and then reused while the instance stays warm. Work inside the handler (`main.py:13`) is paid on every request.
- **Analogy:** a cold engine on a winter morning. The first drive is slow, the next ones are fine, until the car sits long enough to go cold again.
- **Misconception:** "Cold start = slow code (in the handler)." Mostly it is startup work: process launch, `uv run`'s environment check, imports and framework init, plus fetching the image. Keep the image lean too: this one installs `build-essential` (`Dockerfile:4,26`) and copies `.git` and screenshots into `/app` (no `.dockerignore`), which makes it bigger than it needs to be.

### 3.3 Request-based vs instance-based billing
- **Explanation:**
  - **Request-based:** you pay for CPU and memory only while an instance is handling at least one request (rounded up to 100 ms), plus a per-request fee. CPU is throttled outside requests.
  - **Instance-based:** you pay for the entire lifetime of each instance, with full CPU even between requests. Both options appear in `images/cloud-run-create.png`.
- **Mental model:** draw requests as spikes on a timeline.
  - VM cost is the whole rectangle under a flat line.
  - Request-based cost is only the area under the spikes. With concurrency, overlapping spikes on one instance are billed once.
  - Instance-based cost is the area under the "instance alive" step function.
- **Analogy:** a taxi meter that runs only while a passenger is in the car (request-based), versus renting the car for the day (instance-based or VM).
- **Misconception:** "Serverless is always cheaper." At steady high utilization, an always-busy VM or instance-based billing can be cheaper. Serverless wins for spiky, idle-heavy traffic, such as a student demo.

### 3.4 Cloud Run functions vs Cloud Run services: a function is a container you did not write
- **Explanation:**
  - With **functions** (path A) you hand over source plus `requirements.txt` plus an **entry-point name**. Cloud Build uses Google's buildpacks to produce a container whose process is `functions-framework --target <entry point>`, stores it in **Artifact Registry**, and deploys it on Cloud Run.
  - With **services** (path B) you hand over a finished image, and its ENTRYPOINT can be anything that speaks HTTP on `$PORT`.
  - This repo demonstrates that the two are the same thing underneath. `docker-entrypoint.sh:18` runs `uv run functions-framework --target translate_http`, i.e. the repo *hand-builds* the container that the functions platform would have built for you.
- **Mental model:**

  | | Cloud Run functions | Cloud Run service |
  |---|---|---|
  | You provide | source files + dependency list + entry-point name | an OCI/Docker image |
  | Who builds | Cloud Build + buildpacks (automatic) | you (`docker build`) |
  | Language/runtime | Google-managed runtimes, which Google deprecates on a schedule | anything that runs in a Linux amd64 container |
  | Who patches the OS/Python | Google | you (base image, e.g. `python:3.12-slim-bookworm`, `Dockerfile:2`) |
  | Typical unit | one handler | a whole app (FastAPI with many routes) |
- **Analogy:** a meal-kit service where you send the recipe and they cook it (functions), versus a food truck where you bring the fully equipped kitchen and they give you a parking spot and customers (Cloud Run).
- **Misconception:** "Cloud Functions and Cloud Run are unrelated products." Since 2024 "Cloud Functions (2nd gen)" has been rebranded **Cloud Run functions** and runs on Cloud Run. The README's first bullet already says "Cloud Run -> Functions" (README.md:8).

### 3.5 The container contract: `$PORT`, `0.0.0.0`, stateless, amd64
- **Explanation:** for a container to run on Cloud Run it must:
  - **listen for HTTP on the port given in the `PORT` environment variable** (default 8080), as the console itself says in `images/cloud-run-create.png`: "Should listen for HTTP requests on $PORT (default: 8080) and not rely on local state";
  - listen on **all interfaces** (`0.0.0.0`), not on `127.0.0.1`;
  - be built for **linux/amd64**;
  - not rely on local disk state.

  functions-framework satisfies the first two automatically:
  `@click.option("--host", envvar="HOST", type=click.STRING, default="0.0.0.0")` and
  `@click.option("--port", envvar="PORT", type=click.INT, default=8080)` (`_cli.py:32-33`, v3.9.2).
  The `Dockerfile` has no `EXPOSE`, and it does not need one.
- **Mental model:** Cloud Run hands your container an envelope with `PORT=8080` written on it, then knocks on that port from *outside* the container. If nobody answers in time, the revision fails to become ready.
- **Analogy:** a hotel assigns you a room number at check-in, and room service will only knock on that door. If you sit in a different room, or lock yourself in the bathroom (`127.0.0.1`), you get no food.
- **Misconception:** "`-p 8080:8080` or `EXPOSE` tells Cloud Run the port." No. `-p` is a local Docker host↔container mapping (Lecture 4's `port_toy`). Cloud Run uses its **container port** setting and injects `PORT`. `port_toy/gateway/gateway.py:51` follows the same `os.environ.get("PORT", …)` pattern.

### 3.6 Images, registries, tags vs digests (Docker Hub vs Artifact Registry)
- **Explanation:**
  - An image is addressed by `registry/repo:tag`. A **tag** is a movable label. A **digest** (`sha256:…`) is the immutable content hash.
  - When Cloud Run deploys `dlops/simple-translate-http:latest`, it resolves the tag to a digest and the revision is pinned to that digest.
  - **Artifact Registry** is GCP's private registry (`LOCATION-docker.pkg.dev/PROJECT/REPO/IMAGE:TAG`, where LOCATION is a region such as `us-central1` or a multi-region such as `us`; `cheese-app-v3/src/deployment/deploy_images/__main__.py:15` later uses the multi-region form `us-docker.pkg.dev/{project}/{repository_name}`). Path (A) silently uses it, and it is where production images should live (IAM-controlled, close to the service, no Docker Hub rate limits).
- **Mental model:** a tag is a sticky note on a box. The digest is the box's serial number. A deployment records the serial number.
- **Analogy:** "the latest edition" of a textbook vs its ISBN.
- **Misconception:** "If the instructor pushes a new `:latest`, my Cloud Run service updates." It does not, until you deploy a new revision. A related trap: a tag says nothing about *which code* is inside. `dlops/simple-translate-http:latest` today is still the 2024 pipenv build (Python 3.9.17, functions-framework 3.4.0), not the 2025 `uv` code in `main`, because nobody re-pushed the tag after the repo changed.

### 3.7 Two IAM identities: who may *call* the service vs who the service *is*
- **Explanation:**
  - **Invocation IAM** controls who may send requests. "Allow public access" (README.md:20, 98) makes the service public; the classic mechanism (and what `gcloud run deploy --allow-unauthenticated` does) is granting `roles/run.invoker` to the special principal `allUsers`. Cloud Run also has a newer "disable invoker IAM check" switch (`--no-invoker-iam-check`) that achieves the same effect without a binding; see Step 9 for how to tell which one your service uses. The older console label in the screenshot was "Allow unauthenticated invocations". With "Require authentication", callers must present a Google-signed identity token and hold `roles/run.invoker`.
  - **Runtime identity** is the service account the container runs *as* when it calls other Google APIs, such as Vertex AI in path (C). Client libraries get its token from the metadata server through Application Default Credentials, so no key file is involved (README.md:123).
- **Mental model:** two badges. A visitor pass at the front door (invoker) and an employee badge the code wears when it goes out to other buildings (service account).
- **Analogy:** the bouncer checks *your* ID at the club door, while the club's delivery driver carries the *club's* credentials when picking up supplies.
- **Misconception:** "Making my service public also makes it able to call Vertex AI," or the reverse. The two are independent. A public service with no runtime permissions can call nothing, and a private service can have powerful runtime permissions.

### 3.8 Services vs Jobs
- **Explanation:**
  - A **service** is request-driven, has a URL, and runs indefinitely and elastically.
  - A **job** runs a container to completion (no URL, no port). It runs N tasks (`images/cloud-run-job-01.png`: "Number of tasks 1") and succeeds when every task exits 0.
  - Container **arguments** replace the image's CMD and are appended to its ENTRYPOINT (`images/cloud-run-job-02.png`: "Arguments passed to the entry point command").
- **Mental model:** a service is a shop with opening hours. A job is a one-off delivery.
- **Misconception:** "A job that shows *succeeded* did its work." The gemini image's `cli.py:51-52` catches every exception raised inside `main()` and just prints it, so a failed Gemini call still exits 0. (Only failures at import time, e.g. in the module-level `GenerativeModel(...)` at `cli.py:11`, which sits outside the `try`, would exit non-zero.)

---

## 4. Step-by-step walkthrough

> Convention: **[README]** means the action is quoted from the README. **[added]** means the step or command is not in the README; it is written from the code or from standard `gcloud`/`docker` usage, and it is not part of the official tutorial.

**Step 0 — Get the code [added]**
- Action:
  `cd ~/Desktop/AC215 && git clone https://github.com/dlops-io/serverless-deployment.git && cd serverless-deployment && git log -1 --format='%h %ci'`
- What happens: you get `README.md`, `main.py`, `cli.py`, `Dockerfile`, `docker-entrypoint.sh`, `docker-shell.sh`, `pyproject.toml` and `uv.lock`.
- Checkpoint: `4eaf343 2025-10-20 21:53:06 -0400`.

**Step 1 — Local rehearsal of the container contract [added; uses repo scripts]**
- Commands:
  - `sh docker-shell.sh`. This only **builds**: the `docker run` lines are commented out (`docker-shell.sh:14-18`).
  - `docker run --rm -ti --name simple-translate -p 8080:8080 simple-translate`
  - In a second terminal: `curl "http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=fr"`
- Under the hood:
  1. `docker-shell.sh:11` runs `docker build -t $IMAGE_NAME --platform=linux/amd64/v2 -f Dockerfile .`.
  2. The Dockerfile starts from `python:3.12-slim-bookworm` (`Dockerfile:2`), installs `uv`, creates user `app` (`Dockerfile:22-35`), runs `uv sync --frozen` into `/.venv` (`Dockerfile:18,45`), and sets `ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]` (`Dockerfile:51`).
  3. At run time `docker-entrypoint.sh:3-12` prints diagnostics and activates the venv.
  4. Because `DEV` is unset, it runs `uv run functions-framework --target translate_http` (`docker-entrypoint.sh:18`).
  5. functions-framework loads `./main.py` (default source, `_function_registry.py:27`), finds `translate_http` (`main.py:6`) and starts gunicorn on `0.0.0.0:8080` with 1 worker and `cpu_count*4` threads (`_http/gunicorn.py:32-43`).
- You should see:
  - `Container is running!!!`, `Architecture: x86_64`, `Environment ready! Virtual environment activated.`, `Python version: Python 3.12.…`, `UV version: uv …` and `Activating virtual environment...` (`docker-entrypoint.sh:3-11`).
  - Then **silence**: gunicorn's log level is `"error"` (`_http/gunicorn.py:41`).
  - On `curl`, the container logs `request_json: None`, `request_args: ImmutableMultiDict([...])` and `Output: …` (`main.py:10-11,26`). curl prints the French text.
- If it fails:
  - `Bind for 0.0.0.0:8080 failed: port is already allocated`: use `-p 8081:8080` and curl port 8081.
  - Very slow build on an M-series Mac: expected, because amd64 is emulated. For a local-only test you can use the native line `docker-shell.sh:10`, but do not push that image to Cloud Run.
  - `500 Internal Server Error`: googletrans failed to reach or parse Google's unofficial endpoint (`main.py:25` has no `try/except`). Read the container log.
  - Ctrl-C does nothing without `-ti`: bash is PID 1 and `docker-entrypoint.sh:18` does not `exec`. Use `docker stop simple-translate`.

**Step 2 — Open Cloud Run functions and enable the APIs [README.md:7-14]**
- Action:
  - "In GCP go to [Cloud Run -> Functions](https://console.cloud.google.com/functions)"
  - Click the "{...} Write a function" button
  - "Enable the required APIs. Click "ENABLE""
- Under the hood: this enables the Build, Functions, Logging and Pub/Sub APIs (screenshot `images/cloud-function-enable-apis.png`). The link redirects into Cloud Run's "Create service" page with the **Function** card ("Use an inline editor to create a function", third card in `images/cloud-run-create.png`).
- Checkpoint: the Create service form appears.
- If it fails: billing is not linked to the project. Link a billing account first.

**Step 3 — Configure the function [README.md:16-21]**
- Action:
  - "Under the Configure -> "Service Name" add a name." For example, `simple-translate`.
  - "Under Endpoint URL -> "Runtime", select "Python 3.10"".
  - "Under the Authentication section. Select "Allow public access"".
  - Click "Create".
- Under the hood: Cloud Run creates a service and deploys the console's template function (`hello_http`) through Cloud Build. "Allow public access" adds the IAM binding `allUsers → roles/run.invoker`.
- Checkpoint: the service page opens with a Source tab containing `main.py` and `requirements.txt`.
- If it fails:
  - If "Python 3.10" is missing or marked deprecated (Python 3.10 reaches upstream EOL in Oct 2026), pick **Python 3.12**, which matches `pyproject.toml:6` and the versions locked in `uv.lock`.
  - If "Allow public access" errors with an org-policy message, your project's organization blocks `allUsers` (domain-restricted sharing). Choose "Require authentication" and use Step 9.

**Step 4 — Paste the code and requirements [README.md:23-68]**
- Action: replace `main.py` with the block at README.md:24-62, and `requirements.txt` with:
  ```
  functions-framework==3.*
  googletrans==4.0.0rc1
  ```
- Under the hood: `@functions_framework.http` (README.md:28) registers `hello_http(request)` as an HTTP handler. `request` is a `flask.Request`. `request.args` is the parsed query string (README.md:40). Defaults are `text="Welcome to AC215. Everyone knows the moon is made out of cheese"`, `src="en"`, `dest="es"` (README.md:47-49).
- Checkpoint: the editor shows no syntax errors, and the **Function entry point** field still says `hello_http`.
- Note: the README function is **`hello_http`**, while the repo's `main.py:6` is **`translate_http`**. If you paste the repo's `main.py` instead, you must change the entry-point field to `translate_http`.

**Step 5 — Deploy [README.md:70-71]**
- Action: "Click on "Save and Deploy" to deploy the code as a CLoud Function". The button may be labelled "Save and redeploy" in today's console.
- Under the hood: the source is uploaded → Cloud Build runs the Python buildpack (`pip install -r requirements.txt`) → the image is pushed to Artifact Registry → a new Cloud Run revision is created → traffic is shifted to it.
- Checkpoint: a green check on the new revision after "a few minutes" (README.md:71).
- If it fails:
  - Open the build log link. Typical causes are a typo in `requirements.txt` and an entry-point mismatch: `MissingTargetException: File /workspace/main.py is expected to contain a function named 'hello_http'. Found: ... instead` (message format from `_function_registry.py:57-61`).
  - Dependency resolution failures if you changed `googletrans` to a newer version (see §6).

**Step 6 — Test the function [README.md:73-81]**
- Action: copy the URL from the details page and append `?text=Good afternoon everyone&src=en&dest=fr`. Repeat with `dest=el` and `dest=hi` (README.md:79-81).
  - From a terminal [added]: `curl -G "https://YOUR-URL/" --data-urlencode "text=Ready to go home?" -d src=en -d dest=hi`
- Under the hood: the HTTPS request hits Google's front end → IAM invoker check → an instance (cold-started if none is warm) → `hello_http` → googletrans → plain-text response.
- You should see:
  - With no parameters: a Spanish sentence (the default `dest="es"`).
  - With parameters: the French, Greek and Hindi text.
  - In the **Logs** tab: the `request_json:`, `request_args:` and `Output:` lines from the `print` calls (README.md:42-43,58).
- Note: your URL will look like `https://<name>-<project-number>.<region>.run.app` (see `images/cloud-run-create.png`). It will not match the README's `https://us-central1-ac215-project.cloudfunctions.net/simple-translate` (README.md:76), which is the old 1st-gen format.
- If it fails:
  - `403 Forbidden`: public access was not granted. Fix the Security/Authentication setting.
  - `500`: check Logs for a googletrans traceback.
  - The first call is slow: cold start.

**Step 7 — Create a Cloud Run service from an existing image [README.md:90-103]**
- Action:
  - "In GCP go to [Cloud Run](https://console.cloud.google.com/run)" → "Deploy container".
  - "If you have not enabled the required APIs, a popup will showup" (README.md:93): enable them (Cloud Run Admin API).
  - "Select the "Deploy one revision from an existing container image" and put in the image name: `dlops/simple-translate-http:latest`"
  - Give it a service name.
  - "Under Authentication, select "Allow public access"" → Create.
- CLI equivalent [added]:
  `gcloud run deploy simple-translate-run --image=docker.io/dlops/simple-translate-http:latest --region=us-central1 --allow-unauthenticated`
- Under the hood:
  1. Cloud Run resolves `:latest` to digest `sha256:77751cec…`.
  2. It creates a revision whose single container gets `PORT=8080`.
  3. The image's entrypoint is `["/bin/bash","./docker-entrypoint.sh"]`, which runs `pipenv run functions-framework --target translate_http`. That is the image's `/app/docker-entrypoint.sh:5-10`, identical to the `pipenv` branch, **not** to `main`. The functions-framework inside is 3.4.0, whose gunicorn config is fixed at 1 worker × **1024 threads**, `timeout 0`, log level `"error"` (it ignores `THREADS`/`GUNICORN_LOG_LEVEL`); the host/port contract (`_cli.py:32-33`) is the same as in 3.9.2.
  4. Cloud Run waits for the port to open (startup probe) and then routes traffic.
- Checkpoint: the service shows a green check and a URL. The form matches `images/cloud-run-create.png`: request-based billing, auto scaling, min instances 0.
- If it fails:
  - `The user-provided container failed to start and listen on the port defined provided by the PORT=8080 environment variable…`: you changed the container port, added `DEV=1`, or used an arm64 image.
  - An image-pull error from Docker Hub: retry, or build and push your own image to Artifact Registry (Step 11).

**Step 8 — Test the service [README.md:105-113]**
- Action: the same three query strings as Step 6, against the service URL.
- Expected: the translated text. The **no-parameter default differs** from Step 6. The image's `main.py:15` uses `"Welcome to AC215"`, while the README function uses the longer cheese sentence.
- Checkpoint for understanding: in the service's **Revisions** tab, note the image digest. In **Metrics**, the "instance count" drops back to 0 once the service has been idle for a while (Cloud Run may keep an idle instance around for up to about 15 minutes).

**Step 9 — Lock it down and call it with an identity token [added; teaches invocation IAM]**
- Console: Service → Security → Authentication → "Require authentication". Or remove the public binding:
  `gcloud run services remove-iam-policy-binding simple-translate-run --region=us-central1 --member=allUsers --role=roles/run.invoker`
- First check which public-access mechanism you have: `gcloud run services get-iam-policy simple-translate-run --region=us-central1`. If `allUsers` is not listed but the URL is still public, the invoker IAM check is disabled; turn it back on with `gcloud run services update simple-translate-run --region=us-central1 --invoker-iam-check`.
- Test:
  - `curl -i "https://YOUR-URL/?text=hello&dest=fr"` → `403`.
  - `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" "https://YOUR-URL/?text=hello&dest=fr"` → `200`. This works as the project owner, because your user already has `run.invoker`.

**Step 10 — Bonus: Cloud Run Job with a service account [README.md:121-147]**
- Action:
  - "Click the "Deploy container" and pick "Job"".
  - Container Image URL `dlops/simple-translate-gemini`.
  - Job name.
  - Expand "Container(s), Volumes, Connections, Security" → "SECURITY" tab → pick a service account with Vertex AI access.
  - "Select the check box "Execute job immediately"".
  - Without arguments the README says the job runs "using the default arguments" (README.md:141; but see §9 erratum 8).
  - Optional arguments (README.md:142-143): "Select "CONTAINER(S)" tab and in the SETTINGS area" → "For Container arguments type in: cli.py --text Ready+to+go+home?". `images/cloud-run-job-02.png` shows this entered as **one** argument chip containing spaces.
  - Click Create (the README does not say it, but the screenshot's button is "Create").
- Under the hood:
  1. The job runs the image's `/docker-entrypoint.sh` with your arguments.
  2. That script does `args="$@"` then `pipenv run python $args`. The unquoted `$args` word-splits the single chip into `cli.py`, `--text`, `Ready+to+go+home?`, so the command becomes `python cli.py --text Ready+to+go+home?`.
  3. `cli.py:30` turns `+` back into spaces.
  4. Vertex AI is called **as the attached service account**. There is no key file and no `vertexai.init`; the project comes from Application Default Credentials (the metadata server) and the location falls back to the SDK default (`us-central1`). The image pins `google-cloud-aiplatform==1.70.0` in its `Pipfile.lock`.
- Checkpoint: Jobs → your job → Executions → Logs show the `AC215` ASCII art, `Input: Ready to go home?`, then `Generated text:` and an Italian translation (default `--dest it`). **Or** they show `Error occurred while generating content: …`.
- If it fails:
  - `Permission 'iam.serviceaccounts.actAs' denied`: you need `roles/iam.serviceAccountUser` on that service account.
  - `403 … aiplatform` in the logs: the service account lacks `roles/aiplatform.user`, or the Vertex AI API is not enabled.
  - `404 … gemini-1.5-flash-001`: the hard-coded model (image `cli.py:11`) has been retired on Vertex AI (Gemini 1.5 models were retired in 2025; verify). The execution may still show **Succeeded** because the exception is swallowed (`cli.py:51-52`).

**Step 11 — Extension: ship *your* build through Artifact Registry [added]**
```
gcloud artifacts repositories create ac215-images --repository-format=docker --location=us-central1
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build --platform=linux/amd64 -t us-central1-docker.pkg.dev/PROJECT_ID/ac215-images/simple-translate-http:v1 .
docker push us-central1-docker.pkg.dev/PROJECT_ID/ac215-images/simple-translate-http:v1
gcloud run deploy simple-translate-mine --image=us-central1-docker.pkg.dev/PROJECT_ID/ac215-images/simple-translate-http:v1 --region=us-central1 --allow-unauthenticated
```
- This deploys the **current `main`** code (`uv`, Python 3.12) instead of the 2024 pipenv image.
- Use an immutable tag (`v1`, `v2`) rather than `latest`.

**Step 12 — Clean up [added; the README has none]**
- Delete:
  - the function and service (`gcloud run services delete NAME --region=us-central1`);
  - the job (`gcloud run jobs delete NAME --region=us-central1`);
  - the Artifact Registry repositories and images (yours, plus the auto-created one from Step 5);
  - the auto-created source bucket in Cloud Storage.
- Confirm in Billing → Reports over the next day.

---

## 5. Code tour

```
serverless-deployment/            (main @ 4eaf343)
|- README.md               console click-path for Functions, Cloud Run service, Cloud Run job
|- main.py                 the HTTP handler translate_http(request) -- what Cloud Run serves
|- cli.py                  older sync CLI translator (googletrans 4.0.0rc1); never run by the entrypoint
|- Dockerfile              python:3.12-slim-bookworm + uv; non-root user; venv at /.venv
|- docker-entrypoint.sh    DEV=1 -> interactive bash; else run functions-framework on $PORT
|- docker-shell.sh         builds image "simple-translate" for linux/amd64/v2 (run lines commented out)
|- pyproject.toml          deps: art, functions-framework>=3.9.2, googletrans==4.0.0rc1; Python 3.12 only
|- uv.lock                 exact pins (functions-framework 3.9.2, flask 3.1.2, gunicorn 23.0.0, httpx 0.13.3, ...)
|- images/*.png            console screenshots referenced by README
|- __pycache__/main.cpython-312.pyc   accidentally committed bytecode
`- .gitignore              misc + leftovers (/docker-volumes, trainer.tar.gz)
```

**`main.py:1-13`**
```python
from googletrans import Translator
import functions_framework


@functions_framework.http
def translate_http(request):
    request_json = request.get_json(silent=True)
    request_args = request.args

    print("request_json:", request_json)
    print("request_args:", request_args)

    translator = Translator()
```
- `@functions_framework.http` registers the function in functions-framework's registry as an HTTP-signature function. The CLI's `--target translate_http` later looks it up *by name*.
- `request` is a Flask `Request`. `get_json(silent=True)` returns `None` instead of raising when the body is not JSON. With a browser GET it is always `None`.
- `request.args` is an immutable multi-dict of the query string.
- The `print` calls go to stdout, and Cloud Run ships stdout to Cloud Logging. `PYTHONUNBUFFERED=1` (`Dockerfile:14`) ensures they are not lost in a buffer.
- `Translator()` is constructed **per request**. That is cheap, but it means no HTTP connection reuse across requests (compare `cli.py:11`, which does it at module scope).

**`main.py:15-28`**
```python
    text = "Welcome to AC215"
    src = "en"
    dest = "es"
    if request_args and "text" in request_args:
        text = request_args["text"]
    if request_args and "src" in request_args:
        src = request_args["src"]
    if request_args and "dest" in request_args:
        dest = request_args["dest"]

    results = translator.translate(text, src=src, dest=dest)
    print("Output:", results.text)

    return results.text
```
- Each query parameter is optional and overrides a default.
- `translator.translate(...)` is a **blocking network call** to Google's unofficial web-translate endpoint (sync API of googletrans 4.0.0rc1). It runs inside the request, so its latency is billed request time.
- There is no `try/except`, so any network or parse error becomes an HTTP 500.
- Returning a `str` makes Flask send `200 text/html; charset=utf-8` with that body.

**`docker-entrypoint.sh:10-19`**
```bash
# Activate virtual environment
echo "Activating virtual environment..."
source /.venv/bin/activate

if [ "${DEV}" = 1 ];
then
  exec /bin/bash
else
  uv run functions-framework --target translate_http
fi
```
- `source /.venv/bin/activate` puts the venv on `PATH`. `uv run` would find `/.venv` anyway, through `UV_PROJECT_ENVIRONMENT` (`Dockerfile:18`).
- `DEV=1` gives a developer shell. Never set it on Cloud Run: bash with no TTY reads EOF and exits, so nothing listens on `$PORT`.
- The production branch launches functions-framework, which reads `PORT`/`HOST` from the environment.
- There is no `exec` on that line, so bash stays PID 1, and SIGTERM sent on scale-down is not forwarded to gunicorn.
- `uv run` also re-checks the lock and environment at every start, which adds cold-start time, and can trigger installs if `uv.lock` is stale (§6).

**`Dockerfile:13-18`**
```dockerfile
# Tell Python to disable buffering so we don't lose any logs.
ENV PYTHONUNBUFFERED=1

# Tell uv to copy packages from the wheel into the site-packages
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/.venv
```
- The venv lives at `/.venv`, **outside** `/app`. The commented dev run (`docker-shell.sh:15`) bind-mounts your laptop folder over `/app`, and the venv survives that mount because it is not under `/app`.
- `UV_LINK_MODE=copy` avoids hard-link warnings across filesystems.

**`Dockerfile:37-51`**
```dockerfile
# Switch to the new user
USER app
WORKDIR /app

# Copy dependency files first for better layer caching
COPY --chown=app:app pyproject.toml uv.lock* ./

# Install dependencies in a separate layer for better caching
RUN uv sync --frozen

# Copy the rest of the source code
COPY --chown=app:app . ./

# Entry point
ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]
```
- Running as non-root `app` (uid 1000) is fine on Cloud Run.
- Copying the dependency files first means a code-only change reuses the cached `uv sync` layer.
- `--frozen` installs exactly what `uv.lock` says, without checking that it matches `pyproject.toml`.
- `COPY . ./` has no `.dockerignore`, so `.git/`, `images/` and `__pycache__/` end up in the image. The published image confirms it: `/app/.git/...` is in its last layer.
- `ENTRYPOINT` is exec-form, so Cloud Run job "arguments" would be appended after `docker-entrypoint.sh`. This script ignores them.

**`docker-shell.sh:6-18`**
```bash
export IMAGE_NAME="simple-translate"
export BASE_DIR=$(pwd)

# Build the image based on the Dockerfile
#docker build -t $IMAGE_NAME -f Dockerfile .
docker build -t $IMAGE_NAME --platform=linux/amd64/v2 -f Dockerfile .

# Run Container
# docker run --rm --name $IMAGE_NAME -ti \
# -v "$BASE_DIR":/app \
# -p 8080:8080 \
# -e DEV=1 \
# $IMAGE_NAME
```
- The build targets **amd64**, the architecture Cloud Run executes, even on an Apple Silicon Mac. `/v2` is the x86-64-v2 micro-architecture variant, which is why the Docker Hub image reports `amd64 v2`.
- Run is disabled. Commit `cba4910` (2025-03-25) commented it out.
- The image name is `simple-translate`, **not** `dlops/simple-translate-http`. Nothing in the repo tags or pushes the image the README deploys.

**`pyproject.toml:6-11`**
```toml
requires-python = ">=3.12,<3.13"
dependencies = [
    "art>=6.5",
    "functions-framework>=3.9.2",
    "googletrans==4.0.0rc1",
]
```
- `googletrans==4.0.0rc1` is the 2020 *synchronous* API. It drags in `httpx==0.13.3` (`uv.lock:230-231`).
- Simple-translate (L1/L2) has since moved to `googletrans==4.0.2`, which is **async** (`simple-translate/cli.py:25-31` uses `async with Translator(...)` / `await translator.translate`). Do not mix the two.
- `uv.lock:20-22` marks the project `source = { virtual = "." }`: the project itself is not installed as a package, only its dependencies.

**`README.md:64-68` (the function's dependency list)**
````
* Replace the content of `requirements.txt` with the following:
```
functions-framework==3.*
googletrans==4.0.0rc1
```
````
- Functions use `requirements.txt` (pip), and the container uses `pyproject.toml`/`uv.lock`. Same two libraries, different manifests.
- `art` is absent here because the function never prints ASCII art.

**functions-framework v3.9.2 `src/functions_framework/_cli.py:32-33`** (external, the version locked in `uv.lock:136`)
```python
@click.option("--host", envvar="HOST", type=click.STRING, default="0.0.0.0")
@click.option("--port", envvar="PORT", type=click.INT, default=8080)
```
- This is the whole Cloud Run container contract in two lines: bind all interfaces, and take the port from `$PORT`.
- `--target` similarly falls back to the env var `FUNCTION_TARGET` (`_cli.py:24`).

**functions-framework v3.9.2 `src/functions_framework/_http/gunicorn.py:32-43`** (external)
```python
        threads = int(os.environ.get("THREADS", (os.cpu_count() or 1) * 4))

        global TIMEOUT_SECONDS
        TIMEOUT_SECONDS = int(os.environ.get("CLOUD_RUN_TIMEOUT_SECONDS", 0))

        self.options = {
            "bind": "%s:%s" % (host, port),
            "workers": int(os.environ.get("WORKERS", 1)),
            "threads": threads,
            "loglevel": os.environ.get("GUNICORN_LOG_LEVEL", "error"),
            "limit_request_line": 0,
        }
```
- In production the Flask app is served by **gunicorn**: one worker process with several threads (`cpu_count × 4`).
- So one instance processes a few requests truly concurrently. Cloud Run's "max concurrent requests per instance" setting sits on top of this.
- The `"error"` log level is why a healthy container prints nothing.
- This is the 3.9.2 code your own `main` build runs (Step 1, Step 11). The Docker Hub image deployed in Step 7 has functions-framework **3.4.0**, whose `GunicornApplication` hard-codes `"workers": 1, "threads": 1024, "timeout": 0, "loglevel": "error"` with no env-var overrides.

**Image `dlops/simple-translate-gemini@sha256:ec05eb27…`, file `/docker-entrypoint.sh:5-14`** (read from the image layer; not in any repo)
```bash
args="$@"
echo $args

if [[ -z ${args} ]]; 
then
    pipenv shell python cli.py
    #pipenv run python cli.py --text "Ready to go home?"
else
  pipenv run python $args
fi
```
- The job's "Container arguments" arrive as `$@` (one argv element per argument chip).
- `args="$@"` flattens them into one string, and the unquoted `$args` re-splits it on spaces. That is what lets the README's single chip `cli.py --text Ready+to+go+home?` become three arguments. It also means a multi-word `--text "Ready to go home?"` would break into separate words, whether typed in one chip or several.
- That is why README.md:143 encodes spaces as `+` and the image's `cli.py:30` does `text = text.replace("+"," ")`.
- The image sets no `WORKDIR`, so its files live at `/` (`ADD . /`) and `./docker-entrypoint.sh` resolves to `/docker-entrypoint.sh`.

---

## 6. Gotchas and common errors

1. **Wrong CPU architecture (Apple Silicon).**
   - Symptom: Cloud Run deploy fails with an error that the image manifest "must support amd64/linux", or the revision logs `exec format error`.
   - Cause: you built natively on an M-series Mac (arm64) and pushed that image yourself.
   - Fix: build with `--platform=linux/amd64` as `docker-shell.sh:11` does, or with `docker buildx build --platform linux/amd64 …`. The course images are amd64 only (verified on Docker Hub).

2. **`sh docker-shell.sh` "does nothing".**
   - Symptom: the build finishes and you are back at your prompt with no container.
   - Cause: the run lines are commented out (`docker-shell.sh:14-18`).
   - Fix: run `docker run --rm -ti -p 8080:8080 simple-translate` yourself (Step 1).

3. **Local port conflict.**
   - Symptom: `Bind for 0.0.0.0:8080 failed: port is already allocated`.
   - Cause: another container or app holds 8080.
   - Fix: `docker ps` and stop it, or map `-p 8081:8080`. The right side must stay 8080 unless you also set `-e PORT=…`.

4. **Container never becomes ready on Cloud Run.**
   - Symptom: "The user-provided container failed to start and listen on the port defined provided by the PORT=8080 environment variable…".
   - Causes:
     - (a) you changed the service's container port to something the app does not listen on;
     - (b) you set env var `DEV=1`, so `docker-entrypoint.sh:14-16` execs an interactive bash that exits immediately with no TTY (in the Docker Hub image the same branch runs `pipenv shell` instead, image `/app/docker-entrypoint.sh:5-7`, which likewise never starts the server);
     - (c) a custom server binds `127.0.0.1`;
     - (d) a wrong architecture.
   - Fix: leave port 8080 and do not set `DEV`. functions-framework already binds `0.0.0.0:$PORT` (`_cli.py:32-33`).

5. **Entry-point mismatch in Cloud Run functions.**
   - Symptom: the build or start fails with `File /workspace/main.py is expected to contain a function named 'hello_http'. Found: 'translate_http' instead` (format from `_function_registry.py:57-61`).
   - Cause: README code uses `hello_http` (README.md:29), the repo uses `translate_http` (`main.py:6`), and the console field must match.
   - Fix: make the "Function entry point" field equal the `def` name.

6. **Copying the newer googletrans.**
   - Symptom: `AttributeError: 'coroutine' object has no attribute 'text'`, plus a "coroutine was never awaited" warning.
   - Cause: `googletrans==4.0.2` (used in `simple-translate/pyproject.toml:9`) is async, but `main.py:25-26` uses the sync API.
   - Fix: keep `googletrans==4.0.0rc1` (README.md:67, `pyproject.toml:10`) or rewrite the handler with `asyncio.run(...)`.

7. **HTTP 500 from a perfectly deployed service.**
   - Symptom: `Internal Server Error`, with an `httpx`/JSON traceback in Logs.
   - Cause: googletrans scrapes Google's unofficial endpoint, which may rate-limit or block datacenter IPs or change format. Evidence: the course's own `simple-translate` added an error message to this effect in commit `62f821b` (2026-09-08), at `simple-translate/cli.py:33-37`.
   - Fix: retry, add `try/except` that returns a 502 with a message, or swap in the official Cloud Translation API with a service account (what `mega-pipeline` does).

8. **403 Forbidden on your URL.**
   - Causes:
     - "Require authentication" is selected;
     - public access was blocked by an organization policy (domain-restricted sharing rejects `allUsers`);
     - your identity token was minted for the wrong audience.
   - Fix: choose "Allow public access" (README.md:20, 98), or call with `curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" URL` and grant teammates `roles/run.invoker`.

9. **`iam.serviceaccounts.actAs` denied (Job step).**
   - Cause: attaching a service account requires `roles/iam.serviceAccountUser` on it.
   - Also: the README's screenshot uses `mega-pipeline`, a service account from the instructor's project that does not exist in yours.
   - Fix: create your own service account, grant it `roles/aiplatform.user`, and grant yourself Service Account User on it.

10. **Job "Succeeded" but no translation.**
    - Cause: the image hard-codes `gemini-1.5-flash-001` (image `cli.py:11`), which has been retired. The 404 is raised by `model.generate_content` inside `main()`'s `try` (`cli.py:44`); `cli.py:51-52` catches it and prints `Error occurred while generating content: …`, so the process still exits 0.
    - Fix: read the execution's logs, not the status badge. To modernise, rebuild with a current model name. The image source is not published; its entrypoint is quoted in §5, and its `cli.py` lines are cited in §3.8, §4 Step 10, §5 and §9.

11. **Spaces in job arguments get mangled.**
    - Cause: `args="$@"` then unquoted `$args` (image `/docker-entrypoint.sh:5,13`).
    - Fix: use `+` for spaces as README.md:143 does. Splitting the arguments into separate chips does **not** help: the script joins all chips with spaces and re-splits them. Only a rebuilt image using `pipenv run python "$@"` would preserve multi-word arguments.

12. **"I pushed a new image but nothing changed."**
    - Cause: a Cloud Run revision is pinned to the digest resolved at deploy time.
    - Fix: deploy a new revision (`gcloud run deploy … --image …:v2`), ideally with immutable tags.

13. **Stale `uv.lock` makes cold starts slow or fail.**
    - Cause: if you add a dependency to `pyproject.toml` without running `uv lock`, `uv sync --frozen` (`Dockerfile:45`) silently installs the *old* set. `uv run` (`docker-entrypoint.sh:18`) then re-resolves and installs at **container start**, needing network and time on every cold start.
    - Fix: run `uv lock` before `docker build`. Consider `uv run --frozen`, or calling `/.venv/bin/functions-framework` directly.

14. **Bloated image and leaked files.**
    - Cause: there is no `.dockerignore`, so `COPY . ./` (`Dockerfile:48`) copies `.git/`, screenshots, `__pycache__`, and a host `.venv` if you created one. The published `dlops/simple-translate-http` image does contain `/app/.git`.
    - Fix: add a `.dockerignore` with `.git`, `images/`, `__pycache__/`, `.venv/` and `secrets/`. Never keep key files inside the build context.

15. **Runtime drift across the three paths.**
    - The function uses Python 3.10 (README.md:19), the Docker Hub image uses Python 3.9.17 (image env `PYTHON_VERSION=3.9.17`), and the repo pins 3.12 (`pyproject.toml:6`, `Dockerfile:2`).
    - functions-framework drifts too: whatever `3.*` resolves to at build time for the function (README.md:66), 3.4.0 in the Docker Hub image (its `Pipfile.lock`), 3.9.2 in the repo (`uv.lock:135-136`). Their gunicorn threading differs (1024 fixed threads vs `cpu_count × 4`).
    - Symptom: something works locally (3.12) and differs in the cloud.
    - Fix: select Python 3.12 for the function, and build and deploy your own image (Step 11).

16. **Surprise charges.**
    - Causes: min instances ≥ 1, instance-based billing, forgotten Artifact Registry images and source buckets from function builds, or a public URL being hammered.
    - Fix: Step 12 cleanup. Set max instances low (e.g. 2–3) on student projects, and keep min instances at 0.

17. **No graceful shutdown.**
    - Cause: bash stays PID 1 because there is no `exec` at `docker-entrypoint.sh:18`. On scale-in, Cloud Run's SIGTERM is not forwarded, and the instance is killed after the grace period.
    - Effect: harmless here because the app is stateless. In apps that flush buffers or close database connections, use `exec uv run …`.

---

## 7. Where this sits in the course

**What earlier lectures gave you**
- **L1–L2 (`simple-translate`):** the same translator as a CLI on a VM, then in a uv venv, then in a Docker image pushed to Docker Hub (`simple-translate/README.md:186-191`). The VM model meant *you* provisioned, patched, paid for idle time and deleted the machine (`simple-translate/README.md:62`).
- **L3 (`mega-pipeline`):** a service-account JSON key file (`mega-pipeline.json`) placed in each component's `secrets/` folder (`mega-pipeline/README.md:95-99`) and pointed at by `ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` (`mega-pipeline/README.md:195`).
- **L4 (`port_toy`):** ports, published vs internal ports, and reading the port from `$PORT` (`port_toy/gateway/gateway.py:51`).
- **L10 (`cheese-app-v0`):** the convention of a `secrets` folder outside the repo, mounted into the container at `/secrets` (`cheese-app-v0/README.md:146`: "Mount `../../secrets` into the container at `/secrets`").
- **L13 (`model-training`):** serverless **training** (Vertex AI custom jobs, `model-training/cli.sh:32-37`, with prebuilt images from Artifact Registry `us-docker.pkg.dev/vertex-ai/training/...`, `cli.sh:31`).

**What L14 adds:** serverless **serving**.
- HTTP functions with functions-framework.
- The Cloud Run container contract.
- Autoscaling, scale to zero, cold starts and request-based billing.
- Invoker IAM vs runtime service accounts. The service account replaces the mounted JSON key once code runs in Google's cloud.
- Jobs for run-to-completion work.
- This is exactly what Milestone 3 asks for: "Deploy your model or API using Cloud Functions or Cloud Run" (`milestone3.md:47-51`).

**What builds on it next**
- **L15 (`model-deployment`, `ml-workflow`):** managed model serving on Vertex AI Endpoints and Pipelines. These have the same "give Google a container or model, get an endpoint" shape, but with an ML-specific registry and serving stack.
- **L18 (`cheese-app-v2`):** a FastAPI backend, which is a natural Cloud Run service with many routes.
- **L20 (`cheese-app-v3` Pulumi):** pushes images to Artifact Registry programmatically (`cheese-app-v3/src/deployment/deploy_images/__main__.py:15`).
- **L22 (Kubernetes):** you take the autoscaling knobs back into your own hands.

**Concrete diff vs the previous version of this app (`simple-translate` main → `serverless-deployment` main)**, from `git diff --no-index --stat` on the shared files (`Dockerfile.txt` compared as `Dockerfile`):
```
 .gitignore            |  4 +-
 Dockerfile            | 36 ++++++++++++---
 cli.py                | 81 ++++++++++++---------------------
 docker-entrypoint.sh  | 19 ++++++++   (new)
 docker-shell.sh       | 13 ++++--
 main.py               | 28 ++++++++++++  (new)
 pyproject.toml        |  7 +--
 7 files changed, 119 insertions(+), 69 deletions(-)
```
The meaningful changes:
- **+ `main.py`**: the CLI becomes an HTTP handler, with query-string parameters instead of argparse flags.
- **+ `docker-entrypoint.sh`**: the container now *serves* (functions-framework) instead of dropping you into a shell.
- **`Dockerfile`**: non-root user `app`, venv at `/.venv`, dependency-first layer caching with `uv sync --frozen`, `ENTRYPOINT` script. The L2 solution `Dockerfile.txt` ran as root with `CMD ["-c", "source .venv/bin/activate && exec bash"]`.
- **`pyproject.toml`**: + `functions-framework>=3.9.2`; `googletrans` pinned *back* to the sync `4.0.0rc1` (simple-translate uses async `4.0.2`); Python narrowed to 3.12.
- **`docker-shell.sh`**: builds for `linux/amd64/v2`, with run commented out.

**Within this repo, `pipenv` → `main`** (four commits on 2025-10-20: `d469a52` "upgraded to uv", `1a7798a` "removed pipfile", `212975e` "updated readme", `4eaf343` "updates"):
- `d469a52`: Python 3.9 → 3.12; `pipenv sync` → `uv sync --frozen`; `pipenv run functions-framework` → `uv run functions-framework`; `pipenv shell` → `exec /bin/bash`.
- `1a7798a`: `Pipfile` and `Pipfile.lock` deleted.
- `212975e`: the README was relabelled from "Allow unauthenticated invocations" to "Allow public access", and the Functions link to "Cloud Run -> Functions".
- `4eaf343`: added the paragraph at README.md:123 explaining why a deployed container needs a service account.
- The Docker Hub image the README deploys was **not** rebuilt after this change.

---

## 8. Exercises

**E1 — Change the port, predict, run (hands-on).**
- Task: after Step 1, run `docker run --rm -ti -e PORT=9090 -p 8080:8080 simple-translate`, then `curl localhost:8080`. Predict the result first. Then fix it *without* changing `-e PORT=9090`.
- Answer:
  - functions-framework now binds `0.0.0.0:9090` (`_cli.py:33` reads `PORT`), while Docker forwards host 8080 → container 8080, where nothing listens. curl fails with "Empty reply from server" or a connection reset.
  - Fix: `-p 8080:9090`. This is exactly what Cloud Run does in the other direction: it chooses `PORT` and connects to it.

**E2 — Global vs per-request initialisation (hands-on and conceptual).**
- Task: move `translator = Translator()` from `main.py:13` to module scope, as `cli.py:11` does. Rebuild and run, and send 20 requests with `for i in $(seq 20); do curl -s -o /dev/null -w "%{time_total}\n" "http://localhost:8080/?text=hi&dest=fr"; done`. Which requests get faster, and what new risk did you introduce?
- Answer:
  - The very first request after start is not faster, because the object is now built during import, which is part of the cold start.
  - Warm requests may get slightly faster: the object and its HTTP client are reused, so connections can be kept alive.
  - The risk: gunicorn runs several threads per worker (`gunicorn.py:32`), so one `Translator` is now shared across concurrent requests. You must trust it to be thread-safe (or use a lock, or a per-thread instance).
  - General rule: do expensive, *thread-safe* setup (model loading!) at global scope, so that it is paid once per instance.

**E3 — "coroutine has no attribute text" (debugging).**
- Task: a classmate deploys path A with `requirements.txt` containing `functions-framework==3.*` and `googletrans==4.0.2`. Every request returns 500, and Logs show `AttributeError: 'coroutine' object has no attribute 'text'`. Why?
- Answer:
  - googletrans 4.0.2 (used by `simple-translate/pyproject.toml:9`) made `Translator.translate` async (`simple-translate/cli.py:25-31`).
  - In the sync handler, `translator.translate(...)` returns an un-awaited coroutine, and `.text` on it fails at `results.text`.
  - Fix: pin `googletrans==4.0.0rc1` (README.md:67), or write
    `result = asyncio.run(_translate(text, src, dest))` with an `async def _translate` that uses `async with Translator() as t: return (await t.translate(...)).text`.

**E4 — Entry point mismatch (debugging).**
- Task: you paste the repo's `main.py` (function `translate_http`) into the inline editor and click deploy. The deploy fails. What is the message, and what are two fixes?
- Answer:
  - functions-framework cannot find the configured target: `File /workspace/main.py is expected to contain a function named 'hello_http'. Found: 'translate_http' instead` (message template `_function_registry.py:57-61`).
  - Fix 1: set the console's "Function entry point" to `translate_http`.
  - Fix 2: rename the function back to `hello_http`.

**E5 — Revision never becomes ready (debugging).**
- Task: on your Cloud Run service built from `main` (Step 11) you add the environment variable `DEV=1` "to see more logs" and deploy. The new revision fails with "failed to start and listen on the port defined provided by the PORT=8080 environment variable". Explain with file and line.
- Answer:
  - `docker-entrypoint.sh:14-16`: with `DEV=1` the script runs `exec /bin/bash` instead of functions-framework.
  - On Cloud Run there is no TTY or stdin, so bash reads EOF and exits immediately. Nothing ever listens on 8080, so the startup probe fails.
  - Remove `DEV`. For more logs, set `GUNICORN_LOG_LEVEL=info` (`gunicorn.py:41`, functions-framework 3.9.2) or add `print`s.
  - On the Step 7 Docker Hub image the DEV branch is `pipenv shell` (image `/app/docker-entrypoint.sh:5-7`), with the same result, and `GUNICORN_LOG_LEVEL` does nothing there because functions-framework 3.4.0 hard-codes `"loglevel": "error"`.

**E6 — Concurrency and cost (conceptual).**
- Task: your endpoint gets a steady 10 requests/s, and each spends 2 s waiting on the translate API. Compare max concurrency 80 vs 1 in (a) instance count and (b) billed vCPU-seconds per second under request-based billing.
- Answer:
  - Little's law: in-flight L = λ·W = 10 × 2 = 20.
  - At concurrency 80, about 1 instance holds all 20, and you pay about 1 instance-second per second, because overlapping requests on one instance are billed once.
  - At concurrency 1, about 20 instances are needed, so about 20 instance-seconds per second: roughly 20× the CPU and memory bill, plus 20× the cold starts during ramp-up.
  - The catch, for your own `main` build (functions-framework 3.9.2): one instance only has `cpu_count×4` gunicorn threads (`gunicorn.py:32`), so if `os.cpu_count()` reports 1 (4 threads), the requests beyond 4 queue inside that instance. That is a reason to tune `THREADS` or lower Cloud Run concurrency to match. The Step 7 Docker Hub image (functions-framework 3.4.0) has a fixed 1024 threads, so it does not hit this limit.

**E7 — Two identities (conceptual and IAM).**
- Task: you switch the service to "Require authentication" and want (a) your teammate to call it and (b) the job in Step 10 to call Gemini. List the principal, the role and the resource for each grant, plus the extra grant *you* need to attach the service account.
- Answer:
  - (a) Principal `user:teammate@…`, role `roles/run.invoker`, on the Cloud Run service. The teammate then calls with `Authorization: Bearer $(gcloud auth print-identity-token)`.
  - (b) Principal `serviceAccount:translate-job@PROJECT.iam.gserviceaccount.com`, role `roles/aiplatform.user`, on the project. You attach it under the job's Security tab.
  - You need `roles/iam.serviceAccountUser` on that service account (the "actAs" permission).
  - Neither grant implies the other.

**E8 — Tags vs digests (hands-on with Artifact Registry).**
- Task: do Step 11 with tag `:latest` instead of `:v1`. Change the default text in `main.py:15`, rebuild, and push `:latest` again. Reload your service URL: which text do you see? Then run `gcloud run deploy` again with the same image string and reload.
- Answer:
  - After the push you still see the old text, because the revision is pinned to the digest resolved at the first deploy.
  - Re-running `gcloud run deploy` resolves `:latest` to the new digest and creates a new revision, so the new text appears.
  - Lesson: use immutable tags (`v1`, `v2`, or the git SHA) so a revision's image is self-documenting.

---

## 9. Errata and open questions

**Errata (evidence-based)**
1. **The deployed image is not this repo's code.**
   - README.md:96 deploys `dlops/simple-translate-http:latest`. Docker Hub shows it was pushed 2024-10-22, is `linux/amd64/v2`, Python 3.9.17 and **pipenv**.
   - Its `main.py`, `Dockerfile` and `docker-entrypoint.sh` (and `cli.py`, `Pipfile`) are identical to branch `pipenv` (verified by diffing them against `git show origin/pipenv:…`). Its `docker-shell.sh` differs from the branch's: the image copy still has an active `docker run … -p 8080:8080` (no `DEV=1`).
   - Its `Pipfile.lock` runs functions-framework 3.4.0 / Flask 2.3.3 / gunicorn 20.1.0 on Python 3.9, not the 3.9.2 / 3.1.2 / 23.0.0 on Python 3.12 that `uv.lock` describes, so the gunicorn behaviour explained from 3.9.2 source (threads, `GUNICORN_LOG_LEVEL`) does not apply to the service students actually deploy.
   - The `main` branch (uv, Python 3.12, commit `d469a52`, 2025-10-20) was never rebuilt or pushed under that name.
   - Nothing in the repo builds that tag: `docker-shell.sh:6` names the image `simple-translate` and there is no push step.
2. **Function name and default text differ between the README and the repo.** `hello_http` (README.md:29) vs `translate_http` (`main.py:6`). Default `"Welcome to AC215. Everyone knows the moon is made out of cheese"` (README.md:47) vs `"Welcome to AC215"` (`main.py:15`).
3. **Three different Python versions.** Function runtime "Python 3.10" (README.md:19), Docker Hub image 3.9.17, repo `requires-python = ">=3.12,<3.13"` (`pyproject.toml:6`). Python 3.10 reaches upstream EOL in Oct 2026 and 3.9 already has.
4. **Outdated example URLs.** `https://us-central1-ac215-project.cloudfunctions.net/simple-translate` (README.md:76) is the 1st-gen Cloud Functions format. Functions created through "Cloud Run → Functions" get `…run.app` URLs, as the README's own screenshot `images/cloud-run-create.png` shows (`https://service-name-129349313346.us-central1.run.app`). README.md:108's `…-uc.a.run.app` is the legacy Cloud Run URL format; it still works but differs from what students will see.
5. **Screenshots disagree with the text.** README.md:20 and 98 say "Allow public access", but `images/cloud-run-create.png` shows "Allow unauthenticated invocations". README.md:135 says to tick "Execute job immediately", but `images/cloud-run-job-01.png` shows it unticked. The API-enable screenshot (`images/cloud-function-enable-apis.png`) is from the old Cloud Functions UI.
6. **The job image's model is retired.** `dlops/simple-translate-gemini` hard-codes `gemini-1.5-flash-001` (image `cli.py:11`). Gemini 1.5 models were retired on Vertex AI in 2025 (verify on the current model-versions page). Errors are swallowed (`cli.py:51-52`), so the job can report success while failing.
7. **The job image's source is unpublished.** README.md:131 uses `dlops/simple-translate-gemini`, whose `Dockerfile`, `Pipfile`, `cli.py` and `docker-entrypoint.sh` exist only inside the image (`ADD . /` layer, pushed 2024-10-21). Students cannot rebuild or fix it from any dlops repo.
8. **The job's default-arguments path is dubious.** README.md:141 says the job runs "using the default arguments". With no args, the image runs `pipenv shell python cli.py` (image `docker-entrypoint.sh:10`) in a non-interactive container; `pipenv shell` is meant to spawn an interactive subshell, and the `pipenv run` form is left commented out on the next line (image `docker-entrypoint.sh:11`). Whether this actually runs `cli.py` could not be confirmed. The explicit-argument path (`pipenv run python $args`, line 13) is the reliable one.
9. **No cleanup section.** The README never tells students to delete the function, service or job, or the Artifact Registry images and source buckets that path A creates.
10. **Repo hygiene.**
    - `__pycache__/main.cpython-312.pyc` is committed (added in `d469a52`).
    - `.gitignore:3-4` carries leftovers from other tutorials (`/docker-volumes`, `trainer.tar.gz`).
    - There is no `.dockerignore`, so the published image contains `/app/.git` (seen in its last layer).
11. **`docker-shell.sh` no longer runs anything.** Lines 14-18 are commented out (since `cba4910`). The README never mentions `docker-shell.sh`, `Dockerfile`, `docker-entrypoint.sh` or any local test, and its only `cli.py` mention (README.md:143) refers to the gemini image's file, not the repo's. The repo's own build files are effectively undocumented.
12. **`docker-entrypoint.sh` details.** It prints "Environment ready! Virtual environment activated." (line 6) *before* activating (line 12). It does not `exec` the server (line 18), so SIGTERM is not forwarded.
13. **Minor typos.** An empty bullet at README.md:22; "CLoud Function" (README.md:70); "showup" (README.md:10, 93); "Give you Cloud Run" (README.md:97); "should looks like" (README.md:76, 108).
14. **Hidden googletrans fragility.** `googletrans==4.0.0rc1` (2020, sync, unofficial endpoint) is pinned here while the L1/L2 repo moved to async `4.0.2`. Copying requirements between tutorials breaks the handler (§6 #6). There is no error handling (`main.py:25`).

**Open questions / could not determine**
- The Ed lesson (slides, any updated instructions) was not accessible. If it differs from the README (e.g. it uses `gcloud run deploy` or Artifact Registry explicitly), prefer the lesson.
- Not checked: the exact list of APIs the current "Write a function" dialog asks for, the current button label ("Save and Deploy" vs "Save and redeploy"), or whether Python 3.10 is still offered in the runtime dropdown. They depend on today's console.
- Not checked: whether a Harvard-managed GCP organization blocks `allUsers` (domain-restricted sharing). Student-owned projects normally do not.
- Whether today's console "Allow public access" radio adds the `allUsers → roles/run.invoker` binding or instead disables the invoker IAM check. Both make the URL public; Step 9 shows how to tell which one you got.
- Whether googletrans' unofficial endpoint currently answers requests from Cloud Run egress IPs. The course's own 2026 change to `simple-translate/cli.py:33-37` suggests blocking or rate-limiting happens.
- The default concurrency the console assigns to a function created via "Write a function" (80 like a service, or 1 like `gcloud functions deploy --gen2`). Check the "Maximum concurrent requests per instance" field on your deployment.
- Which auto-created Artifact Registry repository (`cloud-run-source-deploy` vs `gcf-artifacts`) and Cloud Storage source bucket the current console flow uses. Look in your project after Step 5.

---

## Links

- README sections (pinned commit): [Running App as Cloud Function](https://github.com/dlops-io/serverless-deployment/blob/4eaf3433a3430f51306e67247287a124d0c35710/README.md#running-app-as-cloud-function) · [Running App in Cloud Run](https://github.com/dlops-io/serverless-deployment/blob/4eaf3433a3430f51306e67247287a124d0c35710/README.md#running-app-in-cloud-run) · bonus [Setup Cloud Run (Job + Service Account)](https://github.com/dlops-io/serverless-deployment/blob/4eaf3433a3430f51306e67247287a124d0c35710/README.md#setup-cloud-run-job--service-account) · latest README on [`main`](https://github.com/dlops-io/serverless-deployment#serverless-deployment)
- Ed lesson: [L14 · Serverless Deployment](https://edstem.org/us/courses/97373/lessons/166039/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Previous lecture with a tutorial: [L13 · Advanced Training Workflows](L13-training-workflows.md) (serverless *training* on Vertex AI)
- Next lecture with a tutorial: [L15 · ML Workflows with Vertex AI](L15-vertex-ml-workflows.md) (Vertex AI Endpoints and Pipelines)
- Referenced in §7: [L01](L01-vms-venvs.md) · [L02](L02-containers-1.md) · [L03](L03-containers-2-mega-pipeline.md) · [L04](L04-containers-2b-flexible-workflow-ports.md) · [L10](L10-cloud-connect-cheese-app-v0.md) · [L18](L18-apis-frontend.md) · [L20](L20-deployment-pulumi.md) · [L22](L22-kubernetes-cloud.md)
