from apstra_bp_consolidation.apstra_blueprint import CkApstraBlueprint

# def test_12_session(var_global):
#     apstra = CkApstraSession(
#         var_global.apstra_host, 
#         var_global.apstra_port, 
#         var_global.apstra_user, 
#         var_global.apstra_password)
#     apstra.print_token()

def test_12_main_blueprint(session, main_bp):
    bp = CkApstraBlueprint(session, main_bp)
    bp.print_id()
    assert True

def test_13_tor_blurprint(session, tor_bp):
    bp = CkApstraBlueprint(session, tor_bp)
    bp.print_id()
    assert True

 