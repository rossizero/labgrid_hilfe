"""
This module implements switching GPIOs via libgpiod.

Takes an integer property 'index' which refers to the GPIO line.
"""

import logging
import gpiod
import time
from gpiod.line import Direction, Value


class GpioDigitalOutput:
    _chip_name = '/dev/gpiochip0'

    def __init__(self, index):
        self._logger = logging.getLogger(f"Device: GPIO{index}")
        self.index = index

        self._request = gpiod.request_lines(
            "/dev/gpiochip0",
            consumer="blink-example",
            config={
                self.index: None
            },
        )
        self.direction = None

    def __del__(self):
        print("released gpio line", self.index)
        self._request.release()

    def get(self):
        self.change_direction(Direction.INPUT)
        return self._request.get_value(self.index) == Value.ACTIVE

    def set(self, status):
        self.change_direction(Direction.OUTPUT)
        self._logger.debug(f"Setting GPIO{self.index} to `{status}`")
        self._request.set_value(self.index, Value.ACTIVE if status else Value.INACTIVE)

    def change_direction(self, direction):
        if self.direction != direction:
            self.direction = direction
            self._request.reconfigure_lines(
                config={
                    self.index: gpiod.LineSettings(
                        direction=direction
                    )
                }
            )

_gpios = {}

def _get_gpio_line(index):
    if index not in _gpios:
        _gpios[index] = GpioDigitalOutput(index=index)
        print("made new gpio", index)
    else:
        print("found gpio", index)
    return _gpios[index]

def handle_set(index, status):
    gpio_line = _get_gpio_line(index)
    gpio_line.set(status)

def handle_get(index):
    gpio_line = _get_gpio_line(index)
    return gpio_line.get()

def handle_record(index, duration: float, sampling_rate: int):
    num_samples = int(sampling_rate * duration)
    samples = []

    for i in range(num_samples):
        val = int(handle_get(index))
        samples.append(val)
        time.sleep(1 / sampling_rate)
    del _gpios[index]  # this is necessary if different tests uses record and get right after each other
    return samples
    
methods = {
    'set': handle_set,
    'get': handle_get,
    'record': handle_record,
}