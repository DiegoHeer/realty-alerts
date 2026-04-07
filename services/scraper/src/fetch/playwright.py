from playwright.sync_api import sync_playwright


class PlaywrightFetch:
    def __init__(self, browser_url: str) -> None:
        self.browser_url = browser_url

    def fetch(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.connect(self.browser_url)
            page = browser.new_page()
            page.goto(url)
            content = page.content()
            browser.close()
            return content
