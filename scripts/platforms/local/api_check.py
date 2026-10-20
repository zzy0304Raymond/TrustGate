"""Read-only OpenRouter key check; never creates a generation or trial directory."""
import json
import urllib.error
import urllib.request
from runtime import ROOT


def probe(key, opener=None):
    if not key.strip():
        raise ValueError('Empty API credential')
    request = urllib.request.Request('https://openrouter.ai/api/v1/key',
                                     headers={'Authorization': 'Bearer ' + key})
    try:
        with (opener or urllib.request.urlopen)(request, timeout=30) as response:
            data = json.load(response)['data']
    except urllib.error.HTTPError as exc:
        raise RuntimeError('OpenRouter key check failed: HTTP %s. No trial was created.' % exc.code) from None
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError('OpenRouter key metadata unavailable. No trial was created.') from None
    if not isinstance(data, dict) or 'limit_remaining' not in data:
        raise RuntimeError('Missing key limit metadata; not ready to start formal trials.')
    remaining = data['limit_remaining']
    if remaining is not None and (isinstance(remaining, bool) or not isinstance(remaining, (int, float)) or remaining <= 0):
        raise RuntimeError('Key spending cap is exhausted or invalid. No trial was created.')
    return dict(key_authenticated=True, key_cap_covers_two_dollars=remaining is None or remaining >= 2,
                model_generation_requests=0,
                note='Key cap is not the account balance; provider availability and paid inference remain untested.')


def main():
    from trustgate.runner import get_key
    print(json.dumps(probe(get_key()), indent=2))


if __name__ == '__main__':
    main()
