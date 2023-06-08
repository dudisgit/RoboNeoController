# RoboNeoController
A simple controller app that allows you to play video files on triggers and stream segments to another rasbperry pi over serial.

This software is bespoke to unicorn hats and a 32x16 image size

## Setup
This setup does not cover installing the unicorn hat library, please install the one for python3!

To install run the following in terminal within the repo directory
```sh
sudo apt-get update
sudo apt-get upgrade
sudo chmod +x setup.sh
sudo ./setup.sh
sudo python3 -m pip install -r requirements
```

## Usage
Edit the config.json files and assign expressions to the pins you want to trigger them, to note that these pins are the BOARD pins and not GPIO numbers!

Run the program on the master Pi with the following
```sh
sudo python3 main.py
```
And run the slave app on the slave pi with the following
```sh
sudo python3 main.py -slave
```

You should see a yellow line with a breathing white rectangle in the middle if all is good.

You can now drag video files into the "expressions" directory and name them EXACTLY the same as they appear in the config.json in "Expression_pins" (excluding extension). E.g. "Eyeroll.mp4"

For more settings please look at the comments within the config.jsonc file

## Setup startup script
To run either script when the system starts up edit the following file with
```sh
sudo nano /etc/rc.local
```
And enter the following before the exit command. Remove the "-slave" argument if running on master, remember to keep the '&' symbol at the end!
```sh
sudo python3 /home/pi/RoboNeoController/main.py -slave &
```
It should look like this

![Nano editor example](https://i2.paste.pics/OFJMD.png)
