#!/usr/bin/python
'''
    Simulator of hardware bitcoin wallet.

    This is not the most elegant Python code I've ever wrote.
    It's purpose is to demonstrate features of hardware wallet
    implemented on microcontroller with very limited resources.

    I tried to avoid any dynamic language features, so rewriting
    this prototype to final device should be quite straighforward.

    @author: Marek Palatinus (slush) <info@bitcoin.cz>
    @license: GPLv3
'''
import argparse
import time

import signer_pb2 as proto
from buttons import Buttons
from layout import Layout
from display import Display
from display_buffer import DisplayBuffer

from machine import StateMachine

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64


def parse_args():
    parser = argparse.ArgumentParser(description='Signer optimized for Raspberry Pi (but works on any '
                                                 'Linux machine).')

    parser.add_argument('-k', '--keyfile', dest='keyfile', default='key.pem', help='Private key file (in PEM)')
    parser.add_argument('-s', '--shield', dest='shield', action='store_true',
                        help="Use Raspberry Pi shield with OLED display and hardware buttons.")
    parser.add_argument('-t', '--transport', dest='transport', default='cp2110',
                        help="Transport used for talking with the main computer")
    parser.add_argument('-p', '--path', dest='path', default='/dev/ttyAMA0',
                        help="Path used by the transport (usually serial port)")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='Enable low-level debugging messages')
    return parser.parse_args()


def get_transport(transport_string, path):
    if transport_string == 'cp2110':
        # Transport compatible with CP2110 HID-to-UART chip
        # (used by Trezor shield)
        from transport_cp2110 import Cp2110Transport
        return Cp2110Transport(path)

    if transport_string == 'serial':
        from transport_serial import SerialTransport
        return SerialTransport(path)

    if transport_string == 'pipe':
        from transport_pipe import PipeTransport
        return PipeTransport(path, is_device=True)

    if transport_string == 'socket':
        print "Socket transport is for development only. NEVER use socket transport with real wallet!"
        from transport_socket import SocketTransport
        return SocketTransport(path)

    if transport_string == 'fake':
        from transport_fake import FakeTransport
        return FakeTransport(path)

    raise NotImplemented("Unknown transport")


def main(args):
    # Initialize main transport
    transport = get_transport(args.transport, args.path)

    # Initialize hardware (screen, buttons)
    but = Buttons(hw=args.shield, stdin=not args.shield, pygame=not args.shield)
    buff = DisplayBuffer(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    display = Display(buff, spi=args.shield, virtual=not args.shield)
    display.init()

    # Initialize layout driver
    layout = Layout(buff)

    # Startup state machine and switch it to default state
    machine = StateMachine(args.keyfile, layout)

    display.refresh()

    # Main cycle
    while True:
        # Set True if device does something
        # False = device will sleep for a moment
        is_active = False

        try:
            # Read button states
            button = but.read()
        except KeyboardInterrupt:
            # User requested to close the app
            break

        if button is not None:
            print "Button", button
            is_active = True

            resp = machine.press_button(button)
            if resp is not None:
                print "Sending", resp
                transport.write(resp)

        # Handle main connection
        msg = transport.read()
        if msg is not None:
            print "Received", msg.__class__.__name__  # , msg
            resp = machine.process_message(msg)
            if resp is not None:
                print "Sending", resp.__class__.__name__, resp
                transport.write(resp)
                is_active = True

        # Display scrolling
        is_active |= layout.update()

        if layout.need_refresh:
            # Update display
            display.refresh()

        if not is_active:
            # Nothing to do, sleep for a moment
            time.sleep(0.1)

    # Close transports
    transport.close()

def run():
    args = parse_args()
    main(args)


if __name__ == '__main__':
    run()
