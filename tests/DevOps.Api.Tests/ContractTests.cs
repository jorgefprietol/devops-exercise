using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;

namespace DevOps.Api.Tests;

public class ContractTests
{
    [Theory]
    [InlineData("GET")]
    [InlineData("PUT")]
    [InlineData("PATCH")]
    [InlineData("DELETE")]
    [InlineData("OPTIONS")]
    public async Task Otros_metodos_devuelven_error_literal(string method)
    {
        await using var app = new ApiFactory();
        using var client = app.CreateClient();
        using var response = await client.SendAsync(new HttpRequestMessage(new HttpMethod(method), "/DevOps"));
        Assert.Equal(HttpStatusCode.MethodNotAllowed, response.StatusCode);
        Assert.Equal("ERROR", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Post_sin_credenciales_no_esta_autorizado()
    {
        await using var app = new ApiFactory();
        using var client = app.CreateClient();
        using var response = await client.PostAsJsonAsync("/DevOps", new { message = "This is a test", to = "Juan Perez", from = "Rita Asturia", timeToLifeSec = 45 });
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
