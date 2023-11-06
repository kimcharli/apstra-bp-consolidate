# apstra-bp-consolidate

## python version: 3.9
```
ckim@ckim-mbp apstra-bp-consolidate % python3.9 -m venv .venv
ckim@ckim-mbp apstra-bp-consolidate % 
ckim@ckim-mbp apstra-bp-consolidate % 
ckim@ckim-mbp apstra-bp-consolidate % source .venv/bin/activate
(.venv) ckim@ckim-mbp apstra-bp-consolidate % 
(.venv) ckim@ckim-mbp apstra-bp-consolidate % pip install -e .
```


## run command

edit env files

tests/fixtures/.env 
```
apstra_server_host=nf-apstra.pslab.link
apstra_server_port=443
apstra_server_username=admin
apstra_server_password=zaq1@WSXcde3$RFV
config_yaml_input_file=tests/fixtures/config.yaml
logging_level=DEBUG
cabling_maps_yaml_file=tests/fixtures/sample-cabling-maps.yaml
```

tests/fixtures/config.yaml 
```
---
blueprint:
  main:
    name: ATLANTA-Master
  tor:
    name: AZ-1_1-R5R15
    torname: atl1tor-r5r15 # the generic system name to be removed in the main blueprint 
    switch_names: [ atl1tor-r5r15a, atl1tor-r5r15b ]
    new_interface_map: _ATL-AS-5120-48T
```


```
logging_level=INFO consolidation-helper move-virtual-networks 
```


## venv for tox and build

```
python3.9 -m venv ~/venv/tox-build
source ~/venv/tox-build/bin/activate
pip install tox build
pip install --upgrade pip
deactivate
```


## run test

```
source ~/venv/tox-build/bin/activate
tox
deactivate
```

## run build package
```
source ~/venv/tox-build/bin/activate
python -m build
deactivate
```