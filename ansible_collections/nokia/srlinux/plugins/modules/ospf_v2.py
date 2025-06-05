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
module: ospf_v2
short_description: Configure OSPFv2 on Nokia SR Linux (all settings)
description:
  - Configure OSPFv2 with global, area, interface, and redistribution settings on SR Linux.
options:
  config:
    description:
      - OSPF configuration parameters.
    type: dict
    suboptions:
      network_instance:
        description: Network-instance name (VRF).
        type: str
        required: true
      router_id:
        description: Router ID.
        type: str
        required: true
      admin_state:
        description: Enable or disable OSPF.
        type: str
        choices: [enable, disable]
      reference_bandwidth:
        description: Reference bandwidth for OSPF.
        type: int
      max_metric:
        description: Set max-metric options.
        type: dict
        suboptions:
          on_startup:
            type: bool
          router_lsa:
            type: int
      spf_timers:
        description: SPF timers.
        type: dict
        suboptions:
          initial_delay:
            type: int
          secondary_delay:
            type: int
          max_delay:
            type: int
      lsa_timers:
        description: LSA timers.
        type: dict
        suboptions:
          initial_delay:
            type: int
          secondary_delay:
            type: int
          max_delay:
            type: int
          min_arrival_interval:
            type: int
      graceful_restart:
        description: Enable/disable OSPF graceful-restart.
        type: bool
      export_policy:
        description: Policy for exporting routes into OSPF.
        type: str
      areas:
        description: List of areas.
        type: list
        elements: dict
        suboptions:
          area_id:
            description: Area ID (e.g. 0.0.0.0).
            type: str
            required: true
          type:
            description: Area type (normal, stub, nssa).
            type: str
          range:
            description: List of area ranges.
            type: list
            elements: dict
            suboptions:
              prefix:
                type: str
              advertise:
                type: bool
          interfaces:
            description: List of interfaces in this area.
            type: list
            elements: dict
            suboptions:
              name:
                type: str
                required: true
              admin_state:
                type: str
                choices: [enable, disable]
              cost:
                type: int
              priority:
                type: int
              hello_interval:
                type: int
              dead_interval:
                type: int
              network_type:
                type: str
                choices: [broadcast, point-to-point]
              authentication:
                type: dict
                suboptions:
                  type:
                    type: str
                  key_id:
                    type: int
                  key:
                    type: str
              passive:
                type: bool
      redistribute:
        description: List of redistribution rules.
        type: list
        elements: dict
        suboptions:
          protocol:
            type: str
            choices: [static, direct, bgp]
          policy:
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
    cfg = module.params['config']
    ni = cfg["network_instance"]
    ospf_path = f"/network-instance[name=\"{ni}\"]/protocols/ospf/instance[name=\"1\"]"
    cmds = []
    changed = False

    # Handle deleted
    if state == "deleted":
        cmds.append({
            "action": "delete",
            "path": ospf_path
        })
        changed = True
    else:
        ospf_conf = {
            "admin-state": cfg.get("admin_state", "enable"),
            "router-id": cfg["router_id"],
            "version": "ospf-v2"
        }
        if cfg.get("reference_bandwidth") is not None:
            ospf_conf["reference-bandwidth"] = cfg["reference_bandwidth"]
        if cfg.get("max_metric"):
            mm = cfg["max_metric"]
            ospf_conf["max-metric"] = {}
            if "on_startup" in mm:
                ospf_conf["max-metric"]["on-startup"] = mm["on_startup"]
            if "router_lsa" in mm:
                ospf_conf["max-metric"]["router-lsa"] = mm["router_lsa"]
        if cfg.get("spf_timers"):
            spf = cfg["spf_timers"]
            ospf_conf["spf-timers"] = {}
            for k, v in spf.items():
                ospf_conf["spf-timers"][k.replace('_', '-')] = v
        if cfg.get("lsa_timers"):
            lsa = cfg["lsa_timers"]
            ospf_conf["lsa-timers"] = {}
            for k, v in lsa.items():
                ospf_conf["lsa-timers"][k.replace('_', '-')] = v
        if cfg.get("graceful_restart") is not None:
            ospf_conf["graceful-restart"] = cfg["graceful_restart"]
        if cfg.get("export_policy"):
            ospf_conf["export-policy"] = cfg["export_policy"]

        # 1. Set the OSPF instance itself
        cmds.append({
            "action": "update",
            "path": ospf_path,
            "value": ospf_conf
        })

        # 2. Area configs
        if cfg.get("areas"):
            for area in cfg["areas"]:
                area_id = area["area_id"]
                area_path = ospf_path + f"/area[area-id=\"{area_id}\"]"
                area_conf = {}
                if area.get("type"):
                    area_conf["type"] = area["type"]
                if area.get("range"):
                    area_conf["range"] = []
                    for r in area["range"]:
                        ritem = {"prefix": r["prefix"]}
                        if "advertise" in r:
                            ritem["advertise"] = r["advertise"]
                        area_conf["range"].append(ritem)
                cmds.append({
                    "action": "update",
                    "path": area_path,
                    "value": area_conf
                })

                # 3. Interface configs within area
                if area.get("interfaces"):
                    for iface in area["interfaces"]:
                        iface_path = area_path + f"/interface[interface-name=\"{iface['name']}\"]"
                        iface_conf = {}
                        if iface.get("admin_state"):
                            iface_conf["admin-state"] = iface["admin_state"]
                        if iface.get("cost") is not None:
                            iface_conf["cost"] = iface["cost"]
                        if iface.get("priority") is not None:
                            iface_conf["priority"] = iface["priority"]
                        if iface.get("hello_interval") is not None:
                            iface_conf["hello-interval"] = iface["hello_interval"]
                        if iface.get("dead_interval") is not None:
                            iface_conf["dead-interval"] = iface["dead_interval"]
                        if iface.get("network_type"):
                            iface_conf["network-type"] = iface["network_type"]
                        if iface.get("passive") is not None:
                            iface_conf["passive"] = iface["passive"]
                        if iface.get("authentication"):
                            auth = iface["authentication"]
                            iface_conf["authentication"] = {
                                "type": auth.get("type", "none"),
                            }
                            if "key_id" in auth:
                                iface_conf["authentication"]["key-id"] = auth["key_id"]
                            if "key" in auth:
                                iface_conf["authentication"]["key"] = auth["key"]
                        cmds.append({
                            "action": "update",
                            "path": iface_path,
                            "value": iface_conf
                        })
        

        changed = True

    if changed and not module.check_mode and cmds:
        rpc = build_rpc("set", cmds, rpcID())
        response = client.post(payload=json.dumps(rpc))
        if response.get("error"):
            module.fail_json(msg="Server error (UPDATE)", response=pprint.pformat(response))
        after = response.get("result", {})

    module.exit_json(changed=changed, commands=cmds)

if __name__ == "__main__":
    main()
