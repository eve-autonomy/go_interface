#!/usr/bin/env python3
# coding: utf-8

# Copyright 2021 eve autonomy inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from go_interface_msgs.msg import ChangeLockFlg, VehicleStatus
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
import requests
from requests.adapters import HTTPAdapter
from std_msgs.msg import String
from urllib3.util.retry import Retry

# Definition of constants
API_OK_CODE = 200
STR_RESULT = "result"
STR_VEHICLE_ID = "vehicle_id"
STR_LOCK_FLG = "lock_flg"
STR_VOICE_FLG = "voice_flg"
STR_ACTIVE_SCHEDULE = "active_schedule_exists"

# Definition of setting value
GET_CONNECT_TIMEOUT = 0.8
GET_READ_TIMEOUT = 1.0
PATCH_CONNECT_TIMEOUT = 1.0
PATCH_READ_TIMEOUT = 2.0
PATCH_MAX_RETRY = 5


class GoInterface(Node):
    def __init__(self):
        super().__init__("go_interface")
        logger = self.get_logger()

        timer_period = 3.0

        service_url = self.declare_parameter("delivery_reservation_service_url")
        access_token = self.declare_parameter("access_token")

        if not service_url.get_parameter_value().string_value \
                or not access_token.get_parameter_value().string_value:
            logger.error("[go_interface] Parameters not found.")
            return

        self._is_emergency = False

        self._service_url = service_url.get_parameter_value().string_value
        self._access_token = access_token.get_parameter_value().string_value

        self._get_connect_timeout = GET_CONNECT_TIMEOUT
        self._get_read_timeout = GET_READ_TIMEOUT
        self._patch_connect_timeout = PATCH_CONNECT_TIMEOUT
        self._patch_read_timeout = PATCH_READ_TIMEOUT
        self._patch_max_retry = PATCH_MAX_RETRY

        self._vehicle_id = ""
        self._lock_flg = False
        self._voice_flg = False
        self._active_schedule_exists = False
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Token {}".format(self._access_token)
        }

        # QoS Setting
        depth = 1
        profile = QoSProfile(depth=depth)
        self._vehicle_info_subcriber = self.create_subscription(
            String, "/webauto/vehicle_info", self.on_vehicle_info, profile)
        self._change_lock_flg_subscriber = self.create_subscription(
            ChangeLockFlg, "req_change_lock_flg", self.on_change_lock_flg, profile)
        self._vehicle_status_publisher = self.create_publisher(
            VehicleStatus, "api_vehicle_status", profile)

        # timer
        self._timer = self.create_timer(timer_period, self.output_timer)

        logger.info("[go_interface] init.")

    def on_change_lock_flg(self, change_lock_flg):
        logger = self.get_logger()
        # Check if vehicle id has been updated
        if not self._vehicle_id:
            return

        lock_flg = change_lock_flg.flg

        # Patch lock-flg from server via REST API
        url = "{}/api/vehicle_status".format(self._service_url)
        payload = {
            STR_VEHICLE_ID: self._vehicle_id,
            STR_LOCK_FLG: int(lock_flg)}

        try:
            session = self.retry_session(retries=self._patch_max_retry)
            res = session.patch(
                url,
                headers=self._headers,
                data=json.dumps(payload),
                timeout=(
                    self._patch_connect_timeout,
                    self._patch_read_timeout))
            res.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(
                "[go_interface] Unable to communicate with the server. {}".format(e))
            return

        if res.status_code != API_OK_CODE:
            logger.error(
                "[go_interface] Server returned an error code : {}.".format(
                    res.status_code))
            return

        response_data = res.json()

        # Comparing response data with the owned data
        if (self._vehicle_id !=
                response_data.get(STR_RESULT).get(STR_VEHICLE_ID)):
            logger.error(
                "[go_interface] Response data does not match the owned data.")
            return
        
        if response_data.get(STR_RESULT).get(STR_LOCK_FLG) is None:
            logger.error(
                "[go_interface] Failed to parse lock_flg retrieved from server.")
            return
        
        self.get_vehicle_status()


    def on_vehicle_info(self, vehicle_info):
        logger = self.get_logger()
        # Parse data into json format
        json_str = json.loads(vehicle_info.data)
        # Get vehicle_id
        vehicle_id = json_str.get(STR_VEHICLE_ID)
        if vehicle_id is None:
            self._is_emergency = True
            logger.error(
                "[go_interface] Vehicle ID could not be obtained from FMS.")
            return
        self._vehicle_id = vehicle_id
        self._is_emergency = False

    def output_timer(self):
        logger = self.get_logger()
        if (self._is_emergency):
            logger.error("[go_interface] is_emergency.")
            return
        if (self._vehicle_id==""):
            logger.error("[go_interface] _vehicle_id is unset.")
            return
        self.get_vehicle_status()

    def get_vehicle_status(self):
        logger = self.get_logger()

        # Get vehicle-status from server via REST API
        url = "{0}/api/vehicle_status?vehicle_id={1}".format(
            self._service_url, self._vehicle_id)

        try:
            res = requests.get(
                url,
                headers=self._headers,
                timeout=(
                    self._get_connect_timeout, self._get_read_timeout))
            res.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(
                "[go_interface] Unable to communicate with the server. {}".format(e))
            return

        if res.status_code != API_OK_CODE:
            logger.error(
                "[go_interface] The server returned an error code : {}.".format(
                    res.status_code))
            return

        response_data = res.json()

        # Comparing response data with the owned data
        if(self._vehicle_id !=
                response_data.get(STR_RESULT).get(STR_VEHICLE_ID)):
            logger.error(
                "[go_interface] Response data does not match the owned data.")
            return

        # Check vehicle status of response data
        lock_flg_int = response_data.get(STR_RESULT).get(STR_LOCK_FLG)
        if lock_flg_int is not None:
            self._lock_flg = (lock_flg_int != 0)
        else:
            logger.error(
                "[go_interface] Failed to parse lock_flg retrieved from server.")

        voice_flg_int = response_data.get(STR_RESULT).get(STR_VOICE_FLG)
        if voice_flg_int is not None:
            self._voice_flg = (voice_flg_int != 0)
        else:
            logger.error(
                "[go_interface] Failed to parse voice_flg retrieved from server.")

        active_schedule_exists_int = response_data.get(STR_RESULT).get(
            STR_ACTIVE_SCHEDULE)
        if active_schedule_exists_int is not None:
            self._active_schedule_exists = (active_schedule_exists_int != 0)
        else:
            logger.error(
                "[go_interface] \
                Failed to parse active_schedule_exists retrieved from server.")

        # Publish vehicle-status to autoware-state-machine
        vehicle_status = VehicleStatus()
        vehicle_status.stamp = self.get_clock().now().to_msg()
        vehicle_status.lock_flg = self._lock_flg
        vehicle_status.voice_flg = self._voice_flg
        vehicle_status.active_schedule_exists = self._active_schedule_exists
        self._vehicle_status_publisher.publish(vehicle_status)

    def retry_session(self, retries, session=None, backoff_factor=0.3):
        session = session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            method_whitelist=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session


def main(args=None):
    rclpy.init(args=args)

    node = GoInterface()
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
