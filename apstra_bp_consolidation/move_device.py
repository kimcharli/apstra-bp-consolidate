#!/usr/bin/env python3

import json
import logging

from apstra_session import CkApstraSession
from apstra_blueprint import CkApstraBlueprint
from consolidation import prep_logging
from consolidation import deep_compare
from consolidation import pretty_yaml


def move_device(order):
    ########
    # 
    system_snapshot = {} # label: sn
    remove_spec = []
    for switch_label in order.switch_label_pair:
        systems_got = order.tor_bp.get_system_from_label(switch_label)
        id = systems_got['id']
        sn = systems_got['sn']
        deploy_mode = systems_got['deploy_mode']
        # TODO: any variations
        if sn is not None and deploy_mode is not None:
            system_snapshot[switch_label] = sn
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
        systems_got = order.main_bp.get_system_from_label(switch_label)
        id = systems_got['id']
        sn = systems_got['sn']
        deploy_mode = systems_got['deploy_mode']
        add_spec.append({
            'id': id,
            'deploy_mode': 'deploy',
            'system_id': system_snapshot[switch_label],
        })
    device_added = order.main_bp.patch_nodes(add_spec)



    # add_device_to_bp(order.main_bp, order.switch_label_pair)


def main(yaml_in_file):
    from consolidation import ConsolidationOrder
    order = ConsolidationOrder(yaml_in_file)
    move_device(order)


if __name__ == '__main__':
    log_level = logging.DEBUG
    prep_logging(log_level)
    main('./tests/fixtures/config.yaml')    
