#!/usr/bin/env python3

import json
import time
import logging
import click

from apstra_bp_consolidation.consolidation import ConsolidationOrder
from apstra_bp_consolidation.consolidation import prep_logging
from apstra_bp_consolidation.apstra_blueprint import CkEnum

def build_access_switch_fabric_links_dict(links_dict:dict) -> dict:
    '''
    Build each "links" data from tor_interface_nodes_in_main
    It is assumed that the interface names are in et-0/0/48-b format
    '''
    # logging.debug(f"{len(links_dict)=}, {links_dict=}")

    translation_table = {
        "et-0/0/48-a": { 'system_peer': 'first', 'system_if_name': 'et-0/0/48' },
        "et-0/0/48-b": { 'system_peer': 'second', 'system_if_name': 'et-0/0/48' },
        "et-0/0/49-a": { 'system_peer': 'first', 'system_if_name': 'et-0/0/49' },
        "et-0/0/49-b": { 'system_peer': 'second', 'system_if_name': 'et-0/0/49' },

        "et-0/0/48a": { 'system_peer': 'first', 'system_if_name': 'et-0/0/48' },
        "et-0/0/48b": { 'system_peer': 'second', 'system_if_name': 'et-0/0/48' },
        "et-0/0/49a": { 'system_peer': 'first', 'system_if_name': 'et-0/0/49' },
        "et-0/0/49b": { 'system_peer': 'second', 'system_if_name': 'et-0/0/49' },
    }

    tor_intf_name = links_dict['gs_intf']['if_name']
    link_candidate = {
            "lag_mode": "lacp_active",
            "system_peer": translation_table[tor_intf_name]['system_peer'],
            "switch": {
                "system_id": links_dict[CkEnum.MEMBER_SWITCH]['id'],
                "transformation_id": 2,
                "if_name": links_dict[CkEnum.MEMBER_INTERFACE]['if_name']
            },
            "system": {
                "system_id": None,
                "transformation_id": 1,
                "if_name": translation_table[tor_intf_name]['system_if_name']
            }
        }
    return link_candidate

def build_switch_pair_spec(tor_interface_nodes_in_main, tor_label) -> dict:
    '''
    Build the switch pair spec from the links query
    '''
    switch_pair_spec = {
        "links": [build_access_switch_fabric_links_dict(x) for x in tor_interface_nodes_in_main],
        "new_systems": None
    }

    # TODO: 
    with open('./tests/fixtures/fixture-switch-system-links-5120.json', 'r') as file:
        sample_data = json.load(file)

    switch_pair_spec['new_systems'] = sample_data['new_systems']
    switch_pair_spec['new_systems'][0]['label'] = tor_label

    return switch_pair_spec


def remove_old_generic_system_from_main(order, tor_ae_id_in_main, tor_interface_nodes_in_main):
    """
    Remove the old generic system from the main blueprint
    """
    if tor_ae_id_in_main is None:
        logging.warning(f"tor_ae_id_in_main is None")
        return
    
    cts_to_remove = order.main_bp.get_interface_cts(tor_ae_id_in_main)

    # damping CTs in chunks
    while len(cts_to_remove) > 0:
        throttle_number = 50
        cts_chunk = cts_to_remove[:throttle_number]
        logging.debug(f"Removing Connecitivity Templates on this links: {len(cts_chunk)=}")
        batch_ct_spec = {
            "operations": [
                {
                    "path": "/obj-policy-batch-apply",
                    "method": "PATCH",
                    "payload": {
                        "application_points": [
                            {
                                "id": tor_ae_id_in_main,
                                "policies": [ {"policy": x, "used": False} for x in cts_chunk]
                            }
                        ]
                    }
                }
            ]
        }
        batch_result = order.main_bp.batch(batch_ct_spec, params={"comment": "batch-api"})
        del cts_to_remove[:throttle_number]

    link_remove_spec = {
        "operations": [
            {
                "path": "/delete-switch-system-links",
                "method": "POST",
                "payload": {
                    "link_ids": [ x['link']['id'] for x in tor_interface_nodes_in_main ]
                }
            }
        ]
    }
    batch_result = order.main_bp.batch(link_remove_spec, params={"comment": "batch-api"})
    logging.debug(f"{link_remove_spec=}")
    while True:
        if_generic_system_present = order.main_bp.query(f"node('system', label='{order.tor_label}')")
        if len(if_generic_system_present) == 0:
            break
        logging.info(f"{if_generic_system_present=}")
        time.sleep(3)
    # the generic system is gone.            

    return


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
    
    REDUNDANCY_GROUP = 'redundancy_group'

    # skip if the access switch piar already exists
    tor_a = f"{order.tor_label}a"
    if order.main_bp.get_system_node_from_label(tor_a):
        logging.info(f"{tor_a} already exists in main blueprint")
        return
    
    access_switch_pair_created = order.main_bp.add_generic_system(switch_pair_spec)
    logging.info(f"{access_switch_pair_created=}")

    # wait for the new system to be created
    while True:
        new_systems = order.main_bp.query(f"""
            node('link', label='{access_switch_pair_created[0]}', name='link')
            .in_().node('interface')
            .in_().node('system', name='leaf')
            .out().node('redundancy_group', name='{REDUNDANCY_GROUP}'
            )""", multiline=True)
        # There should be 5 links (including the peer link)
        if len(new_systems) == 2:
            break
        logging.info(f"Waiting for new systems to be created: {len(new_systems)=}")
        time.sleep(3)

    # The first entry is the peer link

    # rename redundancy group with <tor_label>-pair
    order.main_bp.patch_node_single(
        new_systems[0][REDUNDANCY_GROUP]['id'], 
        {"label": f"{order.tor_label}-pair" }
        )

    # rename each access switch for the label and hostname
    for leaf in new_systems:
        given_label = leaf['leaf']['label']
        # when the label is <tor_label>1, rename it to <tor_label>a
        if given_label[-1] == '1':
            new_label = f"{order.tor_label}a"
        # when the labe is <tor_label>2, rename it to <tor_label>b
        elif given_label[-1] == '2':
            new_label = f"{order.tor_label}b"
        else:
            logging.warning(f"skipp chaning name {given_label=}")
            continue
        order.main_bp.patch_node_single(
            leaf['leaf']['id'], 
            {"label": new_label, "hostname": new_label }
            )


def get_tor_ae_id_in_main(tor_interface_nodes_in_main, tor_name):
    """
    Get the AE id from the nodes list
        Present warning if the AE does not exist
    """
    if len(tor_interface_nodes_in_main) == 0:
        logging.warning(f"{tor_name}  does not exist in main blueprint")
        return None
    if CkEnum.EVPN_INTERFACE not in tor_interface_nodes_in_main[0]:
        logging.warning(f"{tor_name}  does not have AE in main blueprint")
        return None
    return tor_interface_nodes_in_main[0][CkEnum.EVPN_INTERFACE]['id']


@click.command(name='move-access-switch')
def click_move_access_switch():    
    order = ConsolidationOrder()
    main(order)

def main(order):

    tor_name = order.config['blueprint']['tor']['torname']

    tor_interface_nodes_in_main = order.main_bp.get_server_interface_nodes(tor_name)
    tor_ae_id_in_main = get_tor_ae_id_in_main(tor_interface_nodes_in_main, tor_name)

    # build switch pair spec from the main blueprint generic system links
    switch_pair_spec = build_switch_pair_spec(tor_interface_nodes_in_main, order.tor_label)
    
    remove_old_generic_system_from_main(order, tor_ae_id_in_main, tor_interface_nodes_in_main)

    create_new_access_switch_pair(order, switch_pair_spec)

if __name__ == '__main__':
    order = ConsolidationOrder()
    main(order)

