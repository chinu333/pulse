# PULSE — Demo Talk Track (LIVE MODE)

**Audience:** E.W. Scripps Senior Leadership  
**Duration:** 15–20 minutes  
**Presenter:** GTO / AI Engineering  
**Date:** March 2026  
**Mode:** `DEMO_MODE=false` — Live Azure OpenAI, Azure AI Search, Azure AI Speech, Azure Video Indexer

---

## Pre-Demo Checklist

- [ ] `.env` has `DEMO_MODE=false`
- [ ] Azure credentials configured (`az login` or managed identity)
- [ ] App running at **http://localhost:8000** (`python -m app.main`)
- [ ] Browser: Chrome or Edge (required for audio narration/podcast playback)
- [ ] Browser volume turned up (for live narration and podcast demo)
- [ ] Browser zoom at 100 % — full-screen mode (F11) recommended
- [ ] Terminal visible but minimized (shows real-time agent logs + Azure API calls)
- [ ] Verify internet connectivity (live Azure API calls required)

> **Important:** In live mode, each agent makes real API calls to Azure. The step-by-step approval flow lets you narrate while agents complete (~5–30 sec per step).

---

## Opening (1 min)

> "What you're about to see is **PULSE** — our Newsroom AI Orchestrator.
>
> PULSE takes a single story idea and runs it through **twelve specialized AI agents** — from research to security to compliance — and delivers a publish-ready article, a podcast episode, multi-voice audio narration, video analysis, and multi-language translations.
>
> The AI pipeline is **live** — real calls to **Azure OpenAI GPT-4.1**, **Azure AI Search**, **Azure AI Speech (Dragon HD Omni)**, and **Azure Video Indexer** — running in our own Azure tenant, orchestrated by **LangGraph**, with full observability through **LangSmith**. We're using a **representative hurricane scenario** to showcase the full pipeline — the same architecture applies to any story from any Scripps market.
>
> The pipeline runs **step by step** — after each agent completes, I'll approve it so you can see exactly what every AI agent produces before the next one starts.
>
> Let me show you how it works."

---

## Act 1 — The Interface (1 min)

Walk through the three-panel layout without submitting yet.

| Panel | What to Point Out |
|-------|-------------------|
| **Left sidebar** | Story intake form — headline, description, priority, audience. Just like an assignment desk. |
| **Center** | Eight output tabs — **Audio, Video, Article, Fact-Check, Compliance, SEO, Podcast, Translation** — ordered to match the agent execution sequence. Every artifact the newsroom needs. |
| **Right panel** | The agent pipeline — twelve nodes that will light up in sequence as each AI agent does its work. Content Safety and Security and Brand are clearly labeled. Real-time visibility into every step. |

> "Think of this as a **digital newsroom** where every role — researcher, writer, fact-checker, content safety scanner, podcast producer, translator, SEO specialist, compliance reviewer — is an AI agent that collaborates in a defined workflow."

---

## Act 2 — Submit a Story (1 min)

**Recommended for maximum impact:**

| Field | Value |
|-------|-------|
| Headline | *"Breaking: Major Hurricane Approaching Gulf Coast — Millions Under Evacuation Orders"* |
| Description | *"Category 4 hurricane expected to make landfall within 48 hours. Multiple Scripps markets in the path."* |
| Priority | **Breaking** |
| Audience | **General** |

Click the submit arrow icon.

> "I'm submitting a breaking story — the kind of scenario where speed and accuracy are life-or-death. Watch the pipeline on the right — the first agent is already working."

---

## Act 3 — Step-by-Step Agent Pipeline (8–10 min)

Each agent runs one at a time. After each completes, a **bottom approval banner** appears showing what the agent produced. You approve to continue. The tab auto-switches to the relevant output so the audience can see results in real time.

> **Pacing tip:** Use the 5–30 second wait time while each agent runs to narrate what it's doing. When the banner appears, briefly review the output tab, then click **Continue**.

---

### Step 1: Orchestrator (Editor-in-Chief)
*Wait ~5 seconds for completion. Banner appears.*

> "The **Editor-in-Chief agent** triages the story — assesses priority, decides which agents need to run, and creates the assignment. Think of this as your executive producer making the call."

**Click Continue.**

---

### Step 2: Content Safety → Security Tab ⭐
*Wait ~5 seconds. Tab auto-switches to Security.*

> "Before anything else, the **Content Safety agent** scans the incoming content. It's checking for **prompt injection attacks**, **PII exposure** — social security numbers, credit cards, phone numbers — and any **harmful content**. It also classifies the data: PUBLIC, INTERNAL, or CONFIDENTIAL."

*Point out the inbound scan card showing PASSED in green, risk score at 0%, and the clean status.*

> "This is defense-in-depth. In live mode, this calls **Azure AI Content Safety** for deep content analysis. Every scan is logged to the **audit trail** — you can see the first event already in the timeline at the bottom."

**Click Continue.**

---

### Step 3: Researcher
*Wait ~10–15 seconds. Banner appears.*

> "The **Research agent** is hitting our **Azure AI Search** knowledge base right now — pulling relevant context, related stories, and source material. The knowledge base is seeded with **sample editorial content and Scripps guidelines** — in production, this would be ingesting live AP feeds, archive stories, and market-specific data. This is **RAG** — Retrieval-Augmented Generation — grounding the AI in real information, not hallucinations."

**Click Continue.**

---

### Step 4: Speech Agent → Audio Tab
*Wait ~5–10 seconds. Tab auto-switches to Audio.*

> "The **Speech agent** uses **Azure AI Speech** to process audio — transcription, speaker diarization, and language detection. In production, this would ingest field audio, press conferences, and interviews."

*Point out the transcript with speaker-labeled lines (Anchor, Field Reporter, Official Source) and the speaker chips showing segment counts.*

> "Notice the transcript is **speaker-diarized** — each line is tagged with who's speaking. When you hit play, you'll hear **three distinct Dragon HD Omni voices** — a male anchor, a female field reporter, and a male official source. Multi-voice, broadcast-quality narration generated live by Azure AI Speech."

**Click Continue.**

---

### Step 5: Video Agent → Video Tab
*Wait ~5–10 seconds. Tab auto-switches to Video.*

> "The **Video agent** leverages **Azure Video Indexer** for scene detection, face identification, on-screen text extraction via OCR, and content moderation. Imagine automatically indexing all of our broadcast footage."

*Point out the scene list, topics, face detection, and moderation results.*

**Click Continue.**

---

### Step 6: Writer → Article Tab
*Wait ~15–20 seconds. Tab auto-switches to Article.*

> "Now the **Writer agent** takes all the research, transcripts, and video insights and drafts a broadcast-quality article. It's calling **GPT-4.1** through Azure OpenAI right now — the same model, running in our own Azure tenant with enterprise security."

*Let the audience read the headline and first few paragraphs.*

> "Notice the word count, tone analysis, and key quotes extracted automatically."

**Click Continue.**

---

### Step 7: Fact-Checker → Fact-Check Tab
*Wait ~10–15 seconds. Tab auto-switches to Fact-Check.*

> "The **Fact-Check agent** extracts every verifiable claim from the article and grades each one. It cross-references against our **Azure AI Search knowledge base** — the same sample knowledge base the researcher used — and uses the LLM to assess plausibility. In production with real Scripps content indexed, this becomes even more powerful. It gives us a confidence score and flags anything that needs human verification before publish."

*Point out the score ring, verified claims in green, and any flagged items.*

**Click Continue.**

---

### Step 8: Security and Brand → Security Tab ⭐
*Wait ~5 seconds. Tab auto-switches to Security.*

> "Now the **Security and Brand agent** comes back for the **outbound scan** — this time scanning everything the AI **generated**: the article draft, looking for PII leakage, harmful content, or anything that shouldn't go on air."

> "This is a **hard gate**. If the outbound security scan finds threats — the pipeline **stops immediately**. Compliance, SEO, Podcast, Translation — none of them run. The content is flagged for human review. Security before compliance, not after."

*Point out the outbound scan card showing PASSED in green alongside the inbound scan. Scroll down to the audit trail.*

> "Both inbound and outbound scans are logged in the **audit trail** — every agent, every decision, every confidence score. Chain-of-custody for AI-generated content."

**Click Continue.**

---

### Step 9: Compliance → Compliance Tab
*Wait ~10–15 seconds. Tab auto-switches to Compliance.*

> "**Compliance** runs a legal and editorial policy review — FCC regulations, libel risk, source attribution, editorial standards. It checks against our knowledge base which contains actual **Scripps Editorial Standards** and **FCC Broadcast Compliance Requirements**."

> "This is also a **gate**. If compliance rejects, the SEO, Podcast, and Translation agents are skipped — no point optimizing or translating content that can't be published."

*Point out the verdict badge (should show APPROVED in green), legal flags, and editorial notes.*

**Click Continue.**

---

### Step 10: SEO Optimizer → SEO Tab
*Wait ~10–15 seconds. Tab auto-switches to SEO.*

> "The **SEO agent** generates optimized headlines, meta descriptions, keywords, and pre-written social media copy for Twitter, Facebook, and LinkedIn — all tailored for maximum engagement."

*Point out the SEO score and the ready-to-post social copies.*

> "The social media team would normally spend 20 minutes on this."

**Click Continue.**

---

### Step 11: Podcast Agent → Podcast Tab ⭐ **Wow Moment #1**
*Wait ~10–15 seconds. Tab auto-switches to Podcast.*

> "The **Podcast agent** just converted our article into a **two-host podcast episode** — 'PULSE Daily' with hosts Alex and Morgan. It generated the full script with segments: cold open, main story, and what to watch."

*Scroll through the script showing alternating speakers.*

> "Hit play and listen."

**Click the play button.** Let it play for 15–20 seconds with alternating voices.

> "Two distinct **Dragon HD Omni voices** — Andrew for Alex, Ava for Morgan. Male and female, natural conversation flow, broadcast-ready. These are Azure AI Speech's highest-quality neural voices, generated live per line."

*Pause playback.*

**Click Continue.**

---

### Step 12: Translator → Translation Tab
*Wait ~10–15 seconds. Tab auto-switches to Translation.*

> "The **Translation agent** produces localized versions — Spanish, French, German — ready to go. For Scripps markets with multilingual audiences, this is instant reach expansion."

*Point out the language cards, translated headlines, and quality scores.*

**Click Continue.**

---

### Step 13: Orchestrator Final Decision → Article Tab
*Wait ~5 seconds. Pipeline completes. Tab auto-switches to Article.*

> "The **Editor-in-Chief** comes back for the final call — reviewing every agent's output, the fact-check score, compliance status, security scan results — and makes the publish decision. And there it is — **pipeline complete**."

*Click Dismiss on the final banner.*

---

## Act 4 — Quick Output Recap (1 min)

Click through tabs rapidly to show the full picture:

> "So from one story submission, we now have:
> - A **publish-ready article** drafted by GPT-4.1
> - A **two-host podcast episode** with distinct male/female Dragon HD Omni voices
> - **Multi-voice audio narration** with three speakers — Anchor, Field Reporter, Official Source
> - **Three language translations** for multilingual markets
> - Full **audio transcription** with speaker diarization
> - **Video analysis** with scene detection and face ID
> - **SEO optimization** with social media copy
> - **Fact-checking** on every claim
> - **Content Safety and Security and Brand scanning** — inbound and outbound — with audit trail
> - **Legal and editorial compliance** review
>
> All live. All real Azure API calls. Twelve agents, one pipeline."

---

## Act 5 — Architecture & Strategic Value (2–3 min)

> "Let me explain what's under the hood and why this matters strategically."

### The Technology Stack

> "PULSE is built on five pillars:
>
> 1. **Azure OpenAI** — GPT-4.1 for reasoning and writing, embedding models for search. Enterprise-grade, running in our Azure tenant. No data leaves our environment.
>
> 2. **Azure AI Services** — Speech (Dragon HD Omni for multi-voice TTS), Video Indexer for video analysis, AI Search for our knowledge base, **Content Safety for security scanning**. Native Azure services with RBAC authentication — no API keys, just managed identity.
>
> 3. **LangGraph** — the orchestration layer. It's a state machine that manages agent handoffs, error recovery, and workflow logic. Not a simple prompt chain — a production-grade pipeline with **security gates at entry and exit, and a compliance gate** — three conditional checkpoints that can halt the pipeline.
>
> 4. **LangSmith** — full observability. Every agent call, every LLM invocation, every decision is traced and logged. We can debug, evaluate, and improve the pipeline over time.
>
> 5. **Step-by-step approval** — the pipeline pauses after each agent so a human editor can review, approve, or stop. AI proposes, humans decide.
>
> 6. **Security & Audit** — Immutable audit trail, prompt injection defense, PII detection, data classification. Enterprise security baked into the agentic architecture, not bolted on.\"

### Why This Matters for Scripps

> "Three things:
>
> **Speed** — A story goes from idea to publish-ready in minutes. Twelve agents working in sequence, each doing what would take a human 15–30 minutes.
>
> **Quality** — Built-in fact-checking, **Content Safety** (inbound) and **Security and Brand** (outbound) with hard gates, compliance review, and human approval at every step means fewer retractions, fewer legal risks, and higher editorial standards at scale.
>
> **Scale** — This works for one story or a hundred. Every Scripps market gets the same level of research, fact-checking, and SEO optimization — without adding headcount."

---

## Act 6 — PULSE Assist & Ad Monetization ⭐ **Wow Moment #3** (2–3 min)

Open the PULSE Assist chat by clicking the floating button (bottom-right).

> "Beyond the pipeline, PULSE includes a **real-time Q&A assistant** that's contextually aware of whatever story is loaded. Let me show you."

### Q&A Demo

*Type: "How do I prepare for the hurricane?"*

> "The assistant understands the story context and gives actionable guidance. Notice it only **speaks the answer aloud** when you ask via the **microphone button** — text questions stay silent. If you use voice, there's a **stop button** to cut the audio anytime."

### Contextual Ad Placement

*After the response, a sponsored ad banner appears in a fixed bar above the input — rotating between up to 3 relevant ads (e.g., Home Depot, Red Cross, Nestlé Pure Life).*

> "See that? A **contextual ad banner** just appeared — and here's the key: **no hardcoded rules decided this**. An actual **AI agent** — GPT-4.1 running in Azure — evaluated four signals in real-time:
>
> 1. The **story headline** — it knows this is a hurricane story
> 2. The **user's question** — they asked about preparation
> 3. The **bot's answer text** — it mentioned water, batteries, and supplies
> 4. The **response type** — general, weather, traffic, or stores
>
> The agent reviewed all 19 available sponsor ads and chose up to **three most relevant ones**. They rotate automatically every 4 seconds with dot indicators — or you can click to switch. It also knows NOT to show ads on purely emotional questions like 'Is my family safe?' — that's the kind of nuance only an LLM can handle."

> "This is a **real agentic workflow** — the same AI architecture powering the newsroom pipeline is now powering ad monetization. The LLM reasons about context, not keyword matching."

### AI-Driven Store Locator

*Ask: "Where can I buy gas?"*

> "Notice it returned **gas stations** — QuikTrip, Shell, BP — not hardware stores or pharmacies. The LLM decides **what to search for** based on the question. It generates the search queries — brand names like 'Shell', 'QuikTrip' — and sends them to Azure Maps. Completely AI-driven, no hardcoded category mapping."

*Point out the new ad banner: GasBuddy and Waze ads now showing.*

> "And the ad agent swapped to **gas and traffic ads** — GasBuddy and Waze — because it understood the question changed. Every question gets fresh ad targeting."

### Multi-Topic Demo

*Ask: "What's the weather forecast?" → Weather Channel or AcuRite ads appear.*
*Ask: "How's traffic to Tampa?" → Waze or GEICO ads appear.*
*Ask: "Where can I buy groceries?" → Instacart or DoorDash ads appear.*

> "Every topic gets a **different, relevant sponsor**. Weather questions show weather apps. Traffic questions show Waze or auto insurance. Store questions show delivery services. The AI agent handles all the targeting — no hardcoded rules, no keyword matching, no fixed intervals. It decides per-question whether an ad is appropriate at all."

### Config & Control

> "The entire ad system is driven by a **single JSON config file** — `ads_config.json`. Sales teams can add sponsors, set keywords, define branding — all without touching code. There's an **enable/disable toggle** for demos or ad-free tiers.
>
> But the decision of **when and whether** to show an ad — that's made by an **AI agent** calling GPT-4.1 in real-time. It's the same Azure OpenAI infrastructure powering the entire newsroom. The agent even filters out emotionally sensitive moments — it won't show an ad when someone asks 'Am I in danger?'
>
> For Scripps, this turns the Q&A assistant into a **revenue channel**. Every user interaction is a monetization opportunity — contextually relevant, AI-curated, native to the experience."

---

## Act 7 — Security & Observability Dashboard ⭐ **Wow Moment #4** (2 min)

> "Let me circle back to something the CIO will care about — security and observability."

*Click the **Security** button in the header.*

> "This opens the Security & Observability Dashboard — a full-screen, real-time view into the entire AI pipeline. The dashboard is built to integrate with **LangSmith**, our observability layer — think of it as Application Insights specifically built for AI agents. Right now, it's displaying **representative analytics data** to demonstrate the monitoring capabilities. In production, this aggregates live traces from every agent run flowing through PULSE."

*Point to the KPI cards.*

> "Top row: total agent runs, success rate, total tokens consumed, average latency, threats caught by Content Safety, and P95 latency. This is your CIO's single-pane-of-glass for AI pipeline health."

*Point to the Agent Run Distribution chart (Nightingale Rose).*

> "This **Nightingale Rose chart** shows how workload distributes across our 13 agents. You can immediately see which agents are doing the most work — and spot imbalances."

*Point to the Agent Reliability Radar chart.*

> "The **Radar chart** overlays success rate against run volume for each agent. Green is reliability, purple is workload. If an agent is handling high volume with low success rate — that's a red flag. You can catch it here before it becomes a production issue."

*Point to the Daily Activity chart.*

> "Daily pipeline activity — green bars are successful runs, red are failures. You can toggle between **7, 15, or 30 days** using these buttons."

*Click the **30 Days** toggle.*

> "The **Token Consumption** chart shows burn rate over time — critical for cost governance. Every token is a real Azure OpenAI API call flowing through our subscription."

*Point to Content Safety stat card.*

> "And here — the real-time Content Safety scanner. Every story goes through **Azure AI Content Safety** before and after the pipeline. We scan for hate speech, self-harm, violence, and sexual content — with severity levels from the Azure API. Plus our rule-based engine catches prompt injection and PII exposure. Defense-in-depth."

> "In production, this dashboard hits the **LangSmith API live**, pulling actual trace data from every agent run flowing through PULSE — giving the CIO real-time visibility into AI operations."

---

## Act 8 — Production Roadmap (1 min)

> "What you just saw was the **live pipeline** — real Azure API calls, real AI models generating content.
>
> The path to production:
>
> - **Phase 1** *(done)* — Live Azure OpenAI (GPT-4.1) and Azure AI Search connected and working
> - **Phase 2** — Ingest real Scripps content into the knowledge base — AP feeds, archive stories, style guides
> - **Phase 3** — Deploy to Azure App Service with managed identity — zero secrets, enterprise auth, auto-scaling
> - **Phase 4** — Integrate with existing CMS and broadcast workflows via API — automatic story routing and publish
> - **Phase 5** — Azure AI Avatar integration for on-screen AI news anchor with lip-synced video"

---

## Closing (30 sec)

> "PULSE is a working proof-of-concept that demonstrates how **multi-agent AI** can transform newsroom operations — not by replacing journalists, but by giving them a team of AI specialists that handle the repetitive, time-consuming work so they can focus on what matters: the story.
>
> And with the **contextual ad engine**, it's not just a cost center — it's a **revenue generator** from day one.
>
> Happy to take questions."

---

## Anticipated Questions & Answers

| Question | Answer |
|----------|--------|
| **"Is this using our data or public data?"** | The knowledge base in Azure AI Search is currently seeded with sample editorial content and Scripps guidelines. In production, we'd ingest live AP feeds, archive stories, and market-specific data. All within our Azure tenant — no data leaves our environment. The LLM calls go to Azure OpenAI in our subscription. |
| **"Those images — are they really generated live?"** | Image generation is currently disabled in the pipeline. We evaluated gpt-image-1 but paused it for this demo to focus on the core editorial workflow. It can be re-enabled with one config change. |
| **"What about hallucinations?"** | Two safeguards: (1) RAG — the researcher grounds the LLM in retrieved facts, not free generation. (2) The Fact-Check agent independently verifies every claim. Plus, the step-by-step approval means a human reviews everything before it progresses. |
| **"How much does this cost to run?"** | Azure OpenAI is token-based. A full 12-agent pipeline run costs roughly $0.15–$0.40 per story (GPT-4.1 + Dragon HD Omni TTS). At scale, that's pennies per article compared to hours of human labor. |
| **"Why does image generation take longer?"** | Image generation (gpt-image-1) is currently disabled in the pipeline. When enabled, it generates high-resolution 1024×1024 images from scratch — ~15–30 sec for 3 images. |
| **"Can we customize the agents?"** | Absolutely. Each agent is a separate Python module with its own system prompt. We can add agents, remove agents, or change the pipeline order without touching the core framework. |
| **"What about editorial voice / brand standards?"** | The Writer agent's system prompt can be tuned with Scripps editorial guidelines, AP style rules, and market-specific voice. The compliance agent already checks against editorial policy. |
| **"Why step-by-step instead of automatic?"** | For the demo, step-by-step lets you see each agent's work. In production, we can run fully automatic (all agents in sequence without pausing) or keep the approval flow for sensitive stories. It's configurable. |
| **"How does this integrate with our existing systems?"** | PULSE exposes a REST API and WebSocket interface. It can be embedded in any CMS, triggered by an assignment desk system, or run standalone. |
| **"Is this secure?"** | Yes. It uses **Azure RBAC** with `DefaultAzureCredential` — no API keys stored anywhere. In production, it runs on managed identity with network isolation. All data stays in our Azure subscription. |
| **"What model is it using?"** | GPT-4.1 for text via Azure OpenAI, Dragon HD Omni for multi-voice TTS via Azure AI Speech. We can swap models by changing one config value. The architecture is model-agnostic. |
| **"Can it handle breaking news speed?"** | The full pipeline runs in a few minutes with live API calls. For breaking news, we can configure the orchestrator to skip optional agents (e.g., skip podcast/translation, run only research → write → fact-check → publish) or run in automatic mode without approval pauses. |
| **"Is the story scenario real?"** | The hurricane scenario is a representative sample designed to exercise every agent in the pipeline — research, fact-check, compliance, multi-voice audio, podcast, translations. The same architecture handles any story type from any Scripps market. |
| **"Is the security dashboard live data?"** | The security analytics dashboard currently displays representative data to demonstrate monitoring capabilities. In production, it connects to LangSmith's API for real-time trace aggregation across all agent runs. The pipeline's Content Safety scans (inbound + outbound) are live Azure API calls. |
| **"What's LangSmith and why do we need it?"** | LangSmith is our AI observability layer — it traces every LLM call with latency, tokens, and success/failure. The Security Dashboard pulls real run data from LangSmith via API — 7, 15, or 30 day analytics with Nightingale Rose charts, Radar charts, and daily breakdowns. Essential for production AI governance. |
| **"Can the podcast use real voices?"** | It already does! Dragon HD Omni is Azure AI Speech's highest-quality neural voice family. Alex uses Andrew (male) and Morgan uses Ava (female). The audio narration uses three voices — Andrew, Ava, and Brian — for Anchor, Field Reporter, and Official Source respectively. |
| **"How does the ad targeting work?"** | It's an AI agent — GPT-4.1 running in Azure OpenAI. For each Q&A interaction, the agent receives the user's question, story headline, response type, and the available ad catalog. It reasons about relevance and decides whether to show an ad and which one. No keyword matching, no fixed intervals — pure LLM reasoning. It even filters emotionally sensitive moments. |
| **"Can advertisers manage their own ads?"** | Yes. The ad config is a simple JSON file — sponsor name, logo, headline, body, CTA link, keywords, and brand color. A sales team could manage it via a simple admin UI without engineering involvement. |
| **"What about ad frequency — won't users be annoyed?"** | There's no fixed frequency — the AI agent decides per-question whether an ad is appropriate. If the question doesn't match any sponsor well, no ad is shown. It also deduplicates within a session so users never see the same ad twice. And it's smart enough to suppress ads on emotional or crisis questions. |
| **"Is the Q&A assistant only for emergencies?"** | No. It adapts to any story topic. For emergency stories, it adds Weather, Traffic, and Stores tabs with live Azure Maps data. For non-emergency stories, it's a general-purpose Q&A chatbot grounded in the story context. |

---

## Timing Guide (Live Mode)

| Section | Duration | Notes |
|---------|----------|-------|
| Opening | 1 min | Set the stage |
| Interface walkthrough | 1 min | Before submitting |
| Steps 1–5 (Orchestrator → Video) | 3 min | Foundational agents |
| Step 6 (Writer) | 2 min | Let them read the article |
| Steps 7–9 (Fact-Check → Compliance) | 3 min | Security gate + compliance gate |
| Steps 10–12 (SEO → Translation) | 2 min | Optimization agents |
| Step 13 (Final) | 1 min | Pipeline complete |
| Output recap | 1 min | Quick tab tour |
| Play audio narration | 1 min | **Wow moment #1** — multi-voice Dragon HD |
| Play podcast | 1 min | **Wow moment #2** — two-host podcast |
| PULSE Assist + Ads | 2–3 min | **Wow moment #3** — monetization story |
| Architecture + Strategy | 2 min | The "why" |
| Roadmap + Close | 1 min | Forward-looking |
| **Total** | **~19–20 min** | Adjust by lingering less on steps 10–12 |

---

## Demo Recovery Tips

| Issue | Fix |
|-------|-----|
| App won't start | Check Python venv is activated: `scribbs\Scripts\activate` then `python -m app.main` |
| WebSocket disconnects | Refresh the browser — it auto-reconnects |
| Pipeline stalls | Check the terminal for errors — most common is a timeout, just resubmit |
| Audio won't play | Make sure browser volume is up; Chrome/Edge required (Firefox has limited Speech API) |
| Pipeline nodes don't animate | Hard refresh with Ctrl+Shift+R to clear cached JS/CSS |
