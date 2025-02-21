import logging
import time

from labgrid import Target
from labgrid.logging import basicConfig, StepLogger
from labgrid.driver import GpioDigitalOutputDriver
from labgrid.resource import LibGpiodGPIO

# enable info logging
basicConfig(level=logging.INFO)

# show labgrid steps on the console
StepLogger.start()

t = Target("main")
r = LibGpiodGPIO(t, name=None, index=60)
d = GpioDigitalOutputDriver(t, name=None)

p = t.get_driver("DigitalOutputProtocol")
print(t.resources)
p.set(True)
print(p.get())
time.sleep(2)
p.set(False)
print(p.get())
time.sleep(2)
p.set(True)
print(p.get())
