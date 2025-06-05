#!/usr/bin/python
# Copyright 2023 Nokia
# Licensed under the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause

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
module: hostname
short_description: Manage system hostname on Nokia SR Linux via JSON-RPC
description:
  - Retrieve, set, or delete the system hostname using JSON-RPC against SR Linux.
version_added: "1.0.0"
options:
  config:
    description:
      - Hostname configuration.
    type: dict
    required: true
  state:
    description:
      - Whether to set (merged) or delete the hostname.
    type: str
    choices: [merged, deleted]
    default: merged
author:
  - Uzma Saman (@NetOpsChic)
'''

EXAMPLES = r'''
- name: Set SR Linux hostname
  nokia.srlinux.hostname:
    config:
      hostname: srl01
    state: merged

- name: Remove SR Linux hostname
  nokia.srlinux.hostname:
    config: {}
    state: deleted
'''

RETURN = r'''
before:
  description: Hostname before the change.
  type: str
after:
  description: Hostname after the change.
  type: str
changed:
  description: Whether a change was made.
  type: bool
'''

def main():
    module = AnsibleModule(
        argument_spec=dict(
            config=dict(type='dict', required=True),
            state=dict(type='str', choices=['merged', 'deleted'], default='merged'),
        ),
        supports_check_mode=True
    )

    client = JSONRPCClient(module)

    def build_rpc(method, commands, req_id):
        return {
            "jsonrpc": JSON_RPC_VERSION,
            "method": method,
            "params": {"commands": commands},
            "id": req_id
        }

    # 1) GET current hostname
    get_commands = [{"path": "/system/name/host-name"}]
    get_rpc = build_rpc("get", get_commands, rpcID())
    response = client.post(payload=json.dumps(get_rpc))

    # Error handling for GET
    if response.get("error"):
        module.fail_json(msg="Server error (GET)", response=pprint.pformat(response))

    # --- Normalize result: handle both list and dict ---
    result = response.get("result", {})
    if isinstance(result, list):
        if len(result) > 0 and isinstance(result[0], dict):
            result = result[0]
        else:
            result = {}

    entry = result.get("/system/name/host-name")
    before = entry["value"] if entry and "value" in entry else None

    # Prepare outputs
    desired = module.params["config"].get("hostname")
    state   = module.params["state"]
    changed = False
    after   = before

    # 2) DELETE case
    if state == "deleted":
        if before is not None:
            changed = True
            if not module.check_mode:
                del_commands = [{"action": "delete", "path": "/system/name/host-name"}]
                del_rpc = build_rpc("set", del_commands, rpcID())
                response = client.post(payload=json.dumps(del_rpc))
                if response.get("error"):
                    module.fail_json(
                        msg="Server error (DELETE)", 
                        response=pprint.pformat(response)
                    )
                after = None

    # 3) MERGE (set) case
    else:
        if not desired:
            module.fail_json(msg="config.hostname is required when state=merged")
        if before != desired:
            changed = True
            if not module.check_mode:
                set_commands = [{"action": "update", "path": "/system/name/host-name", "value": desired}]
                set_rpc = build_rpc("set", set_commands, rpcID())
                response = client.post(payload=json.dumps(set_rpc))
                if response.get("error"):
                    module.fail_json(
                        msg="Server error (SET)", 
                        response=pprint.pformat(response)
                    )
                after = desired

    module.exit_json(changed=changed, before=before, after=after)

if __name__ == "__main__":
    main()
