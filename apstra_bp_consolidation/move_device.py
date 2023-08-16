#!/usr/bin/env python3

import logging

from consolidation import ConsolidationOrder
from consolidation import prep_logging

def move_device(order):
    ########
    # 
    system_snapshot = {} # label: sn
    remove_spec = []
    for switch_label in order.switch_label_pair:
        systems_got = order.tor_bp.get_system_node_from_label(switch_label)
        id = systems_got['id']
        system_id = systems_got['system_id']
        # deploy_mode = systems_got['deploy_mode']
        if system_id is not None:
            system_snapshot[switch_label] = system_id
            remove_spec.append({
                'system_id': None,
                'id': id,
                'deploy_mode': None
            })
    if len(remove_spec) == 0:
        logging.info("No devices to remove")
    else:
        device_removed = order.tor_bp.patch_nodes(remove_spec)
    logging.debug(f"{system_snapshot=}")

    add_spec = []
    for switch_label in order.switch_label_pair:
        system_got = order.main_bp.get_system_node_from_label(switch_label)
        id = system_got['id']
        # system_id = system_got['system_id']
        # deploy_mode = system_got['deploy_mode']
        add_spec.append({
            'id': id,
            'deploy_mode': 'deploy',
            'system_id': system_snapshot[switch_label],
        })
    device_added = order.main_bp.patch_nodes(add_spec)



    # add_device_to_bp(order.main_bp, order.switch_label_pair)


def main(order):
    move_device(order)


if __name__ == '__main__':
    yaml_in_file = './tests/fixtures/config.yaml'
    log_level = logging.DEBUG
    prep_logging(log_level)
    order = ConsolidationOrder(yaml_in_file)
    main(order)
