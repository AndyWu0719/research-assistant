from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes


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


LPBYTE = ctypes.POINTER(ctypes.c_ubyte)
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", LPBYTE),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", wintypes.LPVOID),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _encode_secret(username: str, password: str) -> bytes:
    return json.dumps({"username": username, "password": password}, ensure_ascii=False).encode("utf-16-le")


def _advapi32():
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        raise RuntimeError("Windows Credential Manager 仅在 Windows 主机可用。")
    return ctypes.WinDLL("Advapi32.dll", use_last_error=True)


class SecretStore:
    def save_secret(self, service: str, account: str, username: str, password: str) -> None:
        advapi32 = _advapi32()
        blob = _encode_secret(username, password)
        blob_buffer = ctypes.create_string_buffer(blob)
        credential = CREDENTIALW()
        credential.Type = CRED_TYPE_GENERIC
        credential.TargetName = f"{service}:{account}"
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(blob_buffer, LPBYTE)
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = username
        cred_write = advapi32.CredWriteW
        cred_write.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
        cred_write.restype = wintypes.BOOL
        if not cred_write(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def load_secret(self, service: str, account: str):
        advapi32 = _advapi32()
        pointer = ctypes.POINTER(CREDENTIALW)()
        cred_read = advapi32.CredReadW
        cred_read.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
        cred_read.restype = wintypes.BOOL
        if not cred_read(f"{service}:{account}", CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == ERROR_NOT_FOUND:
                return None
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            size = int(pointer.contents.CredentialBlobSize)
            raw = ctypes.string_at(pointer.contents.CredentialBlob, size)
            payload = json.loads(raw.decode("utf-16-le"))
            return {"username": str(payload["username"]), "password": str(payload["password"])}
        finally:
            advapi32.CredFree(pointer)

    def delete_secret(self, service: str, account: str) -> bool:
        advapi32 = _advapi32()
        cred_delete = advapi32.CredDeleteW
        cred_delete.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        cred_delete.restype = wintypes.BOOL
        if cred_delete(f"{service}:{account}", CRED_TYPE_GENERIC, 0):
            return True
        if ctypes.get_last_error() == ERROR_NOT_FOUND:
            return False
        raise ctypes.WinError(ctypes.get_last_error())


def save_site_secret(store: SecretStore, site_key: str, account_label: str, username: str, password: str) -> None:
    store.save_secret(secret_service_name(site_key, account_label), account_label, username, password)


def load_site_secret(store: SecretStore, site_key: str, account_label: str):
    return store.load_secret(secret_service_name(site_key, account_label), account_label)


def delete_site_secret(store: SecretStore, site_key: str, account_label: str) -> bool:
    return store.delete_secret(secret_service_name(site_key, account_label), account_label)
