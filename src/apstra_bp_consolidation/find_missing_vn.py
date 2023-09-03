import click
import logging

from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint
from apstra_bp_consolidation.consolidation import ConsolidationOrder


@click.command(name='find-missing-vns', help='find the virtual networks absent in main blueprint but present in tor blueprints')
def find_missing_vn():
    order = ConsolidationOrder()
    order_find_missing_vn(order)

def order_find_missing_vn(order):
    logging.info(f"======== Finding Missing VN from {order.main_bp.label}")

    VN_ID = 'virtual_network'
    main_vni_list = []
    all_vn_query = f"node('{VN_ID}', name='{VN_ID}')"
    main_vn_nodes = order.main_bp.query(all_vn_query)
    for vn_node in main_vn_nodes:
        # logging.debug(f"{vn_node=}")
        vni = vn_node[VN_ID]['vn_id']
        vni in main_vni_list or main_vni_list.append(vni)
    logging.info(f"{len(main_vni_list)=}")

    bp_list = order.session.list_blueprint_ids()
    logging.debug(f"{bp_list=}")
    for bp_id in bp_list:
        this_bp = CkApstraBlueprint(order.session, None, bp_id)
        logging.debug(f"checking BP {this_bp.label}")
        this_vni_nodes = this_bp.query(all_vn_query)
        missing_vns = []
        for vn_node in this_vni_nodes:
            vni = vn_node[VN_ID]['vn_id']
            if vni not in main_vni_list:
                missing_vns.append(vni) 
        if len(missing_vns) > 0:
            logging.warning(f"BP {this_bp.label} {len(missing_vns)=} {missing_vns=}")






