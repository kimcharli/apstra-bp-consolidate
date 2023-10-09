#!/usr/bin/env python3

# *******************************************************************************
#
#  Author        : Juniper Networks Professional Services
#  Version       : 1.0
#  Platform      : Python, Any OS platform  (tested on Python 3.9)
#  Release       : FOR INTERNAL USE ONLY
#  Description   : Python script to extract switch configuration information from
#                  the Apstra.  The information extracted will be used to recreate
#                  the switch in the 'ATLANTA-Master' blueprint.
#
#  Revision History:
#  1.0  06/Oct/2023 - initial release
#  1.1    /Oct/2023 -
#
# *******************************************************************************
#
#  Copyright (c) 2023  Juniper Networks. All Rights Reserved.
#
#  YOU MUST ACCEPT THE TERMS OF THIS DISCLAIMER TO USE THIS SOFTWARE
#
#  JUNIPER IS WILLING TO MAKE THE INCLUDED SCRIPTING SOFTWARE AVAILABLE TO YOU
#  ONLY UPON THE CONDITION THAT YOU ACCEPT ALL OF THE TERMS CONTAINED IN THIS
#  DISCLAIMER. PLEASE READ THE TERMS AND CONDITIONS OF THIS DISCLAIMER
#  CAREFULLY.
#
#  THE SOFTWARE CONTAINED IN THIS FILE IS PROVIDED "AS IS." JUNIPER MAKES NO
#  WARRANTIES OF ANY KIND WHATSOEVER WITH RESPECT TO SOFTWARE. ALL EXPRESS OR
#  IMPLIED CONDITIONS, REPRESENTATIONS AND WARRANTIES, INCLUDING ANY WARRANTY
#  OF NON-INFRINGEMENT OR WARRANTY OF MERCHANTABILITY OR FITNESS FOR A
#  PARTICULAR PURPOSE, ARE HEREBY DISCLAIMED AND EXCLUDED TO THE EXTENT
#  ALLOWED BY APPLICABLE LAW.
#
#  IN NO EVENT WILL JUNIPER BE LIABLE FOR ANY LOST REVENUE, PROFIT OR DATA, OR
#  FOR DIRECT, SPECIAL, INDIRECT, CONSEQUENTIAL, INCIDENTAL OR PUNITIVE
#  DAMAGES HOWEVER CAUSED AND REGARDLESS OF THE THEORY OF LIABILITY ARISING
#  OUT OF THE USE OF OR INABILITY TO USE THE SOFTWARE, EVEN IF JUNIPER HAS
#  BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
#
# *******************************************************************************

import sys
import json
import re
import requests
import hashlib
import argparse
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from pprint import pprint as pp


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

bp_system_info= {}
bp_consolidate_info= {}
if_prefix= 'IF-'
ip_prefix= 'IP-'



def auth(url, user, password):

    """
    Retrieve the API authentication token.
    """

    auth_resp= requests.post(\
        f"{url}/api/aaa/login",\
        json={"username": user, "password": password},\
        verify= False,\
        timeout= 3\
    ).json()
    return auth_resp["token"]


def bp_id(url,token,bp_name):

    """
    Retrieve the blueprint ID for a given blueprint name.
    """

    bp_ids= requests.get(\
        f"{url}/api/blueprints",\
        headers= { "AuthToken": token },\
        verify= False,\
        timeout= 3\
    ).json()['items']
    for i in bp_ids:
        if i['label'] == bp_name:
            bp_id= i['id']
    return bp_id


def configlet_prop(url,token,bp_id):

    """
    Retrieve a list of configured configlets in a blueprint.
    """

    configlets_lst= requests.get(
        f"{url}/api/blueprints/{bp_id}/configlets", 
        headers= { "AuthToken": token },
        verify= False,
        timeout= 3,
    ).json()['items']
    return configlets_lst


def bp_ct_prop(url,token,bp_id,qe):

    """
    Retrieve a list of connectivity templates configured in a blueprint.
    """

    bp_ct_info_lst = requests.post(\
        f"{url}/api/blueprints/{bp_id}/qe",\
        data=qe,\
        headers={"AuthToken": token},\
        verify=False,\
        timeout=3\
    ).json()['items']
    return bp_ct_info_lst


def bp_switch_properties(url,token,bp_id):

    """
    Create a dictionary with retrieved switch specific configuration information.
    """

    print("\nStart:\t\tblueprint switch information collection.")

    bp_consolidate_info['systems'] = {}

    bp_sw_qe= json.dumps(\
        {\
            'query': "node('system',name='system',system_type='switch')"\
        }\
    ).replace('"','\"')

    bp_switches_list= requests.post(\
        f"{url}/api/blueprints/{bp_id}/qe",\
        data= bp_sw_qe,\
        headers= { "AuthToken": token },\
        verify= False,\
        timeout= 3\
    ).json()['items']

    for sys in bp_switches_list:
        bp_system_info[sys['system']['hostname']]= sys['system']['system_id']
        bp_consolidate_info['systems'][sys['system']['hostname']]= { 'system_id': sys['system']['system_id'],'role': sys['system']['role'],'deploy_mode': sys['system']['deploy_mode'] }

    for hst in bp_system_info.keys():
        sys_facts= requests.get(\
            f"{url}/api/systems/{bp_system_info[hst]}",\
            headers= { "AuthToken": token },\
            verify= False,\
            timeout= 3
        ).json()
        bp_consolidate_info['systems'][hst]['facts'] = sys_facts['facts']

        bp_sys_conf_cnxt= json.loads(\
            requests.get(\
                f"{url}/api/blueprints/{bp_id}/systems/{bp_system_info[hst]}/config-context",\
                headers= { "AuthToken": token },\
                verify= False,\
                timeout= 3\
            ).json()['context']\
        )
        bp_consolidate_info['systems'][hst]['interfaces']= { inf[3:]: None for inf in bp_sys_conf_cnxt['interface'].keys() }
        bp_consolidate_info['systems'][hst]['device_profile_id']=  bp_sys_conf_cnxt['hcl']
        bp_consolidate_info['systems'][hst]["lo0_ipv4_address"]= bp_sys_conf_cnxt['lo0_ipv4_address']
        bp_consolidate_info['systems'][hst]["dhcp_servers"]= bp_sys_conf_cnxt['dhcp_servers']
        bp_consolidate_info['systems'][hst]["loopbacks"]= bp_sys_conf_cnxt['loopbacks']
        bp_consolidate_info['systems'][hst]["vrf"]= bp_sys_conf_cnxt['security_zones']
        bp_consolidate_info['systems'][hst]["bgp"]= bp_sys_conf_cnxt['bgpService']
        bp_consolidate_info['systems'][hst]["routing"]= bp_sys_conf_cnxt['routing']
        bp_consolidate_info['systems'][hst]["bgp"]["sessions"]= bp_sys_conf_cnxt['bgp_sessions']
        bp_consolidate_info['systems'][hst]["management_ip"]= bp_sys_conf_cnxt['management_ip']

        bp_ifl_map_qe= json.dumps(
            {\
                'query': f"node('system',system_type='switch',system_id='{bp_system_info[hst]}')\
                    .out('interface_map')\
                    .node('interface_map',name='interface_map')"\
            }\
        ).replace('"','\"')
        bp_ifl_map_list= requests.post(\
            f"{url}/api/blueprints/{src_bp_id}/qe",\
            data=bp_ifl_map_qe,\
            headers= { "AuthToken": token },\
            verify= False,\
            timeout= 3\
        ).json()['items']
        bp_consolidate_info['systems'][hst]["interface_map"]= bp_ifl_map_list[0]['interface_map']['label']

        for ifl in bp_consolidate_info['systems'][hst]['interfaces'].keys():
            bp_consolidate_info['systems'][hst]['interfaces'][ifl]= \
                {\
                    "native_vlan":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['native_vlan'],\
                    "description":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['description'],\
                    "vrf_name":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['vrf_name'],\
                    "lag_mode":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['lag_mode'],\
                    "mtu":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['mtu'],\
                    "evpn_esi":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['evpn_esi'],\
                    "lacp_system_id":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['lacp_system_id'],\
                    "switch_port_mode":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['switch_port_mode'],\
                    "part_of":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['part_of'],\
                    "composed_of":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['composed_of'],\
                    "allowed_vlans":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['allowed_vlans'],\
                    "tags":bp_sys_conf_cnxt['ip'][ip_prefix+ifl]['interface']['tags'],\
                    "ipv4_address":bp_sys_conf_cnxt['ip'][ip_prefix+ifl]['ipv4_address'],\
                    "operation_state":bp_sys_conf_cnxt['interface'][if_prefix+ifl]['operation_state']\
                }

    print("\nComplete:\tblueprint switch information collection.")


def bp_configlet_properties(url,token,src_bp_id,dst_bp_id):

    """
    Expand dictionary with configlet information as used in the blueprint.
    """

    print("\nStart:\t\tblueprint configlet information collection.")

    bp_consolidate_info['configlets']= []
    gl_ctlg_configlet_csum= {}
    dst_bp_configlet_csum= {}

    gbl_configlets= requests.get(\
        f"{url}/api/design/configlets",\
        headers= { "AuthToken": token },\
        verify= False,\
        timeout= 3\
    ).json()

    for cfgl in gbl_configlets['items']:
        for tmpl in cfgl['generators']:
            gl_ctlg_configlet_csum[cfgl['display_name']]= hashlib.md5(tmpl['template_text'].encode()).hexdigest()

    dst_bp_configlet = configlet_prop(url,token,dst_bp_id)
    for cfgl in dst_bp_configlet:
        for tmpl in cfgl['configlet']['generators']:
            dst_bp_configlet_csum[cfgl['configlet']['display_name']]= hashlib.md5(tmpl['template_text'].encode()).hexdigest()

    src_bp_configlet = configlet_prop(url,token,src_bp_id)
    for cnfl in src_bp_configlet:
        for genrtr in cnfl['configlet']['generators']:
            config_style = genrtr['config_style']
            section = genrtr['section']
            tmplt_txt = genrtr['template_text']
            tmplt_txt_md5 = hashlib.md5(tmplt_txt.encode()).hexdigest()
            if tmplt_txt_md5 in gl_ctlg_configlet_csum.values():
                gl_ctlg_match= True
            else:
                gl_ctlg_match= False
            if tmplt_txt_md5 in dst_bp_configlet_csum.values():
                dst_bp_ctlg_match= True
            else:
                dst_bp_ctlg_match= False
            bp_consolidate_info['configlets'].append( \
                {\
                    'display_name': cnfl['configlet']['display_name'],\
                    'condition': cnfl['condition'],\
                    'config_style': config_style,\
                    'section': section,\
                    'tmplt_txt_md5': tmplt_txt_md5,\
                    'tmplt_txt': tmplt_txt,\
                    'gl_ctlg_match': gl_ctlg_match,\
                    'dst_bp_match':dst_bp_ctlg_match\
                }\
            )

    print("\nComplete:\tblueprint configlet information collection.")


def sz_properties(url,token,bp_id):

    """
    Retrieve and add rouitng instance information for a blueprint.
    """

    print("\nStart:\t\tblueprint routing-zone information collection.")

    bp_consolidate_info['security_zone']= []

    bp_sz = requests.get(\
        f"{url}/api/blueprints/{bp_id}/security-zones",\
        headers= { "AuthToken": token },\
        verify= False,\
        timeout= 3\
    ).json()['items']

    for sz in bp_sz:
        bp_consolidate_info['security_zone'].append( \
            {\
                'vrf_name': bp_sz[sz]['vrf_name'],\
                'sz_type': bp_sz[sz]['sz_type'],\
                'vni_id': bp_sz[sz]['vni_id'],\
                'vlan_id': bp_sz[sz]['vlan_id'],\
                'route_target':bp_sz[sz]['route_target'],\
                'rt_policy':bp_sz[sz]['rt_policy']\
            }\
        )

    print("\nComplete:\tblueprint routing-zone information collection.")


def gs_properties(url,token,bp_id):

    """
    Retrieve Generic System (GS) connectivity information relating switch connections.
    """

    print("\nStart:\t\tblueprint generic system information collection.")

    bp_consolidate_info['generic_systems']= {}

    for v in bp_system_info.values():
        gs_qry_data_str= json.dumps( 
            {\
                'query':f"node('logical_device',name='log_dev')\
                    .in_('logical_device')\
                    .node('system', system_type='server', name='srvr')\
                    .out('hosted_interfaces')\
                    .node('interface', if_name=ne('ipmi/idrac'),name='srvr_inf')\
                    .out('link')\
                    .node('link', name='link')\
                    .in_('link')\
                    .node('interface', name='sw_inf')\
                    .in_('hosted_interfaces')\
                    .node('system',system_id='{v}',name='switch')"\
            }\
        ).replace('"','\"')

        bp_gs_info_list= requests.post(\
            f"{url}/api/blueprints/{bp_id}/qe",\
            data= gs_qry_data_str,\
            headers= { "AuthToken": token },\
            verify= False,\
            timeout= 3\
        ).json()['items']

        qry_data_str= json.dumps( \
            {\
                'query':f"node('system',system_type='switch',system_id='{v}')\
                    .out('hosted_interfaces')\
                    .node('interface',if_type='port_channel',name='ifl')\
                    .out('composed_of')\
                    .node('interface',name='ifd')"\
            }\
        ).replace('"','\"')

        lag_lnks_list= requests.post(\
            f"{url}/api/blueprints/{bp_id}/qe",\
            data= qry_data_str,\
            headers= { "AuthToken": token },\
            verify= False,\
            timeout= 3\
        ).json()['items']

        for gs in bp_gs_info_list:
            for lg in lag_lnks_list:
                if lg['ifd']['if_name'] == gs['sw_inf']['if_name']:
                    aggr_lnk = lg['ifl']['if_name']
                    break
                else:
                    aggr_lnk = ''
            if not gs['srvr']['label'] in bp_consolidate_info['generic_systems'].keys():
                bp_consolidate_info['generic_systems'][gs['srvr']['label']]= \
                    {\
                        gs['link']['id']: {\
                            'gs_if_name':gs['srvr_inf']['if_name'],\
                            'sw_if_name': gs['sw_inf']['if_name'],\
                            'sw_label': gs['switch']['label'],\
                            'log_dev': gs['log_dev']['label'],\
                            'speed': gs['link']['speed'],\
                            'aggregate_link': aggr_lnk,\
                            'tags': gs['link']['tags']\
                        }\
                    }
            else:
                bp_consolidate_info['generic_systems'][gs['srvr']['label']][gs['link']['id']]=\
                    {\
                        'gs_if_name': gs['srvr_inf']['if_name'],\
                        'sw_if_name': gs['sw_inf']['if_name'],\
                        'sw_label': gs['switch']['label'],\
                        'log_dev': gs['log_dev']['label'],\
                        'speed': gs['link']['speed'],\
                        'aggregate_link': aggr_lnk,\
                        'tags':gs['link']['tags']\
                    }

    print("\nComplete:\tblueprint generic system information collection.")


def vn_properties(url,token,bp_id):

    """
    Retrieve VLAN configuration for a bleuprint and add to the dictionary.
    """

    print("\nStart:\t\tblueprint virtual networks information collection.")

    bp_consolidate_info['virtual_networks']= {}
    
    for v in bp_system_info.values():
        bp_sys_conf_cnxt= json.loads( \
            requests.get(\
                f"{url}/api/blueprints/{bp_id}/systems/{v}/config-context",\
                headers= { "AuthToken": token },\
                verify= False,\
                timeout= 3\
            ).json()['context']\
        )
        bp_consolidate_info['virtual_networks'][bp_sys_conf_cnxt['hostname']]= \
            { inf[3:]: None for inf in bp_sys_conf_cnxt['interface'].keys() if 'ae' not in inf }

        for nvl in bp_sys_conf_cnxt['interface'].keys():
            if 'ae' not in nvl:
                if bp_sys_conf_cnxt['interface'][nvl]['native_vlan'] != '' or bp_sys_conf_cnxt['interface'][nvl]['allowed_vlans'] != []:
                    bp_consolidate_info['virtual_networks'][bp_sys_conf_cnxt['hostname']][nvl[3:]]= \
                        {\
                            'untagged_vlan': bp_sys_conf_cnxt['interface'][nvl]['native_vlan'],\
                            'tagged_vlans':bp_sys_conf_cnxt['interface'][nvl]['allowed_vlans']\
                        }
                else:
                    del(bp_consolidate_info['virtual_networks'][bp_sys_conf_cnxt['hostname']][nvl[3:]])
            elif 'ae' in nvl:
                if not 'redundancy_group' in bp_consolidate_info['virtual_networks'].keys():
                    bp_consolidate_info['virtual_networks']['redundancy_group']= {}
                if nvl[3:] in bp_consolidate_info['virtual_networks']['redundancy_group'].keys():
                    bp_consolidate_info['virtual_networks']['redundancy_group'][nvl[3:]]['member_interfaces'][bp_sys_conf_cnxt['hostname']]= \
                        bp_sys_conf_cnxt['interface'][nvl]['composed_of']
                else:
                    bp_consolidate_info['virtual_networks']['redundancy_group'][nvl[3:]]= \
                        {\
                            'untagged_vlan': bp_sys_conf_cnxt['interface'][nvl]['native_vlan'],\
                            'tagged_vlans':bp_sys_conf_cnxt['interface'][nvl]['allowed_vlans'],\
                            'member_interfaces': { bp_sys_conf_cnxt['hostname']: bp_sys_conf_cnxt['interface'][nvl]['composed_of']}\
                        }

    print("\nComplete:\tblueprint virtual networks information collection.")


def bp_connectivity_template_properties(url,token,src_bp_id,dst_bp_id):

    """
    Retrieve the connectivity template configuration for blueprint.
    """

    print("\nStart:\t\tblueprint connectivity templates information collection.")

    bp_consolidate_info['ct']= {}
    bp_consolidate_info['ct']['no_match']= []
    dst_bp_ct_info_dict= {}

    ct_qry_data_str = json.dumps(\
        {\
            'query':f"node('ep_application_instance')\
                        .out('ep_nested')\
                        .node('ep_endpoint_policy', policy_type_name='batch', name='ct_label')\
                        .out('ep_subpolicy')\
                        .node('ep_endpoint_policy')\
                        .out('ep_first_subpolicy')\
                        .node('ep_endpoint_policy',name='ct_tag_info')\
                        .out('vn_to_attach')\
                        .node('virtual_network',name='vn')"\
        }\
    ).replace('"','\"')

    src_bp_ct_info_list = bp_ct_prop(url,token,src_bp_id,ct_qry_data_str)

    dst_bp_ct_info_list = bp_ct_prop(url,token,dst_bp_id,ct_qry_data_str)

    for dst_ct in dst_bp_ct_info_list:
        dst_bp_ct_lbl= dst_ct['ct_label']['label']
        dst_bp_ct_tag_info= json.loads(dst_ct['ct_tag_info']['attributes'])['tag_type']
        dst_bp_ct_type= dst_ct['ct_tag_info']['policy_type_name']
        dst_bp_ct_vn_id= dst_ct['vn']['vn_id']
        dst_bp_ct_info_dict[dst_bp_ct_vn_id]= { 'label': dst_bp_ct_lbl, 'tag_info': dst_bp_ct_tag_info, 'type': dst_bp_ct_type }

    for src_ct in src_bp_ct_info_list:
        src_bp_ct_tag_info= json.loads(src_ct['ct_tag_info']['attributes'])['tag_type']
        src_bp_ct_type= src_ct['ct_tag_info']['policy_type_name']
        src_bp_ct_vn_id= src_ct['vn']['vn_id']
        if src_bp_ct_vn_id in dst_bp_ct_info_dict.keys():
            if src_bp_ct_tag_info == dst_bp_ct_info_dict[src_bp_ct_vn_id]['tag_info'] and\
               src_bp_ct_type ==  dst_bp_ct_info_dict[src_bp_ct_vn_id]['type']:
                bp_consolidate_info['ct'][src_bp_ct_vn_id]= {'dst_ct':dst_bp_ct_info_dict[src_bp_ct_vn_id]['label']}
            else:
                bp_consolidate_info['ct']['no_match'].append(\
                    {\
                        'src_vn_id':src_bp_ct_vn_id,\
                        'src_tag_type':src_bp_ct_tag_info,\
                    }\
                )
        else:
            bp_consolidate_info['ct']['no_match'].append({'src_vn_id':src_bp_ct_vn_id,'dst_vn_id':'not present'})

    print("\nComplete:\tblueprint connectivity templates information collection.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('aos_server', help='IP Address of AOS Server',)
    parser.add_argument('-u','--username', help='AOS Username (default= admin)',default="admin",required=True)
    parser.add_argument('-p','--password', help='AOS User Password (default= admin)',default="admin",required=True)
    parser.add_argument('-s','--source', help='Source blueprint',required=True)
    args= parser.parse_args()
    aos_url= f"https://{args.aos_server if args.aos_server else '127.0.0.1'}"
    aos_user= args.username if args.username else "admin"
    aos_user_password= args.password if args.password else "admin"
    src_bp_name= args.source
    dst_bp_name= 'ATLANTA-Master'

    token= auth(aos_url,aos_user,aos_user_password)
    src_bp_id= bp_id(aos_url,token,src_bp_name)
    dst_bp_id= bp_id(aos_url,token,dst_bp_name)
    bp_switch_properties(aos_url,token,src_bp_id)
    bp_configlet_properties(aos_url,token,src_bp_id,dst_bp_id)
    sz_properties(aos_url,token,src_bp_id)
    gs_properties(aos_url,token,src_bp_id)
    vn_properties(aos_url,token,src_bp_id)
    bp_connectivity_template_properties(aos_url,token,src_bp_id,dst_bp_id)

    print("\n\tWriting collected Blueprint consolidation information to disk.\n")
    with open(f"./{src_bp_name}_info.json", 'w') as f:
        json.dump(bp_consolidate_info, f)
