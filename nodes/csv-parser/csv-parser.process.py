from typing import Any
import csv
import io

async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Process function for the CSV Parser node.
    Parses a CSV string into an array of objects or arrays.
    """
    csv_string = inputs.get("csv", "")
    delimiter = settings.get("delimiter", ",")
    has_headers = settings.get("has_headers", True)
    trim_values = settings.get("trim_values", True)
    skip_empty_lines = settings.get("skip_empty_lines", True)
    
    data = []
    headers = []
    error = ""
    success = False
    
    try:
        # Create a file-like object from the string
        csv_file = io.StringIO(csv_string)
        
        # Create CSV reader
        csv_reader = csv.reader(csv_file, delimiter=delimiter)
        
        # Read all rows
        rows = list(csv_reader)
        
        # Skip empty lines if configured
        if skip_empty_lines:
            rows = [row for row in rows if any(cell.strip() for cell in row)]
        
        if not rows:
            return {
                "data": [],
                "headers": [],
                "error": "",
                "success": True
            }
        
        # Parse headers if configured
        if has_headers and rows:
            headers = [h.strip() if trim_values else h for h in rows[0]]
            rows = rows[1:]
        
        # Parse data rows
        if has_headers:
            # Parse as objects with header keys
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers):
                        row_dict[headers[i]] = value.strip() if trim_values else value
                data.append(row_dict)
        else:
            # Parse as arrays of values
            data = [[cell.strip() if trim_values else cell for cell in row] for row in rows]
        
        success = True
    except Exception as e:
        error = str(e)
        data = []
        headers = []
    
    return {
        "data": data,
        "headers": headers,
        "error": error,
        "success": success
    } 