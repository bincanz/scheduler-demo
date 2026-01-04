"""
Core scheduling algorithms for agent staffing.
"""

import math
from typing import Dict, List, Optional

from .models import CustomerRequest, HourlySchedule, CapacityAllocation


def compute_schedule(
    requests: List[CustomerRequest],
    utilization: float = 1.0
) -> List[HourlySchedule]:
    """
    Compute hour-by-hour agent needs for all customers.
    
    Args:
        requests: List of customer call requirements
        utilization: Agent utilization factor (0-1). Lower means more conservative sizing.
        
    Returns:
        List of 24 HourlySchedule objects (one per hour, 00:00-23:00)
    """
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


def compute_with_capacity(
    requests: List[CustomerRequest],
    capacity: int,
    utilization: float = 1.0
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
    
    Alternative approaches considered:
    - Pure proportional: Splits capacity proportionally regardless of priority
      Pro: Fair to all customers. Con: High-priority customers may not get full service.
    - Strict priority: Only serves lower priority if higher is 100% satisfied
      Pro: Guarantees priority. Con: May starve low-priority customers entirely.
    - Time-shifting: Move lower-priority calls to off-peak hours
      Pro: Maximizes capacity usage. Con: May violate customer time windows.
    
    Args:
        requests: List of customer call requirements
        capacity: Maximum number of agents available
        utilization: Agent utilization factor
        
    Returns:
        CapacityAllocation with schedules and unmet demand info
    """
    # First compute unconstrained schedule
    unconstrained = compute_schedule(requests, utilization)
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
    unmet_demand = {}
    for req in requests:
        total_original = sum(original_demand[req.name].values())
        total_allocated = sum(allocated_per_customer[req.name].values())
        
        if total_allocated < total_original:
            # Calculate unmet calls
            # agents_per_hour * hours = total_agent_hours
            # agent_hours * 3600 / duration = calls handled
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

