# L04 · Containers II-b — Flexible workflow, ports and Compose — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166029/) · Tutorials: [`dlops-io/mega-pipeline`](https://github.com/dlops-io/mega-pipeline) `flexible-workflow` @ [`cc67f3b`](https://github.com/dlops-io/mega-pipeline/tree/cc67f3b8fc471f4fe1afe73d03e89466bae7d485) (Mega Pipeline App · flexible workflow: the whole README and the five component READMEs it sends you to; comparison only: `main` @ [`c6bbc9b`](https://github.com/dlops-io/mega-pipeline/tree/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc), the L03 tutorial, and `pipenv-flexible-workflow` @ [`32fcdb7`](https://github.com/dlops-io/mega-pipeline/tree/32fcdb7aa3ffb3eaf3d09bdde123a02a42f2be12), where the old Docker Hub images come from) and [`dlops-io/port_toy`](https://github.com/dlops-io/port_toy) `main` @ [`d190c71`](https://github.com/dlops-io/port_toy/tree/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c) (Docker Compose · Port Toy App: the whole README) · Video: [AC215 · L04 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l04-flexible-workflow-ports) · Made from the verified digest and real terminal captures, 2026-10-13

## 中文速览

- **做什么：** 两个互相独立的 tutorial。(A) **mega-pipeline 的 `flexible-workflow` branch**：还是 L03 那条五段 podcast pipeline（transcribe → generate → synthesize EN，translate → synthesize FR），这次按 team 的方式来：自己的 GCS bucket、自己的 service account，JSON key 放在 repo **旁边**的 `secrets/`，每个 component 自带 committed 的 `Dockerfile` + `pyproject.toml` + `uv.lock` + `docker-shell.sh`。你不写 Dockerfile，只改每个 `cli.py` 里的三个值，然后用 `./docker-shell.sh` 进 container 跑 CLI。(B) **port_toy**：gateway + processor 两个 container，先用 `docker network create` / `docker run -p` / `-e` 手动连起来，改 port 把它弄坏再修好，最后用一个 `docker-compose.yml` 全部替代。Part B 不需要 GCP，也不花钱。
- **Idea 1 · build 还是 pull：** `Dockerfile` + `uv.lock` 是 source，image 是 build 出来的 artifact，tag 只是一个 pointer。`docker-shell.sh` 有四个 mode：不带参数 = build + run，`dev` = 只 build，`run` = 先用本地 image、没有才用 Docker Hub 上的 `dlops/...:latest`，`prod` = 用 `docker buildx` build amd64 + arm64 并 push。2026-10-14 实测：没有本地 image 时，`run` 拉下来的是 2025-02-18 build 的 Python 3.8.17 + pipenv image，以 root 身份在你的 folder 里留下一个 `Pipfile`，`generate_text` 里 `python cli.py --help` 直接 `ImportError: cannot import name 'genai'`。所以平时用默认 mode 或 `dev`。
- **Idea 2 · 两扇窗：** `-v "$BASE_DIR":/app` 把 host 上的 component folder 盖在 image 的 `/app` 上（VS Code 里改的代码立刻生效，`--download` 建的 folder 直接出现在 host 上）；`-v "$SECRETS_DIR":/secrets` 把 repo 旁边的 `secrets/` 挂进来，`-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` 指向 key。venv 在 `/home/app/.venv`（`UV_PROJECT_ENVIRONMENT`），不在 mount 底下，所以不会被盖住。container 里是 user `app`（uid 1000），录制时是 Python 3.14.8、uv 0.13.0。
- **Idea 3 · 三道门：** key（我是谁）、IAM role（我能做什么）、API enabled（服务开了没）。key 的问题在 container **里面**就报错：`DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.`，transcribe 和 generate 是在 `--download` 时，synthesis_audio_en、translate_text、synthesis_audio 是在 import 时（连 `--help` 都跑不了，因为 Google client 在 import 时就建好了）。role 或 API 的问题要等 request 到了 Google 才回来，是 403。
- **Idea 4 · 每个 container 是一台小电脑：** 自己的 network namespace、自己的 `localhost`、自己一整套 port。user-defined bridge `toynet` 有 Docker 的 embedded DNS（container 里 `nameserver 127.0.0.11`），所以 gateway 用 `http://processor:9200` 按名字就能找到 processor。只有 `-p` / `ports:` 才在 host 上开一扇门（`127.0.0.1:8090->9100/tcp`，顺序是 ip:host:container）；processor 没 publish，笔记本上 `curl localhost:9200` 是 `curl: (7) … Could not connect to server`。只有 host port 会冲突（`port is already allocated`）。
- **Idea 5 · Compose = 把同样的 flags 写下来：** `-p` ↔ `ports:`，`-e` ↔ `environment:`，`--network` ↔ `networks:`，`docker build ./gateway` ↔ `build: ./gateway`。`docker compose up` 会 build image、建 `toynet`、起两个 container；`Ctrl+C` 只是 stop（实测按下后约 20 s 才结束，两个都 `exited with code 137`：Python 当 PID 1 不理 SIGTERM，Docker 每个 container 等 10 s 再 kill），`docker compose down` 才删 container 和 network，image 留着。
- **最费时间的坑（Part A）：** ① 从 L03 的 clone 切 branch：`git checkout flexible-workflow` 一次给出两个理由拒绝（改过的 `cli.py`，加上 untracked 的 `generate_text/Dockerfile`、`generate_text/uv.lock`），README 说的 `git stash` 只解决第一个，要再 `git stash -u`；而且 `transcribe_audio` 等四个 component 里被 ignore 的 L03 `Dockerfile`、`pyproject.toml`、`uv.lock` 会被 silently 换成 branch 的版本，想留就先拷出去。② `generate_text/cli.py` 和 `translate_text/cli.py` 出厂就填着课程的 `ac215-project` / `mega-pipeline-bucket` / `pavlos-advanced`，`assert` 拦不住。③ `gcloud config set project <your-project-id>` 照抄会被 bash 拒绝（`syntax error near unexpected token`），尖括号是 placeholder，要换成你自己的 project id。
- **最费时间的坑（Part B）：** 手动那几步做完不清理就 `docker compose up`，会报 `Conflict. The container name "/processor" is already in use`，因为 compose file 钉死了同样的 container name；只剩 network 的话，Compose v5.6.0 只 warn 一下就用它，但之后 `down` 不会删它。Step 3 "It should fail" 的时候页面什么都不变（没有 error handling），要看 `docker logs gateway` 最后一行的 `ConnectionRefusedError: [Errno 111] Connection refused`。
- **安全坑 + errata：** 没有任何 branch 有 `.dockerignore`，`COPY --chown=app:app . ./` 会把 L03 留在 component 里的 `secrets/mega-pipeline.json` 拷进 image（实测用一个 stand-in 文件确认），`prod` 再把它 push 到 Docker Hub。切完 branch 就删掉 component 里的 `secrets/`，再加一个写着 `secrets/` 的 `.dockerignore`。另外：`translate_text` 代码里是 `target_language="es"`，下一步却是 French voice；README 没给建 bucket 的命令，Appendix 示例里的文件名 `test.mp3` 也过不了后面 `input-*` 的 glob。
- **做完要删：** SA key（IAM & Admin → Service accounts → Keys）；课程不再用 bucket 时删掉它；本地五个 `mega-pipeline-*` image（transcribe 1.48 GB，其余 821–836 MB）和 `run` 拉下来的 `dlops/...` image；`run` 留下的 root-owned `Pipfile`；跑过 `prod` 就 `docker buildx rm multi-arch`；port_toy 里 `docker compose down`，再删 `toy-*` / `port_toy-*` image（共享 layer，合计约 200 MB）。API 按用量计费，跑完没有东西在后台烧钱。

## At a glance

**What you build.** Two independent tutorials.
- **(A) mega-pipeline, `flexible-workflow`.** The five-stage podcast pipeline from L03 (transcribe → generate → synthesize EN, translate → synthesize FR), re-run the way a team would ship it: your own GCS bucket and service account, the JSON key kept in a `secrets/` folder *beside* the repo and mounted at run time, and a committed `Dockerfile`, `pyproject.toml`, `uv.lock` and `docker-shell.sh` per component. The script builds the image locally, runs a prebuilt one (falling back to Docker Hub), or builds a multi-arch image and pushes it. You write no Dockerfile; you set three values in each `cli.py` and drive each container's CLI.
- **(B) port_toy.** A two-container web app: a published **gateway** and an internal **processor** on the network `toynet`. You wire it by hand with `docker network create`, `docker run -p` and `-e`, break it by changing ports, fix it with configuration only, and then replace all of it with one `docker-compose.yml`.

**Time needed** (estimate). Part A: about 45 minutes of GCP setup (service account, key, APIs, bucket), then 10-15 minutes per component; the first build of `transcribe_audio` took 99.5 s on the capture laptop, the others 8-53 s. About 2 hours in all. Part B: about 45 minutes, with no cloud account. The follow-along video: about 32 minutes, in two parts (part 1: the flexible workflow; part 2: port_toy). The exercises in §8: about another hour.

**Prerequisites.**
- Tutorial 0, which covers a GCP account and project, VS Code, Git, Docker Desktop and `uv` (`mega-pipeline/README.md:22-26`). This lecture uses Docker Desktop with Compose v2 (`docker compose`) and Buildx, Git, and a bash shell (Git BASH on Windows).
- Part A: a GCP project with billing enabled, where you can create a service account and grant it roles; the `gcloud` CLI signed in (`gcloud auth login`, Tutorial 0), or the console for everything. Python and `uv` are **not** needed on the host: they live inside the images.
- Part B: only Docker Desktop. "You do not need a GCP account or Python installed on your laptop." (`port_toy/README.md:24`)
- Only for `./docker-shell.sh prod`: a Docker Hub account and access token.
- Background: L02 (`docker build` / `docker run`) and L03 (the same pipeline, with Dockerfiles you wrote yourself).

**What it costs.** Part B is free. Part A pays per use: Speech-to-Text (audio minutes), Gemini on Vertex AI (tokens), Cloud Translation (characters) and Text-to-Speech (characters), plus tiny GCS storage. Nothing keeps running after a CLI command finishes, so keep the input clip short. The SA key costs nothing but is a long-lived credential. Docker Hub is free for public repositories, and a new repository you push to is public.

**Tear down, exactly** (details in §2):
1. `exit` each container shell; `--rm` deletes the container.
2. Delete the SA key: console **IAM & Admin → Service accounts → Keys**, or `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=<sa-email>`.
3. When the course no longer needs the bucket: `gcloud storage rm -r gs://<your-bucket>`.
4. Delete leftover `<component>/secrets/` folders from L03, and add a `.dockerignore` with `secrets/` (G6).
5. Local images: `docker image rm mega-pipeline-transcribe-audio mega-pipeline-generate-text mega-pipeline-synthesis-audio-en mega-pipeline-translate-text mega-pipeline-synthesis-audio`, plus any `dlops/mega-pipeline-*` that `run` pulled.
6. `rm Pipfile` in each component where `./docker-shell.sh run` created one (`git status` shows `?? Pipfile`; the file is owned by root, but the folder is yours).
7. Only if you ran `./docker-shell.sh prod`: `docker buildx rm multi-arch`, and delete pushed Docker Hub repositories if they contain anything sensitive (G6).
8. In `port_toy/`: `docker compose down`, then `docker image rm toy-gateway toy-processor port_toy-gateway port_toy-processor`.
9. In an L03 clone you switched: `git stash list`, and `git stash drop` each stash once you no longer need it (Exercise B6).

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course-site map `src/2026-AC215/tutorials_demo.md:56-67`)
  - mega-pipeline, branch `flexible-workflow` (the README line numbers in this guide refer to this branch):
    - Prerequisites (Tutorial 0): `README.md:22-26`
    - [Get the Code](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#get-the-code): `README.md:30-52`
    - [Where We Are, Where We're Going](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#where-we-are-where-were-going): `README.md:56-76` (includes "Two ways to work", `README.md:67-76`)
    - What You'll Learn: `README.md:80-89`
    - The Five Components and the recommended folder layout: `README.md:93-119`
    - [Configure each `cli.py`](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#%EF%B8%8F-configure-each-clipy-before-you-run-it): `README.md:123-134`
    - Connecting the Pipeline Components and GCS Bucket Details: `README.md:138-165`
    - [Service Account & Secrets](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#service-account--secrets): `README.md:169-203`
    - [How to Run a Component](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#how-to-run-a-component): `README.md:207-226`
    - [Quick Reference](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#quick-reference--running-each-component): `README.md:230-274`
    - Appendix, sample code to read/write a GCS bucket: `README.md:280-317`
    - [Sample Dockerfile](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow#sample-dockerfile) and Windows notes: `README.md:319-380`
    - The five component READMEs: `transcribe_audio/README.md`, `generate_text/README.md`, `synthesis_audio_en/README.md`, `translate_text/README.md`, `synthesis_audio/README.md`
  - port_toy: all of `README.md`
    - What you'll learn, Prerequisites, How the app works: `README.md:9-69`
    - [Step 1](https://github.com/dlops-io/port_toy#step-1-set-up-the-network-by-hand): `README.md:75-183`
    - [Step 2](https://github.com/dlops-io/port_toy#step-2-check-the-ports): `README.md:189-325`
    - [Step 3](https://github.com/dlops-io/port_toy#step-3-change-the-ports): `README.md:331-420`
    - [Step 4](https://github.com/dlops-io/port_toy#step-4-run-with-compose): `README.md:426-529`
    - [Cheat sheet](https://github.com/dlops-io/port_toy#port-and-networking-cheat-sheet): `README.md:535-552`
    - Handy commands: `README.md:557-576`
- **Repos used**
  - `dlops-io/mega-pipeline`, branch **`flexible-workflow`**, commit `cc67f3b8fc471f4fe1afe73d03e89466bae7d485`, committed 2026-09-18 00:12:58 -0400 ("latest mega pipeline flexible flow"), still the branch head when the captures were made.
    - Diffed against `main` @ `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc` (2026-09-27 06:42:25 -0400). `main` is the L03 tutorial.
    - Merge base: `16cb292e7dcd13793133a26dabfbde53e4649863` (2025-09-11). The two branches have evolved separately for a year. `flexible-workflow` is **not** "main plus a few commits", and it is *older* than `main`'s tip (see Errata E6).
    - Other branches that this lecture does **not** use: `pipenv-flexible-workflow` @ `32fcdb7aa3ffb3eaf3d09bdde123a02a42f2be12` (2025-02-18). It matters anyway, because the prebuilt Docker Hub images were built from it (Errata E1). Also unused: `flexible-workflow-javier`, `pipenv`, `simple`, `solution`, `validation/mega-pipeline-javier`.
  - `dlops-io/port_toy`, branch `main`, commit `d190c7122fc35cc1f7e15e467d2babdfc24b5c0c`, committed 2026-09-20 13:46:56 -0400 ("gateway: show the real host port in the diagram").
- **Terminal captures (the strongest evidence in this guide).** Every README command of both tutorials was typed exactly as written, in README order, on 2026-10-14 between 00:29 and 00:40 UTC, on a fresh stand-in laptop: a `docker:29.8.2-dind` container with its own network namespace (Docker Engine 29.8.2, Compose v5.6.0, buildx v0.37.2, git 2.54.0, curl 8.22.0), user `student`, workspace `~/AC215`.
  - Inside the images: `python:3.14-slim-bookworm` (Debian 12, **Python 3.14.8**, pip 26.2.1, **uv 0.13.0** from `pip install uv`) for mega-pipeline; `python:3.14-slim` (Debian 13, Python 3.14.8, curl 8.14.1) for port_toy. `uv sync` installed what `uv.lock` pins, e.g. google-cloud-speech 2.40.0, google-cloud-storage 3.14.1, google-genai 2.23.0, google-cloud-texttospeech 2.37.0, google-cloud-translate 3.27.0.
  - The README's `gcloud` commands ran with Google Cloud SDK 570.0.0, never logged in, with no network.
  - There was **no Google account and no service-account key**: `~/AC215/secrets/` existed but was empty, so every Google call stops at `DefaultCredentialsError`, and nothing reached a bucket or an API. Where that matters, §4 shows the real no-key output and says what to look for with your key.
  - The browser was replaced by `curl` sending the page's request (`POST /` with `{"text": …}`); its JSON reply is what the page draws.
  - Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l04-flexible-workflow-ports/assets/terminal) (`port-laptop/`, `mega-laptop/`, `mega-<component>/`, `mega-l03-laptop/`, `gcloud-laptop/`, `expected/`, with `capture.sh` and `run_steps.sh`); provenance in [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l04-flexible-workflow-ports/ASSETS.md).
  - How they differ from your laptop: builds needed the capture environment's proxy CA, so the two base images were rebuilt under their own names (build logs show a different `FROM` digest and `https://deb.debian.org`, and no base-image download; your first build pulls the base image); Docker Hub pulls went through the `mirror.gcr.io` mirror; container ids, ephemeral ports, timestamps and build times change on every run. Your prompt shows your own user and folder.
- **Exercise checks.** The answers in `exercises.md` were checked the same day (06:10-06:35 UTC) on the same kind of stand-in laptop; §8 quotes them.
- **The digest** (registry metadata read on 2026-10-12 and 2026-10-13, a `git`-only branch-switch experiment, no Docker daemon) supplies the code tour, the history and the errata. Where its expectations differ from the captures, this guide follows the captures:
  - The branch switch from an L03 clone refuses with **two** reasons at once (edited `cli.py` and untracked `generate_text` files); the README's `git stash` clears only the first; `git stash -u` is needed. `git fetch origin` printed nothing.
  - A missing key fails at `storage.Client()` (`transcribe_audio/cli.py:39`), before `get_bucket` (`:40`) is reached; in `generate_text` `--help` works and `--download` fails; in the other three even `--help` fails.
  - `generate_text --generate` with nothing downloaded exits 0 and does nothing (a silent no-op).
  - `run` with no local image: real Python 3.8.17 pipenv shell as root, a root-owned `Pipfile` in your folder, and `ImportError: cannot import name 'genai'` in `generate_text`.
  - After the switch, the L03 key in `transcribe_audio/secrets/` ends up **inside** the image built by `./docker-shell.sh dev` (shown with a 79-byte stand-in file, not a key).
  - Literal `gcloud config set project <your-project-id>` is a shell syntax error; `gcloud services enable` without an account prints `You do not currently have an active account selected.`
  - port_toy: exact curl errors, `Empty reply from server` in Step 3, network `172.19.0.0/16` and DNS at `127.0.0.11`, real ephemeral ports, Ctrl+C ≈ 20 s with exit 137, and Compose v5.6.0 **warning and reusing** a leftover `toynet` instead of refusing it (open question Q5 of the digest, now answered).
  - After `prod`'s `docker buildx create --use`, a plain `docker build` (what `docker-shell.sh` runs) still used the `default` builder on Docker Engine 29.8.2 / buildx v0.37.2 (exercise check B7); the digest's G8 consequence did not happen there.
- **Context repos read for §7**
  - `dlops-io/llm-rag` `main` @ `e17a39f35bc07b440f573def480adaf4703f8b91` (2026-10-07), the L05 tutorial
  - `dlops-io/cheese-app-v0` `main` @ `cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb` (2026-10-08), the L10 tutorial
- **Registry metadata** of `docker.io/dlops/mega-pipeline-{transcribe-audio,generate-text,synthesis-audio-en,translate-text,synthesis-audio}:latest`, read on 2026-10-12 and re-checked 2026-10-13: multi-arch OCI indexes (amd64 + arm64, plus two Buildx attestation entries), last pushed 2025-02-18. The captures pulled two of them (`transcribe-audio`, digest `30e5dbdd…`; `generate-text`, `c1f1ccbe…`).
- **Path convention.** `mega-pipeline/<path>` (or a bare component path such as `transcribe_audio/cli.py`) means the file on the `flexible-workflow` branch, `main:<path>` the same repo on `main`, and `port_toy/<path>` port_toy `main`. A bare `README.md:N` is the mega-pipeline root README in the mega-pipeline parts and the port_toy README in the port_toy parts. Capture files are named by folder and file, e.g. `port-laptop/23-curl-9200.txt`.
- **Colab notebooks:** none for this lecture. **Ed lesson:** not accessible when these sources were checked (Q6); the course-site source above was used instead.

</details>

## Command checklist

Commands in backticks are exactly as the READMEs write them (placeholders kept); the README's multi-line commands (with ` \` continuations) are joined onto one line here and shown as the README writes them in §4. Plain items are console clicks or edits. Items marked *(extra)* are not in the README; their real output is in §4. Each component README lists its CLI steps in short form (`python cli.py -d`), and the root README's *Quick Reference* (`README.md:230-274`) gives the same commands in long form (`python cli.py --download`); both spellings are shown together, at the component's step. Commands marked *inside* run at the container's prompt (`app@<id>:/app$`); everything else runs on your laptop. "Captured" means the 2026-10-14 run, made **without a Google key**; your container ids, ports and versions will differ.

### Before the README *(extra)*

- [ ] `docker version` — *(extra)* the client and the engine both answer (Docker Engine 29.8.2 at the time of capture). If the server part errors, start Docker Desktop.
- [ ] `mkdir -p ~/AC215 && cd ~/AC215` — *(extra, not captured)* a workspace folder; the README calls it `<your-workspace>` (`README.md:108`). Both tutorials are cloned here.

### mega-pipeline · Get the Code (`README.md:30-52`)

*Starting fresh?* (`:32-37`)
- [ ] `git clone --branch flexible-workflow https://github.com/dlops-io/mega-pipeline.git` — copies the repo (every branch) and checks out `flexible-workflow`; captured: `Cloning into 'mega-pipeline'...`.
- [ ] `cd mega-pipeline`
- [ ] `git branch; git log --oneline -1` — *(extra)* `* flexible-workflow` and `cc67f3b latest mega pipeline flexible flow` (or a newer commit).
- [ ] `ls; ls -a transcribe_audio` — *(extra)* five component folders and two PNGs; `transcribe_audio` holds `.gitignore Dockerfile README.md cli.py docker-shell.sh pyproject.toml uv.lock`.
- [ ] `ls -l */docker-shell.sh` — *(extra)* all five are `-rwxr-xr-x` (committed as mode 100755).

*Already have the repo from the last tutorial?* (`:39-50`)
- [ ] *(extra)* Copy any L03 file you want to keep **out of the repo first**: your `Dockerfile`, `pyproject.toml` and `uv.lock` (and `docker-shell.sh`) in `transcribe_audio`, `synthesis_audio_en`, `translate_text` and `synthesis_audio` are ignored by Git on `main` and get replaced silently by the branch's files (G1).
- [ ] `cd mega-pipeline`
- [ ] `git fetch origin` — "get the branches you don't have yet"; captured: prints nothing (a clone already has every branch, and nothing had changed). An older clone may list updates.
- [ ] `git checkout flexible-workflow` — switches to this tutorial's branch.
  - Note: from a real L03 state it refuses, with two reasons in one message (captured): `Your local changes to the following files would be overwritten by checkout: transcribe_audio/cli.py` and `The following untracked working tree files would be overwritten by checkout: generate_text/Dockerfile generate_text/uv.lock`, then `Aborting`. Do the `:48` items below, then run it again.
- [ ] `git branch` — confirm: `* flexible-workflow` (an L03 clone also lists `main`).
- [ ] `git stash` — the README's fix for "Your local changes would be overwritten" (`:48`): stashes your edited `cli.py`; captured: `Saved working directory and index state WIP on main: c6bbc9b …`.
  - Note: it clears only the first reason. `git checkout flexible-workflow` still refuses because of the two untracked `generate_text` files (captured).
- [ ] `git checkout -- .` — the README's other option (`:48`): throws your `cli.py` edits away. Not captured; it does not touch untracked files either.
- [ ] `git stash -u` — *(extra)* stashes the untracked files too.
- [ ] `git checkout flexible-workflow` — *(extra, the second try)* captured: `branch 'flexible-workflow' set up to track 'origin/flexible-workflow'.` and `Switched to a new branch 'flexible-workflow'`. Then `git branch` as above.
- [ ] `git status --short --ignored; git stash list` — *(extra)* only `!! transcribe_audio/secrets/` is left (your old key, still there, `:50`), and two stashes. Delete that `secrets/` folder once your key is beside the repo (G6).

### mega-pipeline · Recommended folder layout (`README.md:105-119`)

- [ ] `cd ..` then `mkdir secrets; ls` — *(extra)* from the repo, go up to `<your-workspace>` and create `secrets/` **beside** `mega-pipeline/`; captured: `mega-pipeline  secrets`. The key goes there in the Service Account step. A `secrets/` folder inside the repo is never mounted.

### mega-pipeline · ⚠️ Configure each `cli.py` before you run it (`README.md:123-134`)

- [ ] In all five `cli.py` files, set `gcp_project`, `bucket_name` and `group_name` to your team's values (`transcribe_audio/cli.py:17-21`, `generate_text/cli.py:16-20`, `synthesis_audio_en/cli.py:14-18`, `translate_text/cli.py:14-18`, `synthesis_audio/cli.py:14-18`).
- [ ] `grep -n -E '^(gcp_project|bucket_name|group_name) *=' */cli.py` — *(extra, from the repo folder)* before the edit it shows `""` in three files and the course's `"ac215-project"`, `"mega-pipeline-bucket"`, `"pavlos-advanced"` in `generate_text` and `translate_text`, which the `assert` does not catch (E2); after the edit, your values in all fifteen lines.
- [ ] `git diff cli.py` — *(extra, in each component folder)* exactly three changed lines.
- [ ] *(extra, optional)* In `translate_text/cli.py:64`, change `target_language="es"` to `"fr"` so the French voice reads French (E3).

### mega-pipeline · Connecting the Pipeline Components, GCS Bucket Details (`README.md:138-165`)

- [ ] Create your team's bucket and put a short recording in `input_audios/`. The README gives no command (E5); the `gcloud` ones are listed under the next section, after `gcloud config set project`. Name the recording `input-<something>.mp3`: every later stage only picks up `input-*` files.

### mega-pipeline · Service Account & Secrets (`README.md:169-203`)

- [ ] In the GCP console, go to **IAM & Admin → Service accounts** (`:175`).
- [ ] Create a new service account (e.g. `mega-pipeline-sa`) (`:176`).
- [ ] Grant it **Storage Admin** (`roles/storage.admin`), **Agent Platform User** (`roles/aiplatform.user`; search the role picker for "Agent Platform User", since "Vertex AI User" finds nothing), **Cloud Speech Client** (`roles/speech.client`) and **Cloud Translation API User** (`roles/cloudtranslate.user`) (`:177-181`). Text-to-Speech needs no role (`:185`).
- [ ] Under **Keys → Add Key → Create new key**, download a **JSON** key (`:182`).
- [ ] Save it as `mega-pipeline.json` in the `secrets/` folder one level above the repo: `<your-workspace>/secrets/mega-pipeline.json` (`:183`).
- [ ] `ls secrets/; grep client_email secrets/mega-pipeline.json` — *(extra, not captured: no key here)* from `<your-workspace>`: the file is there, and it belongs to `…@<your-project>.iam.gserviceaccount.com`.
- [ ] Enable the five APIs in the console (**APIs & Services → Library**, search each name, **Enable**) (`:187-189`), or:
- [ ] `gcloud config set project <your-project-id>` — points `gcloud` at your project.
  - Note: typed literally it fails in the shell, before gcloud runs (captured): ``-bash: syntax error near unexpected token `newline'`` (zsh, the macOS default: `zsh: parse error near '\n'`). The angle brackets mark a placeholder. Type your own id without them, e.g. `gcloud config set project your-project-id` → captured: `Updated property [core/project].`
- [ ] `gcloud services enable storage.googleapis.com aiplatform.googleapis.com speech.googleapis.com texttospeech.googleapis.com translate.googleapis.com` — enables all five APIs (the README writes it on six lines, `:193-198`).
  - Note: without a signed-in account it fails (captured): `ERROR: (gcloud.services.enable) You do not currently have an active account selected.` Run `gcloud auth login` (Tutorial 0) and try again. With an account it enables the five services; the tutorial documents no output.
- [ ] `gcloud auth list` — *(extra)* which account gcloud uses; captured without one: `No credentialed accounts.`
- [ ] `gcloud services list --enabled` — *(extra, not captured)* includes the five services.
- [ ] `gcloud storage buckets create gs://<your-bucket> --location=us-central1` — *(extra, not captured)* creates your bucket (E5).
- [ ] `gcloud storage cp input-01.mp3 gs://<your-bucket>/input_audios/` — *(extra, not captured)* seeds it with a short recording named `input-…`.
- [ ] `gcloud storage ls gs://<your-bucket>/input_audios/` — *(extra, not captured)* lists your `input-*.mp3`.

### mega-pipeline · How to Run a Component (`README.md:207-226`)

*Run these from inside a component folder; Task A below runs each one and shows what it prints.*
- [ ] `./docker-shell.sh` — build the image locally and run it (default) (`:212`).
- [ ] `./docker-shell.sh dev` — only build the local image (`:213`).
- [ ] `./docker-shell.sh run` — run from a prebuilt image (falls back to DockerHub) (`:214`).
- [ ] `./docker-shell.sh prod` — build multi-arch (amd64 + arm64) and push to DockerHub (`:215`).
- [ ] `chmod +x docker-shell.sh` — only "If `docker-shell.sh` isn't executable yet" (`:220-224`); captured: prints nothing, and the script was executable already (E12).
- [ ] Windows: run from Git BASH and prefix the command with `winpty` if you see "the input device is not a TTY" (`:226`, `:380`).

### Task A · `transcribe_audio` (`transcribe_audio/README.md`; Quick Reference `README.md:234-240`)

*Project Setup* (`:13-26`) and *Before You Run* (`:30-56`)
- [ ] `cd transcribe_audio` — "`cd` into the `transcribe_audio` folder" (`:15`); from the repo folder.
- [ ] Read the four shipped files, `Dockerfile`, `docker-shell.sh`, `pyproject.toml` and `uv.lock`, before you run anything (`:17-26`; §5 excerpts 1-4).
- [ ] Key at `<your-workspace>/secrets/mega-pipeline.json` (`:32-44`), and the three values in `cli.py` set (`:46-56`).
  - Note: this README shows `gcp_project = "ac215-project"` and `bucket_name = "mega-pipeline-bucket"` as the defaults (`:51-52`); the code ships `""` (E4). Set all three either way.

*Build & Run* (`:60-75`)
- [ ] `./docker-shell.sh` — build the image locally and run it (default) (`:65`). Captured: `Docker Username: dlops, Build Mode: dev-run`, `Building development image locally...`, a first build of `Building 99.5s` (the apt layer with `build-essential ffmpeg` alone took 44.7 s), `Run Docker container...`, `Using local image...`, then the prompt `app@0ceffb272288:/app$`.
- [ ] `docker ps` and `docker inspect --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' mega-pipeline-transcribe-audio` — *(extra, in a second terminal)* the container is named like the image; its two mounts are `…/AC215/mega-pipeline/transcribe_audio -> /app` and `…/AC215/secrets -> /secrets`.
- [ ] `whoami; id`, `which python`, `python --version`, `echo $GOOGLE_APPLICATION_CREDENTIALS`, `ls -la /secrets`, `echo $VIRTUAL_ENV; ls /home/app/.venv; uv --version` — *(extra, inside)* captured: `app`, `uid=1000(app)`; `/home/app/.venv/bin/python`; `Python 3.14.8`; `/secrets/mega-pipeline.json`; an empty `/secrets` (no key here; yours lists `mega-pipeline.json`); `/home/app/.venv`; `uv 0.13.0`.
- [ ] `./docker-shell.sh dev` — only build the local image (`:66`); captured: `Build Mode: dev`, every step `CACHED`, no container.
- [ ] `./docker-shell.sh run` — run from a prebuilt image (falls back to DockerHub) (`:67`); captured with the local image present: `Build Mode: run`, `Using local image...`, the prompt. With no local image it pulls a 2025 image from Docker Hub (§4 A12, E1).
- [ ] `./docker-shell.sh prod` — build multi-arch (amd64 + arm64) and push to DockerHub (`:68`). Not captured (needs `docker login` and push rights); see *OPTIONAL: Publish the container* below.
- [ ] `chmod +x docker-shell.sh` — "If the script isn't executable yet" (`:73`).

*Python packages* (`:79-89`)
- [ ] `uv add <package>` — *inside*, only when the component needs a new dependency (`:89`): updates `pyproject.toml` and `uv.lock` on your laptop through the mount; commit both, then rebuild with `./docker-shell.sh dev` so the package is baked into the image. Not captured (placeholder; Exercise B5 tries it with `rich`).

*CLI to interact with your code* (`:93-108`)
- [ ] `python cli.py --help` — *inside* (`:98`); captured: identical to the README's block (`-d/--download`, `-t/--transcribe`, `-u/--upload`). Until `group_name` is set it stops with `AssertionError: Update group name` (G2).

*Testing your code* (`:110-120`) · *Quick Reference: Transcribe Audio* (`README.md:236-240`)
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key: wipes the local `input_audios/` and downloads every object under `input_audios/` from your bucket.
  - Note: without the key (captured): `Args: Namespace(download=True, transcribe=False, upload=False)`, `download`, then `google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.` at `storage.Client()` (`cli.py:39`). The empty `input_audios/` and `text_prompts/group-01/` were created before the failure.
- [ ] `python cli.py -t` = `python cli.py --transcribe` — *inside*, with your key: MP3 → FLAC with ffmpeg, then Speech-to-Text; writes `text_prompts/<group>/input-….txt`. Without a key: the same `DefaultCredentialsError`, at `speech.SpeechClient()` (`:54`; run, output not kept).
- [ ] `python cli.py -u` = `python cli.py --upload` — *inside*, with your key: uploads `text_prompts/<group>/input-*.txt`.
- [ ] Verify in the GCP console that `text_prompts/<group_name>/` in your bucket contains the new `.txt` files (`:120`).
- [ ] `exit` — *(extra)* leaves the container; `--rm` deletes it.
- [ ] `ls; git status --short --ignored .` — *(extra, on your laptop)* `input_audios/` and `text_prompts/` exist in the component folder; Git shows only ` M cli.py` (the folders are ignored, `.gitignore:5-6`).

*OPTIONAL: Publish the container* (`:124-132`)
- [ ] Change `DOCKER_USERNAME="dlops"` (`docker-shell.sh:13`) to your own Docker Hub namespace (`:75`), and create an access token under Docker Hub → Security (`:132`).
- [ ] *(extra)* Before any push: delete in-component `secrets/` folders and add a `.dockerignore` with `secrets/` and the data folders (G6).
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — logs in to Docker Hub (`:129`). Not captured (credentials).
  - Note: works, but the token lands in your shell history and Docker warns that a password on the command line is insecure; `docker login -u <USER NAME>` and pasting the token at the prompt avoids that.
- [ ] `./docker-shell.sh prod` — builds `linux/amd64` + `linux/arm64` and pushes; ends with `Production build complete and pushed to registry` (`docker-shell.sh:68`). Not captured.
- [ ] `docker buildx ls` — *(extra)* after `prod`, `multi-arch*` is the current builder; `docker buildx use default` (Docker Desktop: `desktop-linux`) switches back, `docker buildx rm multi-arch` also removes it (G8).

### Task B · `generate_text` (`generate_text/README.md`; Quick Reference `README.md:242-248`)

- [ ] `cd ../generate_text` — "`cd` into the `generate_text` folder" (`:15`).
- [ ] Read the four shipped files (`:17-26`); key in place (`:32-46`); set the three values in `cli.py` (`:48-58`). This file ships the course's values (E2).
- [ ] `./docker-shell.sh` — build and run (default) (`:67`). Captured: `Building 52.6s` (its own apt layer: `build-essential` only, 54 packages), `uv sync` installed 34 packages, the prompt `app@45263bb6ca36:/app$`.
- [ ] `./docker-shell.sh dev` · `./docker-shell.sh run` · `./docker-shell.sh prod` — the other three modes (`:68-70`), as in Task A.
- [ ] `chmod +x docker-shell.sh` — only if not executable (`:75`).
- [ ] `export GEMINI_MODEL=gemini-2.5-flash` then `python cli.py --generate` — *inside*, "To try a different model without editing code" (`:89-94`); the default is `gemini-2.5-flash-lite` (`cli.py:73`). Run it after `-d` (below); without downloaded prompts it does nothing (captured: `Args: …`, `generate`, exit 0).
- [ ] `uv add <package>` — *inside*, only for a new dependency (`:105`), as in Task A.
- [ ] `python cli.py --help` — *inside* (`:114`); captured: identical to the README's block (`-d/--download`, `-g/--generate`, `-u/--upload`). It works without a key: the Gemini client is created at import (`cli.py:25`) but asks for credentials only on a request.
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:131`; `README.md:245`): downloads `text_prompts/<group>/input-*.txt`.
  - Note: without the key (captured): `DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.` at `storage.Client(project=gcp_project)` (`cli.py:41`).
- [ ] `python cli.py -g` = `python cli.py --generate` — *inside*, with your key (`:132`; `README.md:246`): Gemini on Vertex AI prints a long "Generated text:" and writes `text_paragraphs/<group>/input-….txt`.
  - Note: with nothing downloaded it prints `Args: Namespace(download=False, generate=True, upload=False)` and `generate`, and exits 0 without calling Gemini (captured): a silent "success" that did nothing. Check that `text_prompts/<group>/` holds `input-*.txt` files first.
- [ ] `python cli.py -u` = `python cli.py --upload` — *inside*, with your key (`:133`; `README.md:247`).
- [ ] Verify `text_paragraphs/<group_name>/` in your bucket (`:136`).
- [ ] `exit` — *(extra)*
- [ ] *OPTIONAL: Publish the container* (`:140-148`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, then `./docker-shell.sh prod` — same notes as in Task A.

### Task C · `synthesis_audio_en` (`synthesis_audio_en/README.md`; Quick Reference `README.md:250-257`)

- [ ] `cd ../synthesis_audio_en` — "`cd` into the `synthesis_audio_en` folder" (`:17`).
- [ ] Read the four files (`:19-28`); key in place (`:34-48`); set the three values in `cli.py` (`:50-60`).
- [ ] `./docker-shell.sh` — build and run (default) (`:69`). Captured: `Building 8.2s` (`CACHED [2/5]`: the four non-transcribe Dockerfiles are identical up to that line, so B's apt layer is reused), 24 packages, the prompt.
- [ ] `./docker-shell.sh dev` · `./docker-shell.sh run` · `./docker-shell.sh prod` (`:70-72`), and `chmod +x docker-shell.sh` (`:77`), as in Task A.
- [ ] `uv add <package>` — *inside*, only for a new dependency (`:90`).
- [ ] `python cli.py --help` — *inside* (`:99`); with the key in place, the README's block (`-d/--download`, `-s/--synthesis`, *expected*, `:98-108`).
  - Note: captured before the `cli.py` edit: `AssertionError: Update group name` (`cli.py:19`). After the edit, made on the laptop while the container ran (the mount shows it at once), it fails at import without a key: `TextToSpeechLongAudioSynthesizeClient()` (`cli.py:23`) raises `DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.`
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:115`; `README.md:253`): downloads the generated paragraphs. Without a key: the same import-time error (captured).
- [ ] `python cli.py -s` = `python cli.py --synthesis` — *inside*, with your key (`:116`; `README.md:254`): long-audio Text-to-Speech (`en-US-Standard-B`) writes `text_audios/<group>/input-*.mp3` straight into the bucket; there is no `--upload` step (`README.md:257`).
- [ ] Verify `text_audios/<group_name>/` in your bucket (`:119`); long-audio synthesis can take a moment (`:121`).
- [ ] `exit` — *(extra)*
- [ ] *OPTIONAL: Publish the container* (`:125-133`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, then `./docker-shell.sh prod`.

### Task D · `translate_text` (`translate_text/README.md`; Quick Reference `README.md:259-265`)

- [ ] `cd ../translate_text` — "`cd` into the `translate_text` folder" (`:15`).
- [ ] Read the four files (`:17-26`); key in place (`:32-46`); set the three values in `cli.py` (`:48-58`). This file ships the course's values (E2).
- [ ] `./docker-shell.sh` — build and run (default) (`:67`). Captured: `Building 7.9s` (apt layer cached), 25 packages, the prompt.
- [ ] `./docker-shell.sh dev` · `./docker-shell.sh run` · `./docker-shell.sh prod` (`:68-70`), and `chmod +x docker-shell.sh` (`:75`), as in Task A.
- [ ] `uv add <package>` — *inside*, only for a new dependency (`:88`).
- [ ] *Translating into a different language* (`:92-105`): the README shows `target_language="fr"`, but the code says `"es"` (`cli.py:64`, E3). Edit it to `"fr"` (or any supported code) on your laptop; the mount makes the edit live.
- [ ] `python cli.py --help` — *inside* (`:114`); with the key in place, the README's block (`-d/--download`, `-t/--translate`, `-u/--upload`, description "Translate English to French", *expected*). Captured without a key: `translate.Client()` at import (`cli.py:22`) raises `DefaultCredentialsError`.
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:131`; `README.md:262`). Without a key: the same import-time error (captured).
- [ ] `python cli.py -t` = `python cli.py --translate` — *inside*, with your key (`:132`; `README.md:263`): Cloud Translation v2; Spanish unless you changed `target_language`.
- [ ] `python cli.py -u` = `python cli.py --upload` — *inside*, with your key (`:133`; `README.md:264`).
- [ ] Verify `text_translated/<group_name>/` in your bucket (`:136`).
- [ ] `exit` — *(extra)*
- [ ] *OPTIONAL: Publish the container* (`:140-148`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, then `./docker-shell.sh prod`.

### Task E · `synthesis_audio` (`synthesis_audio/README.md`; Quick Reference `README.md:267-274`)

- [ ] `cd ../synthesis_audio` — "`cd` into the `synthesis_audio` folder" (`:17`).
- [ ] Read the four files (`:19-28`); key in place (`:34-48`); set the three values in `cli.py` (`:50-60`).
- [ ] `./docker-shell.sh` — build and run (default) (`:69`). Captured: `Building 7.9s`, 24 packages, the prompt.
- [ ] `./docker-shell.sh dev` · `./docker-shell.sh run` · `./docker-shell.sh prod` (`:70-72`), and `chmod +x docker-shell.sh` (`:77`), as in Task A.
- [ ] `uv add <package>` — *inside*, only for a new dependency (`:90`).
- [ ] `python cli.py --help` — *inside* (`:99`); with the key in place, the README's block (`-d/--download`, `-s/--synthesis`, *expected*). Captured without a key: `DefaultCredentialsError` at import (`cli.py:22`).
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:115`; `README.md:270`): downloads the translated text. Without a key: the same import-time error (captured).
- [ ] `python cli.py -s` = `python cli.py --synthesis` — *inside*, with your key (`:116`; `README.md:271`): Text-to-Speech with `fr-FR-Standard-C` writes `output_audios/<group>/input-*.mp3`, "the final output of the pipeline" (`:119`).
- [ ] Verify `output_audios/<group_name>/` in your bucket (`:119-121`).
- [ ] *OPTIONAL ElevenLabs* (`:125-135`): create an ElevenLabs API key and add a file `11lab_api_key.txt` to your `secrets/` folder containing `XI_API_KEY=<API_KEY>`.
  - Note: `cli_11.py` reads `secrets/11lab_api_key.txt` relative to `/app` (the component folder), not `/secrets`, at import, and hard-codes the course's bucket (E10). Captured without it: `python cli_11.py --help` → `FileNotFoundError: [Errno 2] No such file or directory: 'secrets/11lab_api_key.txt'`. Point `secrets_file_path` (`cli_11.py:30`) at `/secrets/11lab_api_key.txt` rather than putting a key inside the component folder, which `COPY . ./` would bake into the image.
- [ ] `exit` — *(extra)*
- [ ] *OPTIONAL: Publish the container* (`:139-147`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, then `./docker-shell.sh prod`.

### mega-pipeline · Appendix (`README.md:278-380`)

- [ ] *Sample Code: Read/Write to a GCS Bucket* (`:280-317`): Python snippets, not commands. The upload sample names the object `input_audios/test.mp3` (`:313`); use an `input-…` name instead (E5).
- [ ] *Sample Dockerfile* (`:319-372`): the same as `transcribe_audio/Dockerfile` except `ARG DEBIAN_PACKAGES="build-essential"`.
- [ ] *Notes for running on Windows* (`:374-380`): run docker commands from Git BASH, always quote `$(pwd)`, prefix `winpty` for "the input device is not a TTY".
  - `MSYS_NO_PATHCONV=1 ./docker-shell.sh` — *(extra, not captured)* if Git BASH mangles `/secrets` or the `-v` specs (G18); combine with `winpty` if needed.

### mega-pipeline · After the README *(extra)*

*What `run` does on a laptop that never built the image* (§4 A12)
- [ ] `docker image rm mega-pipeline-transcribe-audio` — *(extra)* removes the local image (stands in for a teammate who never built it).
- [ ] `./docker-shell.sh run` — README command again, in `transcribe_audio/`; captured: `Local image not found, using image from registry...`, a pull of `dlops/mega-pipeline-transcribe-audio:latest`, `Creating a Pipfile for this project...`, a `(app) root@…:/app#` prompt, `Python 3.8.17`. Type `exit`.
- [ ] `ls -la; git status --short` — *(extra)* a new `Pipfile` owned by `root` in your folder: `?? Pipfile`. Remove it with `rm Pipfile`.
- [ ] `docker image inspect --format '{{.Created}}' dlops/mega-pipeline-transcribe-audio` — *(extra)* `2025-02-18T21:04:17…`.

*The L03 key and the image* (§4 A13)
- [ ] `./docker-shell.sh dev` then `docker run --rm --entrypoint ls mega-pipeline-transcribe-audio -la /app /app/secrets` — *(extra)* in a switched L03 clone whose `transcribe_audio/secrets/` still holds the old key: the key file is listed **inside** the image (captured with a stand-in file).

*Clean up*
- [ ] `docker images` — *(extra)* the five local images: transcribe 1.48 GB, the others 821-836 MB, plus any `dlops/…` you pulled (1.17 GB, 1.02 GB).
- [ ] `docker image rm mega-pipeline-transcribe-audio mega-pipeline-generate-text mega-pipeline-synthesis-audio-en mega-pipeline-translate-text mega-pipeline-synthesis-audio` — *(extra)* frees the disk.
- [ ] `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=<sa-email>` — *(extra)* deletes the SA key when you are done (or console **IAM & Admin → Service accounts → Keys**).
- [ ] `gcloud storage rm -r gs://<your-bucket>` — *(extra)* when the course no longer needs the bucket.
- [ ] `docker buildx rm multi-arch` — *(extra)* only if you ran `prod`.

### port_toy · Prerequisites (`README.md:20-30`)

- [ ] `docker run hello-world` — make sure Docker Desktop is running; captured: `Unable to find image 'hello-world:latest' locally`, the pull, then `Hello from Docker!`.

### port_toy · Step 1: Set up the network by hand (`README.md:75-183`)

- [ ] Clone or download the [repository](https://github.com/dlops-io/port_toy) (`:81`), from `~/AC215`.
- [ ] `git clone https://github.com/dlops-io/port_toy.git` — *(extra)* the usual clone command; the README gives none. Captured: `Cloning into 'port_toy'...`.
- [ ] `cd port_toy` (`:84`)
- [ ] `ls -a; ls gateway processor; git log --oneline -1` — *(extra)* the files of `README.md:59-69`; `d190c71 gateway: show the real host port in the diagram`.
- [ ] `docker network create toynet` (`:92`) — creates the user-defined bridge network; prints the network id.
- [ ] `docker network ls` — *(extra)* lists `toynet` (driver `bridge`) next to Docker's `bridge`, `host` and `none`.
- [ ] `docker build -t toy-processor ./processor` (`:100`) — captured: `Building 7.5s`, the apt step (curl) 6.4 s.
- [ ] `docker build -t toy-gateway ./gateway` (`:101`) — captured: `Building 0.3s`; the apt step is `CACHED` (both Dockerfiles are identical up to `COPY`).
- [ ] `docker image ls 'toy-*'` — *(extra)* both images, 198 MB each on disk (48.8 MB content); quote the pattern so the shell doesn't expand it.
- [ ] `docker run -d --name processor --network toynet -e PORT=9200 toy-processor` (`:109-110`) — starts the processor, detached, unpublished, listening on 9200; prints the container id.
- [ ] `docker run -d --name gateway --network toynet -p 127.0.0.1:8090:9100 -e PROCESSOR_HOST=processor -e PROCESSOR_PORT=9200 toy-gateway` (`:120-124`) — starts the gateway; host `127.0.0.1:8090` → container `9100`.
- [ ] `docker logs processor` (`:132`) — `processor listening on port 9200 (internal only)`.
- [ ] `docker logs gateway` (`:133`) — `gateway listening on port 9100  →  open http://localhost:8090` (two spaces on each side of the arrow; the README shows one, E15).
- [ ] Open http://localhost:8090, type a message, click **Send** (`:145-151`) — the text in capitals and three port lines; the first and third numbers match (an ephemeral port, e.g. `55620` in the capture), the middle one is `9200`.
- [ ] `curl -sS -X POST http://localhost:8090 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'` — *(extra)* the page's request from a terminal; captured: `{"upper": "HELLO FROM THE LAPTOP", "listen_port": 9200, "sender_port": 55620, "gateway_out_port": 55620}`. Leave both containers running (`:183`).

### port_toy · Step 2: Check the ports (`README.md:189-325`)

- [ ] `docker ps` (`:198`) — the gateway's PORTS column shows `127.0.0.1:8090->9100/tcp`; the processor's is empty.
- [ ] `docker ps --format 'table {{.Image}}\t{{.Ports}}\t{{.Names}}'` — *(extra)* the same in the README's three columns (`:204-206`).
- [ ] `docker run -d --name gateway-all --network toynet -p 8090:9100 toy-gateway` — *(extra)* the README's `-p 8090:9100` (`:238-240`, a fragment, not a command) in a full command; captured: `Bind for 127.0.0.1:8090 failed: port is already allocated`, exit 125. The container is created anyway: `docker rm gateway-all`. With `-p 8091:9100` it starts, and `docker ps` shows `0.0.0.0:8091->9100/tcp` (all addresses). Then `docker rm -f gateway-all`.
- [ ] `curl http://localhost:8090` (`:251`) — returns the gateway's HTML page (`<!DOCTYPE html>` …).
- [ ] `curl --max-time 3 http://localhost:9200/health` (`:259`) — should fail; captured: `curl: (7) Failed to connect to localhost:9200 after 0 ms: Could not connect to server`.
  - Note: if it succeeds, another program on your laptop uses port 9200; `lsof -i :9200` *(extra, macOS/Linux)* shows which (G14).
- [ ] `docker exec gateway curl http://processor:9200/health` (`:273`) — `ok`, below curl's progress meter (`docker exec` gives curl no terminal, so the meter shows).
- [ ] `docker exec gateway curl --max-time 3 http://localhost:9200/health` (`:285`) — should fail; captured: `curl: (7) Failed to connect to localhost port 9200 after 0 ms: Could not connect to server`.
- [ ] `docker exec gateway curl -s http://localhost:9100 | head -4` — *(extra)* inside the gateway, `localhost:9100` *is* the gateway: the page's first lines.
- [ ] `docker exec processor curl --version | head -1` — *(extra)* the processor image has curl too (8.14.1), although `:294` implies it does not (E14).
- [ ] `docker exec gateway cat /etc/resolv.conf; docker exec gateway getent hosts processor gateway` — *(extra)* `nameserver 127.0.0.11` (Docker's embedded DNS); `172.19.0.2 processor`, `172.19.0.3 gateway`.
- [ ] *Where do the port settings come from?* (`:298-325`): `-e PORT=9200`, `-e PROCESSOR_HOST=processor`, `-e PROCESSOR_PORT=9200` and `-p 127.0.0.1:8090:9100` are fragments of the Step 1 commands, not new commands.

### port_toy · Step 3: Change the ports (`README.md:331-420`)

- [ ] `docker rm -f gateway` (`:340`) — prints `gateway`.
- [ ] `docker run -d --name gateway --network toynet -p 127.0.0.1:8095:9100 -e PROCESSOR_HOST=processor -e PROCESSOR_PORT=9200 toy-gateway` (`:346-350`) — new host port. Open http://localhost:8095 (`:353`): it works, and `localhost:8090` no longer does (captured: `curl: (7) Failed to connect to localhost:8090 …`). `docker logs gateway` still says `open http://localhost:8090` (E15); `docker ps` shows `127.0.0.1:8095->9100/tcp`.
- [ ] `docker rm -f processor` (`:370`)
- [ ] `docker run -d --name processor --network toynet -e PORT=9300 toy-processor` (`:376-377`) — moves the processor to 9300. "Send a message from the browser. It should fail." (`:380`): use the gateway's current port, 8095.
  - Note: the page simply doesn't change (no error handling, E16). The page's request, captured: `curl: (52) Empty reply from server`.
- [ ] `docker logs gateway` — *(extra; the README's command, used here to see why)* the traceback ends in `ConnectionRefusedError: [Errno 111] Connection refused`; `docker logs processor` *(extra)* says `processor listening on port 9300 (internal only)`.
- [ ] `docker rm -f gateway` (`:389`)
- [ ] `docker run -d --name gateway --network toynet -p 127.0.0.1:8090:9100 -e PROCESSOR_HOST=processor -e PROCESSOR_PORT=9300 toy-gateway` (`:395-399`) — re-points the gateway and restores 8090. Open http://localhost:8090 and send (`:402`): it works, and the middle port line says `9300`.
- [ ] `docker rm -f gateway processor` (`:416`) — *Clean up before Compose*.
- [ ] `docker network rm toynet` (`:417`) — skipping these two makes Step 4 fail (G11).
- [ ] `docker ps -a; docker network ls` — *(extra)* only the exited `hello-world` container is left, and `toynet` is gone.

### port_toy · Step 4: Run with Compose (`README.md:426-529`)

- [ ] `docker compose up` (`:455`) — builds `port_toy-gateway` and `port_toy-processor`, creates network `toynet`, starts both containers, and streams both logs (`[+] up 5/5`, then the two banners). Open http://localhost:8090 and send a message (`:460`): it works.
- [ ] *Compare the commands* (`:478-484`), in a second terminal:
  - `docker ps` → `docker compose ps` — captured: `gateway` (`port_toy-gateway`, `127.0.0.1:8090->9100/tcp`) and `processor` (no ports).
  - `docker exec gateway curl ...` → `docker compose exec gateway curl ...` — with the full URL, `docker compose exec gateway curl http://processor:9200/health` *(the README writes `...`)*; captured: `ok`, no progress meter (`compose exec` gives curl a terminal).
  - `docker rm -f gateway processor` and `docker network rm toynet` → `docker compose down` (below).
  - `-p` on `docker run` → `ports:` in YAML; `-e` on `docker run` → `environment:` in YAML.
- [ ] `docker network ls` — *(extra)* Compose created `toynet` (the file names it, `docker-compose.yml:37-39`).
- [ ] Repeat a port experiment in `docker-compose.yml` (`:487`), e.g. change `"127.0.0.1:8090:9100"` to `"127.0.0.1:8095:9100"` (line 16) in your editor.
- [ ] `docker compose up -d` (`:492`) — applies the change in the background; captured after the port edit: `Container processor Running`, `Container gateway Started 10.5s` (only the changed service is recreated). Change the file back and run it again.
- [ ] `docker compose up -d --build` (`:500`) — rebuilds the images first; needed after editing `processor.py` (copied in by `COPY . .`). Captured after a one-line edit: only the processor's `COPY` layer is new, and only the processor is recreated.
- [ ] `docker compose restart gateway` — *(extra, not captured)* needed after editing `gateway.py`, which is mounted but read once at start; `gateway/index.html` edits show on the next page load.
- [ ] Press `Ctrl+C` if Compose is running in your terminal (`:507`) — stops the containers. Captured: `Gracefully Stopping... press Ctrl+C again to force`, then both `exited with code 137` about 20 s later (G12).
- [ ] `docker compose down` (`:512`) — removes the containers and the Compose-managed network; captured: `[+] down 3/3` (two containers, network `toynet`). The images remain (`:515`).
- [ ] `docker compose ps -a` (`:524`) — after `Ctrl+C` alone, both containers are listed as `Exited (137)`; after `down`, the list is empty.

### port_toy · Port and networking cheat sheet (`README.md:535-552`)

- [ ] Read it; it has no new commands (`-p 8090:9100` and `-p 127.0.0.1:8090:9100` are fragments). Each message in it was seen in the captures: `port is already allocated` (Step 2 extra), `Connection refused` (Step 3), `could not resolve host` (Exercise C1).

### port_toy · Handy commands (`README.md:557-576`)

*In the table's order; the ones not used in Steps 1-4 are marked new.*
- [ ] `docker network create toynet` — Step 1.
- [ ] `docker build -t toy-gateway ./gateway` — Step 1.
- [ ] `docker ps` — Step 2.
- [ ] `docker logs gateway` — Step 1.
- [ ] `docker exec -it gateway sh` — new: an interactive shell in the gateway (by-hand containers running); captured: typed `hostname`, `ls` (`Dockerfile  gateway.py  index.html`), `exit`.
- [ ] `docker rm -f gateway processor` — Step 3.
- [ ] `docker network rm toynet` — Step 3.
- [ ] `docker compose up -d` — Step 4.
- [ ] `docker compose up -d --build` — Step 4.
- [ ] `docker compose ps` — Step 4.
- [ ] `docker compose logs -f gateway` — new: follows the gateway's log; a send from a second terminal shows up as a `POST` line; `Ctrl+C` ends it (exit 130). Use it to watch Step 3's failure (G13).
- [ ] `docker compose exec gateway sh` — new: a shell in the gateway under Compose; captured: `echo $PROCESSOR_HOST $PROCESSOR_PORT` → `processor 9200`.
- [ ] `docker compose down` — Step 4.
- [ ] `docker network ls` — Step 1 extra / Step 4 extra.
- [ ] `docker network inspect toynet` — new: subnet `172.19.0.0/16`, processor `172.19.0.2`, gateway `172.19.0.3` in the capture (by-hand containers running).

### port_toy · Clean up *(extra)*

- [ ] `docker compose down` — in `port_toy/`, if the app is still up.
- [ ] `docker image rm toy-gateway toy-processor port_toy-gateway port_toy-processor` — the by-hand and Compose-built images; they share their layers, about 200 MB in all.
- [ ] `docker ps -a` then `docker rm <id>` — the exited `hello-world` container, if you want it gone.

---

## 1. What you build

This lecture has two independent tutorials.

**(A) Mega-pipeline, `flexible-workflow` branch.** You re-run the five-stage podcast pipeline from L03 (transcribe → generate → synthesize EN, translate → synthesize FR), this time the way a team would ship it:
- **Your own resources.** You use your own GCS bucket and your own service account (SA) with explicit IAM roles.
- **Key outside the repo.** The SA's JSON key lives in a `secrets/` folder *next to* the repo. It is mounted into each container at run time, never baked into an image.
- **Committed tooling.** Each component ships a committed `Dockerfile`, `pyproject.toml` and `uv.lock`, plus a `docker-shell.sh` wrapper with four modes:
  - build-and-run (default)
  - build only (`dev`)
  - run a prebuilt image, falling back to Docker Hub (`run`)
  - build multi-arch and push (`prod`)

You write no Dockerfile this time. You read them, configure three values per `cli.py`, and drive each container's CLI. The stages still talk only through the bucket; there are no ports and no container networks in part A.

**(B) port_toy.** A deliberately tiny two-container web app (Python standard library only, no GCP).
- A **gateway** serves a page on container port 9100, published to your laptop as `127.0.0.1:8090`.
- It forwards text to a **processor** on container port 9200. That port is not published; the gateway reaches it by the DNS name `processor` on a user-defined bridge network, `toynet`.
- You wire it by hand with `docker network create`, `docker run -p` and `-e`, break it by changing ports, fix it with configuration only, and then replace all of it with one `docker-compose.yml`.

```
(A) MEGA-PIPELINE, flexible-workflow            [laptop, e.g. ~/AC215 = <your-workspace>]
+--------------------------------------------------------------------------------------------------+
| <your-workspace>/                                                                                 |
|   secrets/mega-pipeline.json   <- YOUR SA key (outside the repo, never in Git)                    |
|   mega-pipeline/  (branch flexible-workflow)                                                      |
|     transcribe_audio/  generate_text/  synthesis_audio_en/  translate_text/  synthesis_audio/     |
|       each: Dockerfile  pyproject.toml  uv.lock  docker-shell.sh  cli.py                           |
|                                                                                                   |
|   $ ./docker-shell.sh        (no arg = "dev-run")                                                 |
|        |  docker build -t mega-pipeline-<component> -f Dockerfile .                               |
|        |  docker run --rm --name mega-pipeline-<component> -ti                                    |
|        |     -v <component dir>:/app   -v <component dir>/../../secrets/:/secrets                 |
|        |     -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json                        |
|        v                                                                                          |
|  +-- Docker Desktop Linux VM -----------------------------------------------------+              |
|  | [container]  user "app" (uid 1000), bash with /home/app/.venv activated        |              |
|  |   /app             <- bind mount: your live component folder (code + outputs)  |              |
|  |   /secrets         <- bind mount: <your-workspace>/secrets (the key)            |              |
|  |   /home/app/.venv  <- baked into the image by `RUN uv sync` (Python 3.14.8 at  |              |
|  |                       the time of capture, uv 0.13.0)                          |              |
|  |   app@<id>:/app$ python cli.py -d | -t/-g/-s | -u                              |              |
|  +----------|--------------------------------------------------------^------------+              |
+-------------|--------------------------------------------------------|-----------------------------+
              | HTTPS / gRPC with an OAuth token that google-auth       | prod: docker buildx build
              | mints from /secrets/mega-pipeline.json                  |  --platform linux/amd64,linux/arm64 --push
              v                                                         v
 GOOGLE CLOUD - your project                              DOCKER HUB  $DOCKER_USERNAME/mega-pipeline-<component>
 +-------------------------------------------------+       (script default "dlops"; dlops/...:latest is a
 | GCS bucket <your-bucket>                        |        2025-02-18 Python 3.8.17 / pipenv build, E1)
 |   input_audios/input-*.mp3                      |                 ^
 |   text_prompts/<group>/input-*.txt     (A)      |                 | run: pulled only if no local image
 |   text_paragraphs/<group>/input-*.txt  (B)      |
 |   text_audios/<group>/input-*.mp3      (C)      |  APIs called: Speech-to-Text (A), Vertex AI Gemini (B),
 |   text_translated/<group>/input-*.txt  (D)      |  Text-to-Speech long-audio (C, E: writes into the bucket
 |   output_audios/<group>/input-*.mp3    (E)      |  itself), Cloud Translation v2 (D)
 +-------------------------------------------------+

 Data hand-off (no container ever calls another one; the bucket is the "bus"):
 input_audios --A transcribe (ffmpeg mp3->flac, Speech-to-Text)--> text_prompts/<g>
   --B generate (Gemini, default gemini-2.5-flash-lite)--> text_paragraphs/<g>
       +--C synthesis_audio_en (TTS en-US-Standard-B)--> text_audios/<g>
       +--D translate_text (Translation v2, target "es" in code!)--> text_translated/<g>
             --E synthesis_audio (TTS fr-FR-Standard-C)--> output_audios/<g>


(B) PORT_TOY
 YOUR LAPTOP (host network namespace)
   browser --> http://localhost:8090 ----+          curl http://localhost:9200  -->  curl: (7) refused
                                         |  published: 127.0.0.1:8090 -> 9100/tcp  (-p / ports:)
 +---------------------------------------|---- user-defined bridge network "toynet" ------------------+
 |  (172.19.0.0/16 in the capture)       |                                                            |
 |  Docker embedded DNS at 127.0.0.11: "gateway" -> 172.19.0.3    "processor" -> 172.19.0.2           |
 |                                       v                                                            |
 |  [gateway]  own netns, own localhost         [processor]  own netns, own localhost                 |
 |   python -u gateway.py                        python -u processor.py                               |
 |   listens 0.0.0.0:9100 ($PORT, default 9100)  listens 0.0.0.0:9200 ($PORT=9200)                     |
 |   GET /  -> index.html                        GET /health -> "ok"                                  |
 |   POST / -> http://$PROCESSOR_HOST:$PROCESSOR_PORT  ---->  POST / -> {"upper", "listen_port",       |
 |            src port = ephemeral (e.g. 55620)                          "sender_port"}                |
 |   (Compose only: ./gateway bind-mounted at /app)                                                    |
 +----------------------------------------------------------------------------------------------------+
   Steps 1-3: docker network create / docker build / docker run ... by hand
   Step 4:    docker compose up   (the same thing, declared in docker-compose.yml)
```

---

## 2. Prerequisites and costs

### Local installs (both tutorials)
- **Docker Desktop**, with Compose v2 (`docker compose`) and Buildx. The port_toy README asks you to check it with `docker run hello-world` (`port_toy/README.md:26-30`). port_toy needs nothing else: "You do not need a GCP account or Python installed on your laptop." (`port_toy/README.md:24`)
- **Git** and a bash shell. On Windows use Git BASH, and prefix `winpty` if you see "the input device is not a TTY" (`mega-pipeline/README.md:374-380`).
- *Optional:* the **`gcloud` CLI**, signed in with `gcloud auth login` (Tutorial 0), for the one-shot API-enable command (`mega-pipeline/README.md:191-199`). You can do everything in the console instead. Without a signed-in account the command stops at `You do not currently have an active account selected.` (captured).
- **Not needed on the host:** Python and `uv`. Both live inside the images (`mega-pipeline/transcribe_audio/Dockerfile:2`, `:29`).
- **Disk.** The five mega-pipeline images take 1.48 GB (`transcribe_audio`, which also has `ffmpeg`) and 821-836 MB each for the other four, as `docker images` shows them; port_toy's images about 200 MB in all.

### GCP (mega-pipeline only)
1. **A project with billing enabled.** You need its id for `gcp_project` in each `cli.py` (`mega-pipeline/README.md:127-134`).
2. **Enable five APIs.** The command, verbatim from `mega-pipeline/README.md:192-198`:
   ```bash
   gcloud config set project <your-project-id>
   gcloud services enable \
     storage.googleapis.com \
     aiplatform.googleapis.com \
     speech.googleapis.com \
     texttospeech.googleapis.com \
     translate.googleapis.com
   ```
   Replace `<your-project-id>` with your id, without the angle brackets: typed literally, the shell reads `<` and `>` as redirections and refuses the line (captured, §4 A4).
3. **Create a service account** (e.g. `mega-pipeline-sa`) with these roles on the project (`mega-pipeline/README.md:177-181`):

   | Role | Role id | Needed by |
   |---|---|---|
   | Storage Admin | `roles/storage.admin` | all five components |
   | Agent Platform User (formerly "Vertex AI User") | `roles/aiplatform.user` | `generate_text` |
   | Cloud Speech Client | `roles/speech.client` | `transcribe_audio` |
   | Cloud Translation API User | `roles/cloudtranslate.user` | `translate_text` |
   | *(none)* | Text-to-Speech needs no role, per `mega-pipeline/README.md:185` | both synthesis components |

4. **Download a JSON key.** Save it **exactly** as `<your-workspace>/secrets/mega-pipeline.json`, one level *above* the repo (`mega-pipeline/README.md:105-119`, `:183`).
   - The scripts compute this path as `SECRETS_DIR=$(pwd)/../../secrets/` from inside a component folder (`mega-pipeline/transcribe_audio/docker-shell.sh:9`).
   - They mount it at `/secrets` (`:94`) and pass `-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` (`:10`, `:95`).
   - Example: the captures cloned into `~/AC215/mega-pipeline`, and `docker inspect` showed the mount `/home/student/AC215/secrets -> /secrets`. Your key would be `~/AC215/secrets/mega-pipeline.json`.
   - The same `AC215/secrets/` folder is also where `llm-rag` (L05) and `cheese-app-v0` (L10) look for their keys: `llm-rag/docker-compose.yml:11` mounts `../secrets:/secrets`, and `cheese-app-v0/api-service/docker-shell.sh:8` uses `$(pwd)/../../secrets/`.
5. **Your own GCS bucket, seeded with input audio.** The README says you own one (`mega-pipeline/README.md:62`, `:150`), but it gives **no command** to create it (Errata E5). Not in the README, but standard:
   ```bash
   gcloud storage buckets create gs://<your-bucket> --location=us-central1
   gcloud storage cp input-01.mp3 gs://<your-bucket>/input_audios/
   ```
   - Name the audio `input-<something>.mp3`. Transcribe's upload only picks up `input-*.txt` (`mega-pipeline/transcribe_audio/cli.py:102`), and every later stage only downloads `input-*.txt` (e.g. `mega-pipeline/generate_text/cli.py:43`). The README's Appendix uploads `input_audios/test.mp3` (`mega-pipeline/README.md:313`), a name that would never leave the transcribe step.
6. **Environment variables the code reads**
   - `GOOGLE_APPLICATION_CREDENTIALS` is set by the script, as above (captured inside the container: `/secrets/mega-pipeline.json`).
   - `GEMINI_MODEL` is optional; the default is `"gemini-2.5-flash-lite"` (`mega-pipeline/generate_text/cli.py:73`).
   - Optional ElevenLabs bonus: `XI_API_KEY`, read from a file `secrets/11lab_api_key.txt` *relative to the working directory* (`mega-pipeline/synthesis_audio/cli_11.py:30-39`). That path is the component folder, not `/secrets` (Errata E10).
7. **Docker Hub account and access token.** Only for `./docker-shell.sh prod`, after `docker login -u <USER NAME> -p <ACCESS TOKEN>` (`mega-pipeline/transcribe_audio/README.md:126-132`). You must also change `DOCKER_USERNAME="dlops"` (`mega-pipeline/transcribe_audio/docker-shell.sh:13`) to your own namespace.

### Billable resources, and how to shut them down

| Resource | Billed for | Cleanup |
|---|---|---|
| Cloud Speech-to-Text (`long_running_recognize`, `transcribe_audio/cli.py:80`) | audio minutes | none needed after the run. Keep the clip short. |
| Vertex AI Gemini (`generate_text/cli.py:75-77`) | input and output tokens (a 1000+ word output per file) | none needed after the run |
| Cloud Translation v2 (`translate_text/cli.py:61-66`) | characters | none needed after the run |
| Text-to-Speech long audio (`synthesis_audio_en/cli.py:89`, `synthesis_audio/cli.py:88`) | characters | none needed after the run |
| GCS bucket | storage (tiny), operations | `gcloud storage rm -r gs://<your-bucket>` when the course no longer needs it |
| SA key | a long-lived credential (a security liability, not a cost) | delete it when done: console **IAM & Admin → Service accounts → Keys**, or `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=<sa-email>` |
| Docker Hub | free for public repositories | delete pushed repositories in the Hub UI if they contain anything sensitive (G6) |

Local cleanup (not billable, but the images are large; each carries `build-essential`, and transcribe also `ffmpeg`):
```bash
docker image rm mega-pipeline-transcribe-audio mega-pipeline-generate-text mega-pipeline-synthesis-audio-en mega-pipeline-translate-text mega-pipeline-synthesis-audio
docker image rm dlops/mega-pipeline-transcribe-audio dlops/mega-pipeline-generate-text   # only if run pulled them
docker buildx rm multi-arch          # only if you ran ./docker-shell.sh prod
docker compose down                  # in port_toy/, then:
docker image rm toy-gateway toy-processor port_toy-gateway port_toy-processor
```
The last two names are what Compose calls images it builds without an `image:` key (`<project>-<service>`, the project being the folder name `port_toy`); the captures show exactly these names (`port-laptop/66-x-images-remain.txt`).

---

## 3. Concepts this tutorial teaches

### C1. The flexible workflow: build the image yourself, or pull a prebuilt one
- **Explanation.** An image can reach your machine in two ways:
  - **Build it** from a recipe that lives in Git: `Dockerfile` + `pyproject.toml` + `uv.lock`.
  - **Pull it** ready-made from a registry (Docker Hub).

  Early in a project everyone builds, because the recipe changes daily. Later, one person publishes images and everyone else pulls (`mega-pipeline/README.md:67-74`). `docker-shell.sh` covers both: no argument means build then run, `dev` builds, `run` runs (local if present, else registry), `prod` builds multi-arch and pushes (`mega-pipeline/transcribe_audio/docker-shell.sh:28-97`).
- **Mental model.** The Dockerfile plus lock file is the *source*. The image is the *compiled artifact*. A tag like `dlops/mega-pipeline-transcribe-audio` is a *pointer* to some artifact, built at some time, from some commit. The tag does not promise that the artifact came from the commit you have checked out. Not everything in the recipe is pinned either: the base-image tag, `apt-get upgrade` and `pip install uv` take whatever is current on the day you build (Python 3.14.8 and uv 0.13.0 at the time of recording).
- **Analogy.** A recipe card in a shared binder (Git) versus frozen meals in the shop freezer (registry). The frozen meal is fast, but it was cooked from whatever version of the recipe existed on the day it was frozen.
- **Common misconception.** "`./docker-shell.sh run` gives me exactly what this branch's Dockerfile describes." It first uses any local image named `mega-pipeline-<component>`, however old (`docker-shell.sh:83-85`). Only if there is none does it fall back to `$DOCKER_USERNAME/mega-pipeline-<component>`, i.e. whatever `latest` was last pushed (or a copy you pulled earlier). For `dlops/*` that is a 2025-02-18 build: captured, it starts a pipenv shell as `root` on **Python 3.8.17**, and because the script mounts your folder over `/app` (`docker-shell.sh:93`), the code is *yours* while the environment is *theirs*: `generate_text`'s `--help` fails with `ImportError: cannot import name 'genai' from 'google'`.

### C2. A wrapper script as executable documentation
- **Explanation.** `docker run` lines grow: an image name, a container name, two bind mounts, an env var, `-ti`, `--rm`. And `prod` needs three Buildx commands. Putting them in a script that every teammate runs from the same relative location makes the workflow repeatable (`mega-pipeline/README.md:65`).
  - `set -e` (`docker-shell.sh:4`) aborts on the first failing command.
  - `$(pwd)` (`:8-9`) ties all paths to *where you run it from*.
  - `echo "Docker Username: $DOCKER_USERNAME, Build Mode: $BUILD_MODE"` (`:48`) prints the first line you see (captured: `Docker Username: dlops, Build Mode: dev-run`).
- **Mental model.** The script is just a handful of `docker` commands (`docker build`, `docker image inspect`, `docker run`, and the `docker buildx` inspect/rm/create/build sequence for `prod`), chosen by a `case` on `$1`. Read it top to bottom once, and you can always run the commands by hand.
- **Analogy.** A cockpit checklist: no new physics, just the right switches in the right order every time.
- **Common misconception.** "I can run it from anywhere." No. `BASE_DIR` and `SECRETS_DIR` are computed from your *current directory* (`:8-9`), and `docker build ... .` uses the current folder as the build context (`:75`). Run it from inside the component folder.

### C3. Bind mounts shadow the image's `/app`, so the venv lives outside it
- **Explanation.**
  - At build time the Dockerfile copies the component folder into `/app` (`Dockerfile:39`) and runs `uv sync` (`:41`). Because `UV_PROJECT_ENVIRONMENT=/home/app/.venv` (`:17`), the venv lands in `/home/app/.venv`, **not** in `/app/.venv`. The build log says so: `Using CPython 3.14.8 interpreter at: /usr/local/bin/python3`, `Creating virtual environment at: /home/app/.venv`, `Installed 26 packages` (transcribe, captured).
  - At run time `-v "$BASE_DIR":/app` (`docker-shell.sh:93`) lays your *live host folder* over `/app`. The image's copy of the code becomes invisible, but `/home/app/.venv` is untouched.
  - Results: edits in VS Code show up instantly (captured: a `cli.py` edit made on the laptop while the `synthesis_audio_en` container ran changed the next `--help` at once), and files the CLI writes (`input_audios/`, `text_prompts/…`) appear on your host. The venv survives because it is outside the mount point.
- **Mental model.** A container's filesystem is a stack of read-only image layers plus a thin writable layer. A bind mount is a window cut into that stack at one path: through it you see the host, not the image.
- **Analogy.** Laying a transparent sheet with your own notes over one page of a printed book. That page now shows your notes. Every other page still shows the print.
- **Common misconception.** "If I `uv add` a package inside the container, it is installed from now on." `uv add` rewrites `pyproject.toml` and `uv.lock` *on the host* through the mount, but the package is installed into `/home/app/.venv` in the container's writable layer, which `--rm` throws away on exit. You must rebuild (`./docker-shell.sh dev` or the default mode) to bake it in. The README says so (`mega-pipeline/transcribe_audio/README.md:89`), but `run` mode skips the rebuild (Exercise B5 checked it: `ModuleNotFoundError: No module named 'rich'` after `run`).

### C4. Runtime secrets and machine identity (service account → IAM → API)
- **Explanation.**
  - The code authenticates as a **service account**, an identity for software (`mega-pipeline/README.md:171`).
  - Google client libraries use **Application Default Credentials**: if `GOOGLE_APPLICATION_CREDENTIALS` names a JSON key file, they use it to mint short-lived OAuth access tokens.
  - In this branch the key file is **mounted** at `/secrets` and the env var is passed with `-e` at `docker run` time (`docker-shell.sh:94-95`).
  - In L03 it was **baked** into the Dockerfile as `ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` (`main:README.md:194-195`), and the key sat inside each component folder (`main:README.md:97`).

  Two separate gates must open besides the key: the API must be **enabled** in the project, and the SA must hold a **role** that grants the permission (`mega-pipeline/README.md:187`).
- **Mental model.** Three independent layers:
  - *Who am I?* The key file. It fails **inside your container**, before any request leaves: `google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.` (captured in all five components).
  - *What may I do?* IAM roles on the project or bucket. Fails **at Google**, as a 403 permission error.
  - *Is the service even switched on?* The API is enabled. Also fails **at Google**, with a 403 whose message says the API is disabled or has not been used in the project.

  Gates 2 and 3 were not reproduced (no Google account); with your key, read the last line of the traceback for "permission" or "disabled".
- **Analogy.** A hotel key card (the key file) is useless if it is not programmed for your floor (the role), or if the gym is closed for the season (the API is not enabled).
- **Common misconception.** "`.gitignore` keeps my key safe." `.gitignore` only affects Git. `docker build` uses `.dockerignore`, and **none of the branches have one**. A `secrets/` folder left *inside* a component folder from L03 is copied into the image by `COPY --chown=app:app . ./` (`Dockerfile:39`); the captures found it in the image after `./docker-shell.sh dev`, and `prod` would push it to Docker Hub (Gotcha G6).

### C5. Multi-architecture images
- **Explanation.** Images contain CPU-specific binaries. An Apple-Silicon Mac builds `linux/arm64` by default, while most cloud VMs are `linux/amd64`.
  - `docker buildx build --platform linux/amd64,linux/arm64 --push` (`docker-shell.sh:66`) builds both variants (one natively, the other under QEMU emulation) and pushes an **image index** (a.k.a. manifest list): one tag pointing at both. The existing `dlops/*` tags are exactly this: an OCI index with amd64, arm64 and two attestation entries.
  - `docker pull` and `docker run` then pick the variant that matches the host.
  - The script first (re)creates a builder named `multi-arch` (`docker-shell.sh:55-62`). `docker buildx create` without `--driver` uses the `docker-container` driver, i.e. BuildKit running in its own container (`buildx_buildkit_multi-arch0`, image `moby/buildkit:buildx-stable-1`, in exercise check B7); `--driver-opt network=host` gives that container the host's network.
- **Mental model.** A tag is a signpost with one arrow per CPU architecture.
- **Analogy.** A plug adapter kit: one product box (the tag), with a different plug inside for each country (architecture). The shop hands you the one that fits your wall.
- **Common misconception.** "An image runs anywhere Docker runs." It runs anywhere *its architecture* runs, unless the host emulates the other one, slowly. Also, the `multi-arch` builder stays selected after `prod` (`--use`, `:62`); on Docker Engine 29.8.2 that changed only `docker buildx build` commands, not the plain `docker build` the script's other modes run (G8).

### C6. Container networks and service-name DNS
- **Explanation.**
  - Every container gets its own **network namespace**: its own interfaces, its own routing table, its own `localhost`.
  - A **user-defined bridge network** (`docker network create toynet`, `port_toy/README.md:92`) connects containers like a virtual switch. Docker runs an **embedded DNS server** for it, reached inside each container at `127.0.0.11`, so a container's name resolves to its current IP on that network. That is why `http://processor:9200` works (`port_toy/README.md:171-181`). Captured: `toynet` got `172.19.0.0/16`, the processor `172.19.0.2`, the gateway `172.19.0.3`.
  - Compose creates such a network automatically and makes each **service name** resolvable. It is named `toynet` here because of `name: toynet` (`port_toy/docker-compose.yml:37-39`); otherwise it would be `<project>_default` (`port_toy/README.md:473`).
- **Mental model.** Each container is a separate little computer. The network is a LAN with its own phone book, and the phone book is updated whenever a container (re)starts and gets a new IP.
- **Analogy.** An office floor: everyone has their own desk phone (namespace). The internal directory lets you dial "processor" instead of memorizing extension 172.19.0.2.
- **Common misconception.** "Containers can always find each other by name." Only on a user-defined network (or a Compose network). On Docker's default `bridge` network (no `--network`) names don't resolve between containers: captured, `curl: (6) Could not resolve host: processor` (Exercise C1). Second misconception: "`localhost` inside the gateway is my laptop." It is the gateway itself (`port_toy/README.md:290`, `:546`).

### C7. Ports: listening vs published vs exposed vs source; host vs container; bind address
- **Listening port.** A server binds `(address, port)` and accepts connections. Both toy servers bind `("", port)`, meaning all interfaces of their own namespace (`gateway.py:52`, `processor.py:43`), on ports read from `$PORT` (`gateway.py:51`, `processor.py:42`).
- **Published port** (`-p 127.0.0.1:8090:9100`, or `ports:`). Docker forwards connections that reach a *host* address and port into a *container* port. The order is `ip:host:container`: "The host port comes first" (`port_toy/README.md:224-230`). `127.0.0.1` keeps it reachable from your machine only (`:232-244`); without it the PORTS column says `0.0.0.0:<port>->9100/tcp`, all host addresses (captured with 8091).
- **`EXPOSE`.** Only metadata in the image: "Documents a container port. It does not publish it." (`port_toy/README.md:545`). Neither toy Dockerfile uses it, which is why the processor's `PORTS` column is empty (`:211`).
- **Source (ephemeral) port.** The caller's side of a TCP connection, chosen by the OS. Container-to-container traffic on the same bridge is not NATed, so the processor sees the same source port the gateway was given: "gateway sent from port" = "processor saw it arrive from" (`port_toy/README.md:153-169`; read by `gateway.py:38` and `processor.py:32`). Captured: `55620` on one send, `55634` on the next.
- **Mental model.** Every namespace has its own full set of 65,535 port numbers. Two containers can both listen on 9100 without conflict. Only *host* ports can collide, as in `port is already allocated` (`port_toy/README.md:550`; captured).
- **Analogy.** An apartment building. Every flat has a room 9100. The building's street door 8090 (published) leads to flat *gateway*, room 9100. The processor's flat has no street door; you can only reach it from the inside corridor (the network).
- **Common misconception.** "`EXPOSE` (or the processor listening on 9200) means `localhost:9200` works on my laptop." It does not; only `-p`/`ports:` (or `-P`) creates a host-side door. Second misconception: binding to `127.0.0.1` *inside* the container is "safer". It makes the published port useless, because forwarded traffic arrives on the container's network interface, not on its loopback (Exercise C2: `curl: (56) Recv failure: Connection reset by peer`).

### C8. Docker Compose: the same commands, declared once
- **Explanation.** `docker-compose.yml` declares services, how to build them, their ports, environment, volumes, networks and start order. `docker compose up` builds images if needed, creates the network and starts containers; `docker compose down` removes containers and the network (`port_toy/README.md:462-473`, `:505-529`).
  - Mapping: `-p` ↔ `ports:`, `-e` ↔ `environment:`, `docker ps` ↔ `docker compose ps`, and `rm -f` + `network rm` ↔ `down` (`port_toy/README.md:478-484`).
  - This compose file adds two things the by-hand run did not have:
    - a live bind mount of `./gateway:/app` (`docker-compose.yml:17-18`)
    - `depends_on` (`:22-23`), which orders *start-up* only; it does not wait for readiness
- **Mental model.** Compose is a reconciler. You describe the desired state; `up` makes reality match, recreating only the services whose configuration (or image) changed. Captured: after a port edit, `up -d` printed `Container processor Running` and `Container gateway Started`.
- **Analogy.** A restaurant order ticket (YAML) versus shouting instructions to each cook (individual `docker run` commands).
- **Common misconception.** "`Ctrl+C` cleans up." It only *stops* the containers; they and the network remain until `docker compose down` (`port_toy/README.md:517-529`). Captured: after `Ctrl+C`, `docker compose ps -a` still listed both as `Exited (137)`.

---

## 4. Step-by-step walkthrough

Steps follow the README order. Commands in code spans are verbatim from the README unless marked *(extra)*. Each step gives the action, what happens under the hood, a checkpoint and what to do if it fails.

**About the outputs below.** They are real, trimmed (first and last lines, with `…` between) from the 2026-10-14 captures in `assets/terminal/` (file names given with each block; `[exit N]` lines omitted, exit statuses mentioned where they matter). Outputs labelled *expected* come from the READMEs, not from a run. On your laptop:
- **There was no Google key in the captures.** Every command that talks to Google stops at `DefaultCredentialsError` there. With your key in `secrets/`, the same commands do their job; for those, this guide says what to look for (the tutorial documents no output for a successful run).
- The terminal ran as user `student` in `~/AC215` on Linux; your prompt, paths and the exact wording of a few shell messages (zsh on a Mac) differ.
- Container ids, ephemeral ports, times, image ids and digests change on every run. The capture's base images were rebuilt with a proxy certificate, so build logs show a different `FROM` digest and no base-image download; your first build pulls `python:3.14-slim-bookworm` (or `python:3.14-slim` for port_toy) first.
- Versions move: Docker Engine 29.8.2, Compose v5.6.0, Python 3.14.8, uv 0.13.0 and the package versions were current on 2026-10-14.
- port_toy's browser was replaced by `curl` sending the page's request: `curl -sS -X POST http://localhost:8090 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'` (the page sends whatever you type, `"hello from my browser"` by default, `index.html:32`). Its JSON reply is what the page draws: `upper` → "Processor's reply"; `gateway_out_port`, `listen_port`, `sender_port` → the three port lines.

### Part A — mega-pipeline, `flexible-workflow`

**A1. Get the code: starting fresh** (`README.md:32-37`).
```bash
git clone --branch flexible-workflow https://github.com/dlops-io/mega-pipeline.git
cd mega-pipeline
```
- **Under the hood.** `--branch` doesn't limit what is fetched: the clone has every branch, and `flexible-workflow` is the one checked out (a single-branch clone would need `--single-branch`).
- **Checkpoint** *(extra)*. Captured (`mega-laptop/03-x-branch.txt`, `04-x-ls.txt`):
  ```text
  $ git branch; git log --oneline -1
  * flexible-workflow
  cc67f3b latest mega pipeline flexible flow
  $ ls; ls -a transcribe_audio
  README.md
  generate_text
  mega-pipeline-bucket.png
  mega-pipeline-flow.png
  synthesis_audio
  synthesis_audio_en
  transcribe_audio
  translate_text
  .
  ..
  .gitignore
  Dockerfile
  README.md
  cli.py
  docker-shell.sh
  pyproject.toml
  uv.lock
  ```
  All five `docker-shell.sh` are already executable: `-rwxr-xr-x`, committed as mode `100755` (`mega-laptop/05-x-modes.txt`).

**A2. Get the code: switching an L03 clone** (`README.md:39-50`).
```bash
cd mega-pipeline
git fetch origin                      # get the branches you don't have yet
git checkout flexible-workflow        # switch to this tutorial's branch
git branch                            # confirm: * flexible-workflow
```
- **The starting point** the capture recreated (`mega-l03-laptop/01-x-l03-state.txt`): an L03 clone on `main` with your `group_name` edit in `transcribe_audio/cli.py`, the Dockerfile and `uv.lock` you made in `generate_text/` (untracked: `main` has no `generate_text/.gitignore`), and in `transcribe_audio/` your `Dockerfile`, `pyproject.toml`, `uv.lock` and the key in `secrets/` (all four ignored by `main:transcribe_audio/.gitignore:3-7`):
  ```text
  $ git status --short; git status --short --ignored | grep '^!!'; head -1 transcribe_audio/Dockerfile
   M transcribe_audio/cli.py
  ?? generate_text/Dockerfile
  ?? generate_text/uv.lock
  !! transcribe_audio/Dockerfile
  !! transcribe_audio/pyproject.toml
  !! transcribe_audio/secrets/mega-pipeline.json
  !! transcribe_audio/uv.lock
  FROM python:3.12-slim-bookworm
  ```
- **`git fetch origin`** printed nothing (`03-fetch.txt`): a clone already has every branch, and nothing had changed since. An older clone may list updated branches; that's fine.
- **`git checkout flexible-workflow`** refuses, for two reasons, in one message (`04-checkout.txt`, exit 1):
  ```text
  $ git checkout flexible-workflow
  error: Your local changes to the following files would be overwritten by checkout:
  	transcribe_audio/cli.py
  Please commit your changes or stash them before you switch branches.
  error: The following untracked working tree files would be overwritten by checkout:
  	generate_text/Dockerfile
  	generate_text/uv.lock
  Please move or remove them before you switch branches.
  Aborting
  ```
  Nothing changed: Git checks before it writes anything.
- **The README's fix** (`README.md:48`): "Either stash them (`git stash`) or throw them away (`git checkout -- .`)". It covers only the first reason (`05-stash.txt`, `06-checkout-after-stash.txt`):
  ```text
  $ git stash
  Saved working directory and index state WIP on main: c6bbc9b fix for Google Speech-to-Text automatically breaks longer audio files into chunks separated by natural pauses.
  $ git checkout flexible-workflow
  error: The following untracked working tree files would be overwritten by checkout:
  	generate_text/Dockerfile
  	generate_text/uv.lock
  Please move or remove them before you switch branches.
  Aborting
  ```
- **The fix that works** *(extra)*: stash the untracked files too, then switch (`07-x-stash-u.txt`, `08-checkout-ok.txt`, `09-branch.txt`):
  ```text
  $ git stash -u
  Saved working directory and index state WIP on main: c6bbc9b fix for Google Speech-to-Text automatically breaks longer audio files into chunks separated by natural pauses.
  $ git checkout flexible-workflow
  branch 'flexible-workflow' set up to track 'origin/flexible-workflow'.
  Switched to a new branch 'flexible-workflow'
  $ git branch
  * flexible-workflow
    main
  ```
- **What happened quietly** (`10-x-after.txt`, `11-x-dockerfile-replaced.txt`):
  - Your ignored L03 `transcribe_audio/Dockerfile`, `pyproject.toml` and `uv.lock` were **replaced** by the branch's files without a word (Git treats ignored files as expendable): `head -2 transcribe_audio/Dockerfile` now says `FROM python:3.14-slim-bookworm`, and the sizes are the branch's (1274, 249 and 85761 bytes). The same happens in `synthesis_audio_en`, `translate_text` and `synthesis_audio`, whose `main` `.gitignore` files ignore the same names. If you want them, copy them out *before* switching.
  - `transcribe_audio/secrets/mega-pipeline.json` is still there, as the README says ("Your `secrets/` folder … stay[s] put", `:50`): `git status --short --ignored` lists only `!! transcribe_audio/secrets/`. That is now a risk (A13, G6).
  - `git stash list` shows two stashes: `stash@{0}` is the `-u` one (the two `generate_text` files), `stash@{1}` your `cli.py` edit. Exercise B6 shows how to read them back without conflicts.
- **If it fails.** "Your local changes would be overwritten": `git stash` or `git checkout -- .`. "Untracked working tree files would be overwritten": `git stash -u`, or move those files out of the repo.

**A3. The folder layout: `secrets/` beside the repo** (`README.md:105-119`).
- **Action** *(extra commands)*: from the repo, `cd ..` to your workspace, then create the folder (`mega-laptop/06-x-secrets-folder.txt`):
  ```text
  $ mkdir secrets; ls; ls -la secrets
  mega-pipeline
  secrets
  total 8
  drwxr-sr-x 2 student student 4096 Oct 14 00:34 .
  drwxrwsrwx 4 student student 4096 Oct 14 00:34 ..
  ```
  (The `s`/`w` bits on the folders come from the capture's setup, not from the tutorial.) The key goes in here in A6; in the capture it stayed empty.
- **Why there.** `docker-shell.sh` mounts `$(pwd)/../../secrets/` (`transcribe_audio/docker-shell.sh:9`): from `<workspace>/mega-pipeline/transcribe_audio`, up two levels is `<workspace>`, then `secrets/`. A `secrets/` folder inside the repo is never mounted.

**A4. Configure each `cli.py`** (`README.md:123-134`). In every component set `gcp_project`, `bucket_name`, `group_name`.
- **What ships** *(extra check)*, from the repo folder (`mega-laptop/07-x-cli-values.txt`, trimmed):
  ```text
  $ grep -n -E '^(gcp_project|bucket_name|group_name) *=' */cli.py
  generate_text/cli.py:16:gcp_project = "ac215-project"
  generate_text/cli.py:17:bucket_name = "mega-pipeline-bucket"
  generate_text/cli.py:20:group_name = "pavlos-advanced"  # This needs to be your Group name e.g: group-01, group-02, group-03, group-04, group-05, ...
  synthesis_audio/cli.py:14:gcp_project = "" #"ac215-project"
  …
  transcribe_audio/cli.py:21:group_name = "" #"pavlos-advanced"
  translate_text/cli.py:14:gcp_project = "ac215-project" #"ac215-project"
  translate_text/cli.py:15:bucket_name = "mega-pipeline-bucket"  #"mega-pipeline-bucket"
  translate_text/cli.py:18:group_name = "pavlos-advanced" #"pavlos-advanced"
  ```

  | File | Lines | Shipped values |
  |---|---|---|
  | `transcribe_audio/cli.py` | `:17-21` | `""` |
  | `synthesis_audio_en/cli.py` | `:14-18` | `""` |
  | `synthesis_audio/cli.py` | `:14-18` | `""` |
  | `generate_text/cli.py` | `:16-20` | **the course's values** `"ac215-project"`, `"mega-pipeline-bucket"`, `"pavlos-advanced"` |
  | `translate_text/cli.py` | `:14-18` | the same course values |

- **The edit.** In your editor; the capture set placeholders (`your-project-id`, `your-team-bucket`, and the README's example group `group-01`; type your own). `git diff cli.py` in `transcribe_audio/` (`mega-laptop/11-a-x-edit-cli.txt`, trimmed):
  ```text
  $ git diff cli.py
  …
  -gcp_project = "" #"ac215-project"
  -bucket_name = ""  #"mega-pipeline-bucket"
  +gcp_project = "your-project-id" #"ac215-project"
  +bucket_name = "your-team-bucket"  #"mega-pipeline-bucket"
   input_audios = "input_audios"
   text_prompts = "text_prompts"
  -group_name = "" #"pavlos-advanced"
  +group_name = "group-01" #"pavlos-advanced"
  …
  ```
- **Under the hood.** `assert group_name!="", "Update group name"` runs at import time (e.g. `transcribe_audio/cli.py:24`), so even `python cli.py --help` fails until you set it (captured in A9). In `generate_text` and `translate_text` the assert **passes with the course's values** (E2): forget those two files and the CLIs call the course's project and bucket, where your SA has no rights (a 403).
- **Optional, translate:** `target_language` is `"es"` in code (`translate_text/cli.py:64`) but the next stage uses a **French** voice (`synthesis_audio/cli.py:48-49`). Set it to `"fr"` to match the README's story (E3).

**A5. Your bucket** (`README.md:138-165`). The README describes the bucket and its prefixes but gives no command to create it or fill `input_audios/` (E5). In the console (*Cloud Storage → Buckets → Create*), or after `gcloud config set project` (A6):
```bash
gcloud storage buckets create gs://<your-bucket> --location=us-central1
gcloud storage cp input-01.mp3 gs://<your-bucket>/input_audios/
gcloud storage ls gs://<your-bucket>/input_audios/
```
*(extra, not captured: no Google account.)* Name the recording `input-<something>.mp3`: `--upload` and every later `--download` match only `input-*` (`transcribe_audio/cli.py:102`, `generate_text/cli.py:43`). The README's Appendix uploads to `input_audios/test.mp3` (`README.md:313`), which would be transcribed to `test.txt` and never uploaded.

**A6. Service account, key and APIs** (`README.md:169-203`).
1. *IAM & Admin → Service accounts* → create one (e.g. `mega-pipeline-sa`) → grant the four roles of §2 → *Keys → Add Key → Create new key* (JSON) → save it as `<your-workspace>/secrets/mega-pipeline.json` (`:175-183`). In the role picker, search **"Agent Platform User"**; "Vertex AI User" finds nothing (`:179`; the `generate_text` README still says "Vertex AI User", `generate_text/README.md:46`, E9).
2. Enable the five APIs, in the console (`:189`) or with `gcloud` (`:191-199`).
- **Under the hood.** A key file contains the SA's email, the project id and an RSA private key. google-auth signs a JWT with it and exchanges it for a short-lived access token.
- **The `gcloud` commands, as typed** (`gcloud-laptop/01-config-set-project.txt`, `02-…`, `03-…`; Google Cloud SDK 570.0.0, never logged in):
  ```text
  student@laptop:~$ gcloud config set project <your-project-id>
  -bash: syntax error near unexpected token `newline'
  ```
  ```text
  $ gcloud config set project your-project-id
  Updated property [core/project].
  ```
  ```text
  $ gcloud services enable \
    storage.googleapis.com \
    aiplatform.googleapis.com \
    speech.googleapis.com \
    texttospeech.googleapis.com \
    translate.googleapis.com
  ERROR: (gcloud.services.enable) You do not currently have an active account selected.
  Please run:

    $ gcloud auth login

  to obtain new credentials.
  …
  ```
  - The first is the shell, not gcloud: `<` and `>` are redirections, so the placeholder must be replaced, brackets and all (zsh on a Mac says `zsh: parse error near '\n'`). `gcloud config set project` only stores a setting; it doesn't check that the project exists.
  - The last is what you see when Tutorial 0's `gcloud auth login` was skipped. `gcloud auth list` *(extra)* says `No credentialed accounts.` (`04-x-auth-list.txt`). Signed in, the command enables the five services; the tutorial documents no output.
- **Checkpoint.** `gcloud services list --enabled` *(extra)* includes the five services, and `grep client_email <your-workspace>/secrets/mega-pipeline.json` *(extra)* shows `…@<your-project>.iam.gserviceaccount.com` (neither captured: no account, no key).
- **If it fails later.** A 403 that says a service is disabled means the API isn't enabled; a 403 about a permission means a role is missing. "Enabling the API and granting the role are two separate steps." (`:187`) Changes can take a few minutes to apply.

**A7. How to Run a Component, with Task A: `transcribe_audio`** (`README.md:207-226`; `transcribe_audio/README.md`; Quick Reference `README.md:234-240`).
```bash
cd transcribe_audio
./docker-shell.sh          # build the image locally and run it (default)
```
- **What you see** (`mega-laptop/12-a-docker-shell.txt`, trimmed; the full build log, 1,473 lines, is `12-a-docker-shell.plain.txt`):
  ```text
  $ ./docker-shell.sh
  Docker Username: dlops, Build Mode: dev-run
  Building development image locally...
  [+] Building 99.5s (10/10) FINISHED                              docker:default
   => [internal] load build definition from Dockerfile                       0.0s
  …
   => [2/5] RUN set -ex;     for i in $(seq 1 8); do mkdir -p "/usr/share/  44.7s
   => [3/5] WORKDIR /app                                                     0.1s
   => [4/5] COPY --chown=app:app . ./                                        0.0s
   => [5/5] RUN uv sync                                                      1.6s
   => exporting to image                                                    52.9s
  …
   => => naming to docker.io/library/mega-pipeline-transcribe-audio:latest   0.0s
  …
  Run Docker container...
  Using local image...
  app@0ceffb272288:/app$ python cli.py --help
  usage: cli.py [-h] [-d] [-t] [-u]

  Transcribe audio file to text

  options:
    -h, --help        show this help message and exit
    -d, --download    Download audio files from GCS bucket
    -t, --transcribe  Transcribe audio files to text
    -u, --upload      Upload transcribed text to GCS bucket
  app@0ceffb272288:/app$ exit
  exit
  ```
- **Under the hood.**
  1. The script prints its mode (`docker-shell.sh:48`), builds `mega-pipeline-transcribe-audio` from `Dockerfile` with the component folder as the build context (`:75`), then prints `Run Docker container...` and `Using local image...` (`:80`, `:84`).
  2. Build step 2 is the slow one: apt installs `build-essential ffmpeg` (245 packages, 205 MB to download), then `pip install --upgrade pip` (pip 26.2.1 was already the newest) and `pip install uv` (uv 0.13.0), with pip's harmless "Running pip as the 'root' user" warning. Step 5 is `uv sync`: `Using CPython 3.14.8 interpreter at: /usr/local/bin/python3`, `Creating virtual environment at: /home/app/.venv`, `Installed 26 packages` (`12-a-docker-shell.plain.txt:1427-1435`).
  3. It runs `docker run --rm --name mega-pipeline-transcribe-audio -ti -v "$BASE_DIR":/app -v "$SECRETS_DIR":/secrets -e GOOGLE_APPLICATION_CREDENTIALS=… mega-pipeline-transcribe-audio` (`:92-96`).
  4. ENTRYPOINT/CMD start `bash -c "source /home/app/.venv/bin/activate && exec bash"` (`Dockerfile:44-46`): an interactive shell with the venv on `PATH`. The prompt shows no `(app)` prefix; `which python` proves the venv is active.
- **Look around** *(extra; a second terminal for `docker ps`/`docker inspect`, the container's own prompt for the rest)*. Captured (`13-a-x-docker-ps.txt`, `14-a-x-mounts.txt`, `mega-transcribe_audio/02-x-whoami.txt` … `08-x-venv.txt`):
  ```text
  $ docker ps
  CONTAINER ID   IMAGE                            COMMAND                  CREATED          STATUS         PORTS     NAMES
  0ceffb272288   mega-pipeline-transcribe-audio   "/bin/bash -c 'sourc…"   10 seconds ago   Up 8 seconds             mega-pipeline-transcribe-audio
  $ docker inspect --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' mega-pipeline-transcribe-audio
  /home/student/AC215/mega-pipeline/transcribe_audio -> /app
  /home/student/AC215/secrets -> /secrets
  ```
  ```text
  $ whoami; id
  app
  uid=1000(app) gid=1000(app) groups=1000(app)
  $ which python
  /home/app/.venv/bin/python
  $ python --version
  Python 3.14.8
  $ echo $GOOGLE_APPLICATION_CREDENTIALS
  /secrets/mega-pipeline.json
  $ ls -la /secrets
  total 8
  drwxr-sr-x 2 app  app  4096 Oct 14 00:34 .
  drwxr-xr-x 1 root root 4096 Oct 14 00:36 ..
  $ echo $VIRTUAL_ENV; ls /home/app/.venv; uv --version
  /home/app/.venv
  CACHEDIR.TAG
  bin
  lib
  lib64
  pyvenv.cfg
  uv 0.13.0 (x86_64-unknown-linux-gnu)
  ```
  The container is named like the image (`--name $IMAGE_NAME`), `/app` is your laptop's folder, and the venv lives outside it. `/secrets` is empty here because the capture had no key; **yours must list `mega-pipeline.json`**.
- **Python packages** (`transcribe_audio/README.md:79-89`): already in `pyproject.toml` and `uv.lock`; to add one, `uv add <package>` inside, commit both files, then `./docker-shell.sh dev` (C3, Exercise B5).
- **The CLI** (`transcribe_audio/README.md:98`; Quick Reference `README.md:236-240`):
  ```bash
  python cli.py --download
  python cli.py --transcribe
  python cli.py --upload
  ```
  (the component README writes `python cli.py -d`, `-t`, `-u`, `:115-117`).
  - `--download` wipes local `input_audios/` and pulls every object under `input_audios/` (`cli.py:32-46`). This prefix is shared and not scoped by group.
  - `--transcribe` converts each mp3 to FLAC with ffmpeg (which is why this Dockerfile alone installs `ffmpeg`, `Dockerfile:4`), calls `long_running_recognize` with a 90 s timeout, keeps only `response.results[0]`, and writes `text_prompts/<group>/<name>.txt` (`cli.py:49-90`). Existing outputs are skipped (`:64-65`).
  - `--upload` pushes `text_prompts/<group>/input-*.txt` (`cli.py:93-109`).
- **What the capture got, without a key** (`mega-transcribe_audio/09-download.txt`, trimmed; exit 1):
  ```text
  $ python cli.py --download
  Args: Namespace(download=True, transcribe=False, upload=False)
  download
  Traceback (most recent call last):
    File "/app/cli.py", line 148, in <module>
      main(args)
  …
    File "/app/cli.py", line 39, in download
      client = storage.Client()
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.
  ```
  This is exactly what a missing or misplaced key looks like (G3): it fails at `storage.Client()` (`cli.py:39`), before `get_bucket` (`:40`) sends anything. `makedirs()` had already run, so `input_audios/` and `text_prompts/group-01/` exist, empty (`12-x-ls-after.txt`). `--transcribe` and `--upload` stop the same way without a key (at `speech.SpeechClient()`, `:54`, and `storage.Client()`, `:98`; run, output not kept).
- **Checkpoint (with your key).** `--download` prints the object names it fetched (`print(blob.name)`, `:44`); `--transcribe` prints `Transcribing: input_audios/input-….mp3`, the API response and the transcript; `--upload` prints `Uploading: text_prompts/<group>/input-….txt …`. Then the console shows `text_prompts/<group_name>/input-*.txt` in your bucket (`transcribe_audio/README.md:120`).
- **Back on the laptop** *(extra)* after `exit` (`mega-laptop/16-a-x-host-after.txt`): `ls` lists `input_audios` and `text_prompts` in the component folder (made through the mount), and `git status --short --ignored .` shows only ` M cli.py`: the folders are ignored (`transcribe_audio/.gitignore:5-6`) and empty.
- **The other modes on the same folder** (`README.md:213-214`):
  ```text
  $ ./docker-shell.sh dev
  Docker Username: dlops, Build Mode: dev
  Building development image locally...
  [+] Building 0.3s (10/10) FINISHED                               docker:default
  …
   => CACHED [4/5] COPY --chown=app:app . ./                                 0.0s
   => CACHED [5/5] RUN uv sync                                               0.0s
  …
  ```
  ```text
  $ ./docker-shell.sh run
  Docker Username: dlops, Build Mode: run
  Run Docker container...
  Using local image...
  app@631fac50f92b:/app$ exit
  exit
  ```
  (`17-a-dev.txt`, `18-a-run-local.txt`.) `dev` builds and stops; everything came from the cache. If anything in the folder changed since the last build (an edited `cli.py`, downloaded data), `COPY` and `uv sync` run again. `run` skips the build and uses the local image (A12 shows the registry case).
- **`chmod +x docker-shell.sh`** (`README.md:220-224`): `ls -l docker-shell.sh` shows `-rwxr-xr-x` already, and `chmod` prints nothing (`19-a-x-ls-l-script.txt`, `20-a-chmod.txt`). Needed only if the executable bit got lost (E12).
- **Image size** *(extra)*: `docker images` lists `mega-pipeline-transcribe-audio:latest` at `1.48GB` disk usage (`386MB` content) and the base `python:3.14-slim-bookworm` at `195MB` (`21-a-x-images.txt`).
- **If it fails.**

  | Error | Cause | Fix |
  |---|---|---|
  | `AssertionError: Update group name` | `group_name` not set | set it (A4) |
  | `google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.` | key not at `../../secrets/mega-pipeline.json` from the component folder | G3 |
  | a 403 naming `storage.buckets.get` | `get_bucket` (`cli.py:40`) needs a bucket-level permission that "Storage Object Admin" lacks | grant Storage Admin, as the README says |
  | `Conflict. The container name "/mega-pipeline-transcribe-audio" is already in use` | a second terminal ran the script while the first container still runs | G9 |
  | `PermissionError: [Errno 13] Permission denied: 'input_audios'` | Linux host whose user isn't uid 1000 | G10 |

**A8. Task B: `generate_text`** (`generate_text/README.md`; Quick Reference `README.md:242-248`).
```bash
cd ../generate_text
./docker-shell.sh
```
- **What you see** (`mega-laptop/31-b-docker-shell.txt`, trimmed): `Building 52.6s`, with a new apt layer for `build-essential` only (54 packages, 74.5 MB to download), `uv sync` installing 34 packages, then `app@45263bb6ca36:/app$`. `python cli.py --help` (`generate_text/README.md:114`) printed the README's block exactly (`mega-generate_text/01-help.txt`):
  ```text
  $ python cli.py --help
  usage: cli.py [-h] [-d] [-g] [-u]

  Generate text from prompt

  options:
    -h, --help      show this help message and exit
    -d, --download  Download text prompts from GCS bucket
    -g, --generate  Generate a text paragraph
    -u, --upload    Upload paragraph text to GCS bucket
  ```
  It works without a key: `genai.Client(vertexai=True, project=gcp_project, location="us-central1")` is created at import (`cli.py:25`), but asks for credentials only on a request.
- **The CLI** (`README.md:244-248`; `generate_text/README.md:131-133` as `-d`, `-g`, `-u`):
  ```bash
  python cli.py --download
  python cli.py --generate
  python cli.py --upload
  ```
  - `--download` lists `text_prompts/<group>/input-*.txt` with `match_glob` (`cli.py:43`) and downloads them.
  - `--generate` builds a cheese-podcast prompt (`:65-72`) and calls `client.models.generate_content(model=model_name, ...)` (`:75-77`), with `model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")` (`:73`).
- **What the capture got, without a key** (`mega-generate_text/02-download.txt`, `03-generate.txt`):
  ```text
  $ python cli.py --download
  Args: Namespace(download=True, generate=False, upload=False)
  download
  Traceback (most recent call last):
  …
    File "/app/cli.py", line 41, in download
      storage_client = storage.Client(project=gcp_project)
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.
  ```
  ```text
  $ python cli.py --generate
  Args: Namespace(download=False, generate=True, upload=False)
  generate
  ```
  The second exits 0 and does nothing: no prompts were downloaded, so the loop over `text_prompts/<group>/input-*.txt` (`cli.py:53-54`) is empty and Gemini is never called. A silent "success" like this means: check `ls text_prompts/<group>` before you trust it.
- **Optional model switch** (`generate_text/README.md:89-94`):
  ```bash
  export GEMINI_MODEL=gemini-2.5-flash
  python cli.py --generate
  ```
  Captured: the same silent no-op (`05-gemini-model.txt`), for the same reason. The variable lives only in this container's shell; Exercise D2 (c) shows how to pass it from `docker-shell.sh` with `-e`.
- **Checkpoint (with your key).** `--generate` prints the prompt and then a long "Generated text:"; after `--upload`, `text_paragraphs/<group>/` in the bucket (`generate_text/README.md:136`).
- **If it fails.**
  - A 403 mentioning project `ac215-project`: you kept the shipped values (E2).
  - A 404 / model not found: set `GEMINI_MODEL` to a model your project can use (Q3).
  - A 403 with your own project: the Agent Platform User role is missing or `aiplatform.googleapis.com` is not enabled.

**A9. Task C: `synthesis_audio_en`** (`synthesis_audio_en/README.md`; Quick Reference `README.md:250-257`).
```bash
cd ../synthesis_audio_en
./docker-shell.sh
```
- **What you see** (`mega-laptop/40-c-docker-shell.txt`, trimmed): `Building 8.2s`, because `CACHED [2/5]`: the four non-transcribe Dockerfiles are identical up to that line, so B's apt layer is reused. The capture then typed `python cli.py --help` **before** editing this `cli.py`:
  ```text
  app@ba0b1df0eadc:/app$ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 19, in <module>
      assert group_name!="", "Update group name"
             ^^^^^^^^^^^^^^
  AssertionError: Update group name
  ```
  The edit was then made on the laptop while the container ran (`41-c-x-edit-cli.txt`), and through the `/app` mount the next `--help` saw it at once; without a key it now fails one line later, at import (`mega-synthesis_audio_en/02-help.txt`, trimmed):
  ```text
  $ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 23, in <module>
      client = texttospeech.TextToSpeechLongAudioSynthesizeClient()
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.
  ```
  With the key in place, `--help` prints the README's block (*expected*, `synthesis_audio_en/README.md:99-107`): `usage: cli.py [-h] [-d] [-s]`, "Synthesis audio from text", `-d, --download  Download paragraph of text from GCS bucket`, `-s, --synthesis  Synthesis audio`.
- **The CLI** (`README.md:252-255`; `synthesis_audio_en/README.md:115-116` as `-d`, `-s`):
  ```bash
  python cli.py --download
  python cli.py --synthesis
  ```
  Without a key both fail at the same import line (`03-download.txt`; `--synthesis` run, output not kept).
- **Under the hood.** For each paragraph whose output blob does not exist yet (`cli.py:70`), the code sends `SynthesizeLongAudioRequest(parent=f"projects/{gcp_project}/locations/us-central1", ..., output_gcs_uri=f"gs://{bucket_name}/{audio_blob_name}")` and waits up to 300 s (`:78-91`). Google's service writes the audio **directly into the bucket**, so there is no `--upload` (`README.md:257`).
- **Checkpoint (with your key).** `Audio file will be saved to GCS bucket automatically.` (`:92`), then `text_audios/<group>/input-*.mp3` in the bucket. The README says to give it a moment (`synthesis_audio_en/README.md:121`), but the CLI already blocks on `operation.result(timeout=300)` (`:91`) before printing that line, so the object should normally be there once it prints.
- **If it fails.** An empty `gcp_project` produces the resource name `projects//locations/us-central1` (an invalid-argument error). A permission error on the output URI means the SA cannot write to the bucket.

**A10. Task D: `translate_text`** (`translate_text/README.md`; Quick Reference `README.md:259-265`).
```bash
cd ../translate_text
./docker-shell.sh
```
- **What you see** (`mega-laptop/51-d-docker-shell.txt`, trimmed): `Building 7.9s` (apt layer cached), 25 packages, then at the prompt even `--help` fails without a key:
  ```text
  app@40d7497c50f2:/app$ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 22, in <module>
      translate_client = translate.Client()
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json
   was not found.
  ```
  (The line break inside the last line is the 80-column terminal.) With the key: the README's block (*expected*, `translate_text/README.md:114-123`), whose description still says "Translate English to French" (E3).
- **The CLI** (`README.md:261-265`; `translate_text/README.md:131-133` as `-d`, `-t`, `-u`):
  ```bash
  python cli.py --download
  python cli.py --translate
  python cli.py --upload
  ```
  Without a key: the same import-time error (`mega-translate_text/02-download.txt`).
- **Under the hood.** `translate.Client()` (the Translation **v2 / Basic** client, `translate_text/cli.py:9`, `:22`) calls `translate(input_text, source_language="en", target_language="es", format_="text")` (`:61-66`). Re-runs print `Translated file already exists.` (`:55`).
- **Checkpoint (with your key).** `--translate` prints each translation; after `--upload`, `text_translated/<group>/` in the bucket (`translate_text/README.md:136`). The text is **Spanish** unless you changed `target_language` (E3).
- **If it fails.** A 403 on Translation: the role `roles/cloudtranslate.user` or the API is missing.

**A11. Task E: `synthesis_audio`** (`synthesis_audio/README.md`; Quick Reference `README.md:267-274`).
```bash
cd ../synthesis_audio
./docker-shell.sh
```
- **What you see** (`mega-laptop/61-e-docker-shell.txt`): `Building 7.9s`, 24 packages; `--help` fails at import without a key, at `client = texttospeech.TextToSpeechLongAudioSynthesizeClient()` (`cli.py:22`), with the same `DefaultCredentialsError` (`mega-synthesis_audio/01-help.txt`, `02-download.txt`). With the key: the README's block (*expected*, `synthesis_audio/README.md:99-107`).
- **The CLI** (`README.md:269-272`; `synthesis_audio/README.md:115-116` as `-d`, `-s`):
  ```bash
  python cli.py --download
  python cli.py --synthesis
  ```
- **Under the hood.** Same as A9, but it reads `text_translated/<group>/` and uses voice `fr-FR` / `fr-FR-Standard-C` (`synthesis_audio/cli.py:48-49`), writing `output_audios/<group>/input-*.mp3` (`:66`, `:78`).
- **Checkpoint (with your key).** `output_audios/<group>/` in the bucket: "the final output of the pipeline" (`synthesis_audio/README.md:119`). A French voice reading Spanish text means you hit E3.
- **Bonus: ElevenLabs** (`synthesis_audio/README.md:125-135`). `cli_11.py` reads its key file at import, relative to `/app` (`cli_11.py:30-33`), and hard-codes `mega-pipeline-bucket` / `pavlos` (`:15-19`). Captured without it (`mega-synthesis_audio/04-x-cli11-help.txt`):
  ```text
  $ python cli_11.py --help
  Traceback (most recent call last):
    File "/app/cli_11.py", line 33, in <module>
      with open(secrets_file_path) as f:
           ~~~~^^^^^^^^^^^^^^^^^^^
  FileNotFoundError: [Errno 2] No such file or directory: 'secrets/11lab_api_key.txt'
  ```
  See E10 before trying it.

**A12. `run` without a local image, and `prod`** (`README.md:213-216`; each component README's "OPTIONAL: Publish the container", e.g. `transcribe_audio/README.md:124-132`).
- **`run` on a laptop that never built the image** *(the README command; the `docker image rm` before it is extra and stands in for a teammate who never built it)*. Captured (`mega-laptop/71-x-rm-local-image.txt`, `72-run-registry.txt`, trimmed):
  ```text
  $ docker image rm mega-pipeline-transcribe-audio
  Untagged: mega-pipeline-transcribe-audio:latest
  …
  $ ./docker-shell.sh run
  Docker Username: dlops, Build Mode: run
  Run Docker container...
  Local image not found, using image from registry...
  Unable to find image 'dlops/mega-pipeline-transcribe-audio:latest' locally
  latest: Pulling from dlops/mega-pipeline-transcribe-audio
  3db44566b15f: Pull complete
  …
  Status: Downloaded newer image for dlops/mega-pipeline-transcribe-audio:latest
  Creating a Pipfile for this project...
  Launching subshell in virtual environment...
  root@36615ab6e34b:/app#  source /root/.local/share/virtualenvs/app-4PlAip0Q/bin/
  activate
  (app) root@36615ab6e34b:/app# python --version
  Python 3.8.17
  (app) root@36615ab6e34b:/app# which python
  /root/.local/share/virtualenvs/app-4PlAip0Q/bin/python
  (app) root@36615ab6e34b:/app# python cli.py --help
  usage: cli.py [-h] [-d] [-t] [-u]
  …
  optional arguments:
  …
  (app) root@36615ab6e34b:/app# exit
  ```
  - The image (`74-x-registry-image.txt`): created `2025-02-18T21:04:17…`, `PYTHON_VERSION=3.8.17`, `GOOGLE_APPLICATION_CREDENTIALS=../secrets/mega-pipeline.json`, `cmd ["-c","pipenv shell"]`, `user ""` (root), 1.17 GB. It was built from the `pipenv-flexible-workflow` branch (`FROM python:3.8-slim-buster`, `pipenv sync`), not from this branch (E1).
  - Your folder is mounted over its `/app`, which has no `Pipfile`, so pipenv **creates one in your folder, as root** (`73-x-host-after-registry.txt`: `-rw-r--r-- 1 root student 138 … Pipfile`, and `git status` shows `?? Pipfile`). `rm Pipfile` removes it (the folder is yours).
  - Transcribe's `--help` still works on the old image (Python 3.8's argparse says `optional arguments:`). In `generate_text` the same experiment fails (`75-…`, `76-run-registry-b.txt`, trimmed; Python 3.8.17 again):
    ```text
    (app) root@b7bf0236578c:/app# python cli.py --help
    Traceback (most recent call last):
      File "cli.py", line 11, in <module>
        from google import genai
    ImportError: cannot import name 'genai' from 'google' (unknown location)
    ```
    The 2025 image installs `google-generativeai`, not `google-genai` (`pipenv-flexible-workflow:generate_text/Pipfile`).
  - `docker run` pulls a tag only when it's missing locally, so later `run`s keep reusing this cached `latest` until you pull again or remove it (E18).
- **`prod`** (not captured: it needs `docker login` and push rights, and it publishes):
  ```bash
  docker login -u <USER NAME> -p <ACCESS TOKEN>
  ./docker-shell.sh prod     # build multi-arch (amd64 + arm64) and push to DockerHub
  ```
  First edit `DOCKER_USERNAME` (`docker-shell.sh:13`) and add a `.dockerignore` (G6). The script removes and recreates the `multi-arch` builder, then runs `docker buildx build --platform linux/amd64,linux/arm64 --push -t $DOCKER_USERNAME/$IMAGE_NAME -f Dockerfile .` (`:55-66`); it never runs a container. **Checkpoint:** `Production build complete and pushed to registry` (`:68`), and the tag on Docker Hub lists two platforms. **If it fails:** pushing to `dlops/...` without membership fails with an authorization error ("requested access to the resource is denied" or similar); the amd64 half is slow on Apple Silicon (QEMU). Afterwards `docker buildx ls` shows `multi-arch*` as the current builder (G8).

**A13. The old key and the image; clean up.**
- **The L03 key, built in** *(extra)*. In the switched L03 clone of A2, `transcribe_audio/secrets/mega-pipeline.json` was still there. `./docker-shell.sh dev` built the image from that folder (`mega-l03-laptop/12-x-dev-old-key.txt`: `[4/5] COPY --chown=app:app . ./` not cached, `Building 20.9s`), and the key file was then **inside** the image (`13-x-key-in-image.txt`, trimmed; a 79-byte stand-in file, not a key):
  ```text
  $ docker run --rm --entrypoint ls mega-pipeline-transcribe-audio -la /app /app/secrets
  /app:
  …
  drwxr-sr-x 2 app  app   4096 Oct 14 00:40 secrets
  -rw-r--r-- 1 app  app  85761 Oct 14 00:40 uv.lock

  /app/secrets:
  total 12
  drwxr-sr-x 2 app app 4096 Oct 14 00:40 .
  drwxr-xr-x 1 app app 4096 Oct 14 00:40 ..
  -rw-rw-rw- 1 app app   79 Oct 14 00:40 mega-pipeline.json
  ```
  `COPY --chown=app:app . ./` (`Dockerfile:39`) copies the whole build context, and no branch has a `.dockerignore`; `prod` would push this layer to a public repository. Delete the in-component `secrets/` and add a `.dockerignore` (G6; Exercise Q3 checks the fix).
- **What's on disk** *(extra)* (`mega-laptop/70-x-images.txt`, `78-x-images-all.txt`): the five local images (transcribe `1.48GB`, generate `821MB`, synthesis-audio-en and synthesis-audio `833MB`, translate `836MB`) and, after the `run` experiments, `dlops/mega-pipeline-transcribe-audio` (`1.17GB`) and `dlops/mega-pipeline-generate-text` (`1.02GB`). `git status --short --ignored` in the repo (`79-x-git-status-all.txt`): five ` M …/cli.py` and two `?? …/Pipfile`.
- **Clean up.** Type `exit` in each container shell (`--rm` deletes the container), then follow the teardown list in "At a glance" and §2.

### Part B — port_toy

**B1. Check Docker, get the code** (`port_toy/README.md:28-30`, `:81-85`).
```bash
docker run hello-world
```
Captured (`port-laptop/01-hello-world.txt`, trimmed):
```text
$ docker run hello-world
Unable to find image 'hello-world:latest' locally
latest: Pulling from library/hello-world
…
Status: Downloaded newer image for hello-world:latest

Hello from Docker!
This message shows that your installation appears to be working correctly.
…
```
The README says only "Clone or download the [repository](https://github.com/dlops-io/port_toy)" (`:81`); the usual clone command *(extra)* is `git clone https://github.com/dlops-io/port_toy.git` (captured: `Cloning into 'port_toy'...`). Then:
```bash
cd port_toy
```
- **Checkpoint** *(extra)* (`04-ls.txt`): `ls -a` shows `.gitignore README.md browser-gateway-processor.png docker-compose.yml gateway processor`; `gateway/` holds `Dockerfile gateway.py index.html`, `processor/` holds `Dockerfile processor.py`; `git log --oneline -1` says `d190c71 gateway: show the real host port in the diagram`.

**B2. Create the network** (`port_toy/README.md:91-93`).
```bash
docker network create toynet
```
Captured (`05-network-create.txt`, `06-network-ls.txt`): the command prints the new network's id; `docker network ls` *(extra)* then lists it next to Docker's three built-in networks:
```text
$ docker network ls
NETWORK ID     NAME      DRIVER    SCOPE
6dc501e6db46   bridge    bridge    local
2423b89bf480   host      host      local
8ed9d78f7e8c   none      null      local
cedc0ad9fdee   toynet    bridge    local
```
- **Under the hood.** A user-defined bridge with its own subnet and DNS (C6).
- **If it fails.** "network with name toynet already exists": a previous run was not cleaned up. `docker network rm toynet` (after removing the containers on it).

**B3. Build both images** (`port_toy/README.md:99-102`).
```bash
docker build -t toy-processor ./processor
docker build -t toy-gateway ./gateway
```
Captured (`07-build-processor.txt`, `08-build-gateway.txt`, trimmed):
```text
$ docker build -t toy-processor ./processor

[+] Building 7.5s (9/9) FINISHED                                 docker:default
…
 => [2/4] RUN apt-get update && apt-get install -y --no-install-recommend  6.4s
 => [3/4] WORKDIR /app                                                     0.0s
 => [4/4] COPY . .                                                         0.0s
…
 => => naming to docker.io/library/toy-processor:latest                    0.0s
$ docker build -t toy-gateway ./gateway

[+] Building 0.3s (9/9) FINISHED                                 docker:default
…
 => CACHED [2/4] RUN apt-get update && apt-get install -y --no-install-re  0.0s
 => CACHED [3/4] WORKDIR /app                                              0.0s
 => [4/4] COPY . .                                                         0.0s
…
```
- **Under the hood.** Each Dockerfile (`port_toy/processor/Dockerfile:1-5`, `port_toy/gateway/Dockerfile:1-5`) starts from `python:3.14-slim`, apt-installs `curl`, copies the folder to `/app` and sets `CMD ["python", "-u", "<file>.py"]`. The two files are identical up to `COPY`, so the second build reuses the first one's apt layer (`CACHED`). `-u` turns off output buffering so `docker logs` shows prints immediately, the same job `ENV PYTHONUNBUFFERED=1` does in mega-pipeline (`Dockerfile:13`).
- **Checkpoint** *(extra)* (`09-images.txt`):
  ```text
  $ docker image ls 'toy-*'
  IMAGE                  ID             DISK USAGE   CONTENT SIZE   EXTRA
  toy-gateway:latest     efc8b3084509        198MB         48.8MB
  toy-processor:latest   8221f0ec3dfe        198MB         48.8MB
  ```
  Quote the pattern so the shell doesn't expand it. "Disk usage" counts the shared base layers in every row; together the two take about 200 MB.

**B4. Start the processor, unpublished** (`port_toy/README.md:108-111`).
```bash
docker run -d --name processor --network toynet \
  -e PORT=9200 toy-processor
```
- **Under the hood.** `-d` runs it detached and prints the container id (`10-run-processor.txt`). `processor.py:42-44` reads `PORT`, binds `("", 9200)` and prints its banner.

**B5. Start the gateway, published** (`port_toy/README.md:119-125`).
```bash
docker run -d --name gateway --network toynet \
  -p 127.0.0.1:8090:9100 \
  -e PROCESSOR_HOST=processor \
  -e PROCESSOR_PORT=9200 \
  toy-gateway
```
- **Under the hood.** `gateway.py:13-14` reads the processor's address from the environment (the values in quotes there, `"processor"` and `"9200"`, are only defaults). `:51-53` binds `("", 9100)` (the `PORT` default). Docker forwards host `127.0.0.1:8090` → container `9100`.
- **If it fails.** `Bind for 127.0.0.1:8090 failed: port is already allocated`: something else uses 8090. Pick another host port (Step 3 shows how).

**B6. Read the logs** (`port_toy/README.md:131-134`).
```bash
docker logs processor
docker logs gateway
```
Captured (`12-logs-processor.txt`, `13-logs-gateway.txt`):
```text
$ docker logs processor
processor listening on port 9200 (internal only)
$ docker logs gateway
gateway listening on port 9100  →  open http://localhost:8090
```
The README's sample (*expected*, `README.md:139-140`) has one space on each side of the arrow; the code prints two (`gateway.py:53`).

**B7. Send a message** (`port_toy/README.md:145-157`). Open http://localhost:8090, type, click **Send**.
- **Under the hood.**
  1. `do_GET` serves `index.html` (`gateway.py:18-25`).
  2. The page sends `fetch("/", {method: "POST", ... JSON.stringify({ text: text })})` (`index.html:95-99`).
  3. The gateway opens `HTTPConnection(PROCESSOR_HOST, PROCESSOR_PORT)` (`gateway.py:33`), reads its own source port (`:38`), and forwards.
  4. The processor upper-cases the text and reports `listen_port` and `sender_port` (`processor.py:29-33`).
  5. The page reads the host port from its own address bar (`index.html:86-89`).
- **Captured** (`14-send.txt`, `15-send-again.txt`; curl standing in for the page):
  ```text
  $ curl -sS -X POST http://localhost:8090 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'
  {"upper": "HELLO FROM THE LAPTOP", "listen_port": 9200, "sender_port": 55620, "gateway_out_port": 55620}
  $ curl -sS -X POST http://localhost:8090 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'
  {"upper": "HELLO FROM THE LAPTOP", "listen_port": 9200, "sender_port": 55634, "gateway_out_port": 55634}
  ```
  The page turns that into its port card; the README's own example (*expected*, `README.md:154-156`):
  ```text
  gateway sent from port          44456
  processor listening on port      9200
  processor saw it arrive from     44456
  ```
- **Checkpoint.** The text in capitals, and three port lines in which the first and third numbers match and the second is `9200`. The matching number is an ephemeral source port: a new one on each send (55620, then 55634).

**B8. Read the PORTS column** (`port_toy/README.md:197-199`).
```bash
docker ps
```
Captured (`16-ps.txt`):
```text
$ docker ps
CONTAINER ID   IMAGE           COMMAND                  CREATED        STATUS        PORTS                      NAMES
3bf0f65d0cf0   toy-gateway     "python -u gateway.py"   1 second ago   Up 1 second   127.0.0.1:8090->9100/tcp   gateway
51cca10de63c   toy-processor   "python -u processor…"   1 second ago   Up 1 second                              processor
```
The processor's PORTS cell is empty: neither `-p` nor `EXPOSE` (`README.md:211`). The README's three-column sample (`:203-207`) matches `docker ps --format 'table {{.Image}}\t{{.Ports}}\t{{.Names}}'` *(extra)*, `17-ps-short.txt`.
- **What `127.0.0.1` does** *(extra; the README's `-p 8090:9100`, `:238-240`, in a full command)* (`18-x-all-addresses-taken.txt` … `21-x-ps-all-addresses.txt`, trimmed):
  ```text
  $ docker run -d --name gateway-all --network toynet -p 8090:9100 toy-gateway
  ef2a04bcf5166a6af8c998e9d189fdab2b7ca785d087d9a880a29d3adb38acdb
  docker: Error response from daemon: failed to set up container networking: driver failed programming external connectivity on endpoint gateway-all (…): Bind for 127.0.0.1:8090 failed: port is already allocated
  …
  $ docker rm gateway-all
  gateway-all
  $ docker run -d --name gateway-all --network toynet -p 8091:9100 toy-gateway
  …
  $ docker ps --format 'table {{.Image}}\t{{.Ports}}\t{{.Names}}'; docker rm -f gateway-all
  IMAGE           PORTS                      NAMES
  toy-gateway     0.0.0.0:8091->9100/tcp     gateway-all
  toy-gateway     127.0.0.1:8090->9100/tcp   gateway
  toy-processor                              processor
  gateway-all
  ```
  Without an address, `-p` claims the host port on every address, so it collided with the gateway's `127.0.0.1:8090` (exit 125; the container was created anyway and had to be removed). On 8091 it started, published on `0.0.0.0`: all of the laptop's IPv4 addresses, so other machines on your network may connect. (On a host with IPv6, the cell may also list `[::]:8091->9100/tcp`.)

**B9. Probe from the laptop** (`port_toy/README.md:250-252`, `:258-260`).
```bash
curl http://localhost:8090
```
```bash
curl --max-time 3 http://localhost:9200/health
```
Captured (`22-curl-8090.txt`, trimmed; `23-curl-9200.txt`):
```text
$ curl http://localhost:8090
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
…
</body>
</html>
$ curl --max-time 3 http://localhost:9200/health
curl: (7) Failed to connect to localhost:9200 after 0 ms: Could not connect to server
```
- **Checkpoint.** The first returns the gateway's HTML; the second fails (exit 7), "assuming nothing else is using port 9200" (`:262`). If it succeeds, see G14.

**B10. Probe from inside the gateway** (`port_toy/README.md:272-274`, `:284-286`).
```bash
docker exec gateway curl http://processor:9200/health
```
```bash
docker exec gateway curl --max-time 3 http://localhost:9200/health
```
Captured (`24-exec-processor.txt`, `25-exec-localhost.txt`):
```text
$ docker exec gateway curl http://processor:9200/health
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100     2    0     2    0     0    766      0 --:--:-- --:--:-- --:--:--  1000
ok
$ docker exec gateway curl --max-time 3 http://localhost:9200/health
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
curl: (7) Failed to connect to localhost port 9200 after 0 ms: Could not connect
 to server
```
- **Under the hood.** `docker exec` starts a second process in the gateway's namespaces. Without a terminal (`-t`), curl shows its progress meter (on stderr) above the answer. `processor` resolves through Docker's DNS; `localhost` is the gateway's own loopback, where nothing listens on 9200. The processor sends `ok` without a trailing newline (`processor.py:20`).
- **More checks** *(extra)* (`26-…` to `29-x-dns.txt`):
  ```text
  $ docker exec gateway curl -s http://localhost:9100 | head -4
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
  $ docker exec processor curl --version | head -1
  curl 8.14.1 (x86_64-pc-linux-gnu) libcurl/8.14.1 OpenSSL/3.5.7 …
  $ docker exec gateway cat /etc/resolv.conf; docker exec gateway getent hosts processor gateway
  # Generated by Docker Engine.
  …
  nameserver 127.0.0.11
  …
  172.19.0.2      processor
  172.19.0.3      gateway
  ```
  On 9100, the gateway's own port, `localhost` *is* the gateway. The processor image has curl too, although `README.md:294` implies it doesn't (E14). `127.0.0.11` is Docker's embedded DNS; `docker network inspect toynet` (a *Handy command*, `README.md:576`; `28-network-inspect.txt`) shows the same: `"Subnet": "172.19.0.0/16"`, gateway `172.19.0.3/16`, processor `172.19.0.2/16`.
- **An interactive shell** (*Handy commands*, `README.md:566`; `29b-exec-it-sh.txt`):
  ```text
  $ docker exec -it gateway sh
  # hostname
  3bf0f65d0cf0
  # ls
  Dockerfile  gateway.py  index.html
  # exit
  ```
  The `#` prompt: the toy images run as root (no `USER` line), unlike mega-pipeline's `app` user.

**B11. Change the host port** (`port_toy/README.md:339-341`, `:345-351`).
```bash
docker rm -f gateway
```
```bash
docker run -d --name gateway --network toynet \
  -p 127.0.0.1:8095:9100 \
  -e PROCESSOR_HOST=processor \
  -e PROCESSOR_PORT=9200 \
  toy-gateway
```
Captured (`30-…` to `35-ps-8095.txt`, trimmed):
```text
$ curl -sS -X POST http://localhost:8095 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'
{"upper": "HELLO FROM THE LAPTOP", "listen_port": 9200, "sender_port": 47520, "gateway_out_port": 47520}
$ curl --max-time 3 http://localhost:8090
curl: (7) Failed to connect to localhost:8090 after 0 ms: Could not connect to server
$ docker logs gateway
gateway listening on port 9100  →  open http://localhost:8090
172.19.0.1 - - [14/Oct/2026 00:32:26] "POST / HTTP/1.1" 200 -
$ docker ps --format 'table {{.Image}}\t{{.Ports}}\t{{.Names}}'
IMAGE           PORTS                      NAMES
toy-gateway     127.0.0.1:8095->9100/tcp   gateway
toy-processor                              processor
```
- **Checkpoint.** http://localhost:8095 works, :8090 no longer does (`:355`). The page diagram shows `localhost:8095 → :9100` (`index.html:87-88`), but the log banner still says `open http://localhost:8090`: that string is hard-coded (`gateway.py:53`, E15). The request in the log comes from `172.19.0.1`, the bridge's gateway address: Docker forwards published traffic into the network, so the gateway never sees your laptop's own address.

**B12. Move the processor to 9300 and watch it break** (`port_toy/README.md:369-371`, `:375-378`).
```bash
docker rm -f processor
```
```bash
docker run -d --name processor --network toynet \
  -e PORT=9300 toy-processor
```
- **Checkpoint.** "Send a message from the browser. It should fail." (`:380`; use the gateway's current port, 8095). What you actually see: **nothing changes on the page**, because `index.html:95-100` has no error handling. The page's request, captured (`38-send-fails.txt`, exit 52):
  ```text
  $ curl -sS -X POST http://localhost:8095 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'

  curl: (52) Empty reply from server
  ```
- **Why** *(extra; `docker logs` as in B6)* (`39-logs-gateway-refused.txt`, trimmed; `40-logs-processor-9300.txt`):
  ```text
  $ docker logs gateway
  gateway listening on port 9100  →  open http://localhost:8090
  172.19.0.1 - - [14/Oct/2026 00:32:26] "POST / HTTP/1.1" 200 -
  ----------------------------------------
  Exception occurred during processing of request from ('172.19.0.1', 46328)
  Traceback (most recent call last):
  …
    File "/app/gateway.py", line 34, in do_POST
      conn.request("POST", "/", body=text_from_browser,
  …
  ConnectionRefusedError: [Errno 111] Connection refused
  ----------------------------------------
  $ docker logs processor
  processor listening on port 9300 (internal only)
  ```
  The name `processor` still resolves, but nothing listens on 9200 there any more; the gateway has no `try/except` (`gateway.py:33-40`), so the connection to the browser is dropped without an answer.

**B13. Re-point the gateway** (`port_toy/README.md:388-390`, `:394-400`).
```bash
docker rm -f gateway
```
```bash
docker run -d --name gateway --network toynet \
  -p 127.0.0.1:8090:9100 \
  -e PROCESSOR_HOST=processor \
  -e PROCESSOR_PORT=9300 \
  toy-gateway
```
Captured (`43-send-9300.txt`):
```text
$ curl -sS -X POST http://localhost:8090 -H 'Content-Type: application/json' -d '{"text": "hello from the laptop"}' -w '\n'
{"upper": "HELLO FROM THE LAPTOP", "listen_port": 9300, "sender_port": 39938, "gateway_out_port": 39938}
```
- **Checkpoint.** http://localhost:8090 works again, and the middle port line shows `9300`. "The two settings must agree" (`:404-407`); no image was rebuilt: the ports are configuration.

**B14. Clean up before Compose** (`port_toy/README.md:415-418`).
```bash
docker rm -f gateway processor
docker network rm toynet
```
Captured (`44-rm-both.txt`, `45-network-rm.txt`, `46-x-after-cleanup.txt`): the names `gateway`, `processor`, then `toynet` are echoed back; `docker ps -a; docker network ls` *(extra)* shows only the exited `hello-world` container and Docker's three built-in networks.
- **Why it matters here.** The compose file uses the **same container names and network name** (`docker-compose.yml:13`, `:28`, `:37-39`). Skipping this step makes B15 fail (G11).

**B15. Run with Compose** (`port_toy/README.md:454-456`).
```bash
docker compose up
```
Captured (`47-compose-up.txt`, trimmed; the last lines are the Ctrl+C of B17):
```text
$ docker compose up

[+] Building 0.3s (17/17) FINISHED
…
 => CACHED [processor 2/4] RUN apt-get update && apt-get install -y --no-  0.0s
…
 => => naming to docker.io/library/port_toy-processor:latest               0.0s
…
 => => naming to docker.io/library/port_toy-gateway:latest                 0.0s
…
[+] up 5/5
 ✔ Image port_toy-gateway   Built                                           0.5s
 ✔ Image port_toy-processor Built                                           0.5s
 ✔ Network toynet           Created                                         0.0s
 ✔ Container processor      Created                                         0.1s
 ✔ Container gateway        Created                                         0.0s
Attaching to gateway, processor
processor  | processor listening on port 9200 (internal only)
gateway    | gateway listening on port 9100  →  open http://localhost:8090
processor  | 172.19.0.3 - - [14/Oct/2026 00:32:33] "POST / HTTP/1.1" 200 -
gateway    | 172.19.0.1 - - [14/Oct/2026 00:32:33] "POST / HTTP/1.1" 200 -
processor  | 172.19.0.3 - - [14/Oct/2026 00:32:34] "GET /health HTTP/1.1" 200 -
…
```
- **Under the hood.**
  1. Compose reads `docker-compose.yml` and builds both services' images (`:14`, `:29`), named `port_toy-gateway` and `port_toy-processor` (new names, but every layer came from the by-hand builds' cache).
  2. It creates network `toynet` (`:37-39`), as the README lists: build, network, containers (`port_toy/README.md:466-469`).
  3. It starts `processor` first because of `depends_on` (`:22-23`), then `gateway` with `ports`, `environment`, and the **bind mount `./gateway:/app`** (`:15-21`).
  4. Logs from both containers stream in your terminal, prefixed by container name. In the log above, the processor sees requests from `172.19.0.3` (the gateway), the gateway from `172.19.0.1` (forwarded from the laptop).
- **Checkpoint.** The same two banners; http://localhost:8090 works (`:460`; captured send `49-send-compose.txt`: `"listen_port": 9200`).
- **Compare the commands** (`:478-484`), from a second terminal (`48-compose-ps.txt`, `50-network-ls-compose.txt`, `51-compose-exec.txt`):
  ```text
  $ docker compose ps
  NAME        IMAGE                COMMAND                  SERVICE     CREATED         STATUS         PORTS
  gateway     port_toy-gateway     "python -u gateway.py"   gateway     2 seconds ago   Up 2 seconds   127.0.0.1:8090->9100/tcp
  processor   port_toy-processor   "python -u processor…"   processor   2 seconds ago   Up 2 seconds
  $ docker network ls
  …
  cbd50cc80e70   toynet    bridge    local
  $ docker compose exec gateway curl http://processor:9200/health
  ok
  ```
  The README writes `docker compose exec gateway curl ...`; with the URL of Step 2 it prints `ok` without a progress meter, because `compose exec` gives curl a terminal.

**B16. Edit and re-apply** (`port_toy/README.md:487-501`).
```bash
docker compose up -d
```
```bash
docker compose up -d --build
```
The capture ran these with the app in the background (after B17's `Ctrl+C` and `down`, a fresh `docker compose up -d`: `[+] up 3/3`, network `Created`, both containers `Started`, `55-compose-up-d.txt`).
- **A port experiment** *(the edit is yours; the capture made it with `sed`)*: `"127.0.0.1:8090:9100"` → `"127.0.0.1:8095:9100"` in `docker-compose.yml` (line 16), then (`58-compose-up-d-changed.txt`):
  ```text
  $ docker compose up -d
  [+] up 2/2
   ✔ Container processor Running                                              0.0s
   ✔ Container gateway   Started                                             10.5s
  ```
  Only the gateway, whose configuration changed, was recreated (10.5 s: the old one took 10 s to stop, G12); the send on 8095 worked (`59-…`). Restoring the file and `up -d` again recreated it once more.
- **A code change** *(extra edit)*: one added line at the end of `processor/processor.py`, then (`62-compose-up-d-build.txt`, trimmed):
  ```text
  $ docker compose up -d --build

  [+] Building 0.4s (17/17) FINISHED
  …
   => CACHED [gateway 4/4] COPY . .                                          0.0s
   => [processor 4/4] COPY . .                                               0.0s
  …
  [+] up 4/4
   ✔ Image port_toy-processor Built                                           0.5s
   ✔ Image port_toy-gateway   Built                                           0.6s
   ✔ Container gateway        Running                                         0.0s
   ✔ Container processor      Started                                        10.4s
  ```
  Only the processor's `COPY` layer was new, and only the processor was recreated.
- **Under the hood.** `processor.py` reaches the container only through `COPY . .`, so it needs `--build` (a plain `up -d` leaves both containers `Running`, Exercise C5). The gateway's folder is mounted (`docker-compose.yml:17-18`): `index.html` is re-read every time the page loads (`gateway.py:20`), while `gateway.py` itself is read once at start and needs `docker compose restart gateway`.

**B17. Stop and remove** (`port_toy/README.md:505-529`). If Compose is running in your terminal, press `Ctrl+C` (`:507`). Then:
```bash
docker compose down
```
```bash
docker compose ps -a
```
- **Captured.** `Ctrl+C` in the `docker compose up` terminal (end of `47-compose-up.txt`; pressed 3.9 s after start, the command ended at 24.3 s):
  ```text
  Gracefully Stopping... press Ctrl+C again to force
  Container gateway Stopping
  Container gateway Stopped
  Container processor Stopping
  gateway exited with code 137
  Container processor Stopped
  processor exited with code 137
  ```
  ```text
  $ docker compose ps -a
  NAME        IMAGE                COMMAND                  SERVICE     CREATED          STATUS                                PORTS
  gateway     port_toy-gateway     "python -u gateway.py"   gateway     24 seconds ago   Exited (137) 10 seconds ago
  processor   port_toy-processor   "python -u processor…"   processor   24 seconds ago   Exited (137) Less than a second ago
  $ docker compose down
  [+] down 3/3
   ✔ Container gateway   Removed                                              0.0s
   ✔ Container processor Removed                                              0.0s
   ✔ Network toynet      Removed                                              0.2s
  $ docker compose ps -a
  NAME      IMAGE     COMMAND   SERVICE   CREATED   STATUS    PORTS
  ```
  (`52-compose-ps-a-stopped.txt`, `53-compose-down.txt`, `54-compose-ps-a-after.txt`.)
- **Under the hood.** `Ctrl+C` asks Compose to stop the containers with SIGTERM. Python runs as PID 1 and installs no SIGTERM handler, so the signal is ignored; Docker waits its 10-second stop timeout and then kills (exit code 137 = 128 + 9, SIGKILL), the gateway first (reverse `depends_on` order), then the processor (G12). "Gracefully Stopping" is only Compose's message. `docker compose down` on the running app takes as long: `Removed 10.2s` for each container, 20.8 s in all (`64-compose-down-running.txt`). `down` removes the containers and the `toynet` network; the images remain (`:515`): `docker image ls` lists `port_toy-*` and `toy-*`, 198 MB each, sharing their layers (`66-x-images-remain.txt`).
- **Following a log** (*Handy commands*, `README.md:572-573`; `56b-compose-logs-f.txt`, `56d-compose-exec-sh.txt`):
  ```text
  $ docker compose logs -f gateway
  gateway  | gateway listening on port 9100  →  open http://localhost:8090
  gateway  | 172.19.0.1 - - [14/Oct/2026 00:32:58] "POST / HTTP/1.1" 200 -
  ^C
  $ docker compose exec gateway sh
  # hostname
  27b8d17b0ee0
  # echo $PROCESSOR_HOST $PROCESSOR_PORT
  processor 9200
  # exit
  ```
  The `POST` line appeared when a send ran in another terminal; `Ctrl+C` ends the follow (exit 130), not the app.

**B18. *(extra)* What Compose does with leftovers from Steps 1-3** (G11; `67-x-g11-by-hand.txt` … `69c-x-g11-cleanup.txt`).
- With the by-hand network **and** a by-hand `processor` container still there (`docker network create toynet` and the processor's `docker run` of B4), `docker compose up -d` printed:
  ```text
  WARN[0000] a network with name toynet exists but was not created by compose.
  Set `external: true` to use an existing network
  …
  Error response from daemon: Conflict. The container name "/processor" is already
   in use by container "ee89e5b189254cbffb0af0315637440fb50a0fd52e855ff9453b108c8c
  8e8ff6". You have to remove (or rename) that container to be able to reuse that
  name.
  ```
  exit 1. `container_name: processor` (`docker-compose.yml:28`) pins the name.
- With only the network left over, Compose v5.6.0 printed the same warning and then **used** it: both containers `Started`. But `docker compose down` then removed only the containers and left `toynet` behind (Compose didn't create it); `docker network rm toynet` removed it.
- **Fix.** B14 before B15.

---

## 5. Code tour

```
mega-pipeline/  (branch flexible-workflow)
├── README.md                     story, SA/IAM/API setup, docker-shell modes, sample Dockerfile
├── .gitignore                    ignores secrets/ (and misc) repo-wide
├── transcribe_audio/             Task A: mp3 -> FLAC (ffmpeg) -> Speech-to-Text -> text_prompts/
│   ├── Dockerfile                python:3.14-slim-bookworm + build-essential ffmpeg, user app, uv sync
│   ├── docker-shell.sh           4 modes: (none)=build+run, dev, run, prod (buildx multi-arch push)
│   ├── pyproject.toml / uv.lock  ffmpeg-python, google-cloud-speech, google-cloud-storage (locked)
│   ├── cli.py                    -d/-t/-u
│   └── .gitignore                /secrets /input_audios /text_prompts
├── generate_text/                Task B: Gemini on Vertex AI -> text_paragraphs/  (cli.py -d/-g/-u)
├── synthesis_audio_en/           Task C: TTS long-audio (en-US) -> text_audios/  (cli.py -d/-s)
├── translate_text/               Task D: Translation v2 -> text_translated/  (cli.py -d/-t/-u)
└── synthesis_audio/              Task E: TTS long-audio (fr-FR) -> output_audios/ (cli.py -d/-s);
    └── cli_11.py                 bonus ElevenLabs version (requests; output_audios_pp/)
  (all five Dockerfiles are identical except ARG DEBIAN_PACKAGES; all five docker-shell.sh
   are identical except IMAGE_NAME — verified with diff)

port_toy/
├── README.md                     Steps 1-4, cheat sheet, handy commands
├── docker-compose.yml            gateway (published 127.0.0.1:8090:9100, bind mount) + processor; network toynet
├── gateway/
│   ├── Dockerfile                python:3.14-slim + curl; CMD python -u gateway.py
│   ├── gateway.py                GET -> index.html; POST -> forward to $PROCESSOR_HOST:$PROCESSOR_PORT
│   └── index.html                text box, port read-out and SVG diagram
└── processor/
    ├── Dockerfile                python:3.14-slim + curl (README says it has none: E14)
    └── processor.py              GET /health -> ok; POST -> upper-case + ports
```

**1. `mega-pipeline/transcribe_audio/docker-shell.sh:6-14`: the configuration block**
```bash
# Define some environment variables
export IMAGE_NAME="mega-pipeline-transcribe-audio"
export BASE_DIR=$(pwd)
export SECRETS_DIR=$(pwd)/../../secrets/
export GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json

# Default values
DOCKER_USERNAME="dlops"
BUILD_MODE="dev-run"  # Default mode
```
- `IMAGE_NAME` plays three roles: the local tag (`:75`, `:83`), the container name (`:92`), and the registry repository name (`:66`, `:88`). It is the only line that differs between the five scripts (apart from whitespace).
- `BASE_DIR` and `SECRETS_DIR` depend on your **current directory**, so run the script from the component folder. `../../secrets/` means "the `secrets/` folder beside the repo" (captured mount: `/home/student/AC215/secrets -> /secrets`).
- `GOOGLE_APPLICATION_CREDENTIALS` here is the **in-container** path; it is passed in with `-e` later.
- `DOCKER_USERNAME="dlops"`: change it before `prod`. It also decides which registry image `run` falls back to.
- `BUILD_MODE="dev-run"` is used when no argument is given; line 48 prints it.

**2. `mega-pipeline/transcribe_audio/docker-shell.sh:54-66`: `prod`, multi-arch build and push**
```bash
    # Check if multi-arch builder exists and remove it if it does
    if docker buildx inspect multi-arch >/dev/null 2>&1; then
        echo "Removing existing multi-arch builder..."
        docker buildx rm multi-arch
    fi

    # Setup multi architecture build
    echo "Creating new multi-arch builder..."
    docker buildx create --driver-opt network=host --use --name multi-arch

    # Build for multiple architectures and push to registry
    echo "Building and pushing multi-arch image..."
    docker buildx build --platform linux/amd64,linux/arm64 --push -t $DOCKER_USERNAME/$IMAGE_NAME -f Dockerfile .
```
- `buildx inspect` / `rm` makes the script idempotent: it always starts from a fresh builder.
- `buildx create ... --use` makes `multi-arch` the **current** builder, and the script never switches back (G8).
- `--platform linux/amd64,linux/arm64 --push` builds both architectures and pushes one multi-arch tag. Multi-platform results go straight to the registry here; nothing is loaded locally.

**3. `mega-pipeline/transcribe_audio/docker-shell.sh:82-96`: choose an image, then run**
```bash
    # Check if local image exists
    if docker image inspect $IMAGE_NAME >/dev/null 2>&1; then
        echo "Using local image..."
        CONTAINER_IMAGE=$IMAGE_NAME
    else
        echo "Local image not found, using image from registry..."
        CONTAINER_IMAGE=$DOCKER_USERNAME/$IMAGE_NAME
    fi

    # Run Container
    docker run --rm --name $IMAGE_NAME -ti \
    -v "$BASE_DIR":/app \
    -v "$SECRETS_DIR":/secrets \
    -e GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \
    $CONTAINER_IMAGE
```
- `docker image inspect $IMAGE_NAME` checks for the **local** short name only. Any old local build wins, however stale.
- The fallback `$DOCKER_USERNAME/$IMAGE_NAME` has no tag, so `docker run` pulls `:latest` if it is not cached (captured: the 2025 `dlops` image, E1), and reuses the cached copy afterwards.
- `--rm`: the container (and anything installed in it) is deleted on exit. `--name` fixes the container name (G9). `-ti` gives an interactive terminal.
- `-v "$BASE_DIR":/app` is the live-code bind mount; it hides the image's `/app` (C3).
- `-v "$SECRETS_DIR":/secrets` plus `-e GOOGLE_APPLICATION_CREDENTIALS=...` is runtime secret injection (C4). If `SECRETS_DIR` does not exist, Docker creates an empty directory for a `-v` mount instead of failing, so you only find out inside the container (G3).

**4. `mega-pipeline/transcribe_audio/Dockerfile:34-46`: user, code, venv, entrypoint** (paired with `:15-17`)
```dockerfile
# Switch to the new user
USER app
WORKDIR /app

# Copy the source code
COPY --chown=app:app . ./

RUN uv sync

# Entry point
ENTRYPOINT ["/bin/bash"]
# Get into the uv virtual environment shell
CMD ["-c", "source /home/app/.venv/bin/activate && exec bash"]
```
- `USER app` means everything after this line, and the container at run time, runs as uid 1000 (created at `:30`), not root (captured: `uid=1000(app)`).
- `COPY --chown=app:app . ./` copies the **whole build context**, including any leftover `secrets/`, `input_audios/` or `text_*` folders. There is no `.dockerignore` (G6; captured with a stand-in key, A13).
- `RUN uv sync` installs the locked dependencies into `UV_PROJECT_ENVIRONMENT=/home/app/.venv` (`:17`), outside `/app`, so the bind mount cannot hide it.
  - `uv sync` runs without `--locked`/`--frozen`. If `pyproject.toml` and `uv.lock` disagree, uv re-resolves silently instead of failing.
- `ENTRYPOINT` + `CMD` give an interactive bash with the venv activated. `source` runs in the non-interactive `bash -c` shell and exports `PATH`/`VIRTUAL_ENV`; `exec bash` then *replaces* that shell with an interactive one (no wrapper shell left behind) that inherits those variables, so `python` is the venv's. One `exit` ends the container. The prompt shows no venv prefix (captured: `app@0ceffb272288:/app$`), but `which python` says `/home/app/.venv/bin/python`.
  - Only this start command activates the venv: a second shell opened with `docker exec -it <name> bash` gets `/usr/local/bin/python` and no packages (Exercise C3; G19).

**5. `mega-pipeline/generate_text/cli.py:16-25`: configuration that ships with someone else's values**
```python
gcp_project = "ac215-project"
bucket_name = "mega-pipeline-bucket"
text_prompts = "text_prompts"  # THIS IS THE TRANSCRIBED TEXT
text_paragraphs = "text_paragraphs"  # THIS IS THE LLM GENERATED TEXT
group_name = "pavlos-advanced"  # This needs to be your Group name e.g: group-01, group-02, group-03, group-04, group-05, ...
assert group_name != "", "Update group name"
#assert group_name != "pavlos-advanced", "Update group name"
#############################################################################
#                       Initialize the LLM Client                           #
client = genai.Client(vertexai=True, project=gcp_project, location="us-central1")
```
- The first lines are hard-coded configuration, edited by hand per team. Later course repos move this kind of thing to environment variables, as L05/L10 do with `GCP_PROJECT`.
- The `assert` guards only against the empty string. The guard that would have caught `pavlos-advanced` is commented out, so the assert passes with the course's values (E2).
- `genai.Client(vertexai=True, ...)` routes Gemini calls through **Vertex AI** in *your* project, billed and authorized with the SA (role `roles/aiplatform.user`). It is created at import time but doesn't load credentials until a request (captured: `--help` works without a key).

**6. `mega-pipeline/synthesis_audio_en/cli.py:78-91`: long-audio TTS writes straight to GCS**
```python
            parent = f"projects/{gcp_project}/locations/us-central1"
            output_gcs_uri = f"gs://{bucket_name}/{audio_blob_name}"

            request = texttospeech.SynthesizeLongAudioRequest(
                parent=parent,
                input=input,
                audio_config=audio_config,
                voice=voice,
                output_gcs_uri=output_gcs_uri,
            )

            operation = client.synthesize_long_audio(request=request)
            # Set a deadline for your LRO to finish. 300 seconds is reasonable, but can be adjusted depending on the length of the input.
            result = operation.result(timeout=300)
```
- `parent` is why `gcp_project` must be set in this component, while in `transcribe_audio` it is unused.
- `output_gcs_uri` makes Google's service write the result into your bucket; that is why there is no `--upload` step.
- `synthesize_long_audio` returns a **long-running operation**, and `.result(timeout=300)` blocks until it is done or 5 minutes pass.
- Not shown: the client itself is created at import (`:23`), which is why even `--help` needs the key here (captured); and `audio_encoding=LINEAR16` (`:74`) is uncompressed 16-bit PCM (Google returns it with a WAV header), yet the object is named `.mp3` (`:67`), E11.

**7. `port_toy/docker-compose.yml:11-25`: the gateway service**
```yaml
services:
  gateway:
    container_name: gateway
    build: ./gateway         # build the image from gateway/Dockerfile
    ports:
      - "127.0.0.1:8090:9100"  # ip:host:container — 127.0.0.1 = this laptop only
    volumes:
      - ./gateway:/app       # live-mount the source (edit without rebuilding)
    environment:
      PROCESSOR_HOST: processor
      PROCESSOR_PORT: "9200"
    depends_on:
      - processor            # gateway calls processor, so start processor first
    networks:
      - toynet
```
- `container_name: gateway` pins the name. It makes `docker exec gateway ...` from the README keep working, but it collides with a leftover by-hand container (G11, captured).
- `build: ./gateway` is the equivalent of `docker build ./gateway`; with no `image:` key the image is named `port_toy-gateway` (captured).
- `ports:` is `-p` (C7).
- `volumes:` is the bind mount, a feature the by-hand Step 1 did **not** use.
- `environment:` is `-e`. Values are quoted strings because YAML would otherwise parse `9200` as a number.
- `depends_on:` controls start order only; it does not wait for readiness.
- `networks: [toynet]` is `--network toynet`.

**8. `port_toy/docker-compose.yml:27-39`: the processor service and the named network**
```yaml
  processor:
    container_name: processor
    build: ./processor       # build the image from processor/Dockerfile
    environment:
      PORT: "9200"
    networks:
      - toynet
    # no ports: → internal only; reachable only as http://processor:9200


networks:
  toynet:
    name: toynet
```
- There is no `ports:` key, so nothing is published. The processor is reachable only through the network.
- `networks: toynet: name: toynet` makes Compose create a network literally named `toynet` instead of `port_toy_toynet`. This mirrors the by-hand step, and it can also meet a leftover by-hand network (G11: Compose v5.6.0 warns and uses it).

**9. `port_toy/gateway/gateway.py:32-42`: calling another container by name, and the source port**
```python
        # open a connection to the processor container BY NAME, on its port
        conn = http.client.HTTPConnection(PROCESSOR_HOST, PROCESSOR_PORT)
        conn.request("POST", "/", body=text_from_browser,
                     headers={"Content-Type": "application/json"})

        # the OS gave our outgoing connection a source port — read the real one
        out_port = conn.sock.getsockname()[1]

        reply = json.loads(conn.getresponse().read())
        conn.close()
        reply["gateway_out_port"] = out_port   # the port we sent from
```
- `HTTPConnection(PROCESSOR_HOST, PROCESSOR_PORT)`: the host comes from the environment (`:13`), default `"processor"`, and is resolved by Docker's DNS when `request()` connects (line 34, where Step 3's traceback points).
- `conn.sock.getsockname()[1]` reads the **local** (source) port the kernel picked for this TCP connection.
- `reply["gateway_out_port"] = out_port` attaches that port to the reply so the page can show it next to the processor's view. There is no `try/except`, so any connection failure becomes a traceback in `docker logs gateway`, and the browser's request gets no answer at all (captured: `curl: (52) Empty reply from server`).

**10. `port_toy/processor/processor.py:28-33` and `:42-45`: what the server sees**
```python
        # 2. do the "work" — just upper-case it — plus note the ports involved
        reply = {
            "upper": text.upper(),                         # the reply: just the upper-case text
            "listen_port": self.server.server_address[1],  # the real port we're bound to
            "sender_port": self.client_address[1],         # the port the gateway came from
        }
```
```python
port = int(os.environ.get("PORT", "9200"))
server = HTTPServer(("", port), Processor)
print(f"processor listening on port {server.server_address[1]} (internal only)")
server.serve_forever()
```
- `server_address[1]` is the port it actually bound. `client_address[1]` is the peer's port: the gateway's ephemeral port, unchanged because there is no NAT inside the bridge (captured: `"sender_port": 55620, "gateway_out_port": 55620`).
- `HTTPServer(("", port), ...)`: `""` = all interfaces (0.0.0.0) **of this container**. Binding `"127.0.0.1"` would make the server unreachable from other containers and from published ports (Exercise C2).
- `PORT` from the environment makes the listening port configuration, not code (Step 3).

**11. `port_toy/gateway/index.html:86-89`: the page reads the host port from the address bar**
```javascript
    // the host port is whatever you published with -p; read it from the address bar
    const hostPort = location.port || (location.protocol === "https:" ? "443" : "80");
    document.getElementById("d_hostport").textContent = hostPort;
    document.getElementById("d_hostport_r").textContent = hostPort;
```
- A container cannot know which host port it was published on; only the client can. The latest commit (`d190c71`) added this so the diagram shows 8095 in Step 3. The log banner in `gateway.py:53` was not updated (E15; captured: still `open http://localhost:8090` on 8095).

---

## 6. Gotchas and common errors

**G1. Switching from `main` blocks, or silently overwrites your L03 files.** *Captured (`mega-l03-laptop/`).*
- **Symptom 1.** From an L03 state (edited `transcribe_audio/cli.py`, untracked `generate_text/Dockerfile` and `generate_text/uv.lock`), `git checkout flexible-workflow` refuses with **two** reasons in one message: `Your local changes to the following files would be overwritten by checkout: transcribe_audio/cli.py` and `The following untracked working tree files would be overwritten by checkout: generate_text/Dockerfile generate_text/uv.lock`, then `Aborting`.
- **Cause 1.** The branch has its own `cli.py` and its own tracked `generate_text/Dockerfile` and `uv.lock`. On `main`, `generate_text/` has no `.gitignore`, so your files there are untracked and *not* ignored, and Git refuses to clobber them.
- **Symptom 2.** The README's `git stash` (`mega-pipeline/README.md:48`) clears only the first reason; the checkout still refuses. After `git stash -u` it succeeds, and `transcribe_audio/Dockerfile`, `pyproject.toml` and `uv.lock` are **silently replaced** by the branch's versions.
- **Cause 2.** `main:transcribe_audio/.gitignore:4-7` ignores `docker-shell.sh`, `Dockerfile`, `pyproject.toml` and `uv.lock`, and Git treats ignored files as expendable. The same rule exists in `synthesis_audio`, `synthesis_audio_en` and `translate_text` on `main`. (Ignored files aren't stashed by `-u` either.)
- **Fix.** Copy any L03 file you want out of the repo first. Then `git stash -u` (or move the files) before `git checkout flexible-workflow`. `git checkout -- .`, the README's other option, does not remove untracked files. To get your old `group_name` or Dockerfile back afterwards, read the stashes rather than popping them on this branch (Exercise B6).

**G2. `AssertionError: Update group name`.**
- **Cause.** `group_name = ""` and an import-time `assert` (e.g. `transcribe_audio/cli.py:21-24`). Even `python cli.py --help` trips it (captured in `synthesis_audio_en`, `cli.py:19`).
- **Fix.** Set `group_name`. The bind mount makes the edit live, even in a running container. Also note that `generate_text` and `translate_text` **do not** trip it (E2).

**G3. `google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.`** *Captured in all five components.*
- **Cause.** The key is not at `<component>/../../secrets/mega-pipeline.json` (`docker-shell.sh:9`), the file has a different name (a browser may save `mega-pipeline (1).json`), or you ran the script from the wrong folder.
  - Docker creates a **missing** bind-mount source as an empty directory, so `docker run` itself does not fail. You only find out inside.
- **Where it surfaces.**
  - `transcribe_audio`: at `--download`, in `storage.Client()` (`cli.py:39`), before anything is sent.
  - `generate_text`: `--help` works; `--download` fails at `storage.Client(project=gcp_project)` (`cli.py:41`).
  - `synthesis_audio_en`, `translate_text`, `synthesis_audio`: even `--help` fails, because their Google client is built at import (`synthesis_audio_en/cli.py:23`, `translate_text/cli.py:22`, `synthesis_audio/cli.py:22`).
- **Fix.** From the component folder, `ls ../../secrets/`; rename the key to `mega-pipeline.json`. Inside the container, `ls -l /secrets` must list it.

**G4. 403s naming `ac215-project` or `mega-pipeline-bucket`.**
- **Cause.** Shipped course values in `generate_text/cli.py:16-17` and `translate_text/cli.py:14-15` (E2). Your SA has no rights there.
- **Fix.** Set your project and bucket in all five `cli.py` files (the `grep` of A4 checks all of them at once).

**G5. 403 / `PERMISSION_DENIED` with your own project.** *Not reproduced (no Google account).*
- **Cause.** A missing role (§2 table) or a disabled API (`mega-pipeline/README.md:187`).
  - `storage.buckets.get` denied: transcribe uses `client.get_bucket(...)` (`transcribe_audio/cli.py:40`), which needs a bucket-level permission. "Storage Object Admin" is not enough; grant Storage Admin as the README says (`:178`).
  - Vertex denied: grant "Agent Platform User" (`roles/aiplatform.user`) and enable `aiplatform.googleapis.com`.
- **Fix.** Grant the role or enable the API. Both changes can take a few minutes to propagate; re-run after that.

**G6. Your key ends up inside the image, and maybe on Docker Hub.** *Captured with a stand-in file.*
- **Cause.** L03 told you to keep the key in `<component>/secrets/` (`main:README.md:97`), and switching branches leaves it there (`mega-pipeline/README.md:50`). The Dockerfile copies the whole folder (`Dockerfile:39`), and no branch has a `.dockerignore`.
  - `.gitignore`'s `/secrets` (`transcribe_audio/.gitignore:3`) only protects Git.
  - After `./docker-shell.sh dev` in the switched clone, `docker run --rm --entrypoint ls mega-pipeline-transcribe-audio -la /app /app/secrets` listed `mega-pipeline.json` (A13).
  - `./docker-shell.sh prod` pushes the image with that layer to a public repository (`docker-shell.sh:66`).
- **Fix.**
  - Delete the in-component `secrets/` folders after moving the key out.
  - Add a `.dockerignore` per component with `secrets/` and the data folders (`input_audios/`, `text_*/`, `output_audios*/`). Checked: after it, `ls /app/secrets` in a new image says `No such file or directory`.
  - Remove images built before the fix.
  - If a key was pushed, **delete that key in IAM** immediately. Deleting the image is not enough.

**G7. `./docker-shell.sh run` drops you into a Python 3.8 pipenv shell, or into `ImportError`.** *Captured.*
- **Cause.** With no local `mega-pipeline-<component>` image, the script uses `dlops/mega-pipeline-<component>` (`docker-shell.sh:86-88`), whose `latest` is a 2025-02-18 build: `PYTHON_VERSION=3.8.17`, `cmd ["-c","pipenv shell"]`, user root (E1).
  - With your uv-based folder mounted over `/app`, that environment doesn't match `pyproject.toml`/`uv.lock`. Transcribe's `--help` still worked; `generate_text`'s failed with `ImportError: cannot import name 'genai' from 'google' (unknown location)` (the 2025 image has `google-generativeai`). `translate_text`'s 2025 `Pipfile` installs `googletrans==4.0.0rc1`, not `google-cloud-translate`, so expect the same kind of failure there (not run).
  - The mount also hides the image's own `Pipfile`, so `pipenv shell` printed `Creating a Pipfile for this project...` and wrote a **root-owned `Pipfile` into your folder**.
  - A related case: in `run` mode, packages you `uv add`-ed but never rebuilt are missing (C3).
- **Fix.** Use the default mode or `dev` to build locally. Use `run` only for images *your team* pushed from this branch under its own `DOCKER_USERNAME`. `rm Pipfile` and `docker image rm dlops/mega-pipeline-<component>` to undo.

**G8. After `prod`, the `multi-arch` builder stays selected.** *Checked on Docker Engine 29.8.2 + buildx v0.37.2 (Exercise B7); `prod` itself not run.*
- **Cause.** `docker buildx create ... --use` (`docker-shell.sh:62`) makes `multi-arch` (driver `docker-container`) the current builder, and the script never switches back.
- **What it changes.** There, a plain `docker build` (what `docker-shell.sh:75` runs in `dev` and the default mode) still used the `default` builder and updated the local image as usual: its plain log begins `#0 building with "default" instance using docker driver`. Only `docker buildx build` commands use `multi-arch`, and without `--push` or `--load` they leave no local image (`WARNING: No output specified with docker-container driver`). The builder also keeps a BuildKit container running (`buildx_buildkit_multi-arch0`). Other Docker versions may behave differently: check with `docker buildx ls` and the first line of a plain build log.
- **Fix.** After `prod`, `docker buildx use default` (on Docker Desktop the builder may be called `desktop-linux`; see `docker buildx ls`), or `docker buildx rm multi-arch`, which also removes its container.

**G9. `Conflict. The container name "/mega-pipeline-<component>" is already in use`.** *Captured.*
- **Cause.** `--name $IMAGE_NAME` (`docker-shell.sh:92`) while another shell of the same component is still running. The second `./docker-shell.sh` first rebuilt (its `COPY` and `uv sync` re-ran, because the first container's `--download` had created `input_audios/` and `text_prompts/` in the build context), then `docker run` failed with exit 125.
- **Fix.** `exit` the other shell, or `docker rm -f mega-pipeline-<component>`. For a second shell in the *same* container, see G19.

**G10. Linux hosts only: `PermissionError` writing `/app/...` or reading `/secrets/...`.** *Checked as a uid-1001 user (Exercise C6).*
- **Cause.** The container runs as uid 1000 (`Dockerfile:30`, `:35`). Bind mounts keep host ownership. If your host uid is not 1000, the container user cannot create files in your folder: `python cli.py --download` stops with `PermissionError: [Errno 13] Permission denied: 'input_audios'` from `makedirs()` (`transcribe_audio/cli.py:28`), and `uv add` with ``error: failed to create file `/app/pyproject.toml`: Permission denied (os error 13)``. A key that is `chmod 600` for another uid can't be read either.
  - Docker Desktop on macOS and Windows handles ownership in mounts for you, so this mostly hits Linux VMs.
- **Fix.** Work as a user whose uid is 1000 (`id -u`), or make the folders writable for uid 1000. Adding `--user "$(id -u):$(id -g)"` to the script's `docker run` lets the CLI run but breaks `uv add` (Exercise C6).

**G11. `docker compose up` fails right after the by-hand steps.** *Captured with Compose v5.6.0.*
- **Cause.** Containers named `gateway`/`processor` and a network named `toynet` already exist; the compose file pins the same names (`docker-compose.yml:13`, `:28`, `:39`).
  - Leftover containers: `WARN … a network with name toynet exists but was not created by compose.`, then `Conflict. The container name "/processor" is already in use by container …`, exit 1.
  - A leftover network alone: the same warning, then Compose **uses** it and both containers start; `docker compose down` then leaves `toynet` behind. (Other Compose versions may refuse such a network; the digest had flagged this as version-dependent.)
- **Fix.** B14 first: `docker rm -f gateway processor` and `docker network rm toynet`.

**G12. `Ctrl+C` / `docker compose down` takes about 20 seconds.** *Captured.*
- **Cause.** `CMD ["python", "-u", "gateway.py"]` makes Python PID 1. PID 1 ignores SIGTERM unless it installs a handler, and these scripts do not. Docker waits its 10-second stop timeout, then SIGKILLs (`exited with code 137`). Compose stops `gateway` before `processor` (reverse `depends_on`), so the two waits add up: Ctrl+C took about 20 s; `down` on the running app showed `Removed 10.2s` for each container, 20.8 s in all; an `up -d` that recreates a running container waits 10 s too.
- **Fix (optional).** Add `init: true` or `stop_signal: SIGINT` to each service (Exercise B4: `down` then took 0.96 s). `docker rm -f` is instant because it kills straight away.

**G13. "It should fail", but nothing visible happens.** *Captured.*
- **Cause.** In Step 3 the gateway raises `ConnectionRefusedError` at `conn.request` (`gateway.py:34`; no error handling in `:33-40`) and drops the browser's request without an answer (curl: `Empty reply from server`). `index.html:95-100` has no `catch`, so the page simply does not update.
- **Fix.** Watch `docker logs -f gateway` (or `docker compose logs -f gateway`, `port_toy/README.md:572`) while clicking Send.

**G14. `curl localhost:9200` succeeds when it "should fail".**
- **Cause.** Another program on your laptop listens on 9200. The README warns about this (`port_toy/README.md:262`); Elasticsearch's default port is 9200.
- **Fix.** `lsof -i :9200` (macOS/Linux) to see which. The lesson still holds: the toy processor is not published.

**G15. `Bind for 127.0.0.1:8090 failed: port is already allocated`.** *Captured (exit 125).*
- **Cause.** An old `gateway` (by hand or Compose) is still published on 8090, or another app uses it (`port_toy/README.md:357-361`, `:550`). A `-p 8090:9100` without an address also collides with a `127.0.0.1:8090` mapping, because it asks for 8090 on every address.
- **Fix.** `docker ps` to find it and `docker rm -f`, or pick another host port (B11). The failed `docker run` still created its container: `docker rm` it before reusing the name.

**G16. Gemini default model or Translation language surprises.**
- **Cause.** `gemini-2.5-flash-lite` is hard-coded as the default (`generate_text/cli.py:73`); a retired model returns 404. Translation targets `es` (`translate_text/cli.py:64`), while synthesis is French.
- **Fix.** `export GEMINI_MODEL=...` inside the container (`generate_text/README.md:91-94`), or `-e GEMINI_MODEL=…` in the script's `docker run`; set `target_language="fr"`.

**G17. Apple Silicon.**
- Local builds are native arm64. Both bases, `python:3.14-slim-bookworm` and `python:3.14-slim`, exist for arm64, and the lock files contain cp314 manylinux aarch64 wheels for the compiled packages (`grpcio`, `cffi`, `google-crc32c`, `pydantic-core`), so no compilation is needed.
- `prod`'s amd64 half runs under emulation and is noticeably slower.
- An image you build and push *without* `prod` would be arm64-only, which matters once you deploy to amd64 VMs (L02 lesson).

**G18. Windows Git BASH rewrites the container-side paths.** *Well-known MSYS behaviour; not run.*
- **Cause.** The README sends Windows users to Git BASH (`mega-pipeline/README.md:378`). Git BASH's MSYS layer converts POSIX-looking arguments it passes to native programs such as `docker.exe`: `GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` (`docker-shell.sh:95`) can become `...=C:/Program Files/Git/secrets/mega-pipeline.json`, and a `-v <host>:/app` spec (`:93-94`) can be mangled into an invalid volume specification.
- **Symptom.** `invalid volume specification` / "invalid characters for a local volume name", or `DefaultCredentialsError` for a `C:/Program Files/Git/...` path.
- **Fix.** Run `MSYS_NO_PATHCONV=1 ./docker-shell.sh` (combine with `winpty` if needed), or run the script from WSL 2. Neither is in the README.

**G19. A second shell into a running component has no venv.** *Checked (Exercise C3).*
- **Cause.** The image activates `/home/app/.venv` only in its start command (`Dockerfile:46`). `docker exec -it mega-pipeline-transcribe-audio bash` gets you in as `app`, in `/app`, but `which python` prints `/usr/local/bin/python` and `import google.cloud.storage` fails with `ModuleNotFoundError: No module named 'google'`.
- **Fix.** `docker exec -it mega-pipeline-transcribe-audio bash -c "source /home/app/.venv/bin/activate && exec bash"`, or `uv run python cli.py …` in the plain shell.

**G20. A step "succeeds" and does nothing.** *Captured.*
- **Cause.** Each step loops over the files the previous one left (`input-*.txt`). With nothing downloaded, `generate_text`'s `--generate` printed `Args: …` and `generate` and exited 0, without calling Gemini. The same happens after a `--download` that found nothing, e.g. because the recording isn't named `input-…` or `group_name` differs between components.
- **Fix.** After each `--download`, `ls` the folder it filled (`text_prompts/<group>/`, …) before the next step; check names and `group_name` if it is empty.

---

## 7. Where this sits in the course

**Before.**
- **L02 (Containers I)**, `simple-translate`: one image, `docker build` / `docker run --rm -ti`, push to Docker Hub, pull on a VM.
- **L03 (Containers II)**, `mega-pipeline` `main` @ `c6bbc9b`: five components, each with a Dockerfile **you wrote from scratch** (`main:transcribe_audio/README.md:36-92`).
  - Built and run by hand: `docker run --rm -ti -v "$(pwd):/app" transcribe_audio` (`main:transcribe_audio/README.md:99`).
  - A **shared** Canvas key copied into every component's `secrets/` (`main:README.md:97-99`), and `ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` baked into the Dockerfile (`main:README.md:194-195`).
  - A shared bucket (`main:README.md:65`, `:72`), hard-coded as `bucket_name = "mega-pipeline-bucket"` in project `ac215-project` (e.g. `main:transcribe_audio/cli.py:17-18`), and a public leaderboard (`main:README.md:50-56`).

**This lecture adds.**
- Part A turns "it works on my laptop" into a team workflow:
  - committed Dockerfiles and lock files
  - one wrapper script per component with build / pull / publish modes
  - secrets outside the repo, injected at run time
  - your own SA with explicit roles and explicitly enabled APIs
  - multi-arch images
- Part B adds the networking layer that part A deliberately avoids ("Since we haven't covered APIs yet ... communicate indirectly by writing their outputs to storage", `mega-pipeline/README.md:140-142`): container networks, DNS by name, published vs internal ports, and Compose.

**`git diff --stat main origin/flexible-workflow`** (42 files, +4227 / −625):
```
 README.md                           | 287 ++++++++++++----
 */Dockerfile        (5 new)         |  46 +++ each   (identical except DEBIAN_PACKAGES)
 */docker-shell.sh   (5 new, 100755) |  97 +++ each   (identical except IMAGE_NAME)
 */uv.lock           (5 new)         | 505-661 +++ each (2,725 lines total)
 */pyproject.toml    (4 new, 1 mod)  |  10-11 lines each; name "generate-text" -> "app"
 */README.md         (5 rewritten)   | 181-207 lines changed each
 */cli.py            (5 modified)    |   9-24 lines changed each
 */.gitignore        (4 mod, 1 new)  | stop ignoring Dockerfile/pyproject/uv.lock/docker-shell.sh
 generate_text/main.py               |   6 ------  (deleted uv-init stub)
 */secrets/.gitkeep  (5 deleted)     | secrets no longer live inside components
```
The meaningful changes:
1. **Tooling is committed.** On `main`, four components' `.gitignore` files ignore `Dockerfile`, `pyproject.toml`, `uv.lock` and `docker-shell.sh`. On this branch those lines are gone and the files are tracked (which is why switching replaces your L03 copies, G1).
2. **Secrets move out.** `ENV GOOGLE_APPLICATION_CREDENTIALS` disappears from the Dockerfile. `docker-shell.sh` mounts `../../secrets/` at `/secrets` and passes the env var (`mega-pipeline/README.md:372`).
3. **Base image moves from Python 3.12 to 3.14.**
   - `main`'s sample Dockerfile says `python:3.12-slim-bookworm` (`main:README.md:177`), although `main:generate_text/pyproject.toml` already requires `>=3.14`.
   - This branch says `python:3.14-slim-bookworm` (`Dockerfile:2`), and `requires-python = ">=3.14"` (`transcribe_audio/pyproject.toml:6`) matches it: `uv sync` used the image's own CPython 3.14.8 and downloaded no interpreter (captured).
   - `DEBIAN_PACKAGES` drops `curl` (`main:README.md:179` vs `Dockerfile:4`).
4. **`cli.py` changes.**
   - Configuration values are blanked (three components) or set to the course's (two).
   - Import-time asserts are added.
   - `translate_text` targets `es` instead of `fr`.
   - `synthesis_audio`'s argparse description is fixed.
   - `transcribe_audio` **loses** `main`'s 2026-09-27 multi-result fix (E6).
5. **The README** gains the SA/IAM/API section, the folder layout, the four script modes, and a branch-switching guide. It drops the leaderboard.

port_toy is a new repo with no predecessor. Its history is 10 commits from 2026-09-14 to 2026-09-20, and its Compose file gained `container_name`s and the named `toynet` network in `868224b`.

**After: what builds on this.**
- **L05 (RAG)**, `llm-rag`. A Compose app whose CLI container talks to a ChromaDB container **by name on a Compose network**:
  - `networks: default: name: llm-rag-network` (`llm-rag/docker-compose.yml:1-3`)
  - `container_name: llm-rag-chromadb` (`:20`)
  - `CHROMADB_HOST = "llm-rag-chromadb"`, `CHROMADB_PORT = 8000` (`llm-rag/cli.py:30-31`)
  - a published `8000:8000` without the `127.0.0.1` restriction (`docker-compose.yml:21-22`)
  - the same `../secrets:/secrets` pattern (`:11`)
  - a `docker-shell.sh` that just calls `docker compose run --rm` (`llm-rag/docker-shell.sh:12`)

  It is exactly port_toy's pattern, with a database in place of the processor.
- **L10 (cheese-app-v0).**
  - `api-service/docker-shell.sh` reuses `SECRETS_DIR=$(pwd)/../../secrets/` (`:8`), `docker network create cheese-app-network` (`:14`), `-p 9000:9000` and `--network cheese-app-network` (`:20`, `:26`).
  - The frontend publishes `-p 3200:3000`, a host port different from the container port (`frontend-ai-chatbot/docker-shell.sh:11`), which is Step 3's lesson.
- **Milestone 2** requires that "The pipeline must be runnable with one command (e.g., `docker compose up` or `make run`)." (`src/2026-AC215/milestone2.md:48`), plus `pyproject.toml` (uv) per container and Dockerfiles (`:77-79`).

---

## 8. Exercises

The exercises, with full answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l04-flexible-workflow-ports/exercises.md) in the video folder. Their outputs are the 2026-10-14 captures, or were checked the same day on the same kind of stand-in laptop (Docker Engine 29.8.2, Compose v5.6.0, buildx v0.37.2, no Google account). Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. Which files define a mega-pipeline image? What does `run` use when there's no local image?**
<details><summary>Answer</summary>

Three committed files per component: the `Dockerfile` (base `python:3.14-slim-bookworm`, apt packages, user `app`, `COPY --chown=app:app . ./`, `RUN uv sync`), `pyproject.toml` (the dependencies) and `uv.lock` (their exact versions). `docker-shell.sh` builds with the component folder as the context (`docker-shell.sh:75`), so everything else in that folder is copied in too (Q3). The base tag, `apt-get upgrade` and `pip install uv` are not pinned: they take whatever is current (Python 3.14.8, uv 0.13.0 at the time of recording).

`run` (`docker-shell.sh:79-96`) uses any local `mega-pipeline-<component>`, however old (`Using local image...`). Without one it runs `dlops/mega-pipeline-<component>:latest`, pulled the first time and reused afterwards: a 2025-02-18 image from the `pipenv-flexible-workflow` branch, Python 3.8.17, `pipenv shell`, root. Your folder is mounted over its `/app`, so your code runs in their environment: transcribe's `--help` works, `generate_text`'s fails with `ImportError: cannot import name 'genai' from 'google'`, and pipenv leaves a root-owned `Pipfile` in your folder. Build locally (no argument, or `dev`); use `run` only for images your team pushed from this branch.
</details>

**Q2. Which three gates must a call to your bucket pass, and where does each one fail?**
<details><summary>Answer</summary>

1. **Who are you?** The key, found through `GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` (`docker-shell.sh:10`, `:95`). Fails **inside your container**, before any request: `DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.` In `transcribe_audio` and `generate_text` at `--download`; in the other three even at `--help`, because their client is built at import.
2. **What may you do?** The SA's IAM roles (Storage Admin for all five; Agent Platform User, Cloud Speech Client, Cloud Translation API User for B, A, D). Fails **at Google**: a 403 permission error. A `cli.py` that still names the course's project or bucket fails the same way.
3. **Is the API switched on?** The five services of `gcloud services enable`. Also fails **at Google**, with a 403 saying the API is disabled or not used in the project.

Gates 2 and 3 were not reproduced (no Google account). Role and API changes can take a few minutes to apply.
</details>

**Q3. How does a git-ignored key end up in an image? The fix?**
<details><summary>Answer</summary>

`.gitignore` is read by Git only (`transcribe_audio/.gitignore:3`). Docker reads `.dockerignore`, and no branch has one. `docker build … .` sends the component folder as the context, and `COPY --chown=app:app . ./` (`Dockerfile:39`) copies all of it. In an L03 clone switched to this branch, the old key is still in `transcribe_audio/secrets/` (`README.md:50`), so `./docker-shell.sh dev` bakes it in; `docker run --rm --entrypoint ls mega-pipeline-transcribe-audio -la /app /app/secrets` lists it (captured with a stand-in). Fix: delete every `secrets/` folder inside a component, add a `.dockerignore` with `secrets/` (checked: the folder is then absent from the image), remove images built before the fix, and if an image with a key was ever pushed, delete that key in IAM.
</details>

**Q4. In `-p 127.0.0.1:8095:9100`: which number does the browser use, which does `gateway.py` bind, and what does `127.0.0.1` restrict?**
<details><summary>Answer</summary>

IP address : host port : container port (`port_toy/README.md:224-230`). **8095** is for the browser (`http://localhost:8095` worked and `localhost:8090` was refused). **9100** is what `gateway.py` binds (`gateway.py:51-52`, the `PORT` default, on all of its own addresses). **127.0.0.1** restricts the laptop side: only programs on your laptop can connect; without it `docker ps` shows `0.0.0.0:<port>->9100/tcp`. It restricts nothing inside the container, and the container never learns 8095: its banner still says `open http://localhost:8090`.
</details>

**Q5. Inside the gateway, what is `localhost`, and which name reaches the processor?**
<details><summary>Answer</summary>

`localhost` is the gateway container itself: `docker exec gateway curl --max-time 3 http://localhost:9200/health` fails with `curl: (7) Failed to connect to localhost port 9200`, while `localhost:9100` returns the page. The processor is reached by its name, **`processor`**, on 9200: `docker exec gateway curl http://processor:9200/health` prints `ok`. It works because both are on the user-defined network `toynet`, whose DNS (`nameserver 127.0.0.11` in the gateway) answers `processor` with `172.19.0.2`. On Docker's default `bridge` network names don't resolve at all.
</details>

### Hands-on (predict, then run)

**B1. `EXPOSE` is not publish.** Add `EXPOSE 9200` to `processor/Dockerfile` after `WORKDIR /app`, rebuild, re-run Step 1. Predict the processor's `PORTS` cell and whether `curl --max-time 3 http://localhost:9200/health` works; then add `-P` to its `docker run`.
<details><summary>Answer</summary>

`9200/tcp` (declared, no arrow); curl still fails with `curl: (7)`. `EXPOSE` only writes `{"9200/tcp":{}}` into the image config. `-P` publishes every exposed port to a random host port on all addresses (the check got `0.0.0.0:32768->9200/tcp`; `docker port processor` tells you which), and `curl http://localhost:32768/health` printed `ok`. Undo: `git checkout processor/Dockerfile`, rebuild, re-create.
</details>

**B2. Two rooms with the same number.** Processor with `-e PORT=9100`, gateway with `-e PROCESSOR_PORT=9100` (keep `-p 127.0.0.1:8090:9100`). Does either fail with "port is already allocated"?
<details><summary>Answer</summary>

No. Both banners say port 9100, and the page works with `"listen_port": 9100`. Each container has its own set of ports; only a door on the laptop can be "already allocated".
</details>

**B3. Step 3, in Compose.** With `docker compose up -d` running, change only the processor's `PORT` to `"9300"` (`docker-compose.yml:31`) and `up -d`; then the gateway's `PROCESSOR_PORT` (`:21`) and `up -d` again.
<details><summary>Answer</summary>

First: `Container gateway Running`, the processor recreated; a send gets `curl: (52) Empty reply from server`, and `docker compose logs gateway` ends with `ConnectionRefusedError`. Second: the processor `Running`, the gateway recreated (about 11 s: the old one takes 10 s to stop); the send works with `"listen_port": 9300`. No image was rebuilt: both are configuration.
</details>

**B4. Make Ctrl+C fast.** Time `docker compose down` with the app running; add `init: true` to both services and time it again; then try `stop_signal: SIGINT`.
<details><summary>Answer</summary>

21.1 s without the change: Python is PID 1 and ignores SIGTERM, so Docker waits 10 s per container and kills (137). With `init: true`: 0.96 s, `Exited (143)`; Docker's init is PID 1 and passes SIGTERM on. With `stop_signal: SIGINT`: 0.96 s, `Exited (130)`, the log ends in `KeyboardInterrupt`. By hand, `docker run --init` does what `init: true` does.
</details>

**B5. A package that never reached the image.** In `transcribe_audio`: `./docker-shell.sh`, then inside `uv add rich`, `python -c "import rich"`, `exit`; then `./docker-shell.sh run` and the import again; then `./docker-shell.sh dev`.
<details><summary>Answer</summary>

The first import works; `git status` on the laptop shows ` M pyproject.toml` and ` M uv.lock`. `exit` deletes the container and the venv copy with `rich`. `run` uses the image built before `uv add`: `ModuleNotFoundError: No module named 'rich'`. `dev` re-runs `COPY` and `uv sync` (`Installed 30 packages`), and then `run` imports `rich`. That's the README's order (`transcribe_audio/README.md:89`): `uv add` inside, commit both files, `dev`.
</details>

**B6. Get your L03 work back.** After the branch switch of A2 you have two stashes. Predict `git stash pop` and `git stash apply stash@{1}` on `flexible-workflow`, and find two safe ways to recover your old `group_name` and `generate_text/Dockerfile`.
<details><summary>Answer</summary>

`stash@{0}` holds the two untracked `generate_text` files, `stash@{1}` your `cli.py` edit. `pop` refuses (`generate_text/Dockerfile already exists, no checkout`, `could not restore untracked files from stash`; the stash is kept). `apply stash@{1}` gives `CONFLICT (content): Merge conflict in transcribe_audio/cli.py` (back out with `git checkout HEAD -- transcribe_audio/cli.py`). Safe: **read, don't apply** (`git stash show -p stash@{1}`; `git show 'stash@{0}^3:generate_text/Dockerfile'`), or **go back** (`git checkout main`, `git stash pop` twice). Going back can't restore `transcribe_audio`'s ignored L03 `Dockerfile`, `pyproject.toml` and `uv.lock`: they were never stashed. Copy files out *before* you switch.
</details>

**B7. What `prod` leaves behind.** Run only the builder line of `prod`, `docker buildx create --driver-opt network=host --use --name multi-arch`. Predict what `docker buildx ls` marks with `*`, and which builder the next `./docker-shell.sh dev` uses.
<details><summary>Answer</summary>

`multi-arch*` (driver `docker-container`): `--use` made it current, and the script never switches back. On Docker Engine 29.8.2 / buildx v0.37.2, `./docker-shell.sh dev` still built with `default` (`#0 building with "default" instance using docker driver`); a `docker buildx build -t <name> .` without `--push`/`--load` used `multi-arch` and left no image (`WARNING: No output specified with docker-container driver`). The builder runs a container, `buildx_buildkit_multi-arch0`. Clean up with `docker buildx rm multi-arch` (back to `default*`).
</details>

### Debugging

**C1. "The page does nothing."** You started the processor without `--network`. The page doesn't update, and `docker logs gateway` ends with `socket.gaierror: [Errno -2] Name or service not known`. Why, and two fixes?
<details><summary>Answer</summary>

The processor is on Docker's default `bridge` network, not `toynet`, so `toynet`'s DNS doesn't know `processor`: from the gateway, `curl: (6) Could not resolve host: processor` (captured). Unlike Step 3's `Connection refused`, the lookup fails before any port is tried. Fixes: `docker network connect toynet processor` (works at once), or `docker rm -f processor` and re-run it with `--network toynet`. On the default bridge, names don't resolve between containers at all; IP addresses do.
</details>

**C2. A "safer" bind address.** `gateway.py:52` changed to `HTTPServer(("127.0.0.1", port), Gateway)`, rebuilt and run as in Step 1. The banner and `docker ps` look normal, but the browser gets an error. Why?
<details><summary>Answer</summary>

Published traffic arrives at the container's network interface, not its loopback; a server bound to `127.0.0.1` inside accepts only connections from inside that container. Checked: from the laptop `curl: (56) Recv failure: Connection reset by peer`; from the processor `Failed to connect to gateway port 9100`; inside the gateway, `curl http://localhost:9100` still works. Restrict on the host side (`-p 127.0.0.1:8090:9100`) and keep `""` inside.
</details>

**C3. A name already in use.** With `transcribe_audio`'s container open (and `--download` run in it), `./docker-shell.sh` in a second terminal builds, then fails with `Conflict. The container name "/mega-pipeline-transcribe-audio" is already in use`, exit 125. Why did it build again, why the conflict, and how do you get a second shell?
<details><summary>Answer</summary>

It rebuilt because the folder changed: `--download` created `input_audios/` and `text_prompts/`, which Git ignores but Docker copies (list them in `.dockerignore` too). The conflict: `--name $IMAGE_NAME` gives every container of a component the same name. A second shell: `docker exec -it mega-pipeline-transcribe-audio bash -c "source /home/app/.venv/bin/activate && exec bash"` (a plain `bash` has no venv, G19), or `uv run python cli.py …`.
</details>

**C4. Compose refuses to start.** You skipped Step 3's clean-up: `WARN … a network with name toynet exists but was not created by compose.`, then `Conflict. The container name "/processor" is already in use`. Why? And with only the network left over?
<details><summary>Answer</summary>

The compose file pins `container_name: gateway` / `processor` (`docker-compose.yml:13`, `:28`) and `name: toynet` (`:39`); your by-hand containers hold those names. Fix: `docker rm -f gateway processor`, `docker network rm toynet`. Without the pins, Compose would have used `port_toy-gateway-1`, `port_toy-processor-1` and `port_toy_toynet` (checked). With only the network left over, Compose v5.6.0 warns and uses it, and `down` then leaves it behind (captured).
</details>

**C5. "My change to the processor doesn't show."** Under Compose, `processor.py:30` becomes `"upper": text.lower(),`; `docker compose up -d` says both `Running`, the page still shows capitals, and `docker compose restart processor` doesn't help. Why? And why would an `index.html` edit show at once?
<details><summary>Answer</summary>

`processor.py` reaches the container only through `COPY . .`: the image holds the old copy, and `restart` restarts the same image. `docker compose up -d --build` rebuilds (only the processor's `COPY` layer), recreates the processor, and the reply becomes lower case. The gateway's folder is mounted and `index.html` is read on every page load (`gateway.py:20`); a `gateway.py` edit needs `docker compose restart gateway` (still no rebuild).
</details>

**C6. `PermissionError` on a Linux VM.** Your user's `id -u` isn't 1000, and `python cli.py --download` stops with `PermissionError: [Errno 13] Permission denied: 'input_audios'` from `makedirs()` (`transcribe_audio/cli.py:28`). Why?
<details><summary>Answer</summary>

The container runs as uid 1000; the bind mount keeps your ownership, so uid 1000 may read `/app` but not create folders in it (`uv add` fails too). Work as a uid-1000 user or make the folder writable for uid 1000; `--user "$(id -u):$(id -g)"` in the script lets the CLI run but breaks `uv add`. Docker Desktop on macOS/Windows maps ownership for you (G10).
</details>

### Think

**D1. Make `run` safe.** `run` pulled a February 2025 image for a branch written in September 2026. What would you change so it gives everyone the image of the code they have?
<details><summary>Answer</summary>

The tag `latest` is a signpost to whatever was pushed last, by whoever, from whatever branch. Set `DOCKER_USERNAME` to your team's account; push with `prod` from this branch (after the `.dockerignore` fix); tag with the commit too (`-t $DOCKER_USERNAME/$IMAGE_NAME:$(git rev-parse --short HEAD)`) and run that tag; refresh on purpose (`docker pull`, or `docker run --pull=always`), because `run` reuses a cached tag; and `docker image rm` a stale local `mega-pipeline-<component>`, which `run` prefers over any push. While the recipe changes weekly, building locally is the safe default (`README.md:71`).
</details>

**D2. Rebuild or not?** (a) `group_name`; (b) `uv add`; (c) `-e GEMINI_MODEL=gemini-2.5-flash \` in `generate_text/docker-shell.sh`; (d) a new key in `secrets/`; (e) the processor's `PORT` in Step 3; (f) `processor.py` under Compose; (g) `gateway/index.html` under Compose; (h) a package added to `ARG DEBIAN_PACKAGES`.
<details><summary>Answer</summary>

(a) no, the mount shows it at once; (b) yes, `dev`; (c) no, it's set at `docker run` and read when `--generate` runs; (d) never, it's mounted and must never be in an image; (e) no, configuration; (f) yes, `up -d --build`; (g) no, mounted and read on every page load; (h) yes, and it's the slow one (build step 2). One catch for (a) and (c): the default mode rebuilds on every start anyway, and an edited `cli.py` or `docker-shell.sh` makes build steps 4 and 5 run again (quick, but not nothing).
</details>

**D3. Compose for part A.** Write a `docker-compose.yml` for `transcribe_audio` that does what `./docker-shell.sh` does when it runs the container. How do you get the interactive shell?
<details><summary>Answer</summary>

Checked in `transcribe_audio/`:
```yaml
services:
  transcribe:
    build: .
    image: mega-pipeline-transcribe-audio
    volumes:
      - ./:/app
      - ../../secrets/:/secrets
    environment:
      GOOGLE_APPLICATION_CREDENTIALS: /secrets/mega-pipeline.json
    stdin_open: true
    tty: true
```
`docker compose run --rm transcribe` opens the image's start command: the venv shell with both mounts. Relative paths count from the file's folder, like the script's `$(pwd)`; `image:` gives the built image the script's name. It doesn't do `--name` (each run gets its own name, so two shells don't conflict), the `dev`/`run` choice or `prod`, and it creates a network `transcribe_audio_default` that `down` removes. Lecture 5 uses this kind of file.
</details>

**D4. What's still there after the lecture?** List what may be left on your laptop and in the cloud, and what each costs.
<details><summary>Answer</summary>

Laptop (disk only): the five component images (1.48 GB and 821-836 MB), any pulled `dlops/…` images (1.17 GB, 1.02 GB), the base images and `hello-world` with its exited container, port_toy's four images (about 200 MB together), the `multi-arch` builder container and `moby/buildkit` image if you ran `prod` or B7, root-owned `Pipfile`s from `run` (`rm Pipfile` works), your stashes, and the key in `secrets/`. Cloud: the bucket bills storage until deleted; the key works until deleted (do it when done, at once if it ever left your laptop); APIs bill per use, not for being enabled; the SA costs nothing; a pushed Docker Hub repository is public unless you changed it.
</details>

---

## 9. Errata and open questions

**Errata**

- **E1. The registry fallback serves a different, stale image.** `docker-shell.sh` `run` falls back to `$DOCKER_USERNAME/$IMAGE_NAME` = `dlops/mega-pipeline-<component>` (`transcribe_audio/docker-shell.sh:86-88`). The README presents this as the "pull a prebuilt copy" path (`mega-pipeline/README.md:69-74`, `:214`).
  - Registry metadata (2026-10-12): all five `dlops/mega-pipeline-*:latest` were pushed 2025-02-18. Captured on 2026-10-14 for two of them: `PYTHON_VERSION=3.8.17`, `cmd ["-c","pipenv shell"]`, `GOOGLE_APPLICATION_CREDENTIALS=../secrets/mega-pipeline.json`, `user ""` (root); `python --version` → `Python 3.8.17`; `generate_text`'s `--help` → `ImportError: cannot import name 'genai'`; a root-owned `Pipfile` created in your folder.
  - Their build matches `pipenv-flexible-workflow:transcribe_audio/Dockerfile` (`FROM python:3.8-slim-buster`, `pipenv sync`), not this branch's `python:3.14-slim-bookworm` + `uv sync`.
  - Older per-arch tags `amd64`/`arm64` date from 2024-09-17.
- **E2. The assert guard is defeated in two components.** `generate_text/cli.py:16-22` and `translate_text/cli.py:14-20` ship `gcp_project="ac215-project"`, `bucket_name="mega-pipeline-bucket"`, `group_name="pavlos-advanced"`, with the `pavlos-advanced` assert commented out (captured with `grep`, A4).
  - The root README says "The CLIs `assert` that it has been changed from the default — if you forget, the script stops before doing anything." (`mega-pipeline/README.md:134`).
  - Introduced by commits `95cf6f1` (2026-09-15) and `cc67f3b` (2026-09-18), which reverted the blanking done in `6e512da`.
- **E3. French story, Spanish code.**
  - `translate_text/cli.py:64` has `target_language="es"`, while `translate_text/README.md:96-103` shows the same call with `target_language="fr"`.
  - These say French: `mega-pipeline/README.md:3` (the 🇫🇷 in the pipeline emoji line), `:13`, `:157`; `translate_text/README.md:8`, `:100`, `:105`, `:117`, `:132`; the argparse description "Translate English to French" (`translate_text/cli.py:108`).
  - The next stage uses a French voice, `fr-FR-Standard-C` (`synthesis_audio/cli.py:48-49`), so the final audio is Spanish text read by a French voice.
  - **Fix:** set `target_language="fr"`.
- **E4. Three different "defaults" for the same three values.**
  - The root README shows all three as `""` (`mega-pipeline/README.md:128-130`).
  - Every component README shows `gcp_project = "ac215-project"`, `bucket_name = "mega-pipeline-bucket"`, `group_name = ""` (e.g. `transcribe_audio/README.md:51-53`).
  - The code has `""` in three files and the course's values in two (E2).
  - `mega-pipeline/README.md:133` says `gcp_project` and `bucket_name` "still point at the shared class resources from the earlier tutorial", which is false for the three blanked files.
  - **Fix:** set all three in all five files, whatever they show.
- **E5. No bucket creation and no input data.** The branch requires your own bucket (`mega-pipeline/README.md:62`, `:150`) but gives no command to create it and no source for `input_audios/` content.
  - The Appendix's upload sample uses `input_audios/test.mp3` (`:313`), but uploads glob `input-*.txt` (`transcribe_audio/cli.py:102`) and downstream downloads glob `input-*.txt` (`generate_text/cli.py:43`), so a `test.mp3` would never leave the transcribe step.
  - In L03 the shared bucket already held Pavlos's recording.
  - **Fix:** `gcloud storage buckets create …` and upload an `input-<something>.mp3` (§2 item 5).
- **E6. `flexible-workflow` lacks `main`'s transcription fix.** `main` @ `c6bbc9b` (2026-09-27) concatenates *all* `response.results` because "Speech-to-Text automatically breaks longer audio files into chunks". `flexible-workflow` still keeps only `response.results[0]` (`transcribe_audio/cli.py:84-86`). Longer recordings are truncated to their first chunk. **Fix:** join all results, as `main:transcribe_audio/cli.py` does, or keep the recording short.
- **E7. No `.dockerignore` on any branch, while `COPY . ./` copies the whole component folder** (`Dockerfile:39`).
  - Combined with L03's instruction to store the key inside each component (`main:README.md:97`) and the README's reassurance that `secrets/` "stay[s] put" (`mega-pipeline/README.md:50`), `prod` can publish the key (G6; the key in the image was captured with a stand-in).
  - `mega-pipeline/README.md:203` ("Keeping the folder outside the repo ... is the canonical way to make that mistake impossible") holds for Git only.
  - **Fix:** a `.dockerignore` with `secrets/` and the data folders in each component.
- **E8. Branch-switch instructions are incomplete.** `mega-pipeline/README.md:48` covers only modified tracked files. Captured: the checkout refuses for two reasons at once; `git stash` clears only the edited `cli.py`; the untracked `generate_text/Dockerfile` / `uv.lock` still block it until `git stash -u`; and ignored student files in four components (`Dockerfile`, `pyproject.toml`, `uv.lock`) are silently replaced (G1).
- **E9. Role name inconsistency.** `generate_text/README.md:46` says "Vertex AI User", while `mega-pipeline/README.md:179` warns that searching "Vertex AI User" finds nothing and to search "Agent Platform User".
- **E10. The ElevenLabs bonus does not fit the branch's secrets layout.**
  - `synthesis_audio/README.md:129-133` says to add `11lab_api_key.txt` "to your `secrets/` folder", which on this branch is `<workspace>/secrets` → `/secrets`.
  - But `cli_11.py:30` opens `'secrets/11lab_api_key.txt'` relative to `/app` (the component folder), and hard-codes `bucket_name="mega-pipeline-bucket"`, `group_name="pavlos"` with no assert (`cli_11.py:15-19`). The key file is read at import (`:33-39`), so without it even `--help` fails (captured: `FileNotFoundError: … 'secrets/11lab_api_key.txt'`).
  - The README says output "lands in the `output_audios_pp/` prefix of your bucket" (`synthesis_audio/README.md:135`), but `-s` only writes local files (`cli_11.py:105-108`); a separate `-u` uploads them (`:117-133`), and then to the hard-coded bucket.
  - **Fix:** point `secrets_file_path` at `/secrets/11lab_api_key.txt` and set your own bucket and group; never put the key inside the component folder (it would be copied into the image).
- **E11. Audio encoding vs file extension.** Both synthesis components request `AudioEncoding.LINEAR16` (`synthesis_audio_en/cli.py:74`, `synthesis_audio/cli.py:73`) but name the objects `.mp3` (`synthesis_audio_en/cli.py:67`, `synthesis_audio/cli.py:66`). This is also on `main` (`main:synthesis_audio_en/cli.py:66`, `:73`). LINEAR16 output is 16-bit PCM with a WAV header, so the file is really a WAV; most players sniff the content, but it is not MP3. **Fix:** `AudioEncoding.MP3`, or name the objects `.wav`.
- **E12. `chmod +x` is a no-op after a clone** (not an error). All five `docker-shell.sh` files are committed with mode `100755`, and a fresh clone has them as `-rwxr-xr-x` (captured). The README's wording is conditional ("If `docker-shell.sh` isn't executable yet", `mega-pipeline/README.md:220-224`), so it is correct; it matters only if the executable bit gets lost (some archive extractors, or copying through a filesystem without Unix permissions).
- **E13. The `prod` builder is left selected.** `docker buildx create ... --use` (`docker-shell.sh:62`) is never undone. The digest inferred that later plain builds might not load into the local image store; on Docker Engine 29.8.2 / buildx v0.37.2 they did (Exercise B7): only `docker buildx build` commands use the leftover builder, and its BuildKit container keeps running (G8). **Fix:** `docker buildx use default` or `docker buildx rm multi-arch` after `prod`.
- **E14. port_toy README says the processor has no curl; the Dockerfile installs it.**
  - `port_toy/README.md:294`: "The gateway image includes `curl` for these tests. The processor image does not need it."
  - `port_toy/processor/Dockerfile:2` installs `curl` (captured: curl 8.14.1 in the processor). Commit `de54f9f` ("processor: drop curl — nothing ever used it") removed it, and `868224b` re-added it.
  - The *statement* "does not need it" is true; the *implication* that the image lacks it is not.
- **E15. The gateway log banner hard-codes the host port.** `gateway.py:53` always prints `open http://localhost:8090`, even in Step 3 when it is published on 8095 (`README.md:345-351`; captured). `d190c71` fixed only the page diagram (`index.html:86-89`).
  - The README's sample log line (`README.md:140`) also has single spaces where the code prints two around `→`.
- **E16. Step 3's failure is invisible in the UI.** "It should fail" (`port_toy/README.md:380`), but `index.html` has no error handling (`:95-100`) and the gateway does not catch connection errors (`gateway.py:33-40`). The visible symptom is "nothing happens" (captured: the page's request gets `curl: (52) Empty reply from server`), with a traceback ending in `ConnectionRefusedError: [Errno 111] Connection refused` in `docker logs gateway`. **Fix:** watch the log while you click Send (G13).
- **E17. Schedule inconsistency on the course site.**
  - `src/2026-AC215/tutorials_demo.md:56-67` lists Lecture 4 as "Containers II-b".
  - `src/2026-AC215/_modules/week-03.md:5-7` lists "Lecture 4" as "LLM - RAGs" on Sep 15.
  - The commit dates (port_toy 2026-09-14 to 09-20; flexible-workflow READMEs 2026-09-14 to 09-18) fit a mid-September Containers II-b session; the module pages look stale.
- **E18. `run` is described as "pull from the registry", but it prefers any local image.** `mega-pipeline/README.md:74` says "`run` to pull and run from the registry" (`:214`, "falls back to DockerHub", is accurate). The script first checks `docker image inspect mega-pipeline-<component>` and uses that local build if it exists, however old (`docker-shell.sh:83-85`; captured: `Using local image...`); the registry is used only when it is missing (`:86-88`), and an already-pulled `dlops/...:latest` is reused without re-pulling (`docker run` pulls only a missing tag).

**Open questions (could not be determined from the sources)**
- **Q1. Where should students get input audio for their own bucket?** Copy Pavlos's file from the shared bucket (needs read access), or record their own? Also, is a group leaderboard still used on this branch? It was removed from the README, but `group_name` is still required.
- **Q2. Are any Text-to-Speech roles needed?** `mega-pipeline/README.md:185` ("Text-to-Speech needs no role") and `synthesis_audio_en/README.md:48` (long-audio output is written with the caller's Storage Admin permission) could not be verified without a Google account. If long-audio synthesis returns a permission error on `output_gcs_uri`, check the Text-to-Speech long-audio docs for the required bucket permissions. The same goes for how strictly Speech-to-Text enforces the Cloud Speech Client role.
- **Q3. Is `gemini-2.5-flash-lite` (the default, `generate_text/cli.py:73`) still served on Vertex AI in your project and region?** Later course repos use newer model names; if it 404s, set `GEMINI_MODEL`.
- **Q4. Does the course intend students to push to `dlops`?** The script default (`docker-shell.sh:13`) and the README note (`mega-pipeline/README.md:76`) suggest that only staff push there. Will the `dlops/*` images be rebuilt from this branch (fixing E1)?
- **Q5. Answered by the captures:** Compose v5.6.0 warns about a pre-existing `toynet` and uses it (G11). Older or newer Compose versions may still differ.
- **Q6. Ed lesson content.** The Ed lesson (https://edstem.org/us/courses/97373/lessons/166029/) was not accessible when these sources were checked. Any slides or in-class instructions there (e.g. a provided bucket or input audio) are not reflected in this guide.
- **Q7. Long recordings in `transcribe_audio`.** The CLI sends the whole FLAC inline (`content=`, `transcribe_audio/cli.py:74-80`) rather than a `gs://` URI, and waits only 90 s (`:81`). Google documents a ~10 MB limit for inline audio, so a multi-minute stereo recording may be rejected or time out. Not tested; Pavlos's L03 recording presumably fits.
- **Q8. Docker Desktop specifics.** The captures ran on Docker Engine 29.8.2 on Linux. The builder behaviour of G8, the client error wording of Exercise C2 and the ownership mapping of G10 may differ on Docker Desktop for macOS or Windows.

---

## Links

- mega-pipeline README sections (pinned commit `cc67f3b`): [Get the Code](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#get-the-code) · [Where We Are, Where We're Going](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#where-we-are-where-were-going) · [Two ways to work](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#two-ways-to-work--and-we-support-both) · [The Five Components](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#the-five-components) · [Recommended folder layout](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#recommended-folder-layout) · [⚠️ Configure each `cli.py` before you run it](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#%EF%B8%8F-configure-each-clipy-before-you-run-it) · [Connecting the Pipeline Components](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#connecting-the-pipeline-components) · [Service Account & Secrets](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#service-account--secrets) · [How to Run a Component](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#how-to-run-a-component) · [Quick Reference — Running Each Component](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#quick-reference--running-each-component) · [Sample Dockerfile](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#sample-dockerfile) · [Notes for running on Windows](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#notes-for-running-on-windows) · latest README on [`flexible-workflow`](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow)
- mega-pipeline component READMEs (pinned): [transcribe_audio](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/transcribe_audio/README.md) · [generate_text](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/generate_text/README.md) · [synthesis_audio_en](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/synthesis_audio_en/README.md) · [translate_text](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/translate_text/README.md) · [synthesis_audio](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/synthesis_audio/README.md)
- port_toy README sections (pinned commit `d190c71`): [Prerequisites](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#prerequisites) · [How the app works](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#how-the-app-works) · [Step 1: Set up the network by hand](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-1-set-up-the-network-by-hand) · [Step 2: Check the ports](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-2-check-the-ports) · [Step 3: Change the ports](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-3-change-the-ports) · [Step 4: Run with Compose](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-4-run-with-compose) · [Port and networking cheat sheet](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#port-and-networking-cheat-sheet) · [Handy commands](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#handy-commands) · latest README on [`main`](https://github.com/dlops-io/port_toy#port-toy-app)
- Ed lesson: [L04 · Containers II-b](https://edstem.org/us/courses/97373/lessons/166029/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l04-flexible-workflow-ports) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l04-flexible-workflow-ports/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l04-flexible-workflow-ports/assets/terminal) · [ASSETS.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l04-flexible-workflow-ports/ASSETS.md)
- Colab notebooks: none for this lecture.
- Previous lecture: [L03 · Containers II](L03-containers-2-mega-pipeline.md) (the same pipeline on `main`, with Dockerfiles you write yourself)
- Next lecture: [L05 · Introduction to RAG](L05-rag.md) (port_toy's pattern, with a ChromaDB container in place of the processor)
- Referenced in §7: [L02 · Containers I](L02-containers-1.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md)
