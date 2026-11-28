"""Evidence-separated decision aid. No sales forecasts or automatic investment."""
from datetime import timedelta
from . import market, competition
from .memory import Refused, now


def fresh(snapshot):
    return bool(snapshot and (now()-timedelta(days=30)).isoformat() <=
                snapshot["collected_at"] <= now().isoformat())


def analyze(memory, identifier, price=None, unit_cost=None, fixed_cost=None):
    dossier = memory.load(identifier)
    costs = memory.product_report(identifier)
    a = dossier["analysis"]["assumptions"]
    price = a["price_cents"] if price is None else price
    unit_cost = a["estimated_total_unit_cost_cents"] if unit_cost is None else unit_cost
    fixed_cost = a["estimated_fixed_cost_cents"] if fixed_cost is None else fixed_cost
    if (type(price) is not int or not 1<=price<=1000000 or type(unit_cost) is not int
            or not 0<=unit_cost<=1000000 or type(fixed_cost) is not int or not 0<=fixed_cost<=10000):
        raise Refused("Supuestos inválidos")
    # Override only this local what-if; never mutate stored assumptions.
    scenario = {**dossier,"analysis":{**dossier["analysis"],"assumptions":{
        **a,"price_cents":price,"estimated_total_unit_cost_cents":unit_cost,
        "estimated_fixed_cost_cents":fixed_cost}}}
    assessment = market.assessment(scenario,memory.market_observations(identifier),costs["cost_cents"])
    catalogs = {}
    for source in ("books","etsy"):
        snapshot = memory.latest_competition(identifier,source)
        if fresh(snapshot):
            catalogs[source] = {**competition.summarize(snapshot),"query":snapshot["query"],
                                "collected_at":snapshot["collected_at"],
                                "examples":snapshot["observations"][:3]}
        else:
            catalogs[source] = None
    community = memory.latest_community(identifier)
    signals = len(community["observations"]) if fresh(community) else None
    margin = assessment["margin"]
    # Pessimistic exposure: pending reserves may already cover some fixed estimates.
    # This upper accounting scenario deliberately counts them on top of the floor.
    exposure = assessment["fixed_floor"] + costs["reserved_cents"]
    verdict = "NO INVERTIR: margen supuesto no positivo" if margin<=0 else (
        "SOLO VALIDACIÓN SIN GASTO: faltan ventas verificadas y costes confirmados")
    tasks = ["Identificar un comprador concreto y su problema",
             "Verificar ofertas equivalentes y sus diferencias",
             "Comprobar disposición a pagar con interesados reales",
             "Confirmar comisiones, impuestos, devoluciones y coste de producción"]
    if not catalogs["etsy"] or not catalogs["etsy"]["count"]:
        tasks.insert(0,"Buscar plantillas comparables en un marketplace; Apple Books es indirecto")
    if costs["reserved_cents"]:
        tasks.insert(0,"Conciliar reservas de producción pendientes")
    return {"assessment":assessment,"catalogs":catalogs,"signals":signals,
            "direct_cost":costs["cost_cents"],"reserved":costs["reserved_cents"],
            "exposure":exposure,"stress_break_even":(exposure+margin-1)//margin if margin>0 else None,
            "stress_scenarios":{n:n*margin-exposure for n in (0,5,10,25)},
            "verdict":verdict,"tasks":tasks}


def money(cents):
    return f"{cents/100:.2f} EUR"


def report(data):
    a=data["assessment"]
    lines=[f"BODIVE · Decisión comercial\n{a['topic']}",data["verdict"],
           f"Precio supuesto: {money(a['price'])} · coste unitario supuesto: {money(a['unit_cost'])}",
           f"Margen supuesto: {money(a['margin'])}",
           f"Costes directos registrados: {money(data['direct_cost'])}",
           f"Reservas pendientes (no gastos): {money(data['reserved'])}",
           f"Coste fijo mínimo estimado: {money(a['fixed_floor'])}",
           f"Escenario conservador incluyendo reservas: {money(data['exposure'])}",
           "Punto de equilibrio mínimo: "+(str(a["break_even"]) if a["break_even"] is not None else "no alcanzable"),
           "Punto de equilibrio conservador: "+(str(data["stress_break_even"]) if data["stress_break_even"] is not None else "no alcanzable"),
           "Escenarios conservadores, no previsiones: "+", ".join(f"{n} ventas: {money(v)}" for n,v in data["stress_scenarios"].items()),
           f"Conversaciones recientes guardadas: {data['signals'] if data['signals'] is not None else 'sin muestra reciente'}",
           "Señales y observaciones de operador no verifican compras."]
    for name,s in data["catalogs"].items():
        if s is None:
            lines.append(f"{name}: sin catálogo reciente (30 días)")
            continue
        lines.append(f"{name}: {s['count']} resultados EUR; {s['paid_count']} de pago. Consulta: {s['query']}")
        if s["paid_count"]:
            lines.append(f"Rango anunciado {money(s['minimum'])}–{money(s['maximum'])}; mediana inferior {money(s['median'])}.")
        lines.append("Libros: referencia indirecta." if name=="books" else "Descargas: equivalencia pendiente de revisión.")
        for item in s["examples"]:
            lines.append(f"{item['title']} · {money(item['price_cents'])}\n{item['url']}")
    lines.append("Próximos pasos sin inversión:\n"+"\n".join(f"- {t}" for t in data["tasks"]))
    lines.append("No se modifica el dosier ni se autoriza gasto. Costes comunes no asignados.")
    return "\n\n".join(lines)
