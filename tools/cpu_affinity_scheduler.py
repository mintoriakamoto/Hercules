#!/usr/bin/env python3
"""CPU affinity scheduler with cache-aware scheduling.

Binds tool threads to specific CPU cores, maintains cache locality,
avoids context switching between sockets. Target: 3-8x speedup
through better cache locality.

Enables: cpu_affinity (bool), cache_aware_scheduling (bool)
"""

import logging
import os
import subprocess
import threading
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# CPU topology cache
_CPU_TOPOLOGY = None
_CPU_TOPOLOGY_LOCK = threading.Lock()


class CPUTopology:
    """Detects and caches CPU/cache topology."""

    def __init__(self):
        self.num_cpus = os.cpu_count() or 1
        self.l3_cache_groups: Dict[int, List[int]] = {}  # cache_id -> [cpus]
        self.socket_groups: Dict[int, List[int]] = {}  # socket_id -> [cpus]
        self.cpu_to_l3: Dict[int, int] = {}  # cpu -> l3_cache_id
        self.cpu_to_socket: Dict[int, int] = {}  # cpu -> socket_id
        self._detect()

    def _detect(self) -> None:
        """Detect CPU topology from /sys/devices/system/cpu."""
        base = "/sys/devices/system/cpu"

        for cpu_id in range(self.num_cpus):
            cpu_dir = os.path.join(base, f"cpu{cpu_id}")
            if not os.path.exists(cpu_dir):
                continue

            # L3 cache affinity
            l3_index_file = os.path.join(
                cpu_dir,
                "cache/index3/shared_cpu_list",
            )
            if os.path.exists(l3_index_file):
                try:
                    with open(l3_index_file, encoding="utf-8") as f:
                        cpus = self._parse_cpulist(f.read().strip())
                        # All CPUs in this list share the same L3
                        l3_id = min(cpus)  # Use min CPU as cache ID
                        self.cpu_to_l3[cpu_id] = l3_id
                        if l3_id not in self.l3_cache_groups:
                            self.l3_cache_groups[l3_id] = cpus
                except Exception as e:
                    logger.debug("Failed to read L3 cache info for cpu%d: %s", cpu_id, e)

            # Socket affinity (via topology directory)
            topology_file = os.path.join(cpu_dir, "topology/physical_package_id")
            if os.path.exists(topology_file):
                try:
                    with open(topology_file, encoding="utf-8") as f:
                        socket_id = int(f.read().strip())
                        self.cpu_to_socket[cpu_id] = socket_id
                        if socket_id not in self.socket_groups:
                            self.socket_groups[socket_id] = []
                        self.socket_groups[socket_id].append(cpu_id)
                except Exception as e:
                    logger.debug("Failed to read socket info for cpu%d: %s", cpu_id, e)

        # Fallback: if no socket info, assume single socket
        if not self.socket_groups:
            self.socket_groups[0] = list(range(self.num_cpus))
            for cpu_id in range(self.num_cpus):
                self.cpu_to_socket[cpu_id] = 0

    def _parse_cpulist(self, cpulist: str) -> List[int]:
        """Parse CPU list format: '0-3,8-11' -> [0,1,2,3,8,9,10,11]."""
        cpus = []
        for part in cpulist.split(","):
            if "-" in part:
                start, end = part.split("-")
                cpus.extend(range(int(start), int(end) + 1))
            else:
                cpus.append(int(part))
        return cpus

    def cpus_in_l3_cache(self, l3_id: int) -> List[int]:
        """Get CPUs sharing an L3 cache."""
        return self.l3_cache_groups.get(l3_id, [])

    def cpus_in_socket(self, socket_id: int) -> List[int]:
        """Get CPUs in a socket."""
        return self.socket_groups.get(socket_id, [])

    def cache_affinity_distance(self, cpu_a: int, cpu_b: int) -> int:
        """Distance between CPUs (lower = closer in cache hierarchy)."""
        if cpu_a == cpu_b:
            return 0

        # Same L3 cache = close
        if (self.cpu_to_l3.get(cpu_a) == self.cpu_to_l3.get(cpu_b)):
            return 1

        # Same socket = medium
        if (self.cpu_to_socket.get(cpu_a) == self.cpu_to_socket.get(cpu_b)):
            return 10

        # Different socket = far
        return 100


def get_cpu_topology() -> CPUTopology:
    """Get cached CPU topology."""
    global _CPU_TOPOLOGY
    if _CPU_TOPOLOGY is None:
        with _CPU_TOPOLOGY_LOCK:
            if _CPU_TOPOLOGY is None:
                _CPU_TOPOLOGY = CPUTopology()
    return _CPU_TOPOLOGY


class CPUAffinityScheduler:
    """Manages cache-aware CPU affinity for tool threads."""

    def __init__(self):
        self.topology = get_cpu_topology()
        self.config = {
            "enabled": os.getenv("CPU_AFFINITY_ENABLED", "false").lower() == "true",
            "cache_aware": os.getenv("CPU_AFFINITY_CACHE_AWARE", "true").lower() == "true",
            "avoid_context_switching": os.getenv("CPU_AFFINITY_AVOID_CONTEXT_SWITCH", "true").lower() == "true",
        }

        # Track allocated CPUs per priority level
        self.allocated_cpus: Dict[str, Set[int]] = {
            "high": set(),
            "medium": set(),
            "low": set(),
        }
        self._alloc_lock = threading.Lock()

    def select_cpus_for_tool(
        self,
        tool_name: str,
        num_cores: int = 1,
        priority: str = "medium",
    ) -> List[int]:
        """Select CPUs for tool execution with cache awareness.

        High-priority tools get dedicated CPUs in fast L3 groups.
        Medium/low tools fill remaining capacity.
        """
        if not self.config["enabled"]:
            return []

        with self._alloc_lock:
            # Strategy: prefer CPUs in the same L3 cache
            available = set(range(self.topology.num_cpus))
            available -= self.allocated_cpus.get("high", set())

            if self.config["cache_aware"]:
                # Try to keep threads in the same L3 cache group
                for l3_id, l3_cpus in self.topology.l3_cache_groups.items():
                    free_in_cache = [c for c in l3_cpus if c in available]
                    if len(free_in_cache) >= num_cores:
                        selected = free_in_cache[:num_cores]
                        self.allocated_cpus[priority] = selected
                        return selected

            # Fallback: select from available CPUs
            selected = list(available)[: num_cores]
            self.allocated_cpus[priority] = selected
            return selected

    def bind_thread_to_cpus(self, cpus: List[int]) -> None:
        """Bind current thread to specific CPUs."""
        if not cpus or not self.config["enabled"]:
            return

        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6")

            # Build CPU affinity mask
            cpu_set = (ctypes.c_ulong * ((max(cpus) + 63) // 64))()
            for cpu in cpus:
                cpu_set[cpu // 64] |= 1 << (cpu % 64)

            tid = threading.get_ident()
            libc.sched_setaffinity(tid, ctypes.sizeof(cpu_set), ctypes.byref(cpu_set))
            logger.debug("Bound thread %d to CPUs: %s", tid, cpus)
        except Exception as e:
            logger.debug("Failed to set CPU affinity: %s", e)

    def bind_thread_to_l3_cache(self, l3_id: int) -> None:
        """Bind thread to a specific L3 cache domain."""
        cpus = self.topology.cpus_in_l3_cache(l3_id)
        if cpus:
            self.bind_thread_to_cpus(cpus)

    def bind_thread_to_socket(self, socket_id: int) -> None:
        """Bind thread to a specific CPU socket."""
        cpus = self.topology.cpus_in_socket(socket_id)
        if cpus:
            self.bind_thread_to_cpus(cpus)

    def release_cpus(self, priority: str) -> None:
        """Release allocated CPUs for a priority level."""
        with self._alloc_lock:
            self.allocated_cpus[priority] = set()

    def get_preferred_socket(self) -> int:
        """Get socket with most available CPUs."""
        available = set(range(self.topology.num_cpus))
        for allocated in self.allocated_cpus.values():
            available -= allocated

        # Count available CPUs per socket
        socket_load = {}
        for socket_id, cpus in self.topology.socket_groups.items():
            socket_load[socket_id] = sum(1 for c in cpus if c in available)

        return max(socket_load, key=socket_load.get) if socket_load else 0


# Global scheduler instance
_scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> CPUAffinityScheduler:
    """Get global CPU affinity scheduler."""
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = CPUAffinityScheduler()
    return _scheduler


def schedule_tool_affinity(
    tool_name: str,
    priority: str = "medium",
) -> Optional[List[int]]:
    """Schedule CPU affinity for a tool.

    Returns list of CPUs to bind to, or None if no affinity.
    """
    scheduler = get_scheduler()

    if not scheduler.config["enabled"]:
        return None

    # High-priority tools (network, I/O) get more cores
    num_cores = {"high": 4, "medium": 2, "low": 1}.get(priority, 1)
    cpus = scheduler.select_cpus_for_tool(tool_name, num_cores, priority)

    if cpus:
        scheduler.bind_thread_to_cpus(cpus)

    return cpus or None


def set_cpu_affinity_config(config: Dict[str, any]) -> None:
    """Update CPU affinity scheduler configuration."""
    scheduler = get_scheduler()
    scheduler.config.update(config)
    logger.info("CPU affinity config updated: %s", scheduler.config)
