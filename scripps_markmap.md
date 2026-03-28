---
markmap:
  colorFreezeLevel: 2
  maxWidth: 350
  initialExpandLevel: 3
---

# ⚡ PULSE — AI Newsroom Pipeline

## 📡 Story Intake
### 🖥️ Editor Dashboard
- Submit headline & description
- Set priority (🔴 Breaking / 🟡 High / 🟢 Standard)
- Define target audience
- Upload media assets 🎥🎙️
### 🔌 Real-Time Streaming
- WebSocket live updates
- Agent activity feed
- Per-stage status tracking

## 🎬 Editor-in-Chief *(Orchestrator Agent)*
### 📋 Story Triage
- Priority classification
- Content routing
- Resource allocation
### ✅ Final Publish Decision
- Quality gate enforcement
- Cross-agent consensus
- Publish / Hold ruling

## 🔍 Research Bureau *(RAG Agent)*
### 📰 Knowledge Base Search
- Azure AI Search (vector + semantic)
- Historical archive lookup
- Source cross-referencing
### 🧠 LLM Synthesis
- Azure OpenAI GPT-4o
- Contextual background brief
- Key facts extraction

## 🎙️ Audio Desk *(Speech Agent)*
### 🗣️ Transcription
- Azure AI Speech-to-Text
- Speaker diarization
- Timestamp alignment
### 🔊 Narration
- Text-to-Speech generation
- Newscast-formal voice style
- Multi-language support

## 🎥 Video Analysis *(Video Agent)*
### 🎞️ Scene Intelligence
- Azure Video Indexer
- Scene & shot detection
- Timeline segmentation
### 👤 Visual Recognition
- Face identification
- On-screen text OCR
- Content moderation flags

## ✍️ Newsroom Writer *(Writer Agent)*
### 📝 Article Drafting
- Broadcast-quality copy
- Integrates research + transcripts + video
- AP Style compliance
### 📸 Image Generation
- DALL·E hero images
- Story-relevant visuals
- Brand-safe outputs

## 🌍 Translation Desk *(Translation Agent)*
### 🇪🇸 Spanish
### 🇫🇷 French
### 🇩🇪 German
### 🌐 Scalable — add any language on demand

## ✔️ Fact-Check Desk *(Fact-Checker Agent)*
### 🔎 Claim Extraction
- Every assertion identified
- Source attribution
### ⚖️ Verification
- Cross-reference knowledge base
- Confidence scoring
- Flag unverified claims

## 📈 Digital Optimization *(SEO Agent)*
### 🏷️ SEO
- Headline variants
- Meta descriptions
- Keyword strategy
### 📱 Social Media
- Platform-specific copy
- Hashtag recommendations
- Engagement optimization

## 🛡️ Standards & Compliance
### 📜 FCC Review
- Broadcast regulation check
- Decency standards
### ⚖️ Legal Review
- Libel / defamation scan
- Copyright clearance
### 📏 Editorial Policy
- E.W. Scripps brand guidelines
- Bias detection
- Tone & accuracy audit

## 🔒 Security Guard Agent *(Content Safety + Audit Trail)*
### 🛡️ Inbound Security Scan
- Prompt injection / jailbreak detection
- PII scanning (SSN, credit cards, emails, phones)
- Harmful content detection
- Data classification (PUBLIC / INTERNAL / CONFIDENTIAL)
- **Real-time Azure AI Content Safety API** (Hate, SelfHarm, Sexual, Violence)
- Category severity scores returned per scan
### 🛡️ Outbound Security Scan
- Scans all generated content before publication
- Article, podcast, SEO, translations all checked
- PII leakage prevention in AI-generated text
- Content moderation for broadcast safety
### 📋 LangSmith Observability
- **LangSmith API** for real-time trace & run analytics
- Every agent run logged with tokens, latency, status
- Historical data: 7 / 15 / 30 day windows
- Agent distribution, success rates, error tracking
### 📊 Security & Observability Dashboard
- **Standalone full-screen overlay** (separate from article workflow)
- 6 KPI cards: Runs, Success Rate, Tokens, Latency, Threats, P95
- **Nightingale Rose Chart** — Agent run distribution
- **Radar Chart** — Agent reliability (success rate + volume)
- **Stacked Bar Chart** — Daily pipeline activity (success/fail)
- **Area Chart** — Token consumption trend
- Error log with counts
- Content Safety stats (session threats, PII, status)
- 7 / 15 / 30 day toggle
### 🏗️ Pipeline Integration
- Security agent wraps entire pipeline (entry + exit)
- Runs after orchestrator triage (inbound)
- Runs before final decision (outbound)
- Compliance rejection still goes through outbound scan

## 📺 AI Anchor *(Azure Avatar)*
### 🧑‍💼 Virtual News Presenter
- Character: meg (formal)
- Newscast-formal delivery
- Real-time lip sync (visemes)
### 🎤 Live Presentation
- WebRTC video stream
- Teleprompter integration
- On-demand script reading

## 💬 PULSE Assist *(Q&A Chat)*
### 🤖 Contextual AI Chat
- Story-aware Q&A
- Voice input (mic → STT)
- TTS voice responses (voice questions only)
- Stop voice playback control
### 🌦️ Weather Forecasts
- Azure Maps 7-day forecast
- GPS auto-detect location
- Severe weather alerts
### 🚗 Traffic & Routes
- Real-time traffic conditions
- Azure Maps route engine
- Delay severity scoring
### 🏪 Store Locator
- AI-driven search queries (LLM picks stores)
- Contextual to user's question
- Category label from LLM
- Distance & contact info

## 💰 Ad Monetization Engine
### 🤖 AI Ad Placement Agent
- GPT-4.1 decides when to show ads
- Evaluates question + answer + headline context
- Up to 3 ads per response (auto-rotates)
- No hardcoded rules or intervals
- Returns show/don't-show + best ad IDs
### 📋 JSON-Driven Ad Config
- Enable/disable toggle
- Session deduplication
- 19 sponsor ads across categories
### 🎯 Contextual Signals
- Story headline analysis
- User question intent
- Bot answer text analysis
- Response type (weather/traffic/stores/general)
- Emotional sensitivity filtering
### 📦 Ad Categories (19 sponsors)
- 🌪️ Emergency: Home Depot, Red Cross, Nestlé, State Farm
- ⛅ Weather: Weather Channel, AcuRite
- 🚗 Traffic: Waze, GEICO, GasBuddy
- 🛒 Stores: Instacart, DoorDash
- 💼 Jobs: Indeed
- 💊 Health: CVS
- 🎓 Education: Coursera
- 🔒 Safety: SimpliSafe
- 🏦 Community: Bank of America
- ✈️ Travel: KAYAK
- 📊 Finance: NerdWallet
- ☁️ Default: AWS
### 🎨 Native Ad Banner UX
- Fixed banner above input (always visible)
- Multi-ad auto-rotation (4s interval)
- Dot indicators for manual navigation
- Pause on hover
- Branded CTA buttons
- Fade-in animation
