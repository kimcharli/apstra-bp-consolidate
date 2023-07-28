#!/usr/bin/env python3

import json

from apstra_session import CkApstraSession
from apstra_blueprint import CkApstraBlueprint




def pull_vni_ids(the_bp, switch_label_pair: list) -> list:
    """
    Pull the vni ids for the switch pair

    """
    print(f"== pull_vni_ids() pulling vni ids for {switch_label_pair=}")
    vn_list_query = f"""
        match(
            node('system', label=is_in({switch_label_pair}))
            .out().node('vn_instance')
            .out().node('virtual_network', name='vn')
        ).distinct(['vn'])"""
    vn_list = the_bp.query(vn_list_query)
    vni_list = [ x['vn']['vn_id'] for x in vn_list ]
    print(f"     = pull_vni_ids() found {len(vni_list)=}")
    return vni_list


def access_switch_assign_vns(the_bp, vni_list: list, switch_label_pair: list):
    """
    Assign VN to the access switch pair
    """
    print(f"== access_switch_assign_vns() assigning vni ids for {switch_label_pair=} {vni_list[0]=}")  

    for vni in vni_list:
    # for vni in vni_list[:3]:
        # deep copy vn data into vn_spec
        vn_query = f"node('virtual_network', name='vn', vn_id='{vni}').in_().node('security_zone', name='security_zone')"
        vn_nodes = the_bp.query(vn_query)
        vn_spec = vn_nodes[0]['vn'].copy()
        del vn_spec['type']
        del vn_spec['property_set']

        vn_spec['security_zone_id'] = vn_nodes[0]['security_zone']['id']
        vn_spec['vni_ids'] = [int(x) for x in vni]
        vn_spec['floating_ips'] = []
        vn_spec['route_target'] = f"{vni}:1"
        # TODO: get this
        vn_spec['dhcp_service'] = "dhcpServiceDisabled"

        #### build svi_ips data
        svi_ips = []
        # TODO: how is svi used?
        svi_query = f"""
            match(
              node('virtual_network', name='vn', vn_id='{vni}')
                .in_().node('vn_instance', name='vn_instance')
                .in_().node('system', role='leaf', name='leaf_switch')
            )
        """
        svi_nodes = the_bp.query(svi_query, multiline=True)
        for svi in svi_nodes:
            svi_ips.append({
                'ipv4_addr': None, 
                'ipv6_addr': None, 
                'system_id': svi['leaf_switch']['id'],            
                'ipv4_mode': svi['vn_instance']['ipv4_mode'],
                'ipv6_mode': svi['vn_instance']['ipv6_mode'],
             })
        vn_spec['svi_ips'] = svi_ips

        #### build bound_to data
        bound_to = []

        # TODO: only leaf?
        rg_query = f"""
            match(
                node('redundancy_group', name='redundancy_group').out().
                    node('system', name='system').out().
                    node('vn_instance', name='vn_instance').out().
                    node('virtual_network', vn_id='{vni}'),
                node(name='system').out().node('rack', name='rack'),
                node(name='system').out().node('pod', name='pod')
            )
        """
        rg_nodes = the_bp.query(rg_query, multiline=True)
        # build bound_to data - per redundancy_group
        # TODO: implement single home leaf - out of scope at the moment
        # TODO: normalization - separate data for systems
        for rg in [x for x in rg_nodes if x['system']['role'] in ["leaf"]]:
            # There are two data per redundancy_group. Need to skip the second one.
            redundancy_group_id = rg['redundancy_group']['id']
            if redundancy_group_id in [x['system_id'] for x in bound_to]:
                continue
            # boud_to is the list of leaf_pair
            leaf_pair = {
                'role': 'leaf_pair',
                'tags': [],
                'access-switches': [],
                'pod-data': {},
                'system_id': redundancy_group_id,
                'composed_of': [],
                'access_switch_node_ids': [],
                'label': rg['redundancy_group']['label'],
                'vlan_id': rg['vn_instance']['vlan_id'],
                'redundancy_group_id': None,
                'rack-data': {},
                'selected?': True,
            }

            # build pod-data of leaf_pair
            pod_data = rg['pod'].copy()
            del pod_data['property_set']
            del pod_data['pod_type_json']
            del pod_data['tags']
            pod_data['description'] = None
            pod_data['global_catalog_id'] = None
            pod_id = pod_data['id']

            leaf_pair['pod-data'] = pod_data

            # build rack-data of leaf_pair
            rack_data = rg['rack'].copy()
            del rack_data['property_set']
            del rack_data['ip_version']
            del rack_data['tags']
            del rack_data['position']
            rack_data['description'] = None

            rack_type_json = json.loads(rack_data['rack_type_json'])
            # pretty_yaml(rack_type_json, "rack_type_json")
            rack_data['global_catalog_id'] = rack_type_json['id']
            del rack_data['rack_type_json']
            rack_id = rack_data['id']

            leaf_pair['rack-data'] = rack_data

            # build composed_of for each leaf system for leaf_pair (a redundancy_group has two leaf systems)
            leaf_pair_systems = [ x['system'] for x in rg_nodes
                    if x['redundancy_group']['id'] == redundancy_group_id and x['system']['role'] in ["leaf"] ] 
            leaf_pair_system_ids = [ x['id'] for x in leaf_pair_systems ]
            for system in leaf_pair_systems:
                composed_of = {
                    'tags': None,
                    'redundancy_group_id': redundancy_group_id,
                    'label': system['label'],
                    'role': 'leaf',
                    'id': system['id'],
                    'pod-data': pod_data.copy(),
                    'rack-data': rack_data.copy()
                }

                # get tags of the switch
                tags_query = f"node(id='{system['id']}').in_().node('tag', name='tag')"
                # get the list of tag.label
                tags_nodes = the_bp.query(tags_query)
                tags_labels = [x['tag']['label'] for x in tags_nodes]
                composed_of['tags'] = tags_labels

                leaf_pair['composed_of'].append(composed_of)

                # build access-switches for the leaf_pair tracing the links of role'leaf_access'
                acess_group_query = f"""
                    node(id=is_in({leaf_pair_system_ids}), name='leaf_switch')
                        .out().node('interface')
                        .out().node('link', role='leaf_access')
                        .in_().node('interface')
                        .in_().node('system', role='access', name='access_switch')
                        .in_().node('redundancy_group', name='access_redundancy_group')
                """
                access_groups = the_bp.query(acess_group_query, multiline=True)
                # print(f"     =  access_switch_assign_vns() {len(access_groups)=}")
                if len(access_groups) == 0:
                    # no access switch
                    continue
                # iterate access groups 
                for ag in access_groups:
                    access_group_id = ag['access_redundancy_group']['id']
                    leaf_pair['access_switch_node_ids'].append(access_group_id) 
                    # there are two data per access group. Need to skip the second one.
                    # print(f"     =  access_switch_assign_vns() {access_group_id=}, {ag=}")
                    # pretty_yaml(ag, f"access_switch_assign_vns() {access_group_id=}")

                    access_switches = [x['access_switch']['id'] for x in access_groups if x['access_redundancy_group']['id'] == access_group_id]
                    if access_group_id in [x['id'] for x in leaf_pair['access-switches']]:
                        continue
                    access_switch = {
                        'id': access_group_id,
                        'role': 'access_pair',
                        'tags': [],
                        'logical-device': None,
                        'loopback': None,
                        'superspine_plane_id': None,
                        'redundancy_protocol': ag['access_redundancy_group']['rg_type'],
                        'interface-map': None,
                        'composed-of': list(set(access_switches)),
                        'pod_id': pod_id,
                        'position_data': None,
                        'device-profile': None,
                        'logical_vtep': None,
                        'external': None,
                        'pod-data': pod_data.copy(),
                        'unicast_vtep': None,
                        'system_id': None,
                        'logical_device_id': None,
                        'hostname': None,
                        'deploy_mode': None,
                        'port_channel_id_max': None,
                        'uplinked_system_ids': [x['leaf_switch']['id'] for x in access_groups if x['access_redundancy_group']['id'] == access_group_id],
                        'hidden': None,
                        'plane-data': None,
                        'device_profile_id': None,
                        'label': ag['access_redundancy_group']['label'],
                        'id': access_group_id,
                        'group_label': None,
                        'redundancy_group_id': None,
                        'rack-data': rack_data.copy(),
                        'management_level': None,
                        'rack_id': rack_id,
                        'interface_map_id': None,
                        'domain_id': None,
                        'hypervisor_id': None,
                        'href': f"#/blueprints/{the_bp.id}/nodes/{access_group_id}/staged/physical",
                        'port_channel_id_min': None,
                        'anycast_vtep': None
                    }
                    leaf_pair['access-switches'].append(access_switch)


            bound_to.append(leaf_pair.copy())

            

        vn_spec['bound_to'] = bound_to

        # TODO: params: 'svi_requirements': 'none'
        vn_patched = the_bp.patch_virtual_network(vn_spec)


        print(f"     = access_switch_assign_vns() assigning {vni=}")
        # pretty_yaml(vn_spec, f"vn_spec({vni})")

        # TODO: floating_ips: []
        # TODO: route_target: 100112:1
        # TODO: dhcp_service": "dhcpServiceDisabled"


        # break


    pass



def main(yaml_in_file):
    from consolidation import ConsolidationOrder
    order = ConsolidationOrder(yaml_in_file)

    ########
    # assign virtual networks
    vni_list = pull_vni_ids(order.tor_bp, order.switch_label_pair)

    # assign connectivity templates
    access_switch_assign_vns(order.main_bp, vni_list, order.switch_label_pair)


if __name__ == '__main__':
    main('./tests/fixtures/config.yaml')    


