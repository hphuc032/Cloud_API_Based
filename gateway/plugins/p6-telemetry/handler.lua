-- Read the bounded in-memory OpenResty error ring, never persist raw error text.
-- No authentication, request, response or TLS policy is changed by this plugin.
local errlog = require "ngx.errlog"
local json = require "cjson.safe"
local Handler = { PRIORITY = 10, VERSION = "0.1.0" }
local reasons = {
  "does not match",
  "unable to verify the first certificate",
  "certificate has expired",
  "unsuitable certificate purpose",
}

function Handler:log()
  local entries = errlog.get_logs(64)
  if not entries then return end
  local observed = {}
  for i = 3, #entries, 3 do
    local text = type(entries[i]) == "string" and string.lower(entries[i]) or ""
    local boundary = string.find(text, ", client:", 1, true) or string.find(text, ", request:", 1, true)
    local prefix = boundary and string.sub(text, 1, boundary - 1) or text
    local tls_error = string.find(prefix, "upstream ssl certificate verify error:", 1, true)
                   or string.find(prefix, "upstream ssl certificate does not match", 1, true)
    for _, reason in ipairs(reasons) do
      if tls_error and string.find(prefix, reason, 1, true) and not observed[reason] then
        observed[reason] = true
        -- A constant reason is the only information copied out of the raw ring.
        -- Ring records can include earlier worker activity, so do not invent a
        -- request correlation when the error cannot be attributed independently.
        local record = {
          service = "kong", level = "error", event_type = "mtls_verification_failed",
          event_outcome = "denied", security_reason = reason,
          request_id = "unattributed",
        }
        io.stdout:write(json.encode(record), "\n")
        io.stdout:flush()
      end
    end
  end
end
return Handler
