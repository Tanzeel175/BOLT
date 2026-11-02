# ⚡ BOLT – Personal Autonomous AI Assistant for Windows

**BOLT** is a personal autonomous AI assistant designed for Windows 11. It combines intelligent task planning, computer vision, Windows automation, browser interaction, and voice control to turn natural-language instructions into real-world computer actions.

---

## 🎯 Current Milestone: Phase 4 – AI Application Integration (COMPLETED)

### Phase 1 Features:
- 🖥️ **PySide6 Modern Dark-Themed Desktop Interface** tailored for Windows 11.
- ⚡ **BOLT Brand Header & Status Dashboard**: Active provider/model badges, status indicators, and clean controls.
- 💬 **Conversation View**: Rich message cards with Markdown rendering (code blocks, syntax highlighting, bullet points, tables, blockquotes) and one-click copy.
- ⌨️ **Input Bar**: Multi-line command input with Enter to send, Shift+Enter for newlines, and a Phase 7 voice microphone placeholder.
- 🧠 **Configurable AI Providers**: Google Gemini, OpenAI-compatible, and Local Mock.
- 🔒 **Secure Credential Storage**: API keys stored in `.env` and masked in settings.
- 🗄️ **Persistent SQLite History**: Multi-session conversations, automatic title generation, and message history in WAL mode.
- 📊 **Task Status Area**: Real-time worker state ("Ready", "Thinking...", "Completed"), model telemetry, and Windows system specs.
- 📜 **Enterprise Logging**: Rotating file logging (`logs/bolt.log`) and console output.

### Phase 2 Features (Windows & Application Control):
- 🔍 **Deep Application Discovery**: Indexed 120+ applications across Start Menu, Registry, and System paths.
- 🪟 **C-Types Window Management**: Seamless window enumeration, switching, minimize/maximize, and safe closing.
- 🛡️ **Protected Process Defense**: Immune protection for critical Windows OS processes (`explorer`, `dwm`, `svchost`).
- 📊 **Real-Time Hardware Telemetry**: Live CPU, RAM, Disk, and Battery diagnostics.

### Phase 3 Features (Browser & Website Intelligence):
- 🌐 **Browser Detection & Management**: Automatic detection of Chrome, Edge, Firefox, and Brave with default browser resolution.
- 🔄 **Session Reuse**: Dispatches URLs to active browser processes without spawning duplicate instances or profile locks.
- 🗃️ **Persistent Website Registry**: SQLite-backed knowledge base with URL validation and seed sites (ChatGPT, Gemini, Gmail, YouTube, Google Drive).
- 🔍 **Live Search Engine**: Bing web search integration with clean URL resolution and provider search shortcuts (Google, YouTube).
- 📄 **Webpage Content Understanding**: Heading extraction (`H1`-`H3`), executive summarization, and notable links analysis.
- 🔒 **Security-First Auth Detection**: Automatically detects login pages and prompts for manual authentication without capturing credentials.
- 🛠️ **Structured Tool Registry**: LLM tool calling schema preventing arbitrary script execution.

### Phase 4 Features (AI Application Integration):
- 🤖 **Modular AI Architecture**: Standardized provider interface supporting official Google Gemini and OpenAI ChatGPT APIs.
- 🔄 **Runtime Provider Switching**: Switch between Gemini, OpenAI, and Local mode on the fly without restarting BOLT.
- ⚖️ **Multi-AI Comparison**: Concurrently queries multiple AI services (e.g., Gemini and ChatGPT) with identical prompts and synthesizes consensus and stylistic differences.
- 🛡️ **Zero-Faking Error Handling**: Provides actionable troubleshooting cards when credentials are missing or invalid, never feigning fake responses.
- 📋 **AI Workflow Artifacts**: Prepares structured drafts (e.g. professional emails, error diagnoses) for future automated workflow pipelines.
- 🌐 **Dual Integration Modes**: Method A (programmatic API queries) vs Method B (automated browser interaction via Phase 3 Browser Manager).

---

## 📁 Project Architecture

```
BOLT/
├── .env                  # Secure environment credentials & configuration
├── .env.example          # Environment variables template
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project metadata
├── README.md             # Project documentation
├── run.py                # Main application entry point
├── data/
│   └── bolt.db           # SQLite database (conversations, messages, tasks)
├── logs/
│   └── bolt.log          # Application log file (rotating)
└── bolt/
    ├── __init__.py
    ├── config/           # Application constants & settings management
    │   ├── constants.py
    │   └── settings.py
    ├── core/             # Persistence and logging engine
    │   ├── database.py
    │   └── logger.py
    ├── ai/               # AI providers (Gemini, OpenAI, Mock) & router
    │   ├── base.py
    │   ├── gemini_provider.py
    │   ├── openai_provider.py
    │   ├── mock_provider.py
    │   └── router.py
    ├── windows/          # Phase 2 Windows automation, discovery & dispatch
    ├── browser/          # Phase 3 Browser detection, registry, search & content reader
    ├── tasks/            # Tool registry & execution engine
    └── ui/               # PySide6 desktop interface
```

---

## 🚀 Getting Started

### 1. Requirements
- Windows 11 64-bit
- Python 3.10+ (tested on Python 3.13)

### 2. Launching BOLT
Run with the virtual environment Python:
```powershell
.\.venv\Scripts\python.exe run.py
```

### 3. Configuring your AI API Key
1. Click **⚙ Settings** in the top-right of the BOLT window.
2. Select **Google Gemini** or **OpenAI**.
3. Enter your API key (get a free Gemini key at [Google AI Studio](https://aistudio.google.com/)).
4. Click **🔌 Test Connection** and then **💾 Save Configuration**.

---

## 🗺️ 10-Phase Roadmap
- [x] **Phase 1:** BOLT Foundation and Desktop Interface
- [ ] **Phase 2:** Computer Understanding and Application Control
- [ ] **Phase 3:** Browser and Website Intelligence
- [ ] **Phase 4:** AI Application Integration
- [ ] **Phase 5:** Intelligent Task Planning and Multitasking
- [ ] **Phase 6:** Visual Computer Use
- [ ] **Phase 7:** Voice Assistant
- [ ] **Phase 8:** Long-Term Memory and Learning
- [ ] **Phase 9:** Security and Approval System
- [ ] **Phase 10:** Final Desktop Application
