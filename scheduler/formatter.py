"""
Output formatters for schedule data.
"""

import csv
import io
import json
from typing import List, Optional

from .models import HourlySchedule, CapacityAllocation


def format_text(
    schedules: List[HourlySchedule],
    capacity_info: Optional[CapacityAllocation] = None
) -> str:
    """
    Format schedules as text output (24 lines, one per hour).
    
    Args:
        schedules: List of 24 HourlySchedule objects
        capacity_info: Optional capacity allocation info for additional output
        
    Returns:
        Formatted text string
    """
    lines = [schedule.to_text() for schedule in schedules]
    output = "\n".join(lines)
    
    # Add capacity summary if available
    if capacity_info and capacity_info.has_unmet_demand():
        output += "\n\n--- Capacity Analysis ---"
        output += f"\nCapacity: {capacity_info.capacity} agents"
        output += f"\nPeak Demand (unconstrained): {capacity_info.peak_demand} agents"
        output += "\n\nUnmet Demand by Customer:"
        
        for customer, info in sorted(capacity_info.unmet_demand.items(), key=lambda x: x[1]['priority']):
            output += f"\n  {customer} (Priority {info['priority']}): "
            output += f"{info['calls_unmet']:,} calls unmet ({info['percent_unmet']}% of {info['calls_total']:,}), "
            output += f"{info['hours_affected']} hours affected"
        
        output += "\n\nHourly Utilization:"
        for hour, util in capacity_info.utilization_by_hour.items():
            if util > 0:
                output += f"\n  {hour:02d}:00 - {util*100:.1f}%"
    
    return output


def format_json(
    schedules: List[HourlySchedule],
    capacity_info: Optional[CapacityAllocation] = None
) -> str:
    """
    Format schedules as JSON.
    
    Args:
        schedules: List of 24 HourlySchedule objects
        capacity_info: Optional capacity allocation info
        
    Returns:
        JSON string
    """
    data = {
        "schedules": [s.to_dict() for s in schedules],
        "summary": {
            "peak_total_agents": max(s.total_agents for s in schedules),
            "active_hours": sum(1 for s in schedules if s.total_agents > 0)
        }
    }
    
    if capacity_info:
        data["capacity_analysis"] = {
            "capacity": capacity_info.capacity,
            "peak_demand": capacity_info.peak_demand,
            "unmet_demand": capacity_info.unmet_demand,
            "utilization_by_hour": {
                f"{h:02d}:00": round(u, 3) 
                for h, u in capacity_info.utilization_by_hour.items()
            }
        }
    
    return json.dumps(data, indent=2)


def format_csv(
    schedules: List[HourlySchedule],
    capacity_info: Optional[CapacityAllocation] = None
) -> str:
    """
    Format schedules as CSV.
    
    Args:
        schedules: List of 24 HourlySchedule objects
        capacity_info: Optional capacity allocation info
        
    Returns:
        CSV string
    """
    output = io.StringIO()
    
    # Collect all unique customer names
    all_customers = set()
    for schedule in schedules:
        all_customers.update(schedule.customer_agents.keys())
    
    sorted_customers = sorted(all_customers)
    
    # Write header
    fieldnames = ['Hour', 'Total'] + sorted_customers
    if capacity_info:
        fieldnames.append('Utilization')
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    # Write rows
    for schedule in schedules:
        row = {
            'Hour': f"{schedule.hour:02d}:00",
            'Total': schedule.total_agents
        }
        
        for customer in sorted_customers:
            row[customer] = schedule.customer_agents.get(customer, 0)
        
        if capacity_info:
            util = capacity_info.utilization_by_hour.get(schedule.hour, 0)
            row['Utilization'] = f"{util*100:.1f}%"
        
        writer.writerow(row)
    
    return output.getvalue()


def format_output(
    schedules: List[HourlySchedule],
    format_type: str = "text",
    capacity_info: Optional[CapacityAllocation] = None
) -> str:
    """
    Format schedules in the specified format.
    
    Args:
        schedules: List of 24 HourlySchedule objects
        format_type: One of "text", "json", or "csv"
        capacity_info: Optional capacity allocation info
        
    Returns:
        Formatted string
        
    Raises:
        ValueError: If format_type is invalid
    """
    formatters = {
        "text": format_text,
        "json": format_json,
        "csv": format_csv
    }
    
    if format_type not in formatters:
        raise ValueError(f"Invalid format: {format_type}. Must be one of: {list(formatters.keys())}")
    
    return formatters[format_type](schedules, capacity_info)

