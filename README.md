# ⚡ PULSE — Newsroom AI Orchestrator

A **multi-agent AI pipeline** for broadcast news production, built for E.W. Scripps.

PULSE orchestrates **nine specialized AI agents** through a LangGraph workflow to take a story from intake to publish-ready — including research, audio transcription, video analysis, writing, multi-language translation, fact-checking, SEO optimization, and compliance review.

---

## Architecture

```
┌─────────────────┐
│  Editor-in-Chief │  ← Orchestrator: triage, prioritize, final publish decision
└────────┬────────┘
         │
┌────────▼────────┐
│    Researcher    │  ← RAG via Azure AI Search + LLM synthesis
└────────┬────────┘
         │
┌────────▼────────┐
│     Speech       │  ← Audio transcription, speaker diarization, TTS narration
└────────┬────────┘
         │
┌────────▼────────┐
│     Video        │  ← Scene detection, face ID, OCR, content moderation
└────────┬────────┘
         │
┌────────▼────────┐
│     Writer       │  ← Broadcast-quality article drafting
└────────┬────────┘
         │
┌────────▼────────┐
│   Translator     │  ← Multi-language article translation
└────────┬────────┘
         │
┌────────▼────────┐
│   Fact-Checker   │  ← Claim extraction + verification
└────────┬────────┘
         │
┌────────▼────────┐
│  SEO Optimizer   │  ← Headlines, meta, social copy
└────────┬────────┘
         │
┌────────▼────────┐
│   Compliance     │  ← FCC, legal, editorial policy
└────────┬────────┘
         │
┌────────▼────────┐
│  Editor-in-Chief │  ← Final review & publish decision
└─────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | **LangGraph** — stateful multi-agent workflow |
| LLM | **Azure OpenAI** (GPT-4o) |
| Embeddings | **Azure OpenAI** (text-embedding-ada-002) |
| Vector Search | **Azure AI Search** || Speech & Audio | **Azure AI Speech** — STT, TTS, translation |
| Video Analysis | **Azure Video Indexer** — scenes, faces, OCR, moderation || Observability | **LangSmith** — tracing & evaluation |
| Backend | **FastAPI** + WebSocket |
| Frontend | **HTML/CSS/JS** — real-time dashboard |

## Quick Start

### Prerequisites
- Python 3.10+
- Azure OpenAI resource with GPT-4o deployment (not needed in demo mode)
- Azure AI Search service (not needed in demo mode)
- LangSmith account (optional, for tracing)

### Setup

```bash
# 1. Clone and navigate
cd scripps

# 2. Create virtual environment
python -m venv scribbs
scribbs\Scripts\activate       # Windows (PowerShell / CMD)
# source scribbs/bin/activate  # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
# Edit .env with your Azure credentials (or leave defaults for demo mode)

# 5. Run the app
python -m app.main
```

The FastAPI server starts on **http://localhost:8000** by default. Open that URL in your browser to access the PULSE dashboard.

> **Tip:** The port can be changed via `APP_PORT` in `.env`.

### Demo Mode

Set `DEMO_MODE=true` in `.env` (this is the **default**) to run with realistic mock data — no Azure credentials needed. Just start the server and submit stories from the UI.

### Running with Azure (Live Mode)

1. Set `DEMO_MODE=false` in `.env`.
2. Authenticate to Azure using one of:
   - `az login` (Azure CLI)
   - VS Code Azure extension
   - Managed Identity (when deployed to Azure)
3. Fill in the Azure resource endpoints in `.env` (see `.env.example` for reference).
4. Assign RBAC roles on your Azure resources:
   - **Azure OpenAI**: `Cognitive Services OpenAI User`
   - **Azure AI Search**: `Search Index Data Reader`
   - **Azure AI Speech**: `Cognitive Services Speech User`
5. Start the server: `python -m app.main`

## Project Structure

```
scripps/
├── .env                    # Configuration (secrets)
├── .env.example            # Configuration template
├── requirements.txt        # Python dependencies
├── README.md
├── app/
│   ├── main.py             # FastAPI server + WebSocket
│   ├── config.py           # Typed configuration
│   ├── agents/
│   │   ├── orchestrator.py # Editor-in-Chief agent
│   │   ├── researcher.py   # Research + RAG agent
│   │   ├── speech.py       # Audio transcription + TTS agent
│   │   ├── video.py        # Video analysis agent
│   │   ├── writer.py       # Article drafting agent
│   │   ├── translation.py  # Multi-language translation agent
│   │   ├── factchecker.py  # Claim verification agent
│   │   ├── optimizer.py    # SEO + social media agent
│   │   └── compliance.py   # Legal/editorial compliance agent
│   ├── graph/
│   │   └── workflow.py     # LangGraph workflow definition
│   ├── models/
│   │   └── schemas.py      # Pydantic data models
│   ├── services/
│   │   ├── azure_openai.py # Azure OpenAI LLM service
│   │   ├── azure_search.py # Azure AI Search (RAG)
│   │   ├── azure_speech.py # Azure AI Speech service
│   │   ├── azure_video.py  # Azure Video Indexer service
│   │   └── embeddings.py   # Embedding service
│   └── data/
│       ├── mock_stories.json
│       └── knowledge_base.json
└── static/
    ├── index.html          # Dashboard UI
    ├── css/styles.css       # Styles
    └── js/app.js           # Frontend logic
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI dashboard |
| GET | `/api/health` | Health check |
| POST | `/api/stories` | Submit story to pipeline |
| GET | `/api/stories` | List all stories |
| GET | `/api/stories/{id}` | Get story status + outputs |
| GET | `/api/stories/{id}/messages` | Get agent activity log |
| WS | `/ws` | Real-time pipeline updates |

## How It Works

1. **Submit** a story headline + description via the web UI
2. **Orchestrator** triages the story and assigns priority
3. **Researcher** searches the knowledge base (Azure AI Search) and synthesizes a brief
4. **Speech Agent** transcribes any uploaded audio, identifies speakers, prepares narration
5. **Video Agent** analyzes uploaded video — scenes, faces, OCR text, content moderation
6. **Writer** drafts a broadcast-quality article from research, transcripts, and video insights
7. **Translation Agent** produces the article in Spanish, French, and German
8. **Fact-Checker** extracts and verifies every claim
9. **SEO Optimizer** generates headlines, meta descriptions, keywords, and social copy
10. **Compliance** reviews for FCC, legal, and editorial policy adherence
11. **Orchestrator** makes final publish/hold decision based on all agent outputs

All agent activity streams to the UI in real-time via WebSocket.

## Request Flow

Below is the end-to-end request flow — from the moment a user clicks **Submit** to the final publish decision.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USER / BROWSER                                  │
│  1. User fills in headline, description, priority, audience                  │
│  2. Clicks "Submit to PULSE"                                                 │
│  3. WebSocket connection streams real-time updates                           │
└──────────────┬──────────────────────────────────────┬────────────────────────┘
               │  POST /api/stories                   │  WS /ws
               ▼                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND (main.py)                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  submit_story()                                                     │     │
│  │  • Generates story_id                                               │     │
│  │  • Creates PipelineState with StoryInput                            │     │
│  │  • Stores initial state in memory (story_store)                     │     │
│  │  • Returns StoryResponse {story_id, status: "incoming"}             │     │
│  │  • Launches _run_pipeline() as async background task                │     │
│  └─────────────────────┬───────────────────────────────────────────────┘     │
│                        │                                                     │
│                        ▼                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  _run_pipeline()                                                    │     │
│  │  • Invokes LangGraph compiled workflow via graph.astream()          │     │
│  │  • For each node output:                                            │     │
│  │      → Updates story_store with latest state                        │     │
│  │      → Broadcasts agent messages via WebSocket                      │     │
│  │  • On completion: sends "pipeline_complete" event                   │     │
│  └─────────────────────┬───────────────────────────────────────────────┘     │
└────────────────────────┼─────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      LANGGRAPH WORKFLOW (workflow.py)                         │
│                                                                              │
│  WorkflowState (TypedDict) flows through each node:                          │
│  {story_id, input, status, messages[], research, draft, fact_check,          │
│   seo, compliance, current_agent, ...}                                       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  ① ORCHESTRATOR TRIAGE (orchestrator.py)                            │     │
│  │     • Assesses priority (breaking/high/medium/low)                  │     │
│  │     • Routes story into full editorial pipeline                     │     │
│  │     • Sets status → "researching"                                   │     │
│  │                        │                                            │     │
│  │                        ▼                                            │     │
│  │  ② RESEARCH AGENT (researcher.py)                                   │     │
│  │     • Queries Azure AI Search (vector similarity)  ◄──┐            │     │
│  │     • Retrieves top-K relevant knowledge base docs    │            │     │
│  │     • Sends context + headline to Azure OpenAI LLM    │            │     │
│  │     • Produces ResearchResult:                        │            │     │
│  │       {key_facts, sources, background, data_points}   │            │     │
│  │     • Sets status → "writing"                         │            │     │
│  │                        │                    ┌─────────┘            │     │
│  │                        ▼                    │                       │     │
│  │  ③ WRITER AGENT (writer.py)          Azure AI Search               │     │
│  │     • Takes ResearchResult as input   (RAG Vector Store)           │     │
│  │     • Calls Azure OpenAI with creative prompt                      │     │
│  │     • Produces ArticleDraft:                                        │     │
│  │       {headline, subheadline, body, summary, quotes}               │     │
│  │     • Sets status → "fact_checking"                                 │     │
│  │                        │                                            │     │
│  │                        ▼                                            │     │
│  │  ④ FACT-CHECK AGENT (factchecker.py)                                │     │
│  │     • Extracts factual claims from ArticleDraft                     │     │
│  │     • Cross-references claims against knowledge base                │     │
│  │     • Calls Azure OpenAI with analytical prompt                     │     │
│  │     • Produces FactCheckResult:                                     │     │
│  │       {verified_claims[], flagged_issues[], overall_score}          │     │
│  │     • Sets status → "optimizing"                                    │     │
│  │                        │                                            │     │
│  │                        ▼                                            │     │
│  │  ⑤ SEO OPTIMIZER AGENT (optimizer.py)                               │     │
│  │     • Analyzes article for digital distribution                     │     │
│  │     • Calls Azure OpenAI for optimization                           │     │
│  │     • Produces SEOResult:                                           │     │
│  │       {optimized_headline, meta_description, keywords,              │     │
│  │        social_copy: {twitter, facebook, instagram}, seo_score}      │     │
│  │     • Sets status → "compliance_review"                             │     │
│  │                        │                                            │     │
│  │                        ▼                                            │     │
│  │  ⑥ COMPLIANCE AGENT (compliance.py)                                 │     │
│  │     • Reviews for FCC broadcast regulations                         │     │
│  │     • Checks defamation/libel risk, privacy concerns                │     │
│  │     • Queries knowledge base for compliance policies                │     │
│  │     • Calls Azure OpenAI with analytical prompt                     │     │
│  │     • Produces ComplianceResult:                                    │     │
│  │       {approved, issues[], legal_flags[], editorial_notes[]}        │     │
│  │                        │                                            │     │
│  │                        ▼                                            │     │
│  │  ⑦ ORCHESTRATOR FINAL (orchestrator.py)                             │     │
│  │     • Reviews all agent outputs:                                    │     │
│  │       fact_check.overall_score ≥ 0.7 AND compliance.approved        │     │
│  │     • Decision:                                                     │     │
│  │       ✅ APPROVED → status = "ready_to_publish"                     │     │
│  │       ⚠️  HELD    → status = "compliance_review"                    │     │
│  │     • Sets completed_at timestamp                                   │     │
│  │                                                                     │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        AZURE SERVICES (external)                             │
│                                                                              │
│  ┌─────────────────────┐  ┌────────────────────────┐  ┌──────────────────┐  │
│  │  Azure OpenAI       │  │  Azure AI Search        │  │  LangSmith       │  │
│  │  (GPT-4o)           │  │  (Vector Index)         │  │  (Tracing)       │  │
│  │                     │  │                          │  │                  │  │
│  │  • Chat completions │  │  • pulse-knowledge-base  │  │  • Agent traces  │  │
│  │  • Embeddings       │  │  • Vector similarity     │  │  • LLM calls     │  │
│  │  • RBAC auth via    │  │    search (HNSW)         │  │  • Latency data  │  │
│  │    DefaultAzure     │  │  • RBAC auth via         │  │  • Token usage   │  │
│  │    Credential       │  │    DefaultAzure          │  │                  │  │
│  │                     │  │    Credential            │  │                  │  │
│  └─────────────────────┘  └────────────────────────┘  └──────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          REAL-TIME UI (browser)                              │
│                                                                              │
│  ┌──────────────┐  ┌─────────────────────────┐  ┌────────────────────────┐  │
│  │ Story Intake  │  │  Pipeline Visualization  │  │  Output Panels         │  │
│  │              │  │                           │  │                        │  │
│  │ • Form input │  │  ①→②→③→④→⑤→⑥→⑦          │  │  • Article tab         │  │
│  │ • Sample     │  │  Animated node-by-node    │  │  • SEO & Social tab    │  │
│  │   stories    │  │  progress + activity feed │  │  • Fact-Check tab      │  │
│  │ • Priority   │  │                           │  │  • Compliance tab      │  │
│  └──────────────┘  └─────────────────────────┘  └────────────────────────┘  │
│                                                                              │
│  WebSocket receives:                                                         │
│    agent_start → agent_message (per node) → pipeline_complete                │
│  Polling (GET /api/stories/{id}) as fallback                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Sequence Summary

| Step | Component | Action | Output |
|------|-----------|--------|--------|
| 1 | **Browser** | POST `/api/stories` with headline + description | `StoryResponse` with `story_id` |
| 2 | **FastAPI** | Creates `PipelineState`, launches async pipeline | WebSocket: `agent_start` events |
| 3 | **Orchestrator** | Triages priority, routes to pipeline | `AgentMessage` (triage result) |
| 4 | **Researcher** | Vector search (Azure AI Search) → LLM synthesis | `ResearchResult` |
| 5 | **Speech** | Audio transcription, speaker diarization, TTS prep | `SpeechResult` |
| 6 | **Video** | Scene detection, face ID, OCR, content moderation | `VideoResult` |
| 7 | **Writer** | Drafts article from research + transcripts + video | `ArticleDraft` |
| 8 | **Translator** | Multi-language translation (ES, FR, DE) | `TranslationResult` |
| 9 | **Fact-Checker** | Extracts & verifies claims | `FactCheckResult` (score: 0-1) |
| 10 | **SEO Optimizer** | Optimizes headline, meta, social copy | `SEOResult` (score: 0-1) |
| 11 | **Compliance** | FCC, legal, editorial review | `ComplianceResult` (approved/flagged) |
| 12 | **Orchestrator** | Final publish/hold decision | Status: `ready_to_publish` or `held` |
| 13 | **Browser** | Renders all outputs across 7 tabs | Article, Audio, Video, Translation, SEO, Fact-Check, Compliance |

### Authentication Flow

All Azure services use **RBAC via `DefaultAzureCredential`** from `azure-identity`:

```
DefaultAzureCredential auto-chains through:
  1. Managed Identity     (Azure-hosted environments)
  2. Azure CLI            (local dev: `az login`)
  3. VS Code credential   (VS Code Azure extension)
  4. Azure PowerShell     (Connect-AzAccount)
  
No API keys or secrets stored in .env for Azure services.
```

---

*Built with LangGraph + Azure OpenAI + Azure AI Search — E.W. Scripps AI Innovation Lab*
