"""Security middleware for the local FVSC HTTP service.

Binding a service to 127.0.0.1 does not make it unreachable from arbitrary web
pages: browsers can still issue requests to loopback addresses.  This module
limits browser access to the Obsidian application and loopback-hosted FVSC
pages, and rejects unexpected Host headers to reduce DNS-rebinding exposure.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from urllib