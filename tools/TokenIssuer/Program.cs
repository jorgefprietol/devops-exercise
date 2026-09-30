// See https://aka.ms/new-console-template for more information
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.IdentityModel.Tokens;

var secret = Environment.GetEnvironmentVariable("JWT_SECRET") ?? "";
if (Encoding.UTF8.GetByteCount(secret) < 32)
{
    Console.Error.WriteLine("Set JWT_SECRET with at least 32 UTF-8 bytes. Never commit it.");
    return 1;
}
var now = DateTime.UtcNow;
var token = new JwtSecurityToken(
    issuer: "devops-candidate", audience: "devops-api",
    claims: [new Claim("jti", Guid.NewGuid().ToString("N")),
        new Claim("iat", new DateTimeOffset(now).ToUnixTimeSeconds().ToString(System.Globalization.CultureInfo.InvariantCulture), ClaimValueTypes.Integer64),
        new Claim("sub", "candidate-evaluator")],
    notBefore: now, expires: now.AddMinutes(5),
    signingCredentials: new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret)), SecurityAlgorithms.HmacSha256));
Console.WriteLine(new JwtSecurityTokenHandler().WriteToken(token));
return 0;
