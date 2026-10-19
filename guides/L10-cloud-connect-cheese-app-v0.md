# L10 · Connecting to the Cloud: Networking, Authentication & Storage — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166035/) · Tutorial: [`dlops-io/cheese-app-v0`](https://github.com/dlops-io/cheese-app-v0) `main` @ [`cb6fb94`](https://github.com/dlops-io/cheese-app-v0/tree/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb) (the whole README, plus the optional [`llm-rag/README.md`](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/llm-rag/README.md)) · Colab notebooks: none for L10 · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 在自己的 laptop 上用 Docker 跑 cheese-app-v0 的三块：`llm-rag`（Docker Compose：一次性的 CLI + 一直跑着的 ChromaDB server，port 8000）把 11 本 cheese books chunk → 用 Vertex AI 上的 `gemini-embedding-001`（256-d）做 embedding → load 进 Chroma；`api-service`（FastAPI/uvicorn，port 9000）拿着 service account key，负责所有 Gemini call；`frontend-ai-chatbot`（Next.js dev server，container 3000 → host 3200）。代码是个 RAG web app，但这节课的重点是 **local code 怎么连到 cloud**：authentication、IAM、networking、storage。
- **Idea 1 · service account + ADC：从 key 文件到 Bearer token：** 在 console 建 `llm-service-account`，给 Storage Admin + Gemini Enterprise Agent Platform User（就是 Vertex AI User，`roles/aiplatform.user`），下载 JSON key，改名 `llm-service-account.json`，放进 repo **外面**的 `AC215/secrets/`。`genai.Client(vertexai=True, project=GCP_PROJECT, location="global")` 根本不打开 key 文件，是 google-auth 通过 ADC 去找：① `GOOGLE_APPLICATION_CREDENTIALS` 指向的文件 ② gcloud 的 user ADC 文件 ③ metadata server，container 里只有 ①。它用 private key 签一个 JWT，换回大约 1 小时有效的 access token，每个 request 都带 `Authorization: Bearer <token>`。env var 里写的是 **container 里的 path**（`/secrets/...`），要靠 `../../secrets:/secrets` 这个 bind mount 才真的存在。key 里没有 permission，它是长期有效的 password，绝对不能 commit。
- **Idea 2 · 403 ≠ key 错了：** key 找不到是 authentication 失败（`DefaultCredentialsError`、401）；403 通常是 authorization 失败，也就是 principal × role × resource 没对上。三个常见原因：`GCP_PROJECT` 还是 `ac215-project`（要改两个文件：`llm-rag/docker-shell.sh:7` 和 `api-service/docker-shell.sh:9`）；SA 缺 `roles/aiplatform.user`；Vertex AI API 没 enable（README 完全没提这一步）。`/finetunechat` 默认的 endpoint 在 instructor 的 project `129349313346` 里，所以也一定 403，要换成你自己 L08 的 endpoint（`rag.py:22`）。
- **Idea 3 · 一个 server，两个 address：** container 之间用 container name 互相找（Docker DNS，只在同一个 user-defined network 里有效，例如 CLI 连 `llm-rag-chromadb:8000`）；host 上的 browser 用 published port（`localhost:8000`、`localhost:9000`、`localhost:3200`）。server 必须 listen `0.0.0.0`。`next dev` 打印的 `localhost:3000` 是 container 视角，你要打开的是 `localhost:3200`。
- **Idea 4 · browser 才是 integrator，CORS 是它的 bouncer：** frontend container 只负责把 JS 发给 browser。一个 Chat 问题是 browser 直接发三个 cross-origin call：`GET :9000/rag/embedding` → `POST :8000/.../query`（Chroma）→ `POST :9000/rag/llm-response`。API 的 CORS 是 `*`，Chroma 只放行 `http://localhost:3200` 和 course 的 hosted site，所以用 `127.0.0.1:3200` 打开或者换 port，就只有 Chroma 被挡。`curl` 根本不管 CORS。
- **Idea 5 · storage：** container 用完就删（`--rm`），state 只活在 bind mount 里：Chroma 的数据在 `llm-rag/docker-volumes/chromadb`，`docker compose down` 不会删 vectors。v0 其实完全不碰 Cloud Storage（GCS）：GCS 的 read/write 在 L03/L08 的代码里，L11 才真正用上。
- **最费时间的坑：** ① `api-service/docker-shell.sh:14` 是不 idempotent 的 `docker network create`，加上 `set -e`，只要 network 已经存在（照 README 先建了 network，就一定存在），脚本立刻退出，什么都没 build。改成 `docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network`，或者删掉这行。② `secrets/` 必须正好在 service folder 上面两层（`AC215/secrets/`），文件名要对（不是 `.json.json`），而且要先 `cd` 进 service folder 再 `sh docker-shell.sh`。位置不对时 Docker 会悄悄 mount 一个空 folder，文件名不对也一样找不到 key，两种情况都要到第一次 call 才报 `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.`；没先 `cd` 进去的话，`api-service` 的脚本在 `docker build` 这一步就失败了（`api-service/docker-shell.sh:16`）。
- **做完要关/删：** cloud 上不建任何会 idle 计费的资源（没有 VM、bucket、endpoint），只按 Gemini call 计费。API 和 frontend 的 terminal 各 `Ctrl+C` 再 `exit`；在 `llm-rag` 里 `docker compose down` 关掉 Chroma（想彻底重置再删 `llm-rag/docker-volumes/`）；可选 `docker network rm cheese-app-network`；不再用的 key 在 IAM 里删掉；做了 E7 的话 `gcloud storage rm -r gs://YOUR_BUCKET`。
- **Lecture slides：** 老师的 Lecture 10 slides（`L10_connecting_to_the_cloud_3_`，55 页）讲三块理论：networking（IP、port、`-p HOST:CONTAINER` 这条 tunnel、Docker DNS）、authentication（service account、IAM、least privilege，外加 API key、OAuth、Workload Identity Federation）和 Cloud Storage；最后一节 Google Drive 在 tutorial 里没有对应，CORS、Vertex AI 和 ADC 这个名字 slides 都没有提到。这份 guide 各节和 slides 怎么对应、做 tutorial 需要的 9 个 lecture ideas，以及 slides 和 tutorial 不一样的 6 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 建的是 `data-service-account`（L11 才用这个名字），而且只给一个 storage role；这个 app 的脚本找的是 `llm-service-account.json`，还必须有 Gemini Enterprise Agent Platform User（`roles/aiplatform.user`），否则第一个 embedding 就 403；② slides 把 Containers II 的命令写成 `-p 8090:9100`，port_toy 实际用的是 `-p 127.0.0.1:8090:9100`；cheese-app-v0 没加 `127.0.0.1:`，publish 在所有地址上（`0.0.0.0`），同一个 Wi-Fi 上的设备可能直接调用你那个没有登录、却花你 Vertex AI 钱的 API。

## At a glance

**What you build.** You run the cheese RAG web app on your laptop as Docker containers (the `llm-rag` CLI with a ChromaDB server, a FastAPI `api-service` and a Next.js frontend) that call Gemini on Vertex AI with a service-account key kept in a `secrets/` folder outside the repo. Along the way you trace every connection: which identity (the key, through ADC), which authorisation (IAM roles on `GCP_PROJECT`), which address (container DNS name vs published port), which origin policy (CORS on the API and on Chroma) and which state survives (bind-mounted volumes).

**Time needed** (estimate, not timed). About 2–3 hours: roughly 15 minutes for the service account and key; a slow first build of the API image (`pipenv sync` of 170 pinned packages) and the frontend's first `npm install`; a few minutes of embedding calls for the two collections (89 + 148 batch requests, plus a 5 s pause per book); about 30 minutes for the five UI pages. The exercises in §8 add an hour or more.

**Prerequisites.**
- A GCP project with billing enabled, and its **project ID**.
- Docker Desktop, git and Chrome (`README.md:179-180`); optionally the `gcloud` CLI for the command-line equivalents.
- The **Vertex AI API** enabled in your project. No README in this repo says so (§2).
- Credentials: the service account `llm-service-account` (Storage Admin + Vertex AI User) and its JSON key at `AC215/secrets/llm-service-account.json`. If you did L05 or L08 you probably already have both.
- Background: L02–L04 (the `docker-shell.sh` pattern, bind mounts, Docker networks, published ports), L05 (the `llm-rag` CLI and Chroma stack), and L08 for the tuned endpoint that `/finetunechat` calls (optional).

**What it costs.** Only Vertex AI calls. Building both collections embeds about 7 M characters (an estimated ~1.75 M input tokens). Each Chat question is 1 embedding + 1 generation; each Agent question is 1 embedding + 3–7 generations; the tuned endpoint is billed per call in the project that owns it. Nothing idles in the cloud: the tutorial creates no VM, no bucket and no endpoint. The optional `semantic-split` costs noticeably more than the two default splitters.

**Tear down, exactly** (details in §2):
1. API terminal: `Ctrl+C` stops uvicorn, then `exit`. The container is `--rm`, so it disappears.
2. Frontend terminal: `Ctrl+C`, then `exit`.
3. Chroma: `docker compose down` inside `llm-rag` (`README.md:106`). The vectors survive in `llm-rag/docker-volumes/chromadb`; delete that folder to really reset.
4. Optional: `docker network rm cheese-app-network`.
5. Keys: list them with `gcloud iam service-accounts keys list --iam-account=llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com` and delete the ones you no longer use.
6. If you did exercise E7: `gcloud storage rm -r gs://YOUR_BUCKET`.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (all of `cheese-app-v0/README.md`): `#prerequisites`, `#setup-gcp-service-account`, `#create-the-docker-network`, `#build-the-vector-db`, `#optional-llm-rag-tutorial` (→ `llm-rag/README.md`), `#run-api-service-container`, `#run-frontend-container`, `#text-chunking`, `#vector-db-ui`, `#chat`, `#cheese-expert-agent`, `#pavlos-cheese-model`, `#api-endpoints`.
- **Primary repo:** `dlops-io/cheese-app-v0`, branch `main`, commit `cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb` (2026-10-08 11:57:11 -0400, message "final"). The repo was rebuilt on 2026-10-07/08 (6 commits in total), so re-check it if your clone is older or newer.
- **Repos cited only for context. You do not run them in this lecture:**
  - `dlops-io/llm-rag` `main` `e17a39f35bc07b440f573def480adaf4703f8b91` (2026-10-07). L05 predecessor of the `llm-rag/` folder.
  - `dlops-io/llm-finetuning` `main` `44ef6f0a70315aa0a551b8565ca862679a87c1eb` (2026-10-05). L08. Produces the tuned endpoint and contains GCS upload code.
  - `dlops-io/mega-pipeline` `main` `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc` (2026-09-27). L03. GCS download code.
  - `dlops-io/port_toy` `main` `d190c7122fc35cc1f7e15e467d2babdfc24b5c0c` (2026-09-20). L04. Ports and networks.
  - `dlops-io/data-labeling` `main` `03c3e277abeee2cdaf4c1a8149c11c9fd259577d` (2025-10-20) and `dlops-io/data-versioning` `main` `b240b1a03e0abd1964b689ea68e35f0990a33ebc` (2026-09-19). L11, the next lecture.
- **Colab notebooks:** none for L10.
- **Course-site source:** `tutorials_demo.md:139-144` maps L10 to cheese-app-v0 (under a heading that still says "LLM-Fine Tuning"; §9 erratum 13).
- **Ed lesson:** its slides and notes were not accessible when these sources were checked.
- **How the facts were checked.** Every `path:line` reference and excerpt comes from the verified digest. On 2026-10-13 they were spot-checked against `cb6fb94`: both READMEs (`README.md`, `llm-rag/README.md`, including the section line ranges in the command checklist), the three `docker-shell.sh` scripts and both entrypoints, `rag.py`, `service.py`, `cli.py`, `ChatComponent.jsx`, `next.config.js`, `hooks.jsx`, `.gitignore` and the commit log, plus `tutorials_demo.md:139-144`. A second, independent check the same day compared the command checklist with both READMEs again and spot-checked further references: `DataService.js`, `chromaui/page.jsx`, `page.jsx`, the `.env` files, `package.json`, `Pipfile`, `Pipfile.lock` and `uv.lock` in `cheese-app-v0`, and the context repos (`llm-finetuning`, `mega-pipeline`, `port_toy`, `data-labeling` and the standalone `llm-rag` at their pinned commits, `cheese-app-v2`/`v3`, and `_modules/week-06.md`). No repository script, Dockerfile or app was run. The chunk counts in §2 come from re-running the two splitters offline with the pinned `langchain-text-splitters`.
- **How to read the references.** A path without a repo name is inside `cheese-app-v0/`; `README.md` is `cheese-app-v0/README.md` unless another repo is named. Short names: `rag.py` = `api-service/api/routers/rag.py`, `service.py` = `api-service/api/service.py`, `cli.py` and `docker-compose.yml` = the files in `llm-rag/`, `DataService.js` and `Common.js` = `frontend-ai-chatbot/src/services/…`, `ChatComponent.jsx` = `frontend-ai-chatbot/src/components/chat/ChatComponent.jsx`, `hooks.jsx` = `frontend-ai-chatbot/src/hooks/hooks.jsx`, `next.config.js`, `.env.development` and `package.json` = files in `frontend-ai-chatbot/`. A bare `docker-shell.sh:N` or `docker-entrypoint.sh:N` means the script of the service being discussed.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 10: Connecting to the Cloud: Networking, Authentication & Storage* (`L10_connecting_to_the_cloud_3_`), 55 slides. Slide numbers are PDF page numbers; the printed footers differ, because the deck was cut from a longer one. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l10-cloud-connect/SLIDES.md`. The deck is the theory behind this tutorial's plumbing: networking (the Containers II gateway and processor, revisited), authentication and IAM, and Cloud Storage, using the L03 Mega Pipeline as its storage example. It never names `cheese-app-v0` (its "Tutorial" section is an empty divider) and never mentions CORS, ADC by name, `0.0.0.0` or Vertex AI. Its last section, Google Drive, has no counterpart in the tutorial. If the Ed lesson carries this deck, the slides answer part of §9's last open question: the lecture adds the networking and authentication theory, while the tutorial's steps all come from the README (the deck's console steps for the service account repeat the README's).

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 5–6, 11 (every machine and container has addresses; laptop vs cloud), 53 |
| §2 (service account and key); checklist *Setup GCP Service Account*; §4 Step 1 | 24–25, 32–38 (the same console steps, for a differently named account) |
| §3.1; §6 #13, #14 | 24–25, 27–28 (default service accounts), 29–31 (federation; choosing the tool), 37 (the console's key warnings) |
| §3.2 | 42 (the env var points the client library at the key); 19–23, 29–30 (access tokens and short-lived tokens). The slides never say "ADC". |
| §3.3; §6 #3; §8 E3, E6 | 26 (authentication vs authorization, least privilege), 35, 42, 45 |
| §3.4; §6 #2 | 38, 42 |
| §3.5; §4 Steps 2–5; §6 #6, #9, #10; §8 E5, E8 | 4–10 (IP addresses, ports and their ranges, publishing as a tunnel, Docker DNS) |
| §3.6; §6 #8; §8 E1 | none (CORS is not on the slides); 11 and 13 ask the related question, who is allowed in |
| §3.7; §5 Excerpt 12; §8 E7 | 39–45 (Cloud Storage) |
| §3.8; §4 Steps 6–11; §5 (other excerpts); §6 (other items); §7; §9 | none (tutorial-only) |

Lecture-only: authentication factors and MFA (14–16), API keys (17–18), OAuth 2.0's user-consent flow (19–23), Workload Identity Federation in detail (29–30) and Google Drive (46–51).

**Lecture ideas you need for this tutorial**
1. An IP address picks the machine, a port picks the service on it, and `localhost` always means "this machine". Inside a container, that is the container (slides 5–7).
2. `-p HOST:CONTAINER` tunnels a port you choose on the laptop to the port the app listens on inside the container: `3200:3000` is why you open 3200, not 3000 (slide 9).
3. Containers on a shared Docker network dial each other by name; Docker's DNS returns the current address, which can change when a container restarts (slide 10).
4. Once an address and a port are reachable, anyone who can reach them can knock, and an unprotected AI endpoint means runaway bills. The question becomes who is allowed in (slides 11, 13).
5. A service account is an identity for code, with no human and no login screen. You create it under IAM & Admin → Service accounts, grant it roles, and download a JSON key into `secrets/` (slides 24–25, 32–38).
6. Authentication proves who is calling; authorization (IAM roles) decides what it may do. Grant each account only what it needs (slides 26, 45).
7. A container reaches Google through the key folder mounted at `/secrets` and `GOOGLE_APPLICATION_CREDENTIALS` pointing at the file; the client library reads it, so no password appears in the code (slides 42–43).
8. Pick the auth tool by who acts and where: an API key for metered public calls, OAuth 2.0 for an app acting for a user, a service account for code running inside Google Cloud, Workload Identity Federation for code outside it. A downloaded key is the risk to manage (slides 29–31, 37).
9. Cloud Storage keeps objects in buckets under a flat key space, where "folders" are name prefixes. Storage Object Admin is enough to read and write objects, bucket names are global, and you delete what you don't need (slides 40–45).

**Where the slides and the tutorial differ** (in each case the tutorial's scripts, or the earlier lectures' terminal captures, show what the commands do)
- Slides 33–38 create `data-service-account` and its key `data-service-account.json`, which is L11's name. This tutorial's scripts look for `llm-service-account.json`, and any other name ends in `DefaultCredentialsError` (§2, §6 #2).
- Slides 35–36 grant a single storage role, and slide 45 recommends Storage Object Admin. This app needs **Gemini Enterprise Agent Platform User** (`roles/aiplatform.user`); without it the first embedding gets a 403. The README's Storage Admin is not used by v0 (§3.3, §6 #3, E6).
- Slide 42 mounts `"$PWD/../secrets"`, one level up. Here the scripts mount `../../secrets`, two levels up; each reaches `AC215/secrets` from where its script sits (§3.4).
- Slides 4, 9 and 11 write the Containers II command as `-p 8090:9100`. port_toy used `-p 127.0.0.1:8090:9100`, which publishes on the laptop's loopback address only, so nothing but the laptop itself can connect. This app publishes without the prefix (`docker ps` shows `0.0.0.0:…`), so other devices on your Wi-Fi may reach your API, which has no login and spends your Vertex AI budget. *(extra)* `-p 127.0.0.1:9000:9000` narrows it (§3.5).
- Slide 31 sends code running outside Google Cloud to Workload Identity Federation, and the console's banner on slide 37 prefers it to keys. A laptop has nothing for Google to federate with, so the tutorial uses a JSON key: treat it like a password (§3.1, §6 #13–14).
- Slides 40–44 retell the L03 Mega Pipeline with a `/secrets` mount, `gs://ac215-mega-pipeline` and `data-service-account.json`. L03 itself used `mega-pipeline-bucket` and the shared Canvas key at `secrets/mega-pipeline.json` inside each folder (§3.7, §7).

## Command checklist

You use three terminals: **T1** in `llm-rag` (the CLI container; Chroma keeps running after you leave it), **T2** in `api-service`, **T3** in `frontend-ai-chatbot`. Commands in backticks are exactly as the READMEs write them (placeholders such as `YOUR_PROJECT_ID` kept); *(in the container)* marks commands typed in a container shell. Plain items are console, editor or browser steps. Items marked *(extra)* are not in the README; they come from §4 and §6 of this guide.

### Before the README *(extra)*

- [ ] `git clone https://github.com/dlops-io/cheese-app-v0` — *(extra)* run in your course folder (e.g. `AC215/`); the README only says "Cloned this repository to your local machine" (`README.md:44`).
- [ ] Create `AC215/secrets/` **next to** `cheese-app-v0/`, never inside a git repo (`README.md:58-67`). If your whole `AC215/` folder is itself a git repo, add `secrets/` to its `.gitignore` before the first `git add`.

### Prerequisites · Setup GCP Service Account

*(`README.md:41-67`)*
- [ ] Have Docker installed and this repository cloned (`README.md:43-44`).
- [ ] In the [GCP Console](https://console.cloud.google.com/home/dashboard), search for **"Service accounts"**, or go to **IAM & Admin → Service accounts**.
- [ ] Create a new service account called `llm-service-account`.
- [ ] In **"Grant this service account access to project"** select **Storage Admin** and **Gemini Enterprise Agent Platform User** ("Vertex AI User" in older projects; role ID `roles/aiplatform.user`).
- [ ] Click the service account → **KEYS** tab → **ADD Key (Create New Key)** → **JSON**. A private key JSON file downloads.
- [ ] Copy it into the `secrets` folder and rename it to `llm-service-account.json` (not `llm-service-account.json.json`).
- [ ] `gcloud iam service-accounts create llm-service-account --project=YOUR_PROJECT_ID` — *(extra)* CLI equivalent of the console steps: creates the service account.
- [ ] `gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com" --role="roles/aiplatform.user"` — *(extra)* grants Vertex AI User on your project.
- [ ] `gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com" --role="roles/storage.admin"` — *(extra)* grants Storage Admin (unused by v0 code; §3.3).
- [ ] `gcloud iam service-accounts keys create ../secrets/llm-service-account.json --iam-account=llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com` — *(extra)* run from inside `cheese-app-v0/`; creates a key and writes it straight to `AC215/secrets/`.
- [ ] `gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID` — *(extra)* enables the Vertex AI API, which no README mentions.
- [ ] `ls -la AC215/secrets` — *(extra)* lists `llm-service-account.json`.

### Prerequisites · Create the Docker Network

*(`README.md:69-75`)*
- [ ] `docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network` — creates `cheese-app-network` once; safe to re-run.
- [ ] `docker network ls` — *(extra)* lists `cheese-app-network`.

### Build the Vector DB (T1)

*(`README.md:79-106`)*
- [ ] Open a terminal inside the `llm-rag` folder (`cd cheese-app-v0/llm-rag`).
- [ ] Update `GCP_PROJECT` to your own project ID in `docker-shell.sh` (line 7: `export GCP_PROJECT="YOUR_PROJECT_ID"`).
- [ ] `sh docker-shell.sh` — exports the project and key path, builds `llm-rag-cli` if no such image exists, starts ChromaDB (`llm-rag-chromadb`, port 8000) and opens bash in the CLI container; expect `Container is running!!!`.
- [ ] `ls -la /secrets` — *(extra, in the container)* the key file must be listed.
- [ ] `echo $GOOGLE_APPLICATION_CREDENTIALS $GCP_PROJECT` — *(extra, in the container)* both variables are set.
- [ ] `python -c "import google.auth; c, p = google.auth.default(); print(type(c).__name__, getattr(c, 'service_account_email', None), p)"` — *(extra, in the container)* ADC finds the key: `Credentials llm-service-account@….iam.gserviceaccount.com <project_id-from-key>`.
- [ ] `python cli.py --chunk --embed --load --chunk_type char-split` — *(in the container)* chunks the 11 books, embeds the chunks on Vertex AI, loads `char-split-collection` into Chroma.
- [ ] `python cli.py --chunk --embed --load --chunk_type recursive-split` — *(in the container)* the same for `recursive-split-collection` (more chunks, because of langchain's default overlap of 200).
- [ ] `exit` — leaves the CLI container; ChromaDB keeps running (`README.md:106`).
- [ ] `curl http://localhost:8000/api/v2/version` — *(extra, on the host)* Chroma answers through the published port.
- [ ] `docker ps` — *(extra)* lists `llm-rag-chromadb`.

### Optional: LLM RAG Tutorial (T1)

*(`README.md:110-121` → `llm-rag/README.md`. Not required for the app. Every command after the first runs inside the same `llm-rag` container; `--embed`, `--query`, `--chat` and `--agent` call Vertex AI again.)*
- [ ] `sh docker-shell.sh` — "Run LLM RAG Container" (`llm-rag/README.md:77-87`); skip it if you are still inside the container.
- [ ] `python cli.py --chunk --chunk_type char-split` — Chunk Documents (`llm-rag/README.md:93-118`): character splitting, JSONL files in `outputs/`.
- [ ] `python cli.py --chunk --chunk_type recursive-split` — recursive character splitting.
- [ ] `python cli.py --embed --chunk_type char-split` — Generate Embeddings (`llm-rag/README.md:124-140`) with `gemini-embedding-001`.
- [ ] `python cli.py --embed --chunk_type recursive-split`
- [ ] `python cli.py --load --chunk_type char-split` — Load Embeddings into Vector Database (`llm-rag/README.md:146-162`): deletes and re-creates the collection.
- [ ] `python cli.py --load --chunk_type recursive-split`
- [ ] `python cli.py --query --chunk_type char-split` — Query the Vector Database (`llm-rag/README.md:173-188`): similarity search for "How is tolminc cheese made?", with filters.
- [ ] `python cli.py --query --chunk_type recursive-split`
- [ ] `python cli.py --chat --chunk_type char-split` — Chat with LLM (`llm-rag/README.md:194-211`): retrieval plus a Gemini answer.
- [ ] `python cli.py --chat --chunk_type recursive-split`
- [ ] `python cli.py --chunk --embed --load --chunk_type semantic-split` — Advanced RAG: Semantic Chunking (`llm-rag/README.md:222-238`); it embeds sentence groups too, so it costs noticeably more (§2).
- [ ] `python cli.py --agent --chunk_type char-split` — Agents (`llm-rag/README.md:244-268`): the LLM picks a retrieval tool, then answers.

### Run API Service Container (T2)

*(`README.md:125-149`)*
- [ ] Open a terminal inside the `api-service` folder (`cd ../api-service` from `llm-rag`).
- [ ] Update `GCP_PROJECT` to your own project ID in `docker-shell.sh` (line 9).
- [ ] *(extra, required)* In `api-service/docker-shell.sh`, replace line 14 (`docker network create cheese-app-network`) with `docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network`, or delete it. Otherwise the script stops at `network with name cheese-app-network already exists` (§6 #1).
- [ ] `sh docker-shell.sh` — builds `llm-rag-analysis-api-service` (`pipenv sync` from `Pipfile.lock`; slow the first time) and runs it with `-p 9000:9000`, the `/secrets` mount, both env vars and `--network cheese-app-network`; you land in a `pipenv shell`.
- [ ] `uvicorn_server` — *(in the container)* runs `uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/`; wait for `Application startup complete.`
- [ ] Go to [http://localhost:9000/docs](http://localhost:9000/docs) — the Swagger page with the five `/rag` routes.
- [ ] *(extra)* Open `http://localhost:9000/` — `{"message":"Welcome to the API Service"}`.
- [ ] *(extra)* In `/docs`, try `GET /rag/embedding` with `text=hello` — `{"embedding":[…256 floats…]}`. This first real cloud call proves that key, ADC, IAM, project and API enablement all work.

### Run Frontend Container (T3)

*(`README.md:153-180`)*
- [ ] Open a new terminal inside the `frontend-ai-chatbot` folder (`cd cheese-app-v0/frontend-ai-chatbot`).
- [ ] `sh docker-shell.sh` — builds `Dockerfile.dev` (`node:20-alpine` + bash) and runs it with `-v "$(pwd)/:/app/" -p 3200:3000 --network cheese-app-network`.
- [ ] `npm install` — *(in the container)* writes `node_modules/` into your host folder through the bind mount.
- [ ] `npm run dev` — *(in the container)* runs `WATCHPACK_POLLING=true next dev`; it prints `Local: http://localhost:3000`, which is the container's view.
- [ ] Go to [http://localhost:3200](http://localhost:3200) (not 3000) — "LLM + RAG Demo" with five cards. Use Chrome (`README.md:179-180`).

### Text Chunking

*(`README.md:184-194`)*
- [ ] Go to [http://localhost:3200/chunkviz](http://localhost:3200/chunkviz) — splits a book from `public/books/` (or a `.txt` you upload) in the browser; no API calls, no cloud.

### Vector DB UI

*(`README.md:198-207`)*
- [ ] Go to [http://localhost:3200/chromaui](http://localhost:3200/chromaui), keep URL `http://localhost:8000`, tenant `default_tenant`, DB `default_database`, and click **Connect** — the sidebar lists `char-split-collection` and `recursive-split-collection`.

### Chat

*(`README.md:211-222`)*
- [ ] Go to [http://localhost:3200/chat](http://localhost:3200/chat), check which collection is selected (the first one is auto-selected) and ask "How is tolminc cheese made?" — an answer plus a "References · 10 chunks" drawer.
- [ ] *(extra)* DevTools → Network: three XHR calls per question (`:9000/rag/embedding`, `:8000/.../query`, `:9000/rag/llm-response`), plus possibly an `OPTIONS` preflight before each `POST`.

### Cheese Expert Agent

*(`README.md:226-239`)*
- [ ] Go to [http://localhost:3200/agent](http://localhost:3200/agent), pick a collection and ask "Describe where cheese making is important in Pavlos's book?" — the answer ends with a highlighted **Pavlos' fun fact:** paragraph.

### Pavlos Cheese Model

*(`README.md:243-255`)*
- [ ] Update `FINE_TUNE_GENERATIVE_MODEL` in `api-service/api/routers/rag.py` (line 22) to your own fine-tuned endpoint from L08 (`projects/<num>/locations/us/endpoints/<id>`); uvicorn reloads by itself. The default points at the instructor's project and returns 403.
- [ ] Go to [http://localhost:3200/finetunechat](http://localhost:3200/finetunechat) — the same retrieval as Chat, answered by the tuned endpoint.

### API Endpoints

*(`README.md:259-269`)*
- [ ] Compare the README table with `http://localhost:9000/docs`: `GET /rag/embedding`, `POST /rag/llm-response`, `GET /rag/agent_call`, `POST /rag/llm-agent-response`, `POST /rag/fine-tune-llm-response`.

### Shut down *(extra; the README only mentions `docker compose down`)*

- [ ] T2: `Ctrl+C` stops uvicorn, then `exit` — the `--rm` container disappears.
- [ ] T3: `Ctrl+C`, then `exit`.
- [ ] `docker compose down` — inside `llm-rag` (`README.md:106`); stops Chroma. The vectors survive in `llm-rag/docker-volumes/chromadb`; delete that folder to really reset.
- [ ] `docker network rm cheese-app-network` — *(extra, optional)* removes the shared network.
- [ ] `gcloud iam service-accounts keys list --iam-account=llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com` — *(extra)* lists your keys.
- [ ] `gcloud iam service-accounts keys delete KEY_ID --iam-account=...` — *(extra)* deletes a key you no longer use.

### When something fails *(extra)*

- [ ] `gcloud projects get-iam-policy YOUR_PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:llm-service-account@" --format="table(bindings.role)"` — *(extra)* shows which roles the service account holds (§6 #3).
- [ ] `docker rm -f llm-rag-analysis-api-service` — *(extra)* removes a leftover API container when its name "is already in use" (§6 #7).
- [ ] `lsof -i :8000` — *(extra, macOS)* shows what holds a port when Docker says "port is already allocated" (§6 #6).

---

## 1. What you build

> The code is a RAG web app, but the lecture is about **connecting local code to the cloud**. This guide therefore centres on authentication (service account → key → ADC → bearer token), IAM, networking (ports, Docker networks, `localhost` vs container names, CORS), and storage (bind-mounted volumes; GCS is shown from neighbouring repos because v0 never calls GCS, see §9). It covers RAG only as far as you need it to follow the data.

You run three things in Docker on your laptop. They talk to Google's Vertex AI ("Gemini Enterprise Agent Platform" in 2026 console wording) with a service-account key that lives *outside* the repo.

1. **`llm-rag` (Docker Compose, two containers).** A one-shot CLI (`llm-rag-cli`) chunks 11 cheese books, embeds each chunk with `gemini-embedding-001` (256-d) on Vertex AI, and loads them into a **ChromaDB** server (`llm-rag-chromadb`). Chroma keeps its data in a bind-mounted folder on your disk and stays up after the CLI exits.
2. **`api-service`.** A FastAPI/uvicorn container on port 9000. It holds the Google credentials and makes every Gemini call: embeddings, RAG answer, agent tool loop, fine-tuned model.
3. **`frontend-ai-chatbot`.** A Next.js dev server on container port 3000, published on host port 3200.

The key networking fact: **the frontend container never calls the API or Chroma itself.** It only serves JavaScript. That JavaScript runs in *your browser on the host*, and the browser calls `localhost:9000` (API) and `localhost:8000` (Chroma) directly through published ports. That is why CORS matters.

```text
 GOOGLE CLOUD  (project = $GCP_PROJECT: billing, quota and IAM are checked here)
 +--------------------------------------------------------------------------------------------+
 | IAM principal  llm-service-account@<key-project>.iam.gserviceaccount.com                   |
 |   roles        roles/aiplatform.user ("Vertex AI User" / "Agent Platform User")            |
 |                roles/storage.admin   (granted by the README; unused by v0 code)            |
 | Vertex AI      location="global": gemini-embedding-001 (256-d), gemini-3.1-flash-lite      |
 |                location="us":     tuned Gemini endpoint from L08 (/finetunechat)           |
 +--------^-------------------------------------^---------------------------------------------+
          |                                     |
          | HTTPS + "Bearer <access token>"     | same mechanism, API container
          | token minted by google-auth (ADC)   |
          | from /secrets/*.json                |
 YOUR LAPTOP (Docker Desktop)                   |
 +--------|-------------------------------------|---------------------------------------------+
 |        |                                     |                                             |
 | +------+--------------------+   +------------+--------------+  +-------------------------+ |
 | | llm-rag-cli (cli.py, uv)  |   | llm-rag-analysis-         |  | llm-rag-analysis-       | |
 | | net: llm-rag-network      |   |   api-service (FastAPI)   |  |   frontend-ai-chatbot   | |
 | | /secrets <- ../../secrets |   | net: cheese-app-network   |  | net: cheese-app-network | |
 | | /app     <- llm-rag/      |   | uvicorn 0.0.0.0:9000      |  | next dev :3000          | |
 | +------+--------------------+   | /secrets <- ../../secrets |  | /app <- frontend-       | |
 |        | llm-rag-chromadb:8000  | /app     <- api-service/  |  |         ai-chatbot/     | |
 |        | (Docker DNS name)      +------------+--------------+  +------------+------------+ |
 |        v                                     |                              |              |
 | +---------------------------+                |                              |              |
 | | llm-rag-chromadb  :8000   |                |                              |              |
 | | net: llm-rag-network      |                |                              |              |
 | | /data <- llm-rag/         |                |                              |              |
 | |   docker-volumes/chromadb |                |                              |              |
 | +------+--------------------+                |                              |              |
 |        | -p 8000:8000                        | -p 9000:9000                 | -p 3200:3000 |
 +--------|-------------------------------------|------------------------------|--------------+
          |                                     |                              |
          |                                     |                              |
     localhost:8000                        localhost:9000                 localhost:3200
          ^                                     ^                              ^
          +-------------------------------------+------------------------------+
                                                |
              Chrome on the host -- the page JavaScript runs HERE, so it makes every call:
              1) GET  page + JS                      from :3200 (frontend)
              2) GET  /rag/embedding?text=...        to   :9000 (API -> Vertex AI)
              3) POST .../collections/<id>/query     to   :8000 (Chroma; CORS check)
              4) POST /rag/llm-response              to   :9000 (API -> Vertex AI)
```

Who calls whom:
- CLI → Vertex AI (embeddings).
- CLI → Chroma via the container DNS name.
- Browser → frontend (static JS only).
- Browser → API → Vertex AI.
- Browser → Chroma via the published port.
- API ↛ Chroma (`README.md:127`: "it does not connect to ChromaDB").

---

## 2. Prerequisites and costs

**Accounts and local installs**
- A GCP project with billing enabled. You need its **project ID**, e.g. `ac215-project`.
- Docker Desktop, git, and Chrome (`README.md:179-180` says "Use Chrome browser for best performance").
- Optional: the `gcloud` CLI, for the command-line equivalents shown below.
- Suggested local layout. The `secrets/` folder sits **next to** the repos, so every repo's `../../secrets` (or `../secrets`) lands in the same place:

```text
~/Desktop/AC215/
├── cheese-app-v0/            ← git clone https://github.com/dlops-io/cheese-app-v0
│   ├── llm-rag/
│   ├── api-service/
│   └── frontend-ai-chatbot/
└── secrets/                  ← you create this; NEVER inside a git repo
    └── llm-service-account.json
```

**GCP APIs to enable**
- **Vertex AI API (`aiplatform.googleapis.com`)**. All Gemini calls use it. *No README in this repo tells you to enable it.* It was probably done in an earlier tutorial. If not, the first call fails with a "SERVICE_DISABLED / API has not been used in project" 403 (see §6).
  Suggested (not from the repo): `gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID`
- Cloud Storage API: only needed for the optional GCS exercise in §8. It is usually enabled by default.

**Service account, key, and where the code expects them** (`README.md:46-67`)
- Name: `llm-service-account`.
- Roles: **Storage Admin**, plus **Gemini Enterprise Agent Platform User** ("Vertex AI User" in older projects; role ID `roles/aiplatform.user`, as named in `llm-finetuning/README.md:44`).
- Key: JSON, renamed to `llm-service-account.json`, placed in `secrets/`.
- If you already did L05 (`llm-rag`) or L08 (`llm-finetuning`), you probably have this exact service account and key already. Those tutorials use the same name and the same roles.

| Who | Host path mounted | Container path | Env vars set | Set in |
|---|---|---|---|---|
| `llm-rag-cli` | `cheese-app-v0/llm-rag/../../secrets` = `AC215/secrets` | `/secrets` | `GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json`, `GCP_PROJECT` | `llm-rag/docker-shell.sh:7-8`, `llm-rag/docker-compose.yml:11,14-15` |
| `api-service` | `$(pwd)/../../secrets/` = `AC215/secrets` | `/secrets` | same two vars | `api-service/docker-shell.sh:8-10,23-25` |
| `frontend-ai-chatbot` | none (no credentials) | none | `NEXT_PUBLIC_BASE_API_URL=http://localhost:9000` (build-time, browser-side) | `frontend-ai-chatbot/.env.development:4` |
| `llm-rag-chromadb` | none | none | `CHROMA_CORS_ALLOW_ORIGINS` | `llm-rag/docker-compose.yml:25-26` |

You must edit `GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID` in **two** files: `llm-rag/docker-shell.sh:7` and `api-service/docker-shell.sh:9`.

**Billable resources**
- **Vertex AI embeddings.** `--embed` for `char-split` plus `recursive-split` over ~2.72 M characters of books.
  - Re-running the two splitters offline with the pinned `langchain-text-splitters` 0.3.11 gives ~8.2 k chunks (~2.9 M chars, 89 requests) for `char-split` and ~14.2 k chunks (~4.1 M chars, 148 requests) for `recursive-split`.
  - Recursive-split is larger because `RecursiveCharacterTextSplitter(chunk_size=350)` keeps langchain's default `chunk_overlap=200` (`cli.py:199-200`).
  - That is ~7 M characters, an estimated ~1.75 M input tokens at ~4 chars/token, sent in batches of 100 chunks (`batch_size=100`, `cli.py:252-253`).
  - The optional `semantic-split` (`llm-rag/README.md:222-238`) embeds sentence groups too and costs noticeably more.
- **Gemini 3.1 Flash-Lite generation.**
  - Each Chat question costs 1 embedding plus 1 generation call. The prompt is about 10 chunks × ≤350 chars plus the system prompt, with `max_output_tokens` 3000 (`rag.py:30-34`).
  - Each Agent question costs 1 embedding (the tool's `search_content`, embedded inside `/agent_call`, `rag.py:160-163`; the browser does not call `/rag/embedding` in agent mode, `ChatComponent.jsx:176-198`) and 3–7 generation calls: 1 in `/agent_call`, 1 repeated tool-choice call, then up to `MAX_AGENT_STEPS = 5` (`rag.py:83`).
- **Tuned-model endpoint** (`/finetunechat`). Billed per call in whichever project owns the endpoint (see §6 for why the default one will not work for you).
- **Nothing idles in the cloud.** No VM, no bucket, no deployed endpoint is created by this tutorial. Check current prices on the Vertex AI pricing page linked in `llm-finetuning/README.md:278`.

**Shutting down afterwards**
- API: `Ctrl+C` stops uvicorn, then `exit` once. Leaving the `pipenv shell` lets `api-service/docker-entrypoint.sh` run to its end (`:25-29`), so the container's main process exits. The container is `--rm`, so it disappears.
- Frontend: `Ctrl+C` then `exit`.
- Chroma: `docker compose down` inside `llm-rag` (`README.md:106`). Your vectors survive in `llm-rag/docker-volumes/chromadb`. Delete that folder to really reset.
- Optional: `docker network rm cheese-app-network`.
- Key hygiene, suggested (not from the repo): `gcloud iam service-accounts keys list --iam-account=llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com` shows your keys. Delete keys you no longer use with `gcloud iam service-accounts keys delete KEY_ID --iam-account=...`.

---

## 3. Concepts this tutorial teaches

### 3.1 Service account and JSON key: an identity for software
- **Explanation.** A service account is a Google identity for programs, not people. Its email looks like `llm-service-account@PROJECT.iam.gserviceaccount.com`. The downloaded JSON key contains, among other fields, `type: service_account`, `client_email`, `private_key_id`, `private_key` (an RSA private key), and `token_uri`. Whoever has the file can act as that service account until the key is deleted (or the key or service account is disabled).
- **Mental model.** The SA is the employee badge record in HR's system. The JSON key is a physical copy of the badge that anyone can pick up.
- **Analogy.** A hotel key card cut for a robot. The front desk (IAM) decides which doors it opens. The card itself just proves "I am robot #42."
- **Misconception.** "The key file contains my permissions." It does not. Permissions live in IAM policies on projects and resources, and the same key can be granted or revoked roles without re-downloading anything. A second misconception is that the key is "just config" and fine to commit. It is a long-lived password. Leaked keys are one of the most common cloud breaches, which is why the course keeps them in `secrets/` outside every repo.

### 3.2 ADC and `GOOGLE_APPLICATION_CREDENTIALS`: from file to bearer token
- **Explanation.** Look at `genai.Client(vertexai=True, project=GCP_PROJECT, location="global")` (`api-service/api/routers/rag.py:26`, `llm-rag/cli.py:35-36`). Nothing in the repo opens the key file. The google-auth library does it through **Application Default Credentials (ADC)**. It searches in this order:
  1. The file named by `GOOGLE_APPLICATION_CREDENTIALS`.
  2. The gcloud user ADC file (`~/.config/gcloud/application_default_credentials.json`, created by `gcloud auth application-default login`).
  3. The metadata server of the GCE VM, Cloud Run service, or GKE pod you are running on.

  Inside these containers only #1 exists. With a service-account key, google-auth signs a short JWT with the private key, POSTs it to `token_uri` (`https://oauth2.googleapis.com/token`), and receives an **access token**, typically valid for about an hour. Every Vertex request then carries `Authorization: Bearer <token>`. The private key itself never leaves your machine.
- **Mental model.** There are three objects: a **key** (long-lived, secret, local), a **token** (short-lived, sent on every request; google-auth mints a fresh one when it expires), and a **request**. ADC is just the "where do I find the key?" lookup.
- **Analogy.** You show your passport (key) once at the embassy (token endpoint). You get a day visa stamp (access token). You show the visa at every door (API call).
- **Misconception.** "Setting `GOOGLE_APPLICATION_CREDENTIALS` on my Mac makes the container authenticated." It does not. The env var holds a *path that must exist inside the container*. That is why the scripts set it to `/secrets/...` (a container path) and separately bind-mount the host folder to `/secrets`. A second misconception: "`gcloud auth login` is enough." That command logs in the gcloud CLI. Libraries use ADC, and the container cannot see your Mac's gcloud config anyway.

### 3.3 IAM: principal × role × resource
- **Explanation.** Every Vertex call is checked against three things: *who* (the principal, i.e. the SA email), *what* (a permission such as `aiplatform.endpoints.predict`, bundled into a role such as `roles/aiplatform.user`), and *on which resource* (here, the project in `GCP_PROJECT` and its models or endpoints). Roles are granted on a resource, and the grant is inherited downward: org → folder → project → resource. The SA's "home" project, the `project_id` inside the key, can differ from the project it is granted roles in.
- **Mental model.** A sparse 3-D matrix of (principal, role, resource) cells. A request succeeds only if a filled cell covers the permission.
- **Analogy.** A building access-control list: "badge #42 may open *lab doors* on *floor 3*." Badge #42 on floor 4 gets a red light.
- **Worked example.** Rows are principals (you, `llm-service-account`, the instructor's SA); columns are projects (`your-project`, `ac215-project`, `129349313346`). An embedding call with `GCP_PROJECT` set to your project hits a filled cell and succeeds. The same call with an unchanged `GCP_PROJECT="ac215-project"` gets a 403. The tuned-model call to project `129349313346` also gets a 403: your SA has no role there.
- **Misconception.** "403 means my key is wrong." A wrong or missing key is an *authentication* failure: no token, `DefaultCredentialsError`, or 401. A **403** usually means authentication worked and *authorization* failed. Typical causes are a missing role, the wrong project in `GCP_PROJECT`, an API not enabled, or (for `/finetunechat`) an endpoint in someone else's project. A second misconception is that "Storage Admin is needed for this app." v0 never touches Cloud Storage. The role is pre-granted so the same SA also works for L08's GCS dataset upload and tuning (least privilege would say grant it only when needed). L11 creates a separate `data-service-account` instead.

### 3.4 The `secrets/` convention and bind mounts: two filesystems, one folder
- **Explanation.** `-v HOST_PATH:CONTAINER_PATH` (or a Compose `volumes:` entry) makes a host folder appear inside the container. The course rule is: *keys live in `secrets/` next to the repo, the scripts mount it at `/secrets`, and the env var points at `/secrets/<name>.json`*. The number of `../` depends on how deep the script is. Here `api-service/docker-shell.sh:8` uses `$(pwd)/../../secrets/`, and `llm-rag/docker-compose.yml:11` uses `../../secrets` (relative to the compose file). Both resolve to `AC215/secrets`. Other course repos use the same idea at a different depth: `../secrets` in `data-labeling/docker-compose.yml:11`, `$(pwd)/../../../secrets/` in the `src/<service>/docker-shell.sh` scripts of `cheese-app-v1..v4` (e.g. `cheese-app-v2/src/api-service/docker-shell.sh:9`).
- **Mental model.** A portal. Writes on either side appear on the other. The same mechanism also mounts your *code* (`/app`) and Chroma's *data* (`/data`).
- **Analogy.** A shared drawer between two offices. The host and the container each label it differently, but it is one drawer.
- **Worked example.** From `cheese-app-v0/api-service/` (that is `$(pwd)`), `..` climbs one level and `..` again lands in `AC215/`, so `$(pwd)/../../secrets/` is `AC215/secrets/`, which the container sees as `/secrets`; `GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json` reaches the file through that mount. Now suppose the key was saved *inside* the repo, as `AC215/cheese-app-v0/secrets/llm-service-account.json`, and `sh docker-shell.sh` runs from `api-service/`. The path still resolves to `AC215/secrets/`, which does not exist, so Docker creates an empty folder there and `/secrets` is empty. The first call that needs Google credentials fails with `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` Worse, the key now sits inside a git working tree that no `.gitignore` rule protects.
- **Misconception.** "If the folder is missing Docker will error." It will not. Docker silently creates an *empty* directory at the host path, and the failure only shows up later as "File /secrets/llm-service-account.json was not found." A second misconception: "`.gitignore` protects my key." `cheese-app-v0/.gitignore:1-7` ignores only `.DS_Store`, `__pycache__`, `/llm-rag/docker-volumes` and `/llm-rag/outputs`. Nothing protects a key that you put *inside* the repo.

### 3.5 Ports, `0.0.0.0`, and names: one server, two addresses
- **Explanation.**
  - Each container has its own network namespace, so its own `localhost`.
  - **Publishing** (`-p HOST:CONTAINER`, Compose `ports:`) forwards a host port into the container: `3200→3000` for the frontend (`frontend-ai-chatbot/docker-shell.sh:11`), `9000→9000` for the API (`api-service/docker-shell.sh:20`), `8000→8000` for Chroma (`llm-rag/docker-compose.yml:21-22`).
  - The server inside must listen on `0.0.0.0` (all interfaces), not `127.0.0.1`. That is why `uvicorn ... --host 0.0.0.0 --port 9000` appears in `api-service/docker-entrypoint.sh:7`.
  - Containers on the same **user-defined Docker network** reach each other by container name through Docker's built-in DNS. The CLI therefore uses `CHROMADB_HOST = "llm-rag-chromadb"` and port 8000 (`llm-rag/cli.py:30-31`).
  - Your browser is *not* on any Docker network, so it reaches the *same* Chroma server as `http://localhost:8000`.
- **Mental model.** An apartment building. Container names are internal extension numbers, and only phones inside the building can dial them. Published ports are the street-facing doorbells.
- **Analogy.** The CLI calls "extension llm-rag-chromadb". Your browser rings "doorbell 8000". Both reach the same person.
- **Misconception.** "`next dev` printed `http://localhost:3000`, so I open port 3000." No. That is the *container* port. On the host you open `http://localhost:3200`. A second misconception is that `cheese-app-network` lets the frontend call the API. In this code the containers never call each other, because the browser does all calls. The only container-to-container hostnames in the frontend (`next.config.js:16,23,30`) point at `rag-system-api-service`, which does not exist here (see §9).

### 3.6 The browser is the integrator, and CORS is its bouncer
- **Explanation.** All page components are `'use client'` and use axios or fetch from the browser (`frontend-ai-chatbot/src/services/DataService.js:9-63`). One Chat question makes three cross-origin calls:
  1. `GET http://localhost:9000/rag/embedding?text=…`
  2. `POST http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections/<id>/query`
  3. `POST http://localhost:9000/rag/llm-response`

  (`ChatComponent.jsx:162-173`.) An *origin* is scheme + host + port, so `http://localhost:3200`, `:9000`, and `:8000` are three different origins. The browser's same-origin policy blocks reading cross-origin responses unless the server says otherwise. FastAPI says "anyone" (`allow_origins=["*"]`, `api-service/api/service.py:14-20`). Chroma lists exactly two origins: `CHROMA_CORS_ALLOW_ORIGINS: '["https://ac215-llm-rag.dlops.io","http://localhost:3200"]'` (`llm-rag/docker-compose.yml:26`). The first is the instructors' hosted copy of this frontend. The second is your local one.
- **Mental model.** CORS is enforced *by the browser*, configured *by the server*, and keyed on the *page's* origin, not on the target URL.
- **Analogy.** A nightclub (Chroma) with a guest list of page origins. The bouncer is your browser. `curl` has no bouncer, which is why `curl localhost:8000/...` works when the browser fails.
- **Worked example.** For call 2 the browser first sends an `OPTIONS` preflight stamped `Origin: http://localhost:3200`; Chroma checks that origin against its list and only then does the `POST` go out, returning ten chunks. Serve the page from `http://localhost:3300` instead and only Chroma refuses it, because the API's list is `*`. The third call (to the LLM) is then never sent, because the browser code waits for the Chroma call first. Exercise E1 walks through it.
- **Misconception.** "CORS is a security feature that protects my database from other programs." It does not. Any non-browser client, such as `curl` or the CLI, ignores it. A second misconception: "`localhost` and `127.0.0.1` are the same." For CORS they are different origins. Opening the app at `http://127.0.0.1:3200` breaks Chroma calls.

### 3.7 Persistence and storage: bind-mounted state vs cloud object storage
- **Explanation.** Containers are disposable. Every `docker run --rm` here deletes the container on exit. State survives only where it is mounted:
  - Chroma's `/data` ⇄ `llm-rag/docker-volumes/chromadb` (`docker-compose.yml:23-24`).
  - CLI outputs in `/app/outputs` ⇄ `llm-rag/outputs` (through the `../llm-rag:/app` mount, `docker-compose.yml:12`).
  - Frontend `node_modules` ⇄ `frontend-ai-chatbot/node_modules` (through `-v "$(pwd)/:/app/"`).

  These are *local* disks. The cloud equivalent is **Cloud Storage (GCS)**: a global object store of buckets and blobs, reached with the same ADC credentials and authorised by Storage roles. v0 does not use GCS. The neighbouring L03/L08 code shows the pattern (`client = storage.Client()` → `bucket.blob(name).upload_from_filename(...)`, see §5).
- **Mental model.** Local volume means "a folder on *this* laptop that the container can see". A GCS bucket means "a folder on Google's disks that *any* authorised machine can see".
- **Analogy.** A USB stick plugged into one PC versus a shared cloud drive.
- **Misconception.** "`docker compose down` deletes my vectors." It does not, because the data is in the bind-mounted folder. Deleting `llm-rag/docker-volumes/` does. A second misconception: "a bucket is a filesystem." GCS "folders" are just name prefixes, so `list_blobs(prefix=...)` is a prefix filter.

### 3.8 Calling a managed model: project, location, and model ID
- **Explanation.** A Vertex call is addressed by *project* (who pays and whose IAM applies), *location* (which regional or global API host serves it), and *model* (a publisher model name such as `gemini-3.1-flash-lite`, or a full resource path to an endpoint). The base models use `location="global"` (`rag.py:26`). The tuned model uses a full resource path, `projects/129349313346/locations/us/endpoints/7652952773041848320` (`rag.py:22`), and a second client with `location="us"` (`rag.py:111`).
- **Mental model.** It works like a postal address: country (location), company (project), and desk (model or endpoint).
- **Misconception.** "The model string is enough." For an endpoint, the project number inside the path decides whose IAM is checked. Pasting someone else's endpoint means asking for access to their project.

---

## 4. Step-by-step walkthrough

Commands in `code` are copied from the README unless marked **(suggested)**.

**Step 0. Clone into your course folder and make `secrets/`**
- Action: clone `https://github.com/dlops-io/cheese-app-v0` into `AC215/`, and create `AC215/secrets/` next to it (`README.md:58-67`).
- Under the hood: nothing yet. You are just setting up the path that `../../secrets` will resolve to.
- Checkpoint: `ls ../secrets` from inside `cheese-app-v0` should list the folder (after Step 1, the JSON).
- If it fails: if you made your whole `AC215/` folder a git repo (e.g. to push to your own GitHub), add `secrets/` to *that* repo's `.gitignore` before the first `git add`.

**Step 1. Create the service account, roles and key** (`README.md:46-56`)
- Action, in the console: **IAM & Admin → Service accounts** → create `llm-service-account`. Grant **Storage Admin** and **Gemini Enterprise Agent Platform User** ("Vertex AI User"). Open the **KEYS** tab → **ADD Key (Create New Key)** → **JSON**. Move the downloaded file to `AC215/secrets/llm-service-account.json`.
- Equivalent CLI **(suggested, not in the repo)**:
  ```bash
  gcloud iam service-accounts create llm-service-account --project=YOUR_PROJECT_ID
  gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
  gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
  gcloud iam service-accounts keys create ../secrets/llm-service-account.json \
    --iam-account=llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com
  gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID
  ```
- Under the hood: IAM writes two role bindings on the project's policy. The key download creates an RSA key pair. Google keeps the public half, and you hold the private half.
- Checkpoint: `ls -la AC215/secrets` shows `llm-service-account.json`, not `llm-service-account.json.json`. The tip is in `llm-finetuning/README.md:67`.
- If it fails: if key creation is blocked by an organization policy (for example on some university-managed projects), use a personal project or ask the admin. See §6.

**Step 2. Create the shared Docker network once** (`README.md:69-75`)
```bash
docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network
```
- Under the hood: `inspect` succeeds if the network exists, otherwise `create` runs. The command is idempotent.
- Checkpoint: `docker network ls` lists `cheese-app-network`.
- **README/code conflict:** `api-service/docker-shell.sh:14` runs a bare `docker network create cheese-app-network` under `set -e` (line 4). Once you have done this step, that script will abort. Step 4 explains the fix.

**Step 3. Build the vector DB with `llm-rag`** (`README.md:79-106`)
1. `cd cheese-app-v0/llm-rag`, then edit `llm-rag/docker-shell.sh:7` to `export GCP_PROJECT="YOUR_PROJECT_ID"`.
2. Run:
   ```bash
   sh docker-shell.sh
   ```
   Under the hood:
   - `docker-shell.sh:7-9` exports `GCP_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS="/secrets/llm-service-account.json"` and `IMAGE_NAME="llm-rag-cli"`.
   - `docker compose run --rm $IMAGE_NAME` (`:12`). Here `$IMAGE_NAME` is passed as the Compose *service* name. That works only because the service at `docker-compose.yml:6` is also called `llm-rag-cli`. If no image named `llm-rag-cli` exists yet, Compose builds it from `llm-rag/Dockerfile`: `python:3.12-slim-bookworm`, `uv sync --frozen` into `/.venv`, a non-root `app` user. An existing `llm-rag-cli` image, for example from L05, is reused without a rebuild. Then it starts the dependency `chromadb` (`docker-compose.yml:16-17`) on network `llm-rag-network` (`:1-3`), with port `8000:8000` and `./docker-volumes/chromadb:/data`.
   - Compose then runs the CLI container with `../../secrets:/secrets` and `../llm-rag:/app`. The two env vars are *interpolated from your shell* (`docker-compose.yml:14-15`).
   - The entrypoint (`llm-rag/docker-entrypoint.sh:3-15`) prints diagnostics, activates `/.venv`, and drops you into bash.

   Checkpoint: you see `Container is running!!!`, then `Architecture: aarch64` on Apple Silicon or `x86_64` on Intel, then `Python version: Python 3.12.x`, and a bash prompt in `/app`.

   **Sanity check (suggested):**
   ```bash
   ls -la /secrets
   echo $GOOGLE_APPLICATION_CREDENTIALS $GCP_PROJECT
   python -c "import google.auth; c, p = google.auth.default(); print(type(c).__name__, getattr(c, 'service_account_email', None), p)"
   ```
   You should see the key file, both env vars, and something like `Credentials llm-service-account@….iam.gserviceaccount.com <project_id-from-key>`.
3. Inside the container:
   ```bash
   python cli.py --chunk --embed --load --chunk_type char-split
   python cli.py --chunk --embed --load --chunk_type recursive-split
   ```
   Under the hood (`llm-rag/cli.py`):
   - `chunk()` (`:164-227`) splits each of the 11 books into 350-char chunks and writes `outputs/chunks-<method>-<book>.jsonl`. Char-split uses overlap 20 (`:185-189`). Recursive-split passes only `chunk_size`, so it gets langchain's default overlap of 200 (`:197-200`).
   - `embed()` (`:230-264`) sends batches of 100 chunks to `gemini-embedding-001` with `output_dimensionality=256`, retrying with exponential backoff on `errors.APIError` (`:87-121`). It writes `outputs/embeddings-<method>-<book>.jsonl` and sleeps 5 s per book (`:256`).
   - `load()` (`:267-306`) connects to `chromadb.HttpClient(host="llm-rag-chromadb", port=8000)`, **deletes and re-creates** `<method>-collection` with cosine distance, and inserts in batches of 500 with metadata `book`/`author`/`year` (`:124-161`).

   Checkpoint: `Number of files to process: 11` and many `Processing file: …` lines, then `Creating collection: char-split-collection` and either `Collection 'char-split-collection' did not exist. Creating new.` or `Deleted existing collection …`. It ends with `Finished inserting N items into collection 'char-split-collection'` for each book.

   If it fails:
   - `DefaultCredentialsError` means a path problem.
   - A 403 means IAM, project, or API (see §6).
   - `API error (code: 429) … Retrying in 5 seconds` is the built-in backoff working, so just wait.
4. `exit`. **ChromaDB keeps running** (`README.md:106`).
   - Checkpoint **(suggested)**: `curl http://localhost:8000/api/v2/version` from the host prints a version string. The frontend uses the same route (`frontend-ai-chatbot/src/hooks/hooks.jsx:14`). `docker ps` shows `llm-rag-chromadb`.
5. Optional: the step-by-step L05 tutorial in `llm-rag/README.md` (`--chunk`, `--embed`, `--load`, `--query`, `--chat`, `--agent`, semantic split) runs from the same container.

**Step 4. Run the API service** (`README.md:125-149`)
1. `cd ../api-service` and edit `api-service/docker-shell.sh:9` to set `GCP_PROJECT` to your project.
2. **Fix the network line first.** This is not in the README, but it is required if Step 2 ran or if this is your second run. Change line 14 from `docker network create cheese-app-network` to the idempotent README form, `docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network`, or delete the line. Deleting it is safe only while the network exists. Without the network, both this script's and the frontend's `docker run --network cheese-app-network` fail with `network cheese-app-network not found`.
3. Run:
   ```bash
   sh docker-shell.sh
   ```
   Under the hood:
   - The script builds `llm-rag-analysis-api-service` from `api-service/Dockerfile`: `python:3.12-slim-bookworm`, `pipenv sync` from `Pipfile.lock` (170 pinned packages, including fastapi 0.142.2, uvicorn 0.54.0, google-genai 2.28.0, google-auth 2.60.0, google-cloud-storage 3.16.0). Expect a slow first build.
   - It then runs the container with `-p 9000:9000`, `-e DEV=1`, `-v "$BASE_DIR":/app`, `-v "$SECRETS_DIR":/secrets`, both env vars, and `--network cheese-app-network` (`docker-shell.sh:19-27`).
   - Because `DEV=1`, the entrypoint opens `pipenv shell` (`docker-entrypoint.sh:25-26`) after printing the green help text listing `uvicorn_server`.
4. Inside:
   ```bash
   uvicorn_server
   ```
   - This runs `uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/` (`docker-entrypoint.sh:7`).
   - Importing `api.routers.rag` reads `os.environ["GCP_PROJECT"]` (`rag.py:15`) and builds the Gemini client (`rag.py:26`).
   - Checkpoint: `Uvicorn running on http://0.0.0.0:9000`, `Startup tasks` (from `service.py:25`), `Application startup complete.` Open `http://localhost:9000/` to get `{"message":"Welcome to the API Service"}` (`service.py:29-32`), and `http://localhost:9000/docs` for Swagger.
   - **First real cloud call:** in `/docs`, try `GET /rag/embedding` with `text=hello`. You should get `{"embedding":[…256 floats…]}`. This proves key, ADC, IAM, project, and API enablement all work.
   - `/docs` lists the same five `/rag` routes as the README's **API Endpoints** table (`README.md:259-269`; `rag.py:218-265`): `GET /rag/embedding`, `POST /rag/llm-response`, `GET /rag/agent_call`, `POST /rag/llm-agent-response`, `POST /rag/fine-tune-llm-response`.
   - If it fails:
     - `KeyError: 'GCP_PROJECT'` means you started the container without the script.
     - A 500 with `DefaultCredentialsError` in the uvicorn log means `/secrets` is empty.
     - A 403 means IAM, project, or API (see §6).

**Step 5. Run the frontend** (`README.md:153-180`)
1. In a new terminal: `cd cheese-app-v0/frontend-ai-chatbot`.
2. Run:
   ```bash
   sh docker-shell.sh
   ```
   This builds `Dockerfile.dev` (`node:20-alpine` + bash, `EXPOSE 3000`, `ENTRYPOINT ["/bin/bash"]`). It runs with `-v "$(pwd)/:/app/" -p 3200:3000 --network cheese-app-network` (`frontend-ai-chatbot/docker-shell.sh:11`).
3. Inside:
   ```bash
   npm install
   npm run dev
   ```
   - `npm install` writes `node_modules/` into your host folder through the bind mount. `npm run dev` runs `WATCHPACK_POLLING=true next dev` (`package.json:6`). Polling is needed because file-change events don't cross the Docker Desktop bind mount reliably.
   - Next.js inlines `NEXT_PUBLIC_BASE_API_URL=http://localhost:9000` (`.env.development:4`, read in `src/services/Common.js:2`) into the browser bundle.
   - Checkpoint: Next prints `Ready` and **`Local: http://localhost:3000`**, which is the container's view. Open **`http://localhost:3200`**. The home page shows "LLM + RAG Demo" with five cards and an animated architecture diagram (`src/app/page.jsx:7-13,45`).
   - If it fails: a "port is already allocated" error means 3200 is in use (see §6). `network cheese-app-network not found` means Step 2 was skipped or the network was removed, because this script never creates it (`frontend-ai-chatbot/docker-shell.sh:11`). A blank page or a slow first compile is normal for `next dev`, so wait.

**Step 6. Text Chunking: `http://localhost:3200/chunkviz`** (`README.md:184-194`)
- The browser fetches one of three books from `public/books/` (`TextChunkComponent.jsx:247,272-274`) or a `.txt` you upload, and splits it with `@langchain/textsplitters` *in the browser*. No API calls, no cloud.

**Step 7. Vector DB UI: `http://localhost:3200/chromaui`** (`README.md:198-207`)
- The form defaults are URL `http://localhost:8000`, tenant `default_tenant`, DB `default_database` (`src/app/chromaui/page.jsx:23-27`). Click **Connect**.
- Under the hood: `GET {url}/api/v2/version` (`hooks.jsx:14`), then `GET {url}/api/v2/tenants/{tenant}/databases/{db}/collections` (`hooks.jsx:43`). Both go browser → host:8000 → Chroma, so they pass through CORS. The URL, tenant and DB are stored in `localStorage` (`src/app/chromaui/page.jsx:16-18`), and the chat pages reuse them.
- Checkpoint: a sidebar with `char-split-collection` and `recursive-split-collection`. Clicking one shows its records.
- If it fails: "Failed to fetch" means Chroma isn't running (`docker ps`) or CORS blocked the request (check the DevTools console). See §6.

**Step 8. Chat: `http://localhost:3200/chat`** (`README.md:211-222`)
- The first collection is auto-selected (`ChatComponent.jsx:228-231`). Ask "How is tolminc cheese made?".
- Under the hood (`ChatComponent.jsx:162-173`): `GET :9000/rag/embedding` → `POST :8000/.../collections/<uuid>/query` with `n_results: 10` (`DataService.js:34-43`) → `POST :9000/rag/llm-response` with `prompt = query + chunks`. The API calls `gemini-3.1-flash-lite` with `SYSTEM_INSTRUCTION` (`rag.py:98-107`).
- Checkpoint: an answer plus a "References · 10 chunks" drawer showing book, author and `dist` values. Open **DevTools → Network** to see exactly 3 XHR calls per question. Both JSON `POST`s are cross-origin, so you may also see a preflight `OPTIONS` before each: one to `:8000` (Chroma) and one to `:9000/rag/llm-response`. The `GET` to `/rag/embedding` is a "simple" request and has no preflight.
- If it fails: "Not connected to a vector database" means Step 7 hasn't been done in this browser. "Sorry, something went wrong: …" shows the API or Chroma error text (`ChatComponent.jsx:210-213`).

**Step 9. Cheese Expert Agent: `http://localhost:3200/agent`** (`README.md:226-239`)
- Ask "Describe where cheese making is important in Pavlos's book?"
- Under the hood:
  1. `GET :9000/rag/agent_call?query=…`. Gemini is forced (`mode="any"`) to pick `get_book_by_author` or `get_book_by_search_content`. The API replaces `search_content` with its 256-d embedding (`rag.py:150-171`).
  2. The browser queries Chroma, with `where: {"author": …}` when the author tool was chosen (`DataService.js:45-57`).
  3. `POST :9000/rag/llm-agent-response`. The API re-asks for the tool call, appends the chunks as a function response, and loops up to 5 times. On each step Gemini may call `pavlos_fun_fact_tool`, which the server executes locally (`rag.py:173-215`, `agent_tools.py:95-136`).
- Checkpoint: an answer that ends with a highlighted **Pavlos' fun fact:** paragraph (`ChatComponent.jsx:22-28`).

**Step 10. Pavlos Cheese Model: `http://localhost:3200/finetunechat`** (`README.md:243-255`)
- Action: edit `FINE_TUNE_GENERATIVE_MODEL` at `api-service/api/routers/rag.py:22` to your own endpoint from L08. `llm-finetuning/gemini-finetuner/cli.py:91-96` prints it after training, as `projects/<num>/locations/us/endpoints/<id>`. Uvicorn reloads automatically because `rag.py` is under `api/`.
- Under the hood: same retrieval as Chat, but the browser posts to `POST :9000/rag/fine-tune-llm-response` (`DataService.js:15-17`). There `ft_client = genai.Client(vertexai=True, project=GCP_PROJECT, location="us")` calls the endpoint (`rag.py:110-120`, `:257-265`).
- If it fails: if you left the default (the instructor's project `129349313346`), expect a 403. If you get a host or 404 error with your own endpoint, see the `base_url` note in §6 and §9.

**Step 11. Shut down.** Follow the checklist in §2.

---

## 5. Code tour

```text
cheese-app-v0/
├── README.md                     # this lecture's tutorial (269 lines)
├── .gitignore                    # ignores llm-rag/docker-volumes and llm-rag/outputs; NOT secrets
├── llm-rag/                      # = L05 llm-rag repo, re-homed (secrets path now ../../secrets)
│   ├── docker-shell.sh           # sets GCP_PROJECT + GOOGLE_APPLICATION_CREDENTIALS, `docker compose run`
│   ├── docker-compose.yml        # llm-rag-cli + chromadb, network llm-rag-network, port 8000, CORS list
│   ├── Dockerfile                # python 3.12 slim + uv; venv at /.venv; non-root user `app`
│   ├── docker-entrypoint.sh      # prints arch/versions, activates venv, opens bash
│   ├── cli.py                    # chunk / embed (Vertex) / load (Chroma) / query / chat / get / agent
│   ├── agent_tools.py            # function declarations for the 2 retrieval tools
│   ├── semantic_splitter.py      # optional embedding-based splitter
│   ├── pyproject.toml, uv.lock   # pinned deps (chromadb 1.1.0, google-genai 1.39.1, langchain 0.3.27)
│   └── input-datasets/books/     # 11 .txt books
├── api-service/
│   ├── docker-shell.sh           # creates network (!), builds, runs with -p 9000, /secrets, env vars
│   ├── Dockerfile                # python 3.12 slim + pipenv sync; user `app`
│   ├── docker-entrypoint.sh      # defines uvicorn_server; DEV=1 → pipenv shell
│   ├── Pipfile, Pipfile.lock     # many deps, only fastapi/uvicorn/google-genai actually imported
│   ├── agent_tools.py            # retrieval tool decls + server-side pavlos_fun_fact_tool
│   └── api/
│       ├── service.py            # FastAPI app + CORS (*) + mounts /rag router
│       └── routers/rag.py        # Gemini client, 5 endpoints, agent loop, fine-tuned endpoint
└── frontend-ai-chatbot/
    ├── docker-shell.sh           # builds Dockerfile.dev, runs -p 3200:3000 on cheese-app-network
    ├── Dockerfile.dev            # node:20-alpine + bash (you run npm yourself)
    ├── Dockerfile                # production multi-stage build (node:18) — not used in this tutorial
    ├── .env.development          # NEXT_PUBLIC_BASE_API_URL=http://localhost:9000
    ├── .env.production           # NEXT_PUBLIC_BASE_API_URL=/api (for the nginx-hosted copy)
    ├── next.config.js            # dev rewrites to rag-system-api-service (stale, unused by pages)
    └── src/
        ├── services/DataService.js   # every HTTP call the browser makes (API + Chroma v2 REST)
        ├── services/Common.js        # BASE_API_URL from NEXT_PUBLIC_BASE_API_URL
        ├── hooks/hooks.jsx           # Chroma UI queries (version, collections, records)
        ├── components/chat/ChatComponent.jsx  # RAG / agent / fine-tuned orchestration in the browser
        └── components/architecture/ArchitectureDiagram.jsx  # animated diagram of the hosted setup
```

**Excerpt 1. How the credentials and project get into the API container.**

```bash
# api-service/docker-shell.sh:6-14
# Set vairables
export BASE_DIR=$(pwd)
export SECRETS_DIR=$(pwd)/../../secrets/
export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
export GOOGLE_APPLICATION_CREDENTIALS="/secrets/llm-service-account.json"
export IMAGE_NAME="llm-rag-analysis-api-service"


docker network create cheese-app-network
```
- `BASE_DIR=$(pwd)`: the script assumes you run it *from* `api-service/`. Every relative path depends on that.
- `SECRETS_DIR=$(pwd)/../../secrets/`: this is a **host** path, two levels up, so `AC215/secrets/`.
- `GOOGLE_APPLICATION_CREDENTIALS="/secrets/…"`: this is a **container** path. It only makes sense after the mount in the next excerpt.
- `docker network create …`: not idempotent. Combined with `set -e` (line 4), the script aborts if the network already exists. This is the #1 gotcha (§6).

**Excerpt 2. The `docker run` that wires ports, mounts, env and network.**

```bash
# api-service/docker-shell.sh:18-27
# Run the container
docker run --rm --name $IMAGE_NAME -ti \
-p 9000:9000 \
-e DEV=1 \
-v "$BASE_DIR":/app \
-v "$SECRETS_DIR":/secrets \
-e GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \
-e GCP_PROJECT=$GCP_PROJECT \
--network cheese-app-network \
$IMAGE_NAME
```
- `--rm --name … -ti`: the container is deleted on exit, has a fixed name (so two copies conflict), and is interactive.
- `-p 9000:9000`: host port 9000 forwards to container port 9000, where uvicorn listens on `0.0.0.0`.
- `-v "$BASE_DIR":/app`: live code mount. Your edits on the host are seen by `--reload`.
- `-v "$SECRETS_DIR":/secrets`: the "secrets portal".
- `-e …`: copies the two variables from the script's shell into the container's environment. Without them, `rag.py:15` raises `KeyError` and ADC finds no file.
- `--network cheese-app-network`: joins the user-defined network. Nothing in the current code needs it (§3.5).

**Excerpt 3. The Compose version of the same idea, plus Chroma.**

```yaml
# llm-rag/docker-compose.yml:1-17
networks:
    default:
        name: llm-rag-network

services:
    llm-rag-cli:
        image: llm-rag-cli
        build: .
        container_name: llm-rag-cli
        volumes:
            - ../../secrets:/secrets
            - ../llm-rag:/app
        environment:
            GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS
            GCP_PROJECT: $GCP_PROJECT
        depends_on:
            - chromadb
```
- `networks.default.name`: every service in this file joins `llm-rag-network` and can resolve the others by name.
- `../../secrets:/secrets`: a relative host path, resolved against the compose file's folder (`llm-rag/`).
- `$GOOGLE_APPLICATION_CREDENTIALS`, `$GCP_PROJECT`: **interpolated from the shell that runs `docker compose`**, which is why you must go through `docker-shell.sh`. Unset variables become blank strings, with a warning.
- `depends_on: chromadb`: `docker compose run` starts Chroma first and leaves it running afterwards.

```yaml
# llm-rag/docker-compose.yml:18-26
    chromadb:
        image: chromadb/chroma:latest
        container_name: llm-rag-chromadb
        ports:
            - 8000:8000
        volumes:
            - ./docker-volumes/chromadb:/data
        environment:
            CHROMA_CORS_ALLOW_ORIGINS: '["https://ac215-llm-rag.dlops.io","http://localhost:3200"]'
```
- `container_name: llm-rag-chromadb`: this is the DNS name the CLI uses (`cli.py:30`).
- `ports: 8000:8000`: the doorbell your browser rings.
- `./docker-volumes/chromadb:/data`: persistence. Note `chroma:latest` is unpinned (§6).
- `CHROMA_CORS_ALLOW_ORIGINS`: the guest list of *page* origins. The hosted course site and your local frontend on 3200.

**Excerpt 4. Server setup: project, models, and the ADC-backed client.**

```python
# api-service/api/routers/rag.py:14-27
# Setup
GCP_PROJECT = os.environ["GCP_PROJECT"]
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 256
GENERATIVE_MODEL = "gemini-3.1-flash-lite"
# FINE_TUNE_GENERATIVE_MODEL = "projects/129349313346/locations/us-central1/endpoints/3319822527953371136" # Old model

# projects/129349313346/locations/us/endpoints/7652952773041848320
FINE_TUNE_GENERATIVE_MODEL = "projects/129349313346/locations/us/endpoints/7652952773041848320"

#############################################################################
#                       Initialize the LLM Client                           #
llm_client = genai.Client(vertexai=True, project=GCP_PROJECT, location="global")
#############################################################################
```
- `os.environ["GCP_PROJECT"]`: fails fast at import if the variable is missing.
- `EMBEDDING_DIMENSION = 256`: must match the CLI (`cli.py:26`), or Chroma queries fail on a dimension mismatch.
- `FINE_TUNE_GENERATIVE_MODEL = "projects/129349313346/…"`: the instructor's project number. Your SA has no role there.
- `genai.Client(vertexai=True, …)`: no credentials argument, so google-auth falls back to **ADC**, which reads `GOOGLE_APPLICATION_CREDENTIALS`. `project` decides billing and IAM scope. `location="global"` selects the global Vertex host.

**Excerpt 5. One authenticated call: the embedding.**

```python
# api-service/api/routers/rag.py:89-95
def generate_query_embedding(query):
    response = llm_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSION),
    )
    return response.embeddings[0].values
```
- `embed_content(...)`: under the hood this is an HTTPS POST to Vertex carrying a Bearer token. A 403 or 404 surfaces here as a `google.genai.errors.ClientError`.
- `response.embeddings[0].values`: a Python list of 256 floats, which `GET /rag/embedding` returns as JSON (`rag.py:218-223`).

**Excerpt 6. The fine-tuned endpoint: a second client in a different location.**

```python
# api-service/api/routers/rag.py:110-120
def generate_fine_tune_chat_response(input_prompt):
    ft_client  = genai.Client(vertexai=True, project=GCP_PROJECT, location="us")
    response = ft_client.models.generate_content(
        model=FINE_TUNE_GENERATIVE_MODEL,
        contents=input_prompt,  # Input prompt
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            **generation_config,  # Configuration settings
        ),
    )
    return response.text
```
- `location="us"`: a multi-region location, required for tuned gemini-3.1-flash-lite endpoints according to `llm-finetuning/gemini-finetuner/cli.py:12-14,25`. In L08 the equivalent client also sets `http_options=types.HttpOptions(base_url="https://aiplatform.us.rep.googleapis.com")` (`llm-finetuning/gemini-finetuner/cli.py:26-33`). This one does not (§9).
- A new client is created per request. That is harmless here but wasteful.

**Excerpt 7. CORS on the API.**

```python
# api-service/api/service.py:13-20
# Enable CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- `allow_origins=["*"]`: any page origin may read responses, so the API works whether the page is on `localhost:3200`, `127.0.0.1:3200`, or `:3300`.
- `allow_credentials=False`: lets Starlette answer with a literal `Access-Control-Allow-Origin: *`. Browsers reject a literal `*` on credentialed (cookie-bearing) requests, and Starlette would echo the caller's origin instead if credentials were enabled. The frontend sends no cookies, so this setting is enough.

**Excerpt 8. Where the browser learns the API address.**

```text
# frontend-ai-chatbot/.env.development:1-4
REACT_APP_BASE_API_URL=http://localhost:9000
CHOKIDAR_USEPOLLING=true
PORT=3000
NEXT_PUBLIC_BASE_API_URL=http://localhost:9000
```
```javascript
// frontend-ai-chatbot/src/services/Common.js:1-2
//export const BASE_API_URL = process.env.REACT_APP_BASE_API_URL;
export const BASE_API_URL = process.env.NEXT_PUBLIC_BASE_API_URL;
```
- `NEXT_PUBLIC_…` variables are **baked into the JavaScript sent to the browser**. The value must therefore be reachable *from the host browser*, which is why it is `localhost:9000` and not a container name.
- In `.env.production` it is `/api`, a same-origin path that the instructors' nginx strips and proxies to `api-service:9000`. The `deployment/` folder holding that nginx config was deleted in commit `2bc29dd`.

**Excerpt 9. The browser orchestrates RAG: three cross-origin calls.**

```javascript
// frontend-ai-chatbot/src/components/chat/ChatComponent.jsx:161-173
    // RAG / fine-tuned: embed the query, retrieve chunks, then ask the LLM
    const getRagResponse = async (query) => {
        const embeddingResponse = await DataService.GenerateEmbeddings(query);
        const chunksResponse = await DataService.RetrieveChunks(url, selectedCollection, embeddingResponse.data["embedding"], tenant, dbname);
        const chat_data = {
            "session_id": sessionId,
            "prompt": query + '\n' + chunksResponse.data["documents"][0].join('\n')
        };
        const response = finetuned
            ? await DataService.ChatWithFinetunedLLM(chat_data)
            : await DataService.ChatWithLLM(chat_data);
        return { answer: response.data["response"], references: buildReferences(chunksResponse.data) };
    };
```
- Line 163: browser → `localhost:9000/rag/embedding` (API → Vertex).
- Line 164: browser → `url` (from `localStorage`, normally `http://localhost:8000`) → Chroma `query` with the vector.
- Lines 165-168: the prompt is simply the question plus the ten chunks joined by newlines. `session_id` is sent but ignored server-side (`user_sessions` at `rag.py:86` is never used).
- Lines 169-171: the same retrieval feeds either the base or the fine-tuned model.

**Excerpt 10. The Chroma REST call made from the browser.**

```javascript
// frontend-ai-chatbot/src/services/DataService.js:34-43
        var query = {
            "query_embeddings": [embedding],
            "n_results": 10,
            "include": [
                "documents",
                "metadatas",
                "distances"
            ]
        }
        return await axios.post(url + "/api/v2/tenants/" + tenant + "/databases/" + database + "/collections/" + collection + "/query", query);
```
- A JSON `POST` to another origin triggers a **CORS preflight** (`OPTIONS`) first. Chroma must answer with an `Access-Control-Allow-Origin` matching `http://localhost:3200`.
- `collection` is the collection **id** (a UUID), not its name. It is auto-selected (`ChatComponent.jsx:230`) or picked in the toolbar (`:258`).

**Excerpt 11. The CLI side: the container DNS name and idempotent loads.**

```python
# llm-rag/cli.py:271-288
    chromadb.api.client.SharedSystemClient.clear_system_cache()

    # Connect to chroma DB
    client = chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)

    # Get a collection object from an existing collection, by name. If it doesn't exist, create it.
    collection_name = f"{method}-collection"
    print("Creating collection:", collection_name)

    try:
        # Clear out any existing items in the collection
        client.delete_collection(name=collection_name)
        print(f"Deleted existing collection '{collection_name}'")
    except Exception:
        print(f"Collection '{collection_name}' did not exist. Creating new.")

    collection = client.create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"})
```
- `HttpClient(host=CHROMADB_HOST …)`: `CHROMADB_HOST = "llm-rag-chromadb"` (`cli.py:30`) resolves only *inside* `llm-rag-network`.
- delete, then create: re-running `--load` replaces the collection instead of duplicating it.
- `"hnsw:space": "cosine"`: the `dist` values shown in the UI are cosine distances, where lower means more similar.

**Excerpt 12 (from L08, for the "Storage" part of the lecture). Writing to GCS with the same ADC.**

```python
# llm-finetuning/dataset-creator/cli.py:279-294   (repo dlops-io/llm-finetuning @ 44ef6f0)
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    timeout = 300

    data_files = glob.glob(os.path.join(OUTPUT_FOLDER, "*.jsonl")) + glob.glob(
        os.path.join(OUTPUT_FOLDER, "*.csv")
    )
    data_files.sort()

    # Upload
    for index, data_file in enumerate(data_files):
        filename = os.path.basename(data_file)
        destination_blob_name = os.path.join("llm-finetune-dataset-small", filename)
        blob = bucket.blob(destination_blob_name)
        print("Uploading file:", data_file, destination_blob_name)
        blob.upload_from_filename(data_file, timeout=timeout)
```
- `storage.Client()`: no key path appears here either. ADC again picks up `GOOGLE_APPLICATION_CREDENTIALS`. **Storage Admin** (or at least an object-write role) on the bucket is what authorises the write.
- `bucket.blob("prefix/filename")`: a "folder" in GCS is just a name prefix. The read side is `mega-pipeline/transcribe_audio/cli.py:36-43` (`client.get_bucket(...)`, `bucket.list_blobs(prefix=...)`, `blob.download_to_filename(...)`).

---

## 6. Gotchas and common errors

1. **api-service script dies immediately.**
   - Symptom: `Error response from daemon: network with name cheese-app-network already exists`, then the script exits and nothing is built.
   - Cause: `api-service/docker-shell.sh:14` runs a bare `docker network create`, and `set -e` (`:4`) aborts on its non-zero exit. This happens *every time* the network exists, including after the README step "Create the Docker Network" (`README.md:74`) or on your second run. The line was added in the very last commit, `cb6fb94`.
   - Fix: replace line 14 with `docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network`, or delete it.
2. **`DefaultCredentialsError: File /secrets/llm-service-account.json was not found.`**
   - Cause: the key is not at `AC215/secrets/llm-service-account.json`. It may have the wrong name (`.json.json`, or the original `project-123abc.json`), or it was put inside the repo. Another cause is that `secrets/` isn't exactly two levels above the service folder, so `$(pwd)/../../secrets` resolves to a path that doesn't exist and Docker silently creates an empty folder there. Running the script from a different directory fails even earlier, at `docker build -t $IMAGE_NAME -f Dockerfile .` (`api-service/docker-shell.sh:16`), because both `-f Dockerfile` and `.` are relative to your current directory.
   - Fix: `cd` into the service folder before `sh docker-shell.sh`, then check `ls -la /secrets` inside the container (tips in `llm-finetuning/README.md:64-69`).
3. **403 `PERMISSION_DENIED` on the first embedding.** There are three common causes:
   - (a) `GCP_PROJECT` still says `ac215-project` (`llm-rag/docker-shell.sh:7`, `api-service/docker-shell.sh:9`). Your SA has no roles in that project.
   - (b) The SA lacks `roles/aiplatform.user` in your project. IAM changes can also take a few minutes to propagate.
   - (c) The Vertex AI API is not enabled. The message then mentions the API "has not been used in project … or it is disabled" and includes an enable link.

   Fix: correct the project ID, check roles **(suggested)** with `gcloud projects get-iam-policy YOUR_PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:llm-service-account@" --format="table(bindings.role)"`, and enable `aiplatform.googleapis.com`.
4. **`/finetunechat` fails with 403 or "not found".**
   - Cause: `rag.py:22` hard-codes an endpoint in the instructor's project `129349313346`.
   - Fix: paste your own endpoint from L08 (`README.md:247`). If *your* endpoint still fails with a host or 404 error, try adding the L08 `http_options=types.HttpOptions(base_url="https://aiplatform.us.rep.googleapis.com")` to the `ft_client` at `rag.py:111` (see §9; unverified).
5. **`KeyError: 'GCP_PROJECT'` at uvicorn startup, or blank-project errors in the CLI.**
   - Cause: the container was started without the wrapper script. A bare `docker run` of the API image has no `GCP_PROJECT`, so `rag.py:15` raises `KeyError`. Plain `docker compose run llm-rag-cli` instead prints `The "GCP_PROJECT" variable is not set. Defaulting to a blank string.`, because the compose file interpolates from your shell (`docker-compose.yml:14-15`). The CLI then gets *empty strings* (no `KeyError`), so it has neither a project nor a key path, and Gemini calls fail with credential or project errors.
   - Fix: always launch with `sh docker-shell.sh`, or `export` both variables first.
6. **Port already allocated.**
   - Symptom: `Bind for 0.0.0.0:8000 failed: port is already allocated` (or 9000 or 3200).
   - Cause: another container or app holds the port. Common culprits are other course stacks, an old Chroma, or local dev servers.
   - Fix: `docker ps` and stop the old container, or `lsof -i :8000` on macOS. Alternatively change the *host* side of the mapping only. Changing 3200 requires updating the Chroma CORS list (see item 8).
7. **Container name already in use.**
   - Symptom: `Conflict. The container name "/llm-rag-analysis-api-service" is already in use`.
   - Cause: fixed `--name` (`api-service/docker-shell.sh:19`, `frontend-ai-chatbot/docker-shell.sh:11`) plus a still-running copy in another terminal. The llm-rag stack also uses fixed names (`container_name: llm-rag-cli` / `llm-rag-chromadb`, `llm-rag/docker-compose.yml:9,20`). These are identical to the standalone L05 `llm-rag` repo, so a still-running L05 Chroma can collide on the name or on port 8000.
   - Fix: `docker rm -f llm-rag-analysis-api-service`. For an old L05 stack, run `docker compose down` in the old `llm-rag` folder first.
8. **Chroma calls blocked by CORS while API calls work.**
   - Symptom: the browser console shows "…has been blocked by CORS policy… No 'Access-Control-Allow-Origin' header…" for `localhost:8000` only.
   - Cause: the page origin isn't in `CHROMA_CORS_ALLOW_ORIGINS` (`llm-rag/docker-compose.yml:26`). Typical triggers are opening `http://127.0.0.1:3200` instead of `http://localhost:3200`, or remapping the frontend to another port. The API is unaffected because it allows `*` (`service.py:17`).
   - Fix: use `http://localhost:3200`, or add your origin to the list and recreate Chroma (`docker compose down`, then re-run `sh docker-shell.sh`).
9. **Typing a container name into the browser.**
   - Symptom: entering `http://llm-rag-chromadb:8000` in the Vector DB form fails with a DNS or "Failed to fetch" error.
   - Cause: the browser runs on the host and cannot use Docker's internal DNS.
   - Fix: use `http://localhost:8000`, the published port.
10. **Opening the port that Next or uvicorn prints.**
    - Symptom: `next dev` says `http://localhost:3000` and uvicorn says `http://0.0.0.0:9000`. `localhost:3000` fails on the host.
    - Cause: those are container-side addresses. Nothing is published on host port 3000. `0.0.0.0` is a "listen on all interfaces" address, not a destination; some browsers map it to the local machine and others block it.
    - Fix: open `http://localhost:3200` and `http://localhost:9000`.
11. **`http://localhost:3200/docs` errors.**
    - Cause: the dev rewrites in `next.config.js:19-24` proxy `/docs` to `http://rag-system-api-service:9000/docs`, a hostname that doesn't exist in this setup (the API container is `llm-rag-analysis-api-service`).
    - Fix: use `http://localhost:9000/docs` as the README says (`README.md:149`).
12. **Edits to `api-service/agent_tools.py` don't take effect.**
    - Cause: uvicorn only watches `--reload-dir api/` (`docker-entrypoint.sh:7`), and `agent_tools.py` lives at `api-service/agent_tools.py`, outside `api/`.
    - Fix: `Ctrl+C` and re-run `uvicorn_server`.
13. **Service account key creation is blocked.**
    - Symptom: the console says key creation is disabled by an organization policy.
    - Cause: some organizations enforce a "disable service account key creation" policy, often by default on newer orgs. This applies to projects under an organization, such as university accounts.
    - Fix: use a personal project, ask the org admin, or (advanced) use user ADC: `gcloud auth application-default login`, then mount `~/.config/gcloud` into the container at `/home/app/.config/gcloud` and unset `GOOGLE_APPLICATION_CREDENTIALS`. This is not in the repo.
14. **The key gets committed by accident.**
    - Cause: placing `secrets/` inside a repo. `cheese-app-v0/.gitignore` does not ignore it. Making the whole `AC215/` folder a git repo (e.g. to publish your notes) puts `AC215/secrets` *inside* that repo.
    - Fix: add `secrets/` and `*.json` keys to that repo's `.gitignore` *before* the first commit. If a key ever reaches GitHub, delete it in IAM → Keys immediately, because history rewriting is not enough.
15. **Apple Silicon.** No special flags are needed. `python:3.12-slim-bookworm`, `node:20-alpine` and `chromadb/chroma` are multi-arch images, and the llm-rag entrypoint prints `Architecture: aarch64` (`llm-rag/docker-entrypoint.sh:4`). The first `pipenv sync` of 170 packages (`api-service/Pipfile.lock`) is slow. `build-essential` is installed (`api-service/Dockerfile:4`) in case a wheel must be compiled.
16. **Mixing host and container `node_modules`.**
    - Symptom: `npm run dev` on the Mac fails after you ran `npm install` in the container, or the other way round.
    - Cause: the bind mount (`frontend-ai-chatbot/docker-shell.sh:11`) shares one `node_modules` folder between Linux-musl and macOS binaries, for example Next's SWC compiler.
    - Fix: run npm only inside the container, or delete `node_modules` when switching.
17. **Stale or unpinned Chroma.**
    - Cause: `chromadb/chroma:latest` (`docker-compose.yml:19`) can change under you, while the CLI client is pinned to `chromadb 1.1.0` (`uv.lock`).
    - Fix: if a new image breaks client calls or the v2 REST paths used by the UI (`DataService.js:22,43`), pin a specific image tag.
    - To reset all vectors: `docker compose down`, then delete `llm-rag/docker-volumes/`, then rebuild the vector DB.
18. **One book missing author metadata.**
    - Cause: `book_name = filename.split(".")[0]` (`llm-rag/cli.py:178`) truncates "Womans Institute Library of Cookery. Volume 2_ …" at the first dot. The `book_mappings` entry for it (`cli.py:70`) therefore never matches in the lookup at `cli.py:135-138`. Its chunks get no `author`/`year`, and the agent's author filter can never select them.
    - Fix: use `os.path.splitext(filename)[0]`.
19. **429 / quota during `--embed`.** The CLI retries with backoff (`cli.py:108-119`). The API service has no retry, so a 429 surfaces in the chat as "Sorry, something went wrong".
20. **"Use Chrome" (`README.md:179-180`).** The repo gives no reason. The note is inherited from the standalone L05 README, where each copy sits directly under a link to the hosted HTTPS site (`llm-rag/README.md:95-98,162-165,211-214,268-271` @ `e17a39f`). That hosted page called your `http://localhost:8000` Chroma, and browsers differ on such HTTPS-to-local requests. That is the likely origin, though the repo does not confirm it. Locally (http → http on localhost) other browsers should also work. Stick with Chrome to match the instructions.

---

## 7. Where this sits in the course

**What earlier lectures gave you**
- **L01–L04 (VMs, Docker, Compose, `port_toy`).**
  - The `docker-shell.sh` pattern.
  - Bind mounts.
  - User-defined networks and published ports. `port_toy/README.md:52`: "Browser → localhost:8090 → Gateway → processor:9200 → Processor".
  - In L03 `mega-pipeline`, a first taste of reading and writing GCS buckets with a service account.
- **L05 (`llm-rag`).** The same CLI and Chroma stack. Back then, the frontend lived in the cloud at `ac215-llm-rag.dlops.io` (the old links in `llm-rag/README.md:95,162,211,268` of the standalone repo) and talked to *your* local Chroma through your browser.
- **L08 (`llm-finetuning`).** The same `llm-service-account` key. Uploading a dataset to GCS (§5, Excerpt 12). A tuned Gemini endpoint, which is exactly what `/finetunechat` calls.
- **L09 (`cheese-app-ci-cd`, guest lecture).** Testing and pre-commit. It is unrelated to cloud wiring, and nothing from it is reused here.

**What L10 adds**
- You now run **the whole app yourself**: three containers, two Docker networks, one browser, one cloud. You also have to reason about every connection:
  - Which identity (the SA key through ADC).
  - Which authorisation (IAM roles on `GCP_PROJECT`).
  - Which address (container DNS vs published port).
  - Which origin policy (CORS on API and Chroma).
  - Which state survives (bind-mounted volumes).
- It also introduces the **secrets-folder convention** that every later repo uses. Each repo just uses a different key name: `ml-workflow.json` in `cheese-app-v2..v4/src/api-service/docker-shell.sh:29`, `deployment.json` in `cheese-app-v3/src/deployment/docker-shell.sh:16`, `data-service-account.json` in `data-labeling/docker-compose.yml:14`.

**Concrete diff vs the previous version** (standalone `llm-rag` @ `e17a39f` → `cheese-app-v0/llm-rag` @ `cb6fb94`)

```text
llm-rag/docker-compose.yml   |  ../secrets:/secrets  ->  ../../secrets:/secrets   (one level deeper)
llm-rag/README.md            |  links ac215-llm-rag.dlops.io/{chunkviz,chromaui,chat,agent}
                             |    -> http://localhost:3200/{...}; folder tree shows cheese-app-v0/
llm-rag/.gitignore           |  removed; root .gitignore now ignores /llm-rag/docker-volumes, /llm-rag/outputs
api-service/                 |  NEW (10 files): FastAPI + Gemini client + agent loop
frontend-ai-chatbot/         |  NEW (76 files): Next.js app formerly only hosted by the course
README.md                    |  NEW: SA setup, network, 3 services, 5 UI steps, endpoint table
```

The repo's own history also matters:
- Commit `2bc29dd` ("pavlos buldozer", 2026-10-07) **deleted `deployment/`**. That folder held Ansible playbooks, an nginx config that proxied `/api` → `http://api-service:9000` and `/` → `http://frontend:3000`, and Let's Encrypt TLS for `ac215-llm-rag.dlops.io`. The same commit added `--network cheese-app-network` to both run scripts and added the animated `ArchitectureDiagram.jsx`. That diagram still depicts the *hosted* topology (Nginx on a GCP VM, `src/components/architecture/ArchitectureDiagram.jsx:16-28,426-429`).
- Commit `cb6fb94` ("final") added the non-idempotent `docker network create` (§6 #1).

**What comes next**
- **L11 Data Labeling and Versioning.** It reuses the auth pattern with a new SA, `data-service-account` with **Storage Admin** (`data-labeling/README.md:45-46,50`, mounted from `../secrets`). It finally exercises GCS for real: buckets, prefixes, and bucket **CORS** for a localhost UI (`data-labeling/README.md:149-155`). DVC with a GCS remote follows in `data-versioning`.
- **Later lectures.**
  - L13–L15 (Vertex AI training and pipelines) run code *in* Google Cloud, where ADC comes from the metadata server instead of a key file.
  - L18 (`cheese-app-v1/v2`) reorganises this app into `src/<service>/` folders (hence `../../../secrets`).
  - L20–L23 (Pulumi, K8s, CI/CD) replace the deleted `deployment/` folder with infrastructure-as-code.

---

## 8. Exercises

Commit to an answer before you open each one.

### Test yourself

**Q1. Name the three places ADC looks for credentials, and which one this tutorial uses.**
<details><summary>Answer</summary>

(1) The file named by `GOOGLE_APPLICATION_CREDENTIALS`; (2) the gcloud user ADC file, `~/.config/gcloud/application_default_credentials.json`; (3) the metadata server of the GCE VM, Cloud Run service or GKE pod the code runs on. Inside these containers only (1) exists: `/secrets/llm-service-account.json` (§3.2).
</details>

**Q2. Why is `GOOGLE_APPLICATION_CREDENTIALS` set to `/secrets/…` rather than to a Mac path?**
<details><summary>Answer</summary>

The variable is read by google-auth *inside the container*, so it must hold a path that exists there. The scripts bind-mount the host's `AC215/secrets` at `/secrets` (`api-service/docker-shell.sh:23`, `llm-rag/docker-compose.yml:11`); a Mac path does not exist in the container (§3.2, §3.4).
</details>

**Q3. The CLI talks to `llm-rag-chromadb:8000` and the browser to `localhost:8000`. Why can't they swap?**
<details><summary>Answer</summary>

`llm-rag-chromadb` is a Docker DNS name that resolves only for containers on `llm-rag-network`; the browser runs on the host, outside every Docker network. Inside the CLI container, `localhost` is that container's own loopback, not the host where port 8000 is published (§3.5, E5).
</details>

**Q4. Which component would break first if you served the frontend at `http://localhost:3300`, and why does the API keep working?**
<details><summary>Answer</summary>

The Chroma calls: `CHROMA_CORS_ALLOW_ORIGINS` lists only `https://ac215-llm-rag.dlops.io` and `http://localhost:3200` (`llm-rag/docker-compose.yml:26`). The API allows `*` (`service.py:17`), so its calls still pass (§3.6, E1).
</details>

**Q5. You got a 403 on `/rag/embedding`. List three distinct causes and how to tell them apart.**
<details><summary>Answer</summary>

(a) `GCP_PROJECT` still says `ac215-project`: the error names `projects/ac215-project/...`. (b) The SA lacks `roles/aiplatform.user` in your project (or the grant has not propagated yet): check with `gcloud projects get-iam-policy YOUR_PROJECT_ID --flatten="bindings[].members" --filter="bindings.members:llm-service-account@" --format="table(bindings.role)"`. (c) The Vertex AI API is not enabled: the message says the API "has not been used in project … or it is disabled" and includes an enable link (§6 #3, E3).
</details>

**Q6. After `docker compose down`, are your embeddings gone? What would make them gone?**
<details><summary>Answer</summary>

No. Chroma's `/data` is bind-mounted from `llm-rag/docker-volumes/chromadb` (`docker-compose.yml:23-24`), and `docker compose down` leaves that folder alone. Deleting `llm-rag/docker-volumes/` makes them gone (§3.7).
</details>

**Q7. Your key works for embeddings. You keep the instructor's fine-tuned endpoint `projects/129349313346/...` (the default at `rag.py:22`). Which part of the request decides whose IAM policy is checked: `GCP_PROJECT`, the key's `project_id`, or the endpoint path?**
<details><summary>Answer</summary>

The endpoint path, i.e. the resource. Your principal would need a role on project `129349313346`, which it doesn't have, so `/finetunechat` gets a 403 (§3.3, §3.8, §6 #4).
</details>

### Hands-on, debugging and conceptual

**E1. Hands-on: move the frontend port.** Change `-p 3200:3000` to `-p 3300:3000` in `frontend-ai-chatbot/docker-shell.sh:11`, restart, and open `http://localhost:3300/chat`. Predict which of the three calls fail, then run it.
<details><summary>Answer</summary>

`localStorage` is per origin, so first you must reconnect on `/chromaui`. Its `GET :8000/api/v2/version` is blocked by CORS ("Failed to fetch"), because `http://localhost:3300` isn't in `CHROMA_CORS_ALLOW_ORIGINS` (`docker-compose.yml:26`). The URL is still saved, so `/chat` lets you type, but its collection list is also blocked and shows "None found". When you ask a question, call 1 (`GET :9000/rag/embedding`) succeeds because FastAPI allows `*` (`service.py:17`). Call 2 (`:8000`) fails CORS. Call 3 is never sent, because `getRagResponse` awaits call 2 first (`ChatComponent.jsx:163-171`). The chat shows "Sorry, something went wrong: Network Error". Fix: add `"http://localhost:3300"` to the JSON list, run `docker compose down` in `llm-rag`, then `sh docker-shell.sh` to recreate Chroma with the new env. `curl http://localhost:8000/api/v2/version` works throughout, because curl doesn't enforce CORS.
</details>

**E2. Debugging: the instant crash.** `sh docker-shell.sh` in `api-service` prints `Error response from daemon: network with name cheese-app-network already exists` and returns to your prompt. Why, and what is the minimal fix?
<details><summary>Answer</summary>

Line 14 runs `docker network create` unconditionally, and `set -e` (line 4) exits on its failure. Replace it with `docker network inspect cheese-app-network >/dev/null 2>&1 || docker network create cheese-app-network` (`README.md:74`), or `docker network create cheese-app-network || true`.
</details>

**E3. Debugging: authentication vs authorisation.** For each message, say which layer failed and what you check. (a) `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` (b) a 403 `PERMISSION_DENIED` mentioning `aiplatform.endpoints.predict` on `projects/ac215-project/...`. (c) a 403 saying the Vertex AI API "has not been used in project … or it is disabled".
<details><summary>Answer</summary>

- (a) Authentication: the file is missing in the container. Check the host path `AC215/secrets/`, the exact filename, the `cd` location, and `ls -la /secrets`.
- (b) Authorisation on the wrong project: you didn't change `GCP_PROJECT` from `ac215-project` (`docker-shell.sh:9` / `llm-rag/docker-shell.sh:7`). Even with the right project, the SA needs `roles/aiplatform.user` there.
- (c) API enablement: run `gcloud services enable aiplatform.googleapis.com --project=YOUR_PROJECT_ID`, or click the link in the error.
</details>

**E4. Hands-on: who am I?** Inside the llm-rag container, run `python -c "import google.auth; c, p = google.auth.default(); print(type(c).__name__, getattr(c, 'service_account_email', None), p)"`. Then run it again as `GOOGLE_APPLICATION_CREDENTIALS= python -c "..."`. Predict both outputs.
<details><summary>Answer</summary>

First run: something like `Credentials llm-service-account@<proj>.iam.gserviceaccount.com <project_id in the key>`. Note that `p` is the key's home project, which can differ from `GCP_PROJECT`; the code passes `GCP_PROJECT` explicitly. Second run: with the variable empty there is no gcloud config in the container and no metadata server, so you get a `DefaultCredentialsError` ("Your default credentials were not found…"). It may first spend a few seconds probing for a metadata server.
</details>

**E5. Conceptual + hands-on: make two networks meet.** Suppose you want the API to query Chroma server-side. (a) From inside the API container run `python -c "import urllib.request;print(urllib.request.urlopen('http://llm-rag-chromadb:8000/api/v2/version').read())"` and predict the result. (b) On the host run `docker network connect cheese-app-network llm-rag-chromadb` and repeat. (c) Why would `http://localhost:8000` never work from inside the API container?
<details><summary>Answer</summary>

(a) Name resolution fails (`URLError … Name or service not known`), because Chroma is only on `llm-rag-network`. (b) It now prints the version: the container joined a second network, and Docker's DNS on `cheese-app-network` resolves its name. (c) Inside a container, `localhost` is that container's own loopback. Port 8000 is published on the *host*, not inside the API container. (`host.docker.internal:8000` would also work on Docker Desktop, via the host.)
</details>

**E6. Hands-on: least privilege.** Remove **Storage Admin** from `llm-service-account` (console IAM page, or `gcloud projects remove-iam-policy-binding YOUR_PROJECT_ID --member="serviceAccount:llm-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com" --role="roles/storage.admin"`). Predict which v0 features break.
<details><summary>Answer</summary>

None. No v0 code touches GCS: `google-cloud-storage` is listed in `api-service/Pipfile:11` but never imported. What would break is L08's `dataset-creator --upload` (Excerpt 12) and the GCS exercise E7. That is the argument for granting roles when a workload needs them, and re-adding Storage Admin (or `roles/storage.objectAdmin` on one bucket) before you reuse this SA for L08-style GCS work. L11 uses its own `data-service-account`.
</details>

**E7. Hands-on: write to and read from GCS with the same credentials.** Create a bucket **(suggested)** with `gcloud storage buckets create gs://YOUR_BUCKET --location=us-central1 --project=YOUR_PROJECT_ID`. Then, inside the API container's `pipenv shell` (which has `google-cloud-storage` 3.16.0 from the lockfile), run:
```python
from google.cloud import storage
client = storage.Client(project="YOUR_PROJECT_ID")
bucket = client.bucket("YOUR_BUCKET")
bucket.blob("cheese-app-v0/hello.txt").upload_from_string("hello from the api-service container")
print(bucket.blob("cheese-app-v0/hello.txt").download_as_text())
for b in client.list_blobs("YOUR_BUCKET", prefix="cheese-app-v0/"):
    print(b.name, b.size)
```
Predict what happens with and without Storage Admin, and how to clean up.
<details><summary>Answer</summary>

With the role, it prints the text, then `cheese-app-v0/hello.txt 36`. Without it, you get a 403 such as "…does not have storage.objects.create access…". The key is the same in both cases; only IAM differs. Clean up with `gcloud storage rm -r gs://YOUR_BUCKET`. Storage of a few bytes costs essentially nothing, but don't leave buckets lying around.
</details>

**E8. Conceptual: why `NEXT_PUBLIC_BASE_API_URL=http://localhost:9000` and not `http://llm-rag-analysis-api-service:9000`?** Both containers are on `cheese-app-network`.
<details><summary>Answer</summary>

The variable is inlined into JavaScript that runs in the *host browser* (`Common.js:2`, `.env.development:4`), and the browser can't resolve Docker DNS names. Container names only work for server-side code inside the network. Examples are the (stale) `next.config.js` rewrites, or the deleted nginx config that proxied `/api` → `http://api-service:9000`. In production, `.env.production:2` uses `/api` so the browser stays same-origin and nginx does the container-to-container hop.
</details>

---

## 9. Errata and open questions

**Errors and inconsistencies (with evidence)**
1. **Non-idempotent network creation breaks the README flow.** `README.md:69-75` creates the network idempotently "once", but `api-service/docker-shell.sh:14` then runs `docker network create cheese-app-network` under `set -e` (`:4`) and aborts. The line was added in the final commit `cb6fb94`.
2. **The lecture's "Storage" topic isn't exercised.**
   - The README grants **Storage Admin** (`README.md:51`), and `google-cloud-storage` is in `api-service/Pipfile:11`.
   - Yet no file in the repo imports `google.cloud.storage` or touches a bucket (grep over `*.py`/`*.js*`).
   - The only GCS mention is in the diagram caption about the fine-tuning dataset (`ArchitectureDiagram.jsx:23,132`).
   - The GCS read/write material lives in L03 `mega-pipeline` and L08 `llm-finetuning` (§5, Excerpt 12), and is exercised for real in L11.
3. **Stale dev rewrites.** `frontend-ai-chatbot/next.config.js:16,23,30` target `http://rag-system-api-service:9000`, but the API container is `llm-rag-analysis-api-service` (`api-service/docker-shell.sh:11`). The pages don't use these rewrites, but `localhost:3200/docs` and `/openapi.json` would fail.
4. **The fine-tuned endpoint is hard-coded to the instructor's project.** `rag.py:22` points at `projects/129349313346/...`. The README does tell you to replace it (`README.md:247`), but the default will 403 for students.
5. **The fine-tuned client may lack the L08 regional `base_url`.** L08 builds its `location="us"` client with `base_url="https://aiplatform.us.rep.googleapis.com"` (`llm-finetuning/gemini-finetuner/cli.py:26-33`). `rag.py:111` doesn't. Whether google-genai 2.28.0 (pinned in `api-service/Pipfile.lock`) resolves `location="us"` correctly without it is **unverified**: the code was not run for this guide.
6. **Inconsistent role naming.** `README.md:52` says "Gemini Enterprise Agent Platform User". `llm-finetuning/README.md:44-46` says "Agent Platform User (formerly Vertex AI User; role ID `roles/aiplatform.user`)". It is the same role, but students searching the console may be confused.
7. **API enablement isn't mentioned.** Neither `README.md` nor `llm-rag/README.md` mentions enabling the Vertex AI API.
8. **The home page describes the hosted deployment, not the local one.** `src/app/page.jsx:41` says "This web app, hosted on Google Cloud…", and `ArchitectureDiagram.jsx:16-28,426-429` draws Nginx on a GCP VM. The "llm-rag CLI" link on the same page (`page.jsx:40`) points at the standalone `dlops-io/llm-rag` repo, not this repo's `llm-rag/` folder. In this tutorial everything runs locally, and the `deployment/` folder that implemented the hosted version was removed in `2bc29dd`.
9. **Book-name parsing bug.** `llm-rag/cli.py:178` (`filename.split(".")[0]`) drops metadata for "Womans Institute Library of Cookery. Volume 2_ …" (see §6 #18).
10. **Agent flow repeats the tool-choice LLM call.** In `/rag/llm-agent-response`, `generate_agent_call(..., first_call=False)` first re-runs the forced tool-choice call (`rag.py:134-148`), then uses `response.candidates[0].content` from that *new* call (`:177`) together with the `function_name` the browser executed (`:182`). This costs an extra LLM call, and the names could disagree if the model chose differently the second time. Temperature 0 makes that unlikely.
11. **Dead or legacy code.**
    - `user_sessions` (`rag.py:86`) and `session_id` (sent by `ChatComponent.jsx:166,191`) are unused.
    - `/chatui` calls `DataService.RetrieveChunks(response.data["embedding"], tenant, dbname)` with the wrong arguments (`src/components/chatui/ChatComponent.jsx:50` vs `DataService.js:24`). The page isn't linked in the nav.
    - `query()` prints `"load()"` (`llm-rag/cli.py:309-310`).
12. **Heavy, mostly unused API dependencies.** `api-service/Pipfile:9-21` installs `llama-index`, `langchain`, `chromadb`, `pandas`, `google-generativeai`, `google-cloud-aiplatform`, `google-cloud-storage`, `requests`, `python-multipart` and `user-agent`. Only `fastapi` (plus its dependency `starlette`, imported directly in `service.py:3`), `uvicorn` and `google-genai` are used, so build time and image size are inflated.
13. **Course-site inconsistencies.** `tutorials_demo.md:142` titles the L10 tutorial "LLM-Fine Tuning" while its description says "Cheese-app-V0" (a copy-paste leftover). `_modules/week-06.md:5-7` lists this topic (Oct 6) as "Lecture 8", while `tutorials_demo.md:139` calls it Lecture 10.
14. **Minor.**
    - The production `frontend-ai-chatbot/Dockerfile:2,17` uses `node:18-alpine`, while `Dockerfile.dev:1` uses `node:20-alpine` (prod isn't used here).
    - `.DS_Store` files are committed (`git ls-files` lists `.DS_Store`, `api-service/.DS_Store`, `api-service/api/.DS_Store`) even though `.gitignore:2` now ignores them.
    - `llm-rag/out.txt` is a committed run log.
    - The README says "pick a collection" (`README.md:215,232`), but the first collection is auto-selected (`ChatComponent.jsx:228-231`). Check which one is highlighted before asking.

**Open questions (could not be determined from the sources)**
- Does the current `chromadb/chroma:latest` image still honour the `CHROMA_CORS_ALLOW_ORIGINS` env var and persist to `/data`? The compose file assumes both. Since the tag is unpinned, behaviour may drift.
- `useDeleteCollection` calls `DELETE ${url}/api/v2/collections/${collectionName}?tenant=…&database=…` (`hooks.jsx:94`). The record add, update and delete hooks likewise call `${url}/api/v2/collections/${collectionId}/{add,update,delete}` (`hooks.jsx:214,243,185`). Are those valid Chroma v2 routes? The read calls in the same file use `/api/v2/tenants/{t}/databases/{d}/collections/...`, so editing or deleting from the UI may fail. Reading (the tutorial's use) is unaffected.
- `@app.on_event("startup")` (`service.py:23`) is deprecated in FastAPI in favour of lifespan handlers. With the pinned fastapi 0.142.2 / starlette 1.7.0 it may emit a deprecation warning. It was not run to confirm that it still works.
- `PORT=3000` in `.env.development:3` probably has no effect on `next dev`, which defaults to 3000 anyway. This is harmless but unverified.
- Exact cost: the §2 token count is an estimate from offline chunk counts (~7 M embedded characters across both methods, from 2.72 M characters of books) at ~4 chars/token. Gemini's real tokenizer will differ. Current per-token prices were not available in the sources.
- Whether the Ed lesson (166035) adds slides or steps beyond the GitHub README. The Ed content was not accessible when these sources were checked.

---

## Links

- README sections (pinned commit): [Prerequisites](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#prerequisites) · [Setup GCP Service Account](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#setup-gcp-service-account) · [Create the Docker Network](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#create-the-docker-network) · [Build the Vector DB](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#build-the-vector-db) · [Optional: LLM RAG Tutorial](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#optional-llm-rag-tutorial) · [Run API Service Container](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#run-api-service-container) · [Run Frontend Container](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#run-frontend-container) · [Text Chunking](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#text-chunking) · [Vector DB UI](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#vector-db-ui) · [Chat](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#chat) · [Cheese Expert Agent](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#cheese-expert-agent) · [Pavlos Cheese Model](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#pavlos-cheese-model) · [API Endpoints](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/README.md#api-endpoints)
- Optional tutorial: [`llm-rag/README.md`](https://github.com/dlops-io/cheese-app-v0/blob/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb/llm-rag/README.md) (pinned commit) · latest README on [`main`](https://github.com/dlops-io/cheese-app-v0#cheese-app-v0-rag-web-app)
- Ed lesson: [L10 · Connecting to the Cloud: Networking, Authentication & Storage](https://edstem.org/us/courses/97373/lessons/166035/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for L10.
- Context repos (pinned commits): [`llm-rag` @ `e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91) · [`llm-finetuning` @ `44ef6f0`](https://github.com/dlops-io/llm-finetuning/tree/44ef6f0a70315aa0a551b8565ca862679a87c1eb) · [`mega-pipeline` @ `c6bbc9b`](https://github.com/dlops-io/mega-pipeline/tree/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc) · [`port_toy` @ `d190c71`](https://github.com/dlops-io/port_toy/tree/d190c7122fc35cc1f7e15e467d2babdfc24b5c0c) · [`data-labeling` @ `03c3e27`](https://github.com/dlops-io/data-labeling/tree/03c3e277abeee2cdaf4c1a8149c11c9fd259577d) · [`data-versioning` @ `b240b1a`](https://github.com/dlops-io/data-versioning/tree/b240b1a03e0abd1964b689ea68e35f0990a33ebc)
- Previous lecture: [L09 · Automating Software Development: CI, unit testing](L09-ci-testing-precommit.md)
- Next lecture: [L11 · Data Labeling, Versioning and Monitoring](L11-data-labeling-versioning.md) (a new service account, and GCS for real)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II](L03-containers-2-mega-pipeline.md) · [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md) · [L05 · Introduction to RAG](L05-rag.md) · [L08 · LLM: Finetuning](L08-llm-finetuning.md) · [L13 · Advanced Training Workflows: experiment tracking (W&B), multi-GPU, serverless training (Vertex AI)](L13-training-workflows.md) · [L14 · Serverless Deployment: Cloud Functions, Cloud Run](L14-serverless-deployment.md) · [L15 · ML Workflows with Vertex AI](L15-vertex-ml-workflows.md) · [L18 · APIs + Frontend](L18-apis-frontend.md) · [L20 · Deployment: Pulumi](L20-deployment-pulumi.md) · [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md) · [L22 · Scaling: Kubernetes (cloud)](L22-kubernetes-cloud.md) · [L23 · Final Deployment and Review](L23-final-cicd-deployment.md)
