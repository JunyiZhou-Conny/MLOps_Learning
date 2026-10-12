# L18 · APIs + Frontend — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166043/) · Tutorials: [`dlops-io/cheese-app-v1`](https://github.com/dlops-io/cheese-app-v1) `main` @ [`ce03a10`](https://github.com/dlops-io/cheese-app-v1/tree/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8) and [`dlops-io/cheese-app-v2`](https://github.com/dlops-io/cheese-app-v2) `main` @ [`14f2a14`](https://github.com/dlops-io/cheese-app-v2/tree/14f2a1420b43e9f24e977a9e67b53d7e2614013d) · Video: planned · Made from the verified digest, 2026-10-12

## 中文速览

- **做什么：** 在自己的 laptop 上用 Docker 搭 cheese app "Formaggio.me" 的 full-stack 骨架，分两步。v1：一个 FastAPI container（uvicorn，port 9000）+ 一个 static frontend container（`http-server`，port 8080），加一个 `/square_root/` route，看它自动出现在 `/docs` 里。v2：ChromaDB vector-db（8000）+ 带 newsletter / podcast / LLM / LLM + CNN / RAG 等 router 的 api-service（调 Vertex AI 上的 Gemini）+ 两个 frontend：simple HTML/JS（8080）和 React/Next.js（3000）。
- **核心概念 1 · REST + FastAPI：** decorator 建 route table，type hints 变成 validation（`?x=abc` → 422）和 `/docs`；`include_router(prefix=...)` 拼出 `/newsletters/...`、`/llm/...`。uvicorn 是 server，FastAPI 是 app；`--host 0.0.0.0` 才能让 `-p 9000:9000` 访问到它。
- **核心概念 2 · 两种 localhost：** API 在 Docker network `cheese-app-network` 上用 container name `cheese-app-vector-db:8000` 找到 Chroma；browser 通过 published port `localhost:9000` 调 API。frontend container 只负责把文件发给 browser，真正调 API 的是 browser 里跑的 JS，所以代码里才需要 CORS。
- **核心概念 3 · CORS：** 由 browser 执行，问的是 server 给不给权限；POST JSON 或带 `X-Session-ID` header 的 request 会先发一个 preflight `OPTIONS`。看到 "CORS error" 多半其实是 endpoint crash 了（unhandled 500 不带 CORS header），先看 uvicorn log。
- **核心概念 4 · state 和 dev loop：** HTTP 是 stateless，chat state 分三处：`X-Session-ID`（simple frontend 每次 page load 生成新 uuid，React 存在 `localStorage`）、`/persistent/chat-history/...` 里的 JSON（source of truth）、进程内的 `chat_sessions` dict（cache，`--reload` 后清空）。源码 bind mount 到 `/app`，改代码不用 rebuild image，只有 dependencies 或 Dockerfile 变了才要 rebuild。
- **最费时间的坑 1：** `gemini-2.0-flash-001` 已于 2026-06-01 retired，不 patch 的话所有 chat 都会失败。把三个 `api/utils/*.py` 里的 `GENERATIVE_MODEL` 改成 `gemini-3.1-flash-lite`（可能还要改 location），但千万不要单独改 RAG 的 `EMBEDDING_MODEL`。
- **最费时间的坑 2：** 就算 RAG router 注释掉了，API 也必须先有 Chroma 才能启动（import 时就去连 server → `ValueError: Could not connect to a Chroma server`），所以先做 vector-db。另外：两个 container 要的 key 文件名不一样（`ml-workflow.json` vs `llm-service-account.json`）；`GCP_PROJECT="ac215-project"` 两处都要改；Linux 上先自己 `mkdir -p secrets persistent-folder`，否则是 root-owned；README 让你粘贴 `square_root`，但 v2 代码里已经有了；RAG 的第二条消息一定报 500（`llm_rag_chat.py:99`）。
- **做完要删：** 云上不建任何资源，只按 Gemini call 计费。退出所有 container shell，`docker stop cheese-app-vector-db`（CLI 退出后 Chroma 还在跑），可选 `docker network rm cheese-app-network`，再 `docker system prune`。TensorFlow 的 image 有好几 GB，用 `docker image ls` 看看要不要删。

## At a glance

- **What you build.** You run the cheese app "Formaggio.me" on your laptop in Docker in two passes: v1 is one FastAPI container (uvicorn, port 9000) plus one static HTML/JS container (`http-server`, port 8080), and you add a route and watch it appear in `/docs`. v2 grows that into five cooperating containers (a ChromaDB vector DB on 8000 loaded with cheese-book embeddings, its one-shot loader CLI, a FastAPI service whose newsletter, podcast, LLM, LLM + CNN and RAG chat routers call Gemini on Vertex AI, a simple HTML/JS frontend on 8080 and a React/Next.js frontend on 3000), and the frontends' JavaScript runs in your browser and calls the API at `localhost:9000`.
- **Time needed.** A rough estimate (not timed) is 3 hours: under an hour for v1, the rest for v2, where the first build of the multi-GB TensorFlow API image and the first `npm install` take a good share. Add time for the model patch (section 6, item 4), without which no chat works.
- **Prerequisites.**
  - Docker Desktop (macOS/Windows), or Docker Engine plus the compose plugin (Linux); an editor (the READMEs assume VS Code) and a browser. No host Python or Node.
  - Disk and network for a multi-GB API image (`tensorflow==2.19.0`) and two downloads from GitHub releases (the CNN and the embeddings).
  - For v2's chat only: a GCP project with billing and the Vertex AI API enabled, and the L15 `ml-workflow` service-account key, saved as `secrets/ml-workflow.json` (and under a second name, `llm-service-account.json`, for the vector-db container; section 6, item 2). v1, newsletters, podcasts and `/square_root/` need no GCP.
  - Background: L02/L04 (containers, ports, Docker networks), L05 (the RAG pipeline), L10 (`cheese-app-v0`: FastAPI + Next.js + CORS), L15 (the key). See section 7.
- **What it costs.** Only Vertex AI requests: one Gemini call per chat message (`llm`, `llm-cnn` text, `llm-rag`) plus one embedding call per RAG message. `python cli.py --download --load` makes no Vertex calls (the embeddings come precomputed); re-embedding with `--embed` would bill. No cloud resources are created.
- **What to tear down** (details in section 2):
  1. Exit every container shell (`exit` or Ctrl-D); every `docker run` uses `--rm`, so those containers disappear.
  2. `docker stop cheese-app-vector-db`: Chroma keeps running after the CLI exits (or `docker-compose down` from `src/vector-db`).
  3. Optionally `docker network rm cheese-app-network`, then the README's `docker system prune`.
  4. *(extra)* `docker system prune` keeps tagged images. `docker image ls` shows `cheese-app-api-service` (multi-GB because of TensorFlow), `cheese-app-vector-db-cli`, `cheese-app-frontend-simple`, `cheese-app-frontend-react` and `chromadb/chroma`; `docker image rm <name>` removes one if you need the disk space.
  5. On Linux, `src/frontend-react/node_modules/` and `.next/` are root-owned (section 4, B7), so deleting them needs `sudo`.
  6. Nothing in the cloud. Consider revoking the key in IAM when the course ends.
- **How to read the references.** Paths are written from the folder that holds your clones: `cheese-app-v2/src/api-service/api/service.py:7` means line 7 of `src/api-service/api/service.py` inside your `cheese-app-v2` clone. Every `path:line` was checked against the commits below on 2026-10-12. If you use this workspace's `tools/sync_tutorials.py`, your clones are in `tutorials/`, so the `secrets/` and `persistent-folder/` that the scripts expect next to the repo go in `tutorials/` too.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Ed lesson:** https://edstem.org/us/courses/97373/lessons/166043/ — not accessible when these sources were checked; the guide is built from the repos and the course-site source.
- **Course-site map:** `2026-AC215/tutorials_demo.md:223-240` lists four tutorials for L18: "Frontend and FastAPI" (cheese-app-v1), "Backend and FastAPI" (v2 `#tutorial-23-backend-apis`), "Frontend Simple" (v2 `#tutorial-24-simple-frontend-app`) and "Frontend React" (v2 `#tutorial-25-react-frontend-setup`).
- **Repos you run in this lecture:**
  - `dlops-io/cheese-app-v1`, branch `main`, commit `ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8` (2025-11-02 07:33:53 -0500, "gitignore").
  - `dlops-io/cheese-app-v2`, branch `main`, commit `14f2a1420b43e9f24e977a9e67b53d7e2614013d` (2025-11-16 09:16:15 -0500, "image chat fix").
- **Repos cited only for context:**
  - `dlops-io/cheese-app-v0` `main` `cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb` (2026-10-08 11:57:11 -0400). This is the L10 app, rebuilt in October 2026. It is *newer* than v1/v2, which matters in sections 6 and 9.
  - `dlops-io/cheese-app-v3` `main` `3ecef56fea879ac480d260c0906cd95baf05179a` (2025-11-28 16:00:06 -0500). The L20/L22 successor.
  - `dlops-io/ml-workflow` `main` `972ffbb5cb148f9fa6256e7137300dff2b174e2e` (2025-10-23 10:28:44 -0400). L15. It creates the `ml-workflow.json` key that the v2 API expects.
  - Both v1 and v2 also have an `origin/pipenv` branch: v1 `348d00107784dc023377ddfec0f5c9fa468ed2c2` (2025-04-03), v2 `adaa2acd0106b4dc6e8674e53e99e38f1ba84f95` (2025-04-08). Each is the pre-`uv` snapshot, i.e. the merge-base of `main`. This guide does not use them.
- **README sections covered:**
  - `cheese-app-v1/README.md`: the whole file, i.e. `#prerequisites`, `#setup-environments`, `#create-a-local-secrets-folder`, `#backend-api-container`, `#view-api-docs`, `#frontend-app-simple-container`, `#docker-cleanup`.
  - `cheese-app-v2/README.md`: `#tutorial-23-environment-setup` and `#tutorial-23-vector-db-for-rag-setup` (prerequisites the course site does not link), then `#tutorial-23-backend-apis`, `#tutorial-24-simple-frontend-app`, `#tutorial-25-react-frontend-setup`, `#docker-cleanup`. The README numbers its tutorials 23/24/25 (they are not lecture numbers), and three different H2s all say "Tutorial (23)" (`cheese-app-v2/README.md:12`, `:40`, `:67`).
- **Colab notebooks:** none for L18.

</details>

## Command checklist

Each `sh docker-shell.sh` runs on your host in the folder its section names; the commands after it run in the container shell it opens. The README's `cd` lines assume you start in the folder that holds your clones. Commands are written exactly as the READMEs write them; *(extra)* marks commands that come from this guide, not the README. Browser and editor steps are plain items.

### Part A · cheese-app-v1 · Prerequisites

- [ ] Have Docker installed (Docker Desktop on macOS/Windows; Docker Engine plus the compose plugin on Linux).
- [ ] Have VSCode or editor of choice.

### Part A · cheese-app-v1 · Setup Environments

- [ ] Clone or download https://github.com/dlops-io/cheese-app-v1.
- [ ] At the same level as the `cheese-app-v1` folder create a folder called **secrets** (outside Git).
- [ ] `mkdir -p secrets persistent-folder` *(extra)* — run in the folder that contains `cheese-app-v1`; the README asks only for `secrets`, but the scripts also mount `persistent-folder`, and creating both yourself keeps them from being root-owned on Linux.
- [ ] `ls ..` *(extra)* — from inside `cheese-app-v1`; should show `cheese-app-v1 persistent-folder secrets`.

### Part A · cheese-app-v1 · Backend API Container

- [ ] Open a terminal and go to `cheese-app-v1/src/api-service` (the README says `cheese-app-v1/api-service`, which lacks the `src/`).
- [ ] `docker ps` *(extra)* — `cheese-app-api-service` must not be running yet (v1, v2 and v3 share the name), and nothing else (e.g. L10's API) may hold port 9000.
- [ ] `docker stop cheese-app-api-service` *(extra)* — only if the previous command showed it.
- [ ] `sh docker-shell.sh` — builds the `cheese-app-api-service` image (python 3.12 + uv) and opens bash in it with the code at `/app`, `/secrets`, `/persistent` and port 9000 published; expect `Container is running!!!`.
- [ ] `uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/ "$@"` — starts the dev server and reloads on every change under `api/`; wait for `Application startup complete.`
- [ ] Browser: `http://localhost:9000/` — returns `{"message":"Welcome to AC215"}`.
- [ ] Editor: open `api/service.py` and add the `square_root` route at the end of the file (snippet in section 4, A3); uvicorn reloads.
- [ ] Browser: `http://localhost:9000/square_root/` — returns `2.23606797749979`.
- [ ] Browser: `http://localhost:9000/square_root/?x=2&y=10` — returns `10.198039027185569`.
- [ ] Browser: `http://localhost:9000/docs` — expand `GET /square_root/`, then "Try it out" → Execute.

### Part A · cheese-app-v1 · Frontend App (Simple) Container

- [ ] Open a second terminal and go to `cheese-app-v1/src/frontend-simple` (the README says `cheese-app-v1/frontend-simple`).
- [ ] `sh docker-shell.sh` — builds `cheese-app-frontend-simple` (`node:20-alpine` + `http-server`), mounts the folder at `/app` and publishes 8080.
- [ ] `http-server` — serves the folder on 0.0.0.0:8080.
- [ ] Browser: `http://localhost:8080/` — "🧀 Formaggio.me is here!" and two hard-coded podcast cards. Use `localhost`, not the `172.17.x.x` address `http-server` prints.
- [ ] Editor: open `index.html` and add some text with a `<p>` tag inside the existing hero section (do not paste the README's whole `<body>`; section 4, A5). Refresh `http://localhost:8080/`.
- [ ] `http-server -c-1` *(extra)* — Ctrl-C and restart with caching off if your edit does not show (the default cache is 3600 s); or hard-refresh.

### Part A · cheese-app-v1 · Docker Cleanup

- [ ] Exit both container shells (`exit` or Ctrl-D).
- [ ] `docker container ls` — check what is still running.
- [ ] Stop any container that is running.
- [ ] `docker system prune` — removes stopped containers, unused networks, dangling images and build cache.
- [ ] `docker image ls` — the tagged images are still there (v2 rebuilds the same names).

### Part B · cheese-app-v2 · Tutorial (23): Environment Setup

- [ ] Clone or download https://github.com/dlops-io/cheese-app-v2, next to `cheese-app-v1`.
- [ ] At the same level as the `cheese-app-v2` folder create a folder called **secrets** (the one from Part A) and add the secret file from the `ml-workflow` tutorial: the L15 key, named `ml-workflow.json`.
- [ ] *(extra)* Also put `llm-service-account.json` (L05/L10) in `secrets/`, or copy your key under that name too: the vector-db container expects it (section 6, item 2).
- [ ] `mkdir -p persistent-folder` *(extra)* — in the folder that holds `secrets/`, if Part A did not create it.
- [ ] Editor: change `GCP_PROJECT="ac215-project"` to your project ID in **both** `cheese-app-v2/src/api-service/docker-shell.sh:11` and `cheese-app-v2/src/vector-db/docker-shell.sh:9`.
- [ ] Editor *(extra)*: change `GENERATIVE_MODEL = "gemini-2.0-flash-001"` to `gemini-3.1-flash-lite` in `api/utils/llm_utils.py`, `llm_cnn_utils.py` and `llm_rag_utils.py`; leave `EMBEDDING_MODEL` alone (section 6, item 4).
- [ ] `ls ../secrets` *(extra)* — from `cheese-app-v2`; lists both JSON files.
- [ ] `docker ps` *(extra)* — stop any v1 container still running (`docker stop <name>`): v2 reuses its names and ports.

### Part B · cheese-app-v2 · Tutorial (23): Vector DB for RAG Setup

- [ ] `cd cheese-app-v2/src/vector-db`
- [ ] `sh docker-shell.sh` — creates `cheese-app-network` if missing, builds `cheese-app-vector-db-cli`, then `docker-compose run` starts Chroma (`cheese-app-vector-db`, port 8000) and opens a shell in the CLI container.
- [ ] Editor *(extra, Linux without `docker-compose`)*: replace line 20 of `docker-shell.sh` with `docker compose run --rm --service-ports $IMAGE_NAME` and rerun the previous step.
- [ ] `python cli.py --download --load --chunk_type recursive-split` — downloads the precomputed chunks + embeddings zip (about 23 MB) and loads 14,356 chunks into `recursive-split-collection`; no Vertex calls.
- [ ] `ls /app/outputs` *(extra)* — should list 22 `.jsonl` files; check this if the load said `Number of files to process: 0`.
- [ ] Keep the Chroma container running while setting up the backend API service and frontend apps (you may `exit` the CLI shell; Chroma stays up).
- [ ] `docker ps | grep cheese-app-vector-db` *(extra)* — on the host; Chroma is still up.

### Part B · cheese-app-v2 · Tutorial (23): Backend APIs

- [ ] `cd cheese-app-v2/src/api-service`
- [ ] `sh docker-shell.sh` — builds `cheese-app-api-service` (slow the first time: TensorFlow) and runs it on `cheese-app-network` with port 9000 published and `DEV=1`, which keeps you in a shell.
- [ ] Review `docker-shell.sh` (port mapping `-p 9000:9000`, development mode `-e DEV=1`) and `docker-entrypoint.sh` (dev vs. production settings).
- [ ] `export WATCHFILES_FORCE_POLLING=true` *(extra)* — only if your edits are not detected on Docker Desktop; run it before `uvicorn_server`.
- [ ] `uvicorn_server` — the v1 uvicorn command wrapped in a shell function; on first start it downloads and loads the CNN.
- [ ] Browser: `http://localhost:9000` — returns `{"message":"Welcome to AC215"}`.
- [ ] Create Demo Routes: `square_root` is already at `cheese-app-v2/src/api-service/api/service.py:30-33`, so do **not** paste it again. Browser: `http://localhost:9000/square_root/` and `http://localhost:9000/square_root/?x=2&y=10`.
- [ ] View API Docs: `http://localhost:9000/docs`. Try `GET /newsletters/` with `limit=2`; fill the `X-Session-ID` field before trying a chat route.
- [ ] Enable Cheese App API Routes: four routers are already enabled. For RAG, uncomment `app.include_router(llm_rag_chat.router, prefix="/llm-rag")` (`cheese-app-v2/src/api-service/api/service.py:41`); optionally also `test_router` (lines 9 and 43) for `GET /test/test-chroma`.
- [ ] Browser: `http://localhost:9000/docs` again. Keep this container running.

### Part B · cheese-app-v2 · Tutorial (24): Simple Frontend App

- [ ] `cd cheese-app-v2/src/frontend-simple` — in a new terminal.
- [ ] `sh docker-shell.sh` — same image name and port as v1's simple frontend.
- [ ] `http-server`
- [ ] Browser: `http://localhost:8080/index.html` — the landing page, now with "Newsletters" and "Cheese Assistant" links.
- [ ] Browser: `http://localhost:8080/newsletters.html` — three cards (the API log shows a 307, then a 200). Review the API integration in `newsletters-main.js` (the README says `newsletters.html`).
- [ ] Browser: `http://localhost:8080/chat.html` — ask "How is cheese made?". Review the code in `chat-main.js` (the README says `chat.html`).

### Part B · cheese-app-v2 · Tutorial (25): React Frontend Setup

- [ ] `cd cheese-app-v2/src/frontend-react` — in a new terminal.
- [ ] `sh docker-shell.sh` — builds `cheese-app-frontend-react` from `Dockerfile.dev` and mounts the folder at `/app` with port 3000.
- [ ] `npm install` — first time only; writes `node_modules/` into your host folder through the bind mount.
- [ ] `npm run dev` — runs `WATCHPACK_POLLING=true next dev`; wait for `✓ Ready`.
- [ ] Browser: http://localhost:3000 (the API service container must be running).
- [ ] Review App: Home; Newsletters and Podcasts; Chat Assistant with LLM, LLM + CNN (attach a cheese photo) and RAG (only after enabling its router; the second RAG message fails, section 6, item 5).
- [ ] Review App Code in `frontend-react/src`: `src/services/DataService.js`, then the pages `src/app/page.jsx`, `src/app/newsletters/page.jsx`, `src/app/podcasts/page.jsx`, `src/app/chat/page.jsx`, then `src/components` (layout, chat).
- [ ] `rm -rf node_modules .next` *(extra)* — only if you switch between a host and a container install; needs `sudo` on Linux.

### Part B · cheese-app-v2 · Docker Cleanup

- [ ] Exit all container shells.
- [ ] `docker container ls` — Chroma (`cheese-app-vector-db`) is still listed.
- [ ] Stop any container that is running.
- [ ] `docker stop cheese-app-vector-db` *(extra)* — stops Chroma (or `docker-compose down` from `src/vector-db`).
- [ ] `docker network rm cheese-app-network` *(extra)* — optional.
- [ ] `docker system prune`
- [ ] `docker image ls` — remove big images you no longer need with `docker image rm <name>` *(extra)*.

---

## 1. What you build

You build the full-stack skeleton of "Formaggio.me", the cheese app, in two passes, all on your laptop in Docker.

**v1** is the minimum. One Python container runs a FastAPI app under `uvicorn` on port 9000, and one Node container serves static HTML/JS on port 8080 with `http-server`. You add a route (`/square_root/`) and watch it appear in the auto-generated `/docs`.

**v2** turns that into a real multi-service app.
- A **vector-db** stack (Docker Compose) starts a ChromaDB server on 8000 and a one-shot CLI that downloads pre-computed cheese-book embeddings and loads them into a collection named `recursive-split-collection`.
- The **api-service** grows seven routers: newsletters, podcasts, plain LLM chat, LLM+CNN image chat, RAG chat, a stub "agent" chat and a test router. It talks to Gemini on Vertex AI with a service-account key, to Chroma over a Docker network, and to a TensorFlow CNN it downloads at start-up.
- Two frontends call it: the **simple** HTML/JS site (8080) and a **React/Next.js** app (3000).

The key fact to remember is that **neither frontend container ever calls the API**. They only hand files to your browser. The JavaScript then runs *in the browser on your host* and calls `http://localhost:9000` through the published port. That is why CORS exists in the code, and why only the API and Chroma need to share a Docker network.

```text
 YOUR LAPTOP (host OS + Docker)                                                   GOOGLE CLOUD
 ===============================================================================  =========================
                                                                                  Vertex AI (us-central1)
  BROWSER (runs on the host, NOT in a container)                                  gemini-2.0-flash-001
   tab A  http://localhost:8080/chat.html     (simple)                            text-embedding-004 (256-d)
   tab B  http://localhost:3000/chat?model=llm (React)                                    ^
     |  (1) GET html/js/css           |  (2) XHR/axios JSON + header X-Session-ID         | (4) HTTPS, OAuth token
     |      from :8080 / :3000        |      to http://localhost:9000 (CORS!)             |     minted from
     v                                v                                                   |     /secrets/ml-workflow.json
 ---- published ports  -p HOST:CONTAINER ---------------------------------------------------|-------------------------
   8080:8080            3000:3000             9000:9000                                    |
     |                    |                     |                                          |
 +---v--------------+ +---v----------------+ +--v-----------------------------------------+-+
 | frontend-simple  | | frontend-react     | | api-service   (container cheese-app-api-service)|
 | node:20-alpine   | | node:20-alpine     | | python:3.12-slim + uv venv /home/app/.venv     |
 | `http-server`    | | `npm run dev`      | | `uvicorn_server` -> uvicorn api.service:app    |
 |  0.0.0.0:8080    | |  next dev :3000    | |   --host 0.0.0.0 --port 9000 --reload          |
 | /app <- src/     | | /app <- src/       | | /app        <- src/api-service (bind mount)    |
 |   frontend-simple| |   frontend-react   | | /secrets    <- ../../../secrets                |
 | net: default     | | (node_modules land | | /persistent <- ../../../persistent-folder      |
 |      bridge      | |  in host folder)   | |   chat-history/<model>/<session>/<chat>.json   |
 +------------------+ +--------------------+ |   experiments/  (CNN .keras, from github.com)  |
                                             | net: cheese-app-network                        |
                                             +----------------------+-------------------------+
                                                                    | (3) HTTP to cheese-app-vector-db:8000
                                                                    |     (Docker DNS, container name)
          docker-compose (src/vector-db)                            v
 +---------------------------------------+   (0) load    +--------------------------------------------+
 | cheese-app-vector-db-cli  (one-off)   |-------------->| cheese-app-vector-db  chromadb/chroma:latest|
 | python cli.py --download --load       |   HTTP :8000  | published 8000:8000                        |
 |   --chunk_type recursive-split        |               | ./docker-volumes/chromadb:/chroma/chroma   |
 | /app <- src/vector-db                 |               | collection "recursive-split-collection"    |
 | /secrets <- ../../../secrets          |               | net: cheese-app-network (external)         |
 | (0a) downloads cheese-books-          |               +--------------------------------------------+
 |      embeddings.zip from github.com   |
 +---------------------------------------+
```

The numbered flows: (0) you load the vector DB once. (1) the browser fetches the page from a frontend container. (2) the page's JS calls the API from the browser. (3) on a RAG chat, the API embeds the question and queries Chroma by container name. (4) every text chat calls Gemini (an image sent to LLM + CNN goes only to the local CNN).

---

## 2. Prerequisites and costs

**Accounts**
- A GCP project with billing and the **Vertex AI API** (`aiplatform.googleapis.com`) enabled. You only need it for chat. Newsletters, podcasts, `/square_root/` and the whole of v1 work without GCP (v2 still needs internet for the image builds and the first-start CNN download).
- No cloud resources are created. The API passes `GCS_BUCKET_NAME` (`cheese-app-v2/src/api-service/docker-shell.sh:12`, `:31`), but no code reads it. `grep -rn GCS_BUCKET_NAME src/api-service/api` returns nothing.

**Local installs**
- Docker Desktop (macOS/Windows), or Docker Engine plus the compose plugin (Linux). The vector-db script calls the hyphenated `docker-compose` (`cheese-app-v2/src/vector-db/docker-shell.sh:20`). See section 6.
- An editor (the READMEs assume VS Code) and a browser. You need **no** host Python or Node, because everything runs in containers.
- Disk and network: the API image installs `tensorflow==2.19.0` (`cheese-app-v2/src/api-service/pyproject.toml:13`), so expect a multi-GB image and a slow first build. On first start the API downloads a CNN zip, and the vector-db CLI downloads an embeddings zip, both from GitHub releases.

**Folder layout the scripts assume.** The api-service `docker-shell.sh` resolves `$(pwd)/../../../secrets/` (and `persistent-folder`) from `src/api-service/`, and the vector-db compose file mounts `../../../secrets` relative to `src/vector-db/`, i.e. both point *next to* the repo folder (`cheese-app-v2/src/api-service/docker-shell.sh:9-10`, `cheese-app-v2/src/vector-db/docker-compose.yml:10`; the `SECRETS_DIR` exported at `cheese-app-v2/src/vector-db/docker-shell.sh:8` is never used by compose):

```text
AC215/                      <- e.g. ~/Desktop/AC215
  cheese-app-v1/
  cheese-app-v2/
  secrets/
    ml-workflow.json          <- read by v2 api-service
    llm-service-account.json  <- read by v2 vector-db-cli
  persistent-folder/          <- v1 and v2 api-service, mounted at /persistent
```

If your clones live in this workspace's `tutorials/` folder (`tools/sync_tutorials.py`), read `AC215/` above as `AC215/tutorials/`: `secrets/` and `persistent-folder/` sit next to the clones.

**Secrets and environment variables (v2):**

| Container | Env var | Value | Set at |
|---|---|---|---|
| api-service | `GOOGLE_APPLICATION_CREDENTIALS` | `/secrets/ml-workflow.json` | `cheese-app-v2/src/api-service/docker-shell.sh:29` |
| api-service | `GCP_PROJECT` | `"ac215-project" # CHANGE TO YOUR PROJECT ID` | `cheese-app-v2/src/api-service/docker-shell.sh:11` |
| api-service | `CHROMADB_HOST` / `CHROMADB_PORT` | `cheese-app-vector-db` / `8000` | `cheese-app-v2/src/api-service/docker-shell.sh:13-14` |
| api-service | `DEV` | `1` (keeps a shell open instead of starting the server) | `cheese-app-v2/src/api-service/docker-shell.sh:28` |
| vector-db-cli | `GOOGLE_APPLICATION_CREDENTIALS` | `/secrets/llm-service-account.json` | `cheese-app-v2/src/vector-db/docker-shell.sh:10`, passed via `cheese-app-v2/src/vector-db/docker-compose.yml:13` |
| vector-db-cli | `GCP_PROJECT` | `"ac215-project"` | `cheese-app-v2/src/vector-db/docker-shell.sh:9` |
| frontend-react | `NEXT_PUBLIC_BASE_API_URL` | `http://localhost:9000` | `cheese-app-v2/src/frontend-react/.env.development:4` |

- The README says "Add the secret file from the `ml-workflow` tutorial" (`cheese-app-v2/README.md:25`). In L15, `ml-workflow.json` is the key of the `ml-workflow` service account, which has Storage Admin, AI Platform Admin, Vertex AI Administrator and Service Account User (`ml-workflow/README.md:43-45`). For this lecture, `roles/aiplatform.user` would be enough.
- The two containers expect **two different file names**. If you only have one key, copy it under both names, or edit one `docker-shell.sh` (see section 6).

**Billable resources**
- Only Vertex AI requests. You pay per Gemini call (every chat message in `llm`, `llm-cnn` text and `llm-rag`), plus one embedding call per RAG message (`cheese-app-v2/src/api-service/api/utils/llm_rag_utils.py:155`). `cli.py --download --load` makes **no** Vertex calls, because the embeddings come precomputed (`cheese-app-v2/src/vector-db/cli.py:478-494`, `:270-309`). Re-embedding with `--embed` would bill.
- **Shutting down.** Exit each container shell (`exit` or Ctrl-D; every `docker run` uses `--rm`). Chroma keeps running after the CLI exits, so stop it with `docker stop cheese-app-vector-db` (or `docker-compose down` from `src/vector-db`). Then optionally run `docker network rm cheese-app-network` and the README's `docker system prune` (`cheese-app-v2/README.md:241-247`). There is nothing in the cloud to delete. Consider revoking the key in IAM when the course ends.

---

## 3. Concepts this tutorial teaches

### 3.1 REST: an API is a set of nouns (paths) you act on with verbs (HTTP methods)
- **Explanation.** A REST API exposes *resources* at URLs: `/newsletters/`, `/newsletters/{id}`, `/llm/chats/{chat_id}`. A client sends an HTTP *request*: method, path, query string, headers and an optional JSON body. The server returns a *response*: a status code, headers and a body, usually JSON. GET reads, POST creates or acts. In this app, `POST /llm/chats` *starts* a chat and `POST /llm/chats/{chat_id}` *continues* one (`cheese-app-v2/src/api-service/api/routers/llm_chat.py:47`, `:93`).
- **Mental model.** It is a function call over the network. The path plus the method names the function, query, path and body carry the arguments, and the JSON response is the return value. FastAPI makes this literal, since `square_root(x, y)` *is* the handler for `GET /square_root/?x=2&y=10`.
- **Analogy.** A restaurant order slip. The table number is the path, "add" or "cancel" is the method, and the items are the body. The kitchen sends back a plate plus a ticket stamped 200 or 404.
- **Misconception.** "REST means JSON over HTTP, so any URL is RESTful." The status codes and verbs matter. This code sometimes returns 500 where 404 is right. `GET /newsletters/does-not-exist` raises `FileNotFoundError`, which becomes a 500 (`cheese-app-v2/src/api-service/api/routers/newsletter.py:40-42`).

### 3.2 FastAPI: decorators build a route table, type hints build validation and docs
- **Explanation.**
  - **Routes.** `app = FastAPI(...)` (`cheese-app-v2/src/api-service/api/service.py:12`) is an object holding a routing table. `@app.get("/")` registers a function under a (method, path) key. `APIRouter()` (`cheese-app-v2/src/api-service/api/routers/newsletter.py:10`) is a mini-table. `app.include_router(newsletter.router, prefix="/newsletters")` (`cheese-app-v2/src/api-service/api/service.py:37`) grafts it in, so the router's `"/"` becomes `/newsletters/` and its `"/{newsletter_id}"` becomes `/newsletters/{newsletter_id}`.
  - **Type hints become validation.** `x: float` rejects `?x=abc` with **422**. `limit: Optional[int] = None` is an optional query param. A pydantic `BaseModel` parameter (`ChatMessage`, `cheese-app-v2/src/api-service/api/utils/chat_utils.py:12-16`) means "parse the JSON body into this". `Header(None, alias="X-Session-ID")` reads a header.
  - **Docs.** FastAPI also turns the whole table into an OpenAPI schema and serves it at `/docs`.
- **Mental model.** A tree of routes, with routers as branches mounted under prefixes. Each leaf carries a typed signature that FastAPI checks before your code runs.
- **Analogy.** A building directory: floor (prefix) → room (path) → door policy (types and validation).
- **Misconception.** "`/newsletters` and `/newsletters/` are the same." They are different routes. Starlette's `redirect_slashes` answers the "wrong" one with a **307** redirect to the other. You will see this in the logs from the simple frontend (section 4, B6).

### 3.3 ASGI server vs. app: uvicorn, `--host 0.0.0.0`, `--reload`, dev vs. prod
- **Explanation.** FastAPI is the *app*, a Python object. **uvicorn** is the *server* that owns the socket, parses HTTP and calls the app. The string `api.service:app` means "import module `api/service.py` and use its variable `app`". `--host 0.0.0.0` makes uvicorn listen on all interfaces of the container, so Docker's port forward can reach it. `--reload --reload-dir api/` runs a watcher that restarts a worker process whenever a file under `api/` changes. In v2 those flags are wrapped in shell functions in `docker-entrypoint.sh`. `DEV=1` keeps you in a shell where you type `uvicorn_server`. Without `DEV`, the container starts `uvicorn_server_production` itself (`cheese-app-v2/src/api-service/docker-entrypoint.sh:14-20`, `:32-38`).
- **Mental model.** A receptionist (uvicorn) answers the phone and hands each call to the specialist (your app). With `--reload`, a supervisor swaps in a fresh specialist every time you edit the manual.
- **Analogy.** A theatre (server) and a play (app). The same play can run in a dev theatre with live script edits or a production theatre without them.
- **Misconception.** "`127.0.0.1` inside the container is my laptop." It is the container's own loopback. A server bound to `127.0.0.1` in a container cannot be reached through `-p 9000:9000`.

### 3.4 Same-origin policy and CORS (including preflight)
- **Explanation.** A page loaded from origin `http://localhost:3000` (scheme+host+port) may *send* requests to `http://localhost:9000`, but the browser will only let the JS *read* the response if the server says so with `Access-Control-Allow-Origin`. For "non-simple" requests the browser first sends a **preflight** `OPTIONS` asking "may I POST with `Content-Type: application/json` and `X-Session-ID`?". Here that means any POST with a JSON body, or any request carrying the custom `X-Session-ID` header that both frontends add (`cheese-app-v2/src/frontend-simple/chat-main.js:16-23`, `cheese-app-v2/src/frontend-react/src/services/DataService.js:12-24`). `CORSMiddleware` with `allow_origins=["*"]`, `allow_methods=["*"]` and `allow_headers=["*"]` answers yes to everything (`cheese-app-v2/src/api-service/api/service.py:15-21`). Starlette answers the preflight inside the middleware, before routing, and stamps `Access-Control-Allow-Origin: *` on normal responses. Its preflight reply also carries Starlette's default `Access-Control-Max-Age: 600`, so the browser caches the answer per URL for 10 minutes and does not repeat the `OPTIONS` for every request.
- **Mental model.** CORS is enforced **by the browser, about the server's permission**. `curl` and `/docs` never see a CORS error.
- **Analogy.** A bouncer (the browser) checks a guest list that the club (API) publishes. The club does not stop you walking up; the bouncer stops you reading what came back.
- **Misconception.** "A CORS error means my CORS config is wrong." In this app, a CORS error is usually a **crashed endpoint**. An unhandled Python exception turns into a 500 that is sent by Starlette's outermost `ServerErrorMiddleware`, *outside* `CORSMiddleware`, so the 500 carries no CORS header and the browser reports "No 'Access-Control-Allow-Origin' header" / axios "Network Error". Check the uvicorn terminal first. A concrete case is the RAG follow-up bug in sections 6 and 9.

### 3.5 Where code runs, and two meanings of "localhost"
- **Explanation.** The API reaches Chroma at `cheese-app-vector-db:8000`, a *container name* resolved by Docker's embedded DNS. That works only because both containers join the user-defined network `cheese-app-network` (`cheese-app-v2/src/api-service/docker-shell.sh:17`, `:34`, `cheese-app-v2/src/vector-db/docker-compose.yml:1-4`). The browser reaches the API at `localhost:9000` because Docker publishes container port 9000 on host port 9000 (`-p 9000:9000`). The frontend containers are on Docker's default bridge and never talk to the API. They just serve files. In v2 there are therefore two kinds of arrows: container↔container via network + DNS name, and host↔container via published port.
- **Mental model.** Each container is its own little machine with its own `localhost`. A Docker network is a private LAN with a phone book (DNS) of container names. `-p` is a hole drilled from your laptop into one container port.
- **Analogy.** Apartments in a building. Neighbours knock on each other's doors by name (container DNS), while visitors from the street must use the buzzer number on the front door (published port).
- **Misconception.** "The frontend container calls the API, so put `http://cheese-app-api-service:9000` in `.env.development`." The *browser* would then try to resolve `cheese-app-api-service` on your laptop and fail. Server-side code (e.g. a Next.js server component or rewrite, see the commented `rewrites` in `cheese-app-v2/src/frontend-react/next.config.js:11-35`, which point at an old `rag-system-api-service` name) is the only place a container name could work, and only if the frontend container also joined `cheese-app-network`, which v2's React `docker-shell.sh` does not do.

### 3.6 Stateless HTTP and where chat state lives
- **Explanation.** HTTP forgets each request, so the app keeps chat state in three places.
  1. The browser invents a session id and sends it as `X-Session-ID`: a fresh `uuid()` per page load in the simple frontend (`cheese-app-v2/src/frontend-simple/chat-main.js:14`), and one persisted in `localStorage` in React (`cheese-app-v2/src/frontend-react/src/services/DataService.js:13-19`).
  2. The API writes each chat as JSON under `/persistent/chat-history/<model>/<session_id>/<chat_id>.json` (`cheese-app-v2/src/api-service/api/utils/chat_utils.py:9`, `:23`, `:32-34`).
  3. Live Gemini `Chat` objects sit in a process-local dict `chat_sessions` (`cheese-app-v2/src/api-service/api/utils/llm_utils.py:47`). If that dict lost the chat (e.g. after a `--reload`), `rebuild_chat_session` reconstructs the history from the JSON file (`cheese-app-v2/src/api-service/api/utils/llm_utils.py:151-168`).
- **Mental model.** The disk is the source of truth, the dict is a cache, and the header is your locker key.
- **Misconception.** "Reload the page and my chats are still there, so the server remembers me." In React, yes, because the session id lives in `localStorage`. In the simple frontend, no: every reload of `chat.html` creates a new id and starts a new, empty history.

### 3.7 Frontends: DOM scripting vs. React components in a Next.js App Router
- **Explanation.** The simple frontend is plain files. `newsletters.html` loads axios from a CDN and `newsletters-main.js`, which fetches JSON and string-builds `innerHTML` cards (`cheese-app-v2/src/frontend-simple/newsletters-main.js:24-49`). The React app is a **Next.js App Router** project, where folders map to URLs: `src/app/page.jsx` → `/`, `src/app/chat/page.jsx` → `/chat`, `src/app/newsletters/page.jsx` → `/newsletters`, `src/app/podcasts/page.jsx` → `/podcasts`. `src/app/layout.jsx` wraps every page with Header/Footer. Pages marked `'use client'` hold state (`useState`), fetch in `useEffect`, and call a single `DataService` module that owns the axios instance and all API URLs. `@/` is an import alias for `src/` (`cheese-app-v2/src/frontend-react/jsconfig.json:3-7`). Only env vars prefixed `NEXT_PUBLIC_` are inlined into browser JS (`cheese-app-v2/src/frontend-react/src/services/Common.js:2`).
- **Mental model.** State goes in, UI comes out: `UI = f(state)`. A fetch updates state, and React re-renders.
- **Analogy.** The simple site is a hand-painted poster you repaint for every change. React is a scoreboard wired to the score.
- **Misconception.** "`'use client'` means the component never runs on the server." Next.js still pre-renders client components on the server once, where browser globals do not exist. `useRef(new Audio())` (`cheese-app-v2/src/frontend-react/src/components/shared/PodcastCard.jsx:16`) evaluates `new Audio()` on every render, so it is only safe here because no `PodcastCard` exists during that server pass: the cards are rendered after a client-side fetch fills the list.

### 3.8 The container dev loop: bind mounts + hot reload
- **Explanation.** Every service mounts its source folder over `/app` (`-v "$BASE_DIR":/app` in the API and simple-frontend scripts, `-v "$(pwd)/:/app/"` for React, `../vector-db:/app` in the vector-db compose file). Edits in VS Code on the host are therefore instantly visible inside the container. uvicorn `--reload`, Next's `next dev` (with `WATCHPACK_POLLING=true`, `cheese-app-v2/src/frontend-react/package.json:6`) and `http-server` pick them up. The Python venv is installed at `/home/app/.venv` (`cheese-app-v2/src/api-service/Dockerfile:17`), *outside* `/app`, so the bind mount does not hide it.
- **Misconception.** "Rebuild the image after every code change." You only rebuild when dependencies (`pyproject.toml`/`uv.lock`, `package.json`) or the Dockerfile change.

---

## 4. Step-by-step walkthrough

### Part A — cheese-app-v1 ("Simple Frontend with FastAPI")

**A0. Clone, then create the sibling folders.**
- Action: clone `dlops-io/cheese-app-v1` (`cheese-app-v1/README.md:17-18`). Then, from the folder that contains `cheese-app-v1`, run `mkdir -p secrets persistent-folder`. The README asks only for `secrets` (`cheese-app-v1/README.md:22`), but its tree and the script also use `persistent-folder` (`cheese-app-v1/README.md:34`, `cheese-app-v1/src/api-service/docker-shell.sh:10`).
- Under the hood: `docker run -v` with a missing host path makes Docker create it. On Linux it is created **root-owned** and the container user `app` (uid 1000) cannot write to it. That matters in v2 (section 6).
- Checkpoint: `ls ..` from inside `cheese-app-v1` shows `cheese-app-v1 persistent-folder secrets`.

**A1. Build and enter the API container.**
- Command (`cheese-app-v1/README.md:44`): `sh docker-shell.sh`, run **from `cheese-app-v1/src/api-service`**. The README says "`cheese-app-v1/api-service`" (`cheese-app-v1/README.md:41`), which lacks the `src/`.
- Under the hood, in `cheese-app-v1/src/api-service/docker-shell.sh:13-21`, `docker build -t cheese-app-api-service` runs the Dockerfile. It starts `FROM python:3.12-slim-bookworm` (`cheese-app-v1/src/api-service/Dockerfile:2`), installs `uv`, creates user `app` uid 1000 (`:30`), copies `pyproject.toml uv.lock*` and runs `uv sync --frozen` into `/home/app/.venv` (`:17`, `:39-42`). Then `docker run --rm -ti` mounts `.`→`/app`, `../../../secrets/`→`/secrets` and `../../../persistent-folder/`→`/persistent`, and publishes `-p 9000:9000`. The entrypoint activates the venv and `exec /bin/bash` (`cheese-app-v1/src/api-service/docker-entrypoint.sh:11-14`).
- Checkpoint: you see `Container is running!!!`, `Architecture: aarch64` (Apple Silicon) or `x86_64`, the Python and uv versions, and a bash prompt like `app@<id>:/app$`.
- If it fails: `Conflict. The container name "/cheese-app-api-service" is already in use` means an old container (v1, v2 or v3 all use this name) is still running, so run `docker ps` and `docker stop cheese-app-api-service`. `port is already allocated` means something else (e.g. L10's API) holds 9000.

**A2. Start uvicorn.**
- Command (`cheese-app-v1/README.md:47`): `uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/ "$@"`. The trailing `"$@"` is copied from a script and expands to nothing when you type it interactively.
- Checkpoint: `Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)`, `Started reloader process [...] using StatReload` (v1's lock has no `watchfiles`), then `Application startup complete.`. Browse `http://localhost:9000/` and you get `{"message":"Welcome to AC215"}` (`cheese-app-v1/src/api-service/api/service.py:18-20`).

**A3. Add a route and watch reload.**
- Action (`cheese-app-v1/README.md:52-58`): append to `api/service.py`:
  ```
  @app.get("/square_root/")
  async def square_root(x: float = 1, y: float = 2):
      z = x**2 + y**2
      return z**0.5
  ```
- Under the hood: the reloader sees `api/service.py` change, kills the worker and re-imports the module. The decorator registers `GET /square_root/`.
- Checkpoint: `http://localhost:9000/square_root/` returns `2.23606797749979` (√5). `http://localhost:9000/square_root/?x=2&y=10` returns `10.198039027185569` (√104). `?x=abc` returns a 422 JSON error, which is FastAPI's validation. `http://localhost:9000/square_root` (no slash) answers with a 307 redirect.
- If it fails: an `IndentationError` in the uvicorn terminal means the worker could not import. Fix the file and it reloads.

**A4. Explore `/docs`.**
- Action (`cheese-app-v1/README.md:64-67`): open `http://localhost:9000/docs`, expand `GET /square_root/`, then "Try it out" → Execute.
- Checkpoint: Swagger UI lists `GET /` and `GET /square_root/`, with `x` and `y` shown as `number` query params with defaults 1 and 2.

**A5. Simple frontend container.**
- Command: open a **second terminal** in `cheese-app-v1/src/frontend-simple` (the README says `cheese-app-v1/frontend-simple`, `cheese-app-v1/README.md:75`), run `sh docker-shell.sh` (`:78`), then `http-server` (`:82`).
- Under the hood: the image is `node:20-alpine` with bash and a global `http-server` (`cheese-app-v1/src/frontend-simple/Dockerfile:1-7`). The script mounts the folder at `/app` and publishes `8080:8080` (`cheese-app-v1/src/frontend-simple/docker-shell.sh:18-20`). `http-server` serves the current directory on 0.0.0.0:8080.
- Checkpoint: `http://localhost:8080/` shows "🧀 Formaggio.me is here!" and two podcast cards. Those cards are **hard-coded** in JS ("This would normally come from an API", `cheese-app-v1/src/frontend-simple/main.js:37-52`). In v1 the frontend does not call the API at all.
- Edit `index.html` (`cheese-app-v1/README.md:86-95`) and refresh. The README's snippet is a bare `<body>` with "🧀 Welcome to the cheese identification App!" from an older template, so add a `<p>` inside the existing hero section instead of pasting it over the whole body (which would also drop `<script src="main.js">`, `cheese-app-v1/src/frontend-simple/index.html:74`). If the change does not show, `http-server` is caching for 3600 s by default, so hard-refresh or restart it with `http-server -c-1` (section 6).
- If it fails: `http-server` prints `Available on: http://127.0.0.1:8080` and `http://172.17.x.x:8080`. The 172.x address is the container's IP and is unreachable from macOS, so use `localhost`.

**A6. Clean up** (`cheese-app-v1/README.md:100-106`): exit both shells, then `docker container ls`, `docker system prune` and `docker image ls`.

### Part B — cheese-app-v2

**B0. Clone, secrets, folders, project id.**
- Clone `dlops-io/cheese-app-v2` next to v1 (`cheese-app-v2/README.md:20-21`).
- Put `ml-workflow.json` (L15) **and** `llm-service-account.json` (L05/L10) in `../secrets` (`cheese-app-v2/README.md:23-38`). Create `persistent-folder` yourself.
- Edit `GCP_PROJECT="ac215-project"` in **both** `cheese-app-v2/src/api-service/docker-shell.sh:11` and `cheese-app-v2/src/vector-db/docker-shell.sh:9`.
- Patch `GENERATIVE_MODEL` now (section 6, item 4): unpatched v2 chat no longer works in October 2026.
- Checkpoint: `ls ../secrets` (from `cheese-app-v2`) lists both JSON files.

**B1. Vector DB** (`cheese-app-v2/README.md:40-65`).
- Commands: `cd cheese-app-v2/src/vector-db`, then `sh docker-shell.sh`, then inside the container `python cli.py --download --load --chunk_type recursive-split`.
- Under the hood:
  - `docker-shell.sh` creates `cheese-app-network` if missing (`cheese-app-v2/src/vector-db/docker-shell.sh:14`), builds `cheese-app-vector-db-cli` (`:17`) and runs `docker-compose run --rm --service-ports cheese-app-vector-db-cli` (`:20`).
  - Compose first starts the dependency `chromadb` (`cheese-app-v2/src/vector-db/docker-compose.yml:17-18`): image `chromadb/chroma:latest`, container name `cheese-app-vector-db`, port `8000:8000` (`:19-28`). Both services join the external network `cheese-app-network` (`:1-4`).
  - Inside the CLI container, `--download` fetches `github.com/dlops-io/datasets/releases/download/v4.0/cheese-books-embeddings.zip` (about 23 MB) into `outputs/` and `extractall()`s it into the working dir `/app` (`cheese-app-v2/src/vector-db/cli.py:478-494`). Every entry in the zip starts with `outputs/`, so it unpacks to `/app/outputs/`: 11 `chunks-recursive-split-*.jsonl` and 11 `embeddings-recursive-split-*.jsonl` files, about 60 MB, visible on the host in `src/vector-db/outputs/` (git-ignored). The zip was downloaded and inspected (verified on 2026-10-12 in a scratch environment): each embeddings row has `book`, `chunk` and a 256-number `embedding`.
  - `--load` connects to `chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)`, deletes and recreates the collection `recursive-split-collection` with cosine distance (`cheese-app-v2/src/vector-db/cli.py:277-291`), then inserts every `outputs/embeddings-recursive-split-*.jsonl` in batches of 500 (`:296-309`, `:127-164`).
- Checkpoint: `Created new empty collection 'recursive-split-collection'`, `Number of files to process: 11` (one per book), then for each file `Processing file: outputs/embeddings-recursive-split-<book>.jsonl`, repeated `Inserted N items...` and `Finished inserting N items into collection 'recursive-split-collection'`. The per-file counts add up to 14,356 chunks (largest: *The Book of Cheese*, 3,569).
- You can `exit` the CLI shell. **Chroma keeps running** (`docker ps` shows `cheese-app-vector-db`). That container is what the README means by "Keep this container running" (`cheese-app-v2/README.md:65`).
- If it fails:
  - `docker-compose: command not found` (Linux): run the compose line yourself with `docker compose`.
  - `Number of files to process: 0`: you ran `--load` without a successful `--download`, or from a directory other than `/app`. `ls /app/outputs` should list the 22 `.jsonl` files.
  - `Bind for 0.0.0.0:8000 failed`: another Chroma (e.g. L10's `llm-rag-chromadb`) is still up.

**B2. API service** (`cheese-app-v2/README.md:67-94`).
- Commands: `cd cheese-app-v2/src/api-service`, then `sh docker-shell.sh`, then inside the container `uvicorn_server`.
- Under the hood:
  - The README's step 3 asks you to review exactly this (`cheese-app-v2/README.md:82-86`): the script creates `cheese-app-network` if missing (`cheese-app-v2/src/api-service/docker-shell.sh:17`), then uses the same image recipe as v1, plus `-e DEV=1`, the credentials and Chroma env vars, and `--network cheese-app-network` (`cheese-app-v2/src/api-service/docker-shell.sh:23-35`).
  - The entrypoint defines and `export -f`s `uvicorn_server` (the v1 command) and `uvicorn_server_production` (`cheese-app-v2/src/api-service/docker-entrypoint.sh:14-23`). Because `DEV=1`, it then `exec /bin/bash` (`:32-34`).
  - When uvicorn imports `api.service`, **all six router modules are imported** (`cheese-app-v2/src/api-service/api/service.py:4-7`), even the two whose `include_router` lines are commented out.
  - Importing them has side effects. Each `ChatHistoryManager(...)` creates `/persistent/chat-history/<model>/images` (`cheese-app-v2/src/api-service/api/utils/chat_utils.py:20-30`). `llm_cnn_utils` imports TensorFlow and **downloads and loads the CNN** from `github.com/dlops-io/models/releases/download/v4.0/experiment_1760994796.zip` into `/persistent/experiments` (`cheese-app-v2/src/api-service/api/utils/llm_cnn_utils.py:110-149`). `llm_rag_utils` builds a `chromadb.HttpClient`, which in chromadb 1.3.0 contacts the server immediately (`cheese-app-v2/src/api-service/api/utils/llm_rag_utils.py:57`).
- Checkpoint: `Uvicorn running on http://0.0.0.0:9000` and `Started reloader process [...] using WatchFiles` (v2's lock includes `watchfiles`). Then, while the worker imports the app, TensorFlow log noise, `Loading CNN Model...` and a printed Keras `summary()`, and finally `Started server process [...]` and `Application startup complete.`. `http://localhost:9000` returns `{"message":"Welcome to AC215"}`.
- If it fails:
  - `ValueError: Could not connect to a Chroma server. Are you sure it is running?` means B1's Chroma is not up or not on `cheese-app-network`.
  - `PermissionError: [Errno 13] ... '/persistent/...'` is the Linux root-owned folder problem (section 6).
  - `requests.exceptions.ConnectionError` while loading the CNN means you have no internet on first start.
  - With `--reload`, the reloader stays alive after an import error. Fix the cause, then save any file under `api/` (or Ctrl-C and rerun `uvicorn_server`).

**B3. Demo route** (`cheese-app-v2/README.md:96-108`).
- At the pinned commit, `square_root` is **already in** `service.py` (`cheese-app-v2/src/api-service/api/service.py:30-33`; it was added by commit `14f2a14`, after the README was written).
- Do not paste it a second time. Two routes with the same path register silently, the first one wins, and `/docs` triggers FastAPI's `UserWarning: Duplicate Operation ID square_root_square_root__get ...`.
- Checkpoint: the same results as A3.

**B4. API docs** (`cheese-app-v2/README.md:110-113`).
- Checkpoint: `/docs` lists `GET /`, `GET /square_root/` and the `/newsletters/…`, `/podcasts/…`, `/llm/…` and `/llm-cnn/…` operations. They all sit in one "default" section, because no router sets `tags`.
- Try `GET /newsletters/` with `limit=2`: you get two JSON objects, newest `dts` first (`cheese-app-v2/src/api-service/api/routers/newsletter.py:16-35`).
- Try `GET /podcasts/audio/9f2b7e84-5623-4029-bcfd-f99f2d7611e8-EN.mp3`: you get a 200 with `audio/mpeg` (`cheese-app-v2/src/api-service/api/routers/podcast.py:47-68`). Swagger shows a "Download file" link, and opening the URL in a tab downloads the file rather than playing it, because the route sets `Content-Disposition: attachment` (`:64`). React's player (an `Audio` element whose `src` is this URL, `cheese-app-v2/src/frontend-react/src/components/shared/PodcastCard.jsx:77`) ignores that header and plays it.
- Chat routes in `/docs`: **fill the `X-Session-ID` field**. Without it `session_id` is `None`, and `os.path.join(..., None)` raises `TypeError`, a 500 (`cheese-app-v2/src/api-service/api/utils/chat_utils.py:100`, `:141`). For `POST /llm/chats` that happens *after* the paid Gemini call.

**B5. Routers** (`cheese-app-v2/README.md:116-145`).
- The README shows only `newsletter` enabled and says "Enable all the routes" (`cheese-app-v2/README.md:118-127`, `:138`). The code already has four enabled, with RAG and Agent still commented (`cheese-app-v2/src/api-service/api/service.py:37-43`).
- To use the RAG chat, uncomment `app.include_router(llm_rag_chat.router, prefix="/llm-rag")` (`cheese-app-v2/src/api-service/api/service.py:41`). uvicorn reloads.
- Enabling `/llm-agent` (`cheese-app-v2/src/api-service/api/service.py:42`) only gives GET routes: the router has no POST (`cheese-app-v2/src/api-service/api/routers/llm_agent_chat.py:26-44`), and its utils module is a stub (`cheese-app-v2/src/api-service/api/utils/llm_agent_utils.py:1-26`). Sending a chat with "Agent" selected returns **404** (router off) or **405** (router on).
- The README's file names are off: they are `api/routers/newsletter.py` and `podcast.py`, not `newsletters.py`/`podcasts.py` (`cheese-app-v2/README.md:131-132`).
- Optional: uncommenting `test_router` (`cheese-app-v2/src/api-service/api/service.py:9`, `:43`) gives `GET /test/test-chroma`. It lists the Chroma collections the API can see (`cheese-app-v2/src/api-service/api/routers/test_router.py:16-30`) and is a good network check.

**B6. Simple frontend** (`cheese-app-v2/README.md:147-183`).
- Commands: `cd cheese-app-v2/src/frontend-simple`, then `sh docker-shell.sh`, then `http-server`. It uses the same image name and port as v1, so stop v1's container first.
- Checkpoints:
  - `http://localhost:8080/index.html`: the landing page, which now has "Newsletters" and "Cheese Assistant" nav links (the only diff from v1's `index.html`).
  - `http://localhost:8080/newsletters.html`: three cards with images. The **API** terminal logs `GET /newsletters?limit=100` → **307**, then `GET /newsletters/?limit=100` → 200, because the JS omits the trailing slash (`cheese-app-v2/src/frontend-simple/newsletters-main.js:7`). Images come from `/newsletters/image/<file>` (`:15-17`).
  - `http://localhost:8080/chat.html`: ask "How is cheese made?". The API log shows an `OPTIONS` preflight, then `POST /llm/chats/` → 307, then (usually after a second preflight for the new URL) `POST /llm/chats` 200 (`cheese-app-v2/src/frontend-simple/chat-main.js:30-32`). Within 10 minutes the browser reuses the cached preflight answers (section 3.4), so later messages may show no `OPTIONS`. A JSON file appears in `../persistent-folder/chat-history/llm/<uuid>/`.
- The README says to "Review the code in `newsletters.html`/`chat.html`" (`cheese-app-v2/README.md:176`, `:181`), but the API logic is in `newsletters-main.js` and `chat-main.js`. Also, the "Gemini LLM integration" lives in the API, not the page.
- If it fails:
  - The page loads but there are no cards and the console shows `ERR_CONNECTION_REFUSED`: the API is not running.
  - "Sorry, there was an error processing your message.": check the uvicorn terminal. Common causes are a missing key, the wrong `GCP_PROJECT` or the retired `gemini-2.0-flash-001` model (section 6, item 4; as of October 2026 this hits every unpatched chat).

**B7. React frontend** (`cheese-app-v2/README.md:185-212`).
- Commands: `cd cheese-app-v2/src/frontend-react`, then `sh docker-shell.sh`, then (first time) `npm install`, then `npm run dev`.
- Under the hood:
  - `docker-shell.sh` builds from `Dockerfile.dev` (`node:20-alpine` + bash, no dependencies baked in, `cheese-app-v2/src/frontend-react/Dockerfile.dev:1-13`) and mounts the folder at `/app` with `-p 3000:3000` (`cheese-app-v2/src/frontend-react/docker-shell.sh:8-11`).
  - `npm install` resolves from `package-lock.json`. The lock pins `next` 15.0.2 and `react` 18.3.1 even though `package.json` says `"latest"` (`cheese-app-v2/src/frontend-react/package.json:19-22`). It writes `node_modules/` **into your host folder** through the bind mount.
  - `npm run dev` runs `WATCHPACK_POLLING=true next dev` (`cheese-app-v2/src/frontend-react/package.json:6`). Next reads `.env.development` and inlines `NEXT_PUBLIC_BASE_API_URL=http://localhost:9000` into the browser bundle.
- Checkpoint: `▲ Next.js 15.0.2`, `- Local: http://localhost:3000`, `- Environments: .env.development`, `✓ Ready`. The first page compile takes a few seconds (`○ Compiling / ...`). The browser console prints `BASE_API_URL: http://localhost:9000` (`cheese-app-v2/src/frontend-react/src/services/DataService.js:5`).
- If it fails:
  - `EACCES` errors or a very slow install: Docker Desktop file sharing. Retry, or check that the folder is shared. On Linux, the container runs as root (`Dockerfile.dev` has no `USER`), so `node_modules/` and `.next/` end up root-owned in your host folder and deleting them later needs `sudo`.
  - Port 3000 busy: stop other dev servers.

**B8. Review the app** (`cheese-app-v2/README.md:213-216`).
- Home (`/`): Hero, What-is, the first 4 podcasts and the first 4 newsletters (fetched client-side with `GetPodcasts(4)` / `GetNewsletters(4)` in `'use client'` components), then About (`cheese-app-v2/src/frontend-react/src/app/page.jsx:7-17`).
- `/newsletters` and `/newsletters?id=<id>` (the detail view is `dangerouslySetInnerHTML` of the JSON `detail`). `/podcasts` has a playable MP3.
- `/chat`: pick **LLM** and ask a question. The URL becomes `/chat?model=llm&id=<chat_id>` (`cheese-app-v2/src/frontend-react/src/app/chat/page.jsx:99`).
- Attach a cheese photo with **LLM + CNN** and you get a purple-eye message `<label> (<accuracy>%)` (`cheese-app-v2/src/frontend-react/src/components/chat/ChatMessage.jsx:121-123`).
- **RAG** only works after B5. Its first message works, but the *second* message fails (500 → "AxiosError: Network Error" in the error modal), because of `message["content"]` on a pydantic object (`cheese-app-v2/src/api-service/api/routers/llm_rag_chat.py:99`). See section 9.

**B9. Read the code** (`cheese-app-v2/README.md:218-237`). Read in this order: `src/services/DataService.js` (every API call in one place), then `src/app/layout.jsx` and `src/app/page.jsx`, then `src/app/chat/page.jsx`, then `src/components/chat/*`. Section 5 walks through the excerpts.

**B10. Cleanup** (`cheese-app-v2/README.md:241-247`). Exit all shells, then `docker stop cheese-app-vector-db`, then `docker system prune`. Optionally `docker network rm cheese-app-network`.

---

## 5. Code tour

```text
cheese-app-v1/src/
  api-service/                Dockerfile (python 3.12 + uv), docker-shell.sh, docker-entrypoint.sh (venv + bash)
    api/service.py            FastAPI app with CORS and one route "/"
  frontend-simple/            node:20-alpine + http-server; index.html, main.js (hard-coded podcasts), styles.css
  data-collector/ ... vector-db/   empty placeholders (.gitkeep) for the folder layout

cheese-app-v2/src/
  vector-db/
    docker-shell.sh           creates network, builds CLI image, `docker-compose run`
    docker-compose.yml        cli service + chromadb/chroma:latest on cheese-app-network
    cli.py                    --download/--chunk/--embed/--load/--query (RAG data prep from L05)
  api-service/
    docker-shell.sh           env vars, network, mounts, -p 9000:9000, DEV=1
    docker-entrypoint.sh      defines uvicorn_server / uvicorn_server_production
    api/service.py            app, CORS, routes, include_router(...) wiring
    api/routers/              newsletter.py, podcast.py, llm_chat.py, llm_cnn_chat.py,
                              llm_rag_chat.py, llm_agent_chat.py (GET only), test_router.py
    api/utils/                chat_utils.py (ChatMessage + ChatHistoryManager), llm_utils.py (Gemini chat),
                              llm_cnn_utils.py (TF CNN), llm_rag_utils.py (embed + Chroma query), llm_agent_utils.py (stub)
    news-letters/, podcasts/  JSON + assets served by the API (stand-in for a GCS bucket)
  frontend-simple/            + newsletters.html/-main.js, chat.html/chat-main.js (axios from CDN), unused index-simple.html
  frontend-react/
    Dockerfile.dev, docker-shell.sh   dev container (npm install / npm run dev inside)
    Dockerfile                prod 2-stage build on node:18-alpine (not used in L18; v3 replaces it)
    .env.development / .env.production   NEXT_PUBLIC_BASE_API_URL = http://localhost:9000 | /api-service
    src/app/                  layout.jsx, page.jsx, chat/, newsletters/, podcasts/ (App Router)
    src/components/           layout/, home/, chat/, shared/, auth/, seo/ (unused)
    src/services/             Common.js (BASE_API_URL), DataService.js (axios), MockDataService.js
```

**(1) The app object, CORS and the route table**: `cheese-app-v2/src/api-service/api/service.py:12-21`
```python
app = FastAPI(title="API Server", description="API Server", version="v1")

# Enable CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- `FastAPI(...)` creates the app, and its title/version show up in `/docs`.
- `add_middleware(CORSMiddleware, ...)` wraps every request. A preflight `OPTIONS` is answered right here. Every other response gets `Access-Control-Allow-Origin: *`.
- `allow_credentials=False` means the API never sends `Access-Control-Allow-Credentials: true`, so browsers will not expose responses to credentialed (cookie / HTTP-auth) cross-origin requests. Neither frontend sends any (axios's `withCredentials` defaults to false). If you set it to `True` with `allow_origins=["*"]`, Starlette echoes the caller's origin in preflight replies (and in normal replies to requests that carry a `Cookie`) instead of sending `*`, because browsers reject `*` combined with credentials.

**`cheese-app-v2/src/api-service/api/service.py:36-43`**
```python
# Additional routers here
app.include_router(newsletter.router, prefix="/newsletters")
app.include_router(podcast.router, prefix="/podcasts")
app.include_router(llm_chat.router, prefix="/llm")
app.include_router(llm_cnn_chat.router, prefix="/llm-cnn")
# app.include_router(llm_rag_chat.router, prefix="/llm-rag")
# app.include_router(llm_agent_chat.router, prefix="/llm-agent")
# app.include_router(test_router.router, prefix="/test")
```
- Each line mounts a router under a URL prefix. The prefixes are exactly the `model` strings the frontends send (`llm`, `llm-cnn`, `llm-rag`, `llm-agent`), which is how one generic chat UI drives four backends.
- Commenting a line here removes the routes but **not** the import side effects (lines 4-7 still import every module).

**(2) Dev vs. prod start-up**: `cheese-app-v2/src/api-service/docker-entrypoint.sh:13-23`
```bash
# Run the api/service.py file with the instantiated app FastAPI
uvicorn_server() {
    uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/ "$@"
}

uvicorn_server_production() {
    uv run uvicorn api.service:app --host 0.0.0.0 --port 9000 --lifespan on
}

export -f uvicorn_server
export -f uvicorn_server_production
```
- `api.service:app` is module path `api/service.py`, variable `app`. It must be run from `/app`, the WORKDIR.
- `--reload-dir api/` watches only the `api/` folder. Editing a newsletter JSON needs no reload, because it is read per request anyway.
- `export -f` exports the shell functions to the interactive `bash` that `exec /bin/bash` starts (lines 32-34). That is why typing `uvicorn_server` works.
- The production variant drops `--reload` and debug logging. It runs when `DEV` is not `1` (lines 35-37), which is how later lectures run the container non-interactively.

**(3) Wiring the container into the network**: `cheese-app-v2/src/api-service/docker-shell.sh:23-35`
```bash
docker run --rm --name $IMAGE_NAME -ti \
-v "$BASE_DIR":/app \
-v "$SECRETS_DIR":/secrets \
-v "$PERSISTENT_DIR":/persistent \
-p 9000:9000 \
-e DEV=1 \
-e GOOGLE_APPLICATION_CREDENTIALS=/secrets/ml-workflow.json \
-e GCP_PROJECT=$GCP_PROJECT \
-e GCS_BUCKET_NAME=$GCS_BUCKET_NAME \
-e CHROMADB_HOST=$CHROMADB_HOST \
-e CHROMADB_PORT=$CHROMADB_PORT \
--network cheese-app-network \
$IMAGE_NAME
```
- The three `-v` flags mount code, keys and state. Only the code mount is inside the repo, so keys and chat history never get committed.
- `-p 9000:9000` is the hole the browser uses, and `--network cheese-app-network` is the LAN the API uses to reach Chroma by name.
- `GOOGLE_APPLICATION_CREDENTIALS` is read by `google-auth` (Application Default Credentials) the first time the genai client needs a token.

**(4) A request body, a header, a handler**: `cheese-app-v2/src/api-service/api/utils/chat_utils.py:12-16`
```python
class ChatMessage(BaseModel):
    content: Optional[str] = Field(None, description="The message content")
    image: Optional[str] = Field(None, description="The image content")
    message_id: Optional[str] = Field(None, description="The message id")
    role: Optional[str] = Field(None, description="The role")
```
**`cheese-app-v2/src/api-service/api/routers/llm_chat.py:47-60`**
```python
@router.post("/chats")
async def start_chat_with_llm(
    message: ChatMessage, x_session_id: str = Header(None, alias="X-Session-ID")
):
    message_dict = message.model_dump()
    print("content:", message_dict["content"])
    print("x_session_id:", x_session_id)
    """Start a new chat with an initial message"""
    chat_id = str(uuid.uuid4())
    current_time = int(time.time())

    # Create a new chat session
    chat_session = create_chat_session()
    chat_sessions[chat_id] = chat_session
```
- A parameter typed as a `BaseModel` means "parse the JSON body". Unknown fields (the simple frontend also sends `timestamp`, `cheese-app-v2/src/frontend-simple/chat-main.js:120-124`) are ignored. `image` carries a whole base64 `data:` URL.
- `Header(None, alias="X-Session-ID")` maps the HTTP header to a Python arg. Its default is `None`, which is why `/docs` calls without it crash later.
- `model_dump()` turns the model into a dict. You must index the *dict*, not the model, and `llm_rag_chat.py:99` gets this wrong.
- Lines 59-60 create a Gemini `Chat` and cache it in the process-local dict, keyed by the new `chat_id`.

**(5) Calling Gemini with history**: `cheese-app-v2/src/api-service/api/utils/llm_utils.py:18-26`
```python
GCP_PROJECT = os.environ["GCP_PROJECT"]
GCP_LOCATION = "us-central1"
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSION = 256
GENERATIVE_MODEL = "gemini-2.0-flash-001"

#############################################################################
#                       Initialize the LLM Client                           #
llm_client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
```
- `os.environ["GCP_PROJECT"]` raises `KeyError` at import if you run the module outside the container, because the env var comes only from `docker-shell.sh`.
- `genai.Client(vertexai=True, ...)` uses Vertex AI (IAM, project billing) rather than an API key. The same four constants are copied into `llm_cnn_utils.py`, `llm_rag_utils.py`, `llm_agent_utils.py` and `vector-db/cli.py`, so a model change means five edits (four that matter: nothing imports `llm_agent_utils.py`, since the agent router imports `llm_utils`, `cheese-app-v2/src/api-service/api/routers/llm_agent_chat.py:10-15`).
- A `SYSTEM_INSTRUCTION` is defined at `cheese-app-v2/src/api-service/api/utils/llm_utils.py:30` but never passed to `chats.create` (`:53`), so the "cheese expert" persona is not actually applied.

**(6) The RAG step inside the API**: `cheese-app-v2/src/api-service/api/utils/llm_rag_utils.py:151-165`
```python
        else:
            # Add text content if present
            if message.get("content"):
                # Create embeddings for the message content
                query_embedding = generate_query_embedding(message["content"])
                # Retrieve chunks based on embedding value 
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=5
                )
                INPUT_PROMPT = f"""
                {message["content"]}
                {"\n".join(results["documents"][0])}
                """
                message_parts.append(INPUT_PROMPT)
```
- Line 155 embeds the question with the *same* model and dimension that produced the stored vectors (`text-embedding-004`, 256). If you change one side and not the other, retrieval silently returns garbage.
- `collection` is fetched per request from `client.get_collection(name="recursive-split-collection")` (line 92), and that name must match the `--chunk_type` you loaded in B1.
- Line 163 puts a backslash inside an f-string expression, which is legal only in Python ≥ 3.12 (PEP 701). The container runs 3.12.

**(7) The vector-db stack**: `cheese-app-v2/src/vector-db/docker-compose.yml:1-5` and `:19-28`
```yaml
networks:
    default:
        name: cheese-app-network
        external: true
services:
```
```yaml
    chromadb:
        image: chromadb/chroma:latest
        container_name: cheese-app-vector-db
        ports:
            - 8000:8000
        volumes:
            - ./docker-volumes/chromadb:/chroma/chroma
        environment:
            - IS_PERSISTENT=TRUE
            - ANONYMIZED_TELEMETRY=FALSE
```
- `external: true` tells Compose: do not create a project network, join the existing `cheese-app-network`. That is the same network the API joins with `--network`.
- `container_name: cheese-app-vector-db` is the DNS name the API uses (`CHROMADB_HOST`).
- `:latest` plus the `/chroma/chroma` mount is fragile (sections 6 and 9).

**(8) Simple frontend: one axios instance, one header**: `cheese-app-v2/src/frontend-simple/chat-main.js:11-23`
```javascript
const api = axios.create({
    baseURL: BASE_API_URL
});
const sessionId = uuid();
// Add request interceptor to include session ID in headers
api.interceptors.request.use((config) => {
    if (sessionId) {
        config.headers['X-Session-ID'] = sessionId;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});
```
- `BASE_API_URL` is hard-coded to `'http://localhost:9000'` (line 2), a host-side address, because this JS runs in the browser.
- The interceptor adds `X-Session-ID` to every request made through `api`. That custom header forces a CORS preflight even for GETs (the JSON `Content-Type` of the POSTs would force one anyway). `newsletters-main.js` calls plain `axios.get` without the header, so the newsletter GETs need no preflight.
- `uuid()` runs on each page load, so each visit is a new "user" from the API's point of view.

**(9) React: the single place that knows the API**: `cheese-app-v2/src/frontend-react/src/services/DataService.js:12-24` and `:48-56`
```javascript
api.interceptors.request.use((config) => {
    var sessionId = localStorage.getItem('userSessionId');
    if (sessionId) {
        config.headers['X-Session-ID'] = sessionId;
    } else {
        sessionId = uuidv4();
        localStorage.setItem('userSessionId', sessionId);
        config.headers['X-Session-ID'] = sessionId;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});
```
```javascript
    GetChats: async function (model, limit) {
        return await api.get("/" + model + "/chats?limit=" + limit);
    },
    GetChat: async function (model, chat_id) {
        return await api.get("/" + model + "/chats/" + chat_id);
    },
    StartChatWithLLM: async function (model, message) {
        return await api.post("/" + model + "/chats", message);
    },
```
- `localStorage` persists the session id across reloads, so chat history survives in React but not in the simple frontend.
- The paths are relative. axios prefixes `baseURL` = `BASE_API_URL` = `process.env.NEXT_PUBLIC_BASE_API_URL` (`cheese-app-v2/src/frontend-react/src/services/Common.js:2`), so switching between dev (`http://localhost:9000`) and prod (`/api-service` behind NGINX, `cheese-app-v2/src/frontend-react/.env.production:2`) needs no code change.
- The paths match the FastAPI routes exactly (no trailing-slash mismatch), so React avoids the 307s you saw with the simple frontend.

**(10) React page state machine**: `cheese-app-v2/src/frontend-react/src/app/chat/page.jsx:83-99`
```javascript
        const startChat = async (message) => {
            try {
                // Show typing indicator
                setIsTyping(true);
                setHasActiveChat(true);
                setChat(tempChatMessage(message)); // Show the user input message while LLM is invoked

                // Submit chat
                const response = await DataService.StartChatWithLLM(model, message);
                console.log(response.data);

                // Hide typing indicator and add response
                setIsTyping(false);

                setChat(response.data);
                setChatId(response.data["chat_id"]);
                router.push('/chat?model=' + selectedModel + '&id=' + response.data["chat_id"]);
```
- This is an *optimistic UI*. The user's message appears immediately (`tempChatMessage`) while the request is in flight, and `isTyping` shows the three-dot indicator.
- When the API returns, the whole chat object (both messages) replaces the temporary state.
- `router.push` puts `model` and `id` into the URL. On reload, `use(searchParams)` (line 21; in Next 15 `searchParams` is a Promise) re-reads them and `fetchChat` loads the conversation from `GET /<model>/chats/<id>`.

**(11) The React dev container**: `cheese-app-v2/src/frontend-react/docker-shell.sh:1-11`
```bash
#!/bin/bash

set -e

export IMAGE_NAME="cheese-app-frontend-react"

# Build the image based on the Dockerfile
docker build -t $IMAGE_NAME -f Dockerfile.dev .

# Run the container
docker run --rm --name $IMAGE_NAME -ti -v "$(pwd)/:/app/" -p 3000:3000 $IMAGE_NAME
```
- The image holds no app code and no `node_modules`. Everything comes from the bind mount, so `npm install` inside the container writes Linux/musl binaries (e.g. Next's SWC compiler) into your host folder.
- There is no `--network`: this container never needs to see the API, because the browser does the calling.

---

## 6. Gotchas and common errors

1. **The API will not start without Chroma, even with the RAG router disabled.**
   - Symptom: after `uvicorn_server`, a traceback ending in `ValueError: Could not connect to a Chroma server. Are you sure it is running?`. The reloader then just waits.
   - Cause: `service.py` imports `llm_rag_chat` unconditionally (`cheese-app-v2/src/api-service/api/service.py:7`), whose utils build `chromadb.HttpClient(...)` at import time (`cheese-app-v2/src/api-service/api/utils/llm_rag_utils.py:57`). In chromadb 1.3.0 (`uv.lock`), the client's constructor calls `_validate_tenant_database`, which contacts the server.
   - Fix: do B1 first and check `docker ps | grep cheese-app-vector-db`. To run without RAG, comment out line 7 (which also drops the `llm_agent_chat` import) and keep lines 41-42 commented.

2. **Two different key file names.**
   - Symptom: the first chat message fails with `Failed to generate response: File /secrets/ml-workflow.json was not found.` (500). The key is loaded lazily, on the first Vertex call, so the API still starts. In the vector-db container the same error for `llm-service-account.json` appears only with `--embed`, `--query` (or the broken `--chat`/`--agent`), not with `--download --load`.
   - Cause: the API expects `/secrets/ml-workflow.json` (`cheese-app-v2/src/api-service/docker-shell.sh:29`) and the vector-db expects `/secrets/llm-service-account.json` (`cheese-app-v2/src/vector-db/docker-shell.sh:10`). The README mentions only the ml-workflow key (`cheese-app-v2/README.md:25`).
   - Fix: copy the key under both names, or edit one script. `--download --load` does not actually call Vertex, so only the API strictly needs a valid key.

3. **Placeholder project id.**
   - Symptom: `403 PERMISSION_DENIED` or "project not found / billing" errors on chat.
   - Cause: `GCP_PROJECT="ac215-project"` (`cheese-app-v2/src/api-service/docker-shell.sh:11`, `cheese-app-v2/src/vector-db/docker-shell.sh:9`).
   - Fix: set your project id in both, re-run `sh docker-shell.sh` (the env var is fixed at `docker run` time), and make sure the key's service account has Vertex AI User on *that* project.

4. **The generative model is retired.**
   - Symptom: every Gemini call (LLM chat, LLM + CNN text, RAG) fails, typically with a `404 NOT_FOUND ... Publisher Model ... gemini-2.0-flash-001 ...` error in the uvicorn log.
   - Cause: v2 hard-codes `gemini-2.0-flash-001` and `text-embedding-004` in `us-central1` (`cheese-app-v2/src/api-service/api/utils/llm_utils.py:19-22`, and the copies). Google's Vertex AI "Model versions and lifecycle" page (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions, read 2026-10-12) lists `gemini-2.0-flash` as **retired on June 1, 2026**, with `gemini-3.1-flash-lite` as the recommended upgrade. It lists `text-embedding-004` as available until April 1, 2027. The course's own October 2026 rebuilds of L05/v0 already use `gemini-3.1-flash-lite` and `gemini-embedding-001` at `location="global"` (`cheese-app-v0/llm-rag/cli.py:24-27`).
   - Fix: change `GENERATIVE_MODEL` to `gemini-3.1-flash-lite` in the three imported `api/utils/*.py` (`llm_utils`, `llm_cnn_utils`, `llm_rag_utils`). v0 calls it with `GCP_LOCATION = "global"`. If `us-central1` answers 404 for it, switch the location too, and test that RAG's `text-embedding-004` call still works on that endpoint (neither was tested). Do **not** change the `EMBEDDING_MODEL` used for RAG queries on its own: the downloaded vectors were made for `text-embedding-004` (256-d). Changing it means re-embedding (`python cli.py --chunk --embed --load --chunk_type recursive-split`, which is billable) with the new model on both sides. Note that `gemini-2.5-flash` is no safe stop-gap either: the same page retires it on October 20, 2026.

5. **"CORS error" that is really a server crash.**
   - Symptom: browser console `Access to XMLHttpRequest ... has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header`. The React error modal shows `AxiosError: Network Error`.
   - Cause: an unhandled exception, e.g. RAG follow-ups (`cheese-app-v2/src/api-service/api/routers/llm_rag_chat.py:99`), `llm-cnn` text when Vertex fails (`cheese-app-v2/src/api-service/api/utils/llm_cnn_utils.py:77-79` has no try/except), or an unknown newsletter id (`cheese-app-v2/src/api-service/api/routers/newsletter.py:40-42`). These produce a 500 from Starlette's outermost error middleware, which never passes through `CORSMiddleware`. `HTTPException`s *are* CORS-stamped (they are turned into responses inside `CORSMiddleware`), so errors that `llm_utils.generate_chat_response` wraps in one (`cheese-app-v2/src/api-service/api/utils/llm_utils.py:143-148`) reach the browser as readable 500s. Both cases were verified on 2026-10-12 in a scratch environment with a minimal app on the locked FastAPI 0.120.4 / Starlette 0.49.3.
   - Fix: read the uvicorn traceback. Patch line 99 to `message_dict["content"]`.

6. **Linux: Docker creates `persistent-folder` as root.**
   - Symptom: `PermissionError: [Errno 13] Permission denied: '/persistent/chat-history'` at import.
   - Cause: `-v` auto-creates missing host dirs as root, while the container runs as uid 1000 (`cheese-app-v2/src/api-service/Dockerfile:30`, `:35`; writes at `cheese-app-v2/src/api-service/api/utils/chat_utils.py:27-30`).
   - Fix: `mkdir -p persistent-folder secrets` yourself before the first run (or `sudo chown -R 1000:1000 persistent-folder`). On macOS, Docker Desktop's file sharing hides this.

7. **Name and port collisions between lectures.**
   - Symptom: `Conflict. The container name "/cheese-app-api-service" is already in use`, or `Bind for 0.0.0.0:9000 failed: port is already allocated`.
   - Cause: v1, v2 and v3 all use the container names `cheese-app-api-service` and `cheese-app-frontend-simple` (`cheese-app-v1/src/api-service/docker-shell.sh:7`, `cheese-app-v2/src/api-service/docker-shell.sh:7`). L10's v0 API also uses port 9000 and its Chroma uses 8000.
   - Fix: run `docker ps`, then `docker stop <name>`. Run only one version at a time. Rebuilding v2 also overwrites the v1 image tag of the same name.

8. **`docker-compose: command not found`.**
   - Cause: `cheese-app-v2/src/vector-db/docker-shell.sh:20` uses Compose v1 syntax. Linux installs with only the compose *plugin* (and GCP VMs) do not ship `docker-compose`.
   - Fix: replace it with `docker compose run --rm --service-ports $IMAGE_NAME`.

9. **Edits to the simple frontend do not show up.**
   - Cause: `http-server` sends `Cache-Control: max-age=3600` by default. The `<meta http-equiv="Cache-Control">` in `cheese-app-v1/src/frontend-simple/index.html:7-9` does not override cached JS/CSS.
   - Fix: run `http-server -c-1`, or hard refresh (Cmd-Shift-R).

10. **`http-server` advertises an address you cannot open.**
    - Cause: it prints the container IP (`172.17.x.x`) as well as `127.0.0.1`. From macOS or Windows the container IP is not routable.
    - Fix: always use `http://localhost:8080`.

11. **Mixing host and container `npm install`.**
    - Symptom: `next dev` on the host fails with `Failed to load SWC binary for darwin/arm64`, or the container fails after a host install.
    - Cause: `node_modules/` lives in the bind-mounted host folder (`cheese-app-v2/src/frontend-react/docker-shell.sh:11`), and native packages are platform-specific (Alpine = linux-musl).
    - Fix: use one environment only. If you switch, `rm -rf node_modules .next` and reinstall. On Linux these folders were created by the container's root user, so the `rm` needs `sudo` (section 4, B7).

12. **Changing `.env.development` seems to do nothing.**
    - Cause: `NEXT_PUBLIC_*` values are inlined when Next compiles, so a browser tab keeps running the bundle that holds the old value.
    - Fix: Ctrl-C, run `npm run dev` again and reload the page. Restarting is the reliable route; do not count on the dev server picking up the edited file by itself.

13. **Slow reloads after every Python edit.**
    - Cause: `--reload` restarts the worker, which re-imports TensorFlow and reloads the CNN (`cheese-app-v2/src/api-service/api/utils/llm_cnn_utils.py:149`). It is cached in `/persistent/experiments`, so there is no re-download. Reloads also wipe the in-memory `chat_sessions`.
    - Fix: be patient, or temporarily comment out the `llm_cnn_chat` import and include. If edits are not detected at all on Docker Desktop, run `export WATCHFILES_FORCE_POLLING=true` in the container shell before `uvicorn_server` (v2 uses watchfiles).

14. **Chroma data and the `:latest` tag.**
    - Cause: `chromadb/chroma:latest` is unpinned (`cheese-app-v2/src/vector-db/docker-compose.yml:20`), and the clients are pinned at 1.1.0 (vector-db lock) and 1.3.0 (API lock). The mount targets `/chroma/chroma` (`:25`), but the 2026 v0 compose file mounts `/data` for the same image (`cheese-app-v0/llm-rag/docker-compose.yml:24`), so v2's host folder may stay empty. The data then lives only in the container and is lost when the container is removed.
    - Symptom: the RAG chat fails with a "collection ... does not exist" error after you recreate containers.
    - Fix: re-run `python cli.py --load --chunk_type recursive-split` (and `--download` if `outputs/` is gone), or change the mount to `./docker-volumes/chromadb:/data`.

15. **Simple-frontend chat quirks.**
    - LLM+CNN image answers render empty. The CNN reply has `role: "cnn"` and `results`, not `content` (`cheese-app-v2/src/api-service/api/routers/llm_cnn_chat.py:92-96`), but `chat-main.js` only prints `.content` (`cheese-app-v2/src/frontend-simple/chat-main.js:161-164`).
    - The image-preview × button calls a global `removeImage()` (`cheese-app-v2/src/frontend-simple/chat.html:27`), but the function only exists as a `ChatApp` method, so clicking it throws `ReferenceError`.
    - Clicking a newsletter card calls an undefined `handleNewsletterClick` (`cheese-app-v2/src/frontend-simple/newsletters-main.js:27`).

16. **Committed secrets.** `NEXTAUTH_SECRET` is committed in `cheese-app-v2/src/frontend-react/.env.development:5` and `.env.production:3`. The `.gitignore` entry `env.local` lacks the leading dot (`cheese-app-v2/src/frontend-react/.gitignore:6`), so a `.env.local` you create *would* be committed. In your own project, never commit keys and fix that pattern.

17. **Apple Silicon.** This is *not* a problem here. Nothing forces `--platform`, the lock has a `tensorflow-2.19.0-...manylinux_2_17_aarch64` wheel (`cheese-app-v2/src/api-service/uv.lock`, under `name = "tensorflow"`), and `node:20-alpine`/`python:3.12-slim-bookworm` are multi-arch. Expect `Architecture: aarch64` in the banner.

---

## 7. Where this sits in the course

- **What you already have.**
  - L02/L04: containers, ports and Docker networks.
  - L05: the `llm-rag` chunk → embed → Chroma pipeline. `vector-db/cli.py` is a copy of it, the agent code included.
  - L06/L07: the agents.
  - L10 (`cheese-app-v0`): a FastAPI + Next.js RAG app, with service-account authentication and CORS.
  - L13: the MobileNetV2 cheese classifier whose trained artifact the API downloads.
  - L15 (`ml-workflow`): the service account and key file this API reuses.
- **What L18 adds.** Code organisation for a real app (`src/<service>/` folders, one container per concern), a REST API with routers, request models and file-backed state, and two frontends that consume it. Milestone 4 asks exactly for this: "Building APIs with FastAPI and connecting them to user-facing frontends (simple and React-based)" (`2026-AC215/milestone4.md:23`), with the frontend at e.g. `http://localhost:3000` and the API at `http://localhost:9000` (`2026-AC215/milestone4.md:88`).
- **What comes next.**
  - L19, "Scaling: Kubernetes (local)", shows "coming soon" on the course site (`2026-AC215/tutorials_demo.md:251-253`).
  - L20 uses **cheese-app-v3**. It pushes these three images (Docker Hub, then Artifact Registry), runs them on a VM behind NGINX, and later on Kubernetes (L22), with v4 adding CI/CD in L23.
  - The v2→v3 diff is small and telling (`git diff --no-index cheese-app-v2/src cheese-app-v3/src`). `service.py` renames the routed app to `api_app`, **enables `llm-rag` and `llm-agent`**, replaces `/square_root/` with `/status`, and mounts everything under `ROOT_PATH` (`app.mount(ROOT_PATH, api_app)`) so an ingress/NGINX path like `/api-service` works. `next.config.js` gains `output: "standalone"`. The frontend's prod `Dockerfile` becomes a non-root, 3-stage standalone build on `node:20-alpine`. `DataService` adds `GetStatus`. `.env.production`'s `NEXT_PUBLIC_BASE_API_URL=/api-service` (already in v2) is the hook for that reverse proxy.

**Version diffs**

*v0 → v1 (separate repos, not a git diff).* `cheese-app-v0` was rebuilt in October 2026 for L10, so it is *newer* than v1/v2 (last touched November 2025). It has a flat layout (`api-service/`, `frontend-ai-chatbot/`, `llm-rag/` at the repo root), a Pipfile-based API with one `/rag` router, a Next.js UI on host port 3200, and models `gemini-3.1-flash-lite` / `gemini-embedding-001` at `location="global"`. The v1 README text starts from scratch: an empty FastAPI app (`/` only), a static frontend with hard-coded data, and placeholder folders (`src/data-collector`, `src/vector-db`, … each with only `.gitkeep`). Both share the secrets-outside-the-repo convention (`../../secrets` from v0's `api-service`, `../../../secrets` from v1's `src/api-service`, the same folder).

*v1 → v2* (`git diff --no-index --stat cheese-app-v1/src cheese-app-v2/src`, condensed; "116 files changed, 81783 insertions(+), 6 deletions(-)", most of it the books, `uv.lock` and `package-lock.json`):

```text
 api-service/api/service.py           |   23 +   imports 6 routers, /square_root/, include_router x4 (+3 commented: rag, agent, test)
 api-service/api/routers/*.py         | ~760 +   newsletter, podcast, llm_chat, llm_cnn_chat, llm_rag_chat, llm_agent_chat, test_router
 api-service/api/utils/*.py           | ~750 +   chat_utils, llm_utils, llm_cnn_utils, llm_rag_utils, llm_agent_utils
 api-service/docker-entrypoint.sh     |   28 +-  uvicorn_server / uvicorn_server_production, DEV switch
 api-service/docker-shell.sh          |   14 +   GCP/Chroma env vars, network create, --network, -e DEV=1, key path
 api-service/pyproject.toml           |    4 +   chromadb, google-genai, pillow, tensorflow==2.19.0
 api-service/news-letters/, podcasts/ |  (data)  3 newsletters + images, 1 podcast + mp3
 frontend-simple/{chat,newsletters}*  | ~1030 +  two new pages + JS + CSS; index.html +2 nav links; unused index-simple.html (12)
 frontend-react/**                    |  new     whole Next.js 15 app (Dockerfile.dev, Dockerfile, src/app, src/components, src/services)
 vector-db/**                         |  new     Dockerfile, docker-compose.yml, cli.py, agent_tools.py, semantic_splitter.py, 11 books
 data-collector/, data-processor/, model-*/, newsletter/, podcast/, vector-db/ .gitkeep | deleted
 api-service/.gitignore               |    5 +-  ignores /chat-history and _test.py
```

The `api-service/Dockerfile`, `frontend-simple/Dockerfile`, `frontend-simple/main.js` and `styles.css` are byte-identical between v1 and v2.

---

## 8. Exercises

Try each one before you open its answer.

**E1 (hands-on, v1).** Add `@app.get("/hypot/{x}")` with `x: float` as a *path* parameter and `y: float = 0` as a *query* parameter, returning `(x**2 + y**2)**0.5`. Predict the responses to `/hypot/3?y=4`, `/hypot/3` and `/hypot/abc`, then run them.

<details><summary>Answer</summary>

5.0, 3.0, and a 422 with a `float_parsing` validation error that names `path` → `x`. `/docs` shows `x` as required (path) and `y` as optional (query) with default 0. The reload happens automatically because the file is under `api/`.

</details>

**E2 (predict, networking).** In `cheese-app-v2/src/frontend-react/.env.development`, change `NEXT_PUBLIC_BASE_API_URL` to `http://cheese-app-api-service:9000` and restart `npm run dev`. Predict what the Newsletters section on the home page does.

<details><summary>Answer</summary>

It stays empty. The console shows `ERR_NAME_NOT_RESOLVED` (or a network error), because the axios call runs in your browser, which resolves names with the laptop's DNS. Container names exist only inside Docker networks, and the React container is not even on `cheese-app-network`. Revert and restart.

</details>

**E3 (debugging).** You start the v2 API before the vector DB and get `ValueError: Could not connect to a Chroma server`. Your teammate says "but RAG is commented out in `service.py`!" Who is right, and what is the minimal code change to start the API without Chroma?

<details><summary>Answer</summary>

The error is real. Line 7 still *imports* `llm_rag_chat`, and its utils module creates `chromadb.HttpClient` at import (`llm_rag_utils.py:57`), which contacts the server in chromadb 1.3.0. Minimal change: comment out `from api.routers import llm_rag_chat, llm_agent_chat` (`service.py:7`) along with the commented include lines. A better design moves client creation into the request path (as the code already does for `get_collection`, `llm_rag_utils.py:92`) or into a FastAPI lifespan handler.

</details>

**E4 (debugging + CORS).** Enable the RAG router. In React, send a first RAG question (it works), then a follow-up. The modal says `AxiosError: Network Error` and DevTools shows a CORS error. Find the real bug and fix it.

<details><summary>Answer</summary>

The uvicorn terminal shows `TypeError: 'ChatMessage' object is not subscriptable` at `llm_rag_chat.py:99`, i.e. `message["content"]` on the pydantic model. Change it to `message_dict["content"]`, as was done for the CNN router in commit `7e61318`. The browser blamed CORS because unhandled exceptions are turned into 500s outside `CORSMiddleware`, so no `Access-Control-Allow-Origin` header was attached.

</details>

**E5 (conceptual, state).** Upload a cheese photo in React's **LLM + CNN** chat (you get, say, "brie (93%)"), then type "How should I store it?". Does Gemini know which cheese "it" is? Now save any file in `api/` (forcing a reload) and ask again in the same chat. What changes?

<details><summary>Answer</summary>

The first time, no. In `start_chat_with_llm` the image goes only to the CNN (`llm_cnn_chat.py:69-96`), and the Gemini session cached in `chat_sessions` never hears the label. After a reload the dict is empty, so `continue_chat_with_llm` calls `rebuild_chat_session`, which injects "We have already identified the image of a cheese as …" from the stored `cnn` message (`llm_cnn_utils.py:96-105`). Gemini now knows. This shows the difference between a cache and the source of truth. One fix is to `send_message` the label into the session at start. Caveat (not tested): React sends `content: ""` with an image-only message (`ChatInput.jsx:55-58`), so the rebuilt history also contains a user turn with an empty text part (`llm_cnn_utils.py:86-89`). If Vertex AI rejects empty text parts, the post-reload follow-up fails with an unhandled 500 instead (`llm_cnn_utils.py:77-79` has no `try`). Check the uvicorn log when you try it.

</details>

**E6 (hands-on, CORS).** In `service.py`, change `allow_origins=["*"]` to `allow_origins=["http://localhost:3000"]`. Predict which frontend still works: the simple one (8080), React (3000), or `/docs`?

<details><summary>Answer</summary>

React and `/docs` still work. `/docs` is same-origin with the API, so CORS does not apply, and `curl` is unaffected too. The simple frontend at `http://localhost:8080` fails. Its preflight gets a 400 "Disallowed CORS origin", and plain GETs come back without `Access-Control-Allow-Origin`, so newsletters and chat break with CORS errors. Add `"http://localhost:8080"` to fix it. (The 400 and the missing header were verified on 2026-10-12 in a scratch environment with the locked Starlette 0.49.3.)

</details>

**E7 (conceptual, RAG).** Someone "upgrades" only `EMBEDDING_MODEL` in `api/utils/llm_rag_utils.py` to a newer embedding model with the same 256 dimensions, leaving the Chroma data alone. Nothing crashes. What breaks?

<details><summary>Answer</summary>

Retrieval quality, silently. Query vectors now live in a different embedding space from the stored `text-embedding-004` vectors. Cosine distances become meaningless and the top-5 chunks are essentially arbitrary, so the LLM answers from irrelevant context. Equal dimensions only prevent a shape error. Re-embed the corpus with the new model (`cli.py --chunk --embed --load`), or keep both sides on the same model.

</details>

**E8 (hands-on, Next.js routing).** Create `src/app/about/page.jsx` that renders `<h1>About Formaggio</h1>` and add `{ name: 'About Page', path: '/about', ... }` to `navItems` in `Header.jsx`. Predict the URL, and whether you need to restart `npm run dev`.

<details><summary>Answer</summary>

`http://localhost:3000/about`. No restart is needed. `next dev` with `WATCHPACK_POLLING=true` picks up the new folder, and the App Router maps `app/about/page.jsx` → `/about`. The page automatically gets the Header/Footer from `layout.jsx`.

</details>

---

## 9. Errata and open questions

**Errata (with evidence)**
1. **Wrong folder paths in v1 README.** "`cheese-app-v1/api-service`" and "`cheese-app-v1/frontend-simple`" (`cheese-app-v1/README.md:41`, `:75`) should be `cheese-app-v1/src/api-service` and `cheese-app-v1/src/frontend-simple`. The scripts' `../../../secrets` only resolves correctly from `src/<service>`.
2. **v2 README says "three containers" and lists four** (`cheese-app-v2/README.md:3-7`). With the Chroma server, five run at once.
3. **README steps describe an older `service.py`.** The README tells you to add `square_root` and shows only the newsletter router enabled (`cheese-app-v2/README.md:96-104`, `:118-127`). The code at `14f2a14` already contains `square_root` and four enabled routers (`cheese-app-v2/src/api-service/api/service.py:30-40`). Following the README literally creates a duplicate route and a `Duplicate Operation ID` warning.
4. **Router filenames are wrong**: the README has `api/routers/newsletters.py` and `podcasts.py` (`cheese-app-v2/README.md:131-132`), but the actual files are `newsletter.py` and `podcast.py`.
5. **"Enable all the routes" / "Try LLM, LLM + CNN, RAG chats"** (`cheese-app-v2/README.md:138`, `:216`): RAG is disabled in code (`service.py:41`). The Agent router has no POST route and the agent utils are a stub (`llm_agent_chat.py:26-44`, `llm_agent_utils.py:1-26`), so the "Cheese Expert (Agent)" option in both UIs cannot work in v2.
6. **RAG follow-up bug.** `print("content:", message["content"])` on a pydantic model (`cheese-app-v2/src/api-service/api/routers/llm_rag_chat.py:99`) gives a 500 on every second RAG message. The identical bug was fixed for the CNN router in `7e61318` ("fixed key issue") but not here.
7. **Two key file names** (`ml-workflow.json` vs `llm-service-account.json`, section 6, item 2). The README mentions only one.
8. **Secrets text**: "Add the secret file from the `ml-workflow` tutorial" (`cheese-app-v2/README.md:25`) does not say what the file must be named or which roles it needs.
9. **README "review the code in `newsletters.html`/`chat.html`"** (`cheese-app-v2/README.md:176`, `:181`): the integration code is in `newsletters-main.js` and `chat-main.js`.
10. **Unused or unwired code.**
    - `SYSTEM_INSTRUCTION` is defined but never passed to `chats.create` (`cheese-app-v2/src/api-service/api/utils/llm_utils.py:30`, `:53`). The same is true in the CNN and RAG utils, so the RAG "use only the chunks" instruction is not enforced.
    - `GCS_BUCKET_NAME` is set but never read.
    - `api/utils/llm_agent_utils.py` is never imported. The agent router imports `llm_utils` instead (`cheese-app-v2/src/api-service/api/routers/llm_agent_chat.py:10-15`).
    - `MOCK_SERVICE = true` (`cheese-app-v2/src/frontend-react/src/services/Common.js:4`) does nothing. `ChatHistory.jsx:9` imports it but never uses it.
    - `DefaultSEO.jsx` imports `next-seo`, which is not in `package.json`. It is never imported, so it is harmless.
    - `next.config.js` adds an `@svgr/webpack` rule for a package that is not installed (`cheese-app-v2/src/frontend-react/next.config.js:4-10`) and declares `reactStrictMode` twice (`:3`, `:36`).
    - NextAuth is half-wired: `pages.signIn: '/signin'` (`cheese-app-v2/src/frontend-react/src/app/auth.js:38-40`), but there is no `/signin` page and no `app/api/auth/[...nextauth]` route.
11. **`vector-db/cli.py` `--chat` and `--agent` are broken.** They call an undefined `generative_model` (`cheese-app-v2/src/vector-db/cli.py:397`, `:445`, `:465`), leftovers from the old Vertex SDK. They are not used in L18.
12. **Frontend-simple Dockerfile** `ADD --chown=app:app . /app` (`cheese-app-v2/src/frontend-simple/Dockerfile:13`, same in v1). The Dockerfile rewrites to `node:20-alpine` (`0a2a030` "fixed simple frontend" in v1, `890950e` "fixed docker" in v2) removed the creation of user `app`. The pattern was verified on 2026-10-12 in a scratch environment with a minimal test Dockerfile on Docker 29.8.2. BuildKit (the default builder) silently falls back to uid/gid 0, so the build succeeds. The legacy builder (`DOCKER_BUILDKIT=0`) fails with `unable to convert uid/gid chown string to host mapping: can't find uid for user app: no such user: app`. Deleting `--chown=app:app` is the safe fix.
13. **Stale architecture images.** `cheese-app-v2/images/container-architecture-1.png` and `-2.png` show a "Mushroom Identifier" / "experiments CSV" app from an older course and are not referenced by the v2 README.
14. **Small front-end bugs:** see section 6, item 15. In addition, `ChatInput.jsx` calls an undefined `setError` on image-compression failure (`cheese-app-v2/src/frontend-react/src/components/chat/ChatInput.jsx:115`). `get_newsletter`/`get_podcast` return 500 rather than 404 for unknown ids (`cheese-app-v2/src/api-service/api/routers/newsletter.py:40-44`, `cheese-app-v2/src/api-service/api/routers/podcast.py:40-45`).
15. **The generative model is retired.** `gemini-2.0-flash-001` (`cheese-app-v2/src/api-service/api/utils/llm_utils.py:22` and copies) belongs to `gemini-2.0-flash`, which Google's Vertex AI model-versions page lists as retired on June 1, 2026 (upgrade: `gemini-3.1-flash-lite`). So no chat route works unpatched in October 2026. See section 6, item 4. `text-embedding-004` stays available until April 1, 2027 per the same page.
16. **Stale v1 README edit snippet.** The `index.html` edit (`cheese-app-v1/README.md:88-95`, "🧀 Welcome to the cheese identification App!") predates the current Formaggio template (`cheese-app-v1/src/frontend-simple/index.html`). Pasting it as a whole `<body>` removes the page, including the `main.js` script tag (section 4, A5).

**Open questions (could not determine from the sources)**
1. **The Ed lesson's content** (slides, any extra steps or announcements) was not accessible. If Ed tells you to use a newer branch or different model names, follow Ed.
2. **Resolved: model availability.** `gemini-2.0-flash` was retired on June 1, 2026, and `text-embedding-004` runs until April 1, 2027 (errata item 15; section 6, item 4). Still open: whether `gemini-3.1-flash-lite` is served on the `us-central1` endpoint or only on `global` (v0 uses `global`), and whether `text-embedding-004` answers on `global`. Neither was tested.
3. **Resolved: the zip layout.** `cheese-books-embeddings.zip` was downloaded and listed on 2026-10-12 in a scratch environment. Every entry starts with `outputs/` (11 chunks and 11 embeddings files, 14,356 rows of 256-d vectors), so `download()`'s `extractall()` into `/app` (`cheese-app-v2/src/vector-db/cli.py:494`) matches `load()`'s glob `outputs/embeddings-recursive-split-*.jsonl` (`:296-297`). The file does not record which embedding model made the vectors. Only `cli.py`'s `EMBEDDING_MODEL` says `text-embedding-004`.
4. **The persist path of the current `chromadb/chroma:latest` image.** v2 mounts `/chroma/chroma` and v0 (2026) mounts `/data`. Which one the image actually writes to decides whether v2's `docker-volumes/chromadb` survives container removal.
5. **Security of the locked Next.js 15.0.2.** The lock pins `next` 15.0.2 (`cheese-app-v2/src/frontend-react/package-lock.json`, entry `node_modules/next`). Next.js published security fixes for 15.x after that release, including advisories affecting the App Router and middleware. Fine for `localhost` study; upgrade before you expose a derivative of this app publicly. The repo gives no guidance.
6. **Whether the lecture expects you to reuse v1's container names while v2 is running.** They clash (section 6, item 7). The READMEs never say to stop v1 first.

---

## Links

**cheese-app-v1 README** (`main` @ `ce03a10`)
- [Prerequisites](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#prerequisites) · [Setup Environments](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#setup-environments) · [Create a local secrets folder](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#create-a-local-secrets-folder) · [Backend API Container](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#backend-api-container) · [View API Docs](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#view-api-docs) · [Frontend App (Simple) Container](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#frontend-app-simple-container) · [Docker Cleanup](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#docker-cleanup)
- Latest README on [`main`](https://github.com/dlops-io/cheese-app-v1#cheese-app---setup--code-organization)

**cheese-app-v2 README** (`main` @ `14f2a14`)
- [Tutorial (23): Environment Setup](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-23-environment-setup) · [Tutorial (23): Vector DB for RAG Setup](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-23-vector-db-for-rag-setup) · [Tutorial (23): Backend APIs](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-23-backend-apis) · [Create Demo Routes](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#create-demo-routes) · [Enable Cheese App API Routes](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#enable-cheese-app-api-routes)
- [Tutorial (24): Simple Frontend App](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-24-simple-frontend-app) · [Tutorial (25): React Frontend Setup](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-25-react-frontend-setup) · [Docker Cleanup](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#docker-cleanup)
- Latest README on [`main`](https://github.com/dlops-io/cheese-app-v2#cheese-app---apis--frontend)

**Course**
- Ed lesson: [L18 · APIs + Frontend](https://edstem.org/us/courses/97373/lessons/166043/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Previous lecture with a tutorial: [L15 · ML Workflows with Vertex AI](../guides/L15-vertex-ml-workflows.md) (the `ml-workflow` key this API reuses)
- Next lecture with a tutorial: [L20 · Deployment: Pulumi](../guides/L20-deployment-pulumi.md) (cheese-app-v3: these images on a VM behind NGINX)
- Referenced in section 7: [L05 · Introduction to RAG](../guides/L05-rag.md) · [L10 · Connecting to the Cloud (cheese-app-v0)](../guides/L10-cloud-connect-cheese-app-v0.md) · [L22 · Scaling: Kubernetes (cloud)](../guides/L22-kubernetes-cloud.md) · [L23 · Final Deployment and Review](../guides/L23-final-cicd-deployment.md)
