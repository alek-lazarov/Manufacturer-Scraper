import copy
import json
import os
from datetime import datetime

import scrapy
from scrapy.crawler import CrawlerProcess


class ToyotaSpider(scrapy.Spider):
    name = 'toyota'
    url = "https://orchestrator.configurator.toyota.com/graphql"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'bap-guid': '692c6b8b-ae4a-4c46-8c71-c05abbaedff9',
    }

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime('%Y-%m-%d_%H-%M-%S')
    filepath = f"output/toyota_{formatted_datetime}.csv"

    custom_settings = {
        "FEEDS": {
            filepath: {
                "format": "csv",
                "fields": [
                    "make", "model", "year", "trim", "msrp", "exteriorColors", "interiorColors",
                    "driveType", "transmissionType", "engineType", "fuelType", "bodyType", "cabType",
                    "bedLength", "packages", "url"
                ],
            },
        },
        "DOWNLOAD_DELAY": 1.5,
        "LOG_LEVEL": "INFO",
        "CONCURRENT_REQUESTS": 4,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [403, 429, 500, 502, 503, 504],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        self.logger.info(f"Output will be saved to: {self.filepath}")

    def start_requests(self):
        body = {
            "query": """
                query GetSeries($brand: Brand!, $language: Language, $region: Region!) {
                    getSeries(brand: $brand, language: $language, region: $region) {
                        seriesData {
                            id
                            name
                            yearSpecificData {
                                year
                            }
                        }
                    }
                }
            """,
            "variables": {
                "brand": "TOYOTA",
                "language": "EN",
                "region": {"zipCode": "33444"}
            }
        }
        yield scrapy.Request(
            url=self.url,
            method='POST',
            body=json.dumps(body),
            headers=self.headers,
            callback=self.parse_series
        )

    def parse_series(self, response):
        try:
            data = json.loads(response.text)
            if 'errors' in data:
                self.logger.error(f"API errors in series request: {data['errors']}")
                return

            series_data = data.get('data', {}).get('getSeries', {}).get('seriesData', [])
            self.logger.info(f"Found {len(series_data)} vehicle series")

            for series in series_data:
                series_id = series.get('id')
                series_name = series.get('name')

                for year_data in series.get('yearSpecificData', []):
                    year = int(year_data.get('year', 0))
                    if year == 0:
                        continue

                    self.logger.info(f"Processing {series_name} {year}")

                    # Create base model info
                    model = {
                        "make": "Toyota",
                        "model": series_name,
                        "year": year
                    }

                    # Request grades and trims data
                    body = {
                        "query": """
                            query GetSeries($brand: Brand!, $seriesId: String!, $year: Int!, $language: Language, $region: Region!) {
                                getSeries(brand: $brand, seriesId: $seriesId, year: $year, language: $language, region: $region) {
                                    seriesData {
                                        yearSpecificData {
                                            grades {
                                                gradeName
                                                image {
                                                    url
                                                }
                                                trims {
                                                    code
                                                    msrp {
                                                        value
                                                    }
                                                    defaultConfig {
                                                        msrp {
                                                            value
                                                        }
                                                    }
                                                    cabBed {
                                                        bedLength
                                                        label
                                                        description
                                                    }
                                                    powertrain {
                                                        drive {
                                                            value
                                                        }
                                                        engine {
                                                            value
                                                        }
                                                        transmission {
                                                            value
                                                        }
                                                    }
                                                    fuelType
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        """,
                        "variables": {
                            "brand": "TOYOTA",
                            "language": "EN",
                            "region": {"zipCode": "33444"},
                            "seriesId": series_id,
                            "year": year
                        }
                    }

                    yield scrapy.Request(
                        url=self.url,
                        method='POST',
                        body=json.dumps(body),
                        headers=self.headers,
                        callback=self.parse_trims_directly,
                        cb_kwargs={'model': model, 'series_id': series_id}
                    )
        except Exception as e:
            self.logger.error(f"Error parsing series: {str(e)}", exc_info=True)

    def parse_trims_directly(self, response, model, series_id):
        try:
            data = json.loads(response.text)
            if 'errors' in data:
                self.logger.error(f"API errors in trims request: {data['errors']}")
                return

            # Find all trims across all grades
            year_data = \
            data.get('data', {}).get('getSeries', {}).get('seriesData', [{}])[0].get('yearSpecificData', [{}])[0]

            for grade in year_data.get('grades', []):
                if grade is None:
                    continue

                grade_name = grade.get('gradeName', '')

                # Fix for the NoneType error - properly handle image extraction
                grade_image_url = ''
                image = grade.get('image')
                if image is not None:
                    grade_image_url = image.get('url', '')

                self.logger.info(f"Processing grade: {grade_name}")

                # Now get detailed information for colors and packages
                # FIXED QUERY: Removed the invalid msrp field from packages
                body = {
                    "query": """
                        query GetConfigByGrade($configInputGrade: ConfigInputGrade!) {
                            getConfigByGrade(configInputGrade: $configInputGrade) {
                                exteriorColors {
                                    title
                                    msrp { value }
                                    hexCode
                                }
                                interiorColors {
                                    name
                                    msrp { value }
                                    hexCode
                                }
                                categories {
                                    value
                                }
                                packages {
                                    id
                                    title
                                    description
                                }
                            }
                        }
                    """,
                    "variables": {
                        "configInputGrade": {
                            "brand": "TOYOTA",
                            "language": "EN",
                            "region": {"zipCode": "33444"},
                            "seriesId": series_id,
                            "year": model['year'],
                            "gradeName": grade_name
                        }
                    }
                }

                # Process each trim within this grade now
                trims = grade.get('trims', [])
                self.logger.info(f"Found {len(trims)} trims for {grade_name}")

                if trims:
                    yield scrapy.Request(
                        url=self.url,
                        method='POST',
                        body=json.dumps(body),
                        headers=self.headers,
                        callback=self.parse_colors_packages,
                        cb_kwargs={
                            'base_model': model,
                            'grade_name': grade_name,
                            'grade_image_url': grade_image_url,
                            'trims': trims
                        }
                    )

        except Exception as e:
            self.logger.error(f"Error parsing trims directly: {str(e)}", exc_info=True)

    def parse_colors_packages(self, response, base_model, grade_name, grade_image_url, trims):
        try:
            data = json.loads(response.text)
            if 'errors' in data:
                self.logger.error(f"API errors in colors/packages request: {data['errors']}")
                return

            config = data.get('data', {}).get('getConfigByGrade', {})

            # Extract common data (colors, packages, body type)
            exterior_colors = []
            for c in config.get('exteriorColors', []):
                if c is None:
                    continue

                color_info = {
                    "name": c.get('title', ''),
                    "price": c.get('msrp', {}).get('value', ''),
                    "hex": ""
                }

                # Safely extract hex code
                if c.get('hexCode'):
                    hex_code = c.get('hexCode')
                    if isinstance(hex_code, list) and len(hex_code) > 0:
                        color_info["hex"] = hex_code[0]

                exterior_colors.append(color_info)

            interior_colors = []
            for c in config.get('interiorColors', []):
                if c is None:
                    continue

                color_info = {
                    "name": c.get('name', ''),
                    "price": c.get('msrp', {}).get('value', ''),
                    "hex": ""
                }

                # Safely extract hex code
                if c.get('hexCode'):
                    hex_code = c.get('hexCode')
                    if isinstance(hex_code, list) and len(hex_code) > 0:
                        color_info["hex"] = hex_code[0]

                interior_colors.append(color_info)

            categories = config.get('categories', [])
            body_type = ""
            if categories and len(categories) > 0:
                body_type = categories[0].get('value', '')

            # Fixed package extraction without msrp field
            all_packages = []
            for p in config.get('packages', []):
                if p is None:
                    continue

                all_packages.append({
                    'id': p.get('id', ''),
                    'title': p.get('title', ''),
                    'description': p.get('description', '')
                })

            # Process each trim with the common data
            for trim in trims:
                if trim is None:
                    continue

                # Create a separate model for each trim
                trim_model = copy.deepcopy(base_model)
                trim_model.update({
                    "trim": grade_name,
                    "url": grade_image_url,
                    "exteriorColors": json.dumps(exterior_colors),
                    "interiorColors": json.dumps(interior_colors),
                    "bodyType": body_type,
                    "engineType": "",
                    "driveType": "",
                    "transmissionType": "",
                    "fuelType": "",
                    "cabType": "",
                    "bedLength": "",
                    "msrp": "",
                    "packages": json.dumps(all_packages) if all_packages else ""
                })

                # Extract trim-specific info
                trim_code = trim.get('code', '')
                self.logger.info(f"Processing trim {trim_code} for {grade_name}")

                # Get MSRP
                msrp = trim.get('msrp')
                if msrp and 'value' in msrp:
                    trim_model['msrp'] = msrp.get('value', '')
                elif trim.get('defaultConfig') and trim.get('defaultConfig').get('msrp'):
                    default_msrp = trim.get('defaultConfig').get('msrp')
                    if default_msrp and 'value' in default_msrp:
                        trim_model['msrp'] = default_msrp.get('value', '')

                # Extract fuel type
                trim_model['fuelType'] = trim.get('fuelType', '')

                # Extract cab and bed information
                cab_bed = trim.get('cabBed')
                if cab_bed:
                    # Bed length
                    trim_model['bedLength'] = cab_bed.get('bedLength', '')

                    # Cab type
                    cab_label = cab_bed.get('label', '')
                    cab_desc = cab_bed.get('description', '')

                    # Use whichever is available (label or description)
                    cab_text = cab_label if cab_label else cab_desc

                    if cab_text:
                        cab_text_lower = cab_text.lower()
                        if 'crew' in cab_text_lower or 'double cab' in cab_text_lower:
                            trim_model['cabType'] = "Crew Cab"
                        elif 'regular' in cab_text_lower:
                            trim_model['cabType'] = "Regular Cab"
                        elif 'extended' in cab_text_lower or 'access cab' in cab_text_lower:
                            trim_model['cabType'] = "Extended Cab"
                        else:
                            trim_model['cabType'] = cab_text

                # Extract powertrain information
                powertrain = trim.get('powertrain')
                if powertrain:
                    # Drive type
                    drive = powertrain.get('drive')
                    if drive:
                        trim_model['driveType'] = drive.get('value', '')

                    # Engine type
                    engine = powertrain.get('engine')
                    if engine:
                        trim_model['engineType'] = engine.get('value', '')

                    # Transmission
                    transmission = powertrain.get('transmission')
                    if transmission:
                        trim_model['transmissionType'] = transmission.get('value', '')
                    else:
                        trim_model['transmissionType'] = "Automatic"  # Default

                yield trim_model

        except Exception as e:
            self.logger.error(f"Error parsing colors and packages: {str(e)}", exc_info=True)


if __name__ == "__main__":
    process = CrawlerProcess(settings=ToyotaSpider.custom_settings)
    process.crawl(ToyotaSpider)
    process.start()