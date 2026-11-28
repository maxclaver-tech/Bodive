"""Read-only catalog observations, not demand or verified comparable products."""
import os
import re
from decimal import Decimal, InvalidOperation
from statistics import median_low
from urllib.parse import urlencode, urlsplit
from .memory import Refused, now

def clean(value):
    return " ".join(value.split())[:180] if isinstance(value,str) else ""

def cents(value, divisor=1):
    if type(value) not in (int,float,str) or type(divisor) is not int or not 1<=divisor<=1000000:
        return None
    try:
        n=Decimal(str(value))*100/divisor
        if not n.is_finite() or not 0<=n<=1000000 or n!=n.to_integral_value():
            return None
        return int(n)
    except (InvalidOperation, ValueError, OverflowError):
        return None

def catalog(http, topic, source):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{1,59}",topic):
        raise Refused("Tema de investigación no válido")
    if source=="books":
        params=urlencode({"term":topic,"entity":"ebook","country":"ES","limit":10,"explicit":"No"})
        raw=http.request("Apple Books","https://itunes.apple.com/search?"+params)
        items=raw.get("results")
    elif source=="etsy":
        key=os.environ.get("BODIVE_ETSY_API_KEY","")
        if not re.fullmatch(r"[^:\s]+:[^:\s]+",key):
            raise Refused("Etsy requiere una aplicación aprobada y BODIVE_ETSY_API_KEY en Render")
        params=urlencode({"keywords":topic,"limit":10,"sort_on":"score"})
        raw=http.request("Etsy","https://openapi.etsy.com/v3/application/listings/active?"+params,
                         headers={"x-api-key":key})
        items=raw.get("results")
    else:
        raise Refused("Fuente desconocida")
    if not isinstance(items,list):
        raise Refused("Respuesta de catálogo no válida")
    rows=[]
    seen=set()
    for item in items[:10]:
        if not isinstance(item,dict):
            continue
        if source=="books":
            if item.get("kind")!="ebook" or item.get("currency")!="EUR":
                continue
            identifier=item.get("trackId")
            title=clean(item.get("trackName"))
            price=cents(item.get("price"))
            url=f"https://books.apple.com/es/book/id{identifier}"
            kind="ebook"
        else:
            # Exclude physical items and currencies that cannot be compared directly.
            if item.get("listing_type")!="download" or not isinstance(item.get("price"),dict):
                continue
            p=item["price"]
            if p.get("currency_code")!="EUR":
                continue
            identifier=item.get("listing_id")
            title=clean(item.get("title"))
            price=cents(p.get("amount"),p.get("divisor"))
            url=f"https://www.etsy.com/listing/{identifier}"
            kind="digital_download"
        if type(identifier) is not int or identifier<=0 or identifier in seen or not title or price is None:
            continue
        seen.add(identifier)
        rows.append({"title":title,"url":url,"price_cents":price,"kind":kind})
    return {"source":source,"query":topic,"collected_at":now().isoformat(),"currency":"EUR",
            "observations":rows,"interpretation":"Precios anunciados de una muestra; relevancia, ventas, comisiones y demanda no verificadas."}

def summarize(snapshot):
    paid=sorted(r["price_cents"] for r in snapshot["observations"] if r["price_cents"]>0)
    return {"count":len(snapshot["observations"]),"paid_count":len(paid),
            "free_count":len(snapshot["observations"])-len(paid),
            "minimum":paid[0] if paid else None,"maximum":paid[-1] if paid else None,
            "median":median_low(paid) if paid else None}
