"""Tests for formatter module."""

import pytest
import json

from scheduler.models import HourlySchedule
from scheduler.formatter import format_text, format_json, format_csv


class TestFormatText:
    """Tests for text formatting."""
    
    def test_empty_schedule(self):
        schedules = [HourlySchedule(hour=h) for h in range(24)]
        output = format_text(schedules)
        
        lines = output.strip().split('\n')
        assert len(lines) == 24
        assert lines[0] == '00:00 : total=0 ; none'
        assert lines[23] == '23:00 : total=0 ; none'
    
    def test_schedule_with_customers(self):
        schedules = [HourlySchedule(hour=h) for h in range(24)]
        schedules[9] = HourlySchedule(hour=9, customer_agents={'A': 10, 'B': 5})
        
        output = format_text(schedules)
        lines = output.strip().split('\n')
        
        assert '09:00 : total=15' in lines[9]
        assert 'A=10' in lines[9]
        assert 'B=5' in lines[9]


class TestFormatJSON:
    """Tests for JSON formatting."""
    
    def test_json_structure(self):
        schedules = [HourlySchedule(hour=h) for h in range(24)]
        schedules[9] = HourlySchedule(hour=9, customer_agents={'A': 10})
        
        output = format_json(schedules)
        data = json.loads(output)
        
        assert 'schedules' in data
        assert 'summary' in data
        assert len(data['schedules']) == 24
        assert data['summary']['peak_total_agents'] == 10
    
    def test_json_schedule_format(self):
        schedules = [HourlySchedule(hour=0, customer_agents={'Test': 5})]
        output = format_json(schedules)
        data = json.loads(output)
        
        assert data['schedules'][0]['hour'] == '00:00'
        assert data['schedules'][0]['total_agents'] == 5
        assert data['schedules'][0]['customers'] == {'Test': 5}


class TestFormatCSV:
    """Tests for CSV formatting."""
    
    def test_csv_header(self):
        schedules = [HourlySchedule(hour=h) for h in range(24)]
        schedules[9] = HourlySchedule(hour=9, customer_agents={'A': 10, 'B': 5})
        
        output = format_csv(schedules)
        lines = output.strip().split('\n')
        
        header = lines[0]
        assert 'Hour' in header
        assert 'Total' in header
        assert 'A' in header
        assert 'B' in header
    
    def test_csv_data(self):
        schedules = [HourlySchedule(hour=9, customer_agents={'Test': 10})]
        output = format_csv(schedules)
        lines = output.strip().split('\n')
        
        assert len(lines) == 2  # header + 1 row
        assert '09:00' in lines[1]
        assert '10' in lines[1]

