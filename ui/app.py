"""
Simple Flask web UI for the agent scheduler.
"""

import os
import sys
from pathlib import Path

from flask import Flask, render_template, request, jsonify

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler.parser import parse_csv, ValidationError
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
        "capacity": null  // optional
    }
    """
    data = request.get_json() or {}
    
    input_file = data.get('input_file', DEFAULT_INPUT)
    utilization = float(data.get('utilization', 1.0))
    capacity = data.get('capacity')
    
    if capacity is not None:
        capacity = int(capacity)
    
    try:
        requests, warnings = parse_csv(input_file)
        
        if capacity is not None:
            result = compute_with_capacity(requests, capacity, utilization)
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
            schedules = compute_schedule(requests, utilization)
            peak = max(s.total_agents for s in schedules)
            
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

