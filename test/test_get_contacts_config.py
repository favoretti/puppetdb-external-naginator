from naginator import get_contacts_config
from mock import *


def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "alfred" ,
            "parameters": {
                "use": "generic",
                "alias": "Alfred",
                "email": "alfred@example.org",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "bob" ,
            "parameters": {
                "use": "generic",
                "alias": "Bob",
                "email": "bob@example.org",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_contacts_config():
    assert get_contacts_config() == """
define contact {
        contact_name                   alfred
        use                            generic
        alias                          Alfred
        email                          alfred@example.org
}

define contact {
        contact_name                   bob
        use                            generic
        alias                          Bob
        email                          bob@example.org
}
"""

