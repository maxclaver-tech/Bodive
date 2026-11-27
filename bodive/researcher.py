import re

from .memory import Refused, now


def research(topic, connector=None):
    topic = " ".join(topic.split())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{1,59}", topic):
        raise Refused("Use a 2–60 character English topic with letters, spaces, digits or hyphens")
    evidence = (connector.search(topic) if connector else {
        "source": "Offline simulation", "incomplete": True, "observations": [],
    })
    return {"topic": topic, "collected_at": now().isoformat(), **evidence}
