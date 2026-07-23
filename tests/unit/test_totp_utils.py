import pyotp
import pytest

from astrbot.core.db.sqlite import SQLiteDatabase
from astrbot.core.utils.totp import (
    TotpRuntimeState,
    generate_recovery_code,
    is_totp_enabled,
    is_totp_trusted_device_valid,
    issue_totp_trusted_device,
    verify_recovery_code,
)


@pytest.mark.parametrize(
    ("totp_config", "expected"),
    [
        ({}, False),
        ({"enable": False, "secret": "abc", "recovery_code_hash": "hash"}, False),
        ({"enable": True, "secret": "", "recovery_code_hash": "hash"}, False),
        ({"enable": True, "secret": "abc", "recovery_code_hash": ""}, False),
        ({"enable": True, "secret": "abc", "recovery_code_hash": "hash"}, True),
    ],
)
def test_is_totp_enabled_requires_enable_secret_and_recovery_hash(
    totp_config: dict,
    expected: bool,
):
    config = {"dashboard": {"totp": totp_config}}
    assert is_totp_enabled(config) is expected


@pytest.mark.asyncio
async def test_consume_totp_code_prevents_replay_same_timecode():
    state = TotpRuntimeState()
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    assert await state.consume_totp_code(secret, code) is True
    assert await state.consume_totp_code(secret, code) is False


@pytest.mark.asyncio
async def test_totp_runtime_state_is_isolated_per_runtime():
    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    first_runtime = TotpRuntimeState()
    second_runtime = TotpRuntimeState()

    assert await first_runtime.consume_totp_code(secret, code) is True
    assert await first_runtime.consume_totp_code(secret, code) is False
    assert await second_runtime.consume_totp_code(secret, code) is True


@pytest.mark.asyncio
async def test_pending_rotation_is_scoped_to_authenticated_subject():
    state = TotpRuntimeState()
    current_secret = pyotp.random_base32()
    replacement_secret = pyotp.random_base32()
    config = {
        "dashboard": {
            "totp": {
                "enable": True,
                "secret": current_secret,
                "recovery_code_hash": "hash",
            }
        }
    }

    assert await state.verify_current_rotation_code(
        "dashboard-session:one",
        config,
        pyotp.TOTP(current_secret).now(),
    )

    replacement_code = pyotp.TOTP(replacement_secret).now()
    assert not await state.stage_pending_totp_secret(
        "dashboard-session:two",
        config,
        replacement_secret,
        replacement_code,
    )
    assert await state.stage_pending_totp_secret(
        "dashboard-session:one",
        config,
        replacement_secret,
        replacement_code,
    )


def test_generate_and_verify_recovery_code_roundtrip():
    recovery_code, recovery_code_hash = generate_recovery_code()
    config = {"dashboard": {"totp": {"recovery_code_hash": recovery_code_hash}}}
    assert verify_recovery_code(config, recovery_code) is True


def test_verify_recovery_code_rejects_malformed_or_wrong_length():
    recovery_code, recovery_code_hash = generate_recovery_code()
    config = {"dashboard": {"totp": {"recovery_code_hash": recovery_code_hash}}}
    assert verify_recovery_code(config, "abc") is False
    assert verify_recovery_code(config, recovery_code[:-1]) is False


@pytest.mark.asyncio
async def test_issue_and_validate_trusted_device_token(tmp_path):
    db = SQLiteDatabase(str(tmp_path / "trusted-device.db"))
    config = {
        "dashboard": {
            "jwt_secret": "test-jwt-secret",
            "totp": {
                "enable": True,
                "secret": pyotp.random_base32(),
                "recovery_code_hash": "hash",
            },
        }
    }
    try:
        token = await issue_totp_trusted_device(config, db)
        assert isinstance(token, str) and token
        assert await is_totp_trusted_device_valid(config, db, token) is True
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_trusted_device_invalid_after_totp_secret_change(tmp_path):
    db = SQLiteDatabase(str(tmp_path / "trusted-device.db"))
    old_secret = pyotp.random_base32()
    new_secret = pyotp.random_base32()
    config = {
        "dashboard": {
            "jwt_secret": "test-jwt-secret",
            "totp": {
                "enable": True,
                "secret": old_secret,
                "recovery_code_hash": "hash",
            },
        }
    }
    try:
        token = await issue_totp_trusted_device(config, db)
        assert isinstance(token, str) and token
        assert await is_totp_trusted_device_valid(config, db, token) is True

        config["dashboard"]["totp"]["secret"] = new_secret
        assert await is_totp_trusted_device_valid(config, db, token) is False
    finally:
        await db.close()
