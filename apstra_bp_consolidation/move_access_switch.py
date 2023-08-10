#!/usr/bin/env python3

import json
import time
import logging

# from move_generic_system import pull_generic_system_off_switch
from consolidation import ConsolidationOrder
from consolidation import prep_logging

# def get_old_generic_system_ae_id(order) -> str:
#     '''
#     get generic system id for the tor blueprint from the main blueprint
#     '''
#     # find the switch side ae information from the old generic system in the main blueprint
#     old_generic_system_ae_query = f"""
#         node('system', label='{order.old_generic_system_label}')
#             .out().node('interface', if_type='port_channel', name='generic_ae')
#             .out().node('link')
#             .in_().node(name='switch_ae')
#             .where(lambda generic_ae, switch_ae: generic_ae != switch_ae )
#     """
#     # old_generic_system_ae_query = f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='port_channel', name='generic_ae').out().node('link').in_().node(name='switch_ae').where(lambda generic_ae, switch_ae: generic_ae != switch_ae )"
#     old_generic_system_ae_list = order.main_bp.query(old_generic_system_ae_query, print_prefix="get_old_generic_system_ae_id(): old_generic_system_ae_query", multiline=True)
#     # the generic system should exist in main blueprint
#     if len(old_generic_system_ae_list):
#         old_generic_system_ae_id = old_generic_system_ae_list[0]['switch_ae']['id']
#         print(f"== Order::get_old_generic_system_ae_id: {old_generic_system_ae_id =}")
#         return old_generic_system_ae_id
#     return None

def build_switch_fabric_links_dict(links_dict:dict) -> dict:
    '''
    Build "links" data from the links query
    It is assumed that the interface names are in et-0/0/48-b format
    '''
    # print(f"==== build_switch_fabric_links_dict() {len(links_dict)=}, {links_dict=}")
    link_candidate = {
            "lag_mode": "lacp_active",
            "system_peer": None,
            "switch": {
                "system_id": links_dict['switch']['id'],
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
        return None
    return link_candidate

#     # old_generic_system_physical_links has a list of dict with generic, gs_intf, link, leaf_intf, and leaf 
def build_switch_pair_spec(old_generic_system_physical_links, old_generic_system_label) -> dict:
    '''
    Build the switch pair spec from the links query
    '''
    # print(f"==== build_switch_pair_spec() with {len(old_generic_system_physical_links)=}, {old_generic_system_label}")
    # print(f"===== build_switch_pair_spec() {old_generic_system_physical_links[0]=}")
    switch_pair_spec = {
        "links": [build_switch_fabric_links_dict(x) for x in old_generic_system_physical_links],
        "new_systems": None
    }

    # TODO: 
    with open('./tests/fixtures/fixture-switch-system-links-5120.json', 'r') as file:
        sample_data = json.load(file)

    switch_pair_spec['new_systems'] = sample_data['new_systems']
    switch_pair_spec['new_systems'][0]['label'] = old_generic_system_label

    # del switch_pair_spec['new_systems']
    print(f"====== build_switch_pair_spec() from {len(old_generic_system_physical_links)=}")
    return switch_pair_spec


def remove_old_generic_system_from_main(order):
    """
    Remove the old generic system from the main blueprint
    """
    tor_name = order.config['blueprint']['tor']['torname']
    old_generic_system_ae_id = None

    tor_interfaces = order.main_bp.get_interfaces_of_generic_system(tor_name)
    if len(tor_interfaces) == 0:
        logging.warning(f"{tor_name}  does not exist in main blueprint")
        return
    if 'ae' not in tor_interfaces[0]:
        logging.warning(f"{tor_name}  does not have AE in main blueprint")
        return
    old_generic_system_ae_id = tor_interfaces[0]['ae']['id']
    # logging.warning(f"{old_generic_system_ae_id=}")

    cts_to_remove = order.main_bp.get_cts_on_generic_system_with_only_ae(order.old_generic_system_label)

    # capture links to the target old generic system in the main blueprint
    old_generic_system_physical_links_query = f"""
        node('system', label='{order.old_generic_system_label}', name='generic')
            .out().node('interface', if_type='ethernet', name='gs_intf')
            .out().node('link', name='link')
            .in_().node('interface', name='leaf_intf')
            .in_().node('system', system_type='switch', name='switch')
    """
    print(f"== remove_old_generic_system: {old_generic_system_physical_links_query=}")
    # old_generic_system_physical_links has a list of dict with generic, gs_intf, link, leaf_intf, and leaf 
    old_generic_system_physical_links = order.main_bp.query(old_generic_system_physical_links_query, multiline=True)

    print(f"== remove_old_generic_system: about to call build_switch_pair_spec, {len(old_generic_system_physical_links)=}")
    switch_pair_spec = build_switch_pair_spec(old_generic_system_physical_links, order.old_generic_system_label)
    print(f"== remove_old_generic_system: {switch_pair_spec['links']=}")

    # # TODO: Not used?
    # pull_generic_system_data = pull_generic_system_off_switch(order.tor_bp, order.switch_label_pair)
    # # pretty_yaml(pull_generic_system_data, "pull_generic_system_data")



    ########
    # delete the old generic system in main blueprint
    # all the CTs on old generic system are on the AE link
    print(f"== remove_old_generic_system: {order=}")
    # if len(old_generic_system_ae_list):
    if old_generic_system_ae_id:
        # old_generic_system_label = order.config['blueprint']['tor']['torname']
        # old_generic_system_ae_list = order.main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').where(lambda ae1, ae2: ae1 != ae2 )")
        # if len(old_generic_system_ae_list) == 0:
        #     print(f"Generic system {old_generic_system_label} not found")
        #     return
        # old_generic_system_ae_id = old_generic_system_ae_list[0]['ae1']['id']
        # print(f"{old_generic_system_ae_id=}")

        # cts = order.main_bp.get_cts_on_generic_system_with_only_ae(old_generic_system_label)

        # old_generic_system_physical_links has a list of dict with generic, gs_intf, link, leaf_intf, and leaf 
        # old_generic_system_physical_links = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='ethernet').out().node('link', name='link')")
        old_generic_system_physical_links = order.main_bp.query(f"node('system', label='{order.old_generic_system_label}').out().node('interface', if_type='ethernet', name='gs_intf').out().node('link', name='link').in_().node('interface', name='leaf_intf').in_().node('system', name='leaf').where(lambda gs_intf, leaf_intf: gs_intf != leaf_intf)")


        # damping CTs in chunks
        while len(cts_to_remove) > 0:
            cts_chunk = cts_to_remove[:50]
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
            batch_result = order.main_bp.batch(batch_ct_spec, params={"comment": "batch-api"})
            del cts_to_remove[:50]

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
        batch_result = order.main_bp.batch(batch_link_spec, params={"comment": "batch-api"})
        print(f"== remove_old_generic_system: {batch_result=}")
        while True:
            if_generic_system_present = order.main_bp.query(f"node('system', label='{order.old_generic_system_label}')")
            if len(if_generic_system_present) == 0:
                break
            print(f"== remove_old_generic_system: {if_generic_system_present=}")
            time.sleep(3)
        # the generic system is gone.            

    return switch_pair_spec


def create_new_access_switch_pair(order, switch_pair_spec):
    ########
    # create new access system pair
    # olg logical device is not useful anymore
    # logical_device_list = tor_bp.query("node('system', name='system', role=not_in(['generic'])).out().node('logical_device', name='ld')")
    # logical_device_id = logical_device_list[0]['ld']['id']

    # LD _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # IM _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # rack type _ATL-AS-5100-48T, _ATL-AS-5120-48T created and added
    # ATL-AS-LOOPBACK with 10.29.8.0/22

    existing_switches = order.main_bp.query(f"node('system', label='{order.old_generic_system_label}a', name='system')")
    if len(existing_switches):
        print(f"== create_new_access_switch_pair: {existing_switches=}")
        return
    access_switch_pair_created = order.main_bp.add_generic_system(switch_pair_spec)
    print(f"{access_switch_pair_created=}")

    # wait for the new systems to be created
    while True:
        new_systems = order.main_bp.query(f"node('link', label='{access_switch_pair_created[0]}', name='link').in_().node('interface').in_().node('system', name='leaf').out().node('redundancy_group', name='redundancy_group')")
        # There should be 5 links (including the peer link)
        if len(new_systems) == 2:
            break
        print(f"Waiting for new systems to be created: {len(new_systems)=}")
        time.sleep(3)
    # The first entry is the peer link
    # rename redundancy group
    order.main_bp.patch_node_single(new_systems[0]['redundancy_group']['id'], {"label": f"{order.old_generic_system_label}-pair" })
    # rename each access switch for the label and hostname
    for leaf in new_systems:
        given_label = leaf['leaf']['label']
        if given_label[-1] == '1':
            new_label = f"{order.old_generic_system_label}a"
        elif given_label[-1] == '2':
            new_label = f"{order.old_generic_system_label}b"
        else:
            raise Exception(f"During renaming leaf names: Unexpected leaf label {given_label}")
        order.main_bp.patch_node_single(leaf['leaf']['id'], {"label": new_label, "hostname": new_label })


def main(yaml_in_file):
    order = ConsolidationOrder(yaml_in_file)

    # find the switch side ae information from the old generic system in the main blueprint
    # old_generic_system_ae_id = get_old_generic_system_ae_id(order)


    cts = order.main_bp.get_cts_on_generic_system_with_only_ae(order.old_generic_system_label)

    switch_pair_spec = remove_old_generic_system_from_main(order)

    create_new_access_switch_pair(order, switch_pair_spec)

if __name__ == '__main__':
    log_level = logging.DEBUG
    prep_logging(log_level)
    main('./tests/fixtures/config.yaml')    


