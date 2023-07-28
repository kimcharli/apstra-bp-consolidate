#!/usr/bin/env python3

import json
import time
import copy

from apstra_bp_consolidation.apstra_session import CkApstraSession
from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint


class ConsolidationOrder:
    # yaml_in_file
    # config
    # session
    # main_bp
    # tor_bp
    # old_generic_system_label
    # switch_label_pair

    def __init__(self, yaml_in_file):
        import yaml

        self.yaml_in_file = yaml_in_file
        with open(yaml_in_file, 'r') as file:
            self.config = yaml.safe_load(file)
        apstra_server = self.config['apstra_server']
        self.session = CkApstraSession(
            apstra_server['host'], 
            apstra_server['port'], 
            apstra_server['username'],
            apstra_server['password']
            )
        self.main_bp = CkApstraBlueprint(self.session, self.config['blueprint']['main']['name'])
        self.tor_bp = CkApstraBlueprint(self.session, self.config['blueprint']['tor']['name'])
        access_switch_interface_map_label = self.config['blueprint']['tor']['new_interface_map']
        
        self.old_generic_system_label = self.config['blueprint']['tor']['torname']
        self.switch_label_pair = self.config['blueprint']['tor']['switch_names']

    def __repr__(self) -> str:
        return f"ConsolidationOrder({self.yaml_in_file=}, {self.config=}, {self.session=}, {self.main_bp=}, {self.tor_bp=}, {self.old_generic_system_label=}, {self.switch_label_pair=})"

# def build_switch_fabric_links_dict(links_dict:dict) -> dict:
#     '''
#     Build "links" data from the links query
#     It is assumed that the interface names are in et-0/0/48-b format
#     '''
#     # print(f"==== build_switch_fabric_links_dict() {len(links_dict)=}, {links_dict=}")
#     link_candidate = {
#             "lag_mode": "lacp_active",
#             "system_peer": None,
#             "switch": {
#                 "system_id": links_dict['leaf']['id'],
#                 "transformation_id": 2,
#                 "if_name": links_dict['leaf_intf']['if_name']
#             },
#             "system": {
#                 "system_id": None,
#                 "transformation_id": 1,
#                 "if_name": None
#             }
#         }
#     original_intf_name = links_dict['gs_intf']['if_name']
#     if original_intf_name in ['et-0/0/48-a', 'et-0/0/48a']:
#         link_candidate['system_peer'] = 'first'
#         link_candidate['system']['if_name'] = 'et-0/0/48'
#     elif original_intf_name in ['et-0/0/48-b', 'et-0/0/48b']:
#         link_candidate['system_peer'] = 'second'
#         link_candidate['system']['if_name'] = 'et-0/0/48'
#     elif original_intf_name in ['et-0/0/49-a', 'et-0/0/49a']:
#         link_candidate['system_peer'] = 'first'
#         link_candidate['system']['if_name'] = 'et-0/0/49'
#     elif original_intf_name in ['et-0/0/49-b', 'et-0/0/49b']:
#         link_candidate['system_peer'] = 'second'
#         link_candidate['system']['if_name'] = 'et-0/0/49'
#     else:
#         return None
#     return link_candidate

# #     # old_generic_system_physical_links has a list of dict with generic, gs_intf, link, leaf_intf, and leaf 
# def build_switch_pair_spec(old_generic_system_physical_links, old_generic_system_label) -> dict:
#     # print(f"==== build_switch_pair_spec() with {len(old_generic_system_physical_links)=}, {old_generic_system_label}")
#     # print(f"===== build_switch_pair_spec() {old_generic_system_physical_links[0]=}")
#     switch_pair_spec = {
#         "links": [build_switch_fabric_links_dict(x) for x in old_generic_system_physical_links],
#         "new_systems": None
#     }

#     with open('./tests/fixtures/fixture-switch-system-links-5120.json', 'r') as file:
#         sample_data = json.load(file)

#     switch_pair_spec['new_systems'] = sample_data['new_systems']
#     switch_pair_spec['new_systems'][0]['label'] = old_generic_system_label

#     # del switch_pair_spec['new_systems']
#     print(f"====== build_switch_pair_spec() from {len(old_generic_system_physical_links)=}")
#     return switch_pair_spec







def pretty_yaml(data: dict, label: str) -> None:
    print(f"==== {label}\n{yaml.dump(data)}\n====")

def main(yaml_in_file: str):
    # pretty_yaml(config, "config")
    order = ConsolidationOrder(yaml_in_file)

    ########
    # prepare the data with initial validation    
    # main_bp = CkApstraBlueprint(apstra, config['blueprint']['main']['name'])
    # tor_bp = CkApstraBlueprint(apstra, config['blueprint']['tor']['name'])
    # access_switch_interface_map_label = config['blueprint']['tor']['new_interface_map']
    
    # old_generic_system_label = config['blueprint']['tor']['torname']
    # switch_label_pair = config['blueprint']['tor']['switch_names']
    

    # tor_cts = pull_single_vlan_cts(tor_bp, switch_label_pair)
    # main_cts = pull_single_vlan_cts(main_bp, switch_label_pair)
    # associate_missing_cts(main_bp, tor_cts, main_cts)
    # return 

    # # find the switch side ae information from the old generic system in the main blueprint
    # old_generic_system_ae_query = f"""
    #     node('system', label='{old_generic_system_label}')
    #         .out().node('interface', if_type='port_channel', name='generic_ae')
    #         .out().node('link')
    #         .in_().node(name='switch_ae')
    #         .where(lambda generic_ae, switch_ae: generic_ae != switch_ae )
    # """
    # # old_generic_system_ae_query = f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='port_channel', name='generic_ae').out().node('link').in_().node(name='switch_ae').where(lambda generic_ae, switch_ae: generic_ae != switch_ae )"
    # old_generic_system_ae_list = order.main_bp.query(old_generic_system_ae_query, print_prefix="main: old_generic_system_ae_query", multiline=True)
    # # the generic system should exist in main blueprint
    # if len(old_generic_system_ae_list):
    #     old_generic_system_ae_id = old_generic_system_ae_list[0]['switch_ae']['id']
    # print(f"== main: {old_generic_system_ae_list=}")
    from move_access_switch import get_old_generic_system_ae_id
    from move_access_switch import remove_old_generic_system
    from move_access_switch import create_new_access_switch_pair

    # old_generic_system_ae_id = get_old_generic_system_ae_id(order)
    # # return

    # cts_to_remove = order.main_bp.get_cts_on_generic_system_with_only_ae(old_generic_system_label)

    # # capture links to the target old generic system in the main blueprint
    # old_generic_system_physical_links_query = f"node('system', label='{old_generic_system_label}', name='generic').out().node('interface', if_type='ethernet', name='gs_intf').out().node('link', name='link').in_().node('interface', name='leaf_intf').in_().node('system', name='leaf').where(lambda gs_intf, leaf_intf: gs_intf != leaf_intf)"
    # print(f"== main: {old_generic_system_physical_links_query=}")
    # # old_generic_system_physical_links has a list of dict with generic, gs_intf, link, leaf_intf, and leaf 
    # old_generic_system_physical_links = order.main_bp.query(old_generic_system_physical_links_query)

    # print(f"== main: about to call build_switch_pair_spec, {len(old_generic_system_physical_links)=}")
    # switch_pair_spec = build_switch_pair_spec(old_generic_system_physical_links, old_generic_system_label)
    # print(f"== main: {switch_pair_spec['links']=}")

    # pull_generic_system_data = pull_generic_system_off_switch(order.tor_bp, order.switch_label_pair)
    # # pretty_yaml(pull_generic_system_data, "pull_generic_system_data")


    # # revert any staged changes
    # # main_bp.revert()
    # # tor_bp.revert()

    # ########
    # # delete the old generic system in main blueprint
    # # all the CTs on old generic system are on the AE link
    # if len(old_generic_system_ae_list):
    #     old_generic_system_label = order.config['blueprint']['tor']['torname']
    #     old_generic_system_ae_list = order.main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').where(lambda ae1, ae2: ae1 != ae2 )")
    #     if len(old_generic_system_ae_list) == 0:
    #         print(f"Generic system {old_generic_system_label} not found")
    #         return
    #     old_generic_system_ae_id = old_generic_system_ae_list[0]['ae1']['id']
    #     print(f"{old_generic_system_ae_id=}")

    #     # cts = order.main_bp.get_cts_on_generic_system_with_only_ae(old_generic_system_label)

    #     # old_generic_system_physical_links has a list of dict with generic, gs_intf, link, leaf_intf, and leaf 
    #     # old_generic_system_physical_links = main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='ethernet').out().node('link', name='link')")
    #     old_generic_system_physical_links = order.main_bp.query(f"node('system', label='{old_generic_system_label}').out().node('interface', if_type='ethernet', name='gs_intf').out().node('link', name='link').in_().node('interface', name='leaf_intf').in_().node('system', name='leaf').where(lambda gs_intf, leaf_intf: gs_intf != leaf_intf)")


    #     # damping CTs in chunks
    #     while len(cts_to_remove) > 0:
    #         cts_chunk = cts_to_remove[:50]
    #         print(f"Removing Connecitivity Templates on this links: {len(cts_chunk)=}")
    #         batch_ct_spec = {
    #             "operations": [
    #                 {
    #                     "path": "/obj-policy-batch-apply",
    #                     "method": "PATCH",
    #                     "payload": {
    #                         "application_points": [
    #                             {
    #                                 "id": old_generic_system_ae_id,
    #                                 "policies": [ {"policy": x, "used": False} for x in cts_chunk]
    #                             }
    #                         ]
    #                     }
    #                 }
    #             ]
    #         }
    #         batch_result = order.main_bp.batch(batch_ct_spec, params={"comment": "batch-api"})
    #         del cts_to_remove[:50]

    #     batch_link_spec = {
    #         "operations": [
    #             {
    #                 "path": "/delete-switch-system-links",
    #                 "method": "POST",
    #                 "payload": {
    #                     "link_ids": [ x['link']['id'] for x in old_generic_system_physical_links ]
    #                 }
    #             }
    #         ]
    #     }
    #     batch_result = order.main_bp.batch(batch_link_spec, params={"comment": "batch-api"})
    #     print(f"{batch_result=}")
    #     while True:
    #         if_generic_system_present = order.main_bp.query(f"node('system', label='{old_generic_system_label}')")
    #         if len(if_generic_system_present) == 0:
    #             break
    #         print(f"== main: {if_generic_system_present=}")
    #         time.sleep(3)
    #     # the generic system is gone.            


    remove_old_generic_system(order)

    create_new_access_switch_pair(order)


    # ########
    # # create new access system pair
    # # olg logical device is not useful anymore
    # # logical_device_list = tor_bp.query("node('system', name='system', role=not_in(['generic'])).out().node('logical_device', name='ld')")
    # # logical_device_id = logical_device_list[0]['ld']['id']

    # # LD _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # # IM _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # # rack type _ATL-AS-5100-48T, _ATL-AS-5120-48T created and added
    # # ATL-AS-LOOPBACK with 10.29.8.0/22

    # existing_switches = main_bp.query(f"node('system', label='{old_generic_system_label}a', name='system')")
    # if len(existing_switches) == 0:
    #     access_switch_pair_created = main_bp.add_generic_system(switch_pair_spec)
    #     print(f"{access_switch_pair_created=}")

    #     # wait for the new systems to be created
    #     while True:
    #         new_systems = main_bp.query(f"node('link', label='{access_switch_pair_created[0]}', name='link').in_().node('interface').in_().node('system', name='leaf').out().node('redundancy_group', name='redundancy_group')")
    #         # There should be 5 links (including the peer link)
    #         if len(new_systems) == 2:
    #             break
    #         print(f"Waiting for new systems to be created: {len(new_systems)=}")
    #         time.sleep(3)
    #     # The first entry is the peer link
    #     # rename redundancy group
    #     main_bp.patch_node(new_systems[0]['redundancy_group']['id'], {"label": f"{old_generic_system_label}-pair" })
    #     # rename each access switch for the label and hostname
    #     for leaf in new_systems:
    #         given_label = leaf['leaf']['label']
    #         if given_label[-1] == '1':
    #             new_label = f"{old_generic_system_label}a"
    #         elif given_label[-1] == '2':
    #             new_label = f"{old_generic_system_label}b"
    #         else:
    #             raise Exception(f"During renaming leaf names: Unexpected leaf label {given_label}")
    #         main_bp.patch_node(leaf['leaf']['id'], {"label": new_label, "hostname": new_label })

    ########
    # create new generic systems
    # generic system data: generic_system_label.link.dict
    # TODO: make unique for the generic system label
    from move_generic_system import pull_generic_system_off_switch
    from move_generic_system import new_generic_systems
    from move_generic_system import update_generic_systems_link_tag

    generic_systems_data = pull_generic_system_off_switch(order.tor_bp, order.switch_label_pair)

    print(f"=== main: get generic_systems_data. {len(generic_systems_data)=}")

    new_generic_systems(order.main_bp, generic_systems_data)

    # implemented in new_generic_systems
    # update_generic_systems_lag(main_bp, switch_label_pair, generic_systems_data)

    update_generic_systems_link_tag(main_bp, generic_systems_data)




    ########
    # assign virtual networks
    from move_vn import pull_vni_ids
    from move_vn import access_switch_assign_vns

    vni_list = pull_vni_ids(tor_bp, switch_label_pair)

    # assign connectivity templates
    access_switch_assign_vns(main_bp, vni_list, switch_label_pair)

    ########
    # pull CT assignment data

    # q1
    # f"node('ep_endpoint_policy', name='ep', label='{ct_label}').out('ep_subpolicy').node().out('ep_first_subpolicy').node(name='n2')"
    # vn_endpoint_query = f"node('system', label='{system_label}').out('hosted_vn_instances').node('vn_instance').out('instantiates').node('virtual_network', label='{vn_label}').out('member_endpoints').node('vn_endpoint', name='vn_endpoint')"
    # get_ae_or_interface_id(ct_dict['system'], ct_dict['interface'])
    # node('virtual_network', name='virtual_network').out().node('vn_endpoint', name='vn_endpoint').in_().node('interface', name='interface').in_().node('system', name='system')

    from move_ct import pull_single_vlan_cts, associate_missing_cts

    tor_cts = pull_single_vlan_cts(tor_bp, switch_label_pair)
    main_cts = pull_single_vlan_cts(main_bp, switch_label_pair)
    associate_missing_cts(main_bp, tor_cts, main_cts)


    return




if __name__ == "__main__":
    main('./tests/fixtures/config.yaml')
    # with open('./tests/fixtures/config.yaml', 'r') as file:
    #     config = yaml.safe_load(file)
    # apstra_server = config['apstra_server']
    # apstra = CkApstraSession(
    #     apstra_server['host'], 
    #     apstra_server['port'], 
    #     apstra_server['username'],
    #     apstra_server['password']
    #     )
    # main(apstra, config)

