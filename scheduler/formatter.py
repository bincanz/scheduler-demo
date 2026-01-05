"""
Output formatters for schedule data.
"""

import csv
import io
import json
from typing import List, Optional

from .models import HourlySchedule, CapacityAllocation, ScheduleContext


def format_text(
    schedules: List[HourlySchedule],
    capacity_info: Optional[CapacityAllocation] = None,
    context: Optional[ScheduleContext] = None,
    show_utc: bool = False
) -> str:
    """
    Format schedules as text output (one line per hour).
    
    Args:
        schedules: List of HourlySchedule objects
        capacity_info: Optional capacity allocation info for additional output
        context: Optional schedule context for timezone info
        show_utc: Whether to show UTC times (ignored for text format)
        
    Returns:
        Formatted text string
    """
    lines = []
    
    # Add timezone/DST header if context provided
    if context:
        if context.is_dst_transition:
            lines.append(f"# Note: {context.dst_info}")
            lines.append(f"# Timezone: {context.timezone}, Date: {context.date.strftime('%Y-%m-%d')}")
            lines.append("")
    
    for schedule in schedules:
        lines.append(schedule.to_text())
    
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
        for idx, util in capacity_info.utilization_by_hour.items():
            if util > 0:
                if schedules[idx].datetime_local:
                    hour_str = schedules[idx].datetime_local.strftime("%H:%M")
                else:
                    hour_str = f"{schedules[idx].hour:02d}:00"
                output += f"\n  {hour_str} - {util*100:.1f}%"
    
    return output


def format_json(
    schedules: List[HourlySchedule],
    capacity_info: Optional[CapacityAllocation] = None,
    context: Optional[ScheduleContext] = None,
    show_utc: bool = False
) -> str:
    """
    Format schedules as JSON.
    
    Args:
        schedules: List of HourlySchedule objects
        capacity_info: Optional capacity allocation info
        context: Optional schedule context for timezone info
        show_utc: Whether to include UTC timestamps
        
    Returns:
        JSON string
    """
    data = {
        "schedules": [s.to_dict() for s in schedules],
        "summary": {
            "peak_total_agents": max(s.total_agents for s in schedules) if schedules else 0,
            "active_hours": sum(1 for s in schedules if s.total_agents > 0),
            "total_hours": len(schedules)
        }
    }
    
    # Add timezone context if provided
    if context:
        data["timezone_info"] = {
            "timezone": str(context.timezone),
            "date": context.date.strftime("%Y-%m-%d"),
            "hours_in_day": context.num_hours,
            "is_dst_transition": context.is_dst_transition,
            "dst_info": context.dst_info if context.is_dst_transition else None
        }
    
    # Remove UTC timestamps if not requested
    if not show_utc:
        for schedule_dict in data["schedules"]:
            schedule_dict.pop("datetime_utc", None)
    
    if capacity_info:
        data["capacity_analysis"] = {
            "capacity": capacity_info.capacity,
            "peak_demand": capacity_info.peak_demand,
            "unmet_demand": capacity_info.unmet_demand,
            "utilization_by_hour": {
                str(h): round(u, 3) 
                for h, u in capacity_info.utilization_by_hour.items()
            }
        }
    
    return json.dumps(data, indent=2)


def format_csv(
    schedules: List[HourlySchedule],
    capacity_info: Optional[CapacityAllocation] = None,
    context: Optional[ScheduleContext] = None,
    show_utc: bool = False
) -> str:
    """
    Format schedules as CSV.
    
    Args:
        schedules: List of HourlySchedule objects
        capacity_info: Optional capacity allocation info
        context: Optional schedule context for timezone info
        show_utc: Whether to include UTC timestamps
        
    Returns:
        CSV string
    """
    output = io.StringIO()
    
    # Collect all unique customer names
    all_customers = set()
    for schedule in schedules:
        all_customers.update(schedule.customer_agents.keys())
    
    sorted_customers = sorted(all_customers)
    
    # Build header
    fieldnames = ['Hour', 'LocalTime']
    if show_utc:
        fieldnames.append('UTC')
    fieldnames.extend(['Total'] + sorted_customers)
    if capacity_info:
        fieldnames.append('Utilization')
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    # Write rows
    for idx, schedule in enumerate(schedules):
        row = {
            'Hour': f"{schedule.hour:02d}:00",
            'LocalTime': schedule.datetime_local.isoformat() if schedule.datetime_local else '',
            'Total': schedule.total_agents
        }
        
        if show_utc:
            row['UTC'] = schedule.datetime_utc.isoformat() if schedule.datetime_utc else ''
        
        for customer in sorted_customers:
            row[customer] = schedule.customer_agents.get(customer, 0)
        
        if capacity_info:
            util = capacity_info.utilization_by_hour.get(idx, 0)
            row['Utilization'] = f"{util*100:.1f}%"
        
        writer.writerow(row)
    
    return output.getvalue()


def format_output(
    schedules: List[HourlySchedule],
    format_type: str = "text",
    capacity_info: Optional[CapacityAllocation] = None,
    context: Optional[ScheduleContext] = None,
    show_utc: bool = False
) -> str:
    """
    Format schedules in the specified format.
    
    Args:
        schedules: List of HourlySchedule objects
        format_type: One of "text", "json", or "csv"
        capacity_info: Optional capacity allocation info
        context: Optional schedule context for timezone info
        show_utc: Whether to include UTC timestamps
        
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
    
    return formatters[format_type](schedules, capacity_info, context, show_utc)

