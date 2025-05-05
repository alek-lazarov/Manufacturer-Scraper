import json
import re

import playwright
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy_playwright.page import PageMethod
import logging

class TestSpider(scrapy.Spider):
    name = "what-the-fuck"
    start_url = "https://www.ford.com/"
    headers = {
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }

    def start_requests(self):
        self.logger.info("Parse initial called")
        yield scrapy.Request(
            url='https://www.ford.com/fps/script/Ford/USA',
            method='GET',
            callback=self.parse_json,
            meta={
                "playwright": True,
                "playwright_context": "default",
                "playwright_page_close": False,
                "playwright_context_kwargs": {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": self.headers["User-Agent"],
                },
                "cookiejar": 1,
            },
            errback=self.handle_error,
        )

    def parse_json(self, response):
        # Get the raw JavaScript content from the response
        js_content = response.text

        # Use regex to find the vdmActiveNameplates variable
        pattern = r'var vdmActiveNameplates = ({.*?});'
        match = re.search(pattern, js_content, re.DOTALL)

        if match:
            # Extract the JSON string
            json_str = match.group(1)
            try:
                # Parse the JSON string into a Python dictionary
                vdm_active_nameplates = json.loads(json_str)
                self.logger.info(vdm_active_nameplates)
                # Yield or process the JSON data as needed
                yield {'vdmActiveNameplates': vdm_active_nameplates}
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON: {e}")
        else:
            self.logger.error("Could not find vdmActiveNameplates in the response")

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
