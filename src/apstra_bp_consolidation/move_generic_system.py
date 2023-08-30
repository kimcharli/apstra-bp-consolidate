#!/usr/bin/env python3

import json
import logging
import click
import time

from apstra_bp_consolidation.consolidation import ConsolidationOrder
from apstra_bp_consolidation.apstra_blueprint import CkEnum


def pull_generic_system_off_switch(the_bp, switch_label_pair: list) -> dict:
    """
    Pull the generic system off switches from the blueprint.

    Args:
        the_bp: The blueprint object.
        switch_label_pair: The switch pair to pull the generic system from.    

    <generic_system_label>:
        <link_id>:
            gs_if_name: None
            sw_if_name: xe-0/0/15
            sw_label: leaf15
            speed: 10G
            aggregate_link: <aggregate_link_id>
            tags: []
    """
    logging.info(f"{switch_label_pair=} of blueprint {the_bp.label}")
    generic_systems_data = {}

    interface_nodes_in_tor = the_bp.get_switch_interface_nodes(switch_label_pair)

    for link in interface_nodes_in_tor:
        # skip the uplinks. peer link will not present
        logging.debug(f"reading link: {link[CkEnum.MEMBER_SWITCH]['label']}:{link[CkEnum.MEMBER_INTERFACE]['if_name']}")
        if link[CkEnum.MEMBER_INTERFACE]['if_name'] in ["et-0/0/48", "et-0/0/49"]:
            logging.debug(f"skipping uplink: {link[CkEnum.MEMBER_SWITCH]['label']}:{link[CkEnum.MEMBER_INTERFACE]['if_name']}")
            continue
        generic_system_label = link[CkEnum.GENERIC_SYSTEM]['label']
        link_id = link[CkEnum.LINK]['id']
        # create entry for this generic system if it doesn't exist
        if generic_system_label not in generic_systems_data.keys():
            generic_systems_data[generic_system_label] = {}
        if link_id in generic_systems_data[generic_system_label].keys():
            # this link is already in the generic system data
            # this happens when the link has multiple tags
            this_data = generic_systems_data[generic_system_label][link_id]
        else:
            this_data = {'tags': []}
            this_data['sw_label'] = link[CkEnum.MEMBER_SWITCH]['label']
            this_data['sw_if_name'] = link[CkEnum.MEMBER_INTERFACE]['if_name']
            this_data['speed'] = link[CkEnum.LINK]['speed']
            if link[CkEnum.EVPN_INTERFACE]:
                this_data['aggregate_link'] = link[CkEnum.EVPN_INTERFACE]['id']
        if link['tag']:
            this_data['tags'].append(link[CkEnum.TAG]['label'])
        generic_systems_data[generic_system_label][link_id] = this_data

    return generic_systems_data

# generic system data: generic_system_label.link.dict
def new_generic_systems(order, generic_system_data:dict) -> dict:
    """
    Create new generic systems in the main blueprint based on the generic systems in the TOR blueprint. 
        <generic_system_label>:
            <link_id>:
                gs_if_name: None
                sw_if_name: xe-0/0/15
                sw_label: atl1tor-r5r14a
                speed: 10G
                aggregate_link: <aggregate_link_id>
                tags: []

    """
    # to cache the system id of the systems includin leaf
    main_bp = order.main_bp
    total_generic_system_count = len(generic_system_data)
    current_generic_system_count = 1
    logging.info(f"Creating new generic systems for {main_bp.label=}: {total_generic_system_count=}")

    # wait for the access switch to be created
    for switch_label in order.switch_label_pair:
        for i in range(5):
            switch_nodes = main_bp.get_system_node_from_label(switch_label)
            # it returns None if the system is not created yet
            if switch_nodes:
                break
            logging.info(f"waiting for {switch_label} to be created in {main_bp.label}")
            time.sleep(3)
    logging.info(f"{order.switch_label_pair} present in {main_bp.label}")

    # itrerate through the generic systems retrived from the TOR blueprint
    for generic_system_label, gs_data in generic_system_data.items():
        # working with a generic system 
        logging.debug(f"Creating {generic_system_label=} {gs_data=}")
        # this generic system is present in the main blueprint
        if main_bp.get_system_node_from_label(generic_system_label):
            logging.info(f"skipping: {generic_system_label} is present in the main blueprint")
            continue
        # this generic system is absent in main blueprint. Create it.
        lag_group = {}
        generic_system_spec = {
            'links': [],
            'new_systems': [],
        }

        # the link data has dependancy on the order
        link_list = [ v for k, v in gs_data.items()]
        for i in range(len(link_list)):
        # for _, link_data in generic_system_data.items():
            link_data = link_list[i]
            link_spec = {
                'lag_mode': None,
                'system': {
                    'system_id': None
                },
                'switch': {
                    # TODO: this might need to wait for the system to be created
                    'system_id': main_bp.get_system_node_from_label(link_data['sw_label'])['id'],
                    'transformation_id': main_bp.get_transformation_id(link_data['sw_label'], link_data['sw_if_name'] , link_data['speed']),
                    'if_name': link_data['sw_if_name'],
                }                
            }
            if 'aggregate_link' in link_data:
                old_aggregate_link_id = link_data['aggregate_link']
                if old_aggregate_link_id not in lag_group:
                    lag_group[old_aggregate_link_id] = f"link{len(lag_group)+1}"
                # link_spec['lag_mode'] = 'lacp_active' # this should not set in 4.1.2
                # link_spec['group_label'] = lag_group[old_aggregate_link_id] # this should not exist in 4.1.2
            generic_system_spec['links'].append(link_spec)
        new_system = {
            'system_type': 'server',
            'label': generic_system_label,
            # 'hostname': None, # hostname should not have '_' in it
            'port_channel_id_min': 0,
            'port_channel_id_max': 0,
            'logical_device': {
                'display_name': f"auto-{link_data['speed']}x{len(gs_data)}",
                'id': f"auto-{link_data['speed']}x{len(gs_data)}",
                'panels': [
                    {
                        'panel_layout': {
                            'row_count': 1,
                            'column_count': len(gs_data),
                        },
                        'port_indexing': {
                            'order': 'T-B, L-R',
                            'start_index': 1,
                            'schema': 'absolute'
                        },
                        'port_groups': [
                            {
                                'count': len(gs_data),
                                'speed': {
                                    'unit': link_data['speed'][-1:],
                                    'value': int(link_data['speed'][:-1])
                                },
                                'roles': [
                                    'leaf',
                                    'access'
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        generic_system_spec['new_systems'].append(new_system)
        ethernet_interfaces = [f"{main_bp.get_system_label(x['switch']['system_id'])}:{x['switch']['if_name']}" for x in generic_system_spec['links']]
        logging.info(f"adding {current_generic_system_count}/{total_generic_system_count} {generic_system_label} with {ethernet_interfaces} {len(lag_group)} LAG in the blueprint {main_bp.label}")
        generic_system_created = main_bp.add_generic_system(generic_system_spec)
        logging.debug(f"generic_system_created: {generic_system_created}")

        # update the lag mode
        """
        lag_spec example:
            "links": {
                "atl1tor-r5r14a<->_atl_rack_1_001_sys072(link-000000001)[1]": {
                    "group_label": "link1",
                    "lag_mode": "lacp_active"
                },
                "atl1tor-r5r14b<->_atl_rack_1_001_sys072(link-000000002)[1]": {
                    "group_label": "link1",
                    "lag_mode": "lacp_active"
                }
            }            
        """
        lag_spec = {
            'links': {}
        }

        for i in range(len(link_list)):
        # for _, link_data in generic_system_data.items():
            link_data = link_list[i]
            if 'aggregate_link' in link_data and link_data['aggregate_link']:
                lag_spec['links'][generic_system_created[i]] = {
                    'group_label': link_data['aggregate_link'],
                    'lag_mode': 'lacp_active' }

            # tag the link
            if len(link_data['tags']):
                tagged = main_bp.post_tagging([generic_system_created[i]], tags_to_add=link_data['tags'])
                logging.debug(f"{tagged=}")

        if len(lag_spec['links']):
            lag_updated = main_bp.patch_leaf_server_link_labels(lag_spec)
            logging.debug(f"lag_updated: {lag_updated}")



        current_generic_system_count += 1


@click.command(name='move-generic-systems', help='step 2 - create the generic systems under new access switches')
def click_move_generic_systems():
    order = ConsolidationOrder()
    order_move_generic_systems(order)

def order_move_generic_systems(order):
    logging.info(f"======== Moving Generic Systems for {order.switch_label_pair} from {order.tor_bp.label} to {order.main_bp.label}")

    ########
    # create new generic systems
    tor_generic_systems_data = pull_generic_system_off_switch(order.tor_bp, order.switch_label_pair)

    # rename the generic system label
    access_switch_generic_systems_data = {order.rename_generic_system(old_label): data for old_label, data in tor_generic_systems_data.items()}

    new_generic_systems(order, access_switch_generic_systems_data)


if __name__ == '__main__':
    order = ConsolidationOrder()
    order_move_generic_systems(order)


