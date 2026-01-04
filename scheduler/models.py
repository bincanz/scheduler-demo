"""
Data models for the scheduler.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CustomerRequest:
    """Represents a single customer's call requirements."""
    
    name: str
    avg_call_duration_seconds: int
    start_hour: int  # 0-23, inclusive
    end_hour: int    # 0-23, exclusive (e.g., 7PM = 19, means active until 18:59)
    number_of_calls: int
    priority: int    # 1-5, 1 is highest
    
    @property
    def active_hours(self) -> int:
        """Number of hours this customer is active."""
        return self.end_hour - self.start_hour
    
    @property
    def calls_per_hour(self) -> float:
        """Calls uniformly distributed across active hours."""
        if self.active_hours <= 0:
            return 0.0
        return self.number_of_calls / self.active_hours
    
    def agents_needed_per_hour(self, utilization: float = 1.0) -> int:
        """
        Calculate agents needed per hour.
        
        Formula: ceil(calls_per_hour * avg_duration_seconds / 3600 / utilization)
        
        Lower utilization means more agents (conservative sizing).
        """
        import math
        if utilization <= 0:
            utilization = 1.0
        
        raw_agents = self.calls_per_hour * self.avg_call_duration_seconds / 3600
        return math.ceil(raw_agents / utilization)
    
    def is_active_at_hour(self, hour: int) -> bool:
        """Check if this customer is active during the given hour."""
        return self.start_hour <= hour < self.end_hour


@dataclass
class HourlySchedule:
    """Schedule for a single hour."""
    
    hour: int
    customer_agents: Dict[str, int] = field(default_factory=dict)
    
    @property
    def total_agents(self) -> int:
        return sum(self.customer_agents.values())
    
    def to_text(self) -> str:
        """Format as text line."""
        hour_str = f"{self.hour:02d}:00"
        if not self.customer_agents:
            return f"{hour_str} : total=0 ; none"
        
        customer_parts = ", ".join(
            f"{name}={agents}" 
            for name, agents in self.customer_agents.items()
        )
        return f"{hour_str} : total={self.total_agents} ; {customer_parts}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "hour": f"{self.hour:02d}:00",
            "total_agents": self.total_agents,
            "customers": self.customer_agents.copy()
        }


@dataclass
class CapacityAllocation:
    """Result of capacity-constrained allocation."""
    
    schedules: List[HourlySchedule]
    peak_demand: int
    capacity: int
    unmet_demand: Dict[str, dict] = field(default_factory=dict)  # customer -> {calls_unmet, hours_affected}
    utilization_by_hour: Dict[int, float] = field(default_factory=dict)
    
    def has_unmet_demand(self) -> bool:
        return bool(self.unmet_demand)

