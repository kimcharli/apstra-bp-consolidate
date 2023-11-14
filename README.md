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

.env 
```
apstra_server_host=nf-apstra.pslab.link
apstra_server_port=443
apstra_server_username=admin
apstra_server_password=zaq1@WSXcde3$RFV
logging_level=DEBUG
main_bp=ATLANTA-Master
;tor_bp=AZ-1_1-R5R15
tor_bp=AZ-1_1-R5R15
tor_name=atl1tor-r5r15
tor_im_new=_ATL-AS-5120-48T
cabling_maps_yaml_file=tests/fixtures/sample-cabling-maps.yaml
```


```
logging_level=INFO consolidation-helper move-virtual-networks 
```


```
(.venv) ckim@ckim-mbp:apstra-bp-consolidate % consolidation-helper                      
Usage: consolidation-helper [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  collect-cabling-maps   collect the cabling maps from all the blueprints...
  find-missing-vns       find the virtual networks absent in main...
  move-access-switches   step 1 - replace the generic system in main...
  move-all               run all the steps in sequence
  move-cts               step 4 - assign CTs to new generic systems
  move-devices           setp 5 - undeploy device from tor blueprint and...
  move-generic-systems   step 2 - create the generic systems under new...
  move-virtual-networks  step 3 - assign virtual networks to new access...
(.venv) ckim@ckim-mbp:apstra-bp-consolidate % 
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