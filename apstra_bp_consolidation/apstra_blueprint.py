#!/usr/bin/env python3

import yaml

from apstra_bp_consolidation.apstra_session import CkApstraSession


def pretty_yaml(data: dict, label: str) -> None:
    print(f"==== {label}\n{yaml.dump(data)}\n====")


class CkApstraBlueprint:

    def __init__(self, session: CkApstraSession, label: str) -> None:
        """
        Initialize a CkApstraBlueprint object.

        Args:
            session: The Apstra session object.
            label: The label of the blueprint.
        """
        self.session = session
        self.label = label
        self.id = None
        self.get_id()
        self.url_prefix = f"{self.session.url_prefix}/blueprints/{self.id}"

        self.system_id_cache = {} # { system_label: { id: id, interface_map_id: id, device_profile_id: id }

    def get_id(self) -> str:
        """
        Get the ID of the blueprint.

        Returns:
            The ID of the blueprint.
        """
        url = f"{self.session.url_prefix}/blueprints"
        blueprints = self.session.session.get(url).json()['items']
        for blueprint in blueprints:
            if blueprint['label'] == self.label:
                self.id = blueprint['id']
                break
        if self.id is None:
            raise ValueError(f"Blueprint '{self.label}' not found.")
        return self.id

    def print_id(self) -> None:
        """
        Print the ID of the blueprint.
        """
        print(f"Blueprint ID: {self.id}")

    def query(self, query: str, print_prefix: str = None) -> list:
        """
        Query the Apstra API.

        Args:
            query: The query string.

        Returns:
            The results of the query.
        """
        if print_prefix is not None:
            print(f"== BP.query() {print_prefix}: {query}")
        url = f"{self.url_prefix}/qe"
        payload = {
            "query": query
        }
        response = self.session.session.post(url, json=payload)
        # print (f"{query=}, {response.json()=}")
        # the content should have 'items'. otherwise, the query would be invalid
        return response.json()['items']
    
    # return the first entry for the system
    def get_system_with_im(self, system_label):
        system_im = self.query(f"node('system', label='{system_label}', name='system').out().node('interface_map', name='im')")[0]
        if system_label not in self.system_id_cache:
            self.system_id_cache[system_label] = system_im['system']['id']
            if  'interface_map_id' not in self.system_id_cache[system_label]:
                self.system_id_cache[system_label]['interface_map_id'] = system_im['im']['id']
                self.system_id_cache[system_label]['device_profile_id'] = system_im['im']['device_profile_id']
        return system_im

    def get_system_id(self, system_label):
        # cache the id of the system_label if not already cached
        if system_label not in self.system_id_cache:
            system_query_result = self.query(f"node('system', label='{system_label}', name='system')")
            # skip if the system does not exist
            if len(system_query_result) == 0:
                return None            
            self.system_id_cache[system_label] = { 'id': system_query_result[0]['system']['id'] }
        return self.system_id_cache[system_label]['id']

    def add_generic_system(self, gs_spec: dict) -> list:
        """
        Add a generic system (and access switch pair) to the blueprint.

        Args:
            gs_spec: The specification of the generic system.

        Returns:
            The ID of the switch-system-link ids.
        """
        print(f"==== BP: add_generic_system(): {gs_spec['links']=}")
        existing_system_query = f"node('system', label='{gs_spec['new_systems'][0]['label']}', name='system')"
        print(f"====== BP: add_generic_system(): {existing_system_query=}")
        existing_system = self.query(existing_system_query)
        if len(existing_system) > 0:
            print(f"====== BP: skipping: add_generic_system(): System already exists: {gs_spec['new_systems'][0]['label']=}")
            return []
        url = f"{self.url_prefix}/switch-system-links"
        created_generic_system = self.session.session.post(url, json=gs_spec)
        if created_generic_system is None or len(created_generic_system.json()) == 0 or 'ids' not in created_generic_system.json():
            # print(f"add_generic_system(): System not created: {created_generic_system=} for {gs_spec=}")
            # pretty_yaml(gs_spec, "failed spec()")
            return []
        return created_generic_system.json()['ids']

    def get_transformation_id(self, system_label, intf_name, speed) -> int:
        '''
        Get the transformation ID for the interface

        Args:
            system_label: The label of the system
            intf_name: The name of the interface
            speed: The speed of the interface in the format of '10G'
        '''
        system_im = self.get_system_with_im(system_label)
        device_profile = self.session.get_device_profile(system_im['im']['device_profile_id'])

        for port in device_profile['ports']:
            for transformation in port['transformations']:
                # self.logger.debug(f"{transformation=}")
                for intf in transformation['interfaces']:
                    # if intf['name'] == intf_name:
                    #     self.logger.debug(f"{intf=}")
                    if intf['name'] == intf_name and intf['speed']['unit'] == speed[-1:] and intf['speed']['value'] == int(speed[:-1]): 
                        # self.logger.warning(f"{intf_name=}, {intf=}")
                        return transformation['transformation_id']

    def patch_leaf_server_link(self, link_spec: dict) -> None:
        """
        Patch a leaf-server link.

        Args:
            link_spec: The specification of the leaf-server link.
        """
        url = f"{self.url_prefix}/leaf-server-link-labels"
        self.session.session.patch(url, json=link_spec)

    def patch_obj_policy_batch_apply(self, policy_spec, params=None):
        '''
        Apply policies in a batch
        '''
        return self.session.session.patch(f"{self.url_prefix}/obj-policy-batch-apply", json=policy_spec, params=params)

    def patch_node(self, node, patch_spec, params=None):
        '''
        Patch node data
        '''
        return self.session.session.patch(f"{self.url_prefix}/nodes/{node}", json=patch_spec, params=params)


    def batch(self, batch_spec: dict, params=None) -> None:
        '''
        Run API commands in batch
        '''
        url = f"{self.url_prefix}/batch"
        self.session.session.post(url, json=batch_spec, params=params)

    def cts_single_ae_generic_system(self, gs_label) -> list:
        '''
        Get the CTS of generic system with single AE
        '''
        ct_list_spec = f"match(node('system', label='{gs_label}').out().node('interface', if_type='port_channel', name='ae2').out().node('link').in_().node(name='ae1').out().node('ep_group').in_().node('ep_application_instance').out().node('ep_endpoint_policy', policy_type_name='batch', name='batch').where(lambda ae1, ae2: ae1 != ae2 )).distinct(['batch'])"
        ct_list = [ x['batch']['id'] for x in self.query(ct_list_spec) ]
        return ct_list

    def revert(self):
        '''
        Revert the blueprint
        '''
        url = f"{self.url_prefix}/revert"
        revert_result = self.session.session.post(url, json="", params={"aync": "full"})
        print(f"Revert result: {revert_result.json()}")


if __name__ == "__main__":
    apstra = CkApstraSession("10.85.192.50", 443, "admin", "zaq1@WSXcde3$RFV")
    bp = CkApstraBlueprint(apstra, "pslab")
    bp.print_id()

