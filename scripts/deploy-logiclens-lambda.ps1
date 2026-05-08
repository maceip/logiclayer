param(
  [string]$FunctionName = $env:LOGICLENS_LAMBDA_FUNCTION_NAME,
  [string]$RoleName = $env:LOGICLENS_LAMBDA_ROLE_NAME,
  [string]$RoleArn = $env:LOGICLENS_LAMBDA_ROLE_ARN,
  [AllowEmptyString()][string]$RateLimitTable = $env:LOGICLENS_RATE_LIMIT_TABLE,
  [string]$AllowedOrigins = $env:LOGICLENS_ALLOWED_ORIGINS,
  [string]$Region = $(if ($env:AWS_REGION) { $env:AWS_REGION } elseif ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "eu-central-1" }),
  [string]$PythonBin = $env:PYTHON_BIN,
  [switch]$DryRun,
  [switch]$NonInteractive,
  [switch]$UseMemoryRateLimit
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
  $PSNativeCommandUseErrorActionPreference = $false
}

function Assert-LastExitCode {
  param([Parameter(Mandatory = $true)][string]$Action)
  if ($LASTEXITCODE -ne 0) {
    throw "$Action failed with exit code $LASTEXITCODE."
  }
}

function Test-TransientAwsError {
  param([string]$Text)
  return $Text -match "Connection was closed|valid response|timeout|timed out|connection reset|temporarily unavailable|TLS"
}

function Invoke-AwsChecked {
  param(
    [Parameter(Mandatory = $true)][string]$Action,
    [Parameter(Mandatory = $true)][string[]]$AwsArgs,
    [int]$MaxAttempts = 3,
    [switch]$AllowFailure
  )

  $LastOutput = ""
  for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
    $AttemptText = $(if ($MaxAttempts -gt 1) { " attempt $Attempt/$MaxAttempts" } else { "" })
    Write-Host "AWS: $Action$AttemptText..." -ForegroundColor Cyan
    $Output = & $Aws @AwsArgs 2>&1
    $ExitCode = $LASTEXITCODE
    $LastOutput = ($Output | Out-String)
    if ($ExitCode -eq 0) {
      Write-Host "AWS: $Action complete." -ForegroundColor Green
      return $Output
    }
    if ($AllowFailure) {
      Write-Host "AWS: $Action did not succeed; continuing because this check is allowed to fail." -ForegroundColor DarkYellow
      return $Output
    }
    if ($Attempt -lt $MaxAttempts -and (Test-TransientAwsError $LastOutput)) {
      $SleepSeconds = [math]::Min(20, [math]::Pow(2, $Attempt))
      Write-Warning "$Action failed transiently; retrying in $SleepSeconds seconds. $LastOutput"
      Start-Sleep -Seconds $SleepSeconds
      continue
    }
    throw "$Action failed after $Attempt attempt(s): $LastOutput"
  }
  throw "$Action failed: $LastOutput"
}

if (-not $FunctionName) { $FunctionName = "logiclens-beta-analyzer" }
if (-not $RoleName) { $RoleName = "logiclens-beta-analyzer-role" }
if ($env:LOGICLENS_USE_MEMORY_RATE_LIMIT -eq "1") { $UseMemoryRateLimit = $true }
if ($UseMemoryRateLimit) {
  $RateLimitTable = ""
}
elseif ([string]::IsNullOrWhiteSpace($RateLimitTable)) {
  $RateLimitTable = "logiclens-beta-rate-limit"
}
if (-not $AllowedOrigins) { $AllowedOrigins = "https://maceip.github.io" }
if ($env:LOGICLENS_DEPLOY_DRY_RUN -eq "1") { $DryRun = $true }

function Read-Defaulted {
  param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [string]$Default = ""
  )
  if ($NonInteractive) { return $Default }
  $Suffix = $(if ($Default) { " [$Default]" } else { "" })
  $Value = Read-Host "$Prompt$Suffix"
  if ([string]::IsNullOrWhiteSpace($Value)) { return $Default }
  return $Value.Trim()
}

function Read-SecretString {
  param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [string]$Existing = ""
  )
  if ($Existing -or $NonInteractive) { return $Existing }
  $Secure = Read-Host $Prompt -AsSecureString
  if ($Secure.Length -eq 0) { return "" }
  $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
  }
  finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
  }
}

if (-not $NonInteractive) {
  Write-Host "LogicLens Lambda deploy (Frankfurt / eu-central-1 by default)." -ForegroundColor Cyan
  Write-Host "Press Enter to accept defaults. Secret values are not echoed." -ForegroundColor DarkGray
}

if (-not $env:AWS_ACCESS_KEY_ID) {
  $env:AWS_ACCESS_KEY_ID = Read-Defaulted -Prompt "AWS_ACCESS_KEY_ID"
}
if (-not $env:AWS_SECRET_ACCESS_KEY) {
  $env:AWS_SECRET_ACCESS_KEY = Read-SecretString -Prompt "AWS_SECRET_ACCESS_KEY"
}
if (-not $env:AWS_SESSION_TOKEN) {
  $Token = Read-SecretString -Prompt "AWS_SESSION_TOKEN (optional)"
  if ($Token) { $env:AWS_SESSION_TOKEN = $Token }
}
if ($env:AWS_ACCESS_KEY_ID -and $env:AWS_SECRET_ACCESS_KEY) {
  # Raw env credentials should win. A stale AWS_PROFILE or credentials file path
  # can make AWS CLI ignore otherwise-valid access key env vars on some setups.
  Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
  Remove-Item Env:AWS_SHARED_CREDENTIALS_FILE -ErrorAction SilentlyContinue
}

$Region = Read-Defaulted -Prompt "AWS region" -Default $Region
$env:AWS_REGION = $Region
$env:AWS_DEFAULT_REGION = $Region

$AllowedOrigins = Read-Defaulted -Prompt "Allowed GitHub Pages origin" -Default $AllowedOrigins
$FunctionName = Read-Defaulted -Prompt "Lambda function name" -Default $FunctionName
$RoleName = Read-Defaulted -Prompt "IAM role name to create/use" -Default $RoleName

if (-not $RoleArn) {
  $RoleArnInput = Read-Defaulted -Prompt "Existing Lambda role ARN (optional; leave blank to create/use role name)" -Default ""
  if ($RoleArnInput) { $RoleArn = $RoleArnInput }
}

if (-not $UseMemoryRateLimit) {
  $RateLimitTable = Read-Defaulted -Prompt "DynamoDB rate-limit table" -Default $RateLimitTable
  if ([string]::IsNullOrWhiteSpace($RateLimitTable)) {
    $RateLimitTable = "logiclens-beta-rate-limit"
  }
}
else {
  Write-Warning "Using warm-runtime memory rate limiting because -UseMemoryRateLimit or LOGICLENS_USE_MEMORY_RATE_LIMIT=1 was set."
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BuildDir = Join-Path $Root ".lambda-build"
$PackageDir = Join-Path $BuildDir "package"
$ZipPath = Join-Path $BuildDir "logiclens-beta-analyzer.zip"
$RoleArnOverrideSupplied = -not [string]::IsNullOrWhiteSpace($RoleArn)

function Write-Utf8NoBom {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Value
  )
  $Encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Value, $Encoding)
}

function Resolve-CommandPath {
  param([string[]]$Candidates)
  foreach ($Candidate in $Candidates) {
    if (-not $Candidate) { continue }
    $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
    if (Test-Path $Candidate) { return (Resolve-Path $Candidate).Path }
  }
  return $null
}

$UserLocalBin = Join-Path $HOME ".local\bin"
$Uv = Resolve-CommandPath @("uv", "uv.exe", (Join-Path $UserLocalBin "uv.exe"))
if (-not $Uv) {
  throw "uv is required. Install with: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}

if (-not $PythonBin) {
  $PythonBin = Resolve-CommandPath @(
    (Join-Path $UserLocalBin "python3.12.exe"),
    (Join-Path $Root "venv\Scripts\python.exe"),
    "python3.12",
    "python"
  )
}
if (-not $PythonBin) {
  throw "Python 3.12 is required. Set PYTHON_BIN to python3.12.exe if auto-detection fails."
}

$Aws = Resolve-CommandPath @("aws", "aws.exe")
if (-not $Aws) {
  throw "AWS CLI is required in PATH. Install AWS CLI v2 before running this deploy."
}

$PythonVersion = & $PythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($PythonVersion -ne "3.12") {
  throw "Python 3.12 is required for this deploy. Detected Python $PythonVersion at $PythonBin. Set PYTHON_BIN=C:\Users\mac\.local\bin\python3.12.exe and rerun."
}

if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Force $PackageDir | Out-Null

# Important on Windows: Lambda runs Linux, so dependencies with native wheels
# must be resolved for manylinux, not for win_amd64.
Write-Host "Stage: Installing Linux-compatible Lambda dependencies..." -ForegroundColor Cyan
& $Uv pip install `
  --target $PackageDir `
  --python-version 3.12 `
  --python-platform x86_64-manylinux2014 `
  --only-binary ":all:" `
  "pydantic>=2.11,<3" `
  "tree-sitter>=0.25,<0.26" `
  "tree-sitter-language-pack>=0.7,<1" `
  "boto3>=1.34,<2"
Assert-LastExitCode "Installing Lambda dependencies with uv"
Write-Host "Stage: Lambda dependencies installed." -ForegroundColor Green

$PackageHt = Join-Path $PackageDir "heart_transplant"
New-Item -ItemType Directory -Force $PackageHt | Out-Null
Write-Host "Stage: Copying application source into Lambda package..." -ForegroundColor Cyan
Copy-Item -Recurse -Force (Join-Path $Root "backend\src\heart_transplant\*") $PackageHt
Write-Host "Stage: Application source copied." -ForegroundColor Green

if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
$FilesToZip = Get-ChildItem -Path $PackageDir -Recurse -File
$TotalFiles = [Math]::Max(1, $FilesToZip.Count)
Write-Progress -Activity "Packaging Lambda ZIP" -Status "Compressing $TotalFiles files" -PercentComplete 0
Write-Host "Packaging Lambda ZIP ($TotalFiles files)..." -ForegroundColor Cyan
$ZipScript = Join-Path $BuildDir "make-lambda-zip.py"
Write-Utf8NoBom -Path $ZipScript -Value @'
from __future__ import annotations

from pathlib import Path
import os
import sys
import zipfile

package_dir = Path(sys.argv[1]).resolve()
zip_path = Path(sys.argv[2]).resolve()
files = [Path(root) / name for root, _dirs, names in os.walk(package_dir) for name in names]
total = max(1, len(files))
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for index, path in enumerate(files, 1):
        arcname = path.relative_to(package_dir).as_posix()
        zf.write(path, arcname)
        if index == 1 or index % 100 == 0 or index == total:
            print(f"ZIP progress: {index}/{total} files", flush=True)
print(f"ZIP complete: {zip_path}", flush=True)
'@
& $PythonBin $ZipScript $PackageDir $ZipPath
Assert-LastExitCode "Compressing Lambda ZIP with Python zipfile"
Write-Progress -Activity "Packaging Lambda ZIP" -Completed
$ZipSizeMb = [Math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host "Packaged Lambda ZIP: $ZipPath (${ZipSizeMb} MB)" -ForegroundColor Green

if ($DryRun) {
  Write-Output "dry_run=1"
  Write-Output "region=$Region"
  Write-Output "function_name=$FunctionName"
  Write-Output "role_name=$RoleName"
  Write-Output ("role_arn_override=" + $(if ($RoleArnOverrideSupplied) { "set" } else { "unset" }))
  Write-Output ("rate_limit_table=" + $(if ($RateLimitTable) { $RateLimitTable } else { "memory-fallback-explicit" }))
  Write-Output "python_bin=$PythonBin"
  Write-Output "uv=$Uv"
  Write-Output "zip_path=$ZipPath"
  exit 0
}

$AccountId = (Invoke-AwsChecked -Action "Reading AWS caller identity" -AwsArgs @("sts", "get-caller-identity", "--query", "Account", "--output", "text", "--region", $Region) | Out-String).Trim()
if (-not $RoleArn) { $RoleArn = "arn:aws:iam::$AccountId`:role/$RoleName" }
$TableArn = "arn:aws:dynamodb:$Region`:$AccountId`:table/$RateLimitTable"

if (-not $RoleArnOverrideSupplied) {
  $RoleCheck = Invoke-AwsChecked -Action "Checking IAM role $RoleName" -AwsArgs @("iam", "get-role", "--role-name", $RoleName) -AllowFailure
  if ($LASTEXITCODE -ne 0) {
    $AssumeRolePolicy = Join-Path $BuildDir "assume-role-policy.json"
    $AssumeRoleJson = @'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
'@
    Write-Utf8NoBom -Path $AssumeRolePolicy -Value $AssumeRoleJson
    Invoke-AwsChecked -Action "Creating IAM role $RoleName" -AwsArgs @("iam", "create-role", "--role-name", $RoleName, "--assume-role-policy-document", "file://$AssumeRolePolicy") | Out-Null
    Start-Sleep -Seconds 10
  }
  # Idempotent when already attached; keeps pre-created script roles usable.
  Invoke-AwsChecked -Action "Attaching AWSLambdaBasicExecutionRole to $RoleName" -AwsArgs @("iam", "attach-role-policy", "--role-name", $RoleName, "--policy-arn", "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole") | Out-Null
}

if ($RateLimitTable -and -not $RoleArnOverrideSupplied) {
  $RolePolicy = Join-Path $BuildDir "rate-limit-policy.json"
  $RolePolicyJson = @{
    Version = "2012-10-17"
    Statement = @(
      @{
        Effect = "Allow"
        Action = @("dynamodb:GetItem", "dynamodb:PutItem")
        Resource = $TableArn
      }
    )
  } | ConvertTo-Json -Depth 10
  Write-Utf8NoBom -Path $RolePolicy -Value $RolePolicyJson
  Invoke-AwsChecked -Action "Putting DynamoDB rate-limit policy on $RoleName" -AwsArgs @("iam", "put-role-policy", "--role-name", $RoleName, "--policy-name", "logiclens-rate-limit-dynamodb", "--policy-document", "file://$RolePolicy") | Out-Null
}
elseif ($RateLimitTable) {
  Write-Warning "Using an existing Lambda role. Ensure it can write logs and dynamodb:GetItem/PutItem on $TableArn."
}
else {
  Write-Warning "LOGICLENS_RATE_LIMIT_TABLE is empty; deploying with warm-runtime memory rate limiting fallback."
}

if ($RateLimitTable) {
  Invoke-AwsChecked -Action "Checking DynamoDB table $RateLimitTable" -AwsArgs @("dynamodb", "describe-table", "--table-name", $RateLimitTable, "--region", $Region) -AllowFailure | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Invoke-AwsChecked -Action "Creating DynamoDB table $RateLimitTable" -AwsArgs @("dynamodb", "create-table", "--table-name", $RateLimitTable, "--attribute-definitions", "AttributeName=pk,AttributeType=S", "--key-schema", "AttributeName=pk,KeyType=HASH", "--billing-mode", "PAY_PER_REQUEST", "--region", $Region) | Out-Null
    Invoke-AwsChecked -Action "Waiting for DynamoDB table $RateLimitTable" -AwsArgs @("dynamodb", "wait", "table-exists", "--table-name", $RateLimitTable, "--region", $Region) -MaxAttempts 1 | Out-Null
    Invoke-AwsChecked -Action "Enabling TTL on DynamoDB table $RateLimitTable" -AwsArgs @("dynamodb", "update-time-to-live", "--table-name", $RateLimitTable, "--time-to-live-specification", "Enabled=true,AttributeName=expires_at", "--region", $Region) | Out-Null
  }
}

$Environment = @{
  Variables = @{
    LOGICLENS_ALLOWED_ORIGINS = $AllowedOrigins
    LOGICLENS_RATE_LIMIT_TABLE = $RateLimitTable
    HEART_TRANSPLANT_BETA_FETCH_MODE = "zipball"
    HEART_TRANSPLANT_BETA_CACHE = "/tmp/logiclens/repos"
    HEART_TRANSPLANT_ARTIFACT_ROOT = "/tmp/logiclens/artifacts"
  }
} | ConvertTo-Json -Compress -Depth 10
$EnvironmentPath = Join-Path $BuildDir "lambda-environment.json"
Write-Host "Stage: Writing Lambda environment configuration..." -ForegroundColor Cyan
Write-Utf8NoBom -Path $EnvironmentPath -Value $Environment
Write-Host "Stage: Lambda environment configuration written." -ForegroundColor Green

$FunctionCheck = Invoke-AwsChecked -Action "Checking Lambda function $FunctionName" -AwsArgs @("lambda", "get-function", "--function-name", $FunctionName, "--region", $Region) -AllowFailure
if ($LASTEXITCODE -eq 0) {
  Invoke-AwsChecked -Action "Updating Lambda function code for $FunctionName" -AwsArgs @("lambda", "update-function-code", "--function-name", $FunctionName, "--zip-file", "fileb://$ZipPath", "--region", $Region) | Out-Null
  Invoke-AwsChecked -Action "Waiting for Lambda code update for $FunctionName" -AwsArgs @("lambda", "wait", "function-updated", "--function-name", $FunctionName, "--region", $Region) -MaxAttempts 1 | Out-Null
  Invoke-AwsChecked -Action "Updating Lambda function configuration for $FunctionName" -AwsArgs @("lambda", "update-function-configuration", "--function-name", $FunctionName, "--runtime", "python3.12", "--handler", "heart_transplant.beta_lambda.lambda_handler", "--timeout", "240", "--memory-size", "2048", "--ephemeral-storage", '{"Size":2048}', "--environment", "file://$EnvironmentPath", "--region", $Region) | Out-Null
}
else {
  Invoke-AwsChecked -Action "Creating Lambda function $FunctionName" -AwsArgs @("lambda", "create-function", "--function-name", $FunctionName, "--runtime", "python3.12", "--role", $RoleArn, "--handler", "heart_transplant.beta_lambda.lambda_handler", "--timeout", "240", "--memory-size", "2048", "--ephemeral-storage", '{"Size":2048}', "--zip-file", "fileb://$ZipPath", "--environment", "file://$EnvironmentPath", "--region", $Region) | Out-Null
  Invoke-AwsChecked -Action "Waiting for Lambda function $FunctionName to become active" -AwsArgs @("lambda", "wait", "function-active", "--function-name", $FunctionName, "--region", $Region) -MaxAttempts 1 | Out-Null
}

$UrlCheck = Invoke-AwsChecked -Action "Checking Lambda Function URL for $FunctionName" -AwsArgs @("lambda", "get-function-url-config", "--function-name", $FunctionName, "--region", $Region) -AllowFailure
if ($LASTEXITCODE -ne 0) {
  Invoke-AwsChecked -Action "Creating Lambda Function URL for $FunctionName" -AwsArgs @("lambda", "create-function-url-config", "--function-name", $FunctionName, "--auth-type", "NONE", "--region", $Region) | Out-Null
}

$AddPermissionOutput = Invoke-AwsChecked -Action "Adding Function URL invoke permission for $FunctionName" -AwsArgs @("lambda", "add-permission", "--function-name", $FunctionName, "--statement-id", "FunctionURLAllowPublicAccess", "--action", "lambda:InvokeFunctionUrl", "--principal", "*", "--function-url-auth-type", "NONE", "--region", $Region) -AllowFailure
if ($LASTEXITCODE -ne 0 -and (($AddPermissionOutput | Out-String) -notmatch "ResourceConflictException")) {
  throw "Failed to add Function URL invoke permission: $($AddPermissionOutput | Out-String)"
}

$FunctionUrl = (Invoke-AwsChecked -Action "Reading Lambda Function URL for $FunctionName" -AwsArgs @("lambda", "get-function-url-config", "--function-name", $FunctionName, "--query", "FunctionUrl", "--output", "text", "--region", $Region) | Out-String).Trim()
Write-Output $FunctionUrl
