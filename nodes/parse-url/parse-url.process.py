from typing import Any
from urllib.parse import urlparse, parse_qs


async def process(
    *,
    inputs: dict[str, Any],
    settings: dict[str, Any],
    config: dict[str, Any],
    node_config: dict[str, Any],
) -> dict[str, Any]:
    url_string = inputs.get("url")

    empty_result = {
        "protocol": "",
        "host": "",
        "hostname": "",
        "port": "",
        "pathname": "",
        "search": "",
        "query": {},
        "hash": "",
        "origin": "",
    }

    if not isinstance(url_string, str) or url_string == "":
        return empty_result

    try:
        parsed = urlparse(url_string)

        # Build protocol with colon to match JS URL behavior
        protocol = f"{parsed.scheme}:" if parsed.scheme else ""

        # Extract port
        port = str(parsed.port) if parsed.port else ""

        # Build host (hostname:port or just hostname)
        hostname = parsed.hostname or ""
        host = f"{hostname}:{port}" if port else hostname

        # Build origin
        origin = f"{protocol}//{host}" if protocol and host else ""

        # Parse query parameters
        query_dict = parse_qs(parsed.query, keep_blank_values=True)
        # Flatten single-value lists
        query = {}
        for key, values in query_dict.items():
            if len(values) == 1:
                query[key] = values[0]
            else:
                query[key] = values

        # Build search string with leading ?
        search = f"?{parsed.query}" if parsed.query else ""

        # Build hash with leading #
        hash_value = f"#{parsed.fragment}" if parsed.fragment else ""

        # Normalize pathname - add leading slash for root if missing
        pathname = parsed.path or ""
        if not pathname and host:
            pathname = "/"

        return {
            "protocol": protocol,
            "host": host,
            "hostname": hostname,
            "port": port,
            "pathname": pathname,
            "search": search,
            "query": query,
            "hash": hash_value,
            "origin": origin,
        }
    except Exception:
        return empty_result
