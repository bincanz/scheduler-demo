# Agent Scheduler - Design Document

## Overview

A CLI tool that calculates hour-by-hour AI agent staffing needs from customer call requirements, with optional capacity constraints and priority-aware allocation.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                            │
│  - Argument parsing & validation                                │
│  - Orchestrates pipeline                                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Parser      │  │  Scheduler   │  │  Formatter   │
│  (parser.py) │  │(scheduler.py)│  │(formatter.py)│
│              │  │              │  │              │
│ - CSV read   │  │ - Core algo  │  │ - Text       │
│ - Validation │  │ - Capacity   │  │ - JSON       │
│ - Time parse │  │   planning   │  │ - CSV        │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └────────────────►▼◄────────────────┘
                  ┌─────────────┐
                  │   Models    │
                  │ (models.py) │
                  │             │
                  │ - Customer  │
                  │   Request   │
                  │ - Hourly    │
                  │   Schedule  │
                  └─────────────┘
```

### Data Flow

1. **Input**: CSV file → Parser validates and creates `CustomerRequest` objects
2. **Processing**: Scheduler computes `HourlySchedule` for each hour (0-23)
3. **Output**: Formatter converts schedules to requested format (text/json/csv)

---

## Core Algorithms

### 1. Basic Agent Calculation

```
agents_per_hour = ceil(calls_per_hour × avg_duration_seconds / 3600 / utilization)
```

Where:
- `calls_per_hour = total_calls / active_hours`
- `utilization` defaults to 1.0 (100% agent efficiency)

**Example**: 20,000 calls over 10 hours, 300s avg duration
- calls_per_hour = 2,000
- agents = ceil(2000 × 300 / 3600) = ceil(166.67) = 167

### 2. Priority-Aware Capacity Allocation

When `--capacity` is specified, we must allocate limited agents across customers.

**Algorithm: Priority-First Greedy**

```python
for each hour:
    remaining_capacity = total_capacity
    for customer in sorted_by_priority:  # 1 = highest
        demand = customer.agents_needed_per_hour
        allocated = min(demand, remaining_capacity)
        remaining_capacity -= allocated
```

**Trade-offs considered:**

| Approach | Pros | Cons |
|----------|------|------|
| **Priority-First (chosen)** | Guarantees high-priority service | May starve low-priority entirely |
| Proportional | Fair to all customers | High-priority may be under-served |
| Time-Shifting | Maximizes utilization | Violates customer time windows |
| Weighted Proportional | Balances fairness & priority | Complex to tune weights |

**Rationale**: Priority-First was chosen because:
1. Simple to understand and explain
2. Aligns with business priorities (highest priority = most important)
3. Produces deterministic, predictable results
4. Easy to audit and debug

### 3. Utilization Factor

The `--utilization` parameter allows conservative sizing:

- `1.0` = 100% utilization (minimum agents)
- `0.8` = 80% utilization (20% buffer for breaks, variability)
- Formula: `agents = ceil(base_agents / utilization)`

---

## Key Trade-offs

### Uniform Distribution Assumption
- **Assumption**: Calls distributed evenly across active hours
- **Reality**: Call volumes typically have peaks (post-lunch, etc.)
- **Future**: Support hourly distribution profiles per customer

### Ceiling vs. Floor for Agent Count
- **Choice**: `ceil()` ensures capacity to handle all calls
- **Trade-off**: May slightly over-staff
- **Alternative**: `round()` for average-case, `ceil()` for worst-case

### Time Granularity
- **Choice**: 1-hour buckets for simplicity
- **Trade-off**: Less precision, but easier to staff and manage
- **Alternative**: 15-min or 30-min buckets for higher accuracy

---

## Observability & Testing

### Logging Strategy
- **Verbose mode** (`-v`): Prints diagnostic info to stderr
- **Structured output**: JSON format enables easy parsing/monitoring
- **Error handling**: Clear error messages with row numbers for CSV issues

### Testing Approach

| Test Type | Purpose | Location |
|-----------|---------|----------|
| Unit Tests | Individual functions | `tests/test_*.py` |
| Integration | End-to-end pipeline | `tests/test_integration.py` |
| Property Tests | Edge cases via fuzzing | Future enhancement |

**Coverage targets**: 
- Parser: 100% (critical for input validation)
- Scheduler: 90%+ (core business logic)
- Formatter: 80%+ (output correctness)

### Key Test Cases
1. Expected output matches problem statement
2. Time parsing edge cases (12AM, 12PM)
3. Capacity constraints respected
4. Priority ordering correct
5. Empty/malformed CSV handling

---

## Future Enhancements

### Short-term (v1.x)
- [ ] Support for CSV with hourly distribution weights
- [ ] Multiple capacity pools (e.g., by skill/language)
- [ ] Real-time schedule updates via API

### Medium-term (v2.x)
- [ ] Historical data integration for demand forecasting
- [ ] Multi-day scheduling with carryover
- [ ] Agent skill-based routing constraints

### Long-term (v3.x)
- [ ] ML-based demand prediction
- [ ] Integration with workforce management systems
- [ ] Real-time adjustment based on actual call volumes

---

## Running the Tool

```bash
# Basic usage
make run INPUT=./input.csv

# With utilization factor
make run INPUT=./input.csv UTILIZATION=0.8

# With capacity constraint
make run INPUT=./input.csv CAPACITY=500

# JSON output
make run INPUT=./input.csv FORMAT=json

# Run tests
make test

# Start web UI
make ui
```

---

## Example: 500 Agent Capacity Analysis

Given the sample data with a 500-agent constraint:

**Unconstrained Peak**: 2,059 agents (hour 11)
**Constrained Peak**: 500 agents (capacity limit)

**Allocation by Priority**:
1. Stanford Hospital (P1): Full service - 167 agents
2. VNS (P1): Full service - 193 agents
3. CVS (P3): Partial - limited during peak hours
4. NMDX (P3): Partial - limited during peak hours
5. SJC (P4): Reduced allocation
6. ANMC (P5): Severely limited (lowest priority)

**Unmet Demand**: ~60-70% of ANMC calls would be unmet at this capacity.

This demonstrates the priority-based trade-off: ensuring critical customers are fully served while clearly communicating capacity limitations for lower-priority work.

