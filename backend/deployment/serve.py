import os
import ssl

import uvicorn

from deployment.common import configure_application
from deployment.tls import validate_enrollment

configure_application()
# Never log TLS session keys even if an ambient diagnostic environment sets this.
os.environ.pop("SSLKEYLOGFILE", None)
tls = os.environ.get("TLS_DIRECTORY", "/run/tls")
validate_enrollment(tls)
config = uvicorn.Config("main:app", host="0.0.0.0", port=8443,
                        ssl_certfile=tls + "/server.pem", ssl_keyfile=tls + "/server.key",
                        ssl_ca_certs=tls + "/client-pins.pem", ssl_cert_reqs=ssl.CERT_REQUIRED,
                        ssl_version=ssl.PROTOCOL_TLS_SERVER)
config.load()
# Trust only the explicitly enrolled Kong and local health leaf certificates.
# Stock Uvicorn does not authorize a client by SAN. OpenSSL partial-chain anchors
# enforce possession of these exact keys, validity and clientAuth at the handshake.
config.ssl.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
uvicorn.Server(config).run()
