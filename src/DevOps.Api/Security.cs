using System.Globalization;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Cryptography;
using System.Text;
using Microsoft.IdentityModel.Tokens;

namespace DevOps.Api;

public sealed record SecuritySettings(string ApiKey, string JwtSecret, string Issuer, string Audience)
{
    public static SecuritySettings Load(IConfiguration config)
    {
        var key = config["API_KEY"] ?? "";
        var secret = config["JWT_SECRET"] ?? "";
        if (string.IsNullOrWhiteSpace(key) || Encoding.UTF8.GetByteCount(secret) < 32)
            throw new InvalidOperationException("Set API_KEY and JWT_SECRET (at least 32 UTF-8 bytes).");
        return new(key, secret, "devops-candidate", "devops-api");
    }

    public bool MatchesApiKey(string value) => CryptographicOperations.FixedTimeEquals(
        SHA256.HashData(Encoding.UTF8.GetBytes(value)),
        SHA256.HashData(Encoding.UTF8.GetBytes(ApiKey)));
}

public sealed record TransactionToken(string Id, DateTime ExpiresAt);

public sealed class TokenValidator(SecuritySettings settings)
{
    public TransactionToken? Validate(string token)
    {
        if (token.Length > 8192) return null;
        try
        {
            var handler = new JwtSecurityTokenHandler { MapInboundClaims = false };
            handler.ValidateToken(token, new TokenValidationParameters
            {
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(settings.JwtSecret)),
                ValidAlgorithms = [SecurityAlgorithms.HmacSha256],
                ValidateIssuer = true,
                ValidIssuer = settings.Issuer,
                ValidateAudience = true,
                ValidAudience = settings.Audience,
                ValidateLifetime = true,
                RequireExpirationTime = true,
                RequireSignedTokens = true,
                ClockSkew = TimeSpan.Zero
            }, out var validated);
            var jwt = (JwtSecurityToken)validated;
            var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            var jti = jwt.Id;
            if (!Guid.TryParseExact(jti, "N", out _) ||
                !long.TryParse(jwt.Claims.FirstOrDefault(c => c.Type == "iat")?.Value,
                    NumberStyles.Integer, CultureInfo.InvariantCulture, out var issued) ||
                issued > now || now - issued > 300 ||
                !jwt.Payload.ContainsKey("nbf") ||
                new DateTimeOffset(jwt.ValidTo).ToUnixTimeSeconds() - issued > 300)
                return null;
            return new(jti, jwt.ValidTo);
        }
        catch (Exception ex) when (ex is SecurityTokenException or ArgumentException) { return null; }
    }
}
