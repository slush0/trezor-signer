#!/usr/bin/python
import os
import binascii
import argparse
import json
import threading
import urllib2

from signer.client import TrezorClient
from signer.protobuf_json import pb2json

def parse_args(commands):
    parser = argparse.ArgumentParser(description='Commandline tool for Trezor devices.')
    parser.add_argument('-t', '--transport', dest='transport',  choices=['usb', 'serial', 'pipe', 'socket'], default='usb', help="Transport used for talking with the device")
    parser.add_argument('-p', '--path', dest='path', default='', help="Path used by the transport (usually serial port)")
    parser.add_argument('-j', '--json', dest='json', action='store_true', help="Prints result as json object")

    cmdparser = parser.add_subparsers(title='Available commands')
    
    for cmd in commands._list_commands():
        func = object.__getattribute__(commands, cmd)
        try:
            help = func.help
        except AttributeError:
            help = ''
            
        try:
            arguments = func.arguments
        except AttributeError:
            arguments = ((('params',), {'nargs': '*'}),)
        
        item = cmdparser.add_parser(cmd, help=func.help)
        for arg in arguments:
            item.add_argument(*arg[0], **arg[1])
            
        item.set_defaults(func=func)
        item.set_defaults(cmd=cmd)
    
    return parser.parse_args()

def get_transport(transport_string, path, **kwargs):
    if transport_string == 'usb':
        from signer.transport_hid import HidTransport

        if path == '':
            try:
                path = list_usb()[0]
            except IndexError:
                raise Exception("No Trezor found on USB")

        return HidTransport(path, **kwargs)
 
    if transport_string == 'serial':
        from signer.transport_serial import SerialTransport
        return SerialTransport(path, **kwargs)

    if transport_string == 'pipe':
        from signer.transport_pipe import PipeTransport
        return PipeTransport(path, is_device=False, **kwargs)
    
    if transport_string == 'socket':
        from signer.transport_socket import SocketTransportClient
        return SocketTransportClient(path, **kwargs)
    
    if transport_string == 'fake':
        from signer.transport_fake import FakeTransport
        return FakeTransport(path, **kwargs)
    
    raise NotImplemented("Unknown transport")

def load_file_url(filename):
    if filename.startswith('http'):
        fp = urllib2.urlopen(filename)
    else:
        fp = open(filename, 'r')

    data = fp.read()
    fp.close()
    return data

class Commands(object):
    def __init__(self, client):
        self.client = client
        
    @classmethod
    def _list_commands(cls):
        return [ x for x in dir(cls) if not x.startswith('_') ]
  
    def list(self, args):
        # Fake method for advertising 'list' command
        pass
 
    def sign_plugin(self, args):
        if not args.config:
            raise Exception("Must provide config filename/URL")

        if not args.protospec:
            raise Exception("Must provide protobuf spec filename/URL")

        config = load_file_url(args.config)
        protospec = load_file_url(args.protospec)

        print config

        signed = self.client.sign_plugin(config=config, protospec=protospec)
        f = open('config_signed.bin', 'w')
        f.write(signed)
        f.close()

        return "Signed config stored in config_signed.bin"

    list.help = 'List connected Trezor USB devices'
    sign_plugin.help = 'Sign plugin config'

    sign_plugin.arguments = (
        (('protospec',), {'type': str}),
        (('config',), {'type': str}),
    )

def list_usb():
    from signer.transport_hid import HidTransport
    devices = HidTransport.enumerate()
    return devices

def main():
    args = parse_args(Commands)

    if args.cmd == 'list':
        devices = list_usb()
        if args.json:
            print json.dumps(devices)
        else:
            for dev in devices:
                print dev
        return

    transport = get_transport(args.transport, args.path)
    client = TrezorClient(transport)
    cmds = Commands(client)
    
    res = args.func(cmds, args)
    
    if args.json:
        print json.dumps(res, sort_keys=True, indent=4)
    else:
        print res
    
if __name__ == '__main__':
    main()
