output "api_endpoint" {
  description = "The HTTP API endpoint URL"
  value       = "${aws_apigatewayv2_stage.prod.invoke_url}/classify"
}

output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = aws_lambda_function.email_classifier.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function"
  value       = aws_lambda_function.email_classifier.arn
}

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_apigatewayv2_api.email_api.id
}