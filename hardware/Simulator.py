from typing import Callable
from tkinter import *
from PIL import Image, ImageTk, ImageOps

from hardware.IHardware import IHardware

class Simulator(IHardware):
    """
        Tkinter window simulator for simulating hardware
    """
    SCALE = 10
    def __init__(self, config: dict, expression_trigger:Callable):
        """ Creates an instance of Simulator
        
        Args:
            config: The application configuration from the json file
            expression_trigger: The method to call when a trigger has been fired
        """
        self.config = config
        self.trigger_fire = expression_trigger

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
        self.backdrop.paste(ImageOps.scale(image, self.SCALE))

        self.photo = ImageTk.PhotoImage(self.backdrop)
        self.label.config(image=self.photo)

        self.window.update()
    
    def write_serial_to_display(self):
        """ Called ONLY as a slave in order to write incomming serial data to the hardware """
        raise NotImplementedError()
    
    def teardown(self):
        self.window.destroy()

