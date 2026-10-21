"""Auditable built-in Kong OSS functions; no external/Enterprise plugin.

pre-function access priority is before JWT. Native 60/minute limiter remains
after JWT. IPs are transport peers unless an independently reviewed proxy is trusted.
"""

PRE_AUTH = r'''
if kong.request.get_method() == "OPTIONS" then return end
local path = kong.request.get_path()
local limit, group = 120, "other"
if path:match("^/api/v1/users") then limit, group = 60, "users"
elseif path:match("^/api/v1/security/") then limit, group = 45, "security"
elseif path:match("^/api/v1/orders") and kong.request.get_method() ~= "GET" then limit, group = 60, "orders-write"
elseif path == "/api/v1/webhooks/receive" then limit, group = 90, "webhook" end
local window = math.floor(ngx.now() / 60)
local remaining = math.max(1, 60 - (ngx.time() % 60))
local ip = kong.client.get_ip()
local dict = ngx.shared.p5_rate_limits
if not dict then return kong.response.exit(503, {message="Throttle unavailable"}) end
for _, budget in ipairs({{"global",120},{group,limit}}) do
  local key = budget[1] .. ":" .. ip .. ":" .. tostring(window)
  local count, err = dict:incr(key,1,0,61)
  if not count then return kong.response.exit(503, {message="Throttle unavailable"}) end
  if count > budget[2] then
    return kong.response.exit(429,{message="Pre-authentication rate limit exceeded"},
      {["Retry-After"]=tostring(remaining),["X-RateLimit-Layer"]="pre-auth",
       ["X-RateLimit-Limit"]=tostring(budget[2])})
  end
end
'''

HEADERS = r'''
kong.response.set_header("X-Content-Type-Options","nosniff")
kong.response.set_header("X-Frame-Options","DENY")
kong.response.set_header("Strict-Transport-Security","max-age=31536000")
kong.response.set_header("Referrer-Policy","strict-origin-when-cross-origin")
kong.response.set_header("Permissions-Policy","camera=(), microphone=(), geolocation=(), payment=()")
kong.response.set_header("Content-Security-Policy","default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
kong.response.set_header("Cache-Control","no-store")
kong.response.set_header("X-XSS-Protection","0")
'''

LOG = r'''
if ngx.status >= 400 then
  local route = kong.router.get_route()
  kong.log.notice("p5_rejection status=",ngx.status," route=",route and route.name or "unmatched")
end
'''

def harden(document):
    document['plugins'].extend([
        {'name':'pre-function','config':{'access':[PRE_AUTH]}},
        {'name':'post-function','config':{'header_filter':[HEADERS],'log':[LOG]}}])
    for plugin in document['plugins']:
        if plugin['name']=='cors':
            plugin['config']['headers']=['Authorization','Content-Type','X-Signature','X-Timestamp','X-Request-ID']
            plugin['config']['exposed_headers']=['X-Request-ID','X-Webhook-Replayed','Retry-After',
                'X-RateLimit-Layer','X-RateLimit-Limit','Strict-Transport-Security','X-Content-Type-Options',
                'X-Frame-Options','Referrer-Policy','Permissions-Policy','Content-Security-Policy']
    for route in document['services'][0]['routes']:
        if route['name']=='hmac-webhook':
            route['plugins']=[{'name':'request-size-limiting','config':{
                'allowed_payload_size':64,'size_unit':'kilobytes','require_content_length':False}}]
    return document
