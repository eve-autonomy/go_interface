# go_interface テストガイド

## 概要

このディレクトリには、`go_interface` ノードの単体テストが含まれています。

## テスト構成

```
test/
├── README.md                     # このファイル
├── test_go_interface.py         # メインテストファイル
└── __init__.py                  # Pythonパッケージ初期化
```

## 前提条件

### 必要なパッケージ

```bash
# pytest のインストール
pip3 install pytest pytest-cov

# ROS 2 環境のソース
source /opt/ros/humble/setup.bash
source /path/to/your/workspace/install/setup.bash
```

### 依存メッセージ型

以下のメッセージパッケージがビルド済みである必要があります：

- `go_interface_msgs`
- `autoware_state_machine_msgs`

## テスト実行方法

### 全テスト実行

```bash
cd /home/satoshiinoue/ws/pilot-auto/pilot-auto.x1.eve/src/x1/v2x_connection/go_interface
pytest test/test_go_interface.py -v
```

### 特定のテストクラスのみ実行

```bash
# パターン1のテストのみ
pytest test/test_go_interface.py::TestPattern1ReservationOn -v

# パターン2のテストのみ
pytest test/test_go_interface.py::TestPattern2ReservationOff -v

# FMS連携テストのみ
pytest test/test_go_interface.py::TestFMSIntegration -v
```

### 特定のテストケースのみ実行

```bash
pytest test/test_go_interface.py::TestPattern1ReservationOn::test_reservation_on_success -v
```

### カバレッジ計測

```bash
# カバレッジを計測してHTML形式でレポート出力
pytest test/test_go_interface.py --cov=go_interface --cov-report=html

# カバレッジレポートの確認
firefox htmlcov/index.html
```

### 詳細ログ付き実行

```bash
# 標準出力を表示
pytest test/test_go_interface.py -v -s

# ROS 2ログを表示
pytest test/test_go_interface.py -v -s --log-cli-level=INFO
```

## テストケース一覧

### 1. FMS連携テスト (`TestFMSIntegration`)

| テストケース | 説明 |
|------------|------|
| `test_on_vehicle_info_success` | 正常系: vehicle_id を正常に取得 |
| `test_on_vehicle_info_invalid_json` | 異常系: 不正なJSONを受信 |
| `test_on_vehicle_info_no_vehicle_id` | 異常系: vehicle_id フィールドなし |

### 2. パターン1テスト (`TestPattern1ReservationOn`)

| テストケース | 説明 |
|------------|------|
| `test_reservation_on_success` | 正常系: 配送予約ON成功 |
| `test_reservation_on_patch_failed` | 異常系: PATCH失敗 |

### 3. パターン2テスト (`TestPattern2ReservationOff`)

| テストケース | 説明 |
|------------|------|
| `test_reservation_off_success` | 正常系: 配送予約OFF成功 |

### 4. パターン3テスト (`TestPattern3Timeout`)

| テストケース | 説明 |
|------------|------|
| `test_timeout_after_15_seconds` | 正常系: 15秒タイムアウト |
| `test_before_timeout` | 正常系: タイムアウト前（変化なし） |

### 5. パターン4テスト (`TestPattern4ActiveSchedule`)

| テストケース | 説明 |
|------------|------|
| `test_active_schedule_exists` | 拒否: アクティブスケジュール実行中 |

### 6. パターン5テスト (`TestPattern5UnderVerification`)

| テストケース | 説明 |
|------------|------|
| `test_under_verification` | 拒否: 検証中の多重押下 |

### 7. WebAPI GETテスト (`TestWebAPIGet`)

| テストケース | 説明 |
|------------|------|
| `test_fetch_success` | 正常系: GET成功 |
| `test_fetch_network_error` | 異常系: ネットワークエラー |

### 8. 状態遷移テスト (`TestStateTransition`)

| テストケース | 説明 |
|------------|------|
| `test_off_to_on_via_verification` | 状態遷移: OFF → VERIFICATION → ON |
| `test_on_to_off` | 状態遷移: ON → OFF |

## テスト設計の詳細

詳細なテスト設計については、以下のドキュメントを参照してください：

- [go_interface_detailed_callbacks_and_tests.md](/home/satoshiinoue/ws/pilot-auto/pilot-auto.x1.eve/docs/go_interface_detailed_callbacks_and_tests.md)

## Mock クラスの使用方法

### GoInterfaceMock

`GoInterface` を継承したMockクラスで、内部フィールドへのアクセスを提供します。

```python
# ノードの生成
mock_node = GoInterfaceMock()

# 内部状態の取得
vehicle_id = mock_node.get_vehicle_id()
lock_state = mock_node.get_current_lock_state()

# 内部状態の設定（テスト用）
mock_node.set_vehicle_id("test_vehicle_001")
mock_node.set_current_lock_state(StateLock.STATE_VERIFICATION)
```

### FakeWebServer

Webサーバーをモック化するスタブクラスです。

```python
# サーバーの生成
fake_server = FakeWebServer()

# 応答データの設定
fake_server.set_lock_flg(1)
fake_server.set_voice_flg(1)
fake_server.set_active_schedule_exists(0)

# requests.get/patch のモック化
with patch('requests.get', side_effect=fake_server.get_vehicle_status):
    # テスト実行
    pass
```

## トラブルシューティング

### ModuleNotFoundError: No module named 'go_interface'

`PYTHONPATH` を設定してください：

```bash
export PYTHONPATH=$PYTHONPATH:/home/satoshiinoue/ws/pilot-auto/pilot-auto.x1.eve/src/x1/v2x_connection/go_interface
pytest test/test_go_interface.py -v
```

### ModuleNotFoundError: No module named 'go_interface_msgs'

ROS 2 ワークスペースをビルドして、setup.bash をソースしてください：

```bash
cd /home/satoshiinoue/ws/pilot-auto/pilot-auto.x1.eve
colcon build --packages-select go_interface_msgs autoware_state_machine_msgs
source install/setup.bash
```

### rclpy のインポートエラー

ROS 2 環境を正しくソースしてください：

```bash
source /opt/ros/humble/setup.bash
```

## CI/CD統合

### GitHub Actions での実行例

```yaml
name: Test go_interface

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup ROS 2
        uses: ros-tooling/setup-ros@v0.6
        with:
          required-ros-distributions: humble
      
      - name: Install dependencies
        run: |
          pip3 install pytest pytest-cov
      
      - name: Build workspace
        run: |
          source /opt/ros/humble/setup.bash
          colcon build --packages-select go_interface_msgs autoware_state_machine_msgs
      
      - name: Run tests
        run: |
          source /opt/ros/humble/setup.bash
          source install/setup.bash
          pytest src/x1/v2x_connection/go_interface/test/test_go_interface.py -v --cov=go_interface --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## カバレッジ目標

| 項目 | 目標 |
|-----|------|
| ラインカバレッジ | 90%以上 |
| ブランチカバレッジ | 85%以上 |
| 関数カバレッジ | 100% |

## 追加テストケースの実装

新しいテストケースを追加する場合は、以下のテンプレートを使用してください：

```python
class TestNewFeature:
    """新機能のテスト"""
    
    def test_new_feature_success(self, mock_node, fake_web_server):
        """正常系: 新機能の動作確認"""
        # Arrange
        mock_node.set_vehicle_id("test_vehicle_001")
        
        # Act
        # ... テスト対象の処理を実行 ...
        
        # Assert
        assert mock_node.get_some_field() == expected_value
```

## 参考資料

- [pytest ドキュメント](https://docs.pytest.org/)
- [pytest-cov ドキュメント](https://pytest-cov.readthedocs.io/)
- [ROS 2 Testing Guide](https://docs.ros.org/en/humble/Tutorials/Intermediate/Testing/Testing-Main.html)

