import json

from pyrage import DecryptError, passphrase as age_passphrase


class RosterAuthenticationError(ValueError):
    """Wrong passphrase, or a corrupted/truncated ciphertext -- pyrage
    raises the same DecryptError for both (verified live: "Decryption
    failed" vs. "failed to fill whole buffer"), and neither case is
    actionable differently by an admin typing a passphrase, so this
    wraps both the same way."""


class RosterFormatError(ValueError):
    """Decryption succeeded, but the plaintext isn't the expected JSON
    shape -- a hand-edited or wrong-version roster, never the caller's
    passphrase being at fault."""


def create_roster(*, workspace_repo: str, github_token: str, passphrase: str) -> bytes:
    payload = json.dumps({"workspace_repo": workspace_repo, "github_token": github_token})
    return age_passphrase.encrypt(payload.encode("utf-8"), passphrase)


def read_roster(ciphertext: bytes, *, passphrase: str) -> dict:
    try:
        plaintext = age_passphrase.decrypt(ciphertext, passphrase)
    except DecryptError as exc:
        raise RosterAuthenticationError(str(exc)) from exc

    try:
        return json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise RosterFormatError(f"roster plaintext is not valid JSON: {exc}") from exc
