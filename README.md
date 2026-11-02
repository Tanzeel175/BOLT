# ⚡ BOLT – Personal Autonomous AI Assistant for Windows

**BOLT** is a personal autonomous AI assistant designed for Windows 11. It combines intelligent task planning, computer vision, Windows automation, browser interaction, and voice control to turn natural-language instructions into real-world computer actions.

---

## 🎯 Current Milestone: Phase 5 – Intelligent Task Planning & Multitasking (COMPLETED)

### Complete Implemented Capabilities:

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
- 🎯 **Core Workflows Implemented**:
  - **Workflow A (AI Research)**: Search web -> Collect sources -> AI summarize with citations.
  - **Workflow B (Email Preparation)**: Draft email -> Display -> Approval gate -> Open Gmail -> Require explicit approval before sending.
  - **Workflow C (Programming Assistance)**: Locate project -> Open in VS Code -> Run in sandbox -> AI error diagnosis -> Require approval before modifying code.
  - **Workflow D (Document Processing)**: Locate document -> Read content -> Summarize -> Write separate file -> Verify file integrity.

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
│   └── bolt.db           # SQLite database (conversations, registry, workflows, tasks)
├── logs/
│   └── bolt.log          # Application log file (rotating)
├── tests/
│   ├── test_e2e_interaction.py       # Phase 1 UI E2E test
│   ├── test_phase2.py                # Phase 2 Windows control tests
│   ├── test_phase3.py                # Phase 3 browser tests
│   ├── test_phase3_ui_interaction.py # Phase 3 UI E2E test
│   ├── test_phase4.py                # Phase 4 AI integration tests
│   ├── test_phase4_ui_interaction.py # Phase 4 UI E2E test
│   ├── test_phase5.py                # Phase 5 Task Planning tests
│   └── test_phase5_ui_interaction.py # Phase 5 UI E2E test
└── bolt/
    ├── config/           # Application constants & settings management
    ├── core/             # SQLite persistence, telemetry, and logger
    ├── ai/               # Multi-provider AI system, comparator, router
    ├── browser/          # Browser detector, Playwright controller, registry, reader
    ├── windows/          # App discovery, lifecycle, window & file managers, intent dispatcher
    ├── ui/               # PySide6 desktop interface and components
    │   └── components/   # Header, Sidebar, ChatView, InputBar, TaskStatus, TaskActivityPanel
    └── tasks/            # Models, Planner, DependencyManager, ExecutionEngine, Recovery, Memory
```

---

## 🚀 Getting Started

### 1. Requirements
- Windows 11 64-bit
- Python 3.10+ (tested on Python 3.13)
- Playwright browsers: `playwright install msedge` / `playwright install chromium`

### 2. Launching BOLT
Run with the virtual environment Python:
```powershell
.\.venv\Scripts\python.exe run.py
```

### 3. Running Automated Tests
```powershell
# Phase 1
.\.venv\Scripts\python.exe -u tests/test_e2e_interaction.py

# Phase 2
.\.venv\Scripts\python.exe -u tests/test_phase2.py

# Phase 3
.\.venv\Scripts\python.exe -u tests/test_phase3.py
.\.venv\Scripts\python.exe -u tests/test_phase3_ui_interaction.py

# Phase 4
.\.venv\Scripts\python.exe -u tests/test_phase4.py
.\.venv\Scripts\python.exe -u tests/test_phase4_ui_interaction.py

# Phase 5
.\.venv\Scripts\python.exe -u tests/test_phase5.py
.\.venv\Scripts\python.exe -u tests/test_phase5_ui_interaction.py
```

---

## 🗺️ 10-Phase Roadmap
- [x] **Phase 1:** BOLT Foundation and Desktop Interface
- [x] **Phase 2:** Computer Understanding and Application Control
- [x] **Phase 3:** Browser and Website Intelligence
- [x] **Phase 4:** AI Application Integration
- [x] **Phase 5:** Intelligent Task Planning and Multitasking
- [ ] **Phase 6:** Visual Computer Use
- [ ] **Phase 7:** Voice Assistant
- [ ] **Phase 8:** Long-Term Memory and Learning
- [ ] **Phase 9:** Security and Approval System
- [ ] **Phase 10:** Final Desktop Application
