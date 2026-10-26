# Part A — Kong/OpenSSL assessment

Ngày: 2026-10-26. Baseline `d79cb6060e95ba58cd797b6ef24b3b938ae80b8a`.
**A1 decision: BLOCKED. Candidate không được kích hoạt.** Đây là kết quả nghiên
cứu/inspection, không phải một crypto remediation đã nghiệm thu.

## Artifact và kết quả thực thi

| | Baseline | Candidate OSS được kiểm tra |
|---|---|---|
|Version|3.9.3|3.9.4|
|Descriptor / Engine ID ghi nhận|`sha256:92035d16d7ff86b7bc12fb1d0090d29357d924238b1880f78735f3f2fea6b631`|`sha256:aa4a4687b1330e427ad0d3b27a0606b833894297c78abf1a212edc9ba73c8620`|
|linux/amd64 child manifest|`sha256:6328373b745d9228d42d5cfe8338ab39370a13aef8fcb0d0d72c0caa6eb3b1d7`|`sha256:45993f7e2c77036e52e553419553f58eb06b7dd87513e3350e230dc04b5ebe6c`|
|nginx build|OpenResty1.25.3.2 / OpenSSL3.2.3|OpenSSL3.2.3; chi tiết trong receipt|
|Runtime FFI `OpenSSL_version(0)`|OpenSSL3.2.3 / `0x30200030`|OpenSSL3.2.3 / `0x30200030`|
|Dynamic TLS libraries|`/usr/local/kong/lib/libssl.so.3`, `libcrypto.so.3`|Cùng hai đường dẫn; hashes trong receipt|
|OS CLI|OpenSSL3.0.13|Đọc trực tiếp trong receipt; không dùng để kết luận TLS fixed|
|REL-001|BLOCKED|BLOCKED; chưa có chứng nhận extended security fixes|

[Raw sanitized command receipts và file hashes](part-a-evidence-20261026/kong-crypto-inspection.json)
ghi exact argv, timestamps và exits. `ldd` xác nhận dynamic linkage tới thư viện
của Kong; LuaJIT FFI gọi chính `libcrypto.so.3` đó. Đây không phải bằng chứng chỉ
từ Dockerfile hay `/usr/bin/openssl`. Runtime address ASLR được bỏ khỏi báo cáo.

Mỗi inspection container không mạng, không volume, rootfs read-only, tmpfs16MiB,
cap-dropALL/no-new-privileges, memory/swap128MiB,0.5CPU,pids48 và `--rm`. Không có
server listener, dữ liệu ứng dụng hay khóa thật. Attempt đầu `kong version` thất
bại vì `/tmp` read-only; thêm tmpfs có giới hạn, không mở writable root hoặc giảm
certificate verification. Tất cả bốn inspection executions sau đó exit0.

## A0 candidate decision

1. **Official Kong OSS3.9.4:** [release](https://github.com/Kong/kong/releases/tag/3.9.4)
   và [tagged changelog](https://raw.githubusercontent.com/Kong/kong/3.9.4/CHANGELOG.md)
   xác minh tồn tại, edition OSS và bản vá clustering SQL injection. Không phải
   bản vá lifecycle OpenSSL; actual library vẫn3.2.3. Không thay cấu hình chỉ để
   đạt tag mới. CVE clustering không được nhập nhầm vào đánh giá crypto hoặc coi
   là đã chứng minh reachable trong deployment DB-less hiện tại.
2. **Newer supported OSS:** chưa xác lập artifact có supported crypto trong nguồn
   được kiểm tra. Không dùng support policy Enterprise làm bằng chứng OSS.
3. **Maintained/reproducible OSS build:** cần source/dependency/toolchain pins,
   hashes, crypto/provider compatibility, ongoing maintainer và patch process;
   chưa có strategy đáp ứng các điều kiện đó được chứng minh. Không thay `.so`
   trực tiếp trong image hoặc copy binary vào container đang chạy.
4. **Enterprise hoặc gateway migration:** cần owner duyệt riêng. Không thực hiện.
5. **Risk acceptance:** chưa có owner exception; assessment không phê duyệt thay.

OpenSSL xác nhận [3.2 public EOL2025-11-23](https://openssl-library.org/post/2025-11-25-eol-32/).
Không có bằng chứng extended support cho đúng artifact đang xét. X.509/CA/SAN,
TLS1.2/1.3 và upstream mTLS vẫn là controls; chúng không gia hạn lifecycle.

## Compatibility và validation gate

Baseline vẫn giữ nguyên Kong image/config, JWT RS256/kid/exp, backend independent
issuer/audience/type/RBAC/ownership, P5 preauth limiter, P6 Lua telemetry và request
IDs, trusted-forwarded boundary, UID1000/keys0600, `/run/kong` tmpfs, HTTPS/mTLS,
CA/SAN/EKU/client enrollment và rotations. Không có runtime diff hoặc fallback.

Chưa chạy fresh full baseline/candidate stack: ba mẫu đầu host Windows chỉ còn
0.89–0.96GiB physical memory khả dụng; mẫu sau khoảng1.40GiB. Chưa chứng minh đủ
headroom cho full stack dù WSL MemAvailable cao hơn. Không
đánh đồng ceiling/free của guest với headroom vật lý của host. Theo resource gate
của yêu cầu, dừng builds/full-stack/scanner nặng; không tắt ứng dụng người dùng.

Không đánh dấu configuration parse, startup/restart/recreate,16 TLS methods,
JWT/claims/RBAC/BOLA, rate-limit recovery, signing rotation/outage, browser SDK/SPA,
logging/privacy hoặc DB/network regression là PASS ở Part A. Chúng là NOT EXECUTED.
Candidate đã không qua crypto selection gate; tăng RAM không tự sửa REL-001.

## Next action và rollback

Xác nhận một trong hai hướng: vendor evidence bảo trì exact library, hoặc một
artifact OSS/rebuild strategy có maintenance provenance rồi chạy full acceptance
trong môi trường đủ headroom. Enterprise hoặc đổi gateway cần quyết định mới.

Không có deployment đã đổi để rollback. Với candidate tương lai, DB-less rollback
phải khôi phục matching image + declarative config + JWT credentials + enrolled
cert/key/CA trust + limiter/telemetry modules/UID/prefix. Không cần Kong DB migration
trong kiến trúc hiện tại; không dùng verification bypass để phục hồi.

**REL-001 vẫn BLOCKED. A1 result được ghi trước mọi Loki implementation; tác vụ
hiện chỉ tiếp tục independent Loki artifact/config inspection.**
