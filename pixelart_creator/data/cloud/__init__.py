"""Cloud storage subpackage (zero Qt, S11) — Phase-10 Slice A.

A normal ``data/`` subpackage (already governed by the ``data`` layering rule: no Qt,
no ``ui/`` import). Exposes the one provider-agnostic
:class:`~pixelart_creator.data.cloud.port.CloudPort`, its normalized value types, the
``.pixproj`` transport codec, the ``CloudError`` family, and the CI-tested
:class:`~pixelart_creator.data.cloud.fake_adapter.FakeCloudAdapter`. No provider SDK
type, HTTP/credential type, or provider-specific exception leaks above this package
(REQ-P10-DATA-007); tokens live only inside this package (REQ-P10-DATA-008).
"""

from pixelart_creator.data.cloud.fake_adapter import FakeCloudAdapter
from pixelart_creator.data.cloud.loopback_transport import (
    LoopbackHub,
    LoopbackTransport,
)
from pixelart_creator.data.cloud.port import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
    CloudPort,
    Cursor,
    RemoteItem,
    deserialize_project,
    serialize_project,
)
from pixelart_creator.data.cloud.shared_adapter import (
    PresenceEntry,
    ProjectComment,
    RemoteMember,
    SharedProjectAdapter,
    SharedProjectError,
)
from pixelart_creator.data.cloud.transport import TransportError, TransportPort
from pixelart_creator.data.cloud.ws_transport import WebSocketTransport

__all__ = [
    "CloudPort",
    "CloudError",
    "CloudDataError",
    "CloudCapabilities",
    "Cursor",
    "RemoteItem",
    "serialize_project",
    "deserialize_project",
    "FakeCloudAdapter",
    "SharedProjectAdapter",
    "SharedProjectError",
    "RemoteMember",
    "ProjectComment",
    "PresenceEntry",
    "TransportPort",
    "TransportError",
    "LoopbackHub",
    "LoopbackTransport",
    "WebSocketTransport",
]
