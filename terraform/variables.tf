variable "aws_region" {
  description = "AWS region where resources will be deployed. Must be a region where Bedrock is available."
  type        = string
  default     = "us-east-1"
}

variable "gmail_credentials" {
  description = "Gmail API credentials JSON string. This should be the contents of your OAuth 2.0 client credentials file."
  type        = string
  sensitive   = true
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 14
}