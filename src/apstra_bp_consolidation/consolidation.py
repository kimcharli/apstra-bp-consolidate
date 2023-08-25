#!/usr/bin/env python3

import json
import time
import copy
# import yaml
import click
from datetime import datetime
import logging

from apstra_bp_consolidation.apstra_session import CkApstraSession
from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint
from apstra_bp_consolidation.apstra_session import prep_logging



class ConsolidationOrder:
    # yaml_in_file
    # config
    # session
    # main_bp
    # tor_bp
    # tor_label
    # switch_label_pair

    def __init__(self, env_file_input: str = None):
        """
        Build the consolidation order object from the env file path
        """
        import yaml
        import os
        from dotenv import load_dotenv

        env_file = env_file_input or 'tests/fixtures/.env'

        load_dotenv(env_file)
        yaml_in_file = os.getenv('yaml_in_file')
        log_level = os.getenv('logging_level')
        prep_logging(log_level)
        # order = ConsolidationOrder(yaml_in_file)

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
        self.logger = logging.getLogger(f"ConsolidationOrder({self.main_bp.label}<-{self.tor_bp.label})")

        self.tor_label = self.config['blueprint']['tor']['torname']
        self.switch_label_pair = self.config['blueprint']['tor']['switch_names']
        self.logger.debug(f"{self.main_bp.id=}, {self.tor_bp.id=}")

 
    def __repr__(self) -> str:
        return f"ConsolidationOrder({self.yaml_in_file=}, {self.config=}, {self.session=}, {self.main_bp=}, {self.tor_bp=}, {self.tor_label=}, {self.switch_label_pair=})"
    
    def rename_generic_system(self, generec_system_from_tor_bp: str) -> str:
        # rename the generic system in the main blueprint to avoid conflict
        # the maximum length is 32. Prefix 'r5r14-'
        # TODO: remove pattern like: '_atl_rack_1_000'
        prefix = self.tor_label[:len('atl1tor-')]
        max_len = 32
        if ( len(generec_system_from_tor_bp) + len(prefix) ) > max_len:
            # TODO: potential of conflict
            self.logger.warning(f"Generic system name {generec_system_from_tor_bp=} is too long. Keeping original label.")
            return generec_system_from_tor_bp
        return f"{self.tor_label[len('atl1tor-'):]}-{generec_system_from_tor_bp}"



def pretty_yaml(data: dict, label: str) -> None:
    logging.debug(f"==== {label}\n{yaml.dump(data)}\n====")



def main():
    print("Running as main")
    import os
    from dotenv import load_dotenv

    load_dotenv("tests/fixtures/.env")
    yaml_in_file = os.getenv('yaml_in_file')
    log_level = os.getenv('logging_level')

    prep_logging(log_level)
    order = ConsolidationOrder(yaml_in_file)
    # main(order)



    return
    # revert any staged changes
    # main_bp.revert()
    # tor_bp.revert()

    ########

    from move_access_switch import get_tor_ae_id_in_main
    from move_access_switch import build_switch_pair_spec
    from move_access_switch import remove_old_generic_system_from_main
    from move_access_switch import create_new_access_switch_pair

    tor_name = order.config['blueprint']['tor']['torname']

    tor_interface_nodes_in_main = order.main_bp.get_server_interface_nodes(tor_name)
    tor_ae_id_in_main = get_tor_ae_id_in_main(tor_interface_nodes_in_main, tor_name)

    # build switch pair spec from the main blueprint generic system links
    switch_pair_spec = build_switch_pair_spec(tor_interface_nodes_in_main, order.tor_label)
    
    # remove tor generic system from main blueprint
    remove_old_generic_system_from_main(order, tor_ae_id_in_main, tor_interface_nodes_in_main)

    # create new access switch pair in main blueprint
    create_new_access_switch_pair(order, switch_pair_spec)



    ########
    # create new generic systems
    from move_generic_system import pull_generic_system_off_switch
    from move_generic_system import new_generic_systems

    tor_generic_systems_data = pull_generic_system_off_switch(order.tor_bp, order.switch_label_pair)
    access_switch_generic_systems_data = {order.rename_generic_system(old_label): data for old_label, data in tor_generic_systems_data.items()}
    new_generic_systems(order, access_switch_generic_systems_data)


    ########
    # assign virtual networks
    from move_vn import pull_vni_ids
    from move_vn import access_switch_assign_vns

    vni_list = pull_vni_ids(order.tor_bp, order.switch_label_pair)
    access_switch_assign_vns(order.main_bp, vni_list, order.switch_label_pair)


    ########
    # pull CT assignment data

    # q1
    # f"node('ep_endpoint_policy', name='ep', label='{ct_label}').out('ep_subpolicy').node().out('ep_first_subpolicy').node(name='n2')"
    # vn_endpoint_query = f"node('system', label='{system_label}').out('hosted_vn_instances').node('vn_instance').out('instantiates').node('virtual_network', label='{vn_label}').out('member_endpoints').node('vn_endpoint', name='vn_endpoint')"
    # get_ae_or_interface_id(ct_dict['system'], ct_dict['interface'])
    # node('virtual_network', name='virtual_network').out().node('vn_endpoint', name='vn_endpoint').in_().node('interface', name='interface').in_().node('system', name='system')

    from move_ct import pull_single_vlan_cts, associate_missing_cts

    tor_cts = pull_single_vlan_cts(order.tor_bp, order.switch_label_pair)
    main_cts = pull_single_vlan_cts(order.main_bp, order.switch_label_pair)
    associate_missing_cts(order.main_bp, tor_cts, main_cts)


    ########
    # move devices from tor bp to main bp
    from move_device import move_device

    move_device(order)


@click.group()
# @click.option('--log-level', envvar='logging_level', help='The logging level')
# @click.pass_context
# def cli(ctx, log_level):
def cli():
    pass

    # click.echo('Running as cli')
    # print("Running as main")
    # import os
    # from dotenv import load_dotenv

    # load_dotenv("tests/fixtures/.env")
    # yaml_in_file = os.getenv('yaml_in_file')
    # log_level = os.getenv('logging_level')

    # prep_logging(log_level)
    # order = ConsolidationOrder(yaml_in_file)
    # apstra_helper(obj=order)

from apstra_bp_consolidation.move_access_switch import click_move_access_switch
from apstra_bp_consolidation.move_generic_system import click_move_generic_systems
from apstra_bp_consolidation.move_vn import click_move_virtual_networks
from apstra_bp_consolidation.move_ct import click_move_cts
from apstra_bp_consolidation.move_device import click_move_devices

cli.add_command(click_move_generic_systems)
cli.add_command(click_move_access_switch)
cli.add_command(click_move_virtual_networks)
cli.add_command(click_move_cts)
cli.add_command(click_move_devices)

if __name__ == "__main__":
    main()


