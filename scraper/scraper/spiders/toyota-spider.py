import copy
import json
from datetime import datetime

import scrapy
from scrapy import Request
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings


class ToyotaSpider(scrapy.Spider):
    name = 'toyota'
    url = "https://orchestrator.configurator.toyota.com/graphql"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime('%Y-%m-%d %H-%M-%S')
    filepath = f"Manufacturer_Crawlers/output/toyota_{formatted_datetime}.csv"

    custom_settings = {
        "FEED_FORMAT": "csv",
        "FEED_URI": filepath,
        "FEED_EXPORT_FIELDS": [
            "make",
            "model",
            "year",
            "exteriorColors",
            "interiorColors",
            "driveType",
            "transmissionType",
            "bodyType",
            "fuelType",
            "trim",
            "url",
            "packages",
            "cabType",  # Crew Cab ,  Regular Cab, Extended Cab
            "bedLength"  # Short Bed  ( < 6ft) , Standard Bed ( 6ft > x < 8ft ), Long Bed   ( > 8ft ),
        ]
    }

    def start_requests(self):
        body = self.construct_models_request()
        json_body = json.dumps(body)
        yield scrapy.Request(
            self.url,
            method='POST',
            body=json_body,
            headers=self.headers,
            callback=self.parse_models
        )

    def parse_models(self, response):
        makes_response = json.loads(response.text)

        for model in makes_response['data']['getSeries']['seriesData']:
            for year in model['yearSpecificData']:
                localModel = {
                    "make": "Toyota",
                    "model": model['name'],
                    "year": year['year'],
                    'exteriorColors': [],
                    'interiorColors': [],
                    'driveType': "",
                    'transmissionType': "",
                    'bodyType': "",
                    'fuelType': "",
                    'trim': "",
                    'url': "",
                    'packages': "",
                    'cabType': "",
                    'bedLength': ""
                }
                body = self.construct_trims_request(model['id'], year['year'])
                json_body = json.dumps(body)
                yield scrapy.Request(
                    self.url,
                    method='POST',
                    body=json_body,
                    headers=self.headers,
                    callback=self.parse_all_trims,
                    cb_kwargs={'model': localModel, 'seriesId': model['id'], 'year': year['year']}
                )

    def parse_all_trims(self, response, model, seriesId, year):
        trims_response = json.loads(response.text)
        for seriesData in trims_response['data']['getSeries']['seriesData']:
            for yearData in seriesData['yearSpecificData']:
                for grade in yearData['grades']:
                    localModel = copy.deepcopy(model)
                    localModel['trim'] = grade['gradeName']
                    body = self.construct_trim_request(seriesId, year, grade['gradeName'])
                    json_body = json.dumps(body)
                    localModel['url'] = grade['image']['url'] if grade['image'] else ""
                    yield scrapy.Request(
                        self.url,
                        method='POST',
                        body=json_body,
                        headers=self.headers,
                        callback=self.parse_trim,
                        cb_kwargs={'model': localModel}
                    )
        yield {}

    def parse_trim(self, response, model):  # packages in build
        localModel = copy.deepcopy(model)

        trim_response = json.loads(response.text)
        config_data = trim_response.get('data', {}).get('getConfigByGrade', {})

        # Extract exterior colors
        for exteriorColor in config_data.get('exteriorColors', []):
            localModel['exteriorColors'].append({
                "name": exteriorColor.get('title', ''),
                "price": exteriorColor.get('msrp', {}).get('value', ''),
                "hex": exteriorColor.get('hexCode', [''])[0] if exteriorColor.get('hexCode') else '',
            })

        # Extract interior colors
        for interiorColors in config_data.get('interiorColors', []):
            localModel['interiorColors'].append({
                "name": interiorColors.get('name', ''),
                "price": interiorColors.get('msrp', {}).get('value', ''),
                "hex": interiorColors.get('hexCode', [''])[0] if interiorColors.get('hexCode') else '',
            })

        # Extract MSRP
        grade_data = config_data.get('grade', {})
        localModel['msrp'] = grade_data.get('baseMsrp', {}).get('value', '')

        # Extract body type
        for bodyType in config_data.get('categories', []):
            localModel['bodyType'] = bodyType.get('value', '')
            break  # Just take the first one

        # Extract packages with detailed information
        package_details = []
        # Process packages from trims directly, including the MSRP
        for trim in grade_data.get('trims', []):
            # packageIds is a list of dictionaries with 'id' and 'msrp' keys
            for package in trim.get('packageIds', []):
                if isinstance(package, dict) and 'id' in package:
                    package_id = package.get('id', '')
                    # Get MSRP directly from the packageIds array
                    package_msrp = package.get('msrp', {}).get('value', '')

                    # Find the matching package in packages data to get description
                    package_title = ""
                    package_description = ""
                    for pkg in config_data.get('packages', []):
                        if pkg.get('id') == package_id:
                            package_title = pkg.get('title', '')
                            package_description = pkg.get('description', '')
                            break

                    package_details.append({
                        'id': package_id,
                        'description': package_description,
                        'title': package_title,
                        'msrp': package_msrp
                    })

        # Serialize package details to JSON string
        localModel['packages'] = json.dumps(package_details) if package_details else ""

        # Extract other vehicle details
        for trim in grade_data.get('trims', []):
            localModel['fuelType'] = trim.get('fuelType', '')

            # Extract powertrain details
            powertrain = trim.get('powertrain', {})
            if powertrain:
                drive = powertrain.get('drive', {})
                if drive:
                    localModel['driveType'] = drive.get('value', '')

            localModel['transmissionType'] = "Automatic"  # Default as per original code

            # Extract cab and bed information
            cab_bed = trim.get('cabBed')
            if cab_bed:
                localModel['bedLength'] = cab_bed.get('bedLength', '')
                localModel['cabType'] = cab_bed.get('description', '')

            yield localModel
            # Break after first trim since we've captured the information
            break

    def construct_models_request(self):
        return {
            "query": "query GetSeries($brand: Brand!, $language: Language, $region: Region!, $seriesId: String, $showApplicableSeriesForVisualizer: Boolean, $year: Int) {  getSeries(    brand: $brand    language: $language    region: $region    seriesId: $seriesId    showApplicableSeriesForVisualizer: $showApplicableSeriesForVisualizer    year: $year  ) {    seriesData {      id      name      shortName      yearSpecificData {        year        startingMsrp {          disclaimer          value        }        mileage {          category          city          combined          highway          isAvailable          mpge          range        }        seating        categories {          id          value        }        grades {          gradeName          trims {            code            fuelType            powertrain {              drive {                description                disclaimer                icon                value              }              engine {                description                disclaimer                icon                value              }              horsepower {                description                disclaimer                icon                value              }              transmission {                description                disclaimer                icon                value              }            }          }        }      }    }  }}",
            "variables": {
                "brand": "TOYOTA",
                "language": "EN",
                "region": {"zipCode": "33444"},
            }
        }

    def construct_trims_request(self, seriesId, year):
        return {
            "query": "query GetSeries($brand: Brand!, $language: Language, $region: Region!, $seriesId: String, $showApplicableSeriesForVisualizer: Boolean, $year: Int) {\n  getSeries(\n    brand: $brand\n    language: $language\n    region: $region\n    seriesId: $seriesId\n    showApplicableSeriesForVisualizer: $showApplicableSeriesForVisualizer\n    year: $year\n  ) {\n    exteriorColors {\n      code\n      hexCode\n      id\n    }\n    seriesData {\n      name\n      yearSpecificData {\n        grades {\n          exteriorColorIds\n          gradeName\n          image {\n            alias\n            disclaimer\n            isHero\n            url\n          }\n          mileage {\n            category\n            city\n            combined\n            highway\n            isAvailable\n            mpge\n            range\n          }\n          trims {\n            cabBed {\n              bedDepth\n              bedLength\n              bedWidth\n              betweenWheelWell\n              cabDetails\n              compatibilityWithCurrentConfig {\n                availableWithTrims\n                isCompatible\n                requiredItems {\n                  itemCode\n                  itemType\n                }\n              }\n              description\n              id\n              label\n              overallHeight\n              overallLength\n              overallWidth\n              cabDescription\n              bedDescription\n            }\n            code\n            defaultConfig {\n              msrp {\n                disclaimer\n                value\n              }\n            }\n            isDefaultTrim\n            images {\n              url\n            }\n            mileage {\n              category\n              city\n              combined\n              highway\n              isAvailable\n              mpge\n              range\n            }\n            msrp {\n              value\n            }\n            powertrain {\n              drive {\n                value\n              }\n              engine {\n                value\n              }\n              transmission {\n                value\n              }\n            }\n            seating {\n              value\n            }\n          }\n        }\n        year\n      }\n    }\n  }\n}\n",
            "variables": {
                "brand": "TOYOTA",
                "language": "EN",
                "region": {"zipCode": "33444"},
                "seriesId": seriesId,
                "showApplicableSeriesForVisualizer": True,
                "year": year
            },
        }

    def construct_trim_request(self, seriesId, year, gradeName):
        return {
            "query": "query GetConfigByGrade($configInputGrade: ConfigInputGrade!) {\n  getConfigByGrade(configInputGrade: $configInputGrade) {\n    accessories {\n      code\n      compatibilityWithCurrentConfig {\n        availableWithTrims\n        isCompatible\n        requiredItems {\n          itemCode\n          itemType\n        }\n      }\n      description\n      disclaimer\n      id\n      images {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      includedAccessoryIds\n      installPoint\n      title\n      type\n      warranty\n    }\n    categories {\n      id\n      value\n    }\n    configImages {\n      exterior {\n        alias\n        disclaimer\n        url\n        ... on AccessoryImage {\n          isHero\n        }\n        ... on LexusImage {\n          angle\n          background\n          time\n        }\n        ... on StaticImage {\n          isHero\n        }\n        ... on ToyotaImage {\n          angle\n        }\n      }\n      interior {\n        alias\n        disclaimer\n        url\n        ... on AccessoryImage {\n          isHero\n        }\n        ... on LexusImage {\n          angle\n          background\n          time\n        }\n        ... on StaticImage {\n          isHero\n        }\n        ... on ToyotaImage {\n          angle\n        }\n      }\n      ... on LexusConfigImages {\n        backgrounds {\n          thumbnail\n          type\n        }\n        time {\n          icon\n          type\n        }\n      }\n      ... on ToyotaConfigImages {\n        background {\n          alias\n          angle\n          disclaimer\n          url\n        }\n      }\n    }\n    defaultConfig {\n      accessoryIds\n      exteriorColorId\n      interiorColorId\n      packageIds\n      trimId\n      wheelsId\n    }\n    dph\n    exteriorColors {\n      code\n      colorFamilies {\n        hexCode\n        name\n      }\n      compatibilityWithCurrentConfig {\n        availableWithTrims\n        isCompatible\n        requiredItems {\n          itemCode\n          itemType\n        }\n      }\n      hexCode\n      id\n      images {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      isExtraCostColor\n      msrp {\n        disclaimer\n        value\n      }\n      title\n    }\n    grade {\n      asShownPrice {\n        disclaimer\n        value\n      }\n      baseMsrp {\n        disclaimer\n        value\n      }\n      exteriorColorIds\n      gradeName\n      hasSeatingOptions\n      image {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      interiorColorIds\n      mileage {\n        category\n        city\n        combined\n        highway\n        isAvailable\n        mpge\n        range\n      }\n      trims {\n        accessoryIds {\n          id\n          msrp {\n            disclaimer\n            value\n          }\n        }\n        cabBed {\n          bedDepth\n          bedLength\n          bedWidth\n          betweenWheelWell\n          cabDetails\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          id\n          label\n          overallHeight\n          overallLength\n          overallWidth\n        }\n        code\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        defaultColorId\n        description\n        drive {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        engine {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        exteriorColorIds\n        fuelType\n        horsepower {\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        images {\n          alias\n          disclaimer\n          isHero\n          url\n        }\n        interiorColorIds\n        isDefaultTrim\n        mileage {\n          category\n          city\n          combined\n          highway\n          isAvailable\n          mpge\n          range\n        }\n        msrp {\n          disclaimer\n          value\n        }\n        packageIds {\n          id\n          msrp {\n            disclaimer\n            value\n          }\n        }\n        powertrain {\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          drive {\n            code\n            compatibilityWithCurrentConfig {\n              availableWithTrims\n              isCompatible\n              requiredItems {\n                itemCode\n                itemType\n              }\n            }\n            description\n            disclaimer\n            icon\n            value\n          }\n          engine {\n            code\n            compatibilityWithCurrentConfig {\n              availableWithTrims\n              isCompatible\n              requiredItems {\n                itemCode\n                itemType\n              }\n            }\n            description\n            disclaimer\n            icon\n            value\n          }\n          horsepower {\n            compatibilityWithCurrentConfig {\n              availableWithTrims\n              isCompatible\n              requiredItems {\n                itemCode\n                itemType\n              }\n            }\n            description\n            disclaimer\n            icon\n            value\n          }\n          transmission {\n            code\n            compatibilityWithCurrentConfig {\n              availableWithTrims\n              isCompatible\n              requiredItems {\n                itemCode\n                itemType\n              }\n            }\n            description\n            disclaimer\n            icon\n            value\n          }\n        }\n        seating {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        shortDescription\n        title\n        transmission {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        warrantyIds\n        wheelCodes\n      }\n    }\n    interiorColors {\n      code\n      colorFamilies {\n        hexCode\n        name\n      }\n      compatibilityWithCurrentConfig {\n        availableWithTrims\n        isCompatible\n        requiredItems {\n          itemCode\n          itemType\n        }\n      }\n      hexCode\n      id\n      images {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      material\n      msrp {\n        disclaimer\n        value\n      }\n      name\n      title\n    }\n    mileage {\n      category\n      city\n      combined\n      highway\n      isAvailable\n      mpge\n      range\n    }\n    msrp {\n      disclaimer\n      value\n    }\n    packages {\n      availability\n      category\n      code\n      compatibilityWithCurrentConfig {\n        availableWithTrims\n        isCompatible\n        requiredItems {\n          itemCode\n          itemType\n        }\n      }\n      description\n      id\n      images {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      installPoint\n      packageFeatures {\n        category\n        disclaimer\n        subCategories\n        title\n      }\n      subCategories\n      title\n      type\n    }\n    seating\n    seriesId\n    seriesName\n    trim {\n      accessoryIds {\n        id\n        msrp {\n          disclaimer\n          value\n        }\n      }\n      cabBed {\n        bedDepth\n        bedLength\n        bedWidth\n        betweenWheelWell\n        cabDetails\n        code\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        description\n        id\n        label\n        overallHeight\n        overallLength\n        overallWidth\n      }\n      code\n      compatibilityWithCurrentConfig {\n        availableWithTrims\n        isCompatible\n        requiredItems {\n          itemCode\n          itemType\n        }\n      }\n      defaultColorId\n      description\n      drive {\n        code\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        description\n        disclaimer\n        icon\n        value\n      }\n      engine {\n        code\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        description\n        disclaimer\n        icon\n        value\n      }\n      exteriorColorIds\n      fuelType\n      horsepower {\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        description\n        disclaimer\n        icon\n        value\n      }\n      images {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      interiorColorIds\n      isDefaultTrim\n      mileage {\n        category\n        city\n        combined\n        highway\n        isAvailable\n        mpge\n        range\n      }\n      msrp {\n        disclaimer\n        value\n      }\n      packageIds {\n        id\n        msrp {\n          disclaimer\n          value\n        }\n      }\n      powertrain {\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        drive {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        engine {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        horsepower {\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n        transmission {\n          code\n          compatibilityWithCurrentConfig {\n            availableWithTrims\n            isCompatible\n            requiredItems {\n              itemCode\n              itemType\n            }\n          }\n          description\n          disclaimer\n          icon\n          value\n        }\n      }\n      seating {\n        code\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        description\n        disclaimer\n        icon\n        value\n      }\n      shortDescription\n      title\n      transmission {\n        code\n        compatibilityWithCurrentConfig {\n          availableWithTrims\n          isCompatible\n          requiredItems {\n            itemCode\n            itemType\n          }\n        }\n        description\n        disclaimer\n        icon\n        value\n      }\n      warrantyIds\n      wheelCodes\n    }\n    warranties {\n      category\n      description\n      id\n      name\n      value\n    }\n    wheels {\n      code\n      compatibilityWithCurrentConfig {\n        availableWithTrims\n        isCompatible\n        requiredItems {\n          itemCode\n          itemType\n        }\n      }\n      image {\n        alias\n        disclaimer\n        isHero\n        url\n      }\n      title\n      type\n      ... on OptionWheel {\n        msrp {\n          disclaimer\n          value\n        }\n      }\n    }\n    year\n  }\n}\n",
            "variables": {
                "configInputGrade": {
                    "brand": "TOYOTA",
                    "language": "EN",
                    "region": {"zipCode": "33444"},
                    "seriesId": seriesId,
                    "year": year,
                    "gradeName": gradeName
                }
            },
        }


settings = Settings()

settings.set("USER_AGENT",
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

settings.set("DOWNLOADER_MIDDLEWARES", {
    "scraper.scraper.middlewares.ProxyMiddleware": 543,
})

# settings.set("FEED_URI", 'output.csv')
# settings.set("FEED_FORMAT", 'csv')

# settings.set("TWISTED_REACTOR", "twisted.internet.asyncioreactor.AsyncioSelectorReactor")

process = CrawlerProcess(settings)
process.crawl(ToyotaSpider)
process.start()




