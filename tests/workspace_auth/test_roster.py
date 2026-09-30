import json

import pytest

from workspace_auth.roster import create_roster, read_roster


def test_create_then_read_roundtrips_the_exact_payload():
    ciphertext = create_roster(
        workspace_repo="OpenFASTER-Standard/mikadiv-fm-public",
        github_token="github_pat_fake_test_token_value",
        passphrase="correct-horse-battery-staple",
    )

    payload = read_roster(ciphertext, passphrase="correct-horse-battery-staple")

    assert payload == {
        "workspace_repo": "OpenFASTER-Standard/mikadiv-fm-public",
        "github_token": "github_pat_fake_test_token_value",
    }


def test_wrong_passphrase_raises_roster_authentication_error():
    ciphertext = create_roster(
        workspace_repo="owner/repo", github_token="tok", passphrase="right-passphrase",
    )

    from workspace_auth.roster import RosterAuthenticationError

    with pytest.raises(RosterAuthenticationError):
        read_roster(ciphertext, passphrase="wrong-passphrase")


def test_truncated_ciphertext_raises_the_same_roster_authentication_error():
    from workspace_auth.roster import RosterAuthenticationError

    ciphertext = create_roster(workspace_repo="owner/repo", github_token="tok", passphrase="p")
    truncated = ciphertext[:20]

    with pytest.raises(RosterAuthenticationError):
        read_roster(truncated, passphrase="p")


def test_correct_passphrase_but_non_json_plaintext_raises_roster_format_error():
    from pyrage import passphrase as age_passphrase
    from workspace_auth.roster import RosterFormatError

    ciphertext = age_passphrase.encrypt(b"not json at all {{{", "p")

    with pytest.raises(RosterFormatError):
        read_roster(ciphertext, passphrase="p")


def test_create_roster_output_is_real_age_binary_format():
    ciphertext = create_roster(workspace_repo="owner/repo", github_token="tok", passphrase="p")
    assert ciphertext.startswith(b"age-encryption.org/v1")
