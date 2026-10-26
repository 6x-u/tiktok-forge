"""tiktok-forge — real TikTok signatures for web and app.

Web side executes TikTok's own browser bundle (``js/webmssdk.js``) through a
small node bridge, so ``X-Bogus`` is whatever the current build emits, not a
stale Python port.  App side generates Argus/Gorgon/Ladon locally from the
identity in :mod:`tiktokforge.config`.
"""

__version__ = "1.1.0"
__author__ = "MERO"
__contact__ = "TG@QP4RM"
__license__ = "MIT"

from tiktokforge.bridge import (
    BridgeError,
    NodeUnavailable,
    SignBridge,
    find_node,
    get_bridge,
    sign_url,
)
from tiktokforge.config import (
    APP_AID,
    APP_DEFAULTS,
    AID_TIKTOK,
    AppDefaults,
    DeviceProfile,
    VERSION_CODE_OVERRIDES,
    WEB_AID,
    WEB_DEFAULTS,
    WEB_USER_AGENT,
    WebDefaults,
    version_code_for,
)
from tiktokforge.signer import (
    TikTokSigner,
    decode,
    decrypt,
    encode,
    encrypt,
    generate_headers,
)
from tiktokforge.web import (
    WebClient,
    build_query,
    generate_device_id,
    generate_ms_token,
    generate_verify_fp,
    generate_web_headers,
    generate_web_id,
    generate_x_bogus,
    provision_ttwid,
    sign_web,
    with_signature,
)
from tiktokforge.algorithms.argus import Argus
from tiktokforge.algorithms.gorgon import Gorgon
from tiktokforge.algorithms.ladon import Ladon
from tiktokforge.algorithms.protobuf import ProtoBuf, protobuf_decode, protobuf_encode
from tiktokforge.algorithms.simon import Simon
from tiktokforge.algorithms.sm3 import SM3
from tiktokforge.algorithms.stub import generate_stub
from tiktokforge.algorithms.ttencrypt import TTEncrypt

__all__ = [
    # app
    "TikTokSigner",
    "generate_headers",
    "encrypt",
    "decrypt",
    "encode",
    "decode",
    # web
    "WebClient",
    "sign_web",
    "generate_x_bogus",
    "generate_web_headers",
    "generate_ms_token",
    "generate_verify_fp",
    "generate_web_id",
    "generate_device_id",
    "with_signature",
    "build_query",
    "provision_ttwid",
    # bridge
    "SignBridge",
    "get_bridge",
    "sign_url",
    "find_node",
    "NodeUnavailable",
    "BridgeError",
    # config
    "AppDefaults",
    "DeviceProfile",
    "WebDefaults",
    "APP_DEFAULTS",
    "WEB_DEFAULTS",
    "APP_AID",
    "WEB_AID",
    "AID_TIKTOK",
    "WEB_USER_AGENT",
    "version_code_for",
    "VERSION_CODE_OVERRIDES",
    # algorithms
    "Argus",
    "Gorgon",
    "Ladon",
    "Simon",
    "SM3",
    "TTEncrypt",
    "ProtoBuf",
    "protobuf_encode",
    "protobuf_decode",
    "generate_stub",
]
