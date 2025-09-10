from __future__ import annotations
from typing import Optional, Any, Dict, List
from dataclasses import dataclass
import re

try:
    import oracledb  # Oracle official driver
except Exception as ex:  # pragma: no cover
    oracledb = None
    _IMPORT_ERROR = ex
else:
    _IMPORT_ERROR = None

from servers_config import ServersConfig, Server

# Helper to parse host:port/service style TNS
_HOST_PORT_SVC_RE = re.compile(r"^(?P<host>[^/:]+)(?::(?P<port>\d+))?(?:/(?P<svc>[^/]+))?$")


@dataclass(slots=True)
class OracleTarget:
    instance: str
    username: str
    password: str
    dsn: str


class OracleConnector:
    """
    Connector bound to a single Instance.
    Provides ready-to-use query methods using specific usernames + SQL.
    """

    def __init__(self, cfg: ServersConfig, instance: str):
        self.cfg = cfg
        self.instance = instance

    # ---------- Internal helper ----------
    def _run(self, sql: str, username: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        target = self.cfg.get_by_instance_and_username(self.instance, username)
        if not target:
            raise ValueError(f"No credentials for Instance={self.instance} with Username={username}")

        if oracledb is None:
            raise RuntimeError("python-oracledb is not installed. pip install oracledb") from _IMPORT_ERROR

        with oracledb.connect(user=target.username, password=target.password, dsn=target.tns) as con:
            with con.cursor() as cur:
                cur.execute(sql, params or {})
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur]

    # ---------- Example query methods ----------

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all database users (using SYSTEM account)."""
        sql = "SELECT username, account_status FROM dba_users"
        return self._run(sql, username="system")

    def get_user_by_name(self, uname: str) -> List[Dict[str, Any]]:
        """Find one user by exact name (SYSTEM)."""
        sql = "SELECT username, account_status FROM dba_users WHERE username = :uname"
        return self._run(sql, username="system", params={"uname": uname.upper()})

    def find_users_like(self, pattern: str) -> List[Dict[str, Any]]:
        """Find users by partial match (SYSTEM)."""
        sql = "SELECT username, account_status FROM dba_users WHERE username LIKE :uname"
        return self._run(sql, username="system", params={"uname": f"%{pattern.upper()}%"})

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get active sessions (EBS_ADMIN)."""
        sql = "SELECT sid, serial#, username, status FROM v$session WHERE status='ACTIVE'"
        return self._run(sql, username="ebs_admin")

    def find_sessions_by_user_suffix(self, suffix: str) -> List[Dict[str, Any]]:
        """Find active sessions where username ends with suffix (EBS_ADMIN)."""
        sql = "SELECT sid, serial#, username, status FROM v$session WHERE username LIKE :uname"
        return self._run(sql, username="ebs_admin", params={"uname": f"%{suffix.upper()}"})

    def find_tables_starting_with(self, prefix: str) -> List[Dict[str, Any]]:
        """Find tables starting with prefix (EBS_IFX)."""
        sql = "SELECT table_name FROM user_tables WHERE table_name LIKE :tname"
        return self._run(sql, username="ebs_ifx", params={"tname": f"{prefix.upper()}%"})

    # ---------- Multi-table join examples ----------

    def get_employee_details(self, dept_name: str) -> List[Dict[str, Any]]:
        """
        Join 3 tables: employees + departments + locations.
        Requires HR schema (example).
        """
        sql = """
            SELECT e.employee_id,
                   e.first_name || ' ' || e.last_name AS full_name,
                   d.department_name,
                   l.city,
                   l.country_id
            FROM employees e
            JOIN departments d ON e.department_id = d.department_id
            JOIN locations l   ON d.location_id = l.location_id
            WHERE d.department_name = :dept
        """
        return self._run(sql, username="hr_admin", params={"dept": dept_name})

    def get_employee_details_with_country(self, dept_name: str) -> List[Dict[str, Any]]:
        """
        Join 4 tables: employees + departments + locations + countries.
        Requires HR schema (example).
        """
        sql = """
            SELECT e.employee_id,
                   e.first_name || ' ' || e.last_name AS full_name,
                   d.department_name,
                   l.city,
                   c.country_name,
                   c.region_id
            FROM employees e
            JOIN departments d ON e.department_id = d.department_id
            JOIN locations l   ON d.location_id = l.location_id
            JOIN countries c   ON l.country_id = c.country_id
            WHERE d.department_name = :dept
        """
        return self._run(sql, username="hr_admin", params={"dept": dept_name})
