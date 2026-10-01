using DevOps.Api;
using System.Diagnostics;

var builder = WebApplication.CreateBuilder(args);
builder.Logging.ClearProviders();
builder.Logging.AddJsonConsole();
builder.WebHost.ConfigureKestrel(options => options.Limits.MaxRequestBodySize = 16_384);
EvaluationIssuer.Configure(builder);
builder.Services.AddSingleton(_ => SecuritySettings.Load(builder.Configuration));
builder.Services.AddSingleton<TokenValidator>();
builder.Services.AddSingleton<IReplayStore, RedisReplayStore>();
var app = builder.Build();
var issuerMode = app.Configuration["SERVICE_ROLE"] == "token-issuer";
if (!issuerMode) _ = app.Services.GetRequiredService<SecuritySettings>();
app.Use(async (context, next) =>
{
    context.Response.Headers["Cache-Control"] = "no-store";
    context.Response.Headers["X-Content-Type-Options"] = "nosniff";
    var started = Stopwatch.GetTimestamp();
    var status = 500;
    try
    {
        await next(context);
        status = context.Response.StatusCode;
    }
    finally
    {
        if (context.Request.Path == "/DevOps")
            app.Logger.LogInformation("Solicitud {Metodo} /DevOps: estado {Estado}, duración {DuracionMs} ms, referencia {Referencia}",
                context.Request.Method, status, Stopwatch.GetElapsedTime(started).TotalMilliseconds, context.TraceIdentifier);
    }
});
app.MapGet("/health/live", () => Results.Ok());
if (issuerMode) EvaluationIssuer.Map(app);
else
{
    app.MapGet("/health/ready", async (IReplayStore store) =>
        await store.IsReadyAsync() ? Results.Ok() : Results.StatusCode(503));
    app.MapFallback("/{**path}", ApiHandler.Handle);
}
app.Run();

public partial class Program { }
