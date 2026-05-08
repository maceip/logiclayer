param(
  [string]$FunctionName = $env:LOGICLENS_LAMBDA_FUNCTION_NAME,
  [string]$RoleName = $env:LOGICLENS_LAMBDA_ROLE_NAME,
  [string]$RoleArn = $env:LOGICLENS_LAMBDA_ROLE_ARN,
  [AllowEmptyString()][string]$RateLimitTable = $env:LOGICLENS_RATE_LIMIT_TABLE,
  [string]$AllowedOrigins = $env:LOGICLENS_ALLOWED_ORIGINS,
  [string]$Region = $(if ($env:AWS_REGION) { $env:AWS_REGION } elseif ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "eu-central-1" }),
  [string]$PythonBin = $env:PYTHON_BIN,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $FunctionName) { $FunctionName = "logiclens-beta-analyzer" }
if (-not $RoleName) { $RoleName = "logiclens-beta-analyzer-role" }
if ($null -eq $RateLimitTable) { $RateLimitTable = "logiclens-beta-rate-limit" }
if (-not $AllowedOrigins) { $AllowedOrigins = "https://maceip.github.io" }
if ($env:LOGICLENS_DEPLOY_DRY_RUN -eq "1") { $DryRun = $true }

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
    (Join-Path $Root "venv\Scripts\python.exe"),
    (Join-Path $UserLocalBin "python3.12.exe"),
    "python3.12",
    "python",
    "py"
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
  Write-Warning "Packaging with Python $PythonVersion while Lambda runtime is python3.12. Prefer Python 3.12."
}

if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Force $PackageDir | Out-Null

# Important on Windows: Lambda runs Linux, so dependencies with native wheels
# must be resolved for manylinux, not for win_amd64.
& $Uv pip install `
  --target $PackageDir `
  --python-version 3.12 `
  --python-platform x86_64-manylinux2014 `
  "pydantic>=2.11,<3" `
  "tree-sitter>=0.25,<0.26" `
  "tree-sitter-language-pack>=0.7,<1" `
  "boto3>=1.34,<2"

$PackageHt = Join-Path $PackageDir "heart_transplant"
New-Item -ItemType Directory -Force $PackageHt | Out-Null
Copy-Item -Recurse -Force (Join-Path $Root "backend\src\heart_transplant\*") $PackageHt

if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Push-Location $PackageDir
try {
  Compress-Archive -Path * -DestinationPath $ZipPath -Force
}
finally {
  Pop-Location
}

if ($DryRun) {
  Write-Output "dry_run=1"
  Write-Output "region=$Region"
  Write-Output "function_name=$FunctionName"
  Write-Output "role_name=$RoleName"
  Write-Output ("role_arn_override=" + $(if ($RoleArnOverrideSupplied) { "set" } else { "unset" }))
  Write-Output ("rate_limit_table=" + $(if ($RateLimitTable) { $RateLimitTable } else { "memory-fallback" }))
  Write-Output "python_bin=$PythonBin"
  Write-Output "uv=$Uv"
  Write-Output "zip_path=$ZipPath"
  exit 0
}

$AccountId = & $Aws sts get-caller-identity --query Account --output text --region $Region
if (-not $RoleArn) { $RoleArn = "arn:aws:iam::$AccountId`:role/$RoleName" }
$TableArn = "arn:aws:dynamodb:$Region`:$AccountId`:table/$RateLimitTable"

if (-not $RoleArnOverrideSupplied) {
  & $Aws iam get-role --role-name $RoleName *> $null
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
    & $Aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$AssumeRolePolicy" | Out-Null
    Start-Sleep -Seconds 10
  }
  # Idempotent when already attached; keeps pre-created script roles usable.
  & $Aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" | Out-Null
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
  & $Aws iam put-role-policy --role-name $RoleName --policy-name "logiclens-rate-limit-dynamodb" --policy-document "file://$RolePolicy" | Out-Null
}
elseif ($RateLimitTable) {
  Write-Warning "Using an existing Lambda role. Ensure it can write logs and dynamodb:GetItem/PutItem on $TableArn."
}
else {
  Write-Warning "LOGICLENS_RATE_LIMIT_TABLE is empty; deploying with warm-runtime memory rate limiting fallback."
}

if ($RateLimitTable) {
  & $Aws dynamodb describe-table --table-name $RateLimitTable --region $Region *> $null
  if ($LASTEXITCODE -ne 0) {
    & $Aws dynamodb create-table `
      --table-name $RateLimitTable `
      --attribute-definitions AttributeName=pk,AttributeType=S `
      --key-schema AttributeName=pk,KeyType=HASH `
      --billing-mode PAY_PER_REQUEST `
      --region $Region | Out-Null
    & $Aws dynamodb wait table-exists --table-name $RateLimitTable --region $Region
    & $Aws dynamodb update-time-to-live `
      --table-name $RateLimitTable `
      --time-to-live-specification "Enabled=true,AttributeName=expires_at" `
      --region $Region | Out-Null
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
Write-Utf8NoBom -Path $EnvironmentPath -Value $Environment

& $Aws lambda get-function --function-name $FunctionName --region $Region *> $null
if ($LASTEXITCODE -eq 0) {
  & $Aws lambda update-function-code `
    --function-name $FunctionName `
    --zip-file "fileb://$ZipPath" `
    --region $Region | Out-Null
  & $Aws lambda wait function-updated --function-name $FunctionName --region $Region
  & $Aws lambda update-function-configuration `
    --function-name $FunctionName `
    --runtime "python3.12" `
    --handler "heart_transplant.beta_lambda.lambda_handler" `
    --timeout 240 `
    --memory-size 2048 `
    --ephemeral-storage '{"Size":2048}' `
    --environment "file://$EnvironmentPath" `
    --region $Region | Out-Null
}
else {
  & $Aws lambda create-function `
    --function-name $FunctionName `
    --runtime "python3.12" `
    --role $RoleArn `
    --handler "heart_transplant.beta_lambda.lambda_handler" `
    --timeout 240 `
    --memory-size 2048 `
    --ephemeral-storage '{"Size":2048}' `
    --zip-file "fileb://$ZipPath" `
    --environment "file://$EnvironmentPath" `
    --region $Region | Out-Null
  & $Aws lambda wait function-active --function-name $FunctionName --region $Region
}

& $Aws lambda get-function-url-config --function-name $FunctionName --region $Region *> $null
if ($LASTEXITCODE -ne 0) {
  & $Aws lambda create-function-url-config --function-name $FunctionName --auth-type NONE --region $Region | Out-Null
}

& $Aws lambda add-permission `
  --function-name $FunctionName `
  --statement-id "FunctionURLAllowPublicAccess" `
  --action "lambda:InvokeFunctionUrl" `
  --principal "*" `
  --function-url-auth-type NONE `
  --region $Region *> $null

$FunctionUrl = & $Aws lambda get-function-url-config --function-name $FunctionName --query FunctionUrl --output text --region $Region
Write-Output $FunctionUrl
