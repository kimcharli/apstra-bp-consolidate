#!/usr/bin/env python3

import json
import time

from apstra_bp_consolidation.apstra_session import CkApstraSession
from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint







def build_links_dict(links_dict:dict) -> dict:
    '''
    Build "links" data from the links query
    It is assumed that the interface names are in et-0/0/48-b format
    '''
    # print(f"{links_dict=}")
    link_candidate = {
            "lag_mode": "lacp_active",
            "system_peer": None,
            "switch": {
                "system_id": links_dict['leaf']['id'],
                "transformation_id": 2,
                "if_name": links_dict['leaf_intf']['if_name']
            },
            "system": {
                "system_id": None,
                "transformation_id": 1,
                "if_name": None
            }
        }
    original_intf_name = links_dict['gs_intf']['if_name']
    if original_intf_name in ['et-0/0/48-a', 'et-0/0/48a']:
        link_candidate['system_peer'] = 'first'
        link_candidate['system']['if_name'] = 'et-0/0/48'
    elif original_intf_name in ['et-0/0/48-b', 'et-0/0/48b']:
        link_candidate['system_peer'] = 'second'
        link_candidate['system']['if_name'] = 'et-0/0/48'
    elif original_intf_name in ['et-0/0/49-a', 'et-0/0/49a']:
        link_candidate['system_peer'] = 'first'
        link_candidate['system']['if_name'] = 'et-0/0/49'
    elif original_intf_name in ['et-0/0/49-b', 'et-0/0/49b']:
        link_candidate['system_peer'] = 'second'
        link_candidate['system']['if_name'] = 'et-0/0/49'
    else:
        raise Exception(f"Unknown interface name {original_intf_name}")
    return link_candidate

def build_access_switch_pair_spec(old_generic_system_physical_links, old_generic_system_label) -> dict:
    access_switch_pair_spec = {
        "links": [build_links_dict(x) for x in old_generic_system_physical_links],
        "new_systems": None
    }

    with open('./tests/fixtures/switch-system-links-5120.json', 'r') as file:
        sample_data = json.load(file)

    access_switch_pair_spec['new_systems'] = sample_data['new_systems']
    access_switch_pair_spec['new_systems'][0]['label'] = old_generic_system_label

    return access_switch_pair_spec


def main(apstra: str, config: dict):
    print(f"{config=}")

    ########
    # prepare the data with initial validation    
    main_bp = CkApstraBlueprint(apstra, config['blueprint']['main']['name'])
    tor_bp = CkApstraBlueprint(apstra, config['blueprint']['tor']['name'])
    access_switch_interface_map_label = config['blueprint']['tor']['new_interface_map']

    old_generic_system_label = config['blueprint']['tor']['torname']
    old_generic_system_ae_list = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').where(lambda ae1, ae2: ae1 != ae2 )")
    # the generic system should exist in main blueprint
    if len(old_generic_system_ae_list) == 0:
        print(f"Generic system {old_generic_system_label} not found")
        return
    old_generic_system_ae_id = old_generic_system_ae_list[0]['ae1']['id']
    print(f"{old_generic_system_ae_id=}")

    cts = main_bp.cts_single_ae_generic_system(old_generic_system_label)

    old_generic_system_physical_links = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='ethernet', name='gs_intf').out().node('link', name='link').in_().node('interface', name='leaf_intf').in_().node('system', name='leaf').where(lambda gs_intf, leaf_intf: gs_intf != leaf_intf)")

    access_switch_pair_spec = build_access_switch_pair_spec(old_generic_system_physical_links, old_generic_system_label)



    # revert any staged changes
    # main_bp.revert()
    # tor_bp.revert()

    ########
    # delete the old generic system
    # all the CTs on old generic system are on the AE link
    old_generic_system_label = config['blueprint']['tor']['torname']
    old_generic_system_ae_list = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').where(lambda ae1, ae2: ae1 != ae2 )")
    if len(old_generic_system_ae_list) == 0:
        print(f"Generic system {old_generic_system_label} not found")
        return
    old_generic_system_ae_id = old_generic_system_ae_list[0]['ae1']['id']
    print(f"{old_generic_system_ae_id=}")

    cts = main_bp.cts_single_ae_generic_system(old_generic_system_label)

    # old_generic_system_physical_links = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='ethernet').out().node('link', name='link')")
    old_generic_system_physical_links = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='ethernet', name='gs_intf').out().node('link', name='link').in_().node('interface', name='leaf_intf').in_().node('system', name='leaf').where(lambda gs_intf, leaf_intf: gs_intf != leaf_intf)")


    # damping CTs in chunks
    while len(cts) > 0:
        cts_chunk = cts[:50]
        print(f"Removing Connecitivity Templates on this links: {len(cts_chunk)=}")
        batch_ct_spec = {
            "operations": [
                {
                    "path": "/obj-policy-batch-apply",
                    "method": "PATCH",
                    "payload": {
                        "application_points": [
                            {
                                "id": old_generic_system_ae_id,
                                "policies": [ {"policy": x, "used": False} for x in cts_chunk]
                            }
                        ]
                    }
                }
            ]
        }
        batch_result = main_bp.batch(batch_ct_spec, params={"comment": "batch-api"})
        del cts[:50]

    batch_link_spec = {
        "operations": [
            {
                "path": "/delete-switch-system-links",
        		"method": "POST",
                "payload": {
                    "link_ids": [ x['link']['id'] for x in old_generic_system_physical_links ]
                }
            }
        ]
    }
    batch_result = main_bp.batch(batch_link_spec, params={"comment": "batch-api"})
    print(f"{batch_result=}")


    ########
    # create new access system pair
    # olg logical device is not useful anymore
    # logical_device_list = tor_bp.query("node('system', name='system', role=not_in(['generic'])).out().node('logical_device', name='ld')")
    # logical_device_id = logical_device_list[0]['ld']['id']

    # LD _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # IM _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # rack type _ATL-AS-5100-48T, _ATL-AS-5120-48T created and added
    # ATL-AS-LOOPBACK with 10.29.8.0/22

    access_switch_pair_created = main_bp.add_generic_system(access_switch_pair_spec)
    print(f"{access_switch_pair_created=}")

    while True:
        new_systems = main_bp.query(f"node('link', label='{access_switch_pair_created[0]}', name='link').in_().node('interface').in_().node('system', name='leaf').out().node('redundancy_group', name='redundancy_group')")
        # There should be 5 links (including the peer link)
        if len(new_systems) == 2:
            break
        print(f"Waiting for new systems to be created: {len(new_systems)=}")
        time.sleep(3)
    # The first entry is the peer link
    # rename redundancy group
    main_bp.patch_node(new_systems[0]['redundancy_group']['id'], {"label": f"{old_generic_system_label}-pair" })
    # rename each access switch for the label and hostname
    for leaf in new_systems:
        given_label = leaf['leaf']['label']
        if given_label[-1] == '1':
            new_label = f"{old_generic_system_label}a"
        elif given_label[-1] == '2':
            new_label = f"{old_generic_system_label}b"
        else:
            raise Exception(f"During renaming leaf names: Unexpected leaf label {given_label}")
        main_bp.patch_node(leaf['leaf']['id'], {"label": new_label, "hostname": new_label })

    # create new generic systems

    # assign virtual networks
    vn_list = tor_bp.query(f"node('system', name='system', role=not_in(['generic'])).out().node('vn_instance').out().node('virtual_network', name='vn')")
    # print(f"{vn_list=}")

    # assign connectivity templates

    pass

if __name__ == "__main__":
    import yaml

    with open('./tests/fixtures/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    apstra = CkApstraSession("10.85.192.61", 443, "admin", "zaq1@WSXcde3$RFV")
    main(apstra, config)

