# Cloud API Security for SME — FloraSecure

Đồ án NT219: prototype API cho shop bán hoa, tập trung vào xác thực JWT,
phân quyền RBAC, ownership đơn hàng, webhook HMAC và giám sát API.

## Cấu trúc

- `backend/`: FastAPI, SQLAlchemy, Alembic, PostgreSQL.
- `frontend/`: React, Vite, Tailwind, Axios.
- `gateway/`: cấu hình Kong.
- `docker/`: Compose chính và mẫu biến môi trường hạ tầng.
- `monitoring/`: Loki, Promtail, Grafana và dashboard.
- `docs/`: kiến trúc, threat model, RBAC và yêu cầu bảo mật.
- `tests/p0/`, `tests/p1/`, `tests/p2/`: baseline, cách ly và HTTPS/mTLS regression.
- `reports/`: báo cáo theo chương, bản tổng hợp và bản nháp.
- `slides/`: hình ảnh phục vụ trình bày.

## Chạy local

Yêu cầu: Docker Desktop với Linux containers, Docker Compose, Node.js/npm.
Trong PowerShell, từ thư mục gốc:

```powershell
Copy-Item docker/.env.example docker/.env
Copy-Item frontend/.env.example frontend/.env
python docker/generate_secrets.py --new-deployment
python -m pip install -r docker/pki-requirements.txt
python docker/pki.py --development-only
```

Lệnh tạo secret chỉ dùng cho deployment mới; không ghi đè secret hiện có.
Compose dùng file secret trong `docker/.secrets/`, không đọc `backend/.env`.
`docker/.env` chỉ chứa cấu hình không bí mật. Hạn chế quyền truy cập thư mục
secret bằng ACL của hệ điều hành. Với dữ liệu/môi trường cũ, giữ nguyên signing
key, webhook secret và mật khẩu database; làm theo hướng dẫn chuyển đổi trong
[P1 deployment](docs/deployment/p1-deployment.md).

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml up --build -d --wait
# Node phải tin CA của gateway; giữ secure=true trong Vite proxy.
$env:NODE_EXTRA_CA_CERTS = (Resolve-Path docker/certs/trust/edge-ca.pem).Path
Set-Location frontend
npm ci
npm run dev
```

- Frontend: http://localhost:5173
- Gateway: https://localhost:8443 (Swagger tắt khi DEBUG=false)
- Health: https://localhost:8443/health
- Readiness: https://localhost:8443/health/ready
- Keycloak: http://localhost:8080
- Grafana: http://localhost:3001

Compose chạy bootstrap và Alembic bằng hai job riêng trước khi khởi động API.
FastAPI dùng role runtime giới hạn DML, không dùng PostgreSQL superuser và không
chạy migration khi restart. Database mới chưa có tài khoản
hay sản phẩm demo: đăng ký customer qua `/api/v1/auth/register`.
Tài khoản staff/admin cần được provision riêng. Các tài khoản ghi trong hướng
dẫn demo cũ thuộc môi trường lab từ xa, không được seed tự động.

Dừng stack bằng:

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml down
```

## Trạng thái và giới hạn

P2 dùng HTTPS ở Kong và HTTPS/mTLS từ Kong đến FastAPI; không có backend HTTP
listener hay published backend port. CA local development chưa được máy/browser
tin tự động: dùng CA file với CLI/Node, hoặc import CA public của edge vào trust
store development sau khi kiểm tra fingerprint. Không bỏ certificate verification.
Xem [P2 TLS: trust, issuance, renewal, rotation, recovery](docs/deployment/p2-tls.md).
`docs/deployment/compose-mtls.reference.yml` và `backend/nginx/default.conf` là ví dụ
lab cũ không tương thích P1/P2, không được dùng làm deployment/overlay hiện tại.
Generated certificates, private keys và CA signing keys không được commit.

FastAPI hiện tự cấp JWT; Keycloak có chạy nhưng chưa tích hợp OIDC/PKCE.
Kong hiện có rate limit, chưa cấu hình JWT validation/WAF.
Frontend lưu session trong localStorage; logout chưa gọi revoke backend.
Webhook có HMAC/timestamp nhưng chưa chống sự kiện trùng trong cửa sổ thời gian.
SSRF endpoint chỉ validate URL/DNS, không tải nội dung từ URL.
Monitoring đọc Docker JSON logs chỉ đọc, không mount Docker socket. P0/P1/P2 có bộ
test tự động; xem [P2 test record](docs/testing/p2-results.md). Audit logging/alerts còn cần hoàn thiện. Database nằm trên network
internal riêng. API network là bridge thường để giữ DNS cho SSRF validator;
Network membership không phải directional firewall hay encryption. Chỉ API transport
Kong–FastAPI được mã hóa trong P2; DB và monitoring transport chưa có TLS. Nội dung báo cáo có thể mô
tả kiến trúc đích rộng hơn code hiện có.
Các thư viện chưa được kiểm toán hoặc nâng cấp trong đợt dọn thư mục này.

## Chuẩn bị GitHub

`.gitignore` loại secrets, private keys, dependencies, build và `_local_archive/`.
`_local_archive/` lưu nguyên bản các thư mục cũ, gồm lịch sử Git và môi trường local;
không upload thư mục đó. Xem `docs/deployment/github-checklist.md` trước khi push.
Không dùng `git add -f` với các file bị ignore.
