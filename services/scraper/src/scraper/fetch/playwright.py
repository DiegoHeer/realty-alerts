from typing import Self

from loguru import logger
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


class PlaywrightFetch:
    def __init__(self, browser_url: str) -> None:
        self.browser_url = browser_url
        self._pw = None
        self._browser = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def fetch(self, url: str) -> str:
        logger.debug(f"Playwright fetch: {url}")
        browser = self._get_browser()
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
            return page.content()
        except PlaywrightError as e:
            raise RuntimeError(f"Playwright fetch failed for {url}: {e}") from e
        finally:
            page.close()

    def _get_browser(self):
        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.firefox.connect(self.browser_url)
        return self._browser

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._browser = None
        self._pw = None
