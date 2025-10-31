"""Utility package that preserves legacy `app/utils.py` symbols and adds new ones.

We eagerly load the legacy module file `app/utils.py` and re-export its public
symbols so statements like `from app.utils import generate_password_reset_token`
continue to work after turning `app.utils` into a package.
"""

from __future__ import annotations

import sys
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

# Load legacy module (app/utils.py) under a distinct name and copy symbols
_legacy_path = (Path(__file__).resolve().parent.parent / "utils.py").resolve()
if _legacy_path.exists():
	_spec = spec_from_file_location("app_utils_legacy", str(_legacy_path))
	if _spec and _spec.loader:  # type: ignore[truthy-bool]
		_legacy_mod = module_from_spec(_spec)
		sys.modules["app_utils_legacy"] = _legacy_mod
		_spec.loader.exec_module(_legacy_mod)  # type: ignore[arg-type]
		for _name in [
			"EmailData",
			"render_email_template",
			"send_email",
			"generate_test_email",
			"generate_reset_password_email",
			"generate_new_account_email",
			"generate_password_reset_token",
			"verify_password_reset_token",
		]:
			if hasattr(_legacy_mod, _name):
				globals()[_name] = getattr(_legacy_mod, _name)

# Import and expose SSRF utilities from submodule
from .url_validator import validate_url_or_raise, SSRFProtectionError  # noqa: E402

__all__ = [
	# SSRF
	"validate_url_or_raise",
	"SSRFProtectionError",
	# Legacy utils (conditionally available)
	"EmailData",
	"render_email_template",
	"send_email",
	"generate_test_email",
	"generate_reset_password_email",
	"generate_new_account_email",
	"generate_password_reset_token",
	"verify_password_reset_token",
]
