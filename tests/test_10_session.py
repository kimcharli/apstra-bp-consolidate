from apstra_bp_consolidation.apstra_session import CkApstraSession

def test_10_session(var_global):
    apstra = CkApstraSession(
        var_global.apstra_host, 
        var_global.apstra_port, 
        var_global.apstra_user, 
        var_global.apstra_password)
    apstra.print_token()
