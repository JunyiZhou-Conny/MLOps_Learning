# L05 · Introduction to RAG — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/182195/) · Tutorial: [`dlops-io/llm-rag`](https://github.com/dlops-io/llm-rag) `main` @ [`e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91) (the whole README; content identical to [`7a3c66b`](https://github.com/dlops-io/llm-rag/tree/7a3c66b777e7d4048b45f59b7223422325f1a281); its Agents section belongs to L06; comparison branch `pipenv` @ [`0b671ed`](https://github.com/dlops-io/llm-rag/tree/0b671ede29d4b37ecd530da493485b015adad4da)) · Video: [AC215 · L05 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l05-rag) · Made from the verified digest and real terminal captures, 2026-10-13

## 中文速览

- **做什么：** 用 11 本 cheese 书（10 本 Project Gutenberg 的老书 + 老师写的 Tolminc 短篇故事）搭一个经典的两阶段 RAG。Indexing：chunk → embed（Vertex AI 上的 `gemini-embedding-001`，每个 chunk 一个 256 维 vector）→ load 进 ChromaDB；Query：embed 问题 → top-10 nearest chunks → 拼进 prompt → `gemini-3.1-flash-lite` 回答。每一步都是 `cli.py` 的一个 flag（`--chunk`、`--embed`、`--load`、`--query`、`--chat`），在 CLI container 里跑；ChromaDB 是另一个 container，两个都由 Docker Compose 起。下面的 output 来自 2026-10-16 的真实 capture：录制时没有 Google key，Docker、chunking、Chroma 都是真跑的，`--load` 用的是 staff 留在 git history（`68e0bde`）里的 embeddings；凡是要调 Google 的步骤都标明 expected 或 recorded。
- **Idea 1 · RAG 不改 model：** retrieval 是你的代码做的，model 只看到 prompt 里贴进去的 chunks，weights 一点没变；删掉 collection，"知识"就没了。改 weights 的是 fine-tuning（L08）。两条 lane 必须用同一个 embedding model、同一个 dimension（256），question 和 chunks 才在同一个 space 里。
- **Idea 2 · chunking 是 trade-off：** `char-split` 是 350 字符的窗口、overlap 20、`separator=''`，会在单词中间切：capture 里故事的 chunk 0 结尾是 `…intended to ac`，chunk 1 从 `s she intended to accomplish` 开始（共 8,248 个 chunk，故事 24 个）。`recursive-split` 按段落 → 行 → 词切，但悄悄继承了 library 默认的 `chunk_overlap=200`（README 没说），chunk 1 又从 `## Chapter One` 重新开始，所以切出 14,228 个（故事 35 个）。
- **Idea 3 · embedding 是方向：** `gemini-embedding-001` 原生 3,072 维，代码用 `output_dimensionality` 只要前 256 维。这些 vector 不是 unit length（实测长度 0.369–0.402），所以 collection 用 `{"hnsw:space": "cosine"}` 很重要：Chroma 默认是 L2，长度会混进排序。Chroma 返回的是 cosine distance（= 1 − similarity，越小越近），不是 slides 上越大越好的 similarity score。
- **Idea 4 · filter 是 mask，而且先于 ranking：** `--query` 实际只跑 variant 4：`where={"book": "The Complete Book of Cheese"}` + `where_document={"$contains": "Italian"}`。实测 8,248 → 1,355 → 64 个 candidate，含 "Tolminc" 的 0 个；Chroma 先 filter，再从剩下的里取 top 10，所以 10 个结果全是意大利 cheese。这是在演示 filter，不是你做错了；`--chat` 才是不带 filter 的 top-10。
- **Idea 5 · ops 的形状：** `sh docker-shell.sh` 跑的是 `docker compose run --rm llm-rag-cli`：先起常驻的 `llm-rag-chromadb`（host port 8000），再 build、起一次性的 CLI container（真名是 `llm-rag-llm-rag-cli-run-<id>`，`container_name: llm-rag-cli` 对 `compose run` 不生效）。CLI 在 `llm-rag-network` 上用名字 `llm-rag-chromadb:8000` 找 DB，published port 是给你的 `curl` 和 browser 用的。Chroma 的 `/data` bind-mount 到 `docker-volumes/chromadb/`，`docker compose down` 再重启，两个 collection 还在；key 从 `../secrets` mount 到 `/secrets`，永远不放进 repo。
- **最费时间的坑：** ① clone 出来的 folder 必须叫 `llm-rag`（`docker-compose.yml:12` 写死了 `../llm-rag`），否则 Docker 建一个 root 的空 folder 盖在 `/app` 上，container 直接 `docker-entrypoint.sh: No such file or directory`（exit 127）。② 没 key 时 `--chunk` 照常跑，第一次 `--embed` 才报 `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.`；忘改 `docker-shell.sh:7` 的 `GCP_PROJECT`、或者没 enable Vertex AI API（README 根本没写这一步）会得到 403，而 `--embed` 会先 retry 5 次（约 2.5 分钟）才放弃。③ 别自己敲 `docker compose run`：两个变量变成空的，连 `--chunk` 都在 `cli.py:35` 挂掉（`File  was not found.`）。第一次启动时那行 `failed to resolve reference "docker.io/library/llm-rag-cli:latest"` 是无害的，Compose 接着就自己 build。
- **README 的 errata：** `SYSTEM_INSTRUCTION` 定义了但从来没传给 model（E1），所以 grounding 比 README 说的弱；`--query` 打印的标签是 `load()`；`out.txt` 是用旧版 Tolminc 书跑的 `--agent`（L06），别指望复现；`chromadb/chroma:latest` 没 pin（Docker Hub 上和 `1.5.9` 是同一个 digest，里面 `chroma --version` 却是 1.4.4，client 是 1.1.0）；没有 `.dockerignore`，build context 112 MB（`.git` 103 MB，history 里还留着 staff 的 database），image 里也带着 `/app/.git`；Storage Admin 这个 role 用不到；Woman's Institute 那本书没有 author/year metadata。
- **做完要删：** `exit` 只删掉 CLI container，`llm-rag-chromadb` 还在跑、还占着 port 8000，要在 `llm-rag/` 里 `docker compose down`（会打两行 WARN 说变量没 set，无害）。Images 还在（`llm-rag-cli` 2.11 GB、Chroma 826 MB），要空间就自己删。Cloud 上没有常驻的东西，Vertex AI 按你发送的 text 计费（整个 tutorial 做两遍估计远低于 $2）。可选：删 `outputs/` 和 `docker-volumes/`（后者是 root 的，Linux 上要 `sudo`）；课程结束后在 IAM 里删掉 JSON key。
- **Lecture slides：** 老师的两份 Lecture 5 slides（deck A "Introduction to RAG" 64 页，deck B "Advanced RAG" 89 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天的 code/captures 不一样的 9 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的三处：① slides 按 similarity 排序（越大越近），Chroma 返回的是 cosine distance（= 1 − similarity，越小越近）；② slides 把 metadata filtering 放在 ranking 之后，Chroma 的 `where` / `where_document` 是先过滤再排序，所以 `--query` 的 10 个结果里没有 Tolminc；③ slides 的 semantic chunking 用固定的 0.8 threshold，`semantic_splitter.py` 则在 distance 超过所有 distance 的 95th percentile 的地方切。

## At a glance

**What you build.** A question-answering system over 11 cheese books: `cli.py` cuts the books into chunks, embeds each chunk into a 256-number vector with Vertex AI's `gemini-embedding-001`, loads them into a ChromaDB collection, and then answers a question by retrieving the 10 nearest chunks and pasting them under the question in a prompt for `gemini-3.1-flash-lite`. It is your first multi-container Compose app with a stateful service: a throw-away CLI container talks by name to a long-lived Chroma server container whose data lives in a bind-mounted folder on your laptop.

**Time needed** (the recorded times are from the 2026-10-16 captures; the rest are estimates).
- Service account, key and API: about 15 minutes in the console.
- The first `sh docker-shell.sh`: pulling Chroma took 12.1 s and building the CLI image 81.5 s in the recording. On your laptop add the first download of the Python base image (about 48 MB), so plan for a few minutes. Later starts take seconds: no pull, no build.
- Chunking: 7 s (char-split) and 2 s (recursive-split) in the recording. No API call.
- Embedding: not recorded (it needs a key). Roughly 1-3 minutes per chunk type; char-split alone sleeps 55 s on purpose (5 s per book).
- Loading: 10 s (char-split) and 16 s (recursive-split) in the recording, on the staff's recorded vectors.
- Query and chat: seconds each.
- Budget about 1-1.5 hours for the README's core sections, plus 10-20+ minutes of API calls for the optional semantic split and about an hour for the extras and exercises.

**Prerequisites.**
- A GCP project with credits/billing from Tutorial 0 (`ac215-setup/README.md:149-193`), created under an individual account, "not under Harvard Organization" (`ac215-setup/README.md:157`). Have its **Project ID** at hand (not the project name).
- Docker Desktop, or Docker Engine plus the Compose v2 plugin (the script calls `docker compose`), and `git`. No local Python: everything runs in the container. Chrome for the optional web tools.
- Disk: about 3 GB for the two images (`llm-rag-cli` 2.11 GB including its Python base, `chromadb/chroma` 826 MB), plus over 100 MB for the clone (its `.git` alone is 103 MB) and about 170 MB once `outputs/` (about 90 MB) and the database (82 MB) are written.
- Background: service-account JSON keys and `GOOGLE_APPLICATION_CREDENTIALS` (L03); secrets outside the repo mounted at `/secrets`, Compose networks, DNS by container name and published ports (L04).
- Credentials: a service account `llm-service-account` with the Vertex AI User role ("Gemini Enterprise Agent Platform User" in the README) and its JSON key at `../secrets/llm-service-account.json`.
- APIs: the **Vertex AI API** (`aiplatform.googleapis.com`). The README never says to enable it (E6).

**What it costs.** Only pay-per-use Vertex AI charges, billed by the text you send and receive; nothing keeps running in GCP. Roughly $0.10 to embed char-split, $0.15 for recursive-split, about $0.40 for the optional semantic split (chunking plus embedding), and under a cent per query or chat. The whole tutorial, done twice, should cost well under $2 of credits (assumed prices; check the Vertex AI pricing page, §2). On your laptop, `llm-rag-chromadb` keeps running after you exit until you stop it.

**Tear down, exactly** (§2, §4 Step 14):
1. `exit` the container shell. The CLI container is removed (`--rm`), but `llm-rag-chromadb` keeps running (captured: `docker ps -a` still lists it, `Up`, with `0.0.0.0:8000->8000/tcp`).
2. On the host, in `llm-rag/`: `docker compose down`. Two `WARN … variable is not set` lines are harmless; then `Container llm-rag-chromadb Removed` and `Network llm-rag-network Removed`. Your index survives in `docker-volumes/chromadb/`.
3. Optional: delete `outputs/` and `docker-volumes/` to reclaim disk (both git-ignored). On Linux, `docker-volumes/` is owned by root: `sudo rm -rf docker-volumes`. The images stay until you remove them (`llm-rag-cli` 2.11 GB, `chromadb/chroma:latest` 826 MB).
4. When the course ends: delete the JSON key under **IAM & Admin → Service accounts → KEYS**.
5. Nothing to delete in the cloud: no VM, bucket or endpoint is created.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (GitHub anchors on `main`; line numbers in `README.md`):
  - Intro and [What you'll build](https://github.com/dlops-io/llm-rag#what-youll-build) `README.md:1-23`
  - [Prerequisites](https://github.com/dlops-io/llm-rag#prerequisites) `README.md:45-48`, [Setup GCP Service Account](https://github.com/dlops-io/llm-rag#setup-gcp-service-account) `:52-69`
  - [Run LLM RAG Container](https://github.com/dlops-io/llm-rag#run-llm-rag-container) `README.md:75-85`
  - [Chunk Documents](https://github.com/dlops-io/llm-rag#chunk-documents) `README.md:91-116`
  - [Generate Embeddings](https://github.com/dlops-io/llm-rag#generate-embeddings) `README.md:122-138`
  - [Load Embeddings into Vector Database](https://github.com/dlops-io/llm-rag#load-embeddings-into-vector-database) `README.md:144-165`
  - [Query the Vector Database](https://github.com/dlops-io/llm-rag#query-the-vector-database) `README.md:171-186`
  - [Chat with LLM](https://github.com/dlops-io/llm-rag#chat-with-llm) `README.md:192-214`
  - [Advanced RAG: Semantic Chunking](https://github.com/dlops-io/llm-rag#advanced-rag-semantic-chunking-semantic-splitting) `README.md:220-236` (optional, advanced)
  - **Not covered here:** [Agents](https://github.com/dlops-io/llm-rag#agents) `README.md:242-271` (`--agent`, `agent_tools.py`) belongs to **L06** (`2026-AC215/tutorials_demo.md:83-89` links it as "LLM-Agents"). It is only previewed in §4 Step 13 and §7.
- **Primary repo:** `dlops-io/llm-rag`, branch **`main`** (default), commit `e17a39f35bc07b440f573def480adaf4703f8b91`, committed 2026-10-07 21:34:23 -0400 ("Merge pull request #2 from obalatel/revert-1-demo-podcast"); still the head of `main` on 2026-10-16 (captured `git log --oneline -1`).
  - That merge reverts a "Demo podcast" PR, which had moved everything into `llmrag/` and added `api-service/` and `frontend-react/`. **`git diff 7a3c66b HEAD` is empty**, so the tutorial content is exactly commit `7a3c66b777e7d4048b45f59b7223422325f1a281` (2026-10-06 17:06:49 -0400, "updated for localhost"). That commit's only change was a second CORS origin in `docker-compose.yml:26`.
  - The reverted PR left large files in the history. `68e0bde` (2026-10-07) committed the staff's `outputs/` (22 chunk files and 22 embeddings files) and their Chroma database (a 90.9 MB `chroma.sqlite3`) under `llmrag/`. `58dd602` removed the database folder and the revert `d9ced19` removed `outputs/`, but every clone still downloads them: the captured `.git` is 103 MB.
  - Commits that shape this year's version: `59a0f80` + `4a5f347` (2025-10-01, Pipenv → uv and `vertexai` SDK → `google-genai`); `51a2865` (2026-09-16, `GCP_LOCATION = "global"`, `GENERATIVE_MODEL = "gemini-3.1-flash-lite"`); `9a27441` + `500a99c` (2026-09-16, Compose now creates the network and builds the image: `9a27441` "Wed midnight" made the change, commented out the script's `docker network create`/`docker build` and moved Chroma's mount from `/chroma/chroma` to `/data`; `500a99c` only deleted the commented-out lines and rewrote the README); `74dba4a` (2026-09-17, `text-embedding-004` → `gemini-embedding-001`); `96d5fd7` (2026-09-20, chat query changed to the Tolminc question); `85bba32` (2026-09-22, Tolminc book rewritten and `out.txt` added).
- **Other branches, read for comparison only:** `pipenv` @ `0b671ede29d4b37ecd530da493485b015adad4da` (2025-03-04, the older Pipenv version, used in §7); `demo-podcast` @ `96fef434536f6e58a5bd027f49916fc98cd467e1` (2026-10-07, API + React front end, material for a later lecture); `revert-1-demo-podcast` @ `b77a556560befb87e241d39965d68f2e77a6d2ad` (the revert PR's branch).
- **Context repos read for §7:** `dlops-io/cheese-app-v0` @ `cb6fb94` (L10; it ships a near-verbatim copy of this repo in `cheese-app-v0/llm-rag/`, see §7), `dlops-io/llm-agent-google-adk` @ `f89faa79de744f6a046e30dff24b3b6f1d73720b` (L06), `dlops-io/ac215-setup` @ `61a7b9d` (Tutorial 0).
- **Path convention:** paths without a prefix (`cli.py:23`, `README.md:84`) are inside `llm-rag/`. Course-site paths start with `2026-AC215/`, other repos with their repo name.
- **Method.**
  - **Code reading.** The facts and `path:line` references were verified against the repos on 2026-10-13 (adversarial check); library behaviour comes from reading the source of `google-genai 1.39.1` and `chromadb 1.1.0`, the versions pinned in `uv.lock`.
  - **Captures.** On 2026-10-16 (00:52-00:57 UTC) every README command of the RAG part was run in README order, exactly as written, on a fresh stand-in laptop (a Docker-in-Docker container with its own network): Docker Engine 29.8.2 (linux/amd64), Docker Compose v5.6.0, git 2.54.0, user `student`, workspace `~/AC215` holding `llm-rag/` and `secrets/` side by side. The `docker-shell.sh` edit used the placeholder `your-project-id`. The files are in the video folder's [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l05-rag/assets/terminal) (folders `laptop/`, `cli-container/`, `recorded-embeddings/`, `gotchas/`, `expected/`); §4 names the file behind every output block.
  - **No Google key.** `~/AC215/secrets/` was empty, so every Vertex AI call stopped at `DefaultCredentialsError`; nothing reached Google. Steps that need Google show the real no-key failure, plus what to look for with your key, labelled *expected (from the code)*.
  - **Recorded embeddings.** The staff's 22 chunk files in `68e0bde` are byte-identical (sha1) to the ones `--chunk` made in the capture, so their 22 embeddings files are exactly what `--embed` produces for these chunks. Copied into `outputs/`, they let the two `--load` commands and the database checks run for real; those outputs are labelled *recorded (the staff's vectors)*.
  - **Versions in the captures** (they move; "at the time of recording"): in the `llm-rag-cli` image, Python 3.12.15, uv 0.13.1, and `uv sync --frozen` installed 123 packages exactly as `uv.lock` pins them, among them chromadb 1.1.0, google-genai 1.39.1, google-auth 2.41.1, langchain 0.3.27, langchain-community 0.3.30, langchain-text-splitters 0.3.11, numpy 2.3.3, pandas 2.3.3, openai 1.109.1, openai-agents 0.3.2. The Chroma server: `chromadb/chroma:latest`, digest `sha256:1e0b73a1…`, created 2026-05-05; Docker Hub listed that digest under both `latest` and `1.5.9` on 2026-10-16, yet `chroma --version` inside prints `chroma 1.4.4` and `GET /api/v2/version` answers `"1.0.0"`.
  - **Exercise checks.** The answers in §8 were checked on 2026-10-16 in throwaway containers of the tutorial's own image against the same Chroma image, loaded with the staff's recorded vectors (logs in the video folder's `assets/exercise-checks/`).
- **Ed lesson:** not accessible when these sources were checked; the course-site map `2026-AC215/tutorials_demo.md:71-79` was used instead. The weekly schedule lists "LLM - RAGs" on **Sep 15** but labels it "Lecture 4" (`2026-AC215/_modules/week-03.md:5-7`). The lecture slides were provided for study; see [Lecture slides](#lecture-slides).
- **Colab notebooks:** none. The `colab/` folder has nothing for L05; the L06 notebooks are only cited in §7.

</details>

## Lecture slides

The instructor's slides for this lecture come in two decks:
- *Lecture 5: Introduction to RAG* (deck A, `L05_RAGs_I_fix`, 64 slides). It walks the naïve-RAG pipeline that this tutorial builds, one box at a time.
- *Lecture 5 suppl: Advanced RAG* (deck B, `Lec05b_RAG_II_added_j_suffix_in_RRF`, 89 slides). Its semantic-chunking walk-through covers the step in §3.7, with a different cutting rule (see below). Query rewriting, hybrid search, re-ranking and Self-RAG have no code in this tutorial.

Slide numbers are PDF page numbers, written A12 or B46; the printed footers differ. Neither deck shows commands, Docker, ChromaDB or Gemini.

The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video are in the Explainer_Videos repo, in `videos/ac215-l05-rag/SLIDES.md`. This answers the slides part of §9 Q1.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | A6–A16 (why RAG, the three options, what RAG is, the naïve-RAG pipeline); B5–B6 (its three phases) |
| §2 Prerequisites and costs | none. B61 explains the cost shape: the heavy embedding work happens once, up front, and each question costs one embedding. |
| §3.1 RAG = retrieval + generation | A6–A14, A61–A62; B68–B72 (what RAG doesn't guarantee; looking things up only when needed) |
| §3.2 Chunking; §4 Steps 4–5 | A19–A22, B13–B19 |
| §3.3 Embeddings and cosine similarity; §4 Step 6 | A24–A28, A40–A47; B59–B60 (one encoder for documents and queries) |
| §3.4 The vector database; §4 Step 7 | A30–A38 |
| §3.5 Retrieval: top-k and filters; §4 Steps 9, 11 | A39, A44, A48–A55 |
| §3.6 Augmented generation; §4 Step 10; §9 E1 | A57–A62; B78 (checking that the answer is supported) |
| §3.7 Semantic chunking; §4 Step 12 | B19–B34 |
| Command checklist; §3.8 The ops shape; §4 Steps 0–3, 8, 14; §5 Code tour; §6 Gotchas | none (tutorial-only) |
| §4 Step 13 (Agents preview); §7 Where this sits | A9 (fine-tuning comes later: L08); B35–B65 (query rewriting, hybrid search, re-ranking); B66–B88 (Self-RAG) |
| §8 Exercises | Q4 ↔ A54–A55; Q5 and B6 ↔ A57–A59; C5 ↔ B60; D1 ↔ A44–A47; D6 ↔ B42–B48; D7 ↔ A40–A47 |

**Lecture ideas you need for this tutorial**
1. **Why RAG.** LLMs have stale training data, lack domain knowledge, hallucinate and don't cite sources; RAG targets the first two. Pasting every document into the prompt gives garbage, and fine-tuning takes too long (A6–A10).
2. **Naïve RAG is two lanes.** Knowledge base → chunking → embedding model → vector database. Question → the same embedding model → the database → prompt → LLM. The three phases are Indexing, Retrieval, and Augmentation & Generation (A16, B5).
3. **One encoder, two moments.** The same embedding model embeds the documents ahead of time and the question when it arrives. That makes retrieval fast, and it's why the query and the chunks must use the same model and size (B59–B61).
4. **Chunk so the model can focus.** Fixed-size character splitting is the default; it cuts words in half and runs sections together. Chunks that follow the document's structure are better (A20–A21, B14–B19).
5. **Embeddings and similarity measures.** A whole chunk becomes one vector (a sentence embedding, not word embeddings). Cosine similarity compares directions; Euclidean distance and the dot product also count length. Cosine suits text embeddings (A25–A28, A42–A47).
6. **Why a vector database, and why an index.** SQL can't search by meaning, and comparing the query with millions of vectors one by one is too slow. An index (LSH, PQ or HNSW; Chroma builds HNSW) jumps to likely neighbours. The database returns the top K, with K fixed in advance (A31–A39, A48–A53).
7. **Optional post-processing.** Metadata filtering and re-ranking are optional. Metadata is data about the data, such as author, publication date and category (A54–A55).
8. **The final prompt** is a system prompt (how to behave), plus the user's query, plus the retrieved context (A57–A59).
9. **Semantic chunking.** Split the text into sentences, pick an anchor sentence with a window of neighbours on each side, compare them by the cosine similarity of their embeddings, join the similar ones, then move the anchor on (B19–B33).
10. **Limits and next steps** (no code here). Even advanced RAG doesn't guarantee relevant chunks or a supported answer, and it retrieves even when it needn't (B68). The lecture's levers: query rewriting, hybrid search (BM25 plus vectors, merged with Reciprocal Rank Fusion), re-ranking with a cross-encoder, and Self-RAG (B35–B88).

**Where the slides and today's tutorial differ** (the code and the 2026-10-16 captures decide)
- **Scores vs distances.** The slides rank by similarity: higher is closer (A48–A53). Chroma returns cosine distance, 1 − similarity: lower is closer, and a chunk's own vector comes back at 0.0000 (§3.3).
- **When filters apply.** The slides put metadata filtering after ranking (A54–A55). Chroma applies `where` and `where_document` first and picks the top 10 among the survivors. That's why `--query` returns Italian cheeses and no Tolminc (§3.5).
- **The system prompt.** The slides' final prompt starts with a system prompt (A58–A59). `cli.py` defines a cheese-expert `SYSTEM_INSTRUCTION` but never sends it (§9 E1).
- **The semantic-chunking rule.**
  - The slides move an anchor sentence along and join neighbours whose similarity clears a fixed 0.8 (B21–B33).
  - The code compares every pair of neighbouring three-sentence windows and cuts where the distance is above the 95th percentile.
  - The code also calls the embedding API already during `--chunk` (§3.7).
- **Overlap.** The slides' character-split pieces sit end to end, with no overlap (B14–B18). `char-split` repeats 20 characters at each cut. `recursive-split` repeats up to 200, a library default the README doesn't state (§3.2, §9 E14).
- **"Indexing".** It means the search structure on A32–A38, the whole offline phase on B5–B10, and better chunking on B13–B34. The README just says "Chunk -> Embed -> Load" (§1).
- **Who embeds the question.** On A12 the question itself goes to the vector database. In the code, Google embeds the question first, and Chroma receives only the vector. Passing text instead would make Chroma use its own, different embedding model (§3.4, §8 C5).
- **How much RAG guarantees.** The slides claim only fresher and domain-specific knowledge (A7), and warn that answers may still be unsupported (B68). The README promises answers "grounded in your documents" (`README.md:21`). But the code sends no instruction to stay inside them, and it leaves the book names out of the prompt (§3.6).
- **Keyword search.** The slides' hybrid search ranks by keywords (BM25) and fuses the rankings (B42–B48). The tutorial's `where_document={"$contains": …}` only filters by a word, before the vector ranking (§3.5).

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept). Plain items are console clicks, links or edits. Items marked *(extra)* are not in the README; most were captured on 2026-10-16 and are typed here exactly as captured, and §4 shows their real output. "Host" items run on your laptop, in `~/AC215/llm-rag` (open a second terminal there while the container runs); every `python cli.py …` command runs **inside** the CLI container that `sh docker-shell.sh` opens (prompt `app@<id>:/app$`). The capture had no Google key: the notes say which commands need yours.

### Prerequisites

*(`README.md:45-48`; §4 Step 0)*
- [ ] Have Docker installed: Docker Desktop, or Docker Engine plus the Compose v2 plugin (the script calls `docker compose`, with a space).
- [ ] `docker --version; docker compose version` — *(extra, host)* captured: `Docker version 29.8.2, build 7fc2dff` and `Docker Compose version v5.6.0` (at the time of recording).
- [ ] Cloned this repository to your local machine — <https://github.com/dlops-io/llm-rag>.
- [ ] `cd ~/AC215` — *(extra, host)* or wherever you keep course repos; this parent folder will hold both `llm-rag/` and `secrets/`.
- [ ] `git clone https://github.com/dlops-io/llm-rag.git` — *(extra: the README links the repo but prints no clone command)* captured: `Cloning into 'llm-rag'...`. The folder must be named exactly `llm-rag` (`docker-compose.yml:12` mounts `../llm-rag`); rename a ZIP download's `llm-rag-main` (G1).
- [ ] `mkdir secrets; ls` — *(extra, host)* creates `secrets/` as a **sibling** of `llm-rag/`, never inside it (G20); captured: `llm-rag  secrets`.

### Setup GCP Service Account

*(`README.md:52-69`; §4 Step 1)*
- [ ] *(extra)* Enable the **Vertex AI API** in your project (APIs & Services). The README never says to (E6); without it the first embed fails with `SERVICE_DISABLED` (G4).
- [ ] `gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>` — *(extra, host, not captured)* the CLI equivalent of the click above.
- [ ] Go to the [GCP Console](https://console.cloud.google.com/home/dashboard), search for **"Service accounts"** in the top search box, or open **IAM & Admin → Service accounts** from the top-left menu.
- [ ] Create a new service account called `llm-service-account`.
- [ ] In **"Grant this service account access to project"** select **Storage Admin** and **Gemini Enterprise Agent Platform User** (listed as "Vertex AI User" in older projects). Only the Vertex role is used by the code; Storage Admin is unused (E5).
- [ ] Click the service account and open the **KEYS** tab.
- [ ] Click **ADD Key (Create New Key)** and select **JSON**; a private key JSON file downloads to your computer. If key creation is blocked by an org policy, you are probably in an organisation-managed project: use your personal one.
- [ ] Copy the JSON file into the **secrets** folder and rename it to `llm-service-account.json`.
- [ ] `ls ../secrets` — *(extra, host, from inside `llm-rag/`; not captured: no key)* prints `llm-service-account.json`.
- [ ] `grep project_id ../secrets/llm-service-account.json` — *(extra, host, not captured)* shows the project the key belongs to; the next section must use the same ID.

### Run LLM RAG Container

*(`README.md:75-85`; §4 Steps 2-3)*
- [ ] Make sure you are inside the `llm-rag` folder and open a terminal at this location.
- [ ] `cd llm-rag` — *(extra: the README says it in words)*.
- [ ] `ls -a; git log --oneline -1` — *(extra, host)* the repo's files and the commit: captured `e17a39f (HEAD -> main, origin/main, origin/HEAD) Merge pull request #2 …`, or a newer commit if the repo has moved.
- [ ] `du -sh .git; git count-objects -vH | grep size-pack` — *(extra, host)* captured `103M .git`: the history still holds the staff's database and `outputs/` (E21).
- [ ] Update `GCP_PROJECT` to your own project ID in `docker-shell.sh`: line 7, `export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID`. Leave line 8 (`/secrets/llm-service-account.json`, an in-container path) alone. Skipping this gives a 403 `PERMISSION_DENIED` later (G3).
- [ ] `git diff docker-shell.sh` — *(extra, host)* exactly one changed line, line 7 (captured with the placeholder `your-project-id`).
- [ ] `sh docker-shell.sh` — runs `docker compose run --rm llm-rag-cli`: pulls `chromadb/chroma:latest`, creates `llm-rag-network`, creates `llm-rag-chromadb` (port 8000), builds the `llm-rag-cli` image on the first run only, then prints the `Container is running!!!` banner and a bash prompt in `/app` as user `app`.
  - Note: works as written. On the first run Compose v5.6.0 first prints `Image llm-rag-cli Pulling` and `failed to resolve reference "docker.io/library/llm-rag-cli:latest": … not found`, then `Image llm-rag-cli Building`: harmless (G24). On Windows run it from Git Bash or WSL (G22).
- [ ] `docker ps` — *(extra, host)* `llm-rag-chromadb` with `0.0.0.0:8000->8000/tcp`, and the CLI container, named `llm-rag-llm-rag-cli-run-<id>`, not `llm-rag-cli`.
- [ ] `docker network ls` — *(extra, host)* lists `llm-rag-network` (bridge).
- [ ] `curl http://localhost:8000/api/v2/heartbeat` — *(extra, host)* `{"nanosecond heartbeat":…}` through the published port.
- [ ] `curl http://localhost:8000/api/v2/version` — *(extra, host)* captured `"1.0.0"`.
- [ ] `docker exec llm-rag-chromadb chroma --version; docker image inspect chromadb/chroma:latest --format '{{index .RepoDigests 0}} created {{.Created}}'` — *(extra, host)* captured `chroma 1.4.4` and the digest `sha256:1e0b73a1…` created 2026-05-05 (E9).
- [ ] `curl -si -H 'Origin: https://ac215-llm-rag.dlops.io' http://localhost:8000/api/v2/heartbeat` — *(extra, host)* the answer carries `access-control-allow-origin: https://ac215-llm-rag.dlops.io`.
- [ ] `curl -si -H 'Origin: https://example.com' http://localhost:8000/api/v2/heartbeat` — *(extra, host)* no `access-control-allow-origin` header: only the course's site (and `localhost:3200`) may read your database from a browser.
- [ ] `ls -la docker-volumes/chromadb` — *(extra, host)* the folder already exists, with a small `chroma.sqlite3`, owned by `root`.
- [ ] `docker images` — *(extra, host)* `chromadb/chroma:latest` 826MB, `llm-rag-cli:latest` 2.11GB, `python:3.12-slim-bookworm` 198MB.
- [ ] `docker run --rm --entrypoint bash llm-rag-cli -c 'du -sh /app/.git; du -sh /.venv; ls -la /app/docker-volumes/chromadb'` — *(extra, host)* what the image itself holds: `103M /app/.git`, `439M /.venv`, and a copy of `chroma.sqlite3` (G15).
- [ ] `docker inspect <cli-container-name> --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'; docker inspect llm-rag-chromadb --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'` — *(extra, host)* the three bind mounts; use the CLI container's name from `docker ps` (captured with `llm-rag-llm-rag-cli-run-90678535ddef`).
- [ ] `whoami; pwd; which python; python --version; uv --version` — *(extra, container)* `app`, `/app`, `/.venv/bin/python`, `Python 3.12.15`, `uv 0.13.1 …`.
- [ ] `echo GCP_PROJECT=$GCP_PROJECT; echo GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS; ls -la /secrets` — *(extra, container)* your Project ID, `/secrets/llm-service-account.json`, and the key file in `/secrets` (the capture's folder was empty).
- [ ] `ls` — *(extra, container)* the repo, seen through the bind mount at `/app`.
- [ ] `uv pip list 2>/dev/null | grep -E '^(chromadb|google-genai|google-auth|langchain|langchain-community|langchain-text-splitters|numpy|pandas|openai|openai-agents) '` — *(extra, container)* the locked versions (chromadb 1.1.0, google-genai 1.39.1, …).
- [ ] `getent hosts llm-rag-chromadb; curl -s http://llm-rag-chromadb:8000/api/v2/heartbeat; echo` — *(extra, container)* the name resolves on the Compose network (captured `172.19.0.2`), and Chroma answers by name.

### Chunk Documents

*(`README.md:91-116`; §4 Steps 4-5)*
- [ ] *(optional)* Open the chunking [visualization](https://ac215-llm-rag.dlops.io/chunkviz) in Chrome.
- [ ] `python cli.py --chunk --chunk_type char-split` — 350-character windows with a 20-character overlap, cut mid-word; writes `outputs/chunks-char-split-<book>.jsonl`; prints `Number of chunks:` per book (the story: 24). No API call, no key needed.
- [ ] `wc -l outputs/chunks-char-split-*.jsonl` — *(extra, container)* one line per chunk: `8248 total`.
- [ ] `python -c "import json; c = [json.loads(l)['chunk'] for l in open('outputs/chunks-char-split-Tolminc Cheese.jsonl')]; print(len(c)); print(repr(c[0][-40:])); print(repr(c[1][:40]))"` — *(extra, container)* the seam between chunk 0 and chunk 1: the mid-word cut and the 20 repeated characters.
- [ ] `ls -la outputs | head -5` — *(extra, host)* the chunk files are on your laptop, owned by you.
- [ ] `python cli.py --chunk --chunk_type recursive-split` — cuts at paragraph, line, then word boundaries, with the library's default overlap of up to 200 characters (E14); the story: 35 chunks.
- [ ] `wc -l outputs/chunks-recursive-split-*.jsonl` — *(extra, container)* `14228 total`.
- [ ] `python -c "import json; c = [json.loads(l)['chunk'] for l in open('outputs/chunks-recursive-split-Tolminc Cheese.jsonl')]; print(len(c)); print(c[0]); print('---'); print(c[1]); print('---'); print(c[2])"` — *(extra, container)* chunk 1 starts again at `## Chapter One`: the hidden overlap.
- [ ] `ls outputs | head -4; ls outputs | wc -l; du -sh outputs` — *(extra, container)* 22 chunk files, 8.2M.

### Generate Embeddings

*(`README.md:122-138`; §4 Step 6)*
- [ ] `python cli.py --embed --chunk_type char-split` — sends the chunks to `gemini-embedding-001` in batches of 100 (89 calls, plus a 5 s sleep per book) and writes `outputs/embeddings-char-split-<book>.jsonl` with a 256-number `embedding` column. The first command that needs your key.
  - Note: without a key (the capture) it reads the first book, then fails with `google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` (G2). A 403 is retried 5 times, about 2.5 minutes, before it gives up (G3, G4).
- [ ] `python cli.py --embed --chunk_type recursive-split` — the same for the recursive chunks (148 calls).
- [ ] `ls outputs | grep '^embeddings-' | wc -l; ls -la /secrets` — *(extra, container)* 22 embeddings files after both runs, and your key in `/secrets` (the capture printed `0` and an empty folder).
- [ ] *(extra, host, optional: no key yet)* copy the staff's recorded embeddings out of the repo history into `outputs/`, so the load steps and the checks below can run (§4 Step 6). They are the staff's vectors, not yours.
- [ ] *(extra, container)* the vector-length check, `python - <<'EOF'` … `EOF` (full code in §4 Step 6): 24 rows of 256 numbers, lengths 0.369 to 0.402, not 1.

### Load Embeddings into Vector Database

*(`README.md:144-165`; §4 Steps 7-8)*
- [ ] `python cli.py --load --chunk_type char-split` — connects to `llm-rag-chromadb:8000`, deletes and recreates `char-split-collection` (cosine space) and inserts the records in batches of 500: `Finished inserting N items …` per book, 8,248 in all.
  - Note: `Number of files to process: 0` (captured before any embeddings existed) means your embed step did not finish.
- [ ] `python cli.py --load --chunk_type recursive-split` — the same into `recursive-split-collection`, 14,228 records.
- [ ] `curl http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections` — *(extra, host)* both collections, with `"metadata":{"hnsw:space":"cosine"}` and the HNSW settings.
- [ ] `curl -s http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections | grep -oE '"name":"[a-z-]+-collection"|"dimension":[a-z0-9]+'` — *(extra, host)* the same, reduced to names and dimensions: `"dimension":256` once loaded (`null` while empty).
- [ ] `ls -la docker-volumes/chromadb; du -sh docker-volumes/chromadb` — *(extra, host)* `chroma.sqlite3` (59.8 MB) plus one UUID-named index folder per collection, 82M, owned by root.
- [ ] *(extra, container)* the metadata check, `python - <<'EOF'` … `EOF` (full code in §4 Step 7): `count: 8248`, one metadata dict per book; the Woman's Institute book has no author or year (E8).
- [ ] `python cli.py --load --chunk_type char-split` — *(extra, container)* run it again: `Deleted existing collection 'char-split-collection'`; every load is a full rebuild.
- [ ] *(optional)* View your local vector database with the [Chroma UI Tool](https://ac215-llm-rag.dlops.io/chromaui) in Chrome.

*Restart test (§4 Step 8, all extra)*
- [ ] `exit` — *(extra)* leaves the CLI container.
- [ ] `docker ps -a` — *(extra, host)* the CLI container is gone; `llm-rag-chromadb` is still `Up` with port 8000.
- [ ] `docker compose down` — *(extra, host)* two harmless `WARN` lines, then the container and the network are removed.
- [ ] `docker ps -a; docker network ls; ls -la docker-volumes/chromadb` — *(extra, host)* nothing running, no `llm-rag-network`, but the database file and both index folders are still there.
- [ ] `sh docker-shell.sh` — *(extra)* `[+] run 2/2`: no pull, no build; the banner and a new prompt.
- [ ] `curl -s http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections | grep -oE '"name":"[a-z-]+-collection"|"dimension":[a-z0-9]+'` — *(extra, host)* both collections are back, `"dimension":256`.
- [ ] `python cli.py --get --chunk_type char-split` — *(extra, container; the flag is not in the README)* the same 10 record IDs as before the restart (Step 11).

### Query the Vector Database

*(`README.md:171-186`; §4 Steps 9 and 11)*
- [ ] `python cli.py --query --chunk_type char-split` — embeds "How is tolminc cheese made?" and runs only filter variant #4: the top 10 from *The Complete Book of Cheese* whose text contains "Italian". None of the results mentions Tolminc (E2).
  - Note: needs your key. The capture prints `load()` (a copy-paste label, E3), then stops at `DefaultCredentialsError` while embedding the question.
- [ ] `python cli.py --query --chunk_type recursive-split` — the same query against `recursive-split-collection`.
- [ ] *(extra, container)* the filter-count check, `python - <<'EOF'` … `EOF` (full code in §4 Step 9): 8,248 chunks → 1,355 in the book → 64 with "Italian" → 0 with "Tolminc".
- [ ] *(extra, container)* the stand-in query, `python - <<'EOF'` … `EOF` (full code in §4 Step 9): the same search with and without the code's filters; needs no key.
- [ ] *(extra)* On your laptop, uncomment variant #1 at `cli.py:326-331` (no filter), then rerun `--query` (no rebuild needed: the repo is bind-mounted). Variant #4 still runs and prints after it.
- [ ] `python cli.py --get --chunk_type char-split` — *(extra, container)* undocumented flag: a plain metadata lookup (10 records of *The Complete Book of Cheese*, no `distances`, no ranking, no key needed) (Step 11).

### Chat with LLM

*(`README.md:192-214`; §4 Step 10)*
- [ ] `python cli.py --chat --chunk_type char-split` — embeds "How is tolminc cheese made??", takes the top 10 with no filter, pastes them under the question and prints `LLM Response:` from `gemini-3.1-flash-lite`. Needs your key: one embedding call and one Gemini call.
- [ ] `python cli.py --chat --chunk_type recursive-split` — the same with recursive chunks; compare the two answers.
- [ ] *(optional)* Try the [Chat Tool](https://ac215-llm-rag.dlops.io/chat) in Chrome.
- [ ] *(extra)* For your own question, change the string at `cli.py:372` and rerun.

### Advanced RAG: Semantic Chunking (Semantic Splitting)

*(`README.md:220-236`, optional; §4 Step 12)*
- [ ] `python cli.py --chunk --embed --load --chunk_type semantic-split` — chunk, embed and load in one run. The chunking itself calls the embedding API (528 calls for all 11 books), so it needs your key already at `--chunk`: the capture fails on the first book with `DefaultCredentialsError`. Budget 10-20+ minutes and expect 429 retries.
  - Note: to test cheaply, move every book but the story aside first (§4 Step 12 has the three `mv` lines): 4 embedding calls in all.
- [ ] `ls outputs | grep semantic | wc -l` — *(extra, container)* the semantic chunk and embeddings files (`0` in the capture: nothing was saved).
- [ ] `python cli.py --chat --chunk_type semantic-split` — *(extra, container, after the load finishes)* compare the answer with the two `--chat` runs above.

### Agents (preview only; covered in L06)

*(`README.md:242-271`; §4 Step 13)*
- [ ] `python cli.py --agent --chunk_type char-split` — Gemini function calling picks a retrieval tool (by author, or across all books), then answers. Details in L06.
- [ ] *(optional)* Try the [Cheese Agent Tool](https://ac215-llm-rag.dlops.io/agent) in Chrome.

### After the README *(extra)*

*Leave and clean up (§4 Step 14)*
- [ ] `exit` — *(extra)* leaves the CLI container, which is deleted (`--rm`); Chroma keeps running.
- [ ] `docker compose down` — *(extra, host, in `llm-rag/`)* stops `llm-rag-chromadb` and removes `llm-rag-network`; `docker-volumes/chromadb/` stays, so next time you can query straight away.
- [ ] `docker images` — *(extra, host)* the three images remain; remove them when you need the space.
- [ ] `git status; git status --short --ignored` — *(extra, host)* only ` M docker-shell.sh`; `outputs/`, `docker-volumes/` and `__pycache__/` are ignored.
- [ ] `sudo rm -rf docker-volumes` — *(extra, host, Linux, optional)* removes the root-owned Chroma data; delete `outputs/` too if you want the disk back (G14).
- [ ] *(extra)* When the course ends, delete the key under **IAM & Admin → Service accounts → KEYS**.

*Only when needed (§6)*
- [ ] `docker compose build` — *(extra, host)* after a `git pull` that changed `pyproject.toml`, `uv.lock` or the `Dockerfile`, or after `uv add`: Compose only builds when the image is missing (G9, G16). One-step alternative: `docker compose run --build --rm llm-rag-cli`.
- [ ] `ls /secrets` — *(extra, container)* check that the key is mounted when the first embed fails with `DefaultCredentialsError` (G2).
- [ ] `docker stop <name>` — *(extra, host)* frees host port 8000 when `docker ps` shows another container holding it; then `docker compose down` before the next start (G6).
- [ ] `docker rm -f llm-rag-chromadb` — *(extra, host)* clears a `container name "/llm-rag-chromadb" is already in use` conflict (G7).
- [ ] `mkdir outputs && chmod a+w outputs` — *(extra, host, Linux)* fixes `PermissionError … 'outputs'` when your host uid is not 1000 (G14).
- [ ] `git config --global core.autocrlf input` — *(extra, Windows)* then re-clone, so the `.sh` files keep LF endings (G22).

*What-if demos (optional, only to see a gotcha happen; never a way to start)*
- [ ] `docker compose run --rm llm-rag-cli` — *(extra, host, G5)* bypasses the script: both variables are blank, and `python cli.py --chunk --chunk_type char-split` then dies at `cli.py:35`. `exit`, then `docker compose down`.
- [ ] `git clone https://github.com/dlops-io/llm-rag.git llm-rag-main; mkdir secrets; ls` — *(extra, host, G1, in a separate parent folder such as `~/AC215-zip`)* a clone with the ZIP download's name.
- [ ] `sh docker-shell.sh` — *(extra, in `llm-rag-main/`)* `/bin/bash: docker-entrypoint.sh: No such file or directory`, exit 127.
- [ ] `ls -la ..; ls -la ../llm-rag` — *(extra, host)* the empty, root-owned `../llm-rag` that Docker created. Clean up with `docker compose down`, then remove that empty folder with `sudo rmdir ../llm-rag` (Linux; `rmdir` refuses a folder that isn't empty, so it can't touch a real clone).

---

## 1. What you build

You build a **question-answering system over 11 cheese books** (10 Project Gutenberg texts plus the instructor's short Tolminc story), the classic two-phase RAG pipeline (`README.md:5-21`). In the **indexing phase**, `cli.py` does three things:
1. **Chunk:** cut every book into ~350-character chunks with LangChain splitters.
2. **Embed:** send the chunks in batches to Google's `gemini-embedding-001` model on Vertex AI, which returns one **256-number vector** per chunk.
3. **Load:** store chunk text, vector and metadata (`book`, `author`, `year`) in a **ChromaDB** collection.

In the **query phase**, the same CLI embeds a question ("How is tolminc cheese made?"), asks Chroma for the 10 nearest chunks, pastes them under the question in a prompt, and sends that to `gemini-3.1-flash-lite`. The answer can then draw on the books instead of only the model's memory.

On the ops side this is your **first multi-container Compose app with a stateful service**:
- a throw-away **CLI container** (service and image `llm-rag-cli`, built from this repo's Dockerfile, removed when you exit; `docker compose run` names the container itself `llm-rag-llm-rag-cli-run-<id>`), and
- a long-lived **vector-database server container** (`llm-rag-chromadb`, the stock `chromadb/chroma` image).

The two containers share a Docker network, so the CLI reaches the DB **by container name** on port 8000. The DB writes to a **bind-mounted host folder**, so your index survives restarts (captured: both collections came back after `docker compose down` and a new start). The only cloud pieces are two **pay-per-use Vertex AI model endpoints**, reached with a **service-account key** that is mounted from a `secrets/` folder outside the repo. Nothing on GCP keeps running (and billing) after you stop.

```
 YOUR LAPTOP  (Docker Desktop on macOS/Windows, or Docker Engine on Linux; Apple Silicon runs everything natively as arm64)
 +------------------------------------------------------------------------------------------------------------+
 |  ~/AC215/                                  (any parent folder; the two children MUST be siblings)          |
 |  |-- llm-rag/   <- git clone; run `sh docker-shell.sh` from here                                           |
 |  |   |-- cli.py  semantic_splitter.py  agent_tools.py                                                      |
 |  |   |-- input-datasets/books/*.txt      11 books, ~2.8 MB of text                                         |
 |  |   |-- outputs/                        (created) chunks-*.jsonl, embeddings-*.jsonl     (~90 MB)        |
 |  |   `-- docker-volumes/chromadb/        (created, root-owned) chroma.sqlite3 + HNSW index folders (82 MB) |
 |  `-- secrets/llm-service-account.json    (you create; never inside the repo)                               |
 |                                                                                                            |
 |   docker network "llm-rag-network"  (created by Compose, docker-compose.yml:1-3)                           |
 |   +------------------------------------------+            +------------------------------------------+     |
 |   | service llm-rag-cli  (compose run --rm)  |  HTTP      | container llm-rag-chromadb  (stays up!)  |     |
 |   | container llm-rag-llm-rag-cli-run-<id>   |----------->| image chromadb/chroma:latest             |     |
 |   | image llm-rag-cli  <- Dockerfile         | llm-rag-   | Chroma server listening on :8000         |     |
 |   | python 3.12, deps in /.venv (uv sync)    | chromadb   | /data <- bind ./docker-volumes/chromadb  |     |
 |   | /app     <- bind ../llm-rag              | :8000      | env CHROMA_CORS_ALLOW_ORIGINS            |     |
 |   | /secrets <- bind ../secrets              |            +--------------------^---------------------+     |
 |   | env GCP_PROJECT,                         |                published 8000:8000 (host port 8000)         |
 |   |     GOOGLE_APPLICATION_CREDENTIALS       |                                    |                        |
 |   | you type:  python cli.py --<step> ...    |          localhost:8000  <--  curl, and a Chrome tab on     |
 |   +---------------------|--------------------+                         https://ac215-llm-rag.dlops.io     |
 |                         |                                              (/chromaui; CORS-allowed)           |
 +-------------------------|----------------------------------------------------------------------------------+
                           |  HTTPS + OAuth2 access token minted from the service-account key
                           v
 GOOGLE CLOUD  (your project = $GCP_PROJECT)   https://aiplatform.googleapis.com   location "global"  (cli.py:24)
    +-- publishers/google/models/gemini-embedding-001   ":predict"          text(s)  -> 256-number vector(s)
    +-- publishers/google/models/gemini-3.1-flash-lite  "generateContent"   prompt   -> answer text
    (pay per use, billed by the text sent; no VM, bucket or endpoint is created, so nothing to delete in the cloud)


 DATA FLOW
  Indexing (run once per chunk_type; slow, costs a little)
   books/*.txt --chunk--> outputs/chunks-*.jsonl --embed (Vertex, batches of 100)--> outputs/embeddings-*.jsonl
               --load--> Chroma collection "<chunk_type>-collection"  (cosine space)  --> docker-volumes/chromadb/
  Querying (every question; fast, costs ~nothing)
   question --embed (Vertex)--> 256-number vector --Chroma.query(n_results=10, optional filters)--> 10 chunks
            --> prompt = question + chunks --Gemini--> answer
```

---

## 2. Prerequisites and costs

**Accounts and local installs**
- A **GCP account and project with credits/billing**, set up in Tutorial 0 (`ac215-setup/README.md:149-193`).
  - Use an individual account, "not under Harvard Organization" (`ac215-setup/README.md:157`). Org policies there can block service-account key creation.
  - Note your **Project ID**, which differs from the project *name* (`ac215-setup/README.md:188-191`).
- **Docker Desktop** (or Docker Engine plus the Compose v2 plugin), because the script calls `docker compose` with a space (`docker-shell.sh:12`). The README only says "Have Docker installed" (`README.md:47`). The captures used Docker Engine 29.8.2 and Compose v5.6.0.
- **git**, to clone `https://github.com/dlops-io/llm-rag` (`README.md:48`). The clone is over 100 MB, almost all of it history: its `.git` is 103 MB (E21).
- **No local Python is needed.** Everything runs in the container (Python 3.12, `Dockerfile:2`; `requires-python = ">=3.12"`, `pyproject.toml:6`; Python 3.12.15 at the time of recording).
- **Chrome** for the optional web visualisers (`README.md:95-98`, `:162-165`, `:211-214`).

**GCP APIs to enable**
- **Vertex AI API** (`aiplatform.googleapis.com`), in the console or with `gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>` (not in the README). **The README never says to enable it** (Errata E6).
- No other API is used. There is no Cloud Storage call anywhere in the code (`grep -n storage *.py` finds nothing).

**Service account, key and env vars: exactly where the code looks**

| What | Value | Set in / consumed by |
|---|---|---|
| SA name | `llm-service-account` | `README.md:55` |
| Roles | "Storage Admin" + "Gemini Enterprise Agent Platform User (listed as 'Vertex AI User' in older projects)" | `README.md:56-58`. Only the Vertex role is needed; Storage Admin is unused (E5) |
| Key file on host | `../secrets/llm-service-account.json`, a **sibling** of the `llm-rag/` folder | `README.md:62-69`, mount `../secrets:/secrets` at `docker-compose.yml:11` |
| Key path in container | `/secrets/llm-service-account.json` | `export GOOGLE_APPLICATION_CREDENTIALS=...` at `docker-shell.sh:8` → passed through at `docker-compose.yml:14` → read by `google.auth` on the first API call |
| Project ID | `export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID` | `docker-shell.sh:7` → `docker-compose.yml:15` → `GCP_PROJECT = os.environ["GCP_PROJECT"]` at `cli.py:23` |
| Region | `GCP_LOCATION = "global"` (hard-coded) | `cli.py:24`. With `global`, google-genai calls `https://aiplatform.googleapis.com/` (no region prefix) |
| Chroma address | `CHROMADB_HOST = "llm-rag-chromadb"`, `CHROMADB_PORT = 8000` (hard-coded) | `cli.py:30-31`; this is the container name at `docker-compose.yml:20` |

`genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)` runs as soon as `cli.py` starts (`cli.py:35-36`). Because `project` is given, google-genai 1.39.1 does **not** load credentials yet; it loads them lazily on the first request. The captures show both sides of this:
- With `GCP_PROJECT` set and no key file, `--chunk` for `char-split` and `recursive-split` works, and the first `--embed` fails inside `embed_content` with `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` (§4 Step 6).
- With `GCP_PROJECT` *empty* (Compose run without the script), the client calls Application Default Credentials (`google.auth.default()`) at once. `GOOGLE_APPLICATION_CREDENTIALS` is empty too, so even `--chunk` dies at `cli.py:35` with `DefaultCredentialsError: File  was not found.` (§6 G5). If the variable is missing altogether (only possible outside Compose), `cli.py:23` raises `KeyError: 'GCP_PROJECT'`.

**Billable resources and rough cost.** Vertex AI bills the text you send and receive (tokens), not the number of requests; counting calls only tells you how many round trips to expect. Nothing is left running in GCP.

| Run | API calls (from the code's batch sizes) | Input volume (measured) | Rough cost* |
|---|---|---|---|
| `--embed --chunk_type char-split` | 89 `embed_content` calls (8,248 chunks, batch 100, `cli.py:252-253`) | 2.88 M chars ≈ 0.7 M tokens | ~$0.10 |
| `--embed --chunk_type recursive-split` | 148 calls (14,228 chunks; the default 200-char overlap inflates the volume) | 4.10 M chars ≈ 1.0 M tokens | ~$0.15 |
| `--chunk --chunk_type semantic-split` | 528 calls (26,080 sentence windows, batch 50, `semantic_splitter.py:206`) | ~8.0 M chars of 3-sentence windows ≈ 2 M tokens | ~$0.30 |
| `--embed --chunk_type semantic-split` | 92 calls (1,318 chunks, batch 15, `cli.py:249-250`) | ≈ 0.8 M tokens | ~$0.12 |
| `--query` / one `--chat` | 1 embed call (+1 generate call for chat with ~10 × 350 chars of context) | ~1 k tokens | < $0.01 |

\*Assumes about 4 characters per token and a list price of roughly $0.15 per 1 M input tokens for `gemini-embedding-001`. **Check the current Vertex AI pricing page**; prices were not verified for this guide. The semantic-split call and chunk counts were counted with a stand-in for the embedding function that counts calls instead of making them (exercise B7, §8). The whole tutorial, done twice, should cost well under $2 of credits.

**Shutting down afterwards**
1. `exit` the container shell. The CLI container is removed (`--rm`, `docker-shell.sh:12`), but **`llm-rag-chromadb` keeps running** because Compose started it as a dependency (captured `docker ps -a`, §4 Step 8).
2. From `llm-rag/`, run `docker compose down`. It warns that `GCP_PROJECT` and `GOOGLE_APPLICATION_CREDENTIALS` are not set (only the script sets them; `down` needs neither), then stops and removes the Chroma container and `llm-rag-network`. Your index survives in `docker-volumes/chromadb/`.
3. Optional: delete `outputs/` and `docker-volumes/` to reclaim disk. Both are git-ignored (`.gitignore:3-4`). On Linux, `docker-volumes/` needs `sudo`: Docker created the bind-mount folder as root, and the Chroma container (whose image sets no `USER`) writes its files as root (captured `ls -la docker-volumes/chromadb`: `root root`). `outputs/` is owned by uid 1000, the container's `app` user. The images stay until you remove them: `llm-rag-cli` 2.11 GB (its Python base included) and `chromadb/chroma:latest` 826 MB.
4. Key hygiene: the JSON key is a long-lived credential. Keep it only in `secrets/`. When the course ends, delete the key under **IAM & Admin → Service accounts → KEYS**.

---

## 3. Concepts this tutorial teaches

### 3.1 RAG = retrieval + generation (an open-book exam)
- **Explanation.** An LLM only "knows" what was in its training data, frozen at a cutoff. It has never seen your private or niche documents, like the instructor's Tolminc story (in its current form since September 2026, `85bba32`). RAG does **not** change the model. At question time you **retrieve** the few passages most relevant to the question from your own corpus, then **generate** an answer with those passages pasted into the prompt. The README's two figures are exactly these two phases (`README.md:5-11`).
- **Mental model.** Two pipelines that meet at the database.
  - *Indexing* (offline, batch, slow, done once): chunk → embed → store.
  - *Querying* (online, per question, fast): embed question → nearest neighbours → prompt → LLM.
- **Analogy.** A closed-book exam versus an open-book exam where a librarian hands you the 10 most relevant pages first. The student (LLM) is the same; the pages make the difference.
- **Misconception.** "RAG trains or fine-tunes the model on my documents." No weights change. If you delete the collection, the "knowledge" is gone. Fine-tuning is L08.

### 3.2 Chunking: character, recursive, overlap
- **Explanation.** One vector for a whole book (*The Book of Cheese* is 675,515 characters as `cli.py` reads it) averages all its topics, so it cannot match a narrow question precisely. And sending all 11 books (about 2.8 MB, roughly 0.6-0.7 M tokens) with every question is slow and costly, and, as the lecture puts it, gives garbage (A8). So you cut each book into chunks. Each chunk is the unit of retrieval and the unit pasted into the prompt.
  - **`char-split`** (`cli.py:184-194`): `CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator='', strip_whitespace=False)` with `chunk_size = 350` and `chunk_overlap = 20`. With an empty separator the text is split into single characters and greedily re-packed into 350-char windows that step forward 330 characters. The cuts land **mid-word**. Captured on the story: chunk 0 ends `'anized list of things she intended to ac'` and chunk 1 starts `'s she intended to accomplish during her '`; those 20 repeated characters are the overlap, and "accomplish" is whole again in chunk 1.
  - **`recursive-split`** (`cli.py:196-205`): `RecursiveCharacterTextSplitter(chunk_size=chunk_size)` with `chunk_size = 350`. It tries separators in order `["\n\n", "\n", " ", ""]`, so it cuts at paragraph, then line, then word boundaries. It also inherits the library default **`chunk_overlap=200`** (`langchain_text_splitters/base.py`, `TextSplitter.__init__`), so neighbouring chunks share up to 200 characters: captured, the story's chunk 1 starts again with `## Chapter One: The First Slice`, the end of chunk 0. Every chunk ends before 350 characters (median 297, longest 349, exercise Q3).
- **Numbers** (captured with `wc -l`, one line per chunk):
  - char-split gives **8,248** chunks in total, recursive-split **14,228**.
  - The story (7,808 characters) gives **24** char chunks and **35** recursive chunks.
  - For char-split, n = 1 + ⌈(L − 350)/330⌉ = 1 + ⌈7,458/330⌉ = 24; the same formula gives every book's count.
  - Where recursive-split's extra chunks come from (same splitter, overlap varied, exercise B2): overlap 0 → 10,542; overlap 20 → 10,551; the default 200 → 14,228. So about 3,700 come from the hidden overlap and about 2,300 from the shorter, boundary-cut chunks.
- **Mental model.** Chunk size trades precision against context. Small chunks match narrow questions sharply but lose surrounding meaning. Large chunks carry context but blur the vector and eat prompt space. Overlap is insurance against cutting an idea in half.
- **Analogy.** Cutting a long scroll into index cards. char-split uses a ruler and scissors; recursive-split first looks for the gaps between paragraphs.
- **Misconception.** "Smaller chunks are always better" or "overlap is free." Overlap duplicates text: every repeated character is embedded, stored, paid for, and can come back twice in the top 10. The recursive default of 200 characters is why it produces 1.7× as many chunks and 1.4× as many embedded characters.

### 3.3 Embeddings and cosine similarity
- **Explanation.** An embedding model maps text to a point in a high-dimensional space so that texts with similar *meaning* point in similar *directions*.
  - `gemini-embedding-001` natively returns 3,072 numbers. The code asks for **256** via `output_dimensionality` (`cli.py:25-26`, `:76-78`, `:101-102`). The model is trained so that a *prefix* of the vector is still a usable embedding (Matryoshka-style truncation).
  - The truncated vectors are **not unit length**: recorded, the story's 24 vectors have lengths 0.369 to 0.402, and all 8,248 char-split vectors 0.342 to 0.405 (exercise D1).
  - Similarity is the cosine of the angle between two vectors, which ignores length. Chroma reports **cosine distance = 1 − cosine similarity**, so *smaller is closer* (0 to 2; a chunk's own vector comes back at 0.0000).
- **Mental model.** Every chunk is an arrow from the origin. The question is another arrow. Retrieval means "find the arrows with the smallest angle to mine."
- **Analogy.** GPS coordinates for meaning. Two restaurants on the same street have close coordinates even if their names share no letters.
- **Misconceptions.**
  - (a) "Embeddings are keyword matching." They are not. "curd" and "rennet" chunks can be close with no word in common, which is why `where_document={"$contains": ...}` exists as a separate *lexical* filter.
  - (b) "Any two 256-number vectors are comparable." Only vectors from the **same model, same dimension and same settings** live in the same space. Chroma checks only the size: a 768-number query is refused (`Collection expecting embedding with dimension of 256, got 768`), while a 256-number vector from another model would be accepted and give silent garbage (exercise C5).
  - (c) "Cosine or L2, the ranking is the same." Only for unit-length vectors. With these vectors, a brute-force check found the L2 top 10 equal to the cosine top 10 (same order) for only 5.6% of the 8,248 stored vectors used as queries (exercise D1). Keep `"hnsw:space": "cosine"`, or normalise every vector.

### 3.4 The vector database: collection, records, index, persistence
- **Explanation.** Chroma stores **records**: `id`, `embedding`, `document` (the chunk text) and `metadata` (`{"book", "author", "year"}`, `cli.py:132-138`). Records are grouped in a **collection**, one per chunking strategy: `f"{method}-collection"` (`cli.py:277`).
  - The collection is created with `metadata={"hnsw:space": "cosine"}` (`cli.py:287-288`). That picks the distance function for the **HNSW** approximate-nearest-neighbour index. Chroma's default space is L2. The captured collection listing shows the index settings Chroma chose: `"space":"cosine"`, `"max_neighbors":16`, `"ef_construction":100`, `"ef_search":100`.
  - A collection's dimension is fixed by its first insert: the listing shows `"dimension":null` while empty and `"dimension":256` once loaded.
  - Each collection also carries Chroma's own `"embedding_function"` named `"default"`. The tutorial never uses it, because it always passes vectors (see the misconception below).
  - IDs are `hashlib.sha256(x.encode()).hexdigest()[:16]` of the book name, then `"-"`, then the row index (`cli.py:127-130`), so they are deterministic and unique per book (captured: `1021665fac86c5a5-0` … `-9` for *The Complete Book of Cheese*).
  - `load` **deletes and recreates** the collection every time (`cli.py:280-289`). Loading is repeatable but all-or-nothing.
  - The server runs in its own container. Its storage directory `/data` is bind-mounted to `llm-rag/docker-volumes/chromadb` (`docker-compose.yml:23-24`, `README.md:160`). Recorded after both loads: a 59.8 MB `chroma.sqlite3` (documents, metadata, bookkeeping) plus two UUID-named folders, one HNSW index per collection, 82 MB in all, owned by root. Which UUID belongs to which collection is not visible from the folder names.
  - The staff's own copy of this layout is in the repo's history: `68e0bde` committed it under `llmrag/` (with a 90.9 MB `chroma.sqlite3`), and `58dd602` removed it again. That commit came from the `demo-podcast` PR, so it is in `main`'s history even though the PR was later reverted, which is why `.git` is 103 MB.
- **Mental model.** A table of (id, text, metadata, vector), plus a "highway graph" over the vectors that finds nearest neighbours in roughly logarithmic time instead of scanning all 14k rows.
- **Analogy.** A library card catalogue that is shelved by topic-direction instead of by title.
- **Misconception.** "The vector DB understands text." In this tutorial Chroma never computes an embedding. Every vector comes from Vertex AI, and `add()`/`query()` receive explicit `embeddings=`/`query_embeddings=` (`cli.py:151-156`, `:354-359`). If you call `collection.query(query_texts=[...])` instead, Chroma embeds the text with *its own* default function, a small local model (downloaded first, 79 MB) that makes 384 numbers, and the query is refused: `Collection expecting embedding with dimension of 256, got 384` (exercise C5).

### 3.5 Retrieval: top-k, metadata filters and document filters
- **Explanation.** `collection.query(query_embeddings=[query_embedding], n_results=10)` (`cli.py:380-383`) returns the 10 nearest records. Two optional filters are applied **before** ranking:
  - `where={"book": "The Complete Book of Cheese"}` filters on metadata;
  - `where_document={"$contains": search_string}`, with `search_string = "Italian"` (`cli.py:353`), is a case-sensitive substring test on the chunk text.

  The result is a dict of **lists of lists**, one inner list per query: `ids`, `distances`, `metadatas`, `documents`, plus `embeddings`, `uris` and `data` (all `None` unless requested) and `included` (the default `["metadatas", "documents", "distances"]`; chromadb 1.1.0 `api/models/Collection.py:183-187`, `api/fastapi.py:653-662`). That is why `chat()` reads `results["documents"][0]` (`cli.py:386`, `:390`). No query output was captured (it needs a key); the captured `--get` output shows the same dict shape without `distances`.
- **Mental model.** Filters are a mask that greys out most of the points. Top-k then picks the nearest *among what is left*, however far away it is.
- **Analogy.** Asking a librarian for "the 10 pages most about Tolminc, but only from *The Complete Book of Cheese*, and only pages containing the word *Italian*". You get 10 pages, and none of them is about Tolminc.
- **Misconception.** "Filters boost relevance." They constrain; they do not rank. Recorded with Chroma itself (§4 Step 9):
  - The active `--query` (`cli.py:352-361`) combines both filters: of 8,248 char-split chunks, 1,355 are from that book, 64 of those contain "Italian", and **0** contain "Tolminc" (only 3 chunks in the whole collection contain the word).
  - With a stand-in query vector (a stored story chunk), no filter returns 10 story chunks at distances 0.0000 to 0.1627; the code's filters return 10 chunks of *The Complete Book of Cheese* at 0.2833 to 0.3123.
  - Top-k returns k results whenever k records survive the filters, relevant or not. Nothing in this code applies a distance threshold.

### 3.6 Augmented generation: building the prompt
- **Explanation.** The "G" in RAG is ordinary prompt construction. `chat()` builds `INPUT_PROMPT` as the question followed by the 10 chunks joined with newlines (`cli.py:388-391`). It sends that as the user content to `gemini-3.1-flash-lite` (`cli.py:394-396`).
  - A carefully written `SYSTEM_INSTRUCTION` ("Your responses are based solely on the information provided in the text chunks…", `cli.py:40-58`) is **defined but never passed** to the model (Errata E1). Checked without a key by capturing the request just before it leaves: as committed, its body holds only `contents` (exercise Q5).
  - So the model sees "question + some cheese text" with **no instruction to stay inside the text**, and without the book names (only `documents` go in, not `metadatas`). It may blend in its own knowledge. Tolminc is a real Alpine cheese, but today's story is fiction ("A fictional tale inspired by Alpine cheesemaking", line 4 of the book): details from the story came from your chunks, real-world rules for the cheese from the model's memory.
- **Mental model.** The LLM is a stateless function of its input tokens. Grounding is only as strong as (a) what you retrieved and (b) what you told the model to do with it.
- **Analogy.** Handing an expert a stack of photocopies with no note. Do they answer from the pages or from memory? You did not say.
- **Misconception.** "The LLM queries the vector DB." In plain RAG the *code* retrieves; the model never sees the database. Letting the model *choose* which retrieval to make, via function calling, is the **agent** pattern of L06 (`cli.py:421-478`, `README.md:242-271`).

### 3.7 Semantic chunking
- **Explanation.** Instead of a ruler, cut where the *topic changes* (`semantic_splitter.py:99-109`, credited to Greg Kamradt at `semantic_splitter.py:102-105`):
  1. split the book into sentences with the regex `(?<=[.?!])\s+` (`semantic_splitter.py:118`, `:217`);
  2. for each sentence, build a window of itself plus one neighbour on each side (`buffer_size=1`, `combine_sentences`, `semantic_splitter.py:15-53`);
  3. embed every window through **the same Vertex function** (`embedding_function=generate_text_embeddings`, `cli.py:209-210`; called with `batch_size=50`, `semantic_splitter.py:206`);
  4. compute the cosine distance between consecutive windows (`semantic_splitter.py:56-85`);
  5. cut wherever the distance exceeds the **95th percentile** of all distances (`BREAKPOINT_DEFAULTS["percentile"] = 95`, `semantic_splitter.py:91-96`; threshold `:137-141`; cut points `:239-243`).

  So about 5% of sentence gaps become chunk boundaries, and chunk lengths vary widely. The story's 108 sentences give 107 gaps; the 6 above the 95th percentile become cuts, so 7 chunks, whatever the vectors' values (exercise B7).
- **Mental model.** A seismograph of meaning. Draw the distance-to-next-sentence curve over the book; the tallest 5% of spikes are the scene changes.
- **Analogy.** Splitting a podcast transcript wherever the hosts change topic instead of every 5 minutes.
- **Misconception.** "Semantic chunking is free and strictly better." Chunking itself now costs API calls: 26,080 sentence windows, 528 embedding calls for the corpus, and it needs your key already at `--chunk` (captured: the run fails inside the chunk step, §4 Step 12). Chunks also vary a lot in size; some will be thousands of characters. And since 5% of gaps are always cut, even a single-topic book gets the same *fraction* of cuts.

### 3.8 The ops shape: a two-container Compose app with mounts and secrets
- **Explanation.** `docker-shell.sh` exports the two GCP env vars (plus `IMAGE_NAME`) and runs `docker compose run --rm $IMAGE_NAME` with `IMAGE_NAME="llm-rag-cli"` (`docker-shell.sh:7-12`). Compose then, in the order the capture shows:
  - pulls `chromadb/chroma:latest` and creates the network `llm-rag-network` (`docker-compose.yml:1-3`);
  - creates `llm-rag-chromadb` because of `depends_on` (`:16-17`), with the host port published (`8000:8000`, `:21-22`). Docker creates the missing bind-mount source `docker-volumes/chromadb/` on your laptop as root;
  - looks for the image `llm-rag-cli`; when it is missing it first tries Docker Hub (`failed to resolve reference "docker.io/library/llm-rag-cli:latest": … not found`), then builds it from the Dockerfile (`:7-8`). Only when the image does not exist yet;
  - starts an interactive CLI container with the repo bind-mounted at `/app` and the secrets at `/secrets` (`:10-12`). It is named `llm-rag-llm-rag-cli-run-<id>`: `container_name: llm-rag-cli` (`:9`) is not used by `docker compose run`.

  Inside the network the CLI reaches the database at `http://llm-rag-chromadb:8000` by name (`cli.py:30-31`; captured `getent hosts llm-rag-chromadb` → `172.19.0.2`). The published host port exists for *you*: curl, the browser Chroma UI and scripts on the host. The CLI does not need it.
- **Why the venv lives at `/.venv`.** The Dockerfile installs dependencies into `/.venv` (`UV_PROJECT_ENVIRONMENT=/.venv`, `Dockerfile:18`; `uv sync --frozen`, `:45`). The bind mount of `../llm-rag` over `/app` therefore cannot hide them. You can edit `cli.py` on your laptop and rerun it in the container without rebuilding.
- **Mental model.** The CLI container is a disposable workbench; the DB container is a long-running appliance with its data on your disk. Secrets come in through a side door (a mount plus an env var) and are never baked into an image or committed.
- **Misconception.** "`--rm` cleans everything up." It removes only the CLI container. Chroma keeps running until `docker compose down`. A second misconception is "my index updates itself when the books change". It does not: the index is a snapshot, so re-run chunk → embed → load. The staff's own `out.txt` shows chunks from a version of the Tolminc book that no longer exists (E7).

---

## 4. Step-by-step walkthrough

Steps follow the README order. Commands in `bash` blocks are copied verbatim from the README unless marked *(extra)*; extras are typed exactly as captured. Each step gives the action, what happens under the hood, a checkpoint and what to do if it fails.

**About the outputs below.** They are real, trimmed (first and last lines, with `…` between) from the 2026-10-16 captures in the video folder's [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l05-rag/assets/terminal) (file names given with each block; `[exit N]` lines omitted, exit statuses mentioned where they matter). Labels:
- *Captured*: a real run of the command shown.
- *Recorded*: a real run, but on the staff's own embeddings files from the repo history (`68e0bde`), because embedding needs a key. Their chunk files are byte-identical to the ones `--chunk` made here, so their vectors are what `--embed` makes for these chunks.
- *Expected (from the code)*: what a run with your key prints, read off the `print` calls in `cli.py`. No such run was recorded, and the README prints no output for any step, so these never contain invented values.

On your laptop:
- **There was no Google key in the captures.** Every command that calls Vertex AI stops at `DefaultCredentialsError` there. With your key in `secrets/`, the same commands do their job.
- The laptop was a stand-in running Linux as user `student` in `~/AC215`, with Docker Engine 29.8.2 and Compose v5.6.0. Your prompt, paths and a few shell messages (zsh on a Mac, Docker Desktop's progress display) differ. On Apple Silicon the banner says `Architecture: aarch64`.
- Container ids, collection UUIDs, heartbeat values, times and the order in which `glob` returns the books change on every run. The capture's Python base image was rebuilt with a proxy certificate, so its build log shows no base-image download; your first build pulls `python:3.12-slim-bookworm` (about 48 MB) first.
- Long DataFrame and traceback lines are cut on the right; pandas prints its tables for an 80-column terminal.

### Step 0. Lay out the folders (not in README beyond `README.md:48`, `:64-69`)
```bash
cd ~/AC215                         # (extra) or wherever you keep course repos
git clone https://github.com/dlops-io/llm-rag.git
mkdir secrets; ls                  # (extra)
```
- **Under the hood.** `docker-compose.yml:11-12` mounts `../secrets` and **`../llm-rag`**, both relative to the compose file. So the repo folder must be named exactly `llm-rag`, and `secrets/` must sit next to it. The README links the repo (`README.md:48`) and shows the layout (`README.md:64-69`) but prints no clone command.
- **Checkpoint.** Captured (`laptop/02-clone.txt`, `laptop/03-x-mkdir-secrets.txt`):
  ```text
  $ git clone https://github.com/dlops-io/llm-rag.git
  Cloning into 'llm-rag'...
  $ mkdir secrets; ls
  llm-rag  secrets
  ```
- **If it fails.** If you downloaded a ZIP (folder `llm-rag-main`) or cloned under another name, rename it to `llm-rag`. Otherwise Docker mounts an empty folder over `/app` and the container dies at once (§6 G1, captured there).

### Step 1. Service account and key (`README.md:52-69`)
1. Enable the **Vertex AI API** in your project (not in README, see §2).
2. In **IAM & Admin → Service accounts**, create `llm-service-account` (`README.md:54-55`).
3. Grant the roles in `README.md:56-58`. For this code, **Vertex AI User** (the README's "Gemini Enterprise Agent Platform User") is the one that matters.
4. Open **KEYS → ADD KEY → Create new key → JSON**, then copy the file into `secrets/` and rename it **`llm-service-account.json`** (`README.md:60-62`).
- **Not captured.** These are console clicks, and the recording had no GCP account.
- **Checkpoint (not in README).** `ls ../secrets` from inside `llm-rag/` prints `llm-service-account.json`. `grep project_id ../secrets/llm-service-account.json` shows the project the key belongs to; the next step must use the same ID.
- **If it fails.** If "Create key" is greyed out or blocked by an org policy, you are probably in an organisation-managed project. Use your personal project (`ac215-setup/README.md:157`).

### Step 2. Point the script at your project (`README.md:79-80`)
```bash
cd llm-rag                         # (extra) README step 1, in words: "inside the llm-rag folder"
ls -a; git log --oneline -1        # (extra)
du -sh .git; git count-objects -vH | grep size-pack   # (extra)
```
- Edit **`docker-shell.sh:7`**: replace `ac215-project` in `export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID` with your **Project ID**.
- Leave `docker-shell.sh:8` alone. It is the in-container path `/secrets/llm-service-account.json`.
- **Checkpoint.** Captured (`laptop/05-x-ls.txt`, `05b-x-git-size.txt`, `06-x-edit-gcp-project.txt`; the edit used the placeholder `your-project-id`, yours is your real ID):
  ```text
  $ ls -a; git log --oneline -1
  .           Dockerfile      docker-compose.yml    input-datasets        uv.lock
  ..          README.md       docker-entrypoint.sh  out.txt
  .git        agent_tools.py  docker-shell.sh       pyproject.toml
  .gitignore  cli.py          images                semantic_splitter.py
  e17a39f (HEAD -> main, origin/main, origin/HEAD) Merge pull request #2 …
  $ du -sh .git; git count-objects -vH | grep size-pack
  103M	.git
  size-pack: 102.45 MiB
  $ git diff docker-shell.sh
  …
  -export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
  +export GCP_PROJECT="your-project-id" # CHANGE TO YOUR PROJECT ID
   export GOOGLE_APPLICATION_CREDENTIALS="/secrets/llm-service-account.json"
   export IMAGE_NAME="llm-rag-cli"
  ```
  The 103 MB `.git` is the reverted PR's staff database and `outputs/`, still in the history (E21).
- **If you skip this.** Every Vertex call goes to the course project `ac215-project`, where your SA has no rights, and you get a 403 PERMISSION_DENIED (§6 G3).

### Step 3. Start the containers (`README.md:75-85`)
```bash
sh docker-shell.sh
```
- **Under the hood.**
  1. `set -e` (`docker-shell.sh:4`), then the two env vars are exported (`:7-8`).
  2. `docker compose run --rm $IMAGE_NAME` with `IMAGE_NAME="llm-rag-cli"` (`:9`, `:12`); `IMAGE_NAME` happens to equal the *service* name. Compose then:
     - pulls `chromadb/chroma:latest` (`docker-compose.yml:19`), creates the network `llm-rag-network` (`docker-compose.yml:1-3`) and creates `llm-rag-chromadb` with `8000:8000` and `./docker-volumes/chromadb:/data` (`:20-24`). The `docker-volumes/chromadb` folder appears on your host, created by Docker as root;
     - on the **first run only**, looks for the image `llm-rag-cli`, first on Docker Hub (the harmless `not found` below), then builds it from the Dockerfile: `python:3.12-slim-bookworm` (`Dockerfile:2`), apt packages (`Dockerfile:4`, `:22-28`), `pip install uv` (`Dockerfile:30`), user `app` uid 1000 (`Dockerfile:31`), `uv sync --frozen` into `/.venv` (`Dockerfile:42-45`), then `COPY . ./` (`Dockerfile:48`);
     - starts the CLI container with `/app` and `/secrets` mounted and the two env vars passed through (`:10-15`). Its entrypoint (`Dockerfile:51`) runs `docker-entrypoint.sh`.
- **Checkpoint.** Captured (`laptop/07-docker-shell.txt`, lines joined where the 80-column terminal wrapped them):
  ```text
  $ sh docker-shell.sh
  [+] run 9/9
   ✔ Image chromadb/chroma:latest Pulled                                     12.1s
   ✔ Network llm-rag-network      Created                                     0.0s
   ✔ Container llm-rag-chromadb   Created                                     1.4s
  Image llm-rag-cli Pulling
  Image llm-rag-cli failed to resolve reference "docker.io/library/llm-rag-cli:latest": docker.io/library/llm-rag-cli:latest: not found
  Image llm-rag-cli Building
  [+] Building 81.5s (13/13) FINISHED
  …
   => => transferring context: 112.26MB                                      0.6s
   => [2/6] RUN set -ex;     for i in $(seq 1 8); do mkdir -p "/usr/share/  20.2s
   => [3/6] WORKDIR /app                                                     0.1s
   => [4/6] COPY --chown=app:app pyproject.toml uv.lock* ./                  0.0s
   => [5/6] RUN uv sync --frozen                                             6.7s
   => [6/6] COPY --chown=app:app . ./                                        0.4s
   => exporting to image                                                    53.9s
  …
  Image llm-rag-cli Built
  Container llm-rag-llm-rag-cli-run-90678535ddef Creating
  Container llm-rag-llm-rag-cli-run-90678535ddef Created
  Container is running!!!
  Architecture: x86_64
  Environment ready! Virtual environment activated.
  Python version: Python 3.12.15
  UV version: uv 0.13.1 (x86_64-unknown-linux-gnu)
  Activating virtual environment...
  app@92c5bfd26089:/app$
  ```
  - The `failed to resolve reference … not found` line looks like an error but isn't: Compose v5.6.0 asks Docker Hub for an image called `llm-rag-cli`, finds none, and builds it (G24).
  - The build context is **112.26 MB**, almost all of it `.git`; there is no `.dockerignore` (G15).
  - The banner says "activated" three lines before it activates (`docker-entrypoint.sh:6` vs `:12`, E12): cosmetic. The part after `app@` is the container id; it changes every run.
  - You are now at a bash prompt in `/app`, running as user `app` (`USER app` / `WORKDIR /app`, `Dockerfile:38-39`; the prompt is the `exec /bin/bash` at `docker-entrypoint.sh:15`).
- **Optional checks** *(extra)* in a second host terminal, in `~/AC215/llm-rag`. Captured (`laptop/08-x-docker-ps.txt`, `09`, `10`, `11`, `11b`, `12`, `12b`, `13`, `14`, `14b`, `15`):
  ```text
  $ docker ps
  CONTAINER ID   IMAGE                    COMMAND                  CREATED              STATUS              PORTS                    NAMES
  92c5bfd26089   llm-rag-cli              "/bin/bash docker-en…"   4 seconds ago        Up 1 second                                  llm-rag-llm-rag-cli-run-90678535ddef
  38d414943c8a   chromadb/chroma:latest   "dumb-init -- chroma…"   About a minute ago   Up About a minute   0.0.0.0:8000->8000/tcp   llm-rag-chromadb
  $ docker network ls
  NETWORK ID     NAME              DRIVER    SCOPE
  …
  7bdcdbad6ad5   llm-rag-network   bridge    local
  …
  $ curl http://localhost:8000/api/v2/heartbeat
  {"nanosecond heartbeat":1792112033392283593}
  $ curl http://localhost:8000/api/v2/version
  "1.0.0"
  $ docker exec llm-rag-chromadb chroma --version; docker image inspect chromadb/chroma:latest --format '{{index .RepoDigests 0}} created {{.Created}}'
  chroma 1.4.4
  chromadb/chroma@sha256:1e0b73a187a28757c572acba508c46f48c9e8b0acaf5c20e6d95cdedce1acdf6 created 2026-05-05T01:49:45.652638163Z
  $ curl -si -H 'Origin: https://ac215-llm-rag.dlops.io' http://localhost:8000/api/v2/heartbeat
  HTTP/1.1 200 OK
  …
  access-control-allow-origin: https://ac215-llm-rag.dlops.io
  …
  $ curl -si -H 'Origin: https://example.com' http://localhost:8000/api/v2/heartbeat
  HTTP/1.1 200 OK
  content-type: application/json
  vary: origin, access-control-request-method, access-control-request-headers
  content-length: 44
  …
  $ ls -la docker-volumes/chromadb
  total 192
  drwxr-sr-x 2 root root   4096 Oct 16 00:52 .
  drwxr-sr-x 3 root root   4096 Oct 16 00:52 ..
  -rw-r--r-- 1 root root 188416 Oct 16 00:52 chroma.sqlite3
  $ docker images
  IMAGE                       ID             DISK USAGE   CONTENT SIZE   EXTRA
  chromadb/chroma:latest      1e0b73a187a2        826MB          176MB   U
  llm-rag-cli:latest          3b31b15cf50b       2.11GB          537MB   U
  python:3.12-slim-bookworm   60c8fd1dbf1f        198MB         47.8MB
  $ docker run --rm --entrypoint bash llm-rag-cli -c 'du -sh /app/.git; du -sh /.venv; ls -la /app/docker-volumes/chromadb'
  103M	/app/.git
  439M	/.venv
  …
  -rw-r--r-- 1 app app 188416 Oct 16 00:52 chroma.sqlite3
  $ docker inspect llm-rag-llm-rag-cli-run-90678535ddef --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'; docker inspect llm-rag-chromadb --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
  /home/student/AC215/llm-rag -> /app
  /home/student/AC215/secrets -> /secrets

  /home/student/AC215/llm-rag/docker-volumes/chromadb -> /data
  ```
  What these show:
  - The CLI container is called `llm-rag-llm-rag-cli-run-<id>`, not `llm-rag-cli`: `container_name: llm-rag-cli` (`docker-compose.yml:9`) is not used by `docker compose run` (E19). Only Chroma publishes a port.
  - Chroma's version strings disagree: the tag is `latest` (on Docker Hub the same digest as `1.5.9`), the server says `chroma 1.4.4`, the API `"1.0.0"`, and the client library is 1.1.0. It works; pin it anyway (G10).
  - Chroma's CORS setting (`docker-compose.yml:25-26`) answers the course's site with an `access-control-allow-origin` header and another site without one. That is how the course's Chroma UI page can read your local database from Chrome.
  - Docker created `docker-volumes/chromadb/` for the bind mount before the CLI image was built, as root, and Chroma wrote a fresh `chroma.sqlite3` into it. With no `.dockerignore`, `COPY . ./` then copied both that file and the 103 MB `.git` into the image (G15). The bind mount hides both at run time.
  - The image sizes: 2.11 GB for `llm-rag-cli` (the Python base's layers are part of it, not extra) and 826 MB for Chroma.
- **Inside the container** *(extra)*. Captured (`cli-container/00-x-whoami.txt`, `01`, `02`, `03`, `04`; these ran in the same container, at the `app@92c5bfd26089:/app$` prompt):
  ```text
  $ whoami; pwd; which python; python --version; uv --version
  app
  /app
  /.venv/bin/python
  Python 3.12.15
  uv 0.13.1 (x86_64-unknown-linux-gnu)
  $ echo GCP_PROJECT=$GCP_PROJECT; echo GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS; ls -la /secrets
  GCP_PROJECT=your-project-id
  GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json
  total 8
  drwxr-sr-x 2 app  app  4096 Oct 16 00:52 .
  drwxr-xr-x 1 root root 4096 Oct 16 00:53 ..
  $ ls
  Dockerfile      docker-compose.yml    images          semantic_splitter.py
  README.md       docker-entrypoint.sh  input-datasets  uv.lock
  agent_tools.py  docker-shell.sh       out.txt
  cli.py          docker-volumes        pyproject.toml
  $ uv pip list 2>/dev/null | grep -E '^(chromadb|google-genai|google-auth|langchain|langchain-community|langchain-text-splitters|numpy|pandas|openai|openai-agents) '
  chromadb                                 1.1.0
  google-auth                              2.41.1
  google-genai                             1.39.1
  langchain                                0.3.27
  …
  pandas                                   2.3.3
  $ getent hosts llm-rag-chromadb; curl -s http://llm-rag-chromadb:8000/api/v2/heartbeat; echo
  172.19.0.2      llm-rag-chromadb
  {"nanosecond heartbeat":1792112035919998087}
  ```
  Your `/secrets` should list `llm-service-account.json`; the capture's was empty. `docker-volumes` already shows up in `/app`, because the repo folder is bind-mounted. The name `llm-rag-chromadb` resolves only on the Compose network.
- **If it fails.**
  - `port is already allocated`: see G6.
  - `container name "/llm-rag-chromadb" is already in use`: see G7.
  - `docker-entrypoint.sh: No such file or directory`: see G1.
  - Compose warns `The "GCP_PROJECT" variable is not set`: you ran `docker compose` directly instead of the script (G5).

### Step 4. Chunk: character splitting (`README.md:91-104`)
```bash
python cli.py --chunk --chunk_type char-split
```
- **Under the hood.**
  - `main()` prints the parsed args and calls `chunk("char-split")` (`cli.py:481-485`).
  - `chunk()` creates `outputs/` (`:168`), globs `input-datasets/books/*.txt` (`:171`) and derives `book_name = filename.split(".")[0]` (`:178`). That truncates one title (E8).
  - It splits with `CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator='', strip_whitespace=False)` with `chunk_size = 350` and `chunk_overlap = 20` (`:184-193`).
  - It writes `outputs/chunks-char-split-<book>.jsonl`, one JSON object `{"chunk": …, "book": …}` per line (`:217-227`).
  - **No API call is made**, so no key is needed.
- **Checkpoint.** Captured (`cli-container/10-chunk-char-split.txt`, 7 s):
  ```text
  $ python cli.py --chunk --chunk_type char-split
  CLI Arguments: Namespace(chunk=True, embed=False, load=False, query=False, chat=False, get=False, agent=False, chunk_type='char-split')
  chunk()
  Number of files to process: 11
  Processing file: input-datasets/books/The Complete Book of Cheese.txt
  Number of chunks: 1355
  Shape: (1355, 2)
                                                 chunk                         book
  0  The Project Gutenberg eBook of The Complete B...  The Complete Book of Cheese
  1   ebook or online\nat www.gutenberg.org. If you...  The Complete Book of Cheese
  …
  Processing file: input-datasets/books/Tolminc Cheese.txt
  Number of chunks: 24
  Shape: (24, 2)
  …
  Processing file: input-datasets/books/Dairying exemplified, or, The business of cheese-making.txt
  Number of chunks: 545
  Shape: (545, 2)
  …
  ```
  Eleven blocks of `Processing file:` / `Number of chunks:` / `Shape:` / a DataFrame head, in whatever order `glob` returns the files. Row 0 of every Gutenberg book is the Project Gutenberg header: these books start with a header and end with a licence, both chunked like the rest (G23).
- **Extra checks** *(extra)*. Captured (`cli-container/11-x-wc-char-split.txt`, `12-x-overlap-char-split.txt`, `laptop/16-x-outputs-on-laptop.txt`):
  ```text
  $ wc -l outputs/chunks-char-split-*.jsonl
      401 outputs/chunks-char-split-Cheese and its economical uses in the diet.jsonl
      178 outputs/chunks-char-split-Cottage Cheese Recipe Book.jsonl
      545 outputs/chunks-char-split-Dairying exemplified, or, The business of cheese-making.jsonl
      395 outputs/chunks-char-split-Hand-book on cheese making.jsonl
      640 outputs/chunks-char-split-Hints on cheese-making, for the dairyman, the factoryman, and the manufacturer.jsonl
     2047 outputs/chunks-char-split-The Book of Cheese.jsonl
     1355 outputs/chunks-char-split-The Complete Book of Cheese.jsonl
      522 outputs/chunks-char-split-The book of The Cheese Being traits and stories of Ye Olde Cheshire Cheese.jsonl
      636 outputs/chunks-char-split-Theres Pippins and Cheese to Come.jsonl
       24 outputs/chunks-char-split-Tolminc Cheese.jsonl
     1505 outputs/chunks-char-split-Womans Institute Library of Cookery.jsonl
     8248 total
  $ python -c "import json; c = [json.loads(l)['chunk'] for l in open('outputs/chunks-char-split-Tolminc Cheese.jsonl')]; print(len(c)); print(repr(c[0][-40:])); print(repr(c[1][:40]))"
  24
  'anized list of things she intended to ac'
  's she intended to accomplish during her '
  $ ls -la outputs | head -5
  total 8372
  drwxrwsrwx 2 student student    4096 Oct 16 00:54 .
  drwxr-sr-x 8 student student    4096 Oct 16 00:54 ..
  -rw-rw-rw- 1 student student  171164 Oct 16 00:54 chunks-char-split-Cheese and its economical uses in the diet.jsonl
  -rw-rw-rw- 1 student student   74261 Oct 16 00:54 chunks-char-split-Cottage Cheese Recipe Book.jsonl
  ```
  - pandas writes a trailing newline, so the line count equals the chunk count.
  - Chunk 0 stops two letters into "accomplish"; chunk 1 backs up 20 characters, so the word is whole again: the mid-word cut and the overlap of §3.2.
  - The files land on your laptop through the bind mount, owned by you (the container's `app` is uid 1000, like the capture's `student`; the `rw-rw-rw-` modes come from the capture's umask). The Woman's Institute file is named after the truncated title (E8).
- **If it fails.**
  - `KeyError: 'GCP_PROJECT'` at `cli.py:23`: you are not in the container started by the script.
  - `DefaultCredentialsError: File  was not found.` already here: you started with `docker compose run` instead of the script (G5).
  - `PermissionError … 'outputs'` on Linux: see G14.
- **Optional:** the chunk visualiser at https://ac215-llm-rag.dlops.io/chunkviz (`README.md:95`), in Chrome.

### Step 5. Chunk: recursive splitting (`README.md:106-110`)
```bash
python cli.py --chunk --chunk_type recursive-split
```
- **Under the hood.** `RecursiveCharacterTextSplitter(chunk_size=chunk_size)` with `chunk_size = 350` (`cli.py:196-205`), with the library defaults: separators `["\n\n", "\n", " ", ""]`, `chunk_overlap=200`, `strip_whitespace=True`. It writes `outputs/chunks-recursive-split-<book>.jsonl`.
- **Checkpoint.** Captured (`cli-container/13-chunk-recursive-split.txt`, 2 s; `14-x-wc-recursive-split.txt`; `15-x-recursive-chunks.txt`; `16-x-ls-outputs.txt`):
  ```text
  $ python cli.py --chunk --chunk_type recursive-split
  CLI Arguments: Namespace(chunk=True, embed=False, load=False, query=False, chat=False, get=False, agent=False, chunk_type='recursive-split')
  chunk()
  Number of files to process: 11
  Processing file: input-datasets/books/The Complete Book of Cheese.txt
  Number of chunks: 2147
  …
  Processing file: input-datasets/books/Tolminc Cheese.txt
  Number of chunks: 35
  …
  $ wc -l outputs/chunks-recursive-split-*.jsonl
  …
     3569 outputs/chunks-recursive-split-The Book of Cheese.jsonl
     2147 outputs/chunks-recursive-split-The Complete Book of Cheese.jsonl
  …
       35 outputs/chunks-recursive-split-Tolminc Cheese.jsonl
     2623 outputs/chunks-recursive-split-Womans Institute Library of Cookery.jsonl
    14228 total
  $ python -c "import json; c = [json.loads(l)['chunk'] for l in open('outputs/chunks-recursive-split-Tolminc Cheese.jsonl')]; print(len(c)); print(c[0]); print('---'); print(c[1]); print('---'); print(c[2])"
  35
  …
  ## Chapter One: The First Slice

  The first thing Mara noticed was that nobody hurried.
  ---
  ## Chapter One: The First Slice

  The first thing Mara noticed was that nobody hurried.

  She had arrived at her grandfather’s house with a suitcase, a laptop, and a carefully organized list of things she intended to accomplish during her visit. Before she could explain any of them, he placed a wooden board on the kitchen table.
  ---
  On it sat bread, two apples, and a wedge of cheese.
  …
  $ ls outputs | head -4; ls outputs | wc -l; du -sh outputs
  …
  22
  8.2M	outputs
  ```
  - Chunk 0 is the story's header through "nobody hurried."; chunk 1 **starts again** at "## Chapter One…": that repetition is the default overlap of up to 200 characters, which the README never mentions (E14). Every cut falls between words.
  - 14,228 chunks against char-split's 8,248, with the same chunk size: about 3,700 of the difference come from the overlap, the rest from the shorter, boundary-cut chunks (§3.2).
- **If it fails.** Same as step 4.

### Step 6. Embed both chunk sets (`README.md:122-138`)
```bash
python cli.py --embed --chunk_type char-split
python cli.py --embed --chunk_type recursive-split
```
- **Under the hood.**
  - `embed()` (`cli.py:230-264`) reads each `chunks-<type>-*.jsonl` (`:234-235`) and calls `generate_text_embeddings(chunks, EMBEDDING_DIMENSION, batch_size=100)` (`:252-253`).
  - That function loops over batches of 100 (`:91-92`) and calls `llm_client.models.embed_content(...)` with `model=EMBEDDING_MODEL` (`"gemini-embedding-001"`), `contents=batch` and `config=types.EmbedContentConfig(output_dimensionality=dimensionality)` (256) (`:98-103`). On Vertex, google-genai 1.39.1 sends this as a `:predict` request with one instance per text.
  - On `errors.APIError` it retries up to 5 times, waiting 5, 10, 20, 40 and 80 s (`:108-119`), printing `API error (code: …): …. Retrying in N seconds (attempt k/5)...` each time; after the 5th retry it prints `Failed to generate embeddings after 5 attempts. …` and re-raises.
  - It adds an `embedding` column, **sleeps 5 s per book** (`:256`) and writes `outputs/embeddings-<type>-<book>.jsonl` (`:262-264`).
  - This is the first command that calls Google, so it is the first that needs your key: credentials are loaded on the first request, not at start-up.
- **Checkpoint without a key.** Captured (`cli-container/20-embed-char-split.txt`, exit 1; the traceback is trimmed):
  ```text
  $ python cli.py --embed --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=True, load=False, query=False, chat=False, get=False, agent=False, chunk_type='char-split')
  embed()
  Number of files to process: 11
  Processing file: outputs/chunks-char-split-Hand-book on cheese making.jsonl
  Shape: (395, 2)
  …
  Traceback (most recent call last):
    File "/app/cli.py", line 551, in <module>
      main(args)
    File "/app/cli.py", line 488, in main
      embed(method=args.chunk_type)
    File "/app/cli.py", line 252, in embed
      embeddings = generate_text_embeddings(
  …
    File "/app/cli.py", line 98, in generate_text_embeddings
      response = llm_client.models.embed_content(
  …
    File "/.venv/lib/python3.12/site-packages/google/genai/_api_client.py", line 906, in _access_token
      self._credentials, project = load_auth(project=self.project)
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.
  ```
  It reads the first book, then stops at the missing key file; no `embeddings-*` file is written (captured `ls outputs | grep '^embeddings-' | wc -l` → `0`). The same happened, for the same reason, with `recursive-split`.
- **Checkpoint with your key** *(expected, from the code)*.
  - For each book: `Processing file: outputs/chunks-char-split-….jsonl`, `Shape: (N, 2)` and the DataFrame head (`cli.py:240-244`), a 5-second pause, then `Shape: (N, 3)` and a head with an `embedding` column of 256-number lists (`:259-260`).
  - 89 calls plus 55 s of sleeps for char-split, and 148 calls for recursive-split.
  - Afterwards `ls outputs | grep '^embeddings-' | wc -l; ls -la /secrets` *(extra)* should print `22` (11 per chunk type) and your key file.
  - The `embeddings-*.jsonl` files are much bigger than the chunk files: the staff's 22 files are 82 MB, against 8.2 MB for the 22 chunk files.
- **No key yet?** *(extra, optional, host)* The staff committed their whole `outputs/` folder, made with `gemini-embedding-001` and 256 numbers per chunk, in `68e0bde`; the files are gone from `main` but still in every clone's history. From `~/AC215/llm-rag`, this copies their 22 embeddings files into your `outputs/`, so the load steps and the checks below can run (captured, `recorded-embeddings/00-x-copy-staff-embeddings.txt`):
  ```bash
  git ls-tree -z --name-only 68e0bde llmrag/outputs/ | tr "\0" "\n" | grep "/embeddings-" | while IFS= read -r f; do git show "68e0bde:$f" > "outputs/${f##*/}"; done; ls outputs | grep "^embeddings-" | wc -l; du -ch outputs/embeddings-* | tail -1
  ```
  ```text
  22
  82M	total
  ```
  These are the staff's vectors from their own Vertex AI call, not yours; querying and chatting still need your key. Delete them (`rm outputs/embeddings-*`) before you run `--embed` yourself, or let `--embed` overwrite them.
- **Extra check: are the vectors unit length?** *(extra, container)* Recorded (`recorded-embeddings/06-x-vector-norms.txt`):
  ```bash
  python - <<'EOF'
  import json, math
  rows = [json.loads(l) for l in open("outputs/embeddings-char-split-Tolminc Cheese.jsonl")]
  norms = [math.sqrt(sum(x * x for x in r["embedding"])) for r in rows]
  print(len(rows), "rows,", len(rows[0]["embedding"]), "numbers each")
  print("first 5:", [round(x, 4) for x in rows[0]["embedding"][:5]])
  print(f"vector lengths: min {min(norms):.3f}, max {max(norms):.3f}")
  EOF
  ```
  ```text
  24 rows, 256 numbers each
  first 5: [0.0139, 0.0075, 0.0099, -0.0664, -0.0192]
  vector lengths: min 0.369, max 0.402
  ```
  Not 1: the 256-number prefix of `gemini-embedding-001`'s output is not normalised. Cosine ignores length; L2 would not (§3.3, exercise D1).
- **If it fails.**
  - `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.`: see G2.
  - Repeated `API error (code: 403)… Retrying in N seconds (attempt k/5)...`: a wrong Project ID or role (G3), or the API is disabled (G4). It gives up only after about 2.5 minutes, so read the first message instead of waiting.
  - Repeated `API error (code: 429)… Retrying in N seconds`: you hit quota. Wait, or lower `batch_size`.
  - A `400 INVALID_ARGUMENT` mentioning the number of instances: set `batch_size=1` (open question Q2).

### Step 7. Load into ChromaDB (`README.md:144-165`)
```bash
python cli.py --load --chunk_type char-split
python cli.py --load --chunk_type recursive-split
```
- **Under the hood.**
  - `load()` (`cli.py:267-306`) clears the client cache (`:271`) and connects with `chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)` (`:274`), i.e. `llm-rag-chromadb:8000`.
  - It tries `delete_collection` (`:280-285`), then `client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})` (`:287-288`), where `collection_name = f"{method}-collection"` (`:277`).
  - For each `embeddings-<type>-*.jsonl` (`:293-294`) it calls `load_text_embeddings` (`:306`). That builds ids and per-book metadata (`:126-138`) and calls `collection.add(...)` in batches of 500 (`:142-158`).
  - Chroma persists everything under `/data`, which is `llm-rag/docker-volumes/chromadb/` on your host.
- **Checkpoint: the first load, before any embeddings existed.** Captured (`cli-container/30-load-char-split.txt`, exit 0):
  ```text
  $ python cli.py --load --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=True, query=False, chat=False, get=False, agent=False, chunk_type='char-split')
  load()
  Creating collection: char-split-collection
  Collection 'char-split-collection' did not exist. Creating new.
  Created new empty collection 'char-split-collection'
  Collection: Collection(name=char-split-collection)
  Number of files to process: 0
  ```
  The first lines are exactly a first-time student's. `Number of files to process: 0` is the symptom of a skipped or failed embed step: the collection exists, empty.
- **Checkpoint: the load with embeddings.** Recorded on the staff's vectors (`recorded-embeddings/01-load-char-split.txt`, 10 s; `02-load-recursive-split.txt`, 16 s):
  ```text
  $ python cli.py --load --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=True, query=False, chat=False, get=False, agent=False, chunk_type='char-split')
  load()
  Creating collection: char-split-collection
  Deleted existing collection 'char-split-collection'
  Created new empty collection 'char-split-collection'
  Collection: Collection(name=char-split-collection)
  Number of files to process: 11
  Processing file: outputs/embeddings-char-split-The Complete Book of Cheese.jsonl
  Shape: (1355, 3)
                                                 chunk  ...                                          embedding
  0  The Project Gutenberg eBook of The Complete B...  ...  [-0.0324312225, -0.0027327591, -0.0018078726, ...
  …
  [5 rows x 3 columns]
  Inserted 500 items...
  Inserted 1000 items...
  Inserted 1355 items...
  Finished inserting 1355 items into collection 'char-split-collection'
  …
  Processing file: outputs/embeddings-char-split-Tolminc Cheese.jsonl
  …
  Inserted 24 items...
  Finished inserting 24 items into collection 'char-split-collection'
  ```
  - A first load prints `Collection 'char-split-collection' did not exist. Creating new.`; any later load prints `Deleted existing collection …` (captured again, `cli-container/32-x-load-again.txt`): every load is a full rebuild.
  - The 11 `Finished inserting` counts add up to 8,248; the recursive-split load adds up to 14,228.
- **Extra checks** *(extra)*. Captured on the laptop and recorded in the container (`laptop/17b-x-collection-names.txt` before the inserts; `recorded-embeddings/03-x-collection-names.txt`, `04-x-docker-volumes.txt`, `07-x-metadata-per-book.txt` after them):
  ```text
  $ curl -s http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections | grep -oE '"name":"[a-z-]+-collection"|"dimension":[a-z0-9]+'
  "name":"char-split-collection"
  "dimension":256
  "name":"recursive-split-collection"
  "dimension":256
  $ ls -la docker-volumes/chromadb; du -sh docker-volumes/chromadb
  total 58184
  drwxr-sr-x 4 root root     4096 Oct 16 00:55 .
  drwxr-sr-x 3 root root     4096 Oct 16 00:52 ..
  drwxr-sr-x 2 root root     4096 Oct 16 00:54 ab125f80-4e2e-4751-8eb4-8d7d06c87e93
  -rw-r--r-- 1 root root 59781120 Oct 16 00:55 chroma.sqlite3
  drwxr-sr-x 2 root root     4096 Oct 16 00:54 f460d2ab-cd69-4809-a914-a9e03d4e9ec4
  82M	docker-volumes/chromadb
  ```
  - Before the inserts the same `curl` printed `"dimension":null` for both: the first insert fixes a collection's dimension. The full listing (the same `curl` without `-s … | grep`, `laptop/17-x-collections.txt`) also shows `"metadata":{"hnsw:space":"cosine"}`, the HNSW settings (`"max_neighbors":16`, `"ef_search":100`) and Chroma's own `"embedding_function"` named `"default"`, which the tutorial never uses.
  - On disk: one SQLite file plus one UUID-named index folder per collection (which UUID is which collection isn't shown), owned by root. While the collections were still empty, only `chroma.sqlite3` existed.

  The metadata check (container):
  ```bash
  python - <<'EOF'
  import chromadb
  c = chromadb.HttpClient(host="llm-rag-chromadb", port=8000).get_collection("char-split-collection")
  print("count:", c.count())
  first = {}
  for m in c.get(include=["metadatas"])["metadatas"]:
      first.setdefault(m["book"], m)
  for book in sorted(first):
      print(first[book])
  EOF
  ```
  ```text
  count: 8248
  {'author': 'C. F. Langworthy and Caroline Louisa Hunt', 'book': 'Cheese and its economical uses in the diet', 'year': 2023}
  …
  {'year': 2024, 'book': 'The Complete Book of Cheese', 'author': 'Bob Brown'}
  …
  {'book': 'Womans Institute Library of Cookery'}
  ```
  One metadata dict per book (key order varies). The Woman's Institute book has **no author or year**: its name was cut at the first dot (`cli.py:178`) and no longer matches its `book_mappings` key (`cli.py:70`) (E8, G17).
- **Optional:** open https://ac215-llm-rag.dlops.io/chromaui in **Chrome** to browse your local DB (`README.md:162-165`). It reads `localhost:8000` from your browser; the captured CORS answer above is why that one site may.
- **If it fails.**
  - `ValueError: Could not connect to a Chroma server. Are you sure it is running?` means the Chroma container is down, has no network after a failed start (G6), or you are running on the host (G11). Check `docker ps`.
  - `Number of files to process: 0` means you skipped step 6 for this chunk type, or it failed.

### Step 8. (Restart test, not in README)
```bash
exit                                   # (extra) leaves the CLI container
docker ps -a                           # (extra, host)
docker compose down                    # (extra, host, in llm-rag/)
docker ps -a; docker network ls; ls -la docker-volumes/chromadb   # (extra, host)
sh docker-shell.sh                     # (extra) start again
```
- **Checkpoint.** Captured (`laptop/20-x-ps-after-exit.txt`, `21-x-compose-down.txt`, `22-x-after-down.txt`, `23-x-docker-shell-again.txt`, `24-x-collection-names-after-restart.txt`):
  ```text
  $ docker ps -a
  CONTAINER ID   IMAGE                    COMMAND                  CREATED         STATUS         PORTS                    NAMES
  38d414943c8a   chromadb/chroma:latest   "dumb-init -- chroma…"   2 minutes ago   Up 2 minutes   0.0.0.0:8000->8000/tcp   llm-rag-chromadb
  $ docker compose down
  WARN[0000] The "GOOGLE_APPLICATION_CREDENTIALS" variable is not set. Defaulting to a blank string.
  WARN[0000] The "GCP_PROJECT" variable is not set. Defaulting to a blank string.
  [+] down 2/2
   ✔ Container llm-rag-chromadb Removed                                       0.2s
   ✔ Network llm-rag-network    Removed                                       0.1s
  $ docker ps -a; docker network ls; ls -la docker-volumes/chromadb
  CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
  NETWORK ID     NAME      DRIVER    SCOPE
  cd5f6cc0ba21   bridge    bridge    local
  7919486b2391   host      host      local
  9e7ff530c1c6   none      null      local
  total 58184
  …
  -rw-r--r-- 1 root root 59781120 Oct 16 00:55 chroma.sqlite3
  …
  $ sh docker-shell.sh
  [+] run 2/2
   ✔ Network llm-rag-network    Created                                       0.0s
   ✔ Container llm-rag-chromadb Created                                       0.4s
  Container llm-rag-llm-rag-cli-run-660c09bf506a Creating
  Container llm-rag-llm-rag-cli-run-660c09bf506a Created
  Container is running!!!
  …
  app@390fe47a277a:/app$
  $ curl -s http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections | grep -oE '"name":"[a-z-]+-collection"|"dimension":[a-z0-9]+'
  "name":"char-split-collection"
  "dimension":256
  "name":"recursive-split-collection"
  "dimension":256
  ```
  - After `exit` the CLI container is gone (`--rm`), but Chroma is still up and port 8000 still taken.
  - The two `WARN` lines are harmless: the variables live only in `docker-shell.sh`, and `down` needs neither (G25).
  - After `down` nothing runs and `llm-rag-network` is gone, but the database file and both index folders are still on your disk.
  - The second start pulls nothing and builds nothing (the image exists), and both collections are back. `python cli.py --get --chunk_type char-split` in the new container returns the same 10 record IDs as before (Step 11). This is the persistence claim of `README.md:160`.

### Step 9. Query the vector DB, no LLM yet (`README.md:171-186`)
```bash
python cli.py --query --chunk_type char-split
python cli.py --query --chunk_type recursive-split
```
- **Under the hood.**
  - `query()` (`cli.py:309-361`) connects to Chroma first (`:313`), then embeds `"How is tolminc cheese made?"` with `generate_query_embedding` (`:75-84`, `:318-319`), prints `Embedding values:` (`:320`) and opens the collection with `get_collection` (`:323`).
  - It runs **only variant #4** (`:352-361`): `n_results=10`, `where={"book": "The Complete Book of Cheese"}`, `where_document={"$contains": search_string}` with `search_string = "Italian"`. Variants #1-#3 are commented out (`:325-350`).
- **Checkpoint without a key.** Captured (`cli-container/40-query-char-split.txt`, exit 1):
  ```text
  $ python cli.py --query --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=False, query=True, chat=False, get=False, agent=False, chunk_type='char-split')
  load()
  Traceback (most recent call last):
  …
    File "/app/cli.py", line 319, in query
      query_embedding = generate_query_embedding(query)
  …
    File "/app/cli.py", line 79, in generate_query_embedding
      response = llm_client.models.embed_content(
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.
  ```
  - `load()` is a copy-paste label at `cli.py:310` (E3): harmless.
  - It connected to Chroma, then stopped at the key while embedding the question, before it opened the collection or searched. The question must become a vector before the database can compare it, and only the same Google model makes one in the same space. The same happened with `recursive-split`.
- **Checkpoint with your key** *(expected, from the code)*. `load()`, then `Embedding values: [` and 256 numbers `]`, then `Query: How is tolminc cheese made?`, then `Results:` and a dict of lists of lists: `ids`, `distances`, `metadatas`, `documents` (plus `embeddings`, `uris`, `data`, `included`; §3.5). All 10 documents come from *The Complete Book of Cheese* and contain "Italian"; **none mentions Tolminc**.
- **Extra checks: what the filters leave** *(extra, container; no key needed)*. Recorded on the loaded char-split collection (`recorded-embeddings/08-x-filter-counts.txt`):
  ```bash
  python - <<'EOF'
  import chromadb
  c = chromadb.HttpClient(host="llm-rag-chromadb", port=8000).get_collection("char-split-collection")
  bob = {"book": "The Complete Book of Cheese"}
  print("all chunks:                      ", c.count())
  print("where book = Bob Brown's book:   ", len(c.get(where=bob)["ids"]))
  print("  ... and $contains 'Italian':   ", len(c.get(where=bob, where_document={"$contains": "Italian"})["ids"]))
  print("  ... and $contains 'Tolminc':   ", len(c.get(where=bob, where_document={"$contains": "Tolminc"})["ids"]))
  print("any book, $contains 'Tolminc':   ", len(c.get(where_document={"$contains": "Tolminc"})["ids"]))
  EOF
  ```
  ```text
  all chunks:                       8248
  where book = Bob Brown's book:    1355
    ... and $contains 'Italian':    64
    ... and $contains 'Tolminc':    0
  any book, $contains 'Tolminc':    3
  ```
  The query's filters leave 64 candidates, none about Tolminc (`$contains` is case-sensitive). Then a search with a **stand-in query vector**: the stored vector of one story chunk, because the real question needs Google to become a vector (`recorded-embeddings/09-x-query-by-chunk-vector.txt`):
  ```bash
  python - <<'EOF'
  import chromadb
  c = chromadb.HttpClient(host="llm-rag-chromadb", port=8000).get_collection("char-split-collection")
  t = c.get(where={"book": "Tolminc Cheese"}, include=["embeddings", "documents"])
  i = next(k for k, d in enumerate(t["documents"]) if "curd" in d)
  v = t["embeddings"][i]
  print("stand-in query vector: the stored embedding of chunk", t["ids"][i], "(Tolminc Cheese)")
  print(repr(t["documents"][i][:72]))
  bob_italian = {"where": {"book": "The Complete Book of Cheese"}, "where_document": {"$contains": "Italian"}}
  for label, kw in [("no filter", {}), ("where book + $contains 'Italian' (as cli.py:354-359)", bob_italian)]:
      r = c.query(query_embeddings=[v], n_results=10, **kw)
      print("--", label)
      for d, m in zip(r["distances"][0], r["metadatas"][0]):
          print(f"{d:.4f}  {m['book']}")
  EOF
  ```
  ```text
  stand-in query vector: the stored embedding of chunk 8440accaceb0ce96-6 (Tolminc Cheese)
  'is ready?” Mara asked.\n\n“For what?”\n\n“For the next step.”\n\nAnja smiled. '
  -- no filter
  0.0000  Tolminc Cheese
  0.0804  Tolminc Cheese
  …
  0.1627  Tolminc Cheese
  -- where book + $contains 'Italian' (as cli.py:354-359)
  0.2833  The Complete Book of Cheese
  0.2875  The Complete Book of Cheese
  …
  0.3123  The Complete Book of Cheese
  ```
  - Without filters, the 10 nearest are all story chunks, from 0.0000 (the chunk itself; Chroma reports cosine *distance*, smaller is closer) to 0.1627.
  - With the code's filters, all 10 come from *The Complete Book of Cheese*, much further away. The filters act **before** ranking, and top-k fills its 10 places with whatever survives. The lecture draws filtering after ranking (A54–A55); that order would have dropped all 10 story chunks and returned nothing.
- **Try it** *(extra)*. On your laptop (no rebuild needed thanks to the bind mount), uncomment variant #1 (`cli.py:326-331`: the six code lines under the `# # 1:` header) and rerun `--query`. With no filter, every chunk competes; expect story chunks among the top hits (only 3 char-split chunks contain the word "Tolminc", so cheese-making passages from other books may compete). Variant #4 still runs and prints after it. Needs your key, like any query.
- **If it fails.**
  - A `NotFoundError` saying the collection does not exist means you have not run step 7 for this `--chunk_type` (G12).
  - `Could not connect to a Chroma server`: Chroma is down (`query()` connects before it embeds, so this comes before any key error).

### Step 10. Chat: the full RAG loop (`README.md:192-214`)
```bash
python cli.py --chat --chunk_type char-split
python cli.py --chat --chunk_type recursive-split
```
- **Under the hood.**
  - `chat()` (`cli.py:364-399`) connects to Chroma (`:368`), embeds `"How is tolminc cheese made??"` (double "?", `:372-373`; E4) and queries the top 10 with **no filter** (`:380-383`).
  - It builds `INPUT_PROMPT` as the question plus the 10 chunks joined by `"\n"` (`:388-391`). The `"\n"` inside an f-string expression needs Python 3.12 or newer.
  - It calls `llm_client.models.generate_content(model=GENERATIVE_MODEL, contents=INPUT_PROMPT)` (`:394-396`; `GENERATIVE_MODEL = "gemini-3.1-flash-lite"`, `:27`) and prints `LLM Response: <text>` (`:397-399`). No `config`, so the `SYSTEM_INSTRUCTION` is never sent (E1).
- **Not captured with a key.** Without one, both commands print `chat()` and stop at the question's embedding (`cli.py:373`) with the same `DefaultCredentialsError`. Nothing in the repo documents a `--chat` run, so no output is shown here.
- **Checkpoint with your key** *(expected, from the code)*:
  - `chat()`, `Query: How is tolminc cheese made??` (`:374`), `Embedding values:` with 256 numbers (`:375`), the `Results:` dict (`:384`), then `10` (`:386`), then `INPUT_PROMPT:` with your chunks (`:393`), then `LLM Response:` with a few paragraphs (`:399`).
  - The current Tolminc book is a short *fictional* story ("A fictional tale inspired by Alpine cheesemaking", line 4 of the book), though Tolminc itself is a real Alpine cheese. Details from the story (Mara, her grandfather, milk becoming curd) came from your chunks; real-world rules for the cheese would come from the model's memory, since nothing tells it to stay inside the chunks. It will **not** match the PDO/transhumance text in `out.txt` (E7).
  - Compare the char-split and recursive-split answers. Each run costs one embedding call and one Gemini call.
  - Optional web version: https://ac215-llm-rag.dlops.io/chat (`README.md:211`), in Chrome.
  - Your own question: change the string at `cli.py:372`.
- **If it fails.**
  - 404 / `NOT_FOUND` for the model: `gemini-3.1-flash-lite` may not be available to your project or at `global`; change `GENERATIVE_MODEL` at `cli.py:27` (Q3).
  - 403 from the question's embedding: `generate_query_embedding` has no retry loop, so it fails at once (G3, G4).
  - 429: quota, wait.

### Step 11. (Bonus, undocumented) `--get` (not in README)
```bash
python cli.py --get --chunk_type char-split
```
- **Under the hood.** `collection.get(where={"book": "The Complete Book of Cheese"}, limit=10)` (`cli.py:402-418`, flag at `:536-540`). This is a plain metadata lookup with **no similarity at all**, and no Google call, so it needs no key.
- **Checkpoint.** Captured on the empty collection (`cli-container/42-x-get.txt`) and after the restart on the loaded one (`cli-container/70-x-get-after-restart.txt`, cut on the right):
  ```text
  $ python cli.py --get --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=False, query=False, chat=False, get=True, agent=False, chunk_type='char-split')
  get()


  Results: {'ids': [], 'embeddings': None, 'metadatas': [], 'documents': [], 'data': None, 'uris': None, 'included': ['metadatas', 'documents']}

  $ python cli.py --get --chunk_type char-split
  …
  Results: {'ids': ['1021665fac86c5a5-0', '1021665fac86c5a5-1', … '1021665fac86c5a5-9'], 'embeddings': None, 'metadatas': [{'book': 'The Complete Book of Cheese', 'year': 2024, 'author': 'Bob Brown'}, …], 'documents': ['\ufeffThe Project Gutenberg eBook of The Complete Book of Cheese\n    \nThis ebook is for the use of anyone anywhere …', …
  ```
  - 10 records in storage order; there is no `distances` key, because nothing was ranked. Contrast this with step 9: `get` filters, while `query` filters *and* ranks.
  - The IDs are 16 hex characters of the SHA-256 of the book's name plus the row number (`cli.py:127-130`), so they are the same after a restart.
  - The first documents are the Project Gutenberg header and licence text: indexed like any other text (G23, E18).

### Step 12. (Advanced) Semantic chunking end to end (`README.md:220-236`)
```bash
python cli.py --chunk --embed --load --chunk_type semantic-split
```
- **Under the hood.** `main()` runs `chunk`, then `embed`, then `load` in sequence (`cli.py:484-491`).
  - **chunk:** `SemanticChunker(embedding_function=generate_text_embeddings)` (`:207-215`) splits sentences (`semantic_splitter.py:217`), embeds the 3-sentence windows 50 at a time (`:206`) and cuts at the 95th-percentile distance (`:229-243`). These are **real API calls**: 26,080 windows, 528 calls for all 11 books.
  - **embed:** the same as step 6 but with `batch_size=15` (`cli.py:248-250`), because semantic chunks are long: 1,318 chunks, 92 calls.
  - **load:** into `semantic-split-collection`.
- **Checkpoint without a key.** Captured (`cli-container/60-semantic-split.txt`, exit 1; `61-x-after-semantic.txt`):
  ```text
  $ python cli.py --chunk --embed --load --chunk_type semantic-split
  CLI Arguments: Namespace(chunk=True, embed=True, load=True, query=False, chat=False, get=False, agent=False, chunk_type='semantic-split')
  chunk()
  Number of files to process: 11
  Processing file: input-datasets/books/The Complete Book of Cheese.txt
  Traceback (most recent call last):
    File "/app/cli.py", line 551, in <module>
      main(args)
    File "/app/cli.py", line 485, in main
      chunk(method=args.chunk_type)
    File "/app/cli.py", line 212, in chunk
      text_chunks = text_splitter.create_documents([input_text])
  …
    File "/app/semantic_splitter.py", line 206, in _calculate_sentence_distances
      embeddings = self.embedding_function([x["combined_sentence"] for x in sentences],batch_size=50)
  …
    File "/app/cli.py", line 98, in generate_text_embeddings
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.
  $ ls outputs | grep semantic | wc -l
  0
  ```
  Unlike char-split and recursive-split, semantic chunking calls the embedding API already in the **chunk** phase: it fails inside `chunk()`, on the first book, before a single chunk is saved.
- **Checkpoint with your key** *(expected, from the code and exercise B7)*. Per book, `Number of chunks:` is about 5% of its sentence count (the story: 108 sentences → 7 chunks), then the embed step's tables, then `Finished inserting …` lines for `semantic-split-collection`.
- **Test it cheaply first** *(extra, host, in `~/AC215/llm-rag`)*. Move every book but the story aside, run the README command, then put them back:
  ```bash
  mkdir books-aside
  mv input-datasets/books/*.txt books-aside/
  mv "books-aside/Tolminc Cheese.txt" input-datasets/books/
  # in the container: python cli.py --chunk --embed --load --chunk_type semantic-split
  mv books-aside/*.txt input-datasets/books/ && rmdir books-aside
  ```
  The story alone costs 3 embedding calls to chunk (108 windows in batches of 50) and 1 to embed its 7 chunks. The semantic collection then holds only the story until you run the command again on all the books.
- **Follow-up (not in README).** `--chunk_type` is generic, so after the load finishes you can run `python cli.py --chat --chunk_type semantic-split` and compare the answer with the two step-10 runs. Before the load, it raises `NotFoundError` (G12).
- **If it fails.** Expect 429s; the backoff handles brief ones, and after 5 retries the whole run aborts (G13). Budget 10-20+ minutes for all the books.

### Step 13. Preview only: Agents (L06) (`README.md:242-271`)
```bash
python cli.py --agent --chunk_type char-split
```
- This sends a question about the instructor's book (`cli.py:435`) to Gemini with two function declarations (`agent_tools.py:9-81`), forcing a tool call (`mode="any"`, `cli.py:444-452`): the model chooses *which* retrieval to make, not *whether* to retrieve.
- It executes the chosen retrieval, for example `get_book_by_author(...)`, a `where={"author": …}` query (`agent_tools.py:41-49`), and sends the results back for a final answer (`cli.py:456-478`).
- `out.txt` is the staff's recorded run of exactly this command, from 2026-09-22 (`out.txt:1`, `:34`, `:120`; `model_version='gemini-3.1-flash-lite'`). It is not the output of any L05 command, and its retrieved text comes from the older Tolminc book (E7). Leave the details to L06.

### Step 14. Leave and clean up (not in README)
```bash
exit                 # leaves the CLI container (it is deleted: --rm)
docker compose down  # run on the host, in llm-rag/: stops llm-rag-chromadb, removes llm-rag-network
docker images        # (extra, host)
git status; git status --short --ignored   # (extra, host)
```
- **Checkpoint.** Captured (`laptop/25-x-compose-down-final.txt`, `26-x-images.txt`, `27-x-git-status.txt`):
  ```text
  $ docker compose down
  WARN[0000] The "GOOGLE_APPLICATION_CREDENTIALS" variable is not set. Defaulting to a blank string.
  WARN[0000] The "GCP_PROJECT" variable is not set. Defaulting to a blank string.
  [+] down 2/2
   ✔ Container llm-rag-chromadb Removed                                       0.2s
   ✔ Network llm-rag-network    Removed                                       0.2s
  $ docker images
  IMAGE                       ID             DISK USAGE   CONTENT SIZE   EXTRA
  chromadb/chroma:latest      1e0b73a187a2        826MB          176MB
  llm-rag-cli:latest          3b31b15cf50b       2.11GB          537MB
  python:3.12-slim-bookworm   60c8fd1dbf1f        198MB         47.8MB
  $ git status; git status --short --ignored
  On branch main
  Your branch is up to date with 'origin/main'.
  …
  	modified:   docker-shell.sh
  …
   M docker-shell.sh
  !! __pycache__/
  !! docker-volumes/
  !! outputs/
  ```
  - `docker ps` afterwards shows no `llm-rag-*` containers. `docker-volumes/chromadb/` still exists, so next time you can query straight away.
  - The images stay until you remove them: 2.11 GB for the CLI image (its Python base included) and 826 MB for Chroma.
  - Your only change to the repo is the Project ID in `docker-shell.sh`; `outputs/`, `docker-volumes/` and `__pycache__/` are ignored (`.gitignore:3-5`).
  - Nothing keeps running in Google Cloud; you paid only for the text you sent. Keep the key beside the repo, never inside it (G20), and delete it when the course ends.

---

## 5. Code tour

```
llm-rag/                          (= /app inside the CLI container, via the bind mount)
├── README.md                     tutorial: RAG steps (L05) + Agents section (L06)
├── docker-shell.sh               sets GCP_PROJECT / GOOGLE_APPLICATION_CREDENTIALS; `docker compose run --rm $IMAGE_NAME`
├── docker-compose.yml            services llm-rag-cli (built here) + chromadb (chromadb/chroma:latest); network llm-rag-network
├── Dockerfile                    python:3.12-slim-bookworm + uv; deps into /.venv; non-root user app (uid 1000)
├── docker-entrypoint.sh          prints arch/versions, activates /.venv, execs an interactive bash
├── pyproject.toml, uv.lock       chromadb 1.1.0, google-genai 1.39.1, langchain 0.3.27, langchain-text-splitters 0.3.11, pandas 2.3.3, ...
├── cli.py                        the whole pipeline: --chunk --embed --load --query --chat --get --agent, --chunk_type
├── semantic_splitter.py          SemanticChunker (sentence windows -> cosine distances -> percentile breakpoints)
├── agent_tools.py                L06: Gemini function declarations + executor for the --agent flow
├── input-datasets/books/         the corpus: 11 .txt books (Tolminc Cheese.txt = the instructor's short story)
├── images/llm-rag-flow-{1,2,3}.png   README diagrams: index, query, agent
├── out.txt                       the staff's recorded output of one --agent run (2026-09-22)
├── outputs/                      (git-ignored, created) chunks-*.jsonl (8.2 MB), embeddings-*.jsonl (82 MB)
└── docker-volumes/chromadb/      (git-ignored, created by Docker as root) chroma.sqlite3 + one HNSW index folder per collection
../secrets/llm-service-account.json   (you create; mounted read-write at /secrets)
```

**`docker-compose.yml:5-17`**
```yaml
services:
    llm-rag-cli:
        image: llm-rag-cli
        build: .
        container_name: llm-rag-cli
        volumes:
            - ../secrets:/secrets
            - ../llm-rag:/app
        environment:
            GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS
            GCP_PROJECT: $GCP_PROJECT
        depends_on:
            - chromadb
```
- `image:` + `build: .`: Compose builds the Dockerfile in this folder and tags it `llm-rag-cli`, but **only if no such image exists**. Since `9a27441` (2026-09-16) the script no longer runs `docker build` itself, so rebuilding after dependency changes is up to you (G9).
- `container_name: llm-rag-cli` (line 9): meant as a fixed name for the CLI container, but `docker compose run` ignores it. The captured container is `llm-rag-llm-rag-cli-run-90678535ddef` (project, service, `run`, a random id; E19). The name that matters for DNS is the `chromadb` service's (next excerpt).
- `../secrets:/secrets` and `../llm-rag:/app`: both host paths are relative to *this file*. The second one means "this repo folder, **by name**". A plain `.:/app` would not depend on the folder name.
- `GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS`: Compose *interpolates* these from the shell that ran `docker compose`, which is why you must go through `docker-shell.sh`.
- `depends_on: chromadb`: `run` starts the DB first, even before it builds the CLI image (captured order: Chroma pulled and created, then `Image llm-rag-cli Building`). That means "container started", not "server ready".

**`docker-compose.yml:18-26`**
```yaml
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
- `chromadb/chroma:latest`: an unpinned server image. On 2026-10-12, 2026-10-13 and 2026-10-16, Docker Hub listed `latest` and `1.5.9` with the same digest, `sha256:1e0b73a1…` (created 2026-05-05). Inside that image, `chroma --version` prints `chroma 1.4.4` and `GET /api/v2/version` answers `"1.0.0"` (captured), while the Python client is pinned to 1.1.0 (`uv.lock:289-290`). It works; it is multi-arch (amd64 and arm64).
- `container_name: llm-rag-chromadb`: this name is the **hostname** the CLI uses (`cli.py:30`).
- `8000:8000`: publishes the server on your laptop's port 8000, for the browser tools and curl. Container-to-container traffic does not need it.
- `./docker-volumes/chromadb:/data`: Chroma 1.x keeps its database in `/data`. The `pipenv` branch (March 2025, and `main` until `9a27441`) mounted `/chroma/chroma` (the 0.x path), so mixing old instructions with the new image loses persistence. Docker creates the folder on your laptop, as root, when it creates the container.
- `CHROMA_CORS_ALLOW_ORIGINS`: lets JavaScript on the course's web tool (and a local front end on port 3200, added in `7a3c66b`) call your local Chroma from the browser. Captured: a request with `Origin: https://ac215-llm-rag.dlops.io` gets `access-control-allow-origin: https://ac215-llm-rag.dlops.io` back; one from `https://example.com` gets no such header.

**`docker-shell.sh:6-12`**
```bash
# Set variables
export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
export GOOGLE_APPLICATION_CREDENTIALS="/secrets/llm-service-account.json"
export IMAGE_NAME="llm-rag-cli"

# Run all containers using docker compose run --rm
docker compose run --rm $IMAGE_NAME
```
- Line 7 is the one line you must edit; the comment says so.
- Line 8 is a path *inside* the container, matching the `/secrets` mount.
- Line 12: `run --rm` gives you an interactive one-off container that is deleted on exit. Dependencies (Chroma) are started and **left running**.

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
- `USER app`: everything after this, including `uv sync`, runs as uid 1000 (created at `Dockerfile:31`). This matters for writing into bind mounts on Linux (G14).
- Copying `pyproject.toml uv.lock*` first and running `uv sync --frozen` before `COPY . ./` is layer caching: editing `cli.py` does not reinstall dependencies. `--frozen` installs exactly what `uv.lock` says and does not check whether the lock still matches `pyproject.toml` (that check is `--locked`); it errors only if `uv.lock` is missing, which the `uv.lock*` glob in the `COPY` would otherwise tolerate.
- `COPY . ./` copies the whole build context. There is **no `.dockerignore`**, so the context includes `.git` (103 MB of history) and, because Compose creates Chroma before it builds, a fresh `docker-volumes/chromadb/chroma.sqlite3`: the captured first build sent 112.26 MB, and the image holds `/app/.git` and that database file. After a run, `outputs/` and a loaded `docker-volumes/` join them on any rebuild (G15). The bind mount hides this copy at run time anyway.
- `ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]` uses a *relative* script path resolved in `WORKDIR /app`, which is why an empty `/app` mount kills the container (G1).

**`cli.py:22-36`**
```python
# Setup
GCP_PROJECT = os.environ["GCP_PROJECT"]
GCP_LOCATION = "global"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 256
GENERATIVE_MODEL = "gemini-3.1-flash-lite"
INPUT_FOLDER = "input-datasets"
OUTPUT_FOLDER = "outputs"
CHROMADB_HOST = "llm-rag-chromadb"
CHROMADB_PORT = 8000

#############################################################################
#                       Initialize the LLM Client                           #
llm_client = genai.Client(
    vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
```
- Line 23 reads the env var at import; `os.environ[...]` raises `KeyError` if it is absent.
- Line 24: `"global"` routes to `https://aiplatform.googleapis.com/` (not `us-central1-…`). It was changed from `us-central1` in `51a2865`.
- Lines 25-27: the two models. `256` is the embedding size used for *both* the index and queries; they must match forever.
- Lines 30-31: the Chroma server's address on the Compose network. It is valid only inside containers on `llm-rag-network` (G11).
- Lines 35-36: one client object for embeddings and generation. Credentials are loaded lazily on the first call (captured: `--chunk` runs without a key, and the first `embed_content` raises `DefaultCredentialsError` from `_access_token`). With an empty `GCP_PROJECT` they are loaded here instead, and line 35 itself fails (G5).

**`cli.py:183-194`**
```python
        text_chunks = None
        if method == "char-split":
            chunk_size = 350
            chunk_overlap = 20
            # Init the splitter
            text_splitter = CharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator='', strip_whitespace=False)

            # Perform the splitting
            text_chunks = text_splitter.create_documents([input_text])
            text_chunks = [doc.page_content for doc in text_chunks]
            print("Number of chunks:", len(text_chunks))
```
- `separator=''` means "split into characters, then pack": a fixed-width window that ignores words.
- `chunk_overlap=20`: each chunk repeats the last 20 characters of the previous one.
- `strip_whitespace=False`: keeps leading and trailing spaces and newlines, so a chunk can start with `"\n\n"`.
- `create_documents([input_text])` returns LangChain `Document`s; the next line keeps only `.page_content`.

**`cli.py:96-106`**
```python
        while retry_count <= max_retries:
            try:
                response = llm_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        output_dimensionality=dimensionality),
                )
                all_embeddings.extend(
                    [embedding.values for embedding in response.embeddings])
                break
```
- `contents=batch`: up to 100 strings per request for char- and recursive-split (`cli.py:252-253`), 15 for semantic chunks, and 50 inside the semantic splitter. The staff's own `cli.py` with these batch sizes made the embeddings files they committed in `68e0bde` (Q2).
- `output_dimensionality`: asks Vertex to return only the first 256 numbers of the embedding (`parameters.outputDimensionality` in the request).
- No `task_type` is sent, so documents and queries are embedded the same way (E16).
- `response.embeddings[i].values` is a list of floats in the same order as `batch`. `extend` keeps that alignment, and the DataFrame column assignment at `cli.py:254` relies on it.

**`cli.py:126-138`**
```python
    # Generate ids
    df["id"] = df.index.astype(str)
    hashed_books = df["book"].apply(
        lambda x: hashlib.sha256(x.encode()).hexdigest()[:16])
    df["id"] = hashed_books + "-" + df["id"]

    metadata = {
        "book": df["book"].tolist()[0]
    }
    if metadata["book"] in book_mappings:
        book_mapping = book_mappings[metadata["book"]]
        metadata["author"] = book_mapping["author"]
        metadata["year"] = book_mapping["year"]
```
- IDs: a 16-hex-character hash of the book name plus the row index; captured for *The Complete Book of Cheese*: `1021665fac86c5a5-0` … `-9`. They are stable across reloads and unique across books, but the same row number in the char-split and recursive-split collections gives the same ID for different text (exercise B5).
- Metadata is computed **once per file** from the first row, which works because each JSONL file holds exactly one book. `author` and `year` are added only if the (truncated) book name is a key of `book_mappings` (`cli.py:60-72`). One book misses (E8; recorded: `{'book': 'Womans Institute Library of Cookery'}`, no author, no year).

**`cli.py:280-290`**
```python
    try:
        # Clear out any existing items in the collection
        client.delete_collection(name=collection_name)
        print(f"Deleted existing collection '{collection_name}'")
    except Exception:
        print(f"Collection '{collection_name}' did not exist. Creating new.")

    collection = client.create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"})
    print(f"Created new empty collection '{collection_name}'")
    print("Collection:", collection)
```
- The `try/except Exception` swallows Chroma's `NotFoundError` on first load, so either message is normal (both captured: `did not exist. Creating new.` on the first load, `Deleted existing collection` on every later one).
- `metadata={"hnsw:space": "cosine"}` is the legacy-style way (still accepted by chromadb 1.1.0, see `chromadb/api/collection_configuration.py` in the wheel) to choose cosine distance for the HNSW index. The default would be L2.
- Because the collection is dropped and recreated, a load is always a full rebuild.

**`cli.py:352-361`**
```python
    # 4: Query based on embedding value + lexical search filter
    search_string = "Italian"
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        where={"book": "The Complete Book of Cheese"},
        where_document={"$contains": search_string}
    )
    print("Query:", query)
    print("\n\nResults:", results)
```
- `query_embeddings=[query_embedding]` is a *list* of queries; the result has one inner list per query.
- `where` is an exact-match metadata filter; `where_document` with `$contains` is a case-sensitive substring filter on the chunk text.
- Both filters apply before nearest-neighbour ranking, so the result is "the 10 chunks of *The Complete Book of Cheese* containing 'Italian' that are least far from a Tolminc question" (recorded: 64 candidates survive the two filters, none containing "Tolminc").

**`cli.py:386-399`**
```python
    print(len(results["documents"][0]))

    INPUT_PROMPT = f"""
	{query}
	{"\n".join(results["documents"][0])}
	"""

    print("INPUT_PROMPT: ", INPUT_PROMPT)
    response = llm_client.models.generate_content(
        model=GENERATIVE_MODEL, contents=INPUT_PROMPT
    )
    generated_text = response.text

    print("LLM Response:", generated_text)
```
- Line 386 prints `10`, the number of documents returned. `results["documents"][0]` holds the 10 chunk texts for the first (only) query; their `metadatas` (the book names) are not pasted, so the model cannot say which book a fact came from.
- The f-string contains `"\n".join(...)` *inside* the braces, which is legal only from Python 3.12 (PEP 701). The lines inside the triple-quoted string start with tab characters, which are sent to the model as-is.
- `generate_content(model=..., contents=INPUT_PROMPT)` passes **no `config`**, hence no `system_instruction`, temperature or token limit (E1).
- `response.text` is the concatenated text of the first candidate.

**`semantic_splitter.py:229-243`**
```python
        distances, sentences = self._calculate_sentence_distances(single_sentences_list)
        if self.number_of_chunks is not None:
            breakpoint_distance_threshold = self._threshold_from_clusters(distances)
            breakpoint_array = distances
        else:
            (
                breakpoint_distance_threshold,
                breakpoint_array,
            ) = self._calculate_breakpoint_threshold(distances)

        indices_above_thresh = [
            i
            for i, x in enumerate(breakpoint_array)
            if x > breakpoint_distance_threshold
        ]
```
- `distances[i]` is the cosine distance between sentence window *i* and window *i+1*.
- With the default `"percentile"` / `95`, the threshold is the 95th percentile of all those distances, so roughly 5% of gaps become cuts.
- `indices_above_thresh` are the sentence indices after which a chunk ends. Lines 249-264 (not shown) join the sentences between cuts with single spaces, so the whitespace that separated sentences (including paragraph breaks) is replaced by one space.

---

## 6. Gotchas and common errors

Each entry: symptom → cause → fix. "Captured" means reproduced in the 2026-10-16 captures (§4); "checked" means reproduced in the exercise checks (§8).

**G1. Container exits immediately: `/bin/bash: docker-entrypoint.sh: No such file or directory`.**
- **Cause.** `docker-compose.yml:12` mounts `../llm-rag`. If your clone is named anything else (`llm-rag-main` from a ZIP download, or a renamed folder inside a monorepo like `MLOps_Learning/`), Docker creates an empty `../llm-rag` directory, owned by root, and mounts it over `/app`. That hides the code, including the entrypoint script referenced at `Dockerfile:51`.
- **Captured** (`gotchas/03-x-g1-clone-as-main.txt`, `04-x-g1-docker-shell.txt`, `05-x-g1-stray-folder.txt`, in a second workspace `~/AC215-zip`):
  ```text
  $ git clone https://github.com/dlops-io/llm-rag.git llm-rag-main; mkdir secrets; ls
  Cloning into 'llm-rag-main'...
  llm-rag-main
  secrets
  $ sh docker-shell.sh
  [+] run 2/2
   ✔ Network llm-rag-network    Created                                       0.0s
   ✔ Container llm-rag-chromadb Created                                       0.0s
  Container llm-rag-main-llm-rag-cli-run-5ccb3414d5d2 Creating
  Container llm-rag-main-llm-rag-cli-run-5ccb3414d5d2 Created
  /bin/bash: docker-entrypoint.sh: No such file or directory
  $ ls -la ..; ls -la ../llm-rag
  total 20
  …
  drwxr-sr-x 2 root    root    4096 Oct 16 00:56 llm-rag
  drwxr-sr-x 6 student student 4096 Oct 16 00:56 llm-rag-main
  drwxr-sr-x 2 student student 4096 Oct 16 00:56 secrets
  total 8
  drwxr-sr-x 2 root    root    4096 Oct 16 00:56 .
  drwxr-sr-x 5 student student 4096 Oct 16 00:56 ..
  ```
  The script exits with status 127. The Compose project is now named `llm-rag-main` after the folder.
- **Fix.** Name the folder `llm-rag`, or change the mount to `.:/app`. Run `docker compose down`, then delete the stray empty `../llm-rag` folder (root-owned: `sudo rmdir ../llm-rag` on Linux).

**G2. `google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` on the first embed, query or chat.**
- **Cause.** The key is not at `../secrets/llm-service-account.json`: wrong file name, wrong folder level, or `secrets/` created inside `llm-rag/`. Docker silently creates a missing bind-mount source as an empty directory. Chunking still works, because credentials are loaded only on the first request (§2).
- **Captured.** Exactly this error, raised from `_access_token` inside `embed_content`, ends `--embed`, `--query`, `--chat` and the semantic split when `/secrets` is empty (§4 Steps 6, 9, 10, 12).
- **Fix.** Place and rename the key exactly as in `README.md:62-69`. Then check from the container: `ls /secrets`.

**G3. `403 PERMISSION_DENIED` from aiplatform on embed or chat.**
- **Cause, option 1.** You did not edit `docker-shell.sh:7`, so the calls target `ac215-project`, not your project. That is the ID the L03 mega-pipeline hard-codes for the course's own project (`mega-pipeline/generate_text/cli.py:15`).
- **Cause, option 2.** The SA lacks the Vertex AI User role (`README.md:58`), or `GCP_PROJECT` is the project *name* instead of its ID.
- **What you see.** A 403 is an `errors.APIError`, which `generate_text_embeddings` catches (`cli.py:108`): `--embed` prints `API error (code: 403): …. Retrying in 5 seconds (attempt 1/5)...` and retries for 5 + 10 + 20 + 40 + 80 = 155 s before it re-raises (`cli.py:110-119`). The question's embedding in `--query` and `--chat` has no retry loop (`cli.py:75-84`) and fails at once.
- **Fix.** Use the ID that matches `project_id` in the key file and grant `roles/aiplatform.user`. Then `exit` and restart the script, because env vars are read at container start.

**G4. `403 … SERVICE_DISABLED` / "Vertex AI API has not been used in project … or it is disabled".**
- **Cause.** The README never says to enable the API (E6). The same retry behaviour as G3 applies.
- **Fix.** Enable `aiplatform.googleapis.com` and wait a minute.

**G5. Compose prints `The "GCP_PROJECT" variable is not set. Defaulting to a blank string.` and Python fails even for `--chunk`.**
- **Cause.** You ran `docker compose run --rm llm-rag-cli` directly. `docker-compose.yml:14-15` interpolate from your shell, so both vars become empty strings.
- **What the code then does.** `cli.py:23` gets `""` (no `KeyError`). `genai.Client(project="")` treats the project as missing and calls `google.auth.default()` right away (`load_auth(project=None)`). `GOOGLE_APPLICATION_CREDENTIALS` is also the empty string, so google-auth 2.41.1 tries to open a file named `""`.
- **Captured** (`gotchas/01-x-g5-compose-run-direct.txt`, lines joined where the terminal wrapped them):
  ```text
  $ docker compose run --rm llm-rag-cli
  WARN[0000] The "GOOGLE_APPLICATION_CREDENTIALS" variable is not set. Defaulting to a blank string.
  WARN[0000] The "GCP_PROJECT" variable is not set. Defaulting to a blank string.
  …
  app@2af936bbf5b9:/app$ python cli.py --chunk --chunk_type char-split
  Traceback (most recent call last):
    File "/app/cli.py", line 35, in <module>
      llm_client = genai.Client(
  …
  google.auth.exceptions.DefaultCredentialsError: File  was not found.
  Exception ignored in: <function Client.__del__ at 0x7f4bd3835440>
  …
  AttributeError: 'Client' object has no attribute '_api_client'
  ```
  Note the empty file name between the two spaces. The banner and prompt look normal; only the first `python cli.py …` reveals the problem.
- **Fix.** Always start through `sh docker-shell.sh`, or `export` both vars first.

**G6. `Bind for 0.0.0.0:8000 failed: port is already allocated`, and then Chroma with no network.**
- **Cause.** Something on your laptop already uses host port 8000: another Chroma (the L06 ADK repo's `llm-agent-google-adk/6-rag/2-custom-chromadb-rag/docker-compose.yml:8` also publishes `8000:8000`), a FastAPI dev server, or an old `llm-rag-chromadb`. The full message starts `Error response from daemon: failed to set up container networking: driver failed programming external connectivity on endpoint llm-rag-chromadb (…)`.
- **The second trap (checked, exercise C3).** The failed start leaves a half-made `llm-rag-chromadb` in state `Created`. After you free the port, the next `sh docker-shell.sh` reuses it, and on Docker Engine 29.8.2 it starts **with no network**: `docker ps` shows an empty PORTS column, the heartbeat `curl` can't connect, and in the container every Chroma step says `Could not connect to a Chroma server`.
- **Fix.** Stop the other program (`docker ps`, then `docker stop <name>`), then run `docker compose down` in `llm-rag/` (it removes the half-made container and the network) before `sh docker-shell.sh`. Or change the *left* side to `8001:8000` (`docker-compose.yml:22`). The CLI keeps working because it uses the container port over the network, but `curl` and the web Chroma UI will need the new port.

**G7. `Conflict. The container name "/llm-rag-chromadb" is already in use …`, or silently someone else's database.**
- **Cause.** The fixed `container_name` (`docker-compose.yml:20`) is machine-wide. Compose names the project after the folder that holds the compose file.
  - (a) The name is held by a container of a *different* project (a copy in a folder with another name, or the `demo-podcast` branch, which keeps its compose file in `llmrag/` with the same `container_name: llm-rag-chromadb`, `git show origin/demo-podcast:llmrag/docker-compose.yml`, line 21), or of none (started by hand with `docker run --name`). Compose refuses to take it (checked, exercise C4).
  - (b) Two copies in folders that are both called `llm-rag` (for example `~/AC215/llm-rag` and `~/Desktop/llm-rag`, or L10's `cheese-app-v0/llm-rag/`) are the *same* project. Compose finds "its" Chroma, sees a different bind-mount source, and recreates it (`Recreate` / `Recreated`), now mounting the other copy's `docker-volumes/`. No error, but `--query` fails with `NotFoundError` because that folder holds no collections (checked, exercise C4). Nothing is lost.
- **Fix.** (a) `docker rm -f llm-rag-chromadb`, or `docker compose down` in the folder that started it. (b) `docker compose down`, then start from the copy you meant. Better: keep one copy.

**G8. "I exited, but my laptop's fan is still on / port 8000 is still taken."**
- **Cause.** `--rm` removes only the CLI container (`docker-shell.sh:12`). Chroma stays up (captured `docker ps -a` after `exit`, §4 Step 8).
- **Fix.** `docker compose down` from `llm-rag/`.

**G9. After `git pull`, `ModuleNotFoundError` or old behaviour despite a changed `pyproject.toml` / `uv.lock` / `Dockerfile`.**
- **Cause.** Compose builds only when the image `llm-rag-cli` is missing (`docker-compose.yml:7-8`; captured: the second start printed `[+] run 2/2` with no build). The explicit `docker build` was commented out of the script in `9a27441` (and the comment deleted in `500a99c`). Your old image, with old `/.venv` dependencies, is reused. The bind mount gives you the *new* code with the *old* dependencies.
- **Fix.** `docker compose build` (or `docker compose run --build --rm llm-rag-cli`), then start again.

**G10. Behaviour differs between classmates, or a sudden Chroma API error after re-pulling.**
- **Cause.** `chromadb/chroma:latest` (`docker-compose.yml:19`) resolves to whatever was newest when *you* first pulled it, while the client is locked at 1.1.0 (`uv.lock:289-290`). Captured on 2026-10-16: Docker Hub listed `latest` and `1.5.9` with the same digest, `chroma --version` inside it printed `chroma 1.4.4`, and the API reported `"1.0.0"`.
- **Fix.** Pin the server, for example `chromadb/chroma:1.5.9` (the tag the recording's digest carried, multi-arch) or the digest itself, `chromadb/chroma@sha256:1e0b73a187a28757c572acba508c46f48c9e8b0acaf5c20e6d95cdedce1acdf6`, and upgrade server and client together, on purpose.

**G11. Running `python cli.py …` on your laptop instead of in the container.**
- **Symptoms.**
  - `KeyError: 'GCP_PROJECT'`;
  - `SyntaxError: f-string expression part cannot include a backslash` on Python ≤ 3.11 (`cli.py:388-391`);
  - `ValueError: Could not connect to a Chroma server. Are you sure it is running?`. Read the first exception of the chain, not the last: `httpx.ConnectError: [Errno -2] Name or service not known` (checked, exercise C2), because `llm-rag-chromadb` (`cli.py:30`) only resolves inside the Compose network (captured in the container: `172.19.0.2`).
- **Fix.** Use the container. If you really want host-side runs, use Python 3.12, export the env vars with a host path to the key, and make the host configurable: `CHROMADB_HOST = os.environ.get("CHROMADB_HOST", "llm-rag-chromadb")` plus `export CHROMADB_HOST=localhost` (checked, exercise C2).

**G12. A `NotFoundError` saying the collection does not exist, from `--query`, `--chat` or `--get`.**
- **Cause.** Each `--chunk_type` has its own collection (`cli.py:277`, `:316`, `:370`, `:408`), and you have not loaded that one; for example `chromadb.errors.NotFoundError: Collection [semantic-split-collection] does not exist` (checked, exercise C1). Other causes: you deleted `docker-volumes/`, or Chroma was started from another copy of the repo (G7).
- **Fix.** Run `--load` for that `--chunk_type` (and `--embed` first if `outputs/` has no embeddings files). To see what exists: `curl -s http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections` on the laptop.

**G13. Semantic split is slow, eats quota and prints many `API error (code: 429)` retries.**
- **Cause.** Chunking itself embeds 26,080 sentence windows, 528 calls (`semantic_splitter.py:206`). The retry loop only catches `errors.APIError` (`cli.py:108`), and after 5 retries it re-raises and aborts the whole run.
- **Fix.** Try it on one book first (§4 Step 12). Re-running repeats every API call, because `chunk` does not cache.

**G14. `PermissionError: [Errno 13] Permission denied: 'outputs'` (Linux hosts).**
- **Cause.** The container runs as uid 1000 (`Dockerfile:31`, `:38`) and writes into your bind-mounted repo. If your host user is not uid 1000, it cannot create `outputs/` (checked with uid 1001, exercise C7; the capture's `student` was uid 1000, so its files are `student`'s). Separately, the Chroma container runs as root, so `docker-volumes/` ends up owned by root (captured).
- **Fix.** `mkdir outputs && chmod a+w outputs` on the host, or match the uid. Use `sudo rm -rf docker-volumes` to clean up. macOS and Windows Docker Desktop map ownership for you.

**G15. Builds send 100+ MB, and the image carries `.git` and a database file.**
- **Cause.** There is no `.dockerignore`, so `COPY . ./` (`Dockerfile:48`) copies the whole folder. Captured on the very first build: a 112.26 MB context, almost all `.git` (103 MB, because the history keeps the staff's database and `outputs/`, E21), and the image holds `/app/.git` and a copy of the `chroma.sqlite3` that Chroma had just created (Compose starts Chroma before it builds). After a run, `outputs/` and a loaded `docker-volumes/` join them on any rebuild.
- **Fix.** Add a `.dockerignore` with `.git`, `outputs/`, `docker-volumes/` and `__pycache__/` (and `secrets/` as a guard). Checked (exercise D3) on a folder with a full `outputs/` and a loaded database: the context drops from 257.74 MB to 4.58 MB and the image from 2.31 GB to 1.89 GB. Don't exclude `pyproject.toml`, `uv.lock` or `docker-entrypoint.sh`.

**G16. Packages added with `uv add` disappear after you exit.**
- **Cause.** `uv add` inside the container edits `pyproject.toml` and `uv.lock` on your host (bind mount) but installs into `/.venv`, which lives in the throw-away container (`Dockerfile:18`), and the next start uses the old image (checked, exercise C6).
- **Fix.** Rebuild the image (G9) after adding dependencies, and commit both files.

**G17. Filtering by the Woman's Institute book or author returns nothing.**
- **Cause.** `book_name = filename.split(".")[0]` (`cli.py:178`) cuts `Womans Institute Library of Cookery. Volume 2_ Milk, Butter and Cheese Eggs Vegetables.txt` at the first dot. The book is therefore stored as `"Womans Institute Library of Cookery"`, which does not match the `book_mappings` key at `cli.py:70`, so it gets no `author`/`year` metadata (`cli.py:135-138`; recorded: `{'book': 'Womans Institute Library of Cookery'}`).
- **Fix.** Use `os.path.splitext(filename)[0]`, **delete that book's old files** (`rm outputs/*"Womans Institute Library of Cookery.jsonl"`), then re-chunk, re-embed and re-load. Without the delete, `embed` and `load` pick up both the old and the new file, and the book is inserted twice under different ID hashes (checked, exercise B4).

**G18. The answer talks about things that are not in the books any more (or misses new text).**
- **Cause.** The index is a snapshot. Editing `input-datasets/books/` changes nothing until you re-run chunk → embed → load. The staff hit this themselves: `out.txt` (recorded 2026-09-22) retrieves "known as transhumance…" (`out.txt:73`). That text is in the *old* Tolminc book (`git show 85bba32^:"input-datasets/books/Tolminc Cheese.txt"`) but not the current one, which was replaced in the same commit.
- **Fix.** Rebuild the index whenever the corpus changes. Never mix embedding models or dimensions between index and query.

**G19. The web tools (chunkviz / chromaui / chat) do not load or show CORS errors.**
- **Cause.** The README insists on Chrome (`README.md:97-98`, `:164-165`, `:213-214`). The pages answered HTTP 200 on 2026-10-16, and Chroma's CORS answer for the course's origin was captured (§4 Step 3). Likely reasons for a failure (inferences, not verified: no browser in the captures): the HTTPS page calls `http://localhost:8000` from your browser, which other browsers may block as mixed content; newer Chrome versions may ask permission before a public site reaches a local address. This also needs the published port and the allowed origin (`docker-compose.yml:21-22`, `:25-26`).
- **Fix.** Use Chrome, allow the site to reach your local network if it asks, keep `8000:8000`, and make sure `llm-rag-chromadb` is running.

**G20. Secrets ending up in git or in an image.**
- **Cause.** If you put the key inside `llm-rag/` instead of `../secrets/`, it is *not* git-ignored (`.gitignore:1-5` has no `secrets` entry) and `COPY . ./` would bake it into the image.
- **Fix.** Keep `secrets/` a sibling. Before any push, check `git status` (captured at the end: only ` M docker-shell.sh`). If a key ever lands in a commit, delete the key in IAM; rewriting history is not enough.

**G21. Apple Silicon: nothing special is needed.**
- `python:3.12-slim-bookworm` and `chromadb/chroma` are multi-arch.
- Every locked package with native code ships `manylinux … aarch64` wheels. Per `uv.lock`, only `pypika` is source-only, and it is pure Python, which `build-essential` (`Dockerfile:4`) covers anyway.
- The banner prints `Architecture: aarch64` (the capture, on x86_64, printed `x86_64`). Do **not** add `--platform linux/amd64`; emulation would just slow everything down.

**G22. Windows: `sh` not found, or the container dies with `$'\r': command not found`.**
- **Cause.** `sh docker-shell.sh` (`README.md:84`) needs a POSIX shell (Git Bash or WSL), not PowerShell/cmd. Separately, the repo has no `.gitattributes`, so Git for Windows with `core.autocrlf=true` checks the `.sh` files out with CRLF endings. Because the repo is bind-mounted over `/app`, the container runs those CRLF copies, and `docker-entrypoint.sh` breaks inside Linux bash.
- **Fix.** Run from WSL (clone inside the WSL filesystem) or Git Bash, and re-clone with `git config --global core.autocrlf input` (or convert the two scripts to LF).

**G23. Retrieval returns Project Gutenberg licence text.**
- **Cause.** Ten of the eleven books still carry the full Project Gutenberg header and licence (from `*** START OF THE PROJECT GUTENBERG EBOOK` / up to and after `*** END OF …`): about 195 k characters in total, 7.2% of the corpus. It is chunked, embedded (and paid for) and retrievable like any other text; nothing in `chunk()` (`cli.py:180-181`) strips it. Captured: row 0 of every Gutenberg book is the header, and `--get` returns the header and licence as the first 10 records of *The Complete Book of Cheese*.
- **Fix.** Strip everything outside the START/END markers before chunking, then re-chunk, re-embed and re-load. Checked (exercise B3): 7,656 char-split chunks instead of 8,248, 592 fewer, all from the Gutenberg books. This is a good "data cleaning matters" moment.

**G24. The first start prints `failed to resolve reference "docker.io/library/llm-rag-cli:latest": … not found`.**
- **Cause.** Compose v5.6.0 first tries to *pull* an image named `llm-rag-cli` from Docker Hub, because `docker-compose.yml:7` names one; none exists, so it builds instead (captured, §4 Step 3). The README doesn't mention it.
- **Fix.** None needed: wait for `Image llm-rag-cli Building` and `Built`. It appears only on the first run (or after you delete the image).

**G25. `docker compose down` warns `The "GCP_PROJECT" variable is not set. Defaulting to a blank string.`**
- **Cause.** The variables are set only inside `docker-shell.sh`; your own terminal doesn't have them, and Compose interpolates the whole file even for `down` (captured, §4 Step 8).
- **Fix.** None needed: `down` uses neither variable, and the container and network are removed. (The same warning *before* a `run` is G5.)

**G26. "`docker compose down -v` wipes the database."**
- **Cause.** `-v` removes Docker *volumes*: named volumes declared in the compose file and anonymous ones. This compose file declares none; Chroma's data is a **bind mount** of your folder. Checked (exercise D4): after `down -v`, `docker-volumes/chromadb/chroma.sqlite3` is still there.
- **Fix.** To really start the index from scratch: `docker compose down`, then delete the folder (`sudo rm -rf docker-volumes` on Linux). Rarely needed: every `--load` deletes and recreates its collection anyway.

---

## 7. Where this sits in the course

**Before.**
- **L01-L02.** VMs, venvs and uv; one Dockerfile, `docker build` / `docker run`, images on Docker Hub.
- **L03 (`mega-pipeline` `main`).** Single-purpose containers calling Google AI APIs with `google-genai` on Vertex AI, authenticated by a service-account JSON via `GOOGLE_APPLICATION_CREDENTIALS`. The containers never talked to each other; a GCS bucket was the hand-off.
- **L04 (`mega-pipeline` `flexible-workflow` + `port_toy`).**
  - Secrets moved *outside* the repo and were mounted at `/secrets` by a `docker-shell.sh`.
  - Each student used their own SA.
  - `port_toy` taught Docker networks, DNS by container name, and published versus internal ports with Compose.
  - The [L04 guide](L04-containers-2b-flexible-workflow-ports.md) (§7) flags this repo as the first real consumer of those ideas (`docker-compose.yml:1-3`, `:20`; `cli.py:30-31`).

**What L05 adds.**
1. A **stateful service container**: a database server with a persistent bind-mounted data directory, started as a Compose dependency next to a disposable CLI container. It is the first time two of your containers talk over HTTP (captured: `getent hosts llm-rag-chromadb` → `172.19.0.2`, and the collections survive `docker compose down`).
2. The **RAG pattern**: chunking strategies, embedding APIs and vector dimensions, cosine/HNSW indexes, metadata and lexical filters, top-k retrieval and prompt assembly.
3. A **two-phase pipeline** (offline index, online query) whose intermediate artefacts (`outputs/*.jsonl`) are inspectable files. This is the shape that Milestone 2 asks LLM teams to reproduce: "data collection, chunking, and vector database integration … at least one complete retrieval flow from query to retrieved context" (`2026-AC215/milestone2.md:22`, `:53-54`).

**Evolution of this repo** (`git diff --stat origin/pipenv main`: the `pipenv` branch, last changed in March 2025, → this year's `main`):
```
 .gitignore                              |    3 +-
 Dockerfile                              |   37 +-
 Pipfile                                 |   21 -
 Pipfile.lock                            | 3066 -------------------------------
 README.md                               |  278 ++-
 agent_tools.py                          |  120 +-
 cli.py                                  |  844 +++++----
 docker-compose.yml                      |    9 +-
 docker-entrypoint.sh                    |   18 +-
 docker-shell.sh                         |   33 +-
 input-datasets/books/Tolminc Cheese.txt |  311 ++--
 out.txt                                 |  137 ++
 pyproject.toml                          |   15 +
 uv.lock                                 | 2592 ++++++++++++++++++++++++++
 14 files changed, 3703 insertions(+), 3781 deletions(-)
```
Meaningful changes:
- Pipenv → uv, with the venv at `/.venv`.
- `vertexai` SDK (`TextEmbeddingModel`, `GenerativeModel(system_instruction=…)`) → `google-genai` `Client(vertexai=True)`. In this migration (`59a0f80`, 2025-10-01) the system instruction stopped being applied (E1), so the Fall 2025 code already didn't send it.
- Models: `text-embedding-004` + `gemini-1.5-flash-002` in `us-central1` → `gemini-embedding-001` + `gemini-3.1-flash-lite` at `global`.
- Chroma 0.x (`/chroma/chroma`, `IS_PERSISTENT=TRUE`, CORS `["*"]`) → Chroma 1.x (`/data`, an explicit CORS allow-list).
- The script no longer runs `docker network create` or `docker build`; Compose owns both.
- The Tolminc book was replaced by a short fictional story (`85bba32`).

**After: what builds on this.**
- **L06 (Agents I)**, `2026-AC215/tutorials_demo.md:83-98`.
  - The README's **Agents** section on this same repo: `--agent`, Gemini function calling over `get_book_by_author` / `get_book_by_search_content` (`agent_tools.py`).
  - The *Cheese Quiz* Colab, which frames retrieved documents as one layer of "model context" ("Step 3: Retrieve Relevant Documents (e.g. RAG)").
  - `llm-agent-google-adk/6-rag`, which re-does RAG with Vertex AI RAG Engine and with a custom ChromaDB on port 8000 (`6-rag/2-custom-chromadb-rag/`).
- **L07 (Agent harness).** **L08 (fine-tuning)** is the alternative to RAG for injecting knowledge: it changes the weights instead of the prompt.
- **L10 (`cheese-app-v0`).** Ships `cheese-app-v0/llm-rag/`, a **near-verbatim copy** of this repo. `diff -r` shows: all code, the Dockerfile, the books and `out.txt` are identical; `docker-compose.yml:11` becomes `../../secrets:/secrets`; the README points the four web tools at the local front end (`http://localhost:3200/chunkviz`, `/chromaui`, `/chat`, `/agent`) and shows the nested folder layout; and the copy has no `.gitignore`. It is wired to an `api-service` (`api-service/api/routers/rag.py`) and a `frontend-ai-chatbot` (published on host port 3200, `frontend-ai-chatbot/docker-shell.sh:11`), so the CLI you ran today becomes a backend. That front end is presumably why `7a3c66b` ("updated for localhost") added `http://localhost:3200` to Chroma's CORS list.
- **Later cheese-app versions (v2-v4)** carry a `src/vector-db/` service with an older variant of this `cli.py`. Note that `cheese-app-v2/src/vector-db/cli.py:27` still names `text-embedding-004`, which the README here says was retired (`README.md:138`).

---

## 8. Exercises

The exercises, with full answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l05-rag/exercises.md) in the video folder. Their outputs are the 2026-10-16 captures, or were checked the same day in throwaway containers of the tutorial's own image (Python 3.12.15, uv 0.13.1, chromadb 1.1.0, google-genai 1.39.1, langchain-text-splitters 0.3.11) against the same Chroma server image, loaded with the staff's recorded vectors (`68e0bde`). There was no Google key: items marked *with your key* need one, and their answers say what was checked without it. Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. Which `cli.py` flags belong to each lane, and what must both lanes share?**
<details><summary>Answer</summary>

Indexing lane (the README's "Step 1: Chunk -> Embed -> Load", `README.md:5`): `--chunk` (`cli.py:164-227`), `--embed` (`:230-264`), `--load` (`:267-306`); it runs once, offline, and is slow. Query lane ("Step 2: Query -> Embed -> Retrieve -> LLM -> Generate Answer", `README.md:9`): `--query` (`:309-361`) and `--chat` (`:364-399`); it runs for every question. Both must use the same embedding model with the same settings, `gemini-embedding-001` with 256 numbers (`cli.py:25-26`), so question and chunks live in one space; Chroma checks only the size. Both also meet in the same collection, named by `--chunk_type` (`:277`, `:316`, `:370`). One exception to "chunking needs no key": `semantic-split` calls the model while chunking.
</details>

**Q2. Why does the CLI reach the database at `llm-rag-chromadb:8000`, and who uses the published port 8000?**
<details><summary>Answer</summary>

Compose puts both containers on the user-defined network `llm-rag-network` (`docker-compose.yml:1-3`), whose DNS answers container names: `getent hosts llm-rag-chromadb` printed `172.19.0.2` in the CLI container, and `cli.py:30-31` hard-codes that name and port. Port 8000 is Chroma's port inside its own container; another container on the network talks to it directly. `8000:8000` (`docker-compose.yml:21-22`) opens a door on your laptop for programs that aren't on the network: your `curl http://localhost:8000/api/v2/heartbeat`, and the course's Chroma UI page in Chrome, which CORS lets in (`docker-compose.yml:25-26`; captured `access-control-allow-origin`). The CLI never uses it: with `8001:8000` it keeps working.
</details>

**Q3. What does `chunk_overlap` buy and cost, and why did recursive-split make 14,228 chunks?**
<details><summary>Answer</summary>

It buys insurance against cutting an idea in half: char-split's 20-character overlap makes chunk 1 start `s she intended to accomplish`, so the word cut at the end of chunk 0 is whole in chunk 1. It costs repetition: every repeated character is embedded and paid for, stored, and can come back twice in the top 10. `cli.py:199-200` gives `RecursiveCharacterTextSplitter` only `chunk_size=350`, so it uses the library default `chunk_overlap=200` (story chunk 1 starts again at `## Chapter One`), and it cuts only at blank lines, line breaks and spaces, so every chunk ends before 350 characters (median 297). With overlap 0 the same splitter makes 10,542 chunks, with 20 it makes 10,551, with the default 200 it makes 14,228.
</details>

**Q4. Why did the README's `--query` return no Tolminc text?**
<details><summary>Answer</summary>

Only variant 4 runs (`cli.py:352-359`; variants 1-3 are commented out, `:325-350`, although the README promises "various types of filters", `README.md:186`). It asks for 10 results with `where={"book": "The Complete Book of Cheese"}` and `where_document={"$contains": "Italian"}`. Recorded counts: 8,248 chunks → 1,355 in that book → 64 containing "Italian" → **0** containing "Tolminc" (only 3 chunks of any book do). Chroma filters **first** and ranks what survives; with a stand-in query vector, no filter gave 10 story chunks at 0.0000-0.1627 and the code's filters 10 chunks of that book at 0.2833-0.3123. The lecture draws filtering after ranking (A54–A55); that order would have returned nothing. Fix: uncomment variant 1 (`cli.py:326-331`); variant 4 still prints after it.
</details>

**Q5. What is the tutorial's prompt missing compared with the lecture's final prompt, and what is the one-line fix?**
<details><summary>Answer</summary>

The lecture's final prompt is a system prompt, the user's query and the retrieved context (A57–A59). `chat()` sends only the last two: `INPUT_PROMPT` is the question plus the 10 chunks (`cli.py:388-391`), and the call is `generate_content(model=GENERATIVE_MODEL, contents=INPUT_PROMPT)` (`:394-396`). `SYSTEM_INSTRUCTION` (`:40-58`) exists but `grep -n SYSTEM_INSTRUCTION cli.py` finds only line 40. The fix is one argument: `config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION)` (full code in §9 E1). Checked without a key by capturing the request just before it leaves: as committed its body holds only `contents`; with the fix it also carries `systemInstruction`. The `pipenv` branch did send it (`git show 0b671ed:cli.py`, lines 62-64).
</details>

### Hands-on (predict, then run)

**B1. Bigger chunks.** Set `chunk_size = 700` and `chunk_overlap = 100` on `cli.py` lines 185-186; predict the story's chunk count, run `python cli.py --chunk --chunk_type char-split` and `wc -l outputs/chunks-char-split-*.jsonl`. What else must run before `--chat` uses the new chunks?
<details><summary>Answer</summary>

1 + ⌈(7,808 − 700)/600⌉ = **13** for the story, **4,537** in total (against 24 and 8,248). The load step reads the `embeddings-…` files (`cli.py:293-294`), which only `--embed` writes, so run `--embed` (with your key: 51 calls instead of 89) and then `--load` for `char-split`. Each retrieved chunk carries twice the context, so chat's prompt grows from about 3,500 to about 7,000 characters. Undo with `git checkout cli.py`, then chunk (and embed and load) again.
</details>

**B2. Make the hidden overlap visible.** On `cli.py` line 200, pass `chunk_overlap=20` to the recursive splitter and rerun the recursive chunk step and its `wc -l`. Back to 8,248, or between?
<details><summary>Answer</summary>

Between: **10,551** in total, **28** for the story (overlap 0: 10,542 and 28). The overlap made about 3,700 of the 14,228; the rest of the difference from char-split is the cutting rule (chunks stop before 350 characters at a boundary).
</details>

**B3. Strip the Project Gutenberg header and licence.** Add six lines after `input_text = f.read()` (line 181) that keep only the text between `*** START OF` and `*** END OF` (the code is in `exercises.md`), then chunk again and count.
<details><summary>Answer</summary>

**7,656** char-split chunks instead of 8,248: 592 fewer (7.2%), all from the ten Gutenberg books; the story keeps its **24** (it has no markers). Two chunks still mention Project Gutenberg (a closing line that one book places before its END marker, and a note at the start of another): markers do most of the cleaning, not all of it. To use the cleaner chunks, embed (81 calls instead of 89) and load again.
</details>

**B4. The book that lost its author.** Fix `cli.py` line 178 to `book_name = os.path.splitext(filename)[0]` and chunk again without deleting anything. Predict the new file name and the `Number of files to process:` of the next embed.
<details><summary>Answer</summary>

The new file is `chunks-char-split-Womans Institute Library of Cookery. Volume 2_ Milk, Butter and Cheese Eggs Vegetables.jsonl`, **beside** the old one, and the embed step prints `Number of files to process: 12`. Embedding and loading now would insert the book twice, under different ID hashes. Delete the old files first: `rm outputs/*"Womans Institute Library of Cookery.jsonl"`, then chunk both types again and, with your key, embed and load.
</details>

**B5. Same IDs, different chunks.** After loading both collections, run `python cli.py --get --chunk_type char-split` and `--chunk_type recursive-split`. Predict the IDs of the second run.
<details><summary>Answer</summary>

The same ten, `1021665fac86c5a5-0` … `-9`: an ID is the book name's hash plus the row number (`cli.py:127-130`), and both chunkers number rows from 0. The documents differ (350-character windows against 283-346-character, word-bounded chunks). An ID names a row within one collection, not a passage of the book.
</details>

**B6. Turn the system instruction on** *(with your key)*. Change the question on line 372 to `"What is the capital of France?"`, run `--chat`, then add the fix from Q5 and run it again.
<details><summary>Answer</summary>

Both runs retrieve 10 cheese chunks: there is no distance threshold. As committed, expect a plain answer from the model's memory. With the fix, `SYSTEM_INSTRUCTION` says to use only the chunks and to "politely redirect the conversation back to cheese-related subjects" (`cli.py:54`): expect a refusal or a redirect. Not run (no key); checked only that the fix sends `systemInstruction`.
</details>

**B7. Semantic chunking on one book** *(with your key)*. Move every book but the story aside (§4 Step 12), run the README's semantic command, and predict the chunk phase's embedding calls, its `Number of chunks:`, and the number `--chat --chunk_type semantic-split` prints after `Results:`.
<details><summary>Answer</summary>

**3 calls** (108 sentence windows in batches of 50), **7 chunks** (107 gaps, the 6 above the 95th percentile are cut; the count doesn't depend on the vectors' values), **1 call** to embed them (batches of 15), and chat prints **7**: it asks for 10 and Chroma returns what exists. For all eleven books (counted with a stand-in embedding function): 26,080 windows → 528 calls to chunk, 1,318 chunks → 92 calls to embed. Put the books back afterwards.
</details>

### Debugging

**C1. "Collection does not exist."** After the char- and recursive-split steps, `python cli.py --chat --chunk_type semantic-split` prints the embedding values, then `chromadb.errors.NotFoundError: Collection [semantic-split-collection] does not exist`. Why, and what are the fixes?
<details><summary>Answer</summary>

Each chunk type has its own collection (`cli.py:277`, `:370`), and only the load step creates one; the semantic command never ran, or failed before its load. Chat embeds the question first (`:373`), so the call was paid before `get_collection` (`:377`) failed. `--get --chunk_type semantic-split` shows the same error with no key. Use a chunk type you loaded, or build the semantic one (B7). The collections `curl` on the laptop lists what exists.
</details>

**C2. "Could not connect to a Chroma server."** A student runs `python cli.py --get --chunk_type char-split` from a Python 3.12 venv on the laptop, with Chroma up. Why does it fail?
<details><summary>Answer</summary>

The first exception of the chain is `httpx.ConnectError: [Errno -2] Name or service not known`: `CHROMADB_HOST = "llm-rag-chromadb"` (`cli.py:30`) exists only in Docker's DNS on `llm-rag-network`. Run it in the container, or make the host configurable (`os.environ.get("CHROMADB_HOST", "llm-rag-chromadb")`, then `export CHROMADB_HOST=localhost`, the published door); checked, `--get` then returns the ten IDs. Earlier traps on the way: `KeyError: 'GCP_PROJECT'`, and the f-string at `cli.py:388-391` needs Python 3.12.
</details>

**C3. Port 8000 is taken, and then something stranger.** `sh docker-shell.sh` fails with `Bind for 0.0.0.0:8000 failed: port is already allocated`; after stopping the other program it starts, but `llm-rag-chromadb` has an empty PORTS column and every Chroma step says `Could not connect`. Explain both.
<details><summary>Answer</summary>

Another program holds port 8000 on the laptop. The failed start left a half-made `llm-rag-chromadb` in state `Created`; the next start reuses it, and on Docker Engine 29.8.2 it runs with no network at all (reproduced three times). Fix: `docker compose down` after freeing the port, then `sh docker-shell.sh` (G6).
</details>

**C4. "The container name is already in use", or silently someone else's database.** (a) The `Conflict. The container name "/llm-rag-chromadb" is already in use …` error. (b) Two copies of the repo, both folders called `llm-rag`: no error, but `--query` fails with `NotFoundError`. Explain both.
<details><summary>Answer</summary>

`container_name: llm-rag-chromadb` (`docker-compose.yml:20`) is machine-wide, and Compose names a project after its folder. (a) The name belongs to another project or to none: `docker compose down` there, or `docker rm -f llm-rag-chromadb`. (b) Both copies are the *same* project: Compose recreates Chroma with the other copy's `docker-volumes/` mounted, which holds no collections. `docker compose down`, start from the copy you meant, and keep one copy (G7).
</details>

**C5. The dimension trap.** A teammate sets `EMBEDDING_DIMENSION = 768` (`cli.py:26`) and reruns `--chat` without re-embedding, then replaces `query_embeddings=` with `query_texts=[query]`. What happens each time?
<details><summary>Answer</summary>

768 numbers: `chromadb.errors.InvalidArgumentError: Collection expecting embedding with dimension of 256, got 768` (the first insert fixed 256). `query_texts`: Chroma embeds the text itself with its default embedding function, a small local model it downloads first (79 MB) that makes 384 numbers: `Collection expecting embedding with dimension of 256, got 384`. Had the sizes matched, the query would run and return nonsense from another space. Change model or dimension only together with a full re-embed and re-load.
</details>

**C6. A package that disappears.** `uv add rank-bm25` in the container works; the next day, after `exit` and a new start, `import rank_bm25` fails although `pyproject.toml` lists it. Why?
<details><summary>Answer</summary>

`uv add` edited `pyproject.toml` and `uv.lock` in `/app` (your laptop folder, so the edits stayed) and installed into `/.venv`, which lives in the container (`Dockerfile:18`), deleted on exit. The next start uses the old image: Compose builds only when the image is missing. `docker compose build`, then `sh docker-shell.sh` (checked: `Installed 124 packages`, one more than before). Commit both files (G16).
</details>

**C7. `PermissionError` on a Linux laptop.** With uid 1001, chunking ends in `PermissionError: [Errno 13] Permission denied: 'outputs'` (from `os.makedirs`, `cli.py:168`); on a Mac it works. Why?
<details><summary>Answer</summary>

The container runs as `app`, uid 1000 (`Dockerfile:31`, `:38`), and writes into your folder through the bind mount; on Linux the folder keeps your uid 1001 and mode `drwxr-xr-x`. Docker Desktop maps ownership for you. Fix: `mkdir outputs && chmod a+w outputs` (checked: chunking then writes 11 files). Chroma's folder is the reverse: root's, so deleting it needs `sudo` (G14).
</details>

### Think

**D1. Does the distance measure matter?** Without `metadata={"hnsw:space": "cosine"}` (`cli.py:287-288`), would the 10 nearest chunks change? When would they not?
<details><summary>Answer</summary>

Chroma would use `l2`. For vectors of length 1, ‖a − b‖² = 2 − 2·cos(a, b), so both rank identically. These vectors aren't length 1 (0.342 to 0.405 for all char-split vectors), so length leaks into L2: by brute force, the L2 top 10 equals the cosine top 10, in the same order, for only 5.6% of the 8,248 stored vectors used as queries (32% as the same set). After scaling every vector to length 1, they agreed on all 165 sampled queries. Keep cosine, or normalise every vector (A45–A47).
</details>

**D2. Why did the staff's run find "transhumance"?** `out.txt:73` retrieved it, but `grep -c transhumance "input-datasets/books/Tolminc Cheese.txt"` prints `0`. Then: which of (a) editing a book, (b) a new `chunk_size`, (c) a new `GENERATIVE_MODEL`, (d) a new `EMBEDDING_MODEL` or `EMBEDDING_DIMENSION`, (e) a new question need chunk → embed → load again?
<details><summary>Answer</summary>

The database answered from what had been loaded: the book before `85bba32` (its parent `96d5fd7`) had `transhumance` on 3 lines, and `85bba32` replaced it with today's story and added `out.txt` in the same commit. The query side never reads `input-datasets/`. (a) Yes. (b) Yes. (c) No: the generative model only reads the prompt. (d) Yes, all of it. (e) No.
</details>

**D3. Write a `.dockerignore` for this repo.** What goes in, what must stay out of it, and what changes?
<details><summary>Answer</summary>

`.git`, `outputs/`, `docker-volumes/`, `__pycache__/` (and `secrets/` as a guard). Never exclude `pyproject.toml`, `uv.lock` (`Dockerfile:42`) or `docker-entrypoint.sh` (`Dockerfile:51`). Checked on a folder with full `outputs/` and a loaded database: context 257.74 MB → 4.58 MB, `/app` in the image 247 MB → 4.5 MB, image 2.31 GB → 1.89 GB. At run time nothing changes (the bind mount covers `/app`); every build and every push gets smaller, and nothing copied by accident ships with the image.
</details>

**D4. A clean slate?** After `docker compose down -v`, what is still on your laptop, and how would you really start the index from scratch?
<details><summary>Answer</summary>

`-v` removes volumes, and this compose file has none: Chroma's data is a bind mount, so `docker-volumes/chromadb/chroma.sqlite3` stays (checked; `docker volume ls` empty). Also still there: the images (2.11 GB and 826 MB), `outputs/`, the key and, in Google Cloud, the service account and its key. From scratch: `docker compose down`, then `sudo rm -rf docker-volumes` on Linux. Rarely needed: every load rebuilds its collection (`cli.py:280-289`).
</details>

**D5. Pin the database server.** What did `chromadb/chroma:latest` mean on the recording day, why is it a problem for a team, and what would you write instead?
<details><summary>Answer</summary>

On 2026-10-16 Docker Hub listed `latest` and `1.5.9` with one digest, `sha256:1e0b73a1…` (created 2026-05-05); inside it `chroma --version` says 1.4.4 and the API `"1.0.0"`, against the 1.1.0 client in `uv.lock`. It worked, but `latest` is whatever was newest when each student first pulled it. Write `chromadb/chroma:1.5.9` or the digest, and upgrade server and client together on purpose.
</details>

**D6. Fuse a fourth paragraph.** In the lecture's hybrid-search example (B44–B48), add a paragraph that both retrievers rank 2nd, pushing the others down, and compute the RRF order with k = 0 and with k = 60 (w = 0.5).
<details><summary>Answer</summary>

New ranks (BM25, vectors): 1 (3, 1), 2 (1, 4), 3 (4, 3), 4 (2, 2). k = 0: 0.667, 0.625, 0.292, 0.500, so the order is 1, 2, 4, 3. k = 60: 0.016133, 0.016009, 0.015749, 0.016129, so 1, 4, 2, 3. A larger k flattens rank differences, so being good in both lists beats being best in one. The tutorial has no keyword retriever and no fusion: `$contains` only filters.
</details>

**D7. The personality game with a ruler.** In the lecture's game (A40–A47), cosine similarity picks the first candidate and the dot product the second. Who wins with Euclidean distance?
<details><summary>Answer</summary>

The first candidate, 1.673 against 2.093 and 4.498: Euclidean distance squares each trait's difference, so the second candidate's one big gap (emotional stability) costs a lot. Three measures, two winners: the measure is a modelling choice. For text embeddings meaning lives in the direction, and the tutorial's vector lengths (0.34 to 0.41) mean nothing, so compare directions: cosine (D1).
</details>

---

## 9. Errata and open questions

**Errata (with evidence)**

- **E1. The system instruction is never used, so "grounded" is weaker than the README implies.**
  - `SYSTEM_INSTRUCTION` is defined at `cli.py:40-58` but no call passes it: `grep -n SYSTEM_INSTRUCTION cli.py` finds only line 40.
  - `chat()` calls `generate_content(model=GENERATIVE_MODEL, contents=INPUT_PROMPT)` with no `config` (`cli.py:394-396`).
  - The `pipenv` branch (March 2025) applied it via `GenerativeModel(GENERATIVE_MODEL, system_instruction=[SYSTEM_INSTRUCTION])` (`git show 0b671ed:cli.py`, lines 62-64). It was commented out during the uv/genai migration (`59a0f80`, `4a5f347`, 2025-10-01) and never re-attached.
  - Checked without a key by capturing the request just before it leaves: as committed, its body holds only `contents`; with the fix below it also carries `systemInstruction` (exercise Q5).
  - Meanwhile the README says the LLM "answers grounded in your documents, not its own training data" (`README.md:21`).
  - Suggested fix (not in the repo):
    ```python
    response = llm_client.models.generate_content(
        model=GENERATIVE_MODEL,
        contents=INPUT_PROMPT,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
    )
    ```
- **E2. The README's description of `--query` does not match the code.**
  - The README says "Perform similarity searches in the vector database / Apply various types of filters on the queries" (`README.md:185-186`).
  - Only variant #4 runs (`cli.py:352-361`); #1-#3 are commented out (`cli.py:325-350`). #4 restricts results to *The Complete Book of Cheese* chunks containing "Italian", a book with zero mentions of Tolminc, so the sample query's results are unrelated to the question. Recorded with Chroma itself: 8,248 → 1,355 → 64 candidates, 0 containing "Tolminc" (§4 Step 9).
  - This is good for teaching filters, but confusing if unexplained.
- **E3. Wrong label.** `query()` prints `load()` (`cli.py:310`); captured as the first line after the arguments (§4 Step 9).
- **E4. Query text inconsistency.** The README says the chat sample query is "How is tolminc cheese made?" (`README.md:205`), while the code uses `"How is tolminc cheese made??"` (`cli.py:372`, changed in `96d5fd7`). `query()` uses a single "?" (`cli.py:318`). Harmless, but the printed output differs from the README.
- **E5. Over-privileged role.** The README asks for **Storage Admin** (`README.md:57`), but no code touches Cloud Storage. Only the Vertex AI role is needed. Least privilege says drop it.
- **E6. Missing step: enabling the Vertex AI API.** It is not mentioned anywhere in `README.md:45-69`. Without it, the first embed fails with SERVICE_DISABLED, after about 2.5 minutes of retries (G4).
- **E7. `out.txt` is stale and belongs to L06.** It is the staff's `--agent` run (`out.txt:1`) recorded 2026-09-22 (`out.txt:34`) against a DB loaded from the pre-`85bba32` Tolminc book. Its retrieved text ("transhumance", PDO rules, the Soča Valley) is absent from the current book (§8 D2). Do not expect to reproduce it.
- **E8. Book-name truncation drops metadata for one book.**
  - `filename.split(".")[0]` (`cli.py:178`) turns `Womans Institute Library of Cookery. Volume 2_ Milk, Butter and Cheese Eggs Vegetables.txt` into `Womans Institute Library of Cookery`.
  - That no longer matches the key at `cli.py:70`, so the 1,505 char-split chunks of that book carry no `author`/`year` (recorded: `{'book': 'Womans Institute Library of Cookery'}`). The fix needs the old files deleted too (G17).
  - Relatedly, for L06, the agent's author enum (`agent_tools.py:19-29`) omits both "Milk Industry Foundation" and "Woman's Institute of Domestic Arts and Sciences".
- **E9. Unpinned server image.** `chromadb/chroma:latest` (`docker-compose.yml:19`) carried the same digest as `1.5.9` on Docker Hub on 2026-10-12 and 2026-10-16, against a client locked at 1.1.0 (`uv.lock:289-290`). Captured inside it: `chroma --version` → `chroma 1.4.4`, `GET /api/v2/version` → `"1.0.0"`. It works (the captured loads and queries ran), but different students can get different servers.
- **E10. Folder-name coupling.** `../llm-rag:/app` (`docker-compose.yml:12`) silently requires the clone to be named `llm-rag`. The README's folder diagram (`README.md:66-69`) shows this but never says it is mandatory. Captured with a clone named `llm-rag-main`: exit 127 and a root-owned empty `../llm-rag` (G1).
- **E11. Unused dependencies and imports.** `openai` and `openai-agents` (`pyproject.toml:12-13`) are never imported. `GenerationConfig` and `ToolConfig` are imported at `cli.py:13`, but the code uses the `types.` versions. This only makes the image bigger.
- **E12. Cosmetic.** `docker-entrypoint.sh:6` prints "Virtual environment activated." before activation happens at line 12 (captured: three lines before `Activating virtual environment...`).
- **E13. Undocumented flag.** `--get` (`cli.py:499-500`, `:536-540`) exists but is not in the README. It needs no key (captured, §4 Step 11).
- **E14. Hidden default overlap.** The README says chunks are "small, overlapping" (`README.md:17`, `:93`) but never states that recursive-split uses the library default `chunk_overlap=200`, more than half the 350-char chunk size, versus 20 for char-split. Captured: the story's recursive chunk 1 starts again with `## Chapter One…`, the end of chunk 0, and the split makes 14,228 chunks against char-split's 8,248 (§4 Step 5).
- **E15. No `.dockerignore`.** `COPY . ./` (`Dockerfile:48`) copies everything: captured, the first build's context was 112.26 MB and the image holds `/app/.git` (103 MB) and a copy of `chroma.sqlite3`; rebuilds add `outputs/` and the loaded database (G15).
- **E16. Possible quality improvement (not a bug).** Neither embedding call sets `task_type` (`cli.py:76-83`, `:98-103`), so chunks and questions are embedded identically. `gemini-embedding-001` supports asymmetric `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY` task types (google-genai sends `task_type` per instance when set, `_EmbedContentConfig_to_vertex` in the wheel), which usually improves retrieval. Vertex's default when it is unset is believed to be `RETRIEVAL_QUERY`; verify in the docs.
- **E17. Numbering mismatch on the course site.** `2026-AC215/tutorials_demo.md:71` calls this "Lecture 5", while `2026-AC215/_modules/week-03.md:5-7` lists "LLM - RAGs" on Sep 15 as "Lecture 4".
- **E18. Uncleaned corpus.** The ten Gutenberg books still include the Project Gutenberg header and licence, ~195 k characters (7.2% of the corpus) that are chunked, embedded and retrievable (G23; captured: `--get` returns the header as the first records). The README's "This will: Read each text file…" (`README.md:114`) does not mention any cleaning, and `chunk()` does none (`cli.py:180-181`).
- **E19. A container name that isn't used.** `container_name: llm-rag-cli` (`docker-compose.yml:9`) suggests the CLI container is called `llm-rag-cli`, but `docker compose run` ignores `container_name`: the captured container is `llm-rag-llm-rag-cli-run-90678535ddef`. Harmless, but `docker inspect llm-rag-cli` finds nothing; take the name from `docker ps`.
- **E20. Silent first-run noise.** On the first `sh docker-shell.sh`, Compose v5.6.0 prints `failed to resolve reference "docker.io/library/llm-rag-cli:latest": … not found` before it builds (G24), and every `docker compose down` from your own terminal warns about two unset variables (G25). The README mentions neither; both are harmless.
- **E21. A heavy clone.** The reverted "Demo podcast" PR committed the staff's 90.9 MB `chroma.sqlite3` and their `outputs/` (`68e0bde`); `58dd602` and the revert `d9ced19` removed them from the tree, but not from the history. Every clone's `.git` is 103 MB (captured), and with no `.dockerignore` the image carries it too (E15).

**Open questions (could not determine from the sources)**

- **Q1.** What the Ed lesson adds beyond the slides (quiz, extra instructions). The Ed lesson was not accessible; the lecture slides were, and are covered in [Lecture slides](#lecture-slides).
- **Q2. Batch embedding with `gemini-embedding-001` on Vertex.** `generate_text_embeddings` sends up to 100 texts per `:predict` request (`cli.py:91-103`), and the comment claims "Max batch size is 250" (`cli.py:88`), a limit that dates from `text-embedding-004`. Early Vertex docs appear to have limited `gemini-embedding-001` to one input per request (not confirmed). The only staff evidence (`out.txt`) shows single-text query embeddings succeeding at `global`; the batch path (`--embed`, and the semantic splitter) was switched to this model in `74dba4a` with no captured run. New evidence, indirect: the staff committed `embeddings-*` files for both chunk types in `68e0bde` (2026-10-07), made with `gemini-embedding-001` (256 numbers each), and that commit's `cli.py` has the same batch sizes (`batch_size=100` and `15`), which suggests that batches worked for them on that date. If batch embed fails with `400 INVALID_ARGUMENT`, set the batch size to 1 (slower) in all three places: `cli.py:250` (15), `cli.py:253` (100) and `semantic_splitter.py:206` (50); or check the current limits.
- **Q3. Model availability.** `gemini-3.1-flash-lite` at location `global` worked for the staff on 2026-09-22 (`out.txt:34`, `model_version='gemini-3.1-flash-lite'`). Whether it is enabled for every student project, and for how long, could not be checked.
- **Q4. Role naming.** The README's "Gemini Enterprise Agent Platform User" (`README.md:58`) is presumably the renamed Vertex AI User role (`roles/aiplatform.user`). The console label was not confirmed.
- **Q5. The web tools.** `/chunkviz`, `/chromaui`, `/chat` and `/agent` on `ac215-llm-rag.dlops.io` are not in this repo; all four answered HTTP 200 on 2026-10-16. The CORS setting (`docker-compose.yml:25-26`) suggests that `/chromaui` talks to *your* local Chroma at `localhost:8000`, and the captured CORS answer confirms that Chroma lets that origin read it (§4 Step 3). Supporting evidence from the L10 copy of these pages: in `cheese-app-v0/frontend-ai-chatbot`, the Chroma UI form defaults to `url: 'http://localhost:8000'` (`src/app/chromaui/page.jsx:24`) and calls Chroma's `/api/v2/...` endpoints straight from the browser (`src/services/DataService.js:22`, `:43`), while chat goes through the API service (`BASE_API_URL + "/rag/llm-response"`, `DataService.js:13`). Whether the hosted `ac215-llm-rag.dlops.io` site is built the same way, why Chrome is required, and whether Chrome's permission prompt for public sites reaching local addresses gets in the way, could not be verified (no browser in the captures).
- **Q6. Long semantic chunks.** Semantic chunks can be several thousand characters, and `semantic_splitter.py` places no cap on them. It was not verified whether Vertex silently truncates over-long inputs for `gemini-embedding-001` (an `autoTruncate` default) or rejects them.
- **Q7. Exact prices.** The cost table in §2 uses an assumed ~$0.15 / 1 M tokens for embeddings and an approximate 4 characters per token. Check the current Vertex AI pricing page.
- **Q8. Three version numbers.** Why an image that Docker Hub lists as both `latest` and `1.5.9` reports `chroma 1.4.4` from its CLI and `"1.0.0"` from its API could not be determined from the sources; the captured loads and queries worked with the 1.1.0 client regardless.

---

## Links

- README sections (pinned commit): [What you'll build](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#what-youll-build) · [Prerequisites](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#prerequisites) · [Setup GCP Service Account](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#setup-gcp-service-account) · [Run LLM RAG Container](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#run-llm-rag-container) · [Chunk Documents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#chunk-documents) · [Generate Embeddings](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#generate-embeddings) · [Load Embeddings into Vector Database](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#load-embeddings-into-vector-database) · [Query the Vector Database](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#query-the-vector-database) · [Chat with LLM](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#chat-with-llm) · [Advanced RAG: Semantic Chunking](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#advanced-rag-semantic-chunking-semantic-splitting) · L06 preview: [Agents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#agents) · latest README on [`main`](https://github.com/dlops-io/llm-rag#building-a-rag-system-with-vector-db-and-llm) · the [`pipenv` branch](https://github.com/dlops-io/llm-rag/tree/pipenv) (March 2025)
- Video: [AC215 · L05 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l05-rag) · its [exercises](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l05-rag/exercises.md) · the real [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l05-rag/assets/terminal) and their provenance, [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l05-rag/ASSETS.md) · the lecture-slide digest, [`SLIDES.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l05-rag/SLIDES.md)
- Ed lesson: [L05 · Introduction to RAG](https://edstem.org/us/courses/97373/lessons/182195/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab: none for L05. The L06 [Cheese Quiz (Colab)](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) is cited in §7.
- Web tools (optional, Chrome; not in the repo, see §9 Q5): [chunkviz](https://ac215-llm-rag.dlops.io/chunkviz) · [chromaui](https://ac215-llm-rag.dlops.io/chromaui) · [chat](https://ac215-llm-rag.dlops.io/chat) · [agent](https://ac215-llm-rag.dlops.io/agent)
- Previous lecture: [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md) (Compose networks, DNS by container name, published ports, secrets mounted at `/secrets`)
- Next lecture: [L06 · LLM: Agents I](L06-agents-1.md) (the README's Agents section on this same repo: `--agent` and function calling)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II](L03-containers-2-mega-pipeline.md) · [L07 · LLM: Agents II](L07-agents-2-harness.md) · [L08 · LLM: Finetuning](L08-llm-finetuning.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md)
