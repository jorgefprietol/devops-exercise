using StackExchange.Redis;

namespace DevOps.Api;

public interface IReplayStore
{
    Task<bool> TryConsumeAsync(string id, DateTime expiresAt);
    Task<bool> IsReadyAsync();
}

public sealed class ReplayStoreUnavailableException(Exception inner) : Exception("El almacén de control de repetición no está disponible.", inner);

public sealed class RedisReplayStore : IReplayStore, IDisposable
{
    private readonly Lazy<Task<ConnectionMultiplexer>> connection;
    public RedisReplayStore(IConfiguration configuration)
    {
        var config = configuration["REDIS_CONNECTION"] ?? "localhost:6379,abortConnect=false";
        connection = new(() => ConnectionMultiplexer.ConnectAsync(config));
    }
    public async Task<bool> TryConsumeAsync(string id, DateTime expiresAt)
    {
        var ttl = expiresAt - DateTime.UtcNow;
        if (ttl <= TimeSpan.Zero) return false;
        try
        {
            var redis = await connection.Value;
            // Operación atómica compartida por las réplicas; caduca junto con el JWT.
            return await redis.GetDatabase().StringSetAsync("devops:jti:" + id, "used", ttl, When.NotExists);
        }
        catch (Exception ex) when (ex is RedisException or TimeoutException)
        { throw new ReplayStoreUnavailableException(ex); }
    }
    public async Task<bool> IsReadyAsync()
    {
        try { await (await connection.Value).GetDatabase().PingAsync(); return true; }
        catch (Exception ex) when (ex is RedisException or TimeoutException) { return false; }
    }
    public void Dispose()
    {
        if (connection.IsValueCreated && connection.Value.IsCompletedSuccessfully)
            connection.Value.Result.Dispose();
    }
}
