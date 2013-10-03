from naginator import get_config
from mock import *


def mock_get_nagios_data(__):
    return [
        {
            "certname": "aaaa.ofi.lan" ,
            "title": "alice",
            "parameters": {
                "use": "generic",
                "alias": "Alice",
                "email": "alice@example.org",
                "contact_name": "alice",
            },
        },
        {
            "certname": "bbbb.ofi.lan" ,
            "title": "bob" ,
            "parameters": {
                "use": "generic",
                "alias": "Bob",
                "email": "bob@example.org",
                "contact_name": "bob",
            },
        },
    ]


@patch('naginator.get_nagios_data', mock_get_nagios_data)
def test_get_contacts_config():
    assert get_config('contact') == """
define contact {
        alias                          Alice
        contact_name                   alice
        email                          alice@example.org
        use                            generic
}

define contact {
        alias                          Bob
        contact_name                   bob
        email                          bob@example.org
        use                            generic
}

"""

