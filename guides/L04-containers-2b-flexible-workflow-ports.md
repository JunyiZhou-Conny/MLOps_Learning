# L04 · Containers II-b — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166029/) · Tutorials: [`dlops-io/mega-pipeline`](https://github.com/dlops-io/mega-pipeline) `flexible-workflow` @ [`cc67f3b`](https://github.com/dlops-io/mega-pipeline/tree/cc67f3b8fc471f4fe1afe73d03e89466bae7d485) (Mega Pipeline App · flexible workflow) and [`dlops-io/port_toy`](https://github.com/dlops-io/port_toy) `main` @ [`d190c71`](https://github.com/dlops-io/port_toy/tree/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c) (Docker Compose · Port Toy App) · Colab: none for this lecture · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 这节课是两个互相独立的 tutorial。(A) **mega-pipeline 的 `flexible-workflow` branch**：把 L03 的五段 podcast pipeline（transcribe → generate → synthesize EN，translate → synthesize FR）按 team 的方式重跑一遍：自己的 GCS bucket、自己的 service account、key 放在 repo 外面，每个 component 自带 committed 的 `Dockerfile` + `pyproject.toml` + `uv.lock` + `docker-shell.sh`。这次你不写 Dockerfile，只改每个 `cli.py` 里的三个变量，然后进 container 跑 CLI。(B) **port_toy**：gateway + processor 两个 container 的小 web app，先手动 `docker network create` / `docker run -p` / `-e` 连起来，再改 port 把它弄坏，最后用一个 `docker-compose.yml` 全部替代。Part B 不需要 GCP。
- **Idea 1 · build 还是 pull：** `Dockerfile` + lockfile 是 source，image 是编译出来的 artifact，tag 只是一个 pointer，不保证跟你 checkout 的 commit 对得上。`docker-shell.sh` 有四个 mode：不带参数 = build + run，`dev` = 只 build，`run` = 先找本地 image、没有才 fallback 到 Docker Hub 上的 `dlops/...`，`prod` = 用 `docker buildx` build amd64 + arm64 的 multi-arch image 并 push。
- **Idea 2 · bind mount 盖住 `/app`，venv 在外面：** `-v "$BASE_DIR":/app` 把 host 上的 component folder 盖在 image 的 `/app` 上，VS Code 里改的代码立刻生效，CLI 写出的文件也直接出现在 host 上。venv 在 `/home/app/.venv`（`UV_PROJECT_ENVIRONMENT`），不在 mount 底下，所以不会被盖掉。在 container 里 `uv add` 会改 host 上的 `pyproject.toml` / `uv.lock`，但装进去的包随 `--rm` 一起消失，要 rebuild 才算数。
- **Idea 3 · secret 在 runtime 注入：** SA 的 JSON key 放在 `<your-workspace>/secrets/mega-pipeline.json`（repo 的上一层），run 的时候 mount 到 `/secrets`，再用 `-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` 传进去，不 bake 进 image。三道门缺一不可：key（我是谁）、IAM role（我能做什么）、API enabled（服务开了没）。key 找不到或读不了是 `DefaultCredentialsError`，role 或 API 缺了是 403。
- **Idea 4 · network namespace 和 port：** 每个 container 有自己的 network namespace、自己的 `localhost`、自己一整套 port。user-defined bridge `toynet` 自带 embedded DNS，所以 gateway 用 `http://processor:9200` 按名字就能找到 processor。只有 `-p` / `ports:` 才会在 host 上开一扇门（`127.0.0.1:8090 -> 9100`），`EXPOSE` 只是 metadata；processor 没 publish，所以你笔记本上 `curl localhost:9200` 连不上。只有 host port 会冲突。
- **Idea 5 · Compose = 同样的 flags 声明一次：** `-p` ↔ `ports:`，`-e` ↔ `environment:`，`--network` ↔ `networks:`，`docker build ./gateway` ↔ `build: ./gateway`。`docker compose up` 负责 build image、建 network、按 `depends_on` 的顺序起 container（只管启动顺序，不等 ready）；`Ctrl+C` 只是 stop，`docker compose down` 才删 container 和 network。
- **最费时间的坑（Part A）：** ① 从 L03 的 `main` 切 branch：untracked 的 `generate_text/Dockerfile`、`generate_text/uv.lock` 会让 `git checkout flexible-workflow` 直接 abort，另外四个 component 里被 `.gitignore` 忽略的 L03 Dockerfile 会被 silently 覆盖。想留就先拷出 repo，再 `git stash -u`。② `generate_text/cli.py` 和 `translate_text/cli.py` 出厂就填着老师的 `ac215-project` / `mega-pipeline-bucket` / `pavlos-advanced`，`assert` 拦不住，忘了改就是 403。③ `./docker-shell.sh run` 在没有本地 image 时拉的 `dlops/...:latest` 是 2025-02 的 Python 3.8 + Pipenv build，跟这个 branch 的 uv 环境对不上。
- **最费时间的坑（Part B）：** 手动那几步做完不清理（`docker rm -f gateway processor` + `docker network rm toynet`）就 `docker compose up`，会 conflict，因为 compose file 钉死了同样的 container name 和 network name。Step 3 里"应该失败"的时候页面什么都不显示，要看 `docker logs -f gateway` 里的 `ConnectionRefusedError`。
- **安全坑 + 小 errata：** 所有 branch 都没有 `.dockerignore`，`COPY --chown=app:app . ./` 会把 L03 留在 component 里的 `secrets/` 拷进 image，`prod` 再把它 push 到 Docker Hub。切完 branch 立刻删掉 component 里的 `secrets/`。另外 `translate_text` 写的是 `target_language="es"`，下一步用的却是 French voice（想要法语就改成 `"fr"`）；README 没讲怎么建 bucket，也没给 `input-*.mp3`。
- **做完要删：** SA key（IAM → Service accounts → Keys）；课程不再用 bucket 时 `gcloud storage rm -r gs://<your-bucket>`；本地 `docker image rm` 五个 `mega-pipeline-*` image；跑过 `prod` 就 `docker buildx rm multi-arch`；port_toy 里 `docker compose down`，再删 `toy-*` / `port_toy-*` image。API 都按用量计费，跑完没有东西在后台烧钱。

## At a glance

**What you build.** Two independent tutorials: (A) the five-stage podcast pipeline from L03 (transcribe → generate → synthesize EN, translate → synthesize FR), re-run on the `flexible-workflow` branch the way a team would ship it, with your own GCS bucket and service account, the key kept outside the repo and mounted at runtime, and a committed `Dockerfile`, `pyproject.toml`, `uv.lock` and `docker-shell.sh` per component that builds locally, runs a prebuilt image, or builds a multi-arch image and pushes it. (B) port_toy, a two-container web app (a published gateway and an internal processor on the network `toynet`) that you wire by hand with `docker network create` / `docker run -p` / `-e`, break by changing ports, and then replace with one `docker-compose.yml`.

**Time needed** (estimate). Part A: about 45 minutes of GCP setup (service account, key, APIs, bucket), then 10-15 minutes per component, the first build of each image being the slowest; about 2 hours in all. Part B: about 45 minutes, with no cloud account. The exercises in §8: about another hour.

**Prerequisites.**
- Tutorial 0, which covers a GCP account and project, VS Code, Git, Docker Desktop and `uv` (`mega-pipeline/README.md:22-26`). This lecture uses Docker Desktop with Compose v2 (`docker compose`) and Buildx, Git, and a bash shell (Git BASH on Windows).
- Part A: a GCP project with billing enabled, where you can create a service account and grant it roles. Optional: the `gcloud` CLI. Not needed on the host: Python and `uv`, which live inside the images.
- Part B: only Docker Desktop. "You do not need a GCP account or Python installed on your laptop." (`port_toy/README.md:24`)
- Only for `./docker-shell.sh prod`: a Docker Hub account and access token.
- Background: L02 (`docker build` / `docker run`) and L03 (the same pipeline, with Dockerfiles you wrote yourself).

**What it costs.** Part B is free. Part A pays per use: Speech-to-Text (audio minutes), Gemini on Vertex AI (tokens), Cloud Translation (characters) and Text-to-Speech (characters), plus tiny GCS storage. Nothing keeps running after a CLI command finishes, so keep the input clip short. The SA key costs nothing but is a long-lived credential, and Docker Hub is free for public repos.

**Tear down, exactly** (details in §2):
1. `exit` each container shell; `--rm` deletes the container.
2. Delete the SA key: console **IAM → Service accounts → Keys**, or `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=<sa-email>`.
3. When the course no longer needs the bucket: `gcloud storage rm -r gs://<your-bucket>`.
4. Delete leftover `<component>/secrets/` folders from L03 (G6).
5. Local images: `docker image rm mega-pipeline-transcribe-audio mega-pipeline-generate-text mega-pipeline-synthesis-audio-en mega-pipeline-translate-text mega-pipeline-synthesis-audio`.
6. Only if you ran `./docker-shell.sh prod`: `docker buildx rm multi-arch`, and delete pushed Docker Hub repos if they contain anything sensitive (G6).
7. In `port_toy/`: `docker compose down`, then `docker image rm toy-gateway toy-processor port_toy-gateway port_toy-processor`.

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
  - `dlops-io/mega-pipeline`, branch **`flexible-workflow`**, commit `cc67f3b8fc471f4fe1afe73d03e89466bae7d485`, committed 2026-09-18 00:12:58 -0400 ("latest mega pipeline flexible flow").
    - Diffed against `main` @ `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc` (2026-09-27 06:42:25 -0400). `main` is the L03 tutorial.
    - Merge base: `16cb292e7dcd13793133a26dabfbde53e4649863` (2025-09-11). The two branches have evolved separately for a year. `flexible-workflow` is **not** "main plus a few commits", and it is *older* than `main`'s tip (see Errata E6).
    - Other branches in the repo that this lecture does **not** use: `pipenv-flexible-workflow` @ `32fcdb7aa3ffb3eaf3d09bdde123a02a42f2be12` (2025-02-18). It matters anyway, because the prebuilt Docker Hub images were built from it (Errata E1). Also unused: `flexible-workflow-javier`, `pipenv`, `simple`, `solution`, `validation/mega-pipeline-javier`.
  - `dlops-io/port_toy`, branch `main`, commit `d190c7122fc35cc1f7e15e467d2babdfc24b5c0c`, committed 2026-09-20 13:46:56 -0400 ("gateway: show the real host port in the diagram").
- **Context repos read for §7**
  - `dlops-io/llm-rag` `main` @ `e17a39f35bc07b440f573def480adaf4703f8b91` (2026-10-07), the L05 tutorial
  - `dlops-io/cheese-app-v0` `main` @ `cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb` (2026-10-08), the L10 tutorial
- **Registry metadata inspected (read-only, 2026-10-12)**
  - `docker.io/dlops/mega-pipeline-{transcribe-audio,generate-text,synthesis-audio-en,translate-text,synthesis-audio}:latest`
    - All five are multi-arch OCI image indexes (amd64 + arm64, plus two `unknown/unknown` entries that are Buildx provenance attestations), last pushed 2025-02-18. Re-checked 2026-10-13 (tag dates for all five; full config for `generate-text`).
    - Each image config says `PYTHON_VERSION=3.8.17`, `Cmd ["-c","pipenv shell"]`, `GOOGLE_APPLICATION_CREDENTIALS=../secrets/mega-pipeline.json`, and no `User`.
    - In short, they are **not** built from this branch's Dockerfiles (Errata E1).
  - `python:3.14-slim-bookworm` and `python:3.14-slim` exist for both amd64 and arm64.
- **Method.** Nothing was built or run: no Docker daemon was available, and no repository script or Dockerfile was executed.
  - Lines marked *expected* are inferred from the code.
  - One experiment was run with plain `git`, in a throw-away worktree of the local clone: a switch from `main` to `flexible-workflow` with L03-style student files present, to observe what Git does. Results are in Gotcha G1.
- **Path convention.** `mega-pipeline/<path>` means the file on the `flexible-workflow` branch, `main:<path>` means the same repo on `main`, and `port_toy/<path>` means port_toy `main`.
- **Colab notebooks:** none for this lecture. **Ed lesson:** not accessible when these sources were checked (Q6); the course-site source above was used instead.
- Verified against the repos on 2026-10-13.

</details>

## Command checklist

Commands in backticks are exactly as the READMEs write them (placeholders kept); multi-line commands are joined onto one line, without the `\` continuations. Plain items are console clicks or edits. Items marked *(extra)* are not in the README; they come from §2, §4 and §6 of this guide. The root README uses the long CLI flags (`--download`, `--upload`, …); the component READMEs use the short forms (`-d`, `-t`, `-g`, `-s`, `-u`). The mega-pipeline groups follow §4's order (cloud prerequisites before `cli.py`; the three non-default `docker-shell.sh` modes after Task E), which differs slightly from the README's order; no README step is dropped.

### Mega-pipeline · Get the Code

*(`README.md:30-52`; §4 A1)*

*Starting fresh*
- [ ] `git clone --branch flexible-workflow https://github.com/dlops-io/mega-pipeline.git` — clones the repo with this tutorial's branch checked out.
- [ ] `cd mega-pipeline`

*Already have the repo from L03*
- [ ] `cd mega-pipeline`
- [ ] `git fetch origin` — get the branches you don't have yet.
- [ ] *(extra)* If you want to keep your L03 Dockerfiles, copy them out of the repo first: the checkout silently replaces four of them (G1).
- [ ] `git stash -u` — *(extra)* stashes untracked files too, so the checkout does not abort on `generate_text/Dockerfile` / `generate_text/uv.lock` (G1).
- [ ] `git checkout flexible-workflow` — switch to this tutorial's branch.
- [ ] `git stash` or `git checkout -- .` — only if `git checkout` refuses with "Your local changes would be overwritten" (your L03 edits to `cli.py`, `README.md:48`).
- [ ] `git branch` — confirm: `* flexible-workflow`.
- [ ] `ls transcribe_audio` — *(extra)* `Dockerfile README.md cli.py docker-shell.sh pyproject.toml uv.lock`.

### Mega-pipeline · Service Account & Secrets

*(`README.md:169-203`, plus the folder layout at `README.md:105-119`; §4 A2-A5)*
- [ ] In the GCP console, go to **IAM & Admin → Service accounts**.
- [ ] Create a new service account (e.g. `mega-pipeline-sa`).
- [ ] Grant it **Storage Admin** (`roles/storage.admin`), **Agent Platform User** (`roles/aiplatform.user`; search the role picker for "Agent Platform User", since "Vertex AI User" finds nothing), **Cloud Speech Client** (`roles/speech.client`) and **Cloud Translation API User** (`roles/cloudtranslate.user`). Text-to-Speech needs no role.
- [ ] Under **Keys → Add Key → Create new key**, download a **JSON** key.
- [ ] Save it as `mega-pipeline.json` in a `secrets/` folder one level above the repo: `<your-workspace>/secrets/mega-pipeline.json`.
- [ ] *(extra)* Delete any old `<component>/secrets/` folders left over from L03 (G6).
- [ ] `ls ../../secrets/mega-pipeline.json` — *(extra)* run from a component folder; prints the path.
- [ ] `grep client_email ../../secrets/mega-pipeline.json` — *(extra)* shows `...@<your-project>.iam.gserviceaccount.com`.
- [ ] `gcloud config set project <your-project-id>` — points `gcloud` at your project.
- [ ] `gcloud services enable storage.googleapis.com aiplatform.googleapis.com speech.googleapis.com texttospeech.googleapis.com translate.googleapis.com` — enables all five APIs (console alternative: **APIs & Services → Library**, search each name, **Enable**).
- [ ] `gcloud services list --enabled` — *(extra)* includes the five services.
- [ ] `gcloud storage buckets create gs://<your-bucket> --location=us-central1` — *(extra)* the README gives no command to create your bucket (E5).
- [ ] `gcloud storage cp input-01.mp3 gs://<your-bucket>/input_audios/` — *(extra)* seeds the bucket; name the audio `input-<something>.mp3`, because later stages only pick up `input-*` files.
- [ ] `gcloud storage ls gs://<your-bucket>/input_audios/` — *(extra)* lists an `input-*.mp3`.

### Mega-pipeline · ⚠️ Configure each `cli.py` before you run it

*(`README.md:123-134`; §4 A6)*
- [ ] In all five `cli.py` files, set `gcp_project`, `bucket_name` and `group_name` (`transcribe_audio/cli.py:17-21`, `synthesis_audio_en/cli.py:14-18`, `synthesis_audio/cli.py:14-18`, `generate_text/cli.py:16-20`, `translate_text/cli.py:14-18`).
- [ ] Replace the instructor's values that `generate_text/cli.py` and `translate_text/cli.py` ship with (`"ac215-project"`, `"mega-pipeline-bucket"`, `"pavlos-advanced"`); the `assert` does not catch them (E2).
- [ ] *(extra, optional)* In `translate_text/cli.py:64`, change `target_language="es"` to `"fr"` so the French voice reads French (E3).

### Mega-pipeline · Task A: transcribe_audio

*(`README.md:207-240`; `transcribe_audio/README.md:13-120`; §4 A7)*
- [ ] `cd transcribe_audio` — run every `docker-shell.sh` from inside its component folder.
- [ ] Read the four shipped files (`Dockerfile`, `docker-shell.sh`, `pyproject.toml`, `uv.lock`) before you run anything (`transcribe_audio/README.md:17-26`; §5 excerpts 1-4).
- [ ] `./docker-shell.sh` — build the image locally and run it (default). Prints `Docker Username: dlops, Build Mode: dev-run`, builds `mega-pipeline-transcribe-audio` and drops you at `app@<container-id>:/app$`.
- [ ] `chmod +x docker-shell.sh` — only if the previous command said `Permission denied` (then run it again); normally unnecessary (E12).
- [ ] Windows Git BASH: prefix the command with `winpty` if you see "the input device is not a TTY" (`README.md:226`, `:380`).
- [ ] `MSYS_NO_PATHCONV=1 ./docker-shell.sh` — *(extra)* Windows Git BASH, if it mangles `/secrets` or the `-v` specs (G18); combine with `winpty` if needed.

*Inside the container*
- [ ] `python --version` · `which python` · `echo $GOOGLE_APPLICATION_CREDENTIALS` — *(extra)* Python 3.14.x, `/home/app/.venv/bin/python`, `/secrets/mega-pipeline.json` (*expected*).
- [ ] `ls -l /secrets` — *(extra)* should list `mega-pipeline.json` (G3).
- [ ] `uv add <package>` — only when the component needs a new dependency: updates `pyproject.toml` and `uv.lock` on your host through the mount; commit both, then rebuild with `./docker-shell.sh dev` so the package is baked into the image (`transcribe_audio/README.md:89`; C3). The same note is in every component README.
- [ ] `python cli.py --help` — lists `-d/--download`, `-t/--transcribe`, `-u/--upload` (`transcribe_audio/README.md:97-108`); stops with `AssertionError: Update group name` until `group_name` is set (G2).
- [ ] `python cli.py --download` — wipes local `input_audios/` and pulls every object under `input_audios/` from your bucket.
- [ ] `python cli.py --transcribe` — mp3 → FLAC with ffmpeg, then Speech-to-Text; writes `text_prompts/<group>/<name>.txt`.
- [ ] `python cli.py --upload` — pushes `text_prompts/<group>/input-*.txt`; check `text_prompts/<group_name>/` in the console.
- [ ] `exit` — *(extra)* leaves the container; `--rm` deletes it.

### Mega-pipeline · Task B: generate_text

*(`README.md:242-248`; `generate_text/README.md:62-136`; §4 A8)*
- [ ] `cd ../generate_text` — *(extra)* the next component folder ("you'll `cd` into each one", `README.md:52`).
- [ ] `./docker-shell.sh`
- [ ] `python cli.py --help` — lists `-d/--download`, `-g/--generate`, `-u/--upload` (`generate_text/README.md:113-124`).
- [ ] `python cli.py --download` — downloads `text_prompts/<group>/input-*.txt`.
- [ ] `python cli.py --generate` — calls Gemini on Vertex AI (default `gemini-2.5-flash-lite`); prints a long "Generated text:".
- [ ] `export GEMINI_MODEL=gemini-2.5-flash` — optional model switch (`generate_text/README.md:91-94`), also the fix for a 404 model-not-found; then:
- [ ] `python cli.py --generate` — generates again with that model.
- [ ] `python cli.py --upload` — pushes to `text_paragraphs/<group>/`.
- [ ] `exit` — *(extra)*

### Mega-pipeline · Task C: synthesis_audio_en

*(`README.md:250-257`; `synthesis_audio_en/README.md:110-121`; §4 A9)*
- [ ] `cd ../synthesis_audio_en` — *(extra)*
- [ ] `./docker-shell.sh`
- [ ] `python cli.py --help` — lists `-d/--download`, `-s/--synthesis` (`synthesis_audio_en/README.md:98-108`).
- [ ] `python cli.py --download` — downloads the generated paragraphs.
- [ ] `python cli.py --synthesis` — long-audio Text-to-Speech (`en-US-Standard-B`) writes `text_audios/<group>/input-*.mp3` straight into the bucket; there is no `--upload` step.
- [ ] `exit` — *(extra)*

### Mega-pipeline · Task D: translate_text

*(`README.md:259-265`; `translate_text/README.md:126-136`; §4 A10)*
- [ ] `cd ../translate_text` — *(extra)*
- [ ] `./docker-shell.sh`
- [ ] `python cli.py --help` — lists `-d/--download`, `-t/--translate`, `-u/--upload`; the description still says "Translate English to French" (`translate_text/README.md:113-124`, E3).
- [ ] `python cli.py --download` — downloads the generated paragraphs.
- [ ] `python cli.py --translate` — Cloud Translation v2; the text is Spanish unless you changed `target_language` (E3).
- [ ] `python cli.py --upload` — pushes to `text_translated/<group>/`.
- [ ] `exit` — *(extra)*

### Mega-pipeline · Task E: synthesis_audio

*(`README.md:267-274`; `synthesis_audio/README.md:110-135`; §4 A11)*
- [ ] `cd ../synthesis_audio` — *(extra)*
- [ ] `./docker-shell.sh`
- [ ] `python cli.py --help` — lists `-d/--download`, `-s/--synthesis` (`synthesis_audio/README.md:98-108`).
- [ ] `python cli.py --download` — downloads the translated text.
- [ ] `python cli.py --synthesis` — Text-to-Speech with `fr-FR-Standard-C`; writes `output_audios/<group>/input-*.mp3`, the final output of the pipeline.
- [ ] Optional ElevenLabs bonus (`synthesis_audio/README.md:125-135`): create an ElevenLabs API key and put a file `11lab_api_key.txt` containing `XI_API_KEY=<API_KEY>` in your `secrets/` folder. Read E10 first: `cli_11.py` reads it from `secrets/` relative to `/app` and hard-codes the instructor's bucket.
- [ ] `exit` — *(extra)*

### Mega-pipeline · Other `docker-shell.sh` modes and OPTIONAL: Publish the container

*(`README.md:207-216`, `:76`; each component README's "OPTIONAL: Publish the container", e.g. `transcribe_audio/README.md:124-132`; §4 A12)*
- [ ] `./docker-shell.sh dev` — only build the local image.
- [ ] `./docker-shell.sh run` — run from a prebuilt image: the local `mega-pipeline-<component>` if it exists, else `dlops/mega-pipeline-<component>:latest`, a Feb-2025 Python 3.8 / Pipenv build (E1, G7).
- [ ] Change `DOCKER_USERNAME="dlops"` (`docker-shell.sh:13`) to your own Docker Hub namespace, and create an access token under Docker Hub → Security.
- [ ] *(extra)* Before any push: delete in-component `secrets/` folders, or add a `.dockerignore` with `secrets/` and the data folders (G6).
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — log in to Docker Hub.
- [ ] `docker login -u <USER NAME> --password-stdin` — *(extra)* the same, without the token landing in your shell history.
- [ ] `./docker-shell.sh prod` — build multi-arch (amd64 + arm64) and push to Docker Hub; ends with `Production build complete and pushed to registry`.
- [ ] `docker buildx ls` — *(extra)* after `prod`, shows that `multi-arch` is still the selected builder (G8).
- [ ] `docker buildx use default` — *(extra)* switch back (on Docker Desktop the builder may be called `desktop-linux`), or `docker buildx rm multi-arch` (G8).

### Mega-pipeline · Clean up *(extra)*

*(§2, §4 A13)*
- [ ] `exit` in each container shell.
- [ ] `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=<sa-email>` — deletes the SA key when you are done (or console **IAM → Service accounts → Keys**).
- [ ] `gcloud storage rm -r gs://<your-bucket>` — when the course no longer needs the bucket.
- [ ] `docker image rm mega-pipeline-transcribe-audio mega-pipeline-generate-text mega-pipeline-synthesis-audio-en mega-pipeline-translate-text mega-pipeline-synthesis-audio` — frees the disk the five images use.
- [ ] `docker buildx rm multi-arch` — only if you ran `./docker-shell.sh prod`.

### port_toy · Prerequisites

*(`port_toy/README.md:20-30`; §4 B1)*
- [ ] `docker run hello-world` — make sure Docker Desktop is running: "Hello from Docker!".

### port_toy · Step 1: Set up the network by hand

*(`port_toy/README.md:75-183`; §4 B1-B7)*
- [ ] Clone or download the [repository](https://github.com/dlops-io/port_toy).
- [ ] `git clone https://github.com/dlops-io/port_toy.git` — *(extra)* the usual clone command; the README gives none.
- [ ] `cd port_toy`
- [ ] `docker network create toynet` — creates the user-defined bridge network (own subnet and DNS); prints the network id.
- [ ] `docker build -t toy-processor ./processor` — builds the processor image.
- [ ] `docker build -t toy-gateway ./gateway` — builds the gateway image.
- [ ] `docker image ls 'toy-*'` — *(extra)* shows both images (quote the pattern so the shell does not glob it).
- [ ] `docker run -d --name processor --network toynet -e PORT=9200 toy-processor` — starts the processor, detached, unpublished, listening on 9200.
- [ ] `docker run -d --name gateway --network toynet -p 127.0.0.1:8090:9100 -e PROCESSOR_HOST=processor -e PROCESSOR_PORT=9200 toy-gateway` — starts the gateway; host `127.0.0.1:8090` → container `9100`.
- [ ] `docker logs processor` — `processor listening on port 9200 (internal only)`.
- [ ] `docker logs gateway` — `gateway listening on port 9100  →  open http://localhost:8090` (two spaces around the arrow).
- [ ] Open http://localhost:8090, type a message, click **Send** — the upper-cased text plus three port lines; the first and third numbers match (e.g. `44456`), the second is `9200`.

### port_toy · Step 2: Check the ports

*(`port_toy/README.md:189-325`; §4 B8-B10)*
- [ ] `docker ps` — the gateway shows `127.0.0.1:8090->9100/tcp`; the processor's PORTS column is empty.
- [ ] `curl http://localhost:8090` — returns the HTML page (`<!DOCTYPE html>` …).
- [ ] `curl --max-time 3 http://localhost:9200/health` — fails, e.g. `curl: (7) Failed to connect to localhost port 9200 ...` (*expected*): the processor is not published.
- [ ] `lsof -i :9200` — *(extra)* only if the previous command unexpectedly succeeds: shows which program on your laptop owns 9200 (G14).
- [ ] `docker exec gateway curl http://processor:9200/health` — `ok`: the name resolves through Docker DNS (no trailing newline).
- [ ] `docker exec gateway curl --max-time 3 http://localhost:9200/health` — fails (curl exit 7, *expected*): `localhost` is the gateway itself.

### port_toy · Step 3: Change the ports

*(`port_toy/README.md:331-420`; §4 B11-B14)*
- [ ] `docker rm -f gateway` — removes the running gateway.
- [ ] `docker run -d --name gateway --network toynet -p 127.0.0.1:8095:9100 -e PROCESSOR_HOST=processor -e PROCESSOR_PORT=9200 toy-gateway` — new host port: http://localhost:8095 works, :8090 no longer does; the log banner still says 8090 (E15).
- [ ] `docker rm -f processor` — removes the processor.
- [ ] `docker run -d --name processor --network toynet -e PORT=9300 toy-processor` — moves the processor to 9300. Send from the browser (on :8095): "It should fail", but the page simply does not update (G13).
- [ ] `docker logs -f gateway` — *(extra)* watch the traceback ending in `ConnectionRefusedError: [Errno 111] Connection refused` while you click Send; `Ctrl+C` stops following.
- [ ] `docker rm -f gateway`
- [ ] `docker run -d --name gateway --network toynet -p 127.0.0.1:8090:9100 -e PROCESSOR_HOST=processor -e PROCESSOR_PORT=9300 toy-gateway` — re-points the gateway: :8090 works again, and the middle port line shows `9300`.
- [ ] `docker rm -f gateway processor` — clean up before Compose: removes both containers.
- [ ] `docker network rm toynet` — removes the network. Skipping these two makes Step 4 fail (G11).

### port_toy · Step 4: Run with Compose

*(`port_toy/README.md:426-529`; §4 B15-B17)*
- [ ] `docker compose up` — builds `port_toy-gateway` and `port_toy-processor`, creates `toynet`, starts the processor then the gateway, and streams both logs; http://localhost:8090 works.
- [ ] `docker network ls` — *(Handy commands)* in another terminal: lists `toynet`.
- [ ] `docker compose exec gateway curl ...` — the Compose form of `docker exec gateway curl ...` from the "Compare the commands" table (`port_toy/README.md:478-484`), e.g. with `http://processor:9200/health`; that table also maps `docker ps` → `docker compose ps` and `rm -f` + `network rm` → `docker compose down`.
- [ ] Repeat a port experiment in `docker-compose.yml` (`port_toy/README.md:487`), e.g. change the host port under `ports:`; or edit `gateway/index.html`, which is live through the bind mount and re-read on every page load.
- [ ] `docker compose up -d` — re-applies in the background, recreating only the services whose configuration changed.
- [ ] `docker compose up -d --build` — rebuilds the images first; needed after editing `processor.py`.
- [ ] `docker compose restart gateway` — *(extra)* needed after editing `gateway.py`.
- [ ] Press `Ctrl+C` if Compose is running in your terminal — stops the containers (can take about 10 s per container, G12).
- [ ] `docker compose down` — removes the containers and the Compose-managed network; the images remain.
- [ ] `docker compose ps -a` — empty after `down`; after `Ctrl+C` alone it lists both containers as `Exited`.

### port_toy · Handy commands

*(`port_toy/README.md:557-576`; the ones not already used above)*
- [ ] `docker exec -it gateway sh` — opens an interactive shell in the gateway.
- [ ] `docker compose ps` — lists the project's running containers.
- [ ] `docker compose logs -f gateway` — follows the gateway's logs (G13).
- [ ] `docker compose exec gateway sh` — opens a shell in the gateway (Compose).
- [ ] `docker network inspect toynet` — shows the network's containers and IP addresses.

### port_toy · Clean up *(extra)*

*(§2)*
- [ ] `docker compose down` — in `port_toy/`, if the app is still up.
- [ ] `docker image rm toy-gateway toy-processor port_toy-gateway port_toy-processor` — removes the by-hand and Compose-built images (the Compose names are *expected*).

---

## 1. What you build

This lecture has two independent tutorials.

**(A) Mega-pipeline, flexible-workflow branch.** You re-run the five-stage podcast pipeline from L03 (transcribe → generate → synthesize EN, translate → synthesize FR), this time the way a team would ship it:
- **Your own resources.** You use your own GCP bucket and your own service account (SA) with explicit IAM roles.
- **Key outside the repo.** The SA's JSON key lives in a `secrets/` folder *next to* the repo. It is mounted into each container at runtime, never baked into an image.
- **Committed tooling.** Each component ships a committed `Dockerfile`, `pyproject.toml` and `uv.lock`, plus a `docker-shell.sh` wrapper with four modes:
  - build-and-run (default)
  - build only (`dev`)
  - run a prebuilt image, falling back to Docker Hub (`run`)
  - build multi-arch and push (`prod`)

You write no Dockerfile this time. You read them, configure three variables per `cli.py`, and drive each container's CLI. The stages still talk only through the bucket; there are no ports and no container networks in part A.

**(B) port_toy.** A deliberately tiny two-container web app (Python standard library only, no GCP).
- A **gateway** serves a page on container port 9100, published to your laptop as `127.0.0.1:8090`.
- It forwards text to a **processor** on container port 9200. That port is not published and is reached by the DNS name `processor` on a user-defined bridge network `toynet`.
- You wire it by hand with `docker network create` / `docker run -p` / `-e`, break it by changing ports, and then replace all of it with one `docker-compose.yml`.

```
(A) MEGA-PIPELINE, flexible-workflow            [laptop, e.g. ~/Desktop/AC215 = <your-workspace>]
+--------------------------------------------------------------------------------------------------+
| <your-workspace>/                                                                                 |
|   secrets/mega-pipeline.json   <- YOUR SA key (outside the repo, never in Git)                    |
|   mega-pipeline/  (git checkout flexible-workflow)                                                |
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
|  |   /home/app/.venv  <- baked into the image by `RUN uv sync` (Python 3.14)       |              |
|  |   app@...:/app$ python cli.py -d | -t/-g/-s | -u                                |              |
|  +----------|--------------------------------------------------------^------------+              |
+-------------|--------------------------------------------------------|-----------------------------+
              | HTTPS / gRPC with an OAuth token that google-auth       | prod: docker buildx build
              | mints from /secrets/mega-pipeline.json                  |  --platform linux/amd64,linux/arm64 --push
              v                                                         v
 GOOGLE CLOUD - your project                              DOCKER HUB  $DOCKER_USERNAME/mega-pipeline-<component>
 +-------------------------------------------------+       (script default "dlops"; dlops/...:latest is a
 | GCS bucket <your-bucket>                        |        Feb-2025 Python 3.8 / Pipenv build, see E1)
 |   input_audios/*.mp3                            |                 ^
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
   browser --> http://localhost:8090 ----+          curl http://localhost:9200  -->  refused (nothing published)
                                         |  published: 127.0.0.1:8090 -> 9100/tcp  (-p / ports:)
 +---------------------------------------|---- user-defined bridge network "toynet" ------------------+
 |  Docker embedded DNS: "gateway" -> 172.x.y.a     "processor" -> 172.x.y.b                          |
 |                                       v                                                            |
 |  [gateway]  own netns, own localhost         [processor]  own netns, own localhost                 |
 |   python -u gateway.py                        python -u processor.py                               |
 |   listens 0.0.0.0:9100 ($PORT, default 9100)  listens 0.0.0.0:9200 ($PORT=9200)                     |
 |   GET /  -> index.html                        GET /health -> "ok"                                  |
 |   POST / -> http://$PROCESSOR_HOST:$PROCESSOR_PORT  ---->  POST / -> {"upper", "listen_port",       |
 |            src port = ephemeral (e.g. 44456)                          "sender_port"}                |
 |   (Compose only: ./gateway bind-mounted at /app)                                                    |
 +----------------------------------------------------------------------------------------------------+
   Step 1-3: docker network create / docker build / docker run ... by hand
   Step 4:   docker compose up   (same thing, declared in docker-compose.yml)
```

---

## 2. Prerequisites and costs

### Local installs (both tutorials)
- **Docker Desktop**, with Compose v2 (`docker compose`) and Buildx. The port_toy README asks you to check it with `docker run hello-world` (`port_toy/README.md:26-30`). port_toy needs nothing else: "You do not need a GCP account or Python installed on your laptop." (`port_toy/README.md:24`)
- **Git** and a bash shell. On Windows use Git BASH, and prefix `winpty` if you see "the input device is not a TTY" (`mega-pipeline/README.md:374-380`).
- *Optional:* the **`gcloud` CLI**, for the one-shot API-enable command (`mega-pipeline/README.md:191-199`). You can do everything in the console instead.
- **Not needed on the host:** Python and `uv`. Both live inside the images (`mega-pipeline/transcribe_audio/Dockerfile:2`, `:29`).

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
   - Example: if you cloned into `/Users/conny/Desktop/AC215/mega-pipeline`, the key must be at `/Users/conny/Desktop/AC215/secrets/mega-pipeline.json`.
   - The same `AC215/secrets/` folder is also where `llm-rag` (L05) and `cheese-app-v0` (L10) look for their keys: `llm-rag/docker-compose.yml:11` mounts `../secrets:/secrets`, and `cheese-app-v0/api-service/docker-shell.sh:8` uses `$(pwd)/../../secrets/`.
5. **Your own GCS bucket, seeded with input audio.** The README says you own one (`mega-pipeline/README.md:62`, `:150`), but it gives **no command** to create it or to fill `input_audios/` (Errata E5). Not in the README, but standard:
   ```bash
   gcloud storage buckets create gs://<your-bucket> --location=us-central1
   gcloud storage cp input-01.mp3 gs://<your-bucket>/input_audios/
   ```
   - Name the audio `input-<something>.mp3`. Transcribe's upload only picks up `input-*.txt` (`mega-pipeline/transcribe_audio/cli.py:102`), and every later stage only downloads `input-*.txt` (e.g. `mega-pipeline/generate_text/cli.py:43`).
6. **Environment variables the code reads**
   - `GOOGLE_APPLICATION_CREDENTIALS` is set by the script, as above.
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
| SA key | a long-lived credential (a security liability, not a cost) | delete it when done: console **IAM → Service accounts → Keys**, or `gcloud iam service-accounts keys delete <KEY_ID> --iam-account=<sa-email>` |
| Docker Hub | free for public repos | delete pushed repos in the Hub UI if they contain anything sensitive (G6) |

Local cleanup (not billable, but disk use is large; each image carries `build-essential` and, for transcribe, `ffmpeg`):
```bash
docker image rm mega-pipeline-transcribe-audio mega-pipeline-generate-text mega-pipeline-synthesis-audio-en mega-pipeline-translate-text mega-pipeline-synthesis-audio
docker buildx rm multi-arch          # only if you ran ./docker-shell.sh prod
docker compose down                  # in port_toy/, then:
docker image rm toy-gateway toy-processor port_toy-gateway port_toy-processor
```
The last two names are what Compose v2 calls images it builds without an `image:` key (`<project>-<service>`), where the project name is the folder name, `port_toy`. *Expected*; not run.

---

## 3. Concepts this tutorial teaches

### C1. The flexible workflow: build the image yourself, or pull a prebuilt one
- **Explanation.** An image can reach your machine in two ways:
  - **Build it** from a recipe that lives in Git: `Dockerfile` + `pyproject.toml` + `uv.lock`.
  - **Pull it** ready-made from a registry (Docker Hub).

  Early in a project everyone builds, because the recipe changes daily. Later, one person publishes images and everyone else pulls (`mega-pipeline/README.md:67-74`). `docker-shell.sh` covers both: no argument means build then run, `dev` builds, `run` runs (local if present, else registry), `prod` builds multi-arch and pushes (`mega-pipeline/transcribe_audio/docker-shell.sh:28-97`).
- **Mental model.** The Dockerfile plus lock file is the *source*. The image is the *compiled artifact*. A tag like `dlops/mega-pipeline-transcribe-audio` is a *pointer* to some artifact, built at some time, from some commit. The tag does not promise that the artifact came from the commit you have checked out.
- **Analogy.** A recipe card in a shared binder (Git) versus frozen meals in the shop freezer (registry). The frozen meal is fast, but it was cooked from whatever version of the recipe existed on the day it was frozen.
- **Common misconception.** "`./docker-shell.sh run` gives me exactly what this branch's Dockerfile describes." It first uses any local image named `mega-pipeline-<component>`, however old (`docker-shell.sh:83-85`). Only if there is none does it fall back to `$DOCKER_USERNAME/mega-pipeline-<component>`, i.e. whatever `latest` was last pushed (or a copy you pulled earlier). For `dlops/*` that is a February-2025 Python 3.8 / Pipenv build (Errata E1). And because the script bind-mounts your folder over `/app` (`docker-shell.sh:93`), the code is *yours* while the environment is *theirs*.

### C2. A wrapper script as executable documentation
- **Explanation.** `docker run` lines grow: an image name, a container name, two bind mounts, an env var, `-ti`, `--rm`. And `prod` needs three Buildx commands. Putting them in a script that every teammate runs from the same relative location makes the workflow repeatable (`mega-pipeline/README.md:65`).
  - `set -e` (`docker-shell.sh:4`) aborts on the first failing command.
  - `$(pwd)` (`:8-9`) ties all paths to *where you run it from*.
- **Mental model.** The script is just a handful of `docker` commands (`docker build`, `docker image inspect`, `docker run`, and the `docker buildx` inspect/rm/create/build sequence for `prod`), chosen by a `case` on `$1`. Read it top to bottom once, and you can always run the commands by hand.
- **Analogy.** A cockpit checklist: no new physics, just the right switches in the right order every time.
- **Common misconception.** "I can run it from anywhere." No. `BASE_DIR` and `SECRETS_DIR` are computed from your *current directory* (`:8-9`), and `docker build ... .` uses the current folder as the build context (`:75`). Run it from inside the component folder.

### C3. Bind mounts shadow the image's `/app`, so the venv lives outside it
- **Explanation.**
  - At build time the Dockerfile copies the component folder into `/app` (`Dockerfile:39`) and runs `uv sync` (`:41`). Because `UV_PROJECT_ENVIRONMENT=/home/app/.venv` (`:17`), the venv lands in `/home/app/.venv`, **not** in `/app/.venv`.
  - At run time `-v "$BASE_DIR":/app` (`docker-shell.sh:93`) lays your *live host folder* over `/app`. The image's copy of the code becomes invisible, but `/home/app/.venv` is untouched.
  - Results: edits in VS Code show up instantly, and files the CLI writes (`input_audios/`, `text_prompts/...`) appear on your host. The venv survives because it is outside the mount point.
- **Mental model.** A container's filesystem is a stack of read-only image layers plus a thin writable layer. A bind mount is a window cut into that stack at one path: through it you see the host, not the image.
- **Analogy.** Laying a transparent sheet with your own notes over one page of a printed book. That page now shows your notes. Every other page still shows the print.
- **Common misconception.** "If I `uv add` a package inside the container, it is installed from now on." `uv add` rewrites `pyproject.toml` and `uv.lock` *on the host* through the mount, but the package is installed into `/home/app/.venv` in the container's writable layer, which `--rm` throws away on exit. You must rebuild (`./docker-shell.sh dev` or the default mode) to bake it in. The README says so (`mega-pipeline/transcribe_audio/README.md:89`), but `run` mode skips the rebuild.

### C4. Runtime secrets and machine identity (service account → IAM → API)
- **Explanation.**
  - The code authenticates as a **service account**, an identity for software (`mega-pipeline/README.md:171`).
  - Google client libraries use **Application Default Credentials**: if `GOOGLE_APPLICATION_CREDENTIALS` names a JSON key file, they use it to mint short-lived OAuth access tokens.
  - In this branch the key file is **mounted** at `/secrets` and the env var is passed with `-e` at `docker run` time (`docker-shell.sh:94-95`).
  - In L03 it was **baked** into the Dockerfile as `ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` (`main:README.md:194-195`), and the key sat inside each component folder (`main:README.md:97`).

  Two separate gates must open: the API must be **enabled** in the project, and the SA must hold a **role** that grants the permission (`mega-pipeline/README.md:187`).
- **Mental model.** Three independent layers:
  - *Who am I?* The key file.
  - *What may I do?* IAM roles on the project or bucket.
  - *Is the service even switched on?* The API is enabled.

  A failure can come from any of them. A missing or unreadable key fails before any request is sent (`DefaultCredentialsError`); a missing role or a disabled API comes back from Google as a 403 (`PERMISSION_DENIED`, with `SERVICE_DISABLED` for the latter).
- **Analogy.** A hotel key card (the key file) is useless if it is not programmed for your floor (the role), or if the gym is closed for the season (the API is not enabled).
- **Common misconception.** "`.gitignore` keeps my key safe." `.gitignore` only affects Git. `docker build` uses `.dockerignore`, and **none of the branches have one**. A `secrets/` folder left *inside* a component folder from L03 is copied into the image by `COPY --chown=app:app . ./` (`Dockerfile:39`), and `prod` pushes it to Docker Hub (Gotcha G6).

### C5. Multi-architecture images
- **Explanation.** Images contain CPU-specific binaries. An Apple-Silicon Mac builds `linux/arm64` by default, while most cloud VMs are `linux/amd64`.
  - `docker buildx build --platform linux/amd64,linux/arm64 --push` (`docker-shell.sh:66`) builds both variants (one natively, the other under QEMU emulation) and pushes an **image index** (a.k.a. manifest list): one tag pointing at both. The existing `dlops/*` tags are exactly this: an OCI index with amd64, arm64 and two attestation entries.
  - `docker pull` and `docker run` then pick the variant that matches the host.
  - The script first (re)creates a builder named `multi-arch` (`docker-shell.sh:55-62`). `docker buildx create` without `--driver` uses the `docker-container` driver, i.e. BuildKit running in its own container; `--driver-opt network=host` gives that container the host's network. The default builder cannot produce multi-platform indexes in every setup; a container-driver builder can.
- **Mental model.** A tag is a signpost with one arrow per CPU architecture.
- **Analogy.** A plug adapter kit: one product box (the tag), with a different plug inside for each country (architecture). The shop hands you the one that fits your wall.
- **Common misconception.** "An image runs anywhere Docker runs." It runs anywhere *its architecture* runs, unless the host emulates the other one, slowly. Also, the `multi-arch` builder stays selected after `prod` (`--use`, `:62`), which changes how later plain builds behave (Gotcha G8).

### C6. Container networks and service-name DNS
- **Explanation.**
  - Every container gets its own **network namespace**: its own interfaces, its own routing table, its own `localhost`.
  - A **user-defined bridge network** (`docker network create toynet`, `port_toy/README.md:92`) connects containers like a virtual switch. Docker runs an **embedded DNS server** for it, so a container's name resolves to its current IP on that network. That is why `http://processor:9200` works (`port_toy/README.md:171-181`).
  - Compose creates such a network automatically and makes each **service name** resolvable. It is named `toynet` here because of `name: toynet` (`port_toy/docker-compose.yml:37-39`); otherwise it would be `<project>_default` (`port_toy/README.md:473`).
- **Mental model.** Each container is a separate little computer. The network is a LAN with its own phone book, and the phone book is rewritten whenever a container (re)starts and gets a new IP.
- **Analogy.** An office floor: everyone has their own desk phone (namespace). The internal directory lets you dial "processor" instead of memorizing extension 172.18.0.3.
- **Common misconception.** "Containers can always find each other by name." Only on a user-defined network (or a Compose network). On Docker's legacy default `bridge` network (no `--network`) name resolution between containers does not work (Exercise 3). Second misconception: "`localhost` inside the gateway is my laptop." It is the gateway itself (`port_toy/README.md:290`, `:546`).

### C7. Ports: listening vs published vs exposed vs source; host vs container; bind address
- **Listening port.** A server binds `(address, port)` and accepts connections. Both toy servers bind `("", port)`, meaning all interfaces of their namespace (`gateway.py:52`, `processor.py:43`), on ports read from `$PORT` (`gateway.py:51`, `processor.py:42`).
- **Published port** (`-p 127.0.0.1:8090:9100`, or `ports:`). Docker forwards connections that reach a *host* address and port into a *container* port. The order is `ip:host:container`: "host first" (`port_toy/README.md:224-230`). `127.0.0.1` keeps it reachable from your machine only (`:232-244`).
- **`EXPOSE`.** Only metadata in the image: "Documents a container port. It does not publish it." (`port_toy/README.md:545`). Neither toy Dockerfile uses it, which is why the processor's `PORTS` column is empty (`:211`).
- **Source (ephemeral) port.** The caller's side of a TCP connection, chosen by the OS. Container-to-container traffic on the same bridge is not NATed, so the processor sees the same source port the gateway was given: "gateway sent from port" = "processor saw it arrive from" (`port_toy/README.md:153-169`; read by `gateway.py:38` and `processor.py:32`).
- **Mental model.** Every namespace has its own full set of 65,535 port numbers. Two containers can both listen on 9100 without conflict. Only *host* ports can collide, as in "port is already allocated" (`port_toy/README.md:550`).
- **Analogy.** An apartment building. Every flat has a room 9100. The building's street door 8090 (published) leads to flat *gateway*, room 9100. The processor's flat has no street door; you can only reach it from the inside corridor (the network).
- **Common misconception.** "`EXPOSE` (or the processor listening on 9200) means `localhost:9200` works on my laptop." It does not; only `-p`/`ports:` creates a host-side door. Second misconception: binding to `127.0.0.1` *inside* the container is "safer". It makes the published port useless, because forwarded traffic arrives on the container's network interface, not on its loopback (Exercise 4).

### C8. Docker Compose: the same commands, declared once
- **Explanation.** `docker-compose.yml` declares services, how to build them, their ports, environment, volumes, networks and start order. `docker compose up` creates the network, builds images if needed, and starts containers; `docker compose down` removes containers and the network (`port_toy/README.md:462-473`, `:505-529`).
  - Mapping: `-p` ↔ `ports:`, `-e` ↔ `environment:`, `docker ps` ↔ `docker compose ps`, and `rm -f` + `network rm` ↔ `down` (`port_toy/README.md:478-484`).
  - This compose file adds two things the by-hand run did not have:
    - a live bind mount of `./gateway:/app` (`docker-compose.yml:17-18`)
    - `depends_on` (`:22-23`), which orders *start-up* only; it does not wait for readiness
- **Mental model.** Compose is a reconciler. You describe the desired state; `up` makes reality match, recreating only the services whose config changed.
- **Analogy.** A restaurant order ticket (YAML) versus shouting instructions to each cook (individual `docker run` commands).
- **Common misconception.** "`Ctrl+C` cleans up." It only *stops* the containers; they and the network remain until `docker compose down` (`port_toy/README.md:517-529`).

---

## 4. Step-by-step walkthrough

Each step gives the action, what happens under the hood, a checkpoint and what to do if it fails. Lines marked *expected* are inferred from the code; nothing was built or run with Docker (see the sources box at the top).

### Part A — mega-pipeline, `flexible-workflow`

**A1. Get the branch.**
```bash
git clone --branch flexible-workflow https://github.com/dlops-io/mega-pipeline.git
cd mega-pipeline
```
or, if you still have the L03 clone (`mega-pipeline/README.md:41-46`):
```bash
cd mega-pipeline
git fetch origin                      # get the branches you don't have yet
git checkout flexible-workflow        # switch to this tutorial's branch
git branch                            # confirm: * flexible-workflow
```
- **Under the hood.** `git checkout flexible-workflow` finds `origin/flexible-workflow` and creates a local tracking branch.
  - Tracked files are replaced: every component gains a `Dockerfile`, `docker-shell.sh` (mode 100755) and `uv.lock`; four gain a `pyproject.toml` (`generate_text`'s is modified); `generate_text` gains a `.gitignore` (the other four are modified); `generate_text/main.py` and all five `*/secrets/.gitkeep` are deleted (diff in §7).
- **Checkpoint.** `git branch` shows `* flexible-workflow`, and `ls transcribe_audio` lists `Dockerfile README.md cli.py docker-shell.sh pyproject.toml uv.lock`.
- **If it fails.**
  - "Your local changes would be overwritten": your edits to tracked files (e.g. `cli.py`). Use `git stash` or `git checkout -- .`, as the README says (`mega-pipeline/README.md:48`).
  - "The following untracked working tree files would be overwritten by checkout: generate_text/Dockerfile generate_text/uv.lock": the README does **not** cover this. Move those files away, or `git stash -u` (Gotcha G1).
- **README vs reality.** The README says "Your `secrets/` folder ... stay[s] put" (`:50`). True, and that is now a *risk*, because the old key is still inside each component folder (G6).

*Order note.* The README presents the folder layout (`:105-119`), "Configure each `cli.py`" (`:123-134`) and the bucket (`:148-160`) **before** "Service Account & Secrets" (`:169-203`). The steps below put the cloud prerequisites first (SA → key → APIs → bucket → `cli.py`), because each later step depends on the earlier ones; no README step is dropped.

**A2. Create the service account, grant roles, download the key** (console steps, `mega-pipeline/README.md:175-183`).
1. IAM & Admin → Service accounts.
2. Create one (e.g. `mega-pipeline-sa`).
3. Grant the four roles listed in §2.
4. Keys → Add Key → Create new key (JSON).
5. Save as `mega-pipeline.json` in the outer `secrets/` (A3).
- **Under the hood.** A key file contains the SA email, the project id and an RSA private key. google-auth signs a JWT with it and exchanges it for an access token.
- **Checkpoint** (once the key is in place, A3). `grep client_email ../../secrets/mega-pipeline.json` shows `...@<your-project>.iam.gserviceaccount.com`.
- **If it fails.** In the role picker, "Vertex AI User" no longer matches; search **"Agent Platform User"** (`mega-pipeline/README.md:179`). The `generate_text` README still says "Vertex AI User" (`generate_text/README.md:46`, Errata E9).

**A3. Put your key where the scripts look.**
- **Action:** create `<your-workspace>/secrets/` *beside* `mega-pipeline/` and save the key as `mega-pipeline.json` (`mega-pipeline/README.md:105-119`, `:183`).
- **Then delete any old `<component>/secrets/` folders** left over from L03 (`main:README.md:97` put a copy in each component).
- **Files.** `mega-pipeline/transcribe_audio/docker-shell.sh:9-10` (`SECRETS_DIR`, `GOOGLE_APPLICATION_CREDENTIALS`) and `:94-95` (mount and env).
- **Checkpoint.** From a component folder, `ls ../../secrets/mega-pipeline.json` prints the path.
- **If it fails.** Covered in A7: `DefaultCredentialsError ... was not found` means the key is not at `../../secrets/` relative to the component folder.

**A4. Enable the APIs** (command in §2, `mega-pipeline/README.md:192-198`).
- **Checkpoint.** `gcloud services list --enabled` includes the five services.
- **If it fails.** You see a `PERMISSION_DENIED ... SERVICE_DISABLED` style error from a CLI later. "Enabling the API and granting the role are two separate steps." (`:187`)

**A5. Create and seed your bucket.** Not in the README (Errata E5); commands in §2 item 5.
- The README's appendix does show Python for uploading a file into `input_audios/` (`mega-pipeline/README.md:301-317`: `bucket.blob("input_audios/test.mp3").upload_from_filename(...)`), but nothing for creating the bucket. If you use it, name the object `input-<something>.mp3`, not `test.mp3` (E5).
- **Checkpoint.** `gcloud storage ls gs://<your-bucket>/input_audios/` lists an `input-*.mp3`.

**A6. Configure each `cli.py`.** In every component set `gcp_project`, `bucket_name`, `group_name` (`mega-pipeline/README.md:123-134`).

| File | Lines | Shipped values |
|---|---|---|
| `transcribe_audio/cli.py` | `:17-21` | `""` |
| `synthesis_audio_en/cli.py` | `:14-18` | `""` |
| `synthesis_audio/cli.py` | `:14-18` | `""` |
| `generate_text/cli.py` | `:16-20` | **instructor's real values** `"ac215-project"`, `"mega-pipeline-bucket"`, `"pavlos-advanced"` |
| `translate_text/cli.py` | `:14-18` | the same instructor values |

- **Under the hood.** `assert group_name!="", "Update group name"` runs at import time (e.g. `transcribe_audio/cli.py:24`), so even `python cli.py --help` fails until you set it.
  - In `generate_text` and `translate_text` the assert **passes with the instructor's values** (E2). If you forget those two files, you will call the instructor's project and bucket and get 403s.
- **Optional, translate:** `target_language` is `"es"` in code (`translate_text/cli.py:64`) but the next stage uses a **French** voice (`synthesis_audio/cli.py:48-49`). Set it to `"fr"` to match the README story (E3).

**A7. Task A: transcribe_audio.**
```bash
./docker-shell.sh          # build the image locally and run it (default)
```
(`mega-pipeline/README.md:212`, from inside `transcribe_audio/`). If the shell says `Permission denied`, run `chmod +x docker-shell.sh` (`mega-pipeline/README.md:220-224`; normally unnecessary, E12). On Windows Git BASH, prefix `winpty` if you see "the input device is not a TTY" (`:226`; see also G18). Then, inside the container (`mega-pipeline/README.md:236-240`):
```bash
python cli.py --download
python cli.py --transcribe
python cli.py --upload
```
- **Under the hood.**
  1. The script prints `Docker Username: dlops, Build Mode: dev-run` (`docker-shell.sh:48`).
  2. It builds `mega-pipeline-transcribe-audio` from `Dockerfile` with the component folder as build context (`:75`), then prints `Run Docker container...` and `Using local image...` (`:80`, `:84`).
  3. It runs `docker run --rm --name mega-pipeline-transcribe-audio -ti -v "$BASE_DIR":/app -v "$SECRETS_DIR":/secrets -e GOOGLE_APPLICATION_CREDENTIALS=... mega-pipeline-transcribe-audio` (`:92-96`).
  4. ENTRYPOINT/CMD start `bash -c "source /home/app/.venv/bin/activate && exec bash"` (`Dockerfile:44-46`).
  5. Inside, the three CLI commands do the following:
     - `--download` wipes local `input_audios/` and pulls every object under `input_audios/` (`cli.py:32-46`). This prefix is shared and not scoped by group.
     - `--transcribe` converts each mp3 to FLAC with ffmpeg (which is why this Dockerfile alone installs `ffmpeg`, `Dockerfile:4`), calls `long_running_recognize` with a 90 s timeout, keeps only `response.results[0]`, and writes `text_prompts/<group>/<name>.txt` (`cli.py:49-90`). Existing outputs are skipped (`:64-65`).
     - `--upload` pushes `text_prompts/<group>/input-*.txt` (`cli.py:93-109`).
- **Checkpoint.**
  - The prompt looks like `app@<container-id>:/app$`.
  - `python --version` shows Python 3.14.x, `which python` shows `/home/app/.venv/bin/python`, and `echo $GOOGLE_APPLICATION_CREDENTIALS` shows `/secrets/mega-pipeline.json` (*expected*).
  - After `-u`, the console shows `text_prompts/<group>/input-*.txt` in your bucket (`transcribe_audio/README.md:120`). On the host, `transcribe_audio/input_audios/` and `transcribe_audio/text_prompts/` now exist (ignored by `transcribe_audio/.gitignore:5-6`).
- **If it fails.**

  | Error | Cause | Fix |
  |---|---|---|
  | `AssertionError: Update group name` | `group_name` not set | set it (A6) |
  | `google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.` | key not at `../../secrets/` | G3 |
  | `403 ... does not have storage.buckets.get access` | `get_bucket` (`cli.py:40`) needs a bucket-level permission that "Storage Object Admin" lacks | use Storage Admin |
  | `Conflict. The container name "/mega-pipeline-transcribe-audio" is already in use` | a second terminal is still running the same component | G9 |

**A8. Task B: generate_text** (`mega-pipeline/README.md:244-248`):
```bash
python cli.py --download
python cli.py --generate
python cli.py --upload
```
- **Under the hood.**
  - At import, `genai.Client(vertexai=True, project=gcp_project, location="us-central1")` is created (`generate_text/cli.py:25`).
  - `--download` uses `match_glob` for `text_prompts/<group>/input-*.txt` (`:43`).
  - `--generate` builds a cheese-podcast prompt (`:65-72`) and calls `client.models.generate_content(model=model_name, ...)` (`:75-77`), with `model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")` (`:73`).
- **Optional model switch** (`generate_text/README.md:91-94`):
  ```bash
  export GEMINI_MODEL=gemini-2.5-flash
  python cli.py --generate
  ```
- **Checkpoint.** A long "Generated text:" printout; then `text_paragraphs/<group>/` in the bucket (`generate_text/README.md:136`).
- **If it fails.**
  - `403 PERMISSION_DENIED` mentioning project `ac215-project`: you kept the shipped values (E2).
  - `404`/model-not-found: set `GEMINI_MODEL` to a model your project can use (open question Q3).
  - `403` with the right project: the role is missing (Agent Platform User) or `aiplatform.googleapis.com` is not enabled.

**A9. Task C: synthesis_audio_en** (`mega-pipeline/README.md:252-255`):
```bash
python cli.py --download
python cli.py --synthesis
```
- **Under the hood.**
  - `TextToSpeechLongAudioSynthesizeClient()` is created at import (`synthesis_audio_en/cli.py:23`).
  - For each paragraph whose output blob does not exist (`:70`), the code sends `SynthesizeLongAudioRequest(parent=f"projects/{gcp_project}/locations/us-central1", ..., output_gcs_uri=f"gs://{bucket_name}/{audio_blob_name}")` and waits up to 300 s (`:78-91`). Google's service writes the audio **directly into the bucket**, so there is no `--upload` (`mega-pipeline/README.md:257`).
- **Checkpoint.** `Audio file will be saved to GCS bucket automatically.` (`:92`), then `text_audios/<group>/input-*.mp3` in the bucket. The README says to give it a moment (`synthesis_audio_en/README.md:121`), but the CLI already blocks on `operation.result(timeout=300)` (`:91`) before printing that line, so the object should normally be there once it prints.
- **If it fails.** An empty `gcp_project` produces the resource name `projects//locations/us-central1` (an invalid-argument error, *expected*). A permission error on the output URI means the SA cannot write to the bucket.

**A10. Task D: translate_text** (`mega-pipeline/README.md:261-265`):
```bash
python cli.py --download
python cli.py --translate
python cli.py --upload
```
- **Under the hood.** `translate.Client()` (the Translation **v2 / Basic** client, `translate_text/cli.py:9`, `:22`) calls `translate(input_text, source_language="en", target_language="es", format_="text")` (`:61-66`). Re-runs print `Translated file already exists.` (`:55`).
- **Checkpoint.** `text_translated/<group>/` in the bucket (`translate_text/README.md:136`). The text is **Spanish** unless you changed `target_language` (E3).
- **If it fails.** 403 on Translation: role `roles/cloudtranslate.user` or the API is missing.

**A11. Task E: synthesis_audio** (`mega-pipeline/README.md:269-272`):
```bash
python cli.py --download
python cli.py --synthesis
```
- **Under the hood.** Same as A9, but it reads `text_translated/<group>/` and uses voice `fr-FR` / `fr-FR-Standard-C` (`synthesis_audio/cli.py:48-49`), writing `output_audios/<group>/input-*.mp3` (`:66`, `:78`).
- **Checkpoint.** `output_audios/<group>/` in the bucket: "the final output of the pipeline" (`synthesis_audio/README.md:119`). A French voice reading Spanish text means you hit E3.
- **Bonus: ElevenLabs.** `cli_11.py` hard-codes `mega-pipeline-bucket` / `pavlos` (`cli_11.py:15-19`) and reads `secrets/11lab_api_key.txt` relative to `/app` (`:30-33`). See E10 before trying it.

**A12. Optional modes** (`mega-pipeline/README.md:212-216`):
```bash
./docker-shell.sh dev      # only build the local image
./docker-shell.sh run      # run from a prebuilt image (falls back to DockerHub)
./docker-shell.sh prod     # build multi-arch (amd64 + arm64) and push to DockerHub
```
For `prod`, first run `docker login -u <USER NAME> -p <ACCESS TOKEN>` (`transcribe_audio/README.md:129`) and edit `DOCKER_USERNAME` (`docker-shell.sh:13`). (Docker warns that `-p` on the command line is insecure, since the token lands in your shell history; `docker login -u <USER NAME> --password-stdin` avoids that.)
- **Under the hood.**
  - `dev` stops after `docker build` (`:71-76`).
  - `run` skips the build. It uses local `mega-pipeline-<component>` if `docker image inspect` finds it, else `$DOCKER_USERNAME/mega-pipeline-<component>` (`:82-89`), which `docker run` pulls implicitly.
  - `prod` removes and recreates the `multi-arch` builder, then `docker buildx build --platform linux/amd64,linux/arm64 --push -t $DOCKER_USERNAME/$IMAGE_NAME` (`:55-66`). It never runs a container.
- **Checkpoint.**
  - `run` prints `Using local image...` or `Local image not found, using image from registry...` (`:84`, `:87`).
  - `prod` ends with `Production build complete and pushed to registry` (`:68`), and the tag on Docker Hub lists two platforms.
- **If it fails.**
  - `run` on a fresh machine lands in the stale Python-3.8/Pipenv `dlops` image (E1).
  - Pushing to `dlops/...` without membership fails with an authorization error ("requested access to the resource is denied" or similar).
  - The amd64 half of `prod` is slow on Apple Silicon (QEMU).
  - After `prod`, see G8.

**A13. Clean up.** Type `exit` in each container shell (`--rm` deletes the container). Then follow the cleanup in §2.

### Part B — port_toy

**B1. Check Docker, get the code, enter the folder** (`port_toy/README.md:28-30`, `:81-85`):
```bash
docker run hello-world
```
The README only says "Clone or download the [repository](https://github.com/dlops-io/port_toy)" (`:81`); the usual clone command (not in the README) is `git clone https://github.com/dlops-io/port_toy.git`. Then:
```bash
cd port_toy
```
- **Checkpoint.** "Hello from Docker!".

**B2. Create the network** (`port_toy/README.md:91-93`):
```bash
docker network create toynet
```
- **Under the hood.** This creates a user-defined bridge with its own subnet and DNS (C6). It prints the network id.
- **If it fails.** "network with name toynet already exists": a previous run was not cleaned up. Run `docker network rm toynet` (after removing containers on it).

**B3. Build both images** (`port_toy/README.md:99-102`):
```bash
docker build -t toy-processor ./processor
docker build -t toy-gateway ./gateway
```
- **Under the hood.** Each Dockerfile (`port_toy/processor/Dockerfile:1-5`, `port_toy/gateway/Dockerfile:1-5`):
  - starts from `python:3.14-slim`
  - apt-installs `curl`
  - copies the folder to `/app`
  - sets `CMD ["python", "-u", "<file>.py"]`

  `-u` turns off output buffering so `docker logs` shows prints immediately; this is the same job `ENV PYTHONUNBUFFERED=1` does in mega-pipeline (`Dockerfile:13`).
- **Checkpoint.** `docker image ls 'toy-*'` shows both images (quote the pattern so the shell does not glob it).

**B4. Start the processor, unpublished** (`port_toy/README.md:108-111`):
```bash
docker run -d --name processor --network toynet \
  -e PORT=9200 toy-processor
```
- **Under the hood.** `-d` runs it detached. `processor.py:42-44` reads `PORT`, binds `("", 9200)` and prints its banner.

**B5. Start the gateway, published** (`port_toy/README.md:119-125`):
```bash
docker run -d --name gateway --network toynet \
  -p 127.0.0.1:8090:9100 \
  -e PROCESSOR_HOST=processor \
  -e PROCESSOR_PORT=9200 \
  toy-gateway
```
- **Under the hood.** `gateway.py:13-14` reads the processor's address from env. `:51-53` binds `("", 9100)` (the `PORT` default). Docker forwards host `127.0.0.1:8090` → container `9100`.
- **If it fails.** `Bind for 127.0.0.1:8090 failed: port is already allocated`: something else uses 8090. Pick another host port (Step 3 shows how).

**B6. Read the logs** (`port_toy/README.md:131-134`):
```bash
docker logs processor
docker logs gateway
```
- **Checkpoint** (README `:138-141`):
  ```text
  processor listening on port 9200 (internal only)
  gateway listening on port 9100 → open http://localhost:8090
  ```
  The real gateway line has two spaces around the arrow (`gateway.py:53`).

**B7. Send a message.** Open http://localhost:8090, type, click **Send** (`port_toy/README.md:145-157`).
- **Under the hood.**
  1. `do_GET` serves `index.html` (`gateway.py:18-25`).
  2. The page `fetch("/", {method: "POST", ... JSON.stringify({ text: text })})` (`index.html:95-99`).
  3. The gateway opens `HTTPConnection(PROCESSOR_HOST, PROCESSOR_PORT)` (`gateway.py:33`), reads its own source port (`:38`), and forwards.
  4. The processor upper-cases the text and reports `listen_port` and `sender_port` (`processor.py:29-33`).
  5. The page reads the host port from its own address bar (`index.html:86-89`).
- **Checkpoint.** The upper-cased text, plus three port lines in which the first and third numbers match (e.g. `44456`) and the second is `9200`.

**B8. Check the PORTS column** (`port_toy/README.md:197-199`):
```bash
docker ps
```
- **Checkpoint.** `toy-gateway ... 127.0.0.1:8090->9100/tcp ... gateway`, and an empty PORTS column for `processor` (`:203-207`). Empty because there is neither `-p` nor `EXPOSE` (`:211`).

**B9. Probe from the laptop** (`port_toy/README.md:250-252`, `:258-260`):
```bash
curl http://localhost:8090
```
```bash
curl --max-time 3 http://localhost:9200/health
```
- **Checkpoint.** The first returns the HTML (`<!DOCTYPE html>` ...). The second fails, e.g. `curl: (7) Failed to connect to localhost port 9200 ...` (*expected*), "assuming nothing else is using port 9200" (`:262`).

**B10. Probe from inside the gateway** (`port_toy/README.md:272-274`, `:284-286`):
```bash
docker exec gateway curl http://processor:9200/health
```
```bash
docker exec gateway curl --max-time 3 http://localhost:9200/health
```
- **Under the hood.** `docker exec` starts a second process in the gateway's namespaces. `processor` resolves through Docker DNS. `localhost` is the gateway's own loopback, where nothing listens on 9200.
- **Checkpoint.** `ok` (the processor sends no trailing newline, so your prompt may appear right after it, `processor.py:20`). The second command fails with curl exit 7 (*expected*).

**B11. Change the host port** (`port_toy/README.md:339-341`, `:345-351`):
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
- **Checkpoint.** http://localhost:8095 works, :8090 no longer does (`:355`). The page diagram shows `localhost:8095 → :9100` (`index.html:87-88`), but `docker logs gateway` still says `open http://localhost:8090`, because that string is hard-coded (`gateway.py:53`, E15).

**B12. Move the processor to 9300 and watch it break** (`port_toy/README.md:369-371`, `:375-378`):
```bash
docker rm -f processor
```
```bash
docker run -d --name processor --network toynet \
  -e PORT=9300 toy-processor
```
- **Checkpoint.** "Send a message from the browser. It should fail." (`:380`).
  - What you actually see: **nothing changes on the page**, because `index.html:95-100` has no error handling. Use the gateway on its current host port, 8095 after B11.
  - `docker logs gateway` shows a traceback ending in `ConnectionRefusedError: [Errno 111] Connection refused` (*expected*: the name resolves, but nothing listens on 9200).

**B13. Re-point the gateway** (`port_toy/README.md:388-390`, `:394-400`):
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
- **Checkpoint.** http://localhost:8090 works again, and the middle port line shows `9300`. "The two settings must agree" (`:404-407`).

**B14. Clean up before Compose** (`port_toy/README.md:415-418`):
```bash
docker rm -f gateway processor
docker network rm toynet
```
- **Why it matters here.** The compose file uses the **same container names and network name** (`docker-compose.yml:13`, `:28`, `:37-39`). Skipping this step makes B15 fail (G11).

**B15. Run with Compose** (`port_toy/README.md:454-456`):
```bash
docker compose up
```
- **Under the hood.**
  1. Compose reads `docker-compose.yml` and builds any missing images for both services (`:14`, `:29`), named `port_toy-gateway` and `port_toy-processor`.
  2. It creates network `toynet` (`:37-39`). This matches the README's order: build, network, containers (`port_toy/README.md:466-469`).
  3. It starts `processor` first because of `depends_on` (`:22-23`), then `gateway` with `ports`, `environment`, and the **bind mount `./gateway:/app`** (`:15-21`).
  4. Logs from both containers stream in your terminal, prefixed by container name.
- **Checkpoint.** The same two banners; http://localhost:8090 works (`:460`). `docker network ls` shows `toynet`.

**B16. Edit and re-apply** (`port_toy/README.md:491-493`, `:499-501`):
```bash
docker compose up -d
```
```bash
docker compose up -d --build
```
- **Under the hood.** `up -d` recreates only the services whose configuration changed, in the background. `--build` rebuilds images first.
  - Because of the gateway bind mount, `index.html` edits are live on the next page load (it is re-read on every GET, `gateway.py:20`).
  - `gateway.py` edits need `docker compose restart gateway`.
  - `processor.py` edits need `--build`, since it has no mount.

**B17. Stop and remove** (`port_toy/README.md:507-513`, `:523-525`):
```bash
docker compose down
```
```bash
docker compose ps -a
```
- **Under the hood.** `Ctrl+C` makes Compose stop the containers gracefully (SIGTERM). Python as PID 1 installs no SIGTERM handler, so Docker waits its 10 s default before SIGKILL. *Expected*: whichever of `Ctrl+C` or `down` stops the running containers takes about 10 s per container, possibly ~20 s because Compose stops `gateway` before `processor` (reverse `depends_on` order). A `down` after `Ctrl+C` is quick (G12).
  - `down` removes the containers and the `toynet` network. The images remain (`:515`).
- **Checkpoint.** `docker compose ps -a` is empty after `down`. Before `down` (after `Ctrl+C`) it lists both containers as `Exited`.

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
├── README.md                     Steps 1-4, cheat sheet
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
- `IMAGE_NAME` plays three roles: the local tag (`:75`, `:83`), the container name (`:92`), and the registry repository name (`:66`, `:88`). That is the only line that differs between the five scripts (apart from whitespace).
- `BASE_DIR` and `SECRETS_DIR` depend on your **current directory**, so run the script from the component folder. `../../secrets/` means "beside the repo".
- `GOOGLE_APPLICATION_CREDENTIALS` here is the **in-container** path; it is passed in with `-e` later.
- `DOCKER_USERNAME="dlops"`: change it before `prod`. It also decides which registry image `run` falls back to.
- `BUILD_MODE="dev-run"` is used when no argument is given.

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
- The fallback `$DOCKER_USERNAME/$IMAGE_NAME` has no tag, so `docker run` pulls `:latest` if it is not cached (E1).
- `--rm`: the container (and anything installed in it) is deleted on exit. `--name` fixes the container name (G9). `-ti` gives an interactive TTY.
- `-v "$BASE_DIR":/app` is the live-code bind mount; it hides the image's `/app` (C3).
- `-v "$SECRETS_DIR":/secrets` plus `-e GOOGLE_APPLICATION_CREDENTIALS=...` is runtime secret injection (C4). If `SECRETS_DIR` does not exist, Docker creates an empty directory instead of failing (G3).

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
- `USER app` means everything after this line, and the container at runtime, runs as uid 1000 (created at `:30`), not root.
- `COPY --chown=app:app . ./` copies the **whole build context**, including any leftover `secrets/`, `input_audios/` or `text_*` folders. There is no `.dockerignore` (G6).
- `RUN uv sync` installs the locked dependencies into `UV_PROJECT_ENVIRONMENT=/home/app/.venv` (`:17`), outside `/app`, so the bind mount cannot hide it.
  - `uv sync` is run without `--locked`/`--frozen`. If `pyproject.toml` and `uv.lock` disagree, uv re-resolves silently instead of failing.
- `ENTRYPOINT` + `CMD` give an interactive bash with the venv activated. `source` runs in the non-interactive `bash -c` shell and exports `PATH`/`VIRTUAL_ENV`; `exec bash` then *replaces* that shell with an interactive one (PID 1, no wrapper shell left behind) that inherits those variables, so `python` is the venv's. One `exit` ends the container. The new shell reads `~/.bashrc`, which resets the prompt, so you see `app@<id>:/app$` without a venv prefix (*expected*).

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
- The first lines are hard-coded config, edited by hand per team. A later course step moves this kind of thing to env vars, as L05/L10 do with `GCP_PROJECT`.
- The `assert` guards only against the empty string. The guard that would have caught `pavlos-advanced` is commented out, so the assert passes with the instructor's values (E2).
- `genai.Client(vertexai=True, ...)` routes Gemini calls through **Vertex AI** in *your* project, billed and authorized with the SA (role `roles/aiplatform.user`). It is created at import time.

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
- Not shown: `audio_encoding=LINEAR16` (`:74`) is uncompressed 16-bit PCM (Google returns it with a WAV header), yet the object is named `.mp3` (`:67`), E11.

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
- `container_name: gateway` pins the name. It makes `docker exec gateway ...` from the README keep working, but it collides with a leftover by-hand container (G11).
- `build: ./gateway` is the equivalent of `docker build ./gateway`; the image is named `port_toy-gateway` by default.
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
- `networks: toynet: name: toynet` makes Compose create a network literally named `toynet` instead of `port_toy_toynet`/`port_toy_default`. This mirrors the by-hand step, and it can also collide with it (G11).

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
- `HTTPConnection(PROCESSOR_HOST, PROCESSOR_PORT)`: the host comes from env (`:13`), default `"processor"`, and is resolved by Docker's DNS when `request()` connects.
- `conn.sock.getsockname()[1]` reads the **local** (source) port the kernel picked for this TCP connection.
- `reply["gateway_out_port"] = out_port` attaches that port to the reply so the page can show it next to the processor's view. There is no `try/except`, so any connection failure becomes a traceback in `docker logs gateway`, and the browser sees a dropped connection.

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
- `server_address[1]` is the port it actually bound. `client_address[1]` is the peer's port: the gateway's ephemeral port, unchanged because there is no NAT inside the bridge.
- `HTTPServer(("", port), ...)`: `""` = all interfaces (0.0.0.0) **of this container**. Binding `"127.0.0.1"` would make the server unreachable from other containers (Exercise 4).
- `PORT` from env makes the listening port configuration, not code (Step 3).

**11. `port_toy/gateway/index.html:86-89`: the page reads the host port from the address bar**
```javascript
    // the host port is whatever you published with -p; read it from the address bar
    const hostPort = location.port || (location.protocol === "https:" ? "443" : "80");
    document.getElementById("d_hostport").textContent = hostPort;
    document.getElementById("d_hostport_r").textContent = hostPort;
```
- A container cannot know which host port it was published on; only the client can. The latest commit (`d190c71`) added this so the diagram shows 8095 in Step 3. The log banner in `gateway.py:53` was not updated (E15).

---

## 6. Gotchas and common errors

**G1. Switching from `main` blocks, or silently overwrites your L03 files.** *Verified by experiment (re-run with the same result on 2026-10-13; the in-component `secrets/mega-pipeline.json` also survived the switch).*
- **Setup.** In a scratch worktree of the clone, on `main` @ `c6bbc9b`, L03-style untracked files were created: `transcribe_audio/Dockerfile`, `transcribe_audio/pyproject.toml`, `transcribe_audio/secrets/mega-pipeline.json`, `generate_text/Dockerfile`, `generate_text/uv.lock`.
- **Symptom 1.** `git checkout ... flexible-workflow` printed:
  ```text
  error: The following untracked working tree files would be overwritten by checkout:
  	generate_text/Dockerfile
  	generate_text/uv.lock
  Please move or remove them before you switch branches.
  Aborting
  ```
- **Cause 1.** On `main`, `generate_text/` has no `.gitignore` (git check-ignore confirms), so those files are untracked and *not* ignored, and Git refuses to clobber them.
- **Symptom 2.** After removing those two files the checkout succeeded. `transcribe_audio/Dockerfile` and `pyproject.toml` were **silently replaced** by the branch's versions.
- **Cause 2.** `main:transcribe_audio/.gitignore` ignores `Dockerfile`, `pyproject.toml`, `uv.lock` and `docker-shell.sh` (lines 4-7), and Git treats ignored files as expendable. The same rule exists in `synthesis_audio`, `synthesis_audio_en` and `translate_text` on `main`.
- **Fix.** If you want your L03 Dockerfiles, copy them out of the repo first. Then `git stash -u` (or move the files) before `git checkout flexible-workflow`. `git checkout -- .`, as suggested in `mega-pipeline/README.md:48`, does not remove untracked files.

**G2. `AssertionError: Update group name`.**
- **Cause.** `group_name = ""` and an import-time `assert` (e.g. `transcribe_audio/cli.py:21-24`). Even `python cli.py --help` trips it.
- **Fix.** Set `group_name`. Also note that `generate_text` and `translate_text` **do not** trip it (E2).

**G3. `google.auth.exceptions.DefaultCredentialsError: File /secrets/mega-pipeline.json was not found.`**
- **Cause.** The key is not at `<component>/../../secrets/mega-pipeline.json` (`docker-shell.sh:9`), the file has a different name, or you ran the script from the wrong folder.
  - Docker creates a **missing** bind-mount source as an empty directory, so `docker run` itself does not fail. You only find out inside.
- **Where it surfaces.** It surfaces at `python cli.py -d` in transcribe/generate. Their storage clients are built inside the functions; `generate_text`'s `genai.Client` is built at import (`generate_text/cli.py:25`) but, given an explicit project, should load credentials only on its first request (*expected*). In translate and both synthesis components an API client is created at import (`translate_text/cli.py:22`, `synthesis_audio_en/cli.py:23`, `synthesis_audio/cli.py:22`) and looks up credentials immediately, so even `--help` may fail once `group_name` is set (*expected*).
- **Fix.** `ls ../../secrets/` from the component folder; rename the key to `mega-pipeline.json`. Inside the container, `ls -l /secrets` should list it.

**G4. 403s naming `ac215-project` or `mega-pipeline-bucket`.**
- **Cause.** Shipped instructor values in `generate_text/cli.py:16-17` and `translate_text/cli.py:14-15` (E2). Your SA has no rights there.
- **Fix.** Set your project and bucket in all five `cli.py` files.

**G5. 403 / `PERMISSION_DENIED` with your own project.**
- **Cause.** A missing role (§2 table) or a disabled API (`mega-pipeline/README.md:187`).
  - `storage.buckets.get` denied: transcribe uses `client.get_bucket(...)` (`transcribe_audio/cli.py:40`), which needs a bucket-level permission. "Storage Object Admin" is not enough; grant Storage Admin as the README says (`:178`).
  - Vertex denied: grant "Agent Platform User" (`roles/aiplatform.user`) and enable `aiplatform.googleapis.com`.
- **Fix.** Grant the role or enable the API. Both changes can take a few minutes to propagate; re-run after that.

**G6. Your key ends up inside the image, and maybe on Docker Hub.**
- **Cause.** L03 told you to keep the key in `<component>/secrets/` (`main:README.md:97`), and switching branches leaves it there (`mega-pipeline/README.md:50`). The Dockerfile copies the whole folder (`Dockerfile:39`), and no branch has a `.dockerignore`.
  - `.gitignore`'s `/secrets` (`transcribe_audio/.gitignore:3`) only protects Git.
  - `./docker-shell.sh prod` pushes the image with that layer to a public repo (`docker-shell.sh:66`).
- **Fix.**
  - Delete the in-component `secrets/` folders after moving the key out.
  - Add a `.dockerignore` per component with `secrets/` and the data folders (`input_audios/`, `text_*/`, `output_audios*/`).
  - If a key was pushed, **delete that key in IAM** immediately. Deleting the image is not enough.

**G7. `./docker-shell.sh run` drops you into a Python 3.8 Pipenv shell, or into `ModuleNotFoundError`.**
- **Cause.** With no local `mega-pipeline-<component>` image, the script uses `dlops/mega-pipeline-<component>` (`docker-shell.sh:86-88`), whose `latest` is a 2025-02-18 build with `PYTHON_VERSION=3.8.17` and `CMD ["-c","pipenv shell"]` (registry metadata, E1).
  - With your uv-based folder mounted over `/app`, that environment does not match `pyproject.toml`/`uv.lock`. On `pipenv-flexible-workflow`, `generate_text/Pipfile` installs `google-generativeai` and `google-cloud-aiplatform`, not `google-genai` (which needs Python ≥ 3.9 anyway), and `translate_text/Pipfile` installs `googletrans==4.0.0rc1`, not `google-cloud-translate`. *Expected*: `from google import genai` and `from google.cloud import translate_v2` fail with `ImportError`.
  - The mount also hides the image's `Pipfile`, so the image's `CMD ["-c","pipenv shell"]` starts in a folder with no `Pipfile`; pipenv may then try to create one in your host folder, as root (*expected*, not run).
  - A related case: in `run` mode, packages you `uv add`-ed but never rebuilt are missing.
- **Fix.** Use the default mode or `dev` to build locally. Use `run` only for images *your team* pushed from this branch.

**G8. After `prod`, the default mode seems to ignore your rebuild.** *Inference, not run.*
- **Cause.** `docker buildx create ... --use` (`docker-shell.sh:62`) leaves the `docker-container` builder `multi-arch` selected. A plain `docker build` (`:75`) then builds with it, and that driver does not load results into the local image store unless `--load` is given.
  - The next `docker image inspect` (`:83`) then finds either an **older** local image or none at all, which falls through to G7.
- **Fix.** After `prod`, run `docker buildx use default` (on Docker Desktop the builder may be called `desktop-linux`; see `docker buildx ls`), or `docker buildx rm multi-arch`.

**G9. `Conflict. The container name "/mega-pipeline-<component>" is already in use`.**
- **Cause.** `--name $IMAGE_NAME` (`docker-shell.sh:92`) while another shell of the same component is still running. A crashed non-`--rm` container would cause the same.
- **Fix.** `exit` the other shell, or `docker rm -f mega-pipeline-<component>`.

**G10. Linux hosts only: `PermissionError` writing `/app/...` or reading `/secrets/...`.**
- **Cause.** The container runs as uid 1000 (`Dockerfile:30`, `:35`). Bind mounts keep host ownership. If your host uid is not 1000, or the key is `chmod 600` by another uid, the container user cannot write or read.
  - Docker Desktop on macOS and Windows maps ownership for you, so this mostly hits GCP VMs.
- **Fix.** Make the folders writable for uid 1000, or run on a host user with uid 1000.

**G11. `docker compose up` fails right after the by-hand steps.**
- **Cause.** Containers named `gateway`/`processor` and a network named `toynet` already exist; the compose file pins the same names (`docker-compose.yml:13`, `:28`, `:39`).
  - The container clash gives `Conflict. The container name "/processor" is already in use by container ...`.
  - The network clash (version-dependent, Q5): recent Compose v2 versions warn "a network with name toynet exists but was not created by compose" and then refuse it with a `network toynet was found but has incorrect label com.docker.compose.network ...` error; older v2 versions reused it.
- **Fix.** Run B14 first: `docker rm -f gateway processor` and `docker network rm toynet`.

**G12. `Ctrl+C` / `docker compose down` hangs for about 10 seconds (or ~20).** *Expected, not run.*
- **Cause.** `CMD ["python", "-u", "gateway.py"]` makes Python PID 1. PID 1 ignores SIGTERM unless it installs a handler, and these scripts do not. Docker waits its 10-second default stop timeout, then SIGKILLs. Compose stops `gateway` before `processor` (reverse `depends_on`), so the two waits can add up.
- **Fix (optional).** Add `stop_signal: SIGINT` (Python turns SIGINT into `KeyboardInterrupt`) or `init: true` to each service. `docker rm -f` is instant because it kills straight away.

**G13. "It should fail", but nothing visible happens.**
- **Cause.** In Step 3 the gateway raises `ConnectionRefusedError` (`gateway.py:33-34` has no error handling), and `index.html:95-100` has no `catch`. The page simply does not update.
- **Fix.** Watch `docker logs -f gateway` (or `docker compose logs -f gateway`, `port_toy/README.md:572`) while clicking Send.

**G14. `curl localhost:9200` succeeds when it "should fail".**
- **Cause.** Another program on your laptop listens on 9200. The README warns about this (`port_toy/README.md:262`); Elasticsearch's default port is 9200.
- **Fix.** `lsof -i :9200` (macOS/Linux) to see who it is. The lesson still holds: the toy processor is not published.

**G15. `Bind for 127.0.0.1:8090 failed: port is already allocated`.**
- **Cause.** An old `gateway` (by hand or Compose) is still published on 8090, or another app uses it (`port_toy/README.md:357-361`, `:550`).
- **Fix.** `docker ps` to find it and `docker rm -f`, or pick another host port (B11).

**G16. Gemini default model or Translation language surprises.**
- **Cause.** `gemini-2.5-flash-lite` is hard-coded as the default (`generate_text/cli.py:73`); a retired model returns 404. Translation targets `es` (`translate_text/cli.py:64`), while synthesis is French.
- **Fix.** `export GEMINI_MODEL=...` inside the container (`generate_text/README.md:91-94`), and set `target_language="fr"`.

**G17. Apple Silicon.**
- Local builds are native arm64. Both bases, `python:3.14-slim-bookworm` and `python:3.14-slim`, exist for arm64, and the lock files contain cp314 manylinux aarch64 wheels for the compiled packages (`grpcio`, `cffi`, `google-crc32c`, `pydantic-core`), so no compilation is needed.
- `prod`'s amd64 half runs under emulation and is noticeably slower.
- An image you build and push *without* `prod` would be arm64-only, which matters once you deploy to amd64 VMs (L02 lesson).

**G18. Windows Git BASH rewrites the container-side paths.** *Expected (well-known MSYS behaviour), not run.*
- **Cause.** The README sends Windows users to Git BASH (`mega-pipeline/README.md:378`). Git BASH's MSYS layer converts POSIX-looking arguments it passes to native programs such as `docker.exe`: `GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` (`docker-shell.sh:95`) can become `...=C:/Program Files/Git/secrets/mega-pipeline.json`, and a `-v <host>:/app` spec (`:93-94`) can be mangled into an invalid volume specification.
- **Symptom.** `invalid volume specification`/"invalid characters for a local volume name", or `DefaultCredentialsError` for a `C:/Program Files/Git/...` path.
- **Fix.** Run `MSYS_NO_PATHCONV=1 ./docker-shell.sh` (combine with `winpty` if needed), or run the script from WSL 2. Neither is in the README.

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
  - secrets outside the repo, injected at runtime
  - your own SA with least-privilege-ish roles and explicitly enabled APIs
  - multi-arch images
- Part B adds the networking layer that part A deliberately avoided ("Since we haven't covered APIs yet ... communicate indirectly by writing their outputs to storage", `mega-pipeline/README.md:140-142`): container networks, DNS by name, published vs internal ports, and Compose.

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
1. **Tooling is committed.** On `main`, four components' `.gitignore` files ignore `Dockerfile`, `pyproject.toml`, `uv.lock` and `docker-shell.sh`. On this branch those lines are gone and the files are tracked.
2. **Secrets move out.** `ENV GOOGLE_APPLICATION_CREDENTIALS` disappears from the Dockerfile. `docker-shell.sh` mounts `../../secrets/` at `/secrets` and passes the env var (`mega-pipeline/README.md:372`).
3. **Base image moves from Python 3.12 to 3.14.**
   - `main`'s sample Dockerfile says `python:3.12-slim-bookworm` (`main:README.md:177`), although `main:generate_text/pyproject.toml` already requires `>=3.14`.
   - This branch says `python:3.14-slim-bookworm` (`Dockerfile:2`).
   - `DEBIAN_PACKAGES` drops `curl` (`main:README.md:179` vs `Dockerfile:4`).
4. **`cli.py` changes.**
   - Config values are blanked (three components) or set to the instructor's (two).
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

Commit to your own answer before you open each one.

### Test yourself

These six questions check the core ideas of both tutorials.

**Q1. Which two files define what goes into a mega-pipeline image, and which file decides at runtime whether you build or pull?**
<details><summary>Answer</summary>

The `Dockerfile` and the lock file `uv.lock` (resolved from `pyproject.toml`): "devs pull the `Dockerfile` and `uv.lock` from GitHub and build images locally" (`mega-pipeline/README.md:71`). `docker-shell.sh` decides, with a `case` on `$1`: no argument builds and runs, `dev` builds, `run` uses the local `mega-pipeline-<component>` or else `$DOCKER_USERNAME/mega-pipeline-<component>`, and `prod` builds multi-arch and pushes (`docker-shell.sh:28-97`; C1, C2).
</details>

**Q2. Why does `/home/app/.venv` survive `-v "$BASE_DIR":/app` while the image's own `/app/cli.py` does not?**
<details><summary>Answer</summary>

The bind mount covers only the path `/app`. `UV_PROJECT_ENVIRONMENT=/home/app/.venv` (`Dockerfile:17`) made `RUN uv sync` (`:41`) put the venv outside that mount point, so the mount cannot hide it, while the image's copy of the code in `/app` (`Dockerfile:39`) is covered by your live host folder (C3).
</details>

**Q3. Name the three things that must all be right before `python cli.py -d` can read your bucket.**
<details><summary>Answer</summary>

1. *Who am I?* The key file at `<your-workspace>/secrets/mega-pipeline.json`, mounted at `/secrets` and named by `GOOGLE_APPLICATION_CREDENTIALS`; otherwise `DefaultCredentialsError` (G3).
2. *What may I do?* The SA holds a role that grants the permission, here Storage Admin (`roles/storage.admin`); otherwise a 403 (G5).
3. *Is the service switched on?* The API (`storage.googleapis.com`) is enabled in the project; otherwise a 403 with `SERVICE_DISABLED` (C4).

On top of that, `cli.py` must name your own project and bucket and a non-empty `group_name` (A6, G2, G4).
</details>

**Q4. In `-p 127.0.0.1:8095:9100`, which number does the browser use, which does `gateway.py` bind, and what does `127.0.0.1` restrict?**
<details><summary>Answer</summary>

The browser uses host port 8095 (`http://localhost:8095`). `gateway.py` binds container port 9100, its `PORT` default (`gateway.py:51-52`). `127.0.0.1` makes the published port reachable from your machine only (`port_toy/README.md:232-244`). The order is `ip:host:container` (C7, B11).
</details>

**Q5. Inside the gateway container, what does `localhost` refer to, and what name reaches the processor?**
<details><summary>Answer</summary>

`localhost` is the gateway itself, in its own network namespace (`port_toy/README.md:290`, `:546`). The name `processor`, resolved by Docker's embedded DNS on `toynet`, reaches the processor: `http://processor:9200` (C6, B10).
</details>

**Q6. What does `docker compose down` do that `Ctrl+C` does not?**
<details><summary>Answer</summary>

`Ctrl+C` only stops the containers; they and the network remain, and `docker compose ps -a` lists them as `Exited`. `docker compose down` removes the containers and the Compose-managed network `toynet`; the images remain (`port_toy/README.md:505-529`; C8, B17).
</details>

### Hands-on, debugging and conceptual

**Exercise 1 (hands-on): EXPOSE is not publish.** Add `EXPOSE 9200` to `port_toy/processor/Dockerfile` (after `WORKDIR /app`). Rebuild with `docker build -t toy-processor ./processor`, re-create the processor exactly as in B4, and predict: (a) what `docker ps` shows in its PORTS column, (b) whether `curl --max-time 3 http://localhost:9200/health` now works.
<details><summary>Answer</summary>

- (a) `9200/tcp`. It is a declared port without a host mapping, so the arrow form `->` is absent. This is the "declared" case `README.md:211` alludes to.
- (b) Still fails. `EXPOSE` "Documents a container port. It does not publish it." (`README.md:545`). Only `-p`/`ports:` (or `-P`, which publishes every EXPOSEd port to a random host port) creates a host listener.
</details>

**Exercise 2 (hands-on): same container port twice.** With both containers on `toynet`, re-create the processor with `-e PORT=9100` and the gateway with `-e PROCESSOR_PORT=9100` (keep `-p 127.0.0.1:8090:9100`). Predict whether either container fails to start and what the page shows.
<details><summary>Answer</summary>

Both start and the page works, showing `processor listening on port 9100`. Each container has its own network namespace and therefore its own port space. Only *host* ports can be "already allocated" (`README.md:361-363`).
</details>

**Exercise 3 (debugging): forgot `--network`.** You run `docker run -d --name processor -e PORT=9200 toy-processor`, with no `--network toynet`, and the gateway exactly as in B5. The page does nothing, and `docker logs gateway` ends with `socket.gaierror: [Errno -2] Name or service not known` (exact wording may vary). Why, and give two fixes.
<details><summary>Answer</summary>

The processor is on Docker's default `bridge` network, which has no name-based DNS between containers and is not connected to `toynet` anyway. The gateway's lookup of `processor` fails before any port is tried (contrast with Step 3's *Connection refused*, where the name resolved but the port was wrong; cheat sheet `README.md:551-552`). Fixes:
- `docker network connect toynet processor`, or
- `docker rm -f processor` and re-run it with `--network toynet` (B4).
</details>

**Exercise 4 (debugging): "safer" bind address.** A teammate changes `gateway.py:52` to `server = HTTPServer(("127.0.0.1", port), Gateway)` "so it is only local", then rebuilds and re-runs it as in B5. `docker logs gateway` shows the normal banner, but the browser shows an empty response or connection reset. Explain.
<details><summary>Answer</summary>

Published traffic is forwarded to the container's network interface (its `toynet`/bridge IP), not to the container's loopback. A server bound to 127.0.0.1 *inside the container* only accepts connections from processes in that same container; `docker exec gateway curl http://localhost:9100` would still work. Keep `""` (all interfaces) inside the container, and restrict exposure on the **host** side with `-p 127.0.0.1:8090:9100`, which is what the tutorial does (`README.md:232-244`).
</details>

**Exercise 5 (hands-on, mega-pipeline): pass the Gemini model from the script.** Edit `generate_text/docker-shell.sh` to add `-e GEMINI_MODEL=gemini-2.5-flash \` on a new line after `-e GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \` (`:95`). Predict: do you need a rebuild? How can you verify inside the container which model will be used?
<details><summary>Answer</summary>

No rebuild is needed. The env var is set at `docker run` time, and `cli.py:73` reads it at call time; the image is unchanged, although the default mode rebuilds anyway, quickly thanks to the layer cache. Verify with `echo $GEMINI_MODEL` inside the container. This is the same pattern as `GOOGLE_APPLICATION_CREDENTIALS`: configuration injected at runtime, not baked into the image.
</details>

**Exercise 6 (conceptual): where did my package go?** Inside the transcribe container you run `uv add requests`, `exit`, then run `./docker-shell.sh run` (no rebuild) and `python -c "import requests"`.
<details><summary>Answer</summary>

- `pyproject.toml` and `uv.lock` changed **on your host**, through the `/app` bind mount.
- The install went into `/home/app/.venv` in that container's writable layer, deleted by `--rm` on exit.
- `run` reuses the existing local image, built *before* `uv add`. So for a package that is not already present, the import fails with `ModuleNotFoundError`.
- Fix: `./docker-shell.sh dev` (or the default mode) to bake the dependency in, then commit both files (`transcribe_audio/README.md:89`).
- (Twist: `requests` itself happens to be present already as a transitive dependency of the Google client libraries, as `uv.lock` shows, so to see the failure, use a package nobody depends on, e.g. `rich`.)
</details>

**Exercise 7 (debugging): Compose refuses to start.** Right after B13 you run `docker compose up` and get `Conflict. The container name "/processor" is already in use by container "..."`. Why, and what does the compose file do that causes it?
<details><summary>Answer</summary>

The by-hand containers still exist (you skipped B14). `docker-compose.yml:13` and `:28` pin `container_name: gateway` / `processor`, so Compose cannot use its own generated names. The network has the same problem, because of `name: toynet` (`:37-39`). Run `docker rm -f gateway processor` and `docker network rm toynet`, then `docker compose up`. Without the pins, Compose would have created `port_toy-gateway-1` and similar names on `port_toy_toynet` (or `port_toy_default` if the `networks:` keys were dropped too), and both stacks could coexist except for host port 8090.
</details>

**Exercise 8 (conceptual, security): what would `prod` publish?** You followed L03 (key at `transcribe_audio/secrets/mega-pipeline.json`), switched branches, set your own `DOCKER_USERNAME`, and ran `./docker-shell.sh prod`. List everything from your component folder that ends up in the pushed image, and the two-line change that prevents it.
<details><summary>Answer</summary>

- In the image: everything in the build context, because `COPY --chown=app:app . ./` (`Dockerfile:39`) and no `.dockerignore`.
  - `cli.py`, `pyproject.toml`, `uv.lock`, `README.md`, `Dockerfile`, `docker-shell.sh`, `.gitignore`
  - **`secrets/mega-pipeline.json`**
  - any downloaded `input_audios/` and `text_prompts/`
- The fix: create `transcribe_audio/.dockerignore` containing at least
  ```text
  secrets/
  input_audios/
  ```
  (and `text_prompts/`). Better still, delete the in-component `secrets/` folder now that the key lives in `../../secrets/`.
- If an image with the key was pushed, **revoke the key** in IAM; deleting the image is not enough.
</details>

---

## 9. Errata and open questions

**Errata**

- **E1. The registry fallback serves a different, stale image.** `docker-shell.sh` `run` falls back to `$DOCKER_USERNAME/$IMAGE_NAME` = `dlops/mega-pipeline-<component>` (`transcribe_audio/docker-shell.sh:86-88`). The README presents this as the "pull a prebuilt copy" path (`mega-pipeline/README.md:69-74`, `:214`).
  - Registry metadata read on 2026-10-12: all five `dlops/mega-pipeline-*:latest` were pushed 2025-02-18, with `PYTHON_VERSION=3.8.17`, `Cmd ["-c","pipenv shell"]`, `GOOGLE_APPLICATION_CREDENTIALS=../secrets/mega-pipeline.json` and no non-root user.
  - Their build history matches `pipenv-flexible-workflow:transcribe_audio/Dockerfile` (`FROM python:3.8-slim-buster`, `pipenv sync`), not this branch's `python:3.14-slim-bookworm` + `uv sync`.
  - Older per-arch tags `amd64`/`arm64` date from 2024-09-17.
- **E2. The assert guard is defeated in two components.** `generate_text/cli.py:16-22` and `translate_text/cli.py:14-20` ship `gcp_project="ac215-project"`, `bucket_name="mega-pipeline-bucket"`, `group_name="pavlos-advanced"`, with the `pavlos-advanced` assert commented out.
  - The root README says "The CLIs `assert` that it has been changed from the default — if you forget, the script stops before doing anything." (`mega-pipeline/README.md:134`).
  - Introduced by commits `95cf6f1` (2026-09-15) and `cc67f3b` (2026-09-18), which reverted the blanking done in `6e512da`.
- **E3. French story, Spanish code.**
  - `translate_text/cli.py:64` has `target_language="es"`.
  - These say French: `mega-pipeline/README.md:3` (the 🇫🇷 in the pipeline emoji line), `:13`, `:157`; `translate_text/README.md:8`, `:100`, `:105`, `:117`, `:132`; the argparse description "Translate English to French" (`translate_text/cli.py:108`).
  - The next stage uses a French voice, `fr-FR-Standard-C` (`synthesis_audio/cli.py:48-49`), so the final audio is Spanish text read by a French voice.
- **E4. Three different "defaults" for the same three variables.**
  - The root README shows all three as `""` (`mega-pipeline/README.md:128-130`).
  - Every component README shows `gcp_project = "ac215-project"`, `bucket_name = "mega-pipeline-bucket"`, `group_name = ""` (e.g. `transcribe_audio/README.md:51-53`).
  - The code has `""` in three files and instructor values in two (E2).
  - `mega-pipeline/README.md:133` says gcp_project and bucket_name "still point at the shared class resources from the earlier tutorial", which is false for the three blanked files.
- **E5. No bucket creation and no input data.** The branch requires your own bucket (`mega-pipeline/README.md:62`, `:150`) but gives no command to create it and no source for `input_audios/` content.
  - The naming convention matters, because uploads glob `input-*.txt` (`transcribe_audio/cli.py:102`) and downstream downloads glob `input-*.txt`.
  - In L03 the shared bucket already held Pavlos's recording.
- **E6. `flexible-workflow` lacks `main`'s transcription fix.** `main` @ `c6bbc9b` (2026-09-27) concatenates *all* `response.results` because "Speech-to-Text automatically breaks longer audio files into chunks". `flexible-workflow` still keeps only `response.results[0]` (`transcribe_audio/cli.py:84-86`). Longer recordings are truncated to their first chunk.
- **E7. No `.dockerignore` on any branch, while `COPY . ./` copies the whole component folder** (`Dockerfile:39`).
  - Combined with L03's instruction to store the key inside each component (`main:README.md:97`) and the README's reassurance that `secrets/` "stay[s] put" (`mega-pipeline/README.md:50`), `prod` can publish the key (G6).
  - `mega-pipeline/README.md:203` ("Keeping the folder outside the repo ... is the canonical way to make that mistake impossible") holds for Git only.
- **E8. Branch-switch instructions are incomplete.** `mega-pipeline/README.md:48` covers only modified tracked files.
  - Untracked `generate_text/Dockerfile` / `uv.lock` abort the checkout.
  - Ignored student files in the four other components are silently overwritten. Verified by experiment (G1).
- **E9. Role name inconsistency.** `generate_text/README.md:46` says "Vertex AI User", while `mega-pipeline/README.md:179` warns that searching "Vertex AI User" finds nothing and to search "Agent Platform User".
- **E10. The ElevenLabs bonus does not fit the branch's secrets layout.**
  - `synthesis_audio/README.md:129-133` says to put `11lab_api_key.txt` "to your `secrets/` folder", which on this branch is `<workspace>/secrets` → `/secrets`.
  - But `cli_11.py:30` opens `'secrets/11lab_api_key.txt'` relative to `/app` (the component folder), and hard-codes `bucket_name="mega-pipeline-bucket"`, `group_name="pavlos"` with no assert (`cli_11.py:15-19`). The key file is read at import (`:33-39`), so without it even `--help` fails.
  - The README says output "lands in the `output_audios_pp/` prefix of your bucket" (`synthesis_audio/README.md:135`), but `-s` only writes local files (`cli_11.py:105-108`); a separate `-u` uploads them (`:117-133`), and then to the hard-coded bucket.
- **E11. Audio encoding vs file extension.** Both synthesis components request `AudioEncoding.LINEAR16` (`synthesis_audio_en/cli.py:74`, `synthesis_audio/cli.py:73`) but name the objects `.mp3` (`synthesis_audio_en/cli.py:67`, `synthesis_audio/cli.py:66`). This is also on `main` (`main:synthesis_audio_en/cli.py:66`, `:73`). LINEAR16 output is 16-bit PCM with a WAV header, so the file is really a WAV; most players sniff the content, but it is not MP3.
- **E12. `chmod +x` advice is unnecessary for clones.** All five `docker-shell.sh` files are committed with mode `100755` (`git ls-files -s`). The advice (`mega-pipeline/README.md:220-224`) is harmless; it matters only if the executable bit gets lost (e.g. some archive extractors, or copying through a filesystem without Unix permissions).
- **E13. The `prod` builder is left selected.** `docker buildx create ... --use` (`docker-shell.sh:62`) is never undone. Later plain builds may not load into the local image store (G8; inferred from documented Buildx driver behaviour, not executed).
- **E14. port_toy README says the processor has no curl; the Dockerfile installs it.**
  - `port_toy/README.md:294`: "The gateway image includes `curl` for these tests. The processor image does not need it."
  - `port_toy/processor/Dockerfile:2` installs `curl`. Commit `de54f9f` ("processor: drop curl — nothing ever used it") removed it, and `868224b` re-added it.
  - The *statement* "does not need it" is true; the *implication* that the image lacks it is not.
- **E15. The gateway log banner hard-codes the host port.** `gateway.py:53` always prints `open http://localhost:8090`, even in Step 3 when it is published on 8095 (`README.md:345-351`). `d190c71` fixed only the page diagram (`index.html:86-89`).
  - The README's sample log line (`README.md:140`) also has single spaces where the code prints two around `→`.
- **E16. Step 3's failure is invisible in the UI.** "It should fail" (`port_toy/README.md:380`), but `index.html` has no error handling (`:95-100`) and the gateway does not catch connection errors (`gateway.py:33-40`). The visible symptom is "nothing happens", with a traceback in `docker logs gateway`.
- **E17. Schedule inconsistency on the course site.**
  - `src/2026-AC215/tutorials_demo.md:56-67` lists Lecture 4 as "Containers II-b".
  - `src/2026-AC215/_modules/week-03.md:5-7` lists "Lecture 4" as "LLM - RAGs" on Sep 15.
  - The commit dates (port_toy 2026-09-14 to 09-20; flexible-workflow READMEs 2026-09-14 to 09-18) fit a mid-September Containers II-b session; the module pages look stale.
- **E18. `run` is described as "pull from the registry", but it prefers any local image.** `mega-pipeline/README.md:74` says "`run` to pull and run from the registry" and `:214` "run from a prebuilt image (falls back to DockerHub)". The script first checks `docker image inspect mega-pipeline-<component>` and uses that local build if it exists, however old (`docker-shell.sh:83-85`); the registry is used only when it is missing (`:86-88`), and an already-pulled `dlops/...:latest` is reused without re-pulling (`docker run` does not refresh a cached tag).

**Open questions (could not be determined from the sources)**
- **Q1. Where should students get input audio for their own bucket?** Copy Pavlos's file from the shared bucket (needs read access), or record their own? Also, is a group leaderboard still used on this branch? It was removed from the README, but `group_name` is still required.
- **Q2. Are any Text-to-Speech roles needed?** `mega-pipeline/README.md:185` ("Text-to-Speech needs no role") and `synthesis_audio_en/README.md:48` (long-audio output is written with the caller's Storage Admin permission) could not be verified from the repository alone. If long-audio synthesis returns a permission error on `output_gcs_uri`, check the Text-to-Speech long-audio docs for the required bucket permissions.
- **Q3. Is `gemini-2.5-flash-lite` (the default, `generate_text/cli.py:73`) still served on Vertex AI in your project/region as of the lecture?** Later course repos use newer model names; if it 404s, set `GEMINI_MODEL`.
- **Q4. Does the instructor intend students to push to `dlops`?** The script default (`docker-shell.sh:13`) and the README note (`mega-pipeline/README.md:76`) suggest that only staff push there. Will the `dlops/*` images be rebuilt from this branch (fixing E1)?
- **Q5. Exact Compose behaviour on a pre-existing `toynet` network** (error vs warning) depends on the Docker Compose version installed. Not tested (no Docker daemon was available).
- **Q6. Ed lesson content.** The Ed lesson (https://edstem.org/us/courses/97373/lessons/166029/) was not accessible when these sources were checked. Any slides or in-class instructions there (e.g. a provided bucket or input audio) are not reflected in this guide.
- **Q7. Long recordings in `transcribe_audio`.** The CLI sends the whole FLAC inline (`content=`, `transcribe_audio/cli.py:74-80`) rather than a `gs://` URI, and waits only 90 s (`:81`). Google documents a ~10 MB limit for inline audio, so a student's own multi-minute stereo recording may be rejected or time out. Not tested; Pavlos's L03 recording presumably fits.

---

## Links

- mega-pipeline README sections (pinned commit `cc67f3b`): [Get the Code](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#get-the-code) · [Where We Are, Where We're Going](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#where-we-are-where-were-going) · [Two ways to work](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#two-ways-to-work--and-we-support-both) · [The Five Components](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#the-five-components) · [Recommended folder layout](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#recommended-folder-layout) · [⚠️ Configure each `cli.py` before you run it](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#%EF%B8%8F-configure-each-clipy-before-you-run-it) · [Connecting the Pipeline Components](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#connecting-the-pipeline-components) · [Service Account & Secrets](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#service-account--secrets) · [How to Run a Component](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#how-to-run-a-component) · [Quick Reference — Running Each Component](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#quick-reference--running-each-component) · [Sample Dockerfile](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#sample-dockerfile) · [Notes for running on Windows](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/README.md#notes-for-running-on-windows) · latest README on [`flexible-workflow`](https://github.com/dlops-io/mega-pipeline/tree/flexible-workflow)
- mega-pipeline component READMEs (pinned): [transcribe_audio](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/transcribe_audio/README.md) · [generate_text](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/generate_text/README.md) · [synthesis_audio_en](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/synthesis_audio_en/README.md) · [translate_text](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/translate_text/README.md) · [synthesis_audio](https://github.com/dlops-io/mega-pipeline/blob/cc67f3b8fc471f4fe1afe73d03e89466bae7d485/synthesis_audio/README.md)
- port_toy README sections (pinned commit `d190c71`): [Prerequisites](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#prerequisites) · [How the app works](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#how-the-app-works) · [Step 1: Set up the network by hand](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-1-set-up-the-network-by-hand) · [Step 2: Check the ports](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-2-check-the-ports) · [Step 3: Change the ports](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-3-change-the-ports) · [Step 4: Run with Compose](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#step-4-run-with-compose) · [Port and networking cheat sheet](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#port-and-networking-cheat-sheet) · [Handy commands](https://github.com/dlops-io/port_toy/blob/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c/README.md#handy-commands) · latest README on [`main`](https://github.com/dlops-io/port_toy#port-toy-app)
- Ed lesson: [L04 · Containers II-b](https://edstem.org/us/courses/97373/lessons/166029/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for this lecture.
- Previous lecture: [L03 · Containers II](L03-containers-2-mega-pipeline.md) (the same pipeline on `main`, with Dockerfiles you write yourself)
- Next lecture: [L05 · Introduction to RAG](L05-rag.md) (port_toy's pattern, with a ChromaDB container in place of the processor)
- Referenced in §7: [L02 · Containers I](L02-containers-1.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md)
