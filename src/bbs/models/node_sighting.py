"""
Mesh node history (sightings from adverts and received messages).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, Index, Integer, String

from .base import Base


class NodeSighting(Base):
    """
    One row per mesh node ever heard (12-hex public key prefix).

    Updated at most once every few minutes per node (debounced in
    bbs.services.node_history) to spare the SD card.
    """

    __tablename__ = "node_sightings"

    pubkey_prefix = Column(String(12), primary_key=True)
    name = Column(String(32), nullable=True)
    node_type = Column(Integer, nullable=True)  # 1=CLI 2=RPT 3=ROOM 4=SENS
    last_hops = Column(Integer, nullable=True)
    snr = Column(Float, nullable=True)
    rssi = Column(Integer, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    count = Column(Integer, default=0, nullable=False)

    __table_args__ = (Index("idx_node_sightings_last_seen", "last_seen"),)

    def __repr__(self) -> str:
        return f"<NodeSighting {self.pubkey_prefix} {self.name!r} x{self.count}>"


class NodeSightingDay(Base):
    """Which nodes were heard on which (UTC) day: feeds the 7-day chart."""

    __tablename__ = "node_sighting_days"

    day = Column(Date, primary_key=True)
    pubkey_prefix = Column(String(12), primary_key=True)
