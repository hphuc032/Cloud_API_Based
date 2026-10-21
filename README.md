# Cloud API Security for SME — FloraSecure

Đồ án NT219: FastAPI/PostgreSQL, React/Vite, Kong OSS, Keycloak,
RBAC/ownership, webhook HMAC và Loki/Promtail/Grafana.

## Trạng thái triển khai

P0–P2 là baseline và kiến trúc mạng/HTTPS/mTLS đã phê duyệt. P3 chuẩn bị Keycloak
production mode, PostgreSQL identity riêng và bảng ánh xạ danh tính; nghiệm thu
P3 vẫn **BLOCKED** bởi ba lỗi DNS runtime. Xem [P3 evidence](docs/testing/p3-results.md).

P4 là **ứng viên kiểm thử riêng**, chọn bằng `docker/p4-compose.yml`. React dùng
Authorization Code + PKCE S256 qua Keycloak, token trong bộ nhớ; Kong OSS kiểm tra
RS256 trước khi chuyển qua mTLS; FastAPI kiểm tra OIDC độc lập và dùng ánh xạ
issuer/sub, `is_active`, role PostgreSQL và ownership hiện có. Local login/token
issuance trả 410 trong P4, không tự fallback. Compose chính giữ chế độ legacy
để regression/rollback theo release. Không có production cutover hay push từ
Workspace A. Kết quả nghiệm thu thực tế nằm trong [P4 test report](docs/testing/p4-results.md).
P5 đã triển khai và kiểm thử webhook receipt nguyên tử, SSRF IPv4/IPv6, validation,
gateway, CSP và demo phản hồi thật trên ứng viên OIDC. **CONDITIONAL: gate DNS còn bị chặn**; xem [P5 results](docs/testing/p5-results.md)
và [thiết kế/control matrix/rollback](docs/security/p5-design.md). Không bắt đầu P6/P7.

## Kiểm thử local

Cần Docker/Compose, Python với `backend/requirements.txt`, Node/npm và Chromium/NSS
cho kiểm thử trình duyệt thật. Mỗi runner tạo Compose project, PKI, secrets và
volumes dùng một lần; không trỏ vào dữ liệu hiện có.

```sh
npm ci --prefix frontend
node tests/p4/test_session.mjs
npm run build --prefix frontend
python tests/p4/run.py
python tests/p5/run.py
# Toàn bộ P0/P1/P2/P3 chạy ở release legacy rõ ràng:
python tests/p3/run.py
```

Xem [P4 test setup](tests/p4/README.md), [kiến trúc và OAuth flow](docs/authentication/p4-architecture.md),
[account migration/cutover/rollback](docs/deployment/p4-cutover.md) và
[đồng bộ/rotation khóa](docs/deployment/p4-key-rotation.md).
Các cấu hình HTTPS origin/issuer trong realm là giá trị development chính xác;
production cần operator review certificate, hostname, client policy và mappings.
Không dùng local development CA cho production, không bỏ xác minh TLS.

## Giới hạn bảo mật

Kong JWT OSS không thay thế kiểm tra issuer/audience/token type ở resource server.
Quyền không lấy từ token/header không tin cậy; email không tự liên kết tài khoản.
Logout thu hồi phiên refresh, nhưng access token có thể còn hiệu lực đến hạn.
JWT cache/rotation cần quy trình vận hành có kiểm soát. Frontend không phải BFF;
XSS vẫn có thể đọc token trong bộ nhớ. SQL/monitoring TLS, HA, vault và MFA policy
chưa được chứng nhận. P5 đã sửa webhook replay, null-input và SSRF IPv4-mapped
IPv6 trong ứng viên; các lỗi legacy D01/D02 được giữ làm baseline và bị thay thế
bởi OIDC trong ứng viên. Xem kết quả thực chạy và gate DNS trong P5 report.

Database nằm trên network internal riêng và không publish port. HTTPS/mTLS P2,
CA/SAN checking và client enrollment được giữ nguyên. [P2 TLS guide](docs/deployment/p2-tls.md)
và [P1 deployment guide](docs/deployment/p1-deployment.md) mô tả trust và quyền DB.
Network membership không phải directional firewall. SSRF chỉ validate URL/DNS,
không tải nội dung URL. Raw DNS hoạt động là điều kiện nghiệm thu regression.

Generated secrets, private keys, tokens, dependencies, artifacts và `_local_archive/`
không được commit. [Workspace B transfer](docs/deployment/p5-workspace-transfer.md)
chỉ hướng dẫn nhập bundle và push từ workspace được cấp quyền riêng.
