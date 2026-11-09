"""URL features computed from the link text alone.

They follow the encoding of the UCI phishing dataset (datasets/dataseturl.csv):
1 = looks legitimate, 0 = suspicious, -1 = looks like phishing. The dataset has 30
features; the ones below are the ones that can be measured from the URL itself,
without WHOIS, DNS or downloading the page, so the model trained on them can be
used on any link a user pastes.
"""

import ipaddress
import re
from urllib.parse import urlparse

FEATURES = [
    "having_IPhaving_IP_Address",
    "URLURL_Length",
    "Shortining_Service",
    "having_At_Symbol",
    "double_slash_redirecting",
    "Prefix_Suffix",
    "having_Sub_Domain",
    "SSLfinal_State",
    "port",
    "HTTPS_token",
]

SHORTENERS = re.compile(
    r"(bit\.ly|goo\.gl|tinyurl|t\.co|ow\.ly|is\.gd|buff\.ly|adf\.ly|bitly\.com|cutt\.ly|"
    r"shorturl\.at|rebrand\.ly|tiny\.cc|lnkd\.in|db\.tt|qr\.ae|cur\.lv|ity\.im|q\.gs|po\.st|"
    r"bc\.vc|u\.to|j\.mp|v\.gd|x\.co|tr\.im|soo\.gd|s2r\.co|clicky\.me|budurl\.com|bit\.do)",
    re.I,
)


def _host(url: str) -> tuple[str, int | None, str]:
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        port = -1
    return (parsed.hostname or "").lower(), port, parsed.scheme.lower()


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(re.fullmatch(r"0x[0-9a-f]+(\.0x[0-9a-f]+)*", host))


def extract(url: str) -> dict[str, int]:
    url = url.strip()
    host, port, scheme = _host(url)
    bare = host[4:] if host.startswith("www.") else host
    dots = bare.count(".")
    last_double_slash = url.rfind("//")
    return {
        "having_IPhaving_IP_Address": -1 if _is_ip(host) else 1,
        "URLURL_Length": 1 if len(url) < 54 else (0 if len(url) <= 75 else -1),
        "Shortining_Service": -1 if SHORTENERS.search(host) else 1,
        "having_At_Symbol": -1 if "@" in url else 1,
        "double_slash_redirecting": -1 if last_double_slash > 7 else 1,
        "Prefix_Suffix": -1 if "-" in host else 1,
        "having_Sub_Domain": 1 if _is_ip(host) or dots <= 1 else (0 if dots == 2 else -1),
        "SSLfinal_State": 1 if scheme == "https" else -1,
        "port": -1 if port not in (None, 80, 443) else 1,
        "HTTPS_token": -1 if "https" in host else 1,
    }


# Signs that are a strong warning on their own, whatever the model says
HIGH_RISK = {"having_IPhaving_IP_Address", "Shortining_Service", "having_At_Symbol", "double_slash_redirecting", "HTTPS_token", "port"}


def explain(features: dict[str, int]) -> list[str]:
    """Plain-English reasons for the warning signs found in a URL."""
    reasons = {
        "having_IPhaving_IP_Address": "uses a raw IP address instead of a domain name",
        "URLURL_Length": "is unusually long",
        "Shortining_Service": "hides the real destination behind a link shortener",
        "having_At_Symbol": "contains '@', which makes browsers ignore everything before it",
        "double_slash_redirecting": "contains '//' later in the path (a redirect trick)",
        "Prefix_Suffix": "has a hyphen in the domain (common in look-alike domains)",
        "having_Sub_Domain": "stacks several subdomains in front of the real domain",
        "SSLfinal_State": "does not use HTTPS",
        "port": "uses a non-standard port",
        "HTTPS_token": "puts 'https' inside the domain name to look secure",
    }
    return [reasons[k] for k, v in features.items() if v < 1]
