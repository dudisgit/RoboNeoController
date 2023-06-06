import logging

import serial
import numpy
import unicornhathd
import RPi.GPIO as GPIO
from PIL import Image, ImageOps

from IHardware import IHardware

class RaspberryPi(IHardware):
    """
        The true raspberry pi libraries for robo neo
    """

    BUFFER_SIZE = 769  # 768 + checksum

    def __init__(self, config: dict, expression_trigger:Callable):
        """ Creates an instance of RaspberryPi
        
        Args:
            config: The application configuration from the json file
            expression_trigger: The method to call when a trigger has been fired
        """
        self.config = config
        self.trigger_fire = expression_trigger
        self.serial = serial.Serial(
            config["Port"],
            baudrate=115200,
            timeout=0.1
        )
        self.pin_to_expression = {}

        # Hardware setup
        unicornhathd.rotation(config["Rotation"])
        GPIO.setmode(GPIO.BCM)
        for expression, pin in config["Expression_pins"].items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(pin, GPIO.FALLING, callback=self._on_button_press, bouncetime=100)
            GPIO.add_event_detect(pin, GPIO.RISING, callback=self._on_button_release, bouncetime=100)

            self.pin_to_expression[pin] = expression
    
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
        
        unicornhathd._buf = numpy.array(image)  # Inject image into raw display buffer
        unicornhathd.show()
    
    def draw_to_screens(self, image:Image.Image):
        """ Draws the given image to the screens
        
        Args:
            image: The pillow image to draw, must be (32x16)
        """
        left_screen, right_screen = image.crop((0, 0, 16, 16)), image.crop((16, 0, 32, 16)).tobytes()
        right_screen += bytes([sum(right_screen)%255])  # Add checksome

        self._draw_image(left_screen)
        self.serial.write(right_screen)
    
    def write_serial_to_display(self):
        """ Called ONLY as a slave in order to write incomming serial data to the hardware """
        data = self.serial.read(self.BUFFER_SIZE)
        
        if len(data) != self.BUFFER_SIZE:
            self.serial.flush()
            logging.debug("Didn't receive a full message")
        else:
            screen_data, checksum = data[:-1], data[-1]
            if sum(screen_data) % 255 == checksum:
                image = Image.frombytes("RGB", (16, 16), screen_data)
                self._draw_image(image)
            else:
                logging.warning(f"Invalid checksum {sum(screen_data) % 255} != {checksum}")
    
    def teardown(self):
        """ Shutdown all hardware interfaces """
        self.serial.close()
        unicornhathd.off()
        GPIO.cleanup()

