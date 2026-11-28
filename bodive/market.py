"""Conservative commercial assessment; operator observations are not independently verified."""
from datetime import timedelta
from urllib.parse import urlsplit
from .memory import Refused, now

KINDS = {"competitor", "interest", "purchase"}


def observation(kind, url, note):
    if kind not in KINDS or not 1 <= len(note.strip()) <= 300 or len(url)>350:
        raise Refused("Tipo o descripción de evidencia incorrectos")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or any(c.isspace() for c in url)):
            raise ValueError()
    except ValueError:
        raise Refused("Usa una URL HTTPS pública sin parámetros, credenciales ni fragmentos") from None
    return {"kind":kind,"url":url,"note":note.strip(),"collected_at":now().isoformat(),
            "verification":"operator_reported"}


def assessment(dossier, observations, direct_cost_cents=0):
    a = dossier["analysis"]["assumptions"]
    price, cost, fixed = (a[k] for k in ("price_cents","estimated_total_unit_cost_cents","estimated_fixed_cost_cents"))
    margin = price-cost
    # Fixed estimate may already include direct generation costs; avoid double counting.
    floor = max(fixed,direct_cost_cents)
    recent = [o for o in observations if o["collected_at"] >= (now()-timedelta(days=30)).isoformat()]
    counts = {kind:len({o["url"] for o in recent if o["kind"]==kind}) for kind in sorted(KINDS)}
    verdict = "NO INVERTIR: margen unitario no positivo" if margin<=0 else (
        "REVISAR evidencia aportada por operador; no verificada" if counts["purchase"] else
        "VALIDAR DEMANDA antes de ampliar inversión")
    return {"topic":dossier["evidence"]["topic"],"price":price,"unit_cost":cost,"margin":margin,
            "fixed_floor":floor,"break_even":(floor+margin-1)//margin if margin>0 else None,
            "scenarios":{n:n*margin-floor for n in (0,5,10,25)},
            "counts":counts,"verdict":verdict,"observations":recent[-10:],
            "repository_signals":len(dossier["evidence"].get("observations",[]))}
