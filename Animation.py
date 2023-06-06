import math
import time
import logging

import imageio
from PIL import Image

class Animation:
    """
        Represents an animation and provides playback utilities
    """
    def __init__(self, filepath:str, cache_limit:int=128):
        """ Creates an instance of Animation
        
        Args:
            filepath: The filepath to the animation to load
            cache_limit: (OPTIONAL) Indicates the limit on frames to stop caching
        """
        self._filepath = filepath
        self._cache = []
        self._frame_number = 0
        self._current_frame = None
        self._reader = None
        self._frame_delay = 1
        self._next_frame_timer = 0
        self.frames = 0
        self.playing = False

        logging.debug(f"Reading expression file {filepath}")
        reader = imageio.get_reader(filepath)
        self.frames = reader.get_length()
        if self.frames == math.inf:
            self.frames = reader.count_frames()
            meta = reader.get_meta_data()

            if "fps" in meta:
                self._frame_delay = 1000 / float(meta["fps"])
            elif "duration" in meta:
                self._frame_delay = int(meta["duration"])
        
        logging.debug(f"\tExpression has {self.frames} frames and a rate of {self._frame_delay}s")

        if self.frames < cache_limit:
            logging.info(f"\tCaching expression frames...")
            for _ in range(self.frames):
                raw_frame = reader.get_next_data()
                self._cache.append(Image.fromarray(raw_frame).crop((0, 0, 32, 16)))
        else:
            logging.debug("\tExpression frames are over cache limit, not storing!")
    
    def start(self):
        """ Starts the animation from the begining """
        self._frame_number = 0
        self._next_frame_timer = 0
        self.playing = True

        if not self._cache:
            self._reader = imageio.get_reader(self._filepath)
    
    def get_frame(self) -> Image.Image:
        """ Gets the current frame of the animation
        
        Returns:
            Image.Image: The pillow image representing the frame
        """
        if time.monotonic() > self._next_frame_timer:
            self._next_frame_timer += self._frame_delay
            self._frame_number = (self._frame_number+1) % self.frames

            if self._cache:
                self._current_frame = self._cache[self._frame_number]
            else:
                if self._frame_number == 0:
                    self._reader.set_image_index(0)
                
                try:
                    raw_frame = self._reader.get_next_data()
                except IndexError:
                    self._frame_number = 0
                    self._reader.set_image_index(0)
                    raw_frame = self._reader.get_next_data()
                
                self._current_frame = Image.fromarray(raw_frame).crop((0, 0, 32, 16))
        
        if self._current_frame is None:
            return Image.new("RGB", (32, 16), "black")
        else:
            return self._current_frame

    def stop(self):
        """ Stops the current animation and shuts down any readers """
        self.playing = False
        if not self._cache:
            del self._reader
        self._current_frame = None