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

from go_interface_msgs.msg import VehicleStatus
from autoware_state_machine_msgs.msg import VehicleButton, StateLock
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
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
        
        # 基本フィールドの初期化（パラメータエラー時も必要）
        self._is_emergency = False
        self._vehicle_id = ""
        self._lock_flg = False
        self._voice_flg = False
        self._active_schedule_exists = False
        
        # 配送予約状態管理（NEW）
        self._current_lock_state = StateLock.STATE_OFF
        self._verification_start_time = None
        self._verification_timeout = 15.0  # 15秒

        service_url = self.declare_parameter("delivery_reservation_service_url")
        access_token = self.declare_parameter("access_token")

        if not service_url.get_parameter_value().string_value \
                or not access_token.get_parameter_value().string_value:
            logger.error("[go_interface] Parameters not found.")
            return

        self._service_url = service_url.get_parameter_value().string_value
        self._access_token = access_token.get_parameter_value().string_value

        self._get_connect_timeout = GET_CONNECT_TIMEOUT
        self._get_read_timeout = GET_READ_TIMEOUT
        self._patch_connect_timeout = PATCH_CONNECT_TIMEOUT
        self._patch_read_timeout = PATCH_READ_TIMEOUT
        self._patch_max_retry = PATCH_MAX_RETRY
        
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Token {}".format(self._access_token)
        }

        # QoS Setting
        depth = 1
        profile = QoSProfile(depth=depth)
        transient_local_profile = QoSProfile(depth=depth, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self._vehicle_info_subcriber = self.create_subscription(
            String, "/webauto/vehicle_info", self.on_vehicle_info, profile)
        self._delivery_reservation_button_subscriber = self.create_subscription(
            VehicleButton, "/delivery_reservation_button",
            self.on_delivery_reservation_button, transient_local_profile)
        self._vehicle_status_publisher = self.create_publisher(
            VehicleStatus, "api_vehicle_status", transient_local_profile)
        self._lock_state_publisher = self.create_publisher(
            StateLock, "/go_interface/lock_state", transient_local_profile)

        # timer
        self._timer = self.create_timer(timer_period, self.output_timer)

        logger.info("[go_interface] init.")

    def on_delivery_reservation_button(self, msg):
        """配送予約ボタン押下時の処理"""
        logger = self.get_logger()
        
        # 前提条件チェック: アクティブスケジュール
        if self._active_schedule_exists:
            logger.warn(
                "[go_interface] Active schedule exists. Button press ignored.")
            return
        
        # 前提条件チェック: 検証中
        if self._current_lock_state == StateLock.STATE_VERIFICATION:
            logger.warn(
                "[go_interface] Under verification. Button press ignored.")
            return
        
        # 状態による処理分岐
        if self._current_lock_state == StateLock.STATE_OFF:
            # パターン1: 配送予約ON
            self._handle_reservation_on()
        elif self._current_lock_state == StateLock.STATE_ON:
            # パターン2: 配送予約OFF
            self._handle_reservation_off()
        else:
            logger.error(
                f"[go_interface] Unexpected lock_state: {self._current_lock_state}")

    def _handle_reservation_on(self):
        """配送予約ON処理"""
        logger = self.get_logger()
        
        # PATCH lock_flg=1 to Web server
        url = "{}/api/vehicle_status".format(self._service_url)
        payload = {
            STR_VEHICLE_ID: self._vehicle_id,
            STR_LOCK_FLG: 1
        }
        
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
        
        # STATE_VERIFICATION に遷移
        self._current_lock_state = StateLock.STATE_VERIFICATION
        self._verification_start_time = self.get_clock().now()
        self._publish_lock_state()
        logger.info("[go_interface] Reservation ON requested. STATE_VERIFICATION.")

    def _handle_reservation_off(self):
        """配送予約OFF処理"""
        logger = self.get_logger()
        
        # PATCH lock_flg=0 to Web server
        url = "{}/api/vehicle_status".format(self._service_url)
        payload = {
            STR_VEHICLE_ID: self._vehicle_id,
            STR_LOCK_FLG: 0
        }
        
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
        
        logger.info("[go_interface] Reservation OFF requested. Waiting for Web response.")

    def _check_verification_timeout(self):
        """検証タイムアウトのチェック"""
        logger = self.get_logger()
        
        # 状態チェック
        if self._current_lock_state != StateLock.STATE_VERIFICATION:
            return
        
        # verification_start_time チェック
        if self._verification_start_time is None:
            return
        
        # 経過時間計算
        current_time = self.get_clock().now()
        elapsed_ns = (current_time.nanoseconds - 
                      self._verification_start_time.nanoseconds)
        elapsed_sec = elapsed_ns / 1e9
        
        # タイムアウト判定
        if elapsed_sec > self._verification_timeout:
            logger.warn(
                f"[go_interface] Verification timeout ({self._verification_timeout}s). "
                "Resetting to STATE_OFF.")
            
            # STATE_OFF に遷移
            self._current_lock_state = StateLock.STATE_OFF
            self._verification_start_time = None
            
            # lock_state を Publish
            self._publish_lock_state()

    def _publish_lock_state(self):
        """lock_state を Publish"""
        lock_state_msg = StateLock()
        lock_state_msg.stamp = self.get_clock().now().to_msg()
        lock_state_msg.state = self._current_lock_state
        self._lock_state_publisher.publish(lock_state_msg)

    def on_vehicle_info(self, vehicle_info):
        logger = self.get_logger()
        # Parse data into json format
        try:
            json_str = json.loads(vehicle_info.data)
        except json.JSONDecodeError as e:
            self._is_emergency = True
            logger.error(f"[go_interface] Failed to parse vehicle_info: {e}")
            return
        
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
        self.fetch_from_ondemand_delivery_apps()
        self._check_verification_timeout()

    def fetch_from_ondemand_delivery_apps(self):
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
            new_lock_flg = (lock_flg_int != 0)
            
            # 状態遷移判定
            if self._current_lock_state == StateLock.STATE_OFF:
                if new_lock_flg:
                    # OFF → ON（外部からの予約）
                    logger.warn(
                        "[go_interface] lock_flg changed to true externally.")
                    self._current_lock_state = StateLock.STATE_ON
                    self._publish_lock_state()
            
            elif self._current_lock_state == StateLock.STATE_VERIFICATION:
                if new_lock_flg:
                    # VERIFICATION → ON（Web確認完了）
                    logger.info(
                        "[go_interface] Verification complete. STATE_ON.")
                    self._current_lock_state = StateLock.STATE_ON
                    self._verification_start_time = None
                    self._publish_lock_state()
            
            elif self._current_lock_state == StateLock.STATE_ON:
                if not new_lock_flg:
                    # ON → OFF（予約解除完了）
                    logger.info(
                        "[go_interface] Reservation cancelled. STATE_OFF.")
                    self._current_lock_state = StateLock.STATE_OFF
                    self._publish_lock_state()
            
            self._lock_flg = new_lock_flg
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
            allowed_methods=False,
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
