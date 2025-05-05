import json
import re
import uuid

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy_playwright.page import PageMethod


class FordSpider(scrapy.Spider):
    name = 'ford'
    start_urls = ['https://www.ford.com']  # Or use 'https://www.ford.com/fps/script/Ford/USA'

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                method='GET',
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://www.ford.com/',
                },
                callback=self.parse_first,
                meta={
                    'cookiejar': 1,  # Enable cookie handling
                    'download_timeout': 30,  # Set timeout to 30 seconds
                }
            )

    def parse_first(self, response):
        self.logger.info("Parse start called")
        yield scrapy.Request(
            url='https://shop.ford.com/showroom/?gnav=header-shop-bp&linktype=build#/',
            method='GET',
            headers=self.headers,
            callback=self.parse_initial,
            meta={"cookiejar": 1}
        )

    def parse_initial(self, response):
        self.logger.info("Parse initial called")
        yield scrapy.Request(
            url='https://www.ford.com/fps/script/Ford/USA',
            method='GET',
            callback=self.parse_json,
            meta={"cookiejar": 1}
        )

    def parse_json(self, response):
        # Get the raw JavaScript content from the response
        js_content = response.text
        self.logger.info(js_content)
        # Use regex to find the vdmActiveNameplates variable
        pattern = r'var vdmActiveNameplates = ({.*?});'
        match = re.search(pattern, js_content, re.DOTALL)

        if match:
            # Extract the JSON string
            json_str = match.group(1)
            try:
                # Parse the JSON string into a Python dictionary
                vdm_active_nameplates = json.loads(json_str)

                # Yield or process the JSON data as needed
                yield {'vdmActiveNameplates': vdm_active_nameplates}
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON: {e}")
        else:
            self.logger.error("Could not find vdmActiveNameplates in the response")


# settings = Settings()
#
# settings.set("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
#
# settings.set("DOWNLOADER_MIDDLEWARES", {
#     "scraper.scraper.middlewares.ProxyMiddleware": 543,
# })
#
# # settings.set("DOWNLOAD_HANDLERS", {
# #     "http": "scraper.scraper.scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
# #     "https": "scraper.scraper.scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
# # })
#
# # settings.set("FEED_URI", 'output.csv')
# # settings.set("FEED_FORMAT", 'csv')
#
# # settings.set("TWISTED_REACTOR", "twisted.internet.asyncioreactor.AsyncioSelectorReactor")
#
# process = CrawlerProcess(settings)
# process.crawl(FordSpider)
# process.start()
