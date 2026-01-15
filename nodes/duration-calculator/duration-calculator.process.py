"""
Duration Calculator Node - Calculate duration between two timestamps.
"""

from datetime import datetime
from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Duration Calculator node.
    """
    try:
        start_time = inputs.get("start_time")
        end_time = inputs.get("end_time") or datetime.now().isoformat() + "Z"
        output_unit = inputs.get("output_unit", "seconds")

        # Parse timestamps
        start_date = parse_timestamp(start_time)
        end_date = parse_timestamp(end_time)

        if not start_date or not end_date:
            raise Exception("Invalid timestamp format. Use ISO strings, Unix timestamps, or parseable date formats")

        # Calculate duration in seconds
        duration_seconds = (end_date - start_date).total_seconds()
        duration_minutes = duration_seconds / 60
        duration_hours = duration_minutes / 60
        duration_days = duration_hours / 24

        # Get duration in requested unit
        if output_unit == "seconds":
            duration = round(duration_seconds, 2)
        elif output_unit == "minutes":
            duration = round(duration_minutes, 2)
        elif output_unit == "hours":
            duration = round(duration_hours, 2)
        elif output_unit == "days":
            duration = round(duration_days, 2)
        else:
            duration = round(duration_seconds, 2)

        # Generate human readable format
        human_readable = format_human_readable(duration_seconds)

        return {
            "duration": duration,
            "duration_seconds": round(duration_seconds, 2),
            "duration_minutes": round(duration_minutes, 2),
            "duration_hours": round(duration_hours, 2),
            "duration_days": round(duration_days, 2),
            "human_readable": human_readable,
        }

    except Exception as error:
        raise Exception(f"Duration Calculator error: {str(error)}")


def parse_timestamp(timestamp):
    """Helper function to parse various timestamp formats."""
    if not timestamp:
        return None

    try:
        # Try parsing as Unix timestamp (number)
        if isinstance(timestamp, (int, float)):
            num = float(timestamp)
            # If it's a large number, assume it's milliseconds
            if num > 1000000000000:
                return datetime.fromtimestamp(num / 1000)
            else:
                return datetime.fromtimestamp(num)

        if isinstance(timestamp, str):
            # Check if it's a numeric string
            try:
                num = float(timestamp)
                if num > 1000000000000:
                    return datetime.fromtimestamp(num / 1000)
                else:
                    return datetime.fromtimestamp(num)
            except ValueError:
                pass

            # Try parsing as ISO string
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except Exception:
        pass

    return None


def format_human_readable(duration_seconds: float) -> str:
    """Helper function to format duration in human readable format."""
    is_negative = duration_seconds < 0
    seconds = abs(int(duration_seconds))
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24

    remaining_hours = hours % 24
    remaining_minutes = minutes % 60
    remaining_seconds = seconds % 60

    parts = []

    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if remaining_hours > 0:
        parts.append(f"{remaining_hours} hour{'s' if remaining_hours != 1 else ''}")
    if remaining_minutes > 0:
        parts.append(f"{remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}")
    if remaining_seconds > 0 or not parts:
        parts.append(f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}")

    result = " ".join(parts)
    return f"-{result}" if is_negative else result
