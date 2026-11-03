# ⚡ BOLT – Personal Autonomous AI Assistant for Windows

**BOLT** is a personal autonomous AI assistant designed for Windows 11. It combines intelligent task planning, computer vision, Windows automation, browser interaction, and voice control to turn natural-language instructions into real-world computer actions.

---

## 🎯 Current Milestone: Phase 11 – Real-World Testing & Intelligence Improvement (COMPLETED — 100% Complete)

### Complete Implemented Capabilities:

#### 11. Real-World Testing & Intelligence Improvement (Phase 11)
- 🧪 **Comprehensive System Audit**: Exhaustive verification across Desktop UI, Local/Cloud AI, Windows Control, Browser Automation, Search, DAG Planning, Voice, Memory, and Security.
- 🗣️ **Flexible Natural Language Understanding (NLU)**: Robust handling of natural conversational commands without rigid syntax (e.g., *"Find the Python project I was working on yesterday"*, *"Compare the information from these two websites"*, *"Open my downloads folder and find the most recent PDF"*).
- 🔄 **Real Multi-App Multitasking Workflows**: Autonomous execution of compound workflows across browser research, local file synthesis, workspace code diagnostics, and AI reporting.
- 🧠 **Dynamic Preference & Workspace Retention**: Permanent SQLite storage with automatic punctuation and preposition normalization for preferences (`preferred_browser`, `workspace_location`).
- 🛡️ **Autonomous Fault Recovery & Cascade**: Uninstalled browser/editor fallback (Notepad/Edge), multi-tier AI fallback (Gemini/OpenAI -> Ollama -> Mock), and dynamic token dependency piping.
- 📊 **Empirical Performance Benchmarking**: 1.17s startup latency, 23ms storage init, 8ms FTS5 retrieval, 0.67ms DAG planning, and 11.13 tokens/sec local inference (`gemma4:e2b`).
- 💯 **100% Regression Suite Pass**: All 146 unit, integration, and empirical acceptance tests verified.

#### 10. Desktop Application & Windows Deployment (Phase 10)
- 📦 **Standalone PyInstaller Packaging (`bolt.spec`)**: Configured for Windows 11 64-bit with onedir distribution, embedded PE version metadata, application icons, and automatic resource bundling.
- 📂 **Persistent User Data Isolation (`%LOCALAPPDATA%\BOLT`)**: Separates application binaries from persistent user data (`bolt.db`, logs, backups, memory), ensuring zero data loss during application updates, reinstalls, or PyInstaller temp directory extraction.
- 💾 **Live WAL SQLite Backups & Restorations**: Uses native SQLite online backup API (`conn.backup()`) to capture atomic point-in-time snapshots during active WAL mode without locking or concurrency errors.
- 🔄 **Automated Pre-Migration Snapshots & Pruning**: Captures safety snapshots before schema migrations and provides automated backup rotation (`clean_old_backups`).
- 🧙 **First-Run Guided Setup Wizard (`bolt/ui/setup_wizard.py`)**: Automatic first-run onboarding verifying Windows 11 compatibility, 16 GB RAM host, local Ollama runtime, `gemma4:e2b` model, microphone hardware, and optional cloud keys.
- ⚙️ **Tabbed Settings & Configuration Dialog (`bolt/ui/settings_dialog.py`)**: Centralized management for AI Brain, Voice & Audio, Security Permissions, Default Browser, and Live Backups with safe defaults reset.
- 🔔 **Windows System Tray & Background Operations (`bolt/ui/system_tray.py`)**: System tray icon with background minimize, context menu, and native desktop notifications for tasks and security events.
- ⚡ **1-Click Launchers & Shortcuts**: `run.bat` batch launcher, `scripts/build_executable.py` automated build script, and `scripts/create_shortcut.ps1` PowerShell desktop shortcut installer.

#### 1. Foundation & Desktop Interface (Phase 1)
- 🖥️ **PySide6 Dark-Themed Desktop Interface** tailored for Windows 11.
- ⚡ **BOLT Brand Header & Status Dashboard**: Active provider/model badges, status indicators, and controls.
- 💬 **Conversation View**: Rich message cards with Markdown rendering, code highlighting, and one-click copy.
- ⌨️ **Input Bar**: Multi-line command input with Enter to send, Shift+Enter for newlines.
- 🗄️ **Persistent SQLite History**: Multi-session conversations, automatic title generation, and message history in WAL mode.
- 📊 **Task Status Area**: Real-time worker state, model telemetry, and Windows system specs.
- 📜 **Enterprise Logging**: Rotating file logging (`logs/bolt.log`) and safe Unicode console output.

#### 2. Computer Understanding & Windows Control (Phase 2)
- 🔍 **Application Discovery Engine**: Automatic detection across Start Menu shortcuts, Windows App Paths, Registry, and standard directories.
- 🗃️ **Persistent SQLite Application Registry**: Tracks paths, launch methods, aliases, launch verification, and success history.
- 🚀 **Application Lifecycle Controller**: Safe launching, duplicate window prevention, and verified termination.
- 🪟 **Window Management**: Enumerates visible top-level windows, window switching/focusing (`user32.SetForegroundWindow`), minimizing, and maximizing.
- 📁 **File & Folder Operations**: Folder aliasing (`desktop`, `downloads`, `documents`, `pictures`) and multi-directory file search.
- 🛡️ **Protected Process Security**: Guardrails preventing termination of critical Windows system processes (`explorer.exe`, `csrss.exe`, `winlogon.exe`, `python.exe`).

#### 3. Browser & Website Intelligence (Phase 3)
- 🌐 **Browser Detection**: Detects Microsoft Edge, Google Chrome, Brave, Firefox, and reads the default Windows browser.
- 📑 **Playwright Browser Navigation**: Automated browser control using installed browser channels.
- 🔄 **Smart Tab Management & Reuse**: Automatically reuses existing open tabs to avoid duplicate browser windows.
- 🗄️ **Website Registry**: Seeded with ChatGPT, Gemini, Gmail, Google, Google Drive, and YouTube; supports dynamic URL validation and aliasing.
- 🔍 **Search Engine & Content Reader**: Web search across Google, YouTube, DuckDuckGo, and GitHub; reads accessible page content, headings, and outlines.
- 🔐 **Authentication Wall Detection**: Detects login forms and credentials walls, advising users to sign in manually for safety.

#### 4. AI Application Integration (Phase 4)
- 🧠 **Modular AI Provider Architecture**: Standardized abstraction supporting Google Gemini, OpenAI ChatGPT, and offline Mock/Local fallback.
- 🔄 **Runtime Provider Switching**: Swap default providers without restarting BOLT (`"Switch to Gemini"`, `"Switch to ChatGPT"`).
- ⚖️ **Multi-AI Comparison Engine**: Parallel queries to multiple providers with side-by-side comparative Markdown reporting (`"Compare how Gemini and ChatGPT explain recursion"`).
- 🎯 **Explicit Provider Query Routing**: Directs single requests to specified models (`"Ask Gemini to..."`).
- 🔀 **Dual-Method AI Integration**: Seamlessly switches between programmatic API (Method A) and browser-based web navigation (Method B: `"Open ChatGPT in my browser"`).
- 🔒 **Zero-Faking Security Policy**: When API keys are missing, provides actionable setup instructions instead of fabricated responses; masks keys in settings and logs.

#### 5. Intelligent Task Planning and Multitasking (Phase 5)
- 📋 **Directed Acyclic Graph (DAG) Task Planner**: Decomposes complex multi-action instructions into validated execution steps with dependencies, inputs, outputs, and risk levels.
- 🔀 **Task Dependency Management & Data Piping**: Resolves placeholder tokens (`${step_id.attribute}`) to pipe data from earlier steps into dependent inputs; runs independent steps in parallel.
- 🔄 **Autonomous Fault Recovery**: Automatic retries for transient faults and fallback routes (Google -> DuckDuckGo -> Bing; Gemini -> OpenAI -> Local Mock; broad file searches).
- 🛑 **Human-in-the-Loop Approval Gates**: Enforces strict approval gates on sensitive actions (email sending, file modifications, script execution) before continuing.
- 🧠 **Workflow Memory & Reuse**: SQLite persistence in `workflows` table allowing BOLT to recall and re-execute successful past procedures (*"Do the same process you used last time to prepare my research summary"*).
- 🖥️ **Task Activity Panel (PySide6)**: Collapsible activity dock with real-time progress bar (0–100%), interactive step checklist, and `Pause ⏸`, `Resume ▶`, `Cancel ⏹`, `Approve ✅`, `Reject ❌` controls.

#### 6. Offline-First Intelligence & Real Computer Control
- 🧠 **Ollama Local AI as Default Brain**: Connects to `http://127.0.0.1:11434` with recommended model `gemma4:e2b`. Zero cloud dependency for core computer actions.
- 🛡️ **Zero Automatic Downloads & Zero Silent Cloud Fallback**: If the local model is not downloaded, BOLT informs the user with exact terminal instructions (`ollama run gemma4:e2b`) without downloading gigabytes behind the user's back or silently leaking queries to cloud APIs.
- 🔌 **Fast Internet Detection & Graceful Offline Exit**: DNS socket probes detect internet disconnection in milliseconds. If online search is requested offline, BOLT immediately reports graceful notification.
- ⚖️ **Mixed-Task Partial Completion (`PARTIALLY_COMPLETED`)**: For mixed tasks, offline search failure does not cancel local operations.
- 💾 **Persistent Learning Memory**: 7 SQLite memory categories, user correction learning with prompt context injection, and LoRA fine-tuning JSONL dataset export.

#### 7. Event-Driven Computer Control & UI Automation (Phase 6)
- ⚡ **Zero Routine Screenshots**: Eliminates screenshot-heavy visual polling in favor of a 5-tier priority hierarchy:
  1. Direct Windows APIs & Process Tools (Win32, ShellExecute, Direct File API).
  2. Windows UI Automation & Accessibility APIs (control trees, `InvokePattern`, `ValuePattern`, `TextPattern`).
  3. Keyboard Shortcuts & Win32 `SendInput` Unicode stream.
  4. Local Windows Media OCR (`winocr` running 100% on CPU).
  5. Screenshot-on-Demand & Local Vision AI (captured only when UI Automation fails or explicitly requested).
- 🪟 **UI Automation Manager (`bolt.windows.ui_automation`)**:
  - Interactive desktop thread attachment (`SetThreadDesktop`) preventing background isolation failures.
  - Windows 11 UWP Application Frame resolution (`ApplicationFrameWindow` and `CoreWindow`).
  - Semantic button invocation (`InvokePattern`, `TogglePattern`, `LegacyIAccessiblePattern`).
  - Native Calculator control: calculates complex mathematical expressions (e.g., `125 * 25 = 3125`) with zero screenshots.
- 👁️ **Vision Engine (`bolt.windows.vision_engine`)**:
  - Screenshot-on-Demand with pixel difference verification (`has_screen_changed`).
  - Native Windows Media OCR with thread-safe execution (no event-loop collisions).
  - Local visual error diagnosis classifying error dialogs without cloud transmission.
- 🏎️ **Performance Benchmark Suite (`bolt.windows.performance_benchmark`)**:
  - Empirically measures time (ms), RAM delta (MB), CPU usage, and success rates across Direct APIs, UI Automation, and Vision operations.
- 🛠️ **30 Registered System Tools (`bolt.tasks.tool_registry`)**: Fully registered tools covering system actions, browser control, UI automation, file ops, local OCR, and voice control.

#### 8. Offline Voice Assistant (Phase 7)
- 🎙️ **Hardware Audio Detection & VAD (`bolt.voice.speech_recognizer`)**:
  - Automatically discovers microphone input devices via `sounddevice` and measures ambient background noise floor.
  - Energy-based Voice Activity Detection (VAD) detects start of speech and trailing silence.
- 🗣️ **Offline Speech-to-Text (STT)**:
  - Powered locally by **Vosk** with zero cloud speech APIs.
  - Faster-Whisper evaluated; Windows 11 WDAC policy restrictions documented.
  - **Zero Auto-Download Policy**: Does not download large neural models silently; provides clear instructions for manual model installation.
- 🔊 **Offline Text-to-Speech (TTS) (`bolt.voice.tts_engine`)**:
  - Windows native SAPI synthesis with discovered English voices (`Microsoft Hazel Desktop - UK`, `Microsoft Zira Desktop - US`).
  - Configurable speech rate (100–300 words/min), real-time speech interruptibility (`"Stop speaking"`), and echo-cancellation gating.
  - Automatic spoken text sanitization (strips Markdown, URLs, and code blocks for concise verbal delivery).
- 🔄 **Voice Interaction Pipeline (`bolt.voice.voice_pipeline`)**:
  - Glues Microphone -> VAD -> STT -> IntentDispatcher -> ToolRegistry/TaskEngine -> Execution Verification -> TTS feedback.
  - Operates using the **exact same task execution engine** as typed instructions (no separate voice-only hacks).
  - Push-to-Talk as the reliable default with dynamic recording UI feedback.
  - Optional local wake word detector (`"Hey Bolt"`).
- 💬 **Continuous Multi-Turn Conversation Mode (`bolt.voice.conversation_mode`)**:
  - Maintains active listening state for a configurable follow-up window (default 8s).
  - Enables fluid back-and-forth commands without repeating the wake phrase (e.g., *"Open Calculator"* followed by *"Calculate 250 divided by 5"*).
- 🛑 **Voice Safety & Approval Gates**:
  - Automatically holds sensitive actions in voice approval state until the user speaks confirmation (*"yes"*, *"confirm"*).

#### 9. Long-Term Memory and Continuous Learning (Phase 8)
- 💾 **100% Offline SQLite Memory Architecture (`bolt.memory`)**:
  - Fully local SQLite storage in `bolt_memories` table with zero external cloud memory dependencies or online embedding APIs.
  - Retains all preferences, computer knowledge, workflows, and learned corrections across application closes, Windows restarts, internet disconnects, and local AI model swaps.
- 🗃️ **5 Dedicated Memory Categories**:
  1. `personal_preferences`: Preferred browser per-site or global (*"Always open ChatGPT in Chrome"*), default coding IDE, text editors, working directories, voice, and response style.
  2. `computer_knowledge`: Discovered application paths, launch methods, verified directory locations, and automation procedures. Includes automated disk path verification (`verify_computer_knowledge()`) to detect moved or uninstalled applications.
  3. `workflow_memory`: Stores multi-step task execution blueprints, tools selected, applications used, successful outcomes, and recovery procedures for instant reuse (*"Prepare my research summary using the same process as last time"*).
  4. `conversation_memory`: Structured context extraction (`ConversationContextExtractor`) tracking active project names, ongoing tasks, and referenced files without saving raw conversational message dumps.
  5. `corrections`: Automatic learning from user corrections (*"You opened Edge, but I prefer Chrome"*) and explicit directives (*"Always open ChatGPT in Chrome"*), updating permanent preferences with confirmation.
- 🔍 **Lightweight Semantic Retrieval & Gating (`bolt.memory.retriever`)**:
  - SQLite FTS5 BM25 full-text indexing (`bolt_memories_fts`) combined with domain-specific synonym expansion.
  - Strict relevance gating (`min_relevance=0.28`) ensuring unrelated memories are never returned.
- 🛠️ **7 Registered Memory Tools (`bolt.tasks.tool_registry`)**:
  `memory_save`, `memory_retrieve`, `memory_update`, `memory_search`, `memory_delete`, `memory_list`, `memory_export` (bringing total registry tools to 37).

#### 10. Security, Permissions and Approval System (Phase 9)
- 🛡️ **Central Permission Manager (`bolt.security.permission_manager`)**:
  - Enforces mandatory security clearance on every tool execution across BOLT. Individual modules and tool runners cannot bypass the permission layer.
  - 100% offline security operation with zero cloud or external API transmission.
- 🚦 **4-Tier Action Risk Classification (`bolt.security.risk_classifier`)**:
  - **Level 1 — Low Risk (Autonomous):** Ordinary application launching/switching, browser navigation, internet search, file reading, system specs inspection, and local voice synthesis execute automatically without prompting.
  - **Level 2 — Moderate Risk (Contextual Approval):** File modifications, project script executions, and file moving. Automatically computes and renders a unified diff preview (`difflib.unified_diff`) showing exact lines added and deleted before approval. Whitelisted trusted directories and active session grants bypass contextual prompts.
  - **Level 3 — High Risk (Explicit Approval):** Sending emails, deleting files, submitting forms, and modifying security policies. Displays destination, parameters, and full draft preview; requires explicit approval once or for the session.
  - **Level 4 — Critical Risk (Strong Confirmation + Typed Phrase):** Directory deletions, operations targeting Windows system paths (`C:\Windows`, `System32`), and commands with administrator privilege elevation tokens (`runas`, `Start-Process -Verb RunAs`). Strictly requires typing the confirmation phrase (`CONFIRM`) on screen. Simple voice or affirmative button clicks are rejected.
- 📜 **Immutable Security Audit Logging (`bolt.security.audit_logger`)**:
  - Persists all security checks, evaluations, grants, rejections, and policy blocks in SQLite table `security_audit_logs` and rotating file `logs/security.log`.
  - Built-in audit querying, statistics, and local export to JSON and JSONL formats.
- 🖥️ **Interactive PySide6 Security Interface (`bolt.ui.components.task_activity_panel`)**:
  - Color-coded risk badges (🟡 MODERATE, 🟠 HIGH, 🔴 CRITICAL).
  - Target destination, action justification, and monospace diff/draft preview area.
  - `✅ Approve Once`, `🛡️ Allow Session`, `❌ Reject`, and dedicated typed confirmation field for Critical tasks.
- 🛠️ **41 Registered Tools (`bolt.tasks.tool_registry`)**: Includes safe file/directory deletion tools and security policy inspection/revocation utilities.

---

## 📁 Project Architecture

```
BOLT/
├── .env                  # Secure environment credentials (ignored from git)
├── .env.example          # Environment variables template
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project metadata
├── README.md             # Project documentation
├── DEVELOPMENT_PROGRESS.md # Phase-by-phase development tracker
├── run.py                # Main application entry point
├── data/
│   └── bolt.db           # SQLite database (conversations, registry, workflows, tasks, memory, audit)
├── logs/
│   ├── bolt.log          # Application log file (rotating)
│   └── security.log      # Security audit log file (rotating)
├── bolt/
│   ├── ai/               # AI Providers (Ollama, Gemini, OpenAI, Mock, Multi-AI, Router)
│   ├── browser/          # Browser automation (Playwright, Tab reuse, Registry, Search)
│   ├── config/           # App settings and environment loader
│   ├── core/             # Database, Logger, Network manager, Error handling
│   ├── memory/           # Phase 8 Long-Term Memory (Manager, Models, Retriever, FTS5, Corrections)
│   ├── security/         # Phase 9 Security Subsystem (PermissionManager, RiskClassifier, AuditLogger)
│   ├── tasks/            # DAG Planner, Execution engine, Multitasking manager, Tool registry
│   ├── ui/               # PySide6 desktop interface (Header, ChatView, InputBar, ActivityDock)
│   ├── voice/            # Phase 7 Voice subsystem (TTS engine, Speech recognizer, Wake word, Pipeline)
│   └── windows/          # Windows automation (Apps, Windows, Files, UI Automation, Vision, OCR)
└── tests/
    ├── test_e2e_interaction.py          # Phase 1 UI E2E test
    ├── test_phase2.py                   # Phase 2 Windows control tests
    ├── test_phase3.py                   # Phase 3 browser tests
    ├── test_phase3_ui_interaction.py    # Phase 3 UI E2E test
    ├── test_phase4.py                   # Phase 4 AI integration tests
    ├── test_phase4_ui_interaction.py    # Phase 4 AI E2E test
    ├── test_phase5.py                   # Phase 5 Task Planning tests
    ├── test_phase5_ui_interaction.py    # Phase 5 UI E2E test
    ├── test_offline_and_real_control.py # Offline-First, Ollama, & Real Control tests
    ├── test_phase6_event_driven.py      # Phase 6 Event-Driven & UI Automation tests
    ├── test_phase7_voice.py             # Phase 7 Voice Assistant tests
    ├── test_phase8_memory.py            # Phase 8 Long-Term Memory & Learning tests
    └── test_phase9_security.py          # Phase 9 Security, Permissions & Approval tests
```

---

## 🚀 Getting Started

### 1. Requirements
- Windows 11 64-bit (Intel Core i7 / i5, 16 GB RAM)
- Python 3.10+ (tested on Python 3.13)
- Playwright browsers: `playwright install msedge` / `playwright install chromium`
- Ollama runtime (for offline local AI): [ollama.ai](https://ollama.ai)

### 2. Setting Up Local AI (Ollama)
Ollama is the default offline brain for BOLT:
```powershell
# In PowerShell:
ollama run gemma4:e2b
```

### 3. Launching BOLT
You can launch BOLT instantly without opening an IDE:
```powershell
# 1-Click Launch via batch file:
.\run.bat

# Or run via virtual environment Python:
.\.venv\Scripts\python.exe run.py
```

### 4. Standalone Windows Packaging (PyInstaller)
```powershell
# Build standalone Windows 11 executable:
.\.venv\Scripts\python.exe scripts/build_executable.py

# Install Desktop and Start Menu shortcuts:
powershell -ExecutionPolicy Bypass -File scripts/create_shortcut.ps1
```

### 5. Running Automated Tests
```powershell
# Run the complete regression test suite (146 tests across all 11 phases):
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# Run Phase 11 Real-World Acceptance tests (22 tests):
.\.venv\Scripts\python.exe -m unittest tests/test_phase11_real_world.py
```

---

## 🗺️ 11-Phase Roadmap
- [x] **Phase 1:** BOLT Foundation and Desktop Interface
- [x] **Phase 2:** Computer Understanding and Application Control
- [x] **Phase 3:** Browser and Website Intelligence
- [x] **Phase 4:** AI Application Integration
- [x] **Phase 5:** Intelligent Task Planning and Multitasking
- [x] **Phase 6:** Visual Computer Use & Event-Driven Control
- [x] **Phase 7:** Offline Voice Assistant
- [x] **Phase 8:** Long-Term Memory and Continuous Learning
- [x] **Phase 9:** Security, Permissions and Approval System
- [x] **Phase 10:** Final Desktop Application and Windows Deployment
- [x] **Phase 11:** Real-World Testing and Intelligence Improvement (100% COMPLETED)
