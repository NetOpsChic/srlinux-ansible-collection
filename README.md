# SR Linux Ansible Collection

This Ansible Collection provides modules and example playbooks for automating the configuration of Nokia SR Linux devices.  
It includes native modules for hostname, interface, static routing, network-instance, and routing-policy, with end-to-end automation for lab and production environments.

## Disclaimer
This is a personal side project, actively developed and maintained by a solo developer (me!). While I do my best to keep things working, features and stability may vary over time. Feel free to explore, contribute, or use it—but please do so at your own discretion.

## About

This repository is an independent extension of the [Nokia SR Linux Ansible Collection](https://github.com/nokia/srlinux-ansible-collection).

Original copyright:
  Copyright (c) 2021 Nokia

This work is not affiliated with, endorsed by, or supported by Nokia.

## Credits & Base Repository

This collection is **based on and extends** the [Nokia SR Linux Ansible Collection](https://github.com/nokia/srlinux-ansible-collection).

- Special thanks to the [Nokia SR Linux Ansible Collection](https://github.com/nokia/srlinux-ansible-collection) maintainers and contributors.
- This repository includes **custom modules and playbooks** for advanced, lab-friendly, and production automation scenarios.

## Features

- **Modular Ansible Modules:**  
  - Hostname configuration
  - Network-instance (VRF) creation
  - L3/L2 interface configuration
  - Static route & next-hop group management
  - Routing policy and prefix-set creation
  - BGP and OSPF 

---

## Getting Started

If you wish to execute it or test it against Containerlab 
This collection is **not published on Ansible Galaxy**. To use it:

### **Install the Collection**

1. Clone this repository:
    ```sh
    git clone https://github.com/yourusername/srlinux-ansible-collection.git
    cd srlinux-ansible-collection
    ```

2. Build the collection:
    ```sh
    ansible-galaxy collection build
    ```
    This will create a file like `nokia-srlinux-*.tar.gz`.

3. Install the collection locally:
    ```sh
    ansible-galaxy collection install nokia-srlinux-*.tar.gz
    ```
    *(Or, replace `nokia-srlinux` with whatever is in your `galaxy.yml` if you change it.)*

4. Reference the collection in your playbooks as `nokia.srlinux`.

If you want to use the collection without installing, you can set the environment variable:
```sh
export ANSIBLE_COLLECTIONS_PATHS=$(pwd)
```
### **Structure**
```sh
├── ansible.cfg
├── ansible_collections
│   └── nokia
│       └── srlinux
├── playbooks
│   ├── bgp.yaml
│   ├── hostname.yaml
│   ├── l2_interface.yaml
│   ├── l3_interface.yaml
│   ├── network_instance.yaml
│   ├── ospf_v2.yaml
│   ├── routing_policy.yaml
│   └── static_routes.yaml
```
### **Writing Your Own Modules**

All custom modules should live in plugins/modules/
[See Ansible Docs: Developing Modules](https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_general.html#preparing-an-environment-for-developing-ansible-modules)
M
odules are Python scripts with standard AnsibleModule logic and should match Nokia SR Linux YANG structure.

### License
BSD 3-Clause License