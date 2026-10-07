# Huong Dan Demo FloraSecure Shop

File nay dung lam kich ban demo nhanh khi bao cao voi giang vien.

## 1. Chuan bi truoc khi demo

Mo terminal tai thu muc frontend:

```bash
cd D:\MatMaHoc\Project_CLOUD_API\florasecure-shop\florasecure
npm install
npm run dev -- --host 127.0.0.1 --port 5174
```

Mo trinh duyet:

```text
http://127.0.0.1:5174/login
```

Luu y:

- Frontend dang dung Vite proxy trong `vite.config.js` de goi backend ngrok.
- Khong can set `VITE_API_BASE_URL` khi chay local.
- Neu backend moi thay doi rate limit, can restart backend/gateway ben backend truoc. Frontend chi can refresh browser.

## 2. Tai khoan demo

| Vai tro | Email | Mat khau |
|---|---|---|
| Staff | demo_api4@example.com | Demo@123 |
| Customer | customer_order@example.com | Customer@123 |
| Customer B | customer_test2@example.com | Customer2@123 |

Khi demo, co the bam nut `Staff`, `Customer`, hoac `Customer B` tren man hinh login de tu dien thong tin.

## 3. Kich ban demo de bao cao

### Buoc 1: Dang nhap va JWT

1. Mo `http://127.0.0.1:5174/login`.
2. Bam `Staff`.
3. Bam `Sign in`.
4. Giai thich:
   - Frontend gui login theo OAuth2 form `username/password`.
   - Backend tra ve `access_token`, `refresh_token`, `expires_in`.
   - Frontend luu token va tu dong gan header `Authorization: Bearer ...` cho cac request sau.

Sau khi login thanh cong, trang se chuyen vao `Admin Dashboard`.

### Buoc 2: Dashboard va phan quyen Staff

Tai `Admin Dashboard`, trinh bay:

- User hien tai la `staff`.
- Staff co quyen quan ly san pham va xem don hang.
- Dashboard goi API that de lay so luong products/orders.
- Neu backend loi, UI hien thong bao loi ro rang thay vi hien du lieu gia.

### Buoc 3: Danh sach san pham

1. Vao menu `Products`.
2. Chi ra danh sach san pham hien co, vi du:
   - `Business Laptop`
   - `Hoa Hong Sophia`
   - `Bo Hoa Hong Do`
   - `Bo Hoa Huong Duong`
   - `Bo Hoa Ly Trang`
3. Giai thich:
   - Frontend doc response dang wrapper:

```json
{
  "total": 5,
  "skip": 0,
  "limit": 20,
  "items": []
}
```

### Buoc 4: Tao san pham moi

1. Vao `Products`.
2. Bam `Create Product`.
3. Nhap vi du:

```text
SKU: FLOWER-DEMO-001
Product name: Bo Hoa Demo Bao Cao
Description: San pham tao truc tiep trong buoi demo.
Price: 300000
Stock: 5
Image URL: https://images.unsplash.com/photo-1518895949257-7621c3c786d7
```

4. Bam `Create product`.
5. San pham moi se xuat hien trong danh sach.

Giai thich voi giang vien:

- Staff duoc phep tao san pham theo RBAC.
- Request tao san pham goi `POST /api/v1/products/`.
- Endpoint list/create can co dau `/` cuoi de tranh redirect sai sang `http://backend:8000/...`.

### Buoc 5: Cap nhat va xoa san pham

1. Tai card san pham, bam `Update`.
2. Doi stock hoac gia.
3. Bam `Save changes`.
4. Neu can demo xoa, bam `Delete`.

Giai thich:

- Update goi `PATCH /api/v1/products/{id}`.
- Delete goi `DELETE /api/v1/products/{id}`.
- Frontend an nut create/update/delete voi user `customer`.

### Buoc 6: Dang nhap Customer va dat hang

1. Logout.
2. Dang nhap bang `Customer`.
3. Vao `Products`.
4. Bam `Order` o mot san pham.
5. Vao `Orders` de xem don hang cua customer.

Giai thich:

- Customer chi duoc xem san pham va tao don hang.
- Customer khong thay nut Create/Update/Delete Product.
- Backend van la noi enforcement chinh; UI chi la lop UX.

### Buoc 7: BOLA / Ownership check

1. Dang nhap Customer A va xem order cua minh.
2. Neu co ID order cua Customer B, thu nhap vao test BOLA trong `Security Center`.
3. Backend phai tra `403 Forbidden` neu user khong so huu order.

Giai thich:

- Day la demo Broken Object Level Authorization protection.
- Frontend khong mock ket qua; request gui that toi backend.

### Buoc 8: Security Center

Vao `Security Center`, demo cac muc:

- JWT Information: token status, role, thoi gian het han.
- RBAC: bang quyen customer/staff/admin.
- Missing JWT: goi `/auth/me` khong co Authorization.
- Unauthorized Admin Access: customer thu tao product.
- Rate Limit: nhieu lan login sai de kich hoat `429`.
- Webhook Signature: test chu ky dung/sai.
- SSRF: thu cac URL noi bo nhu `localhost`, `127.0.0.1`, `169.254.169.254`.

Luu y khi demo rate limit:

- Neu bam rate limit qua nhieu, backend co the tam thoi chan request.
- Khi backend da nang rate limit, refresh browser la du; neu backend config chua apply thi restart backend/gateway.

## 4. Cac loi thuong gap va cach giai thich

### Loi login failed

Kiem tra:

- Backend/ngrok con song khong.
- Frontend dang chay port `5174` khong.
- Vite proxy co trong `vite.config.js` khong.

Ly do da tung gap:

- Backend login yeu cau form `username/password`, khong phai JSON `{ email, password }`.
- Browser goi truc tiep ngrok co the bi CORS/preflight.
- Giai phap hien tai: frontend goi `/api/...`, Vite proxy sang backend.

### Product/Order hien dau `-`

Y nghia:

- Request API bi loi, timeout, hoac backend rate limit.
- Khong phai frontend tu tao du lieu rong.

Kiem tra nhanh:

```bash
curl http://127.0.0.1:5174/api/v1/products/
```

### Redirect sang `backend:8000`

Ly do:

- Goi sai trailing slash voi FastAPI.
- `/api/v1/products` redirect sang `/api/v1/products/`.
- Redirect location tu backend co the la `http://backend:8000/...`, may local khong resolve duoc.

Fix da ap dung:

- List/Create product dung `/api/v1/products/`.
- Update/Delete product dung `/api/v1/products/{id}`.

## 5. Noi dung nen nhan manh khi thuyet trinh

- Day la frontend ket noi API that, khong mock data.
- JWT duoc gan tu dong qua Axios interceptor.
- RBAC duoc the hien o UI va duoc backend enforcement.
- Ownership check/BOLA duoc demo bang request that.
- Rate limiting, signed webhook, SSRF protection deu co man hinh test rieng.
- Vite proxy giup local frontend noi voi backend ngrok ma khong bi CORS.

## 6. Checklist truoc gio bao cao

- Backend/gateway dang chay.
- Ngrok URL trong `vite.config.js` con dung.
- Chay frontend o `http://127.0.0.1:5174`.
- Dang nhap Staff thanh cong.
- `Products` hien danh sach san pham.
- Tao thu mot san pham demo thanh cong.
- Dang nhap Customer va dat hang duoc.
- Security Center co the goi cac test chinh.
