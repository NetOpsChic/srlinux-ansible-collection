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
module: network_instance
short_description: Manage network-instances (VRF, bridge-table) on Nokia SR Linux
description:
  - Create, update, or delete network-instances (L2 mac-vrf, L3 ip-vrf, default) on Nokia SR Linux devices.
options:
  config:
    description:
      - List of network-instances.
    type: list
    elements: dict
    suboptions:
      name:
        description: Network-instance name.
        type: str
        required: true
      type:
        description: Network-instance type: ip-vrf (L3), mac-vrf (L2), or default.
        type: str
        choices: [ip-vrf, mac-vrf, default]
        required: true
      description:
        description: Description for the NI.
        type: str
      admin_state:
        description: Admin state.
        type: str
        choices: [enable, disable]
      # Add more suboptions as needed for advanced config (e.g., route-distinguisher)
  state:
    description: Whether config should be merged or deleted.
    type: str
    choices: [merged, deleted]
    default: merged
author:
  - Uzma Saman (@NetOpsChic)
'''

EXAMPLES = r'''
- name: Ensure NIs exist
  nokia.srlinux.network_instance:
    config:
      - name: lan-vrf
        type: mac-vrf
        description: L2 VRF
      - name: blue
        type: ip-vrf
        description: L3 VRF
      - name: default
        type: default
        description: Default NI
    state: merged

- name: Remove a network-instance
  nokia.srlinux.network_instance:
    config:
      - name: old-vrf
        type: ip-vrf
    state: deleted
'''

RETURN = r'''
results:
  description: Per-NI before/after state.
  type: list
  elements: dict
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
            config=dict(type='list', elements='dict', required=True),
            state=dict(type='str', choices=['merged', 'deleted'], default='merged'),
        ),
        supports_check_mode=True
    )

    client = JSONRPCClient(module)
    state = module.params["state"]
    results = []

    for ni_item in module.params['config']:
        name = ni_item['name']
        ni_type = ni_item.get('type')
        desc = ni_item.get('description')
        admin_state = ni_item.get('admin_state', 'enable')
        changed = False
        before = {}
        after = {}

        # Path to this network-instance
        ni_path = f"/network-instance[name=\"{name}\"]"
        get_rpc = build_rpc("get", [{"path": ni_path}], rpcID())
        response = client.post(payload=json.dumps(get_rpc))
        if response.get("error"):
            module.fail_json(msg=f"Server error (GET) on {name}", response=pprint.pformat(response))
        result = response.get("result", {})
        if isinstance(result, list):
            result = result[0] if result and isinstance(result[0], dict) else {}
        before = result.get(ni_path, {})

        cmds = []

        if state == "deleted":
            if before:
                changed = True
                if not module.check_mode:
                    cmds.append({
                        "action": "delete",
                        "path": ni_path
                    })
        else:
            # Build NI value dict
            ni_value = {
                "type": ni_type,
                "admin-state": admin_state,
            }
            if desc:
                ni_value["description"] = desc

            # Only push if changed or not present
            if not before or before != ni_value:
                changed = True
                if not module.check_mode:
                    cmds.append({
                        "action": "update",
                        "path": ni_path,
                        "value": ni_value
                    })

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
