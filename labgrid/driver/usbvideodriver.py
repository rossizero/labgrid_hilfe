import re
import subprocess
import attr
import numpy as np
from enum import StrEnum
import yaml
import os

from ..exceptions import InvalidConfigError
from ..factory import target_factory
from ..protocol import VideoProtocol
from .common import Driver


class VideoQuality(StrEnum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"

    @classmethod
    def from_string(cls, name: str, default=MID):
        return next((s for s in cls if s.value.lower() == name.lower()), default)
    
@target_factory.reg_driver
@attr.s(eq=False)
class USBVideoDriver(Driver, VideoProtocol):
    bindings = {
        "video": {"USBVideo", "NetworkUSBVideo"},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.device_configs = self._load_config()

        self._prepared = False

        self.encoding_process = None
        self.decoding_process = None

        self._running = False

        self.width = -1
        self.height = -1

        self.channels = 4
    
    def _load_config(self):
        config = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "usbvideodevices.yaml"
            )
        try:
            with open(config, "r") as file:
                return yaml.safe_load(file)["devices"]
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return {}
    
    def is_stream_open(self):
        return self._running
    
    def get_qualities(self):
        device_key = f"{self.video.vendor_id:04x}:{self.video.model_id:04x}"
        device_config = self.device_configs.get(device_key, self.device_configs.get("default"))
        qualities = []
        for q, cfg in device_config["qualities"].items():
            qualities.append((VideoQuality[q].value, f"{device_config['format']},{cfg}"))
        return ("MID", qualities)  # expected to be that way in remote/client
    
    def _select_caps(self, hint:VideoQuality=None):
        default, variants = self.get_qualities()
        variant = hint.value if hint else default
        for name, caps in variants:
            if name == variant:
                w, h = self._extract_camera_params(caps)
                if w is None or h is None:
                    break
                else:
                    self.width = w
                    self.height = h
                    return caps
        raise InvalidConfigError(
            f"Unknown video format {variant} for device {self.video.vendor_id:04x}:{self.video.model_id:04x}"  # pylint: disable=line-too-long
        )

    def _extract_camera_params(self, caps):
        width_match = re.search(r'width=(\d+)', caps)
        height_match = re.search(r'height=(\d+)', caps)

        width = int(width_match.group(1)) if width_match else None
        height = int(height_match.group(1)) if height_match else None

        return width, height
    
    def _get_pipeline(self, quality:VideoQuality=VideoQuality.MID, controls:str=None):
        device_key = f"{self.video.vendor_id:04x}:{self.video.model_id:04x}"
        device_config =  self.device_configs.get(device_key)

        caps = self._select_caps(quality)
        controls = controls or device_config.get("controls")
        inner = device_config.get("inner")

        pipeline = f"v4l2src device={self.video.path} "
        if controls:
            pipeline += f"extra-controls=c,{controls} "
        pipeline += f"! {caps} "
        if inner:
            pipeline += f"! {inner} "
        pipeline += "! matroskamux streamable=true ! fdsink"

        return pipeline


    @Driver.check_active
    def stream(self, caps_hint:str="low", controls=None):
        pipeline = self._get_pipeline(VideoQuality.from_string(caps_hint), controls)
        
        tx_cmd = self.video.command_prefix + ["gst-launch-1.0", "-q"]
        tx_cmd += pipeline.split()

        rx_cmd = ["gst-launch-1.0", "playbin3", "buffer-duration=0", "uri=fd://0"]

        tx = subprocess.Popen(
            tx_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )
        rx = subprocess.Popen(
            rx_cmd,
            stdin=tx.stdout,
            stdout=subprocess.DEVNULL,
        )

        # wait until one subprocess has terminated
        while True:
            try:
                tx.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
            try:
                rx.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass

        rx.terminate()
        tx.terminate()

        rx.communicate()
        tx.communicate()
    
    @Driver.check_active
    def start_stream(self, caps_hint:str="mid", controls=None):
        pipeline = self._get_pipeline(VideoQuality.from_string(caps_hint), controls)
        tx_cmd = self.video.command_prefix + ["gst-launch-1.0", "-q"]
        tx_cmd += pipeline.split()

        decode_cmd = [
            "gst-launch-1.0", "-q",
            "fdsrc", "fd=0",
            "!", "matroskademux",
            "!", "jpegdec",
            "!", "videoconvert",
            "!", "video/x-raw(ANY),format=BGRA", # this took me hours..
            "!", "fdsink", "fd=1"
        ]

        self.encoding_process = subprocess.Popen(
            tx_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE
        )

        self.decoding_process = subprocess.Popen(
            decode_cmd,
            stdin=self.encoding_process.stdout,
            stdout=subprocess.PIPE
        )

        self._running = True

    @Driver.check_active
    def stop_stream(self):
        self._running = False

        self.encoding_process.terminate()
        self.decoding_process.terminate()

        self.encoding_process.communicate()
        self.decoding_process.communicate()

    @Driver.check_active
    def read(self) -> bytes:
        size = self.width * self.height * self.channels
        chunk = self.decoding_process.stdout.read(size)
        if chunk:
            frame = np.frombuffer(chunk, dtype=np.uint8).reshape((self.height, self.width, self.channels))
        return (True, frame) if chunk else (False, None)  # mimic opencv videocapture