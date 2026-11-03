"""
Internet Connectivity & Network Status Manager for BOLT (Part 3).
Reliably distinguishes:
1. Internet available
2. Internet unavailable
3. Browser unavailable
4. Website unavailable
5. Website authentication/login required
Never assumes the internet works just because a browser process opens.
"""

from enum import Enum
import socket
from typing import Any, Dict, Optional, Tuple
import urllib.parse
import urllib.request
import requests

from bolt.core.logger import get_logger

logger = get_logger("NetworkManager")

OFFLINE_SEARCH_ERROR_MESSAGE = (
    "No internet connection detected. Online search is unavailable. Local BOLT functionality is still available."
)


class NetworkStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BROWSER_UNAVAILABLE = "browser_unavailable"
    WEBSITE_UNAVAILABLE = "website_unavailable"
    AUTH_REQUIRED = "auth_required"


class NetworkManager:
    """Monitors real-time internet connectivity and classifies browser/network failures."""

    def __init__(self):
        # Override flag for testing/simulating offline state without unplugging Wi-Fi
        self._offline_simulation: Optional[bool] = None

    def set_offline_simulation(self, is_offline: Optional[bool]) -> None:
        """Enable or disable offline mode simulation (useful for testing)."""
        self._offline_simulation = is_offline
        logger.info(f"Offline simulation set to: {is_offline}")

    def simulate_offline(self, is_offline: Optional[bool] = True) -> None:
        """Alias for set_offline_simulation."""
        self.set_offline_simulation(is_offline)

    @property
    def is_online(self) -> bool:
        """Convenience property for checking internet connectivity."""
        return self.is_internet_available()

    def is_internet_available(self, timeout: float = 1.5) -> bool:
        """
        Check if laptop has a working internet connection.
        Performs fast, lightweight socket connections to reliable DNS servers.
        Never relies on browser opening.
        """
        if self._offline_simulation is True:
            return False
        if self._offline_simulation is False:
            return True

        # Primary test targets: Cloudflare DNS (1.1.1.1) and Google DNS (8.8.8.8) on port 53
        test_hosts = [
            ("1.1.1.1", 53),
            ("8.8.8.8", 53),
            ("208.67.222.222", 53),  # OpenDNS
        ]

        for host, port in test_hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((host, port))
                sock.close()
                return True
            except (socket.timeout, OSError):
                continue

        # Secondary HTTP ping fallback
        try:
            req = urllib.request.Request(
                "http://www.msftconnecttest.com/connecttest.txt",
                headers={"User-Agent": "BOLT-Network-Check/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        return False

    def classify_browser_error(self, error: Any) -> NetworkStatus:
        """
        Analyze browser navigation error or exception to distinguish exact failure cause.
        """
        err_str = str(error).lower()

        # 1. No Internet
        offline_indicators = [
            "net::err_internet_disconnected",
            "net::err_network_changed",
            "err_internet_disconnected",
            "wsaeconnrefused",
            "wsaehostunreach",
            "no internet connection",
            "connection refused",
            "offline",
        ]
        if any(ind in err_str for ind in offline_indicators):
            return NetworkStatus.OFFLINE

        # 2. DNS / Domain Unreachable
        dns_indicators = [
            "net::err_name_not_resolved",
            "err_name_not_resolved",
            "net::err_connection_timed_out",
            "err_connection_timed_out",
            "getaddrinfo failed",
            "name or service not known",
        ]
        if any(ind in err_str for ind in dns_indicators):
            if not self.is_internet_available(timeout=1.0):
                return NetworkStatus.OFFLINE
            return NetworkStatus.WEBSITE_UNAVAILABLE

        # 3. Browser unavailable
        browser_indicators = [
            "executable doesn't exist",
            "browser closed",
            "target closed",
            "could not launch browser",
            "playwright",
        ]
        if any(ind in err_str for ind in browser_indicators) and "disconnect" not in err_str:
            return NetworkStatus.BROWSER_UNAVAILABLE

        # 4. Authentication / Login Wall
        auth_indicators = [
            "login",
            "sign in",
            "authenticate",
            "401 unauthorized",
            "403 forbidden",
            "captive portal",
        ]
        if any(ind in err_str for ind in auth_indicators):
            return NetworkStatus.AUTH_REQUIRED

        # Default: if internet socket check fails, it's offline
        if not self.is_internet_available(timeout=1.0):
            return NetworkStatus.OFFLINE

        return NetworkStatus.WEBSITE_UNAVAILABLE

    def check_website(self, url: str, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Verify reachability of a specific website and detect login walls.
        """
        if not self.is_internet_available():
            return {
                "success": False,
                "status": NetworkStatus.OFFLINE.value,
                "error": OFFLINE_SEARCH_ERROR_MESSAGE,
            }

        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BOLT/1.0"},
                allow_redirects=True,
            )
            requires_auth = resp.status_code in (401, 403) or any(
                p in resp.url.lower() for p in ["login", "signin", "auth", "accounts"]
            )
            return {
                "success": resp.status_code < 400,
                "status_code": resp.status_code,
                "status": NetworkStatus.AUTH_REQUIRED.value if requires_auth else NetworkStatus.ONLINE.value,
                "requires_auth": requires_auth,
                "final_url": resp.url,
            }
        except requests.RequestException as e:
            classified = self.classify_browser_error(e)
            return {
                "success": False,
                "status": classified.value,
                "error": str(e),
            }


_NETWORK_MGR_INSTANCE: Optional[NetworkManager] = None


def get_network_manager() -> NetworkManager:
    global _NETWORK_MGR_INSTANCE
    if _NETWORK_MGR_INSTANCE is None:
        _NETWORK_MGR_INSTANCE = NetworkManager()
    return _NETWORK_MGR_INSTANCE

