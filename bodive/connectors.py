"""Fixed-endpoint, bounded HTTP adapters."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .memory import Refused


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Http:
    def request(self, service, url, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(url, data=data, headers={
            "User-Agent": "BODIVE/0.1", "Content-Type": "application/json", **(headers or {}),
        })
        try:
            timeout = 120 if service == "Claude" and url == "https://api.anthropic.com/v1/messages" else 12
            with build_opener(NoRedirect).open(request, timeout=timeout) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise Refused(f"{service}: response exceeded size limit")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except HTTPError as exc:
            raise Refused(f"{service}: HTTP {exc.code}") from None
        except TimeoutError:
            raise Refused(f"{service}: request timed out; delivery uncertain") from None
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise Refused(f"{service}: request timed out; delivery uncertain") from None
            raise Refused(f"{service}: network connection error") from None
        except OSError:
            raise Refused(f"{service}: transport error") from None
        except ValueError:
            raise Refused(f"{service}: invalid response format") from None


class GitHubResearch:
    def __init__(self, http):
        self.http = http

    def search(self, topic):
        params = urlencode({"q": f"{topic} in:name,description is:public", "sort": "updated",
                            "per_page": 5})
        result = self.http.request("GitHub Search", f"https://api.github.com/search/repositories?{params}",
                                   headers={"Accept": "application/vnd.github+json",
                                            "X-GitHub-Api-Version": "2022-11-28"})
        try:
            observations = [
                {"url": item["html_url"], "name": item["full_name"],
                 "stars": item["stargazers_count"], "updated_at": item["updated_at"]}
                for item in result["items"][:5]
            ]
            if any(not row["url"].startswith("https://github.com/") for row in observations):
                raise ValueError
            return {"source": "GitHub REST repository search", "incomplete": result["incomplete_results"],
                    "observations": observations}
        except (KeyError, ValueError, TypeError, AttributeError):
            raise Refused("GitHub Search: unexpected response") from None


class Telegram:
    def __init__(self, http, token, operator):
        self.http = http
        self.token = token
        self.operator = operator

    def call(self, method, body):
        result = self.http.request("Telegram", f"https://api.telegram.org/bot{self.token}/{method}", body)
        if result.get("ok") is not True or "result" not in result:
            raise Refused("Telegram rejected the operation")
        return result["result"]

    def send(self, text):
        # A 1500-character chunk also stays below 4096 UTF-16 code units.
        for start in range(0, len(text), 1500):
            self.call("sendMessage", {"chat_id": self.operator, "text": text[start:start + 1500],
                                      "link_preview_options": {"is_disabled": True}})

    def updates(self, offset):
        return self.call("getUpdates", {"offset": offset, "limit": 20, "timeout": 0,
                                        "allowed_updates": ["message"]})


class Claude:
    INPUT_LIMIT = 4_000
    OUTPUT_LIMIT = 1_600

    def __init__(self, http, key):
        self.http = http
        self.headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}

    def call(self, path, body):
        return self.http.request("Claude", "https://api.anthropic.com/v1/messages" + path,
                                 body, self.headers)

    def generate(self, payload, check_running):
        body = {"model": payload["model"], "messages": [{"role": "user", "content": payload["prompt"]}]}
        check_running()
        count = self.call("/count_tokens", body).get("input_tokens")
        if type(count) is not int or not 0 < count <= self.INPUT_LIMIT:
            raise Refused("Claude input exceeds limit or could not be verified")
        check_running()
        result = self.call("", {**body, "max_tokens": self.OUTPUT_LIMIT})
        try:
            draft = "\n".join(block["text"] for block in result["content"] if block["type"] == "text")
            if not draft.strip() or len(draft) > 20_000:
                raise ValueError
            return {"draft": draft, "usage": result["usage"], "model": result["model"],
                    "stop_reason": result["stop_reason"]}
        except (KeyError, TypeError, ValueError):
            raise Refused("Claude response could not be verified") from None
