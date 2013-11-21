import os
import time

import signer_pb2 as proto

def show_message(message):
    print "MESSAGE FROM DEVICE:", message
    
def show_input(input_text, message=None):
    if message:
        print "QUESTION FROM DEVICE:", message
    return raw_input(input_text)

def pin_func(input_text, message=None):
    return show_input(input_text, message)

class CallException(Exception):
    pass

class PinException(CallException):
    pass

class TrezorClient(object):
    
    def __init__(self, transport, message_func=show_message, input_func=show_input, pin_func=pin_func, debug=False):
        self.transport = transport
        
        self.message_func = message_func
        self.input_func = input_func
        self.pin_func = pin_func
        self.debug = debug

    def close(self):
        self.transport.close()

    def _pprint(self, msg):
        return "<%s>:\n%s" % (msg.__class__.__name__, msg)

    def call(self, msg):
        if self.debug:
            print '----------------------'
            print "Sending", self._pprint(msg)
        
        try:
            self.transport.session_begin()
                    
            self.transport.write(msg)
            resp = self.transport.read_blocking()
        finally:
            self.transport.session_end()
        
        if isinstance(resp, proto.Failure):
            self.message_func(resp.message)

            if resp.code == proto.Failure_ActionCancelled:
                raise CallException("Action cancelled by user")
                
            raise CallException(resp.code, resp.message)
        
        if self.debug:
            print "Received", self._pprint(resp)
            
        return resp

    def sign_plugin(self, config, protospec):
        resp = self.call(proto.SignPluginConfig(config=config, protospec=protospec))
        if isinstance(resp, proto.SignedObject):
            return resp.payload

        raise Exception("Unexpected result " % resp)
