from naginator import get_config
from mock import *

def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "admins" ,
            "parameters": {
                "contactgroup_name": "admins",
                "members": "alice,bob",
                "alias": "Administrators",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "visitors" ,
            "parameters": {
                "contactgroup_name": "visitors",
                "members": "charlie,dan",
                "alias": "Visitors",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_contactgroups_config():
    assert get_config('contactgroup') == """
define contactgroup {
        alias                          Administrators
        contactgroup_name              admins
        members                        alice,bob
}

define contactgroup {
        alias                          Visitors
        contactgroup_name              visitors
        members                        charlie,dan
}

"""

