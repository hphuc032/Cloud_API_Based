"""P6 observability only; P5 authentication and quota functions retained."""
import copy
from deployment.p5_gateway import harden

BOUNDARY = r'''
-- Nginx request_id is generated from 16 random bytes at the gateway.
-- Format as canonical UUIDv4 without accepting any inbound ID.
local raw = ngx.var.request_id
local id = raw:sub(1,8).."-"..raw:sub(9,12).."-4"..raw:sub(14,16).."-8"..raw:sub(18,20).."-"..raw:sub(21,32)
kong.ctx.shared.p6_request_id = id
kong.service.request.set_header("X-Request-ID", id)
'''
HEADERS = r'''
if kong.ctx.shared.p6_request_id then
  kong.response.set_header("X-Request-ID", kong.ctx.shared.p6_request_id)
end
'''

def observe(document):
    document = harden(copy.deepcopy(document))
    document['plugins'].append({'name':'p6-telemetry','config':{}})
    for plugin in document['plugins']:
        if plugin['name'] == 'pre-function': plugin['config']['access'].insert(0, BOUNDARY)
        if plugin['name'] == 'post-function':
            plugin['config']['header_filter'].append(HEADERS)
            plugin['config']['log'] = []
    return document
