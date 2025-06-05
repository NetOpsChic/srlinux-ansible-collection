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
module: bgp
short_description: Configure BGP on Nokia SR Linux
description:
  - Configure BGP global, groups, neighbors, and families on Nokia SR Linux.
options:
  config:
    description:
      - BGP configuration dictionary.
    type: dict
    suboptions:
      network_instance:
        description: Network-instance (VRF).
        type: str
        required: true
      router_id:
        description: Router ID (x.x.x.x).
        type: str
        required: true
      admin_state:
        description: Admin state (enable/disable).
        type: str
        choices: [enable, disable]
        default: enable
      autonomous_system:
        description: Local AS number.
        type: int
        required: true
      afi_safi:
        description: Global list of address-families (recommended: always set ipv4-unicast).
        type: list
        elements: dict
        suboptions:
          afi_safi_name:
            type: str
            required: true
          admin_state:
            type: str
            choices: [enable, disable]
      groups:
        description: List of BGP groups.
        type: list
        elements: dict
        suboptions:
          group-name:
            type: str
            required: true
          admin-state:
            type: str
            choices: [enable, disable]
          peer-as:
            type: int
          description:
            type: str
          afi-safi:
            description: List of address-families.
            type: list
            elements: dict
            suboptions:
              afi-safi-name:
                type: str
              admin-state:
                type: str
                choices: [enable, disable]
          export-policy:
            type: str
          import-policy:
            type: str
      neighbors:
        description: List of BGP neighbors.
        type: list
        elements: dict
        suboptions:
          peer-address:
            type: str
            required: true
          peer-as:
            type: int
          peer-group:
            type: str
          admin-state:
            type: str
            choices: [enable, disable]
          description:
            type: str
          afi-safi:
            description: List of address-families.
            type: list
            elements: dict
            suboptions:
              afi-safi-name:
                type: str
              admin_state:
                type: str
                choices: [enable, disable]
          timers:
            type: dict
            suboptions:
              hold-time:
                type: int
              keepalive-interval:
                type: int
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
    bgp_path = f"/network-instance[name=\"{ni}\"]/protocols/bgp"
    cmds = []
    changed = False

    # Handle delete
    if state == "deleted":
        cmds.append({
            "action": "delete",
            "path": bgp_path
        })
        changed = True
    else:
        # 1. Set global BGP process
        bgp_global = {
            "admin-state": cfg.get("admin_state", "enable"),
            "router-id": cfg["router_id"],
            "autonomous-system": cfg["autonomous_system"]
        }
        cmds.append({
            "action": "update",
            "path": bgp_path,
            "value": bgp_global
        })

        # 2. Set BGP global afi-safi (must be done BEFORE group/neigh)
        global_afi_safi = cfg.get("afi_safi", [])
        if not global_afi_safi:
            # Default to ipv4-unicast if not set
            global_afi_safi = [{"afi_safi_name": "ipv4-unicast", "admin_state": "enable"}]
        for af in global_afi_safi:
            af_path = f"{bgp_path}/afi-safi[afi-safi-name={af['afi_safi_name']}]"
            cmds.append({
                "action": "update",
                "path": af_path + "/admin-state",
                "value": af.get("admin_state", "enable")
            })

        # 3. Set BGP groups
        for group in cfg.get("groups", []):
            group_name = group["group-name"]
            group_path = f"{bgp_path}/group[group-name=\"{group_name}\"]"
            group_val = {
                "admin-state": group.get("admin-state", "enable"),
            }
            if group.get("peer-as"):
                group_val["peer-as"] = group["peer-as"]
            if group.get("description"):
                group_val["description"] = group["description"]
            cmds.append({
                "action": "update",
                "path": group_path,
                "value": group_val
            })
            # Per-group afi-safi
            group_afis = group.get("afi-safi", [])
            if not group_afis:
                group_afis = [{"afi-safi-name": "ipv4-unicast", "admin_state": "enable"}]
            for af in group_afis:
                af_path = group_path + f"/afi-safi[afi-safi-name={af['afi-safi-name']}]"
                cmds.append({
                    "action": "update",
                    "path": af_path + "/admin-state",
                    "value": af.get("admin_state", "enable")
                })
            if group.get("export-policy"):
                cmds.append({
                    "action": "update",
                    "path": group_path + "/export-policy",
                    "value": group["export-policy"]
                })
            if group.get("import-policy"):
                cmds.append({
                    "action": "update",
                    "path": group_path + "/import-policy",
                    "value": group["import-policy"]
                })

        # 4. Set BGP neighbors
        for nbr in cfg.get("neighbors", []):
            nbr_addr = nbr["peer-address"]
            nbr_path = f"{bgp_path}/neighbor[peer-address=\"{nbr_addr}\"]"
            nbr_val = {
                "admin-state": nbr.get("admin-state", "enable"),
            }
            if nbr.get("peer-group"):
                nbr_val["peer-group"] = nbr["peer-group"]
            if nbr.get("peer-as"):
                nbr_val["peer-as"] = nbr["peer-as"]
            if nbr.get("description"):
                nbr_val["description"] = nbr["description"]
            cmds.append({
                "action": "update",
                "path": nbr_path,
                "value": nbr_val
            })
            # Per-neighbor afi-safi
            nbr_afis = nbr.get("afi-safi", [])
            if not nbr_afis:
                nbr_afis = [{"afi-safi-name": "ipv4-unicast", "admin_state": "enable"}]
            for af in nbr_afis:
                af_path = nbr_path + f"/afi-safi[afi-safi-name={af['afi-safi-name']}]"
                cmds.append({
                    "action": "update",
                    "path": af_path + "/admin-state",
                    "value": af.get("admin_state", "enable")
                })
            # Timers
            if nbr.get("timers"):
                timers = nbr["timers"]
                timers_path = nbr_path + "/timers"
                timer_val = {}
                if "hold-time" in timers:
                    timer_val["hold-time"] = timers["hold-time"]
                if "keepalive-interval" in timers:
                    timer_val["keepalive-interval"] = timers["keepalive-interval"]
                if timer_val:
                    cmds.append({
                        "action": "update",
                        "path": timers_path,
                        "value": timer_val
                    })

        changed = True

    # Apply changes if needed
    if changed and not module.check_mode and cmds:
        rpc = build_rpc("set", cmds, rpcID())
        response = client.post(payload=json.dumps(rpc))
        if response.get("error"):
            module.fail_json(msg="Server error (UPDATE)", response=pprint.pformat(response))
    module.exit_json(changed=changed, commands=cmds)

if __name__ == "__main__":
    main()
