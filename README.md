# Server_Data
Python script to capture data about your server and send it to emoncms.

You need to install lm-sensors and smartmontools on your linux machine.
sudo apt-get install lm-sensors
Then run the following command to detect what sensors are available. Answer yes to all questions:
sudo sensors-detect

sudo apt-get install smartmontools


I run the script as a conjob every 5 minutes:
sudo contab -e
*/5 * * * * /path to your python script
