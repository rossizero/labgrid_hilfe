"""All GPIO-related drivers"""
import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..resource.remote import NetworkSysfsGPIO, NetworkLibGpiodGPIO
from ..step import step
from .common import Driver
from ..util.agentwrapper import AgentWrapper


@target_factory.reg_driver
@attr.s(eq=False)
class GpioDigitalOutputDriver(Driver, DigitalOutputProtocol):

    bindings = {
        "gpio": {"SysfsGPIO", "NetworkSysfsGPIO", "LibGpiodGPIO", "NetworkLibGpiodGPIO"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.wrapper = None

    def on_activate(self):
        if isinstance(self.gpio, NetworkSysfsGPIO) or isinstance(self.gpio, NetworkLibGpiodGPIO):
            host = self.gpio.host
        else:
            host = None
        self.wrapper = AgentWrapper(host)

        if isinstance(self.gpio, NetworkSysfsGPIO) or isinstance(self.gpio, SysfsGPIO):
            self.proxy = self.wrapper.load('sysfsgpio')
        else:
            self.proxy = self.wrapper.load('libgpiodgpio')

    def on_deactivate(self):
        self.wrapper.close()
        self.wrapper = None
        self.proxy = None

    @Driver.check_active
    @step(args=['status'])
    def set(self, status):
        self.proxy.set(self.gpio.index, status)

    @Driver.check_active
    @step(result=True)
    def get(self):
        return self.proxy.get(self.gpio.index)
