#!/usr/bin/python
# Copyright 2024 Nokia
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
module: routing_policy
short_description: Configure routing policy (prefix-sets and policies) on Nokia SR Linux.
description:
  - Configure routing-policy prefix-sets and policies, e.g., for BGP/OSPF export.
options:
  config:
    description:
      - Routing policy config.
    type: dict
    suboptions:
      prefix_sets:
        description: List of prefix-sets.
        type: list
        elements: dict
        suboptions:
          name:
            type: str
            required: true
          prefixes:
            type: list
            elements: dict
            suboptions:
              ip_prefix:
                type: str
              mask_length_range:
                type: str
      policies:
        description: List of policies.
        type: list
        elements: dict
        suboptions:
          name:
            type: str
            required: true
          statements:
            type: list
            elements: dict
            suboptions:
              name:
                type: str
                required: true
              match:
                type: dict
                suboptions:
                  prefix_set:
                    type: str
              action:
                type: dict
                suboptions:
                  policy_result:
                    type: str
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
    config = module.params['config']
    cmds = []
    changed = False

    if state == "deleted":
        # Delete policies first, then prefix-sets
        for pol in config.get("policies", []):
            cmds.append({
                "action": "delete",
                "path": f"/routing-policy/policy[name={pol['name']}]"
            })
        for ps in config.get("prefix_sets", []):
            cmds.append({
                "action": "delete",
                "path": f"/routing-policy/prefix-set[name={ps['name']}]"
            })
        changed = True
    else:
        # 1. Prefix-sets (must exist before policy uses them)
        for ps in config.get("prefix_sets", []):
            cmds.append({
                "action": "update",
                "path": f"/routing-policy/prefix-set[name={ps['name']}]",
                "value": {}
            })
            for prfx in ps.get("prefixes", []):
                cmds.append({
                    "action": "update",
                    "path": f"/routing-policy/prefix-set[name={ps['name']}]/prefix[ip-prefix={prfx['ip_prefix']}][mask-length-range={prfx['mask_length_range']}]",
                    "value": {
                        "ip-prefix": prfx['ip_prefix'],
                        "mask-length-range": prfx['mask_length_range'],
                    }
                })

        # 2. Policies & statements
        # Prefix-sets
        for ps in config.get("prefix_sets", []):
            cmds.append({
                "action": "update",
                "path": f"/routing-policy/prefix-set[name={ps['name']}]",
                "value": {}
            })
            for prfx in ps.get("prefixes", []):
                base_path = f"/routing-policy/prefix-set[name={ps['name']}]/prefix[ip-prefix={prfx['ip_prefix']}][mask-length-range={prfx['mask_length_range']}]"
                cmds.append({
                    "action": "update",
                    "path": base_path,
                    "value": {}
                })
        changed = True

    # Apply commands
    if changed and not module.check_mode and cmds:
        rpc = build_rpc("set", cmds, rpcID())
        response = client.post(payload=json.dumps(rpc))
        if response.get("error"):
            module.fail_json(msg="Server error (UPDATE)", response=pprint.pformat(response))
        after = response.get("result", {})

    module.exit_json(changed=changed, commands=cmds)

if __name__ == "__main__":
    main()
