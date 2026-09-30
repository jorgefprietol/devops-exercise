FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY Directory.Build.props ./
COPY src/DevOps.Api/DevOps.Api.csproj src/DevOps.Api/packages.lock.json src/DevOps.Api/
RUN dotnet restore src/DevOps.Api/DevOps.Api.csproj --locked-mode
COPY src/DevOps.Api/ src/DevOps.Api/
RUN dotnet publish src/DevOps.Api/DevOps.Api.csproj -c Release --no-restore -o /out /p:UseAppHost=false
FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /out .
ENV ASPNETCORE_HTTP_PORTS=8080
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "DevOps.Api.dll"]
