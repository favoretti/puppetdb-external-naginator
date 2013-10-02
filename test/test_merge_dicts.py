from naginator import merge_dicts


def test_merge_dicts__respects_existing_items():
    d = { 'a': 10 }
    defaults = {'a': 0}
    assert merge_dicts(d, defaults) == { 'a': 10 }


def test_merge_dicts__adds_items():
    d = { 'a': 10 }
    defaults = {'b': 0}
    assert merge_dicts(d, defaults) == { 'a': 10, 'b': 0 }


def test_merge_dicts__works_with_empty_dict():
    d = {}
    defaults = {'b': 0}
    assert merge_dicts(d, defaults) == { 'b': 0 }
 

def test_merge_dicts__works_with_empty_defaults():
    d = { 'a': 10 }
    defaults = {}
    assert merge_dicts(d, defaults) == { 'a': 10 }
 

def test_merge_dicts__works_with_multiple_values():
    d = { 'a': 10 }
    defaults = {'a': 0, 'b': 0}
    assert merge_dicts(d, defaults) == { 'a': 10, 'b': 0 }

