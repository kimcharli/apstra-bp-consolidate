#!/usr/bin/env python3

import json
import logging

from consolidation import prep_logging
from consolidation import ConsolidationOrder

# keeping here to use later
def deep_diff(dict1, dict2, path=""):
    differences = []

    # If both are dictionaries, recurse
    if isinstance(dict1, dict) and isinstance(dict2, dict):
        # Check for keys in dict1 that are not in dict2
        for key in dict1:
            if key not in dict2:
                differences.append(f"Key '{key}' at path '{path}' present in <A>, but not in <B>.")
            else:
                # If key is in both dictionaries, recurse down
                new_path = f"{path}/{key}" if path else key
                differences.extend(deep_diff(dict1[key], dict2[key], new_path))
        
        # Check for keys in dict2 that are not in dict1
        for key in dict2:
            if key not in dict1:
                differences.append(f"Key '{key}' at path '{path}' present in <B>, but not in <A>.")
    
    # If both are lists, compare items
    elif isinstance(dict1, list) and isinstance(dict2, list):
        dict1_sorted = sorted(dict1, key=str)
        dict2_sorted = sorted(dict2, key=str)
        
        for i, (item1, item2) in enumerate(zip(dict1_sorted, dict2_sorted)):
            new_path = f"{path}[{i}]"
            differences.extend(deep_diff(item1, item2, new_path))
        
        if len(dict1_sorted) != len(dict2_sorted):
            diff = len(dict1_sorted) - len(dict2_sorted)
            if diff > 0:
                differences.append(f"List at path '{path}' in <A> has {diff} more items than in <B>.")
            else:
                differences.append(f"List at path '{path}' in <B> has {-diff} more items than in <A>.")
    
    # If neither a dict nor a list, just compare
    else:
        if dict1 != dict2:
            differences.append(f"Different values at path '{path}': <A> has '{dict1}' vs <B> has '{dict2}'.")

    return differences


def pull_vni_ids(the_bp, switch_label_pair: list) -> list:
    """
    Pull the vni ids for the switch pair

    """
    my_logger = logging.getLogger()

    my_logger.debug(f"pulling vni ids for {switch_label_pair=} from {the_bp.label}")
    vn_list_query = f"""
        match(
            node('system', label=is_in({switch_label_pair}))
            .out().node('vn_instance')
            .out().node('virtual_network', name='vn')
        ).distinct(['vn'])"""
    vn_list = the_bp.query(vn_list_query)
    vni_list = [ x['vn']['vn_id'] for x in vn_list ]
    my_logger.debug(f"found {len(vni_list)=}")
    return vni_list

def access_switch_assign_vns(the_bp, vni_list: list, switch_label_pair: list):
    """
    Assign VN to the access switch pair
    """
    my_logger = logging.getLogger()

    my_logger.debug(f"assigning vni ids for {switch_label_pair=} {vni_list[0]=}")

    # get the redundancy group id of the access switch pair and the leaf switch pair
    rg_query = f"""node(type='redundancy_group', name='rg')
        .in_().node('system', label=is_in({switch_label_pair}), name='n1')
        .out().node('interface')
        .out().node('link')
        .in_().node('interface')
        .in_().node('system', role='leaf')
        .out().node(type='redundancy_group', name='leaf-rg')"""
    rg_got = the_bp.query(rg_query, multiline=True)
    if len(rg_got) == 0:
        my_logger.warning(f"access_switch_assign_vns() {switch_label_pair=} not found")
        return
    rg_id = rg_got[0]['rg']['id']
    leaf_rg_id = rg_got[0]['leaf-rg']['id']
    total_vni = len(vni_list)
    total_updated = 0
    total_skipped = 0
    total_leaf_missing = 0


    # iterate vni list
    for vni_index in range(total_vni):
        vni = vni_list[vni_index]
        vni_count = vni_index + 1
        modified = False
        leaf_found = False
        # get the vn spec from the staged data
        vn_spec = the_bp.get_virtual_network(vni)
        # iterate bound_to and add the access switch pair to the upstream leaf pair
        for bound_to_index in range(len(vn_spec['bound_to'])):
            this_bound_to = vn_spec['bound_to'][bound_to_index]
            if this_bound_to['system_id'] == leaf_rg_id:
                leaf_found = True
                # it is already there
                if rg_id in this_bound_to['access_switch_node_ids']:
                    break
                # 
                this_bound_to['access_switch_node_ids'].append(rg_id)
                modified = True
                break
        if modified:
            my_logger.debug(f"{vni_count}/{total_vni} {vni=} -- updating")
            total_updated += 1
        elif leaf_found:
            my_logger.debug(f"{vni_count}/{total_vni} {vni=} already in - skipping")
            total_skipped += 1
            continue
        else:
            my_logger.warning(f"{vni_count}/{total_vni} {vni=} leaf_pair not found -- skipping")
            total_leaf_missing += 1
            continue

        # endpoint would fail due to missing label
        del vn_spec['endpoints']
        vn_patched = the_bp.patch_virtual_network(vn_spec)
        my_logger.debug(f"{vni_count}/{total_vni} {vni=}, {vn_patched=}")
    
    my_logger.info(f"{switch_label_pair=} {total_vni=}, {total_updated=}, {total_skipped=}, {total_leaf_missing=}")

def main(yaml_in_file):
    order = ConsolidationOrder(yaml_in_file)

    ########
    # assign virtual networks
    vni_list = pull_vni_ids(order.tor_bp, order.switch_label_pair)

    # assign connectivity templates
    access_switch_assign_vns(order.main_bp, vni_list, order.switch_label_pair)


if __name__ == '__main__':
    log_level = logging.DEBUG
    prep_logging(log_level)
    main('./tests/fixtures/config.yaml')    
