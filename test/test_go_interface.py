#!/usr/bin/env python3
# coding: utf-8

# Copyright 2024 eve autonomy inc. All Rights Reserved.

import json
import pytest
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from rclpy.duration import Duration
from std_msgs.msg import String
from unittest.mock import patch, MagicMock
import requests

# テスト対象のインポート
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'go_interface'))
from go_interface import GoInterface

# メッセージ型のインポート
from go_interface_msgs.msg import VehicleStatus
from autoware_state_machine_msgs.msg import VehicleButton, StateLock


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Mock クラス
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GoInterfaceMock(GoInterface):
    """テスト用のMockクラス
    
    親クラスのprotectedフィールドにアクセスするためのGetterを提供
    """
    
    # ──────────────────────────────────────
    # Getter: 基本情報
    # ──────────────────────────────────────
    
    def get_vehicle_id(self) -> str:
        """vehicle_id の取得"""
        return self._vehicle_id
    
    def get_is_emergency(self) -> bool:
        """is_emergency フラグの取得"""
        return self._is_emergency
    
    # ──────────────────────────────────────
    # Getter: WebAPI関連
    # ──────────────────────────────────────
    
    def get_lock_flg(self) -> bool:
        """lock_flg の取得"""
        return self._lock_flg
    
    def get_voice_flg(self) -> bool:
        """voice_flg の取得"""
        return self._voice_flg
    
    def get_active_schedule_exists(self) -> bool:
        """active_schedule_exists の取得"""
        return self._active_schedule_exists
    
    # ──────────────────────────────────────
    # Getter: 状態管理
    # ──────────────────────────────────────
    
    def get_current_lock_state(self) -> int:
        """current_lock_state の取得"""
        return self._current_lock_state
    
    def get_verification_start_time(self):
        """verification_start_time の取得"""
        return self._verification_start_time
    
    def get_verification_timeout(self) -> float:
        """verification_timeout の取得"""
        return self._verification_timeout
    
    # ──────────────────────────────────────
    # Setter: テスト用の状態設定
    # ──────────────────────────────────────
    
    def set_vehicle_id(self, vehicle_id: str):
        """vehicle_id の設定"""
        self._vehicle_id = vehicle_id
    
    def set_is_emergency(self, is_emergency: bool):
        """is_emergency フラグの設定"""
        self._is_emergency = is_emergency
    
    def set_current_lock_state(self, state: int):
        """current_lock_state の設定"""
        self._current_lock_state = state
    
    def set_verification_start_time(self, time):
        """verification_start_time の設定"""
        self._verification_start_time = time
    
    def set_active_schedule_exists(self, exists: bool):
        """active_schedule_exists の設定"""
        self._active_schedule_exists = exists
    
    def set_lock_flg(self, lock_flg: bool):
        """lock_flg の設定"""
        self._lock_flg = lock_flg


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fake Web Server
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FakeWebServer:
    """Webサーバーのスタブクラス"""
    
    def __init__(self):
        self._vehicle_status = {
            "vehicle_id": "test_vehicle_001",
            "lock_flg": 0,
            "voice_flg": 0,
            "active_schedule_exists": 0
        }
        self._request_count = 0
        self._should_fail = False
        self._status_code = 200
    
    def get_vehicle_status(self, url, **kwargs) -> MagicMock:
        """GET /api/vehicle_status のスタブ"""
        self._request_count += 1
        
        if self._should_fail:
            raise requests.exceptions.RequestException("Network error")
        
        response = MagicMock()
        response.status_code = self._status_code
        response.json.return_value = {"result": self._vehicle_status}
        return response
    
    def patch_vehicle_status(self, url, **kwargs) -> MagicMock:
        """PATCH /api/vehicle_status のスタブ"""
        self._request_count += 1
        
        if self._should_fail:
            raise requests.exceptions.RequestException("Network error")
        
        # payloadからlock_flgを取得
        if 'data' in kwargs:
            payload = json.loads(kwargs['data'])
            lock_flg = payload.get('lock_flg', 0)
            self._vehicle_status["lock_flg"] = lock_flg
        
        response = MagicMock()
        response.status_code = self._status_code
        response.json.return_value = {
            "result": {
                "vehicle_id": self._vehicle_status["vehicle_id"],
                "lock_flg": self._vehicle_status["lock_flg"]
            }
        }
        return response
    
    # ──────────────────────────────────────
    # テスト用のヘルパーメソッド
    # ──────────────────────────────────────
    
    def set_lock_flg(self, lock_flg: int):
        """lock_flg を設定"""
        self._vehicle_status["lock_flg"] = lock_flg
    
    def set_voice_flg(self, voice_flg: int):
        """voice_flg を設定"""
        self._vehicle_status["voice_flg"] = voice_flg
    
    def set_active_schedule_exists(self, exists: int):
        """active_schedule_exists を設定"""
        self._vehicle_status["active_schedule_exists"] = exists
    
    def set_should_fail(self, should_fail: bool):
        """通信失敗をシミュレート"""
        self._should_fail = should_fail
    
    def set_status_code(self, status_code: int):
        """ステータスコードを設定"""
        self._status_code = status_code
    
    def get_request_count(self) -> int:
        """リクエスト回数を取得"""
        return self._request_count
    
    def reset(self):
        """状態をリセット"""
        self._vehicle_status = {
            "vehicle_id": "test_vehicle_001",
            "lock_flg": 0,
            "voice_flg": 0,
            "active_schedule_exists": 0
        }
        self._request_count = 0
        self._should_fail = False
        self._status_code = 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fixtures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture
def ros_context():
    """ROSコンテキストの初期化と終了"""
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def mock_node(ros_context):
    """GoInterfaceMockノードの生成"""
    # パラメータを設定してノードを生成
    node = GoInterfaceMock()
    
    # パラメータが設定されていない場合は手動で設定
    if not hasattr(node, '_service_url'):
        node._service_url = "http://test-server.com"
        node._access_token = "test_token_12345"
        node._get_connect_timeout = 0.8
        node._get_read_timeout = 1.0
        node._patch_connect_timeout = 1.0
        node._patch_read_timeout = 2.0
        node._patch_max_retry = 5
        node._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Token {node._access_token}"
        }
        
        # Publisher/Subscriberを手動で作成
        from rclpy.qos import QoSProfile
        profile = QoSProfile(depth=1)
        
        if not hasattr(node, '_vehicle_status_publisher'):
            node._vehicle_status_publisher = node.create_publisher(
                VehicleStatus, "api_vehicle_status", profile)
        
        if not hasattr(node, '_lock_state_publisher'):
            node._lock_state_publisher = node.create_publisher(
                StateLock, "/go_interface/lock_state", profile)
    
    yield node
    node.destroy_node()


@pytest.fixture
def fake_web_server():
    """FakeWebServerの生成"""
    server = FakeWebServer()
    yield server
    server.reset()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: FMS連携
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFMSIntegration:
    """FMS連携のテスト"""
    
    def test_on_vehicle_info_success(self, mock_node):
        """正常系: vehicle_id を正常に取得"""
        # Arrange
        msg = String()
        msg.data = json.dumps({"vehicle_id": "test_vehicle_001"})
        
        # Act
        mock_node.on_vehicle_info(msg)
        
        # Assert
        assert mock_node.get_vehicle_id() == "test_vehicle_001"
        assert mock_node.get_is_emergency() == False
    
    def test_on_vehicle_info_invalid_json(self, mock_node):
        """異常系: 不正なJSONを受信"""
        # Arrange
        msg = String()
        msg.data = "invalid json"
        
        # Act
        mock_node.on_vehicle_info(msg)
        
        # Assert
        assert mock_node.get_vehicle_id() == ""
        assert mock_node.get_is_emergency() == True
    
    def test_on_vehicle_info_no_vehicle_id(self, mock_node):
        """異常系: vehicle_id フィールドなし"""
        # Arrange
        msg = String()
        msg.data = json.dumps({"other_field": "value"})
        
        # Act
        mock_node.on_vehicle_info(msg)
        
        # Assert
        assert mock_node.get_vehicle_id() == ""
        assert mock_node.get_is_emergency() == True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: パターン1（配送予約ON）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPattern1ReservationOn:
    """パターン1: 配送予約ON のテスト"""
    
    def test_reservation_on_success(self, mock_node, fake_web_server):
        """正常系: 配送予約ON成功"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        
        # Sessionのpatchとrequests.getのpatchを両方行う
        mock_session = MagicMock()
        mock_session.patch = fake_web_server.patch_vehicle_status
        
        with patch('requests.Session', return_value=mock_session), \
             patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期状態確認
            assert mock_node.get_current_lock_state() == StateLock.STATE_OFF
            
            # Act: ボタン押下
            button_msg = VehicleButton()
            button_msg.data = True
            mock_node.on_delivery_reservation_button(button_msg)
            
            # Assert: STATE_VERIFICATION に遷移
            assert mock_node.get_current_lock_state() == StateLock.STATE_VERIFICATION
            assert mock_node.get_verification_start_time() is not None
            
            # Act: WebサーバーがGETで lock_flg=1 を返す
            fake_web_server.set_lock_flg(1)
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: STATE_ON に遷移
            assert mock_node.get_current_lock_state() == StateLock.STATE_ON
            assert mock_node.get_verification_start_time() is None
            assert mock_node.get_lock_flg() == True
    
    def test_reservation_on_patch_failed(self, mock_node, fake_web_server):
        """異常系: PATCH失敗"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server.set_should_fail(True)
        
        mock_session = MagicMock()
        mock_session.patch = fake_web_server.patch_vehicle_status
        
        with patch('requests.Session', return_value=mock_session):
            
            # Act: ボタン押下
            button_msg = VehicleButton()
            button_msg.data = True
            mock_node.on_delivery_reservation_button(button_msg)
            
            # Assert: STATE_OFF に戻る
            assert mock_node.get_current_lock_state() == StateLock.STATE_OFF
            assert mock_node.get_verification_start_time() is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: パターン2（配送予約OFF）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPattern2ReservationOff:
    """パターン2: 配送予約OFF のテスト"""
    
    def test_reservation_off_success(self, mock_node, fake_web_server):
        """正常系: 配送予約OFF成功"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        mock_node.set_current_lock_state(StateLock.STATE_ON)
        mock_node.set_lock_flg(True)
        fake_web_server.set_lock_flg(1)
        
        mock_session = MagicMock()
        mock_session.patch = fake_web_server.patch_vehicle_status
        
        with patch('requests.Session', return_value=mock_session), \
             patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期状態確認
            assert mock_node.get_current_lock_state() == StateLock.STATE_ON
            
            # Act: ボタン押下
            button_msg = VehicleButton()
            button_msg.data = True
            mock_node.on_delivery_reservation_button(button_msg)
            
            # Assert: STATE_ON 維持（Web応答待ち）
            assert mock_node.get_current_lock_state() == StateLock.STATE_ON
            
            # Act: WebサーバーがGETで lock_flg=0 を返す
            fake_web_server.set_lock_flg(0)
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: STATE_OFF に遷移
            assert mock_node.get_current_lock_state() == StateLock.STATE_OFF
            assert mock_node.get_lock_flg() == False
    
    def test_reservation_off_status_code_error(self, mock_node, fake_web_server):
        """異常系: PATCH時のステータスコードエラー"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        mock_node.set_current_lock_state(StateLock.STATE_ON)
        fake_web_server.set_status_code(400)
        
        mock_session = MagicMock()
        mock_session.patch = fake_web_server.patch_vehicle_status
        
        with patch('requests.Session', return_value=mock_session):
            
            # Act: ボタン押下
            button_msg = VehicleButton()
            button_msg.data = True
            mock_node.on_delivery_reservation_button(button_msg)
            
            # Assert: STATE_ON 維持（エラーのため変化なし）
            assert mock_node.get_current_lock_state() == StateLock.STATE_ON


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: パターン3（タイムアウト）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPattern3Timeout:
    """パターン3: タイムアウト のテスト"""
    
    def test_timeout_after_15_seconds(self, mock_node):
        """正常系: 15秒タイムアウト"""
        # Arrange
        mock_node.set_current_lock_state(StateLock.STATE_VERIFICATION)
        
        # 16秒前の時刻を設定
        current_time = mock_node.get_clock().now()
        timeout_time = rclpy.time.Time(
            nanoseconds=current_time.nanoseconds - 16 * 10**9)
        mock_node.set_verification_start_time(timeout_time)
        
        # Act: タイムアウトチェック
        mock_node._check_verification_timeout()
        
        # Assert: STATE_OFF に遷移
        assert mock_node.get_current_lock_state() == StateLock.STATE_OFF
        assert mock_node.get_verification_start_time() is None
    
    def test_before_timeout(self, mock_node):
        """正常系: タイムアウト前（変化なし）"""
        # Arrange
        mock_node.set_current_lock_state(StateLock.STATE_VERIFICATION)
        
        # 5秒前の時刻を設定（タイムアウト前）
        current_time = mock_node.get_clock().now()
        recent_time = rclpy.time.Time(
            nanoseconds=current_time.nanoseconds - 5 * 10**9)
        mock_node.set_verification_start_time(recent_time)
        
        # Act: タイムアウトチェック
        mock_node._check_verification_timeout()
        
        # Assert: 状態変化なし
        assert mock_node.get_current_lock_state() == StateLock.STATE_VERIFICATION
        assert mock_node.get_verification_start_time() is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: パターン4（アクティブスケジュール）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPattern4ActiveSchedule:
    """パターン4: アクティブスケジュール のテスト"""
    
    def test_active_schedule_exists(self, mock_node):
        """拒否: アクティブスケジュール実行中"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        mock_node.set_current_lock_state(StateLock.STATE_OFF)
        mock_node.set_active_schedule_exists(True)
        
        # Act: ボタン押下
        button_msg = VehicleButton()
        button_msg.data = True
        mock_node.on_delivery_reservation_button(button_msg)
        
        # Assert: 状態変化なし
        assert mock_node.get_current_lock_state() == StateLock.STATE_OFF


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: パターン5（検証中の多重押下）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPattern5UnderVerification:
    """パターン5: 検証中の多重押下 のテスト"""
    
    def test_under_verification(self, mock_node):
        """拒否: 検証中の多重押下"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        mock_node.set_current_lock_state(StateLock.STATE_VERIFICATION)
        
        # Act: ボタン押下
        button_msg = VehicleButton()
        button_msg.data = True
        mock_node.on_delivery_reservation_button(button_msg)
        
        # Assert: 状態変化なし
        assert mock_node.get_current_lock_state() == StateLock.STATE_VERIFICATION


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: WebAPI GET処理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestWebAPIGet:
    """WebAPI GET処理のテスト"""
    
    def test_fetch_success(self, mock_node, fake_web_server):
        """正常系: GET成功"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server.set_lock_flg(1)
        fake_web_server.set_voice_flg(1)
        fake_web_server.set_active_schedule_exists(0)
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert
            assert mock_node.get_lock_flg() == True
            assert mock_node.get_voice_flg() == True
            assert mock_node.get_active_schedule_exists() == False
    
    def test_fetch_network_error(self, mock_node, fake_web_server):
        """異常系: ネットワークエラー"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server.set_should_fail(True)
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期値を設定
            initial_lock_flg = mock_node.get_lock_flg()
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: 状態変化なし
            assert mock_node.get_lock_flg() == initial_lock_flg
    
    def test_fetch_status_code_error(self, mock_node, fake_web_server):
        """異常系: ステータスコードエラー（500）"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server.set_status_code(500)
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期値を設定
            initial_lock_flg = mock_node.get_lock_flg()
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: 状態変化なし
            assert mock_node.get_lock_flg() == initial_lock_flg
    
    def test_fetch_vehicle_id_mismatch(self, mock_node, fake_web_server):
        """異常系: vehicle_id 不一致"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server._vehicle_status["vehicle_id"] = "different_vehicle"
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期値を設定
            initial_lock_flg = mock_node.get_lock_flg()
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: 状態変化なし
            assert mock_node.get_lock_flg() == initial_lock_flg
    
    def test_fetch_lock_flg_parse_error(self, mock_node, fake_web_server):
        """異常系: lock_flg パースエラー"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server._vehicle_status["lock_flg"] = None
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期値を設定
            initial_lock_flg = mock_node.get_lock_flg()
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: 状態変化なし（エラーログは出力される）
            assert mock_node.get_lock_flg() == initial_lock_flg
    
    def test_fetch_voice_flg_parse_error(self, mock_node, fake_web_server):
        """異常系: voice_flg パースエラー"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server._vehicle_status["voice_flg"] = None
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期値を設定
            initial_voice_flg = mock_node.get_voice_flg()
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: 状態変化なし（エラーログは出力される）
            assert mock_node.get_voice_flg() == initial_voice_flg
    
    def test_fetch_active_schedule_parse_error(self, mock_node, fake_web_server):
        """異常系: active_schedule_exists パースエラー"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        fake_web_server._vehicle_status["active_schedule_exists"] = None
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期値を設定
            initial_active_schedule = mock_node.get_active_schedule_exists()
            
            # Act
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: 状態変化なし（エラーログは出力される）
            assert mock_node.get_active_schedule_exists() == initial_active_schedule


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# テストケース: 状態遷移
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStateTransition:
    """状態遷移のテスト"""
    
    def test_off_to_on_via_verification(self, mock_node, fake_web_server):
        """状態遷移: OFF → VERIFICATION → ON"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        
        mock_session = MagicMock()
        mock_session.patch = fake_web_server.patch_vehicle_status
        
        with patch('requests.Session', return_value=mock_session), \
             patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期状態: OFF
            assert mock_node.get_current_lock_state() == StateLock.STATE_OFF
            
            # Act 1: ボタン押下
            button_msg = VehicleButton()
            button_msg.data = True
            mock_node.on_delivery_reservation_button(button_msg)
            
            # Assert 1: VERIFICATION
            assert mock_node.get_current_lock_state() == StateLock.STATE_VERIFICATION
            
            # Act 2: GET応答
            fake_web_server.set_lock_flg(1)
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert 2: ON
            assert mock_node.get_current_lock_state() == StateLock.STATE_ON
    
    def test_on_to_off(self, mock_node, fake_web_server):
        """状態遷移: ON → OFF"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        mock_node.set_current_lock_state(StateLock.STATE_ON)
        fake_web_server.set_lock_flg(1)
        
        mock_session = MagicMock()
        mock_session.patch = fake_web_server.patch_vehicle_status
        
        with patch('requests.Session', return_value=mock_session), \
             patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # 初期状態: ON
            assert mock_node.get_current_lock_state() == StateLock.STATE_ON
            
            # Act 1: ボタン押下
            button_msg = VehicleButton()
            button_msg.data = True
            mock_node.on_delivery_reservation_button(button_msg)
            
            # Act 2: GET応答
            fake_web_server.set_lock_flg(0)
            mock_node.fetch_from_ondemand_delivery_apps()
            
            # Assert: OFF
            assert mock_node.get_current_lock_state() == StateLock.STATE_OFF


class TestOutputTimer:
    """output_timer のテスト"""
    
    def test_output_timer_emergency(self, mock_node, fake_web_server):
        """異常系: is_emergency が True の場合"""
        # Arrange
        mock_node.set_is_emergency(True)
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # Act
            mock_node.output_timer()
            
            # Assert: fetch は呼ばれない（リクエストカウントが0のまま）
            assert fake_web_server.get_request_count() == 0
    
    def test_output_timer_no_vehicle_id(self, mock_node, fake_web_server):
        """異常系: vehicle_id が未設定の場合"""
        # Arrange
        mock_node.set_vehicle_id("")
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # Act
            mock_node.output_timer()
            
            # Assert: fetch は呼ばれない
            assert fake_web_server.get_request_count() == 0
    
    def test_output_timer_success(self, mock_node, fake_web_server):
        """正常系: output_timer が正常に動作"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        mock_node.set_is_emergency(False)
        
        with patch('requests.get', side_effect=fake_web_server.get_vehicle_status):
            
            # Act
            mock_node.output_timer()
            
            # Assert: fetch が呼ばれる
            assert fake_web_server.get_request_count() == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

