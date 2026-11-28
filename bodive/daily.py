"""Opt-in daily discovery, at-most-once attempts, no paid requests."""
from . import discovery
from .memory import Refused


def changes(previous, snapshot):
    old = {r["topic"]:r for r in (previous or {}).get("candidates",[])}
    result = []
    for n,row in enumerate(snapshot["candidates"],1):
        if row["status"]!="sampled":
            continue
        prior = old.get(row["topic"],{})
        known = {h["url"] for h in prior.get("signals",[])}
        fresh = [h for h in row["signals"] if h["url"] not in known]
        if fresh:
            result.append((n,row,fresh))
    return result


def run(memory, telegram):
    if memory.mode!="live" or not memory.claim_daily_discovery():
        return False
    identifier = None
    try:
        prior = memory.get_discovery()
        snapshot = discovery.discover(memory, telegram.http, category="daily")
        identifier = memory.record_discovery(snapshot)
        candidates = changes(prior["snapshot"] if prior else None,snapshot)
        memory.check_running()
        unavailable = sum(r["status"]!="sampled" for r in snapshot["candidates"])
        lines = ["BODIVE · Informe diario",snapshot["collected_at"],
                 "Señales públicas nuevas respecto al último informe; no ventas verificadas.",
                 f"Categorías sin fuente disponible: {unavailable}."]
        for n,row,fresh in candidates:
            lines.append(f"{row['product']} · {len(fresh)} enlaces nuevos en la muestra\n"
                         f"{fresh[0]['title']}\n{fresh[0]['url']}\n/shortlist {identifier} {n}")
        if not candidates:
            lines.append("Sin enlaces nuevos en las muestras disponibles.")
        lines.append("/opportunities · /daily off")
        telegram.send("\n\n".join(lines))
        memory.daily_outcome("sent",identifier)
    except Refused:
        memory.daily_outcome("refused_or_delivery_uncertain",identifier)
    except Exception:
        memory.daily_outcome("failed_or_delivery_uncertain",identifier)
        raise
    return True
