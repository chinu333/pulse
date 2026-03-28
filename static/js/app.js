/* ============================================================
   PULSE — Newsroom AI Orchestrator
   Frontend Application
   ============================================================ */
(function () {
    "use strict";

    const API_BASE = "";

    // ── SVG icons for submit button ─────────────────────────
    const SUBMIT_SVG = `<svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="18" cy="18" r="17" stroke="#3b82f6" stroke-width="2"/>
        <path d="M14 10l10 8-10 8V10z" fill="#3b82f6"/>
    </svg>`;

    const SPINNER_SVG = `<svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="18" cy="18" r="15" stroke="#2a2e3f" stroke-width="3"/>
        <path d="M18 3a15 15 0 0 1 15 15" stroke="#3b82f6" stroke-width="3" stroke-linecap="round"/>
    </svg>`;

    // ── Agent constants ─────────────────────────────────────
    const AGENT_ICONS = {
        orchestrator: "fa-user-tie",
        security: "fa-shield-halved",
        researcher: "fa-magnifying-glass",
        speech: "fa-headphones",
        video: "fa-video",
        writer: "fa-pen-nib",
        image_generator: "fa-image",
        podcast: "fa-podcast",
        translator: "fa-language",
        fact_checker: "fa-check-double",
        optimizer: "fa-chart-line",
        compliance: "fa-shield-halved",
        security_outbound: "fa-shield-halved",
    };

    const AGENT_NAMES = {
        orchestrator: "Orchestrator",
        security: "Content Safety",
        researcher: "Researcher",
        speech: "Speech",
        video: "Video",
        writer: "Writer",
        image_generator: "Image Gen",
        podcast: "Podcast",
        translator: "Translator",
        fact_checker: "Fact-Checker",
        optimizer: "SEO",
        compliance: "Compliance",
        security_outbound: "Security and Brand",
    };

    const STATUS_TO_AGENT = {
        incoming: "orchestrator",
        security_scan: "security",
        researching: "researcher",
        transcribing: "speech",
        video_analysis: "video",
        writing: "writer",
        generating_image: "image_generator",
        generating_podcast: "podcast",
        translating: "translator",
        fact_checking: "fact_checker",
        optimizing: "optimizer",
        compliance_review: "compliance",
        ready_to_publish: "orchestrator",
    };

    const AGENT_ORDER = [
        "orchestrator", "security", "researcher", "speech", "video", "writer",
        /* "image_generator", */  // Disabled per CIO feedback
        "fact_checker",
        "security_outbound", "compliance", "optimizer", "podcast", "translator",
    ];

    const SAMPLES = [
        { headline: "Breaking: Major Hurricane Approaching Gulf Coast", priority: "breaking", audience: "general" },
        { headline: "City Council Approves $50M Downtown Revitalization Plan", priority: "high", audience: "local" },
        { headline: "Tech Giant Announces 2,000 New Jobs in Ohio Valley", priority: "medium", audience: "general" },
        { headline: "Investigation: Water Quality Concerns in Rural Schools", priority: "high", audience: "investigative" },
    ];

    // ── DOM refs ─────────────────────────────────────────────
    const storyForm    = document.getElementById("storyForm");
    const headlineInput = document.getElementById("headline");
    const descInput    = document.getElementById("description");
    const prioritySelect = document.getElementById("priority");
    const audienceSelect = document.getElementById("audience");
    const submitBtn    = document.getElementById("submitBtn");
    const sampleList   = document.getElementById("sampleList");
    const activityFeed = document.getElementById("activityFeed");
    const clearFeedBtn = document.getElementById("clearFeedBtn");

    // Image upload refs
    const imageDropZone   = document.getElementById("imageDropZone");
    const imageFileInput  = document.getElementById("imageFileInput");
    const uploadPlaceholder = document.getElementById("uploadPlaceholder");
    const uploadPreview   = document.getElementById("uploadPreview");
    const previewImg      = document.getElementById("previewImg");
    const removeImgBtn    = document.getElementById("removeImgBtn");
    const uploadAnalyzing = document.getElementById("uploadAnalyzing");

    let currentStoryId = null;
    let ws = null;
    let pipelineFinished = false;
    let pendingImageBase64 = null;
    let pendingImageMime = null;

    // ── Init ────────────────────────────────────────────────
    function init() {
        renderSampleStories();
        setupEventListeners();
        connectWebSocket();
        // Pre-load browser voices (Chrome fires event async)
        if (window.speechSynthesis) {
            window.speechSynthesis.getVoices();
            window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
        }
    }

    function renderSampleStories() {
        sampleList.innerHTML = SAMPLES.map((s, i) => `
            <div class="sample-story" data-idx="${i}">
                <div class="story-title">
                    <span class="priority-dot ${s.priority}"></span> ${s.headline}
                </div>
                <div class="story-meta">
                    <span>${s.priority.toUpperCase()}</span>
                    <span>${s.audience}</span>
                </div>
            </div>
        `).join("");
    }

    function setupEventListeners() {
        storyForm.addEventListener("submit", handleSubmit);
        clearFeedBtn.addEventListener("click", clearFeed);

        // Sample story click
        sampleList.addEventListener("click", (e) => {
            const card = e.target.closest(".sample-story");
            if (!card) return;
            const idx = parseInt(card.dataset.idx);
            const s = SAMPLES[idx];
            headlineInput.value = s.headline;
            descInput.value = "";
            prioritySelect.value = s.priority;
            audienceSelect.value = s.audience;
        });

        // Set submit button SVG
        submitBtn.innerHTML = SUBMIT_SVG;

        // ── Image upload events ─────────────────────────────
        imageDropZone.addEventListener("click", () => imageFileInput.click());
        imageFileInput.addEventListener("change", handleImageSelected);
        removeImgBtn.addEventListener("click", (e) => { e.stopPropagation(); clearUploadedImage(); });

        // Drag & drop
        imageDropZone.addEventListener("dragover", (e) => { e.preventDefault(); imageDropZone.classList.add("drag-over"); });
        imageDropZone.addEventListener("dragleave", () => imageDropZone.classList.remove("drag-over"));
        imageDropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            imageDropZone.classList.remove("drag-over");
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith("image/")) processImageFile(file);
        });

        // Tab switching
        document.querySelectorAll(".tab").forEach(tab => {
            tab.addEventListener("click", () => {
                document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
                document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
                tab.classList.add("active");
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
            });
        });

        // Step approval banner buttons
        document.getElementById("stepContinueBtn").addEventListener("click", onStepBtnClick);
        document.getElementById("stepEndBtn").addEventListener("click", onEndPipeline);
    }

    // ── WebSocket ────────────────────────────────────────────
    function connectWebSocket() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${proto}//${location.host}/ws`);

        ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.story_id !== currentStoryId) return;
            handleWsMessage(data);
        };

        ws.onclose = () => setTimeout(connectWebSocket, 2000);
        ws.onerror = () => ws.close();
    }

    function handleWsMessage(data) {
        switch (data.type) {
            case "agent_start":
                activatePipelineNode(data.agent);
                addFeedItem(data.agent, `${AGENT_NAMES[data.agent] || data.agent} started`);
                break;
            case "agent_message":
                addFeedItem(data.agent, data.message?.content || "Processing…");
                break;
            case "step_complete":
                markAgentDone(data.completed_agent);
                addFeedItem(data.completed_agent, `\u2705 ${data.completed_agent_display} complete`);
                fetchStoryResults();
                if (AGENT_TAB_MAP[data.completed_agent]) switchTab(AGENT_TAB_MAP[data.completed_agent]);
                setTimeout(() => showStepModal(data), 500);
                break;
            case "pipeline_complete":
                completePipeline();
                addFeedItem("orchestrator", "\u2705 Pipeline complete!");
                fetchStoryResults();
                resetSubmitBtn();
                switchTab("article");
                setTimeout(() => showFinalModal(), 500);
                break;
            case "pipeline_error":
                addFeedItem("orchestrator", `\u274C Error: ${data.error}`);
                resetSubmitBtn();
                hideStepModal();
                break;
        }
    }

    // ── Submit ───────────────────────────────────────────────
    async function handleSubmit(e) {
        e.preventDefault();

        const headline = headlineInput.value.trim();
        if (!headline) return;

        // Stop any active narration / podcast playback
        if (isNarrating) stopNarration();
        if (isPodcastPlaying) stopPodcast();

        resetPipeline();

        submitBtn.disabled = true;
        submitBtn.classList.add("btn-loading");
        submitBtn.innerHTML = SPINNER_SVG;

        try {
            const res = await fetch(`${API_BASE}/api/stories`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    headline,
                    description: descInput.value.trim(),
                    priority: prioritySelect.value,
                    target_audience: audienceSelect.value,
                }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const result = await res.json();
            currentStoryId = result.story_id;
            addFeedItem("orchestrator", `Story submitted: ${headline}`);
        } catch (err) {
            addFeedItem("orchestrator", `❌ Submit failed: ${err.message}`);
            resetSubmitBtn();
        }
    }

    // ── Fetch final results ─────────────────────────────────
    async function fetchStoryResults() {
        if (!currentStoryId) return;
        try {
            const res = await fetch(`${API_BASE}/api/stories/${currentStoryId}`);
            if (!res.ok) return;
            const data = await res.json();
            renderArticle(data);
            renderSpeech(data);
            renderVideo(data);
            renderTranslation(data);
            renderImage(data);
            renderPodcast(data);
            renderSEO(data);
            renderFactCheck(data);
            renderCompliance(data);
        } catch (err) {
            console.error("Failed to fetch results:", err);
        }
    }

    function resetSubmitBtn() {
        submitBtn.disabled = false;
        submitBtn.classList.remove("btn-loading");
        submitBtn.innerHTML = SUBMIT_SVG;
    }

    // ── Image Upload & Analysis ─────────────────────────────

    function handleImageSelected(e) {
        const file = e.target.files[0];
        if (file && file.type.startsWith("image/")) processImageFile(file);
    }

    function processImageFile(file) {
        const reader = new FileReader();
        reader.onload = async () => {
            const dataUrl = reader.result;                       // data:image/jpeg;base64,...
            const parts = dataUrl.split(",");
            const base64 = parts[1];
            const mime = file.type || "image/jpeg";

            // Show preview
            previewImg.src = dataUrl;
            uploadPlaceholder.classList.add("hidden");
            uploadPreview.classList.remove("hidden");
            uploadAnalyzing.classList.add("hidden");

            pendingImageBase64 = base64;
            pendingImageMime = mime;

            // Auto-analyze
            await analyzeUploadedImage(base64, mime);
        };
        reader.readAsDataURL(file);
    }

    async function analyzeUploadedImage(base64, mime) {
        // Show analyzing state
        uploadPreview.classList.add("hidden");
        uploadAnalyzing.classList.remove("hidden");
        addFeedItem("orchestrator", "📷 Analyzing uploaded image with GPT-4.1 vision…");

        try {
            const res = await fetch(`${API_BASE}/api/analyze-image`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image_base64: base64, mime_type: mime }),
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const result = await res.json();

            // Populate form fields
            headlineInput.value = result.headline || "";
            descInput.value = result.description || "";

            // Show preview again
            uploadAnalyzing.classList.add("hidden");
            uploadPreview.classList.remove("hidden");

            addFeedItem("orchestrator", `✅ Image analyzed — headline: "${result.headline}"`);
        } catch (err) {
            addFeedItem("orchestrator", `❌ Image analysis failed: ${err.message}`);
            uploadAnalyzing.classList.add("hidden");
            uploadPreview.classList.remove("hidden");
        }
    }

    function clearUploadedImage() {
        pendingImageBase64 = null;
        pendingImageMime = null;
        imageFileInput.value = "";
        previewImg.src = "";
        uploadPreview.classList.add("hidden");
        uploadAnalyzing.classList.add("hidden");
        uploadPlaceholder.classList.remove("hidden");
    }

    // ── Step-by-Step Flow ───────────────────────────────────

    const AGENT_TAB_MAP = {
        writer: "article",
        speech: "audio",
        video: "video",
        translator: "translation",
        image_generator: "image",
        podcast: "podcast",
        optimizer: "seo",
        fact_checker: "factcheck",
        compliance: "compliance",
    };

    function switchTab(tabName) {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        const tabBtn = document.querySelector(`.tab[data-tab="${tabName}"]`);
        if (tabBtn) tabBtn.classList.add("active");
        const tabContent = document.getElementById(`tab-${tabName}`);
        if (tabContent) tabContent.classList.add("active");
    }

    function markAgentDone(agentRole) {
        const node = document.querySelector(`.pipeline-node[data-agent="${agentRole}"]`);
        if (node) {
            node.classList.remove("active");
            node.classList.add("done");
        }
        const idx = AGENT_ORDER.indexOf(agentRole);
        if (idx >= 0) {
            const connectors = document.querySelectorAll(".pipeline-connector");
            if (connectors[idx]) connectors[idx].classList.add("done");
        }
    }

    function showStepModal(data) {
        const banner   = document.getElementById("stepBanner");
        const icon     = document.getElementById("stepBannerIcon");
        const title    = document.getElementById("stepBannerTitle");
        const fill     = document.getElementById("stepProgressFill");
        const progText = document.getElementById("stepProgressText");
        const summary  = document.getElementById("stepBannerSummary");
        const btn      = document.getElementById("stepContinueBtn");
        const btnText  = document.getElementById("stepBtnText");
        const btnIcon  = document.getElementById("stepBtnIcon");
        const endBtn   = document.getElementById("stepEndBtn");

        const agentIcon = AGENT_ICONS[data.completed_agent] || "fa-check";
        icon.innerHTML = `<i class="fas ${agentIcon}"></i>`;
        title.textContent = `\u2705 ${data.completed_agent_display} Complete`;

        fill.style.width = `${data.progress}%`;
        progText.textContent = `Step ${data.step_idx + 1} of ${data.total_steps}`;
        summary.textContent = data.summary || "Review the output, then continue.";

        const nextIcon = AGENT_ICONS[data.next_agent] || "fa-arrow-right";
        btnText.innerHTML = `Next: <strong>${data.next_agent_display}</strong>`;
        btnIcon.className = `fas ${nextIcon}`;
        btn.className = "step-btn-continue";
        btn.disabled = false;
        endBtn.style.display = "";
        pipelineFinished = false;

        banner.classList.remove("hidden");
    }

    function showFinalModal() {
        const banner   = document.getElementById("stepBanner");
        const icon     = document.getElementById("stepBannerIcon");
        const title    = document.getElementById("stepBannerTitle");
        const fill     = document.getElementById("stepProgressFill");
        const progText = document.getElementById("stepProgressText");
        const summary  = document.getElementById("stepBannerSummary");
        const btn      = document.getElementById("stepContinueBtn");
        const btnText  = document.getElementById("stepBtnText");
        const btnIcon  = document.getElementById("stepBtnIcon");
        const endBtn   = document.getElementById("stepEndBtn");

        icon.innerHTML = `<i class="fas fa-flag-checkered"></i>`;
        title.textContent = "\u2705 Pipeline Complete!";

        fill.style.width = "100%";
        progText.textContent = `All ${AGENT_ORDER.length + 1} steps completed`;
        summary.textContent = "All agents finished. Review results across all tabs.";

        btnText.textContent = "Dismiss";
        btnIcon.className = "fas fa-check";
        btn.className = "step-btn-continue final";
        btn.disabled = false;
        endBtn.style.display = "none";
        pipelineFinished = true;

        banner.classList.remove("hidden");
    }

    function hideStepModal() {
        document.getElementById("stepBanner").classList.add("hidden");
    }

    function onStepBtnClick() {
        if (pipelineFinished) {
            hideStepModal();
            pipelineFinished = false;
            return;
        }
        continueStep();
    }

    async function continueStep() {
        if (!currentStoryId) return;
        const btn     = document.getElementById("stepContinueBtn");
        const btnText = document.getElementById("stepBtnText");
        btn.disabled = true;
        btnText.textContent = "Running\u2026";
        hideStepModal();

        try {
            const res = await fetch(`${API_BASE}/api/stories/${currentStoryId}/continue`, {
                method: "POST",
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
        } catch (err) {
            addFeedItem("orchestrator", `\u274C Continue failed: ${err.message}`);
            resetSubmitBtn();
        }
    }

    async function onEndPipeline() {
        if (!currentStoryId) return;
        hideStepModal();
        addFeedItem("orchestrator", "\u23F9 Pipeline ended by user");

        // Mark current completed nodes as done, stop further execution
        try {
            await fetch(`${API_BASE}/api/stories/${currentStoryId}/end`, { method: "POST" });
        } catch (_) { /* best-effort */ }

        resetSubmitBtn();
    }

    // ── Pipeline Nodes ──────────────────────────────────────
    function resetPipeline() {
        document.querySelectorAll(".pipeline-node").forEach(n => {
            n.classList.remove("active", "done");
        });
        document.querySelectorAll(".pipeline-connector").forEach(c => {
            c.classList.remove("done");
        });
        // Clear uploaded image
        clearUploadedImage();
        // Reset output panels
        [
            "articlePlaceholder", "speechPlaceholder", "videoPlaceholder",
            "translationPlaceholder", "imagePlaceholder", "podcastPlaceholder",
            "seoPlaceholder", "factPlaceholder", "compliancePlaceholder",
        ].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove("hidden");
        });
        [
            "articleOutput", "speechOutput", "videoOutput",
            "translationOutput", "imageOutput", "podcastOutput",
            "seoOutput", "factOutput", "complianceOutput",
        ].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add("hidden");
        });
    }

    function activatePipelineNode(agentRole) {
        const nodes = document.querySelectorAll(".pipeline-node");
        const connectors = document.querySelectorAll(".pipeline-connector");
        const idx = AGENT_ORDER.indexOf(agentRole);
        if (idx < 0) return;

        nodes.forEach((node, i) => {
            const nodeAgent = node.dataset.agent;
            const nodeIdx = AGENT_ORDER.indexOf(nodeAgent);
            if (nodeIdx < idx) {
                node.classList.remove("active");
                node.classList.add("done");
            } else if (nodeIdx === idx) {
                node.classList.remove("done");
                node.classList.add("active");
            } else {
                node.classList.remove("active", "done");
            }
        });

        connectors.forEach((c, i) => {
            if (i < idx) c.classList.add("done");
            else c.classList.remove("done");
        });
    }

    function completePipeline() {
        document.querySelectorAll(".pipeline-node").forEach(n => {
            n.classList.remove("active");
            n.classList.add("done");
        });
        document.querySelectorAll(".pipeline-connector").forEach(c => {
            c.classList.add("done");
        });
    }

    // ── Activity Feed ────────────────────────────────────────
    function addFeedItem(agent, text) {
        const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        const div = document.createElement("div");
        div.className = "feed-item";
        div.innerHTML = `
            <span class="feed-time">${time}</span>
            <span class="feed-agent">${AGENT_NAMES[agent] || agent}</span>
            <span class="feed-text">${escapeHtml(text).substring(0, 120)}</span>
        `;
        activityFeed.prepend(div);
        // Keep max 50 items
        while (activityFeed.children.length > 50) activityFeed.lastChild.remove();
    }

    function clearFeed() { activityFeed.innerHTML = ""; }

    function escapeHtml(str) {
        const d = document.createElement("div");
        d.textContent = str;
        return d.innerHTML;
    }

    // ── Render Article ──────────────────────────────────────
    function renderArticle(data) {
        const draft = data.draft;
        if (!draft) return;

        document.getElementById("articlePlaceholder").classList.add("hidden");
        const out = document.getElementById("articleOutput");
        out.classList.remove("hidden");

        document.getElementById("articleHeadline").textContent = draft.headline || "";
        document.getElementById("articleSubheadline").textContent = draft.subheadline || "";
        document.getElementById("articleWordCount").innerHTML = `<i class="fas fa-font"></i> ${draft.word_count || 0} words`;
        document.getElementById("articleTone").innerHTML = `<i class="fas fa-palette"></i> ${draft.tone || "neutral"}`;
        document.getElementById("articleBody").textContent = draft.body || "";

        const quotesEl = document.getElementById("articleQuotes");
        quotesEl.innerHTML = (draft.quotes || []).map(q =>
            `<div class="quote-block">${escapeHtml(q)}</div>`
        ).join("");
    }

    // ── Render Speech ───────────────────────────────────────
    function renderSpeech(data) {
        const sp = data.speech;
        if (!sp) return;

        document.getElementById("speechPlaceholder").classList.add("hidden");
        const out = document.getElementById("speechOutput");
        out.classList.remove("hidden");

        document.getElementById("speechDuration").textContent = `${(sp.duration_seconds || 0).toFixed(1)}s`;
        document.getElementById("speechConfidence").textContent = `${((sp.confidence || 0) * 100).toFixed(0)}%`;
        document.getElementById("speechLanguage").textContent = sp.language_detected || "—";

        // Render transcript — use script lines if available for speaker-labeled view
        const scriptLines = sp.script || [];
        const transcriptEl = document.getElementById("speechTranscript");
        if (scriptLines.length > 0) {
            transcriptEl.innerHTML = scriptLines.map(line =>
                `<div class="script-line" style="margin-bottom:6px;">` +
                `<span class="speaker-tag" style="font-weight:600;color:var(--accent);margin-right:6px;">${escapeHtml(line.speaker)}:</span>` +
                `<span>${escapeHtml(line.text)}</span></div>`
            ).join("");
        } else {
            transcriptEl.textContent = sp.transcript || "No transcript available.";
        }

        const speakers = sp.speakers || [];
        document.getElementById("speechSpeakers").innerHTML = speakers.length
            ? speakers.map(s => `
                <div class="speaker-chip">
                    <i class="fas fa-user-circle" style="color:var(--accent);font-size:18px;"></i>
                    <div>
                        <div class="speaker-name">${escapeHtml(s.name || s.id || 'Unknown')}</div>
                        <div class="speaker-meta">${s.segments || 0} segments · ${(s.duration || 0).toFixed(1)}s</div>
                    </div>
                </div>
            `).join("")
            : '<div style="color:var(--text-dim);font-size:12px;">No speakers detected</div>';

        // Set up narration player
        document.getElementById("narrationVoice").textContent = "Multi-voice Dragon HD";
        document.getElementById("narrationStatus").textContent = "Ready to play";
        setupNarrationPlayer(sp);
    }

    // ── Narration Player (Azure Dragon HD Omni TTS — multi-voice) ───────
    let narrationAudio = null;
    let isNarrating = false;
    let narrationScript = [];
    let narrationLineIdx = 0;
    let narrationAudioCache = [];

    // Distinct voices for speech/narration speakers
    const NARRATION_VOICES = {
        "Anchor":           "en-us-andrew:DragonHDOmniLatestNeural",   // male
        "Field Reporter":   "en-us-ava:DragonHDOmniLatestNeural",      // female
        "Official Source":  "en-us-brian:DragonHDOmniLatestNeural",     // male (different)
    };
    const DEFAULT_NARRATION_VOICE = "en-us-ava:DragonHDOmniLatestNeural";

    function _getNarrationVoice(speaker) {
        return NARRATION_VOICES[speaker] || DEFAULT_NARRATION_VOICE;
    }

    function setupNarrationPlayer(sp) {
        narrationScript = (sp && sp.script) || [];
        narrationLineIdx = 0;
        narrationAudioCache = [];

        const playBtn = document.getElementById("narrationPlayBtn");
        const stopBtn = document.getElementById("narrationStopBtn");
        if (!playBtn || !stopBtn) return;

        const newPlay = playBtn.cloneNode(true);
        playBtn.parentNode.replaceChild(newPlay, playBtn);
        const newStop = stopBtn.cloneNode(true);
        stopBtn.parentNode.replaceChild(newStop, stopBtn);

        newPlay.addEventListener("click", toggleNarration);
        newStop.addEventListener("click", stopNarration);
    }

    async function toggleNarration() {
        // Pause / resume
        if (narrationAudio && isNarrating) {
            if (narrationAudio.paused) {
                narrationAudio.play();
                setNarrationState("playing");
            } else {
                narrationAudio.pause();
                setNarrationState("paused");
            }
            return;
        }

        // If we have a script, play line-by-line with per-speaker voices
        if (narrationScript.length > 0) {
            narrationLineIdx = 0;
            isNarrating = true;
            setNarrationState("loading");
            document.getElementById("narrationVoice").textContent = "Multi-voice Dragon HD";
            playNextNarrationLine();
            return;
        }

        // Fallback: no script — play entire article as single voice
        const text = _getNarrationFallbackText();
        if (!text || text === "No article available.") {
            setNarrationState("error");
            return;
        }

        setNarrationState("loading");
        document.getElementById("narrationVoice").textContent = "Dragon HD Omni";

        try {
            const res = await fetch(`${API_BASE}/api/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text }),
            });
            if (!res.ok) {
                const errBody = await res.text().catch(() => "(no body)");
                console.error(`[TTS] Fallback narration HTTP ${res.status} — response body:`, errBody);
                throw new Error(`HTTP ${res.status}: ${errBody}`);
            }
            const data = await res.json();
            const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
            const blob = new Blob([audioBytes], { type: "audio/mpeg" });
            const url = URL.createObjectURL(blob);

            narrationAudio = new Audio(url);
            isNarrating = true;
            narrationAudio.onplay = () => setNarrationState("playing");
            narrationAudio.onpause = () => { if (!narrationAudio.ended) setNarrationState("paused"); };
            narrationAudio.onended = () => {
                setNarrationState("ended");
                URL.revokeObjectURL(url);
                narrationAudio = null;
                isNarrating = false;
            };
            narrationAudio.onerror = () => setNarrationState("error");
            narrationAudio.play();
        } catch (err) {
            console.error("TTS narration error:", err);
            setNarrationState("error");
        }
    }

    function _getNarrationFallbackText() {
        const h = document.getElementById("articleHeadline")?.textContent || "";
        const b = document.getElementById("articleBody")?.textContent || "";
        if (h && b) return `${h}. ${b}`;
        return document.getElementById("speechTranscript")?.textContent || "No article available.";
    }

    async function playNextNarrationLine() {
        if (narrationLineIdx >= narrationScript.length || !isNarrating) {
            isNarrating = false;
            narrationAudio = null;
            setNarrationState("ended");
            return;
        }

        const line = narrationScript[narrationLineIdx];
        const voice = _getNarrationVoice(line.speaker);

        // Update voice label to show who's speaking
        const label = document.getElementById("narrationVoice");
        if (label) label.textContent = `${line.speaker} speaking`;

        // Highlight current line in the transcript
        const scriptLines = document.querySelectorAll("#speechTranscript .script-line");
        scriptLines.forEach((el, i) => {
            el.style.opacity = i === narrationLineIdx ? "1" : "0.4";
        });

        try {
            let blob = narrationAudioCache[narrationLineIdx];
            if (!blob) {
                setNarrationState("loading");
                console.log(`[TTS] Requesting narration line ${narrationLineIdx}: voice=${voice}, text_len=${line.text.length}`);
                const res = await fetch(`${API_BASE}/api/tts`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: line.text, voice }),
                });
                if (!res.ok) {
                    const errBody = await res.text().catch(() => "(no body)");
                    console.error(`[TTS] HTTP ${res.status} — response body:`, errBody);
                    throw new Error(`HTTP ${res.status}: ${errBody}`);
                }
                const data = await res.json();
                const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
                blob = new Blob([audioBytes], { type: "audio/mpeg" });
                narrationAudioCache[narrationLineIdx] = blob;

                // Pre-fetch next line
                if (narrationLineIdx + 1 < narrationScript.length && !narrationAudioCache[narrationLineIdx + 1]) {
                    _prefetchNarrationLine(narrationLineIdx + 1);
                }
            }

            const url = URL.createObjectURL(blob);
            narrationAudio = new Audio(url);
            narrationAudio.onplay = () => setNarrationState("playing");
            narrationAudio.onended = () => {
                URL.revokeObjectURL(url);
                narrationLineIdx++;
                playNextNarrationLine();
            };
            narrationAudio.onerror = () => {
                isNarrating = false;
                setNarrationState("error");
            };
            narrationAudio.play();
        } catch (err) {
            console.error("Narration TTS error:", err);
            isNarrating = false;
            setNarrationState("error");
        }
    }

    async function _prefetchNarrationLine(idx) {
        if (idx >= narrationScript.length || narrationAudioCache[idx]) return;
        try {
            const voice = _getNarrationVoice(narrationScript[idx].speaker);
            const res = await fetch(`${API_BASE}/api/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: narrationScript[idx].text, voice }),
            });
            if (!res.ok) return;
            const data = await res.json();
            const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
            narrationAudioCache[idx] = new Blob([audioBytes], { type: "audio/mpeg" });
        } catch (_) { /* silent */ }
    }

    function stopNarration() {
        if (narrationAudio) {
            narrationAudio.pause();
            narrationAudio.currentTime = 0;
            narrationAudio = null;
        }
        isNarrating = false;
        // Reset line highlights
        document.querySelectorAll("#speechTranscript .script-line").forEach(el => { el.style.opacity = "1"; });
        setNarrationState("stopped");
    }

    function setNarrationState(state) {
        const player = document.getElementById("narrationPlayer");
        const icon   = document.getElementById("narrationPlayIcon");
        const btn    = document.getElementById("narrationPlayBtn");
        const status = document.getElementById("narrationStatus");
        if (!player || !icon || !status) return;
        switch (state) {
            case "loading":
                isNarrating = true; player.classList.add("playing"); btn.classList.add("playing");
                icon.className = "fas fa-spinner fa-spin"; status.textContent = "Generating audio…"; break;
            case "playing":
                isNarrating = true; player.classList.add("playing"); btn.classList.add("playing");
                icon.className = "fas fa-pause"; status.textContent = "\u25B6 Playing narration…"; break;
            case "paused":
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "\u23F8 Paused"; break;
            case "ended":
                isNarrating = false;
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "\u2713 Narration complete"; break;
            case "stopped":
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "Ready to play"; break;
            case "error":
                isNarrating = false; player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "\u26A0 Narration error"; break;
        }
    }

    // ── Render Video ────────────────────────────────────────
    function renderVideo(data) {
        const vid = data.video;
        if (!vid) return;

        document.getElementById("videoPlaceholder").classList.add("hidden");
        document.getElementById("videoOutput").classList.remove("hidden");

        document.getElementById("videoDuration").textContent = `${vid.duration || 0}s`;
        document.getElementById("videoScenes").textContent = (vid.scenes || []).length;
        document.getElementById("videoFaces").textContent = (vid.faces || []).length;

        // Topics
        document.getElementById("videoTopics").innerHTML = (vid.topics || []).map(t =>
            `<span class="video-tag">${escapeHtml(t.name)}<span class="tag-conf">${((t.confidence||0)*100).toFixed(0)}%</span></span>`
        ).join("");

        // Scenes
        document.getElementById("videoSceneList").innerHTML = (vid.scenes || []).map(s =>
            `<div class="scene-row"><span class="scene-time">${s.start} → ${s.end}</span><span class="scene-desc">${escapeHtml(s.description)}</span></div>`
        ).join("");

        // Faces
        document.getElementById("videoFaceList").innerHTML = (vid.faces || []).map(f =>
            `<div class="face-row"><div class="face-icon"><i class="fas fa-user"></i></div><span class="face-name">${escapeHtml(f.name)}</span><span class="face-title">${escapeHtml(f.title||'')}</span><span class="face-count">${f.appearances||0}×</span></div>`
        ).join("");

        // OCR
        document.getElementById("videoOcr").innerHTML = (vid.ocr_text || []).map(t =>
            `<div class="ocr-line">${escapeHtml(t)}</div>`
        ).join("");

        // Moderation
        const mod = vid.content_moderation || {};
        document.getElementById("videoModeration").innerHTML = Object.entries(mod).map(([k, v]) =>
            `<span class="mod-badge ${v ? 'fail' : 'pass'}"><i class="fas ${v ? 'fa-xmark' : 'fa-check'}"></i> ${k.replace('is_', '')}</span>`
        ).join("");
    }

    // ── Render Translation ──────────────────────────────────
    function renderTranslation(data) {
        const tr = data.translation;
        if (!tr) return;

        document.getElementById("translationPlaceholder").classList.add("hidden");
        document.getElementById("translationOutput").classList.remove("hidden");

        const headerEl = document.getElementById("translationHeader");
        headerEl.innerHTML = `
            <span class="meta-badge"><i class="fas fa-globe"></i> Source: ${tr.source_language_name || 'English'}</span>
            <span class="meta-badge"><i class="fas fa-language"></i> ${(tr.target_languages || []).length} languages</span>
        `;

        const cardsEl = document.getElementById("translationCards");
        const translations = tr.translations || {};
        const scores = tr.quality_scores || {};

        cardsEl.innerHTML = Object.entries(translations).map(([code, t]) => `
            <div class="translation-card">
                <div class="translation-card-header">
                    <div>
                        <span class="lang-name">${t.language_name || code}</span>
                        <span class="lang-code">${code}</span>
                    </div>
                    <span class="quality-score">${((scores[code]||0)*100).toFixed(0)}% quality</span>
                </div>
                <div class="translation-card-body">
                    <div class="trans-headline">${escapeHtml(t.headline || '')}</div>
                    <div class="trans-body">${escapeHtml(t.body || '')}</div>
                </div>
            </div>
        `).join("");
    }

    // ── Render Image ────────────────────────────────────────
    function renderImage(data) {
        const img = data.image;
        if (!img) return;

        document.getElementById("imagePlaceholder").classList.add("hidden");
        document.getElementById("imageOutput").classList.remove("hidden");

        document.getElementById("imageAltText").textContent = img.alt_text || "";
        document.getElementById("imagePrompt").textContent = img.prompt_used || "";

        // Build unified thumbnail array: hero + additional variants
        const allImages = [];
        if (img.hero_image_url) {
            allImages.push({
                url: img.hero_image_url,
                alt: img.alt_text || "",
                style: img.style || "Photojournalistic",
                dims: img.dimensions || "1024×1024",
            });
        }
        (img.additional_images || []).forEach(a => {
            allImages.push({
                url: a.url,
                alt: a.alt_text || "",
                style: a.style || "variant",
                dims: "1024×1024",
            });
        });

        const grid = document.getElementById("imageThumbGrid");
        grid.innerHTML = allImages.map((im, i) => `
            <div class="image-thumb-card" onclick="openLightbox('${im.url}', '${escapeHtml(im.style)}', '${escapeHtml(im.dims)}', '${escapeHtml(im.alt)}')">
                <img src="${im.url}" alt="${escapeHtml(im.alt)}" />
                <div class="image-thumb-overlay">
                    <span class="image-thumb-label">${escapeHtml(im.style)}</span>
                    <span class="image-thumb-expand"><i class="fas fa-expand"></i></span>
                </div>
            </div>
        `).join("");

        // Adjust grid columns based on image count
        grid.style.gridTemplateColumns = allImages.length === 1
            ? "1fr" : allImages.length === 2 ? "repeat(2, 1fr)" : "repeat(3, 1fr)";
    }

    // ── Image Lightbox ──────────────────────────────────────
    window.openLightbox = function(url, style, dims, alt) {
        const lb = document.getElementById("imageLightbox");
        document.getElementById("lightboxImg").src = url;
        document.getElementById("lightboxImg").alt = alt;
        document.getElementById("lightboxStyle").textContent = style;
        document.getElementById("lightboxDims").textContent = dims;
        document.getElementById("lightboxAlt").textContent = alt;
        lb.classList.remove("hidden");
    };

    window.closeLightbox = function() {
        document.getElementById("imageLightbox").classList.add("hidden");
        document.getElementById("lightboxImg").src = "";
    };

    // Close lightbox on Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeLightbox();
    });

    // ── Render Podcast ──────────────────────────────────────
    function renderPodcast(data) {
        const pod = data.podcast;
        if (!pod) return;

        document.getElementById("podcastPlaceholder").classList.add("hidden");
        document.getElementById("podcastOutput").classList.remove("hidden");

        document.getElementById("podcastTitle").textContent = pod.episode_title || "";
        document.getElementById("podcastSummary").textContent = pod.episode_summary || "";
        document.getElementById("podcastDuration").textContent = (pod.estimated_duration_minutes || 0).toFixed(1);
        document.getElementById("podcastSegments").textContent = (pod.segments || []).length;
        document.getElementById("podcastHostA").textContent = pod.host_a || "Alex";
        document.getElementById("podcastHostB").textContent = pod.host_b || "Morgan";

        // Segments
        document.getElementById("podcastSegmentList").innerHTML = (pod.segments || []).map(s =>
            `<div class="segment-row"><span class="segment-name">${escapeHtml(s.name)}</span><span class="segment-time">${s.start || ''} · ${s.duration || ''}</span></div>`
        ).join("");

        // Script
        const hostA = (pod.host_a || "Alex").toLowerCase();
        document.getElementById("podcastScript").innerHTML = (pod.script || []).map(line => {
            const isA = (line.speaker || "").toLowerCase() === hostA;
            return `
                <div class="script-line ${isA ? 'host-a' : 'host-b'}">
                    <span class="speaker-tag">${escapeHtml(line.speaker)}</span>
                    <span class="line-text">${escapeHtml(line.text)}</span>
                </div>
            `;
        }).join("");

        // Set up podcast player
        document.getElementById("podcastStatus").textContent = "Ready to play";
        setupPodcastPlayer(pod);
    }

    // ── Podcast Player (Azure Dragon HD Omni TTS) ─────────
    let podcastAudio = null;
    let isPodcastPlaying = false;
    let podcastScript = [];
    let podcastLineIdx = 0;
    let podcastAudioCache = [];  // pre-synthesized audio blobs per line

    // Map podcast host names to distinct Dragon HD Omni voices
    const PODCAST_VOICES = {
        "Alex":    "en-us-andrew:DragonHDOmniLatestNeural",   // male — authoritative anchor
        "Morgan":  "en-us-ava:DragonHDOmniLatestNeural",      // female — conversational co-host
    };
    const DEFAULT_PODCAST_VOICE_A = "en-us-andrew:DragonHDOmniLatestNeural";
    const DEFAULT_PODCAST_VOICE_B = "en-us-ava:DragonHDOmniLatestNeural";

    function _getPodcastVoice(speaker) {
        if (PODCAST_VOICES[speaker]) return PODCAST_VOICES[speaker];
        // For unknown speakers, alternate male/female based on whether they match
        // the first speaker in the script
        const hostA = (podcastScript[0]?.speaker || "").trim();
        return speaker === hostA ? DEFAULT_PODCAST_VOICE_A : DEFAULT_PODCAST_VOICE_B;
    }

    function setupPodcastPlayer(pod) {
        podcastScript = pod.script || [];
        podcastLineIdx = 0;
        podcastAudioCache = [];
        const playBtn = document.getElementById("podcastPlayBtn");
        const stopBtn = document.getElementById("podcastStopBtn");
        if (!playBtn || !stopBtn) return;

        const newPlay = playBtn.cloneNode(true);
        playBtn.parentNode.replaceChild(newPlay, playBtn);
        const newStop = stopBtn.cloneNode(true);
        stopBtn.parentNode.replaceChild(newStop, stopBtn);

        newPlay.addEventListener("click", togglePodcast);
        newStop.addEventListener("click", stopPodcast);
    }

    async function togglePodcast() {
        // Pause / resume
        if (podcastAudio && isPodcastPlaying) {
            if (podcastAudio.paused) {
                podcastAudio.play();
                setPodcastState("playing");
            } else {
                podcastAudio.pause();
                setPodcastState("paused");
            }
            return;
        }
        if (podcastScript.length === 0) return;

        podcastLineIdx = 0;
        isPodcastPlaying = true;
        setPodcastState("loading");
        document.getElementById("podcastVoiceLabel").textContent = "Dragon HD Omni";
        playNextPodcastLine();
    }

    async function playNextPodcastLine() {
        if (podcastLineIdx >= podcastScript.length || !isPodcastPlaying) {
            isPodcastPlaying = false;
            podcastAudio = null;
            setPodcastState("ended");
            return;
        }

        const line = podcastScript[podcastLineIdx];

        // Highlight current line
        const scriptLines = document.querySelectorAll("#podcastScript .script-line");
        scriptLines.forEach((el, i) => {
            el.style.opacity = i === podcastLineIdx ? "1" : "0.4";
        });

        const label = document.getElementById("podcastVoiceLabel");
        if (label) label.textContent = `${line.speaker} speaking`;

        const voice = _getPodcastVoice(line.speaker);

        try {
            // Check cache first
            let blob = podcastAudioCache[podcastLineIdx];
            if (!blob) {
                setPodcastState("loading");
                console.log(`[TTS] Requesting podcast line ${podcastLineIdx}: voice=${voice}, text_len=${line.text.length}`);
                const res = await fetch(`${API_BASE}/api/tts`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: line.text, voice }),
                });
                if (!res.ok) {
                    const errBody = await res.text().catch(() => "(no body)");
                    console.error(`[TTS] Podcast HTTP ${res.status} — response body:`, errBody);
                    throw new Error(`HTTP ${res.status}: ${errBody}`);
                }
                const data = await res.json();
                const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
                blob = new Blob([audioBytes], { type: "audio/mpeg" });
                podcastAudioCache[podcastLineIdx] = blob;

                // Pre-fetch next line in background
                if (podcastLineIdx + 1 < podcastScript.length && !podcastAudioCache[podcastLineIdx + 1]) {
                    prefetchPodcastLine(podcastLineIdx + 1);
                }
            }

            const url = URL.createObjectURL(blob);
            podcastAudio = new Audio(url);
            podcastAudio.onplay = () => setPodcastState("playing");
            podcastAudio.onended = () => {
                URL.revokeObjectURL(url);
                podcastLineIdx++;
                playNextPodcastLine();
            };
            podcastAudio.onerror = () => {
                isPodcastPlaying = false;
                setPodcastState("error");
            };
            podcastAudio.play();
        } catch (err) {
            console.error("Podcast TTS error:", err);
            isPodcastPlaying = false;
            setPodcastState("error");
        }
    }

    async function prefetchPodcastLine(idx) {
        if (idx >= podcastScript.length || podcastAudioCache[idx]) return;
        try {
            const voice = _getPodcastVoice(podcastScript[idx].speaker);
            const res = await fetch(`${API_BASE}/api/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: podcastScript[idx].text, voice }),
            });
            if (!res.ok) return;
            const data = await res.json();
            const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
            podcastAudioCache[idx] = new Blob([audioBytes], { type: "audio/mpeg" });
        } catch (_) { /* silent */ }
    }

    function stopPodcast() {
        if (podcastAudio) {
            podcastAudio.pause();
            podcastAudio.currentTime = 0;
            podcastAudio = null;
        }
        isPodcastPlaying = false;
        podcastLineIdx = 0;
        setPodcastState("stopped");
        document.querySelectorAll("#podcastScript .script-line").forEach(el => el.style.opacity = "1");
    }

    function setPodcastState(state) {
        const player = document.getElementById("podcastPlayer");
        const icon   = document.getElementById("podcastPlayIcon");
        const btn    = document.getElementById("podcastPlayBtn");
        const status = document.getElementById("podcastStatus");
        if (!player || !icon || !status) return;
        switch (state) {
            case "playing":
                player.classList.add("playing"); btn.classList.add("playing");
                icon.className = "fas fa-pause"; status.textContent = "\u25B6 Playing podcast\u2026"; break;
            case "paused":
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "\u23F8 Paused"; break;
            case "ended":
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "\u2713 Episode complete"; break;
            case "stopped":
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "Ready to play"; break;
            case "error":
                player.classList.remove("playing"); btn.classList.remove("playing");
                icon.className = "fas fa-play"; status.textContent = "\u26A0 Playback error"; break;
        }
    }

    // ── Render SEO ──────────────────────────────────────────
    function renderSEO(data) {
        const seo = data.seo;
        if (!seo) return;

        document.getElementById("seoPlaceholder").classList.add("hidden");
        document.getElementById("seoOutput").classList.remove("hidden");

        const score = seo.seo_score || 0;
        document.getElementById("seoScoreLabel").textContent = `${(score * 100).toFixed(0)}%`;
        const ring = document.getElementById("seoRing");
        const offset = 264 - (264 * score);
        ring.style.strokeDashoffset = offset;

        document.getElementById("seoHeadline").textContent = seo.optimized_headline || "";
        document.getElementById("seoMeta").textContent = seo.meta_description || "";

        document.getElementById("seoKeywords").innerHTML = (seo.keywords || []).map(k =>
            `<span class="tag-item">${escapeHtml(k)}</span>`
        ).join("");

        const social = seo.social_copy || {};
        document.getElementById("seoSocial").innerHTML = Object.entries(social).map(([platform, copy]) => `
            <div class="social-copy-item">
                <div class="platform"><i class="fab fa-${platform === 'twitter' ? 'x-twitter' : platform}"></i> ${platform}</div>
                <div class="copy-text">${escapeHtml(copy)}</div>
            </div>
        `).join("");
    }

    // ── Render Fact-Check ───────────────────────────────────
    function renderFactCheck(data) {
        const fc = data.fact_check;
        if (!fc) return;

        document.getElementById("factPlaceholder").classList.add("hidden");
        document.getElementById("factOutput").classList.remove("hidden");

        const score = fc.overall_score || 0;
        document.getElementById("factScoreLabel").textContent = `${(score * 100).toFixed(0)}%`;
        const ring = document.getElementById("factRing");
        const offset = 264 - (264 * score);
        ring.style.strokeDashoffset = offset;
        ring.style.stroke = score >= 0.8 ? "var(--green)" : score >= 0.5 ? "var(--yellow)" : "var(--red)";
        document.getElementById("factScoreLabel").style.color = ring.style.stroke;

        document.getElementById("factVerified").innerHTML = (fc.verified_claims || []).map(c => {
            const st = (c.status || "verified").toLowerCase();
            const icon = st === "flagged" ? "fa-times-circle" : st === "unverified" ? "fa-question-circle" : "fa-check-circle";
            const color = st === "flagged" ? "var(--red)" : st === "unverified" ? "var(--yellow)" : "var(--green)";
            return `<div class="claim-item ${st}"><i class="fas ${icon}" style="color:${color}"></i> ${escapeHtml(c.claim || c.text || JSON.stringify(c))}</div>`;
        }).join("") || '<div style="color:var(--text-dim);font-size:12px;">None</div>';

        document.getElementById("factFlagged").innerHTML = (fc.flagged_issues || []).map(c =>
            `<div class="claim-item flagged"><i class="fas fa-exclamation-triangle" style="color:var(--yellow)"></i> ${escapeHtml(c.issue || c.text || JSON.stringify(c))}</div>`
        ).join("") || '<div style="color:var(--text-dim);font-size:12px;">None</div>';

        document.getElementById("factRecommendation").textContent = fc.recommendation || "";
    }

    // ── Render Compliance ───────────────────────────────────
    function renderCompliance(data) {
        const comp = data.compliance;
        if (!comp) return;

        document.getElementById("compliancePlaceholder").classList.add("hidden");
        document.getElementById("complianceOutput").classList.remove("hidden");

        const badge = document.getElementById("complianceBadge");
        badge.className = `compliance-badge ${comp.approved ? "approved" : "rejected"}`;
        document.getElementById("complianceVerdict").textContent = comp.approved ? "APPROVED" : "FLAGGED";

        document.getElementById("complianceLegal").innerHTML = (comp.legal_flags || []).map(f =>
            `<div class="claim-item issue"><i class="fas fa-gavel" style="color:var(--red)"></i> ${escapeHtml(f)}</div>`
        ).join("") || '<div style="color:var(--text-dim);font-size:12px;">No legal flags</div>';

        document.getElementById("complianceIssues").innerHTML = (comp.issues || []).map(i =>
            `<div class="claim-item flagged"><i class="fas fa-flag" style="color:var(--yellow)"></i> ${escapeHtml(i.description || i.issue || JSON.stringify(i))}</div>`
        ).join("") || '<div style="color:var(--text-dim);font-size:12px;">No issues</div>';

        document.getElementById("complianceSuggestions").innerHTML = (comp.suggestions || []).map(s =>
            `<div class="claim-item suggestion"><i class="fas fa-lightbulb" style="color:var(--accent)"></i> ${escapeHtml(s)}</div>`
        ).join("") || '<div style="color:var(--text-dim);font-size:12px;">None</div>';
    }

    // ── Security Dashboard Rendering ────────────────────────

    // ============================================================
    //  SECURITY & OBSERVABILITY DASHBOARD
    //  Powered by ECharts + LangSmith API
    // ============================================================

    const secDashBtn    = document.getElementById("secDashBtn");
    const secDashOverlay = document.getElementById("secDashOverlay");
    const secDashClose  = document.getElementById("secDashClose");
    const secDashRefresh = document.getElementById("secDashRefresh");
    const secPeriodToggle = document.getElementById("secPeriodToggle");
    const secSourceToggle = document.getElementById("secSourceToggle");

    let secDashDays = 7;
    let secCharts = {};  // ECharts instances
    let secDataSource = "mock";  // "mock" or "live"
    let secMockData = null;      // cached mock JSON

    if (secDashBtn) {
        secDashBtn.addEventListener("click", () => {
            secDashOverlay.classList.remove("hidden");
            loadSecurityDashboard(secDashDays);
        });
    }
    if (secDashClose) {
        secDashClose.addEventListener("click", () => {
            secDashOverlay.classList.add("hidden");
            Object.values(secCharts).forEach(c => c && c.dispose());
            secCharts = {};
        });
    }
    if (secDashRefresh) {
        secDashRefresh.addEventListener("click", () => loadSecurityDashboard(secDashDays));
    }
    if (secPeriodToggle) {
        secPeriodToggle.addEventListener("click", (e) => {
            const btn = e.target.closest(".sec-period-btn");
            if (!btn) return;
            secPeriodToggle.querySelectorAll(".sec-period-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            secDashDays = parseInt(btn.dataset.days, 10);
            loadSecurityDashboard(secDashDays);
        });
    }
    // Data source toggle (Mock / Live)
    if (secSourceToggle) {
        secSourceToggle.addEventListener("click", (e) => {
            const btn = e.target.closest(".sec-source-btn");
            if (!btn) return;
            secSourceToggle.querySelectorAll(".sec-source-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            secDataSource = btn.dataset.source;
            loadSecurityDashboard(secDashDays);
        });
    }
    // ESC to close
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && secDashOverlay && !secDashOverlay.classList.contains("hidden")) {
            secDashClose.click();
        }
    });

    async function loadSecurityDashboard(days) {
        try {
            let data;
            if (secDataSource === "mock") {
                if (!secMockData) {
                    const res = await fetch("/static/data/mock_dashboard.json");
                    if (!res.ok) throw new Error("Failed to load mock data");
                    secMockData = await res.json();
                }
                data = secMockData[String(days)] || secMockData["7"];
            } else {
                const res = await fetch(`${API_BASE}/api/security/dashboard?days=${days}`);
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                data = await res.json();
            }
            renderDashboardKPIs(data);
            renderDashboardCharts(data);
            renderDashboardErrors(data);
            renderDashboardSafety(data);
        } catch (err) {
            console.error("Dashboard fetch error:", err);
        }
    }

    function _fmtNum(n) {
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
        if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
        return String(n);
    }

    function renderDashboardKPIs(data) {
        const s = data.summary || {};
        document.getElementById("kpiTotalRuns").textContent = _fmtNum(s.total_runs || 0);
        document.getElementById("kpiSuccessRate").textContent = (s.success_rate || 0) + "%";
        document.getElementById("kpiTokens").textContent = _fmtNum(s.total_tokens || 0);
        document.getElementById("kpiLatency").textContent = (s.avg_latency_s || 0).toFixed(1) + "s";
        const cs = data.content_safety || {};
        document.getElementById("kpiThreats").textContent = _fmtNum(cs.session_threats_found || 0);
        document.getElementById("kpiP95").textContent = (s.p95_latency_s || 0).toFixed(1) + "s";
    }

    function renderDashboardCharts(data) {
        // Dispose old charts
        Object.values(secCharts).forEach(c => c && c.dispose());
        secCharts = {};

        if (typeof echarts === "undefined") {
            console.warn("ECharts not loaded");
            return;
        }

        _renderAgentRoseChart(data);
        _renderAgentRadarChart(data);
        _renderDailyActivityChart(data);
        _renderTokenChart(data);

        // Auto-resize charts when container flex sizing settles
        requestAnimationFrame(() => {
            Object.values(secCharts).forEach(c => c && c.resize());
        });
    }

    // Resize all ECharts on window resize
    window.addEventListener("resize", () => {
        Object.values(secCharts).forEach(c => c && c.resize());
    });

    function _renderAgentRoseChart(data) {
        const el = document.getElementById("chartAgentRose");
        if (!el) return;
        const chart = echarts.init(el, null, { renderer: "canvas" });
        secCharts.rose = chart;

        const agents = (data.agent_distribution || []).slice(0, 12);
        const palette = [
            "#8b5cf6", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#38bdf8",
            "#a78bfa", "#60a5fa", "#6ee7b7", "#fcd34d", "#fca5a5", "#7dd3fc"
        ];

        chart.setOption({
            tooltip: {
                trigger: "item",
                backgroundColor: "rgba(18,22,36,0.95)",
                borderColor: "rgba(139,92,246,0.2)",
                textStyle: { color: "#e2e8f0", fontSize: 11 },
                formatter: "{b}: {c} runs ({d}%)",
            },
            series: [{
                type: "pie",
                roseType: "area",
                radius: ["20%", "75%"],
                center: ["50%", "52%"],
                itemStyle: {
                    borderRadius: 6,
                    borderColor: "rgba(18,22,36,0.8)",
                    borderWidth: 2,
                },
                label: {
                    color: "#94a3b8",
                    fontSize: 10,
                    formatter: "{b}",
                },
                labelLine: { lineStyle: { color: "rgba(148,163,184,0.3)" } },
                data: agents.map((a, i) => ({
                    name: a.agent,
                    value: a.runs,
                    itemStyle: { color: palette[i % palette.length] },
                })),
            }],
        });
    }

    function _renderAgentRadarChart(data) {
        const el = document.getElementById("chartAgentRadar");
        if (!el) return;
        const chart = echarts.init(el, null, { renderer: "canvas" });
        secCharts.radar = chart;

        const agents = (data.agent_distribution || []).slice(0, 8);
        if (!agents.length) return;

        const maxRuns = Math.max(...agents.map(a => a.runs), 1);

        chart.setOption({
            tooltip: {
                backgroundColor: "rgba(18,22,36,0.95)",
                borderColor: "rgba(139,92,246,0.2)",
                textStyle: { color: "#e2e8f0", fontSize: 11 },
            },
            radar: {
                indicator: agents.map(a => ({
                    name: a.agent.replace(/_/g, " ").slice(0, 12),
                    max: 100,
                })),
                shape: "polygon",
                axisName: { color: "#94a3b8", fontSize: 9 },
                splitArea: {
                    areaStyle: { color: ["rgba(139,92,246,0.02)", "rgba(139,92,246,0.05)"] },
                },
                splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
                axisLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
            },
            series: [
                {
                    type: "radar",
                    data: [
                        {
                            name: "Success Rate %",
                            value: agents.map(a => a.success_rate),
                            areaStyle: { color: "rgba(16,185,129,0.15)" },
                            lineStyle: { color: "#10b981", width: 2 },
                            itemStyle: { color: "#10b981" },
                            symbol: "circle",
                            symbolSize: 5,
                        },
                        {
                            name: "Run Volume (norm.)",
                            value: agents.map(a => Math.round(a.runs / maxRuns * 100)),
                            areaStyle: { color: "rgba(139,92,246,0.12)" },
                            lineStyle: { color: "#8b5cf6", width: 2 },
                            itemStyle: { color: "#8b5cf6" },
                            symbol: "circle",
                            symbolSize: 5,
                        },
                    ],
                },
            ],
        });
    }

    function _renderDailyActivityChart(data) {
        const el = document.getElementById("chartDailyActivity");
        if (!el) return;
        const chart = echarts.init(el, null, { renderer: "canvas" });
        secCharts.daily = chart;

        const daily = data.daily_breakdown || [];
        const dates = daily.map(d => { const p = d.date.split("-"); return p[1] + "/" + p[2]; });
        const successData = daily.map(d => d.success);
        const failedData = daily.map(d => d.failed);

        chart.setOption({
            tooltip: {
                trigger: "axis",
                backgroundColor: "rgba(18,22,36,0.95)",
                borderColor: "rgba(139,92,246,0.2)",
                textStyle: { color: "#e2e8f0", fontSize: 11 },
            },
            grid: { left: 40, right: 16, top: 30, bottom: 24 },
            xAxis: {
                type: "category",
                data: dates,
                axisLabel: { color: "#64748b", fontSize: 9, rotate: 0 },
                axisLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
            },
            yAxis: {
                type: "value",
                axisLabel: { color: "#64748b", fontSize: 9 },
                splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)" } },
            },
            series: [
                {
                    name: "Successful",
                    type: "bar",
                    stack: "total",
                    data: successData,
                    itemStyle: { color: "#10b981", borderRadius: [4, 4, 0, 0] },
                    barWidth: "60%",
                },
                {
                    name: "Failed",
                    type: "bar",
                    stack: "total",
                    data: failedData,
                    itemStyle: { color: "#ef4444", borderRadius: [4, 4, 0, 0] },
                },
            ],
        });
    }

    function _renderTokenChart(data) {
        const el = document.getElementById("chartTokens");
        if (!el) return;
        const chart = echarts.init(el, null, { renderer: "canvas" });
        secCharts.tokens = chart;

        const daily = data.daily_breakdown || [];
        const dates = daily.map(d => { const p = d.date.split("-"); return p[1] + "/" + p[2]; });
        const tokenData = daily.map(d => d.tokens || 0);

        chart.setOption({
            tooltip: {
                trigger: "axis",
                backgroundColor: "rgba(18,22,36,0.95)",
                borderColor: "rgba(139,92,246,0.2)",
                textStyle: { color: "#e2e8f0", fontSize: 11 },
                formatter: (params) => {
                    const p = params[0];
                    return `${p.name}<br/><b>${_fmtNum(p.value)}</b> tokens`;
                },
            },
            grid: { left: 50, right: 16, top: 20, bottom: 24 },
            xAxis: {
                type: "category",
                data: dates,
                axisLabel: { color: "#64748b", fontSize: 9, rotate: 0 },
                axisLine: { lineStyle: { color: "rgba(255,255,255,0.08)" } },
            },
            yAxis: {
                type: "value",
                axisLabel: { color: "#64748b", fontSize: 9, formatter: v => _fmtNum(v) },
                splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)" } },
            },
            series: [{
                type: "line",
                data: tokenData,
                smooth: true,
                symbol: "circle",
                symbolSize: 6,
                lineStyle: { color: "#f59e0b", width: 2.5 },
                itemStyle: { color: "#f59e0b" },
                areaStyle: {
                    color: {
                        type: "linear",
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: "rgba(245,158,11,0.25)" },
                            { offset: 1, color: "rgba(245,158,11,0.02)" },
                        ],
                    },
                },
            }],
        });
    }

    function renderDashboardErrors(data) {
        const el = document.getElementById("secErrorList");
        if (!el) return;
        const errors = data.error_types || [];
        if (!errors.length) {
            el.innerHTML = '<p class="sec-empty"><i class="fas fa-check-circle" style="color:var(--green);margin-right:6px"></i>No errors in this period</p>';
            return;
        }
        el.innerHTML = errors.map(e =>
            `<div class="sec-error-item">
                <i class="fas fa-bug"></i>
                <span>${escapeHtml(e.error)}</span>
                <span class="sec-error-count">&times;${e.count}</span>
            </div>`
        ).join("");
    }

    function renderDashboardSafety(data) {
        const cs = data.content_safety || {};
        const storiesEl = document.getElementById("safetyStories");
        const threatsEl = document.getElementById("safetyThreats");
        const piiEl = document.getElementById("safetyPii");
        const statusEl = document.getElementById("safetyStatus");

        if (storiesEl) storiesEl.textContent = cs.session_scans || 0;
        if (threatsEl) {
            threatsEl.textContent = cs.session_threats_found || 0;
            threatsEl.className = "sec-safety-val" + (cs.session_threats_found > 0 ? " danger" : "");
        }
        if (piiEl) {
            piiEl.textContent = cs.session_pii_detected || 0;
            piiEl.className = "sec-safety-val" + (cs.session_pii_detected > 0 ? " warn" : "");
        }
        if (statusEl) {
            const hasIssues = (cs.session_threats_found || 0) > 0;
            statusEl.textContent = hasIssues ? "FLAGGED" : "CLEAN";
            statusEl.className = "sec-safety-val " + (hasIssues ? "danger" : "safe");
        }

        // Engine card — rule bars (show hits vs pattern count)
        const injBar = document.getElementById("ruleInjectionBar");
        const piiBar = document.getElementById("rulePiiBar");
        const harmBar = document.getElementById("ruleHarmBar");
        if (injBar) {
            const pct = cs.injection_hits ? Math.min(100, (cs.injection_hits / 11) * 100) : 100;
            injBar.style.width = pct + "%";
            injBar.style.opacity = cs.injection_hits ? "1" : "0.4";
        }
        if (piiBar) {
            const pct = cs.pii_hits ? Math.min(100, (cs.pii_hits / 5) * 100) : 100;
            piiBar.style.width = pct + "%";
            piiBar.style.opacity = cs.pii_hits ? "1" : "0.4";
        }
        if (harmBar) {
            const pct = cs.harmful_hits ? Math.min(100, (cs.harmful_hits / 3) * 100) : 100;
            harmBar.style.width = pct + "%";
            harmBar.style.opacity = cs.harmful_hits ? "1" : "0.4";
        }

        // Azure Content Safety category scores
        const azScores = cs.azure_category_scores || {};
        ["Hate", "SelfHarm", "Sexual", "Violence"].forEach(cat => {
            const scoreEl = document.getElementById("azScore" + cat);
            const catEl = document.getElementById("azCat" + cat);
            const score = azScores[cat] || 0;
            if (scoreEl) scoreEl.textContent = score;
            if (catEl) {
                catEl.className = "sec-azure-cat level-" + Math.min(score, 3);
            }
        });

        // Data classification badge
        const clsEl = document.getElementById("safetyClassification");
        if (clsEl) {
            const cls = (cs.classification || "PUBLIC").toUpperCase();
            clsEl.textContent = cls;
            clsEl.className = "sec-class-badge " + cls.toLowerCase();
        }
    }

    // ============================================================
    //  60-SECOND NEWS DUB — Multi-Voice Multi-Language Dubbing
    // ============================================================

    let dubScript = null;
    let dubCurrentLang = "en";
    let dubPlaying = false;
    let dubCurrentSegIdx = -1;
    let dubAudioQueue = [];
    let dubSpeechSynth = window.speechSynthesis;

    // DOM refs
    const dubModal       = document.getElementById("dubModal");
    const dubLaunchBtn   = document.getElementById("dubLaunchBtn");
    const dubCloseBtn    = document.getElementById("dubCloseBtn");
    const dubSegments    = document.getElementById("dubSegments");
    const dubLangButtons = document.getElementById("dubLangButtons");
    const dubVoiceList   = document.getElementById("dubVoiceList");
    const dubPlayAllBtn  = document.getElementById("dubPlayAllBtn");
    const dubStopBtn     = document.getElementById("dubStopBtn");
    const dubProgressBar = document.getElementById("dubProgressBar");
    const dubStatus      = document.getElementById("dubStatus");
    const dubAudio       = document.getElementById("dubAudio");
    const dubScriptTitle = document.getElementById("dubScriptTitle");
    const dubDuration    = document.getElementById("dubDuration");

    // Voice display names (friendly)
    const VOICE_DISPLAY = {
        "en-US-SaraNeural":    "Sara (Newscast)",
        "en-US-AndrewNeural":  "Andrew (Newscast)",
        "en-US-JennyNeural":   "Jenny (Newscast)",
        "es-MX-DaliaNeural":   "Dalia (México)",
        "es-MX-JorgeNeural":   "Jorge (México)",
        "es-MX-BeatrizNeural": "Beatriz (México)",
        "fr-FR-DeniseNeural":  "Denise (France)",
        "fr-FR-HenriNeural":   "Henri (France)",
        "fr-FR-EloiseNeural":  "Eloise (France)",
    };

    // Role → preferred voice traits for browser TTS matching
    // We use pitch/rate variation to differentiate speakers in browser speech
    const ROLE_VOICE_TRAITS = {
        "anchor_female":        { pitch: 1.05, rate: 0.88, preferGender: "female" },
        "reporter_male":        { pitch: 0.8,  rate: 1.0,  preferGender: "male"   },
        "correspondent_female": { pitch: 1.15, rate: 0.93, preferGender: "female" },
    };

    // Friendly style labels for display
    const STYLE_LABELS = {
        "newscast-formal": "📰 Formal News Anchor",
        "newscast-casual":  "🎤 Live Field Reporting",
    };

    // ── Event listeners ──────────────────────────────────────
    if (dubLaunchBtn) dubLaunchBtn.addEventListener("click", openDubModal);
    if (dubCloseBtn)  dubCloseBtn.addEventListener("click", closeDubModal);
    if (dubPlayAllBtn) dubPlayAllBtn.addEventListener("click", dubPlayAll);
    if (dubStopBtn) dubStopBtn.addEventListener("click", dubStop);
    if (dubModal) {
        dubModal.addEventListener("click", (e) => {
            if (e.target === dubModal) closeDubModal();
        });
    }
    // Pre-load browser voices (they load async in some browsers)
    dubSpeechSynth.getVoices();
    if (dubSpeechSynth.onvoiceschanged !== undefined) {
        dubSpeechSynth.onvoiceschanged = () => { _cachedVoices = null; getGroupedVoices(); };
    }

    // ── Open / close modal ───────────────────────────────────
    async function openDubModal() {
        dubModal.classList.remove("hidden");
        dubStatus.textContent = "Loading script…";
        try {
            const res = await fetch(`${API_BASE}/api/dubbing/script`);
            dubScript = await res.json();
            dubScriptTitle.textContent = dubScript.title || "News Dub";
            dubDuration.textContent = dubScript.duration || "60s";
            renderDubSegments();
            renderDubVoices();
            dubStatus.textContent = "Ready — select a language and press Play";
        } catch (e) {
            dubStatus.textContent = "Failed to load script";
            console.error("Dub script load error:", e);
        }
    }

    function closeDubModal() {
        dubStop();
        dubModal.classList.add("hidden");
    }

    // ── Render segments ──────────────────────────────────────
    function renderDubSegments() {
        if (!dubScript || !dubSegments) return;
        dubSegments.innerHTML = dubScript.segments.map(seg => {
            const isAnchor = seg.role === "anchor_female";
            const isReporter = seg.role === "reporter_male";
            const tagClass = isAnchor ? "anchor" : (isReporter ? "reporter" : "correspondent");
            const roleIcon = isAnchor ? '🎬' : (isReporter ? '🎤' : '📡');
            const voice = dubScript.voices[seg.role]?.[dubCurrentLang] || "—";
            const style = dubScript.styles[seg.role] || "";
            const styleLabel = STYLE_LABELS[style] || style;
            const text = seg[dubCurrentLang] || seg.en;
            return `
                <div class="dub-segment" data-seg-id="${seg.id}" id="dubSeg${seg.id}">
                    <div class="dub-segment-meta">
                        <span class="dub-timecode">${escapeHtml(seg.timecode)}</span>
                        <span class="dub-speaker-tag ${tagClass}">${roleIcon} ${escapeHtml(seg.label)}</span>
                        <span class="dub-style-tag">${styleLabel}</span>
                    </div>
                    <div class="dub-segment-voice-row">
                        <i class="fas fa-waveform-lines" style="color:var(--text-dim);font-size:10px;"></i>
                        <span class="dub-voice-name">${VOICE_DISPLAY[voice] || voice}</span>
                    </div>
                    <div class="dub-segment-text">${escapeHtml(text)}</div>
                    <div class="dub-segment-play">
                        <button class="dub-seg-play-btn" data-seg-id="${seg.id}" title="Play this segment">
                            <i class="fas fa-play"></i>
                        </button>
                        <span style="font-size:10px;color:var(--text-dim);">Play segment</span>
                    </div>
                </div>
            `;
        }).join("");

        // Add click-to-play on individual segments
        dubSegments.querySelectorAll(".dub-seg-play-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const segId = parseInt(btn.dataset.segId);
                dubPlaySingleSegment(segId);
            });
        });
    }

    // ── Render voice cast ────────────────────────────────────
    function renderDubVoices() {
        if (!dubScript || !dubVoiceList) return;
        const voices = dubScript.voices;
        const styles = dubScript.styles;
        const roles = [
            { key: "anchor_female", label: "Lead Anchor", icon: "🎬", cls: "anchor" },
            { key: "reporter_male", label: "Field Reporter", icon: "🎤", cls: "reporter" },
            { key: "correspondent_female", label: "Correspondent", icon: "📡", cls: "correspondent" },
        ];
        dubVoiceList.innerHTML = roles.map(r => {
            const voiceName = voices[r.key]?.[dubCurrentLang] || "—";
            const style = styles[r.key] || "—";
            const styleLabel = STYLE_LABELS[style] || style;
            return `
                <div class="dub-voice-card">
                    <div class="dub-voice-icon ${r.cls}">${r.icon}</div>
                    <div class="dub-voice-info">
                        <div class="dub-voice-role">${r.label}</div>
                        <div class="dub-voice-id">${VOICE_DISPLAY[voiceName] || voiceName}</div>
                        <div class="dub-voice-style-label">${styleLabel}</div>
                    </div>
                    <span class="dub-voice-style">${style}</span>
                </div>
            `;
        }).join("");
    }

    // ── Language selection ────────────────────────────────────
    if (dubLangButtons) {
        dubLangButtons.addEventListener("click", (e) => {
            const btn = e.target.closest(".dub-lang-btn");
            if (!btn) return;
            dubCurrentLang = btn.dataset.lang;
            dubLangButtons.querySelectorAll(".dub-lang-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            renderDubSegments();
            renderDubVoices();
            dubStatus.textContent = `Language switched to ${btn.textContent.trim()}`;
        });
    }

    // ── Play all segments sequentially using Web Speech API ──
    async function dubPlayAll() {
        if (!dubScript) return;
        dubPlaying = true;
        dubPlayAllBtn.disabled = true;
        dubStopBtn.disabled = false;
        const segs = dubScript.segments;

        for (let i = 0; i < segs.length; i++) {
            if (!dubPlaying) break;
            dubCurrentSegIdx = i;
            highlightDubSegment(segs[i].id);
            dubProgressBar.style.width = `${((i) / segs.length) * 100}%`;
            dubStatus.textContent = `▶ Playing segment ${i + 1}/${segs.length} — ${segs[i].label} (${segs[i].timecode})`;

            await dubSpeakSegment(segs[i]);
            // Small pause between segments
            if (dubPlaying) await sleep(400);
        }

        // Finished
        dubProgressBar.style.width = "100%";
        dubPlaying = false;
        dubPlayAllBtn.disabled = false;
        dubStopBtn.disabled = true;
        dubCurrentSegIdx = -1;
        clearDubHighlights();
        dubStatus.textContent = dubPlaying ? "Stopped" : "✓ Playback complete";
    }

    // ── Play single segment ──────────────────────────────────
    async function dubPlaySingleSegment(segId) {
        if (!dubScript) return;
        const seg = dubScript.segments.find(s => s.id === segId);
        if (!seg) return;
        dubStop();
        dubPlaying = true;
        dubStopBtn.disabled = false;
        highlightDubSegment(segId);
        dubStatus.textContent = `▶ Playing — ${seg.label} (${seg.timecode})`;
        await dubSpeakSegment(seg);
        dubPlaying = false;
        dubStopBtn.disabled = true;
        clearDubHighlights();
        dubStatus.textContent = "Ready";
    }

    // ── Speak a segment using browser SpeechSynthesis ────────
    // Hard-coded voice preferences per role+language for the demo
    // Each array is tried in order; first match wins
    const HARDCODED_VOICES = {
        "anchor_female": {
            "en": ["Microsoft Zira", "Zira"],
            "es": ["Microsoft Sabina", "Sabina", "Paulina"],
            "fr": ["Microsoft Denise", "Denise", "Amélie"],
        },
        "reporter_male": {
            "en": ["Microsoft Mark", "Mark"],
            "es": ["Microsoft Pablo", "Pablo"],
            "fr": ["Microsoft Paul", "Paul", "Microsoft Claude", "Claude"],
        },
        "correspondent_female": {
            "en": ["Microsoft Eva", "Eva", "Microsoft Hazel", "Hazel", "Microsoft Jenny", "Jenny"],
            "es": ["Microsoft Dalia", "Dalia", "Beatriz"],
            "fr": ["Microsoft Caroline", "Caroline", "Microsoft Eloise", "Eloise"],
        },
    };

    let _cachedVoices = null;
    function getGroupedVoices() {
        if (_cachedVoices) return _cachedVoices;
        const all = dubSpeechSynth.getVoices();
        if (all.length > 0) _cachedVoices = all;
        return all;
    }

    // Voices to NEVER use (substring match, case-insensitive)
    const BLOCKED_VOICES = ["davis", "david"];

    function pickVoiceForRole(role, lang) {
        const langMap = { en: "en-US", es: "es-MX", fr: "fr-FR" };
        const matchLang = langMap[lang] || "en-US";
        const traits = ROLE_VOICE_TRAITS[role] || { pitch: 1.0, rate: 0.95, preferGender: "female" };
        const voices = getGroupedVoices();

        // Filter out blocked voices globally
        const allowed = voices.filter(v => !BLOCKED_VOICES.some(b => v.name.toLowerCase().includes(b)));

        // 1) Try hard-coded voice names first (case-insensitive substring match)
        const preferred = HARDCODED_VOICES[role]?.[lang] || [];
        for (const pref of preferred) {
            const match = allowed.find(v =>
                v.name.toLowerCase().includes(pref.toLowerCase()) &&
                (v.lang === matchLang || v.lang.startsWith(lang))
            );
            if (match) {
                console.log(`[Dub] ${role} → picked "${match.name}" (${match.lang})`);
                return { voice: match, traits };
            }
        }

        // 2) Fallback: filter by language, then pick by role-specific index
        const langVoices = allowed.filter(v => v.lang === matchLang || v.lang.startsWith(lang));
        console.log(`[Dub] ${role} → no hardcoded match, falling back. Available ${matchLang} voices:`,
            langVoices.map(v => `${v.name} (${v.lang})`));

        // Use different index per role so they don't all get the same fallback
        const roleOffset = { "anchor_female": 0, "reporter_male": 1, "correspondent_female": 2 };
        const offset = roleOffset[role] || 0;
        if (langVoices.length > 0) {
            const picked = langVoices[offset % langVoices.length];
            console.log(`[Dub] ${role} → fallback picked "${picked.name}" (index ${offset % langVoices.length})`);
            return { voice: picked, traits };
        }

        // 3) Last resort: first available voice
        return { voice: allowed[0] || voices[0] || null, traits };
    }

    function dubSpeakSegment(seg) {
        return new Promise((resolve) => {
            const text = seg[dubCurrentLang] || seg.en;
            const langMap = { en: "en-US", es: "es-MX", fr: "fr-FR" };

            // Cancel any existing speech
            dubSpeechSynth.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = langMap[dubCurrentLang] || "en-US";

            // Pick a distinct voice + traits for this role
            const { voice, traits } = pickVoiceForRole(seg.role, dubCurrentLang);
            if (voice) utterance.voice = voice;
            utterance.rate = traits.rate;
            utterance.pitch = traits.pitch;

            utterance.onend = () => resolve();
            utterance.onerror = () => resolve();

            dubSpeechSynth.speak(utterance);
        });
    }

    // ── Stop ─────────────────────────────────────────────────
    function dubStop() {
        dubPlaying = false;
        dubSpeechSynth.cancel();
        dubPlayAllBtn.disabled = false;
        dubStopBtn.disabled = true;
        dubCurrentSegIdx = -1;
        dubProgressBar.style.width = "0%";
        clearDubHighlights();
        dubStatus.textContent = "Stopped";
    }

    // ── Highlight helpers ────────────────────────────────────
    function highlightDubSegment(segId) {
        clearDubHighlights();
        const el = document.getElementById(`dubSeg${segId}`);
        if (el) {
            el.classList.add("playing");
            el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    function clearDubHighlights() {
        document.querySelectorAll(".dub-segment.playing").forEach(el => el.classList.remove("playing"));
    }

    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    // ============================================================
    //  AI NEWS ANCHOR — Azure Avatar Integration (Server-Side SDK)
    // ============================================================

    const DEMO_ANCHOR_SCRIPT = `PULSE AI Newsroom — Live Demo.

Good evening. Welcome to the PULSE AI Newsroom, the next generation of broadcast journalism powered by artificial intelligence.

Tonight we are demonstrating how a multi-agent AI pipeline can take a breaking news tip, research it in real time, write a broadcast-ready article, generate supporting images, translate the story into multiple languages, fact-check every claim, and deliver it right here — read by an AI-powered news anchor.

This technology is built on Microsoft Azure, using large language models, speech synthesis, and real-time avatar rendering to transform how newsrooms operate.

To see the full pipeline in action, submit a story from the main screen and then return here to watch your AI anchor deliver it live.`;

    let avatarConfig = null;
    let avatarPeerConnection = null;
    let avatarConnected = false;
    let avatarSpeaking = false;
    let avatarClientId = null;
    let previousAnimationFrameTimestamp = 0;

    // DOM references
    const avatarModal       = document.getElementById("avatarModal");
    const avatarLaunchBtn   = document.getElementById("avatarLaunchBtn");
    const avatarCloseBtn    = document.getElementById("avatarCloseBtn");
    const avatarVideo       = document.getElementById("avatarVideo");
    const avatarCanvas      = document.getElementById("avatarCanvas");
    const avatarLoading     = document.getElementById("avatarLoading");
    const avatarLoadingText = document.getElementById("avatarLoadingText");
    const avatarStatusDot   = document.getElementById("avatarStatusDot");
    const avatarStatusText  = document.getElementById("avatarStatusText");
    const avatarSpeakBtn    = document.getElementById("avatarSpeakBtn");
    const avatarStopSpeakBtn = document.getElementById("avatarStopSpeakBtn");
    const avatarMuteBtn     = document.getElementById("avatarMuteBtn");
    const avatarMuteIcon    = document.getElementById("avatarMuteIcon");
    const teleprompterText  = document.getElementById("teleprompterText");
    const avatarFullscreenBtn = document.getElementById("avatarFullscreenBtn");

    // ── Launch / Close Modal ────────────────────────────────
    if (avatarLaunchBtn) {
        avatarLaunchBtn.addEventListener("click", openAvatarModal);
    }
    if (avatarCloseBtn) {
        avatarCloseBtn.addEventListener("click", closeAvatarModal);
    }
    if (avatarSpeakBtn) {
        avatarSpeakBtn.addEventListener("click", avatarReadArticle);
    }
    if (avatarStopSpeakBtn) {
        avatarStopSpeakBtn.addEventListener("click", avatarStopSpeaking);
    }
    if (avatarMuteBtn) {
        avatarMuteBtn.addEventListener("click", toggleAvatarMute);
    }
    if (avatarFullscreenBtn) {
        avatarFullscreenBtn.addEventListener("click", toggleAvatarFullscreen);
    }
    // Close on overlay click
    if (avatarModal) {
        avatarModal.addEventListener("click", (e) => {
            if (e.target === avatarModal) closeAvatarModal();
        });
    }

    async function openAvatarModal() {
        avatarModal.classList.remove("hidden");
        avatarLoading.classList.remove("hidden");
        setAvatarStatus("connecting", "Connecting…");

        // Load config
        try {
            const cfgRes = await fetch(`${API_BASE}/api/avatar/config`);
            avatarConfig = await cfgRes.json();
        } catch (e) {
            setAvatarStatus("error", "Failed to load config");
            return;
        }

        // Load article text — use story draft if available, otherwise demo script
        let loaded = false;
        if (currentStoryId) {
            try {
                const textRes = await fetch(`${API_BASE}/api/stories/${currentStoryId}/anchor-text`);
                if (textRes.ok) {
                    const { script } = await textRes.json();
                    setTeleprompterText(script);
                    loaded = true;
                }
            } catch (_) { /* no article yet */ }
        }
        if (!loaded) {
            setTeleprompterText(DEMO_ANCHOR_SCRIPT);
        }

        // Initialize avatar session
        await initAvatarSession();
    }

    function closeAvatarModal() {
        avatarModal.classList.add("hidden");
        destroyAvatarSession();
    }

    // ── Avatar Session (Server-Side SDK + WebRTC) ───────────

    async function initAvatarSession() {
        avatarLoadingText.textContent = "Fetching ICE token…";

        try {
            // 1. Fetch ICE servers from the backend
            const iceRes = await fetch(`${API_BASE}/api/avatar/getIceToken`);
            if (!iceRes.ok) throw new Error("Failed to fetch ICE token");
            const iceData = await iceRes.json();

            const iceUrls = iceData.Urls || [];
            const iceServerUrl = iceUrls[0];
            const iceServerUsername = iceData.Username || "";
            const iceServerCredential = iceData.Password || "";

            if (!iceServerUrl) {
                throw new Error("No ICE/TURN server URL returned — check server logs for ICE token errors");
            }

            avatarLoadingText.textContent = "Preparing WebRTC connection…";

            // 2. Create RTCPeerConnection with TURN relay
            avatarPeerConnection = new RTCPeerConnection({
                iceServers: [{
                    urls: [iceServerUrl],
                    username: iceServerUsername,
                    credential: iceServerCredential
                }],
                iceTransportPolicy: "relay"
            });

            // 3. Handle incoming tracks (video + audio from avatar)
            avatarPeerConnection.ontrack = function (event) {
                console.log("Avatar track received:", event.track.kind);
                if (event.track.kind === "video") {
                    const videoContainer = document.getElementById("avatarVideoContainer");
                    // Remove any existing video/audio elements we previously added
                    const existing = videoContainer.querySelector("video.avatar-remote-video");
                    if (existing) existing.remove();

                    // Attach stream to the existing avatarVideo element
                    avatarVideo.srcObject = event.streams[0];
                    avatarVideo.autoplay = true;
                    avatarVideo.playsInline = true;

                    avatarVideo.addEventListener("loadeddata", () => {
                        avatarVideo.play().catch(() => {});
                    }, { once: true });

                    // Show the video element directly (server sends dark bg matching the UI)
                    avatarVideo.style.width = "";
                    avatarVideo.style.position = "";
                    if (avatarCanvas) avatarCanvas.hidden = true;
                }
                if (event.track.kind === "audio") {
                    // Create a separate audio element for the avatar's voice
                    const audioContainer = document.getElementById("avatarVideoContainer");
                    let audioEl = audioContainer.querySelector("audio.avatar-remote-audio");
                    if (!audioEl) {
                        audioEl = document.createElement("audio");
                        audioEl.className = "avatar-remote-audio";
                        audioEl.autoplay = true;
                        audioContainer.appendChild(audioEl);
                    }
                    audioEl.srcObject = event.streams[0];
                    // Start muted, unmute when speaking (autoplay policy)
                    audioEl.muted = true;
                }
            };

            // 4. Listen for data channel events from the server
            avatarPeerConnection.addEventListener("datachannel", event => {
                const dataChannel = event.channel;
                dataChannel.onmessage = e => {
                    console.log("[Avatar WebRTC event]", e.data);
                    if (e.data.includes("EVENT_TYPE_SWITCH_TO_IDLE")) {
                        avatarSpeaking = false;
                        avatarSpeakBtn.disabled = false;
                        avatarStopSpeakBtn.disabled = true;
                        setAvatarStatus("connected", "Avatar ready");
                    }
                };
            });

            // Create a client data channel (workaround to enable data channel listening)
            avatarPeerConnection.createDataChannel("eventChannel");

            // 5. Monitor ICE connection state
            avatarPeerConnection.oniceconnectionstatechange = () => {
                const state = avatarPeerConnection.iceConnectionState;
                console.log("Avatar ICE state:", state);
                if (state === "connected" || state === "completed") {
                    avatarLoading.classList.add("hidden");
                    avatarConnected = true;
                    setAvatarStatus("connected", "Avatar ready");
                    avatarSpeakBtn.disabled = false;
                } else if (state === "disconnected" || state === "failed") {
                    setAvatarStatus("error", "Connection lost");
                    avatarConnected = false;
                }
            };

            // 6. Add transceivers (sendrecv to match server expectations)
            avatarPeerConnection.addTransceiver("video", { direction: "sendrecv" });
            avatarPeerConnection.addTransceiver("audio", { direction: "sendrecv" });

            // 7. Create SDP offer and wait for ICE gathering
            avatarLoadingText.textContent = "Gathering ICE candidates…";

            const offer = await avatarPeerConnection.createOffer();
            await avatarPeerConnection.setLocalDescription(offer);

            // Wait for ICE gathering to complete (or timeout after 10s)
            await new Promise((resolve) => {
                let done = false;
                avatarPeerConnection.onicecandidate = (e) => {
                    if (!e.candidate && !done) {
                        done = true;
                        resolve();
                    }
                };
                setTimeout(() => {
                    if (!done) {
                        done = true;
                        resolve();
                    }
                }, 10000);
            });

            // 8. Send local SDP to the server, get remote SDP back
            avatarLoadingText.textContent = "Connecting to avatar service…";

            const localSdp = btoa(JSON.stringify(avatarPeerConnection.localDescription));

            const connectRes = await fetch(`${API_BASE}/api/avatar/connectAvatar`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    localSdp: localSdp,
                    avatarCharacter: avatarConfig.avatarCharacter || "meg",
                    avatarStyle: avatarConfig.avatarStyle || "formal",
                    voiceName: avatarConfig.ttsVoice || "en-US-AvaMultilingualNeural",
                    transparentBackground: avatarConfig.transparentBackground !== false,
                    customized: avatarConfig.customAvatar || false,
                })
            });

            if (!connectRes.ok) {
                const errText = await connectRes.text();
                throw new Error(`Connect failed: ${connectRes.status} ${errText}`);
            }

            const { remoteSdp, clientId } = await connectRes.json();
            avatarClientId = clientId;

            // 9. Set remote SDP on the peer connection
            const remoteDesc = JSON.parse(atob(remoteSdp));
            await avatarPeerConnection.setRemoteDescription(new RTCSessionDescription(remoteDesc));

            console.log("Avatar service connected, waiting for media tracks…");
            avatarLoadingText.textContent = "Starting avatar…";

        } catch (err) {
            console.error("Avatar init error:", err);
            setAvatarStatus("error", "Connection failed");
            avatarLoadingText.textContent = "Connection failed — " + err.message;
        }
    }

    function destroyAvatarSession() {
        avatarSpeaking = false;
        avatarConnected = false;
        if (avatarSpeakBtn) avatarSpeakBtn.disabled = true;
        if (avatarStopSpeakBtn) avatarStopSpeakBtn.disabled = true;

        // Tell the server to disconnect
        if (avatarClientId) {
            fetch(`${API_BASE}/api/avatar/disconnect`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ clientId: avatarClientId })
            }).catch(() => {});
            avatarClientId = null;
        }

        if (avatarPeerConnection) {
            avatarPeerConnection.close();
            avatarPeerConnection = null;
        }

        // Clean up audio elements
        const audioEl = document.querySelector(".avatar-remote-audio");
        if (audioEl) audioEl.remove();

        avatarVideo.srcObject = null;
        avatarVideo.style.width = "";
        avatarVideo.style.position = "";
        if (avatarCanvas) {
            avatarCanvas.hidden = true;
        }

        setAvatarStatus("disconnected", "Disconnected");
        avatarLoading.classList.remove("hidden");
        avatarLoadingText.textContent = "Connecting to AI Anchor…";
    }

    // ── Speak / Stop ────────────────────────────────────────
    async function avatarReadArticle() {
        if (!avatarPeerConnection || !avatarConnected || !avatarClientId) return;

        // Get article text
        let script = "";
        if (currentStoryId) {
            try {
                const res = await fetch(`${API_BASE}/api/stories/${currentStoryId}/anchor-text`);
                if (res.ok) {
                    const data = await res.json();
                    script = data.script;
                    setTeleprompterText(script);
                }
            } catch (_) {}
        }
        if (!script) {
            script = teleprompterText.innerText;
        }
        if (!script || script.includes("Article text will appear")) {
            setAvatarStatus("error", "No article text available");
            return;
        }

        avatarSpeaking = true;
        avatarSpeakBtn.disabled = true;
        avatarStopSpeakBtn.disabled = false;
        setAvatarStatus("speaking", "Reading article…");

        // Unmute audio element so user can hear
        const audioEl = document.querySelector(".avatar-remote-audio");
        if (audioEl) audioEl.muted = false;

        try {
            // Build SSML for natural news-reading style
            const ssml = buildNewsSSML(script, avatarConfig.ttsVoice || "en-US-AvaMultilingualNeural");

            const speakRes = await fetch(`${API_BASE}/api/avatar/speak`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ssml: ssml,
                    clientId: avatarClientId
                })
            });

            if (!speakRes.ok) {
                const errText = await speakRes.text();
                throw new Error(`Speak failed: ${speakRes.status} ${errText}`);
            }

            console.log("Avatar speak request sent successfully");
            // The datachannel EVENT_TYPE_SWITCH_TO_IDLE will reset speak state when done

        } catch (err) {
            console.error("Avatar speak error:", err);
            setAvatarStatus("error", "Speech failed");
            avatarSpeaking = false;
            avatarSpeakBtn.disabled = false;
            avatarStopSpeakBtn.disabled = true;
        }
    }

    async function avatarStopSpeaking() {
        if (!avatarClientId) return;
        try {
            await fetch(`${API_BASE}/api/avatar/stopSpeaking`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ clientId: avatarClientId })
            });
        } catch (_) {}
        avatarSpeaking = false;
        avatarSpeakBtn.disabled = false;
        avatarStopSpeakBtn.disabled = true;
        setAvatarStatus("connected", "Stopped");
    }

    function buildNewsSSML(text, voice) {
        // Split into paragraphs and wrap in SSML with newscast-formal speaking style
        const paragraphs = text.split(/\n{2,}/).filter(p => p.trim());
        const ssmlBody = paragraphs.map((p, i) => {
            // First paragraph is typically the headline — read it stronger
            if (i === 0) {
                return `<prosody rate="-5%" pitch="+2%"><emphasis level="strong">${escapeXml(p.trim())}</emphasis></prosody><break time="800ms"/>`;
            }
            return `<prosody rate="-3%">${escapeXml(p.trim())}</prosody><break time="500ms"/>`;
        }).join("\n");

        // Wrap in mstts:express-as newscast-formal for authoritative news anchor delivery
        return `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US"><voice name="${voice}"><mstts:viseme type="FacialExpression"/><mstts:express-as style="newscast-formal">${ssmlBody}</mstts:express-as></voice></speak>`;
    }

    function escapeXml(str) {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
    }

    // ── Transparent background compositing ──────────────────
    function makeAvatarBackgroundTransparent(timestamp) {
        if (timestamp - previousAnimationFrameTimestamp > 30) {
            const video = avatarVideo;
            const canvas = avatarCanvas;
            if (video && canvas && video.videoWidth > 0) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext("2d", { willReadFrequently: true });
                ctx.drawImage(video, 0, 0, video.videoWidth, video.videoHeight);
                let frame = ctx.getImageData(0, 0, video.videoWidth, video.videoHeight);
                for (let i = 0; i < frame.data.length / 4; i++) {
                    let r = frame.data[i * 4 + 0];
                    let g = frame.data[i * 4 + 1];
                    let b = frame.data[i * 4 + 2];
                    if (g - 150 > r + b) {
                        frame.data[i * 4 + 3] = 0;
                    } else if (g + g > r + b) {
                        let adjustment = (g - (r + b) / 2) / 3;
                        frame.data[i * 4 + 0] = r + adjustment;
                        frame.data[i * 4 + 1] = g - adjustment * 2;
                        frame.data[i * 4 + 2] = b + adjustment;
                        frame.data[i * 4 + 3] = Math.max(0, 255 - adjustment * 4);
                    }
                }
                ctx.putImageData(frame, 0, 0);
            }
            previousAnimationFrameTimestamp = timestamp;
        }
        window.requestAnimationFrame(makeAvatarBackgroundTransparent);
    }

    // ── Helpers ─────────────────────────────────────────────
    function setAvatarStatus(state, text) {
        if (avatarStatusDot) {
            avatarStatusDot.className = "avatar-status-dot";
            if (state === "connected") avatarStatusDot.classList.add("connected");
            else if (state === "speaking") avatarStatusDot.classList.add("speaking");
            else if (state === "error") avatarStatusDot.classList.add("error");
        }
        if (avatarStatusText) avatarStatusText.textContent = text;
    }

    function setTeleprompterText(script) {
        if (!teleprompterText) return;
        const paragraphs = script.split(/\n{2,}/).filter(p => p.trim());
        teleprompterText.innerHTML = paragraphs.map((p, i) =>
            `<p class="speaking-line" data-line="${i}">${escapeHtml(p.trim())}</p>`
        ).join("");
    }

    function toggleAvatarMute() {
        if (!avatarVideo) return;
        const audioEl = document.querySelector(".avatar-remote-audio");
        if (audioEl) {
            audioEl.muted = !audioEl.muted;
            avatarMuteIcon.className = audioEl.muted ? "fas fa-microphone-slash" : "fas fa-microphone";
        }
    }

    function toggleAvatarFullscreen() {
        const container = document.getElementById("avatarVideoContainer");
        if (!container) return;
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            container.requestFullscreen().catch(() => {});
        }
    }

    // ── Q&A Chat & Store Locator ───────────────────────────
    // ══════════════════════════════════════════════════════════
    // ══  PULSE ASSIST  — Q&A, Weather, Traffic, Stores, Voice
    // ══════════════════════════════════════════════════════════
    const qaFab      = document.getElementById("qaFab");
    const qaPopup    = document.getElementById("qaPopup");
    const qaCloseBtn = document.getElementById("qaCloseBtn");
    const qaMessages = document.getElementById("qaMessages");
    const qaInput    = document.getElementById("qaInput");
    const qaSendBtn  = document.getElementById("qaSendBtn");
    const qaZipcode  = document.getElementById("qaZipcode");
    const qaStoresBtn = document.getElementById("qaStoresBtn");
    const qaMicBtn   = document.getElementById("qaMicBtn");
    const qaStopVoiceBtn = document.getElementById("qaStopVoiceBtn");
    const qaAdBanner = document.getElementById("qaAdBanner");
    const qaToolbar  = document.getElementById("qaToolbar");
    const qaWeatherTab  = document.getElementById("qaWeatherTab");
    const qaTrafficTab  = document.getElementById("qaTrafficTab");
    const qaStoresTab   = document.getElementById("qaStoresTab");
    const qaWeatherGrid = document.getElementById("qaWeatherGrid");
    const qaWeatherLoc  = document.getElementById("qaWeatherLocation");
    const qaTrafficGoBtn  = document.getElementById("qaTrafficGoBtn");
    const qaTrafficOrigin = document.getElementById("qaTrafficOrigin");
    const qaTrafficDest   = document.getElementById("qaTrafficDest");
    const qaTrafficResult = document.getElementById("qaTrafficResult");
    const qaStoresBody    = document.getElementById("qaStoresBody");

    let geoDetected = false;
    let cachedNearbyStores = [];
    let _userLat = null, _userLon = null;    // cached GPS coords
    let _userCity = "", _userState = "";
    let _qaVoiceRecognizer = null;           // Speech SDK recognizer for mic
    let _qaVoicePlaying = false;             // TTS playback state
    let _qaWasVoiceQuestion = false;         // true when question came from mic

    // ── Ad placement engine (AI-driven) ─────────────────────
    let _adsConfig = null;
    let _adsLoaded = false;
    let _shownAdIds = [];                    // track shown ads for dedup
    let _lastQAQuestion = "";                // last user question for ad context

    // ── Emergency / weather topic detection ──────────────────
    const _EMERGENCY_KEYWORDS = [
        "hurricane", "storm", "tornado", "flood", "earthquake", "wildfire",
        "fire", "tsunami", "blizzard", "winter storm", "evacuat", "emergency",
        "disaster", "typhoon", "cyclone", "landslide", "drought", "heatwave",
        "heat wave", "power outage", "blackout", "volcanic", "volcano", "mudslide",
        "severe weather", "tropical", "outbreak", "pandemic", "epidemic",
        "snow", "eruption",
    ];
    const _WEATHER_KEYWORDS = [
        "hurricane", "storm", "tornado", "flood", "blizzard", "winter storm",
        "snow", "tropical", "severe weather", "heatwave", "heat wave",
        "typhoon", "cyclone", "volcanic", "volcano", "eruption",
    ];

    function isEmergencyTopic(headline) {
        if (!headline) return false;
        const h = headline.toLowerCase();
        return _EMERGENCY_KEYWORDS.some(kw => h.includes(kw));
    }
    function isWeatherTopic(headline) {
        if (!headline) return false;
        const h = headline.toLowerCase();
        return _WEATHER_KEYWORDS.some(kw => h.includes(kw));
    }

    let _lastHeadlineForQA = "";

    // ── Weather icon mapping (Azure Maps icon codes) ─────────
    const _WEATHER_ICONS = {
        1: "fa-sun", 2: "fa-sun", 3: "fa-cloud-sun", 4: "fa-cloud-sun",
        5: "fa-smog", 6: "fa-cloud-sun", 7: "fa-cloud", 8: "fa-cloud",
        11: "fa-smog", 12: "fa-cloud-rain", 13: "fa-cloud-sun-rain",
        14: "fa-cloud-sun-rain", 15: "fa-bolt", 16: "fa-cloud-bolt",
        17: "fa-cloud-bolt", 18: "fa-cloud-rain", 19: "fa-snowflake",
        20: "fa-snowflake", 21: "fa-snowflake", 22: "fa-snowflake",
        23: "fa-snowflake", 24: "fa-icicles", 25: "fa-cloud-rain",
        26: "fa-cloud-rain", 29: "fa-cloud-rain", 30: "fa-temperature-high",
        31: "fa-temperature-low", 32: "fa-wind", 33: "fa-moon", 34: "fa-moon",
        35: "fa-cloud-moon", 36: "fa-cloud-moon", 37: "fa-cloud-moon",
        38: "fa-cloud", 39: "fa-cloud-moon-rain", 40: "fa-cloud-moon-rain",
        41: "fa-cloud-bolt", 42: "fa-cloud-bolt", 43: "fa-snowflake",
        44: "fa-snowflake",
    };
    const _DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    // ══════════════════════════════════════════════════════════
    // Setup
    // ══════════════════════════════════════════════════════════
    // ── Load ads config ─────────────────────────────────────
    async function _loadAdsConfig() {
        if (_adsLoaded) return;
        try {
            const res = await fetch(`${API_BASE}/static/ads/ads_config.json`, { signal: AbortSignal.timeout(5000) });
            if (res.ok) _adsConfig = await res.json();
        } catch (_) { /* ads are optional */ }
        _adsLoaded = true;
    }

    function _getContextualAd(responseType) {
        // Deprecated — ad selection now handled by AI agent via /api/ad/decide
        return null;
    }

    async function _maybeInsertAd(responseType, answerText) {
        // Ensure ads config is loaded before deciding
        if (!_adsLoaded) await _loadAdsConfig();

        if (!_adsConfig || !_adsConfig.enabled) {
            return;
        }

        const headline = headlineInput ? headlineInput.value.trim() : "";

        try {
            const res = await fetch(`${API_BASE}/api/ad/decide`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: _lastQAQuestion,
                    answer_text: answerText || "",
                    response_type: responseType || "general",
                    headline: headline,
                    ads: _adsConfig.ads,
                    shown_ad_ids: _shownAdIds,
                }),
                signal: AbortSignal.timeout(20000),
            });
            if (!res.ok) { return; }
            const decision = await res.json();

            if (!decision.show_ad) return;

            // Support multiple ads (ad_ids array) or single (ad_id)
            const adIds = decision.ad_ids || (decision.ad_id ? [decision.ad_id] : []);
            if (!adIds.length) return;

            // Resolve ad objects
            const adObjects = adIds.map(id => _adsConfig.ads.find(a => a.id === id)).filter(Boolean);
            if (!adObjects.length) return;
            adObjects.forEach(a => _shownAdIds.push(a.id));

            // ── Render ad into the fixed banner (always visible above input) ──
            _renderAdBanner(adObjects);

        } catch (err) {
            // Silently fail — ads are an enhancement
        }
    }

    function _renderAdBanner(adObjects) {
        if (!qaAdBanner) return;

        // Stop any previous carousel timers
        _adCarouselTimers.forEach(t => clearInterval(t));
        _adCarouselTimers = [];

        // Build the ad card HTML for the first (or only) ad
        const ad = adObjects[0];
        let html = `
            <div class="qa-ad-banner-card">
                <div class="qa-ad-banner-top">
                    <div class="qa-ad-logo" style="background:${ad.accent_color}">${ad.sponsor_logo}</div>
                    <div class="qa-ad-banner-info">
                        <span class="qa-ad-sponsor">${escapeHtml(ad.sponsor)}</span>
                        <span class="qa-ad-headline">${escapeHtml(ad.headline)}</span>
                    </div>
                    <span class="qa-ad-badge">Ad</span>
                </div>
                <div class="qa-ad-banner-bottom">
                    <span class="qa-ad-desc">${escapeHtml(ad.body)}</span>
                    <a class="qa-ad-cta-btn" href="${encodeURI(ad.cta_url)}" target="_blank" rel="noopener" style="background:${ad.accent_color}">
                        ${escapeHtml(ad.cta_text)} <i class="fas fa-arrow-right"></i>
                    </a>
                </div>
        `;

        // Add dot indicators if multiple ads
        if (adObjects.length > 1) {
            html += `<div class="qa-ad-dots">`;
            adObjects.forEach((_, i) => {
                html += `<span class="qa-ad-dot${i === 0 ? ' active' : ''}" data-idx="${i}"></span>`;
            });
            html += `</div>`;
        }
        html += `</div>`;

        qaAdBanner.innerHTML = html;
        qaAdBanner.classList.remove("hidden");

        // Wire up dot clicks and auto-rotate for multiple ads
        if (adObjects.length > 1) {
            let currentAd = 0;
            const dots = qaAdBanner.querySelectorAll(".qa-ad-dot");

            const showAd = (idx) => {
                currentAd = idx;
                const a = adObjects[idx];
                const logo = qaAdBanner.querySelector(".qa-ad-logo");
                const sponsor = qaAdBanner.querySelector(".qa-ad-sponsor");
                const headline = qaAdBanner.querySelector(".qa-ad-headline");
                const desc = qaAdBanner.querySelector(".qa-ad-desc");
                const cta = qaAdBanner.querySelector(".qa-ad-cta-btn");
                if (logo) { logo.textContent = a.sponsor_logo; logo.style.background = a.accent_color; }
                if (sponsor) sponsor.textContent = a.sponsor;
                if (headline) headline.textContent = a.headline;
                if (desc) desc.textContent = a.body;
                if (cta) { cta.href = a.cta_url; cta.style.background = a.accent_color; cta.innerHTML = `${escapeHtml(a.cta_text)} <i class="fas fa-arrow-right"></i>`; }
                dots.forEach((d, i) => d.classList.toggle("active", i === idx));
            };

            dots.forEach(d => d.addEventListener("click", () => showAd(parseInt(d.dataset.idx))));

            // Auto-rotate every 4s
            const timer = setInterval(() => {
                currentAd = (currentAd + 1) % adObjects.length;
                showAd(currentAd);
            }, 4000);
            _adCarouselTimers.push(timer);

            qaAdBanner.addEventListener("mouseenter", () => clearInterval(timer));
            qaAdBanner.addEventListener("mouseleave", () => {
                const t = setInterval(() => {
                    currentAd = (currentAd + 1) % adObjects.length;
                    showAd(currentAd);
                }, 4000);
                _adCarouselTimers.push(t);
            });
        }
    }

    // ── Ad carousel auto-scroll ──────────────────────────────
    let _adCarouselTimers = [];

    function setupQA() {
        if (!qaFab) return;

        // Load ads config eagerly
        _loadAdsConfig();

        // Fab toggle
        qaFab.addEventListener("click", () => {
            const wasHidden = qaPopup.classList.contains("hidden");
            qaPopup.classList.toggle("hidden");
            if (wasHidden) _onQAOpen();
        });
        qaCloseBtn.addEventListener("click", () => qaPopup.classList.add("hidden"));

        // Chat
        qaSendBtn.addEventListener("click", sendQAQuestion);
        qaInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendQAQuestion(); });

        // Stores
        qaStoresBtn.addEventListener("click", findNearbyStores);

        // Mic
        if (qaMicBtn) qaMicBtn.addEventListener("click", toggleVoiceInput);

        // Stop voice
        if (qaStopVoiceBtn) qaStopVoiceBtn.addEventListener("click", stopQAVoice);

        // Traffic
        if (qaTrafficGoBtn) qaTrafficGoBtn.addEventListener("click", checkTraffic);

        // Toolbar tabs
        if (qaToolbar) {
            qaToolbar.querySelectorAll(".qa-tool-btn").forEach(btn => {
                btn.addEventListener("click", () => _switchQAPanel(btn.dataset.panel));
            });
        }
    }

    function _onQAOpen() {
        const headline = headlineInput ? headlineInput.value.trim() : "";
        const emergency = isEmergencyTopic(headline);
        const weather   = isWeatherTopic(headline);

        if (headline !== _lastHeadlineForQA || !geoDetected) {
            _lastHeadlineForQA = headline;
            _adaptQAPopup(emergency, weather, headline);
        }

        if (!geoDetected && emergency) {
            geoDetected = true;
            detectUserLocation();
        }
    }

    // ── Panel switching ──────────────────────────────────────
    function _switchQAPanel(panelId) {
        // Activate tab
        qaToolbar.querySelectorAll(".qa-tool-btn").forEach(b => b.classList.remove("active"));
        const activeBtn = qaToolbar.querySelector(`[data-panel="${panelId}"]`);
        if (activeBtn) activeBtn.classList.add("active");

        // Show panel
        document.querySelectorAll(".qa-panel").forEach(p => p.classList.remove("active"));
        const panel = document.getElementById("qaPanel" + panelId.charAt(0).toUpperCase() + panelId.slice(1));
        if (panel) panel.classList.add("active");

        // Auto-fetch on first switch
        if (panelId === "weather" && qaWeatherGrid.querySelector(".qa-weather-placeholder") && _userLat) {
            fetchWeatherForecast();
        }
    }

    // ── Adapt popup for headline context ─────────────────────
    function _adaptQAPopup(isEmergency, isWeather, headline) {
        // Show/hide toolbar tabs based on topic
        if (qaWeatherTab) qaWeatherTab.classList.toggle("hidden-tab", !isWeather);
        if (qaTrafficTab) qaTrafficTab.classList.toggle("hidden-tab", !isEmergency);
        if (qaStoresTab)  qaStoresTab.classList.toggle("hidden-tab", !isEmergency);

        // Input placeholder
        if (qaInput) {
            qaInput.placeholder = isEmergency
                ? "Ask about shelters, supplies, safety…"
                : "Ask a question about this story…";
        }

        // Contextual greeting
        const old = qaMessages.querySelector(".qa-bot");
        if (old) old.remove();

        if (isEmergency) {
            addQAMessage(
                `<i class="fas fa-triangle-exclamation"></i> ` +
                `I can help you prepare for <strong>${escapeHtml(headline)}</strong>. ` +
                `Use the tabs above for weather forecasts, traffic, and nearby stores. ` +
                `Detecting your location…`,
                false
            );
        } else {
            addQAMessage(
                `<i class="fas fa-satellite-dish"></i> ` +
                `Hi! I can answer questions about <strong>${escapeHtml(headline || "the current story")}</strong>. ` +
                `Type below or tap the mic to speak.`,
                false
            );
        }
    }

    // ══════════════════════════════════════════════════════════
    // Location detection
    // ══════════════════════════════════════════════════════════
    async function detectUserLocation() {
        // GPS → reverse geocode → IP fallback
        if (navigator.geolocation) {
            try {
                const pos = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, {
                        enableHighAccuracy: false, timeout: 8000, maximumAge: 300000,
                    });
                });
                _userLat = pos.coords.latitude;
                _userLon = pos.coords.longitude;

                const res = await fetch(`${API_BASE}/api/geo/reverse`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ lat: _userLat, lon: _userLon }),
                    signal: AbortSignal.timeout(8000),
                });
                if (res.ok) {
                    const data = await res.json();
                    if (data.zipcode) {
                        qaZipcode.value = data.zipcode;
                        _userCity  = data.city  || "";
                        _userState = data.state || "";
                        _updateLocationUI(data.city, data.state, data.zipcode, "crosshairs");
                        return;
                    }
                }
            } catch (_) { /* fall through */ }
        }

        // IP fallback
        try {
            const res = await fetch("https://ipapi.co/json/", { signal: AbortSignal.timeout(5000) });
            if (!res.ok) return;
            const data = await res.json();
            if (data.postal) {
                qaZipcode.value = data.postal;
                _userLat   = data.latitude  || null;
                _userLon   = data.longitude || null;
                _userCity  = data.city       || "";
                _userState = data.region     || "";
                _updateLocationUI(data.city, data.region, data.postal, "map-marker-alt");
            }
        } catch (_) {
            addQAMessage(
                `<i class="fas fa-map-pin"></i> Couldn't detect location. Enter your ZIP code in the Stores tab.`,
                false
            );
        }
    }

    function _updateLocationUI(city, state, zip, icon) {
        addQAMessage(
            `<i class="fas fa-${icon}"></i> Location: <strong>${city}, ${state} ${zip}</strong>.`,
            false
        );
        // Update traffic origin
        if (qaTrafficOrigin) qaTrafficOrigin.value = `${city}, ${state}`;
        // Update weather header
        if (qaWeatherLoc) qaWeatherLoc.innerHTML = `<i class="fas fa-map-marker-alt"></i> <span>${city}, ${state}</span>`;
    }

    // ══════════════════════════════════════════════════════════
    // Chat messages
    // ══════════════════════════════════════════════════════════
    function addQAMessage(content, isUser) {
        const div = document.createElement("div");
        div.className = `qa-message ${isUser ? "qa-user" : "qa-bot"}`;
        div.innerHTML = `<div class="qa-msg-content">${content}</div>`;
        qaMessages.appendChild(div);
        qaMessages.scrollTop = qaMessages.scrollHeight;
    }

    async function sendQAQuestion(fromVoice) {
        const question = qaInput.value.trim();
        if (!question) return;
        _qaWasVoiceQuestion = !!fromVoice;
        _lastQAQuestion = question;
        addQAMessage(escapeHtml(question), true);
        qaInput.value = "";
        qaInput.disabled = true;
        qaSendBtn.disabled = true;

        try {
            // ── Single agentic call — LLM decides which tool ─────
            addQAMessage("<i class='fas fa-spinner fa-spin'></i> Thinking…", false);

            const res = await fetch(`${API_BASE}/api/qa`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question,
                    zipcode: qaZipcode.value.trim(),
                    story_id: currentStoryId || "",
                    lat: _userLat,
                    lon: _userLon,
                    nearby_stores: cachedNearbyStores,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // Remove "Thinking…" spinner
            const spinner = qaMessages.querySelector(".qa-bot:last-child");
            if (spinner) spinner.remove();

            // ── Render based on response type ────────────────────
            _renderQAResponse(data);

            // ── Extract answer text for ad context ───────────────
            let answerText = data.answer || "";
            if (!answerText && data.forecasts) {
                answerText = data.forecasts.map(f => f.day_phrase).join(" ");
            }
            if (!answerText && data.categories) {
                // Store results: build text from category names and store names
                answerText = data.categories.map(c =>
                    c.category + ": " + c.stores.map(s => s.name).join(", ")
                ).join(". ");
            }
            if (!answerText && data.destination) {
                answerText = `Traffic to ${data.destination}, ${data.distance_miles} miles, ${data.travel_time_minutes} min`;
            }

            // ── Maybe insert a contextual ad ─────────────────────
            _maybeInsertAd(data.type || "general", answerText);

        } catch (err) {
            // Remove spinner if present
            const sp = qaMessages.querySelector(".qa-bot:last-child");
            if (sp && sp.textContent.includes("Thinking")) sp.remove();
            addQAMessage("Sorry, something went wrong. Please try again.", false);
        }
        qaInput.disabled = false;
        qaSendBtn.disabled = false;
        qaInput.focus();
    }

    // ── Render response based on orchestrator's chosen tool ──
    function _renderQAResponse(data) {
        const type = data.type || "general";

        if (type === "weather") {
            _renderWeatherResponse(data);
        } else if (type === "traffic") {
            _renderTrafficResponse(data);
        } else if (type === "stores") {
            _renderStoresResponse(data);
        } else if (type === "error") {
            addQAMessage(`<i class="fas fa-exclamation-circle"></i> ${escapeHtml(data.answer || "Something went wrong.")}`, false);
            if (_qaWasVoiceQuestion) _speakQAAnswer(data.answer || "");
        } else {
            _renderGeneralResponse(data);
        }
    }

    function _renderWeatherResponse(data) {
        const loc = data.location || "your area";
        const days = data.days || 7;
        const forecasts = data.forecasts || [];

        let html = `<div class="qa-weather-inline"><div class="qa-weather-inline-title"><i class="fas fa-cloud-sun"></i> ${days}-Day Forecast for ${escapeHtml(loc)}</div>`;
        let speechParts = [`Here's the ${days} day weather forecast for ${loc}.`];

        forecasts.forEach((d, i) => {
            const date = new Date(d.date);
            const dayName = i === 0 ? "Today" : _DAY_NAMES[date.getDay()];
            const hi = d.max_temp != null ? Math.round(d.max_temp) : "--";
            const lo = d.min_temp != null ? Math.round(d.min_temp) : "--";
            const iconClass = _WEATHER_ICONS[d.day_icon] || "fa-cloud";
            const precip = d.precipitation_probability || 0;

            html += `<div class="qa-weather-inline-day">
                <span class="qa-wi-name">${dayName}</span>
                <i class="fas ${iconClass} qa-wi-icon"></i>
                <span class="qa-wi-temps">${hi}°/${lo}°</span>
                ${precip > 20 ? `<span class="qa-wi-precip"><i class="fas fa-droplet"></i>${precip}%</span>` : ""}
                <span class="qa-wi-desc">${escapeHtml((d.day_phrase || "").substring(0, 40))}</span>
            </div>`;

            if (i < 3) speechParts.push(`${dayName}: ${d.day_phrase || ""}, high of ${hi}, low of ${lo}.`);
        });
        html += `</div>`;
        addQAMessage(html, false);

        // Refresh weather tab data in background (don't switch away from chat)
        fetchWeatherForecast();

        if (_qaWasVoiceQuestion) _speakQAAnswer(speechParts.join(" "));
    }

    function _renderTrafficResponse(data) {
        const travelMin = data.travel_time_minutes || 0;
        const delayMin  = data.traffic_delay_minutes || 0;
        const distMiles = data.distance_miles || 0;
        const origin = data.origin || "Your location";
        const dest = data.destination || "destination";

        let delaySeverity = "good", delayLabel = "Clear roads";
        if (delayMin > 30) { delaySeverity = "heavy"; delayLabel = "Heavy delays"; }
        else if (delayMin > 10) { delaySeverity = "moderate"; delayLabel = "Moderate delays"; }

        const hrs = Math.floor(travelMin / 60);
        const mins = Math.round(travelMin % 60);
        const travelStr = hrs > 0 ? `${hrs}h ${mins}m` : `${mins} minutes`;

        const html = `<div class="qa-traffic-inline">
            <div class="qa-traffic-inline-header"><i class="fas fa-route"></i> ${escapeHtml(origin)} → ${escapeHtml(dest)}</div>
            <div class="qa-traffic-inline-stats">
                <div class="qa-ti-stat"><span class="qa-ti-label">Distance</span><span class="qa-ti-val">${distMiles} mi</span></div>
                <div class="qa-ti-stat"><span class="qa-ti-label">Travel Time</span><span class="qa-ti-val ${delaySeverity}">${travelStr}</span></div>
                <div class="qa-ti-stat"><span class="qa-ti-label">Delay</span><span class="qa-ti-val ${delaySeverity}">${delayMin > 0 ? "+" + Math.round(delayMin) + "m" : "None"}</span></div>
                <div class="qa-ti-stat"><span class="qa-ti-label">Conditions</span><span class="qa-ti-val ${delaySeverity}">${delayLabel}</span></div>
            </div>
        </div>`;
        addQAMessage(html, false);

        const delaySpeak = delayMin > 1 ? ` with about ${Math.round(delayMin)} minutes of delay` : ` with clear roads`;
        if (_qaWasVoiceQuestion) _speakQAAnswer(`Traffic from ${origin} to ${dest}: ${distMiles} miles, about ${travelStr}${delaySpeak}. ${delayLabel}.`);
    }

    function _renderStoresResponse(data) {
        const loc = data.location?.formatted || "your area";

        cachedNearbyStores = [];
        if (data.categories && data.categories.length) {
            data.categories.forEach(cat => cat.stores.forEach(s => cachedNearbyStores.push(s)));
        }

        let html = `<div class="qa-stores-inline">`;
        html += `<div class="qa-stores-inline-title"><i class="fas fa-store"></i> Stores near ${escapeHtml(loc)}</div>`;

        let speechParts = [`Here are the nearby stores in ${loc}.`];
        let spokenCount = 0;

        if (data.categories && data.categories.length) {
            data.categories.forEach(cat => {
                html += `<div class="qa-si-category">${escapeHtml(cat.category)}</div>`;
                cat.stores.forEach(s => {
                    html += `<div class="qa-si-store">`;
                    html += `<div class="qa-si-name">${escapeHtml(s.name)}</div>`;
                    html += `<div class="qa-si-detail">${escapeHtml(s.address)} · ${s.distance_miles} mi</div>`;
                    if (s.phone) html += `<div class="qa-si-detail"><i class="fas fa-phone"></i> ${escapeHtml(s.phone)}</div>`;
                    html += `</div>`;
                    if (spokenCount < 4) { speechParts.push(`${s.name}, ${s.distance_miles} miles away.`); spokenCount++; }
                });
            });
        } else {
            html += `<p style="color:var(--text-dim);padding:10px 0;">No stores found.</p>`;
            speechParts = ["Sorry, I couldn't find stores near your location."];
        }

        if (data.tip) html += `<div class="qa-si-tip"><i class="fas fa-lightbulb"></i> ${escapeHtml(data.tip)}</div>`;
        html += `</div>`;
        addQAMessage(html, false);
        if (_qaWasVoiceQuestion) _speakQAAnswer(speechParts.join(" "));
    }

    function _renderGeneralResponse(data) {
        let html = escapeHtml(data.answer || "Sorry, I couldn't find an answer.");
        if (data.resources && data.resources.length) {
            html += '<div class="qa-resources"><strong>Resources:</strong><ul>';
            data.resources.forEach(r => {
                if (r.startsWith("http")) {
                    html += `<li><a href="${escapeHtml(r)}" target="_blank" rel="noopener">${escapeHtml(r)}</a></li>`;
                } else {
                    html += `<li>${escapeHtml(r)}</li>`;
                }
            });
            html += "</ul></div>";
        }
        addQAMessage(html, false);
        if (_qaWasVoiceQuestion) _speakQAAnswer(data.answer || "");
    }

    // ══════════════════════════════════════════════════════════
    // Voice Interaction (Mic → STT → chat → TTS)
    // ══════════════════════════════════════════════════════════
    let _isRecording = false;
    let _mediaRecorder = null;
    let _audioChunks = [];

    async function toggleVoiceInput() {
        if (_isRecording) {
            _stopRecording();
        } else {
            _startRecording();
        }
    }

    async function _startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            _mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
            _audioChunks = [];

            _mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) _audioChunks.push(e.data);
            };

            _mediaRecorder.onstop = async () => {
                // Stop all tracks
                stream.getTracks().forEach(t => t.stop());

                const blob = new Blob(_audioChunks, { type: "audio/webm" });
                // Use Web Speech API for recognition (client-side, fast)
                _transcribeWithWebSpeech();
            };

            _mediaRecorder.start();
            _isRecording = true;
            qaMicBtn.classList.add("recording");
            qaInput.placeholder = "Listening…";

            // Auto-stop after 15s
            setTimeout(() => { if (_isRecording) _stopRecording(); }, 15000);

            // Use Web Speech API for live transcription
            if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                _qaVoiceRecognizer = new SpeechRecognition();
                _qaVoiceRecognizer.continuous = false;
                _qaVoiceRecognizer.interimResults = true;
                _qaVoiceRecognizer.lang = "en-US";

                _qaVoiceRecognizer.onresult = (event) => {
                    let transcript = "";
                    for (let i = 0; i < event.results.length; i++) {
                        transcript += event.results[i][0].transcript;
                    }
                    qaInput.value = transcript;
                    if (event.results[0].isFinal) {
                        _stopRecording();
                        // Auto-send after final result (mark as voice)
                        setTimeout(() => sendQAQuestion(true), 300);
                    }
                };

                _qaVoiceRecognizer.onerror = () => _stopRecording();
                _qaVoiceRecognizer.onend = () => { /* handled by onstop */ };
                _qaVoiceRecognizer.start();
            }
        } catch (err) {
            addQAMessage("<i class='fas fa-exclamation-circle'></i> Microphone access denied.", false);
        }
    }

    function _stopRecording() {
        _isRecording = false;
        qaMicBtn.classList.remove("recording");
        qaInput.placeholder = "Ask a question…";
        if (_mediaRecorder && _mediaRecorder.state !== "inactive") _mediaRecorder.stop();
        if (_qaVoiceRecognizer) { try { _qaVoiceRecognizer.stop(); } catch (_) {} _qaVoiceRecognizer = null; }
    }

    function _transcribeWithWebSpeech() {
        // Transcription is handled by the live SpeechRecognition API above
        // This is a no-op fallback
    }

    // ── TTS for bot responses (Dragon HD Omni) ───────────────
    let _qaAudioEl = null;
    async function _speakQAAnswer(text) {
        if (!text || text.length < 5) return;
        // Clean HTML tags from answer
        const cleanText = text.replace(/<[^>]*>/g, "").trim();
        if (!cleanText) return;

        try {
            const res = await fetch(`${API_BASE}/api/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: cleanText }),
            });
            if (!res.ok) return;
            const data = await res.json();
            if (!data.audio) return;

            // Decode and play
            const raw = atob(data.audio);
            const arr = new Uint8Array(raw.length);
            for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
            const blob = new Blob([arr], { type: "audio/mp3" });
            const url  = URL.createObjectURL(blob);

            if (_qaAudioEl) { _qaAudioEl.pause(); URL.revokeObjectURL(_qaAudioEl.src); }
            _qaAudioEl = new Audio(url);
            _qaAudioEl.volume = 0.9;
            _qaAudioEl.addEventListener("play",  () => _toggleStopVoiceBtn(true));
            _qaAudioEl.addEventListener("ended", () => _toggleStopVoiceBtn(false));
            _qaAudioEl.addEventListener("pause", () => _toggleStopVoiceBtn(false));
            _qaAudioEl.play().catch(() => {});
        } catch (_) { /* silent — TTS is optional enhancement */ }
    }

    function stopQAVoice() {
        if (_qaAudioEl) {
            _qaAudioEl.pause();
            _qaAudioEl.currentTime = 0;
        }
        _toggleStopVoiceBtn(false);
    }

    function _toggleStopVoiceBtn(show) {
        if (qaStopVoiceBtn) qaStopVoiceBtn.classList.toggle("hidden", !show);
    }

    // ══════════════════════════════════════════════════════════
    // Weather Forecast
    // ══════════════════════════════════════════════════════════
    async function fetchWeatherForecast() {
        if (!_userLat || !_userLon) {
            qaWeatherGrid.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-map-pin"></i><p>Location not detected. Use the Chat tab to enter your ZIP.</p></div>`;
            return;
        }

        qaWeatherGrid.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-spinner fa-spin"></i><p>Loading forecast…</p></div>`;

        try {
            const res = await fetch(`${API_BASE}/api/weather/forecast`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ lat: _userLat, lon: _userLon, days: 7 }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (!data.forecasts || !data.forecasts.length) {
                qaWeatherGrid.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-cloud"></i><p>No forecast data available.</p></div>`;
                return;
            }

            // Check for severe weather in forecast
            const headline = headlineInput ? headlineInput.value.trim().toLowerCase() : "";
            const hasSevere = data.forecasts.some(d =>
                d.precipitation_probability > 70 || d.snow_probability > 50 ||
                (d.wind_speed && d.wind_speed > 40)
            );

            let html = "";
            if (hasSevere) {
                html += `<div class="qa-weather-alert"><i class="fas fa-triangle-exclamation"></i> Severe weather conditions expected in the forecast period</div>`;
            }

            data.forecasts.forEach((d, i) => {
                const date = new Date(d.date);
                const dayName = i === 0 ? "Today" : _DAY_NAMES[date.getDay()];
                const iconClass = _WEATHER_ICONS[d.day_icon] || "fa-cloud";
                const precip = d.precipitation_probability || 0;
                const hi = d.max_temp != null ? Math.round(d.max_temp) : "--";
                const lo = d.min_temp != null ? Math.round(d.min_temp) : "--";

                html += `
                    <div class="qa-weather-day">
                        <div class="qa-weather-day-name">${dayName}</div>
                        <div class="qa-weather-day-icon"><i class="fas ${iconClass}"></i></div>
                        <div class="qa-weather-day-temps">
                            <span class="qa-temp-hi">${hi}°</span>
                            <span class="qa-temp-lo">${lo}°</span>
                        </div>
                        <div class="qa-weather-day-desc">${escapeHtml(d.day_phrase || "")}</div>
                        ${precip > 0 ? `<div class="qa-weather-day-precip"><i class="fas fa-droplet"></i> ${precip}%</div>` : ""}
                    </div>`;
            });

            qaWeatherGrid.innerHTML = html;
        } catch (err) {
            qaWeatherGrid.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-exclamation-circle"></i><p>Failed to load weather data.</p></div>`;
        }
    }

    // ══════════════════════════════════════════════════════════
    // Traffic Check
    // ══════════════════════════════════════════════════════════
    async function checkTraffic() {
        if (!_userLat || !_userLon) {
            qaTrafficResult.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-map-pin"></i><p>Location not detected yet.</p></div>`;
            return;
        }
        const destCity = qaTrafficDest.value;
        if (!destCity) {
            qaTrafficResult.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-flag-checkered"></i><p>Select a destination city.</p></div>`;
            return;
        }

        qaTrafficGoBtn.disabled = true;
        qaTrafficResult.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-spinner fa-spin"></i><p>Checking traffic to ${escapeHtml(destCity)}…</p></div>`;

        try {
            const res = await fetch(`${API_BASE}/api/traffic/route`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    origin_lat: _userLat,
                    origin_lon: _userLon,
                    dest_city: destCity,
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            const travelMin = data.travel_time_minutes || 0;
            const delayMin  = data.traffic_delay_minutes || 0;
            const distMiles = data.distance_miles || 0;
            const normalMin = travelMin - delayMin;

            // Classify delay severity
            let delaySeverity = "good";
            let delayLabel = "Clear";
            if (delayMin > 30) { delaySeverity = "heavy"; delayLabel = "Heavy Delays"; }
            else if (delayMin > 10) { delaySeverity = "moderate"; delayLabel = "Moderate"; }

            const hrs = Math.floor(travelMin / 60);
            const mins = Math.round(travelMin % 60);
            const travelStr = hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`;

            const origin = qaTrafficOrigin.value || "Your Location";

            qaTrafficResult.innerHTML = `
                <div class="qa-traffic-card">
                    <div class="qa-traffic-card-header">
                        <div class="qa-traffic-card-route">
                            <i class="fas fa-route"></i> ${escapeHtml(origin)} → ${escapeHtml(data.destination || destCity)}
                        </div>
                        <div class="qa-traffic-card-dist">${distMiles} mi</div>
                    </div>
                    <div class="qa-traffic-stats">
                        <div class="qa-traffic-stat">
                            <div class="qa-traffic-stat-label">Travel Time</div>
                            <div class="qa-traffic-stat-value ${delaySeverity}">${travelStr}</div>
                        </div>
                        <div class="qa-traffic-stat">
                            <div class="qa-traffic-stat-label">Traffic Delay</div>
                            <div class="qa-traffic-stat-value ${delaySeverity}">
                                ${delayMin > 0 ? `+${Math.round(delayMin)}m` : "0m"}
                                <span class="qa-traffic-stat-unit">${delayLabel}</span>
                            </div>
                        </div>
                        <div class="qa-traffic-stat">
                            <div class="qa-traffic-stat-label">Without Traffic</div>
                            <div class="qa-traffic-stat-value good">
                                ${Math.floor(normalMin/60) > 0 ? Math.floor(normalMin/60) + "h " : ""}${Math.round(normalMin%60)}m
                            </div>
                        </div>
                        <div class="qa-traffic-stat">
                            <div class="qa-traffic-stat-label">Distance</div>
                            <div class="qa-traffic-stat-value">${distMiles}<span class="qa-traffic-stat-unit"> miles</span></div>
                        </div>
                    </div>
                </div>`;
        } catch (err) {
            qaTrafficResult.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-exclamation-circle"></i><p>Failed to get traffic data.</p></div>`;
        }
        qaTrafficGoBtn.disabled = false;
    }

    // ══════════════════════════════════════════════════════════
    // Find Nearby Stores
    // ══════════════════════════════════════════════════════════
    async function findNearbyStores() {
        const zip = qaZipcode.value.trim();
        if (!zip || zip.length < 5) {
            qaStoresBody.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-map-pin"></i><p>Enter a valid 5-digit ZIP code.</p></div>`;
            return;
        }
        qaStoresBtn.disabled = true;
        qaStoresBody.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-spinner fa-spin"></i><p>Finding stores near ${escapeHtml(zip)}…</p></div>`;

        try {
            const res = await fetch(`${API_BASE}/api/stores/nearby`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ zipcode: zip, story_id: currentStoryId || "" }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            if (data.error) {
                qaStoresBody.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-exclamation-circle"></i><p>${escapeHtml(data.error)}</p></div>`;
                qaStoresBtn.disabled = false;
                return;
            }

            // Cache for Q&A context
            cachedNearbyStores = [];
            if (data.categories && data.categories.length) {
                data.categories.forEach(cat => cat.stores.forEach(s => cachedNearbyStores.push(s)));
            }

            let html = `<div class="qa-stores-result">`;
            html += `<div class="qa-stores-header"><i class="fas fa-map-marker-alt"></i> <strong>${escapeHtml(data.location?.formatted || zip)}</strong></div>`;
            if (data.tip) {
                html += `<div class="qa-stores-tip"><i class="fas fa-lightbulb"></i> ${escapeHtml(data.tip)}</div>`;
            }
            if (data.categories && data.categories.length) {
                data.categories.forEach(cat => {
                    html += `<div class="qa-store-category"><strong>${escapeHtml(cat.category)}</strong></div>`;
                    cat.stores.forEach(s => {
                        html += `<div class="qa-store-item">`;
                        html += `<div class="qa-store-name">${escapeHtml(s.name)}</div>`;
                        html += `<div class="qa-store-detail">${escapeHtml(s.address)} · ${s.distance_miles} mi</div>`;
                        if (s.phone) html += `<div class="qa-store-detail"><i class="fas fa-phone"></i> ${escapeHtml(s.phone)}</div>`;
                        html += `</div>`;
                    });
                });
            } else {
                html += `<p style="color:var(--text-dim);padding:20px 0;">No nearby stores found.</p>`;
            }
            html += `</div>`;
            qaStoresBody.innerHTML = html;
        } catch (err) {
            qaStoresBody.innerHTML = `<div class="qa-weather-placeholder"><i class="fas fa-exclamation-circle"></i><p>Store search failed.</p></div>`;
        }
        qaStoresBtn.disabled = false;
    }

    // ── Boot ─────────────────────────────────────────────────
    document.addEventListener("DOMContentLoaded", () => { init(); setupQA(); });

})();
