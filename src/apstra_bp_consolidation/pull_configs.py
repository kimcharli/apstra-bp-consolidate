#!/usr/bin/env python3

import os
import click
from apstra_bp_consolidation.consolidation import ConsolidationOrder

def write_to_file(file_name, content):
    MIN_SIZE = 2  # might have one \n
    if len(content) > MIN_SIZE:
        with open(file_name, 'w') as f:
            f.write(content)



def order_pull_configurations(order: ConsolidationOrder):
    begin_configlet = '------BEGIN SECTION CONFIGLETS------'
    begin_set = '------BEGIN SECTION SET AND DELETE BASED CONFIGLETS------'

    output_folder_name = order.config_dir
    for bp in [ order.main_bp, order.tor_bp ]:
        for system_label in order.switch_label_pair:
            system_id = bp.get_system_node_from_label(system_label)['id']
            rendered_confg = bp.get_switch_rendering(system_id)
            output_dir = f"{order.config_dir}/{bp.label}"
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            write_to_file(f"{output_dir}/{system_label}-rendered.txt", rendered_confg)

@click.command(name='a5-pull-configurations', help='step 5 - pull produced configurations to compare')
def click_pull_configurations():
    order = ConsolidationOrder()
    order_pull_configurations(order)

if __name__ == '__main__':
    click_pull_configurations()

