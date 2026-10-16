"""Guards for this narrowly scoped Microsoft update byte-range downloader."""
from urllib.parse import urlsplit, urlunsplit
from pathlib import PureWindowsPath, PurePosixPath

def microsoft_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    allowed = ('delivery.mp.microsoft.com', 'download.windowsupdate.com', 'download.microsoft.com')
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        raise ValueError('Unexpected download URL form')
    if not any(host == domain or host.endswith('.' + domain) for domain in allowed):
        raise ValueError('Payload host is outside the Microsoft download allowlist')
    # Keep the protocol issued by the update metadata; some delivery hosts do
    # not expose a matching HTTPS endpoint. Never disable TLS verification.
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))

def safe_filename(name):
    if (not name or name in ('.', '..') or ':' in name or '\\' in name or '/' in name
        or PureWindowsPath(name).name != name or PurePosixPath(name).name != name):
        raise ValueError('Unexpected payload filename')
    return name
