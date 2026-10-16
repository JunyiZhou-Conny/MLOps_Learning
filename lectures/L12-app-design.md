# L12 lecture slides — App Design

Source: deck `L12_app_design` (58 slides), "Lecture 12: App Design", AC215/E115, Pavlos Protopapas and Shivas Jayaram. These are the instructor's lecture slides (PDF), provided by the student for study. The PDFs are not in this repository, and slide numbers are PDF page numbers. Everything below is a summary in our own words. Quotes are limited to short titles, labels, names and code. L12 has no tutorial repository (`course/lectures.yaml`: `tutorials: []`). Where this digest compares the lecture's naming with "the tutorials", it means the cheese-app repositories of later lectures, as recorded in our study guides (L10, L15, L18, L20, L22, L23).

## Outline

- Slide 1 · Title: "Lecture 12: App Design".
- Slide 2 · Agenda with seven sections. The same agenda comes back as a section divider, with the current section in bold, on slides 3, 7, 13, 15, 19, 34 and 54.
- Slides 3–6 · **1. Recap**. The Cheese App idea: identify a cheese from a photo, then chat about it (4). The five ingredients of building an app (5). The course's development-to-deployment picture (6).
- Slides 7–12 · **2. Motivation**. What has to happen before you build the app (8). Reviews of the project's problem definition (9), proposed solution (10), scope from POC through Prototype to MVP (11), and where the project stands on the timeline (12).
- Slides 13–14 · **3. App Design**. What an AI app has that a traditional app lacks, and the three design artefacts (14).
- Slides 15–18 · **4. Screenflow & Wireframes**. Start on a whiteboard or paper (16). The chat screenflow (17). Static pages: About Us, Podcasts, Newsletters (18).
- Slides 19–33 · **5. Solution Architecture**. Definition (20). The three layers Process, Execution and State with examples (21). A role-by-layer grid for an AI app (22), filled in for the cheese app (23). A nine-step build-up of the cheese app's solution diagram (24–32). Summary (33).
- Slides 34–53 · **6. Technical Architecture**. Definition (35). An eleven-step build-up on GCP (36–46). The finished diagram (47). The "App is ready!" joke (48–49). Summaries of the blocks on GCP (50), AWS (51) and Azure (52). Comparison table of the three clouds (53).
- Slides 54–56 · **7. Setup & Code Organization**. Principles: microservices, tests and secrets (55). The repository folder layout (56).
- Slide 57 · In-class tutorial: "Building Solution Architecture". Project groups draft their own Process/Execution/State slide in a shared Google Slides deck.
- Slide 58 · "THANK YOU" closing slide, with a theatre-curtain cartoon.

## Key ideas

1. **Design before you build.** Once the ML pipeline exists, the next job is an app that uses its components. Expose the model and Python functions as APIs, work out which user needs those APIs can meet, and design the user interface. The slide ends with the question of how to do this. (Slide 8)
2. **An AI app has more moving parts than a traditional app.** A traditional app has code and data. An AI app adds models that perform tasks, and an LLM app adds prompts and schemas. That is why the lecture uses a structured design method. (Slide 14)
3. **Three design artefacts.** The design consists of Screenflow & Wireframes, a Solution Architecture and a Technical Architecture, in that order. The lecture is organised around these three. (Slides 14, 15, 19, 34)
4. **Screenflow first, on paper.** Start by brainstorming on a whiteboard or paper. Then draw wireframes that show the core interaction screen by screen: an empty chat, then a photo with "What type of cheese is this?", then the answer "Brie". Add the static pages reachable from the menu (About Us, Podcasts, Newsletters). (Slides 16–18)
5. **The solution architecture names the building blocks.** Start from the problem statement and ask how the app addresses it. Then identify three things: the Process (what people do), the Execution blocks (the code that fulfils the process) and the State (what must persist over the app's life cycle). (Slides 20–21)
6. **The role-by-layer grid.** For an AI app, the people are Developers, Users and Data Scientists. The code is Frontend, Backend and AI/ML Tasks. The state is Source Control, Database and Data/Models. The cheese app fills each band with concrete tasks: scraping images, EDA, training CNN/LLM models, users uploading images and chatting, applying the training-time preprocessing at prediction time, RAG for Q/A, and saving images, weights, text chunks and embeddings. (Slides 22–23)
7. **Every arrow says what kind of interaction it is.** In the cheese app's solution diagram there are three human activities (Develop App, AI/ML Tasks, Upload picture and view predictions). They reach code in three ways: by human interaction (notebooks, the frontend), by CLI and automation (the ML pipeline), and by a long link straight to source control (development). Code reaches LLMs over HTTP/HTTPS and reaches state through protocol-specific connections. (Slides 24–32)
8. **The backend has three parts.** An API server exposes Python functions to the frontend. An AI Engine holds the agents, harness, tools, skills and memory. A Vector DB serves retrieval. The frontend is a single-page app for uploading and chatting. (Slides 32–33)
9. **A technical architecture is the system's blueprint.** It gives a high-level view from development to deployment. It shows which components or containers talk to which, so the team sees the big picture and new members can onboard. (Slide 35)
10. **Build the technical diagram from the people outward.** Developers and data scientists work through an IDE/CLI and a browser, and all their development is containerized. Data scientists also use Colab or JupyterHub notebooks and access LLMs. Users only have a browser, where they upload images, see predictions and chat. (Slides 36–38)
11. **On GCP the blueprint has these parts.** GitHub and Colab sit outside the GCP boundary. Inside GCP are a GCS bucket for data and models, Google Artifact Registry for every container image, the Agent Platform running the ML pipeline steps serverlessly next to Gemini, a single compute instance or Kubernetes cluster that runs the app's containers, and a GCE persistent volume. (Slides 39–47, 50)
12. **Every link carries a protocol and a port.** Developer tools use HTTPS 443 and users reach the app on "HTTP/HTTPS 80". Inside the app host, NGINX sits in front of the Cheese App container (3000) and the API Service container (9000). The API Service talks to the AI Engine (9001), the AI Engine to the Vector DB (8000), and the host reaches the persistent disk over NFS. (Slides 41–47)
13. **Images flow from laptop to registry to cloud.** Developers push the images from their containers to Artifact Registry. Both the serverless ML tasks and the app host pull from there over HTTPS 443. (Slides 44–47)
14. **Persist what must outlive an image update.** The persistent volume holds every file that has to survive when the container images are replaced. (Slides 46, 50)
15. **One machine first, a cluster to scale.** A single compute instance can host one copy of every container. A Kubernetes cluster (GKE) is what scales the app. (Slides 43, 50)
16. **The building blocks are cloud-agnostic.** The same seven roles exist on GCP, AWS and Azure: container registry, object storage, AI/ML platform, LLMs, persistent storage, virtual machines and a Kubernetes service. Only the product names change. (Slides 50–53)
17. **A diagram is not an app.** After the full blueprint the slide says "App is ready!", and the next slide adds that it is not: we still need to build it. (Slides 48–49)
18. **Organise the code as microservices.** Think in microservices rather than a monolith, and ask how fine-grained to go. Map each component from the design to a service. Keep the tests inside the container. Keep secrets outside the Git repository: one GitHub root with a folder per service under `src/`, and a `secrets/` folder beside the repository, not inside it. (Slides 55–56)
19. **The project's arc.** Scope grows from POC (scrape data, baseline models, check ideas with an LLM) to Prototype (screen mock-ups, one model behind FastAPI, built with Streamlit) to MVP (the full app with API servers for the model and the LLMs, plus newsletters and podcasts, built with web frameworks). App design runs through the POC and Prototype phases, before the cheese app itself is built in the MVP phase. (Slides 11–12)
20. **Why the course builds this way.** The recap picture shows several people on Mac and Windows working in different Python environments across scripts, Colab and an IDE. The deployed server runs Linux and must keep the loop running from app to new data to retraining to an updated app. (Slide 6)

## Diagrams

**Slide 4 · Cheese App screen (illustration).** A phone-style screen titled "Cheese App" shows a sketched wedge and wheel of cheese, captioned "Type: Brie (93.54%)". This sets the scene and teaches no mechanism.

**Slide 6 · Development → Deployment (recap).**
- *Layout:* A red "Development" brace spans three stages from left to right, joined by coloured arrows (purple, orange, green):
  1. A grid of scraped cheese photos with a "Python Script" box.
  2. A notebook table screenshot with a "Colab" box.
  3. "Rest API" and "Best Model" boxes beside a sketch of the Cheese App screen, above an "IDE / Code Editor" box.
- *Environment notes under each stage:*
  - Stage 1: Python pipenv, Chromium installed separately on Mac and Windows, OS Mac/Windows.
  - Stage 2: the Colab-provided Python on Linux.
  - Stage 3: pipenv on Mac/Windows.
- *People:* Person icons appear under each stage, captioned "Multiple developers, Using Mac and Windows OS".
- *Deployment:* A green "Deployment" brace, labelled "Server" (pipenv, Linux), holds three items stacked from top to bottom: the live Cheese App window with a cheese photo and its prediction, a red "Model Training" box, and the image grid with a "Python Script" box.
- *The loop:* Grey arrows run from the app down to Model Training and to the script, a purple arrow runs from the script up to Model Training, and a red arrow runs from Model Training back up to the app.
- *Purpose:* To show the problem: many people, many environments, and a deployment that is a continuous retraining loop rather than a one-off.

**Slide 11 · Project scope.**
- *Layout:* Three chevrons run left to right: "Proof Of Concept (POC)" in orange, "Prototype" in blue and "Minimum Viable Product (MVP)" in green, each over a list of goals.
- *Annotations:* The Prototype and MVP lists sit in red dashed boxes. A curved arrow runs from the Prototype box to the label "Using Streamlit", and another from the MVP box to "Using Web Frameworks".
- *Purpose:* Scope by phase, plus the tooling that goes with each phase.

**Slide 12 · Project timeline.**
- *Layout:* A long light-blue arrow carries the phases POC, Prototype and MVP, separated by dashed vertical lines. Staggered bars sit underneath, like a Gantt chart:
  - "Data Collection" (early POC)
  - "Setup Experiment Tracking" (POC)
  - "Build Baseline Models" (across the POC/Prototype line)
  - "Build Better Models" and "ML Workflow" (Prototype)
  - "Build Cheese App" (MVP)
  - "Deployment, Scaling & Automation" (from late Prototype to the end of MVP)
- *Highlight:* A red dashed box marks the top bar, "Design Cheese App", which spans POC and Prototype.
- *Purpose:* To show where this lecture sits: design happens early and overlaps model work.

**Slide 17 · Screenflow (three wireframes, red arrows between them).**
1. A "Cheese App" header with a hamburger menu above a chat input that reads "How can I help you?", with a camera icon and a send arrow.
2. The user's bubble on the right, with a cheese photo, a user avatar and "What type of cheese is this?", above the input.
3. The same bubble, plus a reply bubble on the left with a smiley avatar and "Brie", and the input at the bottom.

Purpose: to show how one interaction (photo in, label out, in a chat) moves across screens.

**Slide 18 · Static page wireframes.** Three side-by-side screens, all with the same "Cheese App" header and hamburger menu, and no arrows between them:
- "About Us": a welcome paragraph about Formaggio.me.
- "Podcasts": an intro, then an episode card "Episode 1 Halloumi [EN]" with a play button.
- "Newsletters": an intro, then an article card "Exploring Alpine Cheeses".

Purpose: the secondary pages, reached from the menu.

**Slide 21 · The three layers.**
- *Layout:* Three horizontal bands separated by rules, labelled on the left "Process (People)" in red, "Execution (Code)" in blue and "State (Source, Data, Models)" in green. Each band has a dotted box of examples:
  - Process: user actions, admin tasks, data scientist tasks, developer tasks.
  - Execution: frontend apps, backend services, data science notebooks, ML tasks, LLM APIs, agents & tools.
  - State: source control, artifact registry, data store, model registry, knowledge base.
- *Purpose:* The vocabulary for sorting any component into a layer.

**Slide 22 · Grid for an "AI App".**
- *Layout:* A 3×3 grid of empty coloured cells under the three band labels:

  | Band | Column 1 | Column 2 | Column 3 |
  |---|---|---|---|
  | Process (pink) | Developers | Users | Data Scientists |
  | Execution (blue) | Frontend | Backend | AI / ML Tasks |
  | State (green) | Source Control | Database | Data / Models |

- *Purpose:* A template to fill in.

**Slide 23 · Grid filled in for the cheese app.** Three yellow sticky notes lie over the grid:
- *Red, over the Process cells:* scrape images, EDA, data processing, train CNN/LLM models, build the frontend, and the users' upload, chat and newsletter/podcast viewing.
- *Blue, over Backend and AI/ML:* apply the same preprocessing to an incoming image, predict with the best model, call an LLM for chat, RAG for Q/A, and generate and show newsletters and podcasts.
- *Green, over State:* store images centrally, model weights, text chunks, embeddings and preprocessing information, plus a source repository for collaboration.

**Slides 24–32 · Building the cheese app's solution architecture (one diagram, built up step by step).**
- *Layout:* Three stacked rounded panels: a pink "Process" panel on top, a dotted white "Execution" panel in the middle and a grey "State" panel at the bottom.
- *Build-up, slide by slide:*
  - 24: The three empty panels.
  - 25: A people icon and three white boxes appear in Process: "Develop App", "AI/ML Tasks", "Upload picture, chat, etc.".
  - 26: The third box becomes "Upload picture, view predictions". State gets four icons: "Source Control" (a `</>` glyph), "Artifact Registry" (cloud), "Data Store" (cloud) and "Knowledge Base" (database cylinder).
  - 27: A tall double arrow runs from Develop App straight through Execution down to Source Control.
  - 28: A down arrow labelled "(Human Interactions)" runs from AI/ML Tasks into a yellow "Interactive Notebooks" group that holds "Notebooks". A double arrow joins Notebooks to State, and another double arrow, labelled "(Protocol specific)", joins the whole Execution panel to State.
  - 29: A second down arrow from AI/ML Tasks, labelled "(CLI + Automation)", leads into a blue "ML Pipeline" group with a 2×2 of boxes: Data Collector, Data Processor, Model Training, Model Deploy.
  - 30: A green "LLMs" group with "Frontier LLMs" and "Fine tuned LLMs" appears. Double arrows labelled "(HTTP / HTTPS)" join it to Notebooks and to the ML Pipeline.
  - 31: A down arrow labelled "(Human Interactions)" runs from "Upload picture, view predictions" into a teal "Frontend" group holding "Cheese App".
  - 32: A purple "Backend" group holds "API", "AI Engine" and "Vector DB". A double arrow labelled "(HTTP / HTTPS)" joins Frontend and Backend, and a horizontal double arrow labelled "(HTTPS)" joins LLMs and Backend.
- *Purpose:* To show how each human activity enters the system, which code serves it, and how code reaches models and stored state. The arrow labels classify the interfaces.

**Slides 36–47 · Building the technical architecture on GCP (one diagram, built up step by step).**
- *Layout:* Two pink bands across the top: "Developers / Data Scientists" on the left (wide) and "Users" on the right.
- *Build-up, slide by slide:*
  - 36: The two empty bands.
  - 37: The left band gets an "IDE/ CLI" box with "Containers" (three small green dotted squares) and a "Browser" box. The right band gets a "Browser".
  - 38: Three text columns below the bands list what Developers, Data Scientists and Users do (Key idea 10).
  - 39: Components hang below the bands:
    - A one-way down arrow from the containers to "Source Control" holding "GitHub" (a grey dotted box).
    - A double arrow from the developers' Browser to "Colab" (yellow, a stack of "Notebooks").
    - A second double arrow from the developer band to "Agent Platform", a blue panel with a vertical chain Task 1 → Task 2 → Task 3 → Task 4 and a "Gemini" box under it.
    - A double arrow from the users' Browser to "App", a teal panel with a small chat wireframe.
  - 40: A dotted "GCP" boundary is drawn. It is stepped: it covers Agent Platform, App and the whole lower part of the slide, but leaves out Colab and GitHub.
  - 41: Labels appear on the top arrows: "HTTPS 443" on the two developer arrows and "HTTP/HTTPS 80" on the user arrow.
  - 42: A grey "GCS Bucket" (cloud icon, "Data & Models") appears inside GCP below Colab. It has double arrows, all "HTTPS 443", to Notebooks and to Agent Platform, and a short "HTTPS 443" double arrow joins Notebooks and Agent Platform.
  - 43: The App panel becomes an empty teal "Single Compute Instance/ Kubernetes Cluster", and the Agent Platform's tasks are cleared, leaving only Gemini.
  - 44: A purple "Google Artifact Registry" appears at the bottom left with a list: "Data Collector Image", "Data Processor Image", a vertical ellipsis, "API Service Image", "Cheese App Image". A second one-way down arrow runs from the developers' containers into it.
  - 45: Agent Platform's chain becomes Data Collector → Data Processor → Model Training → Model Deploy, with Gemini below. An elbow arrow labelled "HTTPS 443" runs from the registry into Agent Platform.
  - 46: A grey "GCE Persistent Volume" ("Persistent Disk", cylinder icon) appears at the bottom right. A double arrow labelled "NFS" joins it to the compute/cluster panel.
  - 47 (titled "Technical Architecture"): The cluster panel fills with five green containers:
    - "NGINX Container" at the top.
    - "API Service Container" and "Cheese App Container" below it.
    - "AI Engine Container" and "Vector DB Container" at the bottom.

    The internal lines carry port labels. API Service to NGINX: "HTTP 9000". Cheese App to NGINX: "HTTP 3000". AI Engine to API Service: "HTTP 9001". Vector DB to AI Engine: "HTTP 8000". The arrowheads point at NGINX, API Service and AI Engine, and each label names the listening port of the container at the tail. Three outer links are added, all "HTTPS 443": a double arrow from Agent Platform to the cluster, a long double arrow from the GCS bucket to the cluster, and the registry arrow, which now branches to both Agent Platform and the cluster.
- *Purpose:* The full blueprint. Who connects to what, over which protocol and port; which parts are managed or serverless (Agent Platform, GCS, Artifact Registry) and which are your own containers; and where state lives.
- *Redrawing tip:* Draw the request path as Browser → NGINX → Cheese App (3000) and NGINX → API Service (9000) → AI Engine (9001) → Vector DB (8000). Note that the slide's arrowheads point the other way.

**Slides 48–49 · "App is ready!"** A large red smiley with "App is ready!" covers the cluster area of the finished diagram (48). Slide 49 adds, in red, "Well not really, we need to build it". Purpose: the punchline separating design from implementation.

**Slide 53 · Building blocks across clouds.** A 7×3 table that maps each role to its product on GCP, AWS and Azure (listed under Terms). It is not a mechanism diagram, but a scene author can draw it as one block diagram whose labels swap between three clouds.

**Slide 56 · Repository layout.**
- *Layout:* A monospace folder tree in a dotted box:
  - `/application-root-folder` is at the top, with a blue arrow from a callout "Github root".
  - `/src` (shown in red) sits below it and holds ten service folders.
  - `/secrets`, holding `data-service.json`, sits at the same indentation as the root folder, so it is a sibling of the repository. A red arrow points to it from a callout "Secrets (outside git folder)".
- *Purpose:* One repository with one folder per microservice, and keys kept beside the repository.

## Terms the lecture uses

| Term (as on the slides) | Slides | Meaning, and how it compares with the tutorials |
|---|---|---|
| App Design | 1, 14 | The umbrella for three artefacts: Screenflow & Wireframes, Solution Architecture, Technical Architecture. |
| AI App | 14, 22, 35 | An app with code and data plus models; LLM apps also have "prompts & schemas". |
| ML Pipeline, ML Components | 8, 29, 33 | The containerized steps Data Collector, Data Processor, Model Training and Model Deploy. In the tutorials these are `ml-workflow/src/{data-collector,data-processor,model-training,workflow}`: model deploy is a pipeline step inside `workflow/`, not its own folder (L15 guide). |
| POC / Prototype / MVP | 11–12 | "Proof Of Concept", "Prototype", "Minimum Viable Product": the project's phases. |
| Screenflow & Wireframes | 14–18 | A screen-to-screen flow of the main interaction, plus low-fidelity screen mock-ups. |
| Solution Architecture | 14, 20–33 | The building blocks of the app, sorted into Process, Execution and State. |
| Process (People) / Execution (Code) / State (Source, Data, Models) | 20–22 | The three layers. The State examples drift between slides: "model registry" and "knowledge base" (21), "Database" and "Data / Models" (22), and "Data Store" and "Knowledge Base" (26). |
| Human Interactions / CLI + Automation / Protocol specific | 28–32 | Labels for the kind of interface on an arrow. |
| Interactive Notebooks | 28, 33 | Hosted web notebooks for experiments (Colab, JupyterHub). |
| Frontier LLMs / Fine tuned LLMs | 30, 33 | Hosted model APIs and fine-tuned versions of them (L08). |
| AI Engine | 32–33, 47 | The backend part that holds agents, harness, tools, skills and memory, drawn as its own container on HTTP 9001. The tutorial cheese apps have no separate AI-engine container: `api-service` itself calls Gemini and Chroma (L10, L18 guides). |
| Knowledge Base / Vector DB | 21, 26, 32, 47 | The retrieval store. The tutorials use ChromaDB (`vector-db`, port 8000). |
| Technical Architecture | 35, 47 | The deployment-level "Blueprint" of components and containers. The build-up slides 36–46 are titled "Building a Technical Architecture". |
| Agent Platform | 39–50, 53 | GCP's AI/ML platform, which runs the "Serverless ML Tasks" and hosts the LLMs ("Gemini, Claude"). The tutorial READMEs say **Vertex AI** (L13 custom jobs, L15 "Vertex AI Pipelines"). The IAM role now shows as "Agent Platform User" (L04 and L05 guides). The table calls the LLM row "Agent Platform LLMs". |
| GCS Bucket ("Data & Models") | 42, 50 | Object storage for data, models and model artifacts. |
| Google Artifact Registry | 44, 50, 53 | Hosts "all the container images". Same name as in L20 and L22. |
| Single Compute Instance/ Kubernetes Cluster | 43–47, 50 | Where the app's containers run: one VM ("Compute Instance") or GKE. In the tutorials: one VM in L20, GKE in L22. |
| NGINX Container | 47 | The reverse proxy in front of the app. L20's `nginx.conf` sends `/api-service/` to `api-service:9000` and `/` to `frontend:3000`, which matches the slide's ports. |
| API Service Container / Cheese App Container / Vector DB Container | 47 | The tutorial folders are `api-service`, `frontend-react` and `vector-db`. |
| GCE Persistent Volume / Persistent Disk (NFS) | 46, 50 | Files that must survive image updates. In the tutorials this is the api-service's `/persistent` mount (`persistent-folder` on the L20 VM, PVCs in L22). The slide's "NFS" label has no counterpart in those guides. |
| Microservices vs monolithic | 55 | One service per design component. |
| Github root / Secrets (outside git folder) | 56 | The repository root, and a key folder kept beside it. The tutorials do the same: `secrets/` next to the clone, mounted at `/secrets` (L03, L04, L10 guides). |
| Formaggio.me | 5, 18 | The name of the cheese app and its live site. |

**Cloud building blocks (slide 53).**

| Role | GCP | AWS | Azure |
|---|---|---|---|
| Container Registry | Google Artifact Registry | Elastic Container Registry | Azure Container Registry |
| Object Storage | Google Cloud Storage | S3 Bucket | Azure Blob Storage |
| AI / ML Platform | Agent Platform | Amazon SageMaker | Azure Machine Learning |
| LLMs | Agent Platform LLMs | Bedrock LLMs | Azure Foundry LLMs |
| Persistent Storage | GCE Persistent Volume | Elastic Block Store | Azure Disk Storage |
| Virtual Machines | Compute Instance | EC2 Instance | Azure Virtual Machine |
| Kubernetes Service | Google Kubernetes Engine | Elastic Kubernetes Service | Azure Kubernetes Service |

The per-cloud summaries (50–52) use the short forms GKE, EKS and AKS, plus "Amazon Elastic Block Store", "EC2 Instance" and "Azure Virtual Machines".

**Other differences from the tutorials.**
- **Python tooling.** Slide 6 labels every environment "pipenv". Most current tutorials use `uv`, although `cheese-app-v0/api-service` still uses pipenv (L10 guide).
- **Port 80.** Slides 41–47 label the user link "HTTP/HTTPS 80". Port 80 is plain HTTP, and HTTPS normally uses 443. The deployed cheese app in L20 and L22 is served over plain HTTP on port 80.
- **Streamlit.** Slide 11 pairs the Prototype phase with Streamlit. None of the tutorial repositories covered by our guides uses Streamlit.

## Commands and code on the slides

The slides show no shell commands. The only code-like content is listed below.

- Slide 5: the live demo URL `http://formaggio.me/`, followed by "[Go live]".
- Slides 41–47: link labels `HTTPS 443`, `HTTP/HTTPS 80`, `HTTP 3000`, `HTTP 9000`, `HTTP 9001`, `HTTP 8000`, `NFS`. Slides 28–32 use the labels `(HTTP / HTTPS)`, `(HTTPS)` and `(Protocol specific)`.
- Slide 56: the folder tree, verbatim apart from the two callouts, which are shown here as comments:

```
/application-root-folder          # "Github root"
   /src
      /api-service
      /data-collector
      /data-processor
      /model-training
      /model-deploy
      /ml-workflow
      /frontend-simple
      /frontend-react
      /vector-db
      /postgres-db
/secrets                          # "Secrets (outside git folder)"
   - data-service.json
```

Compared with the repositories:
- `cheese-app-v2` has `api-service`, `vector-db`, `frontend-simple` and `frontend-react` (L18 guide).
- `cheese-app-v4` has `api-service`, `frontend-react`, `vector-db`, `data-collector`, `data-processor`, `workflow` and `deployment` (L23 guide).
- No repository covered by our guides has `postgres-db`, `ml-workflow` or `model-deploy` as service folders under `src/`.
- The key files in the tutorials have other names, such as `llm-service-account.json`, `ml-workflow.json` and `deployment.json`.

## What the lecture stresses

- **Plan before coding.** Build the ML pipeline, then decide which APIs the app needs from user needs, then design the UI. The open question "How do we do this?" is in red. (Slide 8)
- **Start low-tech.** Brainstorm on a whiteboard or paper before drawing wireframes. (Slide 16)
- **Anchor the architecture in the problem statement.** Ask how the app addresses the problem before listing components. (Slide 20)
- **Separate people, code and state.** Every component belongs to one layer, and every interface is labelled with its kind. (Slides 21, 28–32)
- **Preprocessing must match.** Apply to an incoming image the same preprocessing that was used in training, and store the preprocessing information as state. (Slide 23)
- **All development is containerized,** for developers and data scientists alike. (Slide 38)
- **Label every connection with a protocol and a port.** (Slides 41–47)
- **Keep persisted files outside images.** Anything that must survive an image update goes on a persistent volume. (Slides 46, 50)
- **Trade-off: single instance or cluster.** One compute instance hosts one copy of every container; Kubernetes is used to scale. (Slides 43, 50)
- **Think in building blocks, not vendors.** The same design maps onto GCP, AWS or Azure. (Slides 50–53)
- **A blueprint is only the start.** "Well not really, we need to build it." (Slide 49)
- **Microservices, and how fine-grained.** "Think in microservices vs monolithic" and "What determines how micro to get?". Map the design's components to services. (Slide 55)
- **Tests and secrets.** "Keep tests inside the container" and "Keep secrets outside of your git repo". The tree shows `secrets/` as a sibling of the GitHub root. (Slides 55–56)
- **Match tooling to the phase.** Prototype with Streamlit and a single model behind FastAPI; build the MVP with web frameworks. (Slide 11)

## Pointers

- Slide 5: the live cheese app, `http://formaggio.me/` "[Go live]" (an in-lecture demo).
- Slides 9–12: "Review" slides that point back to the project's problem definition, proposed solution, scope and status from earlier in the course.
- Slide 6 is titled as a recap, so it refers back to earlier lectures. The containers and pipelines it motivates are L02–L04 and L15.
- Slide 57, "Tutorial: Building Solution Architecture", is an in-class group exercise:
  1. Open the shared Google Slides deck, `https://docs.google.com/presentation/d/1U69Nri6ZBYmjGSv5402kZwXnswo1eYZDBhBRPuIfKas/edit?usp=sharing`.
  2. Duplicate its slides 2, 3 and 4 to the end of the deck.
  3. Add your group name.
  4. Identify Process, Execution and State for your project.
  5. Draw your project's Solution Architecture slide.
- The slides name no repository, reading, homework or milestone. The `dlops-io` tutorials that implement this architecture come later:
  - `ml-workflow` (L15)
  - `cheese-app-v1`/`v2` (L18)
  - `cheese-app-v3` with Pulumi on one VM (L20) and on GKE (L22)
  - `cheese-app-v4` (L23)
