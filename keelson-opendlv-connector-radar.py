#!/usr/bin/env python3

# Copyright (C) 2024 OpenDLV

# sysv_ipc is needed to access the shared memory where the camera image is present.
# import sysv_ipc
# numpy and cv2 are needed to access, modify, or display the pixels
import numpy as np
# OD4Session is needed to send and receive messages
import OD4Session
# Import the OpenDLV messages.
import opendlv_message_standard_pb2

# # Import the recommended parts for keelson
import time
import json
import atexit
import logging
import argparse
import warnings
from functools import lru_cache
from contextlib import contextmanager
from collections import deque
import zenoh
from google.protobuf.json_format import MessageToDict
import datetime
# from typing import Tuple

import keelson
from keelson.payloads.PointCloud_pb2 import PointCloud
from keelson.payloads.PackedElementField_pb2 import PackedElementField


################################################################################
#Paramaters for Zenoh/Keelson



################################################################################
#Paramaters for opendlv
PointCloudMsgID = 1061


################################################################################
################################################################################
# Main loop that sets up zenoh arguments and then spins the primary loop. 

if __name__ == "__main__":

   parser = argparse.ArgumentParser(
      prog="opendlv-keelson-connector-radar",
      formatter_class=argparse.ArgumentDefaultsHelpFormatter,
   )
   parser.add_argument("--log-level", type=int, default=logging.WARNING)
   parser.add_argument(
      "--connect",
      action="append",
      type=str,
      help="Endpoints to connect to.",
   )

   parser.add_argument("-r", "--realm", type=str, required=True)
   parser.add_argument("-e", "--entity-id", type=str, required=True)
   parser.add_argument("--cid", type=int, default=111)
   parser.add_argument("--srca", type=str, default="radar/1201")
   parser.add_argument("--srcb", type=str, default="radar/1202")

   ################################################################################
   # Parse arguments and start zenoh session
   zargs = parser.parse_args()

   # Setup logger
   logging.basicConfig(
      format="%(asctime)s %(levelname)s %(name)s %(message)s", level=zargs.log_level
   )
   logging.captureWarnings(True)
   warnings.filterwarnings("once")

   ## Construct session
   logging.info("Opening Zenoh session...")
   
   conf = zenoh.Config()

   if zargs.connect is not None:
      conf.insert_json5(zenoh.Config.CONNECT_KEY, json.dumps(zargs.connect))
   
   with zenoh.open(conf) as zsession:
      logging.info("Zenoh session opened!")

      buffer = deque(maxlen=5000)

      ################################################################################
      # Functions to recieve envelopes

      

      def put_to_zenoh(key: str, payload: bytes, session: zenoh.Session, args: argparse.Namespace):
         envelope = keelson.enclose(payload)
         logging.debug("...enclosed into envelope")

         session.put(
            key,
            envelope,
            priority=zenoh.Priority.REAL_TIME,
            congestion_control=zenoh.CongestionControl.BLOCK,
         )
         logging.debug("...published to zenoh!")

      def onMessage(msg, v1, v2):
         logging.debug("Received..")
         logging.debug (v1) ## ID
         logging.debug (v2) ## timings
         logging.debug (len(msg.data)) ## msg

         point_cloud = PointCloud()
         point_cloud.timestamp.FromDatetime(v2[2])
         # Zero relative position
         point_cloud.pose.position.x = 0
         point_cloud.pose.position.y = 0
         point_cloud.pose.position.z = 0


         # Identity quaternion
         point_cloud.pose.orientation.x = 0
         point_cloud.pose.orientation.y = 0
         point_cloud.pose.orientation.z = 0
         point_cloud.pose.orientation.w = 1

         # Fields
         point_cloud.fields.add(name="x", offset=0, type=PackedElementField.NumericType.FLOAT32)
         point_cloud.fields.add(name="y", offset=4, type=PackedElementField.NumericType.FLOAT32)
         point_cloud.fields.add(name="i", offset=8, type=PackedElementField.NumericType.FLOAT32)

         point_cloud.point_stride = 12
         point_cloud.data = msg.data

         buffer.append((point_cloud, v1))\


      ################################################################################
      # Start openDLV session
      odsession = OD4Session.OD4Session(cid=zargs.cid)
      print("Params set, beginning listener")
      odsession.registerMessageCallback(PointCloudMsgID, onMessage, opendlv_message_standard_pb2.opendlv_proxy_PointCloudAngularLayeredReading)
      odsession.connect()

      key1 = keelson.construct_pubsub_key(
               realm=zargs.realm,
               entity_id=zargs.entity_id,
               subject="point_cloud",
               source_id=zargs.srca,
            )
      logging.debug(f"key1:{ key1}")

      key2 = keelson.construct_pubsub_key(
               realm=zargs.realm,
               entity_id=zargs.entity_id,
               subject="point_cloud",
               source_id=zargs.srcb,
            )

      logging.debug(f"key2:{ key2}")

      pub1 = zsession.declare_publisher(key1,
            priority=zenoh.Priority.REAL_TIME,
            congestion_control=zenoh.CongestionControl.DROP)
            
      pub2 = zsession.declare_publisher(key2,
            priority=zenoh.Priority.REAL_TIME,
            congestion_control=zenoh.CongestionControl.DROP)
            

      while (odsession.isRunning and odsession.isConnected):
         time.sleep(0.001)
         while buffer:
            try:
               point_cloud, idx = buffer.popleft() ## Oldest first.
               _currPC = point_cloud.timestamp.toDateTime()
               _currSysC = datetime.now
               asyncCurr= _currSysC - _currPC
               logging.debug(f"Current Async: {asyncCurr}" )
               payload = point_cloud.SerializeToString()
               envelope = keelson.enclose(payload)
               logging.debug(f"id:{idx}")
            except:
               print("Could not serialise the point_cloud")
               continue
            if idx == 1201:
               pub1.put(envelope)
            elif idx == 1202:
               pub2.put(envelope)
            logging.debug("Published!")

      logging.debug("Connection broken: Closing")

      def _on_exit():
         zsession.close()

      atexit.register(_on_exit)



############################################################################

############################################################################