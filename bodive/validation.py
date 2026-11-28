"""Non-spending commercial experiment proposals; independent from payment approvals."""
from . import decision
from .memory import Refused

def build(memory, identifier):
    data=decision.analyze(memory,identifier)
    a=data["assessment"]
    if a["margin"]<=0:
        raise Refused("Margen no positivo: revisar precio y costes antes de proponer validación")
    topic=a["topic"]
    return {"dossier_id":identifier,"product":topic,
            "audience_hypothesis":f"Personas que necesitan resolver la tarea relacionada con {topic}; segmento concreto por confirmar.",
            "differentiation_hypothesis":"Prototipo original, instrucciones claras y ejemplo práctico; contrastar contra alternativas gratuitas y de pago.",
            "price_cents":a["price"],"unit_cost_cents":a["unit_cost"],
            "margin_cents":a["margin"],"direct_cost_cents":data["direct_cost"],
            "pending_reserves_cents":data["reserved"],
            "maximum_new_spend_cents":0,
            "duration_days":7,
            "actions":["Revisar cinco ofertas realmente comparables y sus diferencias",
                       "Preparar una muestra privada reutilizando recursos existentes",
                       "Solicitar opinión a cinco personas del público objetivo que acepten participar",
                       "Preguntar por disposición a pagar el precio indicado sin cobrar ni prometer entrega",
                       "Registrar respuestas y objeciones sin datos personales"],
            "success_rule":"Umbral exploratorio: al menos dos de cinco participantes expresan intención de pago al precio supuesto. No equivale a ventas ni a una muestra representativa.",
            "stop_rule":"Si en siete días no se cumple el umbral, revisar o abandonar la hipótesis. No contratar servicios ni aumentar gasto.",
            "channel_hypothesis":"Venta futura en Gumroad, pendiente de revisar comisiones, derechos, impuestos y autorización separada.",
            "risks":["Sin ventas verificadas","Posibles sustitutos gratuitos","Costes e impuestos sin confirmar"],
            "evidence":{"community_count":data["signals"],"catalogs":data["catalogs"]},
            "authorization_scope":"Solo revisar y aceptar un plan de validación sin gasto. No concede permisos de ejecución, contacto externo, publicación, Claude ni pago."}

def report(p):
    return "\n\n".join([f"BODIVE · Propuesta de validación\n{p['product']}",
      f"Público (hipótesis): {p['audience_hypothesis']}",
      f"Diferenciación (hipótesis): {p['differentiation_hypothesis']}",
      f"Precio supuesto: {p['price_cents']/100:.2f} EUR · margen supuesto: {p['margin_cents']/100:.2f} EUR",
      f"Costes registrados: {p['direct_cost_cents']/100:.2f} EUR · reservas: {p['pending_reserves_cents']/100:.2f} EUR",
      "Gasto nuevo autorizado: 0 EUR · duración propuesta: 7 días",
      "Plan propuesto:\n"+"\n".join(f"{n}. {x}" for n,x in enumerate(p["actions"],1)),
      p["success_rule"],p["stop_rule"],p["channel_hypothesis"],
      "Riesgos: "+"; ".join(p["risks"]),p["authorization_scope"]])
