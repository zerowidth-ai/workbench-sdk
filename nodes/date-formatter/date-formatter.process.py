"""
Date Formatter Node - Formats a date or timestamp into a string.
"""

from typing import Any
from datetime import datetime, timezone

try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the Date Formatter node.
    Formats a date or timestamp into a string using various formats.
    """
    date_input = inputs.get("date")
    format_str = settings.get("format", "YYYY-MM-DD")
    tz_name = settings.get("timezone", "UTC")

    formatted = ""
    timestamp = 0
    iso = ""
    error = ""
    success = False

    try:
        # Parse the input date
        date_obj = None

        if isinstance(date_input, (int, float)):
            # Timestamp in seconds or milliseconds
            if date_input > 1e10:  # Assume milliseconds if very large
                date_obj = datetime.fromtimestamp(date_input / 1000, timezone.utc)
            else:
                date_obj = datetime.fromtimestamp(date_input, timezone.utc)
        elif isinstance(date_input, str):
            # Try to parse string date
            try:
                date_obj = datetime.fromisoformat(date_input.replace("Z", "+00:00"))
            except ValueError:
                # Try other common formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        date_obj = datetime.strptime(date_input, fmt)
                        date_obj = date_obj.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue

                if date_obj is None:
                    raise ValueError("Invalid date")
        else:
            # Default to current time
            date_obj = datetime.now(timezone.utc)

        # Apply timezone if specified
        if tz_name.lower() != "utc" and HAS_PYTZ:
            try:
                tz = pytz.timezone(tz_name)
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
                date_obj = date_obj.astimezone(tz)
            except Exception:
                # If timezone adjustment fails, use the original date
                pass

        # Get timestamp and ISO string
        timestamp = int(date_obj.timestamp() * 1000)  # milliseconds
        iso = date_obj.isoformat()

        # Format the date according to the specified format
        formatted = format_date(date_obj, format_str)

        success = True
    except Exception as e:
        error = str(e) or "Failed to format date"
        formatted = ""
        timestamp = 0
        iso = ""
        success = False

    return {
        "formatted": formatted,
        "timestamp": timestamp,
        "iso": iso,
        "error": error,
        "success": success,
    }


def format_date(date_obj: datetime, format_str: str) -> str:
    """Format a date according to a format string."""
    result = format_str
    result = result.replace("YYYY", f"{date_obj.year:04d}")
    result = result.replace("MM", f"{date_obj.month:02d}")
    result = result.replace("DD", f"{date_obj.day:02d}")
    result = result.replace("HH", f"{date_obj.hour:02d}")
    result = result.replace("mm", f"{date_obj.minute:02d}")
    result = result.replace("ss", f"{date_obj.second:02d}")
    result = result.replace("SSS", f"{date_obj.microsecond // 1000:03d}")
    return result
