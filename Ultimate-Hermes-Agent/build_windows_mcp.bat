@echo off
setlocal
cd /d "%~dp0"
where dotnet >nul 2>nul
if errorlevel 1 (
  echo .NET 10 SDK not found. Install it before building the Windows MCP server.
  echo https://dotnet.microsoft.com/download/dotnet/10.0
  pause
  exit /b 1
)
dotnet publish "upstream\mcp-windows\src\Sbroenne.WindowsMcp\Sbroenne.WindowsMcp.csproj" -c Release -o "upstream\mcp-windows\publish"
if errorlevel 1 (
  echo Build failed. Review the output above.
  pause
  exit /b 1
)
echo Publish completed. Add the executable from upstream\mcp-windows\publish to MCP Settings.
pause
