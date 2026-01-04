# 📞 Agent Scheduler

A CLI tool for calculating hour-by-hour AI agent staffing needs from customer call requirements. Supports priority-aware capacity allocation and multiple output formats.

## ✨ Features

- **CSV Input**: Parse customer call requirements with validation
- **24-Hour Schedule**: Output agent needs for each hour (00:00-23:00 PT)
- **Utilization Factor**: Conservative sizing with configurable utilization
- **Capacity Constraints**: Priority-aware allocation when agents are limited
- **Multiple Formats**: Text, JSON, and CSV output
- **Web UI**: Interactive visualization with hover details

## 🚀 Quick Start

```bash
# Install dependencies
make install

# Run with sample data
make run INPUT=./input.csv

# Run demo (shows multiple scenarios)
make demo
```

## 📋 Input Format

CSV file with the following columns:

| Column                     | Type    | Description                                     |
|----------------------------|---------|-------------------------------------------------|
| CustomerName               | string  | Customer identifier                             |
| AverageCallDurationSeconds | int     | Average call duration in seconds                |
| StartTimePT                | string  | Start time in PT (e.g., "9AM", "7PM")           |
| EndTimePT                  | string  | End time in PT (exclusive)                      |
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
# Basic usage
python run.py --input ./input.csv

# With utilization factor (80% = 20% buffer)
python run.py --input ./input.csv --utilization 0.8

# With capacity constraint (priority-aware allocation)
python run.py --input ./input.csv --capacity 500

# JSON output
python run.py --input ./input.csv --format json

# CSV output
python run.py --input ./input.csv --format csv

# Verbose mode (show diagnostic info)
python run.py --input ./input.csv --verbose
```

### CLI Options

| Option              | Default     | Description                                 |
|---------------------|-------------|---------------------------------------------|
| `--input`, `-i`     | (required)  | Path to input CSV file                      |
| `--utilization`, `-u` | 1.0       | Agent utilization factor (0.0-1.0)          |
| `--capacity`, `-c`  | unlimited   | Maximum agent capacity                      |
| `--format`, `-f`    | text        | Output format: text, json, csv              |
| `--verbose`, `-v`   | false       | Show diagnostic information                 |

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

### Priority-Aware Capacity Allocation

When capacity is constrained, customers are served in priority order (1 = highest):

1. Sort customers by priority
2. For each hour, allocate to highest priority first
3. Continue until capacity exhausted
4. Track unmet demand for reporting

## 🧪 Testing

```bash
# Run all tests
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
│   ├── models.py       # Data models
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
│   └── test_integration.py
├── run.py              # CLI entry script
├── input.csv           # Sample data
├── Makefile            # Build commands
├── requirements.txt    # Dependencies
├── DESIGN.md           # Design document
└── README.md           # This file
```

## 📄 License

MIT
