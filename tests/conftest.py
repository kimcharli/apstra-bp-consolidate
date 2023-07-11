import pytest

class Data:
    apstra_host: str = '10.85.192.61'  # 4.1.2
    apstra_port: int = 443
    apstra_user: str = 'admin'
    apstra_password: str = 'zaq1@WSXcde3$RFV'

@pytest.fixture(scope="module")
def var_global():
    return Data()





