"""Tests for CSV parser module."""

import pytest
import tempfile
from pathlib import Path

from scheduler.parser import parse_time_pt, parse_time_to_hour, parse_csv, ValidationError


class TestParseTimePT:
    """Tests for time parsing."""
    
    def test_am_times(self):
        assert parse_time_pt('6AM') == 6
        assert parse_time_pt('9AM') == 9
        assert parse_time_pt('11AM') == 11
    
    def test_pm_times(self):
        assert parse_time_pt('1PM') == 13
        assert parse_time_pt('3PM') == 15
        assert parse_time_pt('7PM') == 19
        assert parse_time_pt('11PM') == 23
    
    def test_noon_and_midnight(self):
        assert parse_time_pt('12AM') == 0  # Midnight
        assert parse_time_pt('12PM') == 12  # Noon
    
    def test_case_insensitive(self):
        assert parse_time_pt('9am') == 9
        assert parse_time_pt('9Am') == 9
        assert parse_time_pt('9aM') == 9
    
    def test_whitespace(self):
        assert parse_time_pt(' 9AM ') == 9
        assert parse_time_pt('  7PM  ') == 19
    
    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            parse_time_pt('9:00AM')
        with pytest.raises(ValidationError):
            parse_time_pt('9')
        with pytest.raises(ValidationError):
            parse_time_pt('AM')
        with pytest.raises(ValidationError):
            parse_time_pt('13PM')


class TestParseCSV:
    """Tests for CSV parsing."""
    
    def create_temp_csv(self, content: str) -> str:
        """Create a temporary CSV file with given content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            return f.name
    
    def test_valid_csv(self):
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Stanford Hospital,300,9AM,7PM,20000,1
VNS,120,6AM,1PM,40500,1"""
        
        path = self.create_temp_csv(csv_content)
        requests, warnings = parse_csv(path)
        
        assert len(requests) == 2
        assert requests[0].name == 'Stanford Hospital'
        assert requests[0].avg_call_duration_seconds == 300
        assert requests[0].start_hour == 9
        assert requests[0].end_hour == 19
        assert requests[0].number_of_calls == 20000
        assert requests[0].priority == 1
        
        assert requests[1].name == 'VNS'
        assert requests[1].start_hour == 6
        assert requests[1].end_hour == 13
    
    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            parse_csv('/nonexistent/path.csv')
    
    def test_invalid_priority(self):
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Test,300,9AM,7PM,20000,6"""
        
        path = self.create_temp_csv(csv_content)
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(path)
        assert 'Priority must be 1-5' in str(exc_info.value)
    
    def test_invalid_time_range(self):
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Test,300,7PM,9AM,20000,1"""
        
        path = self.create_temp_csv(csv_content)
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(path)
        assert 'StartTime' in str(exc_info.value) and 'EndTime' in str(exc_info.value)
    
    def test_negative_calls(self):
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Test,300,9AM,7PM,-100,1"""
        
        path = self.create_temp_csv(csv_content)
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(path)
        assert 'negative' in str(exc_info.value).lower()
    
    def test_empty_name(self):
        csv_content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
,300,9AM,7PM,20000,1"""
        
        path = self.create_temp_csv(csv_content)
        with pytest.raises(ValidationError) as exc_info:
            parse_csv(path)
        assert 'empty' in str(exc_info.value).lower()

