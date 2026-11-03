"""
Performance Benchmark Subsystem for BOLT (Phase 6 Event-Driven Computer Control).
Benchmarks and compares the performance and resource footprint of:
1. Open Notepad without screenshots.
2. Type text using direct automation.
3. Read text using UI Automation.
4. Click a button using UI Automation.
5. Capture and analyze a screenshot.
6. Perform OCR on a selected region.
7. Invoke local vision AI / visual diagnostics.

Records execution time (ms), RAM usage (MB delta), CPU usage (%), and success rate.
Empirically demonstrates the superior speed and efficiency of event-driven automation over screenshot-heavy approaches.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psutil

from bolt.core.logger import get_logger
from bolt.windows.app_controller import get_app_controller
from bolt.windows.hybrid_controller import get_hybrid_controller
from bolt.windows.ui_automation import get_ui_automation_manager
from bolt.windows.vision_engine import get_vision_engine

logger = get_logger("PerformanceBenchmark")


@dataclass
class BenchmarkMetric:
    operation_name: str
    method_category: str  # 'Direct API', 'UI Automation', 'Vision / OCR'
    execution_time_ms: float
    ram_delta_mb: float
    cpu_percent: float
    success: bool
    notes: str


class PerformanceBenchmark:
    """
    Executes and records performance comparisons between direct automation,
    UI Automation, and screenshot-based vision operations.
    """

    def __init__(self):
        self.hybrid = get_hybrid_controller()
        self.uia = get_ui_automation_manager()
        self.vision = get_vision_engine()
        self.app_ctrl = get_app_controller()

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all 7 benchmark operations and return comparative summary."""
        results: List[BenchmarkMetric] = []
        process = psutil.Process(os.getpid())

        logger.info("Starting BOLT Event-Driven Performance Benchmark...")

        # -------------------------------------------------------------
        # Benchmark 1: Open Notepad without screenshots
        # -------------------------------------------------------------
        m1 = self._benchmark_op(
            name="1. Open Notepad",
            category="Direct API",
            func=lambda: self.hybrid.open_application_direct("notepad"),
            notes="Direct ShellExecute / Window verification; 0 screenshots.",
        )
        results.append(m1)

        time.sleep(0.5)

        # -------------------------------------------------------------
        # Benchmark 2: Type text using direct automation
        # -------------------------------------------------------------
        m2 = self._benchmark_op(
            name="2. Type text (Direct)",
            category="Direct API (SendInput)",
            func=lambda: self.hybrid.type_text_into_active("BOLT Event-Driven Benchmark Text"),
            notes="Win32 SendInput Unicode stream; 0 screenshots.",
        )
        results.append(m2)

        time.sleep(0.3)

        # -------------------------------------------------------------
        # Benchmark 3: Read text using UI Automation
        # -------------------------------------------------------------
        m3 = self._benchmark_op(
            name="3. Read text (UI Automation)",
            category="UI Automation",
            func=lambda: self.hybrid.read_accessible_text("notepad"),
            notes="ValuePattern / TextPattern extraction; 0 screenshots.",
        )
        results.append(m3)

        time.sleep(0.3)

        # -------------------------------------------------------------
        # Benchmark 4: Click a button using UI Automation
        # -------------------------------------------------------------
        # Click Minimise or Settings or a known button in Notepad
        m4 = self._benchmark_op(
            name="4. Click button (UI Automation)",
            category="UI Automation",
            func=lambda: self.hybrid.click_button_by_name("notepad", "Minimise"),
            notes="InvokePattern semantic click; 0 screenshots.",
        )
        results.append(m4)

        # -------------------------------------------------------------
        # Benchmark 5: Capture and analyze a screenshot
        # -------------------------------------------------------------
        m5 = self._benchmark_op(
            name="5. Capture screenshot",
            category="Screenshot / Vision",
            func=lambda: self.vision.capture_region(window_title="notepad"),
            notes="Full window GDI grab + PIL buffer allocation.",
        )
        results.append(m5)

        # -------------------------------------------------------------
        # Benchmark 6: Perform OCR on a selected region
        # -------------------------------------------------------------
        m6 = self._benchmark_op(
            name="6. Perform local OCR",
            category="Screenshot / Vision",
            func=lambda: self.vision.run_ocr(window_title="notepad"),
            notes="Windows Media OCR on image; CPU based.",
        )
        results.append(m6)

        # -------------------------------------------------------------
        # Benchmark 7: Invoke local vision AI / visual error diagnosis
        # -------------------------------------------------------------
        m7 = self._benchmark_op(
            name="7. Visual error diagnosis",
            category="Screenshot / Vision",
            func=lambda: self.vision.diagnose_visual_error(window_title="notepad"),
            notes="On-demand OCR + error token classifier.",
        )
        results.append(m7)

        # Clean up Notepad
        try:
            self.app_ctrl.close_application("notepad")
        except Exception:
            pass

        # Calculate comparative metrics
        direct_avg_ms = sum(r.execution_time_ms for r in results[:2]) / 2.0
        uia_avg_ms = sum(r.execution_time_ms for r in results[2:4]) / 2.0
        vision_avg_ms = sum(r.execution_time_ms for r in results[4:7]) / 3.0

        speedup_factor = vision_avg_ms / max(uia_avg_ms, 1.0)

        report = {
            "success": True,
            "metrics": [r.__dict__ for r in results],
            "direct_api_avg_ms": round(direct_avg_ms, 2),
            "ui_automation_avg_ms": round(uia_avg_ms, 2),
            "vision_screenshot_avg_ms": round(vision_avg_ms, 2),
            "speedup_vs_screenshots": f"{speedup_factor:.1f}x faster",
            "recommendation": (
                "Direct APIs and UI Automation should be used for 100% of routine operations. "
                "Screenshots should strictly be reserved for on-demand inspection or inaccessible UIs."
            ),
        }

        logger.info(f"Benchmark finished. UIA Avg: {uia_avg_ms:.1f}ms, Vision Avg: {vision_avg_ms:.1f}ms (Speedup: {speedup_factor:.1f}x)")
        return report

    def _benchmark_op(self, name: str, category: str, func, notes: str) -> BenchmarkMetric:
        """Measure execution time, RAM delta, and CPU percent for an action."""
        process = psutil.Process(os.getpid())
        ram_before = process.memory_info().rss / (1024 * 1024)
        cpu_before = psutil.cpu_percent(interval=None)

        start = time.perf_counter()
        success = True
        try:
            func()
        except Exception as e:
            logger.warning(f"Benchmark '{name}' error: {e}")
            success = False
        elapsed_ms = (time.perf_counter() - start) * 1000

        ram_after = process.memory_info().rss / (1024 * 1024)
        ram_delta = max(0.0, ram_after - ram_before)
        cpu_after = psutil.cpu_percent(interval=None)

        return BenchmarkMetric(
            operation_name=name,
            method_category=category,
            execution_time_ms=round(elapsed_ms, 2),
            ram_delta_mb=round(ram_delta, 2),
            cpu_percent=cpu_after,
            success=success,
            notes=notes,
        )


_performance_benchmark: Optional[PerformanceBenchmark] = None


def get_performance_benchmark() -> PerformanceBenchmark:
    global _performance_benchmark
    if _performance_benchmark is None:
        _performance_benchmark = PerformanceBenchmark()
    return _performance_benchmark
