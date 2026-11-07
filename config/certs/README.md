Intermediate certificates that some university servers fail to send. The
scraper adds them to the system trust store (`research_map.fetch.ssl_context`)
so TLS verification stays on. Each was downloaded from the issuer URL in the
server certificate's Authority Information Access field.

| File | Issuer URL | Needed by |
|---|---|---|
| incommon-ovg2c.pem | http://repository.emsign.com/certs/EEEMIncommonOVG2C.crt | www.tacoma.uw.edu |
