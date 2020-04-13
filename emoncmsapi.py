# OCTOPUS ENERGY API PARSER FOR OPEN ENERGY MONITOR EMONCMS
# Imports energy meter readings into emoncms
# Stuart Pittaway, April 2020

#  GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
#  Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
#  Everyone is permitted to copy and distribute verbatim copies
#  of this license document, but changing it is not allowed.

import requests
from requests.auth import HTTPBasicAuth
import urllib.parse
import logging
import json


class emoncmsapi:
    """Python wrapper for emonCMS API interface"""
    rwapikey = ''
    emoncmsbaseurl = ''

    def __init__(self, baseurl, readwriteapikey):
        self.emoncmsbaseurl = baseurl
        self.rwapikey = readwriteapikey
        self.session = requests.Session()

    class DataError(Exception):
        """
        Exception indicating invalid or no data from from the API
        """

    def _get(self, path, params=None, headers=None):
        """
        Make a GET HTTP request
        """
        if params is None:
            params = {}
        if headers is None:
            headers={}
        url = self.emoncmsbaseurl + path

        params['apikey']= self.rwapikey

        try:
            response = self.session.request(method="GET", url=url, params=params, headers=headers)
        except requests.RequestException as e:
            raise self.DataError("Network exception") from e

        if response.status_code != 200:
            raise self.DataError("Unexpected response status (%s)" % response.status_code)

        # Try and work around bug https://github.com/emoncms/emoncms/issues/1558
        if response.text.startswith('<br'):
            # Skip over HTML in reply and find the json string
            return json.loads(response.text[response.text.index('{'):])
        else:
            return response.json()

    def InputGet(self, nodeName, elementName):
        """Fetch specific input from node"""

        r = self._get("input/get/"+urllib.parse.quote_plus(nodeName)+"/"+urllib.parse.quote_plus(elementName))

        if r == "Node does not exist":
            return None

        if r == "Node variable does not exist":
            return None

        return r

    def InputGetInputs(self):
        """Fetch all inputs"""
        return self._get("input/getinputs")

    def InputGetInputIdForNodeItem(self, nodeName, elementName):
        """Fetches the unique ID for an input - needed for processlist"""
        data = self.InputGetInputs()
        return data[nodeName][elementName]['id']



    def FeedCreate(self, tag, name, datatype=1, engine=5, interval=1800, unit=''):
        """Creates a new feed and returns new feed id"""

        PARAMS = {'apikey': self.rwapikey, 'tag': tag, 'name': name,
                  'datatype': datatype, 'engine': engine, 'unit': unit, 
                  'options': json.dumps( {'interval':interval} , separators=(',',':'))
        }               

        headers = {'Content-type': 'application/json'}
        jsonreply = self._get("feed/create.json", PARAMS, headers)

        if "success" in jsonreply:
            if jsonreply['success'] != True:
                logging.error("Error when creating emonCMS feed '%s'", jsonreply['message'])
                return None

        # extracting data
        if "feedid" in jsonreply:
            return jsonreply["feedid"]

        return None

    def InputProcessSet(self, inputId, processList):
        try:
            #  Bug requires both querystring and POST values
            #  https://github.com/emoncms/emoncms/issues/1561
            response = self.session.post(url=self.emoncmsbaseurl+"input/process/set?apikey=" +
                            self.rwapikey+"&inputid="+str(inputId), data={'processlist': processList})
        except requests.RequestException as e:
            raise self.DataError("Network exception") from e

        if response.status_code != 200:
            raise self.DataError("Unexpected response status (%s)" % response.status_code)

        jsonreply = response.json()

        if "success" in jsonreply:
            return jsonreply['success']

        #Failed
        return None


    def BulkPostDataToEmonCMS(self, readingArray, node, input):
        """Bulk uploads data into emoncms - expects a time SORTED (2d) array containing UTC timestamps and a value"""
        if len(readingArray) == 0:
            logging.warn("No data in array")
            return False

        lastTimeStamp = readingArray[-1][0]

        data = []
        for reading in readingArray:
            data.append('['+str(reading[0]-lastTimeStamp)+',' +
                        str(node)+',{"'+str(input)+'":'+str(reading[1])+'}]')

        emoncmsParams = {'apikey': self.rwapikey,
                         'time': lastTimeStamp, 'data': '[' + ','.join(data)+']'}

        # logging.debug(emoncmsParams)
        logging.info("Post bulk request to emoncms (UTC timestamp=%s, items %s)", lastTimeStamp, len(readingArray))

        try:
            response = self.session.post(url=self.emoncmsbaseurl+"input/bulk", data=emoncmsParams)
        except requests.RequestException as e:
            raise self.DataError("Network exception") from e

        if response.status_code != 200:
            raise self.DataError("Unexpected response status (%s)" % response.status_code)

        return True
