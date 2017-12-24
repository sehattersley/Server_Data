#!/usr/bin/python
# Author: sehattersley
# Version: v1 - First version
# Purpose: Script to read data about the server and send it to emoncms
# Notes: You need smartmontools and lm-sensors installed for this to work.



# ---Imports---
import sensors # Used to run lm sensors which gives CPU temps etc.
import os, string
import urllib # Used for web access
try:
	import httplib # Used for web access. Python 2
except ImportError:
	import http.client as httplib # Used for web access. Python 3
import psutil # Used for reading CPU and memory load etc



# ---Control Settings---
bDebugPrint = 0 # 0/1 will disable/enable debug print statements
bDebugSendData = 1 # Enable sending data to emoncms servers
bEmoncmsOrg = 1 # Send data to emoncms.org
bEmoncmsOther = 1 # Send data to another emoncms server eg. local emonpi or a linux server



# --- Functions ---
def Run_SmartCtl(strArgs): # Function to run startmontools with a given argument and return the terminal output
	cmdstring = "/usr/sbin/smartctl " + strArgs # Note full path for smartctl is require if running as a cron job.
	the_output = os.popen(cmdstring).read() # Read the output from the terminal
	lines = str.splitlines(the_output) # Split the lines up
	#lines = ["/dev/sda"]
	return lines

def Get_Device_Ids(): # Function to get a list of hard drive letters from smartmontools
	lines = Run_SmartCtl("--scan") # smartctl --scan returns a list of drive letters
	Device_List = [] # Create a blank list
	for line in lines:
		device_id = string.split(line," ",1)[0]
		Device_List.append(device_id) # Add the hard drive IDs to the list
	return Device_List

def Get_Temp_Data(device_id): # Function to get hard drive temperature
	dev_info_lines = Run_SmartCtl("-l scttemp " + device_id ) # Run smartmontools
	for line2 in dev_info_lines:
		TheFirstField = string.split(line2," ",2)
		field = string.split(line2,":",1)
		if  (field[0].lower() == "current temperature" ):
			current_temp = field[1].strip()
			current_temp, separator, endtext = current_temp.partition(' ') # split the text either side of the space
		#elif  (field[0].lower() == "device model" ):
		#    dev.model = field[1].strip()
		#elif  (field[0].lower() == "serial number" ):
		#    dev.serial = field[1].strip()
	return current_temp

def Get_Device_Info(device_id): # Function to get all the information for a given drive
	dev = HardDriveRecord() # Create a class
	dev_info_lines = Run_SmartCtl("-i " + device_id ) # Run smartmontools
	bEnteredInfoSection = False
	dev.device_id = device_id

	dev.temperature = Get_Temp_Data(dev.device_id)

	for line2 in dev_info_lines:
		if ( not bEnteredInfoSection ):
			TheFirstField = string.split(line2," ",2)
			#if (TheFirstField[0].lower() == 'smartctl' ):
			#    print "SmartCtl Version is: " + TheFirstField[1]
			if ( line2.lower()  == "=== start of information section ===" ) :
				bEnteredInfoSection = True
		else:
			field = string.split(line2,":",1)
			if  (field[0].lower() == "model family" ):
				dev.family = field[1].strip()
			elif  (field[0].lower() == "device model" ):
				dev.model = field[1].strip()
			elif  (field[0].lower() == "serial number" ):
				dev.serial = field[1].strip()
			elif  (field[0].lower() == "firmware version" ):
				dev.firmware_version = field[1].strip()
			elif  (field[0].lower() == "user capacity" ):
				dev.capacity = field[1].strip()
			elif  (field[0].lower() == "sector sizes" ):
				dev.sector_sizes = field[1].strip()
			elif  (field[0].lower() == "rotation rate" ):
				dev.rotation_rate = field[1].strip()
			elif  (field[0].lower() == "device is" ):
				dev.device_is = field[1].strip()
			elif  (field[0].lower() == "ata version is" ):
				dev.ata_version = field[1].strip()
			elif  (field[0].lower() == "sata version is" ):
				dev.sata_version = field[1].strip()
			elif  (field[0].lower() == "smart support is" ):
				temp = string.split(field[1].strip()," ",1)
				#temp = string.split(field[1]," ",1)
				strTemp = temp[0].strip().lower()
				if (strTemp == "available" ):
					dev.smart_support_available = True
				elif (strTemp == "unavailable" ):
					dev.smart_support_available = False
					dev.smart_support_enabled = False
				elif (strTemp == "enabled" ) :
					dev.smart_support_enabled = True
				elif (strTemp == "disabled" ) :
					dev.smart_support_enabled = False
	return dev

def RemoveDupes(devices):
	newlist = []
	for device in devices:
		currentSerial = device.serial
		present = False
		for item in newlist:
			if (item.serial == currentSerial):
				present = True
		if ( not present ) :
			newlist.append(device)
	return newlist   

def RemoveDisabledUnsupported(devices): # Function to remove hard drives that dont support SMART
	newlist = []
	for device in devices:
		if ( device.smart_support_available == True and device.smart_support_enabled == True ):
			 newlist.append(device)
	return newlist 

def PostToEmoncms(sSensorName, dSensorValue, conn, sLocation, ApiKey, sNodeID, bDebugPrint): # Function to post data to an emoncms server
	MeasuredData = (sSensorName + ":%.1f" %(dSensorValue)) #Data name cannot have spaces. dSensorValue is set to 1 decimal place
	Request = sLocation + ApiKey + "&node=" + sNodeID + "&json=" + MeasuredData
	conn.request("GET", Request) # Make a GET request to the emoncms data. This basically sends the data.
	Response = conn.getresponse() # Get status and error message back from webpage. This must be done before a new GET command can be done.
	Response.read() # This line prevents the error response not ready. Its to do with the http socket being closed.
	if bDebugPrint == 1:
		print(sSensorName + ": data post status and reason - " + str(Response.status) + ", " + str(Response.reason))



# --- Classes ---
class HardDriveRecord: # Class for storing hard drive data
	device_id = ""
	family = ""
	model =  ""
	serial = ""
	firmware_version = ""
	capacity = ""
	sector_sizes = ""
	rotation_rate = ""
	device_is  = ""
	ata_version = ""
	sata_version = ""
	smart_support_available = False
	smart_support_enabled = False



# --- Main Code ---
dicEmoncmsData = {} # Create blank dictionary

# Get motherboard temperatures
sensors.init() # Initialse
dicMotherboardReadings = {}
try:
	if bDebugPrint == 1:
		print('List of Detected Sensors:')
	for chip in sensors.iter_detected_chips(): # Loop through the chips on the motherboard
		if bDebugPrint == 1:
			print '%s at %s' % (chip, chip.adapter_name)
		for feature in chip: # Loop though the sensors in each chip
			dicMotherboardReadings[chip.adapter_name + ' ' +feature.label] = feature.get_value()  #Add chip name and feature name as key and feature as value
			if bDebugPrint == 1:
				print '  %s: %.2f' % (feature.label, feature.get_value())
finally:
	sensors.cleanup()
if bDebugPrint == 1:
	print('Motherboard Readings Dictionary:')
	print(dicMotherboardReadings)
# Add the motherboard data that I am interested in to the emoncms dictionary
dicEmoncmsData['ISA_adapter_temp1'] = dicMotherboardReadings['ISA adapter temp1']
dicEmoncmsData['ISA_adapter_temp2'] = dicMotherboardReadings['ISA adapter temp2']
dicEmoncmsData['ISA_adapter_temp3'] = dicMotherboardReadings['ISA adapter temp3']


# Get hard drive temperatures
lsHardDriveIDs = Get_Device_Ids() # Get list of hard drives
if bDebugPrint == 1:
	if ( [] == lsHardDriveIDs ) : print "No devices found."

lsHardDriveData = [] # Create a blank list
for strHardDrive in lsHardDriveIDs: # Loop through each drive in the list
	oHardDive = Get_Device_Info(strHardDrive) # Get detailed information on each drive
	#print device.family, device.model, device.serial, device.smart_support_available,device.smart_support_enabled
	lsHardDriveData.append(oHardDive) # Add hard drive oject data to list

lsHardDriveData = RemoveDupes(lsHardDriveData) # Remove duplicates
lsHardDriveData = RemoveDisabledUnsupported(lsHardDriveData) # Remove disabled or unsupported drives

for oHDD in lsHardDriveData:
	dicEmoncmsData[oHDD.device_id + '_temp'] = oHDD.temperature # Add hard drive temps to dictionary
	if bDebugPrint == 1:
		print(oHDD.device_id + ': ' + oHDD.temperature + '*C')
if bDebugPrint == 1:
		print('Here is the emoncms dictionary data:')
		print(dicEmoncmsData)


# Get CPU and Memory information
dicEmoncmsData['CPU_Load_P'] = psutil.cpu_percent()
dicEmoncmsData['Memory_Load_P'] = psutil.virtual_memory().percent # The .percent gives us just the % load. Remove it and you get other memory data.
if bDebugPrint == 1:
	print('CPU Load: ' + str(dicEmoncmsData['CPU_Load_P']) + '%')
	print('Memory Load: ' + str(dicEmoncmsData['Memory_Load_P']) + '%')


# Get file system information
oOSFileSystem = os.statvfs('/')
oMediaFileSystem = os.statvfs('path to media file system')
OSLoad_P = round(((1 - (float(oOSFileSystem.f_frsize * oOSFileSystem.f_bavail)/float(oOSFileSystem.f_frsize * oOSFileSystem.f_blocks))) * 100), 1) # Free space in %
MediaLoad_P = round(((1 - (float(oMediaFileSystem.f_frsize * oMediaFileSystem.f_bavail)/float(oMediaFileSystem.f_frsize * oMediaFileSystem.f_blocks))) * 100) , 1)
dicEmoncmsData['OS_FS_Load_P'] = OSLoad_P
dicEmoncmsData['Media_FS_Load_P'] = MediaLoad_P
if bDebugPrint == 1:
	print('OS File System Load: ' + str(OSLoad_P) + '%')
	print('Media File System Load: ' + str(MediaLoad_P) + '%')


# --- Send data to emoncms.org ---
if bDebugSendData == 1 and bEmoncmsOrg == 1:
	sMyApiKey = "enter API kay here" # emoncms.org read & write api key
	Connection = httplib.HTTPConnection("emoncms.org:80") # Address of emoncms server with port number
	sLocation = "/input/post?apikey=" # Subfolder for the given emoncms server
	sNodeID = "Server" # Node IDs cant have spaces in them

	for key in dicEmoncmsData:
		PostToEmoncms(key.replace(' ', '' ), float(dicEmoncmsData[key]), Connection, sLocation, sMyApiKey, sNodeID, bDebugPrint) # dictionary keys need spaces removing.
	

		# --- Send data to local emoncms server ---
if bDebugSendData == 1 and bEmoncmsOther == 1:
	sMyApiKey = "enter API key here" # Local server emoncms read & write api key
	Connection = httplib.HTTPConnection("IP Address Here:80") # Address of Linux emoncms server with port number
	#Connection = httplib.HTTPConnection("localhost:80") # Address of local emoncms server with port number
	sLocation = "/emoncms/input/post?apikey=" # Subfolder for the given emoncms server
	sNodeID = "Server" # Node IDs cant have spaces in them

	for key in dicEmoncmsData:
		PostToEmoncms(key.replace(' ', '' ), float(dicEmoncmsData[key]), Connection, sLocation, sMyApiKey, sNodeID, bDebugPrint) # dictionary keys need spaces removing.
