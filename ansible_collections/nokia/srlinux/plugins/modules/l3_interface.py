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
module: l3_interface
short_description: Configure L3 routed interfaces on Nokia SR Linux
description:
  - Create/update ip-vrf network-instance, add interface/subinterface, assign IP addresses.
options:
  config:
    description:
      - List of L3 interface configs.
    type: list
    elements: dict
    suboptions:
      name:
        description: Interface or subinterface name (e.g. ethernet-1/4.100)
        type: str
        required: true
      admin_state:
        description: Admin state (enable/disable)
        type: str
        choices: [enable, disable]
      description:
        description: Description for the interface
        type: str
      ipv4_address:
        description: IPv4 address (CIDR format)
        type: str
      network_instance:
        description: Network-instance (ip-vrf)
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
    value = {"type": "ip-vrf"}
    if desc:
        value["description"] = desc
    cmd = [{
        "action": "update",
        "path": path,
        "value": value
    }]
    rpc = build_rpc("set", cmd, rpcID())
    return client.post(payload=json.dumps(rpc))


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
        desc = iface_item.get('description', '')
        ipv4_address = iface_item.get('ipv4_address')
        changed = False
        before = {}
        after = {}

        # 1. Ensure NI exists
        if not ni_exists(client, ni):
            if not module.check_mode:
                create_ni(client, ni)
            changed = True

        cmds = []
        parent = name.split('.')[0]

        # Enable parent interface
        cmds.append({
            "action": "update",
            "path": f"/interface[name=\"{parent}\"]/admin-state",
            "value": admin_state
        })

        if '.' in name:
            base, idx = name.split('.')
            idx = int(idx)
            # Enable subinterface
            cmds.append({
                "action": "update",
                "path": f"/interface[name=\"{base}\"]/subinterface[index={idx}]/admin-state",
                "value": admin_state
            })
            # Enable IPv4 on subinterface
            cmds.append({
                "action": "update",
                "path": f"/interface[name=\"{base}\"]/subinterface[index={idx}]/ipv4/admin-state",
                "value": "enable"
            })
            # Set IPv4 address
            if ipv4_address:
                cmds.append({
                    "action": "update",
                    "path": f"/interface[name=\"{base}\"]/subinterface[index={idx}]/ipv4/address[ip-prefix=\"{ipv4_address}\"]",
                    "value": {}
                })
            # Attach subinterface to NI
            cmds.append({
                "action": "update",
                "path": f"/network-instance[name=\"{ni}\"]/interface[name=\"{name}\"]",
                "value": {}
            })
        else:
            # Base interface IPv4
            if ipv4_address:
                cmds.append({
                    "action": "update",
                    "path": f"/interface[name=\"{parent}\"]/ipv4/address[ip-prefix=\"{ipv4_address}\"]",
                    "value": {}
                })
            cmds.append({
                "action": "update",
                "path": f"/network-instance[name=\"{ni}\"]/interface[name=\"{name}\"]",
                "value": {}
            })

        # Execute updates
        if cmds and not module.check_mode:
            rpc = build_rpc("set", cmds, rpcID())
            response = client.post(payload=json.dumps(rpc))
            if response.get("error"):
                module.fail_json(msg=f"Server error (UPDATE) on {name}", response=pprint.pformat(response))
            after = response.get("result", {})
            changed = True

        results.append({
            "name": name,
            "changed": changed,
            "before": before,
            "after": after,
        })

    module.exit_json(results=results)

if __name__ == "__main__":
    main()
