# L14 · Serverless Deployment: Cloud Functions, Cloud Run — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166039/) · Tutorial: [`dlops-io/serverless-deployment`](https://github.com/dlops-io/serverless-deployment) `main` @ [`46cc62f`](https://github.com/dlops-io/serverless-deployment/tree/46cc62fd8b1ac94ce733571a834b46002d8dd8c4) (the four-part README the course link serves today; the course map's older pin [`4eaf343`](https://github.com/dlops-io/serverless-deployment/tree/4eaf3433a3430f51306e67247287a124d0c35710) is context only) · Video: [AC215 · L14 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l14-serverless-deployment) · Made from the verified digest and real terminal captures, 2026-11-04

## 中文速览

- **做什么：** 同一个 translation app，在 Cloud Run 上跑成三种形态，全程不碰 VM。Part 1 是 **Cloud Run function**：console 里贴 `main.py` + `requirements.txt`，entry point 填 `hello_http`，URL 加上 `?text=…&src=en&dest=fr` 就返回译文。Part 2 先在 laptop 上 `docker run --rm -p 8086:8080 cgumb/ac215-translation-demo:lecture14-agent-platform-20261022` 跑一个 web UI，再把**同一个 image** deploy 成 service `translation-demo`。Part 3 给这个 service 挂一个 runtime service account，打开 **Play audio**（Gemini TTS，走 Agent Platform）。Part 4 用同一个 image 跑 Cloud Run **job** `translation-audio`：从 private input bucket 读 passage，translate，生成语音，把 `translated.txt`、`speech.wav`、`manifest.json` 写进 output bucket，然后 exit。README 是 `46cc62f` 的四段式新版（1,079 行），不是 course map 里写的 `4eaf343` 旧版。
- **Idea 1 · function 也是一个 container：** 你交的是 source + requirements + entry point，Cloud Build 在 build time 装好 functions-framework 3.10.2（底下是 Flask + gunicorn），打成 image 存进 Artifact Registry。entry point 必须等于 `def` 的名字；填错的话 functions-framework 直接报 `MissingTargetException: … expected to contain a function named 'translate'. Found: 'hello_http' instead`（2026-11-04 本地 capture）。
- **Idea 2 · 一个 image，两种启动命令：** image 的 Entrypoint 是空的，`Cmd` 是 `python -m translation_demo serve`；`os.execvp` 把它换成 gunicorn，bind `0.0.0.0:$PORT`（默认 8080）。`-p 8086:8080` 只是 laptop 上的 port mapping：本机要开 8086，开 8080 得到 `curl: (7) Failed to connect`。job 把 Container command 设成 `python`、Container arguments 设成 11 个独立的 chip，同一个 image 就变成跑一次就退出的 `batch`。
- **Idea 3 · scale to zero 和计费：** Part 2 用 request-based billing、min 0 / max 2 instances、concurrency 4（正好等于 gunicorn 的 4 个 threads）。min instances ≥ 1 或 instance-based billing 会让没人用的时候也在计费；cold start 是起一个新的 app instance，不一定是一台新 VM。
- **Idea 4 · 两个权限问题要分开：** 谁可以 call 这个 app（Allow public access，gcloud 里是 `--no-invoker-iam-check`）和 app 以谁的身份去 call 别的服务（attached service account：Agent Platform User + Service Usage Consumer，靠 ADC 拿 token，不需要 key file）。attach 这个 account 需要**你自己**在它上面有 Service Account User。本地开发用 `gcloud auth application-default login --impersonate-service-account=…`；`gcloud auth login` 只登录 CLI，不是 ADC。
- **Idea 5 · job 成功与否看 manifest：** 每次 execution 写到 `run-001/<uuid>/` 下面，create-only，不会覆盖；`manifest.json`（`"status": "complete"`）最后才写。job account 只需要 input bucket 的 Storage Object Viewer 和 output bucket 的 Storage Object Creator。`gcloud run jobs execute --args=…` 会替换**整个** argument list，而且只对这一次 execution 有效。
- **最费时间的坑：** ① 11 个 argument 贴进一个 chip → `No module named ' translation_demo batch …'`；只填 arguments、command 留空 → container 根本起不来（Docker 里是 `exec: "-m": executable file not found in $PATH`）；两个都不改 → job 跑 gunicorn，一直等 request，直到 5 分钟 timeout。② gcloud box 里 `YOUR_PROJECT_ID` 没换成自己的 → `The project property must be set to a valid project ID, not the project name [YOUR_PROJECT_ID]`；换了但没 `gcloud auth login` → `You do not currently have an active account selected`。③ googletrans 走的是非官方 endpoint：2026-11-04 的 capture 里七个 request 有一个 `ReadTimeout`，返回 HTTP 500。build 成功不代表 translation 成功，要看 Logs。
- **做完要删：** function `translate-function`、service `translation-demo`、job `translation-audio`；两个 bucket（soft delete 期间删掉的数据还能恢复，也还在计费）；两个 runtime service account；function build 留在 Artifact Registry 里的 image（还有 build 的 source archive 和 logs）。大家共用的 public image 不要删。laptop 上那个 260 MB 的 image 可以 `docker image rm` *(optional)*。
- **Lecture slides：** Lecture 14 slides（17 页）和这份 guide 各节怎么对应、做 tutorial 需要的 9 个 lecture ideas，以及 slides 和今天 README/captures 不一样的 7 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 12 和 15 链接的 `#running-app-as-cloud-function`、`#running-app-in-cloud-run` 在今天的 README 里已经没有了，打开只会停在 README 顶部：Part 1 是 function，Part 2–4 是 Cloud Run。② slide 10 的 code sketch 用位置参数 `translate(text,src,dest)`，但 googletrans 的第二个参数是 `dest`，要像 handler 一样写 `src=`、`dest=`。

## At a glance

**What you build.** One translation app, deployed on Google Cloud Run four ways, none of them a VM you manage (`README.md:12-17`). Part 1 is a **Cloud Run function**: you paste a 6-line handler and two pinned requirements into the console, and Cloud Build makes the image; its URL answers `?text=Good%20afternoon%20everyone&src=en&dest=fr` with `Bonjour à tous`. Part 2 runs a prebuilt web UI on your laptop with Docker, then deploys **the same image** as a Cloud Run **service** with a public URL that scales to zero. Part 3 attaches a runtime service account to that service, with no key file, so its **Play audio** button can call Gemini text-to-speech through Agent Platform. Part 4 runs the same image again as a Cloud Run **job** that reads a passage from a private bucket, translates it, synthesizes speech, saves `translated.txt`, `speech.wav` and `manifest.json` to a second bucket, and exits; you then submit new work from the terminal and with a small helper script.

**Time needed** (estimate, not timed). About 2.5–3 hours for the whole README: 20 min for Before you begin and the Terminal setup, 30 min for Part 1 (most of it the function's build), 30 min for Part 2 (the first `docker pull` is 62 MB), 30–45 min for Part 3 (45 with the optional local development), 45 min for Part 4. The follow-along video is about 30 minutes, in two parts. The exercises in §8 add an hour or more.

**Prerequisites.**
- A GCP project with **billing enabled**, selected in the console by its **project ID** (`README.md:28-31`), and the right to create Cloud Run resources, service accounts and buckets and to grant roles on them (`README.md:32-34`). Project Owners have all of this; in a restricted course project, ask course staff first.
- On your laptop: a clone of the repo, Docker (Part 2's local demo), Python and the Google Cloud CLI (the gcloud boxes and Part 4's helper), and uv only for the optional local development in Part 3.3 (`README.md:38-41`, `:556`). The console-only path needs none of these (`README.md:39-41`).
- Credentials: **no key file at all**. Part 1 and all text translation need no Google credentials (googletrans calls a public endpoint). Speech and Storage use the attached runtime accounts in the cloud, and impersonated ADC on your laptop (§3.7, §3.9).
- APIs: whatever "Write a function" prompts for (`README.md:102`); the Agent Platform API, `aiplatform.googleapis.com` (Part 3, `README.md:383-384`); the IAM Service Account Credentials API for local impersonation (`README.md:524-525`); Cloud Storage (normally already on).
- Background: Simple Translate on a VM and in a container (L1–L2), `docker run -p` and `PORT` (L4), service-account key files (L3, L10), uv (L1), last week's Vertex AI training job (L13).

**What it costs.** With the README's settings (request-based billing, min instances 0, max 2) the compute is a sliver of Cloud Run's monthly free tier. Money goes to: Cloud Build time on every function (re)deploy, the image that build leaves in Artifact Registry, two small buckets (and their soft-deleted data), every Gemini speech call (each **Play audio** and each job execution), and job execution time. Real surprise bills come from minimum instances ≥ 1, instance-based billing, job retries on paid work, and leftovers (§2).

**Tear down, exactly** (`README.md:1018-1028`, plus what it leaves out; details in §2):
1. Download any results you want to keep.
2. Cloud Run → delete `translate-function` and `translation-demo`; Cloud Run → Jobs → delete `translation-audio`.
3. Cloud Storage → delete the objects and the two buckets. Soft-deleted data stays recoverable, and billable, for the retention period (7 days by default; `docs/lifecycle.md:176-177`).
4. IAM & Admin → Service Accounts → delete `translation-demo-runtime` and `translation-audio-job` once nothing uses them.
5. Artifact Registry → delete the image the function's build left (and review the build's source archives and logs, `docs/lifecycle.md:205-210`). **Keep** the shared public tutorial image: others use it (`README.md:1027-1028`).
6. *(extra, optional)* On your laptop: `docker image rm cgumb/ac215-translation-demo:lecture14-agent-platform-20261022` (260 MB on disk) and, if you did Part 3.3, `gcloud auth application-default revoke`.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Which commit.** The course tutorials page links the repo's default branch, unpinned. On 2026-11-04 `git ls-remote` gave `HEAD` = `main` = **`46cc62fd8b1ac94ce733571a834b46002d8dd8c4`** (2026-10-22 09:26:24 −0400, "Point student setup instructions to the main repository"), and every fresh clone in the captures was at that commit. This is the README a student reaches today, so this guide follows it. The course map (`course/lectures.yaml`) and the batch list still name `4eaf3433a3430f51306e67247287a124d0c35710` (2025-10-20, "updates"), whose README was a ~150-line, two-section tutorial (Python 3.10, `functions-framework==3.*`, the image `dlops/simple-translate-http`). Between the two, 28 commits on 2026-10-21/22 replaced it with the 1,079-line four-part tutorial. Other branches: `codex/four-part-tutorial` @ `fadf1b9` (the rewrite; `46cc62f` is its tip plus one README line), `pipenv` @ `fb0cb7f` (2024 code). Neither is used.
- **README sections covered:** all of `README.md` at `46cc62f`: `## Before you begin` (line 26, with the collapsed *Terminal setup*, 66-89), `## Part 1: Deploy a translation function` (91), `## Part 2: Deploy a translation web app` (235), `## Part 3: Give the web app access to Agent Platform` (355), `## Part 4: Generate and save a translated audio edition` (580), `## Clean up after the tutorial` (1018), `## Troubleshooting and further reading` (1030). The course page's two anchors, `#running-app-as-cloud-function` and `#running-app-in-cloud-run`, existed only in the `4eaf343` README (§9, erratum 1).
- **The image Parts 2–4 deploy:** `cgumb/ac215-translation-demo:lecture14-agent-platform-20261022` (`README.md:58-60`), digest `sha256:c17b6db09f7402febb582bf327920ec9ca4eee113f5ddefa38e9da5619dbe72e` (`README.md:1066-1070`), `linux/amd64`, Python 3.12.15, gunicorn 26.2.0. The pull in the captures resolved to exactly this digest. Its source is `tutorial/app/` in the repo.
- **External code:** functions-framework **3.10.2** (the version `tutorial/function/requirements.txt:1` pins; still the latest release on 2026-11-04): `_cli.py`, `_function_registry.py`, `_http/gunicorn.py`.
- **Terminal captures (the strongest evidence in this guide).** Recorded 2026-11-04 09:24–09:35 UTC in fresh disposable containers, every README command that can run without a Google account exactly as written, in README order: `laptop/` (a fresh Docker 29.8.2 engine standing in for your laptop, git 2.54.0), `dev/` (Debian 12, Python 3.12.15, uv 0.13.7: Part 3.3, and Part 1's handler served locally by functions-framework 3.10.2 as a stand-in for the deployed function), `gcloud/` (Google Cloud SDK 592.0.0 with **no account signed in**: every gcloud box up to its first honest error, the helper's dry run). What only the cloud can show (the deployed function and service answering, speech, the job's files) is quoted from the README and its GIF captions, labelled *recorded* in §4. Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l14-serverless-deployment/assets/terminal); provenance in `ASSETS.md` in the same video folder.
- **Context repos** (none is run in this lecture): `simple-translate` `62f821b`, `port_toy` `d190c71`, `mega-pipeline` `c6bbc9b`, `cheese-app-v0` `cb6fb94`, `model-training` `b9aee1c`.
- **Colab notebooks:** none for L14. **AWS variant:** "Coming Soon" on the course page.
- **Ed lesson:** not accessible when these sources were checked; the lecture slides were used instead (next section).

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 14: Serverless Deployment: Cloud Functions, Cloud Run*, 17 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l14-serverless-deployment/SLIDES.md`. The deck was written against the older README (`4eaf343`); where it and today's README or the captures differ, the list at the end of this section says what to follow.

**Map**

| This guide | Slides |
|---|---|
| §7 Where this sits in the course | 5 (Cheese App roadmap), 6 (the four components; "Model Deploy" is next), 9 (serverless across L13–L15) |
| §1 What you build | 10 (one app, four deployment options) |
| §3.1 Scale to zero; §3.3 billing | 8, 11, 14 |
| §3.2 Cold starts | 16 |
| §3.4 Functions vs services; checklist and §4 *Part 1* | 10–12 |
| Checklist and §4 *Part 2* | 10 (cell 4), 14, 15 |
| §3.8 Services vs jobs; checklist and §4 *Part 4* | 14 (names *service* and *job* only) |
| §6 Gotchas | 16 ("limited control and debugging") |
| §2 clean-up, §3.5 container contract, §3.6 tags and digests, §3.7 IAM, §3.9 ADC, §3.10 job outputs, Part 3, §5 code tour, §8 exercises, §9 errata | none (tutorial-only) |

**Lecture ideas you need for this tutorial**
1. Your project has reached deployment. Of the four Cheese App components, the collector, processor and training are done, and "Model Deploy" is next (slides 5–6).
2. Serverless means code runs only when it is needed and you set up no servers, so you pay for use, not for an idle machine (slide 8).
3. Serverless is a family on GCP: the Vertex AI training job (L13), Cloud Functions and Cloud Run (today), then Vertex AI model deployment and pipelines (L15) (slide 9).
4. The same app can be deployed four ways: as a code file or a container, on a VM or serverless. L1–L2 covered the two VM options. Part 1 is the serverless file, Parts 2–4 the serverless container (slide 10).
5. A Cloud Function runs lightweight code with no server to manage. An event starts it (here, an HTTP request); you pay for the time it runs; it scales on its own (slide 11).
6. Deploying a function takes four steps: open the Functions page, enable the APIs, write the code, deploy (slide 12).
7. Cloud Run runs a whole container you bring, either as a *service* (Parts 2–3) or as a *job* (Part 4) (slide 14).
8. Deploying to Cloud Run takes three steps: open the Cloud Run page, enable the APIs, deploy a Docker image (slide 15).
9. Serverless has three downsides: vendor lock-in, cold starts after idle time, and limited control when debugging (slide 16).

**Where the slides and today's tutorial differ** (in each case, follow the README at `46cc62f` and the 2026-11-04 captures)
1. Slides 12 and 15 link the tutorial as `…/serverless-deployment#running-app-as-cloud-function` and `#running-app-in-cloud-run`. Those headings no longer exist, so the links open the top of the README. Part 1 is the function; Parts 2–4 are Cloud Run (§9, erratum 1).
2. The slides say "Cloud Function(s)" and open `console.cloud.google.com/functions` (slide 12). The product is now *Cloud Run functions*, and the README starts from **Cloud Run → Services → Write a function** (`README.md:99-101`). The deployed function is an ordinary Cloud Run service (§3.4).
3. Slide 10 draws a function as a bare `main.py`, and slide 11 says there are no containers to manage. You don't *manage* one, but there is one: the build installs the requirements, configures the Functions Framework and publishes an image to Artifact Registry (`README.md:212-215`). The same two pins install functions-framework 3.10.2, Flask 3.1.3 and gunicorn 26.2.0 on a laptop (`dev/21`), and that image is what clean-up step 4 removes.
4. Slide 10's sketch calls `translator.translate(text,src,dest)` positionally and ends with `return = results.text`. googletrans orders the arguments `translate(text, dest, src)`, so pass `src=` and `dest=` by name, as the handler does (`tutorial/function/main.py:12`). The handler's default text is just `"Welcome to AC215"` (`main.py:9`), which comes back as `Bienvenido a AC215` (`dev/23`).
5. Slide 12's "Create a python code file" is shorthand. The console wants `main.py`, `requirements.txt` and a **Function entry point** equal to the `def` name, `hello_http` (`README.md:124-152`); a wrong one fails with `MissingTargetException` (`dev/29`, §6 #1).
6. Slides 11 and 14 say you pay only while code runs. That holds for compute with request-based billing and min instances 0, the README's settings (`README.md:281-283`). The build, its stored image, the buckets and every speech call cost money anyway (§2).
7. Slide 15's "Deploy Docker Image in Cloud Run" still holds, but the image is now `cgumb/ac215-translation-demo:…` (a web UI, not the old `dlops/simple-translate-http`), and the README goes on to a runtime identity, speech and a job, which the slides show only as the words "service or job" (slide 14).

## Command checklist

Commands in backticks or code blocks are exactly as the README writes them, placeholders kept: replace `YOUR_PROJECT_ID`, `YOUR_INPUT_BUCKET`, `YOUR_OUTPUT_BUCKET` (and the `YOUR_GLOBALLY_UNIQUE_…` names) with your own values. Plain items are console steps. **The README's "Equivalent gcloud commands" boxes are alternatives to the console steps above them, not extra steps** (`README.md:19-21`): do one or the other. Items marked *(extra)* are not in the README; they come from §4, where the real output of every captured command is shown.

### Before you begin (`README.md:26-60`)

- [ ] Console → project selector: select **your course project**; check its **project ID**, not only its display name.
- [ ] Confirm billing is enabled and that you can create Cloud Run resources, service accounts and buckets and grant their roles.
- [ ] Choose a Cloud Run region. The README uses **Toronto (`northamerica-northeast2`)**; the speech model uses **`us-central1`**, a separate setting (Part 3).
- [ ] `git clone https://github.com/dlops-io/serverless-deployment.git` — the README says "Clone or download the repository" without a command; this is the usual clone (captured). Work from the repository root.
- [ ] `git log -1 --format='%H %ci %s'` — *(extra)* expect `46cc62fd8b1a… 2026-10-22 09:26:24 -0400 Point student setup instructions to the main repository`, or something newer.
- [ ] Fill in the worksheet: `translate-function`, `translation-demo`, `translation-demo-runtime`, `translation-audio`, `translation-audio-job`, and two globally unique bucket names (Part 4).
- [ ] Note the public image `cgumb/ac215-translation-demo:lecture14-agent-platform-20261022`. You don't build or publish anything.

*Terminal setup — run once before using any gcloud command boxes* (`README.md:66-89`)
- [ ] Install the [Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/install) (or use Cloud Shell).
- [ ] Run, replacing the project ID (the first line opens a browser sign-in):
  ```bash
  gcloud auth login
  export PROJECT_ID=YOUR_PROJECT_ID
  export REGION=northamerica-northeast2
  export IMAGE=cgumb/ac215-translation-demo:lecture14-agent-platform-20261022
  export WEB_SERVICE=translation-demo
  export JOB_NAME=translation-audio
  export WEB_EMAIL="translation-demo-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
  export JOB_EMAIL="translation-audio-job@${PROJECT_ID}.iam.gserviceaccount.com"
  ```
  > **Note (captured 2026-11-04):** leave `YOUR_PROJECT_ID` in and every gcloud box below stops with `The project property must be set to a valid project ID, not the project name [YOUR_PROJECT_ID]`; skip `gcloud auth login` and it stops with `You do not currently have an active account selected`. `gcloud auth login` signs in the **CLI** only; it does not set up the app's ADC (Part 3.3).
- [ ] `gcloud auth list` — *(extra)* shows which account the CLI uses.

### Part 1: Deploy a translation function

*1.1 Create the function* (`README.md:97-109`)
- [ ] Console → **Cloud Run → Services → Write a function** (on a narrow window: under **More actions**). This opens **Create service**.
- [ ] If prompted to enable required APIs, enable them and return to the form.
- [ ] **Service name** `translate-function`; your region.
- [ ] **Runtime** → **Python 3.12**.
- [ ] **Authentication** → **Allow public access** → **Create**.
- [ ] Wait for the service; open its **Source** editor (it may hold sample code).

*1.2 Supply the code and dependencies* (`README.md:124-152`)
- [ ] **Edit source** if read-only; replace `main.py` with the contents of `tutorial/function/main.py`:
  ```python
  import functions_framework
  from googletrans import Translator

  @functions_framework.http
  def hello_http(request):
      text = request.args.get("text", "Welcome to AC215")
      source = request.args.get("src", "en")
      destination = request.args.get("dest", "es")
      return Translator().translate(text, src=source, dest=destination).text
  ```
- [ ] Replace `requirements.txt` with:
  ```text
  functions-framework==3.10.2
  googletrans==4.0.0rc1
  ```
- [ ] **Function entry point** → `hello_http` (the Python function, not the file or service name).
- [ ] **Save and redeploy**; wait for the revision to become ready.

*1.3 Call the endpoint* (`README.md:154-173`)
- [ ] Service details → copy the **URL** (not the build details page).
- [ ] Open it with no arguments: the default text in Spanish (*recorded*: `Bienvenido a AC215`).
- [ ] `?text=Good%20afternoon%20everyone&src=en&dest=fr` — append to **your** URL; *recorded*: `Bonjour à tous`.
- [ ] Change `dest=fr` to `dest=el` or `dest=hi`; `dest=zh-cn` for Simplified Chinese.
- [ ] **Observability → Logs**: find your requests and confirm HTTP **200**.

*Equivalent gcloud commands — deploy and call the function* (`README.md:194-205`; alternative to 1.1–1.3)
- [ ] Deploy from source, then call it:
  ```bash
  gcloud run deploy translate-function \
    --project="$PROJECT_ID" --region="$REGION" \
    --source=tutorial/function --function=hello_http --base-image=python312 \
    --no-invoker-iam-check

  FUNCTION_URL=$(gcloud run services describe translate-function \
    --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')
  curl --get "$FUNCTION_URL" \
    --data-urlencode 'text=Good afternoon everyone' \
    --data-urlencode 'src=en' --data-urlencode 'dest=fr'
  ```
  > **Note:** source deployment may prompt you to enable APIs or create a build repository in a new project (`README.md:191-192`). The `curl --get` part was captured against a local stand-in and printed `Bonjour à tous` (§4).

*Rehearse the function locally* *(extra; how the captures stood in for the cloud)*
- [ ] `python3 -m venv ~/fn-venv && ~/fn-venv/bin/pip install -q -r tutorial/function/requirements.txt` — *(extra)* the two pins pull in Flask 3.1.3 and gunicorn 26.2.0.
- [ ] `cd tutorial/function && ~/fn-venv/bin/functions-framework --target hello_http` — *(extra)* serves the handler on port 8080 and prints nothing while it serves; Ctrl+C stops it.
- [ ] `curl -s 'http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=fr'` — *(extra)* in a second terminal; prints `Bonjour à tous`.

### Part 2: Deploy a translation web app

*2.1 Try the prebuilt app locally* (`README.md:242-258`)
- [ ] With Docker running:
  ```bash
  docker run --rm -p 8086:8080 \
    cgumb/ac215-translation-demo:lecture14-agent-platform-20261022
  ```
  The first run pulls 11 layers (`Digest: sha256:c17b6db0…`), then gunicorn prints `Listening at: http://0.0.0.0:8080`.
- [ ] Open [http://localhost:8086](http://localhost:8086) (not 8080).
- [ ] Enter a sentence, choose languages, **Translate**.
- [ ] Notice **Play audio · enable in part 3** is disabled. Stop the container with **Ctrl+C**.
- [ ] `curl -s -X POST -H 'Content-Type: application/json' -d '{"text": "Good afternoon everyone", "src": "en", "dest": "fr"}' http://localhost:8086/api/translate` — *(extra)* in a second terminal while it runs: what **Translate** sends; prints `{"dest":"fr","src":"en","text":"Bonjour \u00e0 tous"}`.
- [ ] `docker image inspect --format '{{index .RepoDigests 0}}' cgumb/ac215-translation-demo:lecture14-agent-platform-20261022` — *(extra)* the digest equals `README.md:1069`.

*2.2 Deploy the same image* (`README.md:270-296`)
- [ ] Console → **Cloud Run → Services → Deploy container**.
- [ ] **Deploy one revision from an existing container image**; **Container image URL**: `cgumb/ac215-translation-demo:lecture14-agent-platform-20261022`.
- [ ] **Service name** `translation-demo`; your region.
- [ ] **Allow public access**; **Request-based** billing.
- [ ] **Auto scaling**, **Minimum number of instances** `0`, **Maximum number of instances** `2`.
- [ ] **Containers, Networking, Security → Containers → Edit Container → Settings**: verify **Container port** `8080`, **Memory** 512 MiB, **CPU** `1`; leave command and arguments unchanged; **Done**.
- [ ] **Requests**: **Request timeout** `120` s, **Maximum concurrent requests per instance** `4`. No speech variables yet.
- [ ] **Create**; wait until the service is ready.
- [ ] Open its **URL**, repeat your translation; speech is still disabled.
- [ ] **Revision History**, then **Observability → Logs**.

*Equivalent gcloud commands — deploy the container service* (`README.md:320-329`; alternative to 2.2)
- [ ] Deploy the image with the same settings:
  ```bash
  gcloud run deploy "$WEB_SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" --image="$IMAGE" \
    --no-invoker-iam-check --min-instances=0 --max-instances=2 \
    --cpu=1 --memory=512Mi --concurrency=4 --timeout=120
  ```
  Re-running the tutorial on a service that already has speech: remove its `ENABLE_SPEECH` setting to get Part 2's behaviour back.

### Part 3: Give the web app access to Agent Platform

*3.1 Enable the API and create the app's identity* (`README.md:364-384`)
- [ ] **APIs & Services → Library → Agent Platform API** → enable it if it isn't already.
- [ ] **IAM & Admin → Service Accounts → Create service account**.
- [ ] Name `Translation demo runtime`, ID `translation-demo-runtime` (description optional).
- [ ] **Create and continue** → **Agent Platform User**, **Add another role → Service Usage Consumer** → **Continue** → leave both "Principals with access" roles empty → **Done**.
- [ ] Record the email. Don't create or download a key.

*Equivalent gcloud commands — create the speech runtime identity* (`README.md:411-420`; alternative to 3.1)
- [ ] Enable the API, create the account, grant its two project roles:
  ```bash
  gcloud services enable aiplatform.googleapis.com --project="$PROJECT_ID"
  gcloud iam service-accounts create translation-demo-runtime \
    --project="$PROJECT_ID" --display-name='Translation demo runtime'
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$WEB_EMAIL" --role=roles/aiplatform.user --condition=None
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$WEB_EMAIL" \
    --role=roles/serviceusage.serviceUsageConsumer --condition=None
  ```

*3.2 Attach the identity and enable speech* (`README.md:430-462`; you need **Service Account User** on the account)
- [ ] **Cloud Run → Services → translation-demo**.
- [ ] **Security** tab → **Service account** → your runtime identity; check its email.
- [ ] **Containers → Variables & Secrets → Environment variables**: `ENABLE_SPEECH` = `true`, `GOOGLE_CLOUD_PROJECT` = your project ID, `GOOGLE_CLOUD_LOCATION` = `us-central1`.
- [ ] **View diff & redeploy** → check the variables, keep **Serve this revision immediately** → **Deploy changes**.
- [ ] Wait for the update, the new revision and the traffic switch.
- [ ] Reload the URL, translate an English sentence into French, **Play audio**.
- [ ] On failure: read the message in the UI and the service **Logs** before changing permissions.

*Equivalent gcloud commands — attach the account and enable speech* (`README.md:488-498`; alternative to 3.2)
- [ ] Update the service:
  ```bash
  gcloud run services update "$WEB_SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" \
    --service-account="$WEB_EMAIL" \
    --update-env-vars="ENABLE_SPEECH=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1"
  ```

*3.3 How would you develop this locally? (optional)* (`README.md:504-578`)
- [ ] Console: **IAM & Admin → Service Accounts → translation-demo-runtime → Principals with access → Grant access**: your user email, role **Service Account Token Creator** (replace any preselected role) → **Save**. Enable the **IAM Service Account Credentials API**.
- [ ] Equivalent commands, then the interactive application login (browser sign-in):
  ```bash
  export DEVELOPER_EMAIL=YOUR_GOOGLE_ACCOUNT_EMAIL
  gcloud services enable iamcredentials.googleapis.com --project="$PROJECT_ID"
  gcloud iam service-accounts add-iam-policy-binding "$WEB_EMAIL" \
    --project="$PROJECT_ID" --member="user:$DEVELOPER_EMAIL" \
    --role=roles/iam.serviceAccountTokenCreator --condition=None

  gcloud auth application-default login --impersonate-service-account="$WEB_EMAIL"
  gcloud auth application-default set-quota-project "$PROJECT_ID"
  ```
- [ ] `curl -LsSf https://astral.sh/uv/install.sh | sh` — *(extra)* install uv if you don't have it ("With uv installed", `README.md:556`); captured: uv 0.13.7.
- [ ] Run the app directly:
  ```bash
  cd tutorial/app
  uv sync --frozen
  ENABLE_SPEECH=true GOOGLE_CLOUD_PROJECT="$PROJECT_ID" \
    GOOGLE_CLOUD_LOCATION=us-central1 PORT=8086 \
    uv run python -m translation_demo serve
  ```
  Captured: `Installed 41 packages`, then gunicorn `Listening at: http://0.0.0.0:8086`.
- [ ] Open [http://localhost:8086](http://localhost:8086), translate, and play audio; Ctrl+C to stop.
- [ ] `uv run python -m unittest discover -s tests -v` — *(extra)* the app's 17 offline tests (`tutorial/app/README.md:23`); `OK`.
- [ ] `cd ../..` — back to the repository root for the commands below.

### Part 4: Generate and save a translated audio edition

*4.1 Create your input and output buckets* (`README.md:593-625`)
- [ ] **Cloud Storage → Buckets → Create**; a globally unique input name (e.g. your project ID + `-translation-input`) → **Continue**.
- [ ] Wizard: **Region** = your region; **Standard**, hierarchical namespace unchecked; **Enforce public access prevention** checked, **Uniform**; soft delete with the default retention, no object versioning, no retention → **Create** → **Confirm**. Check **Configuration**: region, Standard, **Public access: Not public**.
- [ ] Repeat for a separate, globally unique output bucket.
- [ ] Save `tutorial/app/examples/passage.txt` to your machine; input bucket → **Objects → Create folder** `run-001` → open it → **Upload → Upload files** → `passage.txt`.
- [ ] Open `passage.txt` → **Object details → Live object → Cloud Storage URI**: `gs://YOUR_INPUT_BUCKET/run-001/passage.txt`.

*Equivalent gcloud commands — create buckets and upload the first passage* (`README.md:660-673`; alternative to 4.1)
- [ ] Create both buckets and upload the sample passage:
  ```bash
  export INPUT_BUCKET=YOUR_GLOBALLY_UNIQUE_INPUT_BUCKET
  export OUTPUT_BUCKET=YOUR_GLOBALLY_UNIQUE_OUTPUT_BUCKET

  gcloud services enable storage.googleapis.com --project="$PROJECT_ID"
  gcloud storage buckets create "gs://$INPUT_BUCKET" \
    --project="$PROJECT_ID" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets create "gs://$OUTPUT_BUCKET" \
    --project="$PROJECT_ID" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage cp tutorial/app/examples/passage.txt \
    "gs://$INPUT_BUCKET/run-001/passage.txt" --project="$PROJECT_ID"
  ```

*4.2 Create a separate identity for the job* (`README.md:677-694`)
- [ ] **Create service account** with ID `translation-audio-job`.
- [ ] Grant it **Agent Platform User** and **Service Usage Consumer** on the project; record its email.
- [ ] Input bucket → **Permissions → Grant access**: the job email, **Storage Object Viewer** → **Save**.
- [ ] Output bucket → **Permissions → Grant access**: the job email, **Storage Object Creator** → **Save**.
- [ ] Leave the web account unchanged.

*Equivalent gcloud commands — grant the job's runtime permissions* (`README.md:710-727`; alternative to 4.2)
- [ ] Create the account and grant its four roles:
  ```bash
  gcloud iam service-accounts create translation-audio-job \
    --project="$PROJECT_ID" --display-name='Translation audio job'
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$JOB_EMAIL" --role=roles/aiplatform.user --condition=None
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$JOB_EMAIL" \
    --role=roles/serviceusage.serviceUsageConsumer --condition=None
  gcloud storage buckets add-iam-policy-binding "gs://$INPUT_BUCKET" \
    --member="serviceAccount:$JOB_EMAIL" --role=roles/storage.objectViewer
  gcloud storage buckets add-iam-policy-binding "gs://$OUTPUT_BUCKET" \
    --member="serviceAccount:$JOB_EMAIL" --role=roles/storage.objectCreator
  ```

*4.3 Create the job* (`README.md:731-785`; you need **Service Account User** on the job account)
- [ ] **Cloud Run → Jobs → Deploy container** (page title **Create job**).
- [ ] Image: `cgumb/ac215-translation-demo:lecture14-agent-platform-20261022`.
- [ ] **Job name** `translation-audio`, your region, **1 task**.
- [ ] **Containers, Connections, Security → Containers** (expand the row if collapsed) → **Edit Container → Settings** → **Container command**: `python`, then **Enter** (one chip).
- [ ] **Container arguments**, one value per chip (type it, press **Enter**), buckets replaced. Do not paste the whole block into one field:
  ```text
  -m
  translation_demo
  batch
  --input-uri
  gs://YOUR_INPUT_BUCKET/run-001/passage.txt
  --src
  en
  --dest
  fr
  --output-uri
  gs://YOUR_OUTPUT_BUCKET/run-001/
  ```
- [ ] **Variables & Secrets**: `ENABLE_SPEECH` = `true`, `GOOGLE_CLOUD_PROJECT` = your project ID, `GOOGLE_CLOUD_LOCATION` = `us-central1` → **Done**.
- [ ] **Task capacity**: **Task timeout** `5` **minute**, **Number of retries per failed task** `0`; Memory 512 MiB, CPU 1, 1 task.
- [ ] **Security** → **Service account** `translation-audio-job@YOUR_PROJECT_ID.iam.gserviceaccount.com` (pick it by its email).
- [ ] Leave **Execute job immediately** unchecked → **Create**.
- [ ] `docker run --rm cgumb/ac215-translation-demo:lecture14-agent-platform-20261022 python -m translation_demo batch --plan --text-file examples/passage.txt --src en --dest fr --output-uri gs://YOUR_OUTPUT_BUCKET/fresh-run-prefix` — *(extra)* the same program with `--plan`, on your laptop: prints the five steps, calls nothing (`tutorial/app/README.md:210-217`).

*Equivalent gcloud commands — create the job* (`README.md:815-822`; alternative to 4.3)
- [ ] Create the job:
  ```bash
  gcloud run jobs create "$JOB_NAME" \
    --project="$PROJECT_ID" --region="$REGION" --image="$IMAGE" \
    --service-account="$JOB_EMAIL" --command=python \
    --args="-m,translation_demo,batch,--input-uri,gs://$INPUT_BUCKET/run-001/passage.txt,--src,en,--dest,fr,--output-uri,gs://$OUTPUT_BUCKET/run-001/" \
    --set-env-vars="ENABLE_SPEECH=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1" \
    --tasks=1 --max-retries=0 --task-timeout=300 --memory=512Mi --cpu=1
  ```

*4.4 Execute it and collect the files* (`README.md:826-852`)
- [ ] **Cloud Run → Jobs → translation-audio → Execute** (narrow toolbar: **More actions ⋮**).
- [ ] Wait for the green check in **History**; open the execution → **Tasks → View logs**: status, execution ID, `output_uri`.
- [ ] **Cloud Storage → your output bucket → run-001** → the uniquely named attempt folder.
- [ ] Check for `translated.txt`, `speech.wav`, `manifest.json`.
- [ ] Download the text and the WAV (media tab: **Play**, then **⋮ → Download**).

*Equivalent gcloud commands — execute, then download* (`README.md:871-880`; alternative to 4.4)
- [ ] Execute and wait, then download:
  ```bash
  gcloud run jobs execute "$JOB_NAME" \
    --project="$PROJECT_ID" --region="$REGION" --wait
  mkdir -p results
  gcloud storage cp --recursive "gs://$OUTPUT_BUCKET/run-001" ./results \
    --project="$PROJECT_ID"
  ```
  `--wait` waits for completion; it does not stream the application's logs.

*4.5 Submit another passage from the terminal* (`README.md:909-956`; you need `run.jobs.runWithOverrides`, upload on input, read on output)
- [ ] If you followed only the console path, run the Terminal setup now, then set the bucket names:
  ```bash
  export INPUT_BUCKET=YOUR_INPUT_BUCKET
  export OUTPUT_BUCKET=YOUR_OUTPUT_BUCKET
  ```
- [ ] Save a new short UTF-8 passage as `passage.txt` on your laptop and upload it:
  ```bash
  gcloud storage cp ./passage.txt "gs://$INPUT_BUCKET/run-002/passage.txt" \
    --project="$PROJECT_ID"
  ```
  > **Note:** the README gives no command for "save a passage". From the repository root, `cp tutorial/app/examples/passage.txt ./passage.txt` *(extra)* is what the captures used; write your own text into it.
- [ ] Execute the **existing** job with new argument overrides:
  ```bash
  gcloud run jobs execute "$JOB_NAME" \
    --project="$PROJECT_ID" --region="$REGION" \
    --args="-m,translation_demo,batch,--input-uri,gs://$INPUT_BUCKET/run-002/passage.txt,--src,en,--dest,es,--output-uri,gs://$OUTPUT_BUCKET/run-002/" \
    --wait
  ```
- [ ] After it succeeds, download the new output folder:
  ```bash
  mkdir -p results
  gcloud storage cp --recursive "gs://$OUTPUT_BUCKET/run-002" ./results \
    --project="$PROJECT_ID"
  ```

*4.6 Combine upload, execution, and download with the helper* (`README.md:969-1016`)
- [ ] From the repository root:
  ```bash
  python tutorial/run_job.py ./passage.txt \
    --project="$PROJECT_ID" --region="$REGION" --job="$JOB_NAME" \
    --input-bucket="$INPUT_BUCKET" --output-bucket="$OUTPUT_BUCKET" \
    --src=en --dest=fr --download-dir=./results
  ```
  Then open the reported local folder and play `speech.wav` inside its attempt folder.
- [ ] Same command with `--dry-run` added — *(extra, from the helper's own options, `README.md:1000`)* prints the three gcloud commands without uploading, executing or writing anything. Bucket values are **names**, without `gs://`.

### Clean up after the tutorial (`README.md:1018-1028`)

- [ ] Download any results you want to keep.
- [ ] **Cloud Run**: delete `translate-function` and `translation-demo`, then the job `translation-audio` under **Jobs** (check the names against your worksheet).
- [ ] **Cloud Storage**: delete your input/output objects and buckets; then delete the two runtime service accounts once nothing uses them.
- [ ] **Artifact Registry**: remove the function build's unused image. Keep unrelated course resources and the shared public image.
- [ ] *(extra)* Remember soft delete: deleted bucket data stays recoverable and billable for its retention period (`docs/lifecycle.md:176-177`); also review the build's source archives and logs (`docs/lifecycle.md:205-210`).
- [ ] *(extra, laptop)* `docker image rm cgumb/ac215-translation-demo:lecture14-agent-platform-20261022`; `gcloud auth application-default revoke` if you did Part 3.3.
- [ ] *(extra)* Over the next day, check **Billing → Reports**.

The README's last section also points to an optional scripted practice stack (`tutorial/spin_up.py`, `tutorial/tear_down.py`, explained in `docs/lifecycle.md`): both print a plan by default and change the cloud only with `--apply`. It is not part of the walkthrough; §4 shows its plan. The same section prints the public image's Linux AMD64 digest, `sha256:c17b6db09f7402febb582bf327920ec9ca4eee113f5ddefa38e9da5619dbe72e` (`README.md:1066-1070`): the reference to deploy by if you need the exact same image later.

---

## 1. What you build

The README's own table (`README.md:12-17`), with what each part hands to Google:

| Part | What you do | You hand over | Runs as |
|---|---|---|---|
| 1 | Call a URL with text and language parameters | `main.py` + `requirements.txt` + entry point `hello_http` | Cloud Run service `translate-function` (built by Cloud Build) |
| 2 | Move a working local UI to a public URL | a finished image | Cloud Run service `translation-demo` |
| 3 | Play the translation as audio | an identity + three environment variables | the same service, new revision, as `translation-demo-runtime` |
| 4 | Translate a passage and save text and audio | the same image + a command + 11 arguments | Cloud Run job `translation-audio`, as `translation-audio-job` |

The README frames the point (`README.md:7-10`): the translation model is an external service; you deploy the **application code around the model** (accept input, call a model service, return a result), the same role the Cheese App's backend will play.

```
YOUR LAPTOP                                   GOOGLE CLOUD PROJECT (Cloud Run region: northamerica-northeast2, Toronto)
+--------------------------------+
| serverless-deployment/         | Part 1  console "Write a function" (inline editor)
|  tutorial/function/main.py ----+------->  main.py + requirements.txt + entry point hello_http
|  tutorial/function/            |           -> Cloud Build -> image in Artifact Registry
|    requirements.txt            |           -> service "translate-function"  https://…run.app/?text=…&src=en&dest=fr
|                                |              functions-framework --target hello_http on $PORT
| docker run --rm -p 8086:8080   |
|   cgumb/ac215-translation-demo | Part 2  "Deploy container", same image (digest sha256:c17b6db0…)
|   -> http://localhost:8086 ----+------->  service "translation-demo": public, request-based billing,
|                                |           min 0 / max 2, 1 CPU, 512 MiB, concurrency 4, timeout 120 s
|                                |           CMD python -m translation_demo serve -> gunicorn 0.0.0.0:$PORT
|                                | Part 3  + service account translation-demo-runtime (Agent Platform User,
|                                |           Service Usage Consumer) + ENABLE_SPEECH, GOOGLE_CLOUD_PROJECT,
| (optional) impersonated ADC    |           GOOGLE_CLOUD_LOCATION=us-central1
|   uv run python -m             |           browser -> POST /api/speech -> Gemini TTS (us-central1) -> WAV -> browser
|   translation_demo serve       |
|                                | Part 4  job "translation-audio", same image, command python,
| gcloud storage cp ...          |           args -m translation_demo batch --input-uri gs://IN/run-001/passage.txt
| gcloud run jobs execute        |                --src en --dest fr --output-uri gs://OUT/run-001/
|   --args=... --wait     -------+------->  as translation-audio-job (Object Viewer on IN, Object Creator on OUT)
| python tutorial/run_job.py     |           read -> translate -> speak -> write
|                                |           gs://OUT/run-001/<uuid>/{translated.txt, speech.wav, manifest.json} -> exit 0
+--------------------------------+
```

Every text translation (all four parts) leaves Google Cloud for googletrans 4.0.0rc1's *unofficial* web endpoint, with no credentials. Only speech (Parts 3–4) and Storage (Part 4) use a Google identity.

The repo root still holds the 2025 files (`main.py`, `cli.py`, `Dockerfile`, `docker-entrypoint.sh`, `docker-shell.sh`, `pyproject.toml`, `uv.lock`), unchanged since `4eaf343` and never mentioned by the new README. Everything the README uses lives under `tutorial/` (captured listing: `laptop/03-ls.txt`, `04-ls-tutorial.txt`). Don't build the root `Dockerfile` by mistake (§9, erratum 4).

## 2. Prerequisites and costs

**Accounts and local installs.** See *At a glance*. The worksheet names (`README.md:46-55`) matter: the clean-up and the gcloud boxes use them.

**Identities: four kinds, none of them a key file.**

| Identity | Who it is | What it needs | Where set |
|---|---|---|---|
| You, in the console | your Google user | create services, accounts, buckets; grant roles; **Service Account User** on each runtime account to attach it (`README.md:432-434`, `:733-735`) | your project role (Owner has all) |
| You, in the CLI | the same user, via `gcloud auth login` | the same, plus `run.jobs.runWithOverrides` (role **Cloud Run Jobs Executor With Overrides**) to execute with `--args`, upload on input, read on output (`README.md:911-914`) | Terminal setup |
| The web app | `translation-demo-runtime` | **Agent Platform User** + **Service Usage Consumer** on the project; no Storage role | Part 3.1–3.2 |
| The job | `translation-audio-job` | the same two, **Storage Object Viewer** on the input bucket, **Storage Object Creator** on the output bucket | Part 4.2–4.3 |
| You, as the app, locally (optional) | your user impersonating `translation-demo-runtime` | **Service Account Token Creator** on that account + the IAM Service Account Credentials API (`README.md:519-525`) | Part 3.3 |

App configuration is environment variables, not secrets: `ENABLE_SPEECH`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (`README.md:444-448`), optional `VERTEX_TTS_MODEL` (default `gemini-2.5-flash-tts`) and `VERTEX_TTS_VOICE` (default `Kore`) (`speech.py:83-86`), and `PORT` (`__main__.py:23`, image default 8080).

**What costs money, and how to shut it down.** The README's clean-up covers the first four rows; the rest are added.

| Billable resource | Created in | How to remove |
|---|---|---|
| Function `translate-function` (Cloud Run service billing) + Cloud Build time for each (re)deploy | Part 1 | Cloud Run → select → Delete, or `gcloud run services delete translate-function --project="$PROJECT_ID" --region="$REGION"` *(extra)* |
| Service `translation-demo` | Part 2 | the same, with `"$WEB_SERVICE"` |
| Job `translation-audio` (CPU and memory per execution) | Part 4 | Jobs → Delete, or `gcloud run jobs delete "$JOB_NAME" --project="$PROJECT_ID" --region="$REGION"` *(extra)* |
| Artifact Registry image from the function build | Part 1 | delete the unused image (`README.md:1026-1028`); don't delete a shared repository as a shortcut (`docs/lifecycle.md:205-210`) |
| Two buckets + objects (Standard storage) | Part 4 | delete objects and buckets (`README.md:1023-1024`); soft-deleted data stays recoverable and billable for the retention period (`docs/lifecycle.md:176-177`) |
| Gemini TTS calls (each Play audio, each job execution) | Parts 3–4 | stop calling; delete the service and the job |
| Build source archives and logs [added] | Part 1 | review Cloud Storage and Artifact Registry separately (`docs/lifecycle.md:205-210`) |
| Service accounts (free, but remove them) | Parts 3–4 | IAM → Service Accounts → Delete, after nothing uses them (`README.md:1024-1025`) |

Cost intuition (verify on the Cloud Run pricing page; prices change): request-based billing with min instances 0 charges CPU and memory only while a request is being handled, plus a per-request fee, and Cloud Run's monthly free tier dwarfs this tutorial. The README's guardrails bound a mistake: **max 2 instances** for the web service (`README.md:282-283`), **0 retries and a 5-minute timeout** for the job (`README.md:778-780`). Surprise-bill routes: min instances ≥ 1 (an instance kept warm all month), instance-based billing, retries on a paid job (`README.md:895-897`), and leftover images and buckets.

## 3. Concepts this tutorial teaches

### 3.1 Serverless = you hand over the server's lifecycle (scale to zero, scale out)
"Serverless" still runs on servers; you stop deciding *when* one exists. You hand over a unit (source for a function, an image for a service or a job) plus limits (CPU, memory, max instances, concurrency, timeout). The platform starts instances when requests arrive, adds more under load and removes them when traffic stops. The README is precise about it (`README.md:218-224`): a cold start "initializes an instance of the built application; it does not necessarily boot a new VM", scaling to zero "applies to app instances, while Google's routing infrastructure remains available", and "there is no fixed inactivity interval" that predicts the next cold start.
- **Mental model:** instances ≈ ⌈requests in flight ÷ concurrency⌉, clamped to [min, max]. With Part 2's settings (concurrency 4, max 2), at most 8 requests are in progress at once.
- **Misconception:** "My instance remembers the last request." Successive requests can reach different instances (`README.md:343-344`). That is why Part 4 writes its results to Cloud Storage, not the container's disk.

### 3.2 Cold starts and the min-instances knob
A request that finds no free warm instance waits for: container start → `python -m translation_demo serve` → `os.execvp("gunicorn", …)` (`__main__.py:24-26`) → gunicorn imports the app and binds the port → only then the request. Dependencies were installed at **build time**, not per request (`README.md:216`). This code also builds the googletrans `Translator` inside each request and imports googletrans lazily on first use (`translation.py:29-33`), so the first translation on a new instance pays that import too. "Minimum-instance settings can keep capacity warm when that matters" (`README.md:223-224`): a minimum instance buys **warmth, not capacity**, and it bills while idle. Slide 16 lists cold starts as a con of serverless.

### 3.3 Request-based vs instance-based billing
**Request-based** (Part 2's choice, `README.md:281`): pay CPU and memory only while an instance handles at least one request, plus a per-request fee. **Instance-based**: pay for each instance's whole lifetime. A **job** bills its tasks' running time. Picture request spikes on a timeline: a VM is the whole rectangle, request-based is the area under the spikes, instance-based the area under the "instance alive" step, a job one bar from start to exit. Serverless wins for spiky, idle-heavy traffic such as a class demo; at steady high load an always-on instance or a VM can be cheaper.

### 3.4 Cloud Run functions vs Cloud Run services: a function is a container you did not write
Part 1 hands over **source + `requirements.txt` + an entry-point name** ("the Python function the serving framework should call, not the filename or service name", `README.md:150-151`). The build "receives your source, uses Google's build tooling to assemble a Python environment, installs the requirements, configures the Functions Framework, and publishes an application image in Artifact Registry" (`README.md:212-215`). The gcloud box makes it explicit: `--source=tutorial/function --function=hello_http --base-image=python312` (`README.md:195-198`); gcloud's own help says a source deploy uses Google Cloud buildpacks unless a Dockerfile is present (`gcloud/06`). The result is an ordinary Cloud Run service whose process is functions-framework with `--target hello_http`. Part 2 instead hands over a finished image whose own `CMD` starts a server.

| | Part 1: Cloud Run function | Part 2: service from an image |
|---|---|---|
| You provide | `main.py` + `requirements.txt` + entry point | `cgumb/ac215-translation-demo:…` |
| Who builds | Cloud Build, at every deploy | already built from `tutorial/app/Dockerfile`; nothing built at deploy (`README.md:314-315`) |
| Server process | functions-framework 3.10.2 → Flask + gunicorn (`dev/21`) | `python -m translation_demo serve` → gunicorn (`__main__.py:22-26`) |
| Runtime | "Python 3.12" / `--base-image=python312` | `python:3.12-slim-bookworm` (`Dockerfile:1`) |
| Interface | one handler, query string in, text out | a page + two JSON routes (`web.py:13-54`) |

The product used to be "Cloud Functions (2nd gen)"; today it is *Cloud Run functions*, created from **Cloud Run → Services → Write a function** (`README.md:99-101`).

### 3.5 The container contract: `$PORT`, `0.0.0.0`, amd64, no local state
A Cloud Run service container must listen for HTTP on **all interfaces** at the port in the **`PORT`** environment variable (8080 by default), be built for `linux/amd64`, and not rely on local state. Both servers here honour it: functions-framework reads `--host` (default `0.0.0.0`) and `--port` (env `PORT`, default 8080) (`_cli.py:32-33`); the web app does `port = int(os.environ.get("PORT", "8080"))` and binds `0.0.0.0:{port}` (`__main__.py:23-24`), and the image sets `ENV … PORT=8080` (`Dockerfile:2`). `EXPOSE 8080` (`Dockerfile:11`) is documentation; Cloud Run uses its **Container port** setting (`README.md:284-287`).
- **Misconception:** "`-p 8086:8080` tells Cloud Run the port." No: `-p` maps *your laptop's* 8086 to the container's 8080 (L4's `port_toy`). On the laptop, `curl localhost:8080` fails (`laptop/14`); set `-e PORT=9090` and gunicorn listens on 9090 while Docker still forwards to 8080, so the connection is reset (`laptop/30-36`, §8 B1).

### 3.6 Images, registries, tags vs digests
An image is named `registry/repo:tag` (Docker Hub implied for `cgumb/…`). A **tag** is a movable label; a **digest** (`sha256:…`) is the content hash and never changes. The README pastes the **tag** (`README.md:276-278`) and prints the **digest** at the end (`README.md:1066-1070`); the optional practice-stack script deploys by digest (`docs/lifecycle.md:63-67`), and its plan shows `cgumb/ac215-translation-demo@sha256:c17b6db0…` (`gcloud/20`). Captured: the tag pulled exactly that digest (`laptop/10`, `15`). A Cloud Run revision records the image it was deployed with; a new push under the same tag doesn't change your service until you deploy a new revision. **Artifact Registry** is GCP's own registry; Part 1's build stores its image there (`README.md:214-215`, `:1026`).

### 3.7 Two IAM questions: who may *call* the app vs what the app may *access*
"Two permissions questions are separate: **who may call our public app**, and **what the running app may access**. A service account answers the second one." (`README.md:361-362`)
- **Invocation:** "Allow public access" (`README.md:105`, `:281`) lets anyone call the URL. The gcloud boxes spell it `--no-invoker-iam-check` (`README.md:198`, `:323`): the Cloud Run invoker IAM check is switched off.
- **Runtime identity:** the service account attached under **Security** (`README.md:437-439`; `--service-account`, `README.md:491`). Client libraries find its short-lived tokens through ADC; "You do not need to create or download a key" (`README.md:380`).
- **Deploy-time permission:** attaching an account needs `iam.serviceAccounts.actAs` (**Service Account User**) on it: your permission, separate from the account's runtime roles (`README.md:422-427`, `:432-434`).
- **Least privilege per workload:** the web account gets no Storage role because its audio "goes straight to the browser" (`README.md:689-690`); the job account gets read on input only and create on output only (`README.md:683-688`).
- **Service Usage Consumer is not decoration:** `speech.py:102-105` names your project as the **quota project** ("the second permits API quota/billing", `README.md:375-376`).

### 3.8 Services vs jobs; command vs arguments
A person waits for an interactive request; a program that should "read its input, translate it, generate speech, save the files, and exit" is a **job** (`README.md:582-585`). A job has no URL and no port; it runs N tasks (here 1) and an execution succeeds when every task exits 0.
- The image's start-up slots (`laptop/16`): `Entrypoint: []` (empty) and `Cmd: [python -m translation_demo serve]`. In Cloud Run, **Container command** fills the entrypoint slot (gcloud's help: `--command` is the "Entrypoint for the container image", `gcloud/07`) and **Container arguments** replace the `Cmd`. Command `python` + eleven arguments makes the task run `python -m translation_demo batch --input-uri … --src en --dest fr --output-uri …`.
- **One chip, one argv element.** There is no shell to split a line (`README.md:750-753`). Paste all eleven into one chip and Python gets one long module name (§4, Step 4.3).
- **Overrides replace the whole list** for that execution only; the job's saved defaults still point at the first French example (`README.md:954-956`).
- **Truthful exit status:** any failure prints `Batch failed: …` and exits 1 ("A failing job must exit unsuccessfully so execution status is truthful", `__main__.py:58-61`).
- **Misconception:** "A job is a service that happens to stop." Leave the image's command alone and the task starts gunicorn and waits for requests until the 5-minute timeout fails it (`README.md:1044`).

### 3.9 Application Default Credentials and impersonation (local development)
You shouldn't publish an image for every code edit (`README.md:506-514`). ADC "lets the same code discover credentials locally and on Cloud Run": `google.auth.default(…)` finds the attached account's tokens on Cloud Run and an ADC file on your laptop. To test the *runtime account's* permissions locally, **impersonate** it: you sign in as yourself and obtain short-lived tokens as the account, so no private key is ever downloaded (`README.md:519-524`, `:547-548`). Contrast L3/L10, where a JSON key lived in `secrets/`. `gcloud auth login` logs in the CLI only; the app reads ADC, a separate file written by `gcloud auth application-default login` (`README.md:86-87`). The ADC file is still a credential: keep it out of Git and images (`README.md:551-552`).

### 3.10 Durable outputs from a finite job
Each task writes under `<output-uri>/<uuid4 hex>/` (`storage.py:37-38`), uploads `translated.txt` and `speech.wav` with `if_generation_match=0` (create only, never overwrite; `storage.py:46`), then writes `manifest.json` with `"status": "complete"` **last** (`storage.py:48-55`). `run-001` is your chosen prefix, not an auto-numbered folder; re-executing creates another attempt folder; partial files without a manifest "do not establish success"; retries can duplicate paid work (`README.md:887-897`). That is why **Object Creator** is enough on the output bucket: the job only creates. It cannot even list its results; you read them with your own identity (`README.md:692-694`).

## 4. Step-by-step walkthrough

Steps follow the README order and its own numbering (Part.section, step); the video's top-left tracker uses the same numbers. Commands are verbatim from the README unless marked *(extra)*.

**About the outputs below.** Outputs labelled *captured* are real, trimmed (`…`) from the 2026-11-04 captures in `assets/terminal/` (file named with each block; `[exit N]` lines omitted unless they matter). The capture machines had **no Google account and no project**, so:
- every console step is described from the README's own field values;
- what only the cloud shows (the deployed function's and service's answers, speech, the job's files) is labelled *recorded*: it is quoted from the README and the captions of its console GIFs (`expected/` files), never invented;
- Part 1's handler was served locally by the same functions-framework version the build installs (`dev/`, *local stand-in*), so its answers are real, but from `localhost:8080`, not a `run.app` URL;
- every gcloud box was run up to its first honest error.

Timestamps, PIDs, run ids and translations (an external provider) will differ for you; versions may be newer.

### Before you begin (`README.md:26-89`)

**Step 0.1–0.3 · Project, billing, region.** Select your course project and check its **project ID** (`README.md:28-31`); confirm billing and permissions (`README.md:32-34`); pick the Cloud Run region, Toronto `northamerica-northeast2` in the README. The speech model's location, `us-central1`, is a separate setting introduced in Part 3 (`README.md:35-37`).

**Step 0.4 · Clone the repo** (`README.md:38-41`). The README says "Clone or download"; the captures used the usual clone. *Captured* (`laptop/01-clone.txt`, `02-git-log.txt`, `04-ls-tutorial.txt`):
```
$ git clone https://github.com/dlops-io/serverless-deployment.git
Cloning into 'serverless-deployment'...
$ git log -1 --format='%H %ci %s'
46cc62fd8b1ac94ce733571a834b46002d8dd8c4 2026-10-22 09:26:24 -0400 Point student setup instructions to the main repository
```
Everything the README uses is under `tutorial/`: `function/` (Part 1), `app/` (the image of Parts 2–4), `run_job.py` (Part 4.6).

**Terminal setup** (`README.md:66-89`). *Captured* without `gcloud auth login` (it needs a browser sign-in; `gcloud/03`: `No credentialed accounts.`), with the placeholder kept (`laptop/05-terminal-setup.txt`):
```
$ export PROJECT_ID=YOUR_PROJECT_ID
…
echo "$WEB_EMAIL"; echo "$JOB_EMAIL"; echo "$IMAGE"
translation-demo-runtime@YOUR_PROJECT_ID.iam.gserviceaccount.com
translation-audio-job@YOUR_PROJECT_ID.iam.gserviceaccount.com
cgumb/ac215-translation-demo:lecture14-agent-platform-20261022
```
The two emails are built from `PROJECT_ID`, so a typo there follows you into every IAM command. Keep this terminal open: the exports live only in this shell.

### Part 1: Deploy a translation function (`README.md:91-233`)

**Step 1.1 · Create the function** (`README.md:97-109`). **Cloud Run → Services → Write a function**; enable APIs if asked; **Service name** `translate-function`, your region; **Runtime** **Python 3.12**; **Allow public access**; **Create**; open the **Source** editor. Check the name, region and runtime rather than accepting defaults (`README.md:119-121`).

**Step 1.2 · Supply the code and dependencies** (`README.md:124-152`). The handler, *captured* as the file in the repo (`dev/20-function-files.txt`):
```python
"""Part 1: deploy these two files using Cloud Run's function editor."""

import functions_framework
from googletrans import Translator


@functions_framework.http
def hello_http(request):
    text = request.args.get("text", "Welcome to AC215")
    source = request.args.get("src", "en")
    destination = request.args.get("dest", "es")
    return Translator().translate(text, src=source, dest=destination).text
---
functions-framework==3.10.2
googletrans==4.0.0rc1
```
- **Entry point** = `hello_http`, the `def` name. **Save and redeploy**, then wait for the revision.
- **Under the hood:** the build installs the two requirements once and configures functions-framework to call `hello_http` (`README.md:212-216`). The same install on a laptop, *captured* (`dev/21-function-venv.txt`):
  ```
  $ python3 -m venv ~/fn-venv && ~/fn-venv/bin/pip install -q -r tutorial/function/requirements.txt && …
  Flask               3.1.3
  functions-framework 3.10.2
  googletrans         4.0.0rc1
  gunicorn            26.2.0
  httpx               0.13.3
  ```
- **If it fails:** a wrong entry point is the classic. *Captured* with the local stand-in (`dev/29-wrong-target.txt`, traceback trimmed):
  ```
  $ timeout 20 ~/fn-venv/bin/functions-framework --target translate
  Traceback (most recent call last):
  …
  functions_framework.exceptions.MissingTargetException: File /home/student/serverless-deployment/tutorial/function/main.py is expected to contain a function named 'translate'. Found: 'hello_http' instead
  ```
  On Cloud Run the path is the build's app directory (`/workspace/main.py`), and the revision never becomes ready. Fix the field, or rename the `def`.

**Step 1.3 · Call the endpoint** (`README.md:154-173`). Copy the URL from **service details** (`README.md:156-157`), open it bare, then append the query string. `?` starts the query string, `&` separates parameters, and `src`/`dest` are languages, not regions (`README.md:171-173`).
- *Recorded* (`expected/part1-function-recorded.txt`: `README.md:180-184` and the GIF captions): no arguments → `Bienvenido a AC215`; the French query → **Bonjour à tous**, with HTTP **200** in the request log; `dest=el` → Greek.
- *Captured, local stand-in* (`dev/22-28`; functions-framework serving `hello_http` on port 8080, which prints nothing while it serves):
  ```
  $ curl -s -w '\n[HTTP %{http_code}]\n' http://localhost:8080/
  Bienvenido a AC215
  [HTTP 200]
  $ curl -s 'http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=fr'
  Bonjour à tous
  $ curl -s 'http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=el'
  Καλησπέρα σε όλους
  $ curl -s 'http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=hi'
  सबको दोपहर की नमस्ते
  $ curl -s 'http://localhost:8080/?text=Good%20afternoon%20everyone&src=en&dest=zh-cn'
  大家下午好
  ```
- **Logs, for real:** in a first run of the same segment, one of seven requests timed out at the translation provider. The client got `500 Internal Server Error: The server encountered an internal error …`, and the server log showed a traceback through `main.py`, line 12, ending in `httpcore._exceptions.ReadTimeout: The read operation timed out` (`dev/provider-timeout/`); a re-run a minute later succeeded. That is `README.md:228-231` happening: "inspect logs rather than treating a completed build as proof that translation worked".

**Part 1 gcloud box** (alternative, `README.md:194-205`). *Captured* with the placeholder left in (`gcloud/05-function-deploy.txt`):
```
$ gcloud run deploy translate-function \
  --project="$PROJECT_ID" --region="$REGION" \
  --source=tutorial/function --function=hello_http --base-image=python312 \
  --no-invoker-iam-check
ERROR: (gcloud) The project property must be set to a valid project ID, not the project name [YOUR_PROJECT_ID]
…
```
With a validly formatted ID but no signed-in account, the next error (`gcloud/18`):
```
ERROR: (gcloud.run.deploy) You do not currently have an active account selected.
Please run:

  $ gcloud auth login
```
So: replace the placeholder (`README.md:70`), then sign in. The `curl --get` part, run against the local stand-in with `FUNCTION_URL=http://localhost:8080` (*captured*, `dev/24-curl-readme.txt`):
```
$ FUNCTION_URL=http://localhost:8080
curl --get "$FUNCTION_URL" \
  --data-urlencode 'text=Good afternoon everyone' \
  --data-urlencode 'src=en' --data-urlencode 'dest=fr'
Bonjour à tous
```
`--data-urlencode` does the `%20` encoding for you; `--get` turns the data into a query string.

### Part 2: Deploy a translation web app (`README.md:235-353`)

**Step 2.1-1 · Run the prebuilt image** (`README.md:244-249`). *Captured* on a Docker engine that had never seen the image (`laptop/10-docker-run.txt`):
```
$ docker run --rm -p 8086:8080 \
  cgumb/ac215-translation-demo:lecture14-agent-platform-20261022
Unable to find image 'cgumb/ac215-translation-demo:lecture14-agent-platform-20261022' locally
lecture14-agent-platform-20261022: Pulling from cgumb/ac215-translation-demo
edf9b1e67d29: Pull complete
…
c259fd647b57: Pull complete
Digest: sha256:c17b6db09f7402febb582bf327920ec9ca4eee113f5ddefa38e9da5619dbe72e
Status: Downloaded newer image for cgumb/ac215-translation-demo:lecture14-agent-platform-20261022
[2026-11-04 09:25:18 +0000] [1] [INFO] Starting gunicorn 26.2.0
[2026-11-04 09:25:18 +0000] [1] [INFO] Listening at: http://0.0.0.0:8080 (1)
[2026-11-04 09:25:18 +0000] [1] [INFO] Using worker: gthread
[2026-11-04 09:25:18 +0000] [7] [INFO] Booting worker with pid: 7
[2026-11-04 09:25:19 +0000] [1] [INFO] Control socket listening at /home/app/.gunicorn/gunicorn.ctl
^C
[2026-11-04 09:25:22 +0000] [1] [INFO] Handling signal: int
[2026-11-04 09:25:22 +0000] [7] [INFO] Worker exiting (pid: 7)
[2026-11-04 09:25:23 +0000] [1] [INFO] Shutting down: Master
```
- **Read the command:** `--rm` deletes the container when it stops (the image stays: 260 MB on disk, `laptop/17`); `-p 8086:8080` publishes your laptop's port 8086 to the container's 8080; no command is given, so the image's `CMD` runs.
- **Under the hood:** `Listening at: http://0.0.0.0:8080 (1)`: gunicorn is PID 1, because `os.execvp` replaced the Python process (`__main__.py:24-26`). `docker top` shows only gunicorn processes (`laptop/13`), started as `gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 4 --timeout 90 translation_demo.web:create_app()`. Being PID 1 is why **Ctrl+C** stops it cleanly. gunicorn writes no line per request (its access log is off), so the terminal stays quiet while you use the page.
- *(extra)* The image's config, *captured* (`laptop/16-image-config.txt`):
  ```
  Os/Arch: linux/amd64
  User: app
  WorkingDir: /app
  ExposedPorts: map[8080/tcp:{}]
  Entrypoint: []
  Cmd: [python -m translation_demo serve]
  PYTHON_VERSION=3.12.15
  …
  PORT=8080
  ```
  Remember `Entrypoint: []` and `Cmd`: Part 4 swaps them.

**Step 2.1-2 · Open http://localhost:8086** (`README.md:251`). *Captured* (`laptop/11-curl-home.txt`, `14-curl-8080.txt`):
```
$ curl -s -i http://localhost:8086/ | grep -E 'HTTP/|Server:|Content-Type:|<title>|speech-button'
HTTP/1.1 200 OK
Server: gunicorn
Content-Type: text/html; charset=utf-8
  <title>Translate · AC215</title>
    <button id="speech-button" type="button" disabled title="Enable speech with Agent Platform credentials in part 3">Play audio · enable in part 3</button>
…
$ curl -sS http://localhost:8080/
curl: (7) Failed to connect to localhost:8080 after 1 ms: Could not connect to server
```
8080 is the container's port; on your laptop the app is at 8086.

**Step 2.1-3 · Translate.** The page doesn't send a query string: **Translate** posts JSON to `/api/translate` (`index.html:76-80`; "The browser sends a JSON POST here; part 1 used URL query parameters", `tutorial/app/README.md:16-18`). *Captured* (`laptop/21`, `22`, `25`, `26`):
```
$ curl -s -w '\n[HTTP %{http_code}]\n' -X POST -H 'Content-Type: application/json' -d '{"text": "Good afternoon everyone", "src": "en", "dest": "fr"}' http://localhost:8086/api/translate
{"dest":"fr","src":"en","text":"Bonjour \u00e0 tous"}
[HTTP 200]
$ curl -s -X POST … -d '{"text": "Good afternoon everyone", "src": "en", "dest": "zh-cn"}' http://localhost:8086/api/translate | python3 -m json.tool --no-ensure-ascii
{
    "dest": "zh-cn",
    "src": "en",
    "text": "大家下午好"
}
$ curl -s -w '\n[HTTP %{http_code}]\n' -X POST … -d '{"text": "hello", "src": "en", "dest": "xx"}' http://localhost:8086/api/translate
{"error":"Choose a supported destination language."}
[HTTP 400]
$ curl -s -w '\n[HTTP %{http_code}]\n' 'http://localhost:8086/api/translate?text=Good%20afternoon%20everyone&src=en&dest=fr' | tail -3
<p>The method is not allowed for the requested URL.</p>
[HTTP 405]
```
`\u00e0` is `à` in JSON's escaped form; the browser shows `Bonjour à tous`. The app supports nine languages (`translation.py:3-13`).

**Step 2.1-4 · Play audio is disabled; Ctrl+C.** The button is rendered disabled because `ENABLE_SPEECH` is unset (`web.py:15`, `speech.py:34-35`). Calling the speech route anyway, *captured* (`laptop/24-speech-disabled.txt`):
```
$ curl -s -w '\n[HTTP %{http_code}]\n' -X POST -H 'Content-Type: application/json' -d '{"text": "Bonjour à tous", "src": "en", "dest": "fr"}' http://localhost:8086/api/speech
{"error":"Speech is disabled. Enable it for part 3 after configuring Agent Platform access."}
[HTTP 503]
```

**Step 2.2 · Deploy the same image** (`README.md:270-296`). The console form, step by step, is in the checklist. What each setting means:
- **Allow public access**: anyone may call the URL (§3.7). **Request-based** billing: pay while requests are handled (§3.3).
- **Min 0 / max 2**: scale to zero, and never more than two instances (§3.1).
- **Container port 8080**: where Cloud Run connects; the image listens on `$PORT`, which Cloud Run sets (§3.5). **Leave command and arguments unchanged**: the image's `CMD` starts the web server (`README.md:286-287`).
- **Concurrency 4**: at most four requests per instance at once, the same as gunicorn's 4 threads (`__main__.py:25`). **Timeout 120 s**: a request may take up to two minutes.
- *Recorded* (`expected/part2-service-recorded.txt`, from `README.md:291-296`, `:314-315` and the GIF captions): creation completes; the public web app returns `Bonjour à tous` with speech still disabled; **Revision History** shows the ready revision ("A revision is a deployed version of the service's image and configuration"); the log shows a `POST /api/translate` entry with HTTP 200; **Security** confirms Allow public access. Checkpoint: "this deployment did not need to build our source".
- **The gcloud box** (`README.md:320-325`) sets exactly these flags; with no project and no account it stops at the same first error as Part 1's box.

### Part 3: Give the web app access to Agent Platform (`README.md:355-578`)

**Step 3.1 · Enable the API and create the identity** (`README.md:364-384`). **Agent Platform API** (service ID `aiplatform.googleapis.com`); a service account `translation-demo-runtime` with **Agent Platform User** (`roles/aiplatform.user`: call the model) and **Service Usage Consumer** (quota and billing), and **no key**. *Recorded* (`expected/part3-speech-recorded.txt`): the finished account reads "Enabled, No keys".

**Step 3.2 · Attach the identity and enable speech** (`README.md:430-462`). Security tab → the runtime account; three variables; **View diff & redeploy**. Each change makes a new **revision**; "Serve this revision immediately" moves the traffic to it.
- **Under the hood:** **Play audio** posts `{text, dest}` to `/api/speech` (`index.html:95-97`). `synthesize()` checks `ENABLE_SPEECH`, ≤ 4,000 UTF-8 bytes and a supported language (`speech.py:75-82`), gets an ADC token for the attached account with your project as quota project (`speech.py:102-105`), and calls `https://us-central1-aiplatform.googleapis.com/v1beta1/projects/<project>/locations/us-central1/publishers/google/models/gemini-2.5-flash-tts:generateContent` (`speech.py:91-92`). The answer is raw 24 kHz PCM, wrapped as a WAV and sent back to the browser (`speech.py:38-48`, `web.py:54`). The button's state is rendered at page load (`web.py:15`): reload after redeploying.
- *Recorded*: the three variables reviewed, "All deployment stages completed; the service is healthy", then "The player shows Pause: generated French audio is playing".
- **If it fails** (`README.md:457-458`): read the message first. The app maps failures to HTTP codes (`speech.py:108-119` → `web.py:48-53`): missing credentials, 401/403 and 404 → **503** with a configuration message (e.g. "Agent Platform access denied. Check the caller identity, enabled API, inference permissions, and quota project."); 429 and other provider errors → **502**; too long or an unsupported language → **400**.

**Step 3.3 · Develop locally (optional)** (`README.md:504-578`). The grant and the impersonated login need a Google account (not captured). The rest, *captured* on a Debian 12 machine with Python 3.12.15 (`dev/03`, `10`):
```
$ curl -LsSf https://astral.sh/uv/install.sh | sh
downloading uv 0.13.7 x86_64-unknown-linux-gnu
…
$ cd tutorial/app
uv sync --frozen
Using CPython 3.12.15 interpreter at: /usr/local/bin/python3
Creating virtual environment at: .venv
   Building ac215-translation-demo @ file:///home/student/serverless-deployment/tutorial/app
…
      Built googletrans==4.0.0rc1
…
Prepared 41 packages in 4.01s
Installed 41 packages in 259ms
 + ac215-translation-demo==0.1.0 (from file:///home/student/serverless-deployment/tutorial/app)
…
 + flask==3.1.3
 …
 + google-auth==2.62.0
 …
 + google-cloud-storage==3.17.1
 …
 + googletrans==4.0.0rc1
 + gunicorn==26.2.0
 …
 + httpx==0.13.3
 …
 + requests==2.34.2
 …
```
`--frozen` installs exactly what `uv.lock` says, without re-resolving. Then the server (`dev/11-uv-run-serve.txt`; `$PROJECT_ID` still the placeholder):
```
$ ENABLE_SPEECH=true GOOGLE_CLOUD_PROJECT="$PROJECT_ID" \
  GOOGLE_CLOUD_LOCATION=us-central1 PORT=8086 \
  uv run python -m translation_demo serve
[2026-11-04 09:30:45 +0000] [220] [INFO] Starting gunicorn 26.2.0
[2026-11-04 09:30:45 +0000] [220] [INFO] Listening at: http://0.0.0.0:8086 (220)
…
^C
…
[2026-11-04 09:30:50 +0000] [220] [INFO] Shutting down: Master
```
Here `PORT=8086` makes gunicorn itself listen on 8086: no Docker, no port mapping. With speech enabled the button changes (*captured*, `dev/12`, `13`, `14`):
```
$ curl -s http://localhost:8086/ | grep -E '<title>|speech-button'
  <title>Translate · AC215</title>
    <button id="speech-button" type="button" disabled title="Translate some text first">Play audio</button>
…
$ curl -s -w '\n[HTTP %{http_code}]\n' -X POST … http://localhost:8086/api/translate
{"dest":"fr","src":"en","text":"Bonjour \u00e0 tous"}
[HTTP 200]
$ curl -s -w '\n[HTTP %{http_code}]\n' -X POST … http://localhost:8086/api/speech
{"error":"Google credentials are unavailable. Configure local ADC or attach an authorized runtime service account."}
[HTTP 503]
```
That last line is what you see before the impersonated `gcloud auth application-default login`: translation needs no identity, speech does. The app's offline tests pass without any (`dev/15`: `Ran 17 tests in 0.096s` / `OK`). Finish with `cd ../..` (`dev/18`: back at `/home/student/serverless-deployment`).

### Part 4: Generate and save a translated audio edition (`README.md:580-1016`)

**Step 4.1 · Buckets and the first passage** (`README.md:593-625`). Two private buckets (Uniform access, public access prevention), a `run-001` folder in the input bucket, and the sample passage, *captured* (`laptop/40-passage.txt`):
```
$ cat tutorial/app/examples/passage.txt
The evening rain has passed.
Across the square, a window opens.
Someone sets a cup beside a book
and listens to the waking street.
```
Its URI is `gs://YOUR_INPUT_BUCKET/run-001/passage.txt`. Storage shows `run-001` as a folder, but it is just a name prefix (`README.md:890-891`).

**Step 4.2 · The job's identity** (`README.md:677-694`). `translation-audio-job`: the same two project roles as the web account, plus Object Viewer on input and Object Creator on output. Leave the web account alone.

**Step 4.3 · Create the job** (`README.md:731-785`). Command `python`, eleven separate argument chips, the three variables, 5-minute timeout, 0 retries, the job account, **Execute job immediately** unchecked.
- *(extra)* The same program on your laptop with `--plan` (no API call, no upload), *captured* (`laptop/41-batch-plan.txt`):
  ```
  $ docker run --rm cgumb/ac215-translation-demo:lecture14-agent-platform-20261022 \
    python -m translation_demo batch --plan \
    --text-file examples/passage.txt --src en --dest fr \
    --output-uri gs://YOUR_OUTPUT_BUCKET/fresh-run-prefix
  {
    "status": "plan_only",
    "input_characters": 131,
    …
    "steps": [
      "Read the passage",
      "Translate the complete passage",
      "Synthesize speech with Agent Platform",
      "Save text, audio, and completion manifest to a unique attempt prefix",
      "Exit"
    ],
    "implemented": true
  }
  ```
  The words after the image name are exactly what the job's command and arguments supply.
- *(extra)* What the real batch says on a laptop without speech and without an identity, *captured* (`laptop/42`, `43`; both exit 1):
  ```
  Batch failed: Speech is disabled. Enable it for part 3 after configuring Agent Platform access.
  Batch failed: Google credentials are unavailable. Configure local ADC or attach an authorized runtime service account.
  ```
  A failing task exits non-zero, so the execution is marked failed (`__main__.py:58-61`).
- **If it fails:** the two classic set-up mistakes, rehearsed with Docker, *captured*:
  - All eleven values pasted into **one** chip (`laptop/44-one-chip.txt`, exit 1): Python receives one argument after `python` and reads everything after `-m` as a module name, cut at the first dot:
    ```
    /usr/local/bin/python: Error while finding module specification for ' translation_demo batch --input-uri gs://YOUR_INPUT_BUCKET/run-001/passage.txt --src en --dest fr --output-uri gs://YOUR_OUTPUT_BUCKET/run-001/' (ModuleNotFoundError: No module named ' translation_demo batch --input-uri gs://YOUR_INPUT_BUCKET/run-001/passage')
    ```
  - Arguments but **no command** (`laptop/45`, exit 127; Docker's analogue: the arguments replace `Cmd`, and the empty entrypoint leaves `-m` as the program):
    ```
    docker: Error response from daemon: … exec: "-m": executable file not found in $PATH
    ```
  - Neither changed: the task runs `serve` and never exits until the 5-minute timeout (`README.md:1044`).
  - An input URI without `gs://` (`laptop/46`, exit 2): `__main__.py: error: Use a gs://bucket/object-or-prefix URI.`

**Step 4.4 · Execute and collect** (`README.md:826-852`). **Execute**, then **History → the execution → Tasks → View logs**: "The job exits; it does not provide a web URL" (`README.md:832-833`).
- *Recorded* (`expected/part4-job-recorded.txt`): execution `translation-audio-hq9f5` succeeded; the task logs show status complete and the output URIs; the output bucket's `run-001/de2f41…/` attempt folder holds `translated.txt`, `speech.wav` and `manifest.json`; the text download opens the complete French translation. Your execution and attempt ids differ.
- The task log's JSON has this shape (*illustration from the code*, `__main__.py:62` printing what `storage.py:48-56` returns; not an output):
  ```
  {
    "output_uri": "gs://YOUR_OUTPUT_BUCKET/run-001/<attempt>/",
    "manifest_uri": "gs://YOUR_OUTPUT_BUCKET/run-001/<attempt>/manifest.json",
    "status": "complete",
    "artifacts": {
      "translated.txt": "gs://YOUR_OUTPUT_BUCKET/run-001/<attempt>/translated.txt",
      "speech.wav": "gs://YOUR_OUTPUT_BUCKET/run-001/<attempt>/speech.wav"
    },
    "execution": "<execution name>",
    "task_attempt": "<attempt number>"
  }
  ```
- For comparison, the same French passage through the local web app, *captured* (`laptop/23-translate-passage.txt`): `"La pluie du soir est passée.\nDe l’autre côté de la place, une fenêtre s’ouvre.\nQuelqu'un pose une tasse à côté d'un livre\net écoute la rue éveillée."`

**Step 4.5 · Submit another passage from the terminal** (`README.md:909-956`). Upload first: "a remote container cannot read a filename on your laptop" (`README.md:918-919`). Then execute the existing job with `--args` for `run-002` in Spanish, and download. *Captured* without a project (`gcloud/09-upload.txt`):
```
$ export INPUT_BUCKET=YOUR_INPUT_BUCKET
export OUTPUT_BUCKET=YOUR_OUTPUT_BUCKET
gcloud storage cp ./passage.txt "gs://$INPUT_BUCKET/run-002/passage.txt" \
  --project="$PROJECT_ID"
ERROR: (gcloud) The project property must be set to a valid project ID, not the project name [YOUR_PROJECT_ID]
…
```
With your real project and a signed-in CLI, *recorded* (`README.md:963-964`): "upload, successful Spanish job execution, and download". The override replaces all eleven arguments for this one execution; the saved job still says French and `run-001` (`README.md:954-956`).

**Step 4.6 · The helper** (`README.md:969-1016`). It prints each gcloud command, uploads to a fresh `run-<UTC timestamp>-<12 hex>/` prefix in both buckets, executes with `--wait`, downloads, and prints `Downloaded results` only after finding a complete manifest (`run_job.py:47-72`). *Captured* with `--dry-run` (`gcloud/11-helper-dry-run.txt`; long lines cut):
```
$ python tutorial/run_job.py ./passage.txt \
  --project="$PROJECT_ID" --region="$REGION" --job="$JOB_NAME" \
  --input-bucket="$INPUT_BUCKET" --output-bucket="$OUTPUT_BUCKET" \
  --src=en --dest=fr --download-dir=./results --dry-run
$ gcloud storage cp /home/student/serverless-deployment/passage.txt gs://YOUR_INPUT_BUCKET/run-20261104-093455-9d593d979e7f/passage.txt --project=YOUR_PROJECT_ID --quiet
$ gcloud run jobs execute translation-audio --project=YOUR_PROJECT_ID --region=northamerica-northeast2 --args=-m,translation_demo,batch,--input-uri,gs://YOUR_INPUT_BUCKET/run-20261104-093455-9d593d979e7f/passage.txt,--src,en,--dest,fr,--output-uri,gs://YOUR_OU…
Cloud outputs: gs://YOUR_OUTPUT_BUCKET/run-20261104-093455-9d593d979e7f/
$ gcloud storage cp --recursive gs://YOUR_OUTPUT_BUCKET/run-20261104-093455-9d593d979e7f /home/student/serverless-deployment/results --project=YOUR_PROJECT_ID --quiet
```
The real run (`gcloud/10`) printed its first command, then stopped at gcloud's error: `Helper stopped: gcloud failed with exit status 1. Later steps were not run.` A bucket given as `gs://…` is refused before anything runs (`gcloud/13`): `run_job.py: error: input-bucket must be a plain name, without slashes or commas`. *Recorded* (`README.md:991-993`): a full run prints `Downloaded results` only after finding a complete manifest.

### Clean up (`README.md:1018-1028`)

Follow the checklist above, including the *(extra)* items the README leaves out (soft delete, build archives). The optional scripted stack validates the project before doing anything, even in plan mode; *captured* with the placeholder (`gcloud/15`): `Stopped: Invalid project: YOUR_PROJECT_ID`. With a valid-format stand-in ID, `spin_up.py` prints its whole plan, ending `Setup plan only; nothing created.` (`gcloud/20`), and `tear_down.py` stops because only an `--apply` run writes the manifest it needs (`gcloud/21`): `Stopped: [Errno 2] No such file or directory: 'local-state/lecture14-demo.json'`.

## 5. Code tour

```
serverless-deployment/                      (main @ 46cc62f)
|- README.md                     the four-part console-first tutorial (1,079 lines)
|- images/console/*.gif, *.png   annotated console recordings the README embeds
|- docs/lifecycle.md             optional scripted practice stack + teardown
|- tutorial/
|  |- function/main.py           Part 1 handler hello_http (12 lines)
|  |- function/requirements.txt  functions-framework==3.10.2, googletrans==4.0.0rc1
|  |- app/                       the image of Parts 2-4 (package translation_demo)
|  |  |- Dockerfile, .dockerignore, pyproject.toml, requirements.lock, uv.lock
|  |  |- translation_demo/__main__.py      CLI: serve | batch
|  |  |- translation_demo/web.py           Flask: GET /, POST /api/translate, POST /api/speech
|  |  |- translation_demo/translation.py   validate + googletrans
|  |  |- translation_demo/speech.py        Gemini TTS over REST with ADC -> WAV
|  |  |- translation_demo/storage.py       gs:// read, create-only writes, manifest
|  |  |- translation_demo/templates/index.html
|  |  |- examples/passage.txt, tests/, README.md (development guide)
|  |- run_job.py                 Part 4.6 helper (stdlib + gcloud)
|  |- spin_up.py, tear_down.py, lifecycle/, tests/   scripted stack (docs/lifecycle.md)
|- main.py cli.py Dockerfile docker-entrypoint.sh docker-shell.sh pyproject.toml uv.lock
                                 2025 files, unchanged since 4eaf343, not used by the README
```

**`tutorial/function/main.py:7-12`** (quoted in §4, Step 1.2).
- `@functions_framework.http` registers `hello_http` as an HTTP function; functions-framework finds it by the name given as target.
- `request` is a Flask request; `request.args.get(name, default)` reads the query string with defaults `"Welcome to AC215"`, `"en"`, `"es"`.
- A `Translator()` per request; `.translate(...)` blocks on googletrans's endpoint. There is no `try/except`, so a provider failure is an HTTP 500 (§4, Step 1.3). Returning a `str` gives a 200 text body.

**`tutorial/app/Dockerfile:1-12`**
```dockerfile
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml ./
COPY translation_demo ./translation_demo
COPY examples ./examples
RUN pip install --no-cache-dir --no-deps . && useradd --uid 1000 --create-home app
USER app
EXPOSE 8080
CMD ["python", "-m", "translation_demo", "serve"]
```
- Dependencies first (a cached layer), code after: a code-only change reuses the `pip install` layer.
- `requirements.lock` is a `uv export` of `uv.lock`; the six direct dependencies are flask 3.1.3, google-auth 2.62.0, google-cloud-storage 3.17.1, googletrans 4.0.0rc1, gunicorn 26.2.0, requests 2.34.2 (`dev/17-uv-tree.txt`).
- Non-root user `app` (uid 1000; `docker top` on the laptop shows it as `student`, the laptop's uid 1000, `laptop/13`). `CMD` and no `ENTRYPOINT`: that is what lets a job swap the whole command line.

**`translation_demo/__main__.py:9-26`** (the CLI and `serve`)
```python
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Start the HTTP service")
    batch = commands.add_parser("batch", help="Translate a passage, generate speech, save outputs, and exit")
    ...
    if args.command == "serve":
        port = int(os.environ.get("PORT", "8080"))
        os.execvp("gunicorn", ["gunicorn", "--bind", f"0.0.0.0:{port}",
                              "--workers", "1", "--threads", "4", "--timeout", "90",
                              "translation_demo.web:create_app()"])
```
- Docstring, line 1: "One image, different startup commands: serve or batch."
- `batch` options (lines 14-20): exactly one of `--text-file` / `--input-uri`; `--src` (default `en`), `--dest` (default `fr`), required `--output-uri`, `--plan`.
- `os.execvp` replaces Python with gunicorn, so signals reach the server directly. 1 worker × 4 threads; Part 2's concurrency 4 matches.

**`__main__.py:51-62`** (`batch`)
```python
    try:
        if text is None:
            text = read_text(args.input_uri)
        validate(text, args.src, args.dest)
        translated = translate(text, args.src, args.dest)
        audio, mime_type = synthesize(translated, args.dest)
        result = save_artifacts(args.output_uri, translated, audio, mime_type)
    except Exception as exc:
        # A failing job must exit unsuccessfully so execution status is truthful.
        print("Batch failed: " + str(exc), file=__import__("sys").stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, indent=2))
```
Read → validate → translate → speak → save → print: the five steps `--plan` lists (`__main__.py:46-47`). Before that, the URIs are checked (lines 32-40); a bad one is an argparse error, exit 2.

**`translation_demo/web.py:9-54`.** `create_app()`: request bodies capped at 32 KiB (11); `GET /` renders the page with `speech_enabled=enabled()` (13-15); `inputs()` requires a JSON object, defaults `src="en"`, `dest="fr"` (17-25); `POST /api/translate` → 400 on bad input, 502 "The translation provider could not complete the request." on a provider failure, else `{text, src, dest}` (27-38); `POST /api/speech` → 400 / 503 / 502 by exception type, else the WAV with `Cache-Control: no-store` (40-54).

**`translation_demo/translation.py:3-34`.** Nine languages (`en es fr de el hi ja zh-cn zh-tw`, 3-13); `validate` rejects empty text, more than 5,000 characters and unsupported codes (16-24); `translate` imports googletrans lazily, "so offline UI and contract checks do not load the provider" (29), with a 20 s timeout (33).

**`translation_demo/speech.py:74-124`.** `enabled()` accepts `1`, `true`, `yes`, any case (34-35); env defaults (83-86); `GOOGLE_CLOUD_PROJECT` required (87-88); the regional host unless `global` (91-92); the request asks the model to "Read the following text aloud, without adding commentary" with `responseModalities: ["AUDIO"]` and a prebuilt voice (93-100); ADC with `quota_project_id=project` (102-105); status mapping (108-119).

**`translation_demo/storage.py:10-56`.** `split_uri` requires `gs://bucket/path` (10-16); `read_text` checks ≤ 20,000 bytes and pins the inspected generation (23-30); `save_artifacts`: a uuid attempt prefix, create-only uploads, the manifest last (33-56; §3.10).

**`tutorial/run_job.py:35-72`.** Values must be plain names (no slashes, no commas) because commas delimit `gcloud --args` (35-39); the run id is `run-` + UTC timestamp + 12 hex (47); upload, execute with `--wait --quiet`, download (56-65); success only with a complete manifest and both files (66-72).

**functions-framework 3.10.2 (external).** `_cli.py:24` `--target` (env `FUNCTION_TARGET`); `_cli.py:32-33` host `0.0.0.0`, port from `PORT`; `_function_registry.py:57-61` the missing-target message; `_http/gunicorn.py`: gunicorn with log level `error` by default, which is why the local stand-in printed nothing while serving (`dev/22`).

**Root legacy files** (`main.py` with `translate_http`, `Dockerfile`, `docker-entrypoint.sh`, `docker-shell.sh`): identical to `4eaf343`, not used by the README.

## 6. Gotchas and common errors

1. **Wrong entry point (Part 1).** The build succeeds; the revision never becomes ready. Log: `MissingTargetException: File /workspace/main.py is expected to contain a function named '<what you typed>'. Found: 'hello_http' instead` (captured locally with the local path, `dev/29`). Fix: **Function entry point** = `hello_http` (`README.md:150-151`, `:1038`).
2. **Copying the newer googletrans.** `googletrans==4.0.2` (Lecture 1's `simple-translate`) is async: with this sync handler `.translate(...)` returns a coroutine and `.text` fails with `AttributeError: 'coroutine' object has no attribute 'text'`. Keep `googletrans==4.0.0rc1`.
3. **Translation fails while everything is "green".** googletrans uses an unofficial endpoint that can time out or rate-limit: function → HTTP 500 (captured: `ReadTimeout`, `dev/provider-timeout/`); web app → 502 "The translation provider could not complete the request." (`web.py:35-37`); job → `Batch failed: …`, exit 1. Check Logs, not the build status (`README.md:228-231`, `:1039`). Usually a retry a minute later works.
4. **Placeholders left in.** `The project property must be set to a valid project ID, not the project name [YOUR_PROJECT_ID]` (`gcloud/05`, `09`, `10`). Then, with a real ID: `You do not currently have an active account selected` → `gcloud auth login` (`gcloud/18`).
5. **Wrong local port.** `docker run --rm -p 8086:8080 …` → open **8086**; `localhost:8080` is `Failed to connect` (`laptop/14`). If 8086 is taken, change the left number only.
6. **Public access refused.** An organization policy can forbid public endpoints; the URL then answers 403. Resolve with course staff (`README.md:32-34`).
7. **"Play audio" stays disabled.** `ENABLE_SPEECH` missing or not `true`/`1`/`yes`, the change not deployed, or the page not reloaded (`README.md:1040`; `web.py:15`).
8. **Speech says 503.** `Set GOOGLE_CLOUD_PROJECT to the project authorized for Agent Platform.` (variable missing, `speech.py:87-88`); `Google credentials are unavailable …` (no usable identity, captured `dev/14`); `Agent Platform access denied …` (account not attached, a role missing, API off, wrong quota project; `speech.py:112-113`, `README.md:1041`). A 400 means the text: over 4,000 UTF-8 bytes or an unsupported language (`speech.py:77-82`).
9. **Can't attach the service account.** `iam.serviceAccounts.actAs` denied → you need **Service Account User** on that account (`README.md:432-434`, `:733-735`). Its runtime roles give *you* nothing.
10. **`gcloud auth login` ≠ ADC.** Local speech fails with "Google credentials are unavailable…" until `gcloud auth application-default login` (`README.md:86-87`). Impersonation also needs **Token Creator** and the IAM Service Account Credentials API (`README.md:519-525`). A container doesn't see your laptop's ADC file unless you mount it (`tutorial/app/README.md`, "Local development against GCP").
11. **Job never finishes.** Command left at the image default → gunicorn waits for requests until the 5-minute timeout fails the task (`README.md:746-748`, `:1044`).
12. **Arguments in one chip.** `No module named ' translation_demo batch --input-uri gs://YOUR_INPUT_BUCKET/run-001/passage'` (`laptop/44`). One value per chip (`README.md:750-753`).
13. **Arguments but no command.** The first argument `-m` becomes the program; the container can't start (Docker: `exec: "-m": executable file not found in $PATH`, `laptop/45`).
14. **Job can't read or write.** Wrong `gs://` path, or the grants on the wrong account or bucket: Object Viewer on *input*, Object Creator on *output*, for the **job** account (`README.md:683-688`, `:1043`).
15. **Bucket names in the helper.** Names without `gs://` (`README.md:1002`); anything else is refused with `must be a plain name, without slashes or commas` (`gcloud/13`).
16. **Overrides need your permission.** `gcloud run jobs execute --args=…` needs `run.jobs.runWithOverrides` on *your* identity (`README.md:911-914`, `:1046`).
17. **Overrides replace all arguments.** Leaving out `--dest,es` drops it for that execution, and `batch` falls back to its default `fr` (`__main__.py:18`).
18. **Empty-looking or partial output.** Each execution writes a new UUID folder; success means a `manifest.json` with `"status": "complete"` (`README.md:887-897`, `:1045`).
19. **Limits.** More than 5,000 characters or 20,000 bytes of input, or more than 4,000 UTF-8 bytes of translated text for speech, is rejected (`README.md:899-902`).
20. **Region vs model location.** Cloud Run in Toronto, speech in `us-central1`; `GOOGLE_CLOUD_LOCATION` is the model's location, not the service's region (`README.md:495-498`).
21. **Surprise charges.** Min instances ≥ 1, instance-based billing, job retries, leftover buckets (soft delete), the function's image (§2).

## 7. Where this sits in the course

**Earlier lectures**
- **L1–L2 (`simple-translate`):** the same translator on a VM, then in a container on a VM: slide 10's two ticked "dedicated hardware" cells.
- **L3 (`mega-pipeline`) and L10 (`cheese-app-v0`):** a service-account **JSON key** in `secrets/` and `GOOGLE_APPLICATION_CREDENTIALS`. L14 removes the key: an attached identity in the cloud, impersonated ADC on the laptop.
- **L4 (`port_toy`):** published vs container ports, and reading `PORT` from the environment: exactly Cloud Run's container contract.
- **L13 (`model-training`):** serverless *training*, a Vertex AI custom job with a prebuilt image (slide 9: "LAST WEEK").

**What L14 adds:** serverless *serving* and finite work: HTTP functions (functions-framework), the container contract, scale to zero / cold starts / request-based billing, invocation vs runtime identity, ADC and impersonation, jobs with durable outputs in Cloud Storage. The README ties it to the Cheese App: the backend that accepts input, calls a model service and returns a result (`README.md:9-10`); slides 5–6 place it at the "Model Deploy" stage, and the project milestone asks you to deploy your model or API with Cloud Functions or Cloud Run.

**Next:** L15 (`model-deployment`, `ml-workflow`): a Vertex AI endpoint for a trained model, then pipelines (slide 9: "NEXT"). Later, the FastAPI backend (L18) is exactly the kind of app you would run as a Cloud Run service, and Kubernetes (L22) hands the scaling knobs back to you.

**What changed since `4eaf343`** (if you saw the old README or the slides): the old tutorial had a function with a cheese sentence, Python 3.10 and `functions-framework==3.*`, a Cloud Run service from `dlops/simple-translate-http:latest`, and a bonus Gemini job (`dlops/simple-translate-gemini`). The new one (2026-10-21/22) has Python 3.12, `functions-framework==3.10.2`, the Toronto region, a web UI image, speech through a runtime identity, a job with private buckets, a terminal helper and a clean-up section.

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l14-serverless-deployment/exercises.md) in the video folder; their outputs are the 2026-11-04 captures and extra checks run for them (`assets/exercise-checks/`), and nothing there touched a Google project. Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. Place Parts 1 and 2 on the lecture's 2×2: what do you hand over, and who builds the image in each case?**
<details><summary>Answer</summary>

Both sit in the serverless row. **Part 1, a file:** you hand over `main.py`, `requirements.txt` and the entry point `hello_http`; **Cloud Build** installs the requirements once, configures the Functions Framework and publishes an image to Artifact Registry (`README.md:212-216`), which is what clean-up step 4 removes. **Parts 2–4, a container:** you hand over a finished image built by the tutorial's authors from `tutorial/app/Dockerfile`; Cloud Run builds nothing (`README.md:314-315`). The VM row is Lectures 1 and 2.
</details>

**Q2. Which two settings make the meter run while nobody is using the app, and what does min instances buy you?**
<details><summary>Answer</summary>

**Minimum number of instances ≥ 1** and **instance-based billing**. The README uses request-based billing and minimum 0 (`README.md:281-283`), so compute bills only while requests are served. A minimum instance buys **warmth, not capacity**: no cold start after a quiet spell (`README.md:223-224`). Capacity is max instances × concurrency.
</details>

**Q3. Who may call it, and who it runs as: which setting answers each, and why is no key file needed?**
<details><summary>Answer</summary>

Who may call it: **Allow public access** (`--no-invoker-iam-check`). Who it runs as: the **Security** tab's service account, `translation-demo-runtime`, whose roles decide what the app may call. No key file: Cloud Run hands the instance short-lived tokens for the attached account, and `google.auth.default(…)` finds them (`speech.py:102`; "You do not need to create or download a key", `README.md:380`). Attaching it is a third right: **your** Service Account User on the account.
</details>

**Q4. Why does the job set a command and eleven separate arguments, and what happens with neither?**
<details><summary>Answer</summary>

The image has an empty entrypoint and the command `python -m translation_demo serve` (`laptop/16`). **Container command** `python` fills the entrypoint; **Container arguments** replace the default command, one chip per argv item, with no shell to split a line. Together they run `batch`, which reads, translates, speaks, saves and exits. With **neither**, the task runs `serve`: gunicorn listens and never exits, so the 5-minute timeout fails it (`README.md:1044`).
</details>

**Q5. Name the lecture's three downsides of serverless (slide 16), and what this tutorial gives you for each.**
<details><summary>Answer</summary>

**Cold starts** → min instances ≥ 1, for money. **Limited control and debugging** → three places to look: build and start-up logs (a wrong entry point), service logs (a provider timeout, speech errors), the job's logs and `manifest.json`. **Vendor lock-in** → the parts you wrote ran on a plain laptop (the function under the open-source Functions Framework, `dev/22-28`; the image under Docker, `laptop/10-48`); the Google-specific parts are the console set-up, IAM and Cloud Build.
</details>

### Hands-on (predict, then run)

- **B1. Who chooses the port?** `docker run` with `-e PORT=9090 -p 8086:8080`, then `curl`: predict, run, fix without removing `-e PORT=9090`.
- **B2. Tag or digest?** Compare the tag's `RepoDigests` with the digest the README prints.
- **B3. One image, a different program.** Run the job's own arguments with `--plan` added.
- **B4. An override that forgets a flag.** Leave out `--dest,es` from 4.5's `--args`: which language?
- **B5. Which values switch speech on?** `ENABLE_SPEECH` unset, `true`, `True`, `yes`, `on`: which make the button read **Play audio**?
- **B6. What reaches the handler?** Predict `text`, `src`, `dest` for five URLs, including `%26` vs a bare `&` and `Dest=fr`.
- **B7. The helper's plan.** Run the helper with `--dry-run` and read the three commands.

### Debugging

- **C1.** "Revision not ready" after typing `translate` as the entry point.
- **C2.** `googletrans==4.0.2` copied from Lecture 1: `'coroutine' object has no attribute 'text'`.
- **C3.** Four job set-ups: command only, arguments only, one chip, neither.
- **C4.** The execution fails in a second with exit 2: an output URI without a prefix, `--dest xx`, a URI without `gs://`, a 6,000-character passage.
- **C5.** Play audio is on but says 503: which variable or identity is missing?
- **C6.** Speech works with `uv run` but not in Docker.
- **C7.** Translate works, Play audio says 400.
- **C8.** The helper refuses: `gs://` in a bucket name, `--dest=es,de`, no gcloud installed.
- **C9.** Two gcloud errors in a row: what was skipped each time?
- **C10.** A green build and a 500 with `ReadTimeout`: is the deployment broken?
- **C11.** "Agent Platform access denied": what to check, in which order.

### Think

- **D1.** Concurrency 4, max 2, 3 requests per second at 2 s each: requests in flight, instances, and what happens when traffic doubles.
- **D2.** Why Storage Object Creator is enough for the job, and who reads the results.
- **D3.** Three principals: a teammate who deploys the job, the job itself, you testing speech locally.
- **D4.** Function, service or job for a webhook, your API server and a nightly re-embedding.
- **D5.** Does `.dockerignore`'s `__pycache__` keep `translation_demo/__pycache__/` out of the image?
- **D6.** After deleting the function, the service and the job, name four things that can still cost money.

## 9. Errata and open questions

**Errata (evidence-based, `46cc62f`, checked against the 2026-11-04 captures)**
1. **The course links land on no section.** The course tutorials page and slides 12/15 link `#running-app-as-cloud-function` and `#running-app-in-cloud-run`. Those headings existed at `4eaf343`; at `46cc62f` the headings are "Part 1: Deploy a translation function" and so on (`README.md:91`, `:235`, `:355`, `:580`), so the links open the top of the README. Start at the top: Part 1 is the function, Parts 2–4 are Cloud Run.
2. **The course map pins an older commit.** `course/lectures.yaml` and the batch list say `4eaf343`; the course link serves `main` = `46cc62f`, a different tutorial (28 commits on 2026-10-21/22). This guide follows `46cc62f`.
3. **The README spells no clone command, and Part 4.5 no "save a passage" command.** "Clone or download the repository" (`README.md:38`) and "Save a new short UTF-8 passage as `passage.txt`" (`README.md:929`) are left to you; `git clone https://github.com/dlops-io/serverless-deployment.git` and, from the repository root, `cp tutorial/app/examples/passage.txt ./passage.txt` are what the captures used.
4. **Unused 2025 files at the repo root.** `main.py`, `cli.py`, `Dockerfile`, `docker-entrypoint.sh`, `docker-shell.sh`, `pyproject.toml`, `uv.lock` are unchanged from `4eaf343` and never mentioned, yet the README says to work from the repository root (`README.md:38-39`). The tutorial's image is built from `tutorial/app/`.
5. **`docs/lifecycle.md` shows `--project=YOUR_PROJECT_ID`, which its own scripts reject.** Run as printed, `spin_up.py` and `tear_down.py` stop with `Stopped: Invalid project: YOUR_PROJECT_ID` (`gcloud/15-16`): replace it with your project ID.
6. **`.dockerignore` patterns only match at the build-context root.** `__pycache__` and `*.pyc` (`tutorial/app/.dockerignore:2-3`) don't exclude `translation_demo/__pycache__/`; the published image carries those `.pyc` files. Harmless, but `**/__pycache__` is the intended pattern (exercise D5).
7. **Mutable tag in the click path.** The console steps paste the tag (`README.md:276-278`, `:741-743`); the digest is only at `README.md:1068-1070`. Deploying by `@sha256:…` pins it.
8. **Clean-up stops short.** `README.md:1018-1028` covers the services, the job, the buckets, the accounts and the function's image, but not soft-delete retention (`docs/lifecycle.md:176-177`) or the build's source archives and logs (`docs/lifecycle.md:205-210`).
9. **"We add your developer access separately in section 3.3"** (`README.md:378-379`). Section 3.3 grants Token Creator for impersonation; the **Service Account User** needed to attach the account in 3.2 (`README.md:432-434`) is granted by no console step. Fine for project Owners, a blocker in a restricted project.

**Open questions / could not determine here**
- Console labels and dialogs ("Write a function", "Save and redeploy", "View diff & redeploy", "Containers, Networking, Security" vs "Containers, Connections, Security") come from the README and its GIFs; they were not seen live (no Google account in the capture machines).
- Cloud Run's exact error text when a job has arguments but no command (Docker's analogue is captured; Cloud Run's log line is not).
- The default **Maximum concurrent requests per instance** the console gives a function created by "Write a function" (Part 1 doesn't set it).
- Which service account Parts 1 and 2 run as before Part 3 (normally the project's default compute account) and what roles it has in students' projects.
- Whether googletrans's unofficial endpoint answers reliably from Cloud Run's egress IPs (the README warns, `README.md:228-231`; one local request timed out on 2026-11-04).
- Whether `gemini-2.5-flash-tts` and voice `Kore` stay available in `us-central1` ("Model availability, language support, and quota depend on the selected model/location", `README.md:496-498`).
- The Ed lesson was not accessible.

---

## Links

- README sections (pinned commit): [Before you begin](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/README.md#before-you-begin) · [Part 1: Deploy a translation function](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/README.md#part-1-deploy-a-translation-function) · [Part 2: Deploy a translation web app](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/README.md#part-2-deploy-a-translation-web-app) · [Part 3: Give the web app access to Agent Platform](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/README.md#part-3-give-the-web-app-access-to-agent-platform) · [Part 4: Generate and save a translated audio edition](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/README.md#part-4-generate-and-save-a-translated-audio-edition) · [Clean up after the tutorial](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/README.md#clean-up-after-the-tutorial) · latest README on [`main`](https://github.com/dlops-io/serverless-deployment)
- Repo files: [`tutorial/function/`](https://github.com/dlops-io/serverless-deployment/tree/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/tutorial/function) · [`tutorial/app/`](https://github.com/dlops-io/serverless-deployment/tree/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/tutorial/app) (with its [development guide](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/tutorial/app/README.md)) · [`tutorial/run_job.py`](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/tutorial/run_job.py) · [`docs/lifecycle.md`](https://github.com/dlops-io/serverless-deployment/blob/46cc62fd8b1ac94ce733571a834b46002d8dd8c4/docs/lifecycle.md) · the old README at [`4eaf343`](https://github.com/dlops-io/serverless-deployment/blob/4eaf3433a3430f51306e67247287a124d0c35710/README.md)
- Google Cloud docs linked by the README: [function deployment](https://docs.cloud.google.com/run/docs/quickstarts/functions/deploy-functions-console) · [container deployment](https://docs.cloud.google.com/run/docs/deploying) · [service identity](https://docs.cloud.google.com/run/docs/configuring/services/service-identity) · [job execution](https://docs.cloud.google.com/run/docs/execute/jobs) · [local ADC](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment) · [Gemini TTS](https://docs.cloud.google.com/text-to-speech/docs/gemini-tts)
- Ed lesson: [L14 · Serverless Deployment](https://edstem.org/us/courses/97373/lessons/166039/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l14-serverless-deployment) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l14-serverless-deployment/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l14-serverless-deployment/assets/terminal) · the concept-first [exam edition](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l14-exam)
- Previous lecture: [L13 · Training workflows](L13-training-workflows.md) · next: [L15 · Vertex AI ML workflows](L15-vertex-ml-workflows.md)
- Referenced in §7: [L01 · VMs and venvs](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II (mega-pipeline)](L03-containers-2-mega-pipeline.md) · [L04 · Ports](L04-containers-2b-flexible-workflow-ports.md) · [L10 · Connecting to the Cloud](L10-cloud-connect-cheese-app-v0.md) · [L18 · APIs and frontend](L18-apis-frontend.md) · [L22 · Kubernetes](L22-kubernetes-cloud.md)
