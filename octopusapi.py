# Copied from https://gist.github.com/codeinthehole/5f274f46b5798f435e6984397f1abb64
# Original code by David Winterbottom - Head of Engineering at Octopus Energy
# Requires the requests library (install with 'pip install requests')
import requests


class OctopusAPIClient(object):
    BASE_URL = "https://api.octopus.energy/v1"

    class DataUnavailable(Exception):
        """
        Catch-all exception indicating we can't get data back from the API
        """

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()

    def _get(self, path, params=None):
        """
        Make a GET HTTP request
        """
        if params is None:
            params = {}
        url = self.BASE_URL + path
        try:
            response = self.session.request(
                method="GET", url=url, auth=(self.api_key, ""), params=params)
        except requests.RequestException as e:
            raise self.DataUnavailable("Network exception") from e

        if response.status_code != 200:
            raise self.DataUnavailable("Unexpected response status (%s)" % response.status_code)

        return response.json()

    def electricity_meter_point(self, mpan):
        # See https://developer.octopus.energy/docs/api/#electricity-meter-points
        return self._get("/electricity-meter-points/%s/" % mpan)

    def electricity_tariff_unit_rates(self, product_code, tariff_code, period_from=None, period_to=None):
        # See https://developer.octopus.energy/docs/api/#list-tariff-charges
        params = {}
        if period_from:
            params['period_from'] = period_from.isoformat()
            if period_to:
                params['period_to'] = period_to.isoformat()
        return self._get("/products/%s/electricity-tariffs/%s/standard-unit-rates/" % (
            product_code, tariff_code), params=params)

    def electricity_tariff_standing_charges(self, product_code, tariff_code, period_from=None, period_to=None):
        # See https://developer.octopus.energy/docs/api/#list-tariff-charges
        params = {}
        if period_from:
            params['period_from'] = period_from.isoformat()
            if period_to:
                params['period_to'] = period_to.isoformat()
        return self._get("/products/%s/electricity-tariffs/%s/standing-charges/" % (
            product_code, tariff_code), params=params)

    def agile_tariff_unit_rates(self, gsp, period_from=None, period_to=None):
        """
        Helper method to easily look-up the electricity unit rates for given GSP
        """
        # Handle GSPs passed with leading underscore
        if len(gsp) == 2:
            gsp = gsp[1]
        assert gsp in ("A", "B", "C", "D", "E", "F", "G", "P", "N", "J", "H", "K", "L", "M")

        return self.electricity_tariff_unit_rates(
            product_code="AGILE-18-02-21",
            tariff_code="E-1R-AGILE-18-02-21-%s" % gsp,
            period_from=period_from,
            period_to=period_to)

    def electricity_meter_consumption(self, mpan, serial_number, params):
        # See https://developer.octopus.energy/docs/api/#list-consumption-for-a-meter
        return self._get("/electricity-meter-points/%s/meters/%s/consumption/" % (
            mpan, serial_number), params=params)

    def gas_meter_consumption(self, mprn, serial_number, params):
        # See https://developer.octopus.energy/docs/api/#list-consumption-for-a-meter
        return self._get("/gas-meter-points/%s/meters/%s/consumption/" % (
            mprn, serial_number), params=params)
