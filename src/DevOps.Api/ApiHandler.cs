using System.Text.Json;
using System.Text.Json.Serialization;

namespace DevOps.Api;

public sealed record MessageRequest(
    [property: JsonPropertyName("message")] string? Message,
    [property: JsonPropertyName("to")] string? To,
    [property: JsonPropertyName("from")] string? From,
    [property: JsonPropertyName("timeToLifeSec")] int TimeToLifeSec)
{
    public bool IsValid() =>
        !string.IsNullOrWhiteSpace(Message) && Message.Length <= 2000 &&
        !string.IsNullOrWhiteSpace(To) && To.Length <= 200 &&
        !string.IsNullOrWhiteSpace(From) && From.Length <= 200 &&
        TimeToLifeSec is >= 1 and <= 86400;
}

public static class ApiHandler
{
    public static async Task Handle(HttpContext context)
    {
        if (!string.Equals(context.Request.Path.Value, "/DevOps", StringComparison.Ordinal))
        { await Error(context, 404); return; }
        if (!HttpMethods.IsPost(context.Request.Method))
        {
            context.Response.Headers.Allow = "POST";
            await Error(context, 405); return;
        }
        var settings = context.RequestServices.GetRequiredService<SecuritySettings>();
        var headers = context.Request.Headers;
        if (headers["X-Parse-REST-API-Key"].Count != 1 ||
            !settings.MatchesApiKey(headers["X-Parse-REST-API-Key"].ToString()) ||
            headers["X-JWT-KWY"].Count != 1)
        { await Error(context, 401); return; }
        var token = context.RequestServices.GetRequiredService<TokenValidator>().Validate(headers["X-JWT-KWY"].ToString());
        if (token is null) { await Error(context, 401); return; }
        if (!context.Request.HasJsonContentType()) { await Error(context, 415); return; }
        if (context.Request.ContentLength > 16384) { await Error(context, 413); return; }
        MessageRequest? body;
        try { body = await context.Request.ReadFromJsonAsync<MessageRequest>(context.RequestAborted); }
        catch (JsonException) { await Error(context, 400); return; }
        catch (BadHttpRequestException ex) { await Error(context, ex.StatusCode); return; }
        if (body is null || !body.IsValid()) { await Error(context, 400); return; }
        try
        {
            if (!await context.RequestServices.GetRequiredService<IReplayStore>().TryConsumeAsync(token.Id, token.ExpiresAt))
            { await Error(context, 409); return; }
        }
        catch (ReplayStoreUnavailableException) { await Error(context, 503); return; }
        await context.Response.WriteAsJsonAsync(new { message = $"Hello {body.To} your message will be sent" });
    }
    private static async Task Error(HttpContext context, int status)
    {
        context.Response.StatusCode = status;
        context.Response.ContentType = "text/plain; charset=utf-8";
        if (!HttpMethods.IsHead(context.Request.Method)) await context.Response.WriteAsync("ERROR");
    }
}
