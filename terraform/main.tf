provider "aws" {
  region = "us-east-1"  # Change to your region
}

# 🔹 Data Source: Get the Existing Lambda Function
data "aws_lambda_function" "existing_lambda" {
  function_name = "amazon_price_check"  # Replace with your actual Lambda name
}

# 🔹 EventBridge Rule to Trigger Lambda every Friday at 8AM EDT
resource "aws_cloudwatch_event_rule" "lambda_schedule" {
  name                = "lambda-daily-trigger"
  description         = "Triggers Lambda every Friday at 8AM EDT"
  schedule_expression = "cron(0 13 ? * 6 *)"  # Runs every Friday at 13 PM UTC
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
