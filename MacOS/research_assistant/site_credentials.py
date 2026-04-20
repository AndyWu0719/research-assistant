from __future__ import annotations

import subprocess


def secret_service_name(site_key: str, account_label: str) -> str:
    return f"research-assistant.site-account.{site_key}.{account_label}"


def username_hint(value: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    if "@" in candidate:
        local, domain = candidate.split("@", 1)
        prefix = (local[:1] or "*") + "***"
        return f"{prefix}@{domain}"
    return (candidate[:1] or "*") + "***"


def public_record(**payload):
    record = dict(payload)
    record.pop("password", None)
    record["username_hint"] = username_hint(str(record.get("username", ""))) or str(record.get("username_hint", "")).strip()
    record.pop("username", None)
    return record


class SecretStore:
    def save_secret(self, service: str, account: str, username: str, password: str) -> None:
        subprocess.run(
            ["security", "add-generic-password", "-U", "-s", service, "-a", account, "-w", password, "-T", ""],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["security", "add-generic-password", "-U", "-s", f"{service}.username", "-a", account, "-w", username, "-T", ""],
            check=True,
            capture_output=True,
            text=True,
        )

    def load_secret(self, service: str, account: str):
        password = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
        )
        username = subprocess.run(
            ["security", "find-generic-password", "-s", f"{service}.username", "-a", account, "-w"],
            capture_output=True,
            text=True,
        )
        if password.returncode != 0 or username.returncode != 0:
            return None
        return {"username": username.stdout.strip(), "password": password.stdout.strip()}

    def delete_secret(self, service: str, account: str) -> bool:
        removed = False
        for candidate in [service, f"{service}.username"]:
            result = subprocess.run(
                ["security", "delete-generic-password", "-s", candidate, "-a", account],
                capture_output=True,
                text=True,
            )
            removed = removed or result.returncode == 0
        return removed


def save_site_secret(store: SecretStore, site_key: str, account_label: str, username: str, password: str) -> None:
    store.save_secret(secret_service_name(site_key, account_label), account_label, username, password)


def load_site_secret(store: SecretStore, site_key: str, account_label: str):
    return store.load_secret(secret_service_name(site_key, account_label), account_label)


def delete_site_secret(store: SecretStore, site_key: str, account_label: str) -> bool:
    return store.delete_secret(secret_service_name(site_key, account_label), account_label)
