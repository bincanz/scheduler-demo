"""
Data models for the scheduler.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo


# Default timezone
DEFAULT_TIMEZONE = "America/Los_Angeles"


@dataclass
class CustomerRequest:
    """Represents a single customer's call requirements."""
    
    name: str
    avg_call_duration_seconds: int
    start_hour: int  # 0-23, inclusive (local time hour)
    end_hour: int    # 0-23, exclusive (local time hour)
    number_of_calls: int
    priority: int    # 1-5, 1 is highest
    
    def active_hours_for_date(self, date: datetime, tz: ZoneInfo) -> int:
        """
        Calculate number of active hours for a specific date, accounting for DST.
        
        Args:
            date: The date to calculate for
            tz: Timezone for the calculation
            
        Returns:
            Number of hours this customer is active on that date
        """
        active_count = 0
        for hour_dt in enumerate_hours_for_date(date, tz):
            local_hour = hour_dt.hour
            if self.start_hour <= local_hour < self.end_hour:
                active_count += 1
        return active_count
    
    @property
    def active_hours(self) -> int:
        """
        Number of hours this customer is active (simple calculation, no DST).
        For DST-aware calculation, use active_hours_for_date().
        """
        return self.end_hour - self.start_hour
    
    @property
    def calls_per_hour(self) -> float:
        """Calls uniformly distributed across active hours (simple, no DST)."""
        if self.active_hours <= 0:
            return 0.0
        return self.number_of_calls / self.active_hours
    
    def calls_per_hour_for_date(self, date: datetime, tz: ZoneInfo) -> float:
        """Calls per hour accounting for DST on a specific date."""
        active = self.active_hours_for_date(date, tz)
        if active <= 0:
            return 0.0
        return self.number_of_calls / active
    
    def agents_needed_per_hour(self, utilization: float = 1.0) -> int:
        """
        Calculate agents needed per hour (simple, no DST).
        
        Formula: ceil(calls_per_hour * avg_duration_seconds / 3600 / utilization)
        """
        import math
        if utilization <= 0:
            utilization = 1.0
        
        raw_agents = self.calls_per_hour * self.avg_call_duration_seconds / 3600
        return math.ceil(raw_agents / utilization)
    
    def agents_needed_for_date(self, date: datetime, tz: ZoneInfo, utilization: float = 1.0) -> int:
        """
        Calculate agents needed per hour for a specific date, accounting for DST.
        """
        import math
        if utilization <= 0:
            utilization = 1.0
        
        calls_per_hour = self.calls_per_hour_for_date(date, tz)
        raw_agents = calls_per_hour * self.avg_call_duration_seconds / 3600
        return math.ceil(raw_agents / utilization)
    
    def is_active_at_hour(self, hour: int) -> bool:
        """Check if this customer is active during the given local hour."""
        return self.start_hour <= hour < self.end_hour
    
    def is_active_at_datetime(self, dt: datetime, tz: ZoneInfo) -> bool:
        """Check if this customer is active at a specific datetime."""
        local_dt = dt.astimezone(tz)
        return self.start_hour <= local_dt.hour < self.end_hour


@dataclass
class HourlySchedule:
    """Schedule for a single hour."""
    
    hour: int  # Local hour (0-23)
    customer_agents: Dict[str, int] = field(default_factory=dict)
    datetime_utc: Optional[datetime] = None  # UTC datetime for this hour
    datetime_local: Optional[datetime] = None  # Local datetime for this hour
    
    @property
    def total_agents(self) -> int:
        return sum(self.customer_agents.values())
    
    def to_text(self, show_date: bool = False) -> str:
        """Format as text line."""
        if self.datetime_local and show_date:
            hour_str = self.datetime_local.strftime("%Y-%m-%d %H:%M %Z")
        else:
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
        result = {
            "hour": f"{self.hour:02d}:00",
            "total_agents": self.total_agents,
            "customers": self.customer_agents.copy()
        }
        
        if self.datetime_utc:
            result["datetime_utc"] = self.datetime_utc.isoformat()
        if self.datetime_local:
            result["datetime_local"] = self.datetime_local.isoformat()
            result["timezone"] = str(self.datetime_local.tzinfo)
        
        return result


@dataclass
class CapacityAllocation:
    """Result of capacity-constrained allocation."""
    
    schedules: List[HourlySchedule]
    peak_demand: int
    capacity: int
    unmet_demand: Dict[str, dict] = field(default_factory=dict)
    utilization_by_hour: Dict[int, float] = field(default_factory=dict)
    
    def has_unmet_demand(self) -> bool:
        return bool(self.unmet_demand)


@dataclass
class ScheduleContext:
    """Context for schedule computation including timezone info."""
    
    date: datetime  # The date being scheduled
    timezone: ZoneInfo  # Timezone for display
    hours: List[datetime]  # All hours for this day (in local time, may be 23, 24, or 25)
    is_dst_transition: bool = False
    dst_info: str = ""  # Description of DST transition if any
    
    @property
    def num_hours(self) -> int:
        return len(self.hours)


def enumerate_hours_for_date(date: datetime, tz: ZoneInfo) -> List[datetime]:
    """
    Enumerate all hours for a specific date in a timezone, handling DST.
    
    This properly handles:
    - Normal days: 24 hours
    - Spring forward (DST start): 23 hours (2AM-3AM skipped)
    - Fall back (DST end): 25 hours (1AM-2AM repeated)
    
    Args:
        date: The date to enumerate hours for
        tz: Timezone to use
        
    Returns:
        List of datetime objects for each hour of the day in local time
    """
    # Start at midnight local time
    start_of_day = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=tz)
    
    # Get start of next day
    next_day = date + timedelta(days=1)
    end_of_day = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0, tzinfo=tz)
    
    # Convert to UTC to properly enumerate hours
    start_utc = start_of_day.astimezone(ZoneInfo("UTC"))
    end_utc = end_of_day.astimezone(ZoneInfo("UTC"))
    
    hours = []
    current_utc = start_utc
    
    while current_utc < end_utc:
        local_dt = current_utc.astimezone(tz)
        hours.append(local_dt)
        current_utc += timedelta(hours=1)
    
    return hours


def create_schedule_context(date: datetime, tz: ZoneInfo) -> ScheduleContext:
    """
    Create a schedule context for a specific date and timezone.
    
    Args:
        date: The date to schedule for
        tz: Timezone for the schedule
        
    Returns:
        ScheduleContext with DST information
    """
    hours = enumerate_hours_for_date(date, tz)
    num_hours = len(hours)
    
    is_dst_transition = num_hours != 24
    dst_info = ""
    
    if num_hours == 23:
        dst_info = "DST spring forward (23-hour day, 2AM skipped)"
    elif num_hours == 25:
        dst_info = "DST fall back (25-hour day, 1AM repeated)"
    
    return ScheduleContext(
        date=date,
        timezone=tz,
        hours=hours,
        is_dst_transition=is_dst_transition,
        dst_info=dst_info
    )
