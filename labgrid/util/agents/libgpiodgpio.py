"""
This module implements switching GPIOs via libgpiod.

Takes an integer property 'index' which refers to the GPIO line.
"""

import logging
import gpiod
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
                self.index: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.ACTIVE
                )
            },
        )

    def __del__(self):
        self._request.release()
        self._chip.close()

    def get(self):
        return self._request.get_value(self.index) == Value.ACTIVE

    def set(self, status):
        self._logger.debug(f"Setting GPIO{self.index} to `{status}`")
        self._request.set_value(self.index, Value.ACTIVE if status else Value.INACTIVE)

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