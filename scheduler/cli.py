"""
Command-line interface for the agent scheduler.
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from .models import DEFAULT_TIMEZONE, create_schedule_context
from .parser import parse_csv, parse_date, validate_timezone, ValidationError
from .scheduler import compute_schedule, compute_with_capacity
from .formatter import format_output


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog='scheduler',
        description='Calculate hour-by-hour AI agent staffing needs from customer call requirements.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input calls.csv
  %(prog)s --input calls.csv --utilization 0.8
  %(prog)s --input calls.csv --capacity 500 --format json
  %(prog)s --input calls.csv --timezone America/New_York
  %(prog)s --input calls.csv --date 2024-03-10 --timezone America/Los_Angeles

Timezone Examples:
  America/Los_Angeles  (Pacific Time)
  America/New_York     (Eastern Time)
  America/Chicago      (Central Time)
  America/Denver       (Mountain Time)
  Europe/London        (GMT/BST)
  UTC                  (Coordinated Universal Time)

DST Transition Dates (for testing):
  2024-03-10  Spring forward (23-hour day in US)
  2024-11-03  Fall back (25-hour day in US)
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        metavar='PATH',
        help='Path to input CSV file with customer call requirements'
    )
    
    parser.add_argument(
        '--utilization', '-u',
        type=float,
        default=1.0,
        metavar='FLOAT',
        help='Agent utilization factor (0.0-1.0). Lower values size more conservatively. Default: 1.0'
    )
    
    parser.add_argument(
        '--capacity', '-c',
        type=int,
        default=None,
        metavar='INT',
        help='Maximum number of agents available. Enables priority-aware allocation.'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['text', 'json', 'csv'],
        default='text',
        help='Output format. Default: text'
    )
    
    parser.add_argument(
        '--timezone', '-tz',
        default=DEFAULT_TIMEZONE,
        metavar='TZ',
        help=f'Timezone for scheduling (IANA format). Default: {DEFAULT_TIMEZONE}'
    )
    
    parser.add_argument(
        '--date', '-d',
        default=None,
        metavar='YYYY-MM-DD',
        help='Date to schedule for (YYYY-MM-DD). Default: today. '
             'Use specific dates to test DST transitions.'
    )
    
    parser.add_argument(
        '--show-utc',
        action='store_true',
        help='Include UTC timestamps in output (JSON format only)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show additional diagnostic information'
    )
    
    return parser


def validate_args(args: argparse.Namespace) -> List[str]:
    """Validate CLI arguments. Returns list of error messages."""
    errors = []
    
    if args.utilization <= 0 or args.utilization > 1:
        errors.append(f"Utilization must be between 0 (exclusive) and 1 (inclusive), got: {args.utilization}")
    
    if args.capacity is not None and args.capacity <= 0:
        errors.append(f"Capacity must be positive, got: {args.capacity}")
    
    return errors


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the CLI.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Validate arguments
    arg_errors = validate_args(args)
    if arg_errors:
        for error in arg_errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1
    
    try:
        # Validate timezone
        tz = validate_timezone(args.timezone)
        
        # Parse date
        schedule_date = parse_date(args.date)
        
        # Create schedule context
        context = create_schedule_context(schedule_date, tz)
        
        if args.verbose:
            print(f"Timezone: {args.timezone}", file=sys.stderr)
            print(f"Date: {schedule_date.strftime('%Y-%m-%d')}", file=sys.stderr)
            print(f"Hours in day: {context.num_hours}", file=sys.stderr)
            if context.is_dst_transition:
                print(f"DST Note: {context.dst_info}", file=sys.stderr)
        
        # Parse input CSV
        if args.verbose:
            print(f"Reading input from: {args.input}", file=sys.stderr)
        
        requests, warnings = parse_csv(args.input)
        
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        
        if args.verbose:
            print(f"Loaded {len(requests)} customer requests", file=sys.stderr)
            for req in requests:
                print(f"  - {req.name}: {req.number_of_calls:,} calls, "
                      f"{req.start_hour:02d}:00-{req.end_hour:02d}:00, "
                      f"priority {req.priority}", file=sys.stderr)
        
        # Compute schedule
        capacity_info = None
        
        if args.capacity is not None:
            # Capacity-constrained allocation
            if args.verbose:
                print(f"Computing capacity-constrained schedule (capacity={args.capacity}, "
                      f"utilization={args.utilization})", file=sys.stderr)
            
            capacity_info = compute_with_capacity(
                requests, 
                args.capacity, 
                args.utilization,
                context
            )
            schedules = capacity_info.schedules
        else:
            # Unconstrained allocation
            if args.verbose:
                print(f"Computing unconstrained schedule (utilization={args.utilization})", 
                      file=sys.stderr)
            
            schedules = compute_schedule(requests, args.utilization, context)
        
        # Format and print output
        output = format_output(
            schedules, 
            args.format, 
            capacity_info, 
            context=context,
            show_utc=args.show_utc
        )
        print(output)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValidationError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
