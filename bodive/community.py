"""Bounded public discussion discovery; not a proxy for sales."""
import re
from datetime import timedelta, datetime, UTC
from urllib.parse import urlencode

from .memory import Refused, now


def search(http, topic):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{1,59}",topic):
        raise Refused("Tema de investigación no válido")
    cutoff = int((now()-timedelta(days=365)).timestamp())
    params = urlencode({"query":topic,"tags":"story","numericFilters":f"created_at_i>={cutoff}",
                        "hitsPerPage":10,"attributesToRetrieve":"objectID,title,points,num_comments,created_at_i"})
    result = http.request("HN Search", "https://hn.algolia.com/api/v1/search?"+params)
    hits = result.get("hits")
    if not isinstance(hits,list):
        raise Refused("HN Search: respuesta inesperada")
    rows = []
    seen = set()
    for hit in hits[:10]:
        if not isinstance(hit,dict):
            continue
        identifier = hit.get("objectID")
        title = hit.get("title")
        ts = hit.get("created_at_i")
        points, comments = hit.get("points"),hit.get("num_comments")
        if (not isinstance(identifier,str) or not re.fullmatch(r"[0-9]{1,16}",identifier)
                or identifier in seen or not isinstance(title,str) or not title.strip()
                or type(ts) is not int or not cutoff <= ts <= int(now().timestamp())
                or type(points) is not int or type(comments) is not int
                or points<0 or comments<0):
            continue
        seen.add(identifier)
        rows.append({"title":" ".join(title.split())[:180],
                     "url":"https://news.ycombinator.com/item?id="+identifier,
                     "points":points,"comments":comments,
                     "published_at":datetime.fromtimestamp(ts,UTC).isoformat()})
    return {"source":"Hacker News / Algolia","query":topic,"collected_at":now().isoformat(),
            "observations":rows,"interpretation":"Interés de una comunidad tecnológica; relevancia y demanda de pago no verificadas."}
