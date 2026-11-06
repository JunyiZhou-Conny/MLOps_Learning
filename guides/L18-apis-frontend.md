# L18 · APIs + Frontend — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166043/) · Tutorials: [`dlops-io/cheese-app-v1`](https://github.com/dlops-io/cheese-app-v1) `main` @ [`ce03a10`](https://github.com/dlops-io/cheese-app-v1/tree/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8) (the whole README) and [`dlops-io/cheese-app-v2`](https://github.com/dlops-io/cheese-app-v2) `main` @ [`447b5c3`](https://github.com/dlops-io/cheese-app-v2/tree/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47) (Environment Setup, Vector DB, Backend APIs, React Frontend, Setup & Run, Docker Cleanup), with *Tutorial (24): Simple Frontend App* from branch `2025` @ [`14f2a14`](https://github.com/dlops-io/cheese-app-v2/tree/14f2a1420b43e9f24e977a9e67b53d7e2614013d) (removed from `main` on 2026-11-05) and the extra *Production images* steps from [`e98fa55`](https://github.com/dlops-io/cheese-app-v2/tree/e98fa551c5d380517c6dc775ae626ea1a828e4d3)'s README · Video: [AC215 · L18 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l18-apis-frontend) · Made from the verified digest and real terminal captures, 2026-11-05

## 中文速览

- **做什么：** 全部在自己的 laptop 上用 Docker 跑 cheese app "Formaggio"，分三段。① **v1**：一个 FastAPI container（uvicorn，port 9000）加一个 `http-server` static frontend（8080），自己加一个 `/square_root/` route，看它出现在 `/docs` 里。② **v2 `main`（`447b5c3`）**：四个 container 在同一个 Docker network `cheese-app-network` 上：Chroma vector DB（8000，load 进 **14,356** 个 chunks）、loader CLI、api-service（`/api/...`，`/healthz`、`/readyz`，`pytest` 26 passed）、React + Vite frontend（host 3000 → container 5173），最后用 `docker compose up --build` 一条命令全部起来。③ **branch `2025`（`14f2a14`）**：lecture 讲的 simple frontend（Tutorial 24）在 2026-11-05 已经从 `main` 删掉了，要 `git switch 2025` 才能跑，而且要连同 2025 版的 vector DB 和 API 一起跑。
- **Idea 1 · uvicorn 是 server，FastAPI 是 app：** `uvicorn api.service:app` 的意思是 import `api/service.py`，用里面的变量 `app`。`--host 0.0.0.0` 才能让 `-p 9000:9000` 转进来的 request 找到它；`--reload` 让你存档就生效（log 里 `StatReload detected changes`）。type hints 就是 validation：`?x=abc` → 422；route 带 `/` 结尾时，少打一个 `/` → 307 redirect。
- **Idea 2 · `/healthz` vs `/readyz`：** `/healthz` 只说 process 活着；`/readyz` 要等 CNN model 下载并 load 完、Chroma 回 heartbeat 才 200（capture 里 503 → 约 9 秒后 200）。看到 503 先等，不要重启。
- **Idea 3 · chat 是一个 file，不是 memory：** browser 在 `localStorage` 存一个 UUID，每次带 `X-Session-ID` header；API 每条 message 都从 `persistent-folder/chat-history/<mode>/<session>/<chat>.json` 重建对话、存档、然后忘掉。所以任何一份 API copy 都能接着回答。
- **Idea 4 · one origin，所以 `main` 不需要 CORS：** React page 只 call 自己的 origin `localhost:3000/api/...`，Vite（dev）或 nginx（production image）按 container name 转给 `cheese-app-api-service:9000`。2025 的 simple page 从 8080 直接 call 9000，是 cross-origin，所以 API 要 `CORSMiddleware`，chat 的 POST 还会先发一个 preflight `OPTIONS`。
- **最费时间的坑：** ① v1 README 的路径少了 `src/`（`cd cheese-app-v1/api-service` → `No such file or directory`）。② `main` 的 API 没有 `/` 和 `/docs` 了（都是 404），docs 在 `/api/docs`；README:213 的 `localhost:900` 是 typo，应为 9000；Vite 印出 5173，但 laptop 上要开 3000。③ 没有有效的 Google key 时，Ask 和 Cheese books 都只回一个 `500 Internal Server Error`，原因只在 API 的 terminal 里：`RefreshError … invalid_grant`；`cli.py --chat` 也是同一个 traceback。Identify 的 CNN 不需要 Google，capture 里把一张 blue cheese 认成了 `parmigiano`（58.22%）。④ `git switch 2025` 会因为你改过的 project ID 被拒，先 `git stash`；2025 的 vector DB 还要第二个 key 名 `llm-service-account.json`。⑤ production frontend image 必须先有 API 在 network 上，否则 nginx `host not found in upstream`。
- **做完要删：** 所有 server 用 Ctrl-C，container shell 用 `exit`；`docker compose down`（`src/` 或 `src/vector-db`）；`docker system prune` 主要删的是 build cache（这次 4.583 GB）和没用的 network，**tagged images 和 `cheese-app-frontend-react-node_modules` volume 都还在**：API image 有 4.2 GB，用 `docker image rm` / `docker volume rm` 自己删。云上什么都没建，只有 Gemini / embedding call 计费。
- **Lecture slides：** 老师的 Lecture 18 有两份 slides（*APIs* 47 页、*Frontend* 42 页）。它们和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天 repo / captures 不一样的 9 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 上的 route 写成 `@app.get("/newsletters")` 和 `/chat`，今天的 `main` 其实是 router + prefix：`GET /api/newsletters`、`POST /api/llm/chats`（branch `2025` 上没有 `/api`，结尾的 `/` 不对就先收到一个 307）；② slide 上画了六个 route groups 和一个 MCP service，`main` 有 newsletters、podcasts 和三种 chat（`llm`、`llm-cnn`、`llm-rag`），没有 Agent route，MCP 根本没有实现。

## At a glance

- **What you build.** The cheese app "Formaggio", on your laptop, in Docker, in three passes. **v1** is one FastAPI container (uvicorn on 9000) and one static HTML/JS container (`http-server` on 8080); you add a route and watch it appear in `/docs`. **v2 on `main`** is four containers on one Docker network, `cheese-app-network` (`cheese-app-v2/README.md:3-10`): Chroma on 8000 loaded with 14,356 cheese-book chunks, the one-shot loader CLI, the API on 9000 (content, three chat modes that call Gemini on Vertex AI, a TensorFlow cheese classifier, health and readiness probes, 26 tests), and a React app served by Vite on 3000 that reaches the API through a proxy. You finish by starting all of it with one `docker compose up --build`. **Branch `2025`** brings back last year's simple frontend (Tutorial 24, the one the lecture's Frontend deck walks through), which calls the API directly from another origin, and so needs CORS.
- **Time needed** (estimate, not timed). About 3 hours for v1 and `main`: under an hour for v1, the rest for v2, where the first API build alone took 136 s in the captures plus the image download, and Chroma's load takes "about a minute" (`README.md:70-71`). Add 45 minutes for branch `2025`, which builds its own images.
- **Prerequisites.**
  - Docker Desktop (macOS/Windows) or Docker Engine with the compose plugin (Linux), ports 3000, 8000, 8080 and 9000 free, an editor and a browser. No host Python or Node.
  - About 10 GB of free disk for `main` (`cheese-app-v2/README.md:18`; the API image is 4.2 GB on disk) and more for branch `2025`.
  - For the chats only: a Google Cloud project with the Vertex AI API enabled and the `ml-workflow.json` key from L15, whose account needs **Vertex AI User** (`cheese-app-v2/README.md:15-17`). v1, the content routes, the probes, the tests, the CNN and the whole frontend work without it.
  - Background: L02/L04 (containers, `-p HOST:CONTAINER`, bind mounts, Docker networks), L05 (chunk → embed → Chroma), L10 (cheese-app-v0), L13 (the CNN), L15 (the key). See §7.
- **What it costs.** No cloud resource is created. Money goes only to Vertex AI calls made with your key: one Gemini call per Ask message, one embedding call plus one Gemini call per Cheese books message and per `cli.py --chat`, and Gemini for text messages in Identify. `python cli.py --download --load` makes no Vertex call (the embeddings come precomputed); `--chunk --embed` would bill.
- **What to tear down** (details in §2):
  1. Stop every server with Ctrl-C and leave every container shell with `exit`; every `docker run` here uses `--rm`, so those containers disappear.
  2. `docker compose down` in `src/` (after `docker compose up`) or in `src/vector-db` (Chroma keeps running after the CLI exits).
  3. `docker system prune` (the README's last step). It removes build cache and unused networks only (4.583 GB here, `e03`).
  4. *(extra)* Tagged images and the `node_modules` volume survive the prune (`e04`): `docker image ls`, then `docker image rm cheese-app-api-service` (4.2 GB) and the others you no longer need; `docker volume rm cheese-app-frontend-react-node_modules`.
  5. Nothing in the cloud. Revoke the key in IAM when the course ends.
- **How to read the references.** Paths start at the folder that holds your clones: `cheese-app-v2/src/api-service/api/service.py:36` means line 36 of that file in your `cheese-app-v2` clone on `main` (`447b5c3`). `cheese-app-v2@2025/…` means the same path on branch `2025` (`14f2a14`), `cheese-app-v2@e98fa55/README.md` the README one commit earlier. Capture ids such as `b21` name the files in the video's [`assets/terminal/laptop/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l18-apis-frontend/assets/terminal/laptop) (`b21-docker-shell-api.txt`).

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Which commit.** The course's tutorials page links the repos' default branches, unpinned. On 2026-11-05 `git ls-remote` (`p04`) gave:
  - `dlops-io/cheese-app-v1`: `main` = `ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8` (2025-11-02, "gitignore"). Followed as is.
  - `dlops-io/cheese-app-v2`: `main` = **`447b5c3c2c06d724e86dddf70e1a244dbe3d7c47`** (2026-11-05 07:52 −0500, "Merge pull request #2"; its one commit `55ffda8` is "updated readme + added docker compose"). `main` moved **twice on 2026-11-05**: at 07:23 to `e98fa551c5d380517c6dc775ae626ea1a828e4d3` (commits "removed frontend simple", "upgraded vector-db", "code cleanup", 131 files), then at 07:52 to `447b5c3`. Between those two only `README.md` and the new `src/docker-compose.yml` changed; every other file this guide quotes is byte-identical. The course map's pin `14f2a1420b43e9f24e977a9e67b53d7e2614013d` (2025-11-16, "image chat fix") is kept as branch **`2025`**.
- **What this guide follows, and why.** `main` for everything `main` still teaches, because that is what a student clones today. **Tutorial (24): Simple Frontend App from `14f2a14`**, because `main` deleted it (no `src/frontend-simple/`, `c02` vs `b02`) while the lecture teaches it and the course site still links it; its pages call routes that only the 2025 API serves, so the 2025 vector DB and API run with it. The *Production images* steps come from `e98fa55`'s README (lines 197–215), which `447b5c3` replaced with *Setup & Run*; the production `Dockerfile` and `nginx.conf.template` are still in `main`, so they are run here as extras.
- **README sections covered:**
  - `cheese-app-v1/README.md` (106 lines): Prerequisites, Setup Environments, Backend API Container, View API Docs, Frontend App (Simple) Container, Docker Cleanup.
  - `cheese-app-v2/README.md` @ `447b5c3` (246 lines): the intro table, Prerequisites (13), Tutorial: Environment Setup (20), Tutorial: Vector DB for RAG Setup (52), Tutorial: Backend APIs (81), Tutorial: React Frontend Setup (147), Tutorial: Setup & Run Cheese App (192), Troubleshooting (223), Docker Cleanup (235). The headings no longer carry the "(23)"/"(25)" numbers, so the course site's anchors `#tutorial-23-backend-apis` and `#tutorial-25-react-frontend-setup` open the top of the README.
  - `cheese-app-v2@2025/README.md` (247 lines): Tutorial (23): Environment Setup (12), Vector DB for RAG Setup (40), Backend APIs (67), Tutorial (24): Simple Frontend App (147–183).
  - `cheese-app-v2@e98fa55/README.md`: Production images (197–215), extra.
- **Terminal captures (the strongest evidence here).** Recorded 2026-11-05 (12:58–14:16 UTC) in a fresh, empty Docker engine standing in for a laptop: Docker 29.8.2, Compose v5.6.0, linux/amd64, git 2.54.0, user `student`, with `cheese-app-v1/`, `cheese-app-v2/`, `secrets/` and `persistent-folder/` side by side. Every README step was run as written, in README order, plus extras marked as such. Versions at the time of recording: v1 API Python 3.12.16, uv 0.13.7, FastAPI 0.120.4 / uvicorn 0.38.0; `main` API Python 3.13.18, uv 0.13.6, FastAPI 0.162.0, uvicorn 0.54.0, TensorFlow-cpu 2.21.0, pytest 9.2.0; Chroma `chromadb/chroma:1.5.9`; Node v24.22.1, npm 11.19.1, Vite 8.3.5, nginx 1.31.8; `http-server` 14.1.1; branch `2025`: Python 3.12.16, uv 0.13.7, TensorFlow 2.19.0, `chromadb/chroma:latest` (an image created 2026-05-05). Provenance: [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l18-apis-frontend/ASSETS.md).
- **The key in the captures.** `secrets/ml-workflow.json` was a well-formed service-account file around a throwaway key that belongs to no account, with the placeholder project `your-gcp-project`. Google's libraries load it, so everything that does not call Google behaves exactly as for a student, and the first Google call fails honestly with `invalid_grant: Invalid grant: account not found`. **No Gemini answer appears anywhere in this guide**: none was captured and no repo file documents one.
- **Context repos** (not run): `cheese-app-v0` `cb6fb94` (L10), `cheese-app-v3` `3ecef56` (L20/L22), `ml-workflow` (L15, the key).
- **Colab notebooks:** none for L18. **Ed lesson:** not accessible when these sources were checked; the lecture slides were used instead (next section).

</details>

## Lecture slides

The instructor's slides for this lecture come as two decks: *Lecture 18: APIs* (47 slides) and *Lecture 18: Frontend* (42 slides). "APIs 34" below means slide 34 of the APIs deck, and "Frontend 24" means slide 24 of the Frontend deck. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is paraphrased. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l18-apis-frontend/SLIDES.md`. That file writes APIs *n* as A*n* and Frontend *n* as B*n*. The decks were written against last year's code (branch `2025`); where they and today's `main` or the captures differ, the list at the end of this section says what to follow.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §7 Where this sits in the course | APIs 4–5 and Frontend 4–5 (roadmap: "Build Cheese App", the Backend API first, then the Frontend); APIs 7–21 (the technical architecture: the cluster that L20–L22 build); APIs 42 (the same request in production) |
| §1 What you build (the diagram) | APIs 19 (ports 3000, 9000, 8000); APIs 34–41 = Frontend 7–14 (one request, hop by hop); Frontend 24–27 (the browser calls the API) |
| §2 Folder layout and secrets; checklist *Setup* | APIs 43 |
| §3.1 REST; §3.2 FastAPI | APIs 25, 27–28, 39 |
| §3.3 uvicorn and `0.0.0.0` | APIs 26, 35–38 |
| §3.5 Two meanings of localhost | APIs 24, 28 (one API in front of every store); APIs 37–38; Frontend 24–26 |
| §3.7 Frontends | Frontend 16–27 (the simple frontend); Frontend 30–37 (why a framework; React; the header written once) |
| §3.8 One origin; §3.9 production image | APIs 42 |
| Checklist and §4 *Part A* (v1) | APIs 43, 34–41; Frontend 16–23 |
| Checklist and §4 *Part B*: Vector DB, Backend APIs | APIs 29, 44–45 |
| Checklist and §4 *Part B*: React Frontend | Frontend 30–38 |
| Checklist and §4 *Part C* (branch `2025`, simple frontend) | Frontend 18–28 |
| §5 Code tour | APIs 39 (a route); Frontend 24 (the axios call), 27 (the chat handler), 37 (the shared layout) |
| §6 Gotchas | APIs 45 (the vector DB first: item 6) |
| §3.4 probes, §3.6 state, CORS (§3.8), §3.10 Compose, §8 Exercises, §9 Errata | none (tutorial-only) |
| Not needed for this tutorial | APIs 22 (GCP / AWS / Azure building blocks), 30–33 (where agents sit; API vs MCP), 46 (team architecture exercise); Frontend 40–41 (app-building crash course and template repos) |

**Lecture ideas you need for this tutorial**
1. The project has moved from the ML pipeline to the app: a Backend API first, then a Frontend (APIs 4–5, Frontend 5).
2. In this course "API" means a REST API: a Web API over HTTP that uses the methods GET, POST, PUT and DELETE, built with FastAPI (APIs 27–28).
3. One API service is the front door. Every client speaks REST/JSON to it, and only it reaches the stores and models, which is why your browser never talks to Chroma or Gemini (APIs 24, 28).
4. The screens decide the routes: the newsletters, podcasts and chat screens lead to the API's route groups (APIs 29, 44).
5. Follow one request: browser → host port → port mapped into the container → FastAPI function → JSON back (APIs 34–41).
6. The vector DB must be running before the API (APIs 45). On `main` the API starts without it but `/readyz` answers 503 until Chroma answers; last year's API did not even start (§6, item 6).
7. A simple frontend makes two round trips. The container on 8080 serves the HTML, then the page's JavaScript, running in your browser, calls the API on 9000 (Frontend 18–27).
8. One HTML page per feature does not scale: nothing is reused and every page loads separately. So the course uses a component framework, React, in which the header is written once and only the content changes (Frontend 30–37).
9. Secrets live outside the Git folder, next to the repo (APIs 43).
10. In production only the outside changes, the address and the outer ports, not the FastAPI code or its port (APIs 42). The full blueprint puts NGINX in front of the app and API containers, with the vector DB container behind the API (APIs 19).

**Where the slides and today's tutorial differ** (in each case, follow `main` @ `447b5c3` and the 2026-11-05 captures; for Tutorial 24, branch `2025`)
1. The slides' handler is `@app.get("/newsletters")` in `service.py`. On `main` it is `@router.get("")` in `api/routers/newsletter.py:16`, mounted under `/api/newsletters` (`api/service.py:36`), and the React page reaches it through port 3000. On branch `2025` it is mounted at `/newsletters`, its URL ends in a slash, and the simple page's call gets a 307 first (`c25`; §4 Part C).
2. Frontend 27 says `/chat` (its code says `/chats`). The real chat routes are per mode: `POST /api/llm/chats` starts a chat and `POST /api/llm/chats/{chat_id}` continues it, and the same under `/api/llm-cnn` and `/api/llm-rag` (`b32`). On branch `2025` the paths have no `/api`, and the simple page's `POST /llm/chats/` gets a 307 to `/llm/chats` (`c28`).
3. APIs 44 shows six route groups, and APIs 24, 30, 32 and 33 an MCP service. `main` serves five groups: newsletters, podcasts and three chat modes made by one router factory (`api/service.py:36-40`). There is no agent route and no MCP service. Branch `2025` switches on four, with RAG and agent commented out (`c14`).
4. APIs 43's key file is `data-service.json`. `main` uses one key, `ml-workflow.json`, for the API and the vector DB (`src/api-service/docker-shell.sh:29`, `src/vector-db/docker-shell.sh:7`). Branch `2025`'s vector DB wants a second name, `llm-service-account.json` (§6 item 12).
5. APIs 43's folder tree (ten services, including `ml-workflow` and `postgres-db`) is the whole project. `main`'s `src/` holds `api-service`, `frontend-react`, `vector-db` and `docker-compose.yml` (`b02`).
6. The tutorial links on APIs 45 and Frontend 28 and 38 use anchors (`#setup-environments`, `#frontend-app-simple`, `#frontend-app-react`) that the v2 README does not have, and the course site's own anchors (`#tutorial-23-backend-apis`, `#tutorial-24-simple-frontend-app`, `#tutorial-25-react-frontend-setup`) no longer exist on `main`. Use the [Links](#links) at the end of this guide.
7. The slides say React, and `main` is React (19) with React Router, built and served by Vite 8: one `index.html`, `src/main.jsx` maps URLs to page components, and `src/App.jsx` holds the header once, with the page in an `<Outlet />` (§3.7). Last year's app on branch `2025` was Next.js 15; nothing on `main` uses Next.js.
8. APIs 37–42 label the inside of the container `localhost:9000`. uvicorn must listen on `0.0.0.0`, or the published port cannot reach it (§3.3).
9. APIs 42 shows production as `https://…/api/newsletters`, with port 80 mapped straight into the API container. On `main` the production frontend image is that outside: nginx on port 80 serves the built pages and passes `/api/` on to `http://cheese-app-api-service:9000`, path unchanged (`src/frontend-react/nginx.conf.template:13-14`), and the API's code and port stay the same (§4 Part B, *Production images*). L20's `cheese-app-v3` still has last year's layout, with an NGINX container and the path `/api-service` (§7).

## Command checklist

Commands in backticks or code blocks are exactly as the READMEs write them. Replace the project ID with yours. "Go to" URLs are opened in your browser. Items marked *(extra)* are not in the README; they are the checks §4 shows with real outputs. Where a README command fails today, it stays verbatim and a note gives the working variant.

### Setup: Setup Environments (v1 `README.md:14-35`) and Tutorial: Environment Setup (v2 `README.md:20-50`)

Run from one parent folder; it will hold both clones, `secrets/` and `persistent-folder/`.
- [ ] `git clone https://github.com/dlops-io/cheese-app-v1.git` — the README says "Clone or download" (v1 `README.md:18`) without a command; this is the usual clone (captured, `p01`).
- [ ] `git clone https://github.com/dlops-io/cheese-app-v2.git` — the same for v2 (`README.md:23`, `p02`).
- [ ] `git -C cheese-app-v2 log -1 --format='%H %ci %s'` — *(extra)* expect `447b5c3c2c06…` or newer (`p03`).
- [ ] `mkdir -p secrets persistent-folder` — the READMEs show the tree (v1 `README.md:24-35`, v2 `README.md:33-45`), not a command. Creating them yourself keeps them yours, not root's, on Linux (`p05`).
- [ ] Copy your `ml-workflow.json` key from L15 into `secrets/` (v2 `README.md:30`).
- [ ] Set your project: change `GCP_PROJECT` at the top of `src/api-service/docker-shell.sh` and `src/vector-db/docker-shell.sh` (v2 `README.md:47-50`). *(extra)* The same edit as one command, from `cheese-app-v2/`: `sed -i 's/"ac215-project"/"your-gcp-project"/' src/api-service/docker-shell.sh src/vector-db/docker-shell.sh`, with your own ID (`b03`).

### Part A · cheese-app-v1 · Backend API Container (`README.md:37-67`)

- [ ] Go to `cheese-app-v1/api-service` (`README.md:41`). **Note (captured):** `cd cheese-app-v1/api-service` fails with `No such file or directory` (`a01`); the folder is `cd cheese-app-v1/src/api-service`, and the scripts only find `../../../secrets` from there.
- [ ] `sh docker-shell.sh` — builds `cheese-app-api-service` and opens a shell in it (`README.md:44`).
- [ ] `uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/ "$@"` — starts the API inside the container (`README.md:47`).
- [ ] Go to `http://localhost:9000/` — `{"message":"Welcome to AC215"}` (`README.md:48`).
- [ ] Add at the end of `api/service.py` and save (`README.md:52-58`):
  ```
  @app.get("/square_root/")
  async def square_root(x: float = 1, y: float = 2):
      z = x**2 + y**2
      return z**0.5
  ```
- [ ] Go to `http://localhost:9000/square_root/` — `2.23606797749979` (`README.md:59`).
- [ ] Go to `http://localhost:9000/square_root/?x=2&y=10` — `10.198039027185569` (`README.md:61`).
- [ ] `curl -s -w '\n[HTTP %{http_code}]\n' 'http://localhost:9000/square_root/?x=abc'` — *(extra)* 422 (`a08`).
- [ ] `curl -s -i http://localhost:9000/square_root | head -6` — *(extra)* 307 to `/square_root/` (`a09`).
- [ ] Go to `http://localhost:9000/docs` — the interactive docs; you can try the routes there (`README.md:66-67`).
- [ ] *(extra)* Stop uvicorn with Ctrl-C and leave with `exit` before the frontend, or keep it running; the frontend does not need it.

### Part A · cheese-app-v1 · Frontend App (Simple) Container (`README.md:71-97`)

- [ ] Go to `cheese-app-v1/frontend-simple` (`README.md:75`). **Note (captured):** fails like the API path (`a19`); use `cd cheese-app-v1/src/frontend-simple`.
- [ ] `sh docker-shell.sh` — builds `cheese-app-frontend-simple` and opens a shell (`README.md:78`).
- [ ] `http-server` — serves the folder on 8080 (`README.md:82`).
- [ ] Go to `http://localhost:8080/` — the Formaggio.me landing page (`README.md:83`).
- [ ] Open `index.html` and add some text using the `<p>` tag (`README.md:86-95`); the README shows:
  ```
  <body>
      🧀 Welcome to the cheese identification App!
      <p>
          This is a placeholder for the awesome cheese identification app
      </p>
  </body>
  ```
  **Note:** that `<body>` comes from an older page; pasted as a whole, it replaces the page and drops `main.js`. Add only the `<p>` inside the hero section, as the capture does (`a23`).
- [ ] Refresh `http://localhost:8080/` — you see your text (`README.md:96-97`). If not, hard-refresh: `http-server` tells browsers to cache for 3600 s (`a25`).
- [ ] Stop `http-server` with Ctrl-C, then `exit`; stop uvicorn the same way in the API terminal.

### Part A · cheese-app-v1 · Docker Cleanup (`README.md:100-106`)

- [ ] `docker container ls` — nothing should be left; `--rm` removed both containers (`a30`).
- [ ] Stop any container that is running (`docker stop <name>`).
- [ ] `docker system prune` — answer `y` after reading the list (`a31`).
- [ ] `docker image ls` — the v1 images stay; remove them with `docker image rm` if you need the space (`a32`).

### Part B · cheese-app-v2 `main` · Tutorial: Vector DB for RAG Setup (`README.md:52-79`)

From the `cheese-app-v2` folder:
- [ ] `cd src/vector-db` (`README.md:58`).
- [ ] `./docker-shell.sh` — creates `cheese-app-network`, builds the CLI image, starts Chroma (`chromadb/chroma:1.5.9`) and opens a shell in the CLI container (`README.md:62`).
- [ ] `python cli.py --download --load --chunk_type recursive-split` — downloads the precomputed chunks and embeddings and loads 11 books, 14,356 chunks, into `recursive-split-collection` (`README.md:67`).
  *(optional, billed)* `--chunk --embed` make the same files from scratch (`README.md:71`): `python cli.py --chunk --embed --load --chunk_type recursive-split`, as the container's banner prints it (`b06`).
- [ ] `python cli.py --chat --chunk_type recursive-split` — one question through retrieval and Gemini (`README.md:75`); billed; needs a valid key (without one, `RefreshError`, `b06`). It always asks "How is cheese made?" (§6 item 17).
- [ ] `exit` — Chroma keeps running, with its data in `src/vector-db/docker-volumes/chromadb` (`README.md:78-79`).
- [ ] `docker ps` — *(extra)* `cheese-app-vector-db` Up on `0.0.0.0:8000->8000/tcp` (`b07`).

### Part B · cheese-app-v2 `main` · Tutorial: Backend APIs (`README.md:81-145`)

In a new terminal, from the `cheese-app-v2` folder:
- [ ] `cd src/api-service` (`README.md:88`).
- [ ] `./docker-shell.sh` — builds from `Dockerfile.dev` (a few minutes: TensorFlow) and opens a shell (`README.md:92`).
- [ ] `api_server` — starts uvicorn with reload on 9000 (`README.md:97`).
- [ ] Go to http://localhost:9000/healthz — the process is running: `{"ok":true}` (`README.md:101`).
- [ ] Go to http://localhost:9000/readyz — `503` `CNN model is loading` at first, then `200` once the model is loaded and Chroma answers (`README.md:102-103`).
- [ ] Open `api/service.py`, add this after `get_status`, and save (`README.md:106-112`):
  ```python
  @app.get("/api/square_root")
  def square_root(x: float = 1, y: float = 2):
      z = x**2 + y**2
      return z**0.5
  ```
- [ ] Go to http://localhost:9000/api/square_root — `2.23606797749979` (`README.md:114`).
- [ ] Go to http://localhost:9000/api/square_root?x=3&y=4 — `5.0` (`README.md:115`).
- [ ] Go to http://localhost:9000/api/docs — Swagger UI (`README.md:119`). **Note:** `http://localhost:9000/` and `/docs` are 404 on `main` (`b25`).
- [ ] Try `GET /api/newsletters` in the docs page (`README.md:120`); the curl the page shows is `curl -X 'GET' 'http://localhost:9000/api/newsletters?limit=2' -H 'accept: application/json'` (`b33`).
- [ ] Review the code: the table at `README.md:122-138` (§5).
- [ ] *(extra)* Chat by curl: `b36`–`b42` in §4 (422 without a session ID, Identify with a photo, the saved file).
- [ ] `pytest` — inside the container (`README.md:140-143`); in a second terminal, `./docker-shell.sh` again shells into the running container: `26 passed` (`b44`).
- [ ] Keep this container running (`README.md:145`).

### Part B · cheese-app-v2 `main` · Tutorial: React Frontend Setup (`README.md:147-190`)

In a new terminal, from the `cheese-app-v2` folder:
- [ ] `cd src/frontend-react` (`README.md:152`).
- [ ] `./docker-shell.sh` — builds the dev image, installs the npm packages into a named volume and opens a shell (`README.md:156`).
- [ ] `npm run dev` — Vite on container port 5173, published as 3000 (`README.md:161`).
- [ ] Open http://localhost:3000 (`README.md:164`). Vite prints `http://localhost:5173/`: that is inside the container; use 3000.
- [ ] Review the app: Home, Podcasts and Newsletters, Chat with Ask / Identify / Cheese books ("How is Tolminc cheese made?"); chats appear under **Recent** and survive a reload (`README.md:166-174`). Ask and Cheese books need a valid key.
- [ ] Review the code: the table at `README.md:176-185` (§5).
- [ ] `curl -s -i 'http://localhost:3000/api/newsletters?limit=2' | sed -n '1,8p'` — *(extra)* the API answers through port 3000: `server: uvicorn` (`d04`).
- [ ] `npm run check` — lint, format check and production build; in a second terminal `./docker-shell.sh` shells in (`README.md:187-190`, `d12`).

### Part B *(extra)* · Production images (`cheese-app-v2@e98fa55/README.md:197-215`)

Removed from the README at `447b5c3`; the files it uses are still in `main`.
- [ ] Stop `npm run dev` with Ctrl-C and leave the container with `exit`. Then, from `src/frontend-react`: (`README.md:201`)
- [ ] `docker build -t cheese-app-frontend-react:prod .` — two stages: `npm ci` + `vite build`, then `nginx:1.31.8-alpine` with the built files (`README.md:203`, `d20`).
- [ ] `docker run --rm --network cheese-app-network -p 8080:80 cheese-app-frontend-react:prod` — needs the API container running on the network first (`README.md:207`; without it, `e01`).
- [ ] Open http://localhost:8080 — the same app, served by nginx (`README.md:210`, `d22`–`d25`).
- [ ] `docker images | grep cheese-app-frontend-react` — dev 331 MB vs prod 94.8 MB (`README.md:214`, `d27`).

### Part B · cheese-app-v2 `main` · Tutorial: Setup & Run Cheese App (`README.md:192-221`)

- [ ] Do the Environment Setup first, then change `GCP_PROJECT` to your project ID in `src/docker-compose.yml`; it appears twice (`README.md:195-196`). *(extra, one command from `cheese-app-v2/`)* `sed -i 's/ac215-project/your-gcp-project/' src/docker-compose.yml` with your own ID (`f01`).
- [ ] Stop the containers still running: Ctrl-C and `exit` in their terminals, and `docker compose down` in `src/vector-db` (`README.md:198-199`, `f02`).
- [ ] `cd src` — from the `cheese-app-v2` folder (`README.md:203`).
- [ ] `docker compose up --build` — builds and starts the four services (`README.md:207`).
- [ ] Open http://localhost:3000. and http://localhost:900/api/docs. (`README.md:213`). **Note (captured):** `900` is a typo: `curl: (7) Failed to connect to localhost:900` (`f04-x-readme-url`); open `http://localhost:9000/api/docs`.
- [ ] The code is still mounted, so the API and the frontend reload when you save. To open a shell in a running container, for example to run `pytest`, run its `docker-shell.sh` as before (`README.md:215-216`).
- [ ] Stop everything with Ctrl-C, then `docker compose down` (`README.md:218-221`, `f10`).

### Part B · cheese-app-v2 `main` · Troubleshooting (`README.md:223-233`)

Only when you need them:
- [ ] `/readyz` answers `503` with `CNN model is loading`: wait; the first run downloads the model.
- [ ] `/readyz` or Cheese books says `Chroma: ...`: `docker compose up -d chromadb` in `src/vector-db`.
- [ ] Cheese books says `The vector DB is empty`: run step 2 of the Vector DB section again.
- [ ] Ask says `Gemini: 403` or `PERMISSION_DENIED`: check `GCP_PROJECT`, the Vertex AI API and the role; `Gemini: 404`: change `GENERATIVE_MODEL` in `api/settings.py`. **Note (captured):** a key Google rejects shows neither; the page gets a plain 500 and the API's terminal a `RefreshError` (§6 item 7).
- [ ] Pages load with no content: the API container is not running, or `api_server` is not started.
- [ ] `port is already allocated`: stop the other container; `docker ps` finds it.

### Part B · cheese-app-v2 `main` · Docker Cleanup (`README.md:235-246`)

- [ ] Stop the API and frontend containers with Ctrl-C and `exit`, then stop Chroma from `src/vector-db`: `docker compose down` (`README.md:237-240`). After *Setup & Run* there is nothing left to remove (`e02`).
- [ ] `docker system prune` — check the list it shows you first; it acts across all your projects (`README.md:242-246`, `e03`).
- [ ] `docker ps -a; docker images; docker volume ls; docker network ls` — *(extra)* what the prune kept: every tagged image and the `node_modules` volume (`e04`). Remove what you no longer need with `docker image rm …` and `docker volume rm cheese-app-frontend-react-node_modules`.

### Part C · branch `2025` (`14f2a14`) · Tutorial (24): Simple Frontend App, with its vector DB and API

The lecture's simple frontend lives only on branch `2025`. Its pages call last year's API, so this part runs last year's Tutorial (23) Vector DB and Backend APIs first. It builds its own images (more disk).
- [ ] `git switch 2025` — *(extra)* in `cheese-app-v2/`. **Note (captured):** refused while your project-ID and demo-route edits are uncommitted (`c01`); use `git stash && git switch 2025` (`c01b`).
- [ ] `cp ../secrets/ml-workflow.json ../secrets/llm-service-account.json` — *(extra)* the second key name the 2025 vector-DB script reads (`c03`; §6 item 12).
- [ ] Set `GCP_PROJECT` in `src/api-service/docker-shell.sh` and `src/vector-db/docker-shell.sh` again ("CHANGE TO YOUR PROJECT ID"; `c04`).

*Tutorial (23): Vector DB for RAG Setup* (`cheese-app-v2@2025/README.md:40-65`), from the folder that holds the clones:
- [ ] `cd cheese-app-v2/src/vector-db` (`README.md:46`).
- [ ] `sh docker-shell.sh` (`README.md:51`).
- [ ] `python cli.py --download --load --chunk_type recursive-split` (`README.md:56`); the same 14,356 chunks (`c06`).
- [ ] Keep this container running while setting up the backend API service and frontend apps (`README.md:65`). The capture leaves the shell with `exit`; Chroma keeps running (`c07`).

*Tutorial (23): Backend APIs* (`cheese-app-v2@2025/README.md:67-145`), in a new terminal, from the folder that holds the clones:
- [ ] `cd cheese-app-v2/src/api-service` (`README.md:74`).
- [ ] `sh docker-shell.sh` (`README.md:79`).
- [ ] Review `docker-shell.sh` (`-p 9000:9000`, `-e DEV=1`) and `docker-entrypoint.sh` (`README.md:82-86`).
- [ ] `uvicorn_server` (`README.md:92`); verify `http://localhost:9000` (`README.md:94`, `c12`).
- [ ] Create Demo Routes: the README's `@app.get("/square_root/")` snippet (`README.md:96-104`). **Note (captured):** it is already in `api/service.py:30-33` (`c13`); don't paste it again. Go to `http://localhost:9000/square_root/` and `http://localhost:9000/square_root/?x=2&y=10` (`README.md:105-108`).
- [ ] Go to `http://localhost:9000/docs` (`README.md:110-113`).
- [ ] Enable Cheese App API Routes (`README.md:116-138`); the README shows:
  ```python
  # Additional routers here
  app.include_router(newsletter.router, prefix="/newsletters")
  # app.include_router(podcast.router, prefix="/podcasts")
  # app.include_router(llm_chat.router, prefix="/llm")
  # app.include_router(llm_cnn_chat.router, prefix="/llm-cnn")
  # app.include_router(llm_rag_chat.router, prefix="/llm-rag")
  # app.include_router(llm_agent_chat.router, prefix="/llm-agent")
  ```
  then "Go to `http://localhost:9000/docs` and test the newsletters routes" and "Enable all the routes". **Note (captured):** the code is already past this point: four routers are on, RAG and agent are commented out (`c14`), and the router files are `newsletter.py`/`podcast.py`, not the README's `newsletters.py`/`podcasts.py`. Leave `service.py` as it is for this part.
- [ ] Keep this container running (`README.md:145`).

*Tutorial (24): Simple Frontend App* (`cheese-app-v2@2025/README.md:147-183`), in a new terminal, from the folder that holds the clones:
- [ ] `cd cheese-app-v2/src/frontend-simple` (`README.md:153`).
- [ ] `sh docker-shell.sh` (`README.md:158`).
- [ ] `http-server` (`README.md:163`).
- [ ] Visit `http://localhost:8080/index.html` — the landing page (`README.md:170`, `c22`).
- [ ] Open `http://localhost:8080/newsletters.html` — newsletters load from the API; the code is in `newsletters-main.js` (`README.md:174-176`, `c23`–`c25`).
- [ ] Open `http://localhost:8080/chat.html` and ask "How is cheese made?" (`README.md:179-181`); needs a valid key, and the 2025 Gemini model has since been retired (§6 item 13). Captured: preflight `200`, then `307` → `500` (`c27`, `c28`).

*Back to `main`* *(extra)*:
- [ ] Ctrl-C and `exit` in the three terminals; `docker stop cheese-app-vector-db` (`c30`).
- [ ] `git checkout -- . && git switch main && git log -1 --format='%h %s'` — discards the 2025 edits and returns to `447b5c3` (`c31`). Then `git stash pop` restores your `main` edits (not captured).

## 1. What you build

Three passes, one picture: a browser on your laptop, containers behind published ports, and an API that alone talks to the stores and to Google.

- **v1** (`ce03a10`) is the minimum. A Python container runs a FastAPI app under uvicorn on 9000, and a Node container serves static files with `http-server` on 8080. The v1 page never calls the API: its podcast cards are "Sample Podcast Data (This would normally come from an API)" (`a22`, `cheese-app-v1/src/frontend-simple/main.js:37`).
- **v2 `main`** (`447b5c3`) is the real app, drawn below. The browser asks only port **3000**. Vite, running inside the frontend container, forwards everything under `/api` to the API **by container name** over `cheese-app-network`, so the page has one origin and the API needs no CORS (`cheese-app-v2/docs/contract.md:6-7`). In production, nginx takes Vite's place.
- **v2 `2025`** (`14f2a14`, only for Tutorial 24) is last year's design: the page from 8080 calls `http://localhost:9000` directly through the API's published port, so the API must allow that other origin with `CORSMiddleware` (`cheese-app-v2@2025/src/api-service/api/service.py:15-21`).

```text
 YOUR LAPTOP (Docker)  — cheese-app-v2 main 447b5c3                                  GOOGLE CLOUD
 ================================================================================   ======================
  BROWSER                                                                            Vertex AI, location global
   http://localhost:3000/chat?model=llm                                              Gemini (gemini-3.8-flash)
     | (1) GET the page and its JS from :3000                                        text-embedding-004 (256-d)
     | (2) fetch('/api/llm/chats'), same origin :3000, header X-Session-ID                   ^
     v                                                                                       | (5) HTTPS, token from
 ---- published ports -p HOST:CONTAINER -----------------------------------------------------|---- /secrets/ml-workflow.json
   3000:5173                         9000:9000 (for you: /api/docs, /healthz, /readyz, curl) |
     |                                     |                                                 |
 +---v--------------------------------+  +-v-----------------------------------------------+-+
 | cheese-app-frontend-react          |  | cheese-app-api-service                          |
 | node:24.22.1, user node            |  | python:3.13-slim, user app (uid 1000)           |
 | `npm run dev` = Vite on :5173      |  | `api_server` = uvicorn api.service:app          |
 | /app <- src/frontend-react (bind)  |  |   --host 0.0.0.0 --port 9000 --reload           |
 | /app/node_modules <- named volume  |  | /app <- src/api-service (bind)                  |
 | (3) proxy: /api ->                 |->| /secrets <- secrets/ (read-only)                |
 |   http://cheese-app-api-service:9000  | /persistent <- persistent-folder/               |
 +------------------------------------+  |   chat-history/<mode>/<session>/<chat>.json     |
                                         |   experiments/ (the CNN, from GitHub releases)  |
                                         +------------------------+------------------------+
                                                                  | (4) cheese-app-vector-db:8000
                                                                  v     (Docker DNS: the container name)
 +------------------------------------------+   (0) load  +------------------------------------------+
 | cheese-app-vector-db-cli (one-off)       |------------>| cheese-app-vector-db                     |
 | python cli.py --download --load          |  HTTP 8000  | chromadb/chroma:1.5.9, published 8000    |
 |   --chunk_type recursive-split           |             | src/vector-db/docker-volumes/chromadb    |
 | (0a) cheese-books-embeddings.zip, GitHub |             | collection recursive-split-collection    |
 +------------------------------------------+             +------------------------------------------+
            all four containers on the user-defined network cheese-app-network
```

The lecture's request trace (APIs 34–41) fits this picture with one hop added, "3½": the courier inside the frontend container. Without it, step 2 would have to leave the browser for port 9000, as it does on branch `2025`.

## 2. Prerequisites and costs

**Folder layout.** The scripts mount `$(pwd)/../../../secrets/` and `$(pwd)/../../../persistent-folder/` (`cheese-app-v2/src/api-service/docker-shell.sh:7-8`, `cheese-app-v1/src/api-service/docker-shell.sh:9-10`): three levels up from `src/<service>`, the folder that holds the clones. The captured layout (`p06`, trimmed):
```
.
./cheese-app-v1
./cheese-app-v1/src/api-service
./cheese-app-v1/src/frontend-simple
…
./cheese-app-v2/docs/contract.md
./cheese-app-v2/src/api-service
./cheese-app-v2/src/docker-compose.yml
./cheese-app-v2/src/frontend-react
./cheese-app-v2/src/vector-db
./persistent-folder
./secrets
./secrets/ml-workflow.json
```
`src/docker-compose.yml` mounts `../../secrets` and `../../persistent-folder` from `src/` (`cheese-app-v2/src/docker-compose.yml:24-25`, `:45-46`): the same two folders.

**Software.** Docker with Compose v2 (`docker compose`). Branch `2025`'s vector-DB script calls the hyphenated `docker-compose` (`cheese-app-v2@2025/src/vector-db/docker-shell.sh:20`); it worked on the capture engine, and §6 item 14 has the variant for compose-plugin-only installs.

**Google.** A project with the Vertex AI API on, and the L15 key `ml-workflow.json` with Vertex AI User (`cheese-app-v2/README.md:15-17`). The key comes from the `ml-workflow` tutorial (L15). Set the project ID in three places on `main`: two `docker-shell.sh` files (`README.md:47-50`) and twice in `src/docker-compose.yml` (`README.md:195-196`).

**Disk.** "About 10 GB of free disk space" (`README.md:18`). Captured sizes: `main`'s API image **4.2 GB** on disk (790 MB content), vector-DB CLI 813 MB, Chroma 826 MB, React dev 331 MB, React prod 94.8 MB, v1 API 860 MB, simple frontend 218 MB (`b46`, `d27`, `a32`). Branch `2025` builds its own API image with full TensorFlow 2.19; budget the same again.

**Costs.** Only Vertex AI calls with your key (At a glance). No VM, bucket or endpoint is created. The CNN, the newsletters, the podcasts, the probes and the tests are free.

**Tear down, exactly.**
1. Ctrl-C every server (uvicorn, Vite, `http-server`, nginx, `docker compose up`), `exit` every container shell.
2. `docker compose down` in `src/` after *Setup & Run* (`f10` removes all four containers), or in `src/vector-db` for Chroma after the step-by-step sections (`f02`). On branch `2025`, `docker stop cheese-app-vector-db` (`c30`).
3. `docker system prune`: it deleted `cheese-app-network` (no longer used) and 4.583 GB of build cache, and kept every tagged image and the `node_modules` volume (`e03`, `e04`).
4. *(extra)* `docker image rm cheese-app-api-service cheese-app-vector-db-cli cheese-app-frontend-react cheese-app-frontend-react:prod cheese-app-frontend-simple chromadb/chroma:1.5.9` for what you no longer need, and `docker volume rm cheese-app-frontend-react-node_modules`.
5. Your chat files stay in `persistent-folder/chat-history/` and the CNN in `persistent-folder/experiments/` (9 MB zip plus the model); Chroma's data stays in `src/vector-db/docker-volumes/chromadb` (50.9 MB) and the downloads in `src/vector-db/outputs` (78.8 MB) (`b09`, `b26`). Delete them when you are done; Git ignores them.

## 3. Concepts this tutorial teaches

### 3.1 REST: nouns (paths) and verbs (HTTP methods)

A REST API exposes resources as paths and acts on them with HTTP methods. `main`'s whole surface is 25 operations (`b32`): `GET /api/newsletters`, `GET /api/newsletters/{newsletter_id}`, `GET /api/podcasts/audio/{audio_name}`, and per chat mode `GET`/`POST /api/<mode>/chats` and `GET`/`POST /api/<mode>/chats/{chat_id}`, plus `/healthz` and `/readyz` at the root. GET reads; POST creates (a new chat) or adds (a message). The answer's status code is part of the contract (`cheese-app-v2/docs/contract.md:46-54`): 404 no such chat or content, 422 invalid input, 502 Gemini failed, 503 the CNN is loading or Chroma is down.

### 3.2 FastAPI: decorators build a route table, type hints build validation and docs

`@app.get("/square_root/")` adds a row to the app's route table. The function's parameters become query parameters, and their type hints become validation: `?x=abc` never reaches your code, FastAPI answers `422` with `"type":"float_parsing","loc":["query","x"]` (`a08`). The same table produces the OpenAPI schema (`/openapi.json`) and the Swagger page (`/docs` in v1; `/api/docs` on `main`, set by `docs_url` at `cheese-app-v2/src/api-service/api/service.py:27`).

A route declared **with** a trailing slash answers the slash-less path with `307 Temporary Redirect` and `location: …/square_root/` (`a09`); a browser follows it silently, curl needs `-L`. On `main` the demo route has no slash, and routers declare their root as `""` (`api/routers/newsletter.py:16`), so the slash-less path is the real one.

**Routers and prefixes.** A big API is split into routers, each mounted under a prefix: `app.include_router(newsletter.router, prefix="/api/newsletters")` (`api/service.py:36`). On `main` the three chat modes come from one factory, `chat.create_router(model, respond)` (`api/routers/chat.py:31`), mounted three times with a different `respond` (`api/service.py:38-40`).

### 3.3 Server vs app: uvicorn, `--host 0.0.0.0`, `--reload`

uvicorn is the **server**: it owns the port, speaks HTTP and calls the **app**. `api.service:app` is an address: import the module `api.service` (folder `api/`, file `service.py`, relative to `/app`) and use its variable `app` (`cheese-app-v1/src/api-service/api/service.py:5`, `cheese-app-v2/src/api-service/api/service.py:26`).

`--host 0.0.0.0` makes uvicorn listen on every interface of the container. Docker's `-p 9000:9000` delivers your request to the container's network interface, not to its loopback; a server on `127.0.0.1` answers inside the container and resets your browser's connection (exercise B1). The lecture's "localhost:9000" inside the container (APIs 37–42) means "port 9000 of the container".

`--reload --reload-dir api/` runs a reloader that restarts the worker when a file under `api/` changes: `StatReload detected changes in 'api/service.py'. Reloading...` (`a03`). With the source bind-mounted into `/app`, saving in your editor is enough. On `main`, each restart also reloads the CNN, so `/readyz` drops to 503 briefly after every save.

### 3.4 Liveness vs readiness: `/healthz` and `/readyz`

`/healthz` checks nothing: if the process can run a route, it answers `{"ok":true}` (`api/service.py:43-45`). `/readyz` checks that the CNN model is loaded and that Chroma answers a heartbeat (`api/service.py:48-56`). The model loads in a background thread started by the app's lifespan (`api/service.py:19-23`), so the API answers at once and reports when it is ready: `503 {"detail":"CNN model is loading"}` at 13:49:35, `200` at 13:49:44 (`b23`, `b24`). Liveness answers "restart this process?", readiness "send it traffic yet?". The difference matters in L22, where Kubernetes acts on both.

### 3.5 Where code runs, and two meanings of "localhost"

Two kinds of arrows, two kinds of addresses:
- **Your laptop → a container** goes through a published port: `localhost:3000` (frontend), `localhost:9000` (API), `localhost:8000` (Chroma). `docker ps` shows them as `0.0.0.0:3000->5173/tcp` and so on (`d10`).
- **A container → a container** goes over `cheese-app-network`, by container name, on the container's own port: the API reaches `cheese-app-vector-db:8000` (`settings.py:14`), Vite reaches `cheese-app-api-service:9000` (`vite.config.js:13`). Docker's DNS answers those names only on that network (`b10`).

Inside a container, `localhost` is that container. Point Vite's proxy at `http://localhost:9000` and it gets `ECONNREFUSED` (exercise B7), although the laptop publishes 9000. And the page's JavaScript runs in **your browser**, outside every container: it can reach published ports, never a container name.

### 3.6 Stateless HTTP, and where chat state lives

HTTP forgets between requests. `main` keeps a chat in three places:
- **The session ID** in the browser: a random UUID in `localStorage` (`src/frontend-react/src/lib/api.js:17-29`), sent as `X-Session-ID` with every call (`api.js:34`). The API accepts only a UUID (`api/routers/chat.py:19-21`), because the ID becomes part of a file path.
- **The chat file** on disk, the source of truth: `/persistent/chat-history/<mode>/<session>/<chat>.json`, images beside it under `images/<chat>/<message>.png` (`api/utils/chat_utils.py:28-36`); `/persistent` is your `persistent-folder/` (`b42`).
- **Nothing in memory.** Each message opens the file, rebuilds the conversation, adds the turn, saves and forgets (`api/routers/chat.py:35-43`, `:69-76`; `README.md:135-136`). Any copy of the API that sees the same files can answer the next message.

The 2025 simple chat page made a new UUID on every page load (`cheese-app-v2@2025/src/frontend-simple/chat-main.js:14`), so a reload started a new session.

### 3.7 Frontends: files the browser runs, then components

A static site is files: `http-server` returns `index.html`, `main.js` and `styles.css`, and the browser builds the page and runs the JavaScript (Frontend 16–23). The container takes no part in what the JavaScript does next.

`main`'s React app is a single-page app. `index.html` holds an empty `<div id="root">` and one script, `/src/main.jsx` (`d03`). `src/main.jsx` maps URLs to page components with React Router (`src/main.jsx:15-26`), and `src/App.jsx` draws the header once, with the current page in an `<Outlet />`: the lecture's "header defined only once" (Frontend 37). Because the router runs in the browser, every URL returns the same `index.html` (`d08`: even `/nope` is `200 text/html`), and the page decides what to show. Vite serves your source transformed on the fly in development (`d05`) and bundles it for production (`npm run build`, `d12`).

### 3.8 One origin: the dev proxy, and why last year needed CORS

An **origin** is scheme + host + port: `http://localhost:3000` and `http://localhost:9000` are different origins. The browser's same-origin policy lets a page read answers from its own origin; for another origin, it needs the server's permission in `access-control-allow-origin`.
- **`main`:** the page calls relative paths, `fetch(path, …)` (`api.js:44`), on its own origin. Vite's proxy (`vite.config.js:13`) or nginx (`nginx.conf.template:13-14`) carries them to the API. The browser never sees port 9000, so there is nothing to permit: `main`'s API has no CORS middleware, and a cross-origin request gets `200` with **no** `access-control-*` header, its preflight `405 Method Not Allowed` (`b43`).
- **Branch `2025`:** the page from 8080 calls `http://localhost:9000` (`newsletters-main.js:3`, `chat-main.js:2`), and the API grants it with `CORSMiddleware(allow_origins=["*"])` (`cheese-app-v2@2025/src/api-service/api/service.py:15-21`): every answer carries `access-control-allow-origin: *` (`c25`). The chat POST sends JSON with a custom `X-Session-ID` header, so the browser first sends a **preflight** `OPTIONS`, answered `200` with the allowed methods and headers (`c27`, and `OPTIONS /llm/chats` in `c11`).

CORS is a permission the server hands out, not a protection it turns on; curl and other servers never ask (exercise D3). And a "CORS error" in the console is often a crash: an **unhandled** exception's 500 carries no CORS header, so the browser hides it (exercise C6). Read the server's terminal first. v1's API carries the same `CORSMiddleware` (`cheese-app-v1/src/api-service/api/service.py:8-14`), unused by v1's page.

### 3.9 The dev loop, and what goes into a production image

Development images hold the tools, not the code: your folder is bind-mounted into `/app`, the server reloads on save, and `main`'s frontend keeps `node_modules` in a named volume (`cheese-app-frontend-react-node_modules`, 207 entries, 193 MB; `d11`) so the host folder does not need it. Rebuild an image only when dependencies or a Dockerfile change.

The production frontend image (`src/frontend-react/Dockerfile`) builds in a Node stage (`npm ci`, `npm run build`) and keeps only `dist/` on `nginx:1.31.8-alpine`: 94.8 MB instead of 331 MB, with a 766 kB layer of your files (`d27`, `d28`). nginx fills in `API_URL` when it starts (`Running envsubst on /etc/nginx/templates/default.conf.template`, `d21`), so the same image runs anywhere. The browser code does not change between dev and production; only the courier does.

### 3.10 Docker Compose: the three terminals as one file

`src/docker-compose.yml` declares the four services, their ports, mounts, environment and start order (`depends_on`). `vector-db-loader` checks whether the books are already loaded and loads them only if not (`src/docker-compose.yml:22`), then exits `0` (`f04-x-compose-ps`). `docker compose up --build` builds what changed and streams every container's log into one terminal, prefixed by service; Ctrl-C stops them and `docker compose down` removes them (`f10`). The names are the same as in the step-by-step sections, so the two ways collide: stop one before starting the other (`README.md:198-199`).

## 4. Step-by-step walkthrough

Steps follow the README order. Commands are verbatim from the READMEs unless marked *(extra)*.

**About the outputs below.** Outputs labelled *captured* are real, trimmed with `…`, from the 2026-11-05 captures (file id with each block; `[exit N]` lines omitted unless they matter; build logs reduced to their first and last lines). The capture had no Google account (*Versions and sources*, above), so every Gemini or embedding call shows its honest first error, and what only a valid key shows is labelled *expected* and quoted from the repo's own documentation. Times, IDs, container hashes and addresses will differ for you; versions may be newer.

### Part 0: before you start

*Captured* (`p00`, `p03`, `p05`; the merge subject trimmed):
```
$ docker version --format 'Docker client {{.Client.Version}}, engine {{.Server.Version}}'; docker compose version; …
Docker client 29.8.2, engine 29.8.2
Docker Compose version v5.6.0
$ git clone https://github.com/dlops-io/cheese-app-v1.git
Cloning into 'cheese-app-v1'...
$ git clone https://github.com/dlops-io/cheese-app-v2.git
Cloning into 'cheese-app-v2'...
$ git -C cheese-app-v1 log -1 --format='%H %ci %s'; git -C cheese-app-v2 log -1 --format='%H %ci %s'; git -C cheese-app-v2 branch -r
ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8 2025-11-02 07:33:53 -0500 gitignore
447b5c3c2c06d724e86dddf70e1a244dbe3d7c47 2026-11-05 07:52:33 -0500 Merge pull request #2 …
  origin/2025
  origin/HEAD -> origin/main
  origin/main
  …
$ mkdir -p secrets persistent-folder
```
Put your key in `secrets/ml-workflow.json`. Note `origin/2025`: Part C needs it.

### Part A: cheese-app-v1 (`ce03a10`)

**A1 · Go to the API folder** (`README.md:40-41`). *Captured* (`a01`, `a02`):
```
$ cd cheese-app-v1/api-service
bash: line 1: cd: cheese-app-v1/api-service: No such file or directory
$ cd cheese-app-v1/src/api-service && ls          (extra: the folder that exists)
Dockerfile
api
docker-entrypoint.sh
docker-shell.sh
pyproject.toml
uv.lock
```

**A2 · Build & run, start the API** (`README.md:43-48`). `docker-shell.sh` builds the image and runs it with the folder mounted at `/app`, `secrets/` and `persistent-folder/` mounted, and `-p 9000:9000` (`cheese-app-v1/src/api-service/docker-shell.sh:13-21`). *Captured* (`a03`):
```
$ sh docker-shell.sh
[+] Building 49.9s (11/11) FINISHED
 …
 => [5/6] RUN uv sync --frozen                                                1.9s
 …
Container is running!!!
Architecture: x86_64
Environment ready! Virtual environment activated.
Python version: Python 3.12.16
UV version: uv 0.13.7 (x86_64-unknown-linux-gnu)
Activating virtual environment...
app@20a498fecc6f:/app$ uvicorn api.service:app --host 0.0.0.0 --port 9000 --log-level debug --reload --reload-dir api/ "$@"
INFO:     Will watch for changes in these directories: ['/app/api']
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
INFO:     Started reloader process [12] using StatReload
INFO:     Started server process [14]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
The prompt is your shell **inside** the container; on a Mac the banner says `aarch64`. In a second terminal (`a04`, *captured*):
```
$ curl -s -i http://localhost:9000/
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"message":"Welcome to AC215"}
```

**A3 · Add the route** (`README.md:50-58`). Paste the snippet at the end of `api/service.py` in your editor. *Captured* diff (`a05`) and what the server's terminal printed (`a03`):
```
@@ -18,3 +18,8 @@ app.add_middleware(
 @app.get("/")
 async def get_index():
     return {"message": "Welcome to AC215"}
+
+@app.get("/square_root/")
+async def square_root(x: float = 1, y: float = 2):
+    z = x**2 + y**2
+    return z**0.5

WARNING:  StatReload detected changes in 'api/service.py'. Reloading...
…
INFO:     Application startup complete.
```

**A4 · Try it** (`README.md:59-62`, extras after). *Captured* (`a06`–`a09`):
```
$ curl -s http://localhost:9000/square_root/; echo
2.23606797749979
$ curl -s 'http://localhost:9000/square_root/?x=2&y=10'; echo
10.198039027185569
$ curl -s -w '\n[HTTP %{http_code}]\n' 'http://localhost:9000/square_root/?x=abc'          (extra)
{"detail":[{"type":"float_parsing","loc":["query","x"],"msg":"Input should be a valid number, unable to parse string as a number","input":"abc"}]}
[HTTP 422]
$ curl -s -i http://localhost:9000/square_root | head -6                                  (extra)
HTTP/1.1 307 Temporary Redirect
…
location: http://localhost:9000/square_root/
```
The server's access log (`a03`) records the same story: `"GET /square_root/?x=abc HTTP/1.1" 422 Unprocessable Entity`, `"GET /square_root HTTP/1.1" 307 Temporary Redirect`.

**A5 · View API docs** (`README.md:64-67`). *Captured* (`a10`): `<title>API Server - Swagger UI</title>` with `url: '/openapi.json'`. The schema lists `x` and `y` as numbers with defaults 1 and 2 (`a11`). Stop uvicorn with Ctrl-C when you are done (`Stopping reloader process [12]`).

**A6 · The simple frontend** (`README.md:71-83`). The README's path fails again (`a19`); from the parent folder, `cd cheese-app-v1/src/frontend-simple`. The image is `node:20-alpine` plus `http-server` (`cheese-app-v1/src/frontend-simple/Dockerfile:1-15`). *Captured* (`a20b`):
```
$ sh docker-shell.sh
[+] Building 8.8s (9/9) FINISHED
…
f3e65d54d0cb:/app# http-server
Starting up http-server, serving ./

http-server version: 14.1.1
…
CORS: disabled
Cache: 3600 seconds
…
Available on:
  http://127.0.0.1:8080
  http://172.18.0.3:8080
Hit CTRL-C to stop the server
```
Both addresses are the container's; on the laptop it is `http://localhost:8080/`. *Captured* (`a21`, `a22`):
```
$ curl -s -i http://localhost:8080/ | grep -E 'HTTP/|cache-control|content-type|<title>|hero-title|main.js'
HTTP/1.1 200 OK
cache-control: max-age=3600
content-type: text/html; charset=UTF-8
    <title>Formaggio.me</title>
            <h1 class="hero-title">🧀 Formaggio.me is here!</h1>
    <script src="main.js"></script>
$ curl -s http://localhost:8080/main.js | grep -n -A3 'Sample Podcast Data'          (extra)
37:// Sample Podcast Data (This would normally come from an API)
38-const podcastData = [
```
So the v1 page makes one round trip only: files from 8080. It never calls 9000.

**A7 · Edit `index.html`** (`README.md:85-97`). Add a `<p>` inside the hero section; the README's `<body>` snippet would replace the whole page (§9, erratum 3). *Captured* diff (`a23`) and the served page after a refresh (`a24`):
```
             <p class="hero-subtitle">Discover the world of cheese through AI</p>
+            <p>
+                This is a placeholder for the awesome cheese identification app
+            </p>

$ curl -s http://localhost:8080/ | grep -n -B1 -A1 'placeholder for the awesome'
46:                This is a placeholder for the awesome cheese identification app
```
If your browser still shows the old page, that is the 3600-second cache header (`a25`): hard-refresh.

**A8 · Docker Cleanup** (`README.md:100-106`). After Ctrl-C and `exit` in both terminals, *captured* (`a30`–`a32`):
```
$ docker container ls
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
$ docker system prune
WARNING! This will remove:
  - all stopped containers
  - all networks not used by at least one container
  - all dangling images
  - unused build cache

Are you sure you want to continue? [y/N] y
…
Total reclaimed space: 290.8kB
$ docker image ls
IMAGE                               ID             DISK USAGE   CONTENT SIZE
cheese-app-api-service:latest       0ea118e4c49c        860MB          214MB
cheese-app-frontend-simple:latest   b870aebc2f66        218MB         55.1MB
…
```
The images stay: `prune` removes only dangling ones. `main`'s API reuses the name `cheese-app-api-service` and replaces this image when it builds.

### Part B: cheese-app-v2 `main` (`447b5c3`)

**B0 · Environment Setup** (`README.md:20-50`). From `cheese-app-v2/`, *captured* (`b02`, `b03` trimmed, `b04`):
```
$ ls; ls src
README.md
docs
images
src
api-service
docker-compose.yml
frontend-react
vector-db
$ sed -i 's/"ac215-project"/"your-gcp-project"/' src/api-service/docker-shell.sh src/vector-db/docker-shell.sh          (extra)
git diff
…
-export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
+export GCP_PROJECT="your-gcp-project" # CHANGE TO YOUR PROJECT ID
…
$ ls ../secrets ../persistent-folder          (extra)
../persistent-folder:

../secrets:
ml-workflow.json
```

**B1 · Vector DB: build and run** (`README.md:56-63`). `docker-shell.sh` creates the network if needed, builds the CLI image, and runs `docker compose run --rm cheese-app-vector-db-cli`, which starts Chroma first (`src/vector-db/docker-shell.sh:11-17`, `src/vector-db/docker-compose.yml:17-23`). *Captured* (`b06`):
```
$ ./docker-shell.sh
0c884cafa0c1b905ca7335b6f99f0dcd3bce91d35ac8f7b8d098e94bbac0116c
[+] Building 29.2s (11/11) FINISHED
…
 ✔ Image chromadb/chroma:1.5.9    Pulled
 ✔ Container cheese-app-vector-db Created
Container vector-db-cheese-app-vector-db-cli-run-cf062d897656 Creating
Container vector-db-cheese-app-vector-db-cli-run-cf062d897656 Created
Container is running!!!
Architecture: x86_64
Python version: Python 3.13.18
UV version: uv 0.13.6 (x86_64-unknown-linux-gnu)

The following commands are available:
    python cli.py --download --load --chunk_type recursive-split
        Load the cheese books into Chroma, using the embeddings we made for you
    python cli.py --chunk --embed --load --chunk_type recursive-split
        Do the same from scratch (calls the embedding model many times)
    python cli.py --chat --chunk_type recursive-split
        Ask one question through retrieval and Gemini
```
The long hex line is the new network's ID.

**B2 · Load the database** (`README.md:65-71`). *Captured* (`b06`, trimmed):
```
app@920a2e5b27c0:/app$ python cli.py --download --load --chunk_type recursive-split
CLI Arguments: Namespace(chunk=False, embed=False, load=True, query=False, chat=False, get=False, agent=False, download=True, chunk_type='recursive-split')
download()
load()
Creating collection: recursive-split-collection
Collection 'recursive-split-collection' did not exist. Creating new.
Created new empty collection 'recursive-split-collection'
Collection: Collection(name=recursive-split-collection)
Number of files to process: 11
Processing file: outputs/embeddings-recursive-split-The book of The Cheese Being traits and stories of Ye Olde Cheshire Cheese.jsonl
Shape: (923, 3)
…
Finished inserting 923 items into collection 'recursive-split-collection'
…
Processing file: outputs/embeddings-recursive-split-Tolminc Cheese.jsonl
Shape: (163, 3)
…
Finished inserting 163 items into collection 'recursive-split-collection'
```
The eleven books add up to 923 + 714 + 3,569 + 926 + 2,623 + 1,198 + 1,146 + 678 + 2,147 + 269 + 163 = **14,356** chunks. Each row is (chunk text, metadata, a 256-number embedding made earlier with `text-embedding-004`), so no Vertex call happens here.

**B3 · Try a question** (`README.md:73-76`). Needs Gemini. *Captured* with the unusable key (`b06`, traceback trimmed):
```
app@920a2e5b27c0:/app$ python cli.py --chat --chunk_type recursive-split
…
chat()
Traceback (most recent call last):
  …
  File "/app/cli.py", line 378, in chat
    query_embedding = generate_query_embedding(query)
  File "/app/cli.py", line 84, in generate_query_embedding
    response = llm_client.models.embed_content(
  …
google.auth.exceptions.RefreshError: ('invalid_grant: Invalid grant: account not found', {'error': 'invalid_grant', 'error_description': 'Invalid grant: account not found'})
```
The first Google call is the query's embedding; the key is checked when the library asks Google for a token. With your key, the answer is printed here instead (billed: one embedding, one Gemini call).

**B4 · Leave, Chroma stays** (`README.md:78-79`). *Captured* after `exit` (`b07`, `b08`, `b10`, extras):
```
$ docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
NAMES                  IMAGE                   STATUS          PORTS
cheese-app-vector-db   chromadb/chroma:1.5.9   Up 22 seconds   0.0.0.0:8000->8000/tcp
$ curl -s http://localhost:8000/api/v2/heartbeat; echo; curl -s http://localhost:8000/api/v2/version; echo
{"nanosecond heartbeat":1793886432272948513}
"1.0.0"
$ docker network inspect cheese-app-network --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}'
cheese-app-vector-db 172.19.0.2/16
```

**B5 · Start the API** (`README.md:84-98`). In a new terminal. `docker-shell.sh` shells into the container if one with that name already runs; otherwise it builds `Dockerfile.dev` and runs it with `/secrets` read-only, `/persistent`, `-p 9000:9000` and `--network cheese-app-network` (`src/api-service/docker-shell.sh:14-34`). *Captured* (`b21`):
```
$ ./docker-shell.sh
Building cheese-app-api-service (Dockerfile.dev)...
[+] Building 136.2s (10/10) FINISHED
…
 => [5/5] RUN uv sync --frozen                                               21.1s
 => exporting to image                                                      109.9s
…
Container is running!!!
Architecture: x86_64
Python version: Python 3.13.18
UV version: uv 0.13.6 (x86_64-unknown-linux-gnu)
Checked 84 packages in 4ms

The following commands are available:
    api_server
        Run the API server: http://localhost:9000/api/docs
    pytest
        Run the tests

app@2c5c0b0e4f8c:/app$ api_server
INFO:     Will watch for changes in these directories: ['/app/api']
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
INFO:     Started reloader process [16] using StatReload
INFO:     Started server process [18]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
I0000 00:00:1793886575.694067      23 port.cc:153] oneDNN custom operations are on. …
```
`api_server` is a shell function the entrypoint defines: `uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload --reload-dir api/ "$@"` (`src/api-service/docker-entrypoint.dev.sh:12-16`). "Application startup complete" comes at once; the TensorFlow lines after it are the model loading in the background thread.

**B6 · Check that it is up** (`README.md:100-103`). *Captured* (`b22`–`b25`):
```
$ curl -s -i http://localhost:9000/healthz
HTTP/1.1 200 OK
date: Thu, 05 Nov 2026 13:49:35 GMT
…
{"ok":true}
$ curl -s -i http://localhost:9000/readyz
HTTP/1.1 503 Service Unavailable
date: Thu, 05 Nov 2026 13:49:35 GMT
…
{"detail":"CNN model is loading"}
$ curl -s -i http://localhost:9000/readyz
HTTP/1.1 200 OK
date: Thu, 05 Nov 2026 13:49:44 GMT
…
{"ok":true}
$ curl -s -w '\n[HTTP %{http_code}]\n' http://localhost:9000/; curl -s -w '\n[HTTP %{http_code}]\n' http://localhost:9000/docs          (extra)
{"detail":"Not Found"}
[HTTP 404]
{"detail":"Not Found"}
[HTTP 404]
```
About nine seconds from 503 to 200 here, while the model downloaded (a 9 MB zip from GitHub) and loaded. It is saved under `persistent-folder/experiments/` (`b26`), so later starts skip the download. The old URLs are gone: `main` has no `/` route, and its docs live at `/api/docs`.

**B7 · Create a demo route** (`README.md:105-115`). *Captured* diff (`b27`) and results (`b28`, `b29`):
```
@@ -33,6 +33,12 @@ def get_status():
     return {"version": "2.0.0"}
 
 
+@app.get("/api/square_root")
+def square_root(x: float = 1, y: float = 2):
+    z = x**2 + y**2
+    return z**0.5
+
+
 app.include_router(newsletter.router, prefix="/api/newsletters")

$ curl -s http://localhost:9000/api/square_root; echo
2.23606797749979
$ curl -s 'http://localhost:9000/api/square_root?x=3&y=4'; echo
5.0
```
The server reloads by itself (`StatReload detected changes in 'api/service.py'`), and the CNN reloads with it; `/readyz` was `200` again a few seconds later (`b30`).

**B8 · View API docs** (`README.md:117-120`). *Captured* (`b31`, `b32`, `b33` trimmed):
```
$ curl -s -w '\n[HTTP %{http_code}]\n' http://localhost:9000/api/docs | grep -E '<title>|openapi.json|HTTP'
    <title>Cheese App API - Swagger UI</title>
        url: '/api/openapi.json',
[HTTP 200]
$ curl -s http://localhost:9000/api/openapi.json | python3 -c '…'          (extra: every operation)
{'title': 'Cheese App API', 'version': '0.1.0'}
GET    /api/status
GET    /api/square_root
GET    /api/newsletters
GET    /api/newsletters/{newsletter_id}
GET    /api/newsletters/image/{image_name}
GET    /api/podcasts
GET    /api/podcasts/{podcast_id}
GET    /api/podcasts/audio/{audio_name}
GET    /api/llm/chats
POST   /api/llm/chats
GET    /api/llm/chats/{chat_id}
POST   /api/llm/chats/{chat_id}
GET    /api/llm/images/{chat_id}/{message_id}.png
…      (the same five for /api/llm-cnn and /api/llm-rag)
GET    /healthz
GET    /readyz
$ curl -X 'GET' 'http://localhost:9000/api/newsletters?limit=2' -H 'accept: application/json' | python3 -m json.tool | cut -c1-160
…
[
    {
        "id": "9f2b7e84-2176-4029-bcfd-f99f2d7611e8",
        "dts": 1730476705,
        "title": "Spanish Cheese Journey",
        …
    },
    {
        "id": "78ff70af-c678-486c-876f-9a588a567385",
        "dts": 1729871905,
        "title": "The Art of Blue Cheese",
        …
    }
]
```
Newest first, two because of `limit=2`. *(extra, `b34`, `b35`)* An unknown ID is `404 {"detail":"Newsletter not found"}`; `/api/podcasts` lists one podcast ("Spanish Cheese", `00:05:36`), and its MP3 comes back as `200 audio/mpeg 658930 bytes`.

**B9 · Chats by hand** *(extra)*. The README's chat modes, with curl and a placeholder session ID. *Captured* (`b36`–`b38`):
```
$ curl -s -w '\n[HTTP %{http_code}]\n' -X POST http://localhost:9000/api/llm/chats -H 'Content-Type: application/json' -d '{"content": "How is cheese made?"}'
{"detail":[{"type":"missing","loc":["header","X-Session-ID"],"msg":"Field required","input":null}]}
[HTTP 422]
$ curl … -H 'X-Session-ID: 00000000-0000-4000-8000-000000000001' -d '{}'
{"detail":"Message must contain text or an image"}
[HTTP 422]
$ curl … -H 'X-Session-ID: 00000000-0000-4000-8000-000000000001' -d '{"content": "How is cheese made?"}'
Internal Server Error
[HTTP 500]
```
The 500's reason is only in the API's terminal (`b21`): `ERROR:    Exception in ASGI application`, a traceback through `api/routers/chat.py`, line 67 (`start_chat`), line 40 (`add_turn`), `api/utils/llm_utils.py`, line 84 (`ask_gemini`), ending in `google.auth.exceptions.RefreshError: ('invalid_grant: Invalid grant: account not found', …)`. `ask_gemini` turns Gemini's own API errors into `502 "Gemini: …"` (`llm_utils.py:85-86`), but a rejected key fails earlier, while fetching a token, so it surfaces as a plain 500. With your key this request returns the new chat with Gemini's answer. *Expected* shape (`cheese-app-v2/docs/contract.md:38-42`):
```
- **A chat** is `{chat_id, title, dts, messages}`.
- **A message in a chat** is one of:
  - `{message_id, role: "user", content, image_path?}`
  - `{message_id, role: "assistant", content}`
  - `{message_id, role: "cnn", results: {prediction_label, accuracy}}`
```
**Identify** needs no Google for the photo itself. The capture sent the repo's own `news-letters/assets/blue-cheese.jpg` as base64 to `/api/llm-cnn/chats`: `200`, and the saved chat (`b41`, *captured*, trimmed):
```
$ curl -s http://localhost:9000/api/llm-cnn/chats -H 'X-Session-ID: 00000000-0000-4000-8000-000000000001' | python3 -m json.tool; …
[
    {
        "chat_id": "671bbeed-0fe3-4e38-ab98-21a8a46dadd0",
        "title": "Image chat",
        …
        "messages": [
            {
                "content": null,
                …
                "role": "user",
                "image_path": "images/671bbeed-…/61a0ecab-….png"
            },
            {
                …
                "role": "cnn",
                "results": {
                    "prediction_label": "parmigiano",
                    "accuracy": 58.22
                }
            }
        ]
    }
]
[]
```
A blue cheese, called parmigiano with 58 % confidence: the classifier knows four cheeses (its last layer has 4 outputs, `c11`), and a confident-looking label is not a correct one. The `[]` is the same request with another session ID: chats are per session. **Cheese books** (`/api/llm-rag/chats`, "How is Tolminc cheese made?") fails like Ask, at the query embedding (`b40`; `llm_rag_utils.py:47` in the log). The files on disk (`b42`, *captured*):
```
persistent-folder/chat-history/llm-cnn/images/671bbeed-…/61a0ecab-….png
persistent-folder/chat-history/llm-cnn/00000000-0000-4000-8000-000000000001/671bbeed-….json
```
Nothing was saved for the failed Ask: the file is written only after the reply (`chat.py:40-42`).

**B10 · No CORS on `main`** *(extra)*. *Captured* (`b43`):
```
$ curl -s -i -H 'Origin: http://localhost:8080' 'http://localhost:9000/api/newsletters?limit=1' | grep -i -E 'HTTP/|access-control|content-type'; curl -s -i -X OPTIONS -H 'Origin: http://localhost:8080' -H 'Access-Control-Request-Method: POST' http://localhost:9000/api/llm/chats | grep -i -E 'HTTP/|access-control|allow'
HTTP/1.1 200 OK
content-type: application/json
HTTP/1.1 405 Method Not Allowed
allow: GET
```
The answer arrives, but without permission a browser would hide it from a page on 8080. `main`'s pages never need it (§3.8).

**B11 · Review the code, run the tests** (`README.md:122-145`). §5 tours the files. In a second terminal, *captured* (`b44`):
```
$ ./docker-shell.sh
Container 'cheese-app-api-service' is already running. Shelling into it...
app@2c5c0b0e4f8c:/app$ pytest
======================================= test session starts ========================================
platform linux -- Python 3.13.18, pytest-9.2.0, pluggy-1.7.0
cachedir: /home/app/.cache/cheese-app-api/pytest
rootdir: /app
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1
collected 26 items

tests/test_chat.py .................                                                         [ 65%]
tests/test_service.py .........                                                              [100%]

======================================== 26 passed in 0.51s ========================================
```
The tests replace Gemini, Chroma and the CNN with fakes, so they pass without a key. Keep the API running for the frontend (`README.md:145`); `docker ps` now shows the API on 9000 and Chroma on 8000 (`b45`).

**B12 · React Frontend: start it** (`README.md:149-164`). In a new terminal, from `cheese-app-v2/`. The dev image holds Node only; your folder is mounted at `/app`, `node_modules` lives in a named volume, and the container port 5173 is published as 3000 on `cheese-app-network` (`src/frontend-react/docker-shell.sh:18-23`). *Captured* (`d02`):
```
$ ./docker-shell.sh
Building cheese-app-frontend-react (Dockerfile.dev)...
[+] Building 0.4s (7/7) FINISHED
…
Container is running!!!
Architecture: x86_64
Node version: v24.22.1
npm version: 11.19.1
Installing dependencies...

up to date in 571ms

The following commands are available:
    npm run dev
        Run the dev server: http://localhost:3000 (/api goes to the API container)
    npm run check
        Lint, format check and production build

node@cc61a7e26c8f:/app$ npm run dev

> cheese-app-frontend@2.0.0 dev
> vite

  VITE v8.3.5  ready in 297 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://172.19.0.4:5173/  eth0
```
"up to date" because the volume already held the packages in this run; your first run installs them all (257 packages, as the production build's `npm ci` reports in `d20`). Both Vite addresses are inside the container: open **http://localhost:3000**.

**B13 · Open the app** (`README.md:164-174`). No browser ran in the capture; the same requests by curl. *Captured* (`d03`, `d04`, `d08`):
```
$ curl -s -i http://localhost:3000/ | grep -v '^\s*$'
HTTP/1.1 200 OK
…
    <script type="module" src="/@vite/client"></script>
    …
    <title>Formaggio</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
$ curl -s -i 'http://localhost:3000/api/newsletters?limit=2' | sed -n '1,8p'          (extra)
HTTP/1.1 200 OK
Vary: Origin
date: Thu, 05 Nov 2026 13:50:03 GMT
server: uvicorn
content-length: 4969
content-type: application/json
$ for u in / /podcasts /newsletters /chat?model=llm /nope; do …; done          (extra)
/                    200 text/html
/podcasts            200 text/html
/newsletters         200 text/html
/chat?model=llm      200 text/html
/nope                200 text/html
```
A request to port **3000** answered by **uvicorn**: that is Vite's proxy at work. In the browser, Home, Podcasts and Newsletters load through it; in Chat, Identify works offline (`d07`: `200`, a `cnn` reply), while Ask and Cheese books need your key (`d06`: `500`, the same `RefreshError` in the API's log). What the README asks you to look for, *expected* (`README.md:166-174`): Home with a question box and a camera button; Podcasts and Newsletters loading through the API; Chat with Ask, Identify and Cheese books; your chats under **Recent**, still there after a reload.

*(extra, `d09`)* With the API unplugged from the network for one request, the browser's call gets `502` with an empty body, and Vite's terminal says why:
```
[vite] http proxy error: /api/newsletters?limit=2
Error: getaddrinfo ENOTFOUND cheese-app-api-service
```
The page then shows "The API answered 502." (`src/frontend-react/src/lib/api.js:49-52`).

**B14 · Review the code, check it** (`README.md:176-190`). In a second terminal, *captured* (`d12`, trimmed):
```
$ ./docker-shell.sh
Container 'cheese-app-frontend-react' is already running. Shelling into it...
node@cc61a7e26c8f:/app$ npm run check

> cheese-app-frontend@2.0.0 check
> eslint . && prettier --check . && vite build

Checking formatting...
All matched files use Prettier code style!
vite v8.3.5 building client environment for production...
✓ 2385 modules transformed.
…
dist/index.html                                        0.53 kB │ gzip:   0.32 kB
dist/assets/index-Csse5MvO.css                        15.95 kB │ gzip:   4.37 kB
dist/assets/index-DQWKRz1J.js                        440.48 kB │ gzip: 137.31 kB

✓ built in 470ms
```
ESLint printed nothing (no problems); `dist/` is what the production image serves.

**B15 · Production images** *(extra, `cheese-app-v2@e98fa55/README.md:197-215`)*. After Ctrl-C and `exit` in the Vite terminal, from `src/frontend-react`, with the API still running. *Captured* (`d20` trimmed, `d21`, `d22`–`d25`, `d27`):
```
$ docker build -t cheese-app-frontend-react:prod .
…
#10 [build 4/6] RUN npm ci
#10 8.192 added 257 packages, and audited 258 packages in 8s
…
#10 8.199 4 moderate severity vulnerabilities
…
#13 [build 6/6] RUN npm run build
#13 1.473 ✓ built in 800ms
…
#15 naming to docker.io/library/cheese-app-frontend-react:prod done
$ docker run --rm --network cheese-app-network -p 8080:80 cheese-app-frontend-react:prod
…
20-envsubst-on-templates.sh: Running envsubst on /etc/nginx/templates/default.conf.template to /etc/nginx/conf.d/default.conf
…
2026/11/05 13:50:25 [notice] 1#1: nginx/1.31.8
…
172.19.0.1 - - [05/Nov/2026:13:50:27 +0000] "GET /api/newsletters?limit=1 HTTP/1.1" 200 2677 "-" "curl/8.23.0" "-"
$ curl -s -i http://localhost:8080/ | grep -E 'HTTP/|Server:|Content-Type|<title>|assets/'
HTTP/1.1 200 OK
Server: nginx/1.31.8
Content-Type: text/html
    <title>Formaggio</title>
    <script type="module" crossorigin src="/assets/index-DQWKRz1J.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-Csse5MvO.css">
$ curl -s -i http://localhost:8080/healthz | grep -v '^\s*$'
HTTP/1.1 200 OK
Server: nginx/1.31.8
…
ok
$ for u in /newsletters /chat?model=llm-rag /assets/; do …; done
/newsletters           200 text/html
/chat?model=llm-rag    200 text/html
/assets/               404 text/html
$ docker images | grep cheese-app-frontend-react
cheese-app-frontend-react:latest   4f3424bfabb6        331MB         81.2MB
cheese-app-frontend-react:prod     189c48dc039a       94.8MB         26.7MB
```
No Vite and no Node in the running image: nginx serves the built files, answers its own `/healthz`, sends every page URL to `index.html`, and passes `/api/` on to the API (`d23`: newsletters through 8080, `Server: nginx/1.31.8`). With the API stopped, the same `docker run` refuses to start (`e01`, *captured*):
```
nginx: [emerg] host not found in upstream "cheese-app-api-service" in /etc/nginx/conf.d/default.conf:14
[exit 1]
```

**B16 · Setup & Run Cheese App** (`README.md:192-221`). *Captured* (`f01` as a stat, `f02`, `f04-docker-compose-up` trimmed):
```
$ sed -i 's/ac215-project/your-gcp-project/' src/docker-compose.yml          (extra)
…
-            GCP_PROJECT: ac215-project # CHANGE TO YOUR PROJECT ID
+            GCP_PROJECT: your-gcp-project # CHANGE TO YOUR PROJECT ID
…      (twice: vector-db-loader and api-service)
$ docker compose down          (in src/vector-db)
time="…" level=warning msg="The \"GOOGLE_APPLICATION_CREDENTIALS\" variable is not set. Defaulting to a blank string."
time="…" level=warning msg="The \"GCP_PROJECT\" variable is not set. Defaulting to a blank string."
 Container cheese-app-vector-db Stopping
 …
 Container cheese-app-vector-db Removed
$ cd src
$ docker compose up --build
[+] Building 0.5s (30/30) FINISHED
…
WARN[0000] a network with name cheese-app-network exists but was not created by compose.
Set `external: true` to use an existing network
WARN[0000] volume "cheese-app-frontend-react-node_modules" already exists but was not created by Docker Compose. Use `external: true` to use an existing volume
…
 ✔ Container cheese-app-vector-db      Created
 ✔ Container src-vector-db-loader-1    Created
 ✔ Container cheese-app-api-service    Created
 ✔ Container cheese-app-frontend-react Created
…
cheese-app-vector-db  | Saving data to: /data
cheese-app-api-service  | INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
cheese-app-frontend-react  | up to date in 842ms
cheese-app-frontend-react  |   VITE v8.3.5  ready in 660 ms
…
vector-db-loader-1 exited with code 0
…
cheese-app-api-service     | INFO:     172.19.0.1:49160 - "GET /readyz HTTP/1.1" 200 OK
```
The `compose down` warnings mean the variables come from `docker-shell.sh`, not from your shell; they are harmless here. The two `WARN` lines say the network and volume were made by the scripts earlier: warnings, not errors. The build took 0.5 s because every image already existed; on a fresh laptop this is the full build. Then, in a second terminal (`f04-curl-3000`, `f04-curl-api-docs`, `f04-x-readme-url`, `f04-x-compose-ps`):
```
$ curl -s -i http://localhost:3000/ | grep -E 'HTTP/|<title>'
HTTP/1.1 200 OK
    <title>Formaggio</title>
$ curl -s -w '\n[HTTP %{http_code}]\n' http://localhost:9000/api/docs | grep -E '<title>|HTTP'
    <title>Cheese App API - Swagger UI</title>
[HTTP 200]
$ curl -sS -w '\n[HTTP %{http_code}]\n' --max-time 5 http://localhost:900/api/docs          (extra: the README's URL as printed)
curl: (7) Failed to connect to localhost:900 after 0 ms: Could not connect to server
$ docker compose ps -a --format 'table {{.Name}}\t{{.Service}}\t{{.Status}}\t{{.Ports}}'          (extra)
NAME                        SERVICE            STATUS                     PORTS
cheese-app-api-service      api-service        Up 9 seconds               0.0.0.0:9000->9000/tcp
cheese-app-frontend-react   frontend-react     Up 9 seconds               0.0.0.0:3000->5173/tcp
cheese-app-vector-db        vector-db          Up 9 seconds               0.0.0.0:8000->8000/tcp
src-vector-db-loader-1      vector-db-loader   Exited (0) 3 seconds ago
```
The loader found the books already in Chroma (they are in `src/vector-db/docker-volumes/chromadb`, mounted again here) and exited without loading; its log is empty because its check sends output to `/dev/null` (`f04-x-loader-logs`). Ctrl-C prints `Gracefully Stopping... press Ctrl+C again to force`; then `docker compose down` removes all four containers and leaves the volume and the network (`f10`, `f11`).

**B17 · Docker Cleanup** (`README.md:235-246`). *Captured* (`e02`, `e03` trimmed, `e04` trimmed):
```
$ docker compose down          (in src/vector-db)
…
time="…" level=warning msg="Warning: No resource found to remove for project \"vector-db\"."
$ docker system prune
WARNING! This will remove:
…
Are you sure you want to continue? [y/N] y
Deleted Networks:
cheese-app-network

Deleted build cache objects:
…
Total reclaimed space: 4.583GB
$ docker ps -a; docker images; docker volume ls; docker network ls          (extra)
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
IMAGE                              ID             DISK USAGE   CONTENT SIZE
cheese-app-api-service:latest      6250368fcf24        4.2GB          790MB
cheese-app-frontend-react:latest   d959127001ec        331MB         81.2MB
cheese-app-frontend-react:prod     189c48dc039a       94.8MB         26.7MB
cheese-app-vector-db-cli:latest    fcc3ae6283d6        813MB          180MB
chromadb/chroma:1.5.9              1e0b73a187a2        826MB          176MB
…
DRIVER    VOLUME NAME
local     cheese-app-frontend-react-node_modules
```
More than 6 GB of cheese-app images, the base images and the `node_modules` volume are still on your disk. Remove them by name (§2, step 4).

### Part C: branch `2025` (`14f2a14`): the lecture's simple frontend

The course repository changed on the morning of 2026-11-05: `main` no longer has Tutorial 24, and the lecture's simple frontend now lives on branch `2025`. Its pages call last year's routes without `/api`, and need last year's CORS, so they run with last year's vector DB and API.

**C0 · Switch branches** *(extra)*. *Captured* (`c01`, `c01b` with the merge subject trimmed, `c02`, `c03`, `c04`):
```
$ git switch 2025
error: Your local changes to the following files would be overwritten by checkout:
	src/api-service/api/service.py
	src/api-service/docker-shell.sh
	src/docker-compose.yml
	src/vector-db/docker-shell.sh
Please commit your changes or stash them before you switch branches.
Aborting
$ git stash && git switch 2025
Saved working directory and index state WIP on main: 447b5c3 …
branch '2025' set up to track 'origin/2025'.
Switched to a new branch '2025'
$ git log -1 --format='%H %ci %s'; ls src
14f2a1420b43e9f24e977a9e67b53d7e2614013d 2025-11-16 09:16:15 -0500 image chat fix
api-service
frontend-react
frontend-simple
vector-db
$ cp ../secrets/ml-workflow.json ../secrets/llm-service-account.json; ls ../secrets
llm-service-account.json
ml-workflow.json
$ sed -i 's/"ac215-project"/"your-gcp-project"/' src/api-service/docker-shell.sh src/vector-db/docker-shell.sh; git diff --stat
 src/api-service/docker-shell.sh | 2 +-
 src/vector-db/docker-shell.sh   | 2 +-
 2 files changed, 2 insertions(+), 2 deletions(-)
```
The 2025 vector-DB script reads `/secrets/llm-service-account.json` (`cheese-app-v2@2025/src/vector-db/docker-shell.sh:10`); its API reads `ml-workflow.json` (`cheese-app-v2@2025/src/api-service/docker-shell.sh:29`).

**C1 · Tutorial (23) Vector DB, 2025** (`cheese-app-v2@2025/README.md:43-65`). From the folder that holds the clones. *Captured* (`c06` trimmed, `c07`):
```
$ cd cheese-app-v2/src/vector-db
$ sh docker-shell.sh
…
 ✔ Image chromadb/chroma:latest   Pulled
 ✔ Container cheese-app-vector-db Created
…
Container is running!!!
Architecture: x86_64
Environment ready! Virtual environment activated.
Python version: Python 3.12.16
UV version: uv 0.13.7 (x86_64-unknown-linux-gnu)
Activating virtual environment...
app@6373b40a6f62:/app$ python cli.py --download --load --chunk_type recursive-split
…
Number of files to process: 11
…
Finished inserting 163 items into collection 'recursive-split-collection'
$ docker ps -a …; docker image inspect chromadb/chroma:latest --format '{{.Id}} {{.Created}}'          (extra, after exit)
NAMES                  IMAGE                    STATUS          PORTS
cheese-app-vector-db   chromadb/chroma:latest   Up 32 seconds   0.0.0.0:8000->8000/tcp
sha256:a221f339… 2026-05-05T01:49:4…
```
The same eleven books and 14,356 chunks. `chromadb/chroma:latest` is whatever Docker Hub serves that day (here an image from 2026-05-05); the 2025 client worked with it.

**C2 · Tutorial (23) Backend APIs, 2025** (`cheese-app-v2@2025/README.md:70-113`). In a new terminal, from the folder that holds the clones. *Captured* (`c11` trimmed):
```
$ cd cheese-app-v2/src/api-service
$ sh docker-shell.sh
…
The following commands are available:
    uvicorn_server
        Run the Uvicorn Server

app@c9f05403249e:/app$ uvicorn_server
INFO:     Will watch for changes in these directories: ['/app/api']
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
INFO:     Started reloader process [11] using WatchFiles
…
Loading CNN Model...
…
 Total params: 2,422,470 (9.24 MB)
…
INFO:     Started server process [13]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```
Last year's API loads the CNN **before** start-up completes, so it answers nothing until the model is in memory; TensorFlow 2.19 also prints CUDA warnings on a machine without a GPU (harmless). Then (*captured*, `c12`, `c13`, `c14` trimmed):
```
$ curl -s -i http://localhost:9000/
HTTP/1.1 200 OK
…
{"message":"Welcome to AC215"}
$ grep -n -A3 'square_root' api/service.py; curl -s 'http://localhost:9000/square_root/?x=2&y=10'; echo          (extra)
30:@app.get("/square_root/")
31:async def square_root(x: float = 1, y: float = 2):
32-    z = x**2 + y**2
33-    return z**0.5
…
10.198039027185569
$ sed -n '35,42p' api/service.py; curl -s http://localhost:9000/openapi.json | python3 -c '…'          (extra)

# Additional routers here
app.include_router(newsletter.router, prefix="/newsletters")
app.include_router(podcast.router, prefix="/podcasts")
app.include_router(llm_chat.router, prefix="/llm")
app.include_router(llm_cnn_chat.router, prefix="/llm-cnn")
# app.include_router(llm_rag_chat.router, prefix="/llm-rag")
# app.include_router(llm_agent_chat.router, prefix="/llm-agent")
GET    /
GET    /square_root/
GET    /newsletters/
…
POST   /llm/chats
…
GET    /llm-cnn/images/{chat_id}/{message_id}.png
```
The README's demo route and "Enable Cheese App API Routes" describe an older `service.py`: the route is already there and four routers are already on. Pasting the route again would duplicate it (§9). Note the paths: no `/api`, and the routers' roots end in `/`.

**C3 · Tutorial (24) Simple Frontend App** (`cheese-app-v2@2025/README.md:147-183`). In a new terminal, from the folder that holds the clones: `cd cheese-app-v2/src/frontend-simple`, `sh docker-shell.sh`, `http-server` (the same `http-server version: 14.1.1` banner as v1, `c21`). *Captured* (`c22`, `c23`, `c24`):
```
$ curl -s -i http://localhost:8080/index.html | grep -E 'HTTP/|<title>|href="/?(newsletters|chat)'
HTTP/1.1 200 OK
    <title>Formaggio.me</title>
                <a href="/newsletters.html" class="nav-link">Newsletters</a>
                <a href="/chat.html" class="nav-link">Cheese Assistant</a>
$ curl -s -i http://localhost:8080/newsletters.html | grep -E 'HTTP/|<title>|script'
HTTP/1.1 200 OK
    <title>🧀 Formaggio.me</title>
…
    <script src="https://cdnjs.cloudflare.com/ajax/libs/axios/1.6.2/axios.min.js"></script>
    <script src="newsletters-main.js"></script>
$ grep -n 'localhost:9000\|axios' newsletters-main.js chat-main.js | head          (extra)
newsletters-main.js:3:    baseURL: 'http://localhost:9000',
newsletters-main.js:7:            const response = await axios.get(`${this.baseURL}/newsletters?limit=${limit}`);
chat-main.js:2:const BASE_API_URL = 'http://localhost:9000';
…
```
Two round trips, as on the lecture's slides (Frontend 18–27): files from 8080, data from 9000, called by your browser. What the newsletters page's request looks like to the API, with the browser's `Origin` header (*captured*, `c25`):
```
$ curl -s -i -L -H 'Origin: http://localhost:8080' 'http://localhost:9000/newsletters?limit=100' | grep -i -E 'HTTP/|location|access-control|content-type|"title"' | cut -c1-120
HTTP/1.1 307 Temporary Redirect
location: http://localhost:9000/newsletters/?limit=100
access-control-allow-origin: *
HTTP/1.1 200 OK
content-type: application/json
access-control-allow-origin: *
[{"id":"9f2b7e84-2176-4029-bcfd-f99f2d7611e8","dts":1730476705,"title":"Spanish Cheese Journey",…
```
One extra round trip for the missing slash, and the CORS header on both answers. The chat page (`chat.html`, which loads axios, marked and `chat-main.js`, `c26`) posts JSON with `X-Session-ID`, so the browser first sends the preflight (*captured*, `c27`, `c28` trimmed):
```
$ curl -s -i -X OPTIONS -H 'Origin: http://localhost:8080' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type,x-session-id' http://localhost:9000/llm/chats | grep -i -E 'HTTP/|access-control'
HTTP/1.1 200 OK
access-control-allow-origin: *
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-max-age: 600
access-control-allow-headers: content-type,x-session-id
$ curl -s -i -L -X POST -H 'Origin: http://localhost:8080' -H 'Content-Type: application/json' -H 'X-Session-ID: 00000000-0000-4000-8000-000000000001' -d '{"content": "How is cheese made?"}' http://localhost:9000/llm/chats/ | …
HTTP/1.1 307 Temporary Redirect
…
location: http://localhost:9000/llm/chats
access-control-allow-origin: *
HTTP/1.1 500 Internal Server Error
…
access-control-allow-origin: *
{"detail":"Failed to generate response: ('invalid_grant: Invalid grant: account not found', {'error': 'invalid_grant', 'error_description': 'Invalid grant: account not found'})"}
```
This time the slash is extra (`chat-main.js:31` posts to `…/chats/`; the route is `/chats`). The 500 is an `HTTPException` raised by the route, so it carries the CORS header and a browser would show the real reason. The API's log tells the same story in order (`c11`): `GET /newsletters?limit=100` 307, `GET /newsletters/?limit=100` 200, `OPTIONS /llm/chats` 200, `POST /llm/chats/` 307, `Error generating response: ('invalid_grant: …')`, `POST /llm/chats` 500. With a valid key, this chat would still fail today: the 2025 code asks for `gemini-2.0-flash-001` (`cheese-app-v2@2025/src/api-service/api/utils/llm_utils.py:22`), which Google has retired (§6 item 13).

**C4 · Back to `main`** *(extra)*. Ctrl-C and `exit` in the three terminals; *captured* (`c29`, `c30`, `c31` with the merge subject trimmed):
```
$ docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
NAMES                        IMAGE                        PORTS
cheese-app-frontend-simple   cheese-app-frontend-simple   0.0.0.0:8080->8080/tcp
cheese-app-api-service       cheese-app-api-service       0.0.0.0:9000->9000/tcp
cheese-app-vector-db         chromadb/chroma:latest       0.0.0.0:8000->8000/tcp
$ docker stop cheese-app-vector-db; docker ps -a
cheese-app-vector-db
…   chromadb/chroma:latest   …   Exited (0) Less than a second ago   …   cheese-app-vector-db
$ git checkout -- . && git switch main && git log -1 --format='%h %s'
Switched to branch 'main'
Your branch is up to date with 'origin/main'.
447b5c3 Merge pull request #2 …
```
(The first listing was taken while the three servers ran.) `git checkout -- .` throws away the 2025 project-ID edits; `git stash pop` then brings back your `main` edits (not captured). The 2025 images reuse the names `cheese-app-api-service`, `cheese-app-vector-db-cli` and `cheese-app-frontend-simple`; remove them with `docker image rm` when you are done.

## 5. Code tour

All on `main` (`447b5c3`) unless marked.

**`cheese-app-v2/src/api-service/api/service.py:19-56`** — the app, its routers, the probes.
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # In the background, so the API answers while the model loads; /readyz says when it is done
    threading.Thread(target=llm_cnn_utils.load_cnn_model, daemon=True).start()
    yield


app = FastAPI(
    title="Cheese App API", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
)
…
app.include_router(newsletter.router, prefix="/api/newsletters")
app.include_router(podcast.router, prefix="/api/podcasts")
app.include_router(chat.create_router("llm", llm_utils.respond), prefix="/api/llm")
app.include_router(chat.create_router("llm-cnn", llm_cnn_utils.respond), prefix="/api/llm-cnn")
app.include_router(chat.create_router("llm-rag", llm_rag_utils.respond), prefix="/api/llm-rag")
…
@app.get("/readyz")
def readyz():
    if llm_cnn_utils.cnn_model is None:
        raise HTTPException(503, "CNN model is loading")
    try:
        llm_rag_utils.chroma_client().heartbeat()
    except Exception as e:  # noqa: BLE001 - whatever went wrong, this pod is not ready
        raise HTTPException(503, f"Chroma: {e}")
    return {"ok": True}
```
Everything the browser calls is under `/api`; the probes stay at the root. No CORS middleware.

**`api/settings.py:5-23`** — every setting, read once from the environment. `GCP_PROJECT` is required (line 5); `GCP_LOCATION` defaults to `global` (line 7: "Current Gemini models answer on the global endpoint only"); `GENERATIVE_MODEL` defaults to `gemini-3.8-flash` (line 10: "When Google retires a model, this is the only line to change"); `EMBEDDING_MODEL` `text-embedding-004` at 256 dimensions (lines 11-12); Chroma's host and port (14-15); the CNN's GitHub URL (21-23).

**`api/routers/chat.py:31-76`** — one router factory for all three modes.
```python
def create_router(model: str, respond: Callable[[ChatHistoryManager, list[dict], dict], dict]) -> APIRouter:
    router = APIRouter()
    chat_manager = ChatHistoryManager(model=model)

    def add_turn(chat: dict, message: ChatMessage, session_id: str) -> dict:
        if not message.content and not message.image:
            raise HTTPException(status_code=422, detail="Message must contain text or an image")

        user_message = {**message.model_dump(), "message_id": str(uuid.uuid4()), "role": "user"}
        reply = respond(chat_manager, chat["messages"], user_message)
        chat["messages"] += [user_message, {"message_id": str(uuid.uuid4()), **reply}]
        chat_manager.save_chat(chat, session_id)
        return chat
…
    @router.post("/chats")
    def start_chat(message: ChatMessage, x_session_id: SessionId):
…
    @router.post("/chats/{chat_id}")
    def continue_chat(chat_id: ChatId, message: ChatMessage, x_session_id: SessionId):
```
Plain `def`, not `async def`: Gemini, Chroma and TensorFlow block, and FastAPI runs a `def` route in a worker thread (`chat.py:5-6`; exercise B4 measures it). `SessionId` (line 21) is the `X-Session-ID` header, validated against a UUID pattern.

**`api/utils/llm_cnn_utils.py:26-69`** — the classifier. `load_cnn_model` downloads `experiment_1760994796.zip` once into `/persistent/experiments`, then loads the Keras model last ("/readyz waits for this", line 42). `respond` sends text to Gemini and a photo to the CNN, answering `503 "The CNN model is still loading"` until it is ready (lines 64-69).

**`api/utils/llm_rag_utils.py:35-76`** — Cheese books. `chroma_client()` connects on first use and is cached only when it succeeds (lines 38-42), so the API starts before Chroma. `find_chunks` embeds the question, asks the collection for the 5 nearest chunks, and maps an empty DB and a missing Chroma to 503 (lines 57-66). `respond` sends the question plus the chunks to Gemini (69-76).

**`api/utils/chat_utils.py:25-77`** — `ChatHistoryManager`: one JSON file per chat under `/persistent/chat-history/<model>/<session>/`, images saved as files and replaced by their path before saving.

**`cheese-app-v2/src/api-service/docker-shell.sh:16-21`** — reuse a running container by name.
```bash
if docker ps --format "{{.Names}}" | grep -qx "${IMAGE_NAME}"; then
    echo "Container '${IMAGE_NAME}' is already running. Shelling into it..."
    docker exec -it "$IMAGE_NAME" /bin/bash
else
    echo "Building ${IMAGE_NAME} (Dockerfile.dev)..."
    docker build -t "$IMAGE_NAME" -f Dockerfile.dev .
```
That is how the second terminal gets a shell for `pytest`. It checks only the name (§6 item 9).

**`cheese-app-v2/src/frontend-react/vite.config.js:5-15`** — the courier in development.
```js
// The browser always calls /api/... on its own origin. In dev, Vite forwards that to the API
// container by name, on cheese-app-network; in production, nginx does (nginx.conf.template).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // listen on all interfaces, so the container's published port reaches it
    port: 5173,
    strictPort: true,
    proxy: { '/api': process.env.API_URL || 'http://cheese-app-api-service:9000' },
  },
})
```
`host: true` is Vite's `--host 0.0.0.0`.

**`src/frontend-react/src/lib/api.js:31-44`** — every call, one way.
```js
async function request(path, body) {
  const options = {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Session-ID': sessionId() },
    signal: AbortSignal.timeout(130_000), // a little longer than the API gives Gemini
  }
  …
    response = await fetch(path, options)
```
Relative paths only (`startChat` posts to `` `/api/${model}/chats` ``, line 61): no address, so no CORS. `src/routes/Home.jsx:39-40` loads two podcasts and two newsletters this way; `src/routes/Chat.jsx:10-24` names the three modes Ask (`llm`), Identify (`llm-cnn`) and Cheese books (`llm-rag`).

**`src/frontend-react/nginx.conf.template:9-33`** — the courier in production.
```nginx
  location = /healthz { access_log off; default_type text/plain; return 200 "ok\n"; }

  # One entrance: the browser only talks to this origin, and nginx passes /api on, full path included.
  …
  location /api/ {
    proxy_pass ${API_URL};
    …
  }
  …
  location /assets/ {
    add_header Cache-Control "public, max-age=31536000, immutable";
    try_files $uri =404;
  }
  …
  location / {
    add_header Cache-Control "no-cache";
    try_files $uri /index.html;
  }
```
`API_URL` is `http://cheese-app-api-service:9000`, set in the production `Dockerfile` (line 13) and substituted when the container starts. nginx resolves that name at start-up, which is why it refuses to start without the API (`e01`). A trailing `/` after `${API_URL}` would strip `/api` from every request (exercise C5).

**`cheese-app-v2/src/docker-compose.yml:19-22`** — the loader that loads once.
```yaml
    vector-db-loader:
        build: ./vector-db
        image: cheese-app-vector-db-cli
        entrypoint: [ "/bin/bash", "-c", "python cli.py --get --chunk_type recursive-split > /dev/null 2>&1 || python cli.py --download --load --chunk_type recursive-split" ]
```

**Branch `2025`: `cheese-app-v2@2025/src/frontend-simple/newsletters-main.js:2-7`** — the page calls the API directly.
```js
const DataService = {
    baseURL: 'http://localhost:9000',

    async GetNewsletters(limit = 100) {
        try {
            const response = await axios.get(`${this.baseURL}/newsletters?limit=${limit}`);
```
And its API's permission slip, **`cheese-app-v2@2025/src/api-service/api/service.py:15-21`**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 6. Gotchas and common errors

`main` unless marked **[v1]** or **[2025]**.

1. **[v1] The README's folder paths lack `src/`** (`cheese-app-v1/README.md:41`, `:75`): `No such file or directory` (`a01`, `a19`). Use `cheese-app-v1/src/api-service` and `…/src/frontend-simple`; the scripts' `../../../secrets` only resolves from there.
2. **Old URLs are 404s.** `http://localhost:9000/` and `/docs` answer `{"detail":"Not Found"}` (`b25`): there is no root route, and the docs moved to `/api/docs` (`api/service.py:27`). Use `/healthz` for "is it up?".
3. **Vite says 5173, the laptop needs 3000.** Both addresses Vite prints are inside the container (`d02`); the script publishes `-p 3000:5173` (`src/frontend-react/docker-shell.sh:21`).
4. **`localhost:900` in the README** (`README.md:213`) is a typo for 9000 (`f04-x-readme-url`).
5. **`/readyz` is 503 for a while, and again after every save.** The model loads in a thread at each start, and `--reload` restarts the worker; meanwhile Identify answers `503 The CNN model is still loading`. Wait for `{"ok":true}` (`b23`, `b24`, `b30`). If it never comes, see item 8.
6. **`/readyz` says `Chroma: …`.** Chroma is not running: `docker compose up -d chromadb` in `src/vector-db` (`README.md:228`). No API restart needed; the client reconnects on the next call (`llm_rag_utils.py:38-42`; exercise C3). **[2025]** Last year's API could not even start without Chroma: it connected at import (`cheese-app-v2@2025/src/api-service/api/utils/llm_rag_utils.py:57`, imported at `service.py:7`). Start the vector DB first.
7. **Every Gemini call fails with a plain `500 Internal Server Error`** when Google rejects the key: the reason is only in the API's terminal, `google.auth.exceptions.RefreshError: ('invalid_grant: …')` (`b21`). The README's rows "Gemini: 403 / PERMISSION_DENIED" (wrong project, API off, missing role) and "Gemini: 404" (retired model) are what you see once the key itself is accepted (`README.md:230-231`). Check the key file name, that it belongs to a live account, and `GCP_PROJECT` in all three places.
8. **Linux: Docker creates missing bind-mount folders as root.** The containers run as uid 1000 (`app`, `node`). A root-owned `persistent-folder` kills the model thread with `PermissionError` (in the log, not in the HTTP answer) and `/readyz` stays at "loading" forever; chat saves fail too (exercise C2). Create `secrets/` and `persistent-folder/` yourself before the first run, or `sudo chown -R 1000:1000 persistent-folder`. Docker Desktop on macOS and Windows hides this.
9. **Same container name, other code; `api_server: command not found`.** v1, `2025` and `main` all name the API container `cheese-app-api-service`, and `main`'s script shells into whatever runs under that name (`docker-shell.sh:16-18`). A leftover v1 or 2025 container gives you a shell in old code. `api_server` exists only in the container's first shell (it is a shell function, `docker-entrypoint.dev.sh:12-16`), not in a `docker exec` shell (exercise C8). `docker ps` first.
10. **The production frontend needs the API first.** `nginx: [emerg] host not found in upstream "cheese-app-api-service"` and exit 1 (`e01`). Start the API on `cheese-app-network`, then nginx. Vite is lazier: it starts, and each `/api` call answers 502 (`d09`).
11. **`docker system prune` keeps what is big.** Tagged images (the API alone 4.2 GB) and the `node_modules` volume survive (`e04`); remove them by name. The prune does delete `cheese-app-network` once nothing uses it; the scripts re-create it.
12. **[2025] `git switch 2025` refuses, and a second key name.** Stash your edits first (`c01`, `c01b`). The 2025 vector DB reads `llm-service-account.json`; copy your key to that name (`c03`).
13. **[2025] Retired Gemini model.** The 2025 code asks for `gemini-2.0-flash-001` at `us-central1` (`cheese-app-v2@2025/src/api-service/api/utils/llm_utils.py:22`), retired on June 1, 2026 according to Google's Vertex AI model lifecycle page (read 2026-11-05, per the digest). So the 2025 chat page cannot answer even with a valid key; `main` uses `gemini-3.8-flash` at `global`.
14. **[2025] `docker-compose: command not found`** on compose-plugin-only installs (`cheese-app-v2@2025/src/vector-db/docker-shell.sh:20`): run `docker compose run --rm --service-ports cheese-app-vector-db-cli` in `src/vector-db` instead (not captured; the capture engine had both).
15. **[2025] One slash, one extra round trip, and "CORS errors" that are crashes.** `/newsletters?limit=…` and `/llm/chats/` each cost a 307 (`c25`, `c28`). An *unhandled* exception's 500 carries no CORS header, so the browser reports a CORS failure; read uvicorn's traceback first (exercise C6).
16. **[v1, 2025] Edits to the simple frontend don't show.** `http-server` sends `cache-control: max-age=3600` for every file (`a21`, `a25`): hard-refresh, or start it with `http-server -c-1`.
17. **`cli.py --chat` always asks "How is cheese made?"** (`cheese-app-v2/src/vector-db/cli.py:377`), whatever you type; edit that line to ask something else.
18. **Don't change the embedding model on one side.** The stored vectors were made with `text-embedding-004` at 256 dimensions; changing `EMBEDDING_MODEL` in the API alone keeps the shapes valid and makes retrieval meaningless. Re-embed both sides with `python cli.py --chunk --embed --load --chunk_type recursive-split` (billed).
19. **Compose and the scripts share names.** `docker compose up` warns that `cheese-app-network` and the `node_modules` volume were "not created by compose" (`f04-docker-compose-up`): harmless. But containers from the step-by-step sections must be stopped first, or Compose finds their names and ports taken (`README.md:198-199`, `README.md:233`).

## 7. Where this sits in the course

- **What you already have.**
  - L02/L04: images, containers, `-p HOST:CONTAINER`, bind mounts, Docker networks.
  - L05: the chunk → embed → Chroma pipeline; `vector-db/cli.py` is a copy of it.
  - L10 (`cheese-app-v0`): a FastAPI + Next.js RAG app with a service-account key.
  - L13: the MobileNetV2 cheese classifier whose trained artifact the API downloads.
  - L15 (`ml-workflow`): the service account and the `ml-workflow.json` key this API reuses.
- **What L18 adds.** Code organisation for a real app (`src/<service>/`, one container per concern); a REST API with routers, request models, probes and tests; chat state kept in files, not memory; a static frontend and a React single-page app; a dev-server proxy and an nginx production image that give the browser one origin; and Docker Compose. Milestone 4 asks for exactly this: APIs built with FastAPI, connected to user-facing frontends, simple and React-based.
- **What comes next.**
  - L19, "Scaling: Kubernetes (local)": the course site said the tutorial was "coming soon" when the sources were checked.
  - L20/L22 use `cheese-app-v3`, which is still last year's layout: Next.js, an NGINX container that routes `/api-service` to the API, and CORS. `main` of v2 already carries what those lectures need: `/api` behind one entrance, `/healthz` and `/readyz` (nginx's `/healthz` comment says "for the kubelet"), stateless chats ("We need that when we scale in `cheese-app-v3`", `README.md:135-136`), and a numeric `USER 1000:1000` in the API's production image "so Kubernetes can check runAsNonRoot" (`src/api-service/Dockerfile:21-22`).

**Version diffs**

*v1 → v2 `2025`*: six routers and their utils, `square_root` pre-added, the CORS middleware kept, a `DEV` switch in the entrypoint, two new simple pages (newsletters, chat), a Next.js 15 React app, and the vector-DB stack.

*v2 `2025` → `main`* (`14f2a14` → `e98fa55`, 131 files; then `447b5c3` adds `src/docker-compose.yml` and rewrites the README):

```text
 README.md                       four-container table, one key, ./docker-shell.sh, api_server,
                                 /healthz /readyz, /api/square_root, pytest, Tutorial 24 removed,
                                 Vite React, Setup & Run (compose), Troubleshooting
 docs/contract.md                new: routes, messages, errors, settings
 api-service/api/service.py      /api prefix, lifespan thread, /healthz /readyz, no CORS, no "/" route
 api-service/api/settings.py     new: env-driven settings (global, gemini-3.8-flash)
 api-service/api/routers/chat.py new: create_router() replaces llm_chat / llm_cnn_chat / llm_rag_chat;
                                 the agent router is gone
 api-service/tests/              new: 26 pytest tests with fakes
 api-service/Dockerfile(.dev)    Python 3.13, uv 0.13.6; dev image and a two-stage production image
 frontend-simple/**              deleted ("removed frontend simple")
 frontend-react/**               Next.js 15 -> Vite 8 + React 19 + React Router + Tailwind;
                                 node_modules volume, -p 3000:5173, cheese-app-network; nginx image
 vector-db/                      Chroma 1.5.9 at /data, docker compose, Python 3.13, ml-workflow.json
 src/docker-compose.yml          new in 447b5c3: the whole app in one command
```

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l18-apis-frontend/exercises.md) in the video folder. Their outputs are the 2026-11-05 captures and extra checks run for them (`assets/exercise-checks/`); none used a Google account. Do them after watching, without re-watching first, then re-watch only the chapter you got wrong. A summary follows; open each answer only after you have committed to your own.

**The questions the video stops on** (each is answered right after its timer): uvicorn on `--host 127.0.0.1` inside the container: does curl inside work, and your browser? · `/healthz` 200 and `/readyz` 503: restart or wait? · Could the page's JavaScript call `http://cheese-app-api-service:9000` directly? · Why would the production page server refuse to start while the API is down? · Last year's page needed CORS and this year's React app does not: what changed, the API, the browser or the origin it calls?

### Test yourself: the five questions from the end of the video

**Q1. Trace one newsletters request on `main` through the lecture's steps. Which container does the browser talk to, and at which step does the API's port come in?**
<details><summary>Answer</summary>

Only the frontend container, through `localhost:3000`. (1) The page asks for the relative path `/api/newsletters?limit=2` on its own origin (`Home.jsx:40`, `api.js:44`); (2) Docker maps 3000 to the container's 5173; (3) Vite listens there (`host: true`); **3½** Vite's proxy forwards `/api` to `http://cheese-app-api-service:9000` by name on `cheese-app-network`: this is where 9000 comes in; (4) FastAPI runs the newsletters route; (5) the answer comes back through Vite (`d04`: `server: uvicorn` on port 3000); (6) the page shows it. The API's own published 9000 is for you (docs, probes, curl), not on this path: unplug the API from the network and the browser gets 502 while 9000 is still published (`d09`).
</details>

**Q2. What do `api.service:app`, `--host 0.0.0.0` and `--reload` each do, and why does `/square_root` answer 307?**
<details><summary>Answer</summary>

`api.service:app`: import the module `api/service.py` and serve its variable `app`; uvicorn is the server, FastAPI the app. `--host 0.0.0.0`: listen on every interface of the container, including the one Docker's port forwarding arrives on; with `127.0.0.1` your browser's connection is reset. `--reload`: restart the app when a file under `api/` changes (`StatReload detected changes`). 307: v1's route is declared with a trailing slash, so FastAPI redirects the slash-less path to `/square_root/` (`a09`); a 307 keeps the method and body. On `main` the demo route has no slash, and there it is the slash version that is redirected.
</details>

**Q3. `/healthz` vs `/readyz`: what does each one check in this API?**
<details><summary>Answer</summary>

`/healthz` checks nothing beyond "the process can answer" (`200` while `/readyz` said 503, `b22`, `b23`). `/readyz` checks that the CNN model is loaded (`503 CNN model is loading` until the background thread finishes, `200` about nine seconds later) and that Chroma answers a heartbeat (`503 Chroma: …` otherwise). It does not check Gemini, your key, or whether the books are loaded.
</details>

**Q4. Where does a chat stay between two messages, and why can any copy of the API answer it?**
<details><summary>Answer</summary>

In a file: `/persistent/chat-history/<mode>/<session id>/<chat id>.json`, images beside it (`chat_utils.py:28-60`; `b42`). The browser keeps only the session UUID in `localStorage` and sends it as `X-Session-ID`. Each message rebuilds the conversation from the file, adds the turn, saves and forgets (`chat.py:35-43`). Any copy that sees the **same files** can answer the next message; copies with separate disks would not find each other's chats.
</details>

**Q5. Which file decides where `/api` goes in development, which in production, and why did the 2025 API need `CORSMiddleware` while `main`'s does not?**
<details><summary>Answer</summary>

Development: `src/frontend-react/vite.config.js:13`. Production: `src/frontend-react/nginx.conf.template:13-14`, with `API_URL` from the production `Dockerfile:13`. CORS: the 2025 page came from 8080 and its JavaScript called 9000 directly, a different origin, so the browser needed `access-control-allow-origin` (`c25`) and, for the chat POST, a preflight (`c27`). `main`'s page calls its own origin and the courier forwards, so there is nothing to permit (`docs/contract.md:6-7`). What changed is the origin the page calls, not the browser and not the API's security.
</details>

### Hands-on (predict, then run)

- **B1. Which interface?** Start v1's uvicorn with `--host 127.0.0.1`; curl from inside the container, then from the laptop.
- **B2. Path or query?** Add `@app.get("/hypot/{x}")` to v1 and predict `/hypot/3?y=4`, `/hypot/3`, `/hypot/abc` and what `/docs` says.
- **B3. Follow the slash.** Four requests (v1 GET and POST to `/square_root`, `main`'s `/api/newsletters/` and `/api/llm/chats/`): status and `location` for each.
- **B4. `def` or `async def`?** Two 2-second blocking routes, two requests at once each: which takes 4 s?
- **B5. The chat contract, by hand.** Five POSTs: no session ID, a non-UUID ID, `../../etc`, an empty message, an extra field.
- **B6. What does nginx serve?** Seven paths against the production image: status, content type and which `location` block.
- **B7. The proxy's `localhost`.** Point Vite's proxy at `http://localhost:9000`: what does port 3000 return?

### Debugging

- **C1.** "No such file or directory" after v1 `README.md:41`: the fix, and why it matters beyond the `cd`.
- **C2.** `/readyz` never turns 200 on Linux, and the log shows `PermissionError: … '/persistent/experiments'`.
- **C3.** `/readyz` says `Chroma: …` after starting the API first: restart the API?
- **C4.** The production container exits at once; and what if the API stops *after* nginx started?
- **C5.** One extra character, `proxy_pass ${API_URL}/;`, and every API call is `{"detail":"Not Found"}`.
- **C6.** "Blocked by CORS policy": the 2025 page against `main`'s API, and a crash that looks like CORS.
- **C7.** `git switch 2025` refuses: which edits, how to switch, which second key name.
- **C8.** `api_server: command not found` in the second terminal, and the leftover container with the same name.

### Think

- **D1.** Two copies of the API behind a load balancer: what must they share, and what does a user see if they don't?
- **D2.** What happens if both of Kubernetes' probes point at `/readyz`?
- **D3.** "Just add CORS to be safe": is it safer, and when would you add it?
- **D4.** Dev frontend on 3000 vs production on 8080: what serves the files, what is in the image, what happens without the API, what stays the same?

## 9. Errata and open questions

**Errata (with evidence)**
1. **Tutorial 24 removed from `main` while the course still teaches it.** On 2026-11-05 `main` deleted `src/frontend-simple/` and the README section ("removed frontend simple"); the lecture's Frontend deck walks through that app and the course site links its anchor. It survives on branch `2025` (`14f2a14`); Part C follows it there.
2. **The course site's anchors no longer exist on `main`.** `#tutorial-23-backend-apis` and `#tutorial-25-react-frontend-setup` became "Tutorial: Backend APIs" and "Tutorial: React Frontend Setup" (`cheese-app-v2/README.md:81`, `:147`); `#tutorial-24-simple-frontend-app` exists only on branch `2025`. The slides' anchors (`#setup-environments`, `#frontend-app-simple`, `#frontend-app-react`) exist in neither. Use the Links below.
3. **[v1] Stale `<body>` snippet** (`cheese-app-v1/README.md:88-95`, "🧀 Welcome to the cheese identification App!") predates the Formaggio.me page; pasted as a whole body it removes the page and the `main.js` script tag. Add only a `<p>` (`a23`).
4. **[v1] README paths without `src/`** (`cheese-app-v1/README.md:41`, `:75`; `a01`, `a19`).
5. **`http://localhost:900/api/docs`** (`cheese-app-v2/README.md:213`): a typo for 9000, followed by a stray "3000." (`f04-x-readme-url`).
6. **The cleanup misses the big leftovers.** `README.md:235-246` ends with `docker system prune`, which keeps every tagged image (more than 6 GB of cheese-app images here) and the `cheese-app-frontend-react-node_modules` volume (`e04`).
7. **"Production images" left the README** at `447b5c3`, while `src/frontend-react/Dockerfile` and `nginx.conf.template` are still there; the steps are in `cheese-app-v2@e98fa55/README.md:197-215` and work as written (`d20`–`d28`).
8. **`--chat` ignores your question** (`cheese-app-v2/src/vector-db/cli.py:377`), though the README says "Try a question" (`README.md:73`).
9. **Chat images keep a `.png` name whatever their format.** The browser uploads JPEG (`src/frontend-react/src/lib/image.js:12`); the API writes the bytes to `<message_id>.png` and serves them as `image/png` (`api/utils/chat_utils.py:35-43`, `api/routers/chat.py:84`). Browsers sniff the real type, so it displays.
10. **[2025] The README describes an older `service.py`.** "Create Demo Routes" and "Enable Cheese App API Routes" (`cheese-app-v2@2025/README.md:96-104`, `:116-138`) while the code already has `square_root` and four routers (`cheese-app-v2@2025/src/api-service/api/service.py:30-40`; `c13`, `c14`). The router files are `newsletter.py`/`podcast.py`, not `newsletters.py`/`podcasts.py` (`README.md:131-132`).
11. **[2025] Two key names**, `ml-workflow.json` and `llm-service-account.json`; the README names only the first (`cheese-app-v2@2025/README.md:25`).
12. **[2025] Retired model** `gemini-2.0-flash-001` (`cheese-app-v2@2025/src/api-service/api/utils/llm_utils.py:22`).
13. **[2025] RAG follow-up bug**: with the RAG router switched on, `message["content"]` on a pydantic object (`cheese-app-v2@2025/src/api-service/api/routers/llm_rag_chat.py:99`) fails every second message with an unhandled 500. Gone on `main`.
14. **[2025, v1] Simple-frontend Dockerfile `ADD --chown=app:app . /app`** with no user `app` in `node:20-alpine` (`cheese-app-v1/src/frontend-simple/Dockerfile:13`, `cheese-app-v2@2025/src/frontend-simple/Dockerfile:13`). BuildKit builds it anyway (`a20b`); the legacy builder would fail.

**Open questions (could not be settled from the sources)**
1. **The Ed lesson** was not accessible. If Ed points students to branch `2025` for everything, or to a pinned commit, follow Ed.
2. **Real Gemini answers.** Nothing here ran with a valid key, so no Ask or Cheese books answer, and no check that `text-embedding-004` answers on the `global` endpoint (`api/settings.py:7`, `:11`). Your first real call decides.
3. **`main` may move again.** It moved twice on the recording day. If your clone is newer than `447b5c3`, compare its README headings with the checklist above.
4. **L19's tutorial** was "coming soon" when the sources were checked.

## Links

**cheese-app-v1 README** (`main` @ `ce03a10`)
- [Prerequisites](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#prerequisites) · [Setup Environments](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#setup-environments) · [Backend API Container](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#backend-api-container) · [View API Docs](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#view-api-docs) · [Frontend App (Simple) Container](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#frontend-app-simple-container) · [Docker Cleanup](https://github.com/dlops-io/cheese-app-v1/blob/ce03a1029dd6f655a86e3e3edc99bb5938f0cbf8/README.md#docker-cleanup)

**cheese-app-v2 README** (`main` @ `447b5c3`)
- [Prerequisites](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#prerequisites) · [Tutorial: Environment Setup](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#tutorial-environment-setup) · [Tutorial: Vector DB for RAG Setup](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#tutorial-vector-db-for-rag-setup) · [Tutorial: Backend APIs](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#tutorial-backend-apis)
- [Tutorial: React Frontend Setup](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#tutorial-react-frontend-setup) · [Tutorial: Setup & Run Cheese App](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#tutorial-setup--run-cheese-app) · [Troubleshooting](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#troubleshooting) · [Docker Cleanup](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/README.md#docker-cleanup) · [API contract](https://github.com/dlops-io/cheese-app-v2/blob/447b5c3c2c06d724e86dddf70e1a244dbe3d7c47/docs/contract.md)
- Production images, from the README one commit earlier: [`e98fa55` · Production images](https://github.com/dlops-io/cheese-app-v2/blob/e98fa551c5d380517c6dc775ae626ea1a828e4d3/README.md#production-images)
- Latest README on [`main`](https://github.com/dlops-io/cheese-app-v2#readme)

**cheese-app-v2 README** (branch `2025` @ `14f2a14`)
- [Tutorial (23): Environment Setup](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-23-environment-setup) · [Tutorial (23): Vector DB for RAG Setup](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-23-vector-db-for-rag-setup) · [Tutorial (23): Backend APIs](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-23-backend-apis) · [Tutorial (24): Simple Frontend App](https://github.com/dlops-io/cheese-app-v2/blob/14f2a1420b43e9f24e977a9e67b53d7e2614013d/README.md#tutorial-24-simple-frontend-app)
- The branch itself: [`2025`](https://github.com/dlops-io/cheese-app-v2/tree/2025)

**Video and exercises**
- [AC215 · L18 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l18-apis-frontend) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l18-apis-frontend/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l18-apis-frontend/assets/terminal/laptop) · [ASSETS.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l18-apis-frontend/ASSETS.md)

**Course**
- Ed lesson: [L18 · APIs + Frontend](https://edstem.org/us/courses/97373/lessons/166043/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Previous lecture with a tutorial: [L15 · ML Workflows with Vertex AI](../guides/L15-vertex-ml-workflows.md) (the `ml-workflow` key this API reuses)
- Next lecture with a tutorial: [L20 · Deployment: Pulumi](../guides/L20-deployment-pulumi.md) (cheese-app-v3 behind NGINX)
- Referenced in section 7: [L05 · Introduction to RAG](../guides/L05-rag.md) · [L10 · Connecting to the Cloud (cheese-app-v0)](../guides/L10-cloud-connect-cheese-app-v0.md) · [L13 · Training Workflows](../guides/L13-training-workflows.md) · [L22 · Scaling: Kubernetes (cloud)](../guides/L22-kubernetes-cloud.md)
