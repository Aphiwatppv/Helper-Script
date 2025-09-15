from __future__ import annotations
import paramiko
from dataclasses import dataclass
from typing import Optional, List, Dict
from fnmatch import fnmatch
from datetime import datetime

@dataclass
class SSHAuth:
    hostname: str
    username: str
    port: int = 22
    password: Optional[str] = None              # Use this OR key_file
    key_file: Optional[str] = None              # Path to OpenSSH private key (NOT .ppk)
    key_passphrase: Optional[str] = None        # If your key is passphrase-protected
    # known_hosts behavior
    auto_add_host_key: bool = True

def _connect(auth: SSHAuth) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    if auth.auto_add_host_key:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        client.load_system_host_keys()
    client.connect(
        hostname=auth.hostname,
        port=auth.port,
        username=auth.username,
        password=auth.password,
        key_filename=auth.key_file,
        passphrase=auth.key_passphrase,
        look_for_keys=False,
        allow_agent=False
    )
    return client

def list_remote(
    auth: SSHAuth,
    remote_path: str,
    *,
    recursive: bool = False,
    include_files: bool = True,
    include_dirs: bool = False,
    pattern: Optional[str] = None,   # e.g. "*.log" or "2025-*.csv"
) -> List[Dict]:
    """
    List entries at remote_path via SFTP. Returns a list of dicts with metadata.
    - recursive: walk subdirectories
    - include_files / include_dirs: control which to include in results
    - pattern: optional glob (applied to base name)
    """
    client = _connect(auth)
    try:
        sftp = client.open_sftp()
        try:
            results: List[Dict] = []
            def _ls(path: str):
                for attr in sftp.listdir_attr(path):
                    name = attr.filename
                    full_path = f"{path.rstrip('/')}/{name}"
                    is_dir = _is_dir(sftp, full_path)
                    if (pattern is None) or fnmatch(name, pattern):
                        if (is_dir and include_dirs) or ((not is_dir) and include_files):
                            results.append({
                                "name": name,
                                "path": full_path,
                                "is_dir": is_dir,
                                "size": attr.st_size,
                                "mtime": datetime.fromtimestamp(attr.st_mtime),
                                "mode": oct(attr.st_mode),
                            })
                    if recursive and is_dir:
                        _ls(full_path)

            _ls(remote_path)
            # sort by path then name for stable output
            results.sort(key=lambda r: (r["path"], r["name"]))
            return results
        finally:
            sftp.close()
    finally:
        client.close()

def _is_dir(sftp: paramiko.SFTPClient, path: str) -> bool:
    # SFTP has no direct isdir; try stat and check mode bit
    import stat
    try:
        st = sftp.stat(path)
        return stat.S_ISDIR(st.st_mode)
    except IOError:
        return False

