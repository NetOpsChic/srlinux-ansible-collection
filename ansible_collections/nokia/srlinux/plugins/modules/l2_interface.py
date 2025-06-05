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
module: l2_interface
short_description: Configure L2 interfaces (trunk or access) on Nokia SR Linux
description:
  - Create a mac-vrf NI (if missing), enable/disable interface, configure trunk or access, add VLANs as subinterfaces.
options:
  config:
    description:
      - List of L2 interface configs.
    type: list
    elements: dict
    suboptions:
      name:
        description: Interface name (e.g., ethernet-1/2)
        type: str
        required: true
      admin_state:
        description: Admin state (enable/disable)
        type: str
        choices: [enable, disable]
      description:
        description: Description for the interface
        type: str
      trunk_vlans:
        description: List of VLAN IDs for trunk mode (creates subinterfaces)
        type: list
        elements: int
      access_vlan:
        description: VLAN ID for access mode (untagged)
        type: int
      network_instance:
        description: Network-instance (auto-created as mac-vrf as needed)
        type: str
        required: true
  state:
    description: merged (create/update) or deleted (remove config)
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

def ni_exists(client, ni_name):
    path = f"/network-instance[name=\"{ni_name}\"]"
    get_rpc = build_rpc("get", [{"path": path}], rpcID())
    resp = client.post(payload=json.dumps(get_rpc))
    result = resp.get("result", [{}])
    if isinstance(result, list):
        result = result[0]
    return bool(result.get(path))

def create_ni(client, ni_name, desc=None):
    path = f"/network-instance[name=\"{ni_name}\"]"
    value = {"type": "mac-vrf"}
    if desc:
        value["description"] = desc
    cmd = [{
        "action": "update",
        "path": path,
        "value": value
    }]
    rpc = build_rpc("set", cmd, rpcID())
    resp = client.post(payload=json.dumps(rpc))
    return resp

def main():
    module = AnsibleModule(
        argument_spec=dict(
            config=dict(type='list', elements='dict', required=True),
            state=dict(type='str', choices=['merged', 'deleted'], default='merged'),
        ),
        supports_check_mode=True
    )

    client = JSONRPCClient(module)
    state = module.params["state"]
    results = []

    for iface_item in module.params['config']:
        name = iface_item['name']
        ni = iface_item.get('network_instance')
        admin_state = iface_item.get('admin_state', 'enable')
        desc = iface_item.get('description')
        trunk_vlans = iface_item.get('trunk_vlans')
        access_vlan = iface_item.get('access_vlan')
        changed = False
        before = {}
        after = {}

        # 1. Ensure NI exists (mac-vrf for L2)
        if not ni_exists(client, ni):
            if not module.check_mode:
                create_ni(client, ni)
            changed = True

        # 2. Get current interface state (idempotency)
        get_path = f"/interface[name=\"{name}\"]"
        get_rpc = build_rpc("get", [{"path": get_path}], rpcID())
        response = client.post(payload=json.dumps(get_rpc))
        if response.get("error"):
            module.fail_json(msg=f"Server error (GET) on {name}", response=pprint.pformat(response))
        result = response.get("result", {})
        if isinstance(result, list):
            result = result[0] if result and isinstance(result[0], dict) else {}
        before = result.get(get_path, {})

        cmds = []

        if state == "deleted":
            if before:
                changed = True
                if not module.check_mode:
                    cmds.append({
                        "action": "delete",
                        "path": get_path
                    })
        else:
            # --- Trunk logic ---
            if trunk_vlans:
                subifs = []
                for vlan in trunk_vlans:
                    subifs.append({
                        "index": vlan,
                        "vlan": {
                            "encap": {
                                "single-tagged": {
                                    "vlan-id": vlan
                                }
                            }
                        }
                    })
                iface_val = {
                    "admin-state": admin_state,
                    "description": desc or "",
                    "subinterface": subifs
                }
                cmds.append({
                    "action": "update",
                    "path": get_path,
                    "value": iface_val
                })
                changed = True
            # --- Access logic ---
            elif access_vlan is not None:
                iface_val = {
                    "admin-state": admin_state,
                    "description": desc or "",
                    "vlan-tagging": True,
                    "subinterface": [{
                        "index": 0,
                        "type": "bridged",
                        "vlan": {
                            "encap": {
                                "untagged": {}
                            }
                        }
                    }]
                }
                cmds.append({
                    "action": "update",
                    "path": get_path,
                    "value": iface_val
                })
                changed = True
            else:
                # Just bring up interface (no VLAN)
                iface_val = {
                    "admin-state": admin_state,
                    "description": desc or "",
                }
                cmds.append({
                    "action": "update",
                    "path": get_path,
                    "value": iface_val
                })
                changed = True

        if changed and not module.check_mode and cmds:
            rpc = build_rpc("set", cmds, rpcID())
            response = client.post(payload=json.dumps(rpc))
            if response.get("error"):
                module.fail_json(msg=f"Server error (UPDATE) on {name}", response=pprint.pformat(response))
            after = response.get("result", {})

        results.append({
            "name": name,
            "changed": changed,
            "before": before,
            "after": after,
        })

    module.exit_json(results=results)

if __name__ == "__main__":
    main()
