# ⚡ BOLT – Personal Autonomous AI Assistant for Windows

**BOLT** is a personal autonomous AI assistant designed for Windows 11. It combines intelligent task planning, computer vision, Windows automation, browser interaction, and voice control to turn natural-language instructions into real-world computer actions.

---

## 🎯 Current Milestone: Phase 1 – Foundation & Desktop Interface

### Phase 1 Features:
- 🖥️ **PySide6 Modern Dark-Themed Desktop Interface** tailored for Windows 11.
- ⚡ **BOLT Brand Header & Status Dashboard**: Active provider/model badges, status indicators, and clean controls.
- 💬 **Conversation View**: Rich message cards with Markdown rendering (code blocks, syntax highlighting, bullet points, tables, blockquotes) and one-click copy.
- ⌨️ **Input Bar**: Multi-line command input with Enter to send, Shift+Enter for newlines, and a Phase 7 voice microphone placeholder.
- 🧠 **Configurable AI Providers**:
  - **Google Gemini** (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-1.5-flash`, etc.)
  - **OpenAI / OpenAI-Compatible** (GPT-4o, GPT-4o-mini, Groq, OpenRouter, Ollama)
  - **Built-in Local/Diagnostic Engine** for offline testing and hardware diagnostics.
- 🔒 **Secure Credential Storage**: API keys stored in `.env` and masked in settings.
- 🗄️ **Persistent SQLite History**: Multi-session conversations, automatic title generation, and message history in WAL mode.
- 📊 **Task Status Area**: Real-time worker state ("Ready", "Thinking...", "Completed"), model telemetry, and Windows system specs.
- 📜 **Enterprise Logging**: Rotating file logging (`logs/bolt.log`) and console output.

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
    ├── ui/               # PySide6 desktop interface
    │   ├── main_window.py
    │   ├── styles/
    │   │   └── theme.py
    │   └── components/
    │       ├── header.py
    │       ├── sidebar.py
    │       ├── chat_view.py
    │       ├── input_bar.py
    │       ├── task_status.py
    │       └── settings_dialog.py
    └── tasks/            # Task engine scaffolding for Phase 2 & 5
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
