from typing import Callable
from abc import ABCMeta, abstractmethod
from PIL import Image

class IHardware:
    """
        Represents a hardware interface
    """
    @abstractmethod
    def __init__(self, config:dict, expression_trigger:Callable):
        """ Creates an instance of the hardware

        Args:
            config: The configuration data from the json file
            expression_trigger: The method to call when a trigger has been fired
        """
        raise NotImplementedError()
    
    @abstractmethod
    def draw_to_screens(self, image:Image.Image):
        """ Draws the given image to the screens
        
        Args:
            image: The pillow image to draw, must be (32x16)
        """
        raise NotImplementedError()

    @abstractmethod
    def write_serial_to_display(self):
        """ Called ONLY as a slave in order to write incomming serial data to the hardware """
        raise NotImplementedError()
    
    @abstractmethod
    def teardown(self):
        """ Shutdown all hardware interfaces """
        raise NotImplementedError()

