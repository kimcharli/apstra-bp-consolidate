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