#!/usr/bin/env python3

import logging
# from typing import List, Optional
# from pydantic import BaseModel

from consolidation import ConsolidationOrder
from consolidation import prep_logging
from consolidation import pretty_yaml

from apstra_blueprint import CkEnum


def pull_single_vlan_cts(the_bp, switch_label_pair: list) -> dict:
    """
    Pull the single vlan cts for the switch pair

    The return data
    <system_label>:
        <if_name>:
            id: None
            tagged_vlans: []
            untagged_vlan: None
    redundacy_group:
        <ae_id>:
            tagged_vlans: []
            untagged_vlan: None
            member_interfaces:
                <system_label>: [ <member if_name> ]   
    """
    ct_table = {
        # atl1tor-r5r14a:
        #     xe-0/0/0:
        #         id: <interface id>
        #         tagged_vlans: []
        #         untagged_vlan: None
        CkEnum.REDUNDANCY_GROUP: {
            # <ae_id>:
            #     tagged_vlans: []
            #     untagged_vlan: None
            #     member_interfaces:
            #         <system_label>: [ <member if_name> ]             
        }

    }

    # interfaces with massive VLANS may time out. AE interfaces need to process one by one
    switch_interface_nodes = the_bp.get_switch_interface_nodes(switch_label_pair)

    logging.debug(f"BP:{the_bp.label} {len(switch_interface_nodes)=}")

    # build non AE interface entries first
    for nodes_data in [x for x in switch_interface_nodes if not x[CkEnum.EVPN_INTERFACE]]:
        system_label = nodes_data[CkEnum.MEMBER_SWITCH]['label']
        member_if_name = nodes_data[CkEnum.MEMBER_INTERFACE]['if_name']
        member_if_id = nodes_data[CkEnum.MEMBER_INTERFACE]['id']
        if system_label not in ct_table:
            ct_table[system_label] = {}
        the_member_data = ct_table[system_label]
        the_member_data[member_if_name] = {
                'id': member_if_id,
                CkEnum.TAGGED_VLANS: [],
                CkEnum.UNTAGGED_VLAN: None,
            }                

    # pretty_yaml(ct_table, "member ct_table")

    # build AE interface entries then
    for nodes_data in [x for x in switch_interface_nodes if x[CkEnum.EVPN_INTERFACE]]:
        evpn_interface = nodes_data[CkEnum.EVPN_INTERFACE]
        evpn_id = evpn_interface['id']
        system_label = nodes_data[CkEnum.MEMBER_SWITCH]['label']
        member_if_name = nodes_data[CkEnum.MEMBER_INTERFACE]['if_name']
        # skip et-0/0/48 and et-0/0/49 which will be taken care of by Apstra
        if member_if_name in ['et-0/0/48', 'et-0/0/49']:
            continue
        if evpn_id not in ct_table[CkEnum.REDUNDANCY_GROUP]:
            ct_table[CkEnum.REDUNDANCY_GROUP][evpn_id] = {
                CkEnum.TAGGED_VLANS: [],
                CkEnum.UNTAGGED_VLAN: None,
                CkEnum.MEMBER_INTERFACE: {}
            }
        the_evpn_data = ct_table[CkEnum.REDUNDANCY_GROUP][evpn_id]
        if system_label not in the_evpn_data[CkEnum.MEMBER_INTERFACE]:
            the_evpn_data[CkEnum.MEMBER_INTERFACE][system_label] = []
        the_evpn_data[CkEnum.MEMBER_INTERFACE][system_label].append(member_if_name)
        if member_if_name in ct_table[system_label]:
            logging.warning(f"BP:{the_bp.label} {system_label=}, {member_if_name=} already exists in {ct_table[system_label][member_if_name]}")

    # pretty_yaml(ct_table, "ct_table")
    summary = [f"{x}:{len(ct_table[x])}" for x in ct_table.keys()]
    logging.debug(f"BP:{the_bp.label} {summary=}")


        # switch_node = nodes_data['switch']
        # member_switch_node = nodes_data[CkEnum.MEMBER_SWITCH]
        # # if not switch_node or member_switch_node:
        # #     # does not associate interface 
        # #     continue
        # # logging.debug(f"BP:{the_bp.label} {switch_node=}, {member_switch_node=}")
        # # non ae interface
        # if switch_node:
        #     if switch_node['label'] not in ct_table:
        #         ct_table[switch_node['label']] = {}
        #     if_name = nodes_data['interface']['if_name']
        #     if if_name not in ct_table[switch_node['label']]:
        #         ct_table[switch_node['label']][if_name] = {
        #             CkEnum.TAGGED_VLANS: [],
        #             CkEnum.UNTAGGED_VLAN: None
        #         }
        #     vlan_id = nodes_data['vn_instance']['vlan_id']
        #     if CkEnum.UNTAGGED_VLAN in nodes_data['AttachSingleVLAN']['attributes']:
        #         ct_table[switch_node['label']][if_name][CkEnum.UNTAGGED_VLAN] = vlan_id
        #     elif vlan_id not in ct_table[switch_node['label']][if_name][CkEnum.TAGGED_VLANS]:
        #         ct_table[switch_node['label']][if_name][CkEnum.TAGGED_VLANS].append(vlan_id)
        # # ae (evpn) interface
        # if member_switch_node:
        #     ae_id = nodes_data['evpn']['id']
        #     if ae_id not in ct_table[CkEnum.REDUNDANCY_GROUP]:
        #         ct_table[CkEnum.REDUNDANCY_GROUP][ae_id] = {
        #             CkEnum.TAGGED_VLANS: [],
        #             CkEnum.UNTAGGED_VLAN: None,
        #             'member_interfaces': {}
        #         }
        #     member_switch_label = nodes_data['member-switch']['label']
        #     member_if_name = nodes_data['member-interface']['if_name']
        #     if member_switch_label not in ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACES]:
        #         ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACES][member_switch_label] = [ member_if_name ]
        #     elif member_if_name not in ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACES][member_switch_label]:
        #         ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACES][member_switch_label].append(member_if_name)
        #     # logging.debug(f"BP:{the_bp.label} {ae_id=}, ae={nodes_data['evpn']['if_name']}, {member_switch_label=}, {member_if_name=}")

        #     vlan_id = nodes_data['vn_instance']['vlan_id']
        #     if 'untagged' in nodes_data['AttachSingleVLAN']['attributes']:
        #         ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.UNTAGGED_VLAN] = vlan_id
        #     elif vlan_id not in ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.TAGGED_VLANS]:
        #         ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.TAGGED_VLANS].append(vlan_id)

    return ct_table

# def diff_single_vlan_cts(tor_cts, main_cts, switch_interface_nodes):
#     """
#     Compare to produce the connectivity templates to work on
#     """
#     work_cts = {
#         'redundancy_group': {}
#     }

#     for system_label in tor_cts.keys():
#         # treat AE first
#         if system_label == CkEnum.REDUNDANCY_GROUP:
#             # build main_cts member_interface_to_ae
#             member_interface_to_ae = {}  # <system_label>: { <interface_name>: <ae_id> }

#     # redundacy_group:
#     #     <ae_id>:
#     #         tagged_vlans: []
#     #         untagged_vlan: None
#     #         member_interfaces:
#     #             <system_label>: [ <member if_name> ]   

#             for ae_id, ae_data in main_cts[CkEnum.REDUNDANCY_GROUP].items():
#                 for member_system_label, member_if_list in ae_data[CkEnum.MEMBER_INTERFACES].items():
#                     for member_if_name in member_if_list:
#                         if member_system_label not in member_interface_to_ae:
#                             member_interface_to_ae[member_system_label] = {}
#                         if member_if_name not in main_cts[member_system_label]:
#                             main_cts[member_system_label][member_if_name] = ae_id

#             pretty_yaml(member_interface_to_ae, "member_interface_to_ae")    

#             for ae_id, ae_data in tor_cts[CkEnum.REDUNDANCY_GROUP].items():
#                 pass

#         # non AE
#         logging.debug(f"diffing {system_label=}, {tor_cts[system_label]=}")
#         if system_label not in main_cts:
#             # nothing on main_cts, so copy over 
#             main_cts[system_label] = tor_cts[system_label]
#         else:
#             main_cts[system_label][UNTAGGED_VLAN] = tor_cts[system_label][UNTAGGED_VLAN]
#             main_cts[system_label][TAGGED_VLANS] = [x for x in tor_cts[system_label][TAGGED_VLANS] if x not in main_cts[system_label][TAGGED_VLANS]]    



def associate_missing_cts(the_bp, tor_ct, main_ct: list):
    logging.debug(f"associating missing cts, {len(tor_ct[REDUNDANCY_GROUP])=}, {len(main_ct[REDUNDANCY_GROUP])=}")
    for system_label, system_data in tor_ct.items():
        if system_label not in main_ct:
            # no CT on main_ct
            logging.debug(f"BP {the_bp.label} had no CT on {system_label}")
            main_ct[system_label] = {}
            #     'tagged_vlans': [],
            #     'untagged_vlan': None
            # }
        for if_name, if_data in system_data.items():
            # lag interface
            if system_label == REDUNDANCY_GROUP:
                pass
            # non-lag interface
            else:
                if if_name not in main_ct[system_label]:
                    logging.debug(f"adding: {system_label=}, {if_name=}")
                    main_ct[system_label][if_name] = {
                        TAGGED_VLANS: [],
                        UNTAGGED_VLAN: None
                    }
                tagged_vlans = [x for x in if_data[TAGGED_VLANS] if x not in main_ct[system_label][if_name][TAGGED_VLANS]]
                untagged_vlan = if_data[UNTAGGED_VLAN]
                if untagged_vlan or len(tagged_vlans):
                    logging.debug(f"{system_label=}, {if_name=}, {tagged_vlans=}, {untagged_vlan=}")
                    application_point = the_bp.query(f"node('system', label='{system_label}').out().node('interface', if_name='{if_name}', name='interface')")[0]['interface']['id']
                    (_, untagged_id) = the_bp.get_single_vlan_ct_id(100000+untagged_vlan)
                    attach_spec = {
                        'application_points': [{
                            'id': application_point,
                            'policies': [{
                                'policy': untagged_id,
                                'used': True
                            }]
                        }]
                    }
                    logging.debug(f"{attach_spec=}")
                    the_bp.patch_obj_policy_batch_apply(attach_spec, params={'aync': 'full'})


def main(order):

    ########
    # pull CT assignment data

    # q1
    # f"node('ep_endpoint_policy', name='ep', label='{ct_label}').out('ep_subpolicy').node().out('ep_first_subpolicy').node(name='n2')"
    # vn_endpoint_query = f"node('system', label='{system_label}').out('hosted_vn_instances').node('vn_instance').out('instantiates').node('virtual_network', label='{vn_label}').out('member_endpoints').node('vn_endpoint', name='vn_endpoint')"
    # get_ae_or_interface_id(ct_dict['system'], ct_dict['interface'])
    # node('virtual_network', name='virtual_network').out().node('vn_endpoint', name='vn_endpoint').in_().node('interface', name='interface').in_().node('system', name='system')

    tor_cts = pull_single_vlan_cts(order.tor_bp, order.switch_label_pair)
    # pretty_yaml(tor_cts, "tor_cts")
    return

    main_cts = pull_single_vlan_cts(order.main_bp, order.switch_label_pair)
    # pretty_yaml(main_cts, "main_cts")

    switch_interface_nodes = order.main_bp.get_switch_interface_nodes(order.switch_label_pair)

    work_cts = diff_single_vlan_cts(tor_cts, main_cts, switch_interface_nodes)

    # associate_missing_cts(order.main_bp, tor_cts, main_cts)


if __name__ == '__main__':
    yaml_in_file = './tests/fixtures/config.yaml'
    log_level = logging.DEBUG
    prep_logging(log_level)
    order = ConsolidationOrder(yaml_in_file)
    main(order)
