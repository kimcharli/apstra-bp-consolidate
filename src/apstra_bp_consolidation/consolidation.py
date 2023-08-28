#!/usr/bin/env python3

import click
import yaml
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
    
    def rename_generic_system(self, generic_system_from_tor_bp: str) -> str:
        # rename the generic system in the main blueprint to avoid conflict
        # the maximum length is 32. Prefix 'r5r14-'
        old_patterns = ['_atl_rack_1_000_', '_atl_rack_1_001_', '_atl_rack_5120_001_']
        prefix = self.tor_label[len('atl1tor-'):]
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



def pretty_yaml(data: dict, label: str) -> None:
    logging.debug(f"==== {label}\n{yaml.dump(data)}\n====")


@click.command(name='move-all')
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

if __name__ == "__main__":
    move_all()


