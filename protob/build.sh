#!/bin/bash

cd `dirname $0`

protoc --python_out=../signer/ -I/usr/include -I. signer.proto
protoc --python_out=../signer/ -I/usr/include -I. config.proto
