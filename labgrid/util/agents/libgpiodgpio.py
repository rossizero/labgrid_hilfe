"""
This module implements switching GPIOs via libgpiod.

Takes an integer property 'index' which refers to the GPIO line.
"""

import logging
import gpiod

class GpioDigitalOutput:
    _chip_name = '/dev/gpiochip0'

    def __init__(self, index):
        self._logger = logging.getLogger(f"Device: GPIO{index}")
        self.index = index
        self._chip = gpiod.Chip(self._chip_name)

        # Request the GPIO line as output
        self._line = self._chip.get_line(index)
        self._line.request(consumer="GpioDigitalOutput", type=gpiod.LINE_REQ_DIR_OUT)

    def __del__(self):
        self._line.release()
        self._chip.close()

    def get(self):
        return self._line.get_value() == 1

    def set(self, status):
        self._logger.debug(f"Setting GPIO{self.index} to `{status}`")
        value = 1 if status else 0
        self._line.set_value(value)

_gpios = {}

def _get_gpio_line(index):
    if index not in _gpios:
        _gpios[index] = GpioDigitalOutput(index=index)
    return _gpios[index]

def handle_set(index, status):
    gpio_line = _get_gpio_line(index)
    gpio_line.set(status)

def handle_get(index):
    gpio_line = _get_gpio_line(index)
    return gpio_line.get()

methods = {
    'set': handle_set,
    'get': handle_get,
}