import scrapy
import json
import re
from datetime import datetime
from urllib.parse import urlparse

class ScrapyExclusiveSpider(scrapy.Spider):
    name = "ddcContent"
    start_urls = [
        'https://www.napletononnorthlake.com/new-inventory/index.htm',
        'https://www.napletonacura.com/new-inventory/index.htm',
    ]

    def start_requests(self):
        for start_url in self.start_urls:
            yield scrapy.Request(
                start_url,
                callback=self.parse_initial_request,
                errback=self.errback_httpbin
            )

    def parse_initial_request(self, response):
        script_data = response.xpath('//div[contains(@class, "tracking-ddc-data-layer")]/script/text()').get()
        script_data = script_data.split("DDC.dataLayer['vehicles'] = ")[1]
        script_data = script_data.split(";\nDDC.dataLayer['confirmation']")[0]
        script_data = re.sub(r'(?<=\w)\\-(?=\w)', '-', script_data)
        script_data = re.sub(r'(?<=\w)\\x(?=\w)', '-', script_data)
        script_data = json.loads(script_data)

        total_pages = response.xpath('//ul[contains(@class, "pagination")]//a[@data-total-items]/@data-total-items').get()
        #yield self.get_data(response)
        data = response.xpath('//ul[contains(@class, "inventoryList")]/li[contains(@class, "item")]')
        key = -1
        for vehicle in data:
            key += 1
            yield self.get_data(response, vehicle, script_data[key])

        if int(total_pages) > 1:
            offset = int(response.xpath('//ul[contains(@class, "pagination")]//a[@data-total-items]/@href').get().replace('?start=', '').replace('&', ''))
            limit = offset
            for page in range(1, int(total_pages)):
                next_page = response.url + f"?start={offset}"
                yield scrapy.Request(
                    next_page,
                    callback=self.parse,
                    errback=self.errback_httpbin
                )
                offset += limit

    def parse(self, response):
        script_data = response.xpath('//div[contains(@class, "tracking-ddc-data-layer")]/script/text()').get()
        script_data = script_data.split("DDC.dataLayer['vehicles'] = ")[1]
        script_data = script_data.split(";\nDDC.dataLayer['confirmation']")[0]
        script_data = re.sub(r'(?<=\w)\\-(?=\w)', '-', script_data)
        script_data = re.sub(r'(?<=\w)\\x(?=\w)', '-', script_data)
        script_data = json.loads(script_data)
        #yield self.get_data(response)
        data = response.xpath('//ul[contains(@class, "inventoryList")]/li[contains(@class, "item")]')
        key = -1
        for vehicle in data:
            key += 1
            yield self.get_data(response, vehicle, script_data[key])

    def get_data(self,response,vehicle,script_data):
        #data = response.xpath('//ul[contains(@class, "inventoryList")]/li[contains(@class, "item")]')
        #for vehicle in data:
        msrp = ''
        city_mpg = ''
        hw_mpg = ''
        hproduct = vehicle.xpath('./div[contains(@class, "hproduct")]')
        make = hproduct.xpath('./@data-make').get()
        model = hproduct.xpath('./@data-model').get()
        trim = hproduct.xpath('./@data-trim').get()
        year = hproduct.xpath('./@data-year').get()
        vin = hproduct.xpath('./@data-vin').get()
        body_style = hproduct.xpath('./@data-bodystyle').get()
        ext_color = hproduct.xpath('./@data-exteriorcolor').get()
        image = hproduct.xpath('.//div[@class="media"]/a/img/@data-src').get()
        if not image:
            image = hproduct.xpath('.//div[@class="media"]/a/img/@src').get()
        if (hproduct.xpath('.//span[contains(@class, "final-price")]/span[@class="value"]/text()').get()):
            msrp = hproduct.xpath('.//span[contains(@class, "final-price")]/span[@class="value"]/text()').get().replace('$', "").replace(',', "")
        description = hproduct.xpath('.//div[@class="description"]')
        engine = description.xpath('//dt[contains(.,"Engine")]/following-sibling::dd/text()').get()
        transmission = description.xpath('//dt[contains(.,"Transmission")]/following-sibling::dd/text()').get()
        if (description.xpath('//dt[contains(.,"MPG Range")]/following-sibling::dd/text()').get()):
            mpg = description.xpath('//dt[contains(.,"MPG Range")]/following-sibling::dd/text()').get().split('/')
            city_mpg = mpg[0]
            hw_mpg = mpg[1]
        drive_type = description.xpath('//dt[contains(.,"Drive Line")]/following-sibling::dd/text()').get() or ""
        int_color = description.xpath('//dt[contains(.,"Interior Color")]/following-sibling::dd/text()').get()
        doors = script_data['doors']
        if doors == 'null': doors = ""

        parsed_url = urlparse(response.url)
        source = parsed_url.netloc.replace('www.', '')
        link = parsed_url.scheme + '://' + parsed_url.netloc + hproduct.xpath('//a[@class="url"]/@href').get()

        return {
            "Make": make,
            "Model": model,
            "Trim": trim,
            "Year": str(year),
            "VIN": vin,
            "MSRP": str(msrp),
            "FuelType": script_data['normalFuelType'],
            "BodyStyle": body_style,
            "Engine": engine,
            "Transmission": transmission,
            "ExteriorColor": ext_color,
            "ExteriorColorGeneric": "",
            "InteriorColor": int_color,
            "InteriorColorGeneric": "",
            "DriveTrain": drive_type,
            "NumberOfDoors": str(doors),
            "CityMPG": str(city_mpg),
            "HighwayMPG": str(hw_mpg),
            "Features": script_data['features'],
            "Image": image,
            "Link": link,
            "Source": source,
            "CollectedFrom": 'HTML DDC Content',
            "Style": trim
        }

    def errback_httpbin(self, failure):
        #repr(failure)
        self.write_to_log(failure.request.url)

    def write_to_log(self, url):
        time = datetime.now()
        time = time.strftime("%Y-%m-%d %H:%M:%S")
        with open('failed_urls.log', mode='a') as file:
            file.write(time + " - " + url + "\n")
