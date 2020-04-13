# OCTOPUS ENERGY API PARSER FOR OPEN ENERGY MONITOR EMONCMS

Imports energy meter readings into emoncms

This code automatically creates the necessary emoncms configuration of inputs and feeds

The code will automatically find the earliest meter reading available and import all the history


You need to configure these values in the import_octopus.py code

Get your details from https://octopus.energy/dashboard/developer/
Your private API key (don't publish this publically!)
OCTOPUSAPIKEY               = "sk_live_XXXXXXXXXXXXXXXXXXXXXX"
Electric meter MPAN (leave blank for no electric meter readings)
OCTOPUS_MPAN                = "XXXXXXXXXXXXXXXX"
OCTOPUS_ELECTRICMETERSERIAL = "XXXXXXXXX"
Gas meter MPRN (leave blank for no gas meter readings)
OCTOPUS_MPRN                = "XXXXXXXXXXXXXXXX"
OCTOPUS_GASMETERSERIAL      = "XXXXXXXXX"

The INPUT Node to CREATE in emoncms - don't overlap with existing node
This code automatically creates the necessary emoncms configuration of inputs and feeds
EMONINPUTNODE = "30"
Don't forget / at the end  - this is for a local network install of emoncms
EMONCMSURL="http://192.168.1.99/emoncms/"
EMONCMS_RW_APIKEY="XXXXXXXXXXXXXXXXXXXXXXXXXXXXX"



# Usage

Run import_octopus.py every day to obtain the latest data