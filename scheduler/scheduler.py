"""
Core scheduling algorithms for agent staffing.
"""

import math
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .models import (
    CustomerRequest, 
    HourlySchedule, 
    CapacityAllocation,
    ScheduleContext,
    create_schedule_context,
    enumerate_hours_for_date,
    DEFAULT_TIMEZONE
)


def compute_schedule(
    requests: List[CustomerRequest],
    utilization: float = 1.0,
    context: Optional[ScheduleContext] = None
) -> List[HourlySchedule]:
    """
    Compute hour-by-hour agent needs for all customers.
    
    Args:
        requests: List of customer call requirements
        utilization: Agent utilization factor (0-1). Lower means more conservative sizing.
        context: Optional ScheduleContext for timezone-aware scheduling.
                 If None, uses simple 24-hour scheduling without DST handling.
        
    Returns:
        List of HourlySchedule objects (one per hour)
        - Without context: 24 schedules (00:00-23:00)
        - With context: May be 23, 24, or 25 schedules depending on DST
    """
    if context is None:
        # Simple mode: 24 hours, no timezone awareness
        return _compute_schedule_simple(requests, utilization)
    else:
        # Timezone-aware mode
        return _compute_schedule_tz_aware(requests, utilization, context)


def _compute_schedule_simple(
    requests: List[CustomerRequest],
    utilization: float
) -> List[HourlySchedule]:
    """Simple 24-hour scheduling without timezone awareness."""
    schedules = []
    
    for hour in range(24):
        customer_agents = {}
        
        for req in requests:
            if req.is_active_at_hour(hour):
                agents = req.agents_needed_per_hour(utilization)
                if agents > 0:
                    customer_agents[req.name] = agents
        
        schedules.append(HourlySchedule(hour=hour, customer_agents=customer_agents))
    
    return schedules


def _compute_schedule_tz_aware(
    requests: List[CustomerRequest],
    utilization: float,
    context: ScheduleContext
) -> List[HourlySchedule]:
    """Timezone-aware scheduling with DST handling."""
    schedules = []
    
    for hour_dt in context.hours:
        local_hour = hour_dt.hour
        utc_dt = hour_dt.astimezone(ZoneInfo("UTC"))
        
        customer_agents = {}
        
        for req in requests:
            if req.is_active_at_hour(local_hour):
                # Use DST-aware agent calculation
                agents = req.agents_needed_for_date(context.date, context.timezone, utilization)
                if agents > 0:
                    customer_agents[req.name] = agents
        
        schedules.append(HourlySchedule(
            hour=local_hour,
            customer_agents=customer_agents,
            datetime_utc=utc_dt,
            datetime_local=hour_dt
        ))
    
    return schedules


def compute_with_capacity(
    requests: List[CustomerRequest],
    capacity: int,
    utilization: float = 1.0,
    context: Optional[ScheduleContext] = None
) -> CapacityAllocation:
    """
    Compute schedule with a fixed agent capacity constraint.
    
    This implements priority-aware allocation:
    1. Sort customers by priority (1 is highest)
    2. For each hour, allocate agents to higher-priority customers first
    3. Track unmet demand when capacity is exceeded
    
    Allocation Strategy: "Priority-First Proportional"
    - Higher priority customers get their full demand met first
    - Lower priority customers get remaining capacity
    - Within same priority, allocation is proportional to demand
    
    Args:
        requests: List of customer call requirements
        capacity: Maximum number of agents available
        utilization: Agent utilization factor
        context: Optional ScheduleContext for timezone-aware scheduling
        
    Returns:
        CapacityAllocation with schedules and unmet demand info
    """
    if context is None:
        return _compute_with_capacity_simple(requests, capacity, utilization)
    else:
        return _compute_with_capacity_tz_aware(requests, capacity, utilization, context)


def _compute_with_capacity_simple(
    requests: List[CustomerRequest],
    capacity: int,
    utilization: float
) -> CapacityAllocation:
    """Simple capacity-constrained scheduling without timezone awareness."""
    # First compute unconstrained schedule
    unconstrained = _compute_schedule_simple(requests, utilization)
    peak_demand = max(s.total_agents for s in unconstrained)
    
    # If capacity is sufficient, return unconstrained schedule
    if capacity >= peak_demand:
        return CapacityAllocation(
            schedules=unconstrained,
            peak_demand=peak_demand,
            capacity=capacity,
            unmet_demand={},
            utilization_by_hour={h: s.total_agents / capacity if capacity > 0 else 0 
                                 for h, s in enumerate(unconstrained)}
        )
    
    # Need to constrain - sort by priority
    sorted_requests = sorted(requests, key=lambda r: r.priority)
    
    # Track original demand per customer per hour
    original_demand: Dict[str, Dict[int, int]] = {}
    for req in requests:
        original_demand[req.name] = {}
        for hour in range(24):
            if req.is_active_at_hour(hour):
                original_demand[req.name][hour] = req.agents_needed_per_hour(utilization)
    
    # Allocate with capacity constraint
    constrained_schedules = []
    allocated_per_customer: Dict[str, Dict[int, int]] = {req.name: {} for req in requests}
    
    for hour in range(24):
        remaining_capacity = capacity
        customer_agents = {}
        
        # Process customers by priority
        for req in sorted_requests:
            if not req.is_active_at_hour(hour):
                continue
            
            demand = req.agents_needed_per_hour(utilization)
            
            # Allocate up to remaining capacity
            allocated = min(demand, remaining_capacity)
            
            if allocated > 0:
                customer_agents[req.name] = allocated
                allocated_per_customer[req.name][hour] = allocated
                remaining_capacity -= allocated
            else:
                allocated_per_customer[req.name][hour] = 0
        
        constrained_schedules.append(HourlySchedule(hour=hour, customer_agents=customer_agents))
    
    # Calculate unmet demand
    unmet_demand = _calculate_unmet_demand(requests, original_demand, allocated_per_customer)
    
    utilization_by_hour = {
        h: s.total_agents / capacity if capacity > 0 else 0
        for h, s in enumerate(constrained_schedules)
    }
    
    return CapacityAllocation(
        schedules=constrained_schedules,
        peak_demand=peak_demand,
        capacity=capacity,
        unmet_demand=unmet_demand,
        utilization_by_hour=utilization_by_hour
    )


def _compute_with_capacity_tz_aware(
    requests: List[CustomerRequest],
    capacity: int,
    utilization: float,
    context: ScheduleContext
) -> CapacityAllocation:
    """Timezone-aware capacity-constrained scheduling."""
    # First compute unconstrained schedule
    unconstrained = _compute_schedule_tz_aware(requests, utilization, context)
    peak_demand = max(s.total_agents for s in unconstrained) if unconstrained else 0
    
    # If capacity is sufficient, return unconstrained schedule
    if capacity >= peak_demand:
        return CapacityAllocation(
            schedules=unconstrained,
            peak_demand=peak_demand,
            capacity=capacity,
            unmet_demand={},
            utilization_by_hour={i: s.total_agents / capacity if capacity > 0 else 0 
                                 for i, s in enumerate(unconstrained)}
        )
    
    # Need to constrain - sort by priority
    sorted_requests = sorted(requests, key=lambda r: r.priority)
    
    # Track original demand per customer per hour index
    original_demand: Dict[str, Dict[int, int]] = {}
    for req in requests:
        original_demand[req.name] = {}
        for idx, hour_dt in enumerate(context.hours):
            if req.is_active_at_hour(hour_dt.hour):
                original_demand[req.name][idx] = req.agents_needed_for_date(
                    context.date, context.timezone, utilization
                )
    
    # Allocate with capacity constraint
    constrained_schedules = []
    allocated_per_customer: Dict[str, Dict[int, int]] = {req.name: {} for req in requests}
    
    for idx, hour_dt in enumerate(context.hours):
        local_hour = hour_dt.hour
        utc_dt = hour_dt.astimezone(ZoneInfo("UTC"))
        remaining_capacity = capacity
        customer_agents = {}
        
        # Process customers by priority
        for req in sorted_requests:
            if not req.is_active_at_hour(local_hour):
                continue
            
            demand = req.agents_needed_for_date(context.date, context.timezone, utilization)
            
            # Allocate up to remaining capacity
            allocated = min(demand, remaining_capacity)
            
            if allocated > 0:
                customer_agents[req.name] = allocated
                allocated_per_customer[req.name][idx] = allocated
                remaining_capacity -= allocated
            else:
                allocated_per_customer[req.name][idx] = 0
        
        constrained_schedules.append(HourlySchedule(
            hour=local_hour,
            customer_agents=customer_agents,
            datetime_utc=utc_dt,
            datetime_local=hour_dt
        ))
    
    # Calculate unmet demand (adapted for variable hour count)
    unmet_demand = _calculate_unmet_demand_tz(
        requests, original_demand, allocated_per_customer, context
    )
    
    utilization_by_hour = {
        i: s.total_agents / capacity if capacity > 0 else 0
        for i, s in enumerate(constrained_schedules)
    }
    
    return CapacityAllocation(
        schedules=constrained_schedules,
        peak_demand=peak_demand,
        capacity=capacity,
        unmet_demand=unmet_demand,
        utilization_by_hour=utilization_by_hour
    )


def _calculate_unmet_demand(
    requests: List[CustomerRequest],
    original_demand: Dict[str, Dict[int, int]],
    allocated_per_customer: Dict[str, Dict[int, int]]
) -> Dict[str, dict]:
    """Calculate unmet demand for simple scheduling."""
    unmet_demand = {}
    
    for req in requests:
        total_original = sum(original_demand[req.name].values())
        total_allocated = sum(allocated_per_customer[req.name].values())
        
        if total_allocated < total_original:
            agent_hours_deficit = total_original - total_allocated
            calls_unmet = int(agent_hours_deficit * 3600 / req.avg_call_duration_seconds)
            
            hours_affected = sum(
                1 for h in range(24) 
                if h in original_demand[req.name] 
                and allocated_per_customer[req.name].get(h, 0) < original_demand[req.name][h]
            )
            
            unmet_demand[req.name] = {
                'calls_unmet': calls_unmet,
                'calls_total': req.number_of_calls,
                'hours_affected': hours_affected,
                'priority': req.priority,
                'percent_unmet': round(100 * calls_unmet / req.number_of_calls, 1) if req.number_of_calls > 0 else 0
            }
    
    return unmet_demand


def _calculate_unmet_demand_tz(
    requests: List[CustomerRequest],
    original_demand: Dict[str, Dict[int, int]],
    allocated_per_customer: Dict[str, Dict[int, int]],
    context: ScheduleContext
) -> Dict[str, dict]:
    """Calculate unmet demand for timezone-aware scheduling."""
    unmet_demand = {}
    
    for req in requests:
        total_original = sum(original_demand[req.name].values())
        total_allocated = sum(allocated_per_customer[req.name].values())
        
        if total_allocated < total_original:
            agent_hours_deficit = total_original - total_allocated
            calls_unmet = int(agent_hours_deficit * 3600 / req.avg_call_duration_seconds)
            
            hours_affected = sum(
                1 for idx in range(len(context.hours))
                if idx in original_demand[req.name] 
                and allocated_per_customer[req.name].get(idx, 0) < original_demand[req.name][idx]
            )
            
            unmet_demand[req.name] = {
                'calls_unmet': calls_unmet,
                'calls_total': req.number_of_calls,
                'hours_affected': hours_affected,
                'priority': req.priority,
                'percent_unmet': round(100 * calls_unmet / req.number_of_calls, 1) if req.number_of_calls > 0 else 0
            }
    
    return unmet_demand
