import os
import sys
import pytest

from lca_algebraic.helpers import _isForeground
from lca_algebraic.lca import _clearLCACache
from lca_algebraic.params import _param_registry

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "test"))

from lca_algebraic import *
from fixtures import *

USER_DB = "fg"
BG_DB= "bg"
METHOD_PREFIX='tests'

# Reset func project, empty DB
initDb('tests')

# Create 3 bio activities
bio1, bio2, bio3 = init_acts(BG_DB)

# Create one method per bio activity, plus 1 method with several
ibio1, ibio2, ibio3, imulti = init_methods(BG_DB, METHOD_PREFIX)

setForeground(USER_DB)


def setup_function() :
    """Before each test"""

    print("resetting fg DB")

    resetDb(USER_DB)
    resetParams(USER_DB)
    _clearLCACache()

def test_load_params():
    _p1 = newEnumParam('p1',values={"v1":0.6, "v2":0.3}, default="v1")
    _p2 = newFloatParam('p2', min=1, max=3, default=2, distrib=DistributionType.TRIANGLE)
    _p3 = newBoolParam('p3',default=1)
    _p3_fg = newBoolParam('p3', default=1, dbname=USER_DB) # Param with same name linked to a user DB

    # Params are loaded as global variable with their real names
    loadParams()

    # Get params from in memory DB
    loaded_params = {(param.name, param.dbname) : param for param in _param_registry().all()}

    assert _p1.__dict__ == loaded_params[("p1", None)].__dict__
    assert _p2.__dict__ == loaded_params[("p2", None)].__dict__
    assert _p3.__dict__ == loaded_params[("p3", None)].__dict__
    assert _p3_fg.__dict__ == loaded_params[("p3", USER_DB)].__dict__


def test_switch_activity_support_sevral_times_same_target() :
    """ Test that switch activity can target the same activity several times """

    # Enum param
    p1 = newEnumParam(
        'p1',
        values=["v1", "v2", "v3"],
        default="v1")

    bg_act1 = findTechAct("bg_act1")

    act = newSwitchAct(USER_DB, "switchAct", p1, {
        "v1" : bg_act1,
        "v2" : bg_act1,
        "v3" : bg_act1
    })

    impact = (METHOD_PREFIX, 'all', 'total')

    res = multiLCAAlgebric(act, [impact], p1=["v1", "v2", "v3"])
    vals = res.values

    assert vals[0] == vals[1] and vals[1] == vals[2]

def test_new_switch_act_with_tuples() :

    p1 = newEnumParam(
        'p1',
        values=["v1", "v2", "v3"],
        default="v1")

    bg_act1 = findTechAct("bg_act1")
    bg_act2 = findTechAct("bg_act2")

    newSwitchAct(USER_DB, "switchAct", p1, {
        "v1": (bg_act1, 2.0),
        "v2": (bg_act2, 3.0),
    })

def test_list_params_should_support_missing_groups() :

    p1 = newFloatParam('p1', default=1.0)
    p2 = newFloatParam('p2', default=2.0, group="mygroup")

    list_parameters()

def test_freeze() :

    p1 = newFloatParam('p1', default=1.0)
    p2 = newFloatParam('p2', default=1.0)

    newActivity(USER_DB, "act1", "unit", {
        bio1 : 2 * p1,
        bio2 : 3 * p2,
    })

    # p1 should be set as default value 1
    freezeParams(USER_DB, p2=2)

    # Load back activity
    act1 = findActivity("act1", db_name=USER_DB)

    for exc in act1.exchanges():

        # Don't show production
        if exc['type'] == 'production' :
            continue

        name = exc["name"]
        amount = exc["amount"]

        # Brightway2 does not like ints ...
        assert isinstance(amount, float)

        if name == "bio1" :
            # p1=1 (default) * 2
            assert amount == 2.0
        elif name == 'bio2' :
            # p2=2 * 3
            assert amount == 6.0



def test_enum_values_are_enforced():

    # Enum param
    p1 = newEnumParam(
        'p1',
        values=["v1", "v2", "v3"], default="v1")

    act = newActivity(USER_DB, "Foo", "unit")

    climate = [m for m in bw.methods if 'ILCD 1.0.8 2016' in str(m) and 'no LT' in str(m)][1]

    with pytest.raises(Exception) as exc:
        multiLCAAlgebric(act, climate, p1="bar")

    assert 'Invalid value' in str(exc)

def test_setforeground() :

    setForeground(USER_DB)

    assert _isForeground(USER_DB)

    setBackground(USER_DB)

    assert _isForeground(USER_DB) == False


def test_db_params_low_level() :

    # Define 3 variables with same name, attached to project or db (user or bg)
    p1_bg = newBoolParam("p1", False, dbname=BG_DB)
    p1_fg = newBoolParam("p1", False, dbname=USER_DB)
    p1_project = newBoolParam("p1", False, dbname=USER_DB)

    # No context provided  ? => should fail : we can't know what param we refer to
    with pytest.raises(DuplicateParamsAndNoContextException) as exc:
        p1 = _param_registry()["p1"]

    assert "context" in str(exc.value)

    with DbContext(USER_DB) :
        p1 = _param_registry()["p1"]
        assert p1 == p1_fg

    with DbContext(BG_DB):
        p1 = _param_registry()["p1"]
        assert p1 == p1_bg

def test_db_params_lca() :
    """Test multiLCAAlgebraic with parameters with similar names from similar DBs"""
    USER_DB2 = "fg2"
    resetDb(USER_DB2)

    # Define 3 variables with same name, attached to project or db (user or bg)
    p1_project = newFloatParam("p1", 0, min=0, max=2, )
    p1_user = newFloatParam("p1", 1, min=0, max=2, dbname=USER_DB)
    p1_user2 = newFloatParam("p1", 2, min=0, max=2, dbname=USER_DB2)

    # Create 2 models : one for each user db, using different params with same name
    m1 = newActivity(USER_DB, "m1", "kg",
                     {bio1 : 2.0 * p1_user})
    m2 = newActivity(USER_DB2, "m2", "kg",
                     {bio1: 2.0 * p1_user2})

    # p1 as default value of 1 for user db 1
    res = multiLCAAlgebric(m1, [ibio1])
    assert res.values[0] == 2.0

    # p1 as default value of 2 for user db 2
    res = multiLCAAlgebric(m2, [ibio1])
    assert res.values[0] == 4.0

    # Overriding p1 for m1
    res = multiLCAAlgebric(m1, [ibio1], p1=3)
    assert res.values[0] == 6.0

    # Overriding p1 for m2
    res = multiLCAAlgebric(m2, [ibio1], p1=4)
    assert res.values[0] == 8.0


def test_params_as_power() :


    p1 = newFloatParam("p1", 2, min=0, max=2)

    m1 = newActivity(USER_DB, "m1", "kg",
                     {bio1 : 2.0 ** p1})

    res = multiLCAAlgebric(m1, [ibio1], p1=2)
    assert res.values[0] == 4.0

if __name__ == '__main__':
    pytest.main(sys.argv)



