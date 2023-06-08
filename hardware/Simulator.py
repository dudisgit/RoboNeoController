import logging
import hashlib
import time
from typing import Callable
from tkinter import *

import serial
from PIL import Image, ImageTk, ImageOps

from hardware.IHardware import IHardware

class Simulator(IHardware):
    """
        Tkinter window simulator for simulating hardware
    """
    SCALE = 10

    HEADER = b'>I"\x05\x03\xf5'  # Am too tired to do this right D:
    BUFFER_SIZE = 768
    HASH_SIZE = 4  # Cannot be bigger than 16

    def __init__(self, config: dict, expression_trigger:Callable):
        """ Creates an instance of Simulator
        
        Args:
            config: The application configuration from the json file
            expression_trigger: The method to call when a trigger has been fired
        """
        self.config = config
        self.serial = None
        self.trigger_fire = expression_trigger
        self._next_update = 0  # used so that we don't update the screen too fast

        self.window = Tk()
        self.window.title("RoboNeo simulator")
        
        self.backdrop = Image.new("RGB", (32*self.SCALE, 16*self.SCALE), "black")
        self.photo = None
        self.label = Label(self.window)
        self.label.pack(side=RIGHT)

        self._input_frame = LabelFrame(self.window, text="Input pins")
        self.checkbox_values = []
        self._checkbox_changes = []
        self._checkbox_names = []
        self.checkboxes = []

        for expression in config["Expression_pins"]:
            self.checkbox_values.append(IntVar(self.window, 0))
            self.checkbox_values[-1].trace("w", self.recheck_inputs)
            self._checkbox_changes.append(0)
            self._checkbox_names.append(expression)

            checkbox = Checkbutton(self._input_frame, text=expression, variable=self.checkbox_values[-1])
            checkbox.pack(side=TOP, anchor=W)
            self.checkboxes.append(checkbox)
        self._input_frame.pack(side=LEFT)
    
    def recheck_inputs(self, *args):
        """ Called to recheck all checkbox values """
        changes = False
        for i, value in enumerate(self.checkbox_values):
            if value.get() != self._checkbox_changes[i]:
                changes = True
                self._checkbox_changes[i] = value.get()

                if self._checkbox_changes[i]:
                    self.trigger_fire(self._checkbox_names[i])
        
        if changes and sum(self._checkbox_changes) == 0 and not self.config["Sticky"] and self.config["Default"]:
            self.trigger_fire(self.config["Default"])
    
    def draw_to_screens(self, image: Image.Image):
        """ Draws the given image to the virtual displays
        
        Args:
            image: The pillow image to show
        """
        self.backdrop.paste(ImageOps.scale(image, self.SCALE, Image.BOX), (0, 0))
        
        self.photo = ImageTk.PhotoImage(self.backdrop)
        self.label.config(image=self.photo)
        
        if time.monotonic() > self._next_update and not self.serial:
            self.window.update()
            self._next_update = time.monotonic() + 0.04

    def write_serial_to_display(self):
        """ Called ONLY as a slave in order to write incomming serial data to the hardware """
        if not self.serial:
            self.serial = serial.Serial(
                self.config["Port"],
                baudrate=self.config["Serial_baudrate"],
                timeout=0.1
            )
            logging.info(f"Listening on port serial {self.config['Port']}")
        
        data = self.serial.read_until(self.HEADER)
        
        if not data:
            pass
        elif len(data) < self.BUFFER_SIZE+self.HASH_SIZE:
            logging.debug(f"Didn't receive a full message, only recieved {len(data)} bytes")
            self.serial.flush()
        else:
            screen_data, hashcode = data[:self.BUFFER_SIZE], data[self.BUFFER_SIZE:self.BUFFER_SIZE+self.HASH_SIZE]
            hasher = hashlib.md5()
            hasher.update(screen_data)
            check_hash = hasher.digest()[:self.HASH_SIZE]
            if check_hash == hashcode:
                image = Image.frombytes("RGB", (16, 16), screen_data)
                self.draw_to_screens(image)
            else:
                logging.warning(f"Invalid hash {check_hash} != {hashcode}, message length {len(data)}")
                self.serial.flush()
        
        if time.monotonic() > self._next_update:
            self.window.update()
            self._next_update = time.monotonic() + 0.04
    
    def teardown(self):
        self.window.destroy()
        if self.serial:
            self.serial.close()

