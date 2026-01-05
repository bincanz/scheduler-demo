# 📞 Agent Scheduler

A CLI tool for calculating hour-by-hour AI agent staffing needs from customer call requirements. Supports timezone-aware scheduling with DST handling, priority-aware capacity allocation, and multiple output formats.

## ✨ Features

- **CSV Input**: Parse customer call requirements with validation
- **Timezone Support**: Full timezone handling with IANA timezone names (via `zoneinfo`)
- **DST Handling**: Properly handles 23-hour (spring forward) and 25-hour (fall back) days
- **UTC Conversion**: Stores times as UTC internally, converts to local for display
- **Utilization Factor**: Conservative sizing with configurable utilization
- **Capacity Constraints**: Priority-aware allocation when agents are limited
- **Multiple Formats**: Text, JSON, and CSV output
- **Web UI**: Interactive visualization with hover details

## 🚀 Quick Start

```bash
# Create virtual environment
python3 -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with sample data
python run.py --input ./input.csv

# Run demo (shows multiple scenarios)
make demo
```

## 📋 Input Format

CSV file with the following columns:

| Column                     | Type    | Description                                     |
|----------------------------|---------|-------------------------------------------------|
| CustomerName               | string  | Customer identifier                             |
| AverageCallDurationSeconds | int     | Average call duration in seconds                |
| StartTimePT                | string  | Start time in local time (e.g., "9AM", "7PM")   |
| EndTimePT                  | string  | End time in local time (exclusive)              |
| NumberOfCalls              | int     | Total calls to be made                          |
| Priority                   | int     | 1-5, where 1 is highest priority                |

Example:
```csv
CustomerName,AverageCallDurationSeconds,StartTimePT,EndTimePT,NumberOfCalls,Priority
Stanford Hospital,300,9AM,7PM,20000,1
VNS,120,6AM,1PM,40500,1
CVS,180,11AM,3PM,50000,3
```

## 🔧 CLI Usage

```bash
# Basic usage (defaults to America/Los_Angeles timezone)
python run.py --input ./input.csv

# With specific timezone
python run.py --input ./input.csv --timezone America/New_York

# With specific date (for DST testing)
python run.py --input ./input.csv --date 2024-03-10  # Spring forward

# With utilization factor (80% = 20% buffer)
python run.py --input ./input.csv --utilization 0.8

# With capacity constraint (priority-aware allocation)
python run.py --input ./input.csv --capacity 500

# JSON output with UTC timestamps
python run.py --input ./input.csv --format json --show-utc

# Verbose mode (show diagnostic info)
python run.py --input ./input.csv --verbose
```

### CLI Options

| Option                | Default                | Description                                    |
|-----------------------|------------------------|------------------------------------------------|
| `--input`, `-i`       | (required)             | Path to input CSV file                         |
| `--timezone`, `-tz`   | America/Los_Angeles    | IANA timezone name                             |
| `--date`, `-d`        | today                  | Date to schedule (YYYY-MM-DD)                  |
| `--utilization`, `-u` | 1.0                    | Agent utilization factor (0.0-1.0)             |
| `--capacity`, `-c`    | unlimited              | Maximum agent capacity                         |
| `--format`, `-f`      | text                   | Output format: text, json, csv                 |
| `--show-utc`          | false                  | Include UTC timestamps in output               |
| `--verbose`, `-v`     | false                  | Show diagnostic information                    |

### Supported Timezones

Use any valid IANA timezone name:
- `America/Los_Angeles` (Pacific Time)
- `America/New_York` (Eastern Time)
- `America/Chicago` (Central Time)
- `America/Denver` (Mountain Time)
- `Europe/London` (GMT/BST)
- `UTC` (Coordinated Universal Time)

## 🕐 Timezone & DST Handling

The scheduler properly handles Daylight Saving Time transitions:

### Spring Forward (23-hour day)
On spring forward days (e.g., 2024-03-10 in US), 2AM is skipped:
```
01:00 : total=0 ; none
03:00 : total=0 ; none  # 2AM skipped
04:00 : total=0 ; none
```

### Fall Back (25-hour day)
On fall back days (e.g., 2024-11-03 in US), 1AM occurs twice:
```
01:00 : total=0 ; none  # First 1AM (DST)
01:00 : total=0 ; none  # Second 1AM (Standard)
02:00 : total=0 ; none
```

### JSON with UTC
Use `--show-utc` to include UTC timestamps for unambiguous time identification:
```json
{
  "hour": "01:00",
  "datetime_utc": "2024-03-10T09:00:00+00:00",
  "datetime_local": "2024-03-10T01:00:00-08:00",
  "timezone": "America/Los_Angeles"
}
```

## 📊 Output Format

### Text (default)

```
00:00 : total=0 ; none
01:00 : total=0 ; none
...
06:00 : total=193 ; VNS=193
07:00 : total=877 ; VNS=193, ANMC=684
...
```

### JSON

```json
{
  "schedules": [
    {"hour": "06:00", "total_agents": 193, "customers": {"VNS": 193}},
    ...
  ],
  "timezone_info": {
    "timezone": "America/Los_Angeles",
    "date": "2024-01-15",
    "hours_in_day": 24,
    "is_dst_transition": false
  },
  "summary": {"peak_total_agents": 2059, "active_hours": 14}
}
```

## 🌐 Web UI

Start the interactive web interface:

```bash
make ui        # Production mode (port 5000)
make ui-dev    # Development mode with hot reload
```

Open http://localhost:5000 in your browser.

Features:
- 24-cell grid showing hourly totals
- Color-coded intensity bars
- Hover for customer breakdown
- Configurable utilization and capacity
- Unmet demand visualization

## 🧮 Algorithm

### Agent Calculation

```
agents_per_hour = ceil(calls_per_hour × avg_duration_seconds / 3600 / utilization)
```

Where `calls_per_hour = total_calls / active_hours` (uniform distribution).

For DST days, `active_hours` is computed based on actual hours in the timezone, accounting for skipped or repeated hours.

### Priority-Aware Capacity Allocation

When capacity is constrained, customers are served in priority order (1 = highest):

1. Sort customers by priority
2. For each hour, allocate to highest priority first
3. Continue until capacity exhausted
4. Track unmet demand for reporting

## 🧪 Testing

```bash
# Run all tests (50 tests including timezone/DST tests)
make test

# Run with coverage
make test-cov
```

## 📁 Project Structure

```
scheduler-demo/
├── scheduler/
│   ├── __init__.py
│   ├── cli.py          # CLI entry point
│   ├── models.py       # Data models (with timezone support)
│   ├── parser.py       # CSV parsing & validation
│   ├── scheduler.py    # Core scheduling algorithms
│   └── formatter.py    # Output formatters
├── ui/
│   ├── app.py          # Flask web app
│   └── templates/
│       └── index.html  # Web UI
├── tests/
│   ├── test_parser.py
│   ├── test_scheduler.py
│   ├── test_formatter.py
│   ├── test_integration.py
│   └── test_timezone.py  # Timezone & DST tests
├── run.py              # CLI entry script
├── input.csv           # Sample data
├── Makefile            # Build commands
├── requirements.txt    # Dependencies
└── README.md           # This file
```

## 📄 License

MIT
