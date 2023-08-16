#!/usr/bin/env python3

import logging
from typing import Any
# from typing import List, Optional
from pydantic import BaseModel

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

    ct_query = f"""
        match(
            node('ep_endpoint_policy', policy_type_name='batch', name='batch')
                .in_().node('ep_application_instance', name='ep_application_instance')
                .out('ep_affected_by').node('ep_group')
                .in_('ep_member_of').node(name='interface'),
            node(name='ep_application_instance')
                .out('ep_nested').node('ep_endpoint_policy', policy_type_name='AttachSingleVLAN', name='AttachSingleVLAN')
                .out('vn_to_attach').node('virtual_network', name='virtual_network'),
            optional(
                node(name='interface')
                .out('composed_of').node('interface')
                .out('composed_of').node('interface', name='{CkEnum.MEMBER_INTERFACE}')
                .in_('hosted_interfaces').node('system', label=is_in({switch_label_pair}), name='{CkEnum.MEMBER_SWITCH}' )
                ),
            optional(
                node(name='interface')
                .in_('hosted_interfaces').node('system', label=is_in({switch_label_pair}), name='switch')
                )            
        )
    """

    ct_nodes = the_bp.query(ct_query, multiline=True)
    logging.debug(f"BP:{the_bp.label} {len(ct_nodes)=}")
    # why so many (3172) entries?

    for nodes in ct_nodes:
        if nodes[CkEnum.MEMBER_INTERFACE]:
            # AE interface
            ae_id = nodes['interface']['id']
            system_label = nodes[CkEnum.MEMBER_SWITCH]['label']
            if_name = nodes[CkEnum.MEMBER_INTERFACE]['if_name']
            if if_name in ['et-0/0/48', 'et-0/0/49']:
                # skip et-0/0/48 and et-0/0/49 which will be taken care of by Apstra
                continue
            vlan_id = int(nodes['virtual_network']['vn_id'] )- 100000
            is_tagged = 'vlan_tagged' in nodes['AttachSingleVLAN']['attributes']
            if ae_id not in ct_table[CkEnum.REDUNDANCY_GROUP]:
                ct_table[CkEnum.REDUNDANCY_GROUP][ae_id] = {
                    CkEnum.TAGGED_VLANS: [],
                    CkEnum.UNTAGGED_VLAN: None,
                    CkEnum.MEMBER_INTERFACE: {}
                }
            if system_label not in ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACE]:
                ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACE][system_label] = []
            if if_name not in ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACE][system_label]:
                ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.MEMBER_INTERFACE][system_label].append(if_name)
            if is_tagged:
                ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.TAGGED_VLANS].append(vlan_id)
            else:
                ct_table[CkEnum.REDUNDANCY_GROUP][ae_id][CkEnum.UNTAGGED_VLAN] = vlan_id
        else:
            system_label = nodes['switch']['label']
            if_name = nodes['interface']['if_name']
            vlan_id = int(nodes['virtual_network']['vn_id'] )- 100000
            is_tagged = 'vlan_tagged' in nodes['AttachSingleVLAN']['attributes']
            if system_label not in ct_table:
                ct_table[system_label] = {}
            if if_name not in ct_table[system_label]:
                ct_table[system_label][if_name] = {
                    'id': nodes['interface']['id'],
                    CkEnum.TAGGED_VLANS: [],
                    CkEnum.UNTAGGED_VLAN: None,
                }
            if is_tagged:
                ct_table[system_label][if_name][CkEnum.TAGGED_VLANS].append(vlan_id)
            else:
                ct_table[system_label][if_name][CkEnum.UNTAGGED_VLAN] = vlan_id

    summary = [f"{x}:{len(ct_table[x])}" for x in ct_table.keys()]
    logging.debug(f"BP:{the_bp.label} {summary=}")

    return ct_table


class VniCt:
    vni: int = None
    tagged_id: str = None
    untagged_id: str = None

    def __init__(self, vni: int = None):
        self.vni = vni
        self.tagged_id = None
        self.untagged_id = None
        self.logger = logging.getLogger(f"VniCT({self.vni})")

    def set_id(self, ct_id: str, is_tagged: bool):
        if is_tagged:
            self.tagged_id = ct_id
        else:
            self.untagged_id = ct_id
    
    def get_id(self, is_tagged: bool):
        if is_tagged:
            return self.tagged_id
        else:
            if self.untagged_id is None:
                self.logger.warning(f"untagged_id is None")
            return self.untagged_id
    

def associate_cts(the_bp, ct_table, switch_label_pair: list):
    """
    """
    # switch_interface_nodes = the_bp.get_switch_interface_nodes(switch_label_pair)
    vlan_2_ct_table = {}  # VniCt
    interface_2_ct_id_table = {}  # to prep spec for assign: {<interface_id>: [ <ct_id> ]}


    # build vlan_2_ct_table
    vlan_table_query = f"""
        node('ep_endpoint_policy', policy_type_name='batch', name='batch')
            .in_('ep_top_level').node('ep_application_instance')
            .out('ep_nested').node('ep_endpoint_policy',policy_type_name='AttachSingleVLAN',name='AttachSingleVLAN')
            .out('vn_to_attach').node('virtual_network', name='virtual_network')
    """
    vlan_table_nodes = the_bp.query(vlan_table_query, multiline=True)
    for node in vlan_table_nodes:
        vni = int(node['virtual_network']['vn_id'])
        vlan_id = vni - 100000
        ct_id = node['batch']['id']
        is_tagged = 'vlan_tagged' in node['AttachSingleVLAN']['attributes']
        if vni not in vlan_2_ct_table:
            vlan_2_ct_table[vlan_id] = VniCt(vni)
        vlan_2_ct_table[vlan_id].set_id(ct_id, is_tagged)
    # pretty_yaml(vlan_2_ct_table, "vlan_2_ct_table")
    return

    for system_label, system_data in ct_table.items():
        # process AE interfaces first
        if system_label == CkEnum.REDUNDANCY_GROUP:
            for _, ae_data in system_data.items():
                # find the evpn interface ID from the member switch interface
                member_switch_label = list(ae_data[CkEnum.MEMBER_INTERFACE].keys())[0]
                member_switch_if_name = ae_data[CkEnum.MEMBER_INTERFACE][member_switch_label][0]
                ae_id = [x['id'] for x in switch_interface_nodes if x[CkEnum.EVPN_INTERFACE] and x[CkEnum.GENERIC_SYSTEM]['label'] == member_switch_label and x[CkEnum.MEMBER_INTERFACE]['if_name'] == member_switch_if_name][0]                








    # logging.debug(f"associating cts, {len(tor_ct[REDUNDANCY_GROUP])=}, {len(main_ct[REDUNDANCY_GROUP])=}")
    # for system_label, system_data in tor_ct.items():
    #     if system_label not in main_ct:
    #         # no CT on main_ct
    #         logging.debug(f"BP {the_bp.label} had no CT on {system_label}")
    #         main_ct[system_label] = {}
    #         #     'tagged_vlans': [],
    #         #     'untagged_vlan': None
    #         # }
    #     for if_name, if_data in system_data.items():
    #         # lag interface
    #         if system_label == REDUNDANCY_GROUP:
    #             pass
    #         # non-lag interface
    #         else:
    #             if if_name not in main_ct[system_label]:
    #                 logging.debug(f"adding: {system_label=}, {if_name=}")
    #                 main_ct[system_label][if_name] = {
    #                     TAGGED_VLANS: [],
    #                     UNTAGGED_VLAN: None
    #                 }
    #             tagged_vlans = [x for x in if_data[TAGGED_VLANS] if x not in main_ct[system_label][if_name][TAGGED_VLANS]]
    #             untagged_vlan = if_data[UNTAGGED_VLAN]
    #             if untagged_vlan or len(tagged_vlans):
    #                 logging.debug(f"{system_label=}, {if_name=}, {tagged_vlans=}, {untagged_vlan=}")
    #                 application_point = the_bp.query(f"node('system', label='{system_label}').out().node('interface', if_name='{if_name}', name='interface')")[0]['interface']['id']
    #                 (_, untagged_id) = the_bp.get_single_vlan_ct_id(100000+untagged_vlan)
    #                 attach_spec = {
    #                     'application_points': [{
    #                         'id': application_point,
    #                         'policies': [{
    #                             'policy': untagged_id,
    #                             'used': True
    #                         }]
    #                     }]
    #                 }
    #                 logging.debug(f"{attach_spec=}")
    #                 the_bp.patch_obj_policy_batch_apply(attach_spec, params={'aync': 'full'})


def main(order):

    ########
    # pull CT assignment data

    # q1
    # f"node('ep_endpoint_policy', name='ep', label='{ct_label}').out('ep_subpolicy').node().out('ep_first_subpolicy').node(name='n2')"
    # vn_endpoint_query = f"node('system', label='{system_label}').out('hosted_vn_instances').node('vn_instance').out('instantiates').node('virtual_network', label='{vn_label}').out('member_endpoints').node('vn_endpoint', name='vn_endpoint')"
    # get_ae_or_interface_id(ct_dict['system'], ct_dict['interface'])
    # node('virtual_network', name='virtual_network').out().node('vn_endpoint', name='vn_endpoint').in_().node('interface', name='interface').in_().node('system', name='system')

    tor_cts = pull_single_vlan_cts(order.tor_bp, order.switch_label_pair)
    pretty_yaml(tor_cts, "tor_cts")

    # main_cts = pull_single_vlan_cts(order.main_bp, order.switch_label_pair)
    # pretty_yaml(main_cts, "main_cts")

    # switch_interface_nodes = order.main_bp.get_switch_interface_nodes(order.switch_label_pair)

    # work_cts = diff_single_vlan_cts(tor_cts, main_cts, switch_interface_nodes)

    associate_cts(order.main_bp, tor_cts, order.switch_label_pair)


if __name__ == '__main__':
    yaml_in_file = './tests/fixtures/config.yaml'
    log_level = logging.DEBUG
    prep_logging(log_level)
    order = ConsolidationOrder(yaml_in_file)
    main(order)
