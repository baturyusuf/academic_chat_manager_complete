"""Credential storage through the operating system keyring."""
import keyring

SERVICE="AcademicChatManager"
def save_secret(account:str,value:str):
    if not value: raise ValueError("Secret cannot be empty")
    try:keyring.set_password(SERVICE,account,value)
    except keyring.errors.NoKeyringError as exc:raise RuntimeError("İşletim sisteminin kimlik bilgisi kasası kullanılamıyor.") from exc
def get_secret(account:str):
    try:return keyring.get_password(SERVICE,account)
    except keyring.errors.NoKeyringError:return None
def delete_secret(account:str):
    try:keyring.delete_password(SERVICE,account)
    except keyring.errors.PasswordDeleteError:pass
def keyring_ready():
    try:
        backend=keyring.get_keyring()
        return not isinstance(backend,keyring.backends.fail.Keyring)
    except Exception:return False
