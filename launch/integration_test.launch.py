#!/usr/bin/env python3

# Copyright 2024 eve autonomy inc. All Rights Reserved.

"""
go_interface 統合テスト用 launch ファイル

使い方:
  ros2 launch go_interface integration_test.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Launch description生成"""
    
    # go_interface ノード
    go_interface_node = Node(
        package='go_interface',
        executable='go_interface',
        name='go_interface',
        output='screen',
        parameters=[{
            'delivery_reservation_service_url': 'http://localhost:8000',
            'access_token': 'test_token_for_integration_test'
        }]
    )
    
    # 統合テストノード
    integration_test_node = Node(
        package='go_interface',
        executable='integration_test.py',
        name='go_interface_integration_test',
        output='screen'
    )
    
    return LaunchDescription([
        go_interface_node,
        integration_test_node
    ])

