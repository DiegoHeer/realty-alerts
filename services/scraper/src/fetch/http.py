import httpx


class HttpFetch:
    def fetch(self, url: str) -> str:
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        return response.text
