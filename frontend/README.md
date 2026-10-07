# FloraSecure frontend

React + Vite + Tailwind. Xem README ở thư mục gốc để dựng stack đầy đủ.

```powershell
Copy-Item .env.example .env
npm ci
npm run dev
```

Mặc định: http://localhost:5173. Browser gọi `/api` qua Vite proxy đến
`API_PROXY_TARGET` (mặc định http://127.0.0.1:8000).
Khi deploy, đặt `VITE_API_BASE_URL` thành URL gateway và cấu hình CORS tương ứng.

```powershell
npm run build
npm run preview
```

Các màn hình: Login, Customer/Admin Dashboard, Products, Orders, Profile,
Security Center và Monitoring. Session hiện lưu trong localStorage; luồng
Keycloak OIDC/PKCE và logout/revoke chưa tích hợp.

`DEMO_GUIDE.md` là hướng dẫn của môi trường demo cũ; tài khoản và URL trong đó
không tự được provision trong stack local mới. Không dùng credentials demo
cho môi trường thật.
