import requests


def send(topic: str, title: str, body: str, url: str | None) -> None:
    # JSON publish: headers can't carry non-ASCII titles
    payload = {"topic": topic, "title": title, "message": body}
    if url:
        payload["click"] = url
    r = requests.post("https://ntfy.sh/", json=payload, timeout=15)
    r.raise_for_status()
