using System.Globalization;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Threading.RateLimiting;
using Microsoft.IdentityModel.Tokens;

namespace DevOps.Api;

// Servicio auxiliar de evaluación: se ejecuta en un contenedor independiente.
public sealed class EvaluationIssuer
{
    private readonly byte[] credentialHash;
    private readonly SigningCredentials signing;

    public EvaluationIssuer(IConfiguration config)
    {
        var credential = config["ISSUER_KEY"] ?? "";
        var secret = config["JWT_SECRET"] ?? "";
        if (Encoding.UTF8.GetByteCount(credential) < 32 || Encoding.UTF8.GetByteCount(secret) < 32 || credential == secret)
            throw new InvalidOperationException("Configura ISSUER_KEY y JWT_SECRET independientes, de al menos 32 bytes.");
        credentialHash = SHA256.HashData(Encoding.UTF8.GetBytes(credential));
        signing = new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret)), SecurityAlgorithms.HmacSha256);
    }

    public static void Configure(WebApplicationBuilder builder)
    {
        builder.Services.AddSingleton<EvaluationIssuer>();
        builder.Services.AddRateLimiter(options =>
        {
            options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;
            options.AddPolicy("emision", _ => RateLimitPartition.GetFixedWindowLimiter("evaluacion", _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 30,
                Window = TimeSpan.FromMinutes(1),
                QueueLimit = 0,
                AutoReplenishment = true
            }));
        });
    }

    public static void Map(WebApplication app)
    {
        _ = app.Services.GetRequiredService<EvaluationIssuer>();
        app.UseRateLimiter();
        app.MapGet("/health/ready", () => Results.Ok());
        app.MapPost("/auth/token", (HttpContext context, EvaluationIssuer issuer) => issuer.Issue(context))
            .RequireRateLimiting("emision");
    }

    public IResult Issue(HttpContext context)
    {
        var keys = context.Request.Headers["X-Evaluation-Key"];
        if (keys.Count != 1 || keys[0] is not { Length: <= 256 } key ||
            !CryptographicOperations.FixedTimeEquals(credentialHash, SHA256.HashData(Encoding.UTF8.GetBytes(key))))
            return Results.Unauthorized();

        var now = DateTime.UtcNow;
        var jwt = new JwtSecurityToken(issuer: "devops-candidate", audience: "devops-api",
            claims: [new Claim("jti", Guid.NewGuid().ToString("N")), new Claim("sub", "candidate-evaluator"),
                new Claim("iat", new DateTimeOffset(now).ToUnixTimeSeconds().ToString(CultureInfo.InvariantCulture), ClaimValueTypes.Integer64)],
            notBefore: now, expires: now.AddMinutes(5), signingCredentials: signing);
        return Results.Json(new { token = new JwtSecurityTokenHandler().WriteToken(jwt), expires_in = 300, header = "X-JWT-KWY" });
    }
}
