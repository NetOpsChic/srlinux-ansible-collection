#!/usr/bin/python
# Copyright 2023 Nokia
# Licensed under the BSD 3-Clause License.

from __future__ import absolute_import, division, print_function
import json
import pprint

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.nokia.srlinux.plugins.module_utils.const import JSON_RPC_VERSION
from ansible_collections.nokia.srlinux.plugins.module_utils.srlinux import (
    JSONRPCClient,
    rpcID,
)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: static_routes
short_description: Configure static routes (and next-hop-groups) on Nokia SR Linux
description:
  - Configure next-hop-groups and static routes in a single playbook task.
options:
  config:
    description:
      - Dictionary containing network_instance, next_hop_groups, and routes.
    type: dict
    suboptions:
      network_instance:
        description: Network-instance name (VRF).
        type: str
        required: true
      next_hop_groups:
        description: List of next-hop-groups to configure.
        type: list
        elements: dict
        suboptions:
          name:
            type: str
            required: true
          admin_state:
            type: str
            choices: [enable, disable]
          nexthops:
            type: list
            elements: dict
            suboptions:
              index:
                type: int
                required: true
              ip_address:
                type: str
                required: true
      routes:
        description: List of static routes to configure.
        type: list
        elements: dict
        suboptions:
          prefix:
            type: str
            required: true
          admin_state:
            type: str
            choices: [enable, disable]
          metric:
            type: int
          preference:
            type: int
          next_hop_group:
            type: str
          description:
            type: str
          blackhole:
            type: bool
  state:
    description: merged (set/update) or deleted (remove config)
    type: str
    choices: [merged, deleted]
    default: merged
author:
  - Uzma Saman (@NetOpsChic)
'''

def build_rpc(method, commands, req_id):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "method": method,
        "params": {"commands": commands},
        "id": req_id
    }

def main():
    module = AnsibleModule(
        argument_spec=dict(
            config=dict(type='dict', required=True),
            state=dict(type='str', choices=['merged', 'deleted'], default='merged')
        ),
        supports_check_mode=True
    )

    client = JSONRPCClient(module)
    state = module.params["state"]
    cfg = module.params['config']
    ni = cfg["network_instance"]
    cmds = []
    changed = False

    # --- Configure next-hop-groups first ---
    for nhg in cfg.get("next_hop_groups", []):
        nhg_path = f"/network-instance[name=\"{ni}\"]/next-hop-groups/group[name=\"{nhg['name']}\"]"
        nhg_val = {}
        if "admin_state" in nhg:
            nhg_val["admin-state"] = nhg["admin_state"]
        if "nexthops" in nhg:
            nhg_val["nexthop"] = []
            for nh in nhg["nexthops"]:
                nh_item = {
                    "index": nh["index"],
                    "ip-address": nh["ip_address"]
                }
                nhg_val["nexthop"].append(nh_item)
        cmds.append({
            "action": "update" if state == "merged" else "delete",
            "path": nhg_path,
            "value": nhg_val if state == "merged" else None
        })

    # --- Now configure static routes ---
    for route in cfg.get("routes", []):
        route_path = f"/network-instance[name=\"{ni}\"]/static-routes/route[prefix={route['prefix']}]"
        route_val = {}
        if "admin_state" in route:
            route_val["admin-state"] = route["admin_state"]
        if "metric" in route:
            route_val["metric"] = route["metric"]
        if "preference" in route:
            route_val["preference"] = route["preference"]
        if "next_hop_group" in route:
            route_val["next-hop-group"] = route["next_hop_group"]
        if "description" in route:
            route_val["description"] = route["description"]
        if "blackhole" in route:
            route_val["blackhole"] = route["blackhole"]
        cmds.append({
            "action": "update" if state == "merged" else "delete",
            "path": route_path,
            "value": route_val if state == "merged" else None
        })

    if cmds and not module.check_mode:
        rpc = build_rpc("set", cmds, rpcID())
        response = client.post(payload=json.dumps(rpc))
        if response.get("error"):
            module.fail_json(msg="Server error (UPDATE)", response=pprint.pformat(response))
    module.exit_json(changed=bool(cmds), commands=cmds)

if __name__ == "__main__":
    main()
