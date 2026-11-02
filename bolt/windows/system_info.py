"""
Windows System Diagnostics and Hardware Telemetry subsystem for BOLT.
Retrieves CPU, RAM, Disk, Battery, and Windows 11 platform status.
"""

import os
import platform
import socket
from typing import Any, Dict
import psutil

from bolt.core.logger import get_logger

logger = get_logger("SystemInfo")


class SystemInfo:
    """Collects real-time hardware telemetry and OS specifications."""

    @staticmethod
    def get_system_summary() -> Dict[str, Any]:
        """Collect unified system hardware and environment diagnostic dictionary."""
        # 1. OS & Architecture
        os_name = f"Windows {platform.release()} ({platform.version()})"
        arch = platform.machine()
        hostname = socket.gethostname()
        username = os.environ.get("USERNAME", "User")

        # 2. CPU
        cpu_model = platform.processor() or "Intel Core i5 (7th Gen)"
        cpu_cores = psutil.cpu_count(logical=False) or 2
        cpu_threads = psutil.cpu_count(logical=True) or 4
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # 3. RAM
        ram = psutil.virtual_memory()
        total_ram_gb = round(ram.total / (1024 ** 3), 1)
        used_ram_gb = round(ram.used / (1024 ** 3), 1)
        avail_ram_gb = round(ram.available / (1024 ** 3), 1)
        ram_percent = ram.percent

        # 4. Primary Disk (C:)
        try:
            disk = psutil.disk_usage("C:\\")
            disk_total_gb = round(disk.total / (1024 ** 3), 1)
            disk_free_gb = round(disk.free / (1024 ** 3), 1)
            disk_percent = disk.percent
        except Exception:
            disk_total_gb, disk_free_gb, disk_percent = 0, 0, 0

        # 5. Battery (Laptop telemetry)
        battery = psutil.sensors_battery()
        battery_info = {}
        if battery:
            battery_info = {
                "percent": round(battery.percent, 1),
                "power_plugged": battery.power_plugged,
                "status": "Charging" if battery.power_plugged else "Discharging",
            }

        return {
            "os": os_name,
            "architecture": arch,
            "hostname": hostname,
            "username": username,
            "cpu_model": cpu_model,
            "cpu_cores": f"{cpu_cores} physical ({cpu_threads} logical)",
            "cpu_usage_pct": cpu_percent,
            "ram_total_gb": total_ram_gb,
            "ram_used_gb": used_ram_gb,
            "ram_available_gb": avail_ram_gb,
            "ram_usage_pct": ram_percent,
            "disk_total_gb": disk_total_gb,
            "disk_free_gb": disk_free_gb,
            "disk_usage_pct": disk_percent,
            "battery": battery_info,
        }

    @staticmethod
    def format_markdown_summary() -> str:
        """Format system diagnostics into a clean markdown card for user display."""
        info = SystemInfo.get_system_summary()

        battery_line = ""
        if info.get("battery"):
            b = info["battery"]
            plug_icon = "⚡ Plugged In" if b["power_plugged"] else "🔋 On Battery"
            battery_line = f"- **Battery:** {b['percent']}% ({plug_icon})\n"

        return (
            f"### 🖥️ Windows 11 System Diagnostics\n\n"
            f"- **Operating System:** {info['os']}\n"
            f"- **Computer Name:** `{info['hostname']}` | **User:** `{info['username']}`\n"
            f"- **Processor:** {info['cpu_model']} ({info['cpu_cores']}) — **{info['cpu_usage_pct']}%** load\n"
            f"- **Memory (RAM):** {info['ram_used_gb']} GB / {info['ram_total_gb']} GB ({info['ram_usage_pct']}% used, {info['ram_available_gb']} GB free)\n"
            f"- **Storage (C:):** {info['disk_free_gb']} GB free of {info['disk_total_gb']} GB ({info['disk_usage_pct']}% used)\n"
            f"{battery_line}\n"
            f"*BOLT Engine: Connected and monitoring Windows.*"
        )

