# ⚡ BOLT – Personal Autonomous AI Assistant for Windows

**BOLT** is a personal autonomous AI assistant designed for Windows 11. It combines intelligent task planning, computer vision, Windows automation, browser interaction, and voice control to turn natural-language instructions into real-world computer actions.

---

## 🎯 Current Milestone: Phase 7 – Offline Voice Assistant for BOLT (COMPLETED)

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
│   └── bolt.db           # SQLite database (conversations, registry, workflows, tasks, memory)
├── logs/
│   └── bolt.log          # Application log file (rotating)
└── bolt/
    ├── ai/               # AI Providers (Gemini, OpenAI, Mock, Local Ollama, Multi-AI, Router)
    ├── browser/          # Browser automation (Playwright, Tab reuse, Registry, Search)
    ├── config/           # App settings and environment loader
    ├── core/             # Database, Logger, Network manager, Error handling
    ├── tasks/            # DAG Planner, Execution engine, Multitasking manager, Tool registry
    ├── ui/               # PySide6 desktop interface (Main window, Activity dock, Input bar, Styles)
    ├── voice/            # Phase 7 Voice subsystem (TTS engine, Speech recognizer, Wake word, Pipeline)
    └── windows/          # Windows automation (Apps, Windows, Files, UI Automation, Vision, OCR)
├── run.py                # Main application entry point
├── data/
│   └── bolt.db           # SQLite database (conversations, registry, workflows, tasks, memory)
├── logs/
│   └── bolt.log          # Application log file (rotating)
├── tests/
│   ├── test_e2e_interaction.py          # Phase 1 UI E2E test
│   ├── test_phase2.py                   # Phase 2 Windows control tests
│   ├── test_phase3.py                   # Phase 3 browser tests
│   ├── test_phase3_ui_interaction.py    # Phase 3 UI E2E test
│   ├── test_phase4.py                   # Phase 4 AI integration tests
│   ├── test_phase4_ui_interaction.py    # Phase 4 AI E2E test
│   ├── test_phase5.py                   # Phase 5 Task Planning tests
│   ├── test_phase5_ui_interaction.py    # Phase 5 UI E2E test
│   ├── test_offline_and_real_control.py # Offline-First, Ollama, & Real Control tests
│   └── test_phase6_event_driven.py      # Phase 6 Event-Driven & UI Automation tests
└── bolt/
    ├── config/           # Application constants & settings management
    ├── core/             # SQLite persistence, network manager, learning memory, logger
    ├── ai/               # OllamaProvider, GeminiProvider, OpenAIProvider, router, comparator
    ├── browser/          # Browser detector, Playwright controller, registry, reader, search
    ├── windows/          # App discovery, lifecycle, SendInput, UIA, VisionEngine, HybridController
    ├── voice/            # Local Windows SAPI voice synthesis
    ├── ui/               # PySide6 desktop interface and components
    │   └── components/   # Header, Sidebar, ChatView, InputBar, TaskStatus, TaskActivityPanel
    └── tasks/            # Models, Planner, DependencyManager, ExecutionEngine, Recovery, Memory
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
Run with the virtual environment Python:
```powershell
.\.venv\Scripts\python.exe run.py
```

### 4. Running Automated Tests
```powershell
# Run the complete test suite (59 tests):
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# Run Offline-First and Real Control verification (12 tests):
.\.venv\Scripts\python.exe -m unittest tests/test_offline_and_real_control.py
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
