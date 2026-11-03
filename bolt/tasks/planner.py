"""Intelligent Task Planning Engine for BOLT (Phase 5)."""

import re
import uuid
from typing import Any, Dict, List, Optional
from bolt.core.logger import get_logger
from bolt.tasks.models import ExecutionPlan, RiskLevel, TaskStatus, TaskStep
from bolt.tasks.workflow_memory import get_workflow_memory

logger = get_logger("TaskPlanner")


class TaskPlanner:
    """Translates complex natural-language multi-action instructions into structured DAG ExecutionPlans."""

    def __init__(self):
        self.workflow_memory = get_workflow_memory()

    def plan_instruction(self, user_text: str) -> ExecutionPlan:
        """Create an executable DAG plan for a complex user instruction."""
        clean = user_text.strip()
        lower = clean.lower()

        # 0. Check Workflow Memory for previous workflow recall
        if any(k in lower for k in ["same process", "last time", "repeat workflow"]):
            remembered = self.workflow_memory.recall_workflow_by_query(lower)
            if remembered:
                plan = self.workflow_memory.instantiate_plan_from_workflow(remembered, clean)
                if plan:
                    logger.info(f"Instantiated plan from remembered workflow '{remembered.get('name')}'")
                    return plan

        # 1. Specialized Workflow A: AI Research & Summarization / Reporting
        if (
            ("research" in lower or "find information" in lower or "investigate" in lower or "search for" in lower)
            and ("summarize" in lower or "findings" in lower or "developments" in lower or "analyze" in lower or "report" in lower)
        ):
            return self._build_workflow_a_research(clean)

        # 2. Specialized Workflow B: Email Preparation with Approval Gate
        if "email" in lower and any(v in lower for v in ["write", "draft", "prepare", "compose", "ask gemini", "ask chatgpt"]):
            return self._build_workflow_b_email(clean)

        # 3. Specialized Workflow C: Programming Assistance (Run, Diagnose, Fix)
        if any(term in lower for term in ["python project", "python file", "run the python", "run it", "identify the error", "identify errors", "fix errors", "fix it", "help me fix", "debug", "diagnose"]) and any(p in lower for p in ["python", "script", "code", "project"]):
            return self._build_workflow_c_programming(clean)

        # 4. Specialized Workflow D: Document Processing (Search, Read, Summarize, Save)
        if any(term in lower for term in ["assignment", "pdf", "document"]) and ("summarize" in lower or "extract" in lower):
            return self._build_workflow_d_document(clean)

        # 5. Compound Multi-Action Decomposition Engine
        return self._build_compound_plan(clean)

    # ---------------- Specialized Workflow Builders ----------------

    def _build_workflow_a_research(self, instruction: str) -> ExecutionPlan:
        """Workflow A: AI Research & Summarization."""
        plan_id = str(uuid.uuid4())
        # Extract topic
        topic = "the latest developments in artificial intelligence"
        topic_match = re.search(r"research\s+(?:the\s+)?([^\n,]+?)(?:\s+and\s+summarize|\.|$)", instruction, re.IGNORECASE)
        if topic_match:
            topic = topic_match.group(1).strip()

        steps = [
            TaskStep(
                step_id="step_1",
                description="Open browser and initialize research session",
                tool_name="open_website",
                input_params={"website_name_or_url": "https://www.google.com/"},
                expected_output="Browser open with search session ready",
                active_application="Microsoft Edge",
            ),
            TaskStep(
                step_id="step_2",
                description=f"Search the web for {topic}",
                tool_name="search_web",
                input_params={"query": topic, "provider": "google"},
                expected_output="Structured search results with titles and source URLs",
                dependencies=["step_1"],
                active_application="Search Engine",
            ),
            TaskStep(
                step_id="step_3",
                description="Collect and read accessible web source content",
                tool_name="read_webpage",
                input_params={"url": ""},
                expected_output="Extracted text and outlines from web results",
                dependencies=["step_2"],
                active_application="Content Reader",
            ),
            TaskStep(
                step_id="step_4",
                description="Synthesize key findings and prepare structured summary with source links",
                tool_name="generate_ai_response",
                input_params={
                    "prompt": f"Synthesize and summarize the 5 most important findings regarding {topic} using these search findings: ${{step_2.result}}",
                    "system_prompt": "You are BOLT Research Intelligence. Provide clear, objective summaries with numbered key findings and citations.",
                },
                expected_output="Comprehensive research summary with citations",
                dependencies=["step_2", "step_3"],
                active_application="BOLT AI Engine",
            ),
        ]

        return ExecutionPlan(
            plan_id=plan_id,
            title="AI Research & Summarization",
            user_instruction=instruction,
            steps=steps,
        )

    def _build_workflow_b_email(self, instruction: str) -> ExecutionPlan:
        """Workflow B: Professional Email Preparation with Human-in-the-Loop Approval."""
        plan_id = str(uuid.uuid4())

        steps = [
            TaskStep(
                step_id="step_1",
                description="Generate professional email draft",
                tool_name="generate_ai_response",
                input_params={
                    "prompt": f"Write a professional, compelling email draft based on this request: {instruction}",
                    "provider": "gemini" if "gemini" in instruction.lower() else "",
                    "system_prompt": "You are a professional communication assistant. Produce a complete email with Subject line and body.",
                },
                expected_output="Polished email draft with Subject and Body",
                active_application="Google Gemini",
            ),
            TaskStep(
                step_id="step_2",
                description="Wait for user review and approval of the generated email draft",
                tool_name="request_user_approval",
                input_params={
                    "action_name": "Review Email Draft",
                    "details": "${step_1.content}",
                },
                expected_output="User confirmation or revised guidance",
                dependencies=["step_1"],
                risk_level=RiskLevel.APPROVAL_REQUIRED,
                requires_approval=True,
                approval_prompt="Please review the generated email draft. Do you approve proceeding with this draft?",
            ),
            TaskStep(
                step_id="step_3",
                description="Open Gmail to prepare message draft",
                tool_name="open_website",
                input_params={"website_name_or_url": "gmail"},
                expected_output="Gmail web interface opened",
                dependencies=["step_2"],
                active_application="Gmail Web",
            ),
            TaskStep(
                step_id="step_4",
                description="Require explicit user approval before sending email to recipient",
                tool_name="request_user_approval",
                input_params={
                    "action_name": "Send Email",
                    "details": "Ready to send approved email message via Gmail.",
                },
                expected_output="User final approval before sending",
                dependencies=["step_3"],
                risk_level=RiskLevel.HIGH_RISK,
                requires_approval=True,
                approval_prompt="⚠️ HIGH RISK ACTION: Do you explicitly authorize sending this email now?",
            ),
        ]

        return ExecutionPlan(
            plan_id=plan_id,
            title="Email Preparation & Approval",
            user_instruction=instruction,
            steps=steps,
        )

    def _build_workflow_c_programming(self, instruction: str) -> ExecutionPlan:
        """Workflow C: Programming Project Assistance (Locate, Run, Diagnose, Fix)."""
        plan_id = str(uuid.uuid4())

        steps = [
            TaskStep(
                step_id="step_1",
                description="Locate Python project files",
                tool_name="search_files",
                input_params={"query": "main.py"},
                expected_output="Path to project entry script",
            ),
            TaskStep(
                step_id="step_2",
                description="Open Visual Studio Code for project inspection",
                tool_name="open_application",
                input_params={"app_name": "Visual Studio Code"},
                expected_output="Visual Studio Code launched or focused",
                active_application="Visual Studio Code",
            ),
            TaskStep(
                step_id="step_3",
                description="Safely run program in sandboxed environment to capture runtime errors",
                tool_name="run_python_script_safe",
                input_params={"script_path": "${step_1.files[0].path}", "timeout_seconds": 15},
                expected_output="Captured stdout and stderr",
                dependencies=["step_1"],
                active_application="Python Runtime",
            ),
            TaskStep(
                step_id="step_4",
                description="Analyze captured error and prepare solution explanation",
                tool_name="generate_ai_response",
                input_params={
                    "prompt": "Analyze this program execution output and explain how to fix any errors:\nStdout: ${step_3.stdout}\nStderr: ${step_3.stderr}",
                    "system_prompt": "You are a senior software debugging engineer. Explain the root cause and provide exact code fixes.",
                },
                expected_output="Error analysis and step-by-step resolution",
                dependencies=["step_3"],
                active_application="AI Debugger",
            ),
            TaskStep(
                step_id="step_5",
                description="Ask user approval before applying changes to important files",
                tool_name="request_user_approval",
                input_params={
                    "action_name": "Modify Project Code",
                    "details": "Proposed fix:\n${step_4.content}",
                },
                expected_output="User authorization to apply code changes",
                dependencies=["step_4"],
                risk_level=RiskLevel.APPROVAL_REQUIRED,
                requires_approval=True,
                approval_prompt="Would you like BOLT to apply the proposed code fixes to your project files?",
            ),
        ]

        return ExecutionPlan(
            plan_id=plan_id,
            title="Programming Project Diagnosis",
            user_instruction=instruction,
            steps=steps,
        )

    def _build_workflow_d_document(self, instruction: str) -> ExecutionPlan:
        """Workflow D: Document Processing (Search, Read, Summarize, Save)."""
        plan_id = str(uuid.uuid4())

        steps = [
            TaskStep(
                step_id="step_1",
                description="Search user directories for assignment PDF",
                tool_name="search_files",
                input_params={"query": "assignment.pdf"},
                expected_output="Located PDF file candidate",
                active_application="File Search",
            ),
            TaskStep(
                step_id="step_2",
                description="Read and extract document text content",
                tool_name="read_text_file",
                input_params={"file_path": "${step_1.files[0].path}"},
                expected_output="Extracted document text",
                dependencies=["step_1"],
                active_application="Document Reader",
            ),
            TaskStep(
                step_id="step_3",
                description="Summarize document requirements and key deliverables",
                tool_name="generate_ai_response",
                input_params={
                    "prompt": "Summarize the key requirements, deliverables, and instructions in this document:\n\n${step_2.content}",
                    "system_prompt": "You are BOLT Document Intelligence. Produce an accurate, structured summary.",
                },
                expected_output="Structured summary of requirements",
                dependencies=["step_2"],
                active_application="AI Summarizer",
            ),
            TaskStep(
                step_id="step_4",
                description="Save summary in a separate text file without overwriting original",
                tool_name="write_text_file",
                input_params={
                    "file_path": "assignment_summary.txt",
                    "content": "${step_3.content}",
                    "allow_overwrite": False,
                },
                expected_output="New summary text file created",
                dependencies=["step_3"],
                active_application="File Manager",
            ),
            TaskStep(
                step_id="step_5",
                description="Verify that the summary file was created and is readable",
                tool_name="verify_file_exists",
                input_params={"file_path": "${step_4.file_path}"},
                expected_output="File creation verified",
                dependencies=["step_4"],
                active_application="Verification Engine",
            ),
        ]

        return ExecutionPlan(
            plan_id=plan_id,
            title="Document Processing & Summary",
            user_instruction=instruction,
            steps=steps,
        )

    def _build_compound_plan(self, instruction: str) -> ExecutionPlan:
        """General multi-action decomposition for compound instructions."""
        plan_id = str(uuid.uuid4())
        lower = instruction.lower()
        steps: List[TaskStep] = []

        # Split clauses by common conjunctions
        clauses = [c.strip() for c in re.split(r",\s*(?:and\s+)?|\s+and\s+|\s+then\s+", lower) if c.strip()]
        if not clauses:
            clauses = [lower]

        step_counter = 1
        prev_step_id: Optional[str] = None

        for clause in clauses:
            step_id = f"step_{step_counter}"
            deps: List[str] = []

            # 1. Search action
            if "search" in clause or "find" in clause:
                query_text = re.sub(r"^(?:search\s+(?:for|the\s+web\s+for|online\s+for)?|find)\s+", "", clause).strip()
                if any(ext in query_text for ext in [".pdf", ".txt", ".py", "file", "folder", "document"]):
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Search for file matching: {query_text}",
                        tool_name="search_files",
                        input_params={"query": query_text},
                        expected_output="File search candidates",
                        dependencies=deps,
                        active_application="File Search",
                    ))
                else:
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Search web for: {query_text}",
                        tool_name="search_web",
                        input_params={"query": query_text, "provider": "google"},
                        expected_output="Web search results",
                        dependencies=deps,
                        active_application="Browser Search",
                    ))

            # 2. Summarize / Explain / Compare / Analyze action
            elif any(w in clause for w in ["summarize", "explain", "compare", "analyze"]):
                deps = [prev_step_id] if prev_step_id else []
                prompt = f"Please explain or summarize according to instruction: {clause}"
                if prev_step_id:
                    prompt = f"Analyze or compare the results from the previous step according to instruction '{clause}':\n\n${{{prev_step_id}.result}}"
                steps.append(TaskStep(
                    step_id=step_id,
                    description=f"AI synthesis: {clause}",
                    tool_name="generate_ai_response",
                    input_params={"prompt": prompt},
                    expected_output="AI response text",
                    dependencies=deps,
                    active_application="AI Provider",
                ))

            # 3. Create file action (e.g. "create a file called Notes.txt on my Desktop")
            elif "create" in clause and any(w in clause for w in ["file", ".txt", "notes"]):
                filename = "Notes.txt"
                file_match = re.search(r"(?:called|named)?\s*([a-zA-Z0-9_\-\.]+\.txt)", clause, re.IGNORECASE)
                if file_match:
                    filename = file_match.group(1)

                init_content = ""
                content_match = re.search(r"(?:with\s+content|saying|text)\s*[:\"']?([^\"']+)[\"']?", clause, re.IGNORECASE)
                if content_match:
                    init_content = content_match.group(1).strip()

                steps.append(TaskStep(
                    step_id=step_id,
                    description=f"Create file {filename} on Desktop",
                    tool_name="create_text_file",
                    input_params={"file_path": filename, "content": init_content},
                    expected_output=f"File {filename} created on Desktop",
                    dependencies=[],
                    active_application="File Manager",
                ))

            # 4. Write / Type action (Typing into open app vs saving to file)
            elif "write" in clause or "type" in clause or "save" in clause:
                is_file_save = any(
                    w in clause for w in [
                        ".txt", ".pdf", ".py", ".md", ".doc", "to file", "in a file",
                        "in file", "to disk", "workspace", "folder", "document",
                        "save it", "save to", "save in", "summary document",
                    ]
                )
                if is_file_save:
                    target_file = "summary_document.txt"
                    file_match = re.search(r"(?:in|to)\s+(?:a\s+)?([a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+)", clause)
                    if file_match:
                        target_file = file_match.group(1)
                    elif "workspace" in clause:
                        target_file = "summary_document.txt"

                    folder_alias = "workspace" if "workspace" in clause else ""
                    content_ref = f"${{{prev_step_id}.result}}" if prev_step_id else "BOLT Task Output"
                    deps = [prev_step_id] if prev_step_id else []
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Save result to {target_file}" + (f" in {folder_alias}" if folder_alias else ""),
                        tool_name="write_text_file",
                        input_params={
                            "file_path": target_file,
                            "content": content_ref,
                            "allow_overwrite": False,
                            "folder_alias": folder_alias,
                        },
                        expected_output=f"File saved to {target_file}",
                        dependencies=deps,
                        active_application="File Manager",
                    ))
                else:
                    # Typing text into active application (e.g. "write Hello World")
                    text_to_type = re.sub(r"^(?:write|type)\s+", "", clause, flags=re.IGNORECASE).strip().strip("'\"")
                    if not text_to_type:
                        text_to_type = "Hello World"
                    deps = [prev_step_id] if prev_step_id else []
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Type text into active application: \"{text_to_type}\"",
                        tool_name="type_text",
                        input_params={"text": f"{text_to_type}\n", "delay_ms": 15},
                        expected_output=f"Typed \"{text_to_type}\" into window",
                        dependencies=deps,
                        active_application="Active Application",
                    ))

            # 5. Open app or site action
            elif "open" in clause or "launch" in clause:
                target = re.sub(r"^(?:open|launch|start|run)\s+", "", clause).strip()
                if any(b in target for b in ["chrome", "edge", "firefox", "browser", "chatgpt", "gemini", "google", "gmail", "youtube"]) or target.startswith("http"):
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Open web target: {target}",
                        tool_name="open_website",
                        input_params={"website_name_or_url": target},
                        expected_output="Web page opened",
                        dependencies=deps,
                        active_application="Browser",
                    ))
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Open web target: {target}",
                        tool_name="open_website",
                        input_params={"website_name_or_url": target},
                        expected_output="Web page opened",
                        dependencies=deps,
                        active_application="Browser",
                    ))
                else:
                    steps.append(TaskStep(
                        step_id=step_id,
                        description=f"Open desktop application: {target}",
                        tool_name="open_application",
                        input_params={"app_name": target},
                        expected_output="Application opened",
                        dependencies=deps,
                        active_application=target.title(),
                    ))

            # 6. Fallback generic clause
            else:
                deps = [prev_step_id] if prev_step_id else []
                steps.append(TaskStep(
                    step_id=step_id,
                    description=clause.title(),
                    tool_name="generate_ai_response",
                    input_params={"prompt": clause},
                    expected_output="Action response",
                    dependencies=deps,
                    active_application="AI Engine",
                ))

            prev_step_id = step_id
            step_counter += 1

        return ExecutionPlan(
            plan_id=plan_id,
            title="Multi-Action Task Execution",
            user_instruction=instruction,
            steps=steps,
        )


_PLANNER_INSTANCE: Optional[TaskPlanner] = None


def get_task_planner() -> TaskPlanner:
    global _PLANNER_INSTANCE
    if _PLANNER_INSTANCE is None:
        _PLANNER_INSTANCE = TaskPlanner()
    return _PLANNER_INSTANCE
