# Go interface

## Overview
This node integrates user-defined on-demand delivery apps with in-vehicle systems.

The following use cases are realized by using it in combination with FMS (fleet management service) provided by TIER IV, inc.

- Switch between on-demand delivery and regular delivery.
- Call the ego vehicle to any loading / unloading place.
- Send the ego vehicle to any loading / unloading place.

## Input and Output
- input
  - from [Web.Auto](https://tier4.jp/en/products/#webauto) (DevOps Platform provided by TIER IV)
    - `/webauto/vehicle_info` \[[std_msgs/msg/String](https://docs.ros2.org/foxy/api/std_msgs/msg/String.html)\]: Gets unique ID of the ego vehicle managed by Web.Auto.
  - from [autoware_state_machine](https://github.com/eve-autonomy/autoware_state_machine/) 
    - `/req_change_lock_flg` \[[go_interface_msgs/ChangeLockFlg](https://github.com/eve-autonomy/go_interface_msgs/blob/main/msg/ChangeLockFlg.msg)\]: Receives reservations for on-demand delivery.
  - from [on-demand delivery apps (user-defined)](#required-specifications-for-on-demand-delivery-apps)
    - [`GET API`](#get-api--get-current-reservation-status): Gets the current reservation status for on-demand delivery in the ego vehicle.
- output
  - to [autoware_state_machine](https://github.com/eve-autonomy/autoware_state_machine/)
    - `/api_vehicle_status` \[[go_interface_msgs/VehicleStatus](https://github.com/eve-autonomy/go_interface_msgs/blob/main/msg/VehicleStatus.msg)\]: The current reservation status for on-demand delivery in the ego vehicle.
  - to [on-demand delivery apps (user-defined)](#required-specifications-for-on-demand-delivery-apps)
    - [`PATCH API`](#patch-api--update-reservation-status): Updates the reservation status for on-demand delivery in the ego vehicle.

## Node Graph
![node graph](http://www.plantuml.com/plantuml/proxy?src=https://raw.githubusercontent.com/eve-autonomy/go_interface/docs/node_graph.pu)

## Launch arguments
|Name|Description|
|:---|:----------|
|operation_mode|Select the following operation modes; `product`, `server_test`, `local_test`, `not_use`. The URLs corresponding to these modes are set in [go_interface_params](https://github.com/eve-autonomy/go_interface_params.default). This URL applies to the `delivery_reservation_service_url` parameter.|
|access_token|Access token of on-demand delivery application. This value is passed directly to the `access_token` parameter.|

## Parameter description
<table>
  <thead>
    <tr>
      <th scope="col">Name</th>
      <th scope="col">Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>delivery_reservation_service_url</td>
      <td>URL of on-demand delivery application.</td>
    <tr>
    <tr>
      <td>access_token</td>
      <td>Access token of on-demand delivery application.</td>
    <tr>
  </tbody>
</table>

## Required specifications for on-demand delivery apps

The following features need to be provided by on-demand delivery apps.
- Search for available vehicles using the fleet management service.
- Providing a UI, the user can specify an arbitrary destination after identifying the vehicle.
- Reserve a delivery schedule for the fleet management service.

On-demand delivery apps must be implemented according to the following specifications.


### Overview of items 
See the [README](https://github.com/eve-autonomy/go_interface_params.default) in go_interface_params.

### Headers
The following contents are output as Headers.

<details><summary>Headers sample</summary><div>

```
{
  "Accept": "application/json",
  "Content-Type": "application/json",
  "Authorization": "Token 0123456789abcdefgh"
}
```

</div></details>

### GET API : Get current reservation status

<details><summary>GET API sample</summary><div>

#### Request Sample for GET API
```
GET (server_url)/api/vehicle_status?vehicle_id=t728943hy098r3 HTTP/1.1
```
#### Response Sample for GET API
```
{
  "result":
  {
    "vehicle_id": t728943hy098r3,
    "lock_flg": 0,
    "voice_flg": 0,
    "active_scedule_exist": 1
  }
}
```

</div></details>

### PATCH API : Update reservation status

<details><summary>PATCH API sample</summary><div>

#### Request Sample for PATCH API
```
PATCH (server_url)/api/vehicle_status HTTP/1.1

{
  "vehicle_id": 3wpo8r932tc02,
  "lock_flg": 1
}
```
#### Response Sample for PATCH API
```
{
  "result":
  {
    "vehicle_id": 3wpo8r932tc02,
    "lock_flg": 1
  }
}
```

</div></details>
