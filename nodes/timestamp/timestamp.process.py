from datetime import datetime
from typing import Any


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        format_type = inputs.get('format', 'iso')
        
        now = datetime.now()
        unix_timestamp = int(now.timestamp())
        unix_timestamp_ms = int(now.timestamp() * 1000)
        # Format ISO string to match JavaScript's toISOString() format: YYYY-MM-DDTHH:MM:SS.sssZ
        iso_string = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'
        
        # Check for preset format keywords first
        if format_type == 'iso':
            timestamp = iso_string
        elif format_type == 'unix':
            timestamp = str(unix_timestamp)
        elif format_type == 'unix_ms':
            timestamp = str(unix_timestamp_ms)
        elif format_type == 'rfc2822':
            timestamp = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        else:
            # If not a preset keyword, treat as custom format string
            timestamp = format_custom_timestamp(now, format_type)
        
        return {
            'timestamp': timestamp,
            'unix_timestamp': unix_timestamp,
            'unix_timestamp_ms': unix_timestamp_ms,
            'iso_string': iso_string
        }
        
    except Exception as error:
        raise Exception(f"Timestamp error: {str(error)}")

def format_custom_timestamp(date, format_str):
    """Helper function for custom format formatting"""
    year = date.year
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"
    hours = f"{date.hour:02d}"
    minutes = f"{date.minute:02d}"
    seconds = f"{date.second:02d}"
    milliseconds = f"{date.microsecond // 1000:03d}"
    
    return (format_str
            .replace('YYYY', str(year))
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes)
            .replace('ss', seconds)
            .replace('SSS', milliseconds)
            .replace('YY', str(year)[-2:])
            .replace('M', str(date.month))
            .replace('D', str(date.day))
            .replace('H', str(date.hour))
            .replace('m', str(date.minute))
            .replace('s', str(date.second)))
