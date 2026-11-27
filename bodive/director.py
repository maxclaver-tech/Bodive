from . import analyst, commercial, creator, researcher


def plan(memory, topic, price, unit_cost, fixed_cost, research_source=None):
    memory.check_running()
    if research_source:
        memory.research_slot()
    evidence = researcher.research(topic, research_source)
    analysis = analyst.analyze(evidence, price, unit_cost, fixed_cost)
    topic = evidence["topic"]
    return memory.save({
        "mode": memory.mode, "evidence": evidence, "analysis": analysis,
        "product_markdown": creator.create(topic),
        "listing": commercial.listing(topic, price),
        "decision": "Prepare draft for human review. Validate demand and originality before launch.",
    })
