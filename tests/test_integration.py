"""Integration tests for the scheduler."""

import pytest
import tempfile
from pathlib import Path

from scheduler.parser import parse_csv
from scheduler.scheduler import compute_schedule, compute_with_capacity
from scheduler.formatter import format_output


class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def sample_csv(self):
        """Create sample CSV matching the problem statement."""
        content = """CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Stanford Hospital,300,9AM,7PM,20000,1
VNS,120,6AM,1PM,40500,1
CVS,180,11AM,3PM,50000,3
SJC,1200,10AM,12PM,500,4
ANMC,400,7AM,8PM,80000,5
NMDX,220,10AM,6PM,40000,3"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            return f.name
    
    def test_expected_output(self, sample_csv):
        """Test that output matches expected values from problem statement."""
        requests, _ = parse_csv(sample_csv)
        schedules = compute_schedule(requests)
        
        # Verify key hours from expected output
        assert schedules[6].customer_agents == {'VNS': 193}
        assert schedules[6].total_agents == 193
        
        # Hour 7: VNS=193, ANMC=684
        assert schedules[7].customer_agents.get('VNS') == 193
        assert schedules[7].customer_agents.get('ANMC') == 684
        assert schedules[7].total_agents == 877
        
        # Hour 9: Stanford added
        assert schedules[9].customer_agents.get('Stanford Hospital') == 167
        assert schedules[9].total_agents == 1044
        
        # Hour 11: All active (peak for some)
        assert schedules[11].customer_agents.get('CVS') == 625
        assert schedules[11].total_agents == 2059
    
    def test_capacity_constraint(self, sample_csv):
        """Test capacity constraint from problem statement (500 agents)."""
        requests, _ = parse_csv(sample_csv)
        result = compute_with_capacity(requests, capacity=500)
        
        # All hours should be at or below capacity
        for schedule in result.schedules:
            assert schedule.total_agents <= 500
        
        # Should have unmet demand
        assert result.has_unmet_demand()
        assert result.peak_demand == 2059  # Unconstrained peak
    
    def test_full_pipeline(self, sample_csv):
        """Test complete pipeline from CSV to formatted output."""
        requests, warnings = parse_csv(sample_csv)
        schedules = compute_schedule(requests)
        
        # Test all output formats
        text_out = format_output(schedules, 'text')
        assert '00:00 : total=0 ; none' in text_out
        
        json_out = format_output(schedules, 'json')
        import json
        data = json.loads(json_out)
        assert len(data['schedules']) == 24
        
        csv_out = format_output(schedules, 'csv')
        assert 'Hour,Total' in csv_out

