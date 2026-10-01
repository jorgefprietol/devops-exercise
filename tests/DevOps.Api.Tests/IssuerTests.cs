using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;

namespace DevOps.Api.Tests;

public sealed class IssuerFactory : WebApplicationFactory<Program>
{
    public const string Credential = "credential-for-evaluation-test-only-32-bytes";
    protected override void ConfigureWebHost(IWebHostBuilder builder) =>
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["SERVICE_ROLE"] = "token-issuer",
            ["ISSUER_KEY"] = Credential,
            ["JWT_SECRET"] = ApiFactory.Secret
        }));
    public static HttpRequestMessage Request(string? credential = Credential)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/auth/token");
        if (credential != null) request.Headers.Add("X-Evaluation-Key", credential);
        return request;
    }
}

public class IssuerTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("wrong")]
    [InlineData(ApiFactory.Key)]
    public async Task La_emision_exige_una_credencial_independiente(string? key)
    {
        await using var app = new IssuerFactory(); using var client = app.CreateClient();
        using var response = await client.SendAsync(IssuerFactory.Request(key));
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.DoesNotContain("token", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Cada_emision_firma_un_token_unico_de_cinco_minutos_y_un_solo_uso()
    {
        await using var issuer = new IssuerFactory(); using var client = issuer.CreateClient();
        await using var api = new ApiFactory(); using var apiClient = api.CreateClient();
        var ids = new HashSet<string>();
        for (var i = 0; i < 2; i++)
        {
            using var response = await client.SendAsync(IssuerFactory.Request());
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.True(response.Headers.CacheControl?.NoStore);
            var body = (await response.Content.ReadFromJsonAsync<JsonElement>());
            Assert.Equal(300, body.GetProperty("expires_in").GetInt32());
            Assert.Equal("X-JWT-KWY", body.GetProperty("header").GetString());
            var token = body.GetProperty("token").GetString()!;
            var jwt = new JwtSecurityTokenHandler().ReadJwtToken(token);
            Assert.True(ids.Add(jwt.Id));
            Assert.Equal(300, jwt.Payload.Expiration - new DateTimeOffset(jwt.IssuedAt).ToUnixTimeSeconds());
            Assert.Equal(HttpStatusCode.OK, (await apiClient.SendAsync(ApiFactory.Request(token))).StatusCode);
            Assert.Equal(HttpStatusCode.Conflict, (await apiClient.SendAsync(ApiFactory.Request(token))).StatusCode);
            Assert.DoesNotContain(ApiFactory.Secret, await response.Content.ReadAsStringAsync());
        }
    }

    [Fact]
    public async Task El_emisor_esta_aislado_y_limita_las_solicitudes()
    {
        await using var app = new IssuerFactory(); using var client = app.CreateClient();
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/health/ready")).StatusCode);
        Assert.Equal(HttpStatusCode.MethodNotAllowed, (await client.GetAsync("/auth/token")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.SendAsync(ApiFactory.Request())).StatusCode);
        using var duplicate = IssuerFactory.Request(); duplicate.Headers.Add("X-Evaluation-Key", IssuerFactory.Credential);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(duplicate)).StatusCode);
        for (var i = 0; i < 29; i++)
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(IssuerFactory.Request("wrong"))).StatusCode);
        Assert.Equal(HttpStatusCode.TooManyRequests, (await client.SendAsync(IssuerFactory.Request())).StatusCode);
        await using var api = new ApiFactory(); using var apiClient = api.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound, (await apiClient.SendAsync(IssuerFactory.Request())).StatusCode);
    }

    [Theory]
    [InlineData("", "")]
    [InlineData("short", ApiFactory.Secret)]
    [InlineData(ApiFactory.Secret, ApiFactory.Secret)]
    public void No_inicia_con_credenciales_debiles_o_compartidas(string credential, string secret)
    {
        var config = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        { ["ISSUER_KEY"] = credential, ["JWT_SECRET"] = secret }).Build();
        Assert.Throws<InvalidOperationException>(() => new EvaluationIssuer(config));
    }
}
