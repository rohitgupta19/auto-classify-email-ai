terraform {
  required_version = ">= 1.2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "email-classifier"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

# IAM role for Lambda
resource "aws_iam_role" "email_classifier_role" {
  name = "email_classifier_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# IAM policy for Bedrock access
resource "aws_iam_role_policy" "bedrock_policy" {
  name = "bedrock_access_policy"
  role = aws_iam_role.email_classifier_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:ListFoundationModels"
      ]
      Resource = "*"
    }]
  })
}

# CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.email_classifier_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function
resource "aws_lambda_function" "email_classifier" {
  filename         = "../src.zip"
  function_name    = "email-classifier"
  role            = aws_iam_role.email_classifier_role.arn
  handler         = "src.lambda.handler.lambda_handler"
  source_code_hash = filebase64sha256("../src.zip")
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 256

  environment {
    variables = {
      GMAIL_CREDENTIALS = var.gmail_credentials
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_iam_role_policy.bedrock_policy
  ]
}

# API Gateway
resource "aws_apigatewayv2_api" "email_api" {
  name          = "email-classifier-api"
  protocol_type = "HTTP"
  description   = "API Gateway for Email Classification Service"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
  }
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.email_api.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip            = "$context.identity.sourceIp"
      requestTime   = "$context.requestTime"
      httpMethod    = "$context.httpMethod"
      routeKey      = "$context.routeKey"
      status        = "$context.status"
      protocol      = "$context.protocol"
      responseTime  = "$context.responseLatency"
    })
  }
}

# CloudWatch log group for API Gateway
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/email-classifier"
  retention_in_days = 14
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id               = aws_apigatewayv2_api.email_api.id
  integration_type     = "AWS_PROXY"
  integration_uri      = aws_lambda_function.email_classifier.invoke_arn
  integration_method   = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "email_route" {
  api_id    = aws_apigatewayv2_api.email_api.id
  route_key = "POST /classify"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.email_classifier.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.email_api.execution_arn}/*/*"
}
