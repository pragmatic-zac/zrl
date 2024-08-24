local zset_key = KEYS[1]
local user = ARGV[1]
local current_time = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local capacity = tonumber(ARGV[4])
local tokens_needed = tonumber(ARGV[5])

-- get the last time (aka score) for the user
local last_timestamp = redis.call('zscore', zset_key, user)

-- if no record, assume it's a new bucket
if not last_timestamp then
    last_timestamp = 0
end

local time_passed = current_time - last_timestamp
local tokens_to_add = refill_rate * time_passed

-- calculate new token count but don't exceed capacity
local tokens_available = math.min(tokens_to_add, capacity)

if tokens_needed > tokens_available then
    -- not enough tokens, deny the request
    return 0
end

-- update the new timestamp
-- take current time and push it out depending on refill rate
-- this means we don't have to keep track of timestamp AND count, can just use timestamp
local next_timestamp = current_time + (tokens_needed / refill_rate)

redis.call('zadd', zset_key, next_timestamp, user)

-- finally, allow the request
return 1