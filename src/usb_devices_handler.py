#!/usr/bin/env python3
import hashlib
import logging

import gateway_devices
from mdns_advertiser import MDNSAdvertiser
from rfc2217_device import RFC2217Device

logger = logging.getLogger(__name__)


class UsbDevicesHandler:
    def __init__(self, network_interface):
        self.network_interface = network_interface
        self.valid_gateways = gateway_devices.__all__
        self.handled_devices = {}

    def is_valid_device(self, device):
        device_identifier = self.__get_device_identifier(device)
        if device_identifier in self.valid_gateways:
            return True
        return False

    def create_usb_device(self, device):
        ident = device.get("DEVNAME")
        if ident in self.handled_devices:
            logger.warn("Device at '{}' already handled".format(ident))
            return

        constructor = self.__get_gateway_constructor(device)
        if not constructor:
            return
        gateway_device = constructor(device)

        usb_device = UsbDevice(gateway_device, self.network_interface)
        usb_device.start()

        self.handled_devices[usb_device.get_serial_port()] = usb_device

    def delete_usb_device(self, device):
        ident = device.get("DEVNAME")

        device = self.handled_devices.get(ident)
        if not device:
            logger.warn("Device at '{}' not handled".format(ident))
            return

        device.stop()
        del self.handled_devices[ident]

    def stop_all_devices(self):
        for device in self.handled_devices.values():
            device.stop()

        self.handled_devices = {}

    @staticmethod
    def __get_device_identifier(device):
        id_model = device.get("ID_MODEL_ID")
        id_vendor = device.get("ID_VENDOR_ID")
        enc_vendor = device.get("ID_VENDOR_ENC")
        if not id_model or not id_vendor or not enc_vendor:
            return None
        identifier_string = id_model + id_vendor + enc_vendor
        return hashlib.sha224(identifier_string.encode("utf-8")).hexdigest()

    def __get_gateway_constructor(self, device):
        device_identifier = self.__get_device_identifier(device)
        if not device_identifier:
            return None
        return self.valid_gateways.get(device_identifier)


class UsbDevice:
    def __init__(self, gateway_device, network_interface):
        self.gateway_device = gateway_device
        self.network_interface = network_interface
        self.rfc2217_connection = None
        self.mdns_advertiser = None

    def start(self):
        logger.info(
            "Device '{}' ('{}') - type {} - has been created on port {}".
            format(
                self.gateway_device.get_name(),
                self.gateway_device.get_serial_port(),
                self.gateway_device.__class__.__name__,
                self.gateway_device.get_tcp_port(),
            ))
        __type = ("_{}._rfc2217".format(self.gateway_device.get_protocol())
                  if self.gateway_device.get_protocol() else "_rfc2217")
        self.mdns_advertiser = MDNSAdvertiser(
            __type,
            self.gateway_device.get_name_unique(),
            self.gateway_device.get_tcp_port(),
            self.gateway_device.get_properties(),
            None,
            self.network_interface,
        )
        self.rfc2217_connection = RFC2217Device(
            self.gateway_device.get_serial_port(),
            self.gateway_device.get_tcp_port())
        self.rfc2217_connection.start()
        self.mdns_advertiser.start()

    def stop(self):
        if self.rfc2217_connection:
            self.rfc2217_connection.stop()
        if self.mdns_advertiser:
            self.mdns_advertiser.stop()
        logger.info("Device '{}' ('{}') has been deleted".format(
            self.gateway_device.get_name(),
            self.gateway_device.get_serial_port()))

    def get_serial_port(self):
        return self.gateway_device.get_serial_port()
