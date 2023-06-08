import logging
import hashlib
import time
from typing import Callable

HD_EDITION = False

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

    HEADER = b'>I"\x05\x03\xf5'  # Am too tired to do this right D:
    BUFFER_SIZE = 768
    HASH_SIZE = 4  # Cannot be bigger than 16

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
            timeout=0.1
        )
        self.pin_to_expression = {}

        # Hardware setup
        if HD_EDITION:
            unicornhathd.rotation(config["Rotation"])
            unicornhathd.brightness(config["Brightness"])
        else:
            unicornhat.rotation(config["Rotation"])
        
        GPIO.setmode(GPIO.BOARD)
        for expression, pin in config["Expression_pins"].items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(pin, GPIO.BOTH, callback=self._on_button_event, bouncetime=100)

            self.pin_to_expression[pin] = expression
    
    def _on_button_event(self, pin:int):
        """ Called when there is a event change in a button
        
        Args:
            pin: The pin assosiated with the button
        """
        if GPIO.input(pin) == GPIO.LOW:
            self._on_button_press(pin)
        else:
            self._on_button_release(pin)
    
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
        down = sum([int(GPIO.input(i)) for i in self.pin_to_expression.keys()])
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
            right_screen += self.HEADER
            self.serial.write(right_screen)

            self._serial_timer += 1 / self.config["Serial_rate"]

        self._draw_image(left_screen)
    
    def write_serial_to_display(self):
        """ Called ONLY as a slave in order to write incomming serial data to the hardware """
        data = self.serial.read_until(self.HEADER)
        
        if not data:
            pass  # No data sent
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
                self._draw_image(image)
            else:
                logging.warning(f"Invalid hash {check_hash} != {hashcode}, message length {len(data)}")
                self.serial.flush()
    
    def teardown(self):
        """ Shutdown all hardware interfaces """
        self.serial.close()
        if HD_EDITION:
            unicornhathd.off()
        else:
            unicornhat.off()
        GPIO.cleanup()

