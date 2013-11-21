import time
import random
import base64
import hashlib
import math
import os
import traceback

import signer_pb2 as proto

import sign_plugin

class PinState(object):
    def __init__(self, layout, storage):
        self.layout = layout
        self.storage = storage
        self.matrix = None

        self.set_main_state()

    def set_main_state(self):
        self.cancel()

    def is_waiting(self):
        return self.func is not None

    def _generate_matrix(self):
        # Generate random order of numbers 1-9
        matrix = range(1, 10)
        random.shuffle(matrix)
        return matrix

    def _decode_from_matrix(self, pin_encoded):
        # Receive pin encoded using a matrix
        # Return original PIN sequence
        pin = ''.join([ str(self.matrix[int(x) - 1]) for x in pin_encoded ])        
        return pin    
        
    def request(self, pass_or_check, func, *args):
        self.pass_or_check = pass_or_check
        self.func = func
        self.args = args
        self.matrix = self._generate_matrix()
        
        self.layout.show_matrix(self.matrix)
        return proto.PinMatrixRequest()

    def check(self, pin_encoded):
        try:
            pin = self._decode_from_matrix(pin_encoded)
        except ValueError:
            return proto.Failure(code=proto.Failure_SyntaxError, message="Syntax error")
        
        if self.pass_or_check:
            # Pass PIN to method
            msg = self.func(pin, *self.args)
            self.cancel()
            return msg
        else:
            # Check PIN against device's internal PIN
            if pin == self.storage.get_pin():
                func = self.func
                args = self.args
                self.cancel()
                self.storage.clear_pin_attempt()
                msg = func(*args)

                return msg
            else:
                self.storage.increase_pin_attempt()
                print "Invalid PIN, waiting %s seconds" % self.storage.get_pin_delay()
                time.sleep(self.storage.get_pin_delay())
                self.cancel()
                self.set_main_state()
                return proto.Failure(code=proto.Failure_PinInvalid, message="Invalid PIN")

    def cancel(self):
        self.pass_or_check = False
        self.func = None
        self.args = []
        self.matrix = None

class YesNoState(object):
    def __init__(self, layout):
        self.layout = layout

        self.set_main_state()

    def set_main_state(self):
        self.cancel()

    def is_waiting(self):
        # We're waiting for confirmation from computer
        return self.func is not None and self.pending

    def allow(self):
        # Computer confirms that we can accept button press now
        self.pending = False

    def cancel(self):
        self.pending = False
        self.decision = None
        self.func = None
        self.args = []

    def request(self, message, question, yes_text, no_text, func, *args):
        self.layout.show_question(message, question, yes_text, no_text)

        self.func = func
        self.args = args

        self.allow()

    def store(self, button):
        if not self.func:
            return

        self.decision = button

    def resolve(self):
        if not self.func:
            # We're not waiting for hw buttons
            return

        if self.pending:
            # We still didn't received ButtonAck from computer
            return

        if self.decision is None:
            # We still don't know user's decision (call yesno_store() firstly)
            return

        if self.decision is True:
            ret = self.func(*self.args)
        else:
            self.set_main_state()
            ret = proto.Failure(code=proto.Failure_ActionCancelled, message='Action cancelled by user')

        self.func = None
        self.args = []
        return ret


class StateMachine(object):
    def __init__(self, keyfile, layout):
        self.keyfile = keyfile
        self.layout = layout

        self.yesno = YesNoState(layout)

        self.set_main_state()

    def protect_call(self, yesno_message, question, no_text, yes_text, func, *args):
        '''
            yesno_message - display text on the main part of the display
            question - short question in status bar (above buttons)
            no_text - text of the left button
            yes_text - text of the right button
            func - which function to call when user passes the protection
            *args - arguments for func
        '''  

        # If confirmed, call final function directly
        return self.yesno.request(yesno_message, question, yes_text, no_text, func, *args)

    def clear_custom_message(self):
        if self.custom_message:
            self.custom_message = False
            self.layout.show_logo(None, self.storage.get_label())

    def press_button(self, button):
        if button and self.custom_message:
            self.clear_custom_message()

        self.yesno.store(button)
        ret = self.yesno.resolve()
        if isinstance(ret, proto.Failure):
            self.set_main_state()
        return ret

    def set_main_state(self):
        # Switch device to default state
        self.yesno.set_main_state()
        # self.pin.set_main_state()

        # Display is showing custom message which just wait for "Continue" button,
        # but doesn't require any interaction with computer
        self.custom_message = False

        self.layout.show_logo(None, "FIRMWARE SIGNER")

    def _sign_plugin_config(self, config, protospec):
        key_pem = open(os.path.expanduser('~/.trezor_key.pem'), 'r').read()
        payload = sign_plugin.sign(key_pem, config, protospec)

        self.set_main_state()
        return proto.SignedObject(payload=payload)

    def _process_message(self, msg):
        if isinstance(msg, proto.SignPluginConfig):
            s = msg.config
            x = [ s[i * 21:i * 21 + 21] for i in range(int(math.ceil(len(s) / 21.))) ]
            return self.protect_call(["Sign plugin config?"] + x, '', '{ Cancel', 'Confirm }', self._sign_plugin_config, msg.config, msg.protospec)

        self.set_main_state()
        return proto.Failure(code=proto.Failure_UnexpectedMessage, message="Unexpected message")

    def process_message(self, msg):
        # Any exception thrown during message processing
        # will result in Failure message instead of application crash
        try:
            ret = self._process_message(msg)
            if isinstance(ret, proto.Failure):
                self.set_main_state()
            return ret
        except Exception as exc:
            traceback.print_exc()
            self.set_main_state()
            return proto.Failure(message=str(exc))
