"""
Make sure mwrelease works
"""


from mwrelease.branch import MWVERSION_REGEX


def test_mwversion_regex_matches():
    assert MWVERSION_REGEX.match("define( 'MW_VERSION', '1.35.0-alpha' );")


def test_mwversion_regex_sub():
    text = "hi!\ndefine( 'MW_VERSION', '1.35.0-alpha' );\nbye!"
    expected = "hi!\ndefine( 'MW_VERSION', 'FOO' );\nbye!"
    assert MWVERSION_REGEX.sub(r"\1'FOO'\2", text) == expected
