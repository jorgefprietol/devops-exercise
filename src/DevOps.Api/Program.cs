using DevOps.Api;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.ConfigureKestrel(options => options.Limits.MaxRequestBodySize = 16_384);
builder.Services.AddSingleton(_ => SecuritySettings.Load(builder.Configuration));
builder.Services.AddSingleton<TokenValidator>();
builder.Services.AddSingleton<IReplayStore, RedisReplayStore>();
var app = builder.Build();
_ = app.Services.GetRequiredService<SecuritySettings>();
app.MapGet("/health/live", () => Results.Ok());
app.MapGet("/health/ready", async (IReplayStore store) =>
    await store.IsReadyAsync() ? Results.Ok() : Results.StatusCode(503));
app.MapFallback("/{**path}", ApiHandler.Handle);
app.Run();

public partial class Program { }
