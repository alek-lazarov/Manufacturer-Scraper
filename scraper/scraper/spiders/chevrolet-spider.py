import copy
import json
import uuid
import playwright
import scrapy
from scrapy_playwright.page import PageMethod
from scrapy.item import Item, Field

# Define a Scrapy Item to structure the output
class ChevyItem(Item):
    make = Field()
    modelDisplayName = Field()
    model = Field()
    year = Field()
    bodyType = Field()
    msrp = Field()
    image = Field()
    bodyStyle = Field()
    cabType = Field()
    bedLength = Field()
    driveType = Field()
    trim = Field()
    exteriorColors = Field()
    interiorColors = Field()
    packages = Field()

class ChevySpider(scrapy.Spider):
    name = "chevrolet"
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
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",  # Bypass bot detection
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",  # Relax security for testing
                "--disable-features=IsolateOrigins,site-per-process",  # Disable strict isolation
            ],
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,  # 60s timeout
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 10,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "FEED_URI": "trim_output.csv",
        "FEED_FORMAT": "csv",
        "FEED_EXPORT_FIELDS": [
            "make", "modelDisplayName", "model", "year", "bodyType", "msrp", "image",
            "bodyStyle", "cabType", "bedLength", "driveType", "trim", "exteriorColors",
            "interiorColors", "packages"
        ],
        "ITEM_PIPELINES": {
            "scraper.middlewares.ChevyPipeline": 300,
        },
        "PLAYWRIGHT_CONTEXTS": {
            "default": {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "locale": "en-US",
                "timezone_id": "America/New_York",
                "permissions": ["geolocation"],
                "java_script_enabled": True,
                "ignore_https_errors": True,  # Ignore SSL errors
                "bypass_csp": True,
                "extra_http_headers": {
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                },
            }
        },
    }

    def start_requests(self):
        yield scrapy.Request(
            url=self.start_url,
            method="GET",
            callback=self.after_get,
            meta={"cookiejar": 1}
        )

    async def after_get(self, response):
        self.logger.info("Visited GET page. Now sending POST...")
        payload = {
            "make": "chevrolet",
            "yearFilter": ["2026", "2025", "2024"],
            "quickFilter": ["ELECTRIC", "SUV", "TRUCK", "CAR", "PERFORMANCE"]
        }

        yield scrapy.Request(
            url="https://www.chevrolet.com/chevrolet/shopping/api/aec-cp-configurator-gateway/p/v1/catalogue",
            method="POST",
            headers=self.headers,
            body=json.dumps(payload),
            callback=self.parse_response,
            meta={"cookiejar": 1}
        )

    def parse_response(self, response):
        parsed_response = json.loads(response.text)
        catalogs = [x for x in parsed_response["data"]["catalogue"] if x["bodyType"] not in ["ELECTRIC", "VAN"]]
        for catalog in catalogs:
            for model in catalog["models"]:
                for year in model["years"]:
                    payload = {
                        "make": "chevrolet",
                        "model": year["model"],
                        "bodyStyle": year["bodyStyle"],
                        "year": year["year"],
                        "zipCode": "48243",
                    }
                    localModel = {
                        "make": year["make"],
                        "modelDisplayName": year["displayName"],
                        "model": year["model"],
                        "year": year["year"],
                        "bodyType": year["bodyType"],
                        "msrp": year["msrp"],
                        "image": year["largeImage"],
                        "bodyStyle": year["bodyStyle"],
                        "cabType": "",
                        "bedLength": "",
                        "driveType": "",
                    }
                    if year["navigation"][0]["key"] == "config":
                        yield scrapy.Request(
                            url="https://www.chevrolet.com/chevrolet/shopping/api/aec-cp-configurator-gateway/p/v1/line",
                            method="POST",
                            headers=self.headers,
                            body=json.dumps(payload),
                            callback=self.parse_line_response,
                            cb_kwargs={"model": localModel},
                            meta={"cookiejar": 1}
                        )
                    else:
                        yield scrapy.Request(
                            url="https://www.chevrolet.com/chevrolet/shopping/api/aec-cp-configurator-gateway/p/v1/trim",
                            method="POST",
                            headers=self.headers,
                            body=json.dumps(payload),
                            callback=self.parse_trims_response,
                            cb_kwargs={"model": localModel},
                            meta={"cookiejar": 1}
                        )

    def parse_trims_response(self, response, model):
        parsed_response = json.loads(response.text)
        if parsed_response["data"]["trimOptions"].get("bodyType"):
            for bodyType in parsed_response["data"]["trimOptions"]["bodyType"]["options"]:
                for driveType in bodyType["driveType"]:
                    localModel = copy.deepcopy(model)
                    if bodyType["description"]:
                        props = [x.strip() for x in bodyType["description"].split(",") if x]
                        if len(props) < 2:
                            localModel["bodyType"] = props[0]
                        else:
                            localModel["cabType"] = props[0]
                            localModel["bedLength"] = props[1]
                    localModel["driveType"] = driveType["id"]
                    payload = {
                        "make": localModel["make"],
                        "model": localModel["model"],
                        "bodyStyle": localModel["bodyStyle"],
                        "year": localModel["year"],
                        "zipCode": "48243",
                        "driveTypeId": localModel["driveType"],
                        "bodyTypeId": bodyType["bodyTypeID"],
                    }
                    yield scrapy.Request(
                        url="https://www.chevrolet.com/chevrolet/shopping/api/aec-cp-configurator-gateway/p/v1/trim",
                        method="POST",
                        headers=self.headers,
                        body=json.dumps(payload),
                        callback=self.parse_deep_trims_response,
                        cb_kwargs={"model": localModel},
                        meta={"cookiejar": 1}
                    )

    def parse_line_response(self, response, model):
        parsed_response = json.loads(response.text)
        if parsed_response["data"]["bodyTypes"]:
            for bodyType in parsed_response["data"]["bodyTypes"]:
                for driveType in bodyType["driveTypes"]:
                    localModel = copy.deepcopy(model)
                    if bodyType["description"]:
                        props = [x.strip() for x in bodyType["description"].split(",") if x]
                        if len(props) < 2:
                            localModel["bodyType"] = props[0]
                        else:
                            localModel["cabType"] = props[0]
                            localModel["bedLength"] = props[1]
                    localModel["driveType"] = driveType["driveType"]
                    localModel["image"] = bodyType["imageUrl"]
                    localModel["msrp"] = bodyType["msrp"]["value"]
                    payload = {
                        "make": localModel["make"],
                        "model": localModel["model"],
                        "bodyStyle": localModel["bodyStyle"],
                        "year": localModel["year"],
                        "zipCode": "48243",
                        "driveTypeId": localModel["driveType"],
                        "bodyTypeId": bodyType["id"],
                    }
                    yield scrapy.Request(
                        url="https://www.chevrolet.com/chevrolet/shopping/api/aec-cp-configurator-gateway/p/v1/trim",
                        method="POST",
                        headers=self.headers,
                        body=json.dumps(payload),
                        callback=self.parse_deep_trims_response,
                        cb_kwargs={"model": localModel},
                        meta={"cookiejar": 1}
                    )

    def parse_deep_trims_response(self, response, model):
        localModel = copy.deepcopy(model)
        parsed_response = json.loads(response.text)
        for trim in parsed_response["data"]["trims"]:
            localModel["image"] = parsed_response["data"]["trims"][trim]["imageUrl"]
            localModel["trim"] = parsed_response["data"]["trims"][trim]["name"]
            if parsed_response["data"]["trims"][trim].get("msrp"):
                localModel["msrp"] = parsed_response["data"]["trims"][trim]["msrp"]["value"]


            # Trigger exterior colors request
            url = f"https://www.chevrolet.com/shopping/configurator/{localModel['bodyType']}/{localModel['year']}/{localModel['model']}/{localModel['bodyStyle']}/exterior?buildCode=&radius=250&zipCode=48243"
            yield scrapy.Request(
                url=url,
                method="GET",
                headers=self.headers,
                callback=self.parse_exterior_response,
                cb_kwargs={"model": localModel},
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_context": "default",
                    "playwright_page_close": True,
                    "playwright_context_kwargs": {
                        "viewport": {"width": 1920, "height": 1080},
                        "user_agent": self.headers["User-Agent"],
                        "locale": "en-US",
                        "timezone_id": "America/New_York",
                        "permissions": ["geolocation"],
                        "java_script_enabled": True,
                        "ignore_https_errors": True,
                        "bypass_csp": True,
                    },
                    "playwright_page_methods": [
                        PageMethod("goto", url, wait_until="domcontentloaded", timeout=30000),  # Reduced initial timeout
                        PageMethod("wait_for_timeout", 2000),  # Wait for initial render
                        PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),  # Scroll to trigger lazy loading
                        PageMethod("wait_for_timeout", 2000),  # Wait for dynamic content
                        PageMethod("wait_for_selector", "div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs", timeout=30000, state="attached"),  # Relaxed selector wait
                        PageMethod("screenshot", path=f"screenshots/chevy_{uuid.uuid4()}.png", full_page=True),
                    ],
                    "playwright_page_event_handlers": {
                        "console": lambda msg: self.logger.info(f"Console: {msg.text}"),
                        "pageerror": lambda err: self.logger.error(f"Page error: {err}"),
                        "request": lambda req: self.logger.debug(f"Request: {req.url}"),
                        "response": lambda res: self.logger.debug(f"Response: {res.url} {res.status}"),
                        "requestfailed": lambda req: self.logger.error(f"Request failed: {req.url}"),
                    },
                    "cookiejar": 1,
                },
                errback=self.handle_error,
            )

    async def parse_exterior_response(self, response, model):
        self.logger.info(f"Processing exterior URL: {response.url}")
        localModel = copy.deepcopy(model)

        page = response.meta["playwright_page"]
        content = await page.content()
        self.logger.debug(f"Page content for {response.url}: {content[:1000]}...")

        extracted_data = []
        if not response.css("div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs"):
            self.logger.warning(f"Target div not found on {response.url}")
            # Attempt to extract data with fallback selector or log DOM state
            fallback_elements = response.css("div[class*='optionsContainer']")  # Broader selector
            if fallback_elements:
                self.logger.info(f"Fallback selector found {len(fallback_elements)} elements")
                for element in fallback_elements:
                    name = element.css("p[class*='title']::text").get(default="No name").strip()
                    price = element.css("div[class*='pricing']::text").get(default="No price").strip()
                    extracted_data.append({"name": name, "price": price})
        else:
            options = response.css("div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs div.configuratorControlPanelSectionOptionV1_container__tKC_W")
            for option in options:
                image_url = option.css("div.productImageV1_imageContainer__otCnJ img::attr(src)").get(default="No image")
                name = option.css("p.configuratorControlPanelSectionOptionV1_title__C78__::text").get(default="No name")
                price = option.css("div.imageSwatchPricing_pricing__HzkIR::text").get(default="No price")
                extracted_data.append({
                    "image_url": image_url,
                    "name": name.strip() if name else "No name",
                    "price": price.strip() if price else "No price",
                })
        localModel["exteriorColors"] = extracted_data
        self.logger.info(f"Extracted exterior data: {extracted_data}")

        await page.close()

        url = f"https://www.chevrolet.com/shopping/configurator/{localModel['bodyType']}/{localModel['year']}/{localModel['model']}/{localModel['bodyStyle']}/interior?buildCode=&radius=250&zipCode=48243"
        yield scrapy.Request(
            url=url,
            method="GET",
            headers=self.headers,
            callback=self.parse_interior_response,
            cb_kwargs={"model": localModel},
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_context": "default",
                "playwright_page_close": True,
                "playwright_context_kwargs": {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": self.headers["User-Agent"],
                    "locale": "en-US",
                    "timezone_id": "America/New_York",
                    "permissions": ["geolocation"],
                    "java_script_enabled": True,
                    "ignore_https_errors": True,
                    "bypass_csp": True,
                },
                "playwright_page_methods": [
                    PageMethod("goto", url, wait_until="domcontentloaded", timeout=30000),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("wait_for_selector", "div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs", timeout=30000, state="attached"),
                    PageMethod("screenshot", path=f"screenshots/chevy_{uuid.uuid4()}.png", full_page=True),
                ],
                "playwright_page_event_handlers": {
                    "console": lambda msg: self.logger.info(f"Console: {msg.text}"),
                    "pageerror": lambda err: self.logger.error(f"Page error: {err}"),
                    "request": lambda req: self.logger.debug(f"Request: {req.url}"),
                    "response": lambda res: self.logger.debug(f"Response: {res.url} {res.status}"),
                    "requestfailed": lambda req: self.logger.error(f"Request failed: {req.url}"),
                },
                "cookiejar": 1,
            },
            errback=self.handle_error,
        )

    async def parse_interior_response(self, response, model):
        self.logger.info(f"Processing interior URL: {response.url}")
        localModel = copy.deepcopy(model)

        page = response.meta["playwright_page"]
        content = await page.content()
        self.logger.debug(f"Page content for {response.url}: {content[:1000]}...")

        extracted_data = []
        if not response.css("div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs"):
            self.logger.warning(f"Target div not found on {response.url}")
            fallback_elements = response.css("div[class*='optionsContainer']")
            if fallback_elements:
                self.logger.info(f"Fallback selector found {len(fallback_elements)} elements")
                for element in fallback_elements:
                    name = element.css("p[class*='title']::text").get(default="No name").strip()
                    price = element.css("div[class*='pricing']::text").get(default="No price").strip()
                    extracted_data.append({"name": name, "price": price})
        else:
            options = response.css("div.configuratorControlPanelSectionOptionsV1_optionsContainer__wkZjs div.configuratorControlPanelSectionOptionV1_container__tKC_W")
            for option in options:
                image_url = option.css("div.productImageV1_imageContainer__otCnJ img::attr(src)").get(default="No image")
                name = option.css("p.configuratorControlPanelSectionOptionV1_title__C78__::text").get(default="No name")
                price = option.css("div.imageSwatchPricing_pricing__HzkIR::text").get(default="No price")
                extracted_data.append({
                    "image_url": image_url,
                    "name": name.strip() if name else "No name",
                    "price": price.strip() if price else "No price",
                })
        localModel["interiorColors"] = extracted_data
        self.logger.info(f"Extracted interior data: {extracted_data}")

        await page.close()

        url = f"https://www.chevrolet.com/shopping/configurator/{localModel['bodyType']}/{localModel['year']}/{localModel['model']}/{localModel['bodyStyle']}/options?buildCode=&radius=250&zipCode=48243"
        yield scrapy.Request(
            url=url,
            method="GET",
            headers=self.headers,
            callback=self.parse_packages_response,
            cb_kwargs={"model": localModel},
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_context": "default",
                "playwright_page_close": True,
                "playwright_context_kwargs": {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": self.headers["User-Agent"],
                    "locale": "en-US",
                    "timezone_id": "America/New_York",
                    "permissions": ["geolocation"],
                    "java_script_enabled": True,
                    "ignore_https_errors": True,
                    "bypass_csp": True,
                },
                "playwright_page_methods": [
                    PageMethod("goto", url, wait_until="domcontentloaded", timeout=30000),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_timeout", 2000),
                    PageMethod("wait_for_selector", "div#packages_options", timeout=30000, state="attached"),
                    PageMethod("screenshot", path=f"screenshots/chevy_{uuid.uuid4()}.png", full_page=True),
                ],
                "playwright_page_event_handlers": {
                    "console": lambda msg: self.logger.info(f"Console: {msg.text}"),
                    "pageerror": lambda err: self.logger.error(f"Page error: {err}"),
                    "request": lambda req: self.logger.debug(f"Request: {req.url}"),
                    "response": lambda res: self.logger.debug(f"Response: {res.url} {res.status}"),
                    "requestfailed": lambda req: self.logger.error(f"Request failed: {req.url}"),
                },
                "cookiejar": 1,
            },
            errback=self.handle_error,
        )

    async def parse_packages_response(self, response, model):
        self.logger.info(f"Processing packages URL: {response.url}")
        localModel = copy.deepcopy(model)

        page = response.meta["playwright_page"]
        content = await page.content()
        self.logger.debug(f"Page content for {response.url}: {content[:1000]}...")

        extracted_packages = []
        packages = response.css('#packages_options div.drp-grid-item')
        if not packages:
            self.logger.warning(f"No packages found on {response.url}")
            fallback_elements = response.css("div[class*='options']")
            if fallback_elements:
                self.logger.info(f"Fallback selector found {len(fallback_elements)} elements")
                for element in fallback_elements:
                    title = element.css("h6::text").get(default="No title").strip()
                    price = element.css("p[class*='pricing']::text").get(default="No price").strip()
                    extracted_packages.append({"title": title, "price": price})
        else:
            for package in packages:
                title = package.css('h6::text').get(default='No title').strip()
                options = [option.strip() for option in package.css('ul li div::text').getall()]
                price = package.css('p.configuratorProductCardFooterPricing_breakWord__nWBHl::text').get(default='No price').strip()
                extracted_packages.append({
                    'title': title,
                    'options': options,
                    'price': price
                })
        localModel['packages'] = extracted_packages
        self.logger.info(f"Extracted packages: {extracted_packages}")

        await page.close()

        # Yield the final enriched item
        item = ChevyItem()
        for key, value in localModel.items():
            item[key] = value
        yield item

    async def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure}")
        if failure.check(playwright._impl._errors.Error):
            self.logger.error(f"Playwright error: {failure.value}")
        if "playwright_page" in failure.request.meta:
            page = failure.request.meta["playwright_page"]
            content = await page.content()
            self.logger.debug(f"Error page content: {content[:1000]}...")
            await page.close()
