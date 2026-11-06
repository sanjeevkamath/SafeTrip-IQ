"""Check the public data-health endpoint without database credentials."""
import json
from pathlib import Path
import urllib.error
import urllib.request

URL = 'https://safetripiq.vercel.app/api/health'


def valid_health(value):
    return (value.get('healthy') is True and value.get('refresh_threshold_hours') == 216
            and all(value.get('sources', {}).get(s, {}).get('fresh') is True for s in ['us_state', 'uk_fcdo'])
            and value.get('publication', {}).get('fresh') is True)


def main():
    # The public endpoint returns only dates/counts, no application rows or credentials.
    try:
        with urllib.request.urlopen(URL, timeout=30) as response:
            value = json.load(response)
            healthy = response.status == 200 and valid_health(value)
    except Exception:
        value, healthy = {'healthy': False, 'error': 'Public health request failed or returned an unhealthy status.'}, False
    output = Path('.local/monitor/health.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + '\n')
    print('Production advice and score freshness:', 'healthy' if healthy else 'requires attention')
    return 0 if healthy else 1


if __name__ == '__main__':
    raise SystemExit(main())
