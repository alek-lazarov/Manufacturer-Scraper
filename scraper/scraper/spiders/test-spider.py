import playwright
import scrapy
from scrapy_playwright.page import PageMethod
import logging

class TestSpider(scrapy.Spider):
    name = "test"
    start_url = "https://www.chevrolet.com/shopping/configurator"
    headers = {
        "Dealerid": "0",
        "Oemid": "GM",
        "Programid": "CHEVROLET",
        "Tenantid": "0",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.chevrolet.com",
        "Referer": "https://www.chevrolet.com/shopping/configurator",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # custom_settings = {
    #     "PLAYWRIGHT_BROWSER_TYPE": "chromium",
    #     "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": False, "slow_mo": 500},
    #     "LOG_LEVEL": "DEBUG",
    #     "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,  # 60 seconds
    #     "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1,
    #     "PLAYWRIGHT_CONTEXTS": {
    #         "default": {
    #             "viewport": {"width": 1920, "height": 1080},
    #             "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    #         }
    #     },
    # }

    def start_requests(self):
        yield scrapy.Request(
            url=self.start_url,
            method="GET",
            callback=self.after_get,
            meta={"cookiejar": 1}
        )

    def after_get(self, response):
        self.logger.info("Cookies: %s", response.meta.get("cookiejar"))
        yield scrapy.Request(
            url="https://www.chevrolet.com/shopping/configurator/truck/2024/silverado/silverado-ev/exterior?buildCode=&radius=255&zipCode=48243",
            method="GET",
            headers=self.headers,
            callback=self.parse_response,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_context": "default",
                "playwright_page_close": False,  # Prevent premature page closure
                "playwright_context_kwargs": {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": self.headers["User-Agent"],
                },
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "domcontentloaded", timeout=60000),
                    # Wait for the specific div to be rendered
                    PageMethod("wait_for_selector", "div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs", timeout=60000),
                    PageMethod("wait_for_timeout", 15000),  # Additional wait for rendering
                    PageMethod("screenshot", path="chevy_debug.png", full_page=True),
                ],
                "playwright_page_event_handlers": {
                    "console": lambda msg: self.logger.info(f"Console: {msg.text}"),
                    "pageerror": lambda err: self.logger.error(f"Page error: {err}"),
                    "request": lambda req: self.logger.debug(f"Request: {req.url}"),
                    "response": lambda res: self.logger.debug(f"Response: {res.url} {res.status}"),
                },
                "cookiejar": 1,
            },
            errback=self.handle_error,
        )

    def parse_response(self, response):
        self.logger.info("Response body length: %d", len(response.text))

        # Save raw response for debugging
        with open("output.txt", "a", encoding="utf-8") as f:
            f.write(response.text)

        # Select the container div
        options = response.css("div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs div.configuratorControlPanelSectionOptionV1_container__tKC_W")
        extracted_data = []

        for option in options:
            # Extract image URL
            image_url = option.css("div.productImageV1_imageContainer__otCnJ img::attr(src)").get(default="No image")

            # Extract name
            name = option.css("p.configuratorControlPanelSectionOptionV1_title__C78__::text").get(default="No name")

            # Extract price (if available in the pricing div)
            price = option.css("div.imageSwatchPricing_pricing__HzkIR::text").get(default="No price")

            extracted_data.append({
                "image_url": image_url,
                "name": name.strip() if name else "No name",
                "price": price.strip() if price else "No price",
            })

        # Log extracted data
        self.logger.info("Extracted data: %s", extracted_data)

        # Save extracted data to a file
        with open("extracted_data.json", "a", encoding="utf-8") as f:
            import json
            json.dump(extracted_data, f, indent=2)

        return extracted_data

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure}")
        if failure.check(playwright._impl._errors.Error):
            self.logger.error(f"Playwright error: {failure.value}")
