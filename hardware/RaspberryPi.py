import logging
import hashlib
import time
from typing import Callable

HD_EDITION = True

import serial
import numpy
if HD_EDITION:
    import unicornhathd
else:
    import unicornhat
import RPi.GPIO as GPIO
from PIL import Image, ImageOps

from hardware.IHardware import IHardware

class RaspberryPi(IHardware):
    """
        The true raspberry pi libraries for robo neo
    """

    BUFFER_SIZE = 768
    HASH_SIZE = 4  # Cannot be bigger than 16

    BUTTON_ACTIVE_STATE = GPIO.LOW

    def __init__(self, config: dict, expression_trigger:Callable):
        """ Creates an instance of RaspberryPi
        
        Args:
            config: The application configuration from the json file
            expression_trigger: The method to call when a trigger has been fired
        """
        self.config = config
        self.trigger_fire = expression_trigger
        self._serial_timer = time.monotonic()
        self.serial = serial.Serial(
            config["Port"],
            baudrate=config["Serial_baudrate"],
            timeout=0.01
        )
        self.pin_to_expression = {}
        self._button_changes = {}

        self._data_buffer = bytes()

        # Hardware setup
        if HD_EDITION:
            unicornhathd.rotation(config["Rotation"])
            unicornhathd.brightness(config["Brightness"])
        else:
            unicornhat.rotation(config["Rotation"])
        
        GPIO.setmode(GPIO.BOARD)
        for expression, pin in config["Expression_pins"].items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            self.pin_to_expression[pin] = expression
            self._button_changes[pin] = False
    
    def _on_button_press(self, pin:int):
        """ Called when a button is pressed
        This is usually called by an event handler

        Args:
            pin: The PIN of the button thas was pressed
        """
        if pin in self.pin_to_expression:
            self.trigger_fire(self.pin_to_expression[pin])
        else:
            logging.error(f"Unknown pin {pin} in press event")
    
    def _on_button_release(self, pin:int):
        """ Called when a button is released
        This is usually called by an event handler

        Args:
            pin: The PIN of the button thas was released
        """
        down = sum([int(GPIO.input(i) == self.BUTTON_ACTIVE_STATE) for i in self.pin_to_expression.keys()])
        if down == 0 and not self.config["Sticky"] and self.config["Default"]:
            self.trigger_fire(self.config["Default"])
    
    def _draw_image(self, image:Image.Image):
        """ Draws an image to the unicorn hat screens
        
        Args:
            image: The pillow image to draw
        """
        if self.config["Flip_horizontal"]:
            image = ImageOps.mirror(image)
        if self.config["Flip_vertical"]:
            image = ImageOps.flip(image)
        
        if HD_EDITION:
            # Inject image into raw display buffer
            unicornhathd._buf = numpy.array(image, dtype=int)
            unicornhathd.show()
        else:
            # Translation is difficult to the original library :(
            for y in range(8):
                for x in range(8):
                    colour = image.getpixel((x, y))
                    unicornhat.set_pixel(x, y, colour[0], colour[1], colour[2])
            unicornhat.show()
    
    def draw_to_screens(self, image:Image.Image):
        """ Draws the given image to the screens
        
        Args:
            image: The pillow image to draw, must be (32x16)
        """
        left_screen, right_screen = image.crop((0, 0, 16, 16)), image.crop((16, 0, 32, 16)).tobytes()

        if time.monotonic() > self._serial_timer:
            hasher = hashlib.md5()
            hasher.update(right_screen)
            right_screen += hasher.digest()[:self.HASH_SIZE]  # Add hash
            self.serial.write(right_screen)

            self._serial_timer += 1 / self.config["Serial_rate"]

        self._draw_image(left_screen)

        for pin in self.pin_to_expression.keys():
            if (GPIO.input(pin) == self.BUTTON_ACTIVE_STATE) != self._button_changes[pin]:
                self._button_changes[pin] = GPIO.input(pin) == self.BUTTON_ACTIVE_STATE
                if self._button_changes[pin]:
                    self._on_button_press(pin)
                else:
                    self._on_button_release(pin)
    
    def write_serial_to_display(self):
        """ Called ONLY as a slave in order to write incomming serial data to the hardware """
        self._data_buffer += self.serial.read(self.BUFFER_SIZE+self.HASH_SIZE)
        
        if not self._data_buffer:
            pass  # No data sent
        elif len(self._data_buffer) >= self.BUFFER_SIZE+self.HASH_SIZE:
            screen_data, hashcode = self._data_buffer[:self.BUFFER_SIZE], self._data_buffer[self.BUFFER_SIZE:self.BUFFER_SIZE+self.HASH_SIZE]
            hasher = hashlib.md5()
            hasher.update(screen_data)
            check_hash = hasher.digest()[:self.HASH_SIZE]
            if check_hash == hashcode:
                image = Image.frombytes("RGB", (16, 16), screen_data)
                self._draw_image(image)
                self._data_buffer = self._data_buffer[self.BUFFER_SIZE+self.HASH_SIZE:]
            else:
                logging.warning(f"Invalid hash {check_hash} != {hashcode}, message length {len(self._data_buffer)}")
                self._data_buffer = bytes()
                self.serial.reset_input_buffer()
    
    def teardown(self):
        """ Shutdown all hardware interfaces """
        self.serial.close()
        if HD_EDITION:
            unicornhathd.off()
        else:
            unicornhat.off()
        GPIO.cleanup()

