#!/bin/bash

cd `dirname $0`

# This cycle emulates device reset on DebugLinkStop message
while [ true ]; do

    rm -f pipe.*
    python signer/__init__.py -t pipe -p pipe.signer
    sleep 1

done
