provider "aws" {
  region = "us-east-1"  # Change to your region
}

# 🔹 Data Source: Get the Existing Lambda Function
data "aws_lambda_function" "existing_lambda" {
  function_name = "amazon_price_check"  # Replace with your actual Lambda name
}

# 🔹 IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_execution_role" {
  name = "amazon_price_check_lambda_execution_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# 🔹 IAM Policy for Lambda Basic Execution
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 🔹 IAM Policy for Lambda Services Access
resource "aws_iam_policy" "lambda_services_policy" {
  name        = "amazon_price_check_services_policy"
  description = "Policy for Lambda to access Athena, S3, and related services"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetWorkGroup",
          "athena:ListWorkGroups"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload",
          "s3:PutObject",
          "s3:UploadFile"
        ]
        Resource = [
          "arn:aws:s3:::aws-athena-query-results-*",
          "arn:aws:s3:::aws-athena-query-results-*/*",
          "arn:aws:s3:::amazon-product-price-history",
          "arn:aws:s3:::amazon-product-price-history/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions"
        ]
        Resource = "*"
      }
    ]
  })
}

# 🔹 Attach Services Policy to Lambda Role
resource "aws_iam_role_policy_attachment" "lambda_services_policy" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_services_policy.arn
}

# 🔹 EventBridge Rule to Trigger Lambda every 3 days at 8AM EDT
resource "aws_cloudwatch_event_rule" "lambda_schedule" {
  name                = "lambda-every-3-days-trigger"
  description         = "Triggers Lambda every 3 days at 8AM EDT"
  schedule_expression = "rate(3 days)"  # Runs every 3 days
}

# 🔹 Attach the Lambda Function as a Target for the EventBridge Rule
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.lambda_schedule.name
  target_id = "amazon-price-check-lambda"
  arn       = data.aws_lambda_function.existing_lambda.arn
  depends_on = [aws_lambda_permission.allow_eventbridge] # Explicit dependency
}

# 🔹 Allow EventBridge to Invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvokeLambdaDaily"
  action        = "lambda:InvokeFunction"
  function_name = data.aws_lambda_function.existing_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule.arn
}

# 🔹 Update Lambda Function to use the new execution role
resource "aws_lambda_function" "updated_lambda" {
  function_name = data.aws_lambda_function.existing_lambda.function_name
  role          = aws_iam_role.lambda_execution_role.arn
  
  # Keep existing configuration
  filename         = data.aws_lambda_function.existing_lambda.filename
  source_code_hash = data.aws_lambda_function.existing_lambda.source_code_hash
  runtime          = data.aws_lambda_function.existing_lambda.runtime
  handler          = data.aws_lambda_function.existing_lambda.handler
  timeout          = data.aws_lambda_function.existing_lambda.timeout
  memory_size      = data.aws_lambda_function.existing_lambda.memory_size
  
  # Preserve environment variables if they exist
  dynamic "environment" {
    for_each = data.aws_lambda_function.existing_lambda.environment
    content {
      variables = environment.value.variables
    }
  }
}
