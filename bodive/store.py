"""Read-only Gumroad API adapter. Never sends buyer data to Telegram or memory."""
import os
import re
from collections import Counter
from datetime import timedelta
from urllib.parse import urlencode
from .memory import Refused, now

class Store:
    def __init__(self,http):
        self.http=http
        self.token=os.environ.get("GUMROAD_ACCESS_TOKEN","").strip()
        if not self.token or any(c.isspace() for c in self.token):
            raise Refused("Falta GUMROAD_ACCESS_TOKEN válido en Render")

    def get(self, endpoint, params=None):
        if endpoint not in {"products","sales"}:
            raise Refused("Operación de tienda no permitida")
        url="https://api.gumroad.com/v2/"+endpoint
        if params:
            url+="?"+urlencode(params)
        data=self.http.request("Gumroad",url,headers={"Authorization":"Bearer "+self.token})
        if data.get("success") is not True or not isinstance(data.get(endpoint),list):
            raise Refused("Gumroad no confirmó la consulta; revisa permisos del token")
        return data

    def products(self):
        data=self.get("products")
        rows=[]
        for item in data["products"][:20]:
            if not isinstance(item,dict):
                continue
            name=item.get("name")
            identifier=item.get("id")
            if not isinstance(name,str) or not isinstance(identifier,str) or not re.fullmatch(r"[A-Za-z0-9_=-]{1,120}",identifier):
                continue
            rows.append({"name":" ".join(name.split())[:180],"id":identifier,
                         "published":item.get("published") if type(item.get("published")) is bool else None})
        return {"rows":rows,"returned":len(data["products"]),
                "limited":len(rows)!=len(data["products"]) or bool(data.get("next_page_url"))}

    def sales(self):
        after=(now()-timedelta(days=30)).date().isoformat()
        data=self.get("sales",{"after":after})
        counts=Counter()
        amounts=Counter()
        seen=set()
        skipped=0
        # A first-page observation, not a financial ledger or payout report.
        for item in data["sales"][:100]:
            if not isinstance(item,dict):
                skipped+=1
                continue
            identifier=item.get("id")
            if not isinstance(identifier,str) or not identifier or identifier in seen:
                skipped+=1
                continue
            seen.add(identifier)
            if item.get("test") is True or item.get("is_test") is True:
                counts["test"]+=1
            elif item.get("refunded") is True or item.get("disputed") is True or item.get("chargebacked") is True:
                counts["refund_or_dispute"]+=1
            else:
                counts["other"]+=1
                currency=item.get("currency")
                price=item.get("price")
                if isinstance(currency,str) and re.fullmatch(r"[A-Z]{3}",currency.upper()) and type(price) is int and 0<=price<=100000000:
                    amounts[currency.upper()]+=price
        return {"after":after,"returned":len(data["sales"]),"counts":dict(counts),
                "price_minor_units":dict(amounts),"skipped":skipped,
                "limited":len(data["sales"])>100 or bool(data.get("next_page_url") or data.get("next_page_key"))}
