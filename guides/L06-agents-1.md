# L06 · LLM: Agents I — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166030/) · Tutorials: [`dlops-io/llm-rag`](https://github.com/dlops-io/llm-rag) `main` @ [`e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91) (README section "Agents"; tree identical to [`7a3c66b`](https://github.com/dlops-io/llm-rag/tree/7a3c66b777e7d4048b45f59b7223422325f1a281)) and [`dlops-io/llm-agent-google-adk`](https://github.com/dlops-io/llm-agent-google-adk) `main` @ [`f89faa7`](https://github.com/dlops-io/llm-agent-google-adk/tree/f89faa79de744f6a046e30dff24b3b6f1d73720b) (whole repo) · Colab: [Cheese Quiz](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) · [Travel Planner](https://colab.research.google.com/drive/1I_jJEHJsVkGxNoSC1c4wEoVF2QL6vCVY?usp=sharing) · [Cheese Newsletter · Harness](https://colab.research.google.com/drive/1nnHrJ4Si3tpgUQl6HqlcwxKymV1-ecPv?usp=sharing) · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** L05 里 retrieval 是你写死的 top-10；L06 让 **LLM 自己决定怎么 retrieve**，分三层做：(1) 在 `llm-rag` container 里跑 `python cli.py --agent --chunk_type char-split`，Gemini 3.1 Flash-Lite 拿到两个 function declaration（按 author 搜一本书 / 搜全部的书），你的 Python 去查 L05 建好的 ChromaDB，再调第二次 Gemini 写答案；(2) 在本机用 uv 跑 Google ADK（`uv run adk web`），六个 module：SequentialAgent travel planner、LiteLLM、MCP filesystem tools、FastAPI、custom agent、RAG；(3) 三个 OpenAI Colab：Cheese Quiz（LLM → workflow → agent → context → tools/MCP → 六个 agent 的 Guild）、Travel Planner、Cheese Newsletter。
- **Idea 1 · 谁握方向盘：** workflow 的 `if`/`for` 写在你的 code 里；agent 的 control flow 由 model 决定，你的 code 只是一个听话的 loop。三次跑的都是同一个 `gpt-4o`，变的只是 loop 和 tools。
- **Idea 2 · function calling：** model 只"写" call（`{name, args}`），你的 code 才"执行"它，结果包成 `function_response` 送回去，model 再写答案。Gemini 从来没碰过你 `localhost` 上的 ChromaDB。`mode="any"` 是**强制** function call，不是"可以 call"。
- **Idea 3 · agent loop：** ADK 的核心就是一个 `while True:`，直到 `is_final_response()`（没有 function call/response、不是 partial）才停；OpenAI Agents SDK 用 `max_turns`（notebook 设成 12），Microsoft Agent Framework 用 `max_iterations`。`llm-rag --agent` 不是 loop，是固定的两次 call。
- **Idea 4 · state 和 MCP：** ADK 里 `output_key="x"` 把 agent 的 final text 写进 `session.state["x"]`，下一个 agent 的 instruction 里的 `{x}` 会被替换成这个值；sub-agents 之间不直接传 message。MCP 把 tool 做成可插拔的 server（stdio child process 或 HTTP），`tool_filter` 限制 model 能要哪些 tool。
- **Idea 5 · harness：** model 选 action，Python 决定这个 action 算不算数。Travel Planner 的价格全部由 Python 算（$2690 可以手算验证），`finalize_itinerary` 只产生 pending proposal，要下一轮 human 输入 "yes" 才 approve；Newsletter 的成功 = 有 `receipt` 而且 HTML file 真的在 disk 上，不是 model 说 "done"。只写在 prompt 里、没有 code 检查的规则（"no URLs"）靠不住：saved run 的 HTML 里照样出现了 `Promotion URL: https://…`。
- **最费时间的坑：** ① ADK repo 没有 lockfile（`uv.lock` 被 gitignore），今天 `uv sync` 装的是 google-adk 2.11.0，一选 `1-baseline` 就报 `Invalid agent name`；先 `uv add "google-adk>=1.8.0,<1.28"`（→ 1.27.5）再 `uv sync`。② 除了 `6-rag/1-vertex-rag-engine`（写死 `gemini-2.5-flash`），每个 `agent.py` 的 fallback `gemini-2.0-flash` 都已经在 2026-06-01 shut down：root `.env` 里写 `GEMINI_MODEL=gemini-3.1-flash-lite`，也别随手 copy module 的 `.env.example`，ADK 用 `override=True` 加载离 agent 最近的 `.env`。③ port 8000 冲突：`adk web` 和 llm-rag 的 ChromaDB 都要 8000，`exit` container 之后 `llm-rag-chromadb` 还在跑，要 `docker compose down`，或者 `uv run adk web --port 8080`。
- **别拿 `out.txt` 对答案：** `out.txt` 里的答案（Soča Valley、transhumance）是用 2026-09-22 改写 Tolminc 书之前的旧 index 跑的，README 流程图里的答案（"Slovenian Alps"）也来自旧书，今天你会得到 Mara 和她爷爷的故事。agent 查的是 L05 的 `char-split-collection`，没有的话先跑 `python cli.py --chunk --embed --load --chunk_type char-split`。
- **做完要删：** llm-rag `exit` 之后在 `llm-rag/` 里 `docker compose down`；`adk web` / `uvicorn` 用 Ctrl+C；6-rag 的 ChromaDB `docker compose down`（加 `-v` 连 volume 一起删）；做了 `6-rag/1-vertex-rag-engine` 的话，用 `setup_corpus.py` 的 option 5 删掉 RAG Engine corpus；三个 Colab 都 *Runtime → Disconnect and delete runtime*；不用的 service-account key 删掉，`secrets/` 和 `**/.env` 永远不要 commit。
- **Lecture slides：** 老师的 Lecture 6 slides（56 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天的 repo/notebook 不一样的 7 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slide 26 说 agent 会自己一直跑到任务完成，但 `llm-rag --agent` 只有一次强制的 tool call 加一次回答，没有 loop，loop 要到 ADK 和 notebook 里才有；② slides 10、13、33 里 agent 可以决定**不** retrieve，而 `mode="any"`（`cli.py:449`）逼 Gemini 每次都 call tool：它只能选搜哪本书，不能选搜不搜（Exercise 2 把这个选择还给它）。

## At a glance

**What you build.** An agent that lets Gemini choose how to search your L05 ChromaDB collection through function calling (`python cli.py --agent` inside the `llm-rag` container), then the same idea with Google's Agent Development Kit run locally (`uv run adk web`: a sequential travel planner that shares session state, MCP filesystem tools, a FastAPI wrapper, custom routing agents) and in three OpenAI Colab notebooks that climb from a single LLM call to a six-agent quiz guild. The last two notebooks add a harness, where Python owns the arithmetic, a human approval gate and the definition of success (a receipt for a file on disk).

**Time needed** (estimate).
- Cheese Quiz: about 1 h (dozens of `gpt-4o` calls; the two guild runs take a while).
- llm-rag Agents: 15-30 min if L05's `char-split-collection` is loaded; add a few minutes of embedding calls if you have to rebuild it (§4 B2).
- ADK repo: 1.5-2 h. The first `uv sync` downloads PyTorch (G13), and module 3 needs Node.js. The optional `6-rag` module adds about an hour.
- Travel Planner and Newsletter: about 30-45 min each.
- Exercises: 1-2 h more.

**Prerequisites.**
- L05 done: the `llm-rag` clone next to `secrets/llm-service-account.json` (the service account has Vertex AI User), the Vertex AI API enabled, `docker-shell.sh:7` pointing at your project, and a loaded `char-split-collection` (or rebuild it, §4 B2).
- Docker Desktop with Compose v2, `uv`, Node.js + npm (`npx`), Git.
- Keys: a Google AI Studio API key (ADK repo) and an OpenAI API key with billing (Colab secret `OPENAI_API_KEY`; also ADK `2-litellm`).
- Background: Compose networks, ports and mounted secrets (L04); chunking, embeddings and the vector DB (L05).

**What it costs.** Small, but not zero (§2). Pennies for Vertex embeddings, and only if you rebuild the collection. Negligible Gemini tokens for the agent run (247 + 1,269 tokens recorded). Cents to low dollars of OpenAI per full notebook run; the hosted web search tool is billed per call on top of tokens. The Gemini API free tier may cover the ADK exercises. The optional Vertex AI RAG Engine corpus (`6-rag/1-vertex-rag-engine`) stays in your project until you delete it.

**Tear down, exactly** (§2):
1. llm-rag: `exit` the container shell, then `docker compose down` in `llm-rag/`. `compose run` leaves `llm-rag-chromadb` running and holding port 8000 (G4).
2. `adk web` / `uvicorn`: Ctrl+C.
3. `6-rag/2-custom-chromadb-rag`: `docker compose down` (add `-v` to also delete the `chroma_data` volume).
4. `6-rag/1-vertex-rag-engine`, if you ran it: `uv run python setup_corpus.py`, then option `5. Delete corpus`.
5. Each Colab notebook: *Runtime → Disconnect and delete runtime*.
6. Rotate or delete any service-account key you no longer need (IAM → Service accounts → Keys).

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Lecture-to-tutorial mapping:** the course-site source `2026-AC215/tutorials_demo.md:83-98`, at site commit `12dfbffcf117b5e67c1784863d7c31adf53fd365` (2026-10-08). The Ed lesson itself was not accessible when these sources were checked.
- **Repo 1:** `dlops-io/llm-rag`, branch `main`, commit `e17a39f35bc07b440f573def480adaf4703f8b91`, committed 2026-10-07 21:34:23 -0400 ("Merge pull request #2 from obalatel/revert-1-demo-podcast"). That merge reverts a same-day "demo podcast" merge, so the tree is byte-identical to `7a3c66b` (2026-10-06, "updated for localhost").
  - Other branches, not used here: `pipenv` `0b671ede29d4b37ecd530da493485b015adad4da` (2025-03-04, the old `vertexai` SDK version), `demo-podcast` `96fef434536f6e58a5bd027f49916fc98cd467e1` (2026-10-07, the restructure that was merged and then reverted on `main`), `revert-1-demo-podcast` `b77a556560befb87e241d39965d68f2e77a6d2ad` (2026-10-07, the PR branch of the revert; its tree is identical to `main`).
  - README section for this lecture: [`#agents`](https://github.com/dlops-io/llm-rag?tab=readme-ov-file#agents) (`llm-rag/README.md:242-272`).
  - It depends on L05's sections `#prerequisites` (45-69), `#run-llm-rag-container` (75-85) and `#chunk-documents` through `#load-embeddings-into-vector-database` (91-166): the agent queries the vector collection you built there.
- **Repo 2:** `dlops-io/llm-agent-google-adk`, branch `main` (its only branch), commit `f89faa79de744f6a046e30dff24b3b6f1d73720b`, committed 2025-12-02 14:02:38 -0500 ("fix bugs and clean readme"). It has **no lockfile**: `uv.lock` is git-ignored (`llm-agent-google-adk/.gitignore:34`).
- **Colab notebooks** (local JSON copies; Colab links at `2026-AC215/tutorials_demo.md:88, 94, 98`):
  - `L06_cheese_quiz.ipynb`, "Cheese Quiz". 79 cells. OpenAI API + OpenAI Agents SDK + FastMCP. Last saved run: 2026-09-23 (the tool outputs carry `generated_at: 1790132526`).
  - `L06_travel_planner.ipynb`, "Travel Planner". 31 cells. OpenAI Agents SDK `0.3.2`.
  - `L06_cheese_newsletter_harness.ipynb`, "Cheese Newsletter - Harness". 33 cells. Microsoft Agent Framework. Last saved run: 2026-09-20 13:27 UTC (footer of the saved HTML).
  - Cell numbers in this guide are 0-based indices in the `.ipynb` JSON. Colab does not show numbers, so each cell's `# @title` or first line is given too.
- **Files read in full:** every tracked text file in both repos. In `llm-rag`: `README.md`, `cli.py`, `agent_tools.py`, `semantic_splitter.py`, `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, `docker-shell.sh`, `pyproject.toml`, the relevant part of `uv.lock`, `.gitignore` and `out.txt` (a recorded `--agent` run), plus the flow diagram `images/llm-rag-flow-3.png`. In `llm-agent-google-adk`: all 54 tracked files (53 text files plus `demo.gif`), covering the 6 modules, READMEs, `QUICKSTART.md`, every `.env.example` and `pyproject.toml`. All three notebooks: every code and markdown cell, plus the saved outputs.
- **Third-party code read to check claims** (downloaded wheels, unzipped, read only): `google-adk` 1.19.0 (current on the repo's last commit date), 1.27.5, 1.28.0 and 2.11.0 (what `uv sync` resolves today); `google-genai` 1.39.1 (pinned by llm-rag's `uv.lock:496-497`); `chromadb` 1.1.0; `openai-agents` 0.3.2 and 0.23.1; `fastmcp-slim` 4.1.0; the npm package `@modelcontextprotocol/server-filesystem` 1.0.0. Google's Gemini deprecation page (last updated 2026-10-09) and OpenAI's deprecation page were checked too.
- **Method:** every repo `path:line` was checked with `sed -n` / `grep -n`. Docker, the notebooks and the repo scripts were **not** run. Two things were run: (1) a metadata-only dependency resolution (`uv pip compile --only-binary :all:`) on a copy of the ADK repo's dependency list, to see which versions `uv sync` picks today; (2) the langchain splitter (version from `uv.lock`) on the book files, to count chunks. Claims that were reasoned out but could not be run are marked *(reasoned, not run)*. Verified against the repos on 2026-10-13.
- **Path convention:** `cli.py`, `agent_tools.py`, `out.txt`, `docker-*.sh` and `docker-compose.yml` without a prefix are in `llm-rag/`; module paths such as `1-baseline/agent.py` are in `llm-agent-google-adk/`. A bare `README.md` is the README of the repo the surrounding part is about (llm-rag in Part B, the ADK repo in Part C). Third-party paths start with the package name and version, notebook references with the notebook name and cell number.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 6: LLM: Agents I*, 56 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The deck has no code: it teaches with box diagrams and annotated screenshots of a chat assistant. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l06-agents-1/SLIDES.md`.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 20–22 (why agents), 13–14 (agentic RAG), 26–27 (definition, anatomy) |
| §3.1 LLM vs workflow vs agent; §4 Part A4 | 4–5 (plain LLM), 16–18 (the multi-call "Reasoning LLM"), 26–27 |
| §3.2 Function calling; §4 Part B; checklist *llm-rag · Agents* | 13–14, 39, 51 |
| §3.3 The agent loop | 26, 37–41 (the decision maker's cycle; dynamic control) |
| §3.4 Context engineering; §4 Part A5 | 36, 40–41 (the full topic is in Lecture 7, slides 11–18) |
| §3.5 Tools, schemas and MCP; §4 Parts A6–A7, C5 | 51–53 |
| §3.6 ADK's runtime objects; §4 Parts C1–C3 | 35–36, 40–41 (the blocks you configure) |
| §3.7 Multi-agent patterns; §4 Parts A8, C7 | 38 (planner), 44–49 (a research agent with sub-agents), 51 (orchestration tools) |
| §3.8 The harness; §4 Parts D–E | 20–22 (the travel planner), 36–37 (success criteria, guardrails) |
| §8 Exercise 2 (let the model skip the tool) | 10, 13, 33 (deciding whether to retrieve) |
| §2 costs and teardown, §5 code tour, §6 gotchas, the other exercises, §9 errata | none (tutorial-only) |
| — (background) | 6–12 (L05's RAG variants recapped), 28–33 and 42–49 (the chat-assistant demos) |

**Lecture ideas you need for this tutorial**
1. A plain LLM or RAG cannot act: it has no contact with live systems, no tools that change anything, and no autonomy to adapt. Agents add these (slides 20–22).
2. Agentic RAG puts an LLM in front of retrieval to choose how to retrieve. `llm-rag --agent` is exactly this, with a menu of two search tools (slides 13–14).
3. An agent is an LLM with instructions and tools that keeps running on its own until the task is done (slide 26).
4. An agent has five parts: LLM core, instructions, dynamic control, tools, memory. You configure four of them; dynamic control emerges from the model plus the prompt, and in code it is the framework's loop (slides 27, 37, 41).
5. Choosing the LLM core is a design decision: the model, its sampling parameters (`temperature`, top-p, max tokens) and the response format. Here that is `GEMINI_MODEL`, `temperature=0` and the JSON schema (slide 35).
6. Instructions give the core a role, constraints, goals with success criteria, and an output format (slide 36).
7. The decision maker cycles through a planner, tools and memory. That cycle is the agent loop that ADK and the Agents SDK run for you (slides 37–40).
8. Tools are functions with schemas. The agent must pick the right one, format its inputs and interpret its outputs. There are three families: data tools (search), action tools (change something) and orchestration tools (hand work to another agent) (slides 39, 51).
9. MCP replaces one custom integration per tool with one standard protocol: the agent is a host with clients, and each external system sits behind a server (slides 52–53).
10. An agent can direct sub-agents: a lead agent makes a plan and sends several search agents out in parallel, then writes one report (slides 44–49).

**Where the slides and today's tutorial differ** (in each case, the repos at `e17a39f` / `f89faa7` and the notebooks decide)
- Slide 26's agent runs until the task is done. `llm-rag --agent` makes one forced tool call and one answer, with no loop (§3.3). The loop arrives with ADK and the notebooks.
- On slides 10, 13 and 33 an agent may decide not to retrieve. `mode="any"` (`cli.py:449`) forces a tool call every time, so the llm-rag agent picks which search, never whether (Exercise 2).
- Slide 40's memory lasts across sessions. The ADK README uses "Memory" for per-session state (E12), and the Travel Planner's `SQLiteSession` ends with the runtime.
- Slide 53 draws one "MCP" box in front of every server. In code each server is its own connection: an HTTP URL, a thread on port 8001, an `npx` child process over stdio (§3.5).
- Slides 20–22's planner books a Paris trip through live systems and replans for weather or delays. The notebook uses a three-city mock catalog with no weather tool and books nothing; ADK's `1-baseline` has no tools at all, so its prices are the model's guesses.
- "Reasoning" means three things on the slides: a multi-call system (16–18), the model's own thinking (31–33) and the LLM core (27). The Cheese Quiz's `ReasoningLLM` is the first kind, with Python ordering the calls (§3.1).
- Slides 36–37 put success criteria and guardrails in the instructions. The harness notebooks check them in code (the approval gate, the receipt), and a rule left only in the prompt slipped through (E15; §3.8).

## Command checklist

Commands in backticks are exactly as the README or notebook writes them (placeholders kept; multi-line commands are joined onto one line). Plain items are console clicks, file edits or notebook cells (0-based cell index, plus the cell's `# @title` or first line). Items marked *(extra)* are not in the tutorial; they come from §4 of this guide. The order follows the course site: Cheese Quiz → llm-rag Agents → ADK → Travel Planner → Newsletter. All `python cli.py …` commands run **inside** the container that `sh docker-shell.sh` opens; items marked "host" run in a second terminal on your laptop.

### Cheese Quiz (Colab)

*(Tutorial 1a; §4 Part A)*
- [ ] Open the [Cheese Quiz](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) and click *File → Save a copy in Drive* (cell 1); the tab title starts with "Copy of".
- [ ] Colab left sidebar → 🔑 *Secrets* → add `OPENAI_API_KEY` → toggle *Notebook access* (G15).
- [ ] `!pip -q install fastmcp openai-agents > /dev/null 2>&1` — cell 10 (`# @title Install Packages`): unpinned, output hidden. If cell 11 cannot import `agents` or `fastmcp`, rerun it without `> /dev/null 2>&1` (G16).
- [ ] Cell 11 (`# @title Imports`) and cell 12 (`# @title Set Up OpenAI Key`) — reads `userdata.get('OPENAI_API_KEY')` and builds `client = OpenAI(...)`.
- [ ] `!gdown 1dxvxGZZ-yYEEHQuaoP4HwaYxsbOC4XEh` — cell 13 (`# @title Download`): saved output `To: /content/quiz-schema.json … 2.10k`.
- [ ] `!gdown 1OykEQrwa5cnZgPIVrOdnDeq3txots3H0` — cell 13: saved output `To: /content/quiz-ui.html … 10.8k`. Cell 62 needs both files.
- [ ] Cells 17-21 (`# Define the LLM model and question`, `# @title Define BaseLLM`, `# Initialize`) — one `chat.completions.create` call; saved output `Tokens: 293, Time: 2.81s`.
- [ ] Cells 24-26 (`# @title Define ReasoningLLM`, `# Initialize`, `steps = reasoning_result["reasoning_steps"]`) — 11 calls per question; eleven `🧠 BaseLLM: Making single API call...` lines and `Sub-questions explored: 4`. "Total tokens" is approximate.
- [ ] Cells 30-31 (`# @title Define SimpleAgent`, `# Initialize`) — an Agents-SDK `Agent` with `WebSearchTool`; saved output `Time: 13.29s` plus a "Sources" list. "Tools used: 1" counts configured tools, not calls.
- [ ] Cells 37-44 (`model = "gpt-4o"`, `# @title Step 1: Basic prompt` … `# @title Step 7: Structured Output`) — seven context layers. Step 2 (cell 39, lines 18-21) swaps the `user` and `system` roles (E1).
- [ ] Cells 46-50 (`# Define the LLM model and question`, `# --- Fun Facts data ---`, `# System Prompt`, `# If you want to list all the tools called in the agent run`) — `@function_tool(name_override="pavlos_fun_fact_tool")`; saved output `1. pavlos_fun_fact_tool  args={}` three times.
- [ ] Cell 54 (`# MCP Server`) — `MCPServerStreamableHttp` to `https://pavlos-fun-facts.dlops.io/mcp`, passed as `mcp_servers=`.
- [ ] Cells 57-59 *(optional)* — your own FastMCP server in a daemon thread at `http://127.0.0.1:8001/mcp`; expect `"POST /mcp HTTP/1.1" 200 OK` and `Pavlos Fun Fact Tool Called`. Do not rerun cell 57 in the same runtime.
- [ ] Cells 62-71 (`# @title Some Utils`, the specialists, `# Agents-as-tools for orchestration`, `orchestrator = Agent(`, `async def run_guild`) — Pydantic contracts, `.as_tool(...)`, `Runner.run(orchestrator, prompt, max_turns=12)`.
- [ ] `await run_guild("Cheeses from Star Wars")` — cell 75: an interactive quiz widget (the saved run also printed three `ERROR:openai.agents:Error getting response` lines).
- [ ] `await run_guild("Greek cheeses")` — cell 77: a second quiz.

### llm-rag · Run LLM RAG Container (from L05)

*(`README.md:75-85`; §4 Part B1)*
- [ ] `cd ~/Desktop/AC215/llm-rag` — *(extra)* "Make sure you are inside the `llm-rag` folder". `llm-rag/` and `secrets/` must sit side by side (G8).
- [ ] Update `GCP_PROJECT` to your own project ID in `docker-shell.sh` (line 7: replace `"ac215-project"`).
- [ ] `sh docker-shell.sh` — exports `GCP_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` and `IMAGE_NAME`, then `docker compose run --rm llm-rag-cli` builds the image if missing, starts `llm-rag-chromadb` and opens a prompt like `app@<id>:/app$`.

### llm-rag · Check the collection *(extra)*

*(Not in the Agents section, but the agent needs L05's collection; §4 Part B2)*
- [ ] `python cli.py --get --chunk_type char-split` — *(extra)* a dict with `ids`, `documents`, `metadatas` means `char-split-collection` exists.
- [ ] `python cli.py --chunk --embed --load --chunk_type char-split` — *(extra)* builds it if `--get` fails with NotFound (G6), or rebuilds it if you loaded before 2026-09-22 (G7). `load` drops and recreates the collection, so rerunning is safe.
- [ ] `git show 85bba32 --stat` — *(extra, host)* the 2026-09-22 commit that rewrote `Tolminc Cheese.txt` (G7).

### llm-rag · Agents

*(`README.md:242-272`; §4 Parts B3-B6)*
- [ ] `python cli.py --agent --chunk_type char-split` — call 1 forces a function call (`mode="any"`), your code queries Chroma, call 2 writes the answer. The printout has the structure of `out.txt` but not its content (G7).
- [ ] *(optional)* Try the [Cheese Agent Tool](https://ac215-llm-rag.dlops.io/agent) (the README recommends Chrome).
- [ ] `exit` — *(extra)* leaves the `llm-rag-cli` container, which is removed (`--rm`).
- [ ] `docker compose down` — *(extra, host, in `llm-rag/`)* stops `llm-rag-chromadb` and frees port 8000 for `adk web` (G4); the data stays in `./docker-volumes/chromadb`.

### llm-agent-google-adk · Getting Started

*(ADK `README.md:72-107`; §4 Part C1)*
- [ ] `cd ~/Desktop/AC215` — *(extra)*
- [ ] `git clone <repository-url>` — the README's placeholder; the URL is `https://github.com/dlops-io/llm-agent-google-adk.git`.
- [ ] `cd google-adk-tutorial` — as written, but the folder is `llm-agent-google-adk`, so run `cd llm-agent-google-adk` (E8).
- [ ] `cp .env.example .env` — the root `.env` that `uv run adk web` uses.
- [ ] Visit [Google AI Studio](https://aistudio.google.com/app/apikey), create an API key and put it in `.env` as `GOOGLE_API_KEY=…`.
- [ ] *(extra)* In the same `.env`, set `GEMINI_MODEL=gemini-3.1-flash-lite`. The file's `gemini-2.5-flash` and the code's `gemini-2.0-flash` fallback fail (G2).
- [ ] `uv add "google-adk>=1.8.0,<1.28"` — *(extra)* resolves 1.27.5; without it you get 2.11.0 and `Invalid agent name` (G1).
- [ ] `uv sync` — one venv for all modules; the first run downloads PyTorch (G13).
- [ ] `uv run adk --version` — *(extra)* prints a line ending in `version 1.27.5`.

### llm-agent-google-adk · Running Agents

*(ADK `README.md:109-119`; §4 Part C2)*
- [ ] `uv run adk web` — from the repository root: FastAPI + dev UI on `127.0.0.1:8000`; every subfolder is offered as an agent.
- [ ] `uv run adk web --port 8080` — *(extra)* if llm-rag's ChromaDB still holds port 8000 (G3).
- [ ] Open http://localhost:8000 and select a tutorial folder in the agent dropdown.

### 1-baseline · Travel Planner

*(`1-baseline/README.md:52-92`; §4 Part C3)*
- [ ] `uv sync` — already done at the root; run inside the module folder it builds an extra venv (G13).
- [ ] `cp .env.example .env` — skip it if the root `.env` is set: a copied module `.env` becomes the nearest one and silently wins over the root one (G2). If you do copy it, put your key and `GEMINI_MODEL=gemini-3.1-flash-lite` in it.
- [ ] `uv run adk web` — then select `1-baseline`.
- [ ] *(extra)* Type a trip request (the README gives no example), e.g. "2 adults, Boston → Montréal, Oct 30-Nov 2, $1500, train preferred" — three agent responses in order; the event/state inspector shows `itinerary_validation`, `travel_plan`, `trip_summary`.

### 2-litellm · Multi-Model Support

*(`2-litellm/README.md:22-88`; §4 Part C4)*
- [ ] `uv sync` — "from root".
- [ ] `cp .env.example .env` — note that `AWS_OPENAI_API_KEY` is read by no code; `litellm_config.py:28` reads `OPENAI_API_KEY` (G11).
- [ ] `uv run adk` — as written it prints a usage screen (G10): run `uv run adk web` and select `2-litellm`. As written the agent then fails with `Model gpt-4 not found.` (G11); Exercise 7 fixes it.
- [ ] `cd 2-litellm` — "Option 2: Test LiteLLM Configuration".
- [ ] `uv run python litellm_config.py` — prints nothing, whatever keys you set: the file has no `__main__` block (G19).
- [ ] `uv run --project .. python -c "from litellm_config import configure_litellm; configure_litellm()"` — *(extra, reasoned, not run)* prints `✓ OpenAI configured` if `OPENAI_API_KEY` is set.

### 3-mcp-tools · MCP & Tools

*(`3-mcp-tools/README.md:29-94`; §4 Part C5)*
- [ ] `uv sync` — from the root.
- [ ] `cp .env.example .env` — same caveat as in 1-baseline (G2).
- [ ] `brew install node` — macOS.
- [ ] `sudo apt install nodejs npm` — Ubuntu (Windows: download from https://nodejs.org/).
- [ ] `node --version` — *(extra)* must work before you start.
- [ ] `npx -y @modelcontextprotocol/server-filesystem .` — *(extra)* warms the npx cache so the first run does not hit `timeout=10`. It then waits on stdin; stop it with Ctrl+C (G12).
- [ ] `uv run adk` — as written it prints a usage screen: run `uv run adk web` and select `3-mcp-tools` (G10).
- [ ] Ask "List files in this directory", "Read the README.md file", "What Python files are here?", "Search for files containing 'agent'" — function-call events for `list_directory` and `read_file`; the folder's four tracked files plus `__pycache__`.

### 4-production-ready · FastAPI

*(`4-production-ready/README.md:9-52`; §4 Part C6)*
- [ ] `cd 4-production-ready`
- [ ] `uv sync` — builds a second venv with `google-adk[all]`; you can skip it and use the root venv instead.
- [ ] `uv run uvicorn app.main:app --reload --port 8080` — as written (module venv).
- [ ] `uv run --project .. uvicorn app.main:app --reload --port 8080` — *(extra, reasoned, not run)* the same server from the root venv.
- [ ] Open http://localhost:8080/docs — FastAPI's Swagger UI; `GET /health` returns `{"status":"healthy"}`.
- [ ] `curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"user_message": "Hello!"}'` — returns `{"response":"..."}`; every request gets a new random session.
- [ ] `curl -X POST http://localhost:8080/chat/stream -H "Content-Type: application/json" -d '{"user_message": "Tell me a story"}'` — NDJSON `{"chunk": …}` lines; final-response events only, not token streaming.
- [ ] Ctrl+C — *(extra)* stops uvicorn.
- [ ] `docker build -t adk-agent .` — builds the module's image.
- [ ] `docker run -p 8080:8080 -e GOOGLE_API_KEY=your_google_api_key adk-agent` — as written; add `-e GEMINI_MODEL=gemini-3.1-flash-lite`, or the image falls back to the retired default (`app/agent.py:12`).

### 5-custom-agent · Custom Agents

*(`5-custom-agent/README.md:93-153`; §4 Part C7)*
- [ ] `uv sync` — already done at the root; run inside the module folder it builds an extra venv (G13).
- [ ] `cp .env.example .env` — "Add your GOOGLE_API_KEY". This module's `.env.example:5` sets `GEMINI_MODEL=gemini-2.0-flash` (shut down): change it in the copy, or skip the copy (G2).
- [ ] `uv run adk` — as written it prints a usage screen: run `uv run adk web` and select `5-custom-agent`; the final reply gets a 🤖 prefix (G10).
- [ ] `cd 5-custom-agent`
- [ ] `uv run python simple_custom_agent.py` — prints `Agent: 🤖 [Bot]: …`.
- [ ] `uv run --project .. python simple_custom_agent.py` — *(extra)* the same from the root venv (G13).
- [ ] `cd 5-custom-agent` — Option 3 repeats it; skip it if you are already in the folder.
- [ ] `uv run python conditional_agent.py` — prints `→ Routed to: SimpleHandler` / `ComplexHandler` / `ClarificationHandler`, then `Response:` for each of three test queries.
- [ ] `uv run --project .. python conditional_agent.py` — *(extra)* the same from the root venv.

### 6-rag · RAG (optional)

*(`6-rag/README.md:102-141`; §4 Part C8. Each sub-folder also has its own, longer README, e.g. creating a service account with `gcloud`; those setups are not covered in this guide.)*

*Option 1: Vertex RAG Engine* (creates a managed corpus in your GCP project; delete it afterwards)
- [ ] `cd 1-vertex-rag-engine` — from `6-rag/`.
- [ ] `uv sync`
- [ ] `cp .env.example .env` — then edit `.env` with your Google Cloud project details and service account.
- [ ] `uv run python setup_corpus.py` — creates the RAG corpus and imports documents (`setup_corpus.py:41-64`).
- [ ] `uv run python agent.py` — runs queries (recommended). It hard-codes `gemini-2.5-flash` and ignores `GEMINI_MODEL` (`6-rag/1-vertex-rag-engine/agent.py:47`, E7).
- [ ] `uv run adk web` — or use the web UI.
- [ ] `uv run python setup_corpus.py` — *(extra)* when done, choose option `5. Delete corpus` (`setup_corpus.py:160, 192-194`).

*Option 2: Custom ChromaDB*
- [ ] `cd 2-custom-chromadb-rag` — from `6-rag/`.
- [ ] `docker compose up -d` — starts ChromaDB on port 8000; stop llm-rag's ChromaDB first (G3).
- [ ] `uv sync`
- [ ] `cp .env.example .env` — its `.env.example:10` sets `GEMINI_MODEL=gemini-2.0-flash`, and this copy becomes the nearest `.env`: fix it (G2).
- [ ] `curl http://localhost:8000/api/v2/heartbeat` — *(extra)* the README's v1 heartbeat fails against this server (G14).
- [ ] `uv run python ingest_documents.py` — run it before `agent.py`, which calls `get_collection` at import time (the README's comment "assumes RAG is already populated" is wrong, E13).
- [ ] `uv run python agent.py` — runs queries (recommended).
- [ ] `uv run adk web` — in this folder it does not find the agent (G14); use `uv run python agent.py`.
- [ ] `docker compose down` — *(extra)* add `-v` to also delete the `chroma_data` volume.

### Travel Planner (Colab)

*(Tutorial 2; §4 Part D)*
- [ ] Open the [Travel Planner](https://colab.research.google.com/drive/1I_jJEHJsVkGxNoSC1c4wEoVF2QL6vCVY?usp=sharing), *File → Save a copy in Drive*, and give the copy access to the `OPENAI_API_KEY` secret.
- [ ] `%pip install -q "openai-agents==0.3.2"` — cell 8 (`# @title Install OpenAI Agents SDK`).
- [ ] Cells 9-10 (`# @title Imports`, `# @title Setup OpenAI Key`).
- [ ] Cells 12-16 (`# @title Catalog Data & Utils`, `# @title Search Tools`, `# @title Finalize Plan Tool`, `# Test`) — mock catalog in cents, five search tools, the gated `finalize_plan`. Cell 16 should print `LAX-OBSERVATORY` (0.0) and `LAX-MUSEUM` (25.0) (no saved output).
- [ ] Cells 18, 20, 21 (`# @title Business Logic`, `# @title Travel Agent Instructions`, `# @title Travel Agent`) — `check_itinerary`, `run_turn`, and `build_agent()` with `gpt-5.6-luna`, six tools and `SQLiteSession("travel-planner")`.
- [ ] Cell 24 (`# Build the Agent`, Turn 1) — `Kind: clarification`, asking "San Francisco or Los Angeles?" and for the allowances.
- [ ] Cell 25 (Turn 2) — five tool calls, then `Kind: options`.
- [ ] Cell 26 (Turn 3) — `[tool] finalize_plan: …`, then `Kind: clarification` with the exact JSON proposal.
- [ ] Cell 27 (Turn 4, `"yes"`) — `Kind: itinerary`, `"total_usd": 2690.0`, `"remaining_usd": 3310.0`. An `AssertionError` on `reply.kind` means the model took another plausible path: rerun the turn.
- [ ] Cell 28 (`# @title Start an interactive conversation`) — defines the chat loop.
- [ ] `await chat_loop()` — cell 29: end a message with a blank line or `/send`; `exit` or `quit` leaves. It starts a fresh session.

### Cheese Newsletter · Harness (Colab)

*(Tutorial 3; §4 Part E)*
- [ ] Open the [Cheese Newsletter · Harness](https://colab.research.google.com/drive/1nnHrJ4Si3tpgUQl6HqlcwxKymV1-ecPv?usp=sharing), *File → Save a copy in Drive*, and give the copy access to the `OPENAI_API_KEY` secret.
- [ ] `%pip install -qU "agent-framework-core==1.18.0" "agent-framework-openai==1.14.3" "opentelemetry-api==1.42.1"` — cell 8 (`# @title Install Microsoft Agent Framework`).
- [ ] Cells 9-10 (`# @title Imports`, `# @title Setup OpenAI Key`).
- [ ] Edit `USERS` in cell 16 (`# @title Catalog Data & Utils`, lines 7-12): replace the staff names and addresses with yours and keep at least two readers (cell 31 displays `receipts[1]`). Write "Somerville" if you mean Somerville, MA.
- [ ] Run cells 16-25 (`# @title Catalog Data & Utils` … `# @title Orchestrator Agent`) — contracts, validation, rendering, the researcher and editor as `@tool`s, the orchestrator (`max_iterations: 16`, `allow_multiple_tool_calls: False`).
- [ ] `receipts = await run_demo()` — cell 27 (`# @title Run Demo`): per reader `[tool] researcher_agent`, `[tool] editor_agent`, `[tool] send_email: validating and saving HTML (mock)` and `Saved HTML: …`; a fresh run ends with `Created 2 mock emails. No email was sent.`
- [ ] Cells 30-31 — render the saved HTML previews and file links.

### After the tutorials *(extra)*

*Clean up (§2)*
- [ ] Ctrl+C — stops `adk web` and `uvicorn`.
- [ ] `docker compose down` — *(host)* in `llm-rag/` if it is still running, and in `6-rag/2-custom-chromadb-rag/` (add `-v` there to delete the `chroma_data` volume).
- [ ] In each Colab notebook: *Runtime → Disconnect and delete runtime*.
- [ ] IAM → Service accounts → Keys: rotate or delete any key you no longer need.
- [ ] Before the first `git add` in your own repo: add `secrets/`, `**/.env` and `*.json` keys to its `.gitignore` (G18).

---

## 1. What you build

In L05 you built a RAG pipeline: chunk → embed → load into ChromaDB → retrieve → answer. In L06 the **LLM decides how to retrieve**. You do this in three settings, from "by hand" to "framework" to "harness":

1. **`llm-rag --agent` (Docker, Gemini on Vertex AI).** Gemini 3.1 Flash-Lite receives two *function declarations*: "search one author's book" and "search all books". It is **forced** to answer with a function call (`mode="any"`). Your Python code runs that call against ChromaDB, sends the chunks back, and a second Gemini call writes the answer. Two LLM calls, no loop.
2. **`llm-agent-google-adk` (uv on your laptop, Gemini API).** Google's Agent Development Kit runs the *agent loop* for you: call the model → run the tools it asked for → call the model again, until it gives a final answer. The repo has six modules:
   - a sequential travel-planner pipeline that shares *state*
   - LiteLLM for other model providers
   - an MCP filesystem tool server
   - a FastAPI deployment
   - custom agents that route between sub-agents
   - two RAG agents
3. **Three Colab notebooks (OpenAI).**
   - *Cheese Quiz* climbs the ladder plain LLM → hand-written reasoning workflow → agent with web search → context layers → tools and MCP → a six-agent "Cheese Quiz Guild".
   - *Travel Planner* lets the model choose tools, but Python owns the money arithmetic and a human-approval gate.
   - *Cheese Newsletter* is an orchestrator with sub-agents-as-tools. Python decides whether the run succeeded, through a *receipt*.

```
YOUR LAPTOP  (~/Desktop/AC215)
+-----------------------------------------------------------------------------------------------+
| (B) llm-rag/   sh docker-shell.sh  ->  docker compose run --rm llm-rag-cli                     |
|     docker network "llm-rag-network"                                                          |
|     +---------------- container llm-rag-cli (python:3.12-slim, venv /.venv) ---------------+  |
|     | /app     <- bind ../llm-rag        /secrets <- bind ../secrets                        |  |
|     | $ python cli.py --agent --chunk_type char-split                                     |  |
|     |   (1) generate_content(question, tools, mode=ANY) -------------------------------+  |  |
|     |   (2) execute_function_calls(): embed(search_content) -> collection.query() --+ |  |  |
|     |   (3) generate_content(question + model's call + function responses) ---------+-+->+-+--HTTPS--+
|     +-----------------------------------------------------------------|---------------+  |         |
|                         http://llm-rag-chromadb:8000 (container DNS)  v                  |         |
|     +------------- container llm-rag-chromadb (chromadb/chroma:latest) -------------+   |         |
|     | collection "char-split-collection" (cosine, metadata: book, author, year)    |   |         |
|     | /data <- bind ./docker-volumes/chromadb (persists between runs)              |<--+-- host :8000 (browser Chroma UI)
|     +-------------------------------------------------------------------------------+   |         |
|                                                                                            |         |
| (C) llm-agent-google-adk/   uv run adk web  ->  FastAPI + dev UI on http://127.0.0.1:8000 (!) |       |
|     loads <folder>/agent.py :: root_agent ; reads nearest .env (GOOGLE_API_KEY, GEMINI_MODEL) --HTTPS--> Gemini API
|     3-mcp-tools: spawns child process `npx -y @modelcontextprotocol/server-filesystem <dir>` (stdio) |
|     4-production-ready: uvicorn app.main:app :8080  (POST /chat, /chat/stream)              |         |
+-----------------------------------------------------------------------------------------------+       |
                                                                                                        |
GOOGLE CLOUD (your project)   Vertex AI, location "global": gemini-embedding-001 (256-d), gemini-3.1-flash-lite <-+
                              auth: GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json

GOOGLE COLAB VM (browser)     notebook --HTTPS--> OpenAI API (gpt-4o, gpt-5.6-luna, hosted web_search tool)
                              Cheese Quiz --HTTP--> https://pavlos-fun-facts.dlops.io/mcp  (remote MCP server)
                              Cheese Quiz: FastMCP thread on 127.0.0.1:8001/mcp inside the Colab VM
                              Newsletter: writes /content/newsletter_output/*.html (no email is sent)
```

(!) `adk web` and the llm-rag ChromaDB both want port **8000** on your laptop. See G3.

---

## 2. Prerequisites and costs

**Accounts and keys, and where the code expects them**

| What | Used by | Where the code looks |
|---|---|---|
| GCP project with billing; **Vertex AI API** (`aiplatform.googleapis.com`) enabled | llm-rag | `GCP_PROJECT` is exported in `llm-rag/docker-shell.sh:7` (edit `"ac215-project"`), passed through `docker-compose.yml:15`, read with `os.environ["GCP_PROJECT"]` at `cli.py:23`. The client uses `vertexai=True, location="global"` (`cli.py:24, 35-36`). |
| Service account `llm-service-account` with **Vertex AI User** (now listed as "Gemini Enterprise Agent Platform User") | llm-rag | README.md:52-62. The JSON key goes to `../secrets/llm-service-account.json`, i.e. `~/Desktop/AC215/secrets/`, a sibling of `llm-rag/` (README.md:64-69). It is mounted at `/secrets` (`docker-compose.yml:11`), and `GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json` (`docker-shell.sh:8`). The README also grants **Storage Admin** (README.md:57). Nothing in the L06 code path touches Cloud Storage, so the agent does not need it. |
| A loaded Chroma collection `char-split-collection` | llm-rag `--agent` | `cli.py:427-429` calls `get_collection(f"{method}-collection")`. You build it with L05's `--chunk`, `--embed`, `--load`. |
| **Google AI Studio API key** | ADK repo | `GOOGLE_API_KEY` in `llm-agent-google-adk/.env` (`.env.example:5`). Alternative: Vertex mode via `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (`1-baseline/.env.example:10-12`, commented out). |
| A **current Gemini model name** | ADK repo | Read as `GEMINI_MODEL` from `.env` (root `.env.example:21` says `gemini-2.5-flash`). Every `agent.py` except `6-rag/1-vertex-rag-engine/agent.py` (which hard-codes `gemini-2.5-flash`, line 47) falls back to `gemini-2.0-flash` (e.g. `1-baseline/agent.py:12`), which is **shut down**. See G2. |
| **OpenAI API key** with billing | all three notebooks; ADK `2-litellm` | Colab **Secrets** panel, name `OPENAI_API_KEY`, with notebook access on. Read via `userdata.get('OPENAI_API_KEY')`: Cheese Quiz cell 12 (`# @title Set Up OpenAI Key`), Travel Planner cell 10, Newsletter cell 10. |

**Local installs:**
- Docker Desktop with Compose v2, for llm-rag.
- `uv`, for the ADK repo (`README.md:59-64` says Python 3.10+; uv can fetch Python for you).
- **Node.js + npm (`npx`)**, for `3-mcp-tools` (`3-mcp-tools/README.md:53-64`).
- Git.

**Platform:** `python:3.12-slim-bookworm` and `chromadb/chroma` are multi-arch images, and `uv.lock` pins chromadb 1.1.0 wheels for `manylinux_2_17_aarch64` as well as x86_64. So Apple Silicon runs natively. The entrypoint prints `Architecture: aarch64` on an M-series Mac (`docker-entrypoint.sh:4`).

**Costs (all small, but not zero):**
- *Vertex embeddings (only if you rebuild the collection).* char-split produces **8,248 chunks** of ≤350 characters (counted with the locked splitter version): about 2.9 M characters. `embed()` batches per book file, up to 100 chunks per request (`cli.py:239-253`), so that is 89 embedding requests, not 83. That costs pennies.
- *Vertex Gemini.* The recorded agent run used 247 + 1,269 tokens (`out.txt:49`, `out.txt:135`). Negligible.
- *OpenAI.* Cheese Quiz makes dozens of `gpt-4o` calls. The "Reasoning LLM" alone makes 11 calls per question (saved output, cell 25). The hosted **web search** tool is billed by OpenAI per call on top of tokens, and Stilton, Cashew and SimpleAgent use it. The Newsletter runs a researcher with web search at least once per reader (the orchestrator may make up to four researcher calls, cell 24; the saved run made one per reader). Expect cents to low dollars per full run.
- *Gemini API (AI Studio):* free-tier limits may cover the ADK exercises. Check your quota page.
- *Optional `6-rag/1-vertex-rag-engine`:* creates a managed **Vertex AI RAG Engine corpus** in your project (`setup_corpus.py:41-64`). Delete it when done: `uv run python setup_corpus.py`, then option `5. Delete corpus` (`setup_corpus.py:160, 192-194`).

**Shut down afterwards:**
- llm-rag: `exit` the container shell, then run `docker compose down` in `llm-rag/`. `compose run` leaves `llm-rag-chromadb` running (G4).
- `adk web` / `uvicorn`: Ctrl+C.
- `6-rag/2-custom-chromadb-rag`: `docker compose down` (add `-v` to also delete the `chroma_data` volume).
- Colab: *Runtime → Disconnect and delete runtime*.
- Rotate or delete any service-account key you no longer need (IAM → Service accounts → Keys).

---

## 3. Concepts this tutorial teaches

### 3.1 LLM vs workflow vs agent: who holds the steering wheel?
- **Explanation:** The Cheese Quiz notebook asks the same question three ways.
  - *Base LLM:* one call (cell 20, `# @title Define BaseLLM`).
  - *"Reasoning LLM":* **your Python** decides the steps. Analyse → decompose → answer each sub-question → verify → synthesise = 11 calls (cell 24, `# @title Define ReasoningLLM`).
  - *Agent:* **the model** decides what to do next, including when to call `web_search` and when to stop (cell 30, `# @title Define SimpleAgent`; definition in cell 8: "a component that uses an LLM with instructions and tools that can run autonomously").
- **Mental model:** The difference is *who controls the control flow*. In a workflow, the `if`/`for` live in your code. In an agent, they live in the model's next-token choices, and your code is a loop that obeys.
- **Analogy:** A recipe card (workflow) vs a chef who reads the order and decides which station to visit (agent).
- **Misconception:** "An agent is a smarter model." The model is the same `gpt-4o` in all three runs. What changes is the loop and the tools around it.

### 3.2 Function (tool) calling: the model *writes* the call, your code *makes* it
- **Explanation:** You send the model a JSON-schema description of functions it may call: `FunctionDeclaration` with name, description and parameters (`llm-rag/agent_tools.py:9-38, 52-66`). The model never runs anything. It replies with a structured `function_call` part, for example `name='get_book_by_author', args={'author': 'Pavlos Protopapas', 'search_content': ...}` (`out.txt:19-27`). **Your code** looks at the name, runs the real Python function (`agent_tools.py:84-127`), wraps the result in a `function_response` part (`agent_tools.py:103-110`) and sends everything back. The model then writes the answer.
- **Mental model:** The model is a manager who can only write sticky notes ("please run X with Y"). You are the assistant who runs X and staples the result to the note.
- **Analogy:** Ordering at a counter. You fill out the order form (schema). The kitchen (your code) cooks. The server (the model) presents the dish.
- **Misconception:** "Gemini queried my ChromaDB." It could not have: ChromaDB is on `localhost`, inside Docker. Gemini only produced arguments. Also, `mode="any"` (`cli.py:447-451`) does not mean "maybe call a tool": it **forces** a function call. In google-genai's own words, ANY means the "Model is constrained to always predicting function calls only" (google-genai 1.39.1 `types.py:500-501`).

### 3.3 The agent loop and its stopping rule
- **Explanation:** Real agents repeat §3.2 until the model stops asking for tools. In ADK the core is literally `while True:`. Run one LLM step (which may execute tools), then break if the last event `is_final_response()` (google-adk 1.19.0 `flows/llm_flows/base_llm_flow.py:343-352`). An event counts as final when it has no function calls, no function responses and is not partial (`events/event.py:82-97`; also true when a tool set `skip_summarization` or is long-running). The OpenAI Agents SDK does the same with a `max_turns` budget (default 10, `openai-agents 0.3.2 agents/run.py:77`). The notebooks set `max_turns=12` (Cheese Quiz cell 71, Travel Planner cell 21). Microsoft Agent Framework calls the budget `max_iterations` (Newsletter cell 25, `{"max_iterations": 16}`).
- **Mental model:** A `while` loop whose exit condition is decided by the model, plus a hard iteration cap decided by you.
- **Analogy:** A detective who keeps sending the intern for evidence until ready to name the culprit, with a deadline.
- **Misconception:** "`llm-rag --agent` is an agent loop." It is a fixed two-call pipeline: forced tool call → answer (`cli.py:439-478`). If the second call asked for another tool, the code would just print that request: `cli.py:478` prints a response whose part is a `function_call` (no text), and the program ends. ADK's loop would execute that call and call the model again until `is_final_response()`.

### 3.4 Context engineering: the model knows only what is in the request
- **Explanation:** "LLMs are stateless functions" (Cheese Quiz cell 35). The notebook keeps the model and question fixed and adds one context layer at a time (cells 38-44): basic prompt → system prompt → retrieved documents (RAG) → short-term memory (prior turns) → long-term memory (user profile) → tool outputs → structured output (JSON schema, `strict: True`).
- **Mental model:** Every call is a fresh envelope. Memory, RAG and tool results are just more paper you put inside it.
- **Analogy:** Briefing a consultant who has amnesia between meetings.
- **Misconception:** "The model remembers the last cell." It does not. Step 4 *re-sends* the whole message history (cell 41).
  - Watch the roles: Step 2 accidentally sends the system prompt as a `user` message and the question as a `system` message (cell 39, lines 18-21). See E1 in §9.
  - The ADK README also blurs two terms: it calls per-session state "Memory" (`llm-agent-google-adk/README.md:140`). In ADK, *state* is per session and *memory* is a separate cross-session service.

### 3.5 Tools, schemas and MCP
- **Explanation:** A tool is a name, a description and a parameter schema, plus code. Frameworks can build the schema for you from a Python signature and docstring:
  - OpenAI Agents SDK: `@function_tool` (Cheese Quiz cell 48)
  - ADK: plain functions in `tools=[...]` (`6-rag/2-custom-chromadb-rag/agent.py:73-121`)
  - Microsoft Agent Framework: `@tool` (Newsletter cell 20)

  By contrast, llm-rag writes the JSON schema by hand (`agent_tools.py:9-38`).

  **MCP** (Model Context Protocol) standardises *where tools live*. A server lists its tools, and any client can call them over **stdio** (a child process) or **HTTP**. The Cheese Quiz connects to a remote server (cell 54, `https://pavlos-fun-facts.dlops.io/mcp`) and to a local FastMCP server it starts in a thread on port 8001 (cells 57-59). ADK `3-mcp-tools` spawns the npm filesystem server over stdio and whitelists three tools (`3-mcp-tools/agent.py:20-29`).
- **Mental model:** Tool = function + contract. MCP = a USB standard for plugging tool servers into any agent.
- **Analogy:** A universal power socket. The appliance (tool server) does not care which house (agent framework) it is plugged into.
- **Misconception:** "MCP gives the model network access." The *client process* talks to the server. The model still only emits a function call, and `tool_filter` (`3-mcp-tools/agent.py:28`) limits what it can even ask for.

### 3.6 ADK's runtime objects: Agent, Runner, Session, State, Event; `output_key` and `{key}`
- **Explanation:**
  - An **`LlmAgent`** (alias `Agent`) bundles model + instruction + tools.
  - A **Runner** executes an agent for a `(user_id, session_id)`, streams **Events**, and appends each event to the **Session** (`4-production-ready/app/runner.py:16-46`).
  - A session holds **state**, a dict. When an `LlmAgent` has `output_key="x"`, its final text is written into `state["x"]` (google-adk 1.19.0 `agents/llm_agent.py:796-816`).
  - Any later instruction containing `{x}` gets that value pasted in before the call. A missing key raises `KeyError: Context variable not found` unless you write `{x?}` (`utils/instructions_utils.py:81-124`).
  - `SequentialAgent` runs sub-agents in order (`1-baseline/agent.py:35-39`). `ParallelAgent` runs them concurrently on separate *branches* but with shared state (`agents/parallel_agent.py`, `_create_branch_ctx_for_sub_agent`).
  - `adk web` imports `<folder>/agent.py`, looks for `root_agent`, and loads the nearest `.env` walking up from that folder with `override=True` (`cli/utils/envs.py`, `load_dotenv_for_agent`). In 1.27.5 (the version the G1 pin installs) variables you exported in the shell before starting `adk web` are restored afterwards, so only earlier `.env` values get overridden.
- **Mental model:** A shared whiteboard (state). Each agent reads cells off the board through `{placeholders}` and writes its answer into one named cell.
- **Analogy:** A relay race where the baton is a labelled envelope pinned to a corkboard.
- **Misconception:** "Sub-agents pass messages directly to each other." They do not. Data flows through session state (and the shared event history), which is why `output_key` names matter.

### 3.7 Multi-agent patterns: workflow agents, agents-as-tools, custom routers
- **Explanation:** There are three ways to compose agents in this lecture.
  - (a) **Workflow agents:** `SequentialAgent`, `ParallelAgent` and `LoopAgent`. Deterministic orchestration, LLM inside each step. Only `SequentialAgent` is in runnable code (`1-baseline/agent.py:35-39`); `ParallelAgent` appears only as a README snippet (`1-baseline/README.md:139-147`) and `LoopAgent` only in `5-custom-agent/README.md:232-260`.
  - (b) **Agents-as-tools:** each specialist is wrapped with `.as_tool(name, description)`, and an orchestrator LLM decides which one to call (Cheese Quiz cells 64-71: Stilton, Cashew, Brie, Cheddar, Mozzarella, Ricotta). The Newsletter wraps the researcher and editor as `@tool` functions (cells 21-22).
  - (c) **Custom agents:** subclass `BaseAgent` and write `_run_async_impl` with ordinary `if` statements (`5-custom-agent/conditional_agent.py:72-104`).
- **Mental model:** (a) is an assembly line, (b) is a manager with a phone book of specialists, (c) is code that you write yourself.
- **Analogy:** A factory line, a general contractor, and your own hand-written SOP.
- **Misconception:** "More agents means better answers." Each hop adds latency, cost and failure points. In the saved run, three `ERROR:openai.agents:Error getting response` lines appear in each of the two quiz runs (Cheese Quiz cells 75 and 77), yet both still render a quiz.

### 3.8 The harness: Python owns state, approvals, validation and the definition of success
- **Explanation:** In the last two notebooks the model chooses actions, but deterministic code decides what those actions are *allowed* to mean.
  - **Travel Planner.** Python computes all prices (`check_itinerary`, cell 18). The model's `finalize_itinerary` call only produces a *pending proposal* until a **later human turn** literally says "yes": `apply_confirmation` (cell 18) and the `proposal != approved_proposal` gate (cell 15, lines 33-42). What the user sees is rendered from checked state, not from the model's prose (cell 18, lines 122-131).
  - **Newsletter.** Sources are registered only from search citation metadata (cell 20, `collect_evidence`). Drafts are validated (`validate_newsletter`, cell 18). Success means a `receipt` exists **and the file is on disk** (cell 18, lines 118-124), never "the model said it's done".
- **Mental model:** The LLM is a powerful but untrusted planner inside a sandbox whose walls, gauges and exit door are code.
- **Analogy:** A pilot with autopilot: the plane suggests, but the checklist and the co-pilot's signature are required before take-off.
- **Misconception:** "Put the rule in the prompt and it will be followed." The prompt says "no monetary amounts" (cell 20). The code still checks with a regex and warns (cell 18, lines 133-135). The Newsletter editor is told "no embedded URLs" (cell 22), yet the saved HTML contains `Promotion URL: https://…` inside a summary, because `validate_newsletter` does not check for URLs.

---

## 4. Step-by-step walkthrough

This follows the course-site order (`tutorials_demo.md:86-98`): Tutorial 1 = Cheese Quiz Colab + llm-rag Agents + ADK, Tutorial 2 = Travel Planner, Tutorial 3 = Newsletter. If you are working from your local clones first, do Part B, then Part C, then the Colabs.

### Part A — Tutorial 1a: Cheese Quiz (Colab)

**A1. Open and copy.** Open the Colab link (`tutorials_demo.md:88`), then *File → Save a copy in Drive* (cell 1). *Checkpoint:* the tab title starts with "Copy of".

**A2. Add your OpenAI key.**
- *Action:* Colab left sidebar → 🔑 *Secrets* → add `OPENAI_API_KEY` → toggle *Notebook access*. Cell 12 (`# @title Set Up OpenAI Key`) runs `api_key = userdata.get('OPENAI_API_KEY')` and builds `client = OpenAI(...)`.
- *If it fails:* a `SecretNotFoundError` / notebook-access error means the secret name or the toggle is wrong.

**A3. Install, import, download.**
- *Cells 10-13.* Cell 10 runs `!pip -q install fastmcp openai-agents > /dev/null 2>&1`. These are **unpinned**, and errors are hidden by the redirect, so if cell 11 fails to import `agents` or `fastmcp`, re-run the install without `> /dev/null 2>&1` to see why.
- *Cell 13* runs `!gdown` twice. *Checkpoint (saved output):* `To: /content/quiz-schema.json … 2.10k` and `To: /content/quiz-ui.html … 10.8k`. Both files are needed later by cell 62.

**A4. LLM → Reasoning LLM → Agent** (cells 17-31).
- *Under the hood:*
  - `BaseLLM.generate` makes one `chat.completions.create` call (cell 20).
  - `ReasoningLLM.reason` chains 11 calls: 1 analyse + 1 decompose + 4 × (answer + verify) + 1 synthesise (cell 24).
  - `SimpleAgent` gives a `WebSearchTool` to an Agents-SDK `Agent` and calls `Runner.run` (cell 30).
- *Checkpoints (saved outputs):*
  - cell 21 `Tokens: 293, Time: 2.81s`
  - cell 25 shows eleven `🧠 BaseLLM: Making single API call...` lines and `Sub-questions explored: 4`
  - cell 31 `Time: 13.29s`, with a "Sources" list of URLs.
- *Read critically:*
  - "Total tokens: 701" in cell 25 is an approximation: the code adds `100` per sub-question (cell 24, `total_tokens += 100  # Approximate token usage`).
  - "Tools used: 1" in cell 31 counts *configured* tools (`self.agent.tools`), not calls.

**A5. Managing LLM inputs** (cells 37-44). Run the seven steps and compare answers.
- *Under the hood:* Steps 1-6 only change `messages`. Step 7 adds `response_format={"type": "json_schema", … "strict": True}` and then parses with `json.loads`.
- *Watch:* Step 2 swaps the roles (cell 39, lines 18-21). Fix it before drawing conclusions about "prompt engineering" (E1 in §9).

**A6. Your first tool** (cells 46-50).
- `@function_tool(name_override="pavlos_fun_fact_tool")` turns an async function into a tool (cell 48, lines 21-25). The instruction says to call it 2-3 times (cell 49).
- *Checkpoint (saved output, cell 50):* `1. pavlos_fun_fact_tool  args={}` three times, then three fact dicts. Because the facts are drawn with `random.choice`, a duplicate can appear (it did in the saved run).

**A7. MCP** (cells 51-59).
- Cell 54 connects `MCPServerStreamableHttp(params={"url": "https://pavlos-fun-facts.dlops.io/mcp"})` and passes it as `mcp_servers=` (not `tools=`). (A plain browser GET of that URL returns HTTP 406, because the streamable-HTTP transport expects MCP's own headers. That does not mean the server is down; it answered on 2026-10-13.)
- Cell 57 starts **your own** FastMCP server in a daemon thread at `http://127.0.0.1:8001/mcp`. The comment in that cell says port 8000; the code uses 8001.
- *Checkpoint (cell 59):* uvicorn log lines `"POST /mcp HTTP/1.1" 200 OK` interleaved with `Pavlos Fun Fact Tool Called`.
- *If it fails:* re-running cell 57 in the same runtime tries to bind 8001 again ("address already in use"). Restart the runtime or skip it.

**A8. The Cheese Quiz Guild** (cells 60-77).
- Cell 62 defines the Pydantic contracts and the custom output schema `QuizAgentOutputSchema`, which validates against `quiz-schema.json`.
- Cells 64-66 define the six specialists. Cell 68 wraps them with `.as_tool(...)`. Cell 70 builds the orchestrator with `output_type=QuizAgentOutputSchema()`. Cell 71 runs `Runner.run(orchestrator, prompt, max_turns=12)` and renders the HTML quiz.
- *Run:* `await run_guild("Cheeses from Star Wars")` (cell 75), then `await run_guild("Greek cheeses")` (cell 77).
- *Checkpoint:* an interactive quiz widget. In the saved run each of the two cells also printed three `ERROR:openai.agents:Error getting response` lines and still produced HTML.
- *If it fails:* `MaxTurnsExceeded` means raise `max_turns`, or simplify the topic. `ModelBehaviorError: JSON failed schema validation` comes from the guardrail in cell 62.

### Part B — Tutorial 1b: llm-rag "Agents" (local Docker)

**B1. Start the container** (README.md:75-85).
- *First* (README.md:80): edit `docker-shell.sh:7`, replacing `"ac215-project"` with your own GCP project ID.
```bash
cd ~/Desktop/AC215/llm-rag
sh docker-shell.sh
```
- *Under the hood:*
  - `docker-shell.sh:7-9` exports `GCP_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` and `IMAGE_NAME`.
  - Line 12 runs `docker compose run --rm $IMAGE_NAME`. Compose builds the image if it is missing (`docker-compose.yml:8`; `Dockerfile:45` runs `uv sync --frozen` into `/.venv`) and starts the `chromadb` dependency (`docker-compose.yml:16-17`).
  - It bind-mounts `../secrets` and `../llm-rag` (`docker-compose.yml:10-12`).
  - The entrypoint activates the venv and execs bash (`docker-entrypoint.sh:12, 15`).
- *Checkpoint:* `Container is running!!!`, `Architecture: aarch64` (or `x86_64`), `Environment ready! Virtual environment activated.`, `Python version: Python 3.12.x`, `UV version: uv …`, `Activating virtual environment...`, then a prompt like `app@<id>:/app$` (`docker-entrypoint.sh:3-15`; note the "activated" line is printed before the venv is actually activated at line 12).
- *If it fails:* see G5 (project / key) and G8 (folder names).

**B2. Make sure the collection exists and is current.** This is not in the Agents section, but the agent needs it.
```bash
python cli.py --get --chunk_type char-split
```
- *Under the hood:* `get()` fetches 10 documents `where={"book": "The Complete Book of Cheese"}` (`cli.py:402-418`).
- *Checkpoint:* a dict with `ids`, `documents`, `metadatas`.
- *If it fails* with a "collection does not exist" / NotFound error, build it (L05 steps). The three flags may be combined because `main()` checks them in order (`cli.py:484-491`):
```bash
python cli.py --chunk --embed --load --chunk_type char-split
```
- **Rebuild anyway if you loaded before 2026-09-22.** That day Pavlos's book `Tolminc Cheese.txt` was rewritten into a fictional story (commit `85bba32`; it now starts with `Author: Pavlos Protopapas` / `*A fictional tale inspired by Alpine cheesemaking*`). `load` drops and recreates the collection (`cli.py:280-289`), so re-running it is safe.

**B3. Run the agent** (README.md:257-259).
```bash
python cli.py --agent --chunk_type char-split
```
- *Under the hood* (`cli.py:421-478`):
  1. Connect to `llm-rag-chromadb:8000` and get `char-split-collection` (`cli.py:425-429`).
  2. Build the user turn "Describe where cheese making is important in Pavlos's book?" (`cli.py:432-437`).
  3. **Call 1:** `generate_content` with `temperature=0`, `tools=[agent_tools.cheese_expert_tool]` and `FunctionCallingConfig(mode="any")` (`cli.py:441-453`).
  4. Extract `function_call` parts (`cli.py:457`) and execute them. `get_book_by_author` embeds `search_content` and queries Chroma with `n_results=10, where={"author": author}` (`agent_tools.py:41-49`). The 10 chunks are joined into one string, wrapped with `Part.from_function_response(name=…, response={"content": …})` (`agent_tools.py:103-110`).
  5. **Call 2:** send [user turn, the model's own function-call content *unchanged*, the function responses] (`cli.py:465-477`).
- *Checkpoint.* The printed structure matches `out.txt`:
  - `user_prompt_content:  parts=[Part(` (out.txt:7)
  - `LLM Response: … function_call=FunctionCall( args={ 'author': 'Pavlos Protopapas', 'search_content': … }, … name='get_book_by_author'` plus a `thought_signature=b'…'` (out.txt:14-34)
  - `Function calls: [FunctionCall(` … `)]`, the list extracted at `cli.py:457-458` (out.txt:56-63)
  - `Function: get_book_by_author` and `Calling function with args: Pavlos Protopapas , <search text>` (out.txt:64-67)
  - `Response: <10 chunks>`
  - a second `LLM Response: … text="""…"""` (out.txt:98-113).
- **Expect different content than `out.txt`.** The recorded run retrieved chunks about the Soča Valley, transhumance and monastic orders. None of those words exist in the current book; they are all in the pre-`85bba32` version, so `out.txt` was produced with a stale index. With today's book you will get a story about Mara and her grandfather. The README diagram's sample answer ("…production of Tolminc cheese, a traditional cheese made in the Slovenian Alps…", `images/llm-rag-flow-3.png`) also comes from the old book.
- *If it fails:*
  - `KeyError: 'GCP_PROJECT'`: you are not inside the container started by `docker-shell.sh`.
  - `403 PERMISSION_DENIED`: the service-account role is missing, or the Vertex AI API is disabled.
  - `404 … model`: the project cannot see `gemini-3.1-flash-lite` in location `global`. Check model availability.

**B4. Read the output like a debugger.** Find the three objects of §3.2: the `FunctionCall` (with an `id='call_…'`), your `Response:` block, and the final text. Note `automatic_function_calling_history=[]` (out.txt:51): google-genai did **not** auto-run anything, because the tools were declarations, not Python callables.

**B5. (Optional) Hosted demo.** The "Cheese Agent Tool" at https://ac215-llm-rag.dlops.io/agent (README.md:268; it responded HTTP 200 on 2026-10-12). The compose file whitelists that origin for browser access to your local Chroma (`docker-compose.yml:25-26`), which is how the hosted **Chroma UI** (README.md:162) can read `localhost:8000`.

**B6. Exit and stop.**
```bash
exit                   # leaves the llm-rag-cli container (it is removed: --rm)
docker compose down    # stops llm-rag-chromadb (data stays in ./docker-volumes/chromadb)
```

### Part C — Tutorial 1c: Google ADK (`llm-agent-google-adk`, local uv)

**C1. Clone and configure** (`README.md:74-101`; the README says `cd google-adk-tutorial`, but the folder is `llm-agent-google-adk`).
```bash
cd ~/Desktop/AC215
git clone https://github.com/dlops-io/llm-agent-google-adk.git
cd llm-agent-google-adk
cp .env.example .env
#   edit .env:  GOOGLE_API_KEY=<your AI Studio key>
#               GEMINI_MODEL=gemini-3.1-flash-lite     (see G2; not the file's gemini-2.5-flash)
uv add "google-adk>=1.8.0,<1.28"    # fix from this guide, not in the README: see G1
uv sync
```
- *Under the hood:* the root `pyproject.toml:9-20` installs ADK, LiteLLM, FastAPI, MCP, Vertex SDK, **chromadb and sentence-transformers (which pulls PyTorch)**. With no lockfile, `uv sync` without the pin resolves **google-adk 2.11.0** today. That version refuses folder names like `1-baseline` (G1). With the pin it resolves **1.27.5** (both checked by metadata-only resolution).
- *Checkpoint:* `uv run adk --version` prints a line ending in `version 1.27.5` (the CLI has a click `version_option`).
- *If it fails:* expect a large download because of torch (G13).

**C2. Run the web UI** (`README.md:111-119`).
```bash
uv run adk web            # add --port 8080 if llm-rag's ChromaDB still holds 8000
```
- *Under the hood:*
  - `adk web` takes an *agents directory* (default: the current directory; `cli_tools_click.py`, `agents_dir` argument with `file_okay=False`).
  - It lists the subfolders. When you pick one, it imports `<folder>.agent` and reads `root_agent`, after loading the nearest `.env` with `override=True`.
  - It serves FastAPI on `127.0.0.1:8000` (`--host`/`--port` defaults).
- *Checkpoint:* open http://localhost:8000 and pick `1-baseline` in the agent dropdown.
- *If it fails:*
  - `Invalid agent name: '1-baseline'` → G1.
  - `address already in use` → G3.
  - `QUICKSTART.md`'s `uv run adk web 1-baseline/agent.py` fails because the argument must be a directory (G9).

**C3. Module 1: Travel-planner pipeline** (`1-baseline/README.md:76-92`, `1-baseline/agent.py:14-39`).
- *Do:* type a trip request, e.g. "2 adults, Boston → Montréal, Oct 30-Nov 2, $1500, train preferred".
- *Under the hood:* `SequentialAgent` runs `ItineraryValidator` → `TravelPlanner` → `TripSummarizer`. Each `output_key` lands in session state, and `{itinerary_validation}` / `{travel_plan}` are substituted into the next instruction (§3.6).
- *Checkpoint:* three agent responses in order. In the UI's event/state inspector, the three state keys `itinerary_validation`, `travel_plan`, `trip_summary` appear.
- *If it fails* with `404 … models/gemini-2.0-flash`: your `.env` has no `GEMINI_MODEL`, or a module `.env` overrides it (G2).

**C4. Module 2: LiteLLM** (`2-litellm/README.md:67-88`).
- *As written* it cannot work. `root_agent = LlmAgent(model="gpt-4", …)` (`2-litellm/agent.py:25-29`) is a bare model name, which ADK 1.x does not resolve ("Model gpt-4 not found."). 1.27.5 does register LiteLLM, but only for provider-prefixed names such as `openai/…`. The `.env.example` key `AWS_OPENAI_API_KEY` is read by no code (`litellm_config.py:28` reads `OPENAI_API_KEY`).
- *Fix (reasoned, not run):* see Exercise 7 (use `LiteLlm(model="openai/gpt-4o-mini")` and `OPENAI_API_KEY`).
- *Optional check:* the README's `uv run python litellm_config.py` (`2-litellm/README.md:81-88`) prints **nothing**, whatever keys you set: the module only defines `configure_litellm()` and `get_available_models()` and has no `__main__` block. To really check, run `cd 2-litellm && uv run --project .. python -c "from litellm_config import configure_litellm; configure_litellm()"`. It prints `✓ OpenAI configured` if `OPENAI_API_KEY` is set (`litellm_config.py:28-32`) *(reasoned, not run)*. `agent.py:22` also calls `configure_litellm()` on import, so the same line shows up in the `adk web` terminal.

**C5. Module 3: MCP filesystem tools** (`3-mcp-tools/README.md:78-94`).
- *Prereq:* `node --version` works.
- *Do:* in the UI pick `3-mcp-tools` and ask "List files in this directory", then "Read the README.md file".
- *Under the hood:* `MCPToolset(StdioConnectionParams(StdioServerParameters(command='npx', args=['-y', '@modelcontextprotocol/server-filesystem', ALLOWED_PATH]), timeout=10), tool_filter=[...])` (`3-mcp-tools/agent.py:20-29`). ADK spawns the Node server as a **child process** and talks MCP over stdin/stdout. `ALLOWED_PATH` defaults to the module folder (`agent.py:17-18`).
- *Checkpoint:* function-call events for `list_directory` and `read_file`, with the folder's four tracked files listed (`.env.example`, `README.md`, `agent.py`, `pyproject.toml`), plus a `__pycache__` directory once Python has imported `agent.py`.
- *If it fails:* `npx: command not found` → install Node. The first run downloads the package; a 10 s timeout on a slow network gives a connection timeout, so retry.

**C6. Module 4: FastAPI deployment** (`4-production-ready/README.md:9-52`).
- Its `app/` package is not an `adk web` agent folder.
- *Run from the root venv (reasoned, not run).* The README's per-module `uv sync` builds a second venv with `google-adk[all]`.
```bash
cd 4-production-ready
uv run --project .. uvicorn app.main:app --reload --port 8080
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"user_message": "Hello!"}'
```
- *Under the hood:*
  - `/chat` calls `AgentRunner.run`, which creates a **new random session per request** (`app/runner.py:24-33`) and returns the last `is_final_response()` text (`runner.py:45-46`).
  - `/chat/stream` yields NDJSON `{"chunk": …}` lines (`app/main.py:35-44`). It is not token-level streaming: only final-response events are yielded (`runner.py:72-73`).
- *Checkpoint:* `{"response":"..."}`. The README also suggests http://localhost:8080/docs (FastAPI's Swagger UI, `README.md:22`); `GET /health` returns `{"status":"healthy"}` (`app/main.py:23-25`).
- *Docker variant:* `docker build -t adk-agent .` then `docker run -p 8080:8080 -e GOOGLE_API_KEY=… -e GEMINI_MODEL=gemini-3.1-flash-lite adk-agent`. Pass `GEMINI_MODEL`, or the image falls back to the retired default (`app/agent.py:12`).

**C7. Module 5: Custom agents** (`5-custom-agent/README.md:113-153`).
- In the UI, `5-custom-agent` prefixes 🤖 to the final reply (`5-custom-agent/agent.py:36-42`).
- Scripts:
```bash
cd 5-custom-agent
uv run --project .. python simple_custom_agent.py
uv run --project .. python conditional_agent.py
```
- *Checkpoint:*
  - `simple_custom_agent.py` prints `Agent: 🤖 [Bot]: …` (`simple_custom_agent.py:84-94`).
  - `conditional_agent.py` prints `→ Routed to: SimpleHandler` / `ComplexHandler` / `ClarificationHandler`, once per handler event, then `Response:` for each of three test queries (`conditional_agent.py:243-250`).

**C8. Module 6: RAG agents (optional; RAG was L05's topic).**
- `6-rag/2-custom-chromadb-rag`: `docker compose up -d`, `uv sync`, `cp .env.example .env`, `uv run python ingest_documents.py`, then `uv run python agent.py` (`6-rag/README.md:122-141`). That module's `.env.example:10` sets `GEMINI_MODEL=gemini-2.0-flash`, and the copied `.env` becomes the nearest one, so fix it (G2). `agent.py` connects to Chroma and calls `get_collection` at import time (lines 42-43), so ingest first.
- Its ChromaDB also publishes port 8000 (`6-rag/2-custom-chromadb-rag/docker-compose.yml:7-8`), so stop llm-rag's first.
- `uv run adk web` *in that folder* does not find the agent: ADK looks for subfolders, and the module imports `agent_tools` relative to itself (G14).

**C9. Stop.** Ctrl+C the servers. `docker compose down` any ChromaDB you started.

### Part D — Tutorial 2: Travel Planner (Colab)

**D1.** Copy the notebook (`tutorials_demo.md:94`). Add the `OPENAI_API_KEY` secret. Run cell 8 (`%pip install -q "openai-agents==0.3.2"`), then cells 9-10.

**D2. Catalog and tools** (cells 12-16).
- *Under the hood:*
  - Mock catalog: 3 cities and 6 hotels, with prices in **cents** (cell 12).
  - Five search functions print `[tool]` and `[catalog]` lines (cell 14).
  - `finalize_plan` computes a proposal and gates it (cell 15).
- *Checkpoint:* cell 16 prints LA attractions `LAX-OBSERVATORY` (0.0) and `LAX-MUSEUM` (25.0). (Expected from the code; this cell has no saved output.)

**D3. Business logic and instructions** (cells 18-21).
- `check_itinerary` does all arithmetic. `run_turn` enforces confirmation, adds a corrective retry, and decides what the user sees from state (cell 18, lines 91-138).
- `build_agent()` uses model `gpt-5.6-luna`, six tools, `SQLiteSession("travel-planner")` and `output_type=PlannerReply` (cell 21).
- The model-visible tool is `finalize_itinerary`, a `@function_tool` wrapper (cell 21, lines 3-10) around `finalize_plan` (cell 15). The `[tool]` log line is printed inside `finalize_plan`, so the output says `[tool] finalize_plan: …` even though the model called `finalize_itinerary`.

**D4. Run the scripted four-turn example** (cells 24-27). Each cell asserts the reply kind.
- *Checkpoints (saved outputs):*
  - Turn 1 → `Kind: clarification`, asking "San Francisco or Los Angeles?" and for the allowances.
  - Turn 2 → five tool calls (`flight_search` ×2, `hotel_search`, `attraction_search`, `restaurant_search`) and `Kind: options` listing `SEA-SFO-20261106-1` etc.
  - Turn 3 → `[tool] finalize_plan: …` then `Kind: clarification` with the exact JSON proposal.
  - Turn 4 (`"yes"`) → `Kind: itinerary` and a budget report with `"total_usd": 2690.0`, `"remaining_usd": 3310.0`.
- *Verify the 2690 yourself:*

| Item | Calculation | Amount |
|---|---|---|
| Flights | 2 people × (220 + 220) | $880 |
| Hotel | 4 nights × 250 | $1000 |
| Food | 60 × 2 people × 5 calendar days | $600 |
| Transport | whole-trip allowance | $150 |
| Museum | 30 × 2 people | $60 |
| **Total** | | **$2690** |

- *If it fails:* an `AssertionError` on `reply.kind` means the model took a different but plausible path, for example asking one more question. Re-run the turn or continue interactively.

**D5. Interactive chat** (cells 28-29). Type multi-line messages, finish with a blank line or `/send`; `exit` or `quit` leaves. `chat_loop()` calls `build_agent()` again, so it starts with a fresh session and `TravelContext`, not the scripted conversation. `SQLiteSession` defaults to an in-memory database (`openai-agents 0.3.2 agents/memory/sqlite_session.py:21-24`), so history lasts only for this runtime.

### Part E — Tutorial 3: Cheese Newsletter Harness (Colab)

**E1. Install.** Copy the notebook (`tutorials_demo.md:98`), add the secret, run cell 8 (`agent-framework-core==1.18.0`, `agent-framework-openai==1.14.3`, `opentelemetry-api==1.42.1`), then cells 9-10.

**E2. Edit `USERS`** (cell 16, lines 7-12). Replace the staff names and addresses with yours. Email is **preview-only**: `send_email` writes HTML, and `Settings` only validates the address format.
- Keep at least two readers, because cell 31 displays `receipts[1]`.
- `"Summerville"` was researched as **Summerville, South Carolina** in the saved output. If you meant Somerville, MA, spell it that way.

**E3. Run cells 16-25,** which define contracts, validation, rendering, the researcher (with web search) and editor sub-agents as `@tool`s, and the orchestrator (`max_iterations: 16`, `allow_multiple_tool_calls: False`).

**E4. Generate** (cell 27, `# @title Run Demo`).
- *Checkpoint (saved output):* for each reader:
  ```
  Generating newsletter for <city> · <YYYY-MM>
    [tool] researcher_agent
    [tool] editor_agent
    [tool] send_email: validating and saving HTML (mock)
  Saved HTML: /content/newsletter_output/<Name>-<YYYY-MM>-<batch>.html (<n> bytes). No email sent.
  ```
- The editor may run several times: Summerville took four `editor_agent` calls in the saved run, because validation errors are fed back as tool results.
- The saved output covers **four** readers (Summerville, Charlotte, Atlanta, Cambridge) because Rashmi and Chris were active when it was run. The current cell 16 comments them out (lines 10-11), so a fresh run makes two newsletters, and the output ends with `Created 2 mock emails. No email was sent.`
- *If it fails:*
  - `RuntimeError: No successful tool receipt…` means the orchestrator ended without a valid `send_email` (cell 18, lines 119-120). Read the reply text it includes.
  - A `ValueError` about the month or email comes from `Settings.__post_init__` (cell 16).

**E5. View** (cells 30-31). Each cell renders a saved HTML preview and shows file links.

---

## 5. Code tour

**llm-rag/** (only the files that matter for L06)
```
llm-rag/
├── README.md              # L05+L06 tutorial; Agents = lines 242-272
├── cli.py                 # all steps; agent() at 421-478; flags at 511-547
├── agent_tools.py         # 2 FunctionDeclarations, 2 Python tools, the dispatcher
├── out.txt                # a recorded `--agent` run (2026-09-22, made against the OLD book)
├── docker-shell.sh        # sets GCP_PROJECT + credentials path, `docker compose run --rm llm-rag-cli`
├── docker-compose.yml     # llm-rag-cli + chromadb services, bind mounts, CORS for hosted UIs
├── Dockerfile             # python:3.12-slim-bookworm, uv sync --frozen into /.venv, user app
├── docker-entrypoint.sh   # prints info, activates /.venv, exec bash
├── pyproject.toml/uv.lock # google-genai 1.39.1, chromadb 1.1.0, langchain 0.3.27 ...
├── input-datasets/books/  # 11 .txt books; "Tolminc Cheese.txt" is "Pavlos's book"
└── images/llm-rag-flow-3.png  # the 6-step agent flow diagram
```

**llm-agent-google-adk/**
```
llm-agent-google-adk/
├── README.md, QUICKSTART.md      # overview; QUICKSTART is stale (G9)
├── pyproject.toml, .env.example  # root env used by `uv run adk web`
├── 1-baseline/agent.py           # SequentialAgent travel planner (root_agent)
├── 2-litellm/agent.py, litellm_config.py   # multi-provider (broken as written, G11)
├── 3-mcp-tools/agent.py          # MCPToolset over stdio (npx filesystem server)
├── 4-production-ready/app/{agent,runner,main}.py, Dockerfile  # FastAPI wrapper
├── 5-custom-agent/{agent,simple_custom_agent,conditional_agent}.py  # BaseAgent subclasses
└── 6-rag/{1-vertex-rag-engine, 2-custom-chromadb-rag}/   # RAG agents (managed vs ChromaDB)
```

**Excerpt 1. A tool's contract, written by hand**

`llm-rag/agent_tools.py:9-19`
```python
get_book_by_author_func = types.FunctionDeclaration(
    name="get_book_by_author",
    description="Get the book chunks filtered by author name",
    # Function parameters are specified in OpenAPI JSON schema format
    parameters={
        "type": "object",
        "properties": {
            "author": {
                "type": "string",
                "description": "The author name",
                "enum": [
```
- `name` is what the model will write in its `function_call`. It must match the `if function_call.name == …` branches in the dispatcher (`agent_tools.py:88, 111`).
- `description` (here and on each property) is the **only** documentation the model sees. Both functions' `search_content` descriptions even coach the model: "Expand the search term to a a sentence or two to get better matches" (typo in the source; `agent_tools.py:33, 61`).
- `enum` (lines 19-29) restricts `author` to 9 strings. Constrained decoding means the model cannot invent an author spelling that fails the metadata filter. It also means it cannot target the two books whose authors are missing from the list (E4 in §9).
- `required` (line 36) forces both arguments to be present.

**Excerpt 2. The real function behind the contract**

`llm-rag/agent_tools.py:41-49`
```python
def get_book_by_author(author, search_content, collection, embed_func):

    query_embedding = embed_func(search_content)

    # Query based on embedding value
    results = collection.query(
        query_embeddings=[query_embedding], n_results=10, where={"author": author}
    )
    return "\n".join(results["documents"][0])
```
- `collection` and `embed_func` are **not** in the schema. Your code injects them, so the model only controls `author` and `search_content`.
- `where={"author": author}` is a metadata filter on the `author` key, which `load_text_embeddings` added per book (`cli.py:132-138`).
- `n_results=10` returns 10 of the **24** char-split chunks of the current Tolminc book.
- The return value is a single string. The model never sees chunk IDs or distances.

**Excerpt 3. Call 1: force the model to pick a tool**

`llm-rag/cli.py:439-453`
```python
    # Step 1: Prompt LLM to find the tool(s) to execute to find the relevant chunks in vector db
    print("\n\n\n\nuser_prompt_content: ", user_prompt_content)
    response = llm_client.models.generate_content(
        model=GENERATIVE_MODEL,
        contents=user_prompt_content,
        config=types.GenerateContentConfig(
            temperature=0,
            tools=[agent_tools.cheese_expert_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="any"
                )
            )
        )
    )
```
- `temperature=0` makes tool selection as repeatable as possible.
- `tools=[cheese_expert_tool]` is one `types.Tool` holding both declarations (`agent_tools.py:79-81`).
- `mode="any"` is case-insensitively mapped to `ANY` (google-genai `_common.py:482-492`). The model **must** answer with one or more function calls.
- No `system_instruction` is passed. `SYSTEM_INSTRUCTION` at `cli.py:40-58` is defined but used nowhere (E3 in §9).

**Excerpt 4. Call 2: send back the call and its results**

`llm-rag/cli.py:464-477`
```python
        # Call LLM with retrieved responses
        response = llm_client.models.generate_content(
            model=GENERATIVE_MODEL,
            contents=[
                user_prompt_content,  # User prompt
                response.candidates[0].content,  # Function call response
                Content(
                    parts=function_responses
                ),
            ],
            config=types.GenerateContentConfig(
                tools=[agent_tools.cheese_expert_tool]
            )
        )
```
- The history is three turns: the user question, **the model's own turn unchanged**, and your function responses.
- Re-sending `response.candidates[0].content` verbatim preserves the `thought_signature` (out.txt:28). Google's thinking guide says thought blocks must be resent "exactly as they were received".
- `tools=` is passed again but without `tool_config`, so the mode is AUTO. The model *may* call another tool, and this code has no loop to handle it (§3.3).
- Line 478 prints the whole response object. To see only the answer, print `response.text`.

**Excerpt 5. Packaging a tool result**

`llm-rag/agent_tools.py:103-110`
```python
            parts.append(
                types.Part.from_function_response(
                    name=function_call.name,
                    response={
                        "content": response,
                    },
                ),
            )
```
- A function response is a `Part` whose `name` echoes the call. `response` must be a JSON object, so the chunk string is wrapped as `{"content": …}`.
- The call's `id` (`out.txt:25`) is not echoed. Matching is by name, which works because each tool is called at most once here.

**Excerpt 6. The agent loop inside ADK** (third-party library, not in either repo)

`google-adk 1.19.0 · google/adk/flows/llm_flows/base_llm_flow.py:343-352`
```python
    while True:
      last_event = None
      async with Aclosing(self._run_one_step_async(invocation_context)) as agen:
        async for event in agen:
          last_event = event
          yield event
      if not last_event or last_event.is_final_response() or last_event.partial:
        if last_event and last_event.partial:
          logger.warning('The last event is partial, which is not expected.')
        break
```
- One "step" is one LLM call plus any tool executions it triggers.
- Every event is streamed out with `yield`. That is what `adk web` displays, and what your `async for event in runner.run_async(...)` receives.
- The exit test is `is_final_response()`: no function calls, no function responses, not partial (`events/event.py:82-97`). This is exactly the loop llm-rag hand-codes with only two iterations.
- ADK 2.11 keeps the same `while True` shape and adds abort checks (`base_llm_flow.py:322-343`).

**Excerpt 7. A pipeline that communicates through state**

`llm-agent-google-adk/1-baseline/agent.py:14-26`
```python
validator = LlmAgent(
    name="ItineraryValidator",
    model=GEMINI_MODEL,
    instruction="You validate trip requests. Extract traveler count, origin, destinations, dates, budget, and constraints from the input.",
    output_key="itinerary_validation"
)

processor = LlmAgent(
    name="TravelPlanner",
    model=GEMINI_MODEL,
    instruction="Using {itinerary_validation}, design a realistic multi-day travel plan with routing, daily schedule, estimated costs, and key booking recommendations.",
    output_key="travel_plan"
)
```
- `output_key` stores this agent's final text in `session.state["itinerary_validation"]`.
- `{itinerary_validation}` is replaced with that value *before* the TravelPlanner's call. Without the validator's output in state, you would get `KeyError: Context variable not found`.
- `GEMINI_MODEL` comes from `.env`, with fallback `"gemini-2.0-flash"` (line 12; retired, G2).
- Lines 35-39 wrap the three agents in `SequentialAgent(... sub_agents=[validator, processor, summarizer])` and name it `root_agent`. That variable name is what `adk web` looks for.

**Excerpt 8. Plug in someone else's tools via MCP**

`llm-agent-google-adk/3-mcp-tools/agent.py:20-29`
```python
toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',
            args=['-y', '@modelcontextprotocol/server-filesystem', ALLOWED_PATH]
        ),
        timeout=10
    ),
    tool_filter=['read_file', 'list_directory', 'search_files']
)
```
- `StdioServerParameters(command='npx', …)` means ADK launches the server as a child process and speaks JSON-RPC over its stdin/stdout.
- `ALLOWED_PATH` is the only directory the server will touch. It defaults to this module's folder (lines 17-18).
- `tool_filter` exposes 3 of the server's 14 tools. The current server (npm 1.0.0) still registers `read_file`, but marks it deprecated in favour of `read_text_file`. If a future release drops it, the filter silently leaves the agent without a read tool.

**Excerpt 9. A custom agent that routes with plain Python**

`llm-agent-google-adk/5-custom-agent/conditional_agent.py:84-97`
```python
        # Get classification result
        complexity = ctx.session.state.get("query_complexity", "simple")
        logger.info(f"  Classification: {complexity}")

        # Step 2: Route based on complexity
        if complexity == "simple":
            logger.info("  Step 2: Routing to simple handler...")
            async for event in self.simple_handler.run_async(ctx):
                yield event

        elif complexity == "complex":
            logger.info("  Step 2: Routing to complex handler...")
            async for event in self.complex_handler.run_async(ctx):
                yield event
```
- The classifier (lines 158-172) writes its text to `state["query_complexity"]` via `output_key`. The runner applies the state change as soon as the classifier's final event is yielded, so it is visible on the next line.
- The comparison is **exact**. ADK stores the raw joined text (google-adk 1.19.0 `agents/llm_agent.py:802-816`), so `"Simple"` or `"simple\n"` would fall through to the `else` (clarification) branch. Exercise 5 covers this.
- `async for … yield event` re-emits every sub-agent event, so the runner and UI still see everything.

**Excerpt 10. The approval gate (harness)**

`L06_travel_planner.ipynb` · cell 15 (`# @title Finalize Plan Tool`), lines 33-42 of the cell
```python
    # A model tool call can propose a plan, but only a later human turn can
    # approve that exact proposal. This prevents the model from silently
    # inventing requirements or treating its own suggestion as confirmation.
    if proposal != travel_context.approved_proposal:
        travel_context.pending_proposal = proposal
        return {
            "status": "needs_confirmation",
            "requirements": proposal,
            "message": "Stop and wait for the user's next chat reply.",
        }
```
- `approved_proposal` is set only by `apply_confirmation(prompt, context)`. That runs **before** the agent, on the human's raw text, and accepts only `y`/`yes`/`confirm`/… (cell 18). This is why the model cannot approve its own proposal by calling `finalize_itinerary` a second time in the same turn: in turn 3 `approved_proposal` is still `None`, so every call returns `needs_confirmation`.
- Any difference in IDs, traveller count or allowances creates a new pending proposal. Attraction IDs are sorted, so order does not matter (cell 15, line 30).
- The tool *returns* a `needs_confirmation` status instead of raising. The model sees it as a normal tool result, and the instructions tell it to stop (cell 20).

**Excerpt 11. Success is a receipt, not a sentence**

`L06_cheese_newsletter_harness.ipynb` · cell 18 (`# @title Business Logic`), lines 118-125 of the cell
```python
    reply = await invoke_agent(agent, json.dumps(request), context)
    if context.receipt is None:
        raise RuntimeError(f"No successful tool receipt. Orchestrator response: {reply}")

    receipt = context.receipt
    if not Path(receipt["path"]).is_file():
        raise RuntimeError("The mock email receipt points to a file that does not exist.")
    print(f"Saved HTML: {receipt['path']} ({receipt['bytes']} bytes). No email sent.")
```
- `invoke_agent` passes the application context to every tool through `function_invocation_kwargs` (cell 20, lines 19-25). Tools read it with `ctx.kwargs` and never receive it as a model-visible argument.
- `context.receipt` is set only inside `save_newsletter` after validation and rendering succeed (cell 16).
- The model's own claims (`reply`) are used only in the error message. The file system is the source of truth.

**Excerpt 12. Agents as tools**

`L06_cheese_quiz.ipynb` · cell 68, lines 1-8 of the cell
```python
# Agents-as-tools for orchestration
stilton_tool = stilton_agent.as_tool(
    "research_facts", "Find ~5 concise, citable facts for a topic."
)
brie_tool = brie_agent.as_tool("write_quiz", "Convert facts into a 5-question MCQ quiz.")
cheddar_tool = cheddar_agent.as_tool("review_quiz", "QA the quiz against the facts.")
mozzarella_tool = mozzarella_agent.as_tool("format_quiz", "Format quiz into Markdown.")
ricotta_tool = ricotta_agent.as_tool("format_quiz_json", "Format quiz into JSON.")
```
- `.as_tool(name, description)` turns an entire agent, with its own model, tools and `output_type`, into a single function the orchestrator can call with a text input (`openai-agents 0.23.1 agents/agent.py:606-618`).
- The orchestrator (cell 70) decides the order. The "assembly line" lives only in its instructions, so nothing in code enforces "at most 2 review rounds". Compare ADK's `SequentialAgent`, where the order *is* code.
- `mozzarella_tool` is defined but not given to the orchestrator (cell 70, tools list).

---

## 6. Gotchas and common errors

| # | Symptom | Cause | Fix |
|---|---|---|---|
| G1 | `uv run adk web` lists `1-baseline`, `2-litellm`… but selecting one fails with `Invalid agent name: '1-baseline'. Agent names must be valid Python identifiers (letters, digits, and underscores only).` | No lockfile (`.gitignore:34`). `google-adk>=1.8.0` (`pyproject.toml:10`) resolves to **2.11.0** today. Since **1.28.0** (2026-03-26), ADK validates folder names against `^[a-zA-Z0-9_]+$` (`cli/utils/agent_loader.py`: line 191 in 1.28.0, line 250 in 2.11.0). The repo was written for ≤1.27, when `import_module("1-baseline.agent")` worked. (2.11 also hides folders without an `agent.py` or `__init__.py`, so `4-production-ready` and `6-rag` are not even listed.) | Pin: `uv add "google-adk>=1.8.0,<1.28"` (resolves 1.27.5), then `uv sync`. Or keep 2.x and give the folders valid names *(reasoned, not run)*: `mkdir agents && ln -s ../1-baseline agents/baseline && ln -s ../3-mcp-tools agents/mcp_tools && ln -s ../5-custom-agent agents/custom_agent`, then `uv run adk web agents`. |
| G2 | `404 NOT_FOUND … models/gemini-2.0-flash is not found` (or a "no access" error for 2.5) | Every agent falls back to `gemini-2.0-flash` (e.g. `1-baseline/agent.py:12`, `4-production-ready/app/agent.py:12`), and `5-custom-agent/.env.example:5` sets it explicitly. Google shut it down on **2026-06-01**. The root `.env.example:21` uses `gemini-2.5-flash`, which Google now limits "to users who have actively used them in the past". ADK loads the **nearest** `.env` with `override=True`, so a copied module `.env` silently wins over the root one. | In the root `.env` set `GEMINI_MODEL=gemini-3.1-flash-lite` (the model llm-rag uses, `cli.py:27`; earliest shutdown 2027-05-07). Do not copy module `.env.example` files, or fix their `GEMINI_MODEL` too. |
| G3 | `adk web` exits with an `[Errno 48]` (macOS) / `[Errno 98]` (Linux) "address already in use" error for port 8000 | `adk web` defaults to `127.0.0.1:8000`. llm-rag's ChromaDB publishes `8000:8000` (`docker-compose.yml:21-22`), and so does `6-rag/2-custom-chromadb-rag/docker-compose.yml:7-8`. | `docker compose down` in llm-rag, or `uv run adk web --port 8080`. |
| G4 | Port 8000 is still busy after you `exit`ed the llm-rag shell | `docker compose run --rm llm-rag-cli` (`docker-shell.sh:12`) starts the `chromadb` dependency (`docker-compose.yml:16-17`), but `--rm` removes only the one-off CLI container. | `docker compose down` (or `docker stop llm-rag-chromadb`). |
| G5 | `KeyError: 'GCP_PROJECT'`, `403 PERMISSION_DENIED`, `DefaultCredentialsError` | `cli.py:23` requires `GCP_PROJECT`, which only `docker-shell.sh:7` sets. The key must exist at `../secrets/llm-service-account.json`, and the SA needs the Vertex AI User role. | Always start via `sh docker-shell.sh`; edit line 7; check `ls ../secrets`; grant the role; enable the Vertex AI API. |
| G6 | `--agent` fails at `get_collection` with "Collection [char-split-collection] does not exist"-style NotFound | The agent uses the L05 collection (`cli.py:427-429`). ChromaDB data lives in `llm-rag/docker-volumes/chromadb`, which is git-ignored (`llm-rag/.gitignore:3`), so a fresh clone has none. | `python cli.py --chunk --embed --load --chunk_type char-split`. Or run with the chunk type you did load (`--chunk_type recursive-split`). |
| G7 | Your answer is about "Mara" and her grandfather, not the Soča Valley as in `out.txt` or the Slovenian Alps as in the README diagram | `Tolminc Cheese.txt` was rewritten on 2026-09-22 (`85bba32`). `out.txt` was recorded against an index built from the old file. | Expected. Re-load if you want your index to match the current repo. Remember that changing source docs requires re-running chunk → embed → load. |
| G8 | Inside the container `/app` is empty, or `/secrets` is empty | Bind mounts are relative and name-dependent: `../llm-rag:/app` and `../secrets:/secrets` (`docker-compose.yml:11-12`). Cloning into a folder not named `llm-rag`, or putting `secrets/` inside the repo, breaks them. | Layout must be `AC215/llm-rag/` and `AC215/secrets/` side by side (README.md:64-69). |
| G9 | `QUICKSTART.md` commands fail: click rejects the argument with an `Invalid value for '[AGENTS_DIR]'` / "is a file" error *(reasoned, not run)*; `No such file` for `sequential_example.py`, `story_flow_agent.py` …; `3-mcp-connections` not found | `adk web` takes a directory (`file_okay=False`). The scripts named at `QUICKSTART.md:70-72, 79, 85, 91-92` never existed in this repo's git history (only `conditional_agent.py`, line 93, exists). The module has been called `3-mcp-tools` since the initial commit `f24b771`; no `3-mcp-connections` folder ever existed in this repo's history, so QUICKSTART was stale from the start. | Use `uv run adk web` from the repo root and pick the folder in the UI. Use the README module instructions, not QUICKSTART. |
| G10 | `uv run adk` prints a usage/help screen and nothing starts | `2-litellm/README.md:74`, `3-mcp-tools/README.md:85` and `5-custom-agent/README.md:120` omit the `web` subcommand. | `uv run adk web`. |
| G11 | `2-litellm` errors on the first message: `Model gpt-4 not found.` (ADK 1.x), or an OpenAI auth error (ADK 2.x) | `model="gpt-4"` (`2-litellm/agent.py:26`) is a bare name. google-adk 1.19.0 registers only Gemini/Gemma/Apigee names (`models/__init__.py:33-35`). 1.27.5 also registers `LiteLlm` when `litellm` is installed, but only for provider-prefixed patterns such as `openai/.*` (`models/lite_llm.py`, `supported_models`), so a bare `gpt-4` still matches nothing and raises `Model gpt-4 not found.` You need `LiteLlm(model="openai/…")` (or, in 1.27.5, the string `"openai/…"`). The README's "ADK supports LiteLLM model names natively" (`2-litellm/README.md:195`) is wrong for bare names. `AWS_OPENAI_API_KEY` is read nowhere. | Exercise 7. |
| G12 | `3-mcp-tools`: `npx: command not found`, or "connection timeout" | Needs Node.js. The first `npx -y` download can exceed `timeout=10` (`3-mcp-tools/agent.py:26`). | Install Node (`brew install node`), run `npx -y @modelcontextprotocol/server-filesystem .` once to warm the cache (it then waits on stdin; stop it with Ctrl+C), retry. |
| G13 | `uv sync` in the ADK repo downloads gigabytes / takes many minutes | The root `pyproject.toml:18-19` includes `chromadb` and `sentence-transformers`, which pull PyTorch (the version depends on platform and pins: a pinned macOS-arm64 resolution picked torch 2.11.0, an unpinned Linux x86_64 resolution 2.14.1). The README's per-module `uv sync` creates *additional* venvs; module `pyproject.toml`s ask for `google-adk[all]`, which on 2.x pulls dozens more packages. | Sync once at the root and run module scripts with `uv run --project .. …`. Be patient the first time. |
| G14 | `6-rag/2-custom-chromadb-rag`: healthcheck stays unhealthy; `curl …/api/v1/heartbeat` errors; no agent appears in `adk web` | The healthcheck and README use the v1 API (`6-rag/2-custom-chromadb-rag/docker-compose.yml:16`, `6-rag/2-custom-chromadb-rag/README.md:33`), but the chromadb client of this era talks `/api/v2` (chromadb 1.1.0 `config.py:153`). The volume path `/chroma/chroma` and the env vars `IS_PERSISTENT`/`PERSIST_DIRECTORY` (`6-rag/2-custom-chromadb-rag/docker-compose.yml:10-13`) are from older images; llm-rag mounts `/data`. `adk web` run inside that folder lists *subfolders*, and `6-rag/2-custom-chromadb-rag/agent.py:29` imports `agent_tools` as a top-level module. | Check with `curl http://localhost:8000/api/v2/heartbeat`. Mount the volume at `/data` if you need persistence. Run the agent with `uv run python agent.py` as the README's "recommended" path says. |
| G15 | Colab: `SecretNotFoundError` / `NotebookAccessError`; or `FileNotFoundError: quiz-ui.html` in cell 62 | The secret must be named exactly `OPENAI_API_KEY` with notebook access on. Cell 13's `gdown` from Google Drive can fail (quota or permission) and then `open("quiz-ui.html")` fails. | Fix the secret. Re-run cell 13 and check the two `To: /content/...` lines. |
| G16 | Colab Cheese Quiz: import errors or API changes | Cell 10 installs `fastmcp` and `openai-agents` **unpinned**, with all output hidden. Today that means fastmcp 4.1.0 and openai-agents 0.23.1. The classes the notebook imports were verified to still exist in 0.23.1. The notebook was last run on 2026-09-23. | If something breaks, pin what worked then, e.g. `pip install "openai-agents==0.22.3"`, and remove the `> /dev/null 2>&1`. |
| G17 | Copying `await …` cells into a `.py` file gives `SyntaxError: 'await' outside function` | Colab/Jupyter allow top-level `await`; Python scripts do not. | Wrap the code in `async def main(): …` and call `asyncio.run(main())`, as `5-custom-agent/simple_custom_agent.py:97-99` does. |
| G18 | A key ends up on GitHub | You keep these clones inside your own `MLOps_Learning` repo. `secrets/` lives *outside* `llm-rag/` and is not covered by llm-rag's `.gitignore`. ADK `.env` files are ignored only by the ADK repo's own `.gitignore:24, 48`. | Add `secrets/`, `**/.env` and `*.json` keys to the top-level `.gitignore` of `MLOps_Learning` before the first `git add`. Never paste keys into notebooks; use Colab Secrets. |
| G19 | `cd 2-litellm && uv run python litellm_config.py` ("Test LiteLLM Configuration", `2-litellm/README.md:81-88`) prints nothing, even with keys set | `litellm_config.py` only defines `configure_litellm()` and `get_available_models()`; there is no `if __name__ == "__main__":` block. (Run from `2-litellm/`, plain `uv run` also builds that module's own venv from `2-litellm/pyproject.toml`.) | `uv run --project .. python -c "from litellm_config import configure_litellm; configure_litellm()"` (§4 Part C4). |

---

## 7. Where this sits in the course

**What L05 (Introduction to RAG) gave you:**
- The `llm-rag` container: Python 3.12 + uv, Vertex AI through a service-account key, ChromaDB as a second container with a persistent bind mount.
- The pipeline `--chunk` → `--embed` (gemini-embedding-001, 256-d) → `--load` (cosine collections with `book`/`author`/`year` metadata) → `--query` → `--chat` (README.md:91-215).

**What L06 adds:**
- **Agency.** The LLM picks the retrieval strategy (function calling) instead of you hard-coding "top-10 by similarity". It reuses the same collection, and the author metadata from `cli.py:132-138` suddenly matters, because it is what `where={"author": …}` filters on.
- **Frameworks that own the loop:**
  - Google ADK: Runner/Session/State/Events, workflow agents, MCP, custom agents, a FastAPI wrapper.
  - OpenAI Agents SDK: `Runner.run`, `function_tool`, `as_tool`, sessions, structured outputs.
  - Microsoft Agent Framework: `@tool`, `function_invocation_kwargs`, `max_iterations`.
- **Harness ideas:** approval gates, Python-owned arithmetic, validated outputs, receipts.

**How the llm-rag agent evolved** (`git log -- agent_tools.py cli.py`):

| Date | Commit | Change |
|---|---|---|
| 2024-09-25 | `64aa948` | Agent tools added |
| 2025-10-01 | `59a0f80` | Migrated from the `vertexai` SDK to `google-genai` + uv. Diff vs the legacy `pipenv` branch: `vertexai.generative_models.FunctionDeclaration` → `google.genai.types.FunctionDeclaration`; `ToolConfig.FunctionCallingConfig.Mode.ANY` → `types.FunctionCallingConfig(mode="any")`; `gemini-1.5-flash-002` → `gemini-2.0-flash-001`. The `GenerativeModel(..., system_instruction=[SYSTEM_INSTRUCTION])` wrapper was dropped (E3). |
| 2026-09-16 | `51a2865` | "Model fix": `gemini-2.0-flash-001` → `gemini-3.1-flash-lite` |
| 2026-09-17 | `74dba4a` | Embedding model `text-embedding-004` → `gemini-embedding-001` |
| 2026-09-22 | `85bba32` / `2079962` | New Pavlos book + `out.txt` |

`git diff --stat origin/pipenv origin/main` touches 14 files (+3703/−3781), mostly the Pipfile → uv swap.

**What comes next:**
- **L07 (Agents II):** the `dlops-io/agent-harness` repo plus an "Agent Harness on Google Colab" notebook (`tutorials_demo.md:102-108`), repo last commit 2026-09-28. Docker, Python 3.13, OpenAI. Six "acts" turn this lecture's harness ideas into the main topic: recap of agent + tools, context engineering, a controlled workflow, planning/memory/compaction/review, skills, agent systems, and evaluation with traces (agent-harness `README.md`, table at the top).
- **L18 (APIs + Frontend):** `cheese-app-v2` ships a byte-identical copy of this lecture's `agent_tools.py` at `src/vector-db/agent_tools.py`, plus `src/api-service/api/routers/llm_agent_chat.py`. The agent you ran from a CLI becomes an API endpoint behind the React app.

---

## 8. Exercises

**Exercise 1 (hands-on, llm-rag): steer the tool choice.**
Change the question at `cli.py:435` to `"What does George E. Newell say about rennet?"`. Before running, predict the function name and `author` argument. Then change it to `"Which books mention goat cheese?"` and predict again.
- *Answer:* For Newell, `get_book_by_author` with `author='George E. Newell'` (an enum value, `agent_tools.py:22`) and a `search_content` about rennet. For goat cheese no author is named, so expect `get_book_by_search_content` (`agent_tools.py:52-66`). Because of `mode="any"` it *must* call one of them. Run with `python cli.py --agent --chunk_type char-split`. The `/app` bind mount means your edit is live inside the container without a rebuild.

**Exercise 2 (hands-on): what if the model may refuse tools?**
Delete the `tool_config=…` block (`cli.py:447-451`) and ask `"Hi! Who are you?"`. Predict the output.
- *Answer:* With AUTO mode the model will most likely answer in text with no function call. `function_calls` is then empty, `execute_function_calls` returns `[]`, and the code prints `Function calls did not result in any responses...` (`cli.py:461-462`). The greeting text was in the first response, which is printed only as the raw object at line 454. Lesson: forcing (`ANY`) guarantees retrieval, but removes the model's option to skip it.

**Exercise 3 (debugging, ADK): "Invalid agent name".**
`uv run adk web` shows the folders, but clicking `1-baseline` gives `Invalid agent name: '1-baseline'. Agent names must be valid Python identifiers …`. Why, and give two fixes.
- *Answer:* No lockfile, so `google-adk>=1.8.0` resolved to 2.x. Since 1.28.0 the loader validates names with `^[a-zA-Z0-9_]+$` (`cli/utils/agent_loader.py:250` in 2.11.0), and the hyphen fails. Fix A: `uv add "google-adk>=1.8.0,<1.28"` then `uv sync` (→ 1.27.5). Fix B: symlink the folders under valid names into an `agents/` dir and run `uv run adk web agents` (G1).

**Exercise 4 (debugging): the port that won't let go.**
You just finished Part B, exited the container, and now `uv run adk web` fails with `Address already in use`. Explain using two specific file lines.
- *Answer:* `docker-shell.sh:12` used `docker compose run --rm`, which also started `chromadb` because of `depends_on` (`docker-compose.yml:16-17`). `--rm` removes only the one-off CLI container, so `llm-rag-chromadb` keeps publishing `8000:8000` (`docker-compose.yml:21-22`), the same port `adk web` uses by default. Run `docker compose down` in `llm-rag/`, or `uv run adk web --port 8080`.

**Exercise 5 (debugging, conceptual): the router that always asks for clarification.**
Suppose `conditional_agent.py` routes "What is Python?" to `ClarificationHandler`, and the log line shows `Classification: Simple` (capital S). Why? Fix it.
- *Answer:* `output_key` stores the classifier's raw final text (google-adk 1.19.0 `agents/llm_agent.py:802-816`), and the router compares exactly: `complexity == "simple"` (`conditional_agent.py:89`). `"Simple"` (or `"simple\n"`) matches neither branch and falls to `else` (lines 99-102). Fix:
  ```python
  complexity = ctx.session.state.get("query_complexity", "simple").strip().lower()
  ```
  A sturdier fix is a structured output: `output_schema=` with an enum field.

**Exercise 6 (conceptual): why a receipt?**
The Newsletter orchestrator's final message says "Newsletter sent successfully!", but `generate_newsletter` raises `RuntimeError: No successful tool receipt`. Is the harness being too strict?
- *Answer:* No. The model's prose is not evidence. Success requires `context.receipt`, which only `save_newsletter` sets after `validate_newsletter` and rendering succeed (cell 16; cell 18, lines 118-124), plus an existing file. The model might have skipped `send_email`, or its call might have returned `{"status": "error", …}`. That status is a valid tool result the model could ignore while still claiming success. This is the same principle as the Travel Planner's "authoritative presentation" (cell 18, lines 122-131).

**Exercise 7 (hands-on, ADK): make `2-litellm` really use LiteLLM.**
Make the module answer with an OpenAI model.
- *Answer (reasoned, not run):* put `OPENAI_API_KEY=sk-…` in the root `.env` (`litellm_config.py:28` reads that name, not `AWS_OPENAI_API_KEY`). Replace `2-litellm/agent.py:25-29` with:
  ```python
  from google.adk.models.lite_llm import LiteLlm

  root_agent = LlmAgent(
      model=LiteLlm(model="openai/gpt-4o-mini"),
      name="assistant",
      instruction="You are a helpful AI assistant."
  )
  ```
  `LiteLlm` exists in google-adk 1.x (`models/lite_llm.py`), and `litellm` is already in the root `pyproject.toml:13`. A bare `"gpt-4"` fails because no registered pattern matches it: 1.19.0 registers only Gemini/Gemma/Apigee, and 1.27.5 adds LiteLLM only for provider prefixes like `openai/`. If `gpt-4o-mini` has been retired by the time you run this, use a current OpenAI model such as `openai/gpt-5.6-luna` (the notebooks' model).

**Exercise 8 (hands-on, stretch): turn llm-rag's pipeline into a real loop.**
Replace `cli.py:439-478` with a loop that keeps executing tool calls until the model answers in text, with at most 5 steps. Keep `mode="any"` off so the model can stop.
- *Answer (reasoned, not run):*
  ```python
      contents = [user_prompt_content]
      config = types.GenerateContentConfig(temperature=0, tools=[agent_tools.cheese_expert_tool])
      for step in range(5):
          response = llm_client.models.generate_content(
              model=GENERATIVE_MODEL, contents=contents, config=config)
          model_turn = response.candidates[0].content
          calls = [p.function_call for p in model_turn.parts if p.function_call]
          if not calls:                      # final answer: no more tool requests
              print("Answer:", response.text)
              break
          contents.append(model_turn)        # keep the model's turn verbatim (thought signatures)
          contents.append(Content(role="user", parts=agent_tools.execute_function_calls(
              calls, collection, embed_func=generate_query_embedding)))
      else:
          print("Gave up after 5 steps")
  ```
  Compare with ADK's `while True` (Excerpt 6): this is the same idea, plus a turn cap like `max_turns`. Try a two-part question, e.g. "Compare what Newell and Curtis say about curd temperature", and count the steps.

---

## 9. Errata and open questions

**Errors and inconsistencies (with evidence)**

- **E1. Cheese Quiz Step 2 swaps roles.** Cell 39, lines 18-21 send `{"role": "user", "content": system_prompt}` and `{"role": "system", "content": user_prompt}`. The "prompt engineering" comparison therefore tests a malformed conversation. Step 3 onward uses the correct order (cell 40).
- **E2. `out.txt` and the README diagram come from the old Pavlos book.** The recorded retrieval mentions "cultural artifact", "transhumance", "Monastic orders", "within two milkings" and "Soča Valley". Every one of these is absent from the current `input-datasets/books/Tolminc Cheese.txt`, and all are present in `85bba32^`. Your run will differ.
- **E3. `SYSTEM_INSTRUCTION` is dead code.** It is defined at `llm-rag/cli.py:40-58`, but neither `chat()` (`cli.py:394-396`) nor `agent()` passes it, so "answer only from chunks" is never enforced. The legacy `pipenv` branch did use it (`GenerativeModel(GENERATIVE_MODEL, system_instruction=[SYSTEM_INSTRUCTION])`, `origin/pipenv:cli.py:62-65`, used by `chat()` and `agent()`). The `59a0f80` migration to google-genai dropped it.
- **E4. Two of eleven books are unreachable by author.** "Milk Industry Foundation" (`cli.py:62`) and "Woman's Institute…" (`cli.py:70`) are missing from the enum (`agent_tools.py:19-29`). In addition, `filename.split(".")[0]` (`cli.py:178`) turns "Womans Institute Library of Cookery. Volume 2_ …" into "Womans Institute Library of Cookery", so that book's chunks get no `author`/`year` metadata (`cli.py:135-138`).
- **E5. README says "Displays the LLM's response"** (README.md:266). The code prints the entire SDK response object (`cli.py:478`; see `out.txt:98-137`), so the answer is buried in metadata.
- **E6. ADK repo dependency drift.**
  - No lockfile (`.gitignore:34`), and every pin is open-ended (`pyproject.toml:9-20`). Today this yields google-adk 2.11.0, which rejects all six module folder names (G1).
  - The `pyproject.toml:2` comment "google-adk[all] extra doesn't exist" was true for 1.x (1.19.0 METADATA has no `all` extra) but is false for 2.x, while the module `pyproject.toml`s still request `google-adk[all]`.
  - Module `pyproject.toml`s point hatch at a non-existent `src/adk_tutorial_baseline` (e.g. `5-custom-agent/pyproject.toml:16-17`). A toy replica builds anyway (an empty package) with a uv deprecation warning for `tool.uv.dev-dependencies`.
- **E7. Retired model defaults.** `gemini-2.0-flash` is hard-coded as the fallback in 8 places (e.g. `1-baseline/agent.py:12`, `2-litellm/litellm_config.py:62`), set in 4 `.env.example` files (e.g. `5-custom-agent/.env.example:5`) and suggested in 3 more as comments (`1-baseline/.env.example:16`, `3-mcp-tools/.env.example:14`, `2-litellm/.env.example:22` as `FALLBACK_MODEL`). Google's deprecation page lists its shutdown as 2026-06-01. `6-rag/1-vertex-rag-engine/agent.py:47` hard-codes `gemini-2.5-flash` and ignores `GEMINI_MODEL`.
- **E8. QUICKSTART.md is stale throughout.**
  - `cd google-adk-tutorial` (`QUICKSTART.md:10`; also `README.md:78`).
  - File paths passed to `adk web` (`QUICKSTART.md:24, 32, 42, 57`).
  - A `3-mcp-connections` folder that never existed in this repo (`QUICKSTART.md:42, 84`); the module has been `3-mcp-tools` since the initial commit.
  - Scripts that never existed (`QUICKSTART.md:70-72, 79, 85, 91-92`).
  - Wrong descriptions: Tutorial 2 "auto-selected based on your API keys" with `AWS_OPENAI_API_KEY` (`QUICKSTART.md:34-36`; the code hard-codes `model="gpt-4"`), and Tutorial 5 as a "Custom Story Agent" with critique/revision/tone analysis (`QUICKSTART.md:55-61`; `5-custom-agent/agent.py` only prefixes 🤖).
  - `2-litellm/README.md:238` also links to `../3-mcp-connections/`.
- **E9. `uv run adk` without `web`** at `2-litellm/README.md:74`, `3-mcp-tools/README.md:85`, `5-custom-agent/README.md:120`.
- **E10. 2-litellm cannot work as written.**
  - `model="gpt-4"` (`2-litellm/agent.py:26`) has no provider prefix, so ADK 1.x does not route it to LiteLLM.
  - `AWS_OPENAI_API_KEY` (`2-litellm/.env.example:5`) is unused.
  - "Option 2: Test LiteLLM Configuration" (`2-litellm/README.md:81-88`, also `QUICKSTART.md:78`) runs `litellm_config.py` as a script, but the file has no `__main__` block, so it never calls `configure_litellm()` and prints nothing (G19).
  - "ADK supports LiteLLM model names natively" (`2-litellm/README.md:195`) is inaccurate. ADK 2.x does resolve bare `gpt-*` names, but through a native OpenAI class (2.11 `models/__init__.py:80-83`), not LiteLLM.
- **E11. 5-custom-agent README uses attributes that do not exist.** `ctx.history` (`5-custom-agent/README.md:80, 288`) and `ctx.session_id` (`5-custom-agent/README.md:81`) are not `InvocationContext` attributes in google-adk 1.19 (fields at `agents/invocation_context.py:144-206`; there is a `user_id` property at line 324). Use `ctx.session.events`, `ctx.user_content` and `ctx.session.id`.
- **E12. "Memory" vs "state."** `llm-agent-google-adk/README.md:140` defines "Memory" as per-session structured state and says "separate sessions do not share memory". In ADK, per-session data is *state*. *Memory* is the separate, cross-session `memory_service` (`invocation_context.py:146`). The Cheese Quiz's own definitions (cells 41-42) use the standard meaning.
- **E13. 6-rag/2-custom-chromadb-rag details.**
  - v1 heartbeat (`6-rag/2-custom-chromadb-rag/docker-compose.yml:16`, `6-rag/2-custom-chromadb-rag/README.md:33`) against a v2-era server.
  - The collection is created with the default distance (L2) (`6-rag/2-custom-chromadb-rag/ingest_documents.py:130-133`), yet results are reported as `"similarity": 1 - distance` (`6-rag/2-custom-chromadb-rag/agent_tools.py:151`). That is not a cosine similarity and can be negative.
  - `6-rag/README.md:133` says "ingest documents (assumes RAG is already populated)", which contradicts the command it precedes.
- **E14. Notebook nits.**
  - All three notebook banners link to `2025-AC215` while saying "Fall 2026" (cell 0 of each).
  - Cheese Quiz cell 57's comment says port 8000 but the code uses 8001. The saved output of that cell (from an older version) prints 8000.
  - Cheese Quiz cell 49's saved output shows `I am a tool` lines that the current tool code no longer prints.
  - Cheese Quiz cell 70 asks the orchestrator to "update context.fact_cache[topic]", but no context object is passed to `Runner.run` (cell 71) and no tool can write it.
  - The Newsletter's cell 23 markdown ("six tools… clarification, options, a checked itinerary…") is copied from the Travel Planner. The orchestrator has three tools (cell 25, lines 12-16).
  - The Newsletter's `USERS` list contains real staff email addresses (cell 16). Nothing is sent, but replace them before sharing outputs.
  - The Newsletter's saved Run Demo output (cell 27) shows four readers, but two of them (Rashmi, Chris) are now commented out in cell 16 (lines 10-11). The saved output therefore does not match what the current code produces.
- **E15. The harness does not enforce "plain text, no URLs".** `EDITOR_INSTRUCTIONS` (cell 22) forbids embedded URLs, but `validate_newsletter` (cell 18) doesn't check, and the saved Summerville preview contains `Promotion URL: https://shop.lowesfoods.com/...` inside an offer summary. This is a good example of a soft (prompt) rule vs a hard (code) rule.

**Open questions (could not determine from the sources)**

- What the Ed lesson itself contains: slides, the recorded lecture, any announcements about version pins. Ed was not accessible when these sources were checked.
- `quiz-schema.json` and `quiz-ui.html` are downloaded from Google Drive at run time (Cheese Quiz cell 13) and are not in any repo, so the schema the Ricotta agent and orchestrator must satisfy could not be read.
- What backend the hosted "Cheese Agent Tool" (https://ac215-llm-rag.dlops.io/agent) calls, and whether it needs your local ChromaDB. The page loads, but its client bundle reveals no endpoint.
- Whether `gemini-3.1-flash-lite` is enabled for every student project in location `global`. It worked for the course staff on 2026-09-22 (`out.txt:34`). Availability can vary by project and organisation policy.
- Whether the course intends students to run the ADK repo with a pinned ADK version. Neither README mentions version constraints, and the repo predates ADK 1.28/2.x.
- OpenAI model lifecycles: `gpt-5.6-luna` (Travel Planner, Newsletter) is listed by OpenAI as a recommended replacement model, so it is current. The `gpt-4o-2024-05-13` snapshot shuts down 2026-10-23, but the deprecations page checked for this guide did not list the `gpt-4o` alias used by the Cheese Quiz. Re-check if Cheese Quiz calls start failing after that date.

---

## Links

- README sections, `dlops-io/llm-rag` (pinned commit): [Agents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#agents) · from L05, needed here: [Prerequisites](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#prerequisites) · [Run LLM RAG Container](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#run-llm-rag-container) · [Chunk Documents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#chunk-documents) · [Generate Embeddings](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#generate-embeddings) · [Load Embeddings into Vector Database](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#load-embeddings-into-vector-database) · latest README on `main` as the course site links it: [#agents](https://github.com/dlops-io/llm-rag?tab=readme-ov-file#agents)
- README sections, `dlops-io/llm-agent-google-adk` (pinned commit): [Prerequisites](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#prerequisites) · [Getting Started](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#getting-started) · [Running Agents](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#running-agents) · [Key Concepts: Session, Memory, Runner](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#key-concepts-session-memory-runner) · [Sequential Agent Data Flow](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#sequential-agent-data-flow)
- Module READMEs (pinned commit): [1-baseline](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/1-baseline/README.md) · [2-litellm](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/2-litellm/README.md) · [3-mcp-tools](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/3-mcp-tools/README.md) · [4-production-ready](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/4-production-ready/README.md) · [5-custom-agent](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/5-custom-agent/README.md) · [6-rag](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/6-rag/README.md) · `QUICKSTART.md` is stale, skip it (G9, E8)
- Ed lesson: [L06 · LLM: Agents I](https://edstem.org/us/courses/97373/lessons/166030/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab: [Cheese Quiz](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) · [Travel Planner](https://colab.research.google.com/drive/1I_jJEHJsVkGxNoSC1c4wEoVF2QL6vCVY?usp=sharing) · [Cheese Newsletter · Harness](https://colab.research.google.com/drive/1nnHrJ4Si3tpgUQl6HqlcwxKymV1-ecPv?usp=sharing)
- Hosted demo (optional, Chrome): [Cheese Agent Tool](https://ac215-llm-rag.dlops.io/agent)
- Previous lecture: [L05 · Introduction to RAG](L05-rag.md) (the `llm-rag` container, the chunk → embed → load pipeline and the `char-split-collection` this agent queries)
- Next lecture: [L07 · LLM: Agents II](L07-agents-2-harness.md) (the `agent-harness` repo: this lecture's harness ideas become the main topic)
- Referenced in §7: [L18 · APIs + Frontend](L18-apis-frontend.md) (`cheese-app-v2` serves this agent behind an API)
