#!/usr/bin/env python3

from apstra_session import CkApstraSession
from apstra_blueprint import CkApstraBlueprint

# class ConsolidationOrder:
#     # yaml_in_file
#     # config
#     # session
#     # main_bp
#     # tor_bp

#     def __init__(self, yaml_in_file):
#         self.yaml_in_file = yaml_in_file
#         with open(yaml_in_file, 'r') as file:
#             self.config = yaml.safe_load(file)
#         apstra_server = self.config['apstra_server']
#         self.session = CkApstraSession(
#             apstra_server['host'], 
#             apstra_server['port'], 
#             apstra_server['username'],
#             apstra_server['password']
#             )
#         self.main_bp = CkApstraBlueprint(self.session, self.config['blueprint']['main']['name'])
#         self.tor_bp = CkApstraBlueprint(self.session, self.config['blueprint']['tor']['name'])
#         access_switch_interface_map_label = self.config['blueprint']['tor']['new_interface_map']
        
#         self.old_generic_system_label = self.config['blueprint']['tor']['torname']
#         self.switch_label_pair = self.config['blueprint']['tor']['switch_names']





def pull_single_vlan_cts(the_bp, switch_label_pair: list) -> dict:
    """
    Pull the single vlan cts for the switch pair

    The return data
    <system_label>:
        <if_name>:
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
        #   xe-0/0/0:
        #     tagged_vlans: []
        #     untagged_vlan: None
        'redundancy_group': {}
    }

    # pull the non-ae interfaces
    ethernet_interface_query = f"""
        node('system', system_type='switch', label=is_in({switch_label_pair}), name='switch')
            .out().node('interface', if_type='ethernet', name='switch_interface')
            .out().node('ep_group', name='ep_group')
            .in_().node('ep_application_instance', name='ep_application_instance')
            .out().node('ep_endpoint_policy', policy_type_name='AttachSingleVLAN', name='ep_endpoint_policy')
            .out().node('virtual_network', name='virtual_network')
            .out().node('vn_instance', name='vn_instance')
    """
    ethernet_interface_nodes = the_bp.query(ethernet_interface_query, multiline=True)
    for node in ethernet_interface_nodes:
        switch_label = node['switch']['label']
        if_name = node['switch_interface']['if_name']
        vlan_id = node['vn_instance']['vlan_id']
        if switch_label not in ct_table:
            ct_table[switch_label] = {}
        if if_name not in ct_table[switch_label]:
            ct_table[switch_label][if_name] = {
                'tagged_vlans': [],
                'untagged_vlan': None
            }
        if 'untagged' in node['ep_endpoint_policy']['attributes']:
            ct_table[switch_label][if_name]['untagged_vlan'] = vlan_id
        else:
            ct_table[switch_label][if_name]['tagged_vlans'].append(vlan_id)


    # process ae interfaces in two stages. combined query used to time out
    ae_interface_query = f"""
        node('system', system_type='switch', label=is_in({switch_label_pair}), name='switch')
            .out().node('redundancy_group')
            .out().node('interface', if_type='port_channel', name='switch_interface')
            .out().node('interface', name='ae')
            .out().node('interface', name='member_interface')
            .in_().node('system', name='member_switch')
    """
    ae_interface_nodes = the_bp.query(ae_interface_query, multiline=True)
    for ae in ae_interface_nodes:
        ae_id = ae['switch_interface']['id']
        if ae_id not in ct_table['redundancy_group']:
            ct_table['redundancy_group'][ae_id] = {
                'tagged_vlans': [],
                'untagged_vlan': None,
                'member_interfaces': {}
            }
        member_switch_label = ae['member_switch']['label']
        member_if_name = ae['member_interface']['if_name']
        if member_switch_label not in ct_table['redundancy_group'][ae_id]['member_interfaces']:
            ct_table['redundancy_group'][ae_id]['member_interfaces'][member_switch_label] = [ member_if_name ]
        elif member_if_name not in ct_table['redundancy_group'][ae_id]['member_interfaces'][member_switch_label]:
            ct_table['redundancy_group'][ae_id]['member_interfaces'][member_switch_label].append(member_if_name)
        print(f"     = pull_single_vlan_cts() BP:{the_bp.label} {ae_id=}, ae={ae['ae']['if_name']}, {member_switch_label=}, {member_if_name=}")

        ae_ct_query = f"""
            node(id='{ae_id}')
                .out().node('ep_group', name='ep_group')
                .in_().node('ep_application_instance', name='ep_application_instance')
                .out().node('ep_endpoint_policy', policy_type_name='AttachSingleVLAN', name='ep_endpoint_policy')
                .out().node('virtual_network', name='virtual_network')
                .out().node('vn_instance', name='vn_instance')
        """
        ae_ct_nodes = the_bp.query(ae_ct_query, multiline=True)

        for ae_ct_node in ae_ct_nodes:
            vlan_id = ae_ct_node['vn_instance']['vlan_id']
            if 'untagged' in ae_ct_node['ep_endpoint_policy']['attributes']:
                ct_table['redundancy_group'][ae_id]['untagged_vlan'] = vlan_id
            elif vlan_id not in ct_table['redundancy_group'][ae_id]['tagged_vlans']:
                ct_table['redundancy_group'][ae_id]['tagged_vlans'].append(vlan_id)

    # TODO: remove empty ae
    # aes = copy.copy(ct_table['redundancy_group'].keys())
    # print(f"     = pull_single_vlan_cts() {type(aes)=}")
    # for key in aes:
    #     ae = ct_table['redundancy_group'][key]
    #     try:
    #         if len(ae['tagged_vlans']) == 0 and ae['untagged_vlan'] is None:
    #             del ct_table['redundancy_group'][key]
    #     except TypeError:
    #         print(f"     = TypeError: pull_single_vlan_cts() {ae=} {ct_table['redundancy_group']=}")
    #         raise
    # print(f"== pull_single_vlan_cts() pulling single vlan cts for {switch_label_pair=}")
    # pretty_yaml(ct_table, "ct_table")
    return ct_table

def associate_missing_cts(the_bp, tor_ct, main_ct: list):
    print(f"== associate_missing_cts() associating missing cts, {len(tor_ct['redundancy_group'])=}, {len(main_ct['redundancy_group'])=}")
    for system_label, system_data in tor_ct.items():
        if system_label not in main_ct:
            print(f"     = associate_missing_cts() adding: {system_label=}")
            main_ct[system_label] = {}
            #     'tagged_vlans': [],
            #     'untagged_vlan': None
            # }
        for if_name, if_data in system_data.items():
            # lag interface
            if system_label == 'redundancy_group':
                pass
            # non-lag interface
            else:
                if if_name not in main_ct[system_label]:
                    print(f"     = associate_missing_cts() adding: {system_label=}, {if_name=}")
                    main_ct[system_label][if_name] = {
                        'tagged_vlans': [],
                        'untagged_vlan': None
                    }
                tagged_vlans = [x for x in if_data['tagged_vlans'] if x not in main_ct[system_label][if_name]['tagged_vlans']]
                untagged_vlan = if_data['untagged_vlan']
                if untagged_vlan or len(tagged_vlans):
                    print(f"     = associate_missing_cts() {system_label=}, {if_name=}, {tagged_vlans=}, {untagged_vlan=}")
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
                    print(f"     = associate_missing_cts() {attach_spec=}")
                    the_bp.patch_obj_policy_batch_apply(attach_spec, params={'aync': 'full'})


def main(yaml_in_file):
    from consolidation import ConsolidationOrder
    order = ConsolidationOrder(yaml_in_file)

    ########
    # pull CT assignment data

    # q1
    # f"node('ep_endpoint_policy', name='ep', label='{ct_label}').out('ep_subpolicy').node().out('ep_first_subpolicy').node(name='n2')"
    # vn_endpoint_query = f"node('system', label='{system_label}').out('hosted_vn_instances').node('vn_instance').out('instantiates').node('virtual_network', label='{vn_label}').out('member_endpoints').node('vn_endpoint', name='vn_endpoint')"
    # get_ae_or_interface_id(ct_dict['system'], ct_dict['interface'])
    # node('virtual_network', name='virtual_network').out().node('vn_endpoint', name='vn_endpoint').in_().node('interface', name='interface').in_().node('system', name='system')

    tor_cts = pull_single_vlan_cts(order.tor_bp, order.switch_label_pair)
    main_cts = pull_single_vlan_cts(order.main_bp, order.switch_label_pair)
    associate_missing_cts(order.main_bp, tor_cts, main_cts)


if __name__ == '__main__':
    main('./tests/fixtures/config.yaml')    


