"""Claude Code / Antigravity statusLine command: forwards usage limits to AI Watch and prints a short status."""
import http.client
import json
import sys

try:
    from bridge import limits
except ImportError:  # executed as a script
    import limits

if __name__ == "__main__":
    text = ""
    try:
        payload = limits.report_status(json.loads(sys.stdin.buffer.read(1024 * 1024)))
        if payload:
            text = f"5h {payload['five_hour']['used_pct']:.0f}% | 7d {payload['weekly']['used_pct']:.0f}%"
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, http.client.HTTPException):
        pass
    print(text)
