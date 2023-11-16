#!/usr/bin/env python3

import click
import yaml
import logging

from apstra_bp_consolidation.apstra_session import CkApstraSession
from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint
from apstra_bp_consolidation.apstra_session import prep_logging


# # PLAN
# class LeafLink:
#     # speed: str
#     # lag_mode: 'lacp_active'
#     # leaf_label: str
#     # leaf_if_name: str
#     # access_label: str
#     # access_if_name: str

#     def __init__(self, speed: str, leaf_label: str, leaf_if_name: str, access_label: str, access_if_name: str):
#         self.speed = speed
#         self.leaf_label = leaf_label
#         self.leaf_if_name = leaf_if_name
#         self.access_label = access_label
#         self.access_if_name = access_if_name

#     def __repr__(self) -> str:
#         return f"LeafLink({self.speed=}, {self.leaf_label=}, {self.leaf_if_name=}, {self.access_leaf=}, {self.leaf_if_name})"

#     def get_link_candidate(self, the_bp):
#         system_peer = 'first' if self.access_label[-1] in ['a', 'c' ] else 'second'
#         leaf_id = the_bp.get_system_node_from_label(self.leaf_label)['id']
#         link_candidate = {
#                 "lag_mode": "lacp_active",
#                 "system_peer": system_peer,
#                 "switch": {
#                     "system_id": leaf_id,
#                     "transformation_id": 2,
#                     "if_name": self.leaf_if_name
#                 },
#                 "system": {
#                     "system_id": None,
#                     "transformation_id": 1,
#                     "if_name": self.access_if_name
#                 }
#             }
#         return link_candidate


ENV_FILE = 'tests/fixtures/.env'

class ConsolidationOrder:
    # config_yaml_input_file
    # config
    # session
    # cabling_maps_yaml_file
    # main_bp
    # tor_bp
    # main_bp_label
    # tor_label # TODO: get this from cabling map
    # tor_name   ## the generic system name in the main blueprint
    # config_dir
    # switch_label_pair
    # vni_list: List[int]
    # PLAN
    # leaf_links: List[{ 
    #     'speed': '100g',
    #     'lag_mode': 'lacp_active',
    #     'leaf_label': 'atl1tor-leaf-1',
    #     'leaf_if_name': 'et-0/0/2'
    #     'access_label': 'atl1tor-r5r4a',
    #     'access_if_name': 'et-0/0/48'
    #  }]

    def __init__(self):
        """
        Build the consolidation order object from the env file path
        """
        import os
        from dotenv import load_dotenv

        load_dotenv()
        log_level = os.getenv('logging_level')
        prep_logging(log_level)

        apstra_server_host = os.getenv('apstra_server_host')
        apstra_server_port = os.getenv('apstra_server_port')
        apstra_server_username = os.getenv('apstra_server_username')
        apstra_server_password = os.getenv('apstra_server_password')

        print(f"{log_level=} {apstra_server_host=} {apstra_server_port=} {apstra_server_username=} {apstra_server_password=}")

        self.session = CkApstraSession(
            apstra_server_host, 
            apstra_server_port,
            apstra_server_username,
            apstra_server_password,
            )
        self.main_bp_label = os.getenv('main_bp')
        self.tor_label = os.getenv('tor_bp')
        self.tor_name = os.getenv('tor_name')
        self.access_switch_interface_map_label = os.getenv('tor_im_new')
        self.config_dir = os.getenv('config_dir')  # for pull-configurations

        self.main_bp = CkApstraBlueprint(self.session, self.main_bp_label)
        self.tor_bp = CkApstraBlueprint(self.session, self.tor_label)
        self.logger = logging.getLogger(f"ConsolidationOrder({self.main_bp.label}<-{self.tor_bp.label})")

        tor_switch_nodes = self.tor_bp.query("node('system', name='system', management_level='full_control')")
        self.switch_label_pair = [ x['system']['label'] for x in tor_switch_nodes ]

        self.logger.debug(f"{self.main_bp.id=}, {self.tor_bp.id=}")
        # self.leaf_links = self.pull_leaf_links()
        # self.vni_list = []
        self.pull_vni_ids()
        # self.logger.info(f"{self=}")
        self.cabling_maps_yaml_file = os.getenv('cabling_maps_yaml_file')
 
    def __repr__(self) -> str:
        return f"ConsolidationOrder({self.config_yaml_input_file=}, {self.config=}, {self.session=}, {self.main_bp=}, {self.tor_bp=}, {self.tor_label=}, {self.switch_label_pair=})"
    
    def rename_generic_system(self, generic_system_from_tor_bp: str) -> str:
        # rename the generic system in the main blueprint to avoid conflict
        # the maximum length is 32. Prefix 'r5r14-'
        old_patterns = ['_atl_rack_1_000_', '_atl_rack_1_001_', '_atl_rack_5120_001_']
        # get the prefix from tor_name
        prefix = self.tor_name[len('atl1tor-'):]
        for pattern in old_patterns:
            if generic_system_from_tor_bp.startswith(pattern):
                # replace the string with the prefix
                return f"{prefix}-{generic_system_from_tor_bp[len(pattern):]}"
        # it doesn't starts with the patterns. See if it is too long to prefix
        max_len = 32
        if ( len(generic_system_from_tor_bp) + len(prefix) + 1 ) > max_len:
            # TODO: potential of conflict
            self.logger.warning(f"Generic system name {generic_system_from_tor_bp=} is too long to prefix. Keeping original label.")
            return generic_system_from_tor_bp
        # just prefix
        return f"{prefix}-{generic_system_from_tor_bp}"

    # PLAN
    # def pull_leaf_links(self):
    #     # TODO: pull the live data from the blueprint
    #     return self.config.get('leaf_links', [])

    def pull_vni_ids(self):
        """
        Pull the vni ids present in the switch pair

        """
        switch_label_pair = self.switch_label_pair
        the_bp = self.tor_bp
        self.logger.debug(f"pulling vni ids for {switch_label_pair=} from {the_bp.label}")
        vn_nodes_query = f"""
            match(
                node('system', label=is_in({switch_label_pair}))
                .out().node('vn_instance')
                .out().node('virtual_network', name='vn')
            ).distinct(['vn'])"""
        vn_nodes = the_bp.query(vn_nodes_query)
        vni_list = [ x['vn']['vn_id'] for x in vn_nodes ]
        logging.debug(f"found {len(vni_list)=}")
        self.vni_list = vni_list
        return


@click.command(name='collect-cabling-maps', help='collect the cabling maps from all the blueprints and write to a yaml file')
def click_collect_cabling_maps():
    """
    Collect the cabling maps from all blueprints
    """
    logging.info(f"======== Collecting Cabling Maps from all blueprints")
    order = ConsolidationOrder()
    order_collect_cabling_maps(order)

def order_collect_cabling_maps(order: ConsolidationOrder):
    logging.info(f"======== Collecting Cabling Maps from all blueprints")
    cabling_maps = {}    # bp_label: cabling_maps
    cable_map_out_yaml_file = order.cabling_maps_yaml_file

    # iterate all the blueprints
    bp_id_list = order.session.list_blueprint_ids()
    for i in range(len(bp_id_list)):
        bp_id = bp_id_list[i]
        this_bp = CkApstraBlueprint(order.session, None, bp_id)
        this_bp_label = this_bp.label
        logging.debug(f"pulling cable map - {i+1}/{len(bp_id_list)} == {this_bp_label}")
        cabling_maps[this_bp_label] = this_bp.get_cabling_maps()
        i += 1

    logging.info(f"writing cabling maps to {cable_map_out_yaml_file}")
    with open(cable_map_out_yaml_file, 'w') as file:
        yaml.dump(cabling_maps, file)
    

def pretty_yaml(data: dict, label: str) -> None:
    logging.debug(f"==== {label}\n{yaml.dump(data)}\n====")


@click.command(name='move-all', help='run all the steps in sequence')
def move_all():
    order = ConsolidationOrder()

    from apstra_bp_consolidation.move_access_switch import order_move_access_switches
    order_move_access_switches(order)

    from apstra_bp_consolidation.move_generic_system import order_move_generic_systems
    order_move_generic_systems(order)

    from apstra_bp_consolidation.move_vn import order_move_virtual_networks
    order_move_virtual_networks(order)

    from apstra_bp_consolidation.move_ct import order_move_cts
    order_move_cts(order)

    from apstra_bp_consolidation.move_device import order_move_devices
    order_move_devices(order)

    

@click.group()
# @click.option('--log-level', envvar='logging_level', help='The logging level')
# @click.pass_context
def cli():
    pass


from apstra_bp_consolidation.move_access_switch import click_move_access_switches
cli.add_command(click_move_access_switches)

from apstra_bp_consolidation.move_generic_system import click_move_generic_systems
cli.add_command(click_move_generic_systems)

from apstra_bp_consolidation.move_vn import click_move_virtual_networks
cli.add_command(click_move_virtual_networks)

from apstra_bp_consolidation.move_ct import click_move_cts
cli.add_command(click_move_cts)

from apstra_bp_consolidation.move_device import click_move_devices
cli.add_command(click_move_devices)

cli.add_command(move_all)

from apstra_bp_consolidation.find_missing_vn import find_missing_vn
cli.add_command(find_missing_vn)

from apstra_bp_consolidation.pull_configs import click_pull_configurations
cli.add_command(click_pull_configurations)

cli.add_command(click_collect_cabling_maps)

if __name__ == "__main__":
    move_all()


