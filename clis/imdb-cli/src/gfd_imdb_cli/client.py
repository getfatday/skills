"""HTTP client for IMDB APIs (suggestion, GraphQL, page scraping)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

import httpx

_BASE_SUGGEST = "https://v3.sg.media-imdb.com/suggestion/x"
_GRAPHQL_URL = "https://graphql.imdb.com/"
_IMDB_BASE = "https://www.imdb.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA}
_GRAPHQL_HEADERS = {**_HEADERS, "Content-Type": "application/json"}

_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    """Return a shared httpx client."""
    global _client
    if _client is None:
        _client = httpx.Client(
            headers=_HEADERS, timeout=15.0, follow_redirects=True
        )
    return _client


# ---------------------------------------------------------------------------
# Suggestion API (search)
# ---------------------------------------------------------------------------


def search_suggestions(query: str) -> list[dict[str, Any]]:
    """Search IMDB via the suggestion/autocomplete API."""
    url = f"{_BASE_SUGGEST}/{quote(query, safe='')}.json"
    resp = get_client().get(url)
    resp.raise_for_status()
    data = resp.json()
    return [
        item
        for item in data.get("d", [])
        if item.get("id", "").startswith(("tt", "nm"))
    ]


# ---------------------------------------------------------------------------
# GraphQL helpers
# ---------------------------------------------------------------------------


def _graphql(query: str) -> dict[str, Any]:
    """Execute a GraphQL query against IMDB's public endpoint."""
    resp = get_client().post(
        _GRAPHQL_URL, json={"query": query}, headers=_GRAPHQL_HEADERS
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and "data" not in data:
        msg = data["errors"][0]["message"]
        raise RuntimeError(f"GraphQL error: {msg}")
    return data.get("data", {})


def _title_query(title_id: str, body: str) -> str:
    return "{ title(id: \"" + title_id + "\") { " + body + " } }"


def _name_query(name_id: str, body: str) -> str:
    return "{ name(id: \"" + name_id + "\") { " + body + " } }"


_TITLE_DETAIL_BODY = """
    id
    titleText { text }
    releaseYear { year }
    ratingsSummary { aggregateRating voteCount }
    runtime { seconds }
    genres { genres { text } }
    directors: credits(first: 10, filter: { categories: ["director"] }) {
      edges { node { name { id nameText { text } } } }
    }
    writers: credits(first: 10, filter: { categories: ["writer"] }) {
      edges { node { name { id nameText { text } } } }
    }
    cast: credits(first: 10, filter: { categories: ["actor", "actress"] }) {
      edges {
        node {
          name { id nameText { text } }
          ... on Cast { characters { name } }
        }
      }
    }
    plot { plotText { plainText } }
"""

_BOX_OFFICE_BODY = """
    id
    titleText { text }
    productionBudget { budget { amount currency } }
    lifetimeGross(boxOfficeArea: DOMESTIC) {
      total { amount currency }
    }
    worldwideGross: lifetimeGross(boxOfficeArea: WORLDWIDE) {
      total { amount currency }
    }
    openingWeekendGross(boxOfficeArea: DOMESTIC) {
      gross { total { amount currency } }
    }
"""

_PERSON_DETAIL_BODY = """
    id
    nameText { text }
    birthDate { dateComponents { year month day } }
    birthLocation { text }
    bio { text { plainText } }
    knownFor(first: 5) {
      edges {
        node {
          title { id titleText { text } releaseYear { year } }
        }
      }
    }
"""


def get_title(title_id: str) -> dict[str, Any]:
    """Fetch full title details via GraphQL."""
    data = _graphql(_title_query(title_id, _TITLE_DETAIL_BODY))
    return data.get("title") or {}


def get_title_cast(
    title_id: str, limit: int = 200
) -> list[dict[str, Any]]:
    """Fetch full cast list via GraphQL."""
    body = f"""
        cast: credits(
          first: {limit},
          filter: {{ categories: ["actor", "actress"] }}
        ) {{
          edges {{
            node {{
              name {{ id nameText {{ text }} }}
              ... on Cast {{ characters {{ name }} }}
            }}
          }}
        }}
    """
    data = _graphql(_title_query(title_id, body))
    title = data.get("title") or {}
    cast = title.get("cast") or {}
    return [e["node"] for e in cast.get("edges", [])]


def get_title_box_office(title_id: str) -> dict[str, Any]:
    """Fetch box office data via GraphQL."""
    data = _graphql(_title_query(title_id, _BOX_OFFICE_BODY))
    return data.get("title") or {}


def get_person(name_id: str) -> dict[str, Any]:
    """Fetch person details via GraphQL."""
    data = _graphql(_name_query(name_id, _PERSON_DETAIL_BODY))
    return data.get("name") or {}


def get_person_credits(
    name_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    """Fetch person filmography via GraphQL."""
    body = f"""
        credits(first: {limit}) {{
          edges {{
            node {{
              title {{ id titleText {{ text }} releaseYear {{ year }} }}
              category {{ text }}
            }}
          }}
        }}
    """
    data = _graphql(_name_query(name_id, body))
    name = data.get("name") or {}
    credits = name.get("credits") or {}
    return [e["node"] for e in credits.get("edges", [])]


# ---------------------------------------------------------------------------
# Chart scraping (__NEXT_DATA__)
# ---------------------------------------------------------------------------


def _scrape_next_data(path: str) -> dict[str, Any]:
    """Fetch an IMDB page and extract __NEXT_DATA__ JSON."""
    resp = get_client().get(f"{_IMDB_BASE}{path}")
    resp.raise_for_status()
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        resp.text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"No __NEXT_DATA__ found on {path}")
    return json.loads(match.group(1))


def get_top_movies(limit: int = 250) -> list[dict[str, Any]]:
    """Fetch Top 250 movies from the chart page."""
    data = _scrape_next_data("/chart/top/")
    edges = (
        data["props"]["pageProps"]["pageData"]["chartTitles"]["edges"]
    )
    return edges[:limit]


def get_top_tv(limit: int = 250) -> list[dict[str, Any]]:
    """Fetch Top 250 TV shows from the chart page."""
    data = _scrape_next_data("/chart/toptv/")
    edges = (
        data["props"]["pageProps"]["pageData"]["chartTitles"]["edges"]
    )
    return edges[:limit]


def get_box_office_chart() -> list[dict[str, Any]]:
    """Fetch current box office chart from the chart page."""
    data = _scrape_next_data("/chart/boxoffice/")
    page = data["props"]["pageProps"]["pageData"]
    return page["topGrossingReleases"]["edges"]


def get_upcoming() -> list[dict[str, Any]]:
    """Fetch upcoming releases from the calendar page."""
    data = _scrape_next_data("/calendar/")
    groups = data["props"]["pageProps"]["groups"]
    entries = []
    for group in groups:
        for entry in group.get("entries", []):
            entries.append(entry)
    return entries
