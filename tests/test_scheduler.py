"""Tests for scheduler module."""

import pytest
import math

from scheduler.models import CustomerRequest, HourlySchedule
from scheduler.scheduler import compute_schedule, compute_with_capacity


class TestCustomerRequest:
    """Tests for CustomerRequest model."""
    
    def test_active_hours(self):
        req = CustomerRequest(
            name='Test',
            avg_call_duration_seconds=300,
            start_hour=9,
            end_hour=17,
            number_of_calls=1000,
            priority=1
        )
        assert req.active_hours == 8
    
    def test_calls_per_hour(self):
        req = CustomerRequest(
            name='Test',
            avg_call_duration_seconds=300,
            start_hour=9,
            end_hour=17,
            number_of_calls=800,
            priority=1
        )
        assert req.calls_per_hour == 100  # 800 / 8 hours
    
    def test_agents_needed_per_hour(self):
        # 100 calls/hour * 300 seconds / 3600 = 8.33 -> ceil = 9
        req = CustomerRequest(
            name='Test',
            avg_call_duration_seconds=300,
            start_hour=9,
            end_hour=17,
            number_of_calls=800,
            priority=1
        )
        assert req.agents_needed_per_hour() == 9
    
    def test_agents_needed_with_utilization(self):
        req = CustomerRequest(
            name='Test',
            avg_call_duration_seconds=300,
            start_hour=9,
            end_hour=17,
            number_of_calls=800,
            priority=1
        )
        # 8.33 / 0.8 = 10.42 -> ceil = 11
        assert req.agents_needed_per_hour(utilization=0.8) == 11
    
    def test_is_active_at_hour(self):
        req = CustomerRequest(
            name='Test',
            avg_call_duration_seconds=300,
            start_hour=9,
            end_hour=17,
            number_of_calls=800,
            priority=1
        )
        assert not req.is_active_at_hour(8)
        assert req.is_active_at_hour(9)
        assert req.is_active_at_hour(16)
        assert not req.is_active_at_hour(17)


class TestComputeSchedule:
    """Tests for compute_schedule function."""
    
    def test_basic_schedule(self):
        requests = [
            CustomerRequest(
                name='Test',
                avg_call_duration_seconds=360,  # 6 minutes
                start_hour=9,
                end_hour=12,
                number_of_calls=300,
                priority=1
            )
        ]
        
        schedules = compute_schedule(requests)
        
        # 300 calls / 3 hours = 100 calls/hour
        # 100 * 360 / 3600 = 10 agents
        assert len(schedules) == 24
        assert schedules[8].total_agents == 0
        assert schedules[9].total_agents == 10
        assert schedules[10].total_agents == 10
        assert schedules[11].total_agents == 10
        assert schedules[12].total_agents == 0
    
    def test_multiple_customers(self):
        requests = [
            CustomerRequest('A', 360, 9, 12, 300, 1),
            CustomerRequest('B', 720, 10, 11, 100, 2),
        ]
        
        schedules = compute_schedule(requests)
        
        # A: 100 calls/hour * 360s / 3600 = 10 agents
        # B: 100 calls/hour * 720s / 3600 = 20 agents
        
        assert schedules[9].customer_agents == {'A': 10}
        assert schedules[10].customer_agents == {'A': 10, 'B': 20}
        assert schedules[11].customer_agents == {'A': 10}


class TestComputeWithCapacity:
    """Tests for capacity-constrained scheduling."""
    
    def test_capacity_sufficient(self):
        requests = [
            CustomerRequest('A', 360, 9, 12, 300, 1)
        ]
        
        result = compute_with_capacity(requests, capacity=100)
        
        assert result.peak_demand == 10
        assert result.capacity == 100
        assert not result.has_unmet_demand()
    
    def test_capacity_insufficient(self):
        requests = [
            CustomerRequest('High', 360, 9, 11, 200, 1),  # 10 agents
            CustomerRequest('Low', 360, 9, 11, 200, 5),   # 10 agents
        ]
        
        result = compute_with_capacity(requests, capacity=15)
        
        # Should allocate 10 to High priority, 5 to Low
        assert result.schedules[9].customer_agents['High'] == 10
        assert result.schedules[9].customer_agents['Low'] == 5
        assert result.has_unmet_demand()
        assert 'Low' in result.unmet_demand
    
    def test_priority_ordering(self):
        # Higher priority should get full allocation first
        requests = [
            CustomerRequest('P5', 360, 9, 10, 100, 5),
            CustomerRequest('P1', 360, 9, 10, 100, 1),
            CustomerRequest('P3', 360, 9, 10, 100, 3),
        ]
        
        result = compute_with_capacity(requests, capacity=15)
        
        # P1 (highest priority) should get full allocation
        # Then P3, then P5 with remaining
        schedule = result.schedules[9]
        
        assert schedule.customer_agents.get('P1', 0) == 10
        assert schedule.customer_agents.get('P3', 0) == 5
        assert schedule.customer_agents.get('P5', 0) == 0

