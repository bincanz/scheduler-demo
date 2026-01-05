"""
Simple Flask web UI for the agent scheduler.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler.models import create_schedule_context, DEFAULT_TIMEZONE
from scheduler.parser import parse_csv, parse_date, validate_timezone, ValidationError
from scheduler.scheduler import compute_schedule, compute_with_capacity

app = Flask(__name__)

# Default input file path
DEFAULT_INPUT = os.environ.get('SCHEDULER_INPUT', 
                               str(Path(__file__).parent.parent / 'input.csv'))


@app.route('/')
def index():
    """Render the main UI."""
    return render_template('index.html')


@app.route('/api/schedule', methods=['POST'])
def compute():
    """
    API endpoint to compute schedule.
    
    Accepts JSON body:
    {
        "input_file": "path/to/file.csv",  // optional, uses default
        "utilization": 1.0,  // optional
        "capacity": null,  // optional
        "timezone": "America/Los_Angeles",  // optional
        "date": "2024-03-10"  // optional, YYYY-MM-DD
    }
    """
    data = request.get_json() or {}
    
    input_file = data.get('input_file', DEFAULT_INPUT)
    utilization = float(data.get('utilization', 1.0))
    capacity = data.get('capacity')
    timezone_str = data.get('timezone', DEFAULT_TIMEZONE)
    date_str = data.get('date')
    
    if capacity is not None:
        capacity = int(capacity)
    
    try:
        # Validate timezone
        tz = validate_timezone(timezone_str)
        
        # Parse date
        schedule_date = parse_date(date_str)
        
        # Create schedule context
        context = create_schedule_context(schedule_date, tz)
        
        requests, warnings = parse_csv(input_file)
        
        if capacity is not None:
            result = compute_with_capacity(requests, capacity, utilization, context)
            schedules = result.schedules
            
            response = {
                'schedules': [s.to_dict() for s in schedules],
                'customers': [
                    {
                        'name': r.name,
                        'priority': r.priority,
                        'start_hour': r.start_hour,
                        'end_hour': r.end_hour,
                        'calls': r.number_of_calls,
                        'duration': r.avg_call_duration_seconds
                    } 
                    for r in requests
                ],
                'timezone_info': {
                    'timezone': str(context.timezone),
                    'date': context.date.strftime('%Y-%m-%d'),
                    'hours_in_day': context.num_hours,
                    'is_dst_transition': context.is_dst_transition,
                    'dst_info': context.dst_info if context.is_dst_transition else None
                },
                'capacity_analysis': {
                    'capacity': result.capacity,
                    'peak_demand': result.peak_demand,
                    'unmet_demand': result.unmet_demand,
                    'utilization_by_hour': {
                        h: round(u, 3) for h, u in result.utilization_by_hour.items()
                    }
                },
                'warnings': warnings
            }
        else:
            schedules = compute_schedule(requests, utilization, context)
            peak = max(s.total_agents for s in schedules) if schedules else 0
            
            response = {
                'schedules': [s.to_dict() for s in schedules],
                'customers': [
                    {
                        'name': r.name,
                        'priority': r.priority,
                        'start_hour': r.start_hour,
                        'end_hour': r.end_hour,
                        'calls': r.number_of_calls,
                        'duration': r.avg_call_duration_seconds
                    } 
                    for r in requests
                ],
                'timezone_info': {
                    'timezone': str(context.timezone),
                    'date': context.date.strftime('%Y-%m-%d'),
                    'hours_in_day': context.num_hours,
                    'is_dst_transition': context.is_dst_transition,
                    'dst_info': context.dst_info if context.is_dst_transition else None
                },
                'peak_demand': peak,
                'warnings': warnings
            }
        
        return jsonify(response)
        
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
