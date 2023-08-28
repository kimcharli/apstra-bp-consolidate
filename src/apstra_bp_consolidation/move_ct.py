#!/usr/bin/env python3

import logging
import copy
import uuid
from typing import Any
# from typing import List, Optional
from pydantic import BaseModel

from apstra_bp_consolidation.consolidation import ConsolidationOrder

from apstra_bp_consolidation.apstra_blueprint import CkEnum


def pull_interface_vlan_table(the_bp, switch_label_pair: list) -> dict:
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
    interface_vlan_table = {
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

    INTERFACE_NODE = 'interface'
    CT_NODE = 'batch'
    SINGLE_VLAN_NODE = 'AttachSingleVLAN'
    VN_NODE = 'virtual_network'

    interface_vlan_query = f"""
        match(
            node('ep_endpoint_policy', policy_type_name='batch', name='{CT_NODE}')
                .in_().node('ep_application_instance', name='ep_application_instance')
                .out('ep_affected_by').node('ep_group')
                .in_('ep_member_of').node(name='{INTERFACE_NODE}'),
            node(name='ep_application_instance')
                .out('ep_nested').node('ep_endpoint_policy', policy_type_name='AttachSingleVLAN', name='{SINGLE_VLAN_NODE}')
                .out('vn_to_attach').node('virtual_network', name='virtual_network'),
            optional(
                node(name='{INTERFACE_NODE}')
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

    interface_vlan_nodes = the_bp.query(interface_vlan_query, multiline=True)
    logging.debug(f"BP:{the_bp.label} {len(interface_vlan_nodes)=}")
    # why so many (3172) entries?

    for nodes in interface_vlan_nodes:
        if nodes[CkEnum.MEMBER_INTERFACE]:
            # INTERFACE_NODE is EVPN
            evpn_id = nodes[INTERFACE_NODE]['id']
            system_label = nodes[CkEnum.MEMBER_SWITCH]['label']
            if_name = nodes[CkEnum.MEMBER_INTERFACE]['if_name']
            if if_name in ['et-0/0/48', 'et-0/0/49']:
                # skip et-0/0/48 and et-0/0/49 which will be taken care of by Apstra
                continue
            vlan_id = int(nodes[VN_NODE]['vn_id'] )- 100000
            is_tagged = 'vlan_tagged' in nodes[SINGLE_VLAN_NODE]['attributes']
            if evpn_id not in interface_vlan_table[CkEnum.REDUNDANCY_GROUP]:
                interface_vlan_table[CkEnum.REDUNDANCY_GROUP][evpn_id] = {
                    CkEnum.TAGGED_VLANS: [],
                    CkEnum.UNTAGGED_VLAN: None,
                    CkEnum.MEMBER_INTERFACE: {}
                }
            this_evpn_interface_data = interface_vlan_table[CkEnum.REDUNDANCY_GROUP][evpn_id]
            if system_label not in this_evpn_interface_data[CkEnum.MEMBER_INTERFACE]:
                this_evpn_interface_data[CkEnum.MEMBER_INTERFACE][system_label] = []
            if if_name not in this_evpn_interface_data[CkEnum.MEMBER_INTERFACE][system_label]:
                this_evpn_interface_data[CkEnum.MEMBER_INTERFACE][system_label].append(if_name)
            if is_tagged:
                # add vlan_id if not already in the list
                if vlan_id not in this_evpn_interface_data[CkEnum.TAGGED_VLANS]:
                    this_evpn_interface_data[CkEnum.TAGGED_VLANS].append(vlan_id)
            else:
                this_evpn_interface_data[CkEnum.UNTAGGED_VLAN] = vlan_id
        else:
            system_label = nodes['switch']['label']
            if_name = nodes['interface']['if_name']
            vlan_id = int(nodes['virtual_network']['vn_id'] )- 100000
            is_tagged = 'vlan_tagged' in nodes[SINGLE_VLAN_NODE]['attributes']
            if system_label not in interface_vlan_table:
                interface_vlan_table[system_label] = {}
            if if_name not in interface_vlan_table[system_label]:
                interface_vlan_table[system_label][if_name] = {
                    'id': nodes['interface']['id'],
                    CkEnum.TAGGED_VLANS: [],
                    CkEnum.UNTAGGED_VLAN: None,
                }
            this_interface_data = interface_vlan_table[system_label][if_name]
            if is_tagged:
                this_interface_data[CkEnum.TAGGED_VLANS].append(vlan_id)
            else:
                this_interface_data[CkEnum.UNTAGGED_VLAN] = vlan_id

    summary = [f"{x}:{len(interface_vlan_table[x])}" for x in interface_vlan_table.keys()]
    logging.debug(f"BP:{the_bp.label} {summary=}")

    return interface_vlan_table


class VniCt:
    """
    vni: int
    tagged_id: <id of tagged CT>
    untagged_id: <id of untagged CT>
    """
    vni: int = None
    tagged_id: str = None
    untagged_id: str = None

    def __init__(self, the_bp, vni: int = None):
        self.bp = the_bp
        self.vni = vni
        self.tagged_id = None
        self.untagged_id = None
        self.logger = logging.getLogger(f"VniCT({self.vni})")

    def set_id(self, ct_id: str, is_tagged: bool):
        if is_tagged:
            self.tagged_id = ct_id
        else:
            self.untagged_id = ct_id
    
    def get_id(self, is_tagged:bool = True):
        if is_tagged:
            if self.tagged_id is None:
                self.logger.warning(f"tagged_id is None")
                self.tagged_id = self.bp.add_single_vlan_ct(self.vni, is_tagged)
                self.logger.warning(f"{self.tagged_id=}")
            return self.tagged_id
        else:
            if self.untagged_id is None:
                self.logger.warning(f"untagged_id is None")
                self.untagged_id = self.bp.add_single_vlan_ct(self.vni, is_tagged)
                self.logger.warning(f"{self.untagged_id=}")
            return self.untagged_id


def get_vni_2_ct_id_table(the_bp) -> dict:
    """
    Build a VNI to CT table of the blueprint

    Return: dict {
        <vni>: { vni: <vni>, tagged_id: <id of tagged CT>, untagged_id: <id of untagged CT> }
    }
    """
    VN_NODE = 'virtual_network'
    CT_NODE = 'batch'
    SINGLE_VLAN_NODE = 'AttachSingleVLAN'

    vni_2_ct_id_table = {}  # VniCt to find CT id from vni
    
    # build vni_2_ct_table
    # should pick all the VNs regradless of attached or not
    vlan_table_query = f"""
        node('ep_endpoint_policy', policy_type_name='batch', name='{CT_NODE}')
            .out('ep_subpolicy').node('ep_endpoint_policy')
            .out('ep_first_subpolicy').node('ep_endpoint_policy',policy_type_name='AttachSingleVLAN',name='{SINGLE_VLAN_NODE}')
            .out('vn_to_attach').node('virtual_network', name='{VN_NODE}')
    """
    vlan_table_nodes = the_bp.query(vlan_table_query, multiline=True)
    for node in vlan_table_nodes:
        vni = int(node[VN_NODE]['vn_id'])
        ct_id = node[CT_NODE]['id']
        is_tagged = 'vlan_tagged' in node[SINGLE_VLAN_NODE]['attributes']
        if vni not in vni_2_ct_id_table:
            vni_2_ct_id_table[vni] = VniCt(the_bp, vni)
        vni_2_ct_id_table[vni].set_id(ct_id, is_tagged)

    return vni_2_ct_id_table

def update_interface_id(the_bp, interface_vlan_table, switch_label_pair: list) -> dict:
    # deepcopy to avoid mutation
    interface_id_vlan_table = copy.deepcopy(interface_vlan_table)

    EVPN_INTERFACE_NODE = 'evpn-interface'
    MEMBER_SWITCH_NODE = 'switch'
    MEMBER_INTERFACE_NODE = 'member-interface'

    interface_id_query = f"""
        match(
            node('system', label=is_in({list(interface_vlan_table.keys())}), name='{MEMBER_SWITCH_NODE}')
                .out('hosted_interfaces').node('interface', if_type='ethernet', name='{MEMBER_INTERFACE_NODE}'),
            optional(
                node('interface', po_control_protocol='evpn', name='{EVPN_INTERFACE_NODE}')
                    .out('composed_of').node('interface')
                    .out('composed_of').node(name='{MEMBER_INTERFACE_NODE}')
                )
        )
    """
    interface_id_nodes_list = the_bp.query(interface_id_query, multiline=True)
    for nodes in interface_id_nodes_list:
        system_label = nodes[MEMBER_SWITCH_NODE]['label']
        if_name = nodes[MEMBER_INTERFACE_NODE]['if_name']
        if nodes[EVPN_INTERFACE_NODE]:
            # the node is not null - it is an EVPN interface
            evpn_id = nodes[EVPN_INTERFACE_NODE]['id']
            # loop through the interface_vlan_table to update
            for ae_id, ae_data in interface_id_vlan_table[CkEnum.REDUNDANCY_GROUP].items():
                if system_label in ae_data[CkEnum.MEMBER_INTERFACE]:
                    if if_name in ae_data[CkEnum.MEMBER_INTERFACE][system_label]:
                        ae_data['id'] = evpn_id
                        break
        else:
            # no EVPN_INTERFACE_NODE - non-LAG interface
            if if_name in interface_vlan_table[system_label]:
                # skip if the interface does not have vlan assignment
                interface_id_vlan_table[system_label][if_name]['id'] = nodes[MEMBER_INTERFACE_NODE]['id']
    return interface_id_vlan_table


def associate_cts(the_bp, interface_vlan_table, switch_label_pair: list):
    """
    """
    # switch_interface_nodes = the_bp.get_switch_interface_nodes(switch_label_pair)
    vni_2_ct_id_table = get_vni_2_ct_id_table(the_bp)
    # from apstra_bp_consolidation.consolidation import pretty_yaml
    # pretty_yaml(vni_2_ct_id_table, "vni_2_ct_id_table")

    interface_id_vlan_table = update_interface_id(the_bp, interface_vlan_table, switch_label_pair)
    # pretty_yaml(interface_id_vlan_table, "interface_id_vlan_table")


    """
    <system_label>:
        <if_name>:
            id: <interface id>
            tagged_vlans: []
            untagged_vlan: None
    redundacy_group:
        <tor_ae_id>:
            id: <ae_id>
            tagged_vlans: []
            untagged_vlan: None
            member_interfaces:
                <system_label>: [ <member if_name> ]   
    """

    for system_label, system_data in interface_id_vlan_table.items():
        for intf_label, intf_data in system_data.items():
            interface_id = intf_data['id']
            # logging.debug(f"{system_label=}, {intf_label=}, {interface_id=}, {intf_data[CkEnum.TAGGED_VLANS]=}")
            ct_id_list = []
            for i in intf_data[CkEnum.TAGGED_VLANS]:
                # logging.debug(f"{i=}, {vni_2_ct_id_table[100000+i]=}")
                ct_id_list.append(vni_2_ct_id_table[100000+i].get_id())
            # ct_id_list = [ vni_2_ct_id_table[100000+x].get_id() for x in intf_data[CkEnum.TAGGED_VLANS] ]
            if intf_data[CkEnum.UNTAGGED_VLAN]:
                # if untagged vlan is configure
                ct_id_list.append(vni_2_ct_id_table[100000+intf_data[CkEnum.UNTAGGED_VLAN]].get_id(False))

            while len(ct_id_list) > 0:
                throttle_number = 50
                cts_chunk = ct_id_list[:throttle_number]
                # logging.debug(f"Adding Connecitivity Templates on this links: {len(cts_chunk)=}")
                batch_ct_spec = {
                    "operations": [
                        {
                            "path": "/obj-policy-batch-apply",
                            "method": "PATCH",
                            "payload": {
                                "application_points": [
                                    {
                                        "id": interface_id,
                                        "policies": [ {"policy": x, "used": True} for x in cts_chunk]
                                    }
                                ]
                            }
                        }
                    ]
                }
                batch_result = the_bp.batch(batch_ct_spec, params={"comment": "batch-api"})
                del ct_id_list[:throttle_number]
        

import click
@click.command(name='move-cts')
def click_move_cts():
    order = ConsolidationOrder()
    order_move_cts(order)



def order_move_cts(order):
    logging.info(f"======== Moving Connectivity Templated for {order.switch_label_pair} from {order.tor_bp.label} to {order.main_bp.label}")
    ########
    # pull CT assignment data

    interface_vlan_table = pull_interface_vlan_table(order.tor_bp, order.switch_label_pair)
    # pretty_yaml(interface_vlan_table, "interface_vlan_table")

    associate_cts(order.main_bp, interface_vlan_table, order.switch_label_pair)


if __name__ == '__main__':
    order = ConsolidationOrder()
    order_move_cts(order)
