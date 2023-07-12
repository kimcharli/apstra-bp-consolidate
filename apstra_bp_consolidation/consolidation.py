#!/usr/bin/env python3

from apstra_bp_consolidation.apstra_session import CkApstraSession
from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint











def main(apstra: str, config: dict):
    print(f"{config=}")

    main_bp = CkApstraBlueprint(apstra, config['blueprint']['main']['name'])
    tor_bp = CkApstraBlueprint(apstra, config['blueprint']['tor']['name'])

    # revert any staged changes
    # main_bp.revert()

    # delete the old generic system
    # all the CTs on old generic system are on the AE link
    old_generic_system = config['blueprint']['tor']['torname']
    old_generic_system_ae_id_list = main_bp.query(f"node('system', label='{old_generic_system}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').where(lambda ae1, ae2: ae1 != ae2 )")
    if len(old_generic_system_ae_id_list) == 0:
        print(f"Generic system {old_generic_system} not found")
        return
    old_generic_system_ae_id = main_bp.query(f"node('system', label='{old_generic_system}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').where(lambda ae1, ae2: ae1 != ae2 )")[0]['ae1']['id']
    print(f"{old_generic_system_ae_id=}")
    cts = main_bp.cts_single_ae_generic_system(old_generic_system)

    old_generic_system_physical_links = main_bp.query(f"node('system', label='{old_generic_system}').out().node('interface', if_type='ethernet').out().node('link', name='link')")

    # damping CTs in chunks
    while len(cts) > 0:
        cts_chunk = cts[:50]
        print(f"{cts_chunk=} ({len(cts_chunk)})")
        batch_ct_spec = {
            "operations": [
                {
                    "path": "/obj-policy-batch-apply",
                    "method": "PATCH",
                    "payload": {
                        "application_points": [
                            {
                                "id": old_generic_system_ae_id,
                                "policies": [ {"policy": x, "used": False} for x in cts_chunk]
                            }
                        ]
                    }
                }
            ]
        }
        batch_result = main_bp.batch(batch_ct_spec, params={"comment": "batch-api"})
        del cts[:50]

    batch_link_spec = {
        "operations": [
            {
                "path": "/delete-switch-system-links",
        		"method": "POST",
                "payload": {
                    "link_ids": [ x['link']['id'] for x in old_generic_system_physical_links ]
                }
            }
        ]
    }
    batch_result = main_bp.batch(batch_link_spec, params={"comment": "batch-api"})
    print(f"{batch_result=}")


    # create new access system pair
    logical_device_list = tor_bp.query("node('system', name='system', role=not_in(['generic'])).out().node('logical_device', name='ld')")
    logical_device_id = logical_device_list[0]['ld']['id']

    # et-0/0/48-a - et-0/0/22 lef15
    # et-0/0/48-b - et-0/0/23 lef15
    # et-0/0/49-a - et-0/0/22 lef16
    # et-0/0/49-b - et-0/0/23 lef16

    # et-0/0/48-a - et-0/0/0 lef15
    # et-0/0/48-b - et-0/0/1 lef15
    # et-0/0/49-a - et-0/0/0 lef16
    # et-0/0/49-b - et-0/0/1 lef16


    # LD _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # IM _ATL-AS-Q5100-48T, _ATL-AS-5120-48T created
    # rack type _ATL-AS-5100-48T, _ATL-AS-5120-48T created and added
    # ATL-AS-LOOPBACK with 10.29.8.0/22





    # create new generic systems

    # assign virtual networks
    vn_list = tor_bp.query(f"node('system', name='system', role=not_in(['generic'])).out().node('vn_instance').out().node('virtual_network', name='vn')")
    # print(f"{vn_list=}")

    # assign connectivity templates

    pass

if __name__ == "__main__":
    import yaml

    with open('./tests/fixtures/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    apstra = CkApstraSession("10.85.192.61", 443, "admin", "zaq1@WSXcde3$RFV")
    main(apstra, config)

