using System.Collections.Concurrent;
using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.IdentityModel.Tokens;

namespace DevOps.Api.Tests;

public sealed class MemoryReplayStore : IReplayStore
{
    private readonly ConcurrentDictionary<string, byte> used = new();
    public bool Available { get; set; } = true;
    public Task<bool> TryConsumeAsync(string id, DateTime expiresAt) => Available
        ? Task.FromResult(used.TryAdd(id, 0))
        : throw new ReplayStoreUnavailableException(new TimeoutException());
    public Task<bool> IsReadyAsync() => Task.FromResult(Available);
}

public sealed class ApiFactory : WebApplicationFactory<Program>
{
    public const string Key = "test-key-not-a-production-credential";
    public const string Secret = "test-only-signing-secret-at-least-32-bytes";
    public MemoryReplayStore Store { get; } = new();
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        { ["API_KEY"] = Key, ["JWT_SECRET"] = Secret }));
        builder.ConfigureTestServices(services =>
        {
            services.RemoveAll<IReplayStore>();
            services.AddSingleton<IReplayStore>(Store);
        });
    }
    public static string Token(string kind = "valid", string? id = null)
    {
        var now = DateTime.UtcNow;
        var issued = kind == "old" ? now.AddMinutes(-10) : kind == "future-iat" ? now.AddMinutes(1) : now;
        var claims = new List<Claim>();
        if (kind != "no-jti") claims.Add(new("jti", kind == "bad-jti" ? "bad" : id ?? Guid.NewGuid().ToString("N")));
        if (kind != "no-iat") claims.Add(new("iat", new DateTimeOffset(issued).ToUnixTimeSeconds().ToString(System.Globalization.CultureInfo.InvariantCulture), ClaimValueTypes.Integer64));
        var token = new JwtSecurityToken(
            issuer: kind == "issuer" ? "intruder" : "devops-candidate",
            audience: kind == "audience" ? "another-api" : "devops-api", claims: claims,
            notBefore: kind == "future" ? now.AddMinutes(1) : now.AddMinutes(-2),
            expires: kind == "expired" ? now.AddMinutes(-1) : kind == "long-life" ? now.AddHours(1) : now.AddMinutes(2),
            signingCredentials: new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(kind == "signature" ? Secret + "wrong" : Secret)), SecurityAlgorithms.HmacSha256));
        if (kind == "no-nbf") token.Payload.Remove("nbf");
        return new JwtSecurityTokenHandler().WriteToken(token);
    }
    public static HttpRequestMessage Request(string? token = null, string? json = null)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/DevOps");
        request.Headers.Add("X-Parse-REST-API-Key", Key);
        request.Headers.Add("X-JWT-KWY", token ?? Token());
        request.Content = new StringContent(json ?? "{\"message\":\"This is a test\",\"to\":\"Juan Perez\",\"from\":\"Rita Asturia\",\"timeToLifeSec\":45}", Encoding.UTF8, "application/json");
        return request;
    }
}

public class SecurityTests
{
    [Fact]
    public async Task La_respuesta_correcta_respeta_el_contrato()
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        using var response = await client.SendAsync(ApiFactory.Request());
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("{\"message\":\"Hello Juan Perez your message will be sent\"}", await response.Content.ReadAsStringAsync());
    }
    [Theory]
    [InlineData("issuer")]
    [InlineData("audience")]
    [InlineData("signature")]
    [InlineData("expired")]
    [InlineData("future")]
    [InlineData("no-jti")]
    [InlineData("bad-jti")]
    [InlineData("no-iat")]
    [InlineData("no-nbf")]
    [InlineData("old")]
    [InlineData("future-iat")]
    [InlineData("long-life")]
    public async Task Se_rechazan_los_tokens_invalidos(string kind)
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        using var response = await client.SendAsync(ApiFactory.Request(ApiFactory.Token(kind)));
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
    [Theory]
    [InlineData("malformed")]
    [InlineData("")]
    public async Task Se_rechazan_los_tokens_mal_formados(string token)
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(ApiFactory.Request(token))).StatusCode);
    }
    [Theory]
    [InlineData("key")]
    [InlineData("jwt")]
    [InlineData("duplicate-key")]
    [InlineData("duplicate-jwt")]
    public async Task Se_rechazan_los_encabezados_invalidos(string kind)
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        using var request = ApiFactory.Request();
        if (kind == "key") { request.Headers.Remove("X-Parse-REST-API-Key"); request.Headers.Add("X-Parse-REST-API-Key", "wrong"); }
        if (kind == "jwt") request.Headers.Remove("X-JWT-KWY");
        if (kind == "duplicate-key") request.Headers.Add("X-Parse-REST-API-Key", ApiFactory.Key);
        if (kind == "duplicate-jwt") request.Headers.Add("X-JWT-KWY", ApiFactory.Token());
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }
    [Theory]
    [InlineData("null")]
    [InlineData("{")]
    [InlineData("{}")]
    [InlineData("{\"message\":\"x\",\"to\":\"x\",\"from\":\"x\",\"timeToLifeSec\":0}")]
    [InlineData("{\"message\":\"x\",\"to\":\"x\",\"from\":\"x\",\"timeToLifeSec\":86401}")]
    [InlineData("{\"message\":\"x\",\"to\":\" \",\"from\":\"x\",\"timeToLifeSec\":45}")]
    [InlineData("{\"message\":\"x\",\"to\":\"x\",\"from\":\" \",\"timeToLifeSec\":45}")]
    public async Task El_cuerpo_invalido_no_consume_el_token(string body)
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient(); var token = ApiFactory.Token();
        Assert.Equal(HttpStatusCode.BadRequest, (await client.SendAsync(ApiFactory.Request(token, body))).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.SendAsync(ApiFactory.Request(token))).StatusCode);
    }
    [Fact]
    public async Task La_repeticion_concurrente_tiene_un_solo_exito()
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient(); var token = ApiFactory.Token();
        var responses = await Task.WhenAll(Enumerable.Range(0, 20).Select(_ => client.SendAsync(ApiFactory.Request(token))));
        Assert.Single(responses, r => r.StatusCode == HttpStatusCode.OK);
        Assert.Equal(19, responses.Count(r => r.StatusCode == HttpStatusCode.Conflict));
    }
    [Fact]
    public async Task La_falla_del_almacen_impide_aceptar_transacciones()
    {
        await using var app = new ApiFactory(); app.Store.Available = false; using var client = app.CreateClient();
        Assert.Equal(HttpStatusCode.ServiceUnavailable, (await client.SendAsync(ApiFactory.Request())).StatusCode);
        Assert.Equal(HttpStatusCode.ServiceUnavailable, (await client.GetAsync("/health/ready")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/health/live")).StatusCode);
    }
    [Fact]
    public async Task La_salud_interna_y_las_rutas_desconocidas()
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/health/ready")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/unknown")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/devops")).StatusCode);
    }
    [Fact]
    public async Task Se_rechazan_el_tipo_y_el_tamano_no_admitidos()
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        using var wrong = ApiFactory.Request(); wrong.Content = new StringContent("not json");
        Assert.Equal(HttpStatusCode.UnsupportedMediaType, (await client.SendAsync(wrong)).StatusCode);
        Assert.Equal(HttpStatusCode.RequestEntityTooLarge, (await client.SendAsync(ApiFactory.Request(json: new string('x', 17000)))).StatusCode);
    }
    [Fact]
    public async Task Head_devuelve_estado_sin_cuerpo()
    {
        await using var app = new ApiFactory(); using var client = app.CreateClient();
        using var response = await client.SendAsync(new HttpRequestMessage(HttpMethod.Head, "/DevOps"));
        Assert.Equal(HttpStatusCode.MethodNotAllowed, response.StatusCode);
        Assert.Equal("", await response.Content.ReadAsStringAsync());
    }
    [Fact]
    public void La_falta_de_secretos_impide_el_inicio()
    {
        Assert.Throws<InvalidOperationException>(() => SecuritySettings.Load(new ConfigurationBuilder().Build()));
        Assert.Null(new TokenValidator(new(ApiFactory.Key, ApiFactory.Secret, "devops-candidate", "devops-api")).Validate(new string('x', 9000)));
    }
    [Theory]
    [InlineData(2001, 1, 1)]
    [InlineData(1, 201, 1)]
    [InlineData(1, 1, 201)]
    public void Se_respetan_los_limites_de_longitud(int message, int to, int from)
    {
        Assert.False(new MessageRequest(new string('a', message), new string('b', to), new string('c', from), 45).IsValid());
    }
}
