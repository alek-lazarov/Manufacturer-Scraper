import json
import re
import uuid

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy_playwright.page import PageMethod


class FordSpider(scrapy.Spider):
    name = 'ford_spider'
    start_urls = ['https://www.ford.com/fps/script/Ford/USA']
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cookie": 'selections=%7B%22modelYear%22%3Atrue%2C%22market%22%3A%5B%22Retail%22%2C%22Commercial%22%2C%22Future%22%2C%22None%22%5D%2C%22power%22%3A%7B%7D%2C%22style%22%3A%7B%7D%2C%22userSortSelection%22%3Anull%7D; bm_sv=92DB3DB8A1CCB767CE44157467C00D73~YAAQPElnaL6EVD2WAQAAbG3BYhtMOLCqeWB6HuS%2Bk7bh9ENZXn5JB2lD6WODKOkStl1vdW%2Bs0Nv9Pk3oZN946FwFBDEpUcJxzfiPWkUEXR1e6FriwCVzrQGZwYqlcuR3uKBVltcJfYXAXMEXqE9fn6AjQjDjOC5%2B7xGVGqSctVVHK8WcTf1Qb0f2%2Bm2KH7DOPwWSG2ZWsjbDIuMAxnq332oOEQ7XUrSOzWChcTSWeecwmnuieuu6aJ3%2FEOpMAA%3D%3D~1; onLoadNoDigData=true; gt_uid=3a6864ac-e62a-4b88-8ebe-e46788dfdbe9; s_ecid=MCMID%7C82362384599979082930326541690423558779; mbox=session#dbc23332b95d443bb6c3c518e4e91716#1737117834|PC#dbc23332b95d443bb6c3c518e4e91716.37_0#1800360774; fv_v54=v54|ui:rad:pc; fv_v1_v10=v8|search-natural; fv_v31_v40=v40|D=v8; fv_v41_v50=v42|logged out,v48|event: visit start,v49|search-natural; fv_entpg=entpg|fv:home; fv_refdom=refdom|www.google.com; s_fid=67BE96732E3BA88E-35F58D23D29E17B7; FPS_DTM_RVV-IMPRESS=T; userInfo=country_code=MK,region_code=,city=SKOPJE,county=,zip=; LPVID=czNjNlMGY1Yzc2YjFmODI2; OptanonAlertBoxClosed=2025-04-23T13:05:36.121Z; LPSID-87872012=bk174hV2RSqpAH2EO421Qg; FPI=make=Ford&html=false&model=Mustang&year=2024&zip=33444; regions=Marketing=Orlando&FDAF=FDAF-24B&LMDA=LMDAF-548&zip=33444&PACode=00206; AKA_A2=A; fma_YmFuYW5h=true; selections=%7B%22modelYear%22%3Atrue%2C%22market%22%3A%5B%22Retail%22%2C%22Future%22%2C%22None%22%5D%2C%22power%22%3A%7B%7D%2C%22style%22%3A%7B%7D%2C%22userSortSelection%22%3Anull%7D; bm_mi=1F031AE1E45A4744947A545C05BC0B17~YAAQh7UQArquenyWAQAA1entnxvS9mNzOX+bRq+5tIFZgDME5ejh8rQWAZGNu0uqKE1y1vmmL9tjVvHxdNlfhkjBehX4MrUp4qNeb7HM9DrRMe4CCXHbGiAPEz1iSrWExYEtO/qkoMdYtoDkwHYcXp3J40+hx3r8On+xvt+rLvMSIVAQIrGzdauVtcoQjrYe8l93WaTSHrvEj0G2dJQCnUOpCJNb9Pp2XM0TdE6zjbFwdHdBetX3YVcV+0ybD+lMO0EfE5kkRgWZMzcp2stwsLMf9pji5lXPDSsXOVmKS2xHV21C7pKPmDTfCDk=~1; bm_sz=F0AF4518F3C2EB418BD4C4237A4D2F73~YAAQh7UQAryuenyWAQAA1entnxtIxP+YUc7FYporBcAQ4TeGRfrMwFdbYFRNz9KZ81cW3y9F2gB63rGUHly2mVq4MEiIlCD6BVY4bHyV17+SvZt2CUdpA1z9G5Se3u9h0CUVSEbi/jDo7RkXHfkNfMkJ1zKsk0yUbUaSa9MF87/XAUQa8P/F7fya2rlACIPMv0qk7wr0+vqXNikX6h6w59SJD1yG9iWOh+/fsSfl1lagke0nCQbsZX9j2nDUppp1EHwn2Nx+OgAwtDv+bc6dNrscPFwp2W0Q7fVB93HSZBGgx3Ik04v7FNm6phKXzYo2Hr00PS6zF9qrNKhomCCuCj4FPNVw3WQmC7I2xFnVJgS2HPascCrhqjI2N6AAAT02S/R4IOXA8+Lty2VEbZElRw==~3621942~4473140; _abck=4FE6CC3D19DAD3D2FC7741B73BFC8CE6~0~YAAQh7UQAu+uenyWAQAAB+ztnw0gDdL398yEOFuWL2/86cMIhQfR2A7n6N4T9Lggve50kbay1GuW+r4kkqEPKUJ5EnYLXZyDd0313CrrFbANRimvEQqlynBD95cGmPQ/+qbRNN/wn95c7D5dSeMX9GkXR7QZyKTnaIaDoawy3ZsaDTpalicE+sTa5kBhJMXC//2arUDJ6CQ4n3G4FfOVuZgnGZzXKjZwzUuhCHcZdNWRRF1Wal1XxlsUyfd87a3pRzPKE1FlmGPMmNSpOzoj5A6eAgPRE+ip7o1iAzxkhMMKF37IR5ykqh5UdffEdN389pwbPT4Y76sSt5nlGGYfSM4X4eJzisd4XVi4NuRwKmyOw23Pre6W+32u/q7F7ED8/SHDiGK6RvIZwgwN8azzEiw5nAm4kZbpCngGcXRpTtMzGemBHtnQTc1LnH2tt7y5QrwR5bu26ZwrJ4ove1uMqEEcOaMbUmPvCP/ss7c6hdtp5t/aYRKCQU3r+WXtPioJrazanY36yhJaukdzC0Y7+vlAB5LUzzBFU9Y=~-1~-1~-1; ak_bmsc=B978C90DD709495887C980889FEBB37D~000000000000000000000000000000~YAAQh7UQAkGvenyWAQAAiu/tnxt3NuJuj5Ksfz50tK5JGJ7t/l4EQ+WSYGKRWypitrv93mv1ZyuA2vulb9af+24tGjrt4BoAit9k2SOIVILeo7R3zLQR/fEtykfmw/Ou4yfnLZCJVUmALmkVSd8fTCN8TIsZGvW4MupPowScbBm3Vd7h9nY5C9s8hX0ynIQIgb7/46tZ1lO/YGoOij95zlwVBJfxlZg3suqgNcbyfCfwsmuLmzF+mB0IOo/1X6e33GpigD1XM0aOhZ31/hzuBkx8IlmoQ+Rc3FXWh561QZQXUgX7RP8CEDK8zuASSoddnqbzl5Q26rV7tQ31OSTZUUi2fByTLWBpeRmX66VzcEQVmpvtM5G3+0jR14sc0b6xlWSzOzr9COC5N+b3JuPc0h4vuvggbKUAQ3GOAj2gHSQtw5KSE7kTKKiw1cgqV0gLWv1NLtl5NShdZ4FgpCIUkrX8w7Xpw+Djt+cjqqU=; loginStatus=logged out; OptanonConsent=isGpcEnabled=0&datestamp=Mon+May+05+2025+12%3A14%3A23+GMT%2B0200+(Central+European+Summer+Time)&version=202502.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=8b19c206-94a4-45d0-b3cc-01681a05faf2&interactionCount=2&landingPath=NotLandingPage&groups=BG114%3A0%2C2%3A0%2C4%3A0%2C6%3A0%2CBG115%3A1%2C1%3A1%2C3%3A1&AwaitingReconsent=false&isAnonUser=1&intType=3&geolocation=MK%3B; bm_sv=719E22040F2507D581E9D238B8713FD3~YAAQRUx1aFOi0YaWAQAAJZHwnxtpYrUPcqAq9re5W+suLrKBJMeIRvjuM2PRxXOOMPD4QJueDSH1J03GE5qlMsttkDEMXf2QblUXOTGjSQt5h6ZL9rHQUDXBQdb5VXcZS3gDYd+LWXCEe03bVnra33uca6R8Z+vzaX8xCubQjWK1EcEnvCmc6AaisIe9YFqrufd6rtIMKYPq8/klaGyI50Eps71ruswP9AbGlYx65MPHn/AlSw83Npwm3lV7gH4=~1; RT="z=1&dm=shop.ford.com&si=b842e21d-842f-485f-8e41-911817ffff38&ss=maax7x0m&sl=4&tt=3qv&bcn=%2F%2F02179916.akstat.io%2F&ld=3phr&ul=3t0p"'
    }
    def start_requests(self):
        url = 'https://shop.ford.com/showroom?linktype=build'
        self.logger.info("Parse start called")
        yield scrapy.Request(
            url=url,
            method='GET',
            callback=self.parse_initial,
            meta={"cookiejar": 1,
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
                      PageMethod("screenshot", path=f"screenshots/chevy_{uuid.uuid4()}.png", full_page=True),
                  ]},
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.ford.com/'
            }
        )

    async def parse_initial(self, response):
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
