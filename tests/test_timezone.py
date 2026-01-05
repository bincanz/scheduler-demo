"""Tests for timezone and DST handling."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from scheduler.models import (
    CustomerRequest,
    enumerate_hours_for_date,
    create_schedule_context,
    DEFAULT_TIMEZONE
)
from scheduler.parser import (
    validate_timezone,
    parse_date,
    parse_time_to_hour,
    parse_time_for_date,
    ValidationError
)
from scheduler.scheduler import compute_schedule, compute_with_capacity


class TestTimezoneValidation:
    """Tests for timezone validation."""
    
    def test_valid_timezones(self):
        """Test that valid IANA timezone names are accepted."""
        valid_tzs = [
            'America/Los_Angeles',
            'America/New_York',
            'America/Chicago',
            'Europe/London',
            'UTC',
            'US/Pacific',
        ]
        
        for tz_str in valid_tzs:
            tz = validate_timezone(tz_str)
            assert tz is not None
    
    def test_invalid_timezone(self):
        """Test that invalid timezone names raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_timezone('Invalid/Timezone')
        assert 'Invalid timezone' in str(exc_info.value)
    
    def test_default_timezone(self):
        """Test that default timezone is valid."""
        tz = validate_timezone(DEFAULT_TIMEZONE)
        assert tz is not None


class TestDateParsing:
    """Tests for date parsing."""
    
    def test_valid_date(self):
        """Test parsing valid date strings."""
        dt = parse_date('2024-03-10')
        assert dt.year == 2024
        assert dt.month == 3
        assert dt.day == 10
    
    def test_none_returns_today(self):
        """Test that None returns today's date."""
        dt = parse_date(None)
        today = datetime.now()
        assert dt.year == today.year
        assert dt.month == today.month
        assert dt.day == today.day
    
    def test_invalid_date_format(self):
        """Test that invalid date formats raise ValidationError."""
        with pytest.raises(ValidationError):
            parse_date('03/10/2024')
        with pytest.raises(ValidationError):
            parse_date('2024-13-01')  # Invalid month


class TestDSTHandling:
    """Tests for Daylight Saving Time handling."""
    
    @pytest.fixture
    def pacific_tz(self):
        return ZoneInfo('America/Los_Angeles')
    
    def test_normal_day_24_hours(self, pacific_tz):
        """Test that a normal day has 24 hours."""
        # January 15, 2024 - regular day
        date = datetime(2024, 1, 15)
        hours = enumerate_hours_for_date(date, pacific_tz)
        
        assert len(hours) == 24
        assert hours[0].hour == 0
        assert hours[-1].hour == 23
    
    def test_spring_forward_23_hours(self, pacific_tz):
        """Test DST spring forward: 2AM->3AM, 23-hour day."""
        # March 10, 2024 - DST spring forward in US
        date = datetime(2024, 3, 10)
        hours = enumerate_hours_for_date(date, pacific_tz)
        
        # Should be 23 hours (2AM skipped)
        assert len(hours) == 23
        
        # Check that 2AM is skipped
        hour_values = [h.hour for h in hours]
        assert 2 not in hour_values
        assert 1 in hour_values
        assert 3 in hour_values
    
    def test_fall_back_25_hours(self, pacific_tz):
        """Test DST fall back: 2AM->1AM repeated, 25-hour day."""
        # November 3, 2024 - DST fall back in US
        date = datetime(2024, 11, 3)
        hours = enumerate_hours_for_date(date, pacific_tz)
        
        # Should be 25 hours (1AM repeated)
        assert len(hours) == 25
        
        # Check that 1AM appears twice
        one_am_count = sum(1 for h in hours if h.hour == 1)
        assert one_am_count == 2
    
    def test_schedule_context_spring_forward(self, pacific_tz):
        """Test schedule context on spring forward day."""
        date = datetime(2024, 3, 10)
        context = create_schedule_context(date, pacific_tz)
        
        assert context.num_hours == 23
        assert context.is_dst_transition is True
        assert 'spring forward' in context.dst_info.lower()
    
    def test_schedule_context_fall_back(self, pacific_tz):
        """Test schedule context on fall back day."""
        date = datetime(2024, 11, 3)
        context = create_schedule_context(date, pacific_tz)
        
        assert context.num_hours == 25
        assert context.is_dst_transition is True
        assert 'fall back' in context.dst_info.lower()


class TestCustomerRequestWithTimezone:
    """Tests for CustomerRequest with timezone awareness."""
    
    @pytest.fixture
    def pacific_tz(self):
        return ZoneInfo('America/Los_Angeles')
    
    @pytest.fixture
    def sample_request(self):
        return CustomerRequest(
            name='Test',
            avg_call_duration_seconds=360,
            start_hour=9,
            end_hour=17,
            number_of_calls=800,
            priority=1
        )
    
    def test_active_hours_normal_day(self, sample_request, pacific_tz):
        """Test active hours calculation on a normal day."""
        date = datetime(2024, 1, 15)  # Normal day
        active = sample_request.active_hours_for_date(date, pacific_tz)
        assert active == 8  # 9AM to 5PM = 8 hours
    
    def test_active_hours_spring_forward(self, pacific_tz):
        """Test active hours on spring forward when customer spans 2AM."""
        # Customer active 1AM-4AM spans the skipped hour
        req = CustomerRequest(
            name='Night',
            avg_call_duration_seconds=360,
            start_hour=1,
            end_hour=4,
            number_of_calls=300,
            priority=1
        )
        
        date = datetime(2024, 3, 10)  # Spring forward
        active = req.active_hours_for_date(date, pacific_tz)
        
        # Should be 2 hours (1AM and 3AM, but 2AM is skipped)
        assert active == 2
    
    def test_calls_per_hour_adjusted_for_dst(self, pacific_tz):
        """Test that calls per hour adjusts for DST."""
        req = CustomerRequest(
            name='Night',
            avg_call_duration_seconds=360,
            start_hour=1,
            end_hour=4,
            number_of_calls=300,
            priority=1
        )
        
        # Normal day: 3 active hours, 100 calls/hour
        normal_date = datetime(2024, 1, 15)
        assert req.calls_per_hour_for_date(normal_date, pacific_tz) == 100
        
        # Spring forward: 2 active hours, 150 calls/hour
        dst_date = datetime(2024, 3, 10)
        assert req.calls_per_hour_for_date(dst_date, pacific_tz) == 150


class TestScheduleWithTimezone:
    """Tests for schedule computation with timezone."""
    
    @pytest.fixture
    def pacific_tz(self):
        return ZoneInfo('America/Los_Angeles')
    
    @pytest.fixture
    def sample_requests(self):
        return [
            CustomerRequest('Day', 360, 9, 17, 800, 1),  # 9AM-5PM
            CustomerRequest('Night', 360, 0, 4, 400, 2),  # Midnight-4AM
        ]
    
    def test_schedule_spring_forward(self, sample_requests, pacific_tz):
        """Test schedule on spring forward day has 23 hours."""
        date = datetime(2024, 3, 10)
        context = create_schedule_context(date, pacific_tz)
        
        schedules = compute_schedule(sample_requests, 1.0, context)
        
        assert len(schedules) == 23
        
        # Verify 2AM is not in schedule
        schedule_hours = [s.hour for s in schedules]
        assert 2 not in schedule_hours
    
    def test_schedule_fall_back(self, sample_requests, pacific_tz):
        """Test schedule on fall back day has 25 hours."""
        date = datetime(2024, 11, 3)
        context = create_schedule_context(date, pacific_tz)
        
        schedules = compute_schedule(sample_requests, 1.0, context)
        
        assert len(schedules) == 25
    
    def test_capacity_with_timezone(self, sample_requests, pacific_tz):
        """Test capacity-constrained scheduling with timezone."""
        date = datetime(2024, 3, 10)  # Spring forward
        context = create_schedule_context(date, pacific_tz)
        
        result = compute_with_capacity(sample_requests, 100, 1.0, context)
        
        assert len(result.schedules) == 23
        assert result.peak_demand > 0


class TestTimezoneConversions:
    """Tests for UTC conversions."""
    
    def test_schedule_contains_utc(self):
        """Test that timezone-aware schedules contain UTC timestamps."""
        tz = ZoneInfo('America/Los_Angeles')
        date = datetime(2024, 1, 15)
        context = create_schedule_context(date, tz)
        
        requests = [CustomerRequest('Test', 360, 9, 17, 800, 1)]
        schedules = compute_schedule(requests, 1.0, context)
        
        # All schedules should have UTC timestamps
        for schedule in schedules:
            assert schedule.datetime_utc is not None
            assert schedule.datetime_local is not None
            
            # UTC time should be different from local (PST is UTC-8)
            assert schedule.datetime_utc.tzinfo == ZoneInfo('UTC')
    
    def test_utc_offset_correct(self):
        """Test that UTC offset is correct for Pacific time."""
        tz = ZoneInfo('America/Los_Angeles')
        
        # Winter (PST = UTC-8)
        winter_date = datetime(2024, 1, 15)
        winter_hours = enumerate_hours_for_date(winter_date, tz)
        
        noon_local = [h for h in winter_hours if h.hour == 12][0]
        noon_utc = noon_local.astimezone(ZoneInfo('UTC'))
        
        # 12:00 PST = 20:00 UTC
        assert noon_utc.hour == 20
        
        # Summer (PDT = UTC-7)
        summer_date = datetime(2024, 7, 15)
        summer_hours = enumerate_hours_for_date(summer_date, tz)
        
        noon_local = [h for h in summer_hours if h.hour == 12][0]
        noon_utc = noon_local.astimezone(ZoneInfo('UTC'))
        
        # 12:00 PDT = 19:00 UTC
        assert noon_utc.hour == 19

