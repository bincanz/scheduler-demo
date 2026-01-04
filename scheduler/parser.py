"""
CSV parser with validation for customer call requirements.
"""

import csv
import re
from pathlib import Path
from typing import List, Tuple

from .models import CustomerRequest


class ValidationError(Exception):
    """Raised when CSV validation fails."""
    pass


def parse_time_pt(time_str: str) -> int:
    """
    Parse Pacific Time string (e.g., '9AM', '7PM', '12PM') to hour (0-23).
    
    Args:
        time_str: Time string like '9AM', '12PM', '7PM'
        
    Returns:
        Hour in 24-hour format (0-23)
        
    Raises:
        ValidationError: If time format is invalid
    """
    time_str = time_str.strip().upper()
    
    # Match patterns like "9AM", "12PM", "7PM"
    match = re.match(r'^(\d{1,2})(AM|PM)$', time_str)
    if not match:
        raise ValidationError(f"Invalid time format: '{time_str}'. Expected format like '9AM' or '7PM'")
    
    hour = int(match.group(1))
    period = match.group(2)
    
    if hour < 1 or hour > 12:
        raise ValidationError(f"Invalid hour: {hour}. Must be 1-12")
    
    # Convert to 24-hour format
    if period == 'AM':
        if hour == 12:
            return 0  # 12AM = midnight = 0
        return hour
    else:  # PM
        if hour == 12:
            return 12  # 12PM = noon = 12
        return hour + 12


def parse_csv(file_path: str) -> Tuple[List[CustomerRequest], List[str]]:
    """
    Parse and validate CSV file with customer call requirements.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Tuple of (list of CustomerRequest, list of warning messages)
        
    Raises:
        ValidationError: If required fields are missing or invalid
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    requests = []
    warnings = []
    
    with open(path, 'r', newline='', encoding='utf-8') as f:
        # Handle potential BOM and whitespace
        content = f.read().strip()
        if content.startswith('\ufeff'):
            content = content[1:]
        
        reader = csv.DictReader(content.splitlines())
        
        # Normalize header names (strip whitespace and handle variations)
        if reader.fieldnames is None:
            raise ValidationError("CSV file appears to be empty or has no header row")
        
        # Expected columns (case-insensitive, whitespace-tolerant)
        required_cols = {
            'customername': 'CustomerName',
            'averagecalldurationseconds': 'AverageCallDurationSeconds', 
            'starttimept': 'StartTimePT',
            'endtimept': 'EndTimePT',
            'numberofcalls': 'NumberOfCalls',
            'priority': 'Priority'
        }
        
        # Map actual column names to our expected names
        col_map = {}
        normalized_headers = {h.lower().replace(' ', '').replace('_', ''): h for h in reader.fieldnames}
        
        for norm_key, display_name in required_cols.items():
            if norm_key in normalized_headers:
                col_map[display_name] = normalized_headers[norm_key]
            else:
                raise ValidationError(f"Missing required column: {display_name}")
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 for header, 1 for first data row)
            try:
                # Extract values using column mapping
                name = row[col_map['CustomerName']].strip()
                if not name:
                    raise ValidationError("CustomerName cannot be empty")
                
                # Parse numeric fields
                try:
                    duration = int(row[col_map['AverageCallDurationSeconds']].strip())
                    if duration <= 0:
                        raise ValidationError("AverageCallDurationSeconds must be positive")
                except ValueError:
                    raise ValidationError(f"Invalid AverageCallDurationSeconds: {row[col_map['AverageCallDurationSeconds']]}")
                
                try:
                    num_calls = int(row[col_map['NumberOfCalls']].strip())
                    if num_calls < 0:
                        raise ValidationError("NumberOfCalls cannot be negative")
                except ValueError:
                    raise ValidationError(f"Invalid NumberOfCalls: {row[col_map['NumberOfCalls']]}")
                
                try:
                    priority = int(row[col_map['Priority']].strip())
                    if priority < 1 or priority > 5:
                        raise ValidationError(f"Priority must be 1-5, got: {priority}")
                except ValueError:
                    raise ValidationError(f"Invalid Priority: {row[col_map['Priority']]}")
                
                # Parse times
                start_hour = parse_time_pt(row[col_map['StartTimePT']])
                end_hour = parse_time_pt(row[col_map['EndTimePT']])
                
                if start_hour >= end_hour:
                    raise ValidationError(
                        f"StartTime ({row[col_map['StartTimePT']]}) must be before "
                        f"EndTime ({row[col_map['EndTimePT']]})"
                    )
                
                request = CustomerRequest(
                    name=name,
                    avg_call_duration_seconds=duration,
                    start_hour=start_hour,
                    end_hour=end_hour,
                    number_of_calls=num_calls,
                    priority=priority
                )
                requests.append(request)
                
            except ValidationError as e:
                raise ValidationError(f"Row {row_num}: {e}")
            except KeyError as e:
                raise ValidationError(f"Row {row_num}: Missing column {e}")
    
    if not requests:
        warnings.append("CSV file contains no data rows")
    
    return requests, warnings

