# Checklist trước khi push GitHub

- Kiểm tra `git status --short` và `git diff --cached --stat`.
- Không stage `.env`, khóa riêng, certs, `_local_archive`, `.venv`, node_modules.
- Kiểm tra báo cáo DOCX/PDF, hình ảnh, XLSX và JSON dashboard để loại token,
  mật khẩu thực, dữ liệu cá nhân và thông tin nhạy cảm trong screenshot.
  Các artifact này cần người sở hữu kiểm tra trước khi công khai.
- Đổi các credentials đã từng được chia sẻ nếu còn sử dụng trên môi trường thật.
- Chọn repo GitHub đích và quyền private/public; root repo chưa gắn remote.
- Build frontend bằng `npm ci` và `npm run build`.
- Dựng stack với secrets riêng và kiểm tra health/Swagger trước khi đánh dấu release.
- Repo gốc của backend được giữ trong `_local_archive`; repo root là lịch sử mới
  để gom cả frontend, backend và tài liệu. Không push đè lịch sử repo cũ.

Sau khi kiểm tra, có thể dùng:

```powershell
git add README.md .gitignore backend frontend gateway docker monitoring docs tests reports slides
git diff --cached --stat
git commit -m "Organize Cloud API Security project"
git remote add origin <URL_REPO_GITHUB_CUA_BAN>
git push -u origin main
```
