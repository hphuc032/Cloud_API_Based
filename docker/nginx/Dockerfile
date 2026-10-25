# Core nginx only: the application does not load optional dynamic modules.
FROM nginx:1.30.6-alpine-slim@sha256:dede8895648b461178c3bc604f7eed4423efe5220b2c4d839f5eb3d34ac3f8f7

# BusyBox wget cannot enforce the existing --ca-certificate healthcheck contract.
RUN apk add --no-cache wget=1.25.0-r3 libidn2=2.3.8-r0 libunistring=1.4.2-r0
