# OCTOPUS ENERGY API PARSER FOR OPEN ENERGY MONITOR EMONCMS
# Imports energy meter readings into emoncms
# Stuart Pittaway, April 2020


# GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
# Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
# Everyone is permitted to copy and distribute verbatim copies
# of this license document, but changing it is not allowed.


# Get your details from https://octopus.energy/dashboard/developer/
# Your private API key (don't publish this publically!)
OCTOPUSAPIKEY               = "sk_live_XXXXXXXXXXXXXXXXXXXXXX"
#Electric meter MPAN (leave blank for no electric meter readings)
OCTOPUS_MPAN                = "AAAAAAAAAAAAAAA"
OCTOPUS_ELECTRICMETERSERIAL = "XXXXXXXXX"
#Gas meter MPRN (leave blank for no gas meter readings)
OCTOPUS_MPRN                = "BBBBBBBBBBBBB"
OCTOPUS_GASMETERSERIAL      = "CCCCCCCCC"

# The INPUT Node to CREATE in emoncms - don't overlap with existing node
# This code automatically creates the necessary emoncms configuration of inputs and feeds
EMONINPUTNODE = "30"
#Don't forget / at the end
EMONCMSURL="http://192.168.1.99/emoncms/"
EMONCMS_RW_APIKEY="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"




# importing the requests library
# python.exe -m pip install requests pytz python-dateutil

import sys
import logging

from emoncmsapi import emoncmsapi
from octopusapi import OctopusAPIClient

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import pytz

import dateutil.parser



# Set debug
logging.getLogger().setLevel(20)

# URL for emoncms
emon_api= emoncmsapi(EMONCMSURL,EMONCMS_RW_APIKEY)
octopus_api = OctopusAPIClient(OCTOPUSAPIKEY)



def GetElectricMeterDataFromOctopus(periodfrom, pagesize=240):
    logging.info("Requesting %s ELECTRIC meter data values from Octopus API since %s",pagesize,periodfrom) 
    # OCTOPUS: If no timezone information is included, the "Europe/London" timezone will be assumed.
    # https://developer.octopus.energy/docs/api/#datetimes
    params={'page_size': pagesize, 'order_by': 'period', 'period_from':str(periodfrom.isoformat())}
    return octopus_api.electricity_meter_consumption(OCTOPUS_MPAN,OCTOPUS_ELECTRICMETERSERIAL,params)

def GetGasMeterDataFromOctopus(periodfrom, pagesize=240):
    logging.info("Requesting %s GAS meter data values from Octopus API since %s",pagesize,periodfrom) 
    params={'page_size': pagesize, 'order_by': 'period', 'period_from':str(periodfrom.isoformat())}
    return octopus_api.gas_meter_consumption(OCTOPUS_MPRN,OCTOPUS_GASMETERSERIAL,params)

def ConvertOctopusDataToArray(jsondata):
    # Returns an array of UTC dates and meter consumption readings in kWh
    d = []

    for reading in jsondata:
        # API readings include timezone so convert back to UTC and get a UNIX timestamp
        INTERVALSTART = dateutil.parser.parse(reading['interval_start'])
        timestamp = int(INTERVALSTART.astimezone(pytz.utc).timestamp())
        d.append([timestamp, reading['consumption']])

    return d

def ProcessElectricityMeter():

    if (OCTOPUS_ELECTRICMETERSERIAL==""):
        raise Exception("Electricity meter serial number not supplied")

    if (OCTOPUS_MPAN==""):
        raise Exception("Electric MPAN not supplied")

    lastemoncmsTimestamp=None

    if (OCTOPUS_MPAN!=""):
        # Check meter exists
        meterpoint=octopus_api.electricity_meter_point(OCTOPUS_MPAN)
        if 'gsp' not in meterpoint:
            raise Exception("Electric meter point (MPAN) may be incorrect (%s)" % OCTOPUS_MPAN)

    # Ask emoncms for its timestamp for the last logged piece of data 
    emoncmsinput=emon_api.InputGet(str(EMONINPUTNODE),OCTOPUS_ELECTRICMETERSERIAL)

    if emoncmsinput is not None:
        lastemoncmsTimestamp=emoncmsinput['time']

    if lastemoncmsTimestamp is None:
        # Ask Octopus for a single meter reading to find out the first smart meter reading date ever recorded
        # Octopus was founded in August 2015, so shouldn't be possible to have a reading before that
        data = GetElectricMeterDataFromOctopus(datetime(2015, 8, 1).astimezone(), 1)
        if data['results'] !=[]:
            firstreadingdate = dateutil.parser.parse(data['results'][0]['interval_start'])
            logging.info("Octopus reports first SMART electric meter reading date %s",firstreadingdate)
            period_from = firstreadingdate.astimezone()
        else:
            logging.error("Octopus JSON did not return any electric meter reading data for %s",OCTOPUS_ELECTRICMETERSERIAL)
            sys.exit(1)

        if emoncmsinput is None:
            logging.info("Creating new emonCMS input and feed")
            #Assume that the input and feed are not created
            #First we have to poke a value into the input API - otherwise the INPUT won't exist and the feed setup will fail
            emon_api.BulkPostDataToEmonCMS(ConvertOctopusDataToArray(data['results']),EMONINPUTNODE,OCTOPUS_ELECTRICMETERSERIAL)

    else:
        period_from = datetime.utcfromtimestamp(lastemoncmsTimestamp).replace(tzinfo=pytz.utc)
        #Add 1 second to last reading so we don't ask for the same data again
        period_from=period_from+timedelta(seconds=1)
        logging.info("emonCms reports last timestamp is %s = %s",lastemoncmsTimestamp,period_from)

    # Create the input and feeds
    if emoncmsinput is None:
        emoncmsinput=emon_api.InputGet(str(EMONINPUTNODE),OCTOPUS_ELECTRICMETERSERIAL)

    if emoncmsinput is None:
        raise Exception("emonCMS input does not exist")

    processes=emoncmsinput['processList'].split(',')

    if len(processes) == 0:
        raise Exception("Input %s (%s) does not have any processes associated with it" % (EMONINPUTNODE,OCTOPUS_ELECTRICMETERSERIAL))

    process=processes[0].split(':')  

    if process[0] != '1':
        logging.warning("Input %s (%s) expected to have logging as first process",EMONINPUTNODE,OCTOPUS_ELECTRICMETERSERIAL)
        feedId=emon_api.FeedCreate("Octopus Smart Meter",OCTOPUS_ELECTRICMETERSERIAL,1,5,1800,'kWh')
        if feedId is not None:        
            inputId=emon_api.InputGetInputIdForNodeItem(str(EMONINPUTNODE),OCTOPUS_ELECTRICMETERSERIAL);
            if inputId is not None:
                emon_api.InputProcessSet(inputId,"1:"+str(feedId))
        
    while True:
        #Get the next meter readings
        data = GetElectricMeterDataFromOctopus(period_from)

        if "results" in data:
            #Stop if there is no data
            if len(data['results'])==0:
                break
            
            if emon_api.BulkPostDataToEmonCMS(ConvertOctopusDataToArray(data['results']),EMONINPUTNODE,OCTOPUS_ELECTRICMETERSERIAL)==False:
                raise Exception("Failed whilst sending data to emoncms")

            INTERVALSTART = dateutil.parser.parse(data['results'][-1]['interval_end'])
            period_from = INTERVALSTART.astimezone(pytz.utc)
        else:
            raise Exception("Reply from Octopus JSON did not include 'results' key")



def ProcessGasMeter():
    lastemoncmsTimestamp=None

    if (OCTOPUS_GASMETERSERIAL==""):
        raise Exception("Gas meter serial number not supplied")

    if (OCTOPUS_MPRN==""):
        raise Exception("Gas MPRN not supplied")

    # Ask emoncms for its timestamp for the last logged piece of data 
    emoncmsinput=emon_api.InputGet(str(EMONINPUTNODE),OCTOPUS_GASMETERSERIAL)

    if emoncmsinput is not None:
        lastemoncmsTimestamp=emoncmsinput['time']

    if lastemoncmsTimestamp is None:
        # Ask Octopus for a single meter reading to find out the first smart meter reading date ever recorded
        # Octopus was founded in August 2015, so shouldn't be possible to have a reading before that
        data = GetGasMeterDataFromOctopus(datetime(2015, 8, 1).astimezone(), 1)
        if data['results'] !=[]:
            firstreadingdate = dateutil.parser.parse(data['results'][0]['interval_start'])
            logging.info("Octopus reports first SMART gas meter reading date %s",firstreadingdate)
            period_from = firstreadingdate.astimezone()
        else:
            raise Exception("Octopus JSON did not return any gas meter reading data for %s" % OCTOPUS_GASMETERSERIAL)

        if emoncmsinput is None:
            logging.info("Creating new emonCMS input and feed")
            #Assume that the input and feed are not created
            #First we have to poke a value into the input API - otherwise the INPUT won't exist and the feed setup will fail
            emon_api.BulkPostDataToEmonCMS(ConvertOctopusDataToArray(data['results']),EMONINPUTNODE,OCTOPUS_GASMETERSERIAL)

    else:
        period_from = datetime.utcfromtimestamp(lastemoncmsTimestamp).replace(tzinfo=pytz.utc)
        #Add 1 second to last reading so we don't ask for the same data again
        period_from=period_from+timedelta(seconds=1)
        logging.info("emonCms reports last timestamp is %s = %s",lastemoncmsTimestamp,period_from)

    # Create the input and feeds
    if emoncmsinput is None:
        emoncmsinput=emon_api.InputGet(str(EMONINPUTNODE),OCTOPUS_GASMETERSERIAL)

    if emoncmsinput is None:
        raise Exception("emonCMS input does not exist")

    processes=emoncmsinput['processList'].split(',')

    if len(processes) == 0:
        raise Exception("Input %s (%s) does not have any processes associated with it" % (EMONINPUTNODE,OCTOPUS_GASMETERSERIAL))

    process=processes[0].split(':')  

    if process[0] != '1':
        logging.warning("Input %s (%s) expected to have logging as first process",EMONINPUTNODE,OCTOPUS_GASMETERSERIAL)
        feedId=emon_api.FeedCreate("Octopus Smart Meter",OCTOPUS_GASMETERSERIAL,1,5,1800,'m^3')
        if feedId is not None:        
            inputId=emon_api.InputGetInputIdForNodeItem(str(EMONINPUTNODE),OCTOPUS_GASMETERSERIAL)
            if inputId is not None:
                emon_api.InputProcessSet(inputId,"1:"+str(feedId))
        
    while True:
        #Get the next meter readings
        data = GetGasMeterDataFromOctopus(period_from)

        if "results" in data:
            #Stop if there is no data
            if len(data['results'])==0:
                break
            
            if emon_api.BulkPostDataToEmonCMS(ConvertOctopusDataToArray(data['results']),EMONINPUTNODE,OCTOPUS_GASMETERSERIAL)==False:
                raise Exception("Failed whilst sending data to emoncms")

            INTERVALSTART = dateutil.parser.parse(data['results'][-1]['interval_end'])
            period_from = INTERVALSTART.astimezone(pytz.utc)
        else:
            raise Exception("Reply from Octopus JSON did not include 'results' key")





if (OCTOPUSAPIKEY==""):
    raise Exception("OCTOPUSAPIKEY not provided")

if (OCTOPUS_GASMETERSERIAL==OCTOPUS_ELECTRICMETERSERIAL):
    raise Exception("Gas and Electric meter numbers are the same - not possible!")

if (OCTOPUS_ELECTRICMETERSERIAL!="" and OCTOPUS_MPAN!=""):
    ProcessElectricityMeter()

if (OCTOPUS_GASMETERSERIAL!="" and OCTOPUS_MPRN!=""):
    ProcessGasMeter()
