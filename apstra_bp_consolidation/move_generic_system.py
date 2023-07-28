#!/usr/bin/env python3

import json

from apstra_session import CkApstraSession
from apstra_blueprint import CkApstraBlueprint


def pull_generic_system_off_switch(the_bp, switch_label_pair: list) -> dict:
    """
    Pull the generic system off switch from the blueprint.

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
    print(f"==== Pulling generic system connected to {switch_label_pair=} of blueprint {the_bp.label} ====")
    generic_systems_data = {}
    # generic systems data with member interfaces on both sides.
    generic_systems_query = f"""
        node('system', role='generic', name='generic')
            .out().node('interface', name='gs_intf')
            .out().node('link', name='link')
            .in_().node(name='sw_intf')
            .in_().node('system', label=is_in({switch_label_pair}), name='switch')
            .where(lambda gs_intf, sw_intf: gs_intf != sw_intf)
    """
    # generic_systems = the_bp.query(f"node('system', role='generic', name='generic').out().node('interface', name='gs_intf').out().node('link', name='link').in_().node(name='sw_intf').in_().node('system', label=is_in({switch_label_pair}), name='switch').where(lambda gs_intf, sw_intf: gs_intf != sw_intf)")
    generic_systems = the_bp.query(generic_systems_query, multiline=True)
    # aggregate links to associate them to the member interfaces
    aggregate_links_query = f"""
        match(node('link', link_type='aggregate_link', name='aggregate_link')
            .in_().node().out().node(name='member_interface')
            .out().node('link', name='member_link')
            .in_().node().in_().node('system', label=is_in({switch_label_pair})),node(name='aggregate_link')
            .in_().node('interface').in_().node('system', name='system'))
    """
    # aggregate_links = the_bp.query(f"match(node('link', link_type='aggregate_link', name='aggregate_link').in_().node().out().node(name='member_interface').out().node('link', name='member_link').in_().node().in_().node('system', label=is_in({switch_label_pair})),node(name='aggregate_link').in_().node('interface').in_().node('system', name='system'))")
    aggregate_links = the_bp.query(aggregate_links_query, multiline=True)
    for gs in generic_systems:
        # TODO: generalize upglinks processing
        # most QFX5120 has port 48 and 49 as uplinks
        if gs['sw_intf']['if_name'] in ["et-0/0/48", "et-0/0/49"]:
            # those are uplinks
            continue
        generic_system_label = gs['generic']['label']
        link_id = gs['link']['id']
        # create entry for this generic system if it doesn't exist
        if generic_system_label not in generic_systems_data.keys():
            generic_systems_data[generic_system_label] = {}
        this_data = {'tags': []}
        this_data['sw_label'] = gs['switch']['label']
        this_data['sw_if_name'] = gs['sw_intf']['if_name']
        this_data['speed'] = gs['link']['speed']
        # register this data as the link id
        generic_systems_data[generic_system_label][link_id] = this_data
        # pretty_yaml(generic_systems_data, "generic_systems_data")
    # update the aggregate link id on the associated member links
    for al in aggregate_links:
        if al['system']['label'] not in generic_systems_data.keys():
            # those may be uplinks
            continue
        generic_systems_data[al['system']['label']][al['member_link']['id']]['aggregate_link'] = al['aggregate_link']['id']
    # retrieve the tags information
    # link_tags = the_bp.query("node('system', role='generic', name='generic_system').out().node('interface').out().node('link', link_type='ethernet', name='link').in_().node('tag', name='tag')")
    link_tags_query = f"""
        match(node('tag', name='tag')
            .out().node('link', name='member_link')
            .in_().node('interface')
            .in_().node('system', label=is_in({switch_label_pair}), name='switch'), 
            node('system', role='generic', name='generic_system')
                .out().node('interface')
                .out().node('link', name='member_link'))
    """
    link_tags = the_bp.query(link_tags_query, multiline=True)
    for tag in link_tags:
        generic_system_label = tag['generic_system']['label']
        member_link_id = tag['member_link']['id']
        tag_value = tag['tag']['label']
        if tag['generic_system']['label'] not in generic_systems_data.keys():
            # this shouldn't happen
            continue
        generic_systems_data[generic_system_label][member_link_id]['tags'].append(tag_value)
    # print(f"==== generic systems pulled: {len(generic_systems_data)}, {generic_systems_data=}")
    print(f"====== generic systems pulled from {the_bp.label}: {len(generic_systems_data)}")
    # generic_system_label.link.dict
    return generic_systems_data

# generic system data: generic_system_label.link.dict
def new_generic_systems(main_bp, generic_system_data:dict) -> dict:
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
    print(f"==== new_generic_systems() Creating new generic systems in {main_bp.label}: {len(generic_system_data)} ====")
    system_id_cache = {}

    for generic_system_label, generic_system_data in generic_system_data.items():
        if main_bp.get_system_id(generic_system_label):
            # this generic system already exists
            print(f"     = new_generic_systems() skipping: {generic_system_label} already exists in the main blueprint")
            continue
        lag_group = {}
        generic_system_spec = {
            'links': [],
            'new_systems': [],
        }
        for _, link_data in generic_system_data.items():
            link_spec = {
                'lag_mode': None,
                'system': {
                    'system_id': None
                },
                'switch': {
                    'system_id': main_bp.get_system_id(link_data['sw_label']),
                    'transformation_id': main_bp.get_transformation_id(link_data['sw_label'], link_data['sw_if_name'] , link_data['speed']),
                    'if_name': link_data['sw_if_name'],
                }                
            }
            if 'aggregate_link' in link_data:
                old_aggregate_link_id = link_data['aggregate_link']
                if old_aggregate_link_id not in lag_group:
                    lag_group[old_aggregate_link_id] = f"link{len(lag_group)+1}"
                link_spec['lag_mode'] = 'lacp_active'
                link_spec['group_label'] = lag_group[old_aggregate_link_id]
            generic_system_spec['links'].append(link_spec)
        new_system = {
            'system_type': 'server',
            'label': generic_system_label,
            'hostname': None, # hostname should not have '_' in it
            'port_channel_id_min': 0,
            'port_channel_id_max': 0,
            'logical_device': {
                'display_name': f"auto-{link_data['speed']}x{len(generic_system_data)}",
                'id': f"auto-{link_data['speed']}x{len(generic_system_data)}",
                'panels': [
                    {
                        'panel_layout': {
                            'row_count': 1,
                            'column_count': len(generic_system_data),
                        },
                        'port_indexing': {
                            'order': 'T-B, L-R',
                            'start_index': 1,
                            'schema': 'absolute'
                        },
                        'port_groups': [
                            {
                                'count': len(generic_system_data),
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
        # pretty_yaml(generic_system_spec, generic_system_label)
        ethernet_interfaces = [f"{main_bp.get_system_label(x['switch']['system_id'])}:{x['switch']['if_name']}" for x in generic_system_spec['links']]
        print(f"     = new_generic_systems() adding {generic_system_label} with {ethernet_interfaces} {len(lag_group)} LAG in the blueprint {main_bp.label}")
        main_bp.add_generic_system(generic_system_spec)

# generic system data: generic_system_label.link.dict
def update_generic_systems_lag(main_bp, switch_label_pair, tor_generic_systems_data):
    """
    Update LAG mode for the new generic systems
        <generic_system_label>:
            <link_id>:
                gs_if_name: None
                sw_if_name: xe-0/0/15
                sw_label: atl1tor-r5r14a
                speed: 10G
                aggregate_link: <aggregate_link_id>
                tags: []
                tagged_vlan: []
                untagged_vlan: 

    """
    # pull the generic systems from the main blueprint
    print(f"== Updating LAG mode for the new generic systems in {main_bp.label} for {len(tor_generic_systems_data)} systems ====")
    main_generic_system_data = pull_generic_system_off_switch(main_bp, switch_label_pair)

    for tor_generic_label, tor_generic_data in tor_generic_systems_data.items():
        lag_data = {}
        lag_number = 1 # to create unique group_label per generic system
        # group the links by the aggregate link
        for _, link_data in tor_generic_data.items():
            if 'aggregate_link' in link_data:
                old_aggregate_link_id = link_data['aggregate_link']
                if old_aggregate_link_id not in lag_data:
                    lag_data[old_aggregate_link_id] = []
                lag_data[old_aggregate_link_id].append(link_data)
        # print(f"====== update_generic_systems_lag() lag_data created: {tor_generic_label} {lag_data=}")
        # make lags under the generic system
        for old_lag_id in lag_data.keys():
            old_lag_data = lag_data[old_lag_id]
            # print(f"====== update_generic_systems_lag() prep lag_spec: {tor_generic_label} {old_lag_id=} {old_lag_data=}")
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
            for old_link_data in old_lag_data:
                link_query = f"""
                    node('system', label='{tor_generic_label}')
                        .out().node('interface')
                        .out().node('link', name='link')
                        .in_().node('interface', if_name='{old_link_data['sw_if_name']}')
                        .in_().node('system', label='{old_link_data['sw_label']}')
                """
                # print_prefix='link_query for lag'
                print_prefix=None
                link_data = main_bp.query(link_query, print_prefix=print_prefix, split=True)
                if len(link_data) != 1:
                    print(f"     = update_generic_systems_lag() Wrong link_data for query: {link_query=}")
                # skip if the link is already in the correct group_label
                if link_data[0]['link']['group_label'] == f"link{lag_number}":
                    print(f"     = update_generic_systems_lag() link already in the correct LAG mode: {link_data[0]['link']['group_label']}")
                    continue
                link_id = link_data[0]['link']['id']
                lag_spec['links'][link_id] = { 'group_label': f"link{lag_number}", 'lag_mode': 'lacp_active' }
            
            # print_prefix='lag_updating'
            print_prefix=None
            # update the lag if there are links to update
            if len(lag_spec['links']):
                link_members = [ f"{x['sw_label']}:{x['sw_if_name']}" for x in old_lag_data]
                print(f"     = update_generic_systems_lag() updating lag: {tor_generic_label} with {link_members}")
                lag_updated = main_bp.patch_leaf_server_link_labels(lag_spec, print_prefix=print_prefix)
                lag_number += 1


    # for generec_system_label, generic_system in generic_systems_data.items():
    #     lag_data = {} # group_label: [ links ]        
    #     for link_label, link_data in { k: v for k, v in generic_system.items() if 'aggregate_link' in v }.items():
    #         lag_data[link_data['aggregate_link']] = link_label
    pass


def update_generic_systems_link_tag(main_bp, tor_generic_systems_data):
    """
    Update tagging on the links towards the new generic systems
        <generic_system_label>:
            <link_id>:
                gs_if_name: None
                sw_if_name: xe-0/0/15
                sw_label: atl1tor-r5r14a
                speed: 10G
                aggregate_link: <aggregate_link_id>
                tags: []
                tagged_vlan: []
                untagged_vlan: 

    """
    print(f"== update_generic_systems_link_tag() Updating tagging for the new generic systems")
    for generic_system_label, generic_system_data in tor_generic_systems_data.items():
        for _, old_link_data in generic_system_data.items():
            if len(old_link_data['tags']) == 0:
                # no tag to update
                continue
            # the tag can be 'forceup'
            tags = old_link_data['tags']
            print(f"     = update_generic_systems_link_tag() updating tag:  {tags=} on the link of {old_link_data['sw_label']}:{old_link_data['sw_if_name']}")
            link_query = f"""
                node('system', label='{generic_system_label}')
                    .out().node('interface')
                    .out().node('link', name='link')
                    .in_().node('interface', if_name='{old_link_data['sw_if_name']}')
                    .in_().node('system', label='{old_link_data['sw_label']}')
            """
            target_link_result = main_bp.query(link_query, multiline=True)
            # print_prefix='link_query for tag'
            print_prefix=None
            tagged = main_bp.post_tagging([x['link']['id'] for x in target_link_result], tags_to_add=tags, print_prefix=print_prefix)





def main(yaml_in_file):
    from consolidation import ConsolidationOrder
    order = ConsolidationOrder(yaml_in_file)

    ########
    # create new generic systems
    # generic system data: generic_system_label.link.dict
    # TODO: make unique for the generic system label
    generic_systems_data = pull_generic_system_off_switch(order.tor_bp, order.switch_label_pair)

    print(f"=== main: get generic_systems_data. {len(generic_systems_data)=}")

    new_generic_systems(order.main_bp, generic_systems_data)

    # implemented in new_generic_systems
    # update_generic_systems_lag(main_bp, switch_label_pair, generic_systems_data)

    update_generic_systems_link_tag(order.main_bp, generic_systems_data)


if __name__ == '__main__':
    main('./tests/fixtures/config.yaml')    

