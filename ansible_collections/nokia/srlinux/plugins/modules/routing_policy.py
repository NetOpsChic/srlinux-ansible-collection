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
  - Configure BGP global, groups, neighbors, and AFI/SAFI on Nokia SR Linux.
  - Attaches routing policies at the NEIGHBOR level as list entries.
options:
  config:
    type: dict
    required: true
  state:
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

def _norm_afi_name(af: dict):
    return af.get("afi_safi_name") or af.get("afi-safi-name")

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
    bgp_path = f'/network-instance[name="{ni}"]/protocols/bgp'

    cmds = []
    changed = False

    if state == "deleted":
        cmds.append({"action": "delete", "path": bgp_path})
        changed = True
    else:
        # 1) Global BGP core settings
        bgp_global = {
            "admin-state": cfg.get("admin_state", "enable"),
            "router-id": cfg["router_id"],
            "autonomous-system": cfg["autonomous_system"],
        }
        cmds.append({"action": "update", "path": bgp_path, "value": bgp_global})

        # 2) Global AFI/SAFI presence (admin-state only)
        global_afis = cfg.get("afi_safi", []) or [{"afi_safi_name": "ipv4-unicast", "admin_state": "enable"}]
        for af in global_afis:
            af_name = _norm_afi_name(af)
            if not af_name:
                continue
            af_path = f'{bgp_path}/afi-safi[afi-safi-name={af_name}]'
            cmds.append({
                "action": "update",
                "path": af_path + "/admin-state",
                "value": af.get("admin_state", "enable")
            })

        # 3) Groups (presence and basics)
        for group in cfg.get("groups", []) or []:
            gname = group["group-name"]
            gp_path = f'{bgp_path}/group[group-name="{gname}"]'
            gval = {"admin-state": group.get("admin-state", "enable")}
            if group.get("peer-as") is not None:
                gval["peer-as"] = group["peer-as"]
            if group.get("description"):
                gval["description"] = group["description"]
            cmds.append({"action": "update", "path": gp_path, "value": gval})

            # group AFI/SAFI presence (admin-state only)
            gafis = group.get("afi-safi", []) or [{"afi-safi-name": "ipv4-unicast", "admin_state": "enable"}]
            for gaf in gafis:
                gaf_name = _norm_afi_name(gaf)
                if not gaf_name:
                    continue
                gaf_path = f'{gp_path}/afi-safi[afi-safi-name={gaf_name}]'
                cmds.append({
                    "action": "update",
                    "path": gaf_path + "/admin-state",
                    "value": gaf.get("admin_state", "enable")
                })

        # 4) Neighbors + policies
        for nbr in cfg.get("neighbors", []) or []:
            naddr = nbr["peer-address"]
            n_path = f'{bgp_path}/neighbor[peer-address="{naddr}"]'
            nval = {"admin-state": nbr.get("admin-state", "enable")}
            if nbr.get("peer-group"):
                nval["peer-group"] = nbr["peer-group"]
            if nbr.get("peer-as") is not None:
                nval["peer-as"] = nbr["peer-as"]
            if nbr.get("description"):
                nval["description"] = nbr["description"]
            cmds.append({"action": "update", "path": n_path, "value": nval})

            # neighbor-level policies (LIST KEYS = node name)
            if nbr.get("export-policy"):
                ep = nbr["export-policy"]
                cmds.append({
                    "action": "update",
                    "path": f'{n_path}/export-policy[export-policy="{ep}"]',
                    "value": {}
                })
            if nbr.get("import-policy"):
                ip = nbr["import-policy"]
                cmds.append({
                    "action": "update",
                    "path": f'{n_path}/import-policy[import-policy="{ip}"]',
                    "value": {}
                })

            # Neighbor AFI/SAFI (admin-state only + optional defaults)
            nafis = nbr.get("afi-safi", []) or [{"afi-safi-name": "ipv4-unicast", "admin_state": "enable"}]
            for naf in nafis:
                naf_name = _norm_afi_name(naf)
                if not naf_name:
                    continue
                naf_path = f'{n_path}/afi-safi[afi-safi-name={naf_name}]'

                cmds.append({
                    "action": "update",
                    "path": naf_path + "/admin-state",
                    "value": naf.get("admin_state", "enable")
                })

                def_exp = naf.get("default-export-policy") or naf.get("default_export_policy")
                def_imp = naf.get("default-import-policy") or naf.get("default_import_policy")
                if def_exp in ("accept", "reject"):
                    cmds.append({
                        "action": "update",
                        "path": naf_path + "/default-export-policy",
                        "value": def_exp
                    })
                if def_imp in ("accept", "reject"):
                    cmds.append({
                        "action": "update",
                        "path": naf_path + "/default-import-policy",
                        "value": def_imp
                    })

            # Neighbor timers (optional)
            if nbr.get("timers"):
                timers = nbr["timers"]
                tval = {}
                if "hold-time" in timers:
                    tval["hold-time"] = timers["hold-time"]
                if "keepalive-interval" in timers:
                    tval["keepalive-interval"] = timers["keepalive-interval"]
                if tval:
                    cmds.append({"action": "update", "path": n_path + "/timers", "value": tval})

        changed = True

    # Apply
    if changed and not module.check_mode and cmds:
        rpc = build_rpc("set", cmds, rpcID())
        response = client.post(payload=json.dumps(rpc))
        if response.get("error"):
            module.fail_json(msg="Server error (UPDATE)", response=pprint.pformat(response))

    module.exit_json(changed=changed, commands=cmds)

if __name__ == "__main__":
    main()
