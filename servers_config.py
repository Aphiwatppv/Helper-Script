from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Iterable
import xml.etree.ElementTree as ET
from pathlib import Path


@dataclass(slots=True)
class Server:
    id: str
    location: str
    instance: str
    instance_type: str
    username: str
    password: str
    tns: str

    def masked(self) -> "Server":
        """Return a copy with the password masked (useful for printing/logging)."""
        return Server(
            id=self.id,
            location=self.location,
            instance=self.instance,
            instance_type=self.instance_type,
            username=self.username,
            password="***",
            tns=self.tns,
        )


class ServersConfig:
    """
    Reader for ServersConfig.xml like:

    <Servers>
        <Server>
            <Id>...</Id>
            <Location>Regensburg</Location>
            <Instance>EBS10</Instance>
            <InstanceType>EBSO</InstanceType>
            <Username>ebs_admin</Username>
            <Password>ebs_2005</Password>
            <TNS>ebso.rbg.infineon.com</TNS>
        </Server>
        ...
    </Servers>
    """

    def __init__(self, servers: List[Server]) -> None:
        self._servers = servers

    # ---------- Constructors ----------
    @classmethod
    def from_file(cls, path: str | Path, encoding: str = "utf-8") -> "ServersConfig":
        tree = ET.parse(path)
        root = tree.getroot()
        servers = list(cls._parse_servers(root))
        return cls(servers)

    @classmethod
    def from_string(cls, xml_text: str) -> "ServersConfig":
        root = ET.fromstring(xml_text)
        servers = list(cls._parse_servers(root))
        return cls(servers)

    # ---------- Public API ----------
    def all(self) -> List[Server]:
        return list(self._servers)

    def get_by_id(self, server_id: str) -> Optional[Server]:
        for s in self._servers:
            if s.id == server_id:
                return s
        return None

    def get_by_instance_and_username(self, instance: str, username: str) -> Optional[Server]:
        """Return a single server by instance and username (or None if no match)."""
        for s in self._servers:
            if s.instance == instance and s.username == username:
                return s
        return None

    def find(
        self,
        *,
        location: Optional[str] = None,
        instance: Optional[str] = None,
        instance_type: Optional[str] = None,
        username: Optional[str] = None,
    ) -> List[Server]:
        """Flexible filter. Example: cfg.find(location="Regensburg", instance="EBS10")"""
        def _match(s: Server) -> bool:
            return (
                (location is None or s.location == location)
                and (instance is None or s.instance == instance)
                and (instance_type is None or s.instance_type == instance_type)
                and (username is None or s.username == username)
            )
        return [s for s in self._servers if _match(s)]

    # ---------- Internal helpers ----------
    @staticmethod
    def _parse_servers(root: ET.Element) -> Iterable[Server]:
        for el in root.findall("Server"):
            def text(tag: str) -> str:
                child = el.find(tag)
                return (child.text or "").strip() if child is not None else ""

            yield Server(
                id=text("Id"),
                location=text("Location"),
                instance=text("Instance"),
                instance_type=text("InstanceType"),
                username=text("Username"),
                password=text("Password"),
                tns=text("TNS"),
            )

    # ---------- Utility ----------
    def to_dicts(self, mask_password: bool = True) -> List[dict]:
        rows: List[dict] = []
        for s in self._servers:
            src = s.masked() if mask_password else s
            rows.append({
                "Id": src.id,
                "Location": src.location,
                "Instance": src.instance,
                "InstanceType": src.instance_type,
                "Username": src.username,
                "Password": src.password,
                "TNS": src.tns,
            })
        return rows
