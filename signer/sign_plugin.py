#!/usr/bin/python
import subprocess
import os
import json
import time
import ecdsa
import hashlib
import binascii
from google.protobuf.descriptor_pb2 import FileDescriptorSet

PROTOBUF_PROTO_DIR=os.environ.get('PROTOBUF_PROTO_DIR', '/usr/include/')
TREZOR_PROTO_DIR = os.environ.get('TREZOR_PROTO_DIR', '/tmp/')

def compile_config():
    cmd = "protoc --python_out=. -I" + PROTOBUF_PROTO_DIR + " -I. protob/config.proto"
    subprocess.check_call(cmd.split())

def parse_json(config_json):
    return json.loads(open(config_json, 'r').read())


def get_compiled_proto(proto):
    # Compile trezor.proto to binary format
    pdir = os.path.abspath(TREZOR_PROTO_DIR)
    pfile = os.path.join(pdir, "trezor.proto")

    f = open(pfile, 'w')
    f.write(proto)
    f.close()

    cmd = "protoc -I" + PROTOBUF_PROTO_DIR + " -I" + pdir  + " " + pfile + " -otrezor.bin"

    subprocess.check_call(cmd.split())

    # Load compiled protocol description to string
    proto = open('trezor.bin', 'r').read()
    os.unlink('trezor.bin')

    # Parse it into FileDescriptorSet structure
    compiled = FileDescriptorSet()
    compiled.ParseFromString(proto)
    return compiled

def compose_message(json, proto):
    import config_pb2

    cfg = config_pb2.Configuration()
    cfg.valid_until = int(time.time()) + json['valid_days'] * 3600 * 24
    cfg.wire_protocol.MergeFrom(proto)

    for url in json['whitelist_urls']:
        cfg.whitelist_urls.append(str(url))

    for url in json['blacklist_urls']:
        cfg.blacklist_urls.append(str(url))

    for dev in json['known_devices']:
        desc = cfg.known_devices.add()
        desc.vendor_id = int(dev[0], 16)
        desc.product_id = int(dev[1], 16)

    return cfg.SerializeToString()

def sign_message(data, key_pem):
    # curve = ecdsa.curves.SECP256k1
    # x = ecdsa.keys.SigningKey.generate(curve=curve)
    key = ecdsa.keys.SigningKey.from_pem(key_pem)

    verify = key.get_verifying_key()
    print "Verifying key:"
    print verify.to_pem()

    return key.sign_deterministic(data, hashfunc=hashlib.sha256)

def pack_datafile(signature, data):
    if len(signature) != 64:
        raise Exception("Signature must be 64 bytes long")

    return binascii.hexlify(signature) + binascii.hexlify(data)

def sign(key_pem, config_json, protospec):
    compile_config()
    config = json.loads(config_json)
    proto = get_compiled_proto(protospec)

    data = compose_message(config, proto)
    signature = sign_message(data, key_pem)

    return pack_datafile(signature, data)

if __name__ == '__main__':
    key_pem = ''
    print "Paste ECDSA private key (in PEM format) and press Enter:"
    while True:
        inp = raw_input()
        if inp == '':
            break

        key_pem += inp + "\n"

    # key_pem = open('sample.key', 'r').read()

    compile_config()
    json = parse_json('config.json')
    proto = get_compiled_proto(open('../../trezor-emu/protob/trezor.proto', 'r').read())

    data = compose_message(json, proto)
    signature = sign_message(data, key_pem)

    signed = pack_datafile(signature, data)
    fp = open('config_signed.bin', 'w')
    fp.write(signed)
    fp.close()

    print "Signature and data stored to", filename
