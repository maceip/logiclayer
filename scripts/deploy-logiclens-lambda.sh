#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNCTION_NAME="${LOGICLENS_LAMBDA_FUNCTION_NAME:-logiclens-beta-analyzer}"
ROLE_NAME="${LOGICLENS_LAMBDA_ROLE_NAME:-logiclens-beta-analyzer-role}"
ROLE_ARN_OVERRIDE="${LOGICLENS_LAMBDA_ROLE_ARN:-}"
TABLE_NAME="${LOGICLENS_RATE_LIMIT_TABLE-logiclens-beta-rate-limit}"
ALLOWED_ORIGINS="${LOGICLENS_ALLOWED_ORIGINS:-https://maceip.github.io}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-central-1}}"
BUILD_DIR="$ROOT/.lambda-build"
PACKAGE_DIR="$BUILD_DIR/package"
ZIP_PATH="$BUILD_DIR/logiclens-beta-analyzer.zip"
PATH="$HOME/.local/bin:$PATH"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$ROOT/venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT/venv/bin/python"
  elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "Python 3.12 or python3 is required. Set PYTHON_BIN=/path/to/python if needed." >&2
    exit 1
  fi
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required in PATH" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required in PATH. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
  echo "Warning: packaging with Python $PYTHON_VERSION while Lambda runtime is python3.12. Prefer PYTHON_BIN pointing to Python 3.12." >&2
fi

rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR"

uv pip install \
  --python "$PYTHON_BIN" \
  --target "$PACKAGE_DIR" \
  "pydantic>=2.11,<3" \
  "tree-sitter>=0.25,<0.26" \
  "tree-sitter-language-pack>=0.7,<1" \
  "boto3>=1.34,<2"

mkdir -p "$PACKAGE_DIR/heart_transplant"
cp -a "$ROOT/backend/src/heart_transplant/." "$PACKAGE_DIR/heart_transplant/"

(
  cd "$PACKAGE_DIR"
  zip -qr "$ZIP_PATH" .
)

if [[ "${LOGICLENS_DEPLOY_DRY_RUN:-0}" == "1" ]]; then
  echo "dry_run=1"
  echo "region=$REGION"
  echo "function_name=$FUNCTION_NAME"
  echo "role_name=$ROLE_NAME"
  echo "role_arn_override=$([[ -n "$ROLE_ARN_OVERRIDE" ]] && echo set || echo unset)"
  echo "rate_limit_table=$([[ -n "$TABLE_NAME" ]] && echo "$TABLE_NAME" || echo memory-fallback)"
  echo "python_bin=$PYTHON_BIN"
  echo "zip_path=$ZIP_PATH"
  exit 0
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "$REGION")"
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"
if [[ -n "$ROLE_ARN_OVERRIDE" ]]; then
  ROLE_ARN="$ROLE_ARN_OVERRIDE"
fi
TABLE_ARN="arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$TABLE_NAME"

if [[ -z "$ROLE_ARN_OVERRIDE" ]] && ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
      }]
    }' >/dev/null
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole >/dev/null
  # IAM propagation is eventually consistent.
  sleep 10
fi

if [[ -n "$TABLE_NAME" && -z "$ROLE_ARN_OVERRIDE" ]]; then
  aws iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name logiclens-rate-limit-dynamodb \
    --policy-document "{
      \"Version\": \"2012-10-17\",
      \"Statement\": [{
        \"Effect\": \"Allow\",
        \"Action\": [\"dynamodb:GetItem\", \"dynamodb:PutItem\"],
        \"Resource\": \"$TABLE_ARN\"
      }]
    }" >/dev/null
elif [[ -n "$TABLE_NAME" ]]; then
  echo "Using existing Lambda role; ensure it can write logs and dynamodb:GetItem/PutItem on $TABLE_ARN" >&2
else
  echo "LOGICLENS_RATE_LIMIT_TABLE is empty; deploying with warm-runtime memory rate limiting fallback" >&2
fi

if [[ -n "$TABLE_NAME" ]] && ! aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION" >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION"
  aws dynamodb update-time-to-live \
    --table-name "$TABLE_NAME" \
    --time-to-live-specification Enabled=true,AttributeName=expires_at \
    --region "$REGION" >/dev/null
fi

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_PATH" \
    --region "$REGION" >/dev/null
  aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --handler heart_transplant.beta_lambda.lambda_handler \
    --timeout 240 \
    --memory-size 2048 \
    --ephemeral-storage '{"Size":2048}' \
    --environment "Variables={LOGICLENS_ALLOWED_ORIGINS=$ALLOWED_ORIGINS,LOGICLENS_RATE_LIMIT_TABLE=$TABLE_NAME,HEART_TRANSPLANT_BETA_FETCH_MODE=zipball,HEART_TRANSPLANT_BETA_CACHE=/tmp/logiclens/repos,HEART_TRANSPLANT_ARTIFACT_ROOT=/tmp/logiclens/artifacts}" \
    --region "$REGION" >/dev/null
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler heart_transplant.beta_lambda.lambda_handler \
    --timeout 240 \
    --memory-size 2048 \
    --ephemeral-storage '{"Size":2048}' \
    --zip-file "fileb://$ZIP_PATH" \
    --environment "Variables={LOGICLENS_ALLOWED_ORIGINS=$ALLOWED_ORIGINS,LOGICLENS_RATE_LIMIT_TABLE=$TABLE_NAME,HEART_TRANSPLANT_BETA_FETCH_MODE=zipball,HEART_TRANSPLANT_BETA_CACHE=/tmp/logiclens/repos,HEART_TRANSPLANT_ARTIFACT_ROOT=/tmp/logiclens/artifacts}" \
    --region "$REGION" >/dev/null
  aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
fi

if ! aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --auth-type NONE \
    --region "$REGION" >/dev/null
fi

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id FunctionURLAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region "$REGION" >/dev/null 2>&1 || true

FUNCTION_URL="$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --query FunctionUrl --output text --region "$REGION")"
echo "$FUNCTION_URL"
