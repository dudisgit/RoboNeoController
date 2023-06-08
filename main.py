import argparse
import os
import logging
import time
import math
from threading import Lock
from collections import defaultdict

import commentjson
from PIL import Image, ImageDraw

from Animation import Animation
from hardware.IHardware import IHardware

class App:
    """
        Main roboneo controller app
    """
    def __init__(self, config:dict, simulate:bool=False):
        """ Creates an instance of App
        
        Args:
            config: The application config
            simulate: Whether to simulate the hardware
        """
        self._current_expression = None
        self._nextUpdate = time.monotonic()
        self._update_lock = Lock()

        logging.info("Loading hardware instance")
        if simulate:
            from hardware.Simulator import Simulator
            self._hardware = Simulator(config, self.switch_to_expression)
        else:
            from hardware.RaspberryPi import RaspberryPi
            self._hardware = RaspberryPi(config, self.switch_to_expression)

        self.config = config
        self.animations_dir = os.path.join(os.path.dirname(__file__), "expressions")
        if not os.path.exists(self.animations_dir):
            logging.info(f"Creating animation directory at {self.animations_dir}")
            os.mkdir(self.animations_dir)
        self.animations = defaultdict(lambda: None)

        self.image = Image.new("RGB", (32, 16), "black")
        self.draw = ImageDraw.Draw(self.image)

        logging.info("Loading expressions")
        for file in os.listdir(self.animations_dir):
            expression = os.path.splitext(file)[0]
            if expression in config["Expression_pins"]:
                self.load_animation(expression, os.path.join(self.animations_dir, file))
            else:
                logging.error(f"Could not map file '{file}' to any known expressions, unknown expression!")
        
        if config["Default"]:
            self.switch_to_expression(config["Default"])
    
    @property
    def hardware(self) -> IHardware:
        """ Gets the currently active hardware controller """
        return self._hardware

    def load_animation(self, expression_name:str, filepath:str):
        """ Loads the given animation into the app under the given expression name
        This will unload any animation currently present
        
        Args:
            expression_name: The expression to assign to the animation
            filepath: The filepath of the animation
        Raises:
            IndexError: If the expression doesn't exist
        """
        if not expression_name in self.config["Expression_pins"]:
            raise IndexError(f"No such expression name '{expression_name}'")

        slot = self.animations[expression_name]
        if slot is not None and slot.playing:
            logging.warning(f"Stopping currently playing Animation instance to {expression_name}")
            slot.stop()
        
        logging.info(f"Loading expression {expression_name} at {filepath}")
        self.animations[expression_name] = Animation(filepath, self.config["Frame_cache_limit"])
    
    @property
    def current_animation(self) -> Animation:
        """ Gets the current animation playing """
        return self.animations.get(self._current_expression, None)
    
    def switch_to_expression(self, expression_name:str):
        """ Switches to the given expression name
        
        Args:
            expression_name: The name of the expresison to switch to
        Raises:
            IndexError: If the expression doesn't exist
        """
        if not expression_name in self.config["Expression_pins"]:
            raise IndexError(f"No such expression name '{expression_name}'")
        
        with self._update_lock:
            if expression_name == self._current_expression:
                return
            elif self.current_animation is not None:
                self.current_animation.stop()
            
            logging.debug(f"Switching to expression {expression_name}")
            self._current_expression = expression_name
            if self.current_animation is None:
                logging.warning(f"No animation tied to {expression_name} currently!")
            else:
                self.current_animation.start()
    
    def update(self):
        """ Renders and animations and displays to hardware """
        with self._update_lock:
            if self.current_animation:
                frame = self.current_animation.get_frame()
                self.image.paste(frame)
            else:
                self.draw.rectangle((0, 0, 32, 16), "black")
                self.draw.line((0, 0, 16, 16), "yellow")
                self.draw.line((16, 0, 32, 16), "yellow")
                
                pulse_colour = tuple([round(255*abs(math.cos(time.time()*3)))]*3)
                self.draw.rectangle((7, 7, 9, 9), pulse_colour)
                self.draw.rectangle((23, 7, 25, 9), pulse_colour)
        
        self.hardware.draw_to_screens(self.image)
    
    def mainloop(self):
        """ Runs the application indefinitely until the user closes it """
        delay = (1/self.config["Update_rate"])

        logging.info("Running mainloop, press Ctrl-C to terminate")
        while True:
            try:
                self.update()

                delta = self._nextUpdate - time.monotonic()
                if delta > 0:
                    time.sleep(delta)
                self._nextUpdate += delay
            except KeyboardInterrupt:
                logging.info("Received keyboard interrupt, closing app...")
                break
    
    def teardown(self):
        """ Shuts down any animation and currently running hardware """
        if self.current_animation:
            logging.info("Stopping current animation")
            self.current_animation.stop()
        logging.info("Shutting down hardware interface")
        self.hardware.teardown()


def slave_instance(config:dict, simulate:bool=False):
    """ Called to start the slave runner to receive data from the oposing Pi
    
    Args:
        config: The application configuration loaded from the json file
        simulate: (OPTIONAL) Whetehr to simulate the hardware
    """
    if simulate:
        from hardware.Simulator import Simulator
        hardware = Simulator(config, lambda trig: 1)
    else:
        from hardware.RaspberryPi import RaspberryPi
        hardware = RaspberryPi(config, lambda trig: 1)
    
    logging.info("Running mainloop, press Ctrl-C to terminate")
    while True:
        try:
            hardware.write_serial_to_display()
        except KeyboardInterrupt:
            break
    
    logging.info("Shutting down hardware")
    hardware.teardown()


def main():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s]: %(message)s",
        level=logging.DEBUG
    )

    parser = argparse.ArgumentParser()

    parser.add_argument("-config", default=os.path.join(os.path.dirname(__file__), "config.jsonc"),
        help="The app configuration to load")
    
    parser.add_argument("-slave", action="store_true",
        help="Indicates this instance is a slave")
    
    parser.add_argument("-simulate", action="store_true",
        help="Launches a simulator instead of interacting with the real hardware")
    
    args = parser.parse_args()

    with open(args.config, "rb") as jfile:
        config = commentjson.load(jfile)
    
    if args.slave:
        slave_instance(config, args.simulate)
        return

    app = App(config, args.simulate)

    try:
        app.mainloop()
    except:
        logging.warning("Fatal exception occured, safely closing app")
        app.teardown()
        raise

    app.teardown()




if __name__ == "__main__":
    main()
